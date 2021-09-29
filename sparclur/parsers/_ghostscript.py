import locale
import os
import re
import sys
import tempfile
import time
import warnings
from typing import Dict, Tuple

import ghostscript as external_gs
from PIL import Image
from PIL.PngImagePlugin import PngImageFile
from func_timeout import func_timeout, FunctionTimedOut

from sparclur._renderer import Renderer
from sparclur._renderer import _SUCCESSFUL_RENDER_MESSAGE as SUCCESS
from sparclur._parser import VALID, REJECTED, REJECTED_AMBIG, RENDER


class Ghostscript(Renderer):
    """SPARCLUR renderer wrapper for Ghostscript"""
    def __init__(self, doc_path: str,
                 skip_check: bool = False,
                 temp_folders_dir: str = None,
                 dpi: int = 200,
                 size: Tuple[int] or int = None,
                 cache_renders: bool = False,
                 timeout: int = None):
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
        timeout : int
            Specify a timeout for rendering
        """
        super().__init__(doc_path=doc_path, skip_check=skip_check, dpi=dpi, cache_renders=cache_renders, verbose=True, timeout=timeout)
        # self._ghostscript_present = 'ghostscript' in sys.modules.keys()
        # assert self._ghostscript_present, "Ghostscript not found"
        self._temp_folders_dir = temp_folders_dir
        self._size = size

    def _check_for_renderer(self) -> bool:
        if self._skip_check:
            self._can_render = True
        if self._can_render is None:
            self._can_render = 'ghostscript' in sys.modules.keys()
        return self._can_render

    def validate_renderer(self):
        if RENDER in self._validity:
            return self._validity[RENDER]
        else:
            validity_results = dict()
            if len(self._logs) == 0:
                _ = self.get_renders()
            results = [(page, value['result']) for (page, value) in self._logs.items()]
            if len(results) == 0:
                validity_results['valid'] = False
                validity_results['status'] = REJECTED
                validity_results['info'] = 'No info returned'
            elif len([result for (_, result) in results if result != SUCCESS]) == 0:
                validity_results['valid'] = True
                validity_results['status'] = VALID
            elif 'Fatal' in [result for (_, result) in results] or 'Abnormal termination' in [result for (_, result) in results]:
                validity_results['valid'] = False
                validity_results['status'] = REJECTED
                validity_results['info'] = ';'.join(['%i: %s' % (page, result) for (page, result) in results if result != SUCCESS])
            else:
                validity_results['valid'] = False
                validity_results['status'] = REJECTED_AMBIG
                validity_results['info'] = ';'.join(['%i: %s' % (page, result) for (page, result) in results if result != SUCCESS])
            self._validity[RENDER] = validity_results
            return validity_results

    @staticmethod
    def get_name():
        return 'Ghostscript'

    @property
    def size(self):
        return self._size

    @size.setter
    def size(self, s):
        self.clear_renders()
        self._size = s

    def _timedout_render(self, arg_list):
        gs = external_gs.Ghostscript(*arg_list)
        gs.exit()

    def _render_page(self, page):
        start_time = time.perf_counter()

        with tempfile.TemporaryDirectory(dir=self._temp_folders_dir) as tmpdir:
            try:
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
                if self._timeout is not None:
                    func_timeout(
                        self._timeout,
                        self._timedout_render,
                        kwargs={
                            'arg_list': args
                        }
                    )
                else:
                    gs = external_gs.Ghostscript(*args)
                    gs.exit()

                pil = Image.open(os.path.join(tmpdir, "out.png"))
                if self._caching:
                    self._renders[page] = pil
                timing = time.perf_counter() - start_time
                self._logs[page] = {'result': SUCCESS, 'timing': timing}
            except FunctionTimedOut:
                pil: PngImageFile = None
                self._logs[page] = {'result': 'Timed out', 'timing': self._timeout}
            except Exception as e:
                pil: PngImageFile = None
                timing = time.perf_counter() - start_time
                self._logs[page] = {'result': str(e), 'timing': timing}
            finally:
                external_gs.cleanup()
        return pil

    def _render_doc(self):
        start_time = time.perf_counter()

        with tempfile.TemporaryDirectory(dir=self._temp_folders_dir) as tmpdir:
            try:
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
                if self._timeout is not None:
                    func_timeout(
                        self._timeout,
                        self._timedout_render,
                        kwargs={
                            'arg_list': args
                        }
                    )
                else:
                    gs = external_gs.Ghostscript(*args)
                    gs.exit()

                pils: Dict[int, PngImageFile] = dict()
                for png in [file for file in os.listdir(tmpdir) if file.endswith('.png')]:
                    try:
                        i = int(re.sub('.png', '', re.sub('page-', '', png))) - 1
                        pil = Image.open(os.path.join(tmpdir, png))
                        pils[i] = pil
                    except:
                       pass

                if self._caching:
                    self._full_doc_rendered = True
                    self._renders = pils
                timing = time.perf_counter() - start_time
                num_pages = len(pils)
                for page in pils.keys():
                    self._logs[page] = {'result': SUCCESS, 'timing': timing / num_pages}
            except FunctionTimedOut:
                pils: Dict[int, PngImageFile] = dict()
                self._logs[0] = {'result': 'Timed out', 'timing': self._timeout}
            except Exception as e:
                pils: Dict[int, PngImageFile] = dict()
                timing = time.perf_counter() - start_time
                self._logs[0] = {'result': str(e), 'timing': timing}
            finally:
                external_gs.cleanup()
        return pils
