import importlib

from .activobank import ActivoBankImporter
from .amex import AmexImporter
from .chase import ChaseImporter
from .eq import EQImporter
from .paypal import PaypalImporter
from .rbc import RBCImporter
from .revolut import RevolutImporter
from .tangerine import TangerineImporter


__version__ = importlib.metadata.version('beancount-importer')
__all__ = [
    'ActivoBankImporter',
    'AmexImporter',
    'ChaseImporter',
    'EQImporter',
    'PaypalImporter',
    'RBCImporter',
    'RevolutImporter',
    'TangerineImporter',
]
