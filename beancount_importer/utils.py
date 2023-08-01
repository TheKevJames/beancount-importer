import csv
import datetime
import enum
import os
import re
from collections.abc import Iterable
from collections.abc import Iterator
from typing import Any

import titlecase
from beancount.core import amount
from beancount.core import data
from beancount.core import number
from beancount.core import position
from beancount.ingest.cache import _FileMemo as File
from beancount.ingest.importer import ImporterProtocol


Directive = (data.Balance | data.Close | data.Commodity | data.Custom
             | data.Document | data.Event | data.Note | data.Open | data.Pad
             | data.Price | data.Query | data.Transaction)


class AccountPatternTarget(int, enum.Enum):
    BOTH = enum.auto()
    NARRATION = enum.auto()
    PAYEE = enum.auto()


class AccountPattern:
    def __init__(
            self,
            account: data.Account,
            pattern: str,
            *,
            flags: int = 0,
            target: AccountPatternTarget = AccountPatternTarget.BOTH,
    ) -> None:
        self.account = account
        self.pattern = re.compile(pattern, flags)
        self.target = target

    def matches(self, tx: data.Transaction) -> bool:
        if self.target == AccountPatternTarget.NARRATION:
            return self.pattern.search(tx.narration)
        if self.target == AccountPatternTarget.PAYEE:
            return tx.payee is not None and self.pattern.search(tx.payee)
        return (self.pattern.search(tx.narration)
                or (tx.payee is not None and self.pattern.search(tx.payee)))

    def posting(self, tx: data.Transaction) -> data.Posting:
        amt = -tx.postings[0].units
        return data.Posting(self.account, amt, None, None, None, None)


# TODO: identifier.IdentifyMixin ?
class Importer(ImporterProtocol):
    _default_currency: data.Currency | None = None
    regex_fname: re.Pattern

    def __init__(
            self,
            account: data.Account,
            *,
            currency: data.Currency | None = None,
            account_patterns: list[AccountPattern] | None = None,
    ) -> None:
        self.account = account
        self.currency = currency or self._default_currency
        self.account_patterns = account_patterns or []

    def file_account(self, _f: File) -> str:
        return self.account

    def file_date(self, f: File) -> datetime.datetime:
        return max([x.date for x in self.extract(f)])

    def identify(self, f: File) -> bool:
        return bool(self.regex_fname.match(os.path.basename(f.name)))

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
            payee=titlecase.titlecase(payee) if payee else None,
            narration=titlecase.titlecase(narration),
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
    ) -> Directive | None:
        raise NotImplementedError()

    def _extract(self, fname: str) -> Iterator[Directive | None]:
        with open(fname, encoding='utf-8') as f:
            for index, row in enumerate(csv.DictReader(f)):
                meta = data.new_metadata(fname, index)
                yield self._extract_from_row(row, meta)

    def _filter(self, xs: Iterable[Directive | None]) -> Iterator[Directive]:
        for x in xs:
            if not x:
                continue

            yield x

    def _add_posting(self, x: Directive) -> Directive:
        if not isinstance(x, data.Transaction):
            return x

        for account_pattern in self.account_patterns:
            if account_pattern.matches(x):
                x.postings.append(account_pattern.posting(x))
                break

        return x

    def _add_postings(self, xs: Iterable[Directive]) -> Iterator[Directive]:
        for x in xs:
            yield self._add_posting(x)

    def extract(self, f: File) -> list[Directive]:
        # TODO: print proposed data.Balance() record at end?
        # It should be manually checked anyway, so probably a bad idea to emit
        return list(self._add_postings(self._filter(self._extract(f.name))))
