"""Regression tests for public option properties."""

from sparclur._astrotruther import Astrotruther
from sparclur._detect_chaos import DetectChaos
from sparclur.prc._analyze import Analyzer
from sparclur.trawler._highlight import Highlight


def test_detect_chaos_parser_timeout_property():
    chaos = DetectChaos(parsers=[])

    chaos.parser_timeout = 45
    assert chaos.parser_timeout == 45
    del chaos.parser_timeout
    assert chaos.parser_timeout is None


def test_analyzer_timeout_properties():
    analyzer = Analyzer(files=[], renderers=["PDFium", "MuPDF"])

    analyzer.overall_timeout = 120
    analyzer.timeout = 30
    assert analyzer.overall_timeout == 120
    assert analyzer.timeout == 30
    del analyzer.overall_timeout
    del analyzer.timeout
    assert analyzer.overall_timeout is None
    assert analyzer.timeout is None


def test_progress_bar_properties_are_settable():
    astrotruther = Astrotruther(parsers=[])
    highlight = Highlight(renderers=[])

    astrotruther.progress_bar = False
    highlight.progress_bar = False

    assert astrotruther.progress_bar is False
    assert highlight.progress_bar is False
