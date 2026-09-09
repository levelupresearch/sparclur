"""Tests for DetectChaos worker option isolation."""

import sparclur._detect_chaos as chaos_module


def test_detect_chaos_renderer_worker_does_not_mutate_options(monkeypatch):
    calls = []

    class RendererMarker:
        pass

    class ProbeRenderer(RendererMarker):
        def __init__(self, doc, skip_check, timeout, **kwargs):
            calls.append(kwargs)

        @staticmethod
        def get_name():
            return "Probe"

        def get_renders(self):
            return {}

    monkeypatch.setattr(chaos_module, "Renderer", RendererMarker)
    monkeypatch.setattr(chaos_module, "get_parser", lambda name: ProbeRenderer)
    options = {"custom": "value"}

    chaos_module._mapper({
        "path": "document.pdf",
        "timeout": 20,
        "parser": "Probe",
        "parser_args": options,
    })

    assert options == {"custom": "value"}
    assert calls == [{"custom": "value", "dpi": 72, "cache_renders": False}]
