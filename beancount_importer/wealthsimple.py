import datetime
import decimal
import re
from typing import Any

from beancount.core import data
from beancount.core import flags
from beancount.core import position
from beancount.core.number import MISSING

from .utils import Importer

# `{}`: an empty cost that defers lot selection to booking (FIFO). MISSING is
# beancount's interpolation sentinel, typed as Any here since the stubs narrow
# the CostSpec fields to Decimal/str.
_MISSING: Any = MISSING
_EMPTY_COST = position.CostSpec(_MISSING, None, _MISSING, None, None, False)


class WealthsimpleCreditCardImporter(Importer):
    _default_currency = 'CAD'
    _require_lastfour = False
    _regex_fname = re.compile(
        r'^credit-card-statement-transactions-\d{4}-\d{2}-\d{2}.csv$'
    )

    def _extract_from_row(
        self, row: dict[str, Any], meta: data.Meta
    ) -> data.Transaction | None:
        date = datetime.datetime.fromisoformat(row['transaction_date'])
        narration = row['details']
        amt = self._amount(row['amount'], row['currency'])

        kind = row['type']
        if kind in {'Refund initiated', 'Refund settled'}:
            narration = f'{narration} (refund)'

        if kind not in {
            'Payment',
            'Purchase',
            'Refund initiated',
            'Refund settled',
        }:
            print(row)
            assert False, f'invalid type {kind}'

        return self._transaction(
            meta=meta,
            date=date.date(),
            narration=narration,
            postings=[self._posting(self.account_name, -amt)],
        )


class WealthsimpleImporter(Importer):
    _default_currency = 'CAD'
    _require_lastfour = True
    _regex_fname = re.compile(
        r'^(?:\w+\-)?monthly-statement-transactions-'
        r'[\d\w]{5}([\d\w]{4})\w{3}[-\d]+.csv$'
    )

    # Structured cash flows on investment accounts route to a derived
    # income/expense account: activity_type -> (root, leaf).
    _CASH_ACCOUNTS = {
        'Dividend': ('Income', 'Dividends'),
        'Interest': ('Income', 'Interest'),
        'Tax': ('Expenses', 'Taxes'),
    }

    @property
    def _is_investment(self) -> bool:
        """
        Investment accounts hold securities and split cash by currency.

        Cash/savings accounts post directly to the account; Trade/Managed
        accounts route cash to a `:<CUR>` subaccount and income/PnL to a
        `:<CUR>:<leaf>` account.
        """
        return bool({'Trade', 'Managed'} & set(self.account_name.split(':')))

    def _related(self, root: str, currency: str, leaf: str) -> str:
        rest = self.account_name.split(':', 1)[1]
        return f'{root}:{rest}:{currency}:{leaf}'

    def _parse_trade(self, row: dict[str, Any]) -> list[data.Posting]:
        symbol = row['symbol'].replace('.', '')
        currency = row['currency']
        qty = self._amount(row['quantity'], symbol)
        price = self._amount(row['unit_price'], currency)
        net = self._amount(row['net_cash_amount'], currency)
        commission = decimal.Decimal(row['commission'] or 0)

        buying = qty.number is not None and qty.number > 0
        # Augmentations carry the whole basis as an explicit total cost
        # (`{# TOTAL CUR}`): currency explicit, exact, never quoted and never
        # inferred from the price currency. The commission is excluded from the
        # basis (Rule 6). Reductions defer lot selection to FIFO booking.
        if buying:
            assert net.number is not None
            basis = abs(net.number) - commission
            cost = position.CostSpec(None, basis, currency, None, None, False)
        else:
            cost = _EMPTY_COST
        postings = [
            self._posting(
                f'{self.account_name}:{symbol}', qty, cost=cost, price=price
            )
        ]
        if commission:
            postings.append(
                self._posting(
                    self._related('Expenses', currency, 'Commissions'),
                    self._amount(commission, currency),
                )
            )
        postings.append(self._posting(f'{self.account_name}:{currency}', net))
        if not buying:
            postings.append(
                self._posting(self._related('Income', currency, 'PnL'), None)
            )
        return postings

    def _parse_income(
        self, row: dict[str, Any], root: str, leaf: str
    ) -> list[data.Posting]:
        currency = row['currency']
        amt = self._amount(row['net_cash_amount'], currency)
        return [
            self._posting(f'{self.account_name}:{currency}', amt),
            self._posting(self._related(root, currency, leaf), None),
        ]

    def _parse_transfer(self, row: dict[str, Any]) -> list[data.Posting]:
        currency = row['currency']
        amt = self._amount(row['net_cash_amount'], currency)
        return [
            self._posting(f'{self.account_name}:{currency}', amt),
            self._posting('Equity:Transfer', None),
        ]

    def _parse_flagged(
        self, row: dict[str, Any], narration: str, symbol: str
    ) -> tuple[str, list[data.Posting]]:
        # Corporate actions, returns of capital and security transfers can't be
        # booked from a single row without the full holdings; emit a flagged,
        # non-bookable stub carrying the raw delta for manual reconciliation.
        currency = row['currency'] or self.currency
        delta = f'{row["quantity"]} {symbol}'.strip()
        narration = f'{narration} ({delta}): TODO handle manually'
        stub = self._posting(
            self.default_equity_account, self._amount('0', currency)
        )
        return narration, [stub]

    def _parse_activity(
        self, row: dict[str, Any]
    ) -> tuple[str, list[data.Posting], data.Flag]:
        atype = row['activity_type']
        sub = row['activity_sub_type']
        direction = row['direction']
        symbol = row['symbol'].replace('.', '') if row['symbol'] else ''

        narration = atype
        if sub and sub != '-':
            narration = f'{narration}: {sub}'

        # Security movements: trades and reinvested dividends (DRIP).
        if (atype == 'Trade' and sub in {'BUY', 'SELL'}) or (
            atype == 'Dividend' and direction
        ):
            narration = f'{narration} ({symbol} {direction.lower()})'
            return narration, self._parse_trade(row), flags.FLAG_OKAY

        if self._is_investment:
            if atype == 'MoneyMovement':
                return narration, self._parse_transfer(row), flags.FLAG_OKAY
            if atype in self._CASH_ACCOUNTS:
                root, leaf = self._CASH_ACCOUNTS[atype]
                if atype == 'Dividend' and symbol:
                    narration = f'{narration} ({symbol})'
                income = self._parse_income(row, root, leaf)
                return narration, income, flags.FLAG_OKAY
            narration, postings = self._parse_flagged(row, narration, symbol)
            return narration, postings, flags.FLAG_WARNING

        # Cash/savings accounts: single leg, let residual-balancing categorize.
        if symbol:
            narration = f'{narration} ({symbol})'
        amt = self._amount(row['net_cash_amount'], row['currency'])
        return (
            narration,
            [self._posting(self.account_name, amt)],
            flags.FLAG_OKAY,
        )

    def _extract_from_row(
        self, row: dict[str, Any], meta: data.Meta
    ) -> data.Transaction | None:
        flag = flags.FLAG_OKAY
        try:
            # monthly statement
            date = datetime.datetime.fromisoformat(row['date'])
            narration = row['description']
            # TODO: read currency from the row rather than defaulting
            postings = [
                self._posting(self.account_name, self._amount(row['amount']))
            ]
        except KeyError:
            # activities export
            date = datetime.datetime.fromisoformat(row['effective_date'])
            narration, postings, flag = self._parse_activity(row)

        return self._transaction(
            meta=meta,
            date=date.date(),
            narration=narration,
            postings=postings,
            flag=flag,
        )
