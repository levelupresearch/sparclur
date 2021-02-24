import locale
import time
import warnings

from func_timeout import func_timeout, FunctionTimedOut

from sparclur._renderer import Renderer
from sparclur._text_extractor import TextExtractor
from sparclur._tracer import Tracer
from sparclur.parsers._poppler_helpers import _parse_poppler_size
from sparclur.utils._tools import fix_splits

from typing import List, Dict
import tempfile
import subprocess
from subprocess import DEVNULL
import re
import os
from typing import Tuple

from PIL import Image
from PIL.PngImagePlugin import PngImageFile
from sparclur._renderer import _SUCCESSFUL_RENDER_MESSAGE as SUCCESS


class PDFtoPPM(Tracer, Renderer):
    """PDFtoPPM tracer and renderer """
    def __init__(self, doc_path: str,
                 binary_path: str = None,
                 temp_folders_dir: str = None,
                 dpi: int = 200,
                 size: Tuple[int] or int = None,
                 cache_renders: bool = False,
                 verbose: bool = False,
                 timeout: int = None):
        """
        Parameters
        ----------
        doc_path : str
            Full path to the document to be traced.
        binary_path : str
            If the pdftoppm binary is not in the system PATH, add the path to the binary here. Can also be used to trace
            specific versions of the binary.
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
        timeout : int
            Specify a timeout for rendering
        """
        super().__init__(doc_path=doc_path, dpi=dpi, cache_renders=cache_renders, verbose=verbose, timeout=timeout)
        self._temp_folders_dir = temp_folders_dir
        self._size = size
        self._cmd_path = 'pdftoppm' if binary_path is None else binary_path
        # try:
        #     subprocess.check_output(self._cmd_path + " -v", shell=True)
        #     self._poppler_present = True
        # except subprocess.CalledProcessError as e:
        #     print("pdftoppm binary not found: ", str(e))
        #     self._poppler_present = False

    def _check_for_renderer(self) -> bool:
        try:
            subprocess.check_output(self._cmd_path + " -v", shell=True)
            pdftoppm_present = True
        except subprocess.CalledProcessError as e:
            pdftoppm_present = False
        return pdftoppm_present

    def _check_for_tracer(self) -> bool:
        return self._check_for_renderer()

    @staticmethod
    def get_name():
        return "PDFtoPPM"

    def _parse_document(self):

        with tempfile.TemporaryDirectory(dir=self._temp_folders_dir) as temp_path:
            sp = subprocess.Popen('%s %s %s' % (self._cmd_path, self._doc_path, os.path.join(temp_path, 'out')),
                                  executable='/bin/bash', stderr=subprocess.PIPE, stdout=DEVNULL, shell=True)
            (_, err) = sp.communicate()
            decoder = locale.getpreferredencoding()
            err = fix_splits(err.decode(decoder))
        error_arr = [message for message in err.split('\n') if len(message) > 0]
        self._messages = ['No warnings'] if len(error_arr) == 0 else error_arr

    def _clean_message(self, err):

        cleaned = re.sub(r"Couldn't", 'Could not', err)
        cleaned = re.sub(r"wasn't", 'was not', cleaned)
        cleaned = re.sub(r"isn't", 'is not', cleaned)
        cleaned = re.sub(r' \([a-f\d]+\)', '', cleaned)
        cleaned = re.sub(r'\s{0, 1}\<[^>]+\>\s{0, 1}', ' ', cleaned)
        cleaned = re.sub(r"\'[^']+\'", "\'<x>\'", cleaned)
        cleaned = re.sub(r'xref num \d+', 'xref num <x>', cleaned)
        cleaned = re.sub(r'\(page \d+\)', '', cleaned)
        cleaned = re.sub(r'\(bad size: \d+\)', '(bad size)', cleaned)
        cleaned = 'Syntax Error: Unknown operator' if cleaned.startswith('Syntax Error: Unknown operator') else cleaned
        cleaned = 'Syntax Error: Unknown character collection Adobe-Identity' if cleaned.startswith(
            'Syntax Error: Unknown character collection Adobe-Identity') else cleaned
        cleaned = 'Syntax Error: Invalid XRef entry' if cleaned.startswith(
            'Syntax Error: Invalid XRef entry') else cleaned
        cleaned = re.sub(r'Corrupt JPEG data: \d+ extraneous bytes before marker [xa-f\d]{4, 4}',
                         'Corrupt JPEG data: extraneous bytes before marker', cleaned)
        cleaned = re.sub(r'Corrupt JPEG data: found marker [xa-f\d]{4, 4} instead of RST\d+',
                         'Corrupt JPEG data: found marker <x> instead of RSTx', cleaned)
        cleaned = re.sub(r'Syntax Error: \d+ extraneous byte[s]{0, 1} after segment',
                         'Syntax Error: extraneous bytes after segment', cleaned)
        cleaned = re.sub(r'Syntax Error: AnnotWidget::layoutText, cannot convert U\+[A-F\d]+',
                         'Syntax Error: AnnotWidget::layoutText, cannot convert U+xxxx', cleaned)
        cleaned = re.sub(r'Arg #\d+', 'Arg ', cleaned)
        cleaned = re.sub(r'Failed to parse XRef entry \[\d+\].', 'Failed to parse XRef entry.', cleaned)
        cleaned = re.sub(
            r'Syntax Error: Softmask with matte entry \d+ x \d+ must have same geometry as the image \d+ x \d+',
            'Syntax Error: Softmask with matte entry must have same geometry as the image', cleaned)
        cleaned = re.sub(r'Syntax Error: Unknown marker segment \d+ in JPX tile-part stream',
                         'Syntax Error: Unknown marker segment in JPX tile-part stream', cleaned)
        cleaned: str = re.sub(r'Syntax Warning: Could not parse ligature component \"[^"]+\" of \"[^"]+\" in parseCharName',
                         'Syntax Warning: Could not parse ligature component in parseCharName', cleaned)

        return cleaned

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

    @property
    def size(self):
        return self._size

    @size.setter
    def size(self, s):
        self._clear_renders()
        self._size = s

    def _render_page(self, page):
        if self._verbose:
            start_time = time.perf_counter()
        try:
            if self._timeout is None:
                render: PngImageFile = self._poppler_render(page=page)
            else:
                render: PngImageFile = func_timeout(
                    self._timeout,
                    self._poppler_render,
                    kwargs={
                        'page': page
                    }
                )
            if self._caching:
                self._renders[page] = render
            if self._verbose:
                timing = time.perf_counter() - start_time
                self._logs[page] = {'result': SUCCESS, 'timing': timing}
        except FunctionTimedOut:
            render: PngImageFile = None
            if self._verbose:
                self._logs[page] = {'result': 'Timed out', 'timing': self._timeout}
        except Exception as e:
            render: PngImageFile = None
            if self._verbose:
                timing = time.perf_counter() - start_time
                self._logs[page] = {'result': str(e), 'timing': timing}
        return render

    def _render_doc(self):
        if self._verbose:
            start_time = time.perf_counter()
        try:
            if self._timeout is None:
                renders: Dict[int, PngImageFile] = self._poppler_render(page=None)
            else:
                renders: Dict[int, PngImageFile] = func_timeout(
                    self._timeout,
                    self._poppler_render,
                    kwargs={
                        'page': None
                    }
                )
            if self._caching:
                self._full_doc_rendered = True
                self._renders = renders
            if self._verbose:
                timing = time.perf_counter() - start_time
                num_pages = len(renders)
                for page in renders.keys():
                    self._logs[page] = {'result': SUCCESS, 'timing': timing / num_pages}
        except FunctionTimedOut:
            renders: Dict[int, PngImageFile] = dict()
            if self._verbose:
                self._logs[0] = {'result': 'Timed out', 'timing': self._timeout}
        except Exception as e:
            print(e)
            renders: Dict[int, PngImageFile] = dict()
            if self._verbose:
                timing = time.perf_counter() - start_time
                self._logs[0] = {'result': str(e), 'timing': timing}
        return renders

    def _poppler_render(self, page=None):

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

        return_single_page = False
        cmd = [self._cmd_path, '-png', '-cropbox', '-r', str(self._dpi)]
        size = _parse_poppler_size(size)
        if size is not None:
            cmd.extend(size)
        if page is not None:
            page = str(int(page) + 1)
            return_single_page = True
            cmd.extend(['-f', page, '-l', page])
        with tempfile.TemporaryDirectory(dir=self._temp_folders_dir) as temp_path:
            cmd.extend([self._doc_path, os.path.join(temp_path, 'out')])
            cmd = ' '.join([entry for entry in cmd])
            sp = subprocess.Popen(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, shell=True)
            (_, err) = sp.communicate()
            if page is None and not self._messages:
                decoder = locale.getpreferredencoding()
                err = fix_splits(err.decode(decoder))
                error_arr = [message for message in err.split('\n') if len(message) > 0]
                self._messages = ['No warnings'] if len(error_arr) == 0 else error_arr
            result: Dict[int, PngImageFile] = dict()
            for render in [file for file in os.listdir(temp_path) if file.endswith('.png')]:
                page_index = int(re.sub('out-', '', re.sub('.png', '', render))) - 1
                result[page_index] = Image.open(os.path.join(temp_path, render))
        if return_single_page:
            result: PngImageFile = result.get(int(page) - 1)
        return result


class PDFtoCairo(Tracer):
    """SPARCLUR tracer wrapper for pdftocairo"""
    def __init__(self, doc_path: str,
                 binary_path: str = None,
                 temp_folders_dir: str = None):
        """

        Parameters
        ----------
        doc_path : str
            Full path to the document to be traced.
        binary_path : str
            If the pdftocairo binary is not in the system PATH, add the path to the binary here. Can also be used to trace
            specific versions of the binary.
        temp_folders_dir : str
            Path to create the temporary directories used for temporary files.
        """
        super().__init__(doc_path=doc_path)
        self._temp_folders_dir = temp_folders_dir
        self._cmd_path = 'pdftocairo' if binary_path is None else binary_path

    def _check_for_tracer(self) -> bool:
        try:
            subprocess.check_output(self._cmd_path + " -v", shell=True)
            pdftocairo_present = True
        except subprocess.CalledProcessError as e:
            pdftocairo_present = False
        return pdftocairo_present

    def get_doc_path(self):
        return self._doc_path

    @staticmethod
    def get_name():
        return 'PDFtoCairo'

    def _parse_document(self):

        with tempfile.TemporaryDirectory(dir=self._temp_folders_dir) as temp_path:
            out_path = os.path.join(temp_path, 'out.pdf')
            sp = subprocess.Popen('%s -ps %s %s' % (self._cmd_path, self._doc_path, out_path), executable='/bin/bash',
                                  stderr=subprocess.PIPE, stdout=subprocess.PIPE, shell=True)
            (stdout, err) = sp.communicate()
        decoder = locale.getpreferredencoding()
        err = fix_splits(err.decode(decoder))
        error_arr = [message for message in err.split('\n') if len(message) > 0]
        self._messages = ['No warnings'] if len(error_arr) == 0 else error_arr

    def _clean_message(self, err):
        cleaned = re.sub(r'\([\d]+\)', '', err)
        cleaned = re.sub(r'<[\w]{2}>', '', cleaned)
        cleaned = re.sub(r"\'[^']+\'", "\'x\'", cleaned)
        cleaned = re.sub(r'\([^)]+\)', "\'x\'", cleaned)
        cleaned = re.sub(r'xref num [\d]+', "xref num \'x\'", cleaned)
        cleaned:str = 'Syntax Error: Unknown character collection Adobe-Identity' if cleaned.startswith(
            'Syntax Error: Unknown character collection Adobe-Identity') else cleaned
        return cleaned

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


class PDFtoText(TextExtractor):

    def __init__(self, doc_path: str,
                 binary_path: str = None,
                 page_delimiter: str = '\x0c',
                 maintain_layout: bool = False,
                 verbose: bool = False):
        super().__init__(doc_path=doc_path)
        self._page_delimiter = page_delimiter
        self._maintain_layout = maintain_layout
        self._cmd_path = 'pdftotext' if binary_path is None else binary_path
        self._verbose = verbose

    @property
    def verbose(self):
        return self._verbose

    @verbose.setter
    def verbose(self, v: bool):
        self._verbose = v

    def _check_for_text_extraction(self) -> bool:
        try:
            subprocess.check_output(self._cmd_path + " -v", shell=True)
            pdftotext_present = True
        except subprocess.CalledProcessError as e:
            pdftotext_present = False
        return pdftotext_present

    @staticmethod
    def get_name():
        return "PDFtoText"

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

    def _extract_doc(self):
        layout = '' if self._maintain_layout else '-layout '
        command = '%s %s%s -' % (self._cmd_path, layout, self._doc_path)
        overall_text = self._pdftotext_subprocess(command)
        for (page, text) in enumerate(overall_text.split(self._page_delimiter)[0:-1]):
            self._text[page] = text
        self._full_text_extracted = True

    def _extract_page(self, page):
        layout = '' if self._maintain_layout else '-layout '
        command = '%s -f %i -l %i %s%s -' % (self._cmd_path, page, page, layout, self._doc_path)
        text = self._pdftotext_subprocess(command)
        self._text[page] = text

    def _pdftotext_subprocess(self, command):
        decoder = locale.getpreferredencoding()
        sp = subprocess.Popen(command, stderr=subprocess.PIPE, stdout=subprocess.PIPE, shell=True)
        (stdout, err) = sp.communicate()

        err = err.decode(decoder)

        if err and self._verbose:
            warnings.warn("Problem encountered: %s" % err)

        return stdout.decode(decoder)
