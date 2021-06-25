import locale
import time
import warnings

# from func_timeout import func_timeout, FunctionTimedOut

from sparclur._parser import VALID, VALID_WARNINGS, REJECTED, REJECTED_AMBIG, RENDER, TRACER, TEXT, FONT, IMAGE
from sparclur._hybrid import Hybrid
from sparclur._tracer import Tracer
from sparclur._renderer import Renderer, _SUCCESSFUL_RENDER_MESSAGE as SUCCESS, _ocr_text
from sparclur._font_extractor import FontExtractor
from sparclur._image_data_extractor import ImageDataExtractor
from sparclur.parsers._poppler_helpers import _parse_poppler_size, _pdftocairo_clean_message, _pdftoppm_clean_message
from sparclur.utils._tools import fix_splits

from typing import List, Dict, Any
import tempfile
import subprocess
from subprocess import DEVNULL, TimeoutExpired
import re
import os
from typing import Tuple

from PIL import Image
from PIL.PngImagePlugin import PngImageFile


class Poppler(Tracer, Hybrid, FontExtractor, ImageDataExtractor):
    """Poppler wrapper for pdftoppm, pdftocairo, and pdftotext"""
    def __init__(self, doc_path:str,
                 skip_check: bool = False,
                 trace: str = 'pdftoppm',
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
        size : int or tuple or Dict[int, int] or Dict[int, tuple]
            fix size for the document or for individual pages
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
        self._trace = trace
        self._page_delimiter = page_delimiter
        self._maintain_layout = maintain_layout
        self._size = size
        self._decoder = locale.getpreferredencoding()
        self._pdftoppm_path = 'pdftoppm' if binary_path is None else os.path.join(binary_path, 'pdftoppm')
        self._pdftocairo_path = 'pdftocairo' if binary_path is None else os.path.join(binary_path, 'pdftocairo')
        self._pdftotext_path = 'pdftotext' if binary_path is None else os.path.join(binary_path, 'pdftotext')
        self._pdffonts_path = 'pdffonts' if binary_path is None else os.path.join(binary_path, 'pdffonts')
        self._pdfimages_path = 'pdfimages' if binary_path is None else os.path.join(binary_path, 'pdfimages')
        self._trace_cmd = self._pdftoppm_path if trace == 'pdftoppm' else self._pdftocairo_path
        self._trace_exit_code = None
        self._render_exit_code = None
        self._text_exit_code = None
        self._fonts_exit_code = None
        self._images_exit_code = None
        self._text_messages = None
        self._font_messages = None
        self._image_messages = None

    @property
    def trace(self):
        return self._trace

    @trace.setter
    def trace(self, t):
        if self._trace != t:
            assert t in ['pdftoppm', 'pdftocairo']
            self._trace_cmd = self._pdftoppm_path if t == 'pdftoppm' else self._pdftocairo_path
            self._trace = t

    @property
    def size(self):
        return self._size

    @size.setter
    def size(self, s):
        self._clear_renders()
        self._size = s

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
            pdftoppm_present = 'Poppler' in err.decode(self._decoder)
            self._can_render = pdftoppm_present
            if self._trace == 'pdftoppm':
                self._can_trace = pdftoppm_present
        return self._can_render

    def _check_for_tracer(self) -> bool:
        if self._can_trace is None:
            sp = subprocess.Popen(self._trace_cmd + " -v", stderr=subprocess.PIPE, stdout=DEVNULL, shell=True)
            (_, err) = sp.communicate()
            trace_present = 'Poppler' in err.decode(self._decoder)
            self._can_trace = trace_present
            if self._trace == 'pdftoppm':
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
            if len(self._text) == 0:
                _ = self.get_text()
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
                self._text = old_text
        return self._validity[TEXT]

    def validate_image_data(self):
        if IMAGE not in self._validity:
            validity_results = dict()
            if self._images is None:
                self._get_image_data()
            if self._images_exit_code > 0:
                validity_results['valid'] = False
                validity_results['status'] = REJECTED
                validity_results['info'] = 'Exit code: %i' % self._images_exit_code
            elif len(self._image_messages) == 0:
                validity_results['valid'] = True
                validity_results['status'] = VALID
            elif len([message for message in self._image_messages if 'Error' in message]) > 0:
                validity_results['valid'] = False
                validity_results['status'] = REJECTED
                validity_results['info'] = 'Errors returned'
            elif len([message for message in self._image_messages if 'Warning' in message]) == len(self._text_messages):
                validity_results['valid'] = True
                validity_results['status'] = VALID_WARNINGS
                validity_results['info'] = 'Warnings only'
            else:
                validity_results['valid'] = False
                validity_results['status'] = REJECTED_AMBIG
                validity_results['info'] = 'Not enough info in message'
            self._validity[IMAGE] = validity_results
        return self._validity[IMAGE]

    def validate_fonts(self):
        if FONT not in self._validity:
            validity_results = dict()
            if self._fonts is None:
                self._get_fonts()
            if self._fonts_exit_code > 0:
                validity_results['valid'] = False
                validity_results['status'] = REJECTED
                validity_results['info'] = 'Exit code: %i' % self._fonts_exit_code
            elif len(self._font_messages) == 0:
                validity_results['valid'] = True
                validity_results['status'] = VALID
            elif len([message for message in self._font_messages if 'Error' in message]) > 0:
                validity_results['valid'] = False
                validity_results['status'] = REJECTED
                validity_results['info'] = 'Errors returned'
            elif len([message for message in self._font_messages if 'Warning' in message]) == len(self._text_messages):
                validity_results['valid'] = True
                validity_results['status'] = VALID_WARNINGS
                validity_results['info'] = 'Warnings only'
            else:
                validity_results['valid'] = False
                validity_results['status'] = REJECTED_AMBIG
                validity_results['info'] = 'Not enough info in message'
            self._validity[FONT] = validity_results
        return self._validity[FONT]

    def _check_for_text_extraction(self) -> bool:
        if self._can_extract is None:
            if self._ocr:
                self._can_extract = super(Renderer)._check_for_text_extraction() and self._check_for_renderer()
            else:
                sp = subprocess.Popen(self._pdftotext_path + " -v", stderr=subprocess.PIPE, stdout=DEVNULL, shell=True)
                (_, err) = sp.communicate()
                self._can_extract = 'Poppler' in err.decode(self._decoder)
        return self._can_extract

    @staticmethod
    def get_name():
        return "Poppler"

    def _parse_document(self):
        with tempfile.TemporaryDirectory(dir=self._temp_folders_dir) as temp_path:
            try:
                sp = subprocess.Popen('%s %s %s' % (self._trace_cmd, self._doc_path, os.path.join(temp_path, 'out')),
                                      executable='/bin/bash', stderr=subprocess.PIPE, stdout=DEVNULL, shell=True)
                (_, err) = sp.communicate(timeout=self._timeout or 600)
                err = fix_splits(err.decode(self._decoder))
                error_arr = [message for message in err.split('\n') if len(message) > 0]
                self._trace_exit_code = sp.returncode
            except TimeoutExpired:
                error_arr = ['Error: Subprocess timed out: %i' % (self._timeout or 600)]
                self._trace_exit_code = 0
            except Exception as e:
                error_arr = str(e).split('\n')
                self._trace_exit_code = 0
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
        if self._trace == 'pdftoppm':
            return _pdftoppm_clean_message(err)
        else:
            return _pdftocairo_clean_message(err)

    # def _render_page(self, page):
    #     start_time = time.perf_counter()
    #     try:
    #         if self._timeout is None:
    #             render: PngImageFile = self._poppler_render(page=page)
    #         else:
    #             render: PngImageFile = func_timeout(
    #                 self._timeout,
    #                 self._poppler_render,
    #                 kwargs={
    #                     'page': page
    #                 }
    #             )
    #         if self._caching:
    #             self._renders[page] = render
    #         timing = time.perf_counter() - start_time
    #         self._logs[page] = {'result': SUCCESS, 'timing': timing}
    #     except FunctionTimedOut:
    #         render: PngImageFile = None
    #         self._logs[page] = {'result': 'Timed out', 'timing': self._timeout}
    #     except Exception as e:
    #         render: PngImageFile = None
    #         timing = time.perf_counter() - start_time
    #         self._logs[page] = {'result': str(e), 'timing': timing}
    #     return render

    def _render_page(self, page):
        render: PngImageFile = self._poppler_render(page=page)
        if self._caching:
            self._renders[page] = render
        return render

    # def _render_doc(self):
    #     start_time = time.perf_counter()
    #     try:
    #         if self._timeout is None:
    #             renders: Dict[int, PngImageFile] = self._poppler_render(page=None)
    #         else:
    #             renders: Dict[int, PngImageFile] = func_timeout(
    #                 self._timeout,
    #                 self._poppler_render,
    #                 kwargs={
    #                     'page': None
    #                 }
    #             )
    #         if self._caching:
    #             self._full_doc_rendered = True
    #             self._renders = renders
    #         timing = time.perf_counter() - start_time
    #         num_pages = len(renders)
    #         for page in renders.keys():
    #             self._logs[page] = {'result': SUCCESS, 'timing': timing / num_pages}
    #     except FunctionTimedOut:
    #         renders: Dict[int, PngImageFile] = dict()
    #         self._logs[0] = {'result': 'Timed out', 'timing': self._timeout}
    #     except Exception as e:
    #         # print(e)
    #         renders: Dict[int, PngImageFile] = dict()
    #         timing = time.perf_counter() - start_time
    #         self._logs[0] = {'result': str(e), 'timing': timing}
    #     return renders

    def _render_doc(self):
        renders: Dict[int, PngImageFile] = self._poppler_render(page=None)
        if self._caching:
            self._full_doc_rendered = True
            self._renders = renders
        return renders

    def _poppler_render(self, page=None):
        start_time = time.perf_counter()
        if isinstance(self._size, dict):
            if page is None:
                warnings.warn("""Poppler does not support page specific sizing when rendering the entire 
                    document. If you want to size each page individually render each page individually. The 
                    first size will be selected from the dictionary for this rendering attempt.""")
                sizes = [self._size.values()]
                size = sizes[0] if len(sizes) > 0 else None
            else:
                size = self._size.get(page)
        else:
            size = self._size

        # return_single_page = False
        cmd = [self._pdftoppm_path, '-png', '-cropbox', '-r', str(self._dpi)]
        size = _parse_poppler_size(size)
        if size is not None:
            cmd.extend(size)
        if page is not None:
            page = str(int(page) + 1)
            # return_single_page = True
            cmd.extend(['-f', page, '-l', page])
        with tempfile.TemporaryDirectory(dir=self._temp_folders_dir) as temp_path:
            try:
                cmd.extend([self._doc_path, os.path.join(temp_path, 'out')])
                cmd = ' '.join([entry for entry in cmd])
                sp = subprocess.Popen(cmd, stderr=subprocess.PIPE, stdout=DEVNULL, shell=True)
                self._render_exit_code = sp.returncode
                (_, err) = sp.communicate(timeout=self._timeout or 600)
                if page is None and self._messages is None and self._trace == 'pdftoppm':
                    err = fix_splits(err.decode(self._decoder))
                    error_arr = [message for message in err.split('\n') if len(message) > 0]
                    self._messages = ['No warnings'] if len(error_arr) == 0 else error_arr
                    self._trace_exit_code = sp.returncode
                result: Dict[int, PngImageFile] = dict()
                for render in [file for file in os.listdir(temp_path) if file.endswith('.png')]:
                    page_index = int(re.sub('out-', '', re.sub('.png', '', render))) - 1
                    result[page_index] = Image.open(os.path.join(temp_path, render))
                num_pages = len(result)
                timing = time.perf_counter() - start_time
                for page in result.keys():
                    self._logs[page] = {'result': SUCCESS, 'timing': timing / num_pages}
            except TimeoutError:
                self._render_exit_code = 0
                if page is None and self._messages is None and self._trace == 'pdftoppm':
                    error_arr = ['Error: Subprocess timed out: %i' % (self._timeout or 600)]
                    self._messages = error_arr
                    self._trace_exit_code = 0
                result: Dict[int, PngImageFile] = dict()
                self._logs[0] = {'result': 'Timed out', 'timing': (self._timeout or 600)}
            except Exception as e:
                if page is None and self._messages is None and self._trace == 'pdftoppm':
                    error_arr = str(e).split('\n')
                    self._messages = error_arr
                    self._trace_exit_code = 0
                result: Dict[int, PngImageFile] = dict()
                timing = time.perf_counter() - start_time
                self._logs[0] = {'result': str(e), 'timing': timing}

        # if return_single_page:
        if page is not None:
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
        try:
            sp = subprocess.Popen(command, stderr=subprocess.PIPE, stdout=subprocess.PIPE, shell=True)
            (stdout, err) = sp.communicate(timeout=self._timeout or 600)
            self._text_exit_code = sp.returncode
            err = fix_splits(err.decode(self._decoder))
            error_arr = [message for message in err.split('\n') if len(message) > 0]

            self._text_messages = error_arr
            result = stdout.decode(self._decoder, errors='ignore')
        except TimeoutExpired:
            self._text_exit_code = 0
            self._text_messages = ['Error: Subprocess timed out: %i' % (self._timeout or 600)]
            result = ''
        except Exception as e:
            self._text_exit_code = 0
            self._text_messages = str(e).split('\n')
            result = ''

        return result

    def _get_fonts(self):
        try:
            sp = subprocess.Popen('%s %s' % (self._pdffonts_path, self._doc_path), stderr=subprocess.PIPE,
                                  stdout=subprocess.PIPE, shell=True)
            (stdout, err) = sp.communicate(timeout=self._timeout or 600)
            stdout = stdout.decode(self._decoder)
            err = err.decode(self._decoder)
            self._font_messages = [message for message in err.split('\n') if len(message) > 0]
            self._fonts_exit_code = sp.returncode
            lines = [line for line in stdout.split('\n') if line != '']
            if len(lines) == 0 or len(lines) == 2:
                self._fonts = []
            else:
                field_lengths = [len(dashes) + 1 for dashes in lines[1].split(' ')]
                header = [lines[0][sum(field_lengths[:i]):sum(field_lengths[:i+1])].strip()
                          for i in range(len(field_lengths))]
                font_results = []
                for line in lines[2:]:
                    d = dict()
                    for (idx, head) in enumerate(header[:-1]):
                        value = line[sum(field_lengths[:idx]):sum(field_lengths[:idx+1])].strip()
                        if value == 'yes':
                            value = True
                        if value == 'no':
                            value = False
                        d[head] = value
                    d[header[-1]] = line[sum(field_lengths[:len(header) - 1]):].strip() + ' R'
                    font_results.append(d)
                self._fonts = font_results
        except TimeoutExpired:
            self._fonts = []
            self._font_messages = ['Error: Subprocess timed out: %i' % (self._timeout or 600)]
            self._fonts_exit_code = 0
        except Exception as e:
            self._fonts = []
            self._fonts_exit_code = 0
            self._font_messages = str(e).split('\n')

    def _get_image_data(self):
        try:
            sp = subprocess.Popen('%s -list %s' % (self._pdfimages_path, self._doc_path), stderr=subprocess.PIPE,
                                  stdout=subprocess.PIPE, shell=True)
            (stdout, err) = sp.communicate(timeout=self._timeout or 600)
            stdout = stdout.decode(self._decoder)
            err = err.decode(self._decoder)
            self._image_messages = [message for message in err.split('\n') if len(message) > 0]
            self._images_exit_code = sp.returncode
            lines = [line for line in stdout.split('\n') if line != '']
            if len(lines) == 0 or len(lines) == 2:
                self._images = []
            else:
                header = re.split('\s+', lines[0])
                self._images = [dict(zip(header, re.split('\s+', line)[1:])) for line in lines[2:]]
        except TimeoutError:
            self._images = []
            self._image_messages = ['Error: Subprocess timed out: %i' % (self._timeout or 600)]
            self._images_exit_code = 0
        except Exception as e:
            self._images = []
            self._images_exit_code = 0
            self._image_messages = str(e).split('\n')

# class PDFtoPPM(Tracer, Renderer):
#     """PDFtoPPM tracer and renderer """
#     def __init__(self, doc_path: str,
#                  binary_path: str = None,
#                  temp_folders_dir: str = None,
#                  dpi: int = 200,
#                  size: Tuple[int] or int = None,
#                  cache_renders: bool = False,
#                  verbose: bool = False,
#                  timeout: int = None):
#         """
#         Parameters
#         ----------
#         doc_path : str
#             Full path to the document to be traced.
#         binary_path : str
#             If the pdftoppm binary is not in the system PATH, add the path to the binary here. Can also be used to trace
#             specific versions of the binary.
#         temp_folders_dir : str
#             Path to create the temporary directories used for temporary files.
#         dpi : int
#             Dots per inch used in rendering the document
#         size : int or tuple or Dict[int, int] or Dict[int, tuple]
#             fix size for the document or for individual pages
#         cache_renders : bool
#             Specify whether or not renders should be retained in the object
#         verbose : bool
#             Specify whether additional logging should be saved, such as successful renders and timing
#         timeout : int
#             Specify a timeout for rendering
#         """
#         super().__init__(doc_path=doc_path, dpi=dpi, cache_renders=cache_renders, verbose=verbose, timeout=timeout)
#         self._temp_folders_dir = temp_folders_dir
#         self._size = size
#         self._cmd_path = 'pdftoppm' if binary_path is None else binary_path
#         # try:
#         #     subprocess.check_output(self._cmd_path + " -v", shell=True)
#         #     self._poppler_present = True
#         # except subprocess.CalledProcessError as e:
#         #     print("pdftoppm binary not found: ", str(e))
#         #     self._poppler_present = False
#
#     def _check_for_renderer(self) -> bool:
#         if self._can_render is None:
#             try:
#                 subprocess.check_output(self._cmd_path + " -v", shell=True)
#                 pdftoppm_present = True
#             except subprocess.CalledProcessError as e:
#                 pdftoppm_present = False
#             self._can_render = pdftoppm_present
#             self._can_trace = pdftoppm_present
#         return self._can_render
#
#     def _check_for_tracer(self) -> bool:
#         if self._can_render is None:
#             try:
#                 subprocess.check_output(self._cmd_path + " -v", shell=True)
#                 pdftoppm_present = True
#             except subprocess.CalledProcessError as e:
#                 pdftoppm_present = False
#             self._can_render = pdftoppm_present
#             self._can_trace = pdftoppm_present
#         return self._can_trace
#
#     @staticmethod
#     def get_name():
#         return "PDFtoPPM"
#
#     def _parse_document(self):
#
#         with tempfile.TemporaryDirectory(dir=self._temp_folders_dir) as temp_path:
#             sp = subprocess.Popen('%s %s %s' % (self._cmd_path, self._doc_path, os.path.join(temp_path, 'out')),
#                                   executable='/bin/bash', stderr=subprocess.PIPE, stdout=DEVNULL, shell=True)
#             (_, err) = sp.communicate()
#             decoder = locale.getpreferredencoding()
#             err = fix_splits(err.decode(decoder))
#         error_arr = [message for message in err.split('\n') if len(message) > 0]
#         self._messages = ['No warnings'] if len(error_arr) == 0 else error_arr
#
#     def _clean_message(self, err):
#
#         cleaned = re.sub(r"Couldn't", 'Could not', err)
#         cleaned = re.sub(r"wasn't", 'was not', cleaned)
#         cleaned = re.sub(r"isn't", 'is not', cleaned)
#         cleaned = re.sub(r' \([a-f\d]+\)', '', cleaned)
#         cleaned = re.sub(r'\s{0, 1}\<[^>]+\>\s{0, 1}', ' ', cleaned)
#         cleaned = re.sub(r"\'[^']+\'", "\'<x>\'", cleaned)
#         cleaned = re.sub(r'xref num \d+', 'xref num <x>', cleaned)
#         cleaned = re.sub(r'\(page \d+\)', '', cleaned)
#         cleaned = re.sub(r'\(bad size: \d+\)', '(bad size)', cleaned)
#         cleaned = 'Syntax Error: Unknown operator' if cleaned.startswith('Syntax Error: Unknown operator') else cleaned
#         cleaned = 'Syntax Error: Unknown character collection Adobe-Identity' if cleaned.startswith(
#             'Syntax Error: Unknown character collection Adobe-Identity') else cleaned
#         cleaned = 'Syntax Error: Invalid XRef entry' if cleaned.startswith(
#             'Syntax Error: Invalid XRef entry') else cleaned
#         cleaned = re.sub(r'Corrupt JPEG data: \d+ extraneous bytes before marker [xa-f\d]{4, 4}',
#                          'Corrupt JPEG data: extraneous bytes before marker', cleaned)
#         cleaned = re.sub(r'Corrupt JPEG data: found marker [xa-f\d]{4, 4} instead of RST\d+',
#                          'Corrupt JPEG data: found marker <x> instead of RSTx', cleaned)
#         cleaned = re.sub(r'Syntax Error: \d+ extraneous byte[s]{0, 1} after segment',
#                          'Syntax Error: extraneous bytes after segment', cleaned)
#         cleaned = re.sub(r'Syntax Error: AnnotWidget::layoutText, cannot convert U\+[A-F\d]+',
#                          'Syntax Error: AnnotWidget::layoutText, cannot convert U+xxxx', cleaned)
#         cleaned = re.sub(r'Arg #\d+', 'Arg ', cleaned)
#         cleaned = re.sub(r'Failed to parse XRef entry \[\d+\].', 'Failed to parse XRef entry.', cleaned)
#         cleaned = re.sub(
#             r'Syntax Error: Softmask with matte entry \d+ x \d+ must have same geometry as the image \d+ x \d+',
#             'Syntax Error: Softmask with matte entry must have same geometry as the image', cleaned)
#         cleaned = re.sub(r'Syntax Error: Unknown marker segment \d+ in JPX tile-part stream',
#                          'Syntax Error: Unknown marker segment in JPX tile-part stream', cleaned)
#         cleaned: str = re.sub(r'Syntax Warning: Could not parse ligature component \"[^"]+\" of \"[^"]+\" in parseCharName',
#                          'Syntax Warning: Could not parse ligature component in parseCharName', cleaned)
#
#         return cleaned
#
#     def _scrub_messages(self):
#
#         if self._messages is None:
#             self._parse_document()
#         scrubbed_messages = [self._clean_message(err) for err in self._messages]
#         error_dict: Dict[str, int] = dict()
#         for (index, error) in enumerate(scrubbed_messages):
#             if error.startswith('warning: ... repeated '):
#                 repeated = re.sub(r'[^\d]', '', error)
#                 error_dict[self._messages[index - 1]] = error_dict.get(error, 0) + int(repeated)
#             else:
#                 error_dict[error] = error_dict.get(error, 0) + 1
#         self._cleaned = error_dict
#
#     @property
#     def size(self):
#         return self._size
#
#     @size.setter
#     def size(self, s):
#         self._clear_renders()
#         self._size = s
#
#     def _render_page(self, page):
#         if self._verbose:
#             start_time = time.perf_counter()
#         try:
#             if self._timeout is None:
#                 render: PngImageFile = self._poppler_render(page=page)
#             else:
#                 render: PngImageFile = func_timeout(
#                     self._timeout,
#                     self._poppler_render,
#                     kwargs={
#                         'page': page
#                     }
#                 )
#             if self._caching:
#                 self._renders[page] = render
#             if self._verbose:
#                 timing = time.perf_counter() - start_time
#                 self._logs[page] = {'result': SUCCESS, 'timing': timing}
#         except FunctionTimedOut:
#             render: PngImageFile = None
#             if self._verbose:
#                 self._logs[page] = {'result': 'Timed out', 'timing': self._timeout}
#         except Exception as e:
#             render: PngImageFile = None
#             if self._verbose:
#                 timing = time.perf_counter() - start_time
#                 self._logs[page] = {'result': str(e), 'timing': timing}
#         return render
#
#     def _render_doc(self):
#         if self._verbose:
#             start_time = time.perf_counter()
#         try:
#             if self._timeout is None:
#                 renders: Dict[int, PngImageFile] = self._poppler_render(page=None)
#             else:
#                 renders: Dict[int, PngImageFile] = func_timeout(
#                     self._timeout,
#                     self._poppler_render,
#                     kwargs={
#                         'page': None
#                     }
#                 )
#             if self._caching:
#                 self._full_doc_rendered = True
#                 self._renders = renders
#             if self._verbose:
#                 timing = time.perf_counter() - start_time
#                 num_pages = len(renders)
#                 for page in renders.keys():
#                     self._logs[page] = {'result': SUCCESS, 'timing': timing / num_pages}
#         except FunctionTimedOut:
#             renders: Dict[int, PngImageFile] = dict()
#             if self._verbose:
#                 self._logs[0] = {'result': 'Timed out', 'timing': self._timeout}
#         except Exception as e:
#             print(e)
#             renders: Dict[int, PngImageFile] = dict()
#             if self._verbose:
#                 timing = time.perf_counter() - start_time
#                 self._logs[0] = {'result': str(e), 'timing': timing}
#         return renders
#
#     def _poppler_render(self, page=None):
#
#         if isinstance(self._size, dict):
#             if page is None:
#                 warnings.warn("""Poppler does not support page specific sizing when rendering the entire
#                     document. If you want to size each page individually render each page individually. The
#                     first size will be selected from the dictionary for this rendering attempt.""")
#                 sizes = [self._size.values()]
#                 size = sizes[0] if len(sizes) > 0 else None
#             else:
#                 size = self._size.get(page)
#         else:
#             size = self._size
#
#         return_single_page = False
#         cmd = [self._cmd_path, '-png', '-cropbox', '-r', str(self._dpi)]
#         size = _parse_poppler_size(size)
#         if size is not None:
#             cmd.extend(size)
#         if page is not None:
#             page = str(int(page) + 1)
#             return_single_page = True
#             cmd.extend(['-f', page, '-l', page])
#         with tempfile.TemporaryDirectory(dir=self._temp_folders_dir) as temp_path:
#             cmd.extend([self._doc_path, os.path.join(temp_path, 'out')])
#             cmd = ' '.join([entry for entry in cmd])
#             sp = subprocess.Popen(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, shell=True)
#             (_, err) = sp.communicate()
#             if page is None and not self._messages:
#                 decoder = locale.getpreferredencoding()
#                 err = fix_splits(err.decode(decoder))
#                 error_arr = [message for message in err.split('\n') if len(message) > 0]
#                 self._messages = ['No warnings'] if len(error_arr) == 0 else error_arr
#             result: Dict[int, PngImageFile] = dict()
#             for render in [file for file in os.listdir(temp_path) if file.endswith('.png')]:
#                 page_index = int(re.sub('out-', '', re.sub('.png', '', render))) - 1
#                 result[page_index] = Image.open(os.path.join(temp_path, render))
#         if return_single_page:
#             single_page_result = result.get(int(page) - 1)
#             if single_page_result is not None:
#                 if single_page_result.width * single_page_result.height == 1:
#                     result = self._render_doc().get(int(page) - 1)
#                 else:
#                     result = single_page_result
#             else:
#                 result = None
#             # result: PngImageFile = result.get(int(page) - 1)
#         return result
#
#
# class PDFtoCairo(Tracer):
#     """SPARCLUR tracer wrapper for pdftocairo"""
#     def __init__(self, doc_path: str,
#                  binary_path: str = None,
#                  temp_folders_dir: str = None):
#         """
#
#         Parameters
#         ----------
#         doc_path : str
#             Full path to the document to be traced.
#         binary_path : str
#             If the pdftocairo binary is not in the system PATH, add the path to the binary here. Can also be used to trace
#             specific versions of the binary.
#         temp_folders_dir : str
#             Path to create the temporary directories used for temporary files.
#         """
#         super().__init__(doc_path=doc_path)
#         self._temp_folders_dir = temp_folders_dir
#         self._cmd_path = 'pdftocairo' if binary_path is None else binary_path
#
#     def _check_for_tracer(self) -> bool:
#         if self._can_trace is None:
#             try:
#                 subprocess.check_output(self._cmd_path + " -v", shell=True)
#                 pdftocairo_present = True
#             except subprocess.CalledProcessError as e:
#                 pdftocairo_present = False
#             self._can_trace = pdftocairo_present
#         return self._can_trace
#
#     def get_doc_path(self):
#         return self._doc_path
#
#     @staticmethod
#     def get_name():
#         return 'PDFtoCairo'
#
#     def _parse_document(self):
#
#         with tempfile.TemporaryDirectory(dir=self._temp_folders_dir) as temp_path:
#             out_path = os.path.join(temp_path, 'out.pdf')
#             sp = subprocess.Popen('%s -ps %s %s' % (self._cmd_path, self._doc_path, out_path), executable='/bin/bash',
#                                   stderr=subprocess.PIPE, stdout=subprocess.PIPE, shell=True)
#             (stdout, err) = sp.communicate()
#         decoder = locale.getpreferredencoding()
#         err = fix_splits(err.decode(decoder))
#         error_arr = [message for message in err.split('\n') if len(message) > 0]
#         self._messages = ['No warnings'] if len(error_arr) == 0 else error_arr
#
#     def _clean_message(self, err):
#         cleaned = re.sub(r'\([\d]+\)', '', err)
#         cleaned = re.sub(r'<[\w]{2}>', '', cleaned)
#         cleaned = re.sub(r"\'[^']+\'", "\'x\'", cleaned)
#         cleaned = re.sub(r'\([^)]+\)', "\'x\'", cleaned)
#         cleaned = re.sub(r'xref num [\d]+', "xref num \'x\'", cleaned)
#         cleaned:str = 'Syntax Error: Unknown character collection Adobe-Identity' if cleaned.startswith(
#             'Syntax Error: Unknown character collection Adobe-Identity') else cleaned
#         return cleaned
#
#     def _scrub_messages(self):
#
#         if self._messages is None:
#             self._parse_document()
#         scrubbed_messages = [self._clean_message(err) for err in self._messages]
#         error_dict: Dict[str, int] = dict()
#         for (index, error) in enumerate(scrubbed_messages):
#             if error.startswith('warning: ... repeated '):
#                 repeated = re.sub(r'[^\d]', '', error)
#                 error_dict[self._messages[index - 1]] = error_dict.get(error, 0) + int(repeated)
#             else:
#                 error_dict[error] = error_dict.get(error, 0) + 1
#         self._cleaned = error_dict
#
#
# class PDFtoText(TextCompare):
#
#     def __init__(self, doc_path: str,
#                  binary_path: str = None,
#                  page_delimiter: str = '\x0c',
#                  maintain_layout: bool = False,
#                  verbose: bool = False):
#         super().__init__(doc_path=doc_path)
#         self._page_delimiter = page_delimiter
#         self._maintain_layout = maintain_layout
#         self._cmd_path = 'pdftotext' if binary_path is None else binary_path
#         self._verbose = verbose
#
#     @property
#     def verbose(self):
#         return self._verbose
#
#     @verbose.setter
#     def verbose(self, v: bool):
#         self._verbose = v
#
#     def _check_for_text_extraction(self) -> bool:
#         if self._can_extract is None:
#             try:
#                 subprocess.check_output(self._cmd_path + " -v", shell=True)
#                 pdftotext_present = True
#             except subprocess.CalledProcessError as e:
#                 pdftotext_present = False
#             self._can_extract = pdftotext_present
#         return self._can_extract
#
#     @staticmethod
#     def get_name():
#         return "PDFtoText"
#
#     @property
#     def page_delimiter(self):
#         return self._page_delimiter
#
#     @property
#     def maintain_layout(self):
#         return self._maintain_layout
#
#     @maintain_layout.setter
#     def maintain_layout(self, layout: bool):
#         self.clear_cache()
#         self._maintain_layout = layout
#
#     def _extract_doc(self):
#         layout = '' if self._maintain_layout else '-layout '
#         command = '%s %s%s -' % (self._cmd_path, layout, self._doc_path)
#         overall_text = self._pdftotext_subprocess(command)
#         for (page, text) in enumdef _extract_doc(self):
# #         layout = '' if self._maintain_layout else '-layout '
# #         command = '%s %s%s -' % (self._cmd_path, layout, self._doc_path)
# #         overall_text = self._pdftotext_subprocess(command)
# #         for (page, text) in enumerate(overall_text.split(self._page_delimiter)[0:-1]):
# #             self._text[page] = text
# #         self._full_text_extracted = True
# #
# #     def _extract_page(self, page):
# #         layout = '' if self._maintain_layout else '-layout '
# #         command = '%s -f %i -l %i %s%s -' % (self._cmd_path, page, page, layout, self._doc_path)
# #         text = self._pdftotext_subprocess(command)
# #         self._text[page] = text
# #
# #     def _pdftotext_subprocess(self, command):
# #         decoder = locale.getpreferredencoding()
# #         sp = subprocess.Popen(command, stderr=subprocess.PIPE, stdout=subprocess.PIPE, shell=True)
# #         (stdout, err) = sp.communicate()
# #
# #         err = err.decode(decoder)
# #
# #         if err and self._verbose:
# #             warnings.warn("Problem encountered: %s" % err)
# #
# #         return stdout.decode(decoder)erate(overall_text.split(self._page_delimiter)[0:-1]):
#             self._text[page] = text
#         self._full_text_extracted = True
#
#     def _extract_page(self, page):
#         layout = '' if self._maintain_layout else '-layout '
#         command = '%s -f %i -l %i %s%s -' % (self._cmd_path, page, page, layout, self._doc_path)
#         text = self._pdftotext_subprocess(command)
#         self._text[page] = text
#
#     def _pdftotext_subprocess(self, command):
#         decoder = locale.getpreferredencoding()
#         sp = subprocess.Popen(command, stderr=subprocess.PIPE, stdout=subprocess.PIPE, shell=True)
#         (stdout, err) = sp.communicate()
#
#         err = err.decode(decoder)
#
#         if err and self._verbose:
#             warnings.warn("Problem encountered: %s" % err)
#
#         return stdout.decode(decoder)
