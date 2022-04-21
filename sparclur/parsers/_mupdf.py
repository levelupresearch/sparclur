import locale
import shlex
from typing import List, Dict, Any, Union, Tuple

import yaml
from func_timeout import func_timeout, FunctionTimedOut

from sparclur._parser import VALID, VALID_WARNINGS, REJECTED, REJECTED_AMBIG, RENDER, TRACER, TEXT, TIMED_OUT
from sparclur._hybrid import Hybrid
from sparclur._reforge import Reforger
from sparclur._renderer import _SUCCESSFUL_RENDER_MESSAGE as SUCCESS
from sparclur._renderer import _SUCCESS_WITH_WARNINGS as SUCCESS_WITH_WARNINGS
from sparclur._renderer import _ocr_text
from sparclur._tracer import Tracer
from sparclur.utils import fix_splits, hash_file

import os
import sys
import re
import subprocess
from subprocess import TimeoutExpired, DEVNULL
import tempfile
import time

import fitz

from PIL import Image
from PIL.PngImagePlugin import PngImageFile

from sparclur.utils._config import _get_config_param, _load_config


class MuPDF(Tracer, Hybrid, Reforger):
    """MuPDF parser"""
    def __init__(self, doc: Union[str, bytes],
                 skip_check: Union[bool, None] = None,
                 hash_exclude: Union[str, List[str], None] = None,
                 page_hashes: Union[int, Tuple[Any], None] = None,
                 validate_hash: bool = False,
                 parse_streams: Union[bool, None] = None,
                 binary_path: Union[str, None] = None,
                 temp_folders_dir: Union[str, None] = None,
                 dpi: Union[int, None] = None,
                 cache_renders: Union[bool, None] = None,
                 timeout: Union[int, None] = None,
                 ocr: Union[bool, None] = None
                 ):
        """
        Parameters
        ----------
        parse_streams : bool
            Indicates whether mutool clean should be called with -s or not. -s parses into the content streams of the
            PDF.
        binary_path : str
            If the mutool binary is not in the system PATH, add the path to the binary here. Can also be used to trace
            specific versions of the binary.
        """
        config = _load_config()
        skip_check = _get_config_param(MuPDF, config, 'skip_check', skip_check, False)
        hash_exclude = _get_config_param(MuPDF, config, 'hash_exclude', hash_exclude, None)
        parse_streams = _get_config_param(MuPDF, config, 'parse_streams', parse_streams, True)
        binary_path = _get_config_param(MuPDF, config, 'binary_path', binary_path, None)
        temp_folders_dir = _get_config_param(MuPDF, config, 'temp_folders_dir', temp_folders_dir, None)
        dpi = _get_config_param(MuPDF, config, 'dpi', dpi, 200)
        cache_renders = _get_config_param(MuPDF, config, 'cache_renders', cache_renders, False)
        timeout = _get_config_param(MuPDF, config, 'timeout', timeout, None)
        ocr = _get_config_param(MuPDF, config, 'ocr', ocr, False)

        super().__init__(doc=doc,
                         temp_folders_dir=temp_folders_dir,
                         skip_check=skip_check,
                         hash_exclude=hash_exclude,
                         page_hashes=page_hashes,
                         validate_hash=validate_hash,
                         dpi=dpi,
                         cache_renders=cache_renders,
                         timeout=timeout,
                         ocr=ocr)
        self._parse_streams = parse_streams
        self._cmd_path = 'mutool clean' if binary_path is None else binary_path.strip() + ' clean'
        self._trace_exit_code = None

    def _check_for_renderer(self) -> bool:
        if self._can_render is None:
            self._can_render = 'fitz' in sys.modules.keys()
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
            elif len(results) == 0:
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
                    ['%i: %s' % (page, result) for (page, result) in results if result != SUCCESS and result != SUCCESS_WITH_WARNINGS])
            self._validity[RENDER] = validity_results
            return validity_results

    # @staticmethod
    # def get_name():
    #     return 'MuDraw'

    def _get_num_pages(self):
        with tempfile.TemporaryDirectory(dir=self._temp_folders_dir) as temp_path:
            if isinstance(self._doc, bytes):
                file_hash = hash_file(self._doc)
                doc_path = os.path.join(temp_path, file_hash)
                with open(doc_path, 'wb') as doc_out:
                    doc_out.write(self._doc)
            else:
                doc_path = self._doc
            try:
                doc = fitz.open(doc_path)
                self._num_pages = doc.pageCount
            except Exception as e:
                print(e)
                self._num_pages = 0
            finally:
                try:
                    doc.close()
                except:
                    pass

    def _mudraw(self, page, mat):
        pix = page.get_pixmap(matrix=mat)
        width = pix.width
        height = pix.height
        return Image.frombytes("RGB", [width, height], pix.samples)

    def _render_page(self, page):
        with tempfile.TemporaryDirectory(dir=self._temp_folders_dir) as temp_path:
            if isinstance(self._doc, bytes):
                file_hash = hash_file(self._doc)
                doc_path = os.path.join(temp_path, file_hash)
                with open(doc_path, 'wb') as doc_out:
                    doc_out.write(self._doc)
            else:
                doc_path = self._doc
            start_time = time.perf_counter()
            try:
                mat = fitz.Matrix(self._dpi / 72, self._dpi / 72)
                fitz.TOOLS.reset_mupdf_warnings()
                doc = fitz.open(doc_path)
                if self._timeout is None:
                    mu_pil: PngImageFile = self._mudraw(doc[page], mat)
                else:
                    mu_pil: PngImageFile = func_timeout(
                        self._timeout,
                        self._mudraw,
                        kwargs={
                            'page': doc[page],
                            'mat': mat
                        }
                    )
                doc.close()
                if self._caching:
                    self._renders[page] = mu_pil
                timing = time.perf_counter() - start_time
                warnings = fitz.TOOLS.mupdf_warnings()
                result = SUCCESS if warnings == '' else SUCCESS_WITH_WARNINGS
                self._logs[page] = {'result': result, 'timing': timing}
                self._file_timed_out[RENDER] = False
            except FunctionTimedOut:
                mu_pil: PngImageFile = None
                self._logs[page] = {'result': 'Timed out', 'timing': self._timeout}
                self._file_timed_out[RENDER] = True
            except Exception as e:
                mu_pil: PngImageFile = None
                timing = time.perf_counter() - start_time
                self._logs[page] = {'result': str(e), 'timing': timing}
                self._file_timed_out[RENDER] = False
            return mu_pil

    def _render_doc(self, pages=None):
        with tempfile.TemporaryDirectory(dir=self._temp_folders_dir) as temp_path:
            if isinstance(self._doc, bytes):
                file_hash = hash_file(self._doc)
                doc_path = os.path.join(temp_path, file_hash)
                with open(doc_path, 'wb') as doc_out:
                    doc_out.write(self._doc)
            else:
                doc_path = self._doc
            start_time = time.perf_counter()
            try:
                mat = fitz.Matrix(self._dpi / 72, self._dpi / 72)
                doc = fitz.open(doc_path)
                num_pages = doc.pageCount
                if num_pages == 0 and pages is not None:
                    num_pages = max(pages) + 1
                if pages is None:
                    page_range = range(num_pages)
                else:
                    page_range = [page for page in pages if -1 < page < num_pages]
                if len(doc) == 0:
                    doc.close()
                    raise Exception('Document failed to load')
                pils: Dict[int, PngImageFile] = dict()
                for page in page_range:
                    fitz.TOOLS.reset_mupdf_warnings()
                    page_start = time.perf_counter()
                    try:
                        if self._timeout is None:
                            pils[page] = self._mudraw(doc[page], mat)
                        else:
                            pils[page] = func_timeout(
                                self._timeout,
                                self._mudraw,
                                kwargs={
                                    'page': doc[page],
                                    'mat': mat
                                }
                            )
                        timing = time.perf_counter() - page_start
                        warnings = fitz.TOOLS.mupdf_warnings()
                        result = SUCCESS if warnings == '' else SUCCESS_WITH_WARNINGS
                        self._logs[page] = {'result': result, 'timing': timing}
                        self._file_timed_out[RENDER] = False
                    except FunctionTimedOut:
                        self._logs[page] = {'result': 'Timed out', 'timing': self._timeout}
                        self._file_timed_out[RENDER] = True
                    except Exception as e:
                        self._logs[page] = {'result': str(e), 'timing': time.perf_counter() - page_start}
                        self._file_timed_out[RENDER] = False
                doc.close()
                if self._caching:
                    if pages is None:
                        self._full_doc_rendered = True
                    self._renders.update(pils)
                # timing = time.perf_counter() - start_time
                # num_pages = len(pils)
                # for page in pils.keys():
                #     self._logs[page] = {'result': SUCCESS, 'timing': timing / num_pages}
            except Exception as e:
                pils: Dict[int, PngImageFile] = dict()
                timing = time.perf_counter() - start_time
                self._logs[0] = {'result': str(e), 'timing': timing}
                self._file_timed_out[RENDER] = False
            return pils

    def _render_pages(self, pages: List[int]):
        return self._render_doc(pages)

# class MuPDF(Tracer, TextCompare):
#     """MuPDF tracer and renderer """
#     def __init__(self, doc_path: str,
#                  parse_streams: bool = True,
#                  binary_path: str = None,
#                  temp_folders_dir: str = None
#                  ):
#         """
#         Parameters
#         ----------
#         doc_path : str
#             Full path to the document to be traced.
#         parse_streams : bool
#             Indicates whether mutool clean should be called with -s or not. -s parses into the content streams of the
#             PDF.
#         binary_path : str
#             If the mutool binary is not in the system PATH, add the path to the binary here. Can also be used to trace
#             specific versions of the binary.
#         temp_folders_dir : str
#             Path to create the temporary directories used for temporary files.
#         """
#         super().__init__(doc_path=doc_path)
#         self._parse_streams = parse_streams
#         self._temp_folders_dir = temp_folders_dir
#         self._cmd_path = 'mutool clean' if binary_path is None else binary_path

    def _check_for_text_extraction(self) -> bool:
        if self._ocr:
            if self._can_extract is None:
                if self._can_render is None:
                    _ = self._check_for_renderer()
                self._can_extract = 'pytesseract' in sys.modules.keys() and self._can_render
        else:
            if self._can_extract is None:
                self._can_extract = 'fitz' in sys.modules.keys()
        return self._can_extract

    @property
    def validate_text(self) -> Dict[str, Any]:
        if TEXT not in self._validity:
            fitz.TOOLS.reset_mupdf_warnings()
            validity_results = dict()
            with tempfile.TemporaryDirectory(dir=self._temp_folders_dir) as temp_path:
                if isinstance(self._doc, bytes):
                    file_hash = hash_file(self._doc)
                    doc_path = os.path.join(temp_path, file_hash)
                    with open(doc_path, 'wb') as doc_out:
                        doc_out.write(self._doc)
                else:
                    doc_path = self._doc
                try:
                    doc = fitz.open(doc_path)
                    for page in doc:
                        text = page.getText()
                        if not self._ocr and page.number not in self._text:
                            self._text[page.number] = text
                    if not self._ocr:
                        self._full_text_extracted = True
                    warnings = fitz.TOOLS.mupdf_warnings()
                    error = None
                except Exception as e:
                    error = str(e)
                    warnings = None
                finally:
                    try:
                        doc.close()
                    except:
                        pass
                if error is not None:
                    validity_results['valid'] = False
                    validity_results['status'] = REJECTED
                    validity_results['info'] = error
                else:
                    validity_results['valid'] = True
                    if warnings == '':
                        validity_results['status'] = VALID
                    else:
                        validity_results['status'] = VALID_WARNINGS
                        validity_results['info'] = warnings
                self._validity[TEXT] = validity_results
        return self._validity[TEXT]

    def _check_for_tracer(self) -> bool:
        if self._can_trace is None:
            try:
                subprocess.check_output(shlex.split("mutool -v"), shell=False)
                mutool_present = True
            except subprocess.CalledProcessError as e:
                mutool_present = False
            self._can_trace = mutool_present
        return self._can_trace

    def _check_for_reforger(self) -> bool:
        if self._can_reforge is None:
            self._can_reforge = self._check_for_tracer()
        return self._can_reforge

    def _reforge(self):
        stream_flag = ' -s' if self._parse_streams else ''

        with tempfile.TemporaryDirectory(dir=self._temp_folders_dir) as temp_path:
            if isinstance(self._doc, bytes):
                file_hash = hash_file(self._doc)
                doc_path = os.path.join(temp_path, file_hash)
                with open(doc_path, 'wb') as doc_out:
                    doc_out.write(self._doc)
            else:
                doc_path = self._doc
            try:
                out_path = os.path.join(temp_path, 'out.pdf')
                sp = subprocess.Popen(shlex.split('mutool clean%s %s %s' % (stream_flag, doc_path, out_path)),
                                      stderr=subprocess.PIPE, stdout=subprocess.PIPE, shell=False)
                (_, err) = sp.communicate(timeout=self._timeout or 600)
                with open(out_path, 'rb') as file_in:
                    raw = file_in.read()
                self._reforged = raw
                self._successfully_reforged = True
                self._reforge_result = 'Successfully reforged'
                decoder = locale.getpreferredencoding()
                err = fix_splits(err.decode(decoder))
                error_arr = [message for message in err.split('\n') if len(message) > 0]
            except TimeoutExpired:
                sp.kill()
                (_, err) = sp.communicate()
                decoder = locale.getpreferredencoding()
                err = fix_splits(err.decode(decoder))
                error_arr = [message for message in err.split('\n') if len(message) > 0]
                error_arr.insert(0, 'Error: Subprocess timed out: %i' % (self._timeout or 600))
                self._successfully_reforged = False
                self._reforge_result = '[' + ', '.join(error_arr) + ']'
            except Exception as e:
                sp.kill()
                decoder = locale.getpreferredencoding()
                err = fix_splits(err.decode(decoder))
                error_arr = str(e).split('\n')
                error_arr.extend([message for message in err.split('\n') if len(message) > 0])
                self._successfully_reforged = False
                self._reforge_result = '[' + ', '.join(error_arr) + ']'
        self._trace_exit_code = sp.returncode
        self._messages = ['No warnings'] if len(error_arr) == 0 else error_arr

    @property
    def validate_tracer(self) -> Dict[str, Any]:
        if TRACER not in self._validity:
            validity_results = dict()
            if self._messages is None:
                self._parse_document()
            if self._cleaned is None:
                self._scrub_messages()
            observed_messages = list(self._cleaned.keys())
            if self._file_timed_out[TRACER]:
                validity_results['valid'] = False
                validity_results['status'] = TIMED_OUT
                validity_results['info'] = 'Timed Out: %i' % self._timeout
            elif self._trace_exit_code > 0:
                validity_results['valid'] = False
                validity_results['status'] = REJECTED
                validity_results['info'] = 'Exit code: %i' % self._trace_exit_code
            elif observed_messages == ['No warnings']:
                validity_results['valid'] = True
                validity_results['status'] = VALID
            elif len([message for message in observed_messages if 'error' in message]) > 0:
                validity_results['valid'] = False
                validity_results['status'] = REJECTED
                validity_results['info'] = 'Errors returned'
            elif len([message for message in observed_messages if 'warning' in message]) == len(observed_messages):
                validity_results['valid'] = True
                validity_results['status'] = VALID_WARNINGS
                validity_results['info'] = 'Warnings only'
            else:
                validity_results['valid'] = False
                validity_results['status'] = REJECTED_AMBIG
                validity_results['info'] = 'Unknown message type returned'
            self._validity[TRACER] = validity_results
        return self._validity[TRACER]

    @staticmethod
    def get_name():
        return 'MuPDF'

    @property
    def streams_parsed(self):
        return self._parse_streams

    def _parse_document(self):

        stream_flag = ' -s' if self._parse_streams else ''

        with tempfile.TemporaryDirectory(dir=self._temp_folders_dir) as temp_path:
            if isinstance(self._doc, bytes):
                file_hash = hash_file(self._doc)
                doc_path = os.path.join(temp_path, file_hash)
                with open(doc_path, 'wb') as doc_out:
                    doc_out.write(self._doc)
            else:
                doc_path = self._doc
            try:
                out_path = os.path.join(temp_path, 'out.pdf')
                sp = subprocess.Popen(shlex.split('mutool clean%s %s %s' % (stream_flag, doc_path, out_path)),
                                      stderr=subprocess.PIPE, stdout=DEVNULL, shell=False)
                (_, err) = sp.communicate(timeout=self._timeout or 600)
                decoder = locale.getpreferredencoding()
                err = fix_splits(err.decode(decoder))
                error_arr = [message for message in err.split('\n') if len(message) > 0]
                self._file_timed_out[TRACER] = False
            except TimeoutExpired:
                sp.kill()
                (_, err) = sp.communicate()
                decoder = locale.getpreferredencoding()
                err = fix_splits(err.decode(decoder))
                error_arr = [message for message in err.split('\n') if len(message) > 0]
                error_arr.insert(0, 'Error: Subprocess timed out: %i' % (self._timeout or 600))
                self._file_timed_out[TRACER] = True
            except Exception as e:
                sp.kill()
                decoder = locale.getpreferredencoding()
                err = fix_splits(err.decode(decoder))
                error_arr = str(e).split('\n')
                error_arr.extend([message for message in err.split('\n') if len(message) > 0])
                self._file_timed_out[TRACER] = False
        self._trace_exit_code = sp.returncode
        self._messages = ['No warnings'] if len(error_arr) == 0 else error_arr

    def _clean_message(self, err):
        cleaned = re.sub(r'\([\d]+ [\d]+ R\)', '', err)
        cleaned = re.sub(r'[\d]+ [\d]+ R', '', cleaned)
        cleaned = re.sub(r"\'[^']+\'", '', cleaned)
        cleaned = 'error: expected generation number' if cleaned.startswith(
            'error: expected generation number ') else cleaned
        cleaned = 'error: unknown colorspace' if cleaned.startswith('error: unknown colorspace: ') else cleaned
        cleaned = re.sub(r'non-embedded font using identity encoding: [.]*',
                         'non-embedded font using identity encoding: <font>', cleaned)
        cleaned = re.sub(r'\(gid [\d]+\)', '', cleaned)
        cleaned = 'error: expected  keyword' if cleaned.startswith('error: expected  keyword ') else cleaned
        cleaned = 'warning: unknown filter name' if cleaned.startswith('warning: unknown filter name ') else cleaned
        cleaned = 'error: aes padding out of range' if cleaned.startswith(
            'error: aes padding out of range:') else cleaned
        cleaned = 'error: cannot authenticate password' if cleaned.startswith(
            'error: cannot authenticate password:') else cleaned
        cleaned = re.sub(r'\[\d+\] prec\(\d+\) sgnd\(\d+\) \[\d+\] prec\(\d+\) sgnd\(\d+\)', 'Out of Memory Error',
                         cleaned)
        cleaned = 'warning: cannot load content stream part' if cleaned.startswith(
            'warning: cannot load content stream part') else cleaned
        cleaned = 'error: object out of range' if cleaned.startswith('error: object out of range') else cleaned
        cleaned = 'warning: object out of range' if cleaned.startswith('warning: object out of range') else cleaned
        cleaned = 'error: object id  out of range' if cleaned.startswith('error: object id  out of range') else cleaned
        cleaned = re.sub(r"\'\'", '', cleaned)
        cleaned = 'error: invalid reference to non-object-stream' if cleaned.startswith(
            'error: invalid reference to non-object-stream:') else cleaned
        cleaned = 'error: object offset out of range' if cleaned.startswith(
            'error: object offset out of range:') else cleaned
        cleaned = 'error: unexpected xref type' if cleaned.startswith('error: unexpected xref type:') else cleaned
        cleaned = 'error: unknown keyword' if cleaned.startswith('error: unknown keyword:') else cleaned
        cleaned = re.sub(r'warning: Encountered new definition for object \d+ - keeping the original one',
                         'warning: Encountered new definition for object - keeping the original one', cleaned)
        cleaned = 'warning: bf_range limits out of range in cmap' if cleaned.startswith(
            'warning: bf_range limits out of range in cmap') else cleaned
        cleaned = re.sub(r'ignoring one to many mapping in cmap [.]*',
                         'ignoring one to many mapping in cmap', cleaned)
        cleaned = re.sub(r'\(segment [\-]?\d+\)', '', cleaned)
        cleaned = re.sub(r'\([\-]?\d+\)', '', cleaned)
        cleaned = re.sub(r'\(\d+\/\d+\)', '', cleaned)
        cleaned = 'warning: jbig2dec error: Invalid SYMWIDTH value' if cleaned.startswith(
            'warning: jbig2dec error: Invalid SYMWIDTH value') else cleaned
        cleaned = 'warning: jbig2dec error: No OOB signalling end of height class' if cleaned.startswith(
            'warning: jbig2dec error: No OOB signalling end of height class') else cleaned
        cleaned = 'warning: openjpeg error: Failed to decode tile' if cleaned.startswith(
            'warning: openjpeg error: Failed to decode tile') else cleaned
        cleaned = 'warning: openjpeg error: Invalid component index' if cleaned.startswith(
            'warning: openjpeg error: Invalid component index') else cleaned
        cleaned = 'warning: openjpeg error: Invalid tile part index for tile number' if cleaned.startswith(
            'warning: openjpeg error: Invalid tile part index for tile number') else cleaned
        cleaned = re.sub(
            r'warning: openjpeg error: Invalid values for comp = \d+ : prec=\d+ (should be between 1 and 38 according to the JPEG2000 norm. OpenJpeg only supports up to 31)',
            'warning: openjpeg error: Invalid values for comp = x : prec=y (should be between 1 and 38 according to the JPEG2000 norm. OpenJpeg only supports up to 31)',
            cleaned)
        cleaned = 'warning: openjpeg error: read: segment too long  with max  for codeblock' if cleaned.startswith(
            'warning: openjpeg error: read: segment too long  with max  for codeblock') else cleaned
        cleaned = re.sub(r'comp\[\d+\]', 'comp', cleaned)
        cleaned = re.sub(r'ignoring CMap range \(\d+-\d+\)', 'ignoring CMap range (a-b)', cleaned)
        cleaned = re.sub(r'FT_New_Memory_Face\([^)]+\)', 'FT_New_Memory_Face(x)', cleaned)
        cleaned = re.sub(r'FT_Load_Glyph\([^)]+\)', 'FT_Load_Glyph(x)', cleaned)
        cleaned = re.sub(r'FT_Set_Char_Size\([^)]+\)', 'FT_Set_Char_Size(x)', cleaned)
        cleaned = re.sub(r'Subprocess timed out: [\d]+', 'Subprocess timed out: <t>', cleaned)
        cleaned = re.sub(r'error: cannot find page [\d]+ in page tree',
                         'error: cannot find page <p> in page tree', cleaned)
        cleaned = re.sub(r'unknown cid collection: [.]+', 'unknown cid collection', cleaned)
        cleaned = re.sub(r'content stream is not a stream \([^)]*\)',
                         'content stream is not a stream (<x>)', cleaned)
        cleaned = re.sub(r'expected endobj or stream keyword \([^)]*\)',
                         'expected endobj or stream keyword (<x>)', cleaned)
        cleaned = re.sub(r'ignoring object with invalid object number \([^)]*\)',
                         'ignoring object with invalid object number (<x>)', cleaned)
        cleaned = re.sub(r'invalid indirect reference \([^)]*\)',
                         'invalid indirect reference (<x>)', cleaned)

        cleaned: str = re.sub(r'\[\d+\] prec\(\d+\) sgnd\(\d+\) \[\d+\] prec\(\d+\) sgnd\(\d+\)', 'Out of Memory Error',
                              cleaned)

        return cleaned

    def _mupdf_scrub(self, messages):
        scrubbed_messages = [self._clean_message(err) for err in messages]
        error_dict: Dict[str, int] = dict()
        for (index, error) in enumerate(scrubbed_messages):
            if '... repeated ' in error:
                repeated = re.sub(r'[^\d]', '', error)
                error_dict[self._messages[index - 1]] = error_dict.get(error, 0) + int(repeated)
            else:
                error_dict[error] = error_dict.get(error, 0) + 1
        return error_dict

    def _scrub_messages(self):

        if self._messages is None:
            self._parse_document()
        error_dict = self._mupdf_scrub(self._messages)
        self._cleaned = error_dict

    def _extract_page(self, page: int):
        if self._ocr:
            self._text[page] = _ocr_text(self.get_renders(page=page))
        else:
            with tempfile.TemporaryDirectory(dir=self._temp_folders_dir) as temp_path:
                if isinstance(self._doc, bytes):
                    file_hash = hash_file(self._doc)
                    doc_path = os.path.join(temp_path, file_hash)
                    with open(doc_path, 'wb') as doc_out:
                        doc_out.write(self._doc)
                else:
                    doc_path = self._doc
                doc = fitz.open(doc_path)
                text = doc[page].getText()
                doc.close()
                self._text[page] = text

    def _extract_doc(self):
        if self._ocr:
            for (page, pil) in self.get_renders().items():
                self._text[page] = _ocr_text(pil)
        else:
            with tempfile.TemporaryDirectory(dir=self._temp_folders_dir) as temp_path:
                if isinstance(self._doc, bytes):
                    file_hash = hash_file(self._doc)
                    doc_path = os.path.join(temp_path, file_hash)
                    with open(doc_path, 'wb') as doc_out:
                        doc_out.write(self._doc)
                else:
                    doc_path = self._doc
                doc = fitz.open(doc_path)
                for page in doc:
                    self._text[page.number] = page.getText()
                doc.close()
            self._full_text_extracted = True
