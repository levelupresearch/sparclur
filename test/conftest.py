"""Test prerequisites for optional external PDF tools."""

import os
import shutil
from pathlib import Path

import pytest


CLI_REQUIREMENTS = {
    "test_ghostscript.py": ("gs",),
    "test_mupdf.py": ("mutool",),
    "test_pdfcpu.py": ("pdfcpu",),
    "test_poppler.py": ("pdfinfo", "pdffonts", "pdfimages", "pdftoppm", "pdftotext"),
    "test_qpdf.py": ("qpdf",),
}


def _missing_xpdf_tools():
    binary_dir = os.environ.get("SPARCLUR_XPDF_BIN_DIR")
    if not binary_dir:
        return ["SPARCLUR_XPDF_BIN_DIR"]
    return [
        str(Path(binary_dir, tool))
        for tool in ("pdfinfo", "pdffonts", "pdftoppm", "pdftotext")
        if not Path(binary_dir, tool).is_file()
    ]


def _missing_arlington_tools():
    arlington_path = os.environ.get("SPARCLUR_ARLINGTON_PATH")
    if not arlington_path:
        return ["SPARCLUR_ARLINGTON_PATH"]
    root = Path(arlington_path)
    if not root.joinpath("tsv").is_dir():
        return [str(root / "tsv")]
    return []


def pytest_collection_modifyitems(items):
    """Skip integrations only when their declared external dependency is absent."""
    for item in items:
        test_file = item.path.name
        required_tools = CLI_REQUIREMENTS.get(test_file, ())
        missing = [tool for tool in required_tools if shutil.which(tool) is None]
        if required_tools:
            item.add_marker(pytest.mark.cli)
        if test_file == "test_xpdf.py":
            item.add_marker(pytest.mark.cli)
            missing.extend(_missing_xpdf_tools())
        elif test_file == "test_arlington.py":
            item.add_marker(pytest.mark.cli)
            missing.extend(_missing_arlington_tools())
        if missing:
            item.add_marker(pytest.mark.skip(reason=f"missing external dependency: {', '.join(missing)}"))
