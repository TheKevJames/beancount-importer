import re
from typing import Any

from beancount.core import data
from dateutil import parser

from . import utils


class RevolutImporter(utils.Importer):
    _default_currency = 'EUR'
    _require_lastfour = True
    _regex_fname = re.compile(
        r'account-statement.*_en-gb_[\d\w]{2}([\d\w]{4})\.csv'
    )

    def _extract_from_row(
        self, row: dict[str, Any], meta: data.Meta
    ) -> data.Transaction:
        try:
            date = parser.parse(row['Data de Conclusão'].strip()).date()
            # TODO: parse out payee vs narration?
            narration = row['Descrição'].strip()
            amt_raw = row['Montante'].replace("'", '').strip()
            amt = self._amount(amt_raw, row['Moeda'])
        except KeyError:
            date = parser.parse(row['Completed Date'].strip()).date()
            # TODO: parse out payee vs narration?
            narration = row['Description'].strip()
            amt_raw = row['Amount'].replace("'", '').strip()
            amt = self._amount(amt_raw, row['Currency'])

        return self._transaction(
            meta=meta,
            date=date,
            narration=narration,
            postings=[self._posting(self.account_name, amt)],
        )
