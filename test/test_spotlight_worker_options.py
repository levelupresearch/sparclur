"""Tests for isolated Spotlight worker options."""

from sparclur._spotlight import _mapper


def test_spotlight_mapper_does_not_mutate_worker_options(tmp_path):
    calls = []

    class ProbeParser:
        def __init__(self, **kwargs):
            calls.append(kwargs)
            self.validity = {}
            self.sparclur_hash = None

        @staticmethod
        def get_name():
            return "Probe"

    options = {"timeout": 30}
    entry = {
        "base_path": str(tmp_path),
        "parser": ProbeParser,
        "version": "original",
        "args": options,
    }

    _mapper(entry)

    assert options == {"timeout": 30}
    assert calls == [{"timeout": 30, "doc": str(tmp_path / "Probe" / "original.pdf")}]
