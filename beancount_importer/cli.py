import pathlib
import re
import tomllib
from collections.abc import Iterable
from typing import Any
from typing import Protocol
from typing import cast

import beangulp  # type: ignore[import-untyped]
import click
from beancount.core import data

from .activobank import ActivobankImporter
from .amex import AmexImporter
from .brim import BrimImporter
from .chase import ChaseImporter
from .eq import EqImporter
from .milleniumbcp import MilleniumbcpImporter
from .paypal import PaypalImporter
from .rbc import RbcImporter
from .remitbee import RemitbeeImporter
from .revolut import RevolutImporter
from .santander import SantanderImporter
from .tangerine import TangerineImporter
from .utils import AccountPattern
from .utils import Importer
from .wealthsimple import WealthsimpleCreditCardImporter
from .wealthsimple import WealthsimpleImporter

# TODO: enable beangulp type checking once it has a py.typed
# https://github.com/beancount/beangulp/pull/141


IMPORTERS: dict[str, type[Importer]] = {
    'activobank': ActivobankImporter,
    'amex': AmexImporter,
    'brim': BrimImporter,
    'chase': ChaseImporter,
    'eq': EqImporter,
    'milleniumbcp': MilleniumbcpImporter,
    'paypal': PaypalImporter,
    'rbc': RbcImporter,
    'remitbee': RemitbeeImporter,
    'revolut': RevolutImporter,
    'santander': SantanderImporter,
    'tangerine': TangerineImporter,
    'wealthsimple': WealthsimpleImporter,
    'wealthsimple-credit-card': WealthsimpleCreditCardImporter,
}


# See https://github.com/beancount/beangulp/blob/v0.2.0/examples/import.py#L53
class Hook(Protocol):
    def __call__(
        self,
        extracted_entries: list[tuple[str, list[data.Transaction]]],
        ledger_entries: list[data.Transaction] | None = None,
    ) -> list[tuple[str, list[data.Transaction]]]:
        """
        Hook function type hint.

        Args:
          extracted_entries: A list of (filename, entries) pairs, where
            'entries' are the directives extract from 'filename'.
          ledger_entries: If provided, a list of directives from the existing
            ledger of the user. This is non-None if the user provided their
            ledger file as an option.

        Returns:
          A possibly different version of extracted_entries_list, a list of
          (filename, entries), to be printed.
        """


# See https://github.com/beancount/beangulp/blob/v0.2.0/beangulp/__init__.py
class Ctx:
    def __init__(self) -> None:
        self.importers = list(self.build_importers())
        self.hooks: list[Hook] = []

    @classmethod
    def load_config(cls) -> dict[str, list[Any]]:
        try:
            fname = pathlib.Path('./config.toml')
            with fname.open('rb') as f:
                config = tomllib.load(f)['beancount-importer']
                return cast(dict[str, list[Any]], config)
        except KeyError as e:
            click.echo('No beancount-importer section in config.', err=True)
            raise click.Abort() from e
        except FileNotFoundError as e:
            click.echo('./config.toml not found.', err=True)
            raise click.Abort() from e

    @classmethod
    def build_importers(cls) -> Iterable[Importer]:
        config = cls.load_config()

        patterns: list[AccountPattern] = []
        for section, definitions in config.items():
            if section == 'patterns':
                patterns = [AccountPattern.from_config(x) for x in definitions]
                continue

            for definition in definitions:
                yield IMPORTERS[section](
                    definition['account'],
                    account_patterns=(
                        patterns
                        + [
                            AccountPattern.from_config(x)
                            for x in definition.get('patterns', [])
                        ]
                    ),
                    currency=definition.get('currency'),
                    lastfour=definition.get('lastfour'),
                )


@click.group('beancount-importer')
@click.version_option()
@click.pass_context
def run(ctx: click.Context) -> None:
    ctx.obj = Ctx()


# TODO: consider renaming to "pre-process"?
@run.command()
@click.argument('src')
def split(src: str) -> None:  # noqa: C901
    """Split merged downloaded files into independent ones."""
    # pylint: disable=too-many-locals,too-many-branches
    config = Ctx.load_config()

    # rbc
    definitions = config.get('rbc') or []
    if len(definitions) > 2:
        merged_regex = re.compile(r'csv\d+\.csv')
        for dirpath, _dirnames, filenames in pathlib.Path(src).walk():
            for fname in filenames:
                if not merged_regex.match(fname):
                    continue

                fpath = dirpath / fname
                click.echo(f'Found grouped RBC csv {fpath}...')
                with fpath.open('r') as f:
                    lines = f.readlines()

                for definition in definitions:
                    lastfour = definition['lastfour']
                    new_fname = dirpath / f'rbc{lastfour}.{fname}'
                    click.echo(f'* writing data for {lastfour} to {new_fname}')
                    with new_fname.open('w') as f:
                        f.write(lines[0])
                        for x in lines:
                            if x.split(',')[1].endswith(lastfour):
                                f.write(x)

                click.echo(f'Deleting {fpath}')
                fpath.unlink()

    # TODO: merge with rbc implementation (rbc doesn't track bad accounts!) and
    # dedupe. Move into importer?
    # wealthsimple
    definitions = config.get('wealthsimple') or []
    if len(definitions) >= 2:
        merged_regex = re.compile(r'^activities-export-\d+-\d+-\d+\.csv')
        for dirpath, _dirnames, filenames in pathlib.Path(src).walk():
            for fname in filenames:
                if not merged_regex.match(fname):
                    continue

                fpath = dirpath / fname
                click.echo(f'Found grouped Wealthsimple csv {fpath}...')
                with fpath.open('r') as f:
                    lines = f.readlines()

                header = lines[0]
                account_col = header.strip().split(',').index('account_id')
                body = []
                accounts = {}
                for x in lines[1:]:
                    if x.strip() and not x.startswith('"As of '):
                        body.append(x)
                        accid = x.split(',')[account_col]
                        accounts[accid[5:-3]] = accid

                prefix = 'monthly-statement-transactions-'
                for accid in accounts.values():
                    new_fname = dirpath / f'{prefix}{accid}-0.csv'
                    click.echo(f'* writing data for {accid} to {new_fname}')
                    with new_fname.open('w') as f:
                        f.write(header)
                        for x in body:
                            if x.split(',')[account_col] == accid:
                                f.write(x)

                click.echo(f'Deleting {fpath}')
                fpath.unlink()

                for lastfour, accid in accounts.items():
                    if lastfour not in {x['lastfour'] for x in definitions}:
                        click.echo(f'No definition for: {accid}', err=True)


run.add_command(beangulp._archive)  # pylint: disable=protected-access
run.add_command(beangulp._extract)  # pylint: disable=protected-access
run.add_command(beangulp._identify)  # pylint: disable=protected-access
