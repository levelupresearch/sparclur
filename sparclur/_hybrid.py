import abc

from sparclur._renderer import Renderer
from sparclur._text_extractor import TextExtractor


class Hybrid(TextExtractor, Renderer, metaclass=abc.ABCMeta):
    """
        Abstract class to handle parsers that both render and have text extraction.
    """

    @abc.abstractmethod
    def __init__(self, doc_path, dpi, cache_renders, timeout, ocr, *args, **kwargs):
        super().__init__(doc_path=doc_path,
                         dpi=dpi,
                         cache_renders=cache_renders,
                         timeout=timeout,
                         *args,
                         **kwargs)
        self._ocr: bool = ocr

    @property
    def ocr(self):
        return self._ocr

    @ocr.setter
    def ocr(self, o: bool):
        if self._ocr != o:
            self.clear_text()
            self._can_extract = None
            self._ocr = o

    def compare_ocr(self, page=None, shingle_size=4):
        other = self.__class__(doc_path=self._doc_path,
                               dpi=self._dpi,
                               cache_renders=self._cache_renders,
                               timeout=self._timeout,
                               ocr=not self._ocr)
        metric = self.compare_text(other, page=page, shingle_size=shingle_size)
        return metric

    @abc.abstractmethod
    def _extract_doc(self):
        pass

    @abc.abstractmethod
    def _extract_page(self, page: int):
        pass