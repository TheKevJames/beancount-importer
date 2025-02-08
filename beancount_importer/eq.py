import re
from collections.abc import Iterator
from typing import Any
from typing import cast

import py_pdf_parser.loaders
import py_pdf_parser.tables
from beancount.core import data
from dateutil.parser import parse

from .utils import Importer


class EqImporter(Importer):
    _default_currency = 'CAD'
    _regex_fname = re.compile(r'(\d+) .* Statement.pdf')

    def _parse_amount(self, row: dict[str, Any]) -> str:
        if row.get('Withdrawals'):
            return f'-{row["Withdrawals"].strip("- $")}'
        return cast(str, row['Deposits'].strip('$'))

    def _extract_from_row(
            self,
            row: dict[str, Any],
            meta: data.Meta,
    ) -> data.Transaction:
        # TODO: get year from filename?
        date = parse(row['Date']).date()
        # TODO: parse out payee vs narration?
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
        doc = py_pdf_parser.loaders.load_file(fname)

        header = doc.elements.filter_by_text_equal('Activity details')[-1]
        footer = doc.elements.filter_by_text_contains('Equitable Bank Towe')[0]
        body = doc.elements.between(header, footer)

        table = py_pdf_parser.tables.extract_table(
            body,
            fix_element_in_multiple_rows=True,
            fix_element_in_multiple_cols=True,
            as_text=True,
        )

        rows = [dict(zip(table[0], x)) for x in table[1:]]
        for index, row in enumerate(rows):
            meta = data.new_metadata(fname, index)
            yield self._extract_from_row(row, meta)
