import os
import re
from typing import Any

from beancount.core import data
from dateutil.parser import parse

from .utils import Importer


class RbcImporter(Importer):
    _default_currency = 'CAD'
    _require_lastfour = True
    _regex_fname = re.compile(r'csv\d+\.csv')

    def identify(self, fname: str) -> bool:
        # TODO: _require_lastfour but not in filename? Mock the filename?
        return bool(self._regex_fname.match(os.path.basename(fname)))

    def _extract_from_row(
            self,
            row: dict[str, Any],
            meta: data.Meta,
    ) -> data.Transaction | None:
        if not row['Account Number'].endswith(self.lastfour):
            return None

        date = parse(row['Transaction Date']).date()
        payee: str | None = row['Description 2'].strip() or None
        narration = row['Description 1']
        amt = self._amount(row['CAD$'])

        return self._transaction(
            meta=meta,
            date=date,
            narration=narration,
            payee=payee,
            postings=[
                self._posting(self.account_name, amt),
            ],
        )
