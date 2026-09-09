import streamlit as st

from sparclur.lit_sparclur._non_parser import NonParser


def app(parsers, **kwargs):
    st.subheader("PDF File")

    st.write(parsers[NonParser.get_name()].get_raw())
