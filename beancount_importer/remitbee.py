import datetime
import re
from typing import Any

from beancount.core import data
from beancount.core import flags

from .utils import Importer


class RemitbeeImporter(Importer):
    _require_lastfour = False
    _regex_fname = re.compile(
        r'^(balance|transaction)_history_[-\w\d_ ]+.csv$',
    )

    def _extract_from_row(
            self,
            row: dict[str, Any],
            meta: data.Meta,
    ) -> data.Transaction | None:
        recipient = row['Recipient']
        if recipient == 'Amount sent':
            return None

        date = datetime.datetime.strptime(row['Date'], '%b %d, %Y %I:%M %p')
        recv_val, recv_cur = row['Amount received'].split()
        recv_amt = self._amount(recv_val.replace(',', ''), recv_cur)

        narration: str
        if recipient == 'Amount received':
            narration = 'Deposit'
            postings = [
                self._posting(self.account_name, recv_amt),
                self._posting('Equity:Transfer', -recv_amt),
            ]
        else:
            narration = f'TRF to {recipient} in {row["Country"]}'
            send_val, send_cur = row['Amount sent'].split()
            send_amt = self._amount(send_val.replace(',', ''), send_cur)

            # TODO: if we could pass total price instead of price, this posting
            # be more simply and accurately representable as
            # `total_price=to_amt`
            # https://github.com/beancount/beangulp/issues/4
            price = self._amount(send_amt.number / recv_amt.number, send_cur)

            postings = [
                # TODO: this account needs to be the one with the price to get
                # the conversion right and avoid negative prices (unsupported),
                # which means we can't support account_patterns properly here.
                # As such, we use an unknown account and flag it for review.
                self._posting(
                    'Expenses:Unknown', recv_amt, price=price,
                    flag=flags.FLAG_WARNING,
                ),
                self._posting(self.account_name, -send_amt),
            ]

        return self._transaction(
            meta=meta,
            date=date.date(),
            narration=narration,
            postings=postings,
        )
