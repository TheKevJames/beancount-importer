import re
from collections.abc import Callable
from collections.abc import Iterator
from typing import Any

from beancount.core import data
from dateutil.parser import parse

from .utils import Importer


class RevolutImporter(Importer):
    _default_currency = 'EUR'
    _regex_fname = re.compile(r'account-statement.*\.csv')

    def _extract_from_row(
            self,
            row: dict[str, Any],
            meta: data.Meta,
    ) -> data.Transaction:
        try:
            # TODO: check the strip/replaces
            date = parse(row['Data de Conclusão'].strip()).date()
            # TODO: parse out payee vs narration?
            narration = row['Descrição'].strip()
            amt_raw = row['Montante'].replace("'", '').strip()
            amt = self._amount(amt_raw, row['Moeda'])
        except KeyError:
            # TODO: check the strip/replaces
            date = parse(row['Completed Date'].strip()).date()
            # TODO: parse out payee vs narration?
            narration = row['Description'].strip()
            amt_raw = row['Amount'].replace("'", '').strip()
            amt = self._amount(amt_raw, row['Currency'])

        return self._transaction(
            meta=meta,
            date=date,
            narration=narration,
            postings=[
                self._posting(self.account_name, amt),
            ],
        )

    @classmethod
    def howto(
            cls,
            query: Callable[[str], str],
            accounts: list[str],
    ) -> Iterator[str]:
        for account in accounts:
            yield f'Select account {account}'
            yield 'Statement > Excel'

            date = query(account)
            yield f'Query date from >={date}'
