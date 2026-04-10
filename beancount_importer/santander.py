import collections
import io
import re
from collections.abc import Iterator
from typing import Any

import py_pdf_parser.loaders
import py_pdf_parser.tables
from beancount.core import data
from dateutil.parser import parse

from .utils import Importer


class SantanderImporter(Importer):
    _default_currency = 'EUR'
    _require_lastfour = True
    _regex_fname = re.compile(r'^EXTCON\d{8}0001\d+(\d{4}).pdf$')

    def _parse_amount(self, row: dict[str, Any]) -> str:
        amt: str = row['Amount'].replace('.', '').replace(',', '.')
        return amt

    def _extract_from_row(
            self,
            row: dict[str, Any],
            meta: data.Meta,
    ) -> data.Transaction:
        date = parse(row['Date']).date()
        narration = row['Description']
        amt = self._amount(self._parse_amount(row))

        return self._transaction(
            meta=meta,
            date=date,
            narration=narration,
            postings=[
                self._posting(self.account_name, amt),
            ],
        )

    def _extract(self, fname: str) -> Iterator[data.Transaction]:
        # pylint: disable=too-complex,too-many-locals
        year = fname.rsplit('/', 1)[-1].replace('EXTCON', '')[:4]
        with open(fname, 'rb') as f:
            header_bytes = f.read(27)
            if header_bytes.startswith(b'\xac\xed\x00\x05'):
                # Handle Java serialized byte array wrapping the PDF
                f.seek(0)
                content = f.read()
                pdf_start = content.find(b'%PDF-')
                if pdf_start != -1:
                    iostream = io.BytesIO(content[pdf_start:])
                    doc = py_pdf_parser.loaders.load(iostream)
                else:
                    f.seek(0)
                    doc = py_pdf_parser.loaders.load(f)
            else:
                f.seek(0)
                doc = py_pdf_parser.loaders.load(f)

        header = doc.elements.filter_by_text_equal(
            'Detalhe de Movimentos da Conta à Ordem',
        )[-1]
        footer = doc.elements.filter_by_text_contains(
            'Saldo Disponível Final',
        )[0]
        body = doc.elements.between(header, footer)

        rows = collections.defaultdict(list)
        for el in body:
            # sidebar
            if el.bounding_box.x0 < 20:
                continue
            key = round(el.bounding_box.y1, 1)
            rows[key].append(el)

        index = 0
        for key in sorted(rows.keys(), reverse=True):
            xs = rows[key]
            try:
                dates_el = next(x for x in xs if 30 < x.bounding_box.x0 < 55)
                desc_el = next(x for x in xs if 65 < x.bounding_box.x0 < 90)
                amt_el = next(x for x in xs if 450 < x.bounding_box.x0 < 490)
            except StopIteration:
                continue

            dates = dates_el.text().split('\n')
            if len(dates) == 0 or dates[0] == 'Data':
                continue

            descs = desc_el.text().split('\n')
            amts = amt_el.text().split('\n')

            for d, desc, a in zip(dates, descs, amts):
                d = d.strip()
                if not d or len(d) != 5:
                    continue

                if desc.startswith(d):
                    desc = desc[len(d):].strip()

                row = {
                    'Date': f'{year}-{d[3:5]}-{d[0:2]}',
                    'Description': desc,
                    'Amount': a,
                }
                meta = data.new_metadata(fname, index)
                yield self._extract_from_row(row, meta)
                index += 1
