# Streamlit for PRC Viz
import streamlit as st
import os
import sys
module_path = os.path.abspath('../../../sparclur/')
if module_path not in sys.path:
    sys.path.append(module_path)
from sparclur.prc.viz import PRCViz


def app(filename):
    st.subheader("PDF Render Comparator")

    viz = PRCViz(doc_path=filename, renderers=['MuPDF', 'Poppler', 'Ghostscript'])

    fig = viz.plot_ssims()
    st.pyplot(fig)
    select_page = st.selectbox('Page', options=list(range(viz.get_observed_pages())))
    display_fig = viz.display(page=select_page)
    st.pyplot(display_fig)
