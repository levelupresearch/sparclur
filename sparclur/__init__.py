from typing import TYPE_CHECKING

from ._astrotruther import Astrotruther
from ._detect_chaos import DetectChaos
from ._spotlight import Spotlight
from ._roll_back import RollBack
from ._floodlight import FloodLight

__version__ = '2022.5.3'

if TYPE_CHECKING:
    from ._pdf_reports import SparclurReport


def __getattr__(name):
    """Load optional report support only when it is requested."""
    if name == "SparclurReport":
        from ._pdf_reports import SparclurReport
        return SparclurReport
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
