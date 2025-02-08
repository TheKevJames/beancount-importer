import importlib.metadata

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
    'RevolutImporter',
    'TangerineImporter',
]
