import locale
from typing import List

from sparclur.parsers._parser import Parser
from sparclur.utils.tools import fix_splits
from sparclur.parsers.tracer import ParserMessages

import os
import subprocess
import tempfile


class QPDF(Parser):

    def __init__(self, binary_path=None):
        self.name = 'QPDF'
        self.cmd_path = 'qpdf' if binary_path is None else binary_path
        try:
            subprocess.check_output(self.cmd_path + " --version", shell=True)
            self.qpdf_present = True
        except subprocess.CalledProcessError as e:
            print("QPDF binary not found: ", str(e))
            self.qpdf_present = False

    def get_name(self):
        return self.name

    def get_messages(self, path, temp_folders_dir=None):

        if not self.qpdf_present:
            raise OSError("Unable to find QPDF.")

        with tempfile.TemporaryDirectory(dir=temp_folders_dir) as temp_path:
            out_path = os.path.join(temp_path, 'out.pdf')
            sp = subprocess.Popen('%s --json %s' % (self.cmd_path, path), executable='/bin/bash',
                                  stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, shell=True)
            (stdout, err) = sp.communicate()
        decoder = locale.getpreferredencoding()
        err = fix_splits(err.decode(decoder))
        error_arr = [message for message in err.split('\n') if len(message) > 0]
        error_arr: List[str] = ['No warnings'] if len(error_arr) == 0 else error_arr
        return ParserMessages(self.name, error_arr)
