"""Tests for PRCViz renderer option isolation."""

import sparclur.prc._viz as viz_module


def test_prc_viz_does_not_mutate_renderer_options(monkeypatch):
    calls = []

    class RendererMarker:
        pass

    class ProbeRenderer:
        def __init__(self, doc, **kwargs):
            calls.append(kwargs)
            self.doc = doc

        def compare(self, other, full):
            return {0: object()}

    monkeypatch.setattr(viz_module, "Renderer", RendererMarker)
    monkeypatch.setattr(
        viz_module,
        "_parse_viz_renderers",
        lambda renderers: {"First": ProbeRenderer, "Second": ProbeRenderer},
    )
    options = {"First": {"custom": "one"}, "Second": {"custom": "two"}}

    viz_module.PRCViz("document.pdf", renderers=["First", "Second"], parser_args=options, dpi=144)

    assert options == {"First": {"custom": "one"}, "Second": {"custom": "two"}}
    assert calls == [
        {"custom": "one", "cache_renders": True, "dpi": 144},
        {"custom": "two", "cache_renders": True, "dpi": 144},
    ]
