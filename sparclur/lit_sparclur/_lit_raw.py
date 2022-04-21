import os
import sys
import streamlit as st
module_path = os.path.abspath('../../')
if module_path not in sys.path:
    sys.path.append(module_path)
from sparclur.lit_sparclur._non_parser import NonParser


def app(parsers, **kwargs):
    st.subheader("PDF File")

    st.write(parsers[NonParser.get_name()].get_raw())
