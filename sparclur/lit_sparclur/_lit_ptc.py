#Streamlit page for viewing warning and error messages

import streamlit as st

from sparclur.parsers.present_parsers import get_sparclur_tracers
TRACERS = [tracer.get_name() for tracer in get_sparclur_tracers()]
MUPDF_NAME = "MuPDF"


def app(parsers, **kwargs):
    st.subheader("Parser Trace Comparator")

    tracers = {p_name: parser for (p_name, parser) in parsers.items() if p_name in TRACERS or p_name == MUPDF_NAME+'-s'}

    if len(tracers) == 0:
        st.write("Please select at least one of [%s]" % ', '.join(TRACERS))
    else:
        cols = st.columns(min(len(tracers), 3))

        for idx, col in enumerate(cols):
            trace_selected = col.selectbox('Trace', [key for key in list(tracers.keys()) if key != MUPDF_NAME+'-s'], index=idx, key='ts_%s' % str(idx))
            # binary_text = col.text_input('Binary Path', key='bt_%s' % str(idx))
            if trace_selected == MUPDF_NAME:
                parse_streams = col.checkbox('Parse Streams', key='cb_%s' % str(idx))
                if parse_streams:
                    trace_selected = MUPDF_NAME+'-s'
                print(tracers[trace_selected].streams_parsed)
            message_type = col.radio('Messages', ['Raw', 'Cleaned'], key='mt_%s' % str(idx))
            tracer = tracers[trace_selected]
            if message_type == 'Raw':
                messages = tracer.messages
            else:
                messages = tracer.cleaned
            col.write(messages)
