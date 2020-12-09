import abc
from sparclur._parser import Parser
from sparclur.utils.tools import shingler, jac_dist, lev_dist


class TextExtractor(Parser, metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def __init__(self, doc_path, *args, **kwargs):
        super().__init__(doc_path=doc_path, *args, **kwargs)
        self._full_text_extracted = False
        self._text = dict()

    @abc.abstractmethod
    def _check_for_text_extraction(self) -> bool:
        """
        Perform a check for the necessary tools to extract the text.
        Returns
        -------
        bool
        """
        pass

    @abc.abstractmethod
    def _extract_page(self, page: int):
        """
        Extract the specified page's texts and caches the result.

        Parameters
        ----------
        page : int
            Zero-indexed page to extract text from

        Returns
        -------

        """
        pass

    @abc.abstractmethod
    def _extract_doc(self):
        """
        Extracts text from the entire document and caches the result.

        Returns
        -------

        """
        pass

    def clear_text(self):
        """Clear any text that has already been extracted for the document"""
        self._text = dict()
        self._full_text_extracted = False

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
        assert self._check_for_text_extraction(), "%s not found" % self.get_name()
        if page is not None:
            if page not in self._text:
                self._extract_page(page)
            result = self._text[page]
        else:
            if not self._full_text_extracted:
                self._extract_doc()
            result = self._text
        return result

    def compare_text(self, other: 'TextExtractor', page=None, dist='jac', shingle_size=4):
        def _jaccard(s1, s2):
            return jac_dist(shingler(s1, shingle_size=shingle_size), shingler(s2, shingle_size=shingle_size))
        s1 = self.get_text(page=page)
        s2 = other.get_text(page=page)
        switcher = {
            'jac': _jaccard,
            'lev': lev_dist
        }
        func = switcher.get(dist, lambda x: 'Distance metric not found. Please select \'jac\' or \'lev\'')
        if page is not None:
            metric = func(s1, s2)
        else:
            pages = {*s1.keys()}.union({*s2.keys()})
            metrics = [func(s1.get(key, ''), s2.get(key, '')) for key in pages]
            metric = sum(metrics) / len(metrics)
        return metric
