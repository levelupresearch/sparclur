import locale
import time
import warnings

from func_timeout import func_timeout, FunctionTimedOut

from sparclur._parser import VALID, VALID_WARNINGS, REJECTED, REJECTED_AMBIG, RENDER, TRACER, TEXT
from sparclur._hybrid import Hybrid
from sparclur._tracer import Tracer
from sparclur._renderer import Renderer
from sparclur.parsers._poppler_helpers import _parse_poppler_size, _pdftocairo_clean_message, _pdftoppm_clean_message
from sparclur.utils._tools import fix_splits

from typing import List, Dict, Any
import tempfile
import subprocess
from subprocess import DEVNULL
import re
import os
from typing import Tuple

from PIL import Image
from PIL.PngImagePlugin import PngImageFile
from sparclur._renderer import _SUCCESSFUL_RENDER_MESSAGE as SUCCESS, _ocr_text


class XPDF(Tracer, Hybrid):
    """XPDF wrapper for pdftoppm, and pdftotext"""
    def __init__(self, doc_path:str,
                 skip_check: bool = False,
                 binary_path: str = None,
                 temp_folders_dir: str = None,
                 page_delimiter: str ='\x0c',
                 maintain_layout: bool = False,
                 dpi: int = 200,
                 size: Tuple[int] or int = None,
                 cache_renders: bool = False,
                 timeout: int = None,
                 ocr: bool = False
                 ):
        """
        Parameters
        ----------
        doc_path : str
            Full path to the document to be traced.
        skip_check: bool
            Flag for skipping the parser check.
        binary_path : str
            If the Poppler binaries are not in the system PATH, add the path to the binaries here. Can also be used to
            use and compare specific versions of the binary.
        temp_folders_dir : str
            Path to create the temporary directories used for temporary files.
        page_delimiter: str
            Marks the end str that separates pages in pdftotext
        maintain_layout: bool
            Tries to maintain the original physical layout of the text. Otherwise uses read order.
        dpi : int
            Dots per inch used in rendering the document
        cache_renders : bool
            Specify whether or not renders should be retained in the object
        timeout : int
            Specify a timeout for rendering
        ocr: bool
            Specify whether or not to OCR for text extraction
        """
        super().__init__(doc_path=doc_path,
                         skip_check=skip_check,
                         dpi=dpi,
                         cache_renders=cache_renders,
                         timeout=timeout,
                         ocr=ocr)
        self._temp_folders_dir = temp_folders_dir
        self._page_delimiter = page_delimiter
        self._maintain_layout = maintain_layout
        self._size = size
        self._decoder = locale.getpreferredencoding()
        self._pdftoppm_path = 'pdftoppm' if binary_path is None else os.path.join(binary_path, 'pdftoppm')
        self._pdftotext_path = 'pdftotext' if binary_path is None else os.path.join(binary_path, 'pdftotext')
        self._trace_exit_code = None
        self._render_exit_code = None
        self._text_exit_code = None
        self._text_messages = None

    @property
    def page_delimiter(self):
        return self._page_delimiter

    @property
    def maintain_layout(self):
        return self._maintain_layout

    @maintain_layout.setter
    def maintain_layout(self, layout: bool):
        self.clear_cache()
        self._maintain_layout = layout

    def _check_for_renderer(self) -> bool:
        if self._can_render is None:
            sp = subprocess.Popen(self._pdftoppm_path + " -v", stderr=subprocess.PIPE, stdout=DEVNULL, shell=True)
            (_, err) = sp.communicate()
            pdftoppm_present = 'Poppler' not in err.decode(self._decoder)
            self._can_render = pdftoppm_present
            self._can_trace = pdftoppm_present
        return self._can_render

    def _check_for_tracer(self) -> bool:
        if self._can_trace is None:
            sp = subprocess.Popen(self._pdftoppm_path + " -v", stderr=subprocess.PIPE, stdout=DEVNULL, shell=True)
            (_, err) = sp.communicate()
            trace_present = 'Poppler' not in err.decode(self._decoder)
            self._can_trace = trace_present
            self._can_render = trace_present
        return self._can_trace

    def validate_tracer(self) -> Dict[str, Any]:
        if TRACER not in self._validity:
            validity_results = dict()
            if self._messages is None:
                self._parse_document()
            if self._cleaned is None:
                self._scrub_messages()
            observed_messages = list(self._cleaned.keys())
            if self._trace_exit_code > 0:
                validity_results['valid'] = False
                validity_results['status'] = REJECTED
                validity_results['info'] = 'Exit code: %i' % self._trace_exit_code
            elif observed_messages == ['No warnings']:
                validity_results['valid'] = True
                validity_results['status'] = VALID
            elif len([message for message in observed_messages if 'Error' in message]) > 0:
                validity_results['valid'] = False
                validity_results['status'] = REJECTED
                validity_results['info'] = 'Errors returned'
            elif len([message for message in observed_messages if 'Warning' in message]) == len(observed_messages):
                validity_results['valid'] = True
                validity_results['status'] = VALID_WARNINGS
                validity_results['info'] = 'Warnings only'
            else:
                validity_results['valid'] = False
                validity_results['status'] = REJECTED_AMBIG
                validity_results['info'] = 'Unknown message type returned'
            self._validity[TRACER] = validity_results
        return self._validity[TRACER]

    def validate_renderer(self) -> Dict[str, Any]:
        if RENDER not in self._validity:
            if self._trace != 'pdftoppm':
                orig_trace = self._trace
                orig_message = self._messages
                orig_cleaned = self._cleaned
                orig_trace_cmd = self._trace_cmd
                self._trace = 'pdftoppm'
                self._trace_cmd = self._pdftoppm_path
                self._messages = None
                self._cleaned = None
                validity_results = self.validate_tracer()
                self._trace = orig_trace
                self._messages = orig_message
                self._cleaned = orig_cleaned
                self._trace_cmd = orig_trace_cmd
            else:
                validity_results = self.validate_tracer()
            self._validity[RENDER] = validity_results
        return self._validity[RENDER]

    def validate_text(self) -> Dict[str, Any]:
        if TEXT not in self._validity:
            validity_results = dict()
            if len(self._text) == 0:
                if self._ocr:
                    swap = True
                    self._ocr = False
                else:
                    swap = False
            if self._text_exit_code > 0:
                validity_results['valid'] = False
                validity_results['status'] = REJECTED
                validity_results['info'] = 'Exit code: %i' % self._text_exit_code
            elif len(self._text_messages) == 0:
                validity_results['valid'] = True
                validity_results['status'] = VALID
            elif len([message for message in self._text_messages if 'Error' in message]) > 0:
                validity_results['valid'] = False
                validity_results['status'] = REJECTED
                validity_results['info'] = 'Errors returned'
            elif len([message for message in self._text_messages if 'Warning' in message]) == len(self._text_messages):
                validity_results['valid'] = True
                validity_results['status'] = VALID_WARNINGS
                validity_results['info'] = 'Warnings only'
            else:
                validity_results['valid'] = False
                validity_results['status'] = REJECTED_AMBIG
                validity_results['info'] = 'Not enough info in message'
            self._validity[TEXT] = validity_results
            if swap:
                self._ocr = True
        return self._validity[TEXT]


    def _check_for_text_extraction(self) -> bool:
        if self._can_extract is None:
            if self._ocr:
                self._can_extract = super(Renderer)._check_for_text_extraction() and self._check_for_renderer()
            else:
                sp = subprocess.Popen(self._pdftotext_path + " -v", stderr=subprocess.PIPE, stdout=DEVNULL, shell=True)
                (_, err) = sp.communicate()
                self._can_extract = 'Poppler' not in err.decode(self._decoder)
        return self._can_extract

    @staticmethod
    def get_name():
        return "XPDF"

    def _parse_document(self):

        with tempfile.TemporaryDirectory(dir=self._temp_folders_dir) as temp_path:
            sp = subprocess.Popen('%s %s %s' % (self._pdftoppm_path, self._doc_path, os.path.join(temp_path, 'out')),
                                  executable='/bin/bash', stderr=subprocess.PIPE, stdout=DEVNULL, shell=True)
            (_, err) = sp.communicate()
            decoder = locale.getpreferredencoding()
            err = fix_splits(err.decode(decoder))
        error_arr = [message for message in err.split('\n') if len(message) > 0]
        self._trace_exit_code = sp.returncode
        self._messages = ['No warnings'] if len(error_arr) == 0 else error_arr

    def _scrub_messages(self):

        if self._messages is None:
            self._parse_document()
        scrubbed_messages = [self._clean_message(err) for err in self._messages]
        error_dict: Dict[str, int] = dict()
        for (index, error) in enumerate(scrubbed_messages):
            if error.startswith('warning: ... repeated '):
                repeated = re.sub(r'[^\d]', '', error)
                error_dict[self._messages[index - 1]] = error_dict.get(error, 0) + int(repeated)
            else:
                error_dict[error] = error_dict.get(error, 0) + 1
        self._cleaned = error_dict

    def _clean_message(self, err):
        return _pdftoppm_clean_message(err)

    def _render_page(self, page):
        start_time = time.perf_counter()
        try:
            if self._timeout is None:
                render: PngImageFile = self._xpdf_render(page=page)
            else:
                render: PngImageFile = func_timeout(
                    self._timeout,
                    self._xpdf_render,
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
                renders: Dict[int, PngImageFile] = self._xpdf_render(page=None)
            else:
                renders: Dict[int, PngImageFile] = func_timeout(
                    self._timeout,
                    self._xpdf_render,
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

    def _xpdf_render(self, page=None):

        return_single_page = False
        cmd = [self._pdftoppm_path, '-png', '-cropbox', '-r', str(self._dpi)]
        if page is not None:
            page = str(int(page) + 1)
            return_single_page = True
            cmd.extend(['-f', page, '-l', page])
        with tempfile.TemporaryDirectory(dir=self._temp_folders_dir) as temp_path:
            cmd.extend([self._doc_path, os.path.join(temp_path, 'out')])
            cmd = ' '.join([entry for entry in cmd])
            sp = subprocess.Popen(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, shell=True)
            self._render_exit_code = sp.returncode
            (_, err) = sp.communicate()
            if page is None and self._messages is None:
                self._trace_exit_code = sp.returncode
                decoder = locale.getpreferredencoding()
                err = fix_splits(err.decode(decoder))
                error_arr = [message for message in err.split('\n') if len(message) > 0]
                self._messages = ['No warnings'] if len(error_arr) == 0 else error_arr
            result: Dict[int, PngImageFile] = dict()
            for render in [file for file in os.listdir(temp_path) if file.endswith('.png')]:
                page_index = int(re.sub('out-', '', re.sub('.png', '', render))) - 1
                result[page_index] = Image.open(os.path.join(temp_path, render))
        if return_single_page:
            single_page_result = result.get(int(page) - 1)
            if single_page_result is not None:
                if single_page_result.width * single_page_result.height == 1:
                    result = self._render_doc().get(int(page) - 1)
                else:
                    result = single_page_result
            else:
                result = None
            # result: PngImageFile = result.get(int(page) - 1)
        return result

    def _extract_doc(self):
        if self._ocr:
            for (page, pil) in self.get_renders().items():
                self._text[page] = _ocr_text(pil)
        else:
            layout = '' if self._maintain_layout else '-layout '
            command = '%s %s%s -' % (self._pdftotext_path, layout, self._doc_path)
            overall_text = self._pdftotext_subprocess(command)
            for (page, text) in enumerate(overall_text.split(self._page_delimiter)[0:-1]):
                self._text[page] = text
        self._full_text_extracted = True

    def _extract_page(self, page):
        if self._ocr:
            self._text[page] = _ocr_text(self.get_renders(page=page))
        else:
            layout = '' if self._maintain_layout else '-layout '
            command = '%s -f %i -l %i %s%s -' % (self._pdftotext_path, page, page, layout, self._doc_path)
            text = self._pdftotext_subprocess(command)
            self._text[page] = text

    def _pdftotext_subprocess(self, command):
        decoder = locale.getpreferredencoding()
        sp = subprocess.Popen(command, stderr=subprocess.PIPE, stdout=subprocess.PIPE, shell=True)
        (stdout, err) = sp.communicate()
        self._text_exit_code = sp.returncode
        err = fix_splits(err.decode(decoder))
        error_arr = [message for message in err.split('\n') if len(message) > 0]

        self._text_messages = error_arr

        return stdout.decode(decoder)
