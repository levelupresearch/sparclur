import streamlit as st
import os
import sys
import itertools
import pandas as pd

module_path = os.path.abspath('../../../sparclur/')
if module_path not in sys.path:
    sys.path.append(module_path)
from sparclur.parsers.present_parsers import get_sparclur_texters

TEXTERS = [texter.get_name() for texter in get_sparclur_texters()]

print(TEXTERS)
def app(parsers):
    st.subheader("Parser Text Comparator")

    texters = {p_name: parser for (p_name, parser) in parsers.items() if p_name in TEXTERS}

    if len(texters) == 1:
        texter = [txtr for txtr in texters.values()][0]
        print(texter.get_name())
        text = texter.get_text()
        print(text)
        page_selected = st.selectbox('Page', list(text.keys()), key='ps_%s' % texter.get_name())
        page_text = text[page_selected]
        st.write(page_text)
    else:
        present_texters = list(texters.keys())
        metrics = dict()
        comparisons = list(itertools.combinations(present_texters, 2))
        for combo in comparisons:
            metrics[frozenset(combo)] = texters[combo[0]].compare_text(texters[combo[1]])
        data = []
        for left in present_texters:
            row = dict()
            row[''] = left
            for top in present_texters:
                row[top] = 1 if left == top else 1 - metrics[frozenset((left, top))]
            data.append(row)
        df = pd.DataFrame(data)
        st.write("Jaccard Similarity")
        st.dataframe(df)

        cols = st.beta_columns(2)

        for idx, col in enumerate(cols):
            texter_selected = col.selectbox('Text', list(texters.keys()), index=idx, key='tx_%s' % str(idx))
            texter = texters[texter_selected]
            text = texter.get_text()
            print(list(text.keys()))
            page_selected = col.selectbox('Page', list(text.keys()), key='%s_ps_%s' % (texter.get_name(), str(idx)))
            page_text = text[page_selected]
            col.write(page_text)
