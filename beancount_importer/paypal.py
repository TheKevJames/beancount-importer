import csv
import datetime
import os
from collections.abc import Iterable
from collections.abc import Iterator
from dateutil.parser import parse
from typing import Any

import titlecase
from beancount.core.number import D
from beancount.core import amount
from beancount.core import flags
from beancount.core import data
from beancount.ingest.importer import ImporterProtocol
from beancount.ingest.cache import _FileMemo as File


MetaTuple = tuple[datetime.datetime, dict[str, int | str], str, str,
                  amount.Amount]


class PaypalImporter(ImporterProtocol):
    # TODO: categorization support
    def __init__(self, account: str) -> None:
        self.account = account
        self.category = 'Expenses:Unknown'

    def file_account(self, _f: File) -> str:
        return self.account

    @staticmethod
    def _get_date(row: dict[str, Any]) -> str:
        # TODO: wtf
        value = row.get('\ufeff"Date"')
        if value is not None:
            return value
        return row['Date']

    def file_date(self, f: File) -> datetime.datetime | None:
        with open(f.name, encoding='utf-8') as f:
            dates: list[datetime.datetime] = []
            for row in csv.DictReader(f):
                dates.append(parse(self._get_date(row)).date())
            return max(dates)

        return None

    def identify(self, f: File) -> bool:
        return os.path.basename(f.name) == 'Download.CSV'

    def _extract(self, fname: str) -> Iterator[MetaTuple]:
        with open(fname, encoding='utf-8') as f:
            for index, row in enumerate(csv.DictReader(f)):
                if row['Status'] != 'Completed':
                    continue

                date = parse(self._get_date(row)).date()
                kind = titlecase.titlecase(row['Type'])
                name = titlecase.titlecase(row['Name'])
                amt = amount.Amount(D(row['Amount']), row['Currency'])

                meta = data.new_metadata(fname, index)
                yield (date, meta, name, kind, amt)

        # TODO: append data.Balance() record

    @staticmethod
    def _is_conversion(transaction: MetaTuple, x: MetaTuple) -> bool:
        date, _, name, kind, amt = x
        if date != transaction[0]:
            return False

        if not name and kind == 'General Currency Conversion':
            return True
        if name == 'PayPal' and kind == 'Reversal of General Account Hold':
            return True
        if name == transaction[2] and kind == 'General Authorization':
            return True

        return False

    def _group(self, xs: Iterable[MetaTuple]) -> Iterator[list[MetaTuple]]:
        data: list[MetaTuple] = []
        for x in xs:
            date, meta, name, kind, amt = x
            if data:
                if self._is_conversion(data[0], x):
                    data.append(x)
                    continue

                yield data
                data = []

            data.append(x)

        if data:
            yield data

    def _consolidate_conversions(self, xs: list[MetaTuple]) -> list[data.Posting]:
        """
        Turn a set of records into one Posting with a conversion.

        Assumes xs[0] is the source-of-truth expense.
        """
        expense = xs[0]
        cost: amount.Amount | None = None
        for x in xs:
            if x[4] == expense[4] or x[4] == -expense[4]:
                continue
            if expense[4].number < 0 and x[4].number >= 0:
                continue
            if expense[4].number >= 0 and x[4].number < 0:
                continue
            cost = x[4]
            break
        else:
            raise ValueError('could not parse conversion postings for %s', xs)

        # At this point, f"{-expense[4]} @@ {-cost}" would be correct.
        # TODO: emit @@ Postings directly.

        # TODO: fetch option account_current_conversions
        # https://beancount.github.io/docs/beancount_options_reference.html
        conv = 'Equity:Conversions:Current'
        return [
            data.Posting(self.category, -expense[4], None, None, None, None),
            data.Posting(self.account, cost, None, None, None, None),
            data.Posting(conv, None, None, None, None, None),
        ]

    def _merge(
            self,
            xss: Iterable[list[MetaTuple]],
    ) -> Iterator[data.Transaction]:
        for xs in xss:
            postings = self._consolidate_conversions(xs)

            date, meta, payee, narration, _ = xs[0]
            yield data.Transaction(
                meta=meta,
                date=date,
                flag=flags.FLAG_OKAY,
                payee=payee,
                narration=narration,
                tags=set(),
                links=set(),
                postings=postings,
            )

    def extract(self, f: File) -> list[data.Transaction]:
        return list(self._merge(self._group(self._extract(f.name))))
