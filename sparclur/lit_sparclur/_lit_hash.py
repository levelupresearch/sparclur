"""Streamlit controls for SPARCLUR hash baselines."""

from __future__ import annotations

import json

import streamlit as st

from sparclur._parser import HashComparisonPolicy, SparclurHash


def _component_rows(comparison):
    """Format component outcomes for a compact Streamlit table."""
    rows = []
    for component, result in sorted(comparison['components'].items()):
        rows.append({
            'Component': component,
            'Similarity': result.get('sim'),
            'Current': result['left']['status'],
            'Baseline': result['right']['status'],
            'Settings match': result['settings_match'],
        })
    return rows


def app(parsers, **kwargs):
    """Render the downloadable-baseline and comparison workflow."""
    st.subheader('Hash Baseline')
    st.caption('Save a parser-output baseline, then compare the current PDF against it.')
    selected_name = st.selectbox('Parser result', options=list(parsers), key='hash-baseline-parser')
    current_hash = parsers[selected_name].sparclur_hash
    document_name = kwargs.get('document_name', 'uploaded.pdf')
    baseline_name = f'{document_name.rsplit(".", 1)[0]}-{selected_name}-baseline.json'

    st.download_button(
        'Download current baseline',
        data=json.dumps(current_hash.to_dict(), indent=2, sort_keys=True),
        file_name=baseline_name,
        mime='application/json',
    )

    with st.expander('Current evidence', expanded=False):
        st.json(current_hash.metadata)
        st.json(current_hash.component_outcomes)

    uploaded_baseline = st.file_uploader(
        'Compare with a baseline JSON file',
        type=['json'],
        key='hash-baseline-upload',
    )
    if uploaded_baseline is None:
        st.info('Download a baseline above or upload an existing one to compare it with this parser result.')
        return

    try:
        baseline = SparclurHash.from_dict(json.loads(uploaded_baseline.getvalue()))
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        st.error(f'The selected baseline is not valid: {error}')
        return

    with st.form('hash-baseline-comparison'):
        compatibility = st.selectbox(
            'Compatibility mode',
            options=['warn', 'strict', 'ignore'],
            help='Strict mode rejects changed hash algorithms or changed provenance for the same parser adapter.',
        )
        minimum_similarity = st.number_input(
            'Minimum similarity', min_value=0.0, max_value=1.0, value=1.0, step=0.01,
        )
        page_aggregation = st.selectbox('Page aggregation', options=['min', 'mean'])
        submitted = st.form_submit_button('Compare baseline')

    if not submitted:
        return

    comparison = current_hash.compare(
        baseline,
        policy=HashComparisonPolicy(page_aggregation=page_aggregation),
        compatibility=compatibility,
    )
    similarity = comparison['sim']
    st.metric('Overall similarity', 'Unavailable' if similarity is None else f'{similarity:.4f}')
    if comparison['warnings']:
        for warning in comparison['warnings']:
            st.warning(warning)
    if comparison.passes(minimum_similarity=minimum_similarity):
        st.success('The baseline comparison meets the selected threshold.')
    else:
        st.error('The baseline comparison did not meet the selected threshold.')
        st.json(comparison.failures(minimum_similarity=minimum_similarity))
    st.dataframe(_component_rows(comparison), hide_index=True, use_container_width=True)
