from sparclur.parsers import PDFMiner, Ghostscript, MuPDF, PDFtoCairo, PDFtoPPM, PDFtoText, QPDF, MuDraw
from sparclur._parser import Parser
from sparclur._tracer import Tracer
from sparclur._renderer import Renderer
from sparclur._text_extractor import TextExtractor
from sparclur._metadata_extractor import MetadataExtractor

from typing import List, Dict


_sparclur_parsers: Dict[str, Parser] = {
        PDFMiner.get_name(): PDFMiner,
        Ghostscript.get_name(): Ghostscript,
        MuPDF.get_name(): MuPDF,
        MuDraw.get_name(): MuDraw,
        PDFtoCairo.get_name(): PDFtoCairo,
        PDFtoPPM.get_name(): PDFtoPPM,
        PDFtoText.get_name(): PDFtoText,
        QPDF.get_name(): QPDF
    }

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

def get_sparclur_texters():
    """Helper function that returns a list of all SPARCLUR TextExtractors"""
    present_texters: List[TextExtractor] = \
        [texter for texter in _sparclur_parsers.values() if issubclass(texter, TextExtractor)]
    return present_texters

def get_sparclur_metadata():
    """Helper function that returns a list of all SPARCLUR MetadataExtractors"""
    present_metadata: List[MetadataExtractor] = \
        [meta for meta in _sparclur_parsers.values() if issubclass(meta, MetadataExtractor)]
    return present_metadata
