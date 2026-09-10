import streamlit as st
import itertools
import pandas as pd

from sparclur._text_compare import TextCompare


def app(parsers, **kwargs):
    st.subheader("Parser Text Comparator")

    # ocr = kwargs['ocr']

    texters = dict()

    for name, parser in parsers.items():
        if isinstance(parser, TextCompare) and parser.can_extract_text:
            texters[name] = parser

    if not texters:
        st.info("Enable a text extractor or OCR-capable renderer to use PXC.")
    elif len(texters) == 1:
        texter = [txtr for txtr in texters.values()][0]
        st.write(texter.get_name())
        text = texter.get_text()
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

        cols = st.columns(2)

        for idx, col in enumerate(cols):
            texter_selected = col.selectbox('Text', list(texters.keys()), index=idx, key='tx_%s' % str(idx))
            texter = texters[texter_selected]
            text = texter.get_text()
            pages = list(text.keys())
            pages.sort()
            page_selected = col.selectbox('Page', pages, key='%s_ps_%s' % (texter.get_name(), str(idx)))
            page_text = text[page_selected]
            col.write(page_text)
