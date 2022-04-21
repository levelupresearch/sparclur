import locale
import os
import shlex
import tempfile
from typing import Dict, Any, List

import yaml

from sparclur._metadata_extractor import MetadataExtractor, METADATA_SUCCESS
from sparclur._parser import VALID, VALID_WARNINGS, REJECTED, REJECTED_AMBIG, META, TRACER, TIMED_OUT
from sparclur._tracer import Tracer
from sparclur.utils import fix_splits, hash_file
from sparclur.utils._config import _get_config_param, _load_config

import re
import subprocess
from subprocess import TimeoutExpired
import json


class QPDF(Tracer, MetadataExtractor):
    """QPDF tracer"""
    def __init__(self, doc: str or bytes,
                 temp_folders_dir: str = None,
                 skip_check: bool = None,
                 hash_exclude: str or List[str] = None,
                 binary_path: str = None,
                 timeout: int = None
                 ):
        """
        Parameters
        ----------
        binary_path : str
            If the qpdf binary is not in the system PATH, add the path to the binary here. Can also be used to trace
            specific versions of the binary.
        """

        config = _load_config()
        temp_folders_dir = _get_config_param(QPDF, config, 'temp_folders_dir', temp_folders_dir, None)
        skip_check = _get_config_param(QPDF, config, 'skip_check', skip_check, False)
        hash_exclude = _get_config_param(QPDF, config, 'hash_exclude', hash_exclude, None)
        binary_path = _get_config_param(QPDF, config, 'binary_path', binary_path, None)
        timeout = _get_config_param(QPDF, config, 'timeout', timeout, None)

        super().__init__(doc=doc,
                         temp_folders_dir=temp_folders_dir,
                         skip_check=skip_check,
                         hash_exclude=hash_exclude,
                         timeout=timeout)
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

    @property
    def validate_tracer(self) -> Dict[str, Any]:
        if TRACER not in self._validity:
            validity_results = dict()
            if self._messages is None:
                self._parse_document()
            if self._cleaned is None:
                self._scrub_messages()
            observed_messages = list(self._cleaned.keys())
            valid_with_warning_check = len([message for message in observed_messages if 'WARNING' in message]) == \
                                       len(observed_messages) or \
                                       'qpdf: operation succeeded with warnings' in self._messages
            if self._file_timed_out[TRACER]:
                validity_results['valid'] = False
                validity_results['status'] = TIMED_OUT
                validity_results['info'] = 'Timed Out: %i' % self._timeout
            elif self._exit_code != 0 and self._exit_code != 3:
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
            elif valid_with_warning_check:
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

    @property
    def validate_metadata(self) -> Dict[str, Any]:
        if META not in self._validity:
            _ = self.validate_tracer
        return self._validity[META]

    @staticmethod
    def get_name():
        return 'QPDF'

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
                sp = subprocess.Popen(shlex.split('%s --show-npages %s' % (self._cmd_path, doc_path)),
                                      stderr=subprocess.PIPE, stdout=subprocess.PIPE)
                (stdout, _) = sp.communicate(timeout=self._timeout or 600)
                self._num_pages = int(stdout.decode(self._decoder).strip())
            except:
                self._num_pages = 0

    def _run_json(self):
        # with tempfile.TemporaryDirectory(dir=self._temp_folders_dir) as temp_path:
        # out_path = os.path.join(temp_path, 'out.pdf')
        with tempfile.TemporaryDirectory(dir=self._temp_folders_dir) as temp_path:
            if isinstance(self._doc, bytes):
                file_hash = hash_file(self._doc)
                doc_path = os.path.join(temp_path, file_hash)
                with open(doc_path, 'wb') as doc_out:
                    doc_out.write(self._doc)
            else:
                doc_path = self._doc
            try:
                sp = subprocess.Popen(shlex.split('%s --json %s' % (self._cmd_path, doc_path)),
                                      stderr=subprocess.PIPE, stdout=subprocess.PIPE, shell=False)
                (stdout, err) = sp.communicate(timeout=self._timeout or 600)
                self._exit_code = sp.returncode
                err = fix_splits(err.decode(self._decoder, errors='ignore'))
                stdout = stdout.decode(self._decoder, errors='ignore')
                error_arr = [message for message in err.split('\n') if len(message) > 0]
                self._file_timed_out[TRACER] = False
            except TimeoutExpired:
                sp.kill()
                (stdout, err) = sp.communicate()
                err = fix_splits(err.decode(self._decoder, errors='ignore'))
                stdout = stdout.decode(self._decoder, errors='ignore')
                error_arr = [message for message in err.split('\n') if len(message) > 0]
                self._exit_code = 0
                stdout = stdout
                error_arr.insert(0, 'Error: Subprocess timed out: %i' % (self._timeout or 600))
                self._file_timed_out[TRACER] = True
            except Exception as e:
                self._exit_code = 0
                sp.kill()
                (stdout, err) = sp.communicate()
                err = fix_splits(err.decode(self._decoder, errors='ignore'))
                stdout = stdout.decode(self._decoder, errors='ignore')
                error_arr = str(e).split('\n')
                error_arr.extend([message for message in err.split('\n') if len(message) > 0])
                self._file_timed_out[TRACER] = False
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
        cleaned = re.sub(r'recovered stream length [\d]+', 'recovered stream length <x>', err)
        cleaned = re.sub(r'object\s{0, 1}[\d]+ [\d]*', 'object', cleaned)
        cleaned = re.sub(r" \(obj=[\d]+\)", "", cleaned)
        cleaned = re.sub(r'converting [\d]+ ', "converting bigint ", cleaned)
        cleaned = re.sub(r' /QPDFFake[\d]+', "", cleaned)
        cleaned = re.sub(r'\([^)]*\)\s{0, 1}', "", cleaned)
        cleaned = re.sub(r'dictionary has duplicated key /[^;]*;', 'dictionary has duplicated key <key>;', cleaned)
        cleaned = re.sub(r'expected \d+ \d+ obj', 'expected <obj>', cleaned)
        cleaned = re.sub(r'reported number of objects \(\d+\) is not one plus the highest object number \(\d+\)',
                         'reported number of objects (x) is not one plus the highest object number (y)', cleaned)
        cleaned = re.sub(r'overflow/underflow converting [-]?[\d]+', 'overflow/underflow converting <x>', cleaned)
        cleaned = re.sub(r'expected = [\d]+; actual = [\d]+', 'expected = <x>; actual = <y>', cleaned)
        cleaned = re.sub(r'supposed object stream [\d]+ is not a stream', 'supposed object stream <x> is not a stream',
                         cleaned)
        cleaned = re.sub(r'object, offset [\d]+\)',
                         'object, offset <x>)', cleaned)
        cleaned = re.sub(r'Subprocess timed out: [\d]+', 'Subprocess timed out: <t>', cleaned)
        cleaned = re.sub(r'invalid character \([^)]*\) in hexstring',
                         'invalid character (<c>) in hexstring', cleaned)
        cleaned = re.sub(r'json key "[^"]+" is supposed to be an array',
                         'json key "<key>" is supposed to be an array', cleaned)
        cleaned = re.sub(r'object [\d+]/[\d+] has unexpected xref entry type',
                         'object <obj>/<gen> has unexpected xref entry type', cleaned)
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
