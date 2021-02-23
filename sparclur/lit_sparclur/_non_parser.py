from sparclur._parser import Parser
import locale

class NonParser(Parser):

    def __init__(self, doc_path, **kwargs):
        super().__init__(doc_path=doc_path, **kwargs)

    @staticmethod
    def get_name():
        return "Non-Parser"

    def get_raw(self):
        with open(self._doc_path, mode='rb') as doc:
            raw_doc = ''.join(line.decode(locale.getpreferredencoding(), errors='ignore') for line in doc)
        return raw_doc
