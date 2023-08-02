import importlib

from .activobank import ActivoBankImporter
from .amex import AmexImporter
from .brim import BrimImporter
from .chase import ChaseImporter
from .eq import EQImporter
from .milleniumbcp import MilleniumBCPImporter
from .paypal import PaypalImporter
from .rbc import RBCImporter
from .revolut import RevolutImporter
from .tangerine import TangerineImporter


__version__ = importlib.metadata.version('beancount-importer')
__all__ = [
    'ActivoBankImporter',
    'AmexImporter',
    'BrimImporter',
    'ChaseImporter',
    'EQImporter',
    'MilleniumBCPImporter',
    'PaypalImporter',
    'RBCImporter',
    'RevolutImporter',
    'TangerineImporter',
]
