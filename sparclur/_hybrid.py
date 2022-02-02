import abc

from sparclur._metaclass import Meta
from sparclur._renderer import Renderer
from sparclur._text_extractor import TextExtractor


class Hybrid(TextExtractor, Renderer, metaclass=Meta):
    """
        Abstract class to handle parsers that both render and have text extraction.
    """

    @abc.abstractmethod
    def __init__(self, doc,
                 temp_folders_dir,
                 skip_check,
                 timeout,
                 hash_exclude,
                 dpi,
                 cache_renders,
                 ocr,
                 *args,
                 **kwargs):
        """
        Parameters
        ----------
        ocr : bool
            Flag for whether or not text extraction calls should be made using OCR or the built-in parser feature.
        """
        super().__init__(doc=doc,
                         skip_check=skip_check,
                         dpi=dpi,
                         cache_renders=cache_renders,
                         timeout=timeout,
                         temp_folders_dir=temp_folders_dir,
                         hash_exclude=hash_exclude,
                         *args,
                         **kwargs)
        hybrid_apis = {'compare_ocr': "Compares the OCR of the document with the text extraction"}
        self._api.update(hybrid_apis)
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
        """
        Method that compares the OCR result to the built-in text extraction.

        Parameters
        ----------
        page : int
            Indicates which page the comparison should be run over. If 'None', all pages are compared.
        shingle_size : int, default=4
            The size of the token shingles used in the Jaccard similarity comparison between the OCR and the text
            extraction.

        Returns
        -------
        float
            The Jaccard similarity between the OCR and the text extraction (for the specified shingle size).
        """
        other = self.__class__(doc=self._doc,
                               dpi=self._dpi,
                               cache_renders=self._caching,
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

    @property
    def validity(self):
        return super().validity

    @property
    def sparclur_hash(self):
        return super().sparclur_hash
