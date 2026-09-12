"""Regression tests for path handling in installed and source checkouts."""

import subprocess
import sys
from pathlib import Path

from sparclur.utils import get_resource_path, is_pdf
from sparclur.utils import _tools
from sparclur.lit_sparclur._non_parser import NonParser


def test_imports_do_not_change_the_working_directory(tmp_path):
    code = (
        "import os; "
        "before = os.getcwd(); "
        "import sparclur.parsers.present_parsers; "
        "import sparclur.utils._config; "
        "assert os.getcwd() == before"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_is_pdf_accepts_uploaded_pdf_bytes():
    example_pdf = Path(__file__).resolve().parents[1] / "resources" / "hello_world_hand_edit.pdf"

    assert is_pdf(example_pdf.read_bytes())
    assert not is_pdf(b"not a PDF")


def test_get_resource_path_finds_bundled_fixture():
    resource = Path(get_resource_path("hello_world_hand_edit.pdf"))

    assert resource.is_file()
    assert resource.name == "hello_world_hand_edit.pdf"


def test_is_pdf_has_a_header_check_without_pymupdf(monkeypatch):
    monkeypatch.setattr(_tools, "fitz", None)

    assert _tools.is_pdf(b"%PDF-1.7\n")
    assert not _tools.is_pdf(b"not a PDF")


def test_optional_python_parser_adapters_do_not_block_base_imports(tmp_path):
    code = """
import builtins

original_import = builtins.__import__
blocked = {"pymupdf", "pypdfium2", "pdfminer"}

def guarded_import(name, *args, **kwargs):
    if name.split(".")[0] in blocked:
        raise ModuleNotFoundError(f"No module named '{name}'", name=name.split(".")[0])
    return original_import(name, *args, **kwargs)

builtins.__import__ = guarded_import
import sparclur.parsers as parsers
from sparclur.parsers.present_parsers import get_sparclur_parsers
from sparclur.utils import is_pdf

assert not {"MuPDF", "PDFium", "PDFMiner"}.intersection(parsers.__all__)
assert not {"MuPDF", "PDFium", "PDFMiner"}.intersection(
    parser.get_name() for parser in get_sparclur_parsers()
)
assert is_pdf(b"%PDF-1.7\\n")
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_non_parser_can_wrap_uploaded_pdf_bytes():
    example_pdf = Path(__file__).resolve().parents[1] / "resources" / "hello_world_hand_edit.pdf"

    parser = NonParser(doc=example_pdf.read_bytes())

    assert parser.get_raw().startswith(b"%PDF")
    assert parser.num_pages == -1
