import importlib.metadata

from .activobank import ActivobankImporter  # noqa: IMR241
from .amex import AmexImporter  # noqa: IMR241
from .brim import BrimImporter  # noqa: IMR241
from .chase import ChaseImporter  # noqa: IMR241
from .eq import EqImporter  # noqa: IMR241
from .milleniumbcp import MilleniumbcpImporter  # noqa: IMR241
from .paypal import PaypalImporter  # noqa: IMR241
from .rbc import RbcImporter  # noqa: IMR241
from .remitbee import RemitbeeImporter  # noqa: IMR241
from .revolut import RevolutImporter  # noqa: IMR241
from .tangerine import TangerineImporter  # noqa: IMR241
from .wealthsimple import WealthsimpleImporter  # noqa: IMR241

__version__ = importlib.metadata.version('beancount-importer')
__all__ = [
    'ActivobankImporter',
    'AmexImporter',
    'BrimImporter',
    'ChaseImporter',
    'EqImporter',
    'MilleniumbcpImporter',
    'PaypalImporter',
    'RbcImporter',
    'RemitbeeImporter',
    'RevolutImporter',
    'TangerineImporter',
    'WealthsimpleImporter',
]
