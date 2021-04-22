import locale
from typing import Dict

from sparclur._metadata_extractor import MetadataExtractor, METADATA_SUCCESS
from sparclur._tracer import Tracer
from sparclur.utils._tools import fix_splits

import re
import subprocess
import json


class QPDF(Tracer, MetadataExtractor):
    """QPDF tracer"""
    def __init__(self, doc_path: str,
                 binary_path: str = None
                 ):
        """
        Parameters
        ----------
        doc_path : str
            Full path to the document to be traced.
        binary_path : str
            If the qpdf binary is not in the system PATH, add the path to the binary here. Can also be used to trace
            specific versions of the binary.
        temp_folders_dir : str
            Path to create the temporary directories used for temporary files.
        """
        super().__init__(doc_path=doc_path)
        self._doc_path = doc_path
        #self._temp_folders_dir = temp_folders_dir
        self._cmd_path = 'qpdf' if binary_path is None else binary_path
        # try:
        #     subprocess.check_output(self._cmd_path + " --version", shell=True)
        #     self.qpdf_present = True
        # except subprocess.CalledProcessError as e:
        #     print("QPDF binary not found: ", str(e))
        #     self.qpdf_present = False

    def _check_for_qpdf(self) -> bool:
        try:
            subprocess.check_output(self._cmd_path + " --version", shell=True)
            qpdf_present = True
        except subprocess.CalledProcessError:
            qpdf_present = False
        return qpdf_present

    def _check_for_tracer(self) -> bool:
        if self._can_trace is None:
            qpdf_present = self._check_for_qpdf()
            self._can_trace = qpdf_present
            self._can_meta_extract = qpdf_present
        return self._can_trace

    def _check_for_metadata(self) -> bool:
        if self._can_trace is None:
            qpdf_present = self._check_for_qpdf()
            self._can_trace = qpdf_present
            self._can_meta_extract = qpdf_present
        return self._can_meta_extract

    @staticmethod
    def get_name():
        return 'QPDF'

    def _run_json(self):
        # with tempfile.TemporaryDirectory(dir=self._temp_folders_dir) as temp_path:
        # out_path = os.path.join(temp_path, 'out.pdf')
        sp = subprocess.Popen('%s --json %s' % (self._cmd_path, self._doc_path), executable='/bin/bash',
                              stderr=subprocess.PIPE, stdout=subprocess.PIPE, shell=True)
        (stdout, err) = sp.communicate()
        decoder = locale.getpreferredencoding()
        err = fix_splits(err.decode(decoder, errors='ignore'))
        stdout = stdout.decode(decoder, errors='ignore')
        error_arr = [message for message in err.split('\n') if len(message) > 0]
        self._messages = ['No warnings'] if len(error_arr) == 0 else error_arr
        try:
            file = json.loads(stdout)
            objects = file['objects'].items()
            self._metadata = dict(objects)
            self._metadata_result = METADATA_SUCCESS
        except Exception as e:
            self._metadata_result = str(e)

    def _parse_document(self):
        self._run_json()

    def _extract_metadata(self):
        self._run_json()

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
        scrubbed_messages = [self._clean_message(err) for err in self._messages]
        error_dict: Dict[str, int] = dict()
        for (index, error) in enumerate(scrubbed_messages):
            if error.startswith('warning: ... repeated '):
                repeated = re.sub(r'[^\d]', '', error)
                error_dict[self._messages[index - 1]] = error_dict.get(error, 0) + int(repeated)
            else:
                error_dict[error] = error_dict.get(error, 0) + 1
        self._cleaned = error_dict
