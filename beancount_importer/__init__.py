import importlib.metadata

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
from .wealthsimple import WealthsimpleImporter


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
