"""Tests for Spotlight document staging."""

from sparclur._parser import META, SparclurHash
from sparclur._spotlight import SpotlightResult, _copy_document


def test_copy_document_writes_bytes(tmp_path):
    destination = tmp_path / "original.pdf"

    _copy_document(b"%PDF-test", destination)

    assert destination.read_bytes() == b"%PDF-test"


def test_copy_document_accepts_paths(tmp_path):
    source = tmp_path / "source.pdf"
    destination = tmp_path / "original.pdf"
    source.write_bytes(b"%PDF-path")

    _copy_document(source, destination)

    assert destination.read_bytes() == b"%PDF-path"


def test_spotlight_hash_comparison_report_exposes_hash_evidence():
    original = SparclurHash(b"original")
    reforged = SparclurHash(b"reforged")
    original._add_hash(META, {"object": 1})
    reforged._add_hash(META, {"object": 1})
    result = SpotlightResult("Probe", "original", {}, original)
    result._spotlight_result["Probe"]["reforged"] = {"validity": {}, "hash": reforged}

    result._compare_hashes("Probe", "original", "reforged")
    report = result.hash_comparison_report()

    assert report.loc[0, "Comparable"]
    assert report.loc[0, "Similarity"] == 1.0
    assert report.loc[0, "Components"] == "Metadata Extractor: ok/ok"
