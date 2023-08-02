import datetime
import re
from collections.abc import Iterator
from typing import Any

import openpyxl
from beancount.core import data

from .utils import Importer


class MilleniumBCPImporter(Importer):
    _default_currency = 'EUR'

    regex_fname = re.compile(r'^MOVS_\d_\d+\.xlsx$')

    def _extract_from_row(
            self,
            row: dict[str, Any],
            meta: data.Meta,
    ) -> data.Transaction | None:
        date = row['Transaction record date ']
        narration = row['Description']
        amt = self._amount(str(row['Amount']))

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
            if row[0] == 'Transaction record date ':
                header = row
                continue
            if not header:
                continue
            if isinstance(row[0], str):
                break
            records.append(row)

        rows = [dict(zip(header, x)) for x in records]
        for index, row in enumerate(rows):
            meta = data.new_metadata(fname, index)
            yield self._extract_from_row(row, meta)
