import os
import sys



module_path = os.path.abspath('../../../sparclur/')
if module_path not in sys.path:
    sys.path.append(module_path)
from sparclur._tracer import Tracer
from sparclur._renderer import Renderer
from sparclur._text_extractor import TextExtractor

from sparclur.parsers import MuPDF
from sparclur.lit_sparclur import _lit_ptc, _lit_prc, _lit_pxc
from sparclur.lit_sparclur._lit_helper import parse_init
from sparclur.utils.tools import create_file_list, is_pdf

from sparclur.parsers.present_parsers import get_sparclur_texters, \
    get_sparclur_renderers, \
    get_sparclur_tracers, \
    get_sparclur_parsers

import streamlit as st
from func_timeout import func_timeout


PARSERS = {parser.get_name(): parser for parser in get_sparclur_parsers()}

TEXTERS = [texter.get_name()for texter in get_sparclur_texters()]

RENDERERS = [r.get_name() for r in get_sparclur_renderers()]

TRACERS = [tracer.get_name() for tracer in get_sparclur_tracers()]

st.set_option('deprecation.showPyplotGlobalUse', False)

st.title('Lit Sparclur')

PAGES = {
    # "Select Parsers": "select",
    "PTC": _lit_ptc,
    "PRC": _lit_prc,
    "PXC": _lit_pxc
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

# @st.cache
# def parser_select(parser_kwargs):
#     parsers = dict()
#
#     for p_name, parser in PARSERS.items():
#         use_parser = st.checkbox(p_name, value=True, key='%s_cb' % p_name)
#
#         if use_parser:
#             params = parse_init(parser)
#             kwargs = dict()
#             for key, values in params.items():
#                 default = values['default']
#                 param_type = values['param_type']
#                 print(key, default, param_type)
#                 if key == 'cache_renders':
#                     val = True
#                 elif key == 'temp_folders_dir':
#                     val = None
#                 elif param_type == 'bool':
#                     val = st.checkbox(key, value=True if default == 'True' else False, key='%s_%s' % (p_name, key))
#                 elif param_type == 'Tuple[int]':
#                     width = st.number_input("Width", min_value=0, key='%s_%s_width' % (p_name, key))
#                     height = st.number_input("Height", min_value=0, key='%s_%s_height' % (p_name, key))
#                     if width == 0 and height != 0:
#                         val = height
#                     elif height == 0 and width != 0:
#                         val = width
#                     elif height != 0 and width != 0:
#                         val = (width, height)
#                     else:
#                         val = None
#                 elif param_type == 'int':
#                     val = st.number_input(key, min_value=72, max_value=400, value=int(default),
#                                           key='%s_%s' % (p_name, key))
#                 else:
#                     val = st.text_input(key, value=default, key='%s_%s' % (p_name, key))
#                     if not val or val == 'None':
#                         val = None
#                 kwargs[key] = val
#                 kwargs['doc_path'] = filename
#
#             parsers[p_name] = parser(**kwargs)
#             if p_name == MuPDF.get_name():
#                 parsers[p_name + '-s']: MuPDF = parser(parse_streams=True, **kwargs)
#                 tmp = parsers[p_name + '-s'].cleaned
#             if p_name in TRACERS:
#                 tmp = parsers[p_name].cleaned
#             if p_name in RENDERERS:
#                 tmp = parsers[p_name].get_renders()
#             if p_name in TEXTERS:
#                 tmp = parsers[p_name].get_tokens()
#             del tmp
#     return parsers


@st.cache
def parse_document(selected_parser_kwargs):
    p = dict()

    for name, kwa in selected_parser_kwargs.items():
        if name == MuPDF.get_name()+'-s':
            p[name] = MuPDF(**kwa)
        else:
            p[name] = PARSERS[name](**kwa)
        if p[name].get_name() in TRACERS:
            tmp = p[name].cleaned
        if p[name].get_name() in RENDERERS:
            tmp = p[name].get_renders()
        if p[name].get_name() in TEXTERS:
            tmp = p[name].get_tokens()
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
                'recurse': recurse,
                'base_path': base_dir_input if base_dir else None
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
            kwargs['doc_path'] = filepath
        print(p_name, kwargs)
        parser_kwargs[p_name] = kwargs
        if p_name == MuPDF.get_name():
            kwargs['parse_streams'] = True
            parser_kwargs[p_name + '-s'] = kwargs
    st.sidebar.markdown('___')

if not is_pdf(filepath):
    st.write("Please select a PDF")
else:
    parsers = parse_document(parser_kwargs)
    page.app(parsers)
    # if isinstance(page, str):
    #     st.subheader("Select Parsers")
    #     parsers = parser_select(filepath)
    # else:
    #     if parsers is None:
    #         st.write("Please select parsers")
    #     else:
    #         page.app(parsers)
