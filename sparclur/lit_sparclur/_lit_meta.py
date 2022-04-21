import os
import sys
import streamlit as st
module_path = os.path.abspath('../../')
if module_path not in sys.path:
    sys.path.append(module_path)
from sparclur.parsers.present_parsers import get_sparclur_metadata
from sparclur.parsers import PDFMiner

METAS = [metas.get_name() for metas in get_sparclur_metadata()]


def sort_transform(obj):
    if obj.count('trailer') > 0:
        return -1
    else:
        return int(obj.split(' ')[0])


def app(parsers, **kwargs):
    st.subheader("Parser Text Comparator")

    metas = {p_name: parser for (p_name, parser) in parsers.items() if p_name in METAS or p_name == PDFMiner.get_name()+'-text'}

    if len(metas) == 0:
        st.write("No metadata extractors selected")
    else:
        if len(metas) == 1:
            meta_selected = [m for m in metas.keys()][0]
            st.write(meta_selected)
        else:
            meta_selected = st.selectbox('Metadata Extractors', [key for key in list(metas.keys()) if key !=PDFMiner.get_name()+'-text'], key='me_select')
            if meta_selected == PDFMiner.get_name():
                pdfm_stream = st.checkbox('Show data streams', key='me_pdfm_stream')
                if pdfm_stream:
                    meta_selected = PDFMiner.get_name()+'-text'
                else:
                    meta_selected = PDFMiner.get_name()
                print(meta_selected)
                print(metas[meta_selected].stream_output)
        meta = metas[meta_selected]
        metadata = meta.metadata if meta.metadata is not None else dict()
        print(meta.metadata_result)
        objects = list(metadata.keys())
        objects.sort(key=lambda x: sort_transform(x))
        object_selected = st.selectbox('PDF Object', objects, key='me_object_select')
        if object_selected is not None:
            st.write(metadata[object_selected])
        else:
            st.write("Metadata failed to load: %s" % meta.metadata_result)
