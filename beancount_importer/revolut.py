import csv
import logging
import os
import re
from datetime import timedelta
from dateutil.parser import parse
from io import StringIO

from beancount.core import amount, data
from beancount.core.number import D
from beancount.ingest.cache import _FileMemo as File
from beancount.ingest.importer import ImporterProtocol


# TODO: identifier.IdentifyMixin ?
class RevolutImporter(ImporterProtocol):
    def __init__(self, account: str, *, currency: str = 'EUR'):
        self.account = account
        self.currency = currency

    def name(self):
        return super().name() + self.account

    def identify(self, f: File) -> bool:
        return bool(re.match(r'account-statement.*\.csv', os.path.basename(f.name)))

    def extract(self, file, existing_entries):
        entries = []

        with StringIO(file.contents()) as csvfile:
            reader = csv.DictReader(
                csvfile,
                [
                    "Type",
                    "Product",
                    "Started Date",
                    "Completed Date",
                    "Description",
                    "Amount",
                    "Fee",
                    "Currency",
                    "State",
                    "Balance",
                ],
                delimiter=",",
                skipinitialspace=True,
            )
            next(reader)
            for row in reader:
                try:
                    bal = D(row["Balance"].replace("'", "").strip())
                    amount_raw = D(row["Amount"].replace("'", "").strip())
                    amt = amount.Amount(amount_raw, row["Currency"])
                    balance = amount.Amount(bal, self.currency)
                    book_date = parse(row["Completed Date"].strip()).date()
                except Exception as e:
                    logging.warning(e)
                    continue

                entry = data.Transaction(
                    data.new_metadata(file.name, 0, {}),
                    book_date,
                    "*",
                    "",
                    row["Description"].strip(),
                    data.EMPTY_SET,
                    data.EMPTY_SET,
                    [
                        data.Posting(self.account, amt, None, None, None, None),
                    ],
                )
                entries.append(entry)

            # only add balance after the last (newest) transaction
            try:
                book_date = book_date + timedelta(days=1)
                entry = data.Balance(
                    data.new_metadata(file.name, 0, {}),
                    book_date,
                    self.account,
                    balance,
                    None,
                    None,
                )
                entries.append(entry)
            except NameError:
                pass

        return entries
