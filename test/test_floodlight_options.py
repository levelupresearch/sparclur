"""Tests for FloodLight parser option preparation."""

import sparclur._floodlight as floodlight_module
from sparclur._floodlight import FloodLight
from sparclur.parsers import present_parsers


def test_floodlight_preserves_and_passes_parser_options(monkeypatch):
    class ProbeParser:
        def __init__(self, doc, **kwargs):
            self.validity = {"overall": {"status": "Valid"}}

        @staticmethod
        def get_name():
            return "Probe"

    monkeypatch.setattr(
        present_parsers,
        "get_sparclur_parsers",
        lambda check_parsers, parser_args: [ProbeParser],
    )
    captured = []

    def serial_floodlight(entries, progress_bar):
        captured.extend(entries)
        return [{"path": "document.pdf", "status": "Valid", "reason": "Original Valid", "traces": set()}]

    monkeypatch.setattr(floodlight_module, "_serial_floodlight", serial_floodlight)
    supplied_options = {"Probe": {"custom": "value"}}
    floodlight = FloodLight(
        parsers=["Probe"],
        translators=[],
        parser_args=supplied_options,
        timeout=25,
        progress_bar=False,
    )

    floodlight.run(["document.pdf"])

    assert supplied_options == {"Probe": {"custom": "value"}}
    assert captured[0]["parser_args"]["Probe"] == {
        "custom": "value",
        "timeout": 25,
        "temp_folders_dir": None,
        "skip_check": True,
    }
