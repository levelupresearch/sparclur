import locale

from pdfminer.high_level import extract_text

from sparclur._text_extractor import TextExtractor


class PDFMiner(TextExtractor):
    """PDFMiner Text Extraction"""

    def __init__(self, doc_path):

        self._doc_path = doc_path

    @staticmethod
    def get_name():
        return 'PDFMiner'

    def get_doc_path(self):
        return self._doc_path

    def get_text(self, page=None):
        page_numbers = None if page is None else [page]
        decoder = locale.getpreferredencoding()
        text = extract_text(self._doc_path, page_numbers=page_numbers, codec=decoder)
        return text