from sparclur.parsers._renderer import Renderer
import ghostscript

from typing import Dict

import locale
import tempfile
import os
import sys
import re

from PIL import Image
from PIL.PngImagePlugin import PngImageFile


class Ghostscript(Renderer):

    def __init__(self, doc_path, temp_folders_dir=None, cache_renders=False):
        self._name = 'GhostScript'
        self._doc_path = doc_path
        self._temp_folders_dir = temp_folders_dir
        self._caching = cache_renders
        self._renders: Dict[int, PngImageFile] = dict()
        self._full_doc_rendered = False
        self._ghostscript_present = 'ghostscript' in sys.modules.keys()
        assert self._ghostscript_present, "Ghostscript not found"

    def get_name(self):
        return self._name

    def get_doc_path(self):
        return self._doc_path

    def set_caching(self, caching: bool):
        assert isinstance(caching, bool)
        self._caching = caching

    def get_caching(self):
        return self._caching

    def clear_cache(self):
        self._full_doc_rendered = False
        self._renders: Dict[int, PngImageFile] = dict()

    def get_renders(self, page: int = None, dpi=200, size=None):

        if self._renders:
            if page is not None:
                if page in self._renders:
                    result = self._renders[page]
                else:
                    result = self._render_page(page=page, dpi=dpi, size=size)
            else:
                if self._full_doc_rendered:
                    result = self._renders
                else:
                    result = self._render_doc(dpi=dpi, size=size)
        else:
            if page is not None:
                result = self._render_page(page=page, dpi=dpi, size=size)
            else:
                result = self._render_doc(dpi=dpi, size=size)
        return result

    def _render_page(self, page, dpi=200, size=None):

        with tempfile.TemporaryDirectory(dir=self._temp_folders_dir) as tmpdir:
            args = ["-dSAFER",
                    "-dBATCH",
                    "-dUseCropBox",
                    "-dNOPAUSE",
                    "-sDEVICE=png16m",
                    "-dTextAlphaBits=4",
                    "-dFirstPage="+str(page + 1),
                    "-dLastPage="+str(page + 1),
                    "-r"+str(dpi)
                    ]

            if size is not None:
                if isinstance(size, tuple):
                    size_arg = "-g%sx%s" % (str(size[0]), str(size[1]))
                else:
                    size_arg = "-g%sx%s" % (str(size), str(size))
                args.append(size_arg)

            args.append("-sOutputFile="+os.path.join(tmpdir, "out.png"))
            args.append(self._doc_path)

            encoding = locale.getpreferredencoding()
            args = [arg.encode(encoding) for arg in args]
            gs = ghostscript.Ghostscript(*args)

            pil = Image.open(os.path.join(tmpdir, "out.png"))
            gs.exit()
            ghostscript.cleanup()
            if self._caching:
                self._renders[page] = pil
        return pil

    def _render_doc(self, dpi=200, size=None):

        with tempfile.TemporaryDirectory(dir=self._temp_folders_dir) as tmpdir:
            args = ["-dSAFER",
                    "-dBATCH",
                    "-dUseCropBox",
                    "-dNOPAUSE",
                    "-sDEVICE=png16m",
                    "-dTextAlphaBits=4",
                    "-r"+str(dpi)
                    ]

            if size is not None:
                if isinstance(size, tuple):
                    size_arg = "-g%sx%s" % (str(size[0]), str(size[1]))
                else:
                    size_arg = "-g%sx%s" % (str(size), str(size))
                args.append(size_arg)

            args.append("-sOutputFile="+os.path.join(tmpdir, "page-%04d.png"))
            args.append(self._doc_path)

            encoding = locale.getpreferredencoding()
            args = [arg.encode(encoding) for arg in args]
            gs = ghostscript.Ghostscript(*args)

            pils: Dict[int, PngImageFile] = dict()
            for png in [file for file in os.listdir(tmpdir) if file.endswith('.png')]:
                try:
                    i = int(re.sub('.png', '', re.sub('page-', '', png))) - 1
                    pil = Image.open(os.path.join(tmpdir, png))
                    pils[i] = pil
                except:
                   pass
            gs.exit()
            ghostscript.cleanup()
            if self._caching:
                self._full_doc_rendered = True
                self._renders = pils
            return pils
