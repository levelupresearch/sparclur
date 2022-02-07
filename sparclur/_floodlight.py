from __future__ import annotations

import copy
import os
import shutil
import sys
import tempfile
from collections import defaultdict
from typing import List, Union, Dict, Any

import numpy as np
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor as Executor
from inspect import signature

import pandas as pd

from sparclur._parser import SparclurHash, TEXT, RENDER, META, REJECTED, REJECTED_AMBIG, VALID_WARNINGS, VALID, FONT, \
    TRACER
from sparclur.parsers import present_parsers, MuPDF, Ghostscript, Poppler
from sparclur._parser import Parser


AMBIGUOUS = 'Ambiguous'
RECOVERABLE = 'Recoverable'


def _overall_validity(parsers, doc, parser_args):

    validities = set([parser(doc, **parser_args.get(parser.get_name(), dict())).validity['status'] for parser in parsers])
    if REJECTED in validities:
        overall = REJECTED
    elif REJECTED_AMBIG in validities:
        overall = REJECTED_AMBIG
    elif VALID_WARNINGS in validities:
        overall = VALID_WARNINGS
    else:
        overall = VALID
    return overall


def _mapper(entry):
    doc_path = entry['path']
    parsers = entry['parsers']
    parser_args = entry['parser_args']

    orig_validity = _overall_validity(parsers, doc_path, parser_args)

    if orig_validity == VALID:
        result = {'status': VALID, 'reason': 'Original Valid'}
    else:
        mupdf_doc = MuPDF(doc_path).reforge
        mupdf_validity = _overall_validity(parsers, mupdf_doc, parser_args)
        if mupdf_validity != VALID:
            result = {'status': AMBIGUOUS, 'reason': 'MuPDF: %s' % mupdf_validity}
        else:
            ghost_doc = Ghostscript(doc_path).reforge
            ghost_validity = _overall_validity(parsers, ghost_doc, parser_args)
            if ghost_validity !=VALID:
                result = {'status': AMBIGUOUS, 'reason': 'GS: %s' % ghost_validity}
            else:
                pop_doc = Poppler(doc_path).reforge
                pop_validity = _overall_validity(parsers, pop_doc, parser_args)
                if pop_validity != VALID:
                    result = {'status': AMBIGUOUS, 'reason': 'Poppler: %s' % pop_validity}
                else:
                    result = {'status': RECOVERABLE, 'reason': 'All translations valid'}
    return result


# class FloodLight:
