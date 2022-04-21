import os
import sys

module_path = os.path.abspath('../../')
if module_path not in sys.path:
    sys.path.append(module_path)

from sparclur.parsers import MuPDF, PDFMiner
from sparclur.lit_sparclur import _lit_prc, _lit_pxc
from sparclur.lit_sparclur import _lit_meta
from sparclur.lit_sparclur import _lit_ptc, _lit_raw
from sparclur.lit_sparclur._non_parser import NonParser
from sparclur.lit_sparclur._lit_helper import parse_init
from sparclur.utils._tools import create_file_list, is_pdf

from sparclur.parsers.present_parsers import get_sparclur_texters, \
    get_sparclur_renderers, \
    get_sparclur_tracers, \
    get_sparclur_parsers, \
    get_sparclur_metadata

import streamlit as st
from func_timeout import func_timeout

PARSERS = {parser.get_name(): parser for parser in get_sparclur_parsers()}

TEXTERS = [texter.get_name() for texter in get_sparclur_texters(no_ocr=True)]

RENDERERS = [r.get_name() for r in get_sparclur_renderers()]

TRACERS = [tracer.get_name() for tracer in get_sparclur_tracers()]

METAS = [metas.get_name() for metas in get_sparclur_metadata()]

st.set_option('deprecation.showPyplotGlobalUse', False)

st.title('Lit Sparclur')

PAGES = {
    # "Select Parsers": "select",
    "PTC": _lit_ptc,
    "PRC": _lit_prc,
    "PXC": _lit_pxc,
    "Metadata": _lit_meta,
    "Raw": _lit_raw
}

# def get_file_list(dir, recurse, base):
#     return create_file_list(files=dir, recurse=recurse, base_path=base)


st.sidebar.title("Navigation")
selection = st.sidebar.radio("Go to", list(PAGES.keys()), key='c')
page = PAGES[selection]

st.sidebar.write("File Selection")
base_dir_input = st.sidebar.text_input('path', '.', key='d')
recurse = st.sidebar.checkbox('Recurse into base directory', key='f')


@st.cache
def parse_document(selected_parser_kwargs):
    p = dict()

    for name, kwa in selected_parser_kwargs.items():
        if name == NonParser.get_name():
            p[name] = NonParser(**kwargs)
        elif name == MuPDF.get_name() + '-s':
            p[name] = MuPDF(**kwa)
            _ = p[name].cleaned
        elif name == PDFMiner.get_name() + '-text':
            p[name] = PDFMiner(**kwa)
            _ = p[name].metadata
        else:
            p[name] = PARSERS[name](**kwa)
        if p[name].get_name() in TRACERS:
            _ = p[name].cleaned
        if p[name].get_name() in RENDERERS:
            _ = p[name].get_renders()
        if p[name].get_name() in TEXTERS:
            _ = p[name].get_tokens()
        if p[name].get_name() in METAS:
            _ = p[name].metadata

    return p


if os.path.isfile(base_dir_input):
    filepath = base_dir_input
else:
    try:
        file_list = func_timeout(
            45,
            create_file_list,
            kwargs={
                'files': base_dir_input,
                'recurse': recurse
            })

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

parser_kwargs = dict()
parser_kwargs[NonParser.get_name()] = {'doc': filepath}
st.sidebar.markdown('___')
ocr = st.sidebar.checkbox('OCR', value=False, key='ocr')
#render_cache = st.sidebar.checkbox('Cache Renders', value=False, key='render_cache')
dpi = st.sidebar.number_input('DPI', min_value=72, max_value=400, value=72,
                              key='dpi')
st.sidebar.markdown('___')
for p_name, parser in PARSERS.items():
    use_parser = st.sidebar.checkbox(p_name, value=True, key='%s_cb' % p_name)

    if use_parser:
        params = parse_init(parser)
        kwargs = dict()
        for key, values in params.items():
            default = values['default']
            param_type = values['param_type']
            print(key, default, param_type)
            if key == 'cache_renders':
                val = True
            elif key == 'temp_folders_dir':
                val = None
            elif key == 'timeout':
                val = 30
            elif key == 'dpi':
                val = dpi
            elif param_type == 'bool':
                val = st.sidebar.checkbox(key, value=True if default == 'True' else False, key='%s_%s' % (p_name, key))
            elif param_type == 'Tuple[int]':
                width = st.sidebar.number_input("Width", min_value=0, value=0, key='%s_%s_width' % (p_name, key))
                height = st.sidebar.number_input("Height", min_value=0, value=0, key='%s_%s_height' % (p_name, key))
                if width == 0 and height != 0:
                    val = height
                elif height == 0 and width != 0:
                    val = width
                elif height != 0 and width != 0:
                    val = (width, height)
                else:
                    val = None
            elif param_type == 'int':
                val = st.sidebar.number_input(key, min_value=72, max_value=400, value=int(default),
                                              key='%s_%s' % (p_name, key))
            else:
                val = st.sidebar.text_input(key, value=default, key='%s_%s' % (p_name, key))
                if not val or val == 'None':
                    val = None
                if val == "\\x0c":
                    val = "\x0c"
            kwargs[key] = val
            kwargs['doc'] = filepath
        print(p_name, kwargs)
        if p_name == MuPDF.get_name():
            ps_kwargs = {key: value for (key, value) in kwargs.items()}
            ps_kwargs['parse_streams'] = True
            kwargs['parse_streams'] = False
            parser_kwargs[p_name + '-s'] = ps_kwargs
            parser_kwargs[p_name] = kwargs
        elif p_name == PDFMiner.get_name():
            so_kwargs = {key: value for (key, value) in kwargs.items()}
            so_kwargs['stream_output'] = 'text'
            kwargs['stream_output'] = None
            parser_kwargs[p_name + '-text'] = so_kwargs
            parser_kwargs[p_name] = kwargs
        else:
            parser_kwargs[p_name] = kwargs
    st.sidebar.markdown('___')

if not is_pdf(filepath):
    st.write("Please select a PDF")
else:
    parsers = parse_document(parser_kwargs)
    page.app(parsers, ocr = False)
    # if isinstance(page, str):
    #     st.subheader("Select Parsers")
    #     parsers = parser_select(filepath)
    # else:
    #     if parsers is None:
    #         st.write("Please select parsers")
    #     else:
    #         page.app(parsers)
