"""Tests for Analyzer worker option isolation."""

import sparclur.prc._analyze as analyze_module


def test_prc_worker_does_not_mutate_parser_options(monkeypatch):
    calls = []

    class ProbeRenderer:
        def __init__(self, doc, skip_check, **kwargs):
            calls.append(kwargs)
            self.logs = {0: {"result": "ok", "timing": 1}}
            self.validate_renderer = {"status": "Valid"}

        def get_renders(self, page=None):
            return {0: object()} if page is None else object()

    monkeypatch.setattr(analyze_module, "AVAILABLE_RENDERERS", {"Probe": ProbeRenderer})
    options = {"Probe": {"custom": "value"}}

    result = analyze_module._prc_worker({
        "path": "document.pdf",
        "renderers": ["Probe"],
        "metrics": [],
        "parser_args": options,
        "timeout": 20,
    })

    assert result[0]["Probe_render"] == "ok"
    assert options == {"Probe": {"custom": "value"}}
    assert calls == [{"custom": "value", "cache_renders": True, "timeout": 20}]
