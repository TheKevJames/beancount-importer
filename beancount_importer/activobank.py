import datetime
import re
from collections.abc import Iterator
from typing import Any

import openpyxl
from beancount.core import data

from .utils import Importer


class ActivoBankImporter(Importer):
    _default_currency = 'EUR'
    _require_lastfour = True
    _regex_fname = re.compile(r'^mov\d+(\d{4})-\d+-\d+.xlsx$')

    def _extract_from_row(
            self,
            row: dict[str, Any],
            meta: data.Meta,
    ) -> data.Transaction | None:
        date = row.get('Value Date', row['Data Valor'])
        narration = row.get('Description', row['Descrição'])
        amt = self._amount(str(row.get('Value', row['Valor'])))

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
        if not ws:
            return

        header: tuple[str, str, str, str, str] | None = None
        records: list[tuple[datetime.datetime, datetime.datetime, str, float,
                            float]] = []
        for row in ws.iter_rows(  # type: ignore[attr-defined]
                values_only=True):
            if row[0] in {'Launch Date', 'Data Lanc.'}:
                header = row
                continue
            if not header:
                continue
            records.append(row)
        if not header:
            raise ValueError('malformed workbook')

        rows = [dict(zip(header, x)) for x in records]
        for index, row in enumerate(rows):
            meta = data.new_metadata(fname, index)
            yield self._extract_from_row(row, meta)
