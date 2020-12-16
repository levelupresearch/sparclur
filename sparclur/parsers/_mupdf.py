import locale
from typing import List, Dict

from sparclur._renderer import Renderer
from sparclur._renderer import _SUCCESSFUL_RENDER_MESSAGE as SUCCESS
from sparclur._tracer import Tracer
from sparclur.utils.tools import fix_splits

import os
import sys
import re
import subprocess
import tempfile
import time

import fitz

from PIL import Image
from PIL.PngImagePlugin import PngImageFile


class MuPDF(Tracer, Renderer):
    """MuPDF tracer and renderer """
    def __init__(self, doc_path: str,
                 parse_streams: bool = True,
                 binary_path: str = None,
                 temp_folders_dir: str = None,
                 dpi: int = 200,
                 cache_renders: bool = False,
                 verbose: bool = False):
        """
        Parameters
        ----------
        doc_path : str
            Full path to the document to be traced.
        parse_streams : bool
            Indicates whether mutool clean should be called with -s or not. -s parses into the content streams of the
            PDF.
        binary_path : str
            If the mutool binary is not in the system PATH, add the path to the binary here. Can also be used to trace
            specific versions of the binary.
        temp_folders_dir : str
            Path to create the temporary directories used for temporary files.
        dpi : int
            Dots per inch used in rendering the document
        cache_renders : bool
            Specify whether or not renders should be retained in the object
        verbose : bool
            Specify whether additional logging should be saved, such as successful renders and timing
        """
        super().__init__(doc_path=doc_path, dpi=dpi, cache_renders=cache_renders, verbose=verbose)
        self._parse_streams = parse_streams
        self._temp_folders_dir = temp_folders_dir
        self._cmd_path = 'mutool clean' if binary_path is None else binary_path

    def _check_for_renderer(self) -> bool:
        return 'fitz' in sys.modules.keys()

    def _check_for_tracer(self) -> bool:
        try:
            subprocess.check_output("mutool -v", shell=True)
            mutool_present = True
        except subprocess.CalledProcessError as e:
            mutool_present = False
        return mutool_present

    @staticmethod
    def get_name():
        return 'MuPDF'

    @property
    def streams_parsed(self):
        return self._parse_streams

    def _parse_document(self):

        stream_flag = ' -s' if self._parse_streams else ''

        with tempfile.TemporaryDirectory(dir=self._temp_folders_dir) as temp_path:
            out_path = os.path.join(temp_path, 'out.pdf')
            sp = subprocess.Popen('mutool clean%s %s %s' % (stream_flag, self._doc_path, out_path),
                                  executable='/bin/bash',
                                  stderr=subprocess.PIPE, stdout=subprocess.PIPE, shell=True)
            (stdout, err) = sp.communicate()
        decoder = locale.getpreferredencoding()
        err = fix_splits(err.decode(decoder))
        error_arr = [message for message in err.split('\n') if len(message) > 0]
        self._messages = ['No warnings'] if len(error_arr) == 0 else error_arr

    def _clean_message(self, err):
        cleaned = re.sub(r'\([\d]+ [\d]+ R\)', '', err)
        cleaned = re.sub(r'[\d]+ [\d]+ R', '', cleaned)
        cleaned = re.sub(r"\'[^']+\'", '', cleaned)
        cleaned = 'error: expected generation number' if cleaned.startswith(
            'error: expected generation number ') else cleaned
        cleaned = 'error: unknown colorspace' if cleaned.startswith('error: unknown colorspace: ') else cleaned
        cleaned = 'warning: non-embedded font using identity encoding' if cleaned.startswith(
            'warning: non-embedded font using identity encoding: ') else cleaned
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
        cleaned = 'warning: ignoring one to many mapping in cmap' if cleaned.startswith(
            'warning: ignoring one to many mapping in cmap') else cleaned
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
        cleaned: str = re.sub(r'\[\d+\] prec\(\d+\) sgnd\(\d+\) \[\d+\] prec\(\d+\) sgnd\(\d+\)', 'Out of Memory Error',
                              cleaned)

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

    def _render_page(self, page):
        if self._verbose:
            start_time = time.perf_counter()
        try:
            mat = fitz.Matrix(self._dpi / 72, self._dpi / 72)
            doc = fitz.open(self._doc_path)
            pix = doc[page].getPixmap(matrix=mat)
            width = pix.width
            height = pix.height
            mu_pil: PngImageFile = Image.frombytes("RGB", [width, height], pix.samples)
            doc.close()
            if self._caching:
                self._renders[page] = mu_pil
            if self._verbose:
                timing = time.perf_counter() - start_time
                self._logging[page] = {'result': SUCCESS, 'timing': timing}
        except Exception as e:
            print(str(e))
            mu_pil: PngImageFile = None
            if self._verbose:
                timing = time.perf_counter() - start_time
                self._logging[page] = {'result': str(e), 'timing': timing}
        return mu_pil

    def _render_doc(self):
        if self._verbose:
            start_time = time.perf_counter()
        try:
            mat = fitz.Matrix(self._dpi / 72, self._dpi / 72)
            doc = fitz.open(self._doc_path)
            pils: Dict[int, PngImageFile] = dict()
            for page in doc:
                try:
                    pix = page.getPixmap(matrix=mat)
                    width = pix.width
                    height = pix.height
                    pils[page.number] = Image.frombytes("RGB", [width, height], pix.samples)
                except:
                    pass
            doc.close()
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
