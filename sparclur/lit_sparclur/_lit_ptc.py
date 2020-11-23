#Streamlit page for viewing warning and error messages

import streamlit as st
import os
import sys

from sparclur._tracer import Tracer

module_path = os.path.abspath('../../../sparclur/')
if module_path not in sys.path:
    sys.path.append(module_path)
from sparclur.parsers.present_parsers import get_sparclur_tracers
from sparclur.parsers.mupdf import MuPDF

TRACERS = {tracer.get_name(): tracer for tracer in get_sparclur_tracers()}


def app(filename):
    st.subheader("Parser Trace Comparator")

    cols = st.beta_columns(min(len(TRACERS), 3))

    for idx, col in enumerate(cols):
        trace_selected = col.selectbox('Trace', list(TRACERS.keys()), index=idx, key='ts_%s' % str(idx))
        binary_text = col.text_input('Binary Path', key='bt_%s' % str(idx))
        if trace_selected == 'MuPDF':
            parse_streams = col.checkbox('Parse Streams', key='cb_%s' % str(idx))
        message_type = col.radio('Messages', ['Raw', 'Cleaned'], key='mt_%s' % str(idx))
        tracer = TRACERS[trace_selected]
        if trace_selected == 'MuPDF':
            mu_binary = None if binary_text == '' else binary_text
            tracer: MuPDF = tracer(filename, parse_streams=parse_streams, binary_path=mu_binary)
        else:
            binary = None if binary_text == '' else binary_text
            tracer: Tracer = tracer(filename, binary_path=binary)
        if message_type == 'Raw':
            messages = tracer.get_messages()
        else:
            messages = tracer.get_cleaned()
        col.write(messages)
