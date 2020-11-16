import locale
from typing import List

from sparclur.parsers._parser import Parser
from sparclur.utils.tools import fix_splits
from sparclur.parsers.tracer import ParserMessages

import os
import subprocess
import tempfile


class PDFToCairo(Parser):

    def __init__(self, binary_path=None):
        self.name = 'PDFToCairo'
        self.cmd_path = 'pdftocairo' if binary_path is None else binary_path
        try:
            subprocess.check_output(self.cmd_path + " -v", shell=True)
            self.pdftocairo_present = True
        except subprocess.CalledProcessError as e:
            print("pdftocairo binary not found: ", str(e))
            self.pdftocairo_present = False

    def get_name(self):
        return self.name

    def get_messages(self, path, temp_folders_dir=None):

        if not self.pdftocairo_present:
            raise OSError("Unable to find pdftocairo.")

        with tempfile.TemporaryDirectory(dir=temp_folders_dir) as temp_path:
            out_path = os.path.join(temp_path, 'out.pdf')
            sp = subprocess.Popen('%s -ps %s %s' % (self.cmd_path, path, out_path), executable='/bin/bash',
                                  stderr=subprocess.PIPE, stdout=subprocess.PIPE, shell=True)
            (stdout, err) = sp.communicate()
        decoder = locale.getpreferredencoding()
        err = fix_splits(err.decode(decoder))
        error_arr = [message for message in err.split('\n') if len(message) > 0]
        error_arr: List[str] = ['No warnings'] if len(error_arr) == 0 else error_arr
        return ParserMessages(self.name, error_arr)
