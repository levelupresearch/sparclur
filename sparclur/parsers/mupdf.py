from typing import List

from sparclur.parsers._renderer import Renderer
from sparclur.parsers._parser import Parser
from sparclur.utils.tools import fix_splits

import os
import subprocess
import tempfile

import fitz

from PIL import Image, PngImagePlugin


class MuTool(Parser):

    def __init__(self):
        self.name = 'MuTool'

    def get_name(self):
        return self.name

    def get_messages(self, path, parse_streams=True, temp_folders_dir=None):

        stream_flag = ' -s' if parse_streams else ''

        with tempfile.TemporaryDirectory(dir=temp_folders_dir) as temp_path:
            out_path = os.path.join(temp_path, 'out.pdf')
            sp = subprocess.Popen('mutool clean%s %s %s' % (stream_flag, path, out_path), executable='/bin/bash',
                                  stderr=subprocess.PIPE, stdout=subprocess.PIPE, shell=True)
            (stdout, err) = sp.communicate()
        err = fix_splits(err.decode("utf-8"))
        error_arr = [message for message in err.split('\n') if len(message) > 0]
        error_arr: List[str] = ['No warnings'] if len(error_arr) == 0 else error_arr
        return error_arr


class MuDraw(Renderer):

    def __init__(self):
        self.name = 'MuDraw'

    def get_name(self):
        return self.name

    def render_page(self, path, page, dpi=200):

        mat = fitz.Matrix(dpi / 72, dpi / 72)
        doc = fitz.open(path)
        pix = doc[page].getPixmap(matrix=mat)
        width = pix.width
        height = pix.height
        mu_pil: PngImagePlugin.PngImageFile = Image.frombytes("RGB", [width, height], pix.samples)
        doc.close()
        return mu_pil

    def render_doc(self, path, dpi=200):

        mat = fitz.Matrix(dpi / 72, dpi / 72)
        doc = fitz.open(path)
        pils = [None for i in range(len(doc))]
        for page in doc:
            try:
                pix = page.getPixmap(matrix=mat)
                width = pix.width
                height = pix.height
                pils[page.number] = Image.frombytes("RGB", [width, height], pix.samples)
            except:
                pass
        return pils
