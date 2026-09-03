import datetime
import re
from collections.abc import Iterator
from typing import Any

import xlrd
from beancount.core import data

from .utils import Importer


class SantanderImporter(Importer):
    _default_currency = 'EUR'
    _require_lastfour = True
    _regex_fname = re.compile(r'^descarga\.(\w+)\.xls$')

    def _extract_from_row(
        self, row: dict[str, Any], meta: data.Meta
    ) -> data.Transaction:
        date = datetime.datetime.strptime(row['Date'], '%d-%m-%Y').date()
        narration = row['Description']
        amt = self._amount(str(row['Amount']))

        return self._transaction(
            meta=meta,
            date=date,
            narration=narration,
            postings=[self._posting(self.account_name, amt)],
        )

    def _find_columns(self, ws: Any) -> tuple[int, int, int, int]:
        for r in range(ws.nrows):
            cells = [str(ws.cell_value(r, c)).strip() for c in range(ws.ncols)]
            dates = [c for c, v in enumerate(cells) if v.startswith('Data ')]
            amounts = [
                c for c, v in enumerate(cells) if v.startswith('Montante')
            ]
            if not dates or 'Descrição' not in cells or not amounts:
                continue
            return r, dates[0], cells.index('Descrição'), amounts[0]

        raise ValueError('malformed workbook')

    def _extract(self, fname: str) -> Iterator[data.Transaction]:
        ws = xlrd.open_workbook(fname).sheet_by_index(0)
        header_row, date_col, desc_col, amt_col = self._find_columns(ws)

        index = 0
        for r in range(header_row + 1, ws.nrows):
            date = str(ws.cell_value(r, date_col)).strip()
            if not date:
                continue

            row = {
                'Date': date,
                'Description': str(ws.cell_value(r, desc_col)).strip(),
                'Amount': ws.cell_value(r, amt_col),
            }
            meta = data.new_metadata(fname, index)
            yield self._extract_from_row(row, meta)
            index += 1
