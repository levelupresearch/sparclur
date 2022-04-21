# Streamlit for PRC Viz
import streamlit as st
import os
import sys

module_path = os.path.abspath('../../')
if module_path not in sys.path:
    sys.path.append(module_path)
from sparclur.prc._viz import PRCViz
from sparclur.parsers.present_parsers import get_sparclur_renderers

RENDERERS = [r.get_name() for r in get_sparclur_renderers()]

# @st.cache
# def get_viz(renderers):
#     filename = [renderer for renderer in renderers.values()][0].doc
#     return PRCViz(doc=filename, renderers=[renderer for renderer in renderers.values()])

def app(parsers, **kwargs):
    st.subheader("PDF Render Comparator")

    renderers = {p_name: parser for (p_name, parser) in parsers.items() if p_name in RENDERERS}

    if len(renderers) < 2:
        st.write("Please select at least 2 of [%s]" % ', '.join(RENDERERS))
    else:
        filename = [renderer for renderer in renderers.values()][0].doc
        viz = PRCViz(doc=filename, renderers=[renderer for renderer in renderers.values()])
        # viz = get_viz(renderers)

        fig = viz.plot_sims()
        st.pyplot(fig)
        select_page = st.selectbox('Page', options=list(range(viz.get_observed_pages())))
        display_fig = viz.display(page=select_page)
        st.pyplot(display_fig)
