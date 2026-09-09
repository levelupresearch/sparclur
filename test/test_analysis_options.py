"""Regression tests for analysis option isolation."""

from sparclur._astrotruther import Astrotruther
from sparclur._detect_chaos import DetectChaos


def test_analysis_instances_do_not_share_default_option_dictionaries():
    first_astrotruther = Astrotruther(parsers=[])
    second_astrotruther = Astrotruther(parsers=[])
    first_chaos = DetectChaos(parsers=[])
    second_chaos = DetectChaos(parsers=[])

    first_astrotruther.parser_args["PDFium"] = {"dpi": 72}
    first_astrotruther.classifier_args["random_state"] = 1
    first_chaos.parser_args["MuPDF"] = {"timeout": 30}

    assert second_astrotruther.parser_args == {}
    assert second_astrotruther.classifier_args == {}
    assert second_chaos.parser_args == {}
