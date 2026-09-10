"""Tests for the Streamlit PDF Render Comparator page."""

from sparclur.lit_sparclur import _lit_prc


def test_prc_page_passes_uploaded_filename_to_current_viz_api(monkeypatch):
    captured = {}

    class ProbeViz:
        def __init__(self, doc_path, renderers):
            captured["doc_path"] = doc_path
            captured["renderers"] = renderers

        def plot_sims(self):
            return "similarity figure"

        def get_observed_pages(self):
            return 1

        def display(self, page):
            captured["page"] = page
            return "comparison figure"

    monkeypatch.setattr(_lit_prc, "RENDERERS", ["First", "Second"])
    monkeypatch.setattr(_lit_prc, "PRCViz", ProbeViz)
    monkeypatch.setattr(_lit_prc.st, "subheader", lambda value: None)
    monkeypatch.setattr(_lit_prc.st, "pyplot", lambda figure: None)
    monkeypatch.setattr(_lit_prc.st, "selectbox", lambda label, options: 0)

    first = object()
    second = object()
    _lit_prc.app(
        {"First": first, "Second": second},
        document_name="uploaded-example.pdf",
    )

    assert captured == {
        "doc_path": "uploaded-example.pdf",
        "renderers": [first, second],
        "page": 0,
    }
