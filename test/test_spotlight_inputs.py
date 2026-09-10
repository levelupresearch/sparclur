"""Tests for Spotlight document staging."""

from sparclur._spotlight import _copy_document


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
