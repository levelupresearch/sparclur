"""Tests for the Streamlit Parser Text Comparator page."""

from sparclur.lit_sparclur import _lit_pxc


def test_pxc_page_explains_when_no_text_parser_is_enabled(monkeypatch):
    messages = []

    monkeypatch.setattr(_lit_pxc, "TEXTERS", ["Text Extractor"])
    monkeypatch.setattr(_lit_pxc.st, "subheader", lambda value: None)
    monkeypatch.setattr(_lit_pxc.st, "info", messages.append)

    _lit_pxc.app({"Ghostscript": object(), "PDFium": object()})

    assert messages == ["Enable at least one text-extraction parser to use PXC."]
