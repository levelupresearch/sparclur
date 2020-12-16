import locale

import sys

from pdfminer.high_level import extract_text
from pdfminer.layout import LAParams

from sparclur._text_extractor import TextExtractor


class PDFMiner(TextExtractor):
    """PDFMiner Text Extraction"""

    def __init__(self, doc_path: str,
                 page_delimiter: str = '\x0c',
                 detect_vertical: bool = False,
                 all_texts: bool = False):
        super().__init__(doc_path=doc_path)
        self._page_delimiter = page_delimiter
        self._detect_vertical = detect_vertical
        self._all_texts = all_texts
        self._laparams = LAParams(detect_vertical=self._detect_vertical, all_texts=self._all_texts)

    def _check_for_text_extraction(self) -> bool:
        return "pdfminer.six" in sys.modules.keys()

    @staticmethod
    def get_name():
        return 'PDFMiner'

    @property
    def page_delimiter(self):
        return self._page_delimiter

    @property
    def detect_vertical(self):
        return self._detect_vertical

    @detect_vertical.setter
    def detect_vertical(self, vert):
        self.clear_cache()
        self._detect_vertical = vert

    @property
    def all_texts(self):
        return self._all_texts

    @all_texts.setter
    def all_texts(self, at):
        self.clear_cache()
        self._all_texts = at

    def _extract_doc(self):
        text = self._pdfminer_text()
        for (page, text) in enumerate(text.split(self._page_delimiter)[0:-1]):
            self._text[page] = text
        self._full_text_extracted = True

    def _extract_page(self, page: int):
        text = self._pdfminer_text(page=page)
        self._text[page] = text

    def _pdfminer_text(self, page=None):
        page_numbers = None if page is None else [page]
        decoder = locale.getpreferredencoding()
        text = extract_text(self._doc_path, page_numbers=page_numbers, codec=decoder, laparams=self._laparams)
        return text