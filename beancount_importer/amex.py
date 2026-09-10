import re
from typing import Any

from beancount.core import data
from dateutil import parser

from . import utils


class AmexImporter(utils.Importer):
    _default_currency = 'USD'
    _regex_fname = re.compile(r'Transactions.*\.csv')

    def _extract_from_row(
        self, row: dict[str, Any], meta: data.Meta
    ) -> data.Transaction:
        # TODO: confirm whether the Date column can carry a time component;
        # if it only ever holds the day, this split(' ')[0] is unnecessary.
        date = parser.parse(row['Date'].split(' ')[0]).date()
        # TODO: parse out payee vs narration?
        narration = row['Description']
        amt = -self._amount(row['Amount'])

        return self._transaction(
            meta=meta,
            date=date,
            narration=narration,
            postings=[self._posting(self.account_name, amt)],
        )
