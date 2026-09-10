"""Tests for the Streamlit Parser Text Comparator page."""

from sparclur.lit_sparclur import _lit_pxc


def test_pxc_page_explains_when_no_text_parser_is_enabled(monkeypatch):
    messages = []

    class TextComparable:
        pass

    monkeypatch.setattr(_lit_pxc, "TextCompare", TextComparable)
    monkeypatch.setattr(_lit_pxc.st, "subheader", lambda value: None)
    monkeypatch.setattr(_lit_pxc.st, "info", messages.append)

    _lit_pxc.app({"Ghostscript": object(), "PDFium": object()})

    assert messages == ["Enable a text extractor or OCR-capable renderer to use PXC."]


def test_pxc_page_accepts_ocr_renderer_via_text_compare_inheritance(monkeypatch):
    messages = []
    output = []

    class TextComparable:
        pass

    class OcrRenderer(TextComparable):
        can_extract_text = True

        @staticmethod
        def get_name():
            return "OCR Renderer"

        @staticmethod
        def get_text():
            return {0: "OCR text"}

    monkeypatch.setattr(_lit_pxc, "TextCompare", TextComparable)
    monkeypatch.setattr(_lit_pxc.st, "subheader", lambda value: None)
    monkeypatch.setattr(_lit_pxc.st, "info", messages.append)
    monkeypatch.setattr(_lit_pxc.st, "write", output.append)
    monkeypatch.setattr(_lit_pxc.st, "selectbox", lambda label, options, key: 0)

    _lit_pxc.app({"Ghostscript": OcrRenderer()})

    assert messages == []
    assert output == ["OCR Renderer", "OCR text"]
