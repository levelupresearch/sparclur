"""Regression tests for path handling in installed and source checkouts."""

import subprocess
import sys
from pathlib import Path

from sparclur.utils import is_pdf


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
