import re
from typing import Any

from beancount.core import data
from dateutil import parser

from . import utils


class TangerineImporter(utils.Importer):
    _default_currency = 'CAD'
    _require_lastfour = True
    _regex_fname = re.compile(r'^(?:\d+ xxxx )?xxxx ?(\d+)\.(?:\d+\.)?CSV$')

    def _extract_from_row(
        self, row: dict[str, Any], meta: data.Meta
    ) -> data.Transaction | None:
        date = parser.parse(row.get('Date') or row['Transaction date']).date()
        payee: str | None = row['Memo'].strip() or None
        narration = row['Name']
        amt = self._amount(row['Amount'])
        if amt == self._amount('0'):
            return None

        return self._transaction(
            meta=meta,
            date=date,
            narration=narration,
            payee=payee,
            postings=[self._posting(self.account_name, amt)],
        )
