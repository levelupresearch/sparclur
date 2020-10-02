from sparclur.parsers._renderer import Renderer
from sparclur.utils.normalizer import clean_mupdf
from sparclur.utils.tools import fix_splits
import fitz


class MuPDF(Renderer):

    def __init__(self):
        self.name = 'MuPDF'

    def get_name(self):
        return self.name

    def get_messages(self, path, save_path = None):
        with tempfile.TemporaryDirectory(dir=temp_folders_dir) as temp_path:
            out_path = os.path.join(temp_path, 'out.pdf')
            sp = subprocess.Popen('mutool clean -s %s %s' % (path, out_path), executable='/bin/bash',
                                  stderr=subprocess.PIPE, stdout=subprocess.PIPE, shell=True)
            (stdout, err) = sp.communicate()
        err = fix_splits(err.decode("utf-8"))
        error_arr = [clean_mupdf(message) for message in err.split('\n') if len(message) > 0]
        error_arr = ['No warnings'] if len(error_arr) == 0 else error_arr
        return error_arr