"""Tests for Streamlit parser-setting introspection."""

from sparclur.lit_sparclur._lit_helper import parse_init
from sparclur.parsers import MuPDF


def test_parser_setting_types_support_modern_union_annotations():
    params = parse_init(MuPDF)

    assert params['ocr'] == {'default': None, 'param_type': 'bool'}
    assert params['dpi'] == {'default': None, 'param_type': 'int'}
