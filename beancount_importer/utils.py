import csv
import datetime
import enum
import os
import re
from collections.abc import Iterable
from collections.abc import Iterator
from typing import Any
from typing import cast

import titlecase
from beancount.core import amount
from beancount.core import data
from beancount.core import number
from beancount.core import position
from beancount.ingest.cache import _FileMemo as File
from beancount.ingest.importer import ImporterProtocol


# TODO: until the beancount.core.data type hints are working, this isn't very
# useful.
# Eventually, all extract() methods should get updated to return any directives
# Directive = (data.Balance | data.Close | data.Commodity | data.Custom
#              | data.Document | data.Event | data.Note | data.Open | data.Pad
#              | data.Price | data.Query | data.Transaction)


class AccountPatternTarget(int, enum.Enum):
    BOTH = enum.auto()
    EITHER = enum.auto()
    NARRATION = enum.auto()
    PAYEE = enum.auto()


class AccountPattern:
    def __init__(
            self,
            account: data.Account,
            pattern: str,
            *,
            flag: data.Flag | None = None,
            target: AccountPatternTarget = AccountPatternTarget.EITHER,
    ) -> None:
        self.account = account
        self.flag = flag
        self.pattern = re.compile(pattern)
        self.target = target

    def matches(self, tx: data.Transaction) -> bool:
        if self.target == AccountPatternTarget.NARRATION:
            return bool(self.pattern.search(tx.narration))
        if self.target == AccountPatternTarget.PAYEE:
            return bool(tx.payee is not None and self.pattern.search(tx.payee))
        if self.target == AccountPatternTarget.BOTH:
            return bool(
                self.pattern.search(
                    f'{tx.payee or ""};{tx.narration}',
                ),
            )
        return bool(
            self.pattern.search(tx.narration)
            or (
                tx.payee is not None
                and self.pattern.search(tx.payee)
            ),
        )

    def posting(self, tx: data.Transaction) -> data.Posting:
        amt = -tx.postings[0].units
        return data.Posting(self.account, amt, None, None, self.flag, None)


# TODO: identifier.IdentifyMixin ?
class Importer(ImporterProtocol):  # type: ignore[misc]
    _default_currency: data.Currency | None = None
    _require_lastfour: bool = False
    _regex_fname: re.Pattern[str]

    def __init__(
            self,
            account: data.Account,
            *,
            account_patterns: list[AccountPattern] | None = None,
            currency: data.Currency | None = None,
            lastfour: str | None = None,
    ) -> None:
        self.account = account
        self.account_patterns = account_patterns or []
        self.currency = currency or self._default_currency
        self.lastfour = lastfour

        if self._require_lastfour and self.lastfour is None:
            raise ValueError('lastfour="xxxx" must be provided')

    def file_account(self, _f: File) -> str:
        return str(self.account)

    def file_date(self, f: File) -> datetime.datetime | None:
        try:
            value = max(x.date for x in self.extract(f))
            return cast(datetime.datetime, value)
        except ValueError:
            # why are you filing this, anyway?
            return None

    def identify(self, f: File) -> bool:
        match = self._regex_fname.match(os.path.basename(f.name))
        if not match:
            return False
        return self.lastfour is None or self.lastfour == match.group(1)

    def name(self) -> str:
        return f'{super().name()}.{self.account}'

    def _amount(
            self,
            raw: str,
            currency: data.Currency | None = None,
    ) -> amount.Amount:
        return amount.Amount(number.D(raw), currency or self.currency)

    def _transaction(
            self,
            *,
            meta: data.Meta,
            date: datetime.date,
            narration: str,
            payee: str | None = None,
            postings: list[data.Posting] | None = None,
    ) -> data.Transaction:
        return data.Transaction(
            meta=meta,
            date=date,
            flag=self.FLAG,
            payee=titlecase.titlecase(payee.strip()) if payee else None,
            narration=titlecase.titlecase(narration.strip()),
            tags=data.EMPTY_SET,
            links=data.EMPTY_SET,
            postings=postings or [],
        )

    def _posting(
            self,
            account: data.Account,
            units: amount.Amount,
            cost: position.Cost | position.CostSpec | None = None,
            price: amount.Amount | None = None,
            flag: data.Flag | None = None,
            meta: data.Meta | None = None,
    ) -> data.Posting:
        return data.Posting(account, units, cost, price, flag, meta)

    def _extract_from_row(
            self,
            row: dict[str, Any],
            meta: data.Meta,
    ) -> data.Transaction | None:
        raise NotImplementedError()

    def _extract(self, fname: str) -> Iterator[data.Transaction | None]:
        with open(fname, encoding='utf-8') as f:
            for index, row in enumerate(csv.DictReader(f)):
                meta = data.new_metadata(fname, index)
                yield self._extract_from_row(row, meta)

    def _filter(
            self,
            xs: Iterable[data.Transaction | None],
    ) -> Iterator[data.Transaction]:
        for x in xs:
            if not x:
                continue

            yield x

    def _add_posting(self, x: data.Transaction) -> data.Transaction:
        if not isinstance(x, data.Transaction):
            return x

        for account_pattern in self.account_patterns:
            if account_pattern.matches(x):
                x.postings.append(account_pattern.posting(x))
                break

        return x

    def _add_postings(
            self,
            xs: Iterable[data.Transaction],
    ) -> Iterator[data.Transaction]:
        for x in xs:
            yield self._add_posting(x)

    def extract(self, f: File) -> list[data.Transaction]:
        # TODO: print proposed data.Balance() record at end?
        # It should be manually checked anyway, so probably a bad idea to emit
        return list(self._add_postings(self._filter(self._extract(f.name))))
