import locale
from typing import List

from sparclur.parsers._parser import Parser
from sparclur.utils.tools import fix_splits

import os
import re
import subprocess
import tempfile


class QPDF(Parser):

    def __init__(self, doc_path, binary_path=None, temp_folders_dir=None):
        self._name = 'QPDF'
        self._doc_path = doc_path
        self._temp_folders_dir = temp_folders_dir
        self._messages: List[str] = None
        self._cleaned: List[str] = None
        self._cmd_path = 'qpdf' if binary_path is None else binary_path
        try:
            subprocess.check_output(self._cmd_path + " --version", shell=True)
            self.qpdf_present = True
        except subprocess.CalledProcessError as e:
            print("QPDF binary not found: ", str(e))
            self.qpdf_present = False

    def get_name(self):
        return self.name

    def get_doc_path(self):
        return self._doc_path

    def _parse_document(self):

        if not self.qpdf_present:
            raise OSError("Unable to find QPDF.")

        with tempfile.TemporaryDirectory(dir=self._temp_folders_dir) as temp_path:
            out_path = os.path.join(temp_path, 'out.pdf')
            sp = subprocess.Popen('%s --json %s' % (self._cmd_path, self._doc_path), executable='/bin/bash',
                                  stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, shell=True)
            (stdout, err) = sp.communicate()
        decoder = locale.getpreferredencoding()
        err = fix_splits(err.decode(decoder))
        error_arr = [message for message in err.split('\n') if len(message) > 0]
        self._messages = ['No warnings'] if len(error_arr) == 0 else error_arr

    def get_messages(self):

        if not self.qpdf_present:
            raise OSError("Unable to find QPDF.")

        if self._messages is None:
            self._parse_document()

        return self._messages

    def _clean_message(self, err):
        split_attempt = err.split(': ')
        if len(split_attempt) == 4:
            err = split_attempt[2] + ' ' + split_attempt[3]
        elif len(split_attempt) == 3:
            err = split_attempt[0] + ': ' + split_attempt[-1]
        else:
            err = split_attempt[-1]
        cleaned = re.sub(r'recovered stream length [\d]+', 'recovered stream length', err)
        cleaned = re.sub(r'object [\d]+ [\d+]', 'object', cleaned)
        cleaned = re.sub(r" \(obj=[\d]+\)", "", cleaned)
        cleaned = re.sub(r'converting [\d]+ ', "converting bigint ", cleaned)
        cleaned = re.sub(r' /QPDFFake[\d]+', "", cleaned)
        cleaned = re.sub(r'\([^)]*\)\s{0, 1}', "", cleaned)
        cleaned: str = re.sub(r' [\d]+ [\d]+ obj\s{0, 1}', ' something else ', cleaned)
        return cleaned

    def _scrub_messages(self):

        if self._messages is None:
            self._parse_document()
        self._cleaned = [self._clean_message(err) for err in self._messages]

    def get_cleaned(self):

        if self._cleaned is None:
            self._scrub_messages()

        return self._cleaned
