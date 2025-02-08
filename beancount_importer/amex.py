import re
from typing import Any

from beancount.core import data
from dateutil.parser import parse

from .utils import Importer


class AmexImporter(Importer):
    _default_currency = 'USD'
    _regex_fname = re.compile(r'Transactions.*\.csv')

    def _extract_from_row(
            self,
            row: dict[str, Any],
            meta: data.Meta,
    ) -> data.Transaction:
        # TODO: check if splitting is necessary
        date = parse(row['Date'].split(' ')[0]).date()
        # TODO: parse out payee vs narration?
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
