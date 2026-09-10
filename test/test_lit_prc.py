"""Tests for the Streamlit PDF Render Comparator page."""

from contextlib import nullcontext

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

        def display(self, page, renderers, width, height):
            captured["page"] = page
            captured["selected_renderers"] = renderers
            captured["figure_size"] = (width, height)
            return "comparison figure"

    monkeypatch.setattr(_lit_prc, "RENDERERS", ["First", "Second"])
    monkeypatch.setattr(_lit_prc, "PRCViz", ProbeViz)
    monkeypatch.setattr(_lit_prc.st, "subheader", lambda value: None)
    monkeypatch.setattr(_lit_prc.st, "pyplot", lambda figure: None)
    monkeypatch.setattr(_lit_prc.st, "form", lambda key: nullcontext())
    monkeypatch.setattr(_lit_prc.st, "form_submit_button", lambda label: True)
    monkeypatch.setattr(_lit_prc.st, "selectbox", lambda label, options: 0)
    monkeypatch.setattr(_lit_prc.st, "multiselect", lambda label, options, default, help: default)

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
        "selected_renderers": [("First", "Second")],
        "figure_size": (12, 5),
    }
