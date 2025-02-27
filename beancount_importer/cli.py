import pathlib
import re
import tomllib
from collections.abc import Iterable
from typing import Any
from typing import cast
from typing import Protocol

import beangulp  # type: ignore[import-untyped]
import click
import sh
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
from .tangerine import TangerineImporter
from .utils import AccountPattern
from .utils import Importer
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
    'tangerine': TangerineImporter,
    'wealthsimple': WealthsimpleImporter,
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

        Returns
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
                        patterns + [
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


@run.command()
@click.argument('src')
def split(src: str) -> None:
    """Split merged downloaded files into independent ones."""
    config = Ctx.load_config()

    definitions = config.get('rbc') or []
    if len(definitions) > 2:
        merged_regex = re.compile(r'csv\d+\.csv')
        for (dirpath, _dirnames, filenames) in pathlib.Path(src).walk():
            for fname in filenames:
                if not merged_regex.match(fname):
                    continue

                fpath = dirpath / fname
                click.echo(f'Found ambiguous RBC csv {fpath}...')
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


@run.command()
@click.argument('importer', type=click.Choice(list(IMPORTERS.keys())))
def howto(importer: str) -> None:
    """Print howto guide for a specific account type."""
    # pylint: disable=too-complex,too-many-branches,too-many-statements
    # TODO: clean this up
    if not sh.which('bean-query'):
        click.echo('Missing dependency bean-query.', err=True)
        click.echo('Try `pipx install beanquery`.', err=True)
        raise click.Abort()

    query = sh.Command('bean-query')
    config = Ctx.load_config()

    i = 1
    if importer == 'activobank':
        for definition in config[importer]:
            account = definition['account']
            click.echo(f'{i}. Select account {account}')

            # TODO: can LAST include balance statements?
            date = query(
                'index.beancount',
                f'SELECT LAST(date) WHERE account="{account}"',
            ).splitlines()[-1]
            click.echo(f'{i + 1}. Query data from >={date}')
            click.echo(f'{i + 2}. Export as XLSX')
            i += 3
    elif importer == 'brim':
        for definition in config[importer]:
            account = definition['account']
            click.echo(f'{i}. Select account {account}')

            date = query(
                'index.beancount',
                f'SELECT LAST(date) WHERE account="{account}"',
            ).splitlines()[-1]
            click.echo(f'{i + 1}. For each billing period since {date}')
            click.echo(f'{i + 2}. Activity > Statements > Download > CSV')
            i += 3
    elif importer == 'chase':
        for definition in config[importer]:
            account = definition['account']
            click.echo(f'{i}. Select account {account}')
            click.echo(f'{i + 1}. Download Activity > Choose a date range')

            date = query(
                'index.beancount',
                f'SELECT LAST(date) WHERE account="{account}"',
            ).splitlines()[-1]
            click.echo(f'{i + 2}. Query date from >={date}')
            i += 3
    elif importer == 'eq':
        for definition in config[importer]:
            account = definition['account']
            click.echo(f'{i}. Select account {account}')
            click.echo('TODO')
            i += 1
    elif importer == 'rbc':
        click.echo(
            f'{i}. Any Account > Download > CSV / All Accounts '
            '/ New Transactions Since Last Download',
        )
        click.echo(f'{i + 1} bean-import split ~/Downloads')
        i += 2
    elif importer == 'remitbee':
        for definition in config[importer]:
            account = definition['account']
            click.echo(f'{i}. Select account {account}')
            click.echo(f'{i + 1}. Dashboard > Your Transactions > View All')

            date = query(
                'index.beancount',
                f'SELECT LAST(date) WHERE account="{account}"',
            ).splitlines()[-1]
            click.echo(f'{i + 2}. Filter date from >={date}, include Balance')
            click.echo(f'{i + 3}. Download > CSV File')
            i += 4
    elif importer == 'revolut':
        for definition in config[importer]:
            account = definition['account']
            click.echo(f'{i}. Select account {account}')
            click.echo(f'{i + 1}. Statement > Excel')

            date = query(
                'index.beancount',
                f'SELECT LAST(date) WHERE account="{account}"',
            ).splitlines()[-1]
            click.echo(f'{i + 2}. Query date from >={date}')
    elif importer == 'tangerine':
        click.echo(
            f'{i}. Transactions > Download Transactions '
            '> All Since Last Download / CSV',
        )
        # TODO: update `split` command, maybe rename to `pre-process`? or
        # download via append.
        click.echo(
            '   Note: for credit cards, you need to repeat this for each '
            'statement month',
        )
        i += 1
    elif importer == 'wealthsimple':
        for definition in config[importer]:
            account = definition['account']
            click.echo(f'{i}. Select account {account}')
            click.echo(f'{i + 1}. View statements')

            date = query(
                'index.beancount',
                f'SELECT LAST(date) WHERE account="{account}"',
            ).splitlines()[-1]
            click.echo(f'{i + 2}. Download all records from >={date}')
            i += 3
    else:
        click.echo(f'Invalid importer {importer} (or missing howto!)')
        raise click.Abort()

    click.echo(f'{i}. bean-import identify -xv ~/Downloads')
    click.echo(f'{i + 1}. bean-import extract -xe index.beancount ~/Downloads')
    click.echo(f'{i + 2}. bean-import archive -o docs ~/Downloads')
    click.echo(f'{i + 3}. bean-check index.beancount')


run.add_command(beangulp._archive)  # pylint: disable=protected-access
run.add_command(beangulp._extract)  # pylint: disable=protected-access
run.add_command(beangulp._identify)  # pylint: disable=protected-access
