import os
import sys

module_path = os.path.abspath('../../../sparclur/')
if module_path not in sys.path:
    sys.path.append(module_path)

from sparclur.lit_sparclur import _lit_ptc, _lit_prc
from sparclur.utils.tools import create_file_list

import streamlit as st
from func_timeout import func_timeout


st.set_option('deprecation.showPyplotGlobalUse', False)

st.title('Lit Sparclur')

PAGES = {
    "PTC": _lit_ptc,
    "PRC": _lit_prc
}


# def get_file_list(dir, recurse, base):
#     return create_file_list(files=dir, recurse=recurse, base_path=base)


st.sidebar.title("Navigation")
selection = st.sidebar.radio("Go to", list(PAGES.keys()), key='c')
page = PAGES[selection]

st.sidebar.write("File Selection")
base_dir_input = st.sidebar.text_input('Base Directory', '.', key='d')
base_dir = st.sidebar.checkbox('Set base directory', key='e')
recurse = st.sidebar.checkbox('Recurse into base directory', key='f')

if os.path.isfile(base_dir_input):
    filepath = base_dir_input
else:
    try:
        file_list = func_timeout(45, create_file_list, kwargs={'files': base_dir_input, 'recurse': recurse, 'base_path': base_dir_input if base_dir else None})
        num_files = len(file_list)
    except Exception as e:
        file_list = []
        num_files = 0
    if len(file_list) > 50 or len(file_list) == 0:
        filename = st.sidebar.text_input('File', '', key='a')
        filepath = os.path.join(base_dir_input, filename)
    else:
        file_dict = {file.split('/')[-1]: file for file in file_list}
        filepath = st.sidebar.selectbox('Select a file', list(file_dict.keys()), key='b')
        filepath = file_dict[filepath]

page.app(filepath)
