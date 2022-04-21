import locale
import platform
import shlex

from sparclur._parser import VALID, VALID_WARNINGS, REJECTED, REJECTED_AMBIG, TIMED_OUT, TRACER
from sparclur._tracer import Tracer
from sparclur.utils import hash_file
from sparclur.utils._config import _get_config_param, _load_config

from typing import List, Dict, Any, Union
import tempfile
import subprocess
from subprocess import TimeoutExpired
import os


def _binary_path():
    system = platform.system()
    if system == 'Windows':
        bits, _ = platform.architecture()
        if bits == '32bit':
            return 'x86'
        else:
            return 'x64'
    else:
        return system.lower()


class Arlington(Tracer):
    """Wrapper for the Arlington DOM TestGrammar (https://github.com/pdf-association/arlington-pdf-model)"""

    def __init__(self, doc: Union[str, bytes],
                 arlington_path: Union[str, None] = None,
                 version: Union[float, str] = None,
                 skip_check: Union[bool, None] = None,
                 hash_exclude: Union[str, List[str], None] = None,
                 temp_folders_dir: Union[str, None] = None,
                 timeout: Union[int, None] = None
                 ):
        """
        Parameters
        ----------
        arlington_path : str
            The top-level path to the local Arlington repo. Default is None, but only to facilitate putting this
            parameter in to the sparclur.yaml for convenience. If this is not set in the config or at instantiation,
            the class will fail to instantiate.
        version : float or str
            The PDF version to use for the DOM check. Default is 1.7, unless otherwise specified in the sparclur config.
        """
        config = _load_config()
        arlington_path = _get_config_param(Arlington, config, 'arlington_path', arlington_path, None)
        version = _get_config_param(Arlington, config, 'version', version, 1.7)
        skip_check = _get_config_param(Arlington, config, 'skip_check', skip_check, False)
        hash_exclude = _get_config_param(Arlington, config, 'hash_exclude', hash_exclude, None)
        temp_folders_dir = _get_config_param(Arlington, config, 'temp_folders_dir', temp_folders_dir, None)
        timeout = _get_config_param(Arlington, config, 'timeout', timeout, None)

        super().__init__(doc=doc,
                         temp_folders_dir=temp_folders_dir,
                         skip_check=skip_check,
                         hash_exclude=hash_exclude,
                         timeout=timeout,
                         foo='bar')
        assert arlington_path is not None, "Arlington path was not defined"
        self._arlington_path = arlington_path
        self._present_versions = os.listdir(os.path.join(arlington_path, 'tsv'))
        if str(version) not in self._present_versions:
            print('Unsupported version supplied; setting to 1.7')
            self._version = '1.7'
        else:
            self._version = str(version)
        self._tsv_path = os.path.join(arlington_path, 'tsv', self._version)
        sys_path = _binary_path()
        self._test_grammar_path = os.path.join(arlington_path, 'TestGrammar', 'bin', sys_path, 'TestGrammar')
        self._decoder = locale.getpreferredencoding()
        self._trace_exit_code = None

    @staticmethod
    def get_name():
        return "Arlington"

    @property
    def arlington_path(self):
        return self._arlington_path

    @arlington_path.setter
    def arlington_path(self, bp):
        self._arlington_path = bp

    @property
    def version(self):
        return self._version

    @version.setter
    def version(self, v: float or str):
        self._version = v

    def _check_for_tracer(self) -> bool:
        if self._can_trace is None:
            try:
                subprocess.check_output(shlex.split('%s -h' % self._test_grammar_path), shell=False)
                tg_present = True
            except Exception as e:
                tg_present = False
            self._can_trace = tg_present
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
            elif self._trace_exit_code > 0:
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

    def _get_num_pages(self):
        print('Warning: This method is not supported')
        self._num_pages = -1

    def _parse_document(self):

        with tempfile.TemporaryDirectory(dir=self._temp_folders_dir) as temp_path:
            if isinstance(self._doc, bytes):
                file_hash = hash_file(self._doc)
                doc_path = os.path.join(temp_path, file_hash)
                with open(doc_path, 'wb') as doc_out:
                    doc_out.write(self._doc)
            else:
                doc_path = self._doc
            try:
                sp = subprocess.Popen(
                    shlex.split('%s --tsvdir %s --pdf %s' % (self._test_grammar_path, self._tsv_path, doc_path)),
                    stderr=subprocess.PIPE, stdout=subprocess.PIPE, shell=False)
                (stdout, err) = sp.communicate(timeout=self._timeout or 600)
                stdout = stdout.decode(self._decoder, errors='ignore')
                self._trace_exit_code = sp.returncode
                messages = []
                m = None
                for line in stdout.split('\n'):
                    if line.startswith('Warning: ') or line.startswith('Error: '):
                        if m is not None:
                            messages.append(m)
                        m = line
                    elif m is not None:
                        if line != 'END':
                            m = m + '\n' + line
                if m is not None:
                    messages.append(m)
                if len(messages) == 0:
                    messages = ['No warnings']
                self._file_timed_out[TRACER] = False
            except TimeoutExpired:
                sp.kill()
                self._trace_exit_code = 0
                self._file_timed_out[TRACER] = True
                messages = ['Error: Subprocess timed out: %i' % (self._timeout or 600)]
            except Exception as e:
                sp.kill()
                messages = str(e).split('\n')
                messages.extend([message for message in err.split('\n') if len(message) > 0])
                self._trace_exit_code = 0
                self._file_timed_out[TRACER] = False
        self._messages = messages

    def _scrub_messages(self):

        if self._messages is None:
            self._parse_document()
        if self._messages == ['No warnings']:
            self._cleaned = {'No warnings': 1}
        else:
            message_dict = dict()
            for message in self._messages:
                message_dict[message.split('\n')[0]] = message_dict.get(message, 0) + 1
            self._cleaned = message_dict

    def _clean_message(self, err):
        pass
