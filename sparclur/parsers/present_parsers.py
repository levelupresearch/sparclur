import site
import sys
from pathlib import Path
from inspect import isclass

from sparclur._reforge import Reforger
from sparclur.parsers import PDFMiner, Ghostscript, MuPDF, Poppler, XPDF, QPDF, Arlington, PDFCPU, PDFium
from sparclur._parser import Parser
from sparclur._tracer import Tracer
from sparclur._renderer import Renderer
from sparclur._hybrid import Hybrid
from sparclur._text_compare import TextCompare
from sparclur._metadata_extractor import MetadataExtractor
from sparclur._text_extractor import TextExtractor
from sparclur._font_extractor import FontExtractor
from sparclur._image_data_extractor import ImageDataExtractor

from typing import Any

_sparclur_parsers: dict[str, Parser] = {
        PDFMiner.get_name(): PDFMiner,
        Ghostscript.get_name(): Ghostscript,
        MuPDF.get_name(): MuPDF,
        Poppler.get_name(): Poppler,
        XPDF.get_name(): XPDF,
        QPDF.get_name(): QPDF,
        Arlington.get_name(): Arlington,
        PDFCPU.get_name(): PDFCPU,
        PDFium.get_name(): PDFium
        #PDFBox.get_name(): PDFBox
    }

_SOURCE_ROOT = Path(__file__).resolve().parents[2]
_RESOURCE_PATHS = (
    _SOURCE_ROOT / 'resources' / 'min_vi.pdf',
    Path(site.USER_BASE) / 'etc' / 'sparclur' / 'resources' / 'min_vi.pdf',
    Path(sys.prefix) / 'etc' / 'sparclur' / 'resources' / 'min_vi.pdf',
)
min_pdf = next((str(path) for path in _RESOURCE_PATHS if path.is_file()), b'')

def get_parser(parser):
    if isinstance(parser, str):
        assert parser in _sparclur_parsers, 'Parser not found'
        result = _sparclur_parsers[parser]
    elif isclass(parser):
        try:
            class_name = parser.get_name()
            assert class_name in _sparclur_parsers, 'Parser not found'
            result = parser
        except Exception:
            print('Parser not found')
            result = None
    elif isinstance(parser, Parser):
        assert parser.get_name() in _sparclur_parsers, 'Parser not found'
        result = _sparclur_parsers[parser.get_name()]
    else:
        print('Parser not found')
        result = None
    return result


def get_sparclur_parsers(check_parsers: bool = False,
                         parser_args: dict[str, dict[str, Any]] | None = None):
    """Helper function that returns a list of all SPARCLUR Parsers"""
    parser_args = {} if parser_args is None else parser_args
    present_parsers: list[Parser] = [parser for parser in _sparclur_parsers.values()]
    if check_parsers:
        good_to_go_parsers = []
        for parser in present_parsers:
            args = dict(parser_args.get(parser.get_name(), {}))
            args['skip_check'] = False
            try:
                p = parser(min_pdf, **args)
            except Exception:
                # Optional adapters can require an externally configured path
                # before their own capability properties are available.
                continue
            if issubclass(parser, Renderer):
                renderer_present = p.can_render
                if not renderer_present:
                    continue
            if issubclass(parser, Tracer):
                tracer_present = p.can_trace
                if not tracer_present:
                    continue
            if issubclass(parser, TextExtractor):
                text_extraction_present = p.can_extract_text
                if not text_extraction_present:
                    continue
            if issubclass(parser, MetadataExtractor):
                meta_present = p.can_extract_metadata
                if not meta_present:
                    continue
            if issubclass(parser, FontExtractor):
                font_present = p.can_extract_font
                if not font_present:
                    continue
            if issubclass(parser, Reforger):
                reforge_present = p.can_reforge
                if not reforge_present:
                    continue
            if issubclass(parser, ImageDataExtractor):
                imager_present = p.can_extract_image_data
                if not imager_present:
                    continue
            good_to_go_parsers.append(parser)
        return good_to_go_parsers
    else:
        return present_parsers


def get_sparclur_renderers():
    """Helper function that returns a list of all SPARCLUR Renderers"""
    present_renderers: list[Renderer] = \
        [renderer for renderer in _sparclur_parsers.values() if issubclass(renderer, Renderer)]
    return present_renderers


def get_sparclur_tracers():
    """Helper function that returns a list of all SPARCLUR Tracers"""
    present_tracers: list[Tracer] = \
        [tracer for tracer in _sparclur_parsers.values() if issubclass(tracer, Tracer)]
    return present_tracers


def get_sparclur_texters(no_ocr=False):
    """Helper function that returns a list of all SPARCLUR TextExtractors"""
    present_texters: list[TextCompare] = \
        [texter for texter in _sparclur_parsers.values() if issubclass(texter, TextCompare)]
    if no_ocr:
        present_texters: list[TextCompare] = \
            [texter for texter in present_texters if issubclass(texter, TextExtractor) or issubclass(texter, Hybrid)]
    return present_texters


def get_sparclur_metadata():
    """Helper function that returns a list of all SPARCLUR MetadataExtractors"""
    present_metadata: list[MetadataExtractor] = \
        [meta for meta in _sparclur_parsers.values() if issubclass(meta, MetadataExtractor)]
    return present_metadata


def get_sparclur_fonts():
    present_fonts: list[FontExtractor] = \
        [font for font in _sparclur_parsers.values() if issubclass(font, FontExtractor)]
    return present_fonts


def get_sparclur_reforgers():
    present_reforgers: list[Reforger] = \
        [reforger for reforger in _sparclur_parsers.values() if issubclass(reforger, Reforger)]
    return present_reforgers


def get_sparclur_imagers():
    present_imagers: list[ImageDataExtractor] = \
        [imager for imager in _sparclur_parsers.values() if issubclass(imager, ImageDataExtractor)]
    return present_imagers
