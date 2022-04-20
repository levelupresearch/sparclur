from typing import List, Tuple
import pweave

def _import_block(sparclur_path):
    if sparclur_path is None:
        sparclur_path_import = ''
    else:
        sparclur_path_import = """
module_path = os.path.abspath('%s')
if module_path not in sys.path:
    sys.path.append(module_path)
""" % sparclur_path

    imports = """
```python; echo=False, name='Imports'
%%capture
import plotly.graph_objects as go
import plotly
import itertools
import sys
import os
import numpy as np
import tempfile
import fitz
from IPython.display import Image
{sparclur_import}

from sparclur.utils.tools import gen_flatten

from sparclur.parsers.present_parsers import get_sparclur_texters, \
    get_sparclur_renderers, \
    get_sparclur_tracers, \
    get_sparclur_parsers
from sparclur.prc.viz import PRCViz
fitz.TOOLS.mupdf_display_errors(False);
```\n\n
    """.format(sparclur_import=sparclur_path_import)
    return imports


def _ptc_block(file_path, idx, num_files):
    block = """
```python; echo=False, name='PTC %i/%i'
tracers = {parser.get_name(): parser for parser in get_sparclur_tracers()}
col_names = list(tracers.keys())
col_names.sort()
cleaned_messages = []
kwargs ={'doc': '%s'}
for parser_name in col_names:
  if parser_name == 'MuPDF':
    kwargs['parse_streams'] = True
  elif 'parse_streams' in kwargs:
    del kwargs['parse_streams']
  parser = tracers[parser_name](**kwargs)
  cleaned_messages.append(parser.cleaned)

num_lines = min(max([len(messages) for messages in cleaned_messages]), 20)
cell_entries = np.ndarray(shape=(len(col_names), num_lines), dtype=object)
cell_entries.fill('')

for (col, parser_messages) in enumerate(cleaned_messages):
  overflow = len(parser_messages) - 19
  for (row, entry) in enumerate(parser_messages.items()):
    if overflow > 1 and row == 19:
      cell_entries[col, row] = str(overflow) + ' more messages'
    elif row < 20:
      cell_entries[col, row] = str(entry[0])+': '+str(entry[1])

fig = go.Figure(data=[go.Table(
  header=dict(values=col_names, fill_color='lightsteelblue'),
  cells=dict(values=cell_entries, fill_color='lavender'))])
fig.update_layout(height=(num_lines + 2) * 50 + 100, margin=dict(r=5, l=5, t=5, b=5))
im_bytes = fig.to_image(format="png")

display(Image(im_bytes))
```
    """ % (idx, num_files, file_path)

    return block


def _pxc_block(file_path, idx, num_files):
    block = """
```python; echo=False, name='PXC %i/%i'
RENDERERS = [parser.get_name() for parser in get_sparclur_renderers()]
kwargs = {'doc': '%s'}
texters = dict()
for parser in get_sparclur_texters():
    if parser.get_name() in RENDERERS:
        texters[parser.get_name()] = parser(dpi=72, **kwargs)
    else:
        texters[parser.get_name()] = parser(**kwargs)
present_texters = list(texters.keys())
present_texters.sort()
txt_idx = {txtr:idx for (idx,txtr) in enumerate(present_texters)}
metrics = dict()
comparisons = list(itertools.combinations(texters, 2))
for combo in comparisons:
    try:
        metrics[frozenset(combo)] = texters[combo[0]].compare_text(texters[combo[1]]);
    except:
        metrics[frozenset(combo)] = None
data = np.zeros((len(texters)+1, len(texters)), dtype=object)
data.fill('')
for row in texters.keys():
    for col in texters.keys():
        if row == col:
            data[txt_idx[row]+1, txt_idx[col]] = 1.0
        else:
            try:
                data[txt_idx[row]+1, txt_idx[col]] = 1 - metrics[frozenset((row, col))];
                data[txt_idx[col]+1, txt_idx[row]] = 1 - metrics[frozenset((row, col))];
            except:
                data[txt_idx[row]+1, txt_idx[col]] = -1
                data[txt_idx[col]+1, txt_idx[row]] = -1

for name in present_texters:
  data[0, txt_idx[name]] = name
header = present_texters
header.insert(0, '')
format = [[None]]
format = format + [['.3f']] * len(present_texters)
fig = go.Figure(data=[go.Table(
  header=dict(values=header,
              fill_color='lightsteelblue'),
  cells=dict(values=data,
              fill_color=['lightsteelblue'] + ['lavender' for _ in range(5)],
              format=format))])
fig.update_layout(height=150, margin=dict(r=5, l=5, t=5, b=5))
im_bytes = fig.to_image(format="png")

display(Image(im_bytes))
```
    """ % (idx, num_files, file_path)
    return block


def _prc_block(file_path, idx, num_files):
    block = """
```python; echo=False, name='PRC %i/%i'
try:
    viz = PRCViz('%s', dpi = 72)
    ssims = [(page, ssim.ssim) for (_, doc) in viz._ssims.items() for (page, ssim) in doc.items()]
    ssims.sort(key=lambda x: x[1])
    page = ssims[0][0]
    display(viz.plot_ssims())
    display(viz.display(page))
except:
    print('PRC Failed')
```
    """ % (idx, num_files, file_path)
    return block


def _parse_document_input(doc: str or Tuple[str]):
    if isinstance(doc, str) or (isinstance(doc, tuple) and len(doc) < 2):
        parsed_doc = (doc, None)
    else:
        parsed_doc = (doc[0], doc[1])
    return parsed_doc


class SparclurReport:
    """
    Generate a Pweave document of the SPARCLUR results over a collection of documents. Pweave can be used to generate
    a report of the SPARCLUR findings.
    """
    def __init__(self, docs: str or List[str] or Tuple[str] or List[Tuple[str]],
                 save_path: str,
                 kernel: str = "python3",
                 title: str = "SPARCLUR Report",
                 sparclur_path=None
                 ):
        """
        Parameters
        ----------
        docs: str or List[str] or Tuple[str] or List[Tuple[str]]
            Single path or list of paths to PDF's to be analyzed. Optionally can include secondary information
            to be printed in the report as tuple of (path, comment).
        kernel: The IPython kernel to use for Pweave
        save_path: str
            The save path of the report
        title: str
            The title of the report
        """
        if not isinstance(docs, list):
            docs = [docs]
        self._docs = [_parse_document_input(doc) for doc in docs]
        self._kernel = kernel
        self._save_path = save_path
        self._title = title
        self._sparclur_path = sparclur_path

    @property
    def title(self):
        return self._title

    @title.setter
    def title(self, t: str):
        self._title = t

    @property
    def kernel(self):
        return self._kernel

    @kernel.setter
    def kernel(self, k):
        self._kernel = k

    @property
    def save_path(self):
        return self._save_path

    @save_path.setter
    def save_path(self, sp: str):
        self._save_path = sp

    def generate_report(self):
        """
        Runs report generation.
        """
        num_files = len(self._docs)
        pmd = "# %s\n\n" % self._title
        pmd = pmd + _import_block(self._sparclur_path)

        for idx, (file, info) in enumerate(self._docs):
            if info is not None:
                info = info + '\n\n'
            else:
                info = ''

            file_name = file.split('/')[-1]
            pmd = pmd + '___\n\n' + file_name + '\n\n' + info + 'Parser Traces\n\n' + _ptc_block(
                file, idx, num_files) + '\n\nParser Text Comparator\n\n' + _pxc_block(
                file, idx, num_files) + '\n\nPDF Renderer Comparator\n\n' + _prc_block(file, idx, num_files) + '\n\n'
        with open(self._save_path, 'w') as out_file:
            out_file.write(pmd)
        pweave.weave(self._save_path, kernel=self._kernel)
