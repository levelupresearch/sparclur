import locale
import shlex
from typing import Dict, Any

from sparclur._metadata_extractor import MetadataExtractor, METADATA_SUCCESS
from sparclur._parser import VALID, VALID_WARNINGS, REJECTED, REJECTED_AMBIG, META, TRACER
from sparclur._tracer import Tracer
from sparclur.utils._tools import fix_splits

import re
import subprocess
from subprocess import TimeoutExpired
import json


class QPDF(Tracer, MetadataExtractor):
    """QPDF tracer"""
    def __init__(self, doc_path: str,
                 skip_check: bool = False,
                 binary_path: str = None,
                 timeout: int = None
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
        super().__init__(doc_path=doc_path, skip_check=skip_check, timeout=timeout)
        self._doc_path = doc_path
        #self._temp_folders_dir = temp_folders_dir
        self._decoder = locale.getpreferredencoding()
        self._cmd_path = 'qpdf' if binary_path is None else binary_path
        self._exit_code = None
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

    def validate_tracer(self) -> Dict[str, Any]:
        if TRACER not in self._validity:
            validity_results = dict()
            if self._messages is None:
                self._parse_document()
            if self._cleaned is None:
                self._scrub_messages()
            observed_messages = list(self._cleaned.keys())
            if self._exit_code > 0:
                validity_results['valid'] = False
                validity_results['status'] = REJECTED
                validity_results['info'] = 'Exit code: %i' % self._exit_code
            elif observed_messages == ['No warnings']:
                validity_results['valid'] = True
                validity_results['status'] = VALID
            elif len([message for message in observed_messages if 'ERROR' in message]) > 0:
                validity_results['valid'] = False
                validity_results['status'] = REJECTED
                validity_results['info'] = 'Errors returned'
            elif len([message for message in observed_messages if 'WARNING' in message]) == len(observed_messages):
                validity_results['valid'] = True
                validity_results['status'] = VALID_WARNINGS
                validity_results['info'] = 'Warnings only'
            else:
                validity_results['valid'] = False
                validity_results['status'] = REJECTED_AMBIG
                validity_results['info'] = 'Unknown message type returned'
            self._validity[TRACER] = validity_results
            self._validity[META] = validity_results
        return self._validity[TRACER]

    def _check_for_metadata(self) -> bool:
        if self._can_trace is None:
            qpdf_present = self._check_for_qpdf()
            self._can_trace = qpdf_present
            self._can_meta_extract = qpdf_present
        return self._can_meta_extract

    def validate_metadata(self) -> Dict[str, Any]:
        if META not in self._validity:
            _ = self.validate_tracer()
        return self._validity[META]

    @staticmethod
    def get_name():
        return 'QPDF'

    def _get_num_pages(self):
        try:
            sp = subprocess.Popen(shlex.split('%s --show-npages %s' % (self._cmd_path, self._doc_path)),
                                  stderr=subprocess.PIPE, stdout=subprocess.PIPE)
            (stdout, _) = sp.communicate(timeout=self._timeout or 600)
            self._num_pages = int(stdout.decode(self._decoder).strip())
        except:
            self._num_pages = 0

    def _run_json(self):
        # with tempfile.TemporaryDirectory(dir=self._temp_folders_dir) as temp_path:
        # out_path = os.path.join(temp_path, 'out.pdf')
        try:
            sp = subprocess.Popen(shlex.split('%s --json %s' % (self._cmd_path, self._doc_path)),
                                  stderr=subprocess.PIPE, stdout=subprocess.PIPE, shell=False)
            (stdout, err) = sp.communicate(timeout=self._timeout or 600)
            self._exit_code = sp.returncode
            err = fix_splits(err.decode(self._decoder, errors='ignore'))
            stdout = stdout.decode(self._decoder, errors='ignore')
            error_arr = [message for message in err.split('\n') if len(message) > 0]
        except TimeoutExpired:
            sp.kill()
            (stdout, err) = sp.communicate()
            err = fix_splits(err.decode(self._decoder, errors='ignore'))
            stdout = stdout.decode(self._decoder, errors='ignore')
            error_arr = [message for message in err.split('\n') if len(message) > 0]
            self._exit_code = 0
            stdout = stdout
            error_arr.insert(0, 'Error: Subprocess timed out: %i' % (self._timeout or 600))
        except Exception as e:
            self._exit_code = 0
            sp.kill()
            (stdout, err) = sp.communicate()
            err = fix_splits(err.decode(self._decoder, errors='ignore'))
            stdout = stdout.decode(self._decoder, errors='ignore')
            error_arr = str(e).split('\n')
            error_arr.extend([message for message in err.split('\n') if len(message) > 0])
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
        scrubbed_messages = [self._clean_message(err) for err in self._messages if err != 'qpdf: operation succeeded with warnings']
        error_dict: Dict[str, int] = dict()
        for (index, error) in enumerate(scrubbed_messages):
            if error.startswith('warning: ... repeated '):
                repeated = re.sub(r'[^\d]', '', error)
                error_dict[self._messages[index - 1]] = error_dict.get(error, 0) + int(repeated)
            else:
                error_dict[error] = error_dict.get(error, 0) + 1
        self._cleaned = error_dict
