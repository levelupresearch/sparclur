import os
import re
import time

import jpype
import jpype.imports
import yaml
from PIL import Image
from PIL.PngImagePlugin import PngImageFile
from func_timeout import func_timeout, FunctionTimedOut

from sparclur._parser import VALID, REJECTED, RENDER, TEXT
from sparclur._hybrid import Hybrid
from sparclur._renderer import _SUCCESSFUL_RENDER_MESSAGE as SUCCESS, _ocr_text

from typing import Dict, Any, List
import tempfile

from sparclur.utils import hash_file
from sparclur.utils._tools import _get_config_param


class PDFBox(Hybrid):
    """PDFBox wrapper"""
    def __init__(self, doc: str or bytes,
                 skip_check: bool = None,
                 hash_exclude: str or List[str] = None,
                 jar_path: str = None,
                 temp_folders_dir: str = None,
                 page_delimiter: str = None,
                 dpi: int = None,
                 cache_renders: bool = None,
                 timeout: int = None,
                 ocr: bool = None):

        """
        Parameters
        ----------
        jar_path: str
            Path to the jar for PDFBox
        page_delimiter: str
            Marks the end str that separates pages in pdftotext
        """
        os.chdir(os.path.dirname(os.path.realpath(__file__)))
        with open('../../sparclur.yaml', 'r') as yaml_in:
            config = yaml.full_load(yaml_in)
        skip_check = _get_config_param(PDFBox, config, 'skip_check', skip_check, False)
        hash_exclude = _get_config_param(PDFBox, config, 'hash_exclude', hash_exclude, None)
        jar_path = _get_config_param(PDFBox, config, 'jar_path', jar_path, '.. /../ jars / *')
        temp_folders_dir = _get_config_param(PDFBox, config, 'temp_folders_dir', temp_folders_dir, None)
        page_delimiter = _get_config_param(PDFBox, config, 'page_delimiter', page_delimiter, '\x0c')
        dpi = _get_config_param(PDFBox, config, 'dpi', dpi, 200)
        cache_renders = _get_config_param(PDFBox, config, 'cache_renders', cache_renders, False)
        timeout = _get_config_param(PDFBox, config, 'timeout', timeout, None)
        ocr = _get_config_param(PDFBox, config, 'ocr', ocr, False)

        super().__init__(doc=doc,
                         temp_folders_dir=temp_folders_dir,
                         skip_check=skip_check,
                         hash_exclude=hash_exclude,
                         dpi=dpi,
                         cache_renders=cache_renders,
                         timeout=timeout,
                         ocr=ocr)
        self._page_delimiter = page_delimiter
        self._jar_path = jar_path
        if not jpype.isJVMStarted():
            jpype.addClassPath(self._jar_path)
            try:
                jpype.startJVM(convertStrings=False)
                self._can_render = True
                self._can_extract = True
            except:
                self._can_render = False
                self._can_extract = False
        else:
            self._can_render = True
            self._can_extract = True
        if self._can_render:
            import org.apache.pdfbox.tools as tools
            self._pdfbox_tools = tools
        else:
            self._pdfbox_tools = None
        self._text_message = None

    @staticmethod
    def get_name():
        return "PDFBox"

    @property
    def page_delimiter(self):
        return self._page_delimiter

    @page_delimiter.setter
    def page_delimiter(self, p):
        self._page_delimiter = p

    def _get_num_pages(self):
        try:
            self._num_pages = len(self.get_renders())
        except:
            self._num_pages = 0

    def _check_for_renderer(self) -> bool:
        return self._can_render

    def _check_for_text_extraction(self) -> bool:
        return self._can_extract

    @property
    def validate_renderer(self) -> Dict[str, Any]:
        if RENDER not in self._validity:
            validity_results = dict()
            if len(self._logs) == 0:
                _ = self.get_renders()
            results = [(page, value['result']) for (page, value) in self._logs.items()]
            not_successful = [result for (_, result) in results if result != SUCCESS]
            if len(results) == 0:
                validity_results['valid'] = False
                validity_results['status'] = REJECTED
                validity_results['info'] = 'No info returned'
            elif len(not_successful) == 0:
                validity_results['valid'] = True
                validity_results['status'] = VALID
            else:
                validity_results['valid'] = False
                validity_results['status'] = REJECTED
                validity_results['info'] = self._logs.get(0, dict()).get('result', 'No info returned')
            self._validity[RENDER] = validity_results
        return self._validity[RENDER]

    @property
    def validate_text(self) -> Dict[str, Any]:
        if TEXT not in self._validity:
            validity_results = dict()
            if self._ocr:
                if len(self._text) > 0:
                    old_text = self._text
                    self._text = dict()
                else:
                    old_text = dict()
                swap = True
                self._ocr = False
            else:
                swap = False
                old_text = dict()
            if len(self._text) == 0:
                _ = self.get_text()
            if self._text_message == 'No warnings':
                validity_results['valid'] = True
                validity_results['status'] = VALID
            else:
                validity_results['valid'] = False
                validity_results['status'] = REJECTED
                validity_results['info'] = self._text_message
            self._validity[TEXT] = validity_results
            if swap:
                self._ocr = True
                self._text = old_text
        return self._validity[TEXT]

    def _pdfbox_render(self, page=None):
        return_single_page = False
        options = ['-imageType', 'png', '-dpi', str(self._dpi)]
        if page is not None:
            page = str(int(page) + 1)
            return_single_page = True
            options.extend(['-page', str(page)])
        with tempfile.TemporaryDirectory(dir=self._temp_folders_dir) as temp_path:
            if isinstance(self._doc, bytes):
                file_hash = hash_file(self._doc)
                doc_path = os.path.join(temp_path, file_hash)
                with open(doc_path, 'wb') as doc_out:
                    doc_out.write(self._doc)
            else:
                doc_path = self._doc
            options.extend(['-outputPrefix', temp_path + '/out-'])
            options.append(doc_path)
            self._pdfbox_tools.PDFToImage.main(options)
            result: Dict[int, PngImageFile] = dict()
            for render in [file for file in os.listdir(temp_path) if file.endswith('.png')]:
                page_index = int(re.sub('out-', '', re.sub('.png', '', render))) - 1
                result[page_index] = Image.open(os.path.join(temp_path, render))
        if return_single_page:
            result: PngImageFile = result.get(int(page) - 1)
        return result

    def _render_page(self, page):
        start_time = time.perf_counter()
        try:
            if self._timeout is None:
                render: PngImageFile = self._pdfbox_render(page=page)
            else:
                render: PngImageFile = func_timeout(
                    self._timeout,
                    self._pdfbox_render,
                    kwargs={
                        'page': page
                    }
                )
            if self._caching:
                self._renders[page] = render
            timing = time.perf_counter() - start_time
            self._logs[page] = {'result': SUCCESS, 'timing': timing}
        except FunctionTimedOut:
            render: PngImageFile = None
            self._logs[page] = {'result': 'Timed out', 'timing': self._timeout}
        except Exception as e:
            render: PngImageFile = None
            timing = time.perf_counter() - start_time
            self._logs[page] = {'result': str(e), 'timing': timing}
        return render

    def _render_doc(self):
        start_time = time.perf_counter()
        try:
            if self._timeout is None:
                renders: Dict[int, PngImageFile] = self._pdfbox_render(page=None)
            else:
                renders: Dict[int, PngImageFile] = func_timeout(
                    self._timeout,
                    self._pdfbox_render,
                    kwargs={
                        'page': None
                    }
                )
            if self._caching:
                self._full_doc_rendered = True
                self._renders = renders
            timing = time.perf_counter() - start_time
            num_pages = len(renders)
            for page in renders.keys():
                self._logs[page] = {'result': SUCCESS, 'timing': timing / num_pages}
        except FunctionTimedOut:
            renders: Dict[int, PngImageFile] = dict()
            self._logs[0] = {'result': 'Timed out', 'timing': self._timeout}
        except Exception as e:
            print(e)
            renders: Dict[int, PngImageFile] = dict()
            timing = time.perf_counter() - start_time
            self._logs[0] = {'result': str(e), 'timing': timing}
        return renders

    def _pdfbox_extract(self, page=None):
        options = ['-pageDelimited']
        if page is not None:
            page = str(page + 1)
            options.extend(['-startPage', page, '-endPage', page])
        with tempfile.TemporaryDirectory(dir=self._temp_folders_dir) as temp_path:
            if isinstance(self._doc, bytes):
                file_hash = hash_file(self._doc)
                doc_path = os.path.join(temp_path, file_hash)
                with open(doc_path, 'wb') as doc_out:
                    doc_out.write(self._doc)
            else:
                doc_path = self._doc
            options.append(doc_path)
            output_file = os.path.join(temp_path, 'out.txt')
            options.append(output_file)
            try:
                self._pdfbox_tools.ExtractText.main(options)
                with open(output_file, 'r') as file:
                    text = ''.join(line for line in file)
                self._text_message = 'No warnings'
            except Exception as e:
                self._text_message = str(e)
                text = ''
        return text

    def _extract_doc(self):
        if self._ocr:
            for (page, pil) in self.get_renders().items():
                self._text[page] = _ocr_text(pil)
        else:
            overall_text = self._pdfbox_extract()
            split_text = overall_text.split(self._page_delimiter)
            if split_text[-1] == '':
                split_text = split_text[0:-1]
            for (page, text) in enumerate(split_text):
                self._text[page] = text
            self._full_text_extracted = True

    def _extract_page(self, page):
        if self._ocr:
            self._text[page] = _ocr_text(self.get_renders(page=page))
        else:
            text = self._pdfbox_extract(page=page)
            self._text[page] = text
