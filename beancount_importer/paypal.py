import csv
import datetime
import re
from collections.abc import Iterable
from collections.abc import Iterator
from typing import Any
from typing import cast

import titlecase
from beancount.core import amount
from beancount.core import data
from beancount.core.number import D
from dateutil.parser import parse

from .utils import Importer


MetaTuple = tuple[
    datetime.datetime, dict[str, int | str], str, str,
    amount.Amount,
]


class PaypalImporter(Importer):
    # TODO: refactor to reuse some base class stuff
    # pylint: disable=abstract-method
    _regex_fname = re.compile(r'Download.CSV')

    @staticmethod
    def _get_date(row: dict[str, Any]) -> str:
        # TODO: wtf
        value: str | None = row.get('\ufeff"Date"')
        if value is not None:
            return value
        return cast(str, row['Date'])

    def _extractz(self, fname: str) -> Iterator[MetaTuple]:
        with open(fname, encoding='utf-8') as f:
            for index, row in enumerate(csv.DictReader(f)):
                if row['Status'] != 'Completed':
                    continue

                date = parse(self._get_date(row)).date()
                kind = titlecase.titlecase(row['Type'])
                name = titlecase.titlecase(row['Name'])
                amt = amount.Amount(D(row['Amount']), row['Currency'])

                meta = data.new_metadata(fname, index)
                yield cast(MetaTuple, (date, meta, name, kind, amt))

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
        if (
            name == transaction[2] and kind == 'General Authorization'
            and amt == transaction[4]
        ):
            return True

        return False

    def _group(self, xs: Iterable[MetaTuple]) -> Iterator[list[MetaTuple]]:
        batch: list[MetaTuple] = []
        for x in xs:
            if batch:
                if self._is_conversion(batch[0], x):
                    batch.append(x)
                    continue

                yield batch
                batch = []

            batch.append(x)

        if batch:
            yield batch

    def _consolidate_conversions(
        self,
        xs: list[MetaTuple],
    ) -> list[data.Posting]:
        """
        Turn a set of records into one Posting with a conversion.

        Assumes xs[0] is the source-of-truth expense.
        """
        expense = xs[0]
        cost: amount.Amount | None = None
        for x in xs:
            if x[4] in (expense[4], -expense[4]):
                continue

            # TODO: handle these checks better
            assert expense[4].number
            assert x[4].number
            if expense[4].number < 0 <= x[4].number:
                continue
            if expense[4].number >= 0 > x[4].number:
                continue
            cost = x[4]
            break
        else:
            raise ValueError(f'could not parse conversion postings for {xs}')

        # At this point, f"{-expense[4]} @@ {-cost}" would be correct.
        # TODO: emit @@ Postings directly.

        # TODO: fetch option account_current_conversions
        # https://beancount.github.io/docs/beancount_options_reference.html
        conv = 'Equity:Conversions:Current'
        # TODO: integrate with account_patterns
        category = 'Expenses:Unknown'
        return [
            self._posting(category, -expense[4]),
            self._posting(self.account_name, cost),
            self._posting(conv, None),
        ]

    def _merge(
            self,
            xss: Iterable[list[MetaTuple]],
    ) -> Iterator[data.Transaction]:
        for xs in xss:
            postings = self._consolidate_conversions(xs)

            date, meta, payee, narration, _ = xs[0]
            yield self._transaction(
                meta=meta,
                date=date,
                payee=payee,
                narration=narration,
                postings=postings,
            )

    def extract(
            self,
            fname: str,
            _existing: list[data.Transaction],
    ) -> list[data.Transaction]:
        return list(self._merge(self._group(self._extractz(fname))))
