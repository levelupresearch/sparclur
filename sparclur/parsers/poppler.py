import locale

from sparclur.parsers._renderer import Renderer
from sparclur.parsers._parser import Parser
from sparclur.utils.tools import fix_splits

from typing import List, Dict
import tempfile
import subprocess
from subprocess import DEVNULL
import re
import os

from PIL import Image
from PIL.PngImagePlugin import PngImageFile


def _parse_poppler_size(size):
    if not (isinstance(size, tuple) or isinstance(size, int) or isinstance(size, float)) or size is None:
        size_cmd = None
    else:
        if isinstance(size, int) or isinstance(size, float):
            size = tuple([size])
        if len(size) == 2:
            x_scale = -1 if size[0] is None else str(int(size[0]))
            y_scale = -1 if size[1] is None else str(int(size[1]))
            size_cmd = ['-scale-to-x', x_scale, '-scale-to-y', y_scale]
        elif len(size) == 1:
            scale = -1 if size[0] is None else str(int(size[0]))
            size_cmd = ['scale-to', scale]
    return size_cmd


class Poppler(Parser, Renderer):

    def __init__(self, doc_path, binary_path=None, temp_folders_dir=None, cache_renders=False):
        self._name = "Poppler"
        self._doc_path = doc_path
        self._temp_folders_dir = temp_folders_dir
        self._caching = cache_renders
        self._renders: Dict[int, PngImageFile] = dict()
        self._full_doc_rendered = False
        self._messages: List[str] = None
        self._cleaned: List[str] = None
        self._cmd_path = 'pdftoppm' if binary_path is None else binary_path
        try:
            subprocess.check_output(self._cmd_path + " -v", shell=True)
            self._poppler_present = True
        except subprocess.CalledProcessError as e:
            print("pdftoppm binary not found: ", str(e))
            self._poppler_present = False

    def get_name(self):
        return self.name

    def get_doc_path(self):
        return self._doc_path

    def _parse_document(self):

        if not self._poppler_present:
            raise OSError("Unable to find pdftoppm.")

        with tempfile.TemporaryDirectory(dir=self._temp_folders_dir) as temp_path:
            sp = subprocess.Popen('%s %s %s' % (self._cmd_path, self._doc_path, os.path.join(temp_path, 'out')), executable='/bin/bash',
                                  stderr=subprocess.PIPE, stdout=DEVNULL, shell=True)
            (_, err) = sp.communicate()
            decoder = locale.getpreferredencoding()
            err = fix_splits(err.decode(decoder))
        error_arr = [message for message in err.split('\n') if len(message) > 0]
        self._messages = ['No warnings'] if len(error_arr) == 0 else error_arr

    def get_messages(self):

        if not self._poppler_present:
            raise OSError("Unable to find pdftoppm.")

        if self._messages is None:
            self._parse_document()

        return self._messages

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
        self._cleaned = [self._clean_message(err) for err in self._messages]

    def get_cleaned(self):

        if self._cleaned is None:
            self._scrub_messages()

        return self._cleaned

    def _poppler_render(self, dpi=200, size=None, page=None):

        if not self._poppler_present:
            raise OSError("Unable to find pdftoppm.")

        return_single_page = False
        cmd = [self._cmd_path, '-png', '-r', str(dpi)]
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
            (stdout, err) = sp.communicate()
            rendered_pages = [int(re.sub('out-', '', re.sub('.png', '', file))) for file in os.listdir(temp_path)]
            highest_rendered_page = max(rendered_pages)
            result: Dict[int, PngImageFile] = dict()
            for render in os.listdir(temp_path):
                page_index = int(re.sub('out-', '', re.sub('.png', '', render))) - 1
                result[page_index] = Image.open(os.path.join(temp_path, render))
        if return_single_page:
            result: PngImageFile = result.get(int(page) - 1)
        return result

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

    def _render_page(self, page, dpi=200, size=None):
        render: PngImageFile = self._poppler_render(page=page, dpi=dpi, size=size)
        if self._caching:
            self._renders[page] = render
        return render

    def _render_doc(self, dpi=200, size=None):
        renders: Dict[int, PngImageFile] = self._poppler_render(dpi=dpi, size=size, page=None)
        if self._caching:
            self._full_doc_rendered = True
            self._renders = renders
        return self._poppler_render(dpi=dpi, size=size, page=None)
