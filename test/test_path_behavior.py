"""Regression tests for path handling in installed and source checkouts."""

import os
import subprocess
import sys


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
