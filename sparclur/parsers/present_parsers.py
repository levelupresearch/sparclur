from inspect import isclass

from sparclur.parsers import PDFMiner, Ghostscript, MuPDF, Poppler, XPDF, QPDF, PDFBox
from sparclur._parser import Parser
from sparclur._tracer import Tracer
from sparclur._renderer import Renderer
from sparclur._hybrid import Hybrid
from sparclur._text_compare import TextCompare
from sparclur._metadata_extractor import MetadataExtractor
from sparclur._text_extractor import TextExtractor
from sparclur._font_extractor import FontExtractor

from typing import List, Dict


_sparclur_parsers: Dict[str, Parser] = {
        PDFMiner.get_name(): PDFMiner,
        Ghostscript.get_name(): Ghostscript,
        MuPDF.get_name(): MuPDF,
        Poppler.get_name(): Poppler,
        XPDF.get_name(): XPDF,
        QPDF.get_name(): QPDF,
        PDFBox.get_name(): PDFBox
    }


def get_parser(parser):
    if isinstance(parser, str):
        assert parser in _sparclur_parsers, 'Parser not found'
        result = _sparclur_parsers[parser]
    elif isclass(parser):
        try:
            class_name = parser.get_name()
            assert class_name in _sparclur_parsers, 'Parser not found'
            result = parser
        except:
            print('Parser not found')
            result = None
    elif isinstance(parser, Parser):
        assert parser.get_name() in _sparclur_parsers, 'Parser not found'
        result = _sparclur_parsers[parser.get_name()]
    else:
        print('Parser not found')
        result = None
    return result

def get_sparclur_parsers():
    """Helper function that returns a list of all SPARCLUR Parsers"""
    present_parsers: List[Parser] = [parser for parser in _sparclur_parsers.values()]
    return present_parsers


def get_sparclur_renderers():
    """Helper function that returns a list of all SPARCLUR Renderers"""
    present_renderers: List[Renderer] = \
        [renderer for renderer in _sparclur_parsers.values() if issubclass(renderer, Renderer)]
    return present_renderers


def get_sparclur_tracers():
    """Helper function that returns a list of all SPARCLUR Tracers"""
    present_tracers: List[Tracer] = \
        [tracer for tracer in _sparclur_parsers.values() if issubclass(tracer, Tracer)]
    return present_tracers


def get_sparclur_texters(no_ocr=False):
    """Helper function that returns a list of all SPARCLUR TextExtractors"""
    present_texters: List[TextCompare] = \
        [texter for texter in _sparclur_parsers.values() if issubclass(texter, TextCompare)]
    if no_ocr:
        present_texters: List[TextCompare] = \
            [texter for texter in present_texters if issubclass(texter, TextExtractor) or issubclass(texter, Hybrid)]
    return present_texters


def get_sparclur_metadata():
    """Helper function that returns a list of all SPARCLUR MetadataExtractors"""
    present_metadata: List[MetadataExtractor] = \
        [meta for meta in _sparclur_parsers.values() if issubclass(meta, MetadataExtractor)]
    return present_metadata


def get_sparclur_fonts():
    present_fonts: List[FontExtractor] = \
        [font for font in _sparclur_parsers.values() if issubclass(font, FontExtractor)]
    return present_fonts