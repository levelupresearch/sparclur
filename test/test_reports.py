"""Tests for native report and evidence-bundle generation."""

from pathlib import Path

import pandas as pd

from sparclur import BatchReport, DocumentReport, SparclurReport


SAMPLE = Path(__file__).resolve().parents[1] / "resources" / "hello_world_hand_edit.pdf"


def test_document_report_writes_html_and_machine_readable_evidence(tmp_path):
    index = DocumentReport(str(SAMPLE), parsers=["PDFium"], dpi=72).write_bundle(tmp_path / "report")

    assert index.name == "index.html"
    assert "SPARCLUR evidence dossier" in index.read_text(encoding="utf-8")
    assert (tmp_path / "report" / "manifest.json").is_file()
    assert (tmp_path / "report" / "data" / "report.json").is_file()
    parser_rows = pd.read_csv(tmp_path / "report" / "data" / "parsers.csv")
    assert parser_rows.loc[0, "parser"] == "PDFium"


def test_document_report_writes_prc_figures_for_two_renderers(tmp_path):
    report_dir = tmp_path / "render-report"
    DocumentReport(str(SAMPLE), parsers=["MuPDF", "PDFium"], dpi=72, timeout=30).write_bundle(report_dir)

    comparisons = pd.read_csv(report_dir / "data" / "render-comparison.csv")
    assert not comparisons.empty
    assert (report_dir / "figures" / "prc-similarity.png").is_file()
    assert (report_dir / "figures" / "prc-worst-page.png").is_file()


def test_batch_report_links_to_each_document_dossier(tmp_path):
    index = BatchReport([(str(SAMPLE), "fixture")], parsers=["PDFium"], dpi=72).write_bundle(tmp_path / "batch")

    assert "documents/001/index.html" in index.read_text(encoding="utf-8")
    assert (tmp_path / "batch" / "documents" / "001" / "index.html").is_file()
    assert (tmp_path / "batch" / "data" / "summary.csv").is_file()


def test_legacy_report_facade_writes_native_html(tmp_path):
    index = SparclurReport(str(SAMPLE), tmp_path / "legacy.pmd", parsers=["PDFium"], dpi=72).generate_report()

    assert index == tmp_path / "legacy.html"
    assert index.is_file()
