import locale
from typing import List, Dict

from sparclur._tracer import Tracer
from sparclur.utils.tools import fix_splits

import os
import re
import subprocess
import tempfile


class PDFToCairo(Tracer):
    """SPARCLUR tracer wrapper for pdftocairo"""
    def __init__(self, doc_path, binary_path=None, temp_folders_dir=None):
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
        self._doc_path: str = doc_path
        self._temp_folders_dir = temp_folders_dir
        self._messages: List[str] = None
        self._cleaned: Dict[str, int] = None
        self._cmd_path = 'pdftocairo' if binary_path is None else binary_path
        try:
            subprocess.check_output(self._cmd_path + " -v", shell=True)
            self._pdftocairo_present = True
        except subprocess.CalledProcessError as e:
            print("pdftocairo binary not found: ", str(e))
            self._pdftocairo_present = False

    def get_doc_path(self):
        return self._doc_path

    @staticmethod
    def get_name():
        return 'PDFToCairo'

    def _parse_document(self):

        if not self._pdftocairo_present:
            raise OSError("Unable to find pdftocairo.")

        with tempfile.TemporaryDirectory(dir=self._temp_folders_dir) as temp_path:
            out_path = os.path.join(temp_path, 'out.pdf')
            sp = subprocess.Popen('%s -ps %s %s' % (self._cmd_path, self._doc_path, out_path), executable='/bin/bash',
                                  stderr=subprocess.PIPE, stdout=subprocess.PIPE, shell=True)
            (stdout, err) = sp.communicate()
        decoder = locale.getpreferredencoding()
        err = fix_splits(err.decode(decoder))
        error_arr = [message for message in err.split('\n') if len(message) > 0]
        self._messages = ['No warnings'] if len(error_arr) == 0 else error_arr

    def get_messages(self):

        if not self._pdftocairo_present:
            raise OSError("Unable to find pdftocairo.")

        if self._messages is None:
            self._parse_document()

        return self._messages

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

    def get_cleaned(self):

        if self._cleaned is None:
            self._scrub_messages()

        return self._cleaned
