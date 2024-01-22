import re
from typing import Any

from beancount.core import data
from dateutil.parser import parse

from .utils import Importer


class ChaseImporter(Importer):
    _default_currency = 'USD'
    _require_lastfour = True
    _regex_fname = re.compile(
        r'Chase(\d{4})_Activity([\d]+_)*[\d]+.CSV',
        re.IGNORECASE,
    )

    regex_desc_full = re.compile(
        (
            r'ORIG CO NAME:(.+?)\s*ORIG ID:.*DESC DATE:.*CO ENTRY '
            r'DESCR:(.+?)\s*SEC:.*TRACE#:.*EED:.*'
        ),
        re.IGNORECASE,
    )
    regex_desc_generic = re.compile(
        r'(.+?)\s+(PPD|WEB) ID: \d+', re.IGNORECASE,
    )
    regex_desc_inbound_tx = re.compile(
        r'Online Transfer \d+ from (.+?)\s*transaction #', re.IGNORECASE,
    )
    regex_desc_outbound_tx = re.compile(
        r'Online Transfer \d+ to (.+?)\s*transaction #', re.IGNORECASE,
    )

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
        # TODO: move to base class
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
