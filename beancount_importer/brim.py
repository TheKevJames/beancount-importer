import re
from collections.abc import Callable
from collections.abc import Iterator
from typing import Any

from beancount.core import data
from dateutil.parser import parse

from .utils import Importer


class BrimImporter(Importer):
    _default_currency = 'CAD'
    _regex_fname = re.compile(r'statement-[\dA-Z]+-\d+\.csv')

    def _extract_from_row(
            self,
            row: dict[str, Any],
            meta: data.Meta,
    ) -> data.Transaction | None:
        date = parse(row['Transaction Date']).date()
        narration = row['Description']
        amt = -self._amount(row['Amount'])

        return self._transaction(
            meta=meta,
            date=date,
            narration=narration,
            postings=[
                self._posting(self.account_name, amt),
            ],
        )

    @classmethod
    def howto(
            cls,
            query: Callable[[str], str],
            accounts: list[str],
    ) -> Iterator[str]:
        for account in accounts:
            yield f'Select account {account}'

            date = query(account)
            yield f'For each billing period since {date}'
            yield 'Export as Activity > Statements > Download CSV'
