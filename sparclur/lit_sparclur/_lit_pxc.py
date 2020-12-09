import streamlit as st
import os
import sys

from sparclur._text_extractor import TextExtractor
from sparclur.parsers import PDFtoPPM, PDFtoText

module_path = os.path.abspath('../../../sparclur/')
if module_path not in sys.path:
    sys.path.append(module_path)
from sparclur.parsers.present_parsers import get_sparclur_texters, get_sparclur_renderers

TEXTERS = {texter.get_name(): texter for texter in get_sparclur_texters()}
BINARY_PARAM = [
                PDFtoPPM.get_name(),
                PDFtoText.get_name()
            ]

RENDERERS = [r.get_name() for r in get_sparclur_renderers()]


def app(filename):
    st.subheader("Parser Text Comparator")

    cols = st.beta_columns(min(len(TEXTERS), 3))

    for idx, col in enumerate(cols):
        texter_selected = col.selectbox('Text', list(TEXTERS.keys()), index=idx, key='tx_%s' % str(idx))
        if texter_selected in BINARY_PARAM:
            binary_text = col.text_input('Binary Path', key='bx_%s' % str(idx))
        texter = TEXTERS[texter_selected]
        extra_args = dict()
        if texter in RENDERERS:
            extra_args['cache_renders'] = True
        if texter_selected in BINARY_PARAM:
            binary = None if binary_text == '' else binary_text
            texter: TextExtractor = texter(filename, binary_path=binary, **extra_args)
        else:
            texter: TextExtractor = texter(filename, **extra_args)
        text = texter.get_text()
        page_selected = col.selectbox('Page', list(text.keys()), key='ps_%s' % str(idx))
        page_text = text[page_selected]
        col.write(page_text)