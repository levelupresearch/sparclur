import shutil
from typing import List, Dict, Any, Union
import os
import re
import locale
import shlex
import tempfile
import subprocess
from subprocess import DEVNULL, TimeoutExpired

import yaml

from sparclur._tracer import Tracer
from sparclur._parser import VALID, VALID_WARNINGS, REJECTED, REJECTED_AMBIG, TRACER, TIMED_OUT
from sparclur.utils import hash_file
from sparclur.utils._config import _get_config_param, _load_config


class PDFCPU(Tracer):
    """Wrapper for PDFCPU (https://pdfcpu.io/)"""

    def __init__(self, doc: Union[str, bytes],
                 skip_check: Union[bool, None] = None,
                 hash_exclude: Union[str, List[str], None] = None,
                 binary_path: Union[str, None] = None,
                 temp_folders_dir: Union[str, None] = None,
                 timeout: Union[int, None] = None
                 ):
        """
        Parameters
        ----------
        binary_path : str
            If the mutool binary is not in the system PATH, add the path to the binary here. Can also be used to trace
            specific versions of the binary.
        """
        config = _load_config()
        skip_check = _get_config_param(PDFCPU, config, 'skip_check', skip_check, False)
        hash_exclude = _get_config_param(PDFCPU, config, 'hash_exclude', hash_exclude, None)
        binary_path = _get_config_param(PDFCPU, config, 'binary_path', binary_path, None)
        temp_folders_dir = _get_config_param(PDFCPU, config, 'temp_folders_dir', temp_folders_dir, None)
        timeout = _get_config_param(PDFCPU, config, 'timeout', timeout, None)

        super().__init__(doc=doc,
                         temp_folders_dir=temp_folders_dir,
                         skip_check=skip_check,
                         hash_exclude=hash_exclude,
                         timeout=timeout)

        self._pdfcpu_path = 'pdfcpu' if binary_path is None else os.path.join(binary_path, 'pdfcpu')
        self._trace_exit_code = None
        self._decoder = locale.getpreferredencoding()

    def _check_for_tracer(self) -> bool:
        if self._can_trace is None:
            try:
                subprocess.check_output(shlex.split(self._pdfcpu_path + " version"), shell=False)
                pc_present = True
            except Exception as e:
                pc_present = False
            self._can_trace = pc_present
        return self._can_trace

    @property
    def validate_tracer(self) -> Dict[str, Any]:
        if TRACER not in self._validity:
            validity_results = dict()
            if self._cleaned is None:
                self._scrub_messages()
            observed_messages = list(self._cleaned.keys())
            if self._file_timed_out[TRACER]:
                validity_results['valid'] = False
                validity_results['status'] = TIMED_OUT
                validity_results['info'] = 'Timed Out: %i' % self._timeout
            elif self._trace_exit_code > 1:
                validity_results['valid'] = False
                validity_results['status'] = REJECTED
                validity_results['info'] = 'Exit code: %i' % self._trace_exit_code
            elif observed_messages == ['No warnings']:
                validity_results['valid'] = True
                validity_results['status'] = VALID
            elif len([message for message in observed_messages if 'Error' in message]) > 0:
                validity_results['valid'] = False
                validity_results['status'] = REJECTED
                validity_results['info'] = 'Errors returned'
            elif len([message for message in observed_messages if 'Warning' in message]) == len(observed_messages):
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
        return 'PDFCPU'

    def _get_num_pages(self):
        if not self._skip_check:
            assert self._check_for_tracer(), "%s not found" % self.get_name()
        with tempfile.TemporaryDirectory(dir=self._temp_folders_dir) as temp_path:
            if isinstance(self._doc, bytes):
                file_hash = hash_file(self._doc)
                doc_path = os.path.join(temp_path, file_hash)
                with open(doc_path+'.pdf', 'wb') as doc_out:
                    doc_out.write(self._doc)
            # elif not self._doc.endswith('.pdf'):
            #     doc_path = os.path.join(temp_path, 'infile.pdf')
            #     shutil.copy2(self._doc, doc_path)
            else:
                doc_path = self._doc
            try:
                sp = subprocess.Popen([self._pdfcpu_path, 'info', doc_path], stdout=subprocess.PIPE, stderr=DEVNULL,
                                      shell=False)
                (stdout, _) = sp.communicate()
                stdout = stdout.decode(self._decoder)
                self._num_pages = [int(line.split(':')[1].strip())
                                   for line in stdout.split('\n') if 'Page count:' in line][0]
            except:
                self._num_pages = 0

    def _parse_document(self):

        with tempfile.TemporaryDirectory(dir=self._temp_folders_dir) as temp_path:
            if isinstance(self._doc, bytes):
                file_hash = hash_file(self._doc)
                doc_path = os.path.join(temp_path, file_hash + '.pdf')
                with open(doc_path, 'wb') as doc_out:
                    doc_out.write(self._doc)
            elif not self._doc.endswith('.pdf'):
                doc_path = os.path.join(temp_path, 'infile.pdf')
                shutil.copy2(self._doc, doc_path)
            else:
                doc_path = self._doc
            try:
                strict_cmd = '%s validate -m strict %s' % (self._pdfcpu_path, doc_path)
                relaxed_cmd = '%s validate -m relaxed %s' % (self._pdfcpu_path, doc_path)
                # if self._verbose:
                #     cmd = cmd + ' -v'
                strict_sp = subprocess.Popen(
                    shlex.split(strict_cmd),
                    stderr=subprocess.PIPE, stdout=DEVNULL, shell=False)
                relaxed_sp = subprocess.Popen(
                    shlex.split(relaxed_cmd),
                    stderr=subprocess.PIPE, stdout=DEVNULL, shell=False)
                (_, strict_err) = strict_sp.communicate(timeout=self._timeout or 600)
                strict_err = strict_err.decode(self._decoder, errors='ignore').strip()
                strict_err = re.sub(r" \(try -mode=relaxed\)", '', strict_err)
                (_, relaxed_err) = relaxed_sp.communicate(timeout=self._timeout or 600)
                relaxed_err = relaxed_err.decode(self._decoder, errors='ignore').strip()
                error_arr = [relaxed_err, strict_err] if relaxed_err not in strict_err else [relaxed_err]
                # error_arr = [message for message in err.split('\n') if len(message) > 0]
                self._trace_exit_code = max(strict_sp.returncode, relaxed_sp.returncode)
                self._file_timed_out[TRACER] = False
            except TimeoutExpired:
                strict_sp.kill()
                relaxed_sp.kill()
                (_, strict_err) = strict_sp.communicate()
                (_, relaxed_err) = relaxed_sp.communicate()
                strict_err = strict_err.decode(self._decoder, errors='ignore').strip()
                strict_err = re.sub(r" \(try -mode=relaxed\)", '', strict_err)
                relaxed_err = relaxed_err.decode(self._decoder, errors='ignore').strip()
                error_arr = [relaxed_err, strict_err] if relaxed_err not in strict_err else [relaxed_err]
                error_arr.insert(0, 'Error: Subprocess timed out: %i' % (self._timeout or 600))
                self._trace_exit_code = 0
                self._file_timed_out[TRACER] = True
            except Exception as e:
                strict_sp.kill()
                relaxed_sp.kill()
                (_, strict_err) = strict_sp.communicate()
                (_, relaxed_err) = relaxed_sp.communicate()
                strict_err = strict_err.decode(self._decoder, errors='ignore').strip()
                strict_err = re.sub(r" \(try -mode=relaxed\)", '', strict_err)
                relaxed_err = relaxed_err.decode(self._decoder, errors='ignore').strip()
                error_arr = str(e).split('\n')
                pdfcpu_errs = [relaxed_err, strict_err] if relaxed_err not in strict_err else [relaxed_err]
                error_arr.extend(pdfcpu_errs)
                self._trace_exit_code = 0
                self._file_timed_out[TRACER] = False
        error_arr = [err for err in error_arr if len(err) > 0]
        self._messages = ['No warnings'] if len(error_arr) == 0 else error_arr

    def _scrub_messages(self):
        if self._messages is None:
            self._parse_document()
        scrubbed_messages = [self._clean_message(err) for err in self._messages]
        error_dict: Dict[str, int] = dict()
        for error in scrubbed_messages:
            error_dict[error] = error_dict.get(error, 0) + 1
        self._cleaned = error_dict

    def _clean_message(self, err):
        message = err.strip()
        cleaned = 'runtime error' if message.startswith('runtime:') else message
        cleaned = re.sub(r"\<\<", "[", cleaned)
        cleaned = re.sub(r"\>\>", "]", cleaned)
        cleaned = re.sub(r"\[[^]]+\]", "<<x>>", cleaned)
        cleaned = re.sub(r"\(obj\#:\d+\)", "(obj#:<x>)", cleaned)
        cleaned = re.sub(r"\(obj\#\d+\)", "(obj#<x>)", cleaned)
        cleaned = re.sub(r"line = \<[^>]+\>", "line = <x>", cleaned)
        cleaned = re.sub(r"parsing \"[^\"]+\":", "parsing <x>:", cleaned)
        cleaned = re.sub(r"problem dereferencing object \d+", "problem dereferencing object <x>", cleaned)
        cleaned = re.sub(r"problem dereferencing stream \d+", "problem dereferencing stream <x>", cleaned)
        cleaned = re.sub(r"unknown PDF Header Version: .+", "unknown PDF Header Version: <x>", cleaned)
        cleaned = re.sub(r"\nThis file could be PDF/A compliant but pdfcpu only supports versions <= PDF V1.7", '',
                         cleaned)
        cleaned = re.sub(r"validateDateEntry: .+ invalid date", "validateDateEntry: <x> invalid date", cleaned)
        cleaned = re.sub(r"validateDateObject: .+ invalid date", "validateDateObject: <x> invalid date", cleaned)
        cleaned = re.sub(r"leaf node corrupted .+", "leaf node corrupted", cleaned)
        return cleaned
