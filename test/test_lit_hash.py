"""Tests for the Streamlit hash-baseline presentation helpers."""

from sparclur.lit_sparclur._lit_hash import _component_rows


def test_component_rows_expose_outcomes_and_scores():
    rows = _component_rows({
        'components': {
            'Renderer': {
                'sim': 0.99,
                'left': {'status': 'ok'},
                'right': {'status': 'unavailable'},
                'settings_match': True,
            },
        },
    })

    assert rows == [{
        'Component': 'Renderer',
        'Similarity': 0.99,
        'Current': 'ok',
        'Baseline': 'unavailable',
        'Settings match': True,
    }]
