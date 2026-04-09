import datetime
import re
from typing import Any

from beancount.core import data
from beancount.core import position

from .utils import Importer


class WealthsimpleImporter(Importer):
    _default_currency = 'CAD'
    _require_lastfour = True
    _regex_fname = re.compile(
        r'^(?:\w+\-)?monthly-statement-transactions-'
        r'[\d\w]{5}([\d\w]{4})\w{3}[-\d]+.csv$',
    )

    def _parse_stock_row(
            self,
            date: datetime.datetime,
            row: dict[str, Any],
    ) -> list[data.Posting]:
        price = self._amount(row['unit_price'], row['currency'])

        # When selling, we want to pick the cost basis
        kind = row['activity_sub_type']
        date_ = date.date() if kind == 'BUY' else None
        label = price if kind == 'BUY' else None

        symbol = row['symbol'].replace('.', '')
        cost = position.Cost(row['unit_price'], row['currency'], date_, label)
        amt = self._amount(row['quantity'], symbol)
        total = self._amount(row['net_cash_amount'], row['currency'])

        postings = [
            self._posting(
                f'{self.account_name}:{symbol}',
                amt,
                price=price,
                cost=cost,
            ),
            self._posting(f'{self.account_name}:{row["currency"]}', total),
        ]
        if kind == 'SELL':
            postings.append(
                self._posting(
                    f'{self.account_name}:{row["currency"]}:PnL',
                    None,
                ),
            )
            pass
        return postings

    def _extract_from_row(
            self,
            row: dict[str, Any],
            meta: data.Meta,
    ) -> data.Transaction | None:
        postings: list[data.Posting] = []
        try:
            # monthly statement
            date = datetime.datetime.fromisoformat(row['date'])
            narration = row['description']
            amt = self._amount(row['amount'])  # TODO: currency?
        except KeyError:
            # synthetic data from split()
            date = datetime.datetime.fromisoformat(row['transaction_date'])
            narration = row['activity_type']

            kind = row['activity_sub_type']
            if kind:
                narration = f'{narration}: {kind}'

            symbol = row['symbol'].replace('.', '')
            if symbol:
                # stock trade
                direction = row['direction']
                if direction:
                    details = ' '.join((symbol, direction.lower()))
                    narration = f'{narration} ({details})'
                    postings = self._parse_stock_row(date, row)
                else:
                    narration = f'{narration} ({symbol})'
                    amt = self._amount(row['quantity'], symbol)
                    postings = [
                        self._posting(f'{self.account_name}:{symbol}', amt),
                    ]
            else:
                amt = self._amount(row['net_cash_amount'], row['currency'])

        postings = postings or [
            self._posting(self.account_name, amt),
        ]
        return self._transaction(
            meta=meta,
            date=date.date(),
            narration=narration,
            postings=postings,
        )
