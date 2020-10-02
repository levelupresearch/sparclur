from sparclur.parsers._parser import Parser
from sparclur.utils.tools import fix_splits

import tempfile
import subprocess
import os


class CustomParser(Parser):

    def __init__(self, name, message_method=None, cli_call=None, tool_path=None, temp_folders_dir=None):
        self.name = name
        self.message_method = message_method
        self.cli_call = cli_call
        self.tool_path = tool_path
        self.temp_folders_dir = temp_folders_dir
        assert message_method is not None and cli_call is not None

    def get_name(self):
        return self.name

    def get_messages(self, path):
        if self.message_method:

        sub_call = parser_call
        with tempfile.TemporaryDirectory(dir=temp_folders_dir) as temp_path:
            out_path = os.path.join(temp_path, 'out.pdf')
            sp = subprocess.Popen('mutool clean -s %s %s' % (path, out_path), executable='/bin/bash',
                                  stderr=subprocess.PIPE, stdout=subprocess.PIPE, shell=True)
            (stdout, err) = sp.communicate()
        err = fix_splits(err.decode("utf-8"))
        error_arr = [clean_mupdf(message) for message in err.split('\n') if len(message) > 0]
        error_arr = ['No warnings'] if len(error_arr) == 0 else error_arr
        error_dict = dict()
        for (index, error) in enumerate(error_arr):
            if error.startswith('warning: ... repeated '):
                repeated = re.sub(r'[^\d]', '', error)
                error_dict['mutool::' + error_arr[index - 1]] = error_dict.get('mutool::' + error, 0) + int(repeated)
            else:
                error_dict['mutool::' + error] = error_dict.get('mutool::' + error, 0) + 1
        return error_dict
