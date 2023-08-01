import re
from dateutil.parser import parse
from typing import Any

from beancount.core import data

from .utils import Importer


class RBCImporter(Importer):
    _default_currency = 'CAD'

    regex_fname = re.compile(r'csv\d+\.csv')

    def __init__(self, account: str, lastfour: str, *, currency: str = 'CAD',
                 account_patterns: None | list[tuple[re.Pattern, str]] = None):
        super().__init__(account, account_patterns=account_patterns,
                         currency=currency)
        self.lastfour = lastfour

    def _extract_from_row(
            self,
            row: dict[str, Any],
            meta: data.Meta,
    ) -> data.Transaction | None:
        if not row['Account Number'].endswith(self.lastfour):
            return None

        date = parse(row['Transaction Date']).date()
        payee: str | None = row['Description 2'].strip()
        payee = payee if payee else None
        narration = row['Description 1']
        amt = self._amount(row['CAD$'])

        return self._transaction(
            meta=meta,
            date=date,
            narration=narration,
            payee=payee,
            postings=[
                self._posting(self.account, amt),
            ],
        )
