from typing import List

from sparclur.parsers._parser import Parser
from sparclur.utils.tools import fix_splits

import os
import subprocess
import tempfile


class PDFToCairo(Parser):

    def __init__(self):
        self.name = 'PDFToCairo'

    def get_name(self):
        return self.name

    def get_messages(self, path, temp_folders_dir=None):

        with tempfile.TemporaryDirectory(dir=temp_folders_dir) as temp_path:
            out_path = os.path.join(temp_path, 'out.pdf')
            sp = subprocess.Popen('pdftocairo -ps %s %s' % (path, out_path), executable='/bin/bash',
                                  stderr=subprocess.PIPE, stdout=subprocess.PIPE, shell=True)
            (stdout, err) = sp.communicate()
        err = fix_splits(err.decode("utf-8"))
        error_arr = [message for message in err.split('\n') if len(message) > 0]
        error_arr: List[str] = ['No warnings'] if len(error_arr) == 0 else error_arr
        return error_arr
