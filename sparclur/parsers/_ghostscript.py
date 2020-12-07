import locale
import os
import re
import sys
import tempfile
import time
import warnings
from typing import Dict

import ghostscript as external_gs
from PIL import Image
from PIL.PngImagePlugin import PngImageFile

from sparclur._renderer import Renderer
from sparclur._renderer import _SUCCESSFUL_RENDER_MESSAGE as SUCCESS


class Ghostscript(Renderer):
    """SPARCLUR renderer wrapper for Ghostscript"""
    def __init__(self, doc_path, temp_folders_dir=None, dpi=200, size=None, cache_renders=False, verbose=False):
        """
        Parameters
        ----------
        doc_path : str
            Full path to the document to be traced.
        temp_folders_dir : str
            Path to create the temporary directories used for temporary files.
        dpi : int
            Dots per inch used in rendering the document
        size : int or tuple or Dict[int, int] or Dict[int, tuple]
            fix size for the document or for individual pages
        cache_renders : bool
            Specify whether or not renders should be retained in the object
        verbose : bool
            Specify whether additional logging should be saved, such as successful renders and timing
        """
        super().__init__()
        self._doc_path = doc_path
        self._temp_folders_dir = temp_folders_dir
        self._dpi = dpi
        self._size = size
        self._caching = cache_renders
        self._verbose = verbose
        self._logging = dict()
        self._ghostscript_present = 'ghostscript' in sys.modules.keys()
        assert self._ghostscript_present, "Ghostscript not found"

    @staticmethod
    def get_name():
        return 'Ghostscript'

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

    def get_verbose(self):
        return self._verbose

    def set_verbose(self, v: bool):
        self._verbose = v

    def get_logs(self):
        return self._logging

    def set_dpi(self, new_dpi: int):
        self._dpi = new_dpi

    def get_dpi(self):
        return self._dpi

    def get_size(self):
        return self._size

    def set_size(self, s):
        self._size = s

    def _render_page(self, page):
        if self._verbose:
            start_time = time.perf_counter()
        try:
            with tempfile.TemporaryDirectory(dir=self._temp_folders_dir) as tmpdir:
                args = ["-dSAFER",
                        "-dBATCH",
                        "-dUseCropBox",
                        "-dNOPAUSE",
                        "-sDEVICE=png16m",
                        "-dTextAlphaBits=4",
                        "-dFirstPage="+str(page + 1),
                        "-dLastPage="+str(page + 1),
                        "-r"+str(self._dpi)
                        ]

                if isinstance(self._size, dict):
                    size = self._size.get(page, None)
                else:
                    size = self._size
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
                gs = external_gs.Ghostscript(*args)

                pil = Image.open(os.path.join(tmpdir, "out.png"))
                gs.exit()
                external_gs.cleanup()
                if self._caching:
                    self._renders[page] = pil
                if self._verbose:
                    timing = time.perf_counter() - start_time
                    self._logging[page] = {'result': SUCCESS, 'timing': timing}
        except Exception as e:
            print(e)
            pil: PngImageFile = None
            if self._verbose:
                timing = time.perf_counter() - start_time
                self._logging[page] = {'result': str(e), 'timing': timing}
        return pil

    def _render_doc(self):
        if self._verbose:
            start_time = time.perf_counter()
        try:
            with tempfile.TemporaryDirectory(dir=self._temp_folders_dir) as tmpdir:
                args = ["-dSAFER",
                        "-dBATCH",
                        "-dUseCropBox",
                        "-dNOPAUSE",
                        "-sDEVICE=png16m",
                        "-dTextAlphaBits=4",
                        "-r"+str(self._dpi)
                        ]

                if isinstance(self._size, dict):
                    warnings.warn("""Ghostscript does not support page specific sizing when rendering the entire 
                        document. If you want to size each page individually render each page individually. The 
                        first size will be selected from the dictionary for this rendering attempt.""")
                    sizes = [self._size.values()]
                    size = sizes[0] if len(sizes) > 0 else None
                else:
                    size = self._size
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
                gs = external_gs.Ghostscript(*args)

                pils: Dict[int, PngImageFile] = dict()
                for png in [file for file in os.listdir(tmpdir) if file.endswith('.png')]:
                    try:
                        i = int(re.sub('.png', '', re.sub('page-', '', png))) - 1
                        pil = Image.open(os.path.join(tmpdir, png))
                        pils[i] = pil
                    except:
                       pass
                gs.exit()
                external_gs.cleanup()
                if self._caching:
                    self._full_doc_rendered = True
                    self._renders = pils
                if self._verbose:
                    timing = time.perf_counter() - start_time
                    num_pages = len(pils)
                    for page in pils.keys():
                        self._logging[page] = {'result': SUCCESS, 'timing': timing / num_pages}
        except Exception as e:
            print(e)
            pils: Dict[int, PngImageFile] = dict()
            if self._verbose:
                timing = time.perf_counter() - start_time
                self._logging[0] = {'result': str(e), 'timing': timing}
        return pils
