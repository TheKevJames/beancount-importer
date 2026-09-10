import operator
import re
from collections.abc import Iterator
from typing import Any

import pdfplumber
import pdfplumber.page
from beancount.core import data
from dateutil import parser

from . import utils

Word = dict[str, Any]

_HEADERS = ('Date', 'Description', 'Withdrawals', 'Deposits', 'Balance')
_FOOTER_ANCHOR = 'Equitable'
_ROW_TOLERANCE = 6.0


class EqImporter(utils.Importer):
    _default_currency = 'CAD'
    _regex_fname = re.compile(r'(\d+) .* Statement.pdf')

    def _parse_amount(self, row: dict[str, str]) -> str:
        if row.get('Withdrawals'):
            return f'-{row["Withdrawals"].strip("- $")}'
        return row['Deposits'].strip('$')

    def _extract_from_row(
        self, row: dict[str, str], meta: data.Meta
    ) -> data.Transaction:
        # TODO: get year from filename?
        date = parser.parse(row['Date']).date()
        # TODO: parse out payee vs narration?
        narration = row['Description']
        amt = self._amount(self._parse_amount(row))

        return self._transaction(
            meta=meta,
            date=date,
            narration=narration,
            postings=[self._posting(self.account_name, amt)],
        )

    def _column_bounds(self, header: list[Word]) -> list[float]:
        bounds: list[float] = [0.0]
        for left, right in zip(header, header[1:]):
            bounds.append((left['x1'] + right['x0']) / 2)
        return bounds

    def _header(self, words: list[Word]) -> list[Word] | None:
        header: dict[str, Word] = {}
        for w in words:
            if w['text'] in _HEADERS and w['text'] not in header:
                header[w['text']] = w
        if set(header) != set(_HEADERS):
            return None
        return [header[name] for name in _HEADERS]

    def _rows(self, page: pdfplumber.page.Page) -> Iterator[dict[str, str]]:
        words = page.extract_words()
        header = self._header(words)
        if header is None:
            return

        bounds = self._column_bounds(header)
        top = min(w['top'] for w in header)
        bottoms = [w['top'] for w in words if w['text'] == _FOOTER_ANCHOR]
        bottom = min(bottoms, default=float(page.height))

        body = sorted(
            (w for w in words if top < w['top'] < bottom),
            key=operator.itemgetter('top', 'x0'),
        )

        prev: dict[str, str] | None = None
        for row_words in self._group_rows(body):
            row = self._assign_columns(row_words, bounds)
            # Wrapped descriptions land on a line with no date; fold them back
            # into the transaction they belong to.
            if not row['Date'] and prev is not None:
                prev['Description'] = (
                    f'{prev["Description"]} {row["Description"]}'.strip()
                )
                continue
            if prev is not None:
                yield prev
            prev = row
        if prev is not None:
            yield prev

    def _group_rows(self, body: list[Word]) -> Iterator[list[Word]]:
        group: list[Word] = []
        anchor: float | None = None
        for word in body:
            if anchor is None or word['top'] - anchor <= _ROW_TOLERANCE:
                group.append(word)
                anchor = group[0]['top']
            else:
                yield group
                group = [word]
                anchor = word['top']
        if group:
            yield group

    def _assign_columns(
        self, words: list[Word], bounds: list[float]
    ) -> dict[str, str]:
        cells: list[list[Word]] = [[] for _ in _HEADERS]
        for word in words:
            center = (word['x0'] + word['x1']) / 2
            column = max(i for i, edge in enumerate(bounds) if edge <= center)
            cells[column].append(word)
        return {
            name: ' '.join(
                w['text'] for w in sorted(cell, key=operator.itemgetter('x0'))
            )
            for name, cell in zip(_HEADERS, cells)
        }

    def _extract(self, fname: str) -> Iterator[data.Transaction]:
        with pdfplumber.open(fname) as pdf:
            index = 0
            for page in pdf.pages:
                for row in self._rows(page):
                    meta = data.new_metadata(fname, index)
                    index += 1
                    yield self._extract_from_row(row, meta)
