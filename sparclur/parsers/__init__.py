from ._poppler import Poppler
from ._xpdf import XPDF
from ._ghostscript import Ghostscript
from ._qpdf import QPDF
from ._arlington import Arlington
from ._pdfcpu import PDFCPU

__all__ = [
    "Arlington",
    "Ghostscript",
    "PDFCPU",
    "Poppler",
    "QPDF",
    "XPDF",
]


def _load_optional_adapter(name, module_name, dependency):
    try:
        module = __import__(module_name, fromlist=[name])
    except ModuleNotFoundError as error:
        if error.name != dependency:
            raise
        return
    globals()[name] = getattr(module, name)
    __all__.append(name)


_load_optional_adapter("MuPDF", "sparclur.parsers._mupdf", "pymupdf")
_load_optional_adapter("PDFium", "sparclur.parsers._pdfium", "pypdfium2")
_load_optional_adapter("PDFMiner", "sparclur.parsers._pdfminer", "pdfminer")
