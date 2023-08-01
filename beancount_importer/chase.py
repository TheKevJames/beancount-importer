import os
import re
from dateutil.parser import parse
from typing import Any

from beancount.core import data
from beancount.ingest.cache import _FileMemo as File

from .utils import Importer


class ChaseImporter(Importer):
    _default_currency = 'USD'

    regex_fname = re.compile(r'Chase(\d{4})_Activity([\d]+_)*[\d]+.CSV',
                             re.IGNORECASE)

    regex_desc_full = re.compile(
        (r'ORIG CO NAME:(.+?)\s*ORIG ID:.*DESC DATE:.*CO ENTRY DESCR:(.+?)\s*'
         r'SEC:.*TRACE#:.*EED:.*'),
        re.IGNORECASE)
    regex_desc_generic = re.compile(
        r'(.+?)\s+(PPD|WEB) ID: \d+', re.IGNORECASE)
    regex_desc_inbound_tx = re.compile(
        r'Online Transfer \d+ from (.+?)\s*transaction #', re.IGNORECASE)
    regex_desc_outbound_tx = re.compile(
        r'Online Transfer \d+ to (.+?)\s*transaction #', re.IGNORECASE)

    def __init__(self, account: str, lastfour: str, *, currency: str = 'USD',
                 account_patterns: None | list[tuple[re.Pattern, str]] = None):
        super().__init__(account, account_patterns=account_patterns,
                         currency=currency)
        self.lastfour = lastfour

    def identify(self, f: File) -> bool:
        match = self.regex_fname.match(os.path.basename(f.name))
        return bool(match and self.lastfour == match.group(1))

    def _parse_description(self, description: str) -> tuple[str | None, str]:
        match = self.regex_desc_full.search(description)
        if match:
            return match.group(1), match.group(2)
        match = self.regex_desc_outbound_tx.search(description)
        if match:
            return match.group(1), description
        match = self.regex_desc_inbound_tx.search(description)
        if match:
            return match.group(1), description
        match = self.regex_desc_generic.search(description)
        if match:
            return None, match.group(1)
        return None, description

    def _extract_from_row(
            self,
            row: dict[str, Any],
            meta: data.Meta,
    ) -> data.Transaction | None:
        date = parse(row['Posting Date']).date()
        payee, narration = self._parse_description(row['Description'])
        amt = self._amount(row['Amount'])
        if amt == self._amount('0'):
            return None

        return self._transaction(
            meta=meta,
            date=date,
            payee=payee,
            narration=narration,
            postings=[
                self._posting(self.account, amt),
            ],
        )
