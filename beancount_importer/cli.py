import pathlib
import tomllib

import beangulp  # type: ignore[import-untyped]
import click

from .activobank import ActivobankImporter
from .amex import AmexImporter
from .brim import BrimImporter
from .chase import ChaseImporter
from .eq import EqImporter
from .milleniumbcp import MilleniumbcpImporter
from .paypal import PaypalImporter
from .rbc import RbcImporter
from .revolut import RevolutImporter
from .tangerine import TangerineImporter
from .utils import AccountPattern
from .utils import Importer


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
    'revolut': RevolutImporter,
    'tangerine': TangerineImporter,
}


# See https://github.com/beancount/beangulp/blob/v0.2.0/beangulp/__init__.py
class Ctx:
    def __init__(self) -> None:
        try:
            fname = pathlib.Path('./config.toml')
            with fname.open('rb') as f:
                config = tomllib.load(f)['beancount-importer']
        except KeyError as e:
            click.echo('No beancount-importer section in config file.')
            raise click.Abort() from e
        except FileNotFoundError as e:
            click.echo('./config.toml not found.')
            raise click.Abort() from e

        importers: list[Importer] = []
        patterns: list[AccountPattern] = []
        for section, definitions in config.items():
            if section == 'patterns':
                patterns = [AccountPattern.from_config(x) for x in definitions]
                continue

            for definition in definitions:
                importers.append(
                    IMPORTERS[section](
                        definition['account'],
                        account_patterns=(
                            patterns + [
                                AccountPattern.from_config(x)
                                for x in definition.get('patterns', [])
                            ]
                        ),
                        currency=definition.get('currency'),
                        lastfour=definition.get('lastfour'),
                    ),
                )

        self.importers = importers


@click.group('beancount-importer')
@click.version_option()
@click.pass_context
def run(ctx: click.Context) -> None:
    ctx.obj = Ctx()


@run.command()
@click.argument('importer', type=click.Choice(list(IMPORTERS.keys())))
def howto(importer: str) -> None:
    """Print howto guide for a specific account type."""
    # pylint: disable=too-complex
    # TODO: clean this up
    if importer == 'activobank':
        click.echo('1. Search since last reconcile')
        click.echo('2. Export as XLSX')
    elif importer == 'amex':
        click.echo('TODO')
    elif importer == 'brim':
        click.echo('1. Activity > Statements > Download > CSV')
    elif importer == 'chase':
        click.echo('TODO')
    elif importer == 'eq':
        click.echo('TODO')
    elif importer == 'milleniumbcp':
        click.echo('TODO')
    elif importer == 'paypal':
        click.echo('TODO')
    elif importer == 'rbc':
        click.echo(
            '1. Account > Download > CSV / All Accounts / New Transactions',
        )
    elif importer == 'revolut':
        click.echo('TODO')
    elif importer == 'tangerine':
        click.echo('# Account')
        click.echo(
            '1. Transactions > Download Transactions '
            '> All Since Last Download / CSV',
        )
        # TODO: update regex_fname
        click.echo(
            '2. mv ~/Downloads/finance/Chequing.CSV '
            '~/Downloads/finance/"xxxx 1234.CSV"',
        )
        click.echo(
            '3. mv ~/Downloads/finance/Savings.CSV '
            '~/Downloads/finance/"xxxx 5678.CSV"',
        )
        click.echo()
        click.echo('# Credit Card')
        click.echo('Note: Import one month at a time')  # TODO: append?
        click.echo(
            '1. mv ~/Downloads/finance/"World Mastercard.CSV" '
            '~/Downloads/finance/"xxxx 1234.CSV"',
        )
    else:
        click.echo(f'Invalid importer {importer}')
        raise click.Abort()


run.add_command(beangulp._archive)  # pylint: disable=protected-access
run.add_command(beangulp._extract)  # pylint: disable=protected-access
run.add_command(beangulp._identify)  # pylint: disable=protected-access
