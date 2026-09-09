"""Tests for parser discovery helpers."""

from sparclur.parsers import present_parsers


def test_capability_probe_does_not_mutate_parser_arguments(monkeypatch):
    calls = []

    class ProbeParser:
        @staticmethod
        def get_name():
            return "Probe"

        def __init__(self, doc, **kwargs):
            calls.append((doc, kwargs))

    monkeypatch.setattr(present_parsers, "_sparclur_parsers", {"Probe": ProbeParser})
    parser_args = {"Probe": {"timeout": 30}}

    assert present_parsers.get_sparclur_parsers(check_parsers=True, parser_args=parser_args) == [ProbeParser]
    assert calls == [(present_parsers.min_pdf, {"timeout": 30, "skip_check": False})]
    assert parser_args == {"Probe": {"timeout": 30}}
