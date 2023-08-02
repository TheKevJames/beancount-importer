import os
import re
from dateutil.parser import parse
from typing import Any

from beancount.core import data
from beancount.ingest.cache import _FileMemo as File

from .utils import Importer


class TangerineImporter(Importer):
    _default_currency = 'CAD'

    regex_fname = re.compile(r'^(?:\d+ xxxx )?xxxx ?(\d+)\.CSV$')

    def __init__(self, account: str, lastfour: str, *, currency: str = 'CAD',
                 account_patterns: None | list[tuple[re.Pattern, str]] = None):
        super().__init__(account, account_patterns=account_patterns,
                         currency=currency)
        self.lastfour = lastfour

    def identify(self, f: File) -> bool:
        match = self.regex_fname.match(os.path.basename(f.name))
        return bool(match and self.lastfour == match.group(1))

    def _extract_from_row(
            self,
            row: dict[str, Any],
            meta: data.Meta,
    ) -> data.Transaction | None:
        date = parse(row.get('Date') or row['Transaction date']).date()
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
            postings=[
                self._posting(self.account, amt),
            ],
        )
