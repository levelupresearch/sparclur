#Streamlit page for viewing warning and error messages

import os
import sys
module_path = os.path.abspath('../../../sparclur/')
if module_path not in sys.path:
    sys.path.append(module_path)
from sparclur.parsers.present_parsers import get_sparclur_tracers
from sparclur.parsers import MuPDF

import streamlit as st

from sparclur._tracer import Tracer


TRACERS = [tracer.get_name() for tracer in get_sparclur_tracers()]


def app(filename, parsers):
    st.subheader("Parser Trace Comparator")

    tracers = {p_name: parser for (p_name, parser) in parsers.items() if p_name in TRACERS or p_name == MuPDF.get_name()+'-s'}

    if len(tracers) == 0:
        st.write("Please select at least one of [%s]" % ', '.join(TRACERS))
    else:
        cols = st.beta_columns(min(len(tracers), 3))

        for idx, col in enumerate(cols):
            trace_selected = col.selectbox('Trace', list(tracers.keys()), index=idx, key='ts_%s' % str(idx))
            binary_text = col.text_input('Binary Path', key='bt_%s' % str(idx))
            if trace_selected == MuPDF.get_name():
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
                messages = tracer.messages
            else:
                messages = tracer.cleaned
            col.write(messages)
