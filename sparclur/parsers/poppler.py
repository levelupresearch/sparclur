from sparclur.parsers._renderer import Renderer

import tempfile
import subprocess
import re
import os

from PIL import Image


def _parse_poppler_size(size):
    if not (isinstance(size, tuple) or isinstance(size, int) or isinstance(size, float)) or size is None:
        size_cmd = None
    else:
        if isinstance(size, int) or isinstance(size, float):
            size = tuple([size])
        if len(size) == 2:
            x_scale = -1 if size[0] is None else str(int(size[0]))
            y_scale = -1 if size[1] is None else str(int(size[1]))
            size_cmd = ['-scale-to-x', x_scale, '-scale-to-y', y_scale]
        elif len(size) == 1:
            scale = -1 if size[0] is None else str(int(size[0]))
            size_cmd = ['scale-to', scale]
    return size_cmd


def _poppler_render(path, dpi=200, size=None, page=None, temp_folders_dir=None):
    return_single_page = False
    cmd = ['pdftoppm', '-png', '-r', str(dpi)]
    size = _parse_poppler_size(size)
    if size is not None:
        cmd.extend(size)
    if page is not None:
        page = str(int(page) + 1)
        return_single_page = True
        cmd.extend(['-f', page, '-l', page])
    with tempfile.TemporaryDirectory(dir=temp_folders_dir) as temp_path:
        cmd.extend([path, os.path.join(temp_path, 'out')])
        cmd = ' '.join([entry for entry in cmd])
        sp = subprocess.Popen(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, shell=True)
        (stdout, err) = sp.communicate()
        rendered_pages = [int(re.sub('out-', '', re.sub('.png', '', file))) for file in os.listdir(temp_path)]
        highest_rendered_page = max(rendered_pages)
        result = [None for i in range(highest_rendered_page)]
        for render in os.listdir(temp_path):
            page_index = int(re.sub('out-', '', re.sub('.png', '', render))) - 1
            result[page_index] = Image.open(os.path.join(temp_path, render))
    if return_single_page:
        result = [render for render in result if render is not None][0]
    return result


class Poppler(Renderer):

    def __init__(self):
        self.name = 'Poppler'

    def get_name(self):
        return self.name

    def render_page(self, path, page, dpi=200, size=None, temp_folders_dir=None):
        return _poppler_render(path, page, dpi=dpi, size=size, temp_folders_dir=temp_folders_dir)

    def render_doc(self, path, dpi=200, size=None, temp_folders_dir=None):
        return _poppler_render(path, dpi=dpi, size=size, page=None, temp_folders_dir=temp_folders_dir)
