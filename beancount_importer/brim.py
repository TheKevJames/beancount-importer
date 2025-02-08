import re
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
