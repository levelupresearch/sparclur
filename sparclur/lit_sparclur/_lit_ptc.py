#Streamlit page for viewing warning and error messages

import os
import sys
import streamlit as st
module_path = os.path.abspath('../../')
if module_path not in sys.path:
    sys.path.append(module_path)
from sparclur.parsers.present_parsers import get_sparclur_tracers
from sparclur.parsers import MuPDF

TRACERS = [tracer.get_name() for tracer in get_sparclur_tracers()]


def app(parsers, **kwargs):
    st.subheader("Parser Trace Comparator")

    tracers = {p_name: parser for (p_name, parser) in parsers.items() if p_name in TRACERS or p_name == MuPDF.get_name()+'-s'}

    if len(tracers) == 0:
        st.write("Please select at least one of [%s]" % ', '.join(TRACERS))
    else:
        cols = st.beta_columns(min(len(tracers), 3))

        for idx, col in enumerate(cols):
            trace_selected = col.selectbox('Trace', [key for key in list(tracers.keys()) if key != MuPDF.get_name()+'-s'], index=idx, key='ts_%s' % str(idx))
            # binary_text = col.text_input('Binary Path', key='bt_%s' % str(idx))
            if trace_selected == MuPDF.get_name():
                parse_streams = col.checkbox('Parse Streams', key='cb_%s' % str(idx))
                if parse_streams:
                    trace_selected = MuPDF.get_name()+'-s'
                print(tracers[trace_selected].streams_parsed)
            message_type = col.radio('Messages', ['Raw', 'Cleaned'], key='mt_%s' % str(idx))
            tracer = tracers[trace_selected]
            if message_type == 'Raw':
                messages = tracer.messages
            else:
                messages = tracer.cleaned
            col.write(messages)
