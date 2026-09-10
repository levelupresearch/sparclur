# Streamlit for PRC Viz
import itertools

import streamlit as st

from sparclur.prc._viz import PRCViz
from sparclur.parsers.present_parsers import get_sparclur_renderers

RENDERERS = [r.get_name() for r in get_sparclur_renderers()]

# def get_viz(renderers):
#     filename = [renderer for renderer in renderers.values()][0].doc
#     return PRCViz(doc=filename, renderers=[renderer for renderer in renderers.values()])

def app(parsers, **kwargs):
    st.subheader("PDF Render Comparator")

    renderers = {p_name: parser for (p_name, parser) in parsers.items() if p_name in RENDERERS}

    if len(renderers) < 2:
        st.write("Please select at least 2 of [%s]" % ', '.join(RENDERERS))
    else:
        document_name = kwargs.get('document_name', 'uploaded.pdf')
        viz = PRCViz(doc_path=document_name, renderers=list(renderers.values()))
        # viz = get_viz(renderers)

        fig = viz.plot_sims()
        st.pyplot(fig)
        pair_labels = {
            f'{left} ↔ {right}': (left, right)
            for left, right in itertools.combinations(renderers, 2)
        }
        with st.form('prc-comparison-controls'):
            select_page = st.selectbox('Page', options=list(range(viz.get_observed_pages())))
            selected_labels = st.multiselect(
                'Renderer pairs',
                options=list(pair_labels),
                default=list(pair_labels)[:1],
                help='Select one pair for a focused comparison, or add pairs to stack them vertically.',
            )
            st.form_submit_button('Refresh comparison')
        if selected_labels:
            display_fig = viz.display(
                page=select_page,
                renderers=[pair_labels[label] for label in selected_labels],
                width=12,
                height=5,
            )
            st.pyplot(display_fig)
        else:
            st.info('Select at least one renderer pair to display a visual comparison.')
