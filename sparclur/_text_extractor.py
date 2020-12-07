import abc
from sparclur._parser import Parser
from sparclur.utils.tools import shingler, jac_dist, lev_dist


class TextExtractor(Parser, metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def __init__(self):
        self._overall_text = None
        self._full_text_extracted = False
        self._page_texts = dict()

    @abc.abstractmethod
    def _extract_page(self, page: int):
        """
        Extract the specified page's texts.

        Parameters
        ----------
        page : int
            Zero-indexed page to extract text from

        Returns
        -------
        str
        """
        pass

    @abc.abstractmethod
    def _extract_doc(self):
        """
        Extracts text from the entire document.

        Returns
        -------
        Dict[int, str]
        """
        pass

    @abc.abstractmethod
    def clear_cache(self):
        """Clear any text that has already been extracted for the document"""
        pass

    def get_text(self, page: int = None):
        """
        Return the extracted text from the document. If page is None, return all text from the document. Otherwise
        returns the text for the specified text only.

        Parameters
        ----------
        page: int or None
            zero-indexed page to extract text from. Returns the whole document if None
        Returns
        -------
        str or Dict[int, str]
        """

        if page is not None:
            if page in self._page_texts:
                result = self._page_texts[page]
            else:
                result = self._extract_page(page=page)
        else:
            if self._full_text_extracted:
                result = self._overall_text
            else:
                result = self._extract_doc()
        return result

    def compare_text(self, other: 'TextExtractor', dist='jac', shingle_size=4):
        def _jaccard(s1, s2):
            return jac_dist(shingler(s1, shingle_size=shingle_size), shingler(s2, shingle_size=shingle_size))
        s1 = self.get_text()
        s2 = other.get_text()
        switcher = {
            'jac': _jaccard,
            'lev': lev_dist
        }
        func = switcher.get(dist, lambda x: 'Distance metric not found. Please select \'jac\' or \'lev\'')
        metric = func(s1, s2)
        return metric
