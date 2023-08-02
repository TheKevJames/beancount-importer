import datetime
import os
import re
from collections.abc import Iterator
from typing import Any

import openpyxl
from beancount.core import data
from beancount.ingest.cache import _FileMemo as File

from .utils import Importer


class ActivoBankImporter(Importer):
    _default_currency = 'EUR'

    regex_fname = re.compile(r'^mov\d+(\d{4})-\d+-\d+.xlsx$')

    def __init__(self, account: str, lastfour: str, *, currency: str = 'EUR',
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
        date = row['Value Date']
        narration = row['Description']
        amt = self._amount(str(row['Value']))

        return self._transaction(
            meta=meta,
            date=date.date(),
            narration=narration,
            postings=[
                self._posting(self.account, amt),
            ],
        )

    def _extract(self, fname: str) -> Iterator[None]:
        wb = openpyxl.load_workbook(fname)
        ws = wb.active

        header: tuple[str, str, str, str, str] | None = None
        records: list[tuple[datetime.datetime, datetime.datetime, str, float,
                            float]] = []
        for row in ws.iter_rows(values_only=True):
            if row[0] == 'Launch Date':
                header = row
                continue
            if not header:
                continue
            records.append(row)

        rows = [dict(zip(header, x)) for x in records]
        for index, row in enumerate(rows):
            meta = data.new_metadata(fname, index)
            yield self._extract_from_row(row, meta)
