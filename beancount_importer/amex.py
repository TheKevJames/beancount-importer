import csv
import os
import re
from dateutil.parser import parse

import titlecase
from beancount.core.number import D
from beancount.core import amount
from beancount.core import flags
from beancount.core import data
from beancount.ingest.importer import ImporterProtocol
from beancount.ingest.cache import _FileMemo as File


class AmexImporter(ImporterProtocol):
    # TODO: categorization support
    def __init__(self, account: str, *, currency: str = 'USD') -> None:
        self.account = account
        self.currency = currency

    def identify(self, f: File) -> bool:
        return bool(re.match(r'Transactions.*\.csv', os.path.basename(f.name)))

    def extract(self, f: File) -> list[data.Transaction]:
        entries = []

        with open(f.name, encoding='utf-8') as f:
            for index, row in enumerate(csv.DictReader(f)):
                trans_date = parse(row['Date'].split(' ')[0]).date()
                trans_desc = titlecase.titlecase(row['Description'])
                trans_amt = row['Amount']

                meta = data.new_metadata(f.name, index)

                txn = data.Transaction(
                    meta=meta,
                    date=trans_date,
                    flag=flags.FLAG_OKAY,
                    payee=trans_desc,
                    narration="",
                    tags=set(),
                    links=set(),
                    postings=[],
                )

                txn.postings.append(
                    data.Posting(
                        self.account,
                        amount.Amount(-1*D(trans_amt), self.currency),
                        None, None, None, None
                    )
                )

                entries.append(txn)

        # TODO: append data.Balance() record
        return entries
