"""Tests for the installed Streamlit UI command."""

import sys

from sparclur.lit_sparclur import _cli


def test_ui_command_runs_packaged_app_and_forwards_arguments(monkeypatch):
    received = []

    def fake_streamlit_main():
        received.extend(sys.argv)
        return 0

    monkeypatch.setattr(_cli, "_streamlit_main", lambda: fake_streamlit_main)
    monkeypatch.setattr(sys, "argv", ["sparclur-ui", "--server.port", "8501"])

    assert _cli.main() == 0
    assert received[:2] == ["sparclur-ui", "run"]
    assert received[2].endswith("sparclur/lit_sparclur/lit_sparclur.py")
    assert received[3:] == ["--server.port", "8501"]


def test_ui_command_explains_missing_optional_dependency(monkeypatch, capsys):
    monkeypatch.setattr(_cli, "_streamlit_main", lambda: (_ for _ in ()).throw(ImportError()))

    assert _cli.main() == 1
    assert "pip install 'sparclur[ui]'" in capsys.readouterr().err
