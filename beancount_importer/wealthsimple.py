import datetime
import re
from typing import Any

from beancount.core import data

from .utils import Importer


class WealthsimpleImporter(Importer):
    _default_currency = 'CAD'
    _require_lastfour = True
    _regex_fname = re.compile(
        r'^monthly-statement-transactions-[\d\w]{5}([\d\w]{4})CAD[-\d]+.csv$',
    )

    def _extract_from_row(
            self,
            row: dict[str, Any],
            meta: data.Meta,
    ) -> data.Transaction | None:
        date = datetime.datetime.fromisoformat(row['date'])
        narration = row['description']
        amt = self._amount(row['amount'])

        return self._transaction(
            meta=meta,
            date=date.date(),
            narration=narration,
            postings=[
                self._posting(self.account_name, amt),
            ],
        )
