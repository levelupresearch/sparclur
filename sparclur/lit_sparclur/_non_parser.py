from sparclur._parser import Parser
import locale

class NonParser(Parser):

    def __init__(self, doc, **kwargs):
        super().__init__(doc=doc, **kwargs)

    @staticmethod
    def get_name():
        return "Non-Parser"

    def get_raw(self):
        if isinstance(self._doc, bytes):
            return self._doc
        else:
            with open(self._doc, mode='rb') as doc:
                raw_doc = ''.join(line.decode(locale.getpreferredencoding(), errors='ignore') for line in doc)
            return raw_doc
