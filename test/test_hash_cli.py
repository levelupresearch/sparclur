"""Tests for the SPARCLUR hash baseline command-line interface."""

from hashlib import sha256
from pathlib import Path

from sparclur import _hash_cli
from sparclur._parser import META, SparclurHash


class _ProbeParser:
    def __init__(self, doc):
        self.sparclur_hash = SparclurHash(doc)
        self.sparclur_hash._set_provenance(parser={'name': self.get_name(), 'class': 'test.Probe'})
        self.sparclur_hash._add_hash(META, {'content': sha256(Path(doc).read_bytes()).hexdigest()})

    @staticmethod
    def get_name():
        return 'Probe'


def test_hash_cli_creates_inspects_and_compares_baselines(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(_hash_cli, 'get_sparclur_parsers', lambda: [_ProbeParser])
    monkeypatch.setattr(_hash_cli, 'get_parser', lambda name: _ProbeParser if name == 'Probe' else None)
    document = tmp_path / 'document.pdf'
    baseline = tmp_path / 'baseline.json'
    document.write_bytes(b'%PDF-baseline')

    assert _hash_cli.main(['create', str(document), '--parser', 'Probe', '--output', str(baseline)]) == 0
    assert baseline.is_file()
    assert _hash_cli.main(['inspect', str(baseline)]) == 0
    assert 'Parser: Probe' in capsys.readouterr().out
    assert _hash_cli.main(['compare', str(document), str(baseline), '--parser', 'Probe']) == 0


def test_hash_cli_returns_failure_for_a_regression(monkeypatch, tmp_path):
    monkeypatch.setattr(_hash_cli, 'get_sparclur_parsers', lambda: [_ProbeParser])
    monkeypatch.setattr(_hash_cli, 'get_parser', lambda name: _ProbeParser if name == 'Probe' else None)
    baseline_document = tmp_path / 'baseline.pdf'
    candidate = tmp_path / 'candidate.pdf'
    baseline = tmp_path / 'baseline.json'
    baseline_document.write_bytes(b'%PDF-baseline')
    candidate.write_bytes(b'%PDF-candidate')

    assert _hash_cli.main(['create', str(baseline_document), '--parser', 'Probe', '--output', str(baseline)]) == 0
    assert _hash_cli.main([
        'compare', str(candidate), str(baseline), '--parser', 'Probe', '--minimum-similarity', '1.0',
    ]) == 1
