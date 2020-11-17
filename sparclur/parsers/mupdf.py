import locale
from typing import List, Dict

from sparclur.parsers._renderer import Renderer
from sparclur.parsers._parser import Parser
from sparclur.utils.tools import fix_splits

import os
import re
import subprocess
import tempfile

import fitz

from PIL import Image
from PIL.PngImagePlugin import PngImageFile


class MuPDF(Parser, Renderer):

    def __init__(self, doc_path, parse_streams=True, binary_path=None, temp_folders_dir=None, cache_renders=False):
        self._name = 'MuPDF'
        self._doc_path = doc_path
        self._parse_streams = parse_streams
        self._caching = cache_renders
        self._renders: Dict[int, PngImageFile] = dict()
        self._full_doc_rendered = False
        self._messages: List[str] = None
        self._cleaned: List[str] = None
        self._temp_folders_dir = temp_folders_dir
        self._cmd_path = 'mutool clean' if binary_path is None else binary_path
        try:
            subprocess.check_output("mutool -v", shell=True)
            self._mutool_present = True
        except subprocess.CalledProcessError as e:
            print("MuPDF binary not found: ", str(e))
            self._mutool_present = False

    def get_doc_path(self):
        return self._doc_path

    def get_name(self):
        return self._name

    def streams_parsed(self):
        return self._parse_streams

    def _parse_document(self):

        if not self._mutool_present:
            raise OSError("Unable to find MuPDF.")

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

    def get_messages(self):

        if not self._mutool_present:
            raise OSError("Unable to find MuPDF.")

        if self._messages is None:
            self._parse_document()

        return self._messages

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
        self._cleaned = [self._clean_message(err) for err in self._messages]

    def get_cleaned(self):

        if self._cleaned is None:
            self._scrub_messages()

        return self._cleaned

    def set_caching(self, caching: bool):
        assert isinstance(caching, bool)
        self._caching = caching

    def get_caching(self):
        return self._caching

    def clear_cache(self):
        self._full_doc_rendered = False
        self._renders: Dict[int, PngImageFile] = dict()

    def get_renders(self, page: int = None, dpi=200):

        if self._renders:
            if page is not None:
                if page in self._renders:
                    result = self._renders[page]
                else:
                    result = self._render_page(page=page, dpi=dpi)
            else:
                if self._full_doc_rendered:
                    result = self._renders
                else:
                    result = self._render_doc(dpi=dpi)
        else:
            if page is not None:
                result = self._render_page(page=page, dpi=dpi)
            else:
                result = self._render_doc(dpi=dpi)
        return result

    def _render_page(self, page, dpi=200):
        try:
            mat = fitz.Matrix(dpi / 72, dpi / 72)
            doc = fitz.open(self._doc_path)
            pix = doc[page].getPixmap(matrix=mat)
            width = pix.width
            height = pix.height
            mu_pil: PngImageFile = Image.frombytes("RGB", [width, height], pix.samples)
            doc.close()
            if self._caching:
                self._renders[page] = mu_pil
        except Exception as e:
            print(str(e))
            mu_pil: PngImageFile = None
        return mu_pil

    def _render_doc(self, dpi=200):
        try:
            mat = fitz.Matrix(dpi / 72, dpi / 72)
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
        except Exception as e:
            print(e)
            pils: Dict[int, PngImageFile] = dict()
        return pils
