import datetime
import re
from collections.abc import Iterator
from typing import Any
from typing import cast
from typing import TypeAlias

import openpyxl
from beancount.core import data
from openpyxl.worksheet.worksheet import Worksheet

from .utils import Importer


Header: TypeAlias = tuple[str, str, str, str, str]
Row: TypeAlias = tuple[datetime.datetime, datetime.datetime, str, float, float]


class ActivobankImporter(Importer):
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
                self._posting(self.account_name, amt),
            ],
        )

    def _extract(self, fname: str) -> Iterator[None]:
        # TODO(perf): check out
        # https://github.com/ericgazoni/openpyxl/blob/c55988e4904d4337ce4c35ab8b7dc305bca9de23/doc/source/optimized.rst#L15
        wb = openpyxl.load_workbook(fname)
        ws = cast(Worksheet, wb.active)
        if not ws:
            return

        header: Header | None = None
        records: list[Row] = []
        for raw in ws.iter_rows(values_only=True):
            if raw[0] in {'Launch Date', 'Data Lanc.'}:
                header = raw  # type: ignore[assignment]
                continue
            if not header:
                continue
            records.append(raw)  # type: ignore[arg-type]
        if not header:
            raise ValueError('malformed workbook')

        rows = [dict(zip(header, x)) for x in records]
        for index, row in enumerate(rows):
            meta = data.new_metadata(fname, index)
            yield self._extract_from_row(row, meta)
