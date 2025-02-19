import re
from typing import Any

from beancount.core import data
from dateutil.parser import parse

from .utils import Importer


class RbcImporter(Importer):
    _default_currency = 'CAD'
    _require_lastfour = True
    # N.B. the csv file contains data for *all* accounts, but beangulp doesn't
    # like having multiple configured accounts pointing to the same file. To
    # differentiate, see the `split` command, which breaks apart the merged
    # file into multiple individual subsets containing only the data for a
    # single account.
    # This regex should match the name produced by that method.
    _regex_fname = re.compile(r'rbc(\d{4}).csv\d+\.csv')

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
