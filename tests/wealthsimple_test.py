import pathlib

from beancount import loader
from beancount.core import amount
from beancount.core import data
from beancount.core import number
from beancount.core import position
from beancount.parser import printer

from beancount_importer import wealthsimple

FIXTURES = pathlib.Path(__file__).parent / 'fixtures'
ACCOUNT = 'Assets:CA:Wealthsimple:Trade:Stocks'
FIXTURE = 'wealthsimple-trade-activities.csv'


def _extract(account: str = ACCOUNT) -> list[data.Directive]:
    return wealthsimple.WealthsimpleImporter(account, lastfour='7K05').extract(
        str(FIXTURES / FIXTURE), []
    )


def _txn(entries: list[data.Directive], needle: str) -> data.Transaction:
    return next(
        e
        for e in entries
        if isinstance(e, data.Transaction)
        and e.narration
        and needle in e.narration
    )


def _posting(txn: data.Transaction, account_fragment: str) -> data.Posting:
    return next(p for p in txn.postings if account_fragment in p.account)


def _cost(txn: data.Transaction, account_fragment: str) -> position.CostSpec:
    cost = _posting(txn, account_fragment).cost
    assert isinstance(cost, position.CostSpec)
    return cost


def _qty(txn: data.Transaction, account_fragment: str) -> number.Decimal:
    units: amount.Amount | None = _posting(txn, account_fragment).units
    assert units is not None and units.number is not None
    return units.number


def test_buy_carries_explicit_total_cost() -> None:
    buy = _txn(_extract(), 'BUY')
    cost = _cost(buy, ':VFV')
    # {# TOTAL CUR}: explicit currency, whole basis, never quoted/inferred.
    assert cost.number_per is None
    assert cost.number_total == number.D('3000')
    assert cost.currency == 'CAD'
    # No residual leaked to a flagged default account.
    assert all('Unknown' not in p.account for p in buy.postings)


def test_drip_books_as_a_buy() -> None:
    drip = _txn(_extract(), 'Dividend Reinvested')
    assert _qty(drip, ':VFV') > 0
    cost = _cost(drip, ':VFV')
    assert cost.number_total == number.D('12.10')
    assert cost.currency == 'CAD'


def test_sell_defers_lot_to_fifo_and_books_pnl() -> None:
    sell = _txn(_extract(), 'SELL')
    assert _qty(sell, ':VFV') < 0
    # `{}` empty cost -> FIFO booking picks the lot at disposal.
    assert '-5.00 VFV {} @ 160.00 CAD' in printer.format_entry(sell)
    pnl = _posting(sell, ':PnL')
    assert pnl.account == 'Income:CA:Wealthsimple:Trade:Stocks:CAD:PnL'
    assert pnl.units is None  # interpolated at booking


def test_cash_flows_derive_income_and_expense_accounts() -> None:
    entries = _extract()
    assert (
        _posting(_txn(entries, 'Dividend (VFV)'), ':Dividends').account
        == 'Income:CA:Wealthsimple:Trade:Stocks:CAD:Dividends'
    )
    assert (
        _posting(_txn(entries, 'Interest'), ':Interest').account
        == 'Income:CA:Wealthsimple:Trade:Stocks:CAD:Interest'
    )
    assert (
        _posting(_txn(entries, 'Tax'), ':Taxes').account
        == 'Expenses:CA:Wealthsimple:Trade:Stocks:USD:Taxes'
    )


def test_transfer_routes_to_equity_transfer() -> None:
    transfer = _txn(_extract(), 'MoneyMovement')
    assert _posting(transfer, 'Equity:Transfer').account == 'Equity:Transfer'


def test_unbookable_events_are_flagged_and_touch_no_lots() -> None:
    for needle in (
        'CorporateAction',
        'ReturnOfCapital',
        'InternalSecurityTransfer',
    ):
        txn = _txn(_extract(), needle)
        assert txn.flag == '!'
        assert txn.narration and 'TODO' in txn.narration
        # Never a bare at-cost reduction against the holding.
        assert all(
            ':VFV' not in p.account and p.cost is None for p in txn.postings
        )


def test_extracted_ledger_books_cleanly_under_fifo() -> None:
    entries = _extract()
    accounts = {p.account for e in entries for p in getattr(e, 'postings', [])}
    header = ['option "booking_method" "FIFO"']
    header += [f'2026-01-01 open {a}' for a in sorted(accounts)]
    body = ''.join(printer.format_entry(e) for e in entries)
    ledger = '\n'.join(header) + '\n' + body
    _, errors, _ = loader.load_string(ledger)
    assert not errors, [e.message for e in errors]
