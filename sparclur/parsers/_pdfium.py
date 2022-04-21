from typing import Union, List, Tuple, Any
import time
import os
import sys

import yaml
import pypdfium2 as pdfium
from func_timeout import func_timeout, FunctionTimedOut
from PIL.PngImagePlugin import PngImageFile

from sparclur._parser import VALID, VALID_WARNINGS, REJECTED, RENDER, TIMED_OUT
from sparclur._renderer import Renderer
from sparclur._renderer import _SUCCESSFUL_RENDER_MESSAGE as SUCCESS
from sparclur._renderer import _SUCCESS_WITH_WARNINGS as SUCCESS_WITH_WARNINGS
from sparclur.utils._config import _get_config_param, _load_config


class PDFium(Renderer):
    "PDFium renderer"
    def __init__(self, doc: Union[str, bytes],
                 skip_check: Union[bool, None] = None,
                 hash_exclude: Union[str, List[str], None] = None,
                 page_hashes: Union[int, Tuple[Any], None] = None,
                 validate_hash: bool = False,
                 temp_folders_dir: Union[str, None] = None,
                 dpi: Union[int, None] = None,
                 cache_renders: Union[bool, None] = None,
                 timeout: Union[int, None] = None):

        config = _load_config()
        skip_check = _get_config_param(PDFium, config, 'skip_check', skip_check, False)
        hash_exclude = _get_config_param(PDFium, config, 'hash_exclude', hash_exclude, None)
        temp_folders_dir = _get_config_param(PDFium, config, 'temp_folders_dir', temp_folders_dir, None)
        dpi = _get_config_param(PDFium, config, 'dpi', dpi, 200)
        cache_renders = _get_config_param(PDFium, config, 'cache_renders', cache_renders, False)
        timeout = _get_config_param(PDFium, config, 'timeout', timeout, None)

        super().__init__(doc=doc,
                         temp_folders_dir=temp_folders_dir,
                         skip_check=skip_check,
                         hash_exclude=hash_exclude,
                         page_hashes=page_hashes,
                         validate_hash=validate_hash,
                         dpi=dpi,
                         cache_renders=cache_renders,
                         timeout=timeout)

    @staticmethod
    def get_name():
        return 'PDFium'

    def _check_for_renderer(self) -> bool:
        if self._can_render is None:
            self._can_render = 'pypdfium2' in sys.modules.keys()
        return self._can_render

    @property
    def validate_renderer(self):
        if RENDER in self._validity:
            return self._validity[RENDER]
        else:
            validity_results = dict()
            if len(self._logs) == 0:
                if self._validate_hash:
                    _ = self.get_renders(self._parse_page_hashes)
                else:
                    _ = self.get_renders()
            results = [(page, value['result']) for (page, value) in self._logs.items()]
            not_successful = [result for (_, result) in results if result != SUCCESS]
            if self._file_timed_out[RENDER]:
                validity_results['valid'] = False
                validity_results['status'] = TIMED_OUT
                validity_results['info'] = 'Timed Out: %i' % self._timeout
            if len(results) == 0:
                validity_results['valid'] = False
                validity_results['status'] = REJECTED
                validity_results['info'] = 'No info returned'
            elif len(not_successful) == 0:
                validity_results['valid'] = True
                validity_results['status'] = VALID
            elif len([result for result in not_successful if result != SUCCESS_WITH_WARNINGS]) == 0:
                validity_results['valid'] = True
                validity_results['status'] = VALID_WARNINGS
            else:
                validity_results['valid'] = False
                validity_results['status'] = REJECTED
                validity_results['info'] = ';'.join(
                    ['%i: %s' % (page, result) for (page, result) in results if
                     result != SUCCESS and result != SUCCESS_WITH_WARNINGS])
            self._validity[RENDER] = validity_results
            return validity_results

    def _get_num_pages(self):
        try:
            doc = pdfium.FPDF_LoadDocument(self._doc, None)
            self._num_pages = pdfium.FPDF_GetPageCount(doc)
        except Exception as e:
            self._num_pages = 0
        finally:
            try:
                pdfium.FPDF_CloseDocument(doc)
            except:
                pass

    def _render_page(self, page):
        start_time = time.perf_counter()
        try:
            with pdfium.PdfContext(self._doc) as pdf:
                kwargs = {
                    'pdf': pdf,
                    'page_index': page,
                    'scale': self._dpi / 72
                }
                if self._timeout is None:
                    pil_image: PngImageFile = pdfium.render_page(**kwargs)
                else:
                    pil_image: PngImageFile = func_timeout(
                        self._timeout,
                        pdfium.render_page,
                        kwargs=kwargs
                    )
                if self._caching:
                    self._renders[page] = pil_image
                timing = time.perf_counter() - start_time
                result = SUCCESS
                self._logs[page] = {'result': result, 'timing': timing}
                self._file_timed_out = False
        except FunctionTimedOut:
            pil_image: PngImageFile = None
            self._logs[page] = {'result': 'Timed out', 'timing': self._timeout}
            self._file_timed_out = True
        except Exception as e:
            pil_image: PngImageFile = None
            timing = time.perf_counter() - start_time
            self._logs[page] = {'result': str(e), 'timing': timing}
            self._file_timed_out = False
        return pil_image

    def _pdfium_render_pdf(self, page_indices):
        result = dict()
        for image, suffix in pdfium.render_pdf(self._doc, page_indices=page_indices, scale=self._dpi/72):
            result[int(suffix) - 1] = image
        return result

    def _render_pages(self, pages: Union[List[int], None]):
        num_pages = self.num_pages
        start_time = time.perf_counter()
        try:
            if num_pages != 0 or pages is None:
                if pages is not None:
                    page_range = [page for page in pages if -1 < page < num_pages]
                else:
                    page_range = None
                result = dict()
                if page_range is not None and len(page_range) == 0:
                    print('Pages out of index')
                    return result
                else:
                    if self._timeout is None:
                        result = self._pdfium_render_pdf(page_range)
                    else:
                        result = func_timeout(
                            self._timeout,
                            self._pdfium_render_pdf,
                            kwargs={
                                'page_indices': page_range
                            }
                        )
                    timing = time.perf_counter() - start_time
                    if page_range is not None:
                        for page in page_range:
                            self._logs[page] = {'result': SUCCESS, 'timing': timing/len(page_range)}
                    else:
                        for page in range(len(result)):
                            self._logs[page] = {'result': SUCCESS, 'timing': timing / len(result)}
            else:
                result = dict()
                for page in pages:
                    pil = self._render_page(page)
                    if pil is not None:
                        result[page] = pil
            self._file_timed_out[RENDER] = False
        except FunctionTimedOut:
            result = dict()
            self._logs[0] = {'result': 'Timed out', 'timing': self._timeout}
            self._file_timed_out[RENDER] = True
        except Exception as e:
            result = dict()
            timing = time.perf_counter() - start_time
            self._logs[0] = {'result': str(e), 'timing': timing}
            self._file_timed_out[RENDER] = False
        if self._caching:
            if pages is None:
                self._full_doc_rendered = True
            self._renders.update(result)
        return result

    def _render_doc(self):
        renders = self._render_pages(pages=None)
        return renders
