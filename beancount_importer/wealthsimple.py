import datetime
import re
from typing import Any

from beancount.core import data
from beancount.core import position

from .utils import Importer


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

    def _parse_stock_row(
        self, date: datetime.datetime, row: dict[str, Any]
    ) -> list[data.Posting]:
        symbol = row['symbol'].replace('.', '')
        amt = self._amount(row['quantity'], symbol)

        # Corporate actions (splits, consolidations) only adjust the share
        # count and carry no cash leg, price or currency.
        if not row['net_cash_amount']:
            return [self._posting(f'{self.account_name}:{symbol}', amt)]

        currency = row['currency']
        price = self._amount(row['unit_price'], currency)

        # When selling, we want to pick the cost basis
        kind = row['activity_sub_type']
        date_ = date.date() if kind == 'BUY' else None
        label = price if kind == 'BUY' else None

        cost = position.Cost(
            row['unit_price'],
            currency,
            date_,  # type: ignore[arg-type]
            label,  # type: ignore[arg-type]
        )
        total = self._amount(row['net_cash_amount'], currency)

        return [
            self._posting(
                f'{self.account_name}:{symbol}', amt, price=price, cost=cost
            ),
            self._posting(f'{self.account_name}:{currency}', total),
        ]

    def _extract_from_row(
        self, row: dict[str, Any], meta: data.Meta
    ) -> data.Transaction | None:
        postings: list[data.Posting] = []
        try:
            # monthly statement
            date = datetime.datetime.fromisoformat(row['date'])
            narration = row['description']
            amt = self._amount(row['amount'])  # TODO: currency?
        except KeyError:
            # synthetic data from split()
            date = datetime.datetime.fromisoformat(row['effective_date'])
            narration = row['activity_type']

            kind = row['activity_sub_type']
            if kind and kind != '-':
                narration = f'{narration}: {kind}'

            symbol = row['symbol'].replace('.', '')
            # A direction (LONG/SHORT) marks a change in a share position;
            # everything else (dividends, interest, tax, transfers) is cash,
            # even when it references a symbol.
            if row['direction']:
                details = ' '.join((symbol, row['direction'].lower()))
                narration = f'{narration} ({details})'
                postings = self._parse_stock_row(date, row)
            else:
                if symbol:
                    narration = f'{narration} ({symbol})'
                amt = self._amount(row['net_cash_amount'], row['currency'])

        postings = postings or [self._posting(self.account_name, amt)]
        return self._transaction(
            meta=meta, date=date.date(), narration=narration, postings=postings
        )
