import abc
import re

from sparclur._metaclass import Meta
from sparclur._parser import Parser
from sparclur.utils._tools import shingler, jac_dist
import sys
from spacy.lang.en import English


class TextCompare(Parser, metaclass=Meta):
    """
    An abstract class that encapsulates parsers with Text Extraction capabilities and also Renderers when used in
    conjunction with OCR.
    """

    @abc.abstractmethod
    def __init__(self, doc,
                 temp_folders_dir,
                 skip_check,
                 timeout,
                 hash_exclude,
                 *args,
                 **kwargs):
        super().__init__(doc=doc,
                         temp_folders_dir=temp_folders_dir,
                         skip_check=skip_check,
                         timeout=timeout,
                         hash_exclude=hash_exclude,
                         *args,
                         **kwargs)
        text_apis = {'can_extract_text': '(Property) Boolean for whether or not text extraction is present',
                     'get_text': 'Return a dictionary of pages and their extracted texts',
                     'clear_text': 'Clear the cache of text extraction',
                     'get_tokens': 'Return a dictionary of the parsed text tokens',
                     'compare_text': 'Return the Jaccard similarity of the shingled tokens between two text extractors'}
        self._api.update(text_apis)
        self._full_text_extracted = False
        self._document_tokenized = False
        self._text = dict()
        self._tokens = dict()
        self._can_extract: bool = None

    @property
    def can_extract_text(self):
        if self._can_extract is None:
            self._can_extract = self._check_for_text_extraction()
        return self._can_extract

    @can_extract_text.deleter
    def can_extract_text(self):
        self._can_extract = None

    @abc.abstractmethod
    def _check_for_text_extraction(self) -> bool:
        """
        Perform a check for the necessary tools to extract the text.
        Returns
        -------
        bool
        """
        pass

    @property
    def validity(self):
        return super().validity

    @property
    def sparclur_hash(self):
        return super().sparclur_hash

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
        self._tokens = dict()
        self._full_text_extracted = False
        self._document_tokenized = False

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
        assert self._skip_check or self._check_for_text_extraction(), "%s not found" % self.get_name()
        if page is not None:
            if page not in self._text:
                self._extract_page(page)
            result = self._text.get(page, '')
        else:
            if not self._full_text_extracted:
                self._extract_doc()
            result = self._text
        return result

    def get_tokens(self, page: int=None):
        """
        Return the parsed text tokens from the document. If page is None, return all token sets from the document.
        Otherwise returns the text for the specified text only.

        Parameters
        ----------
        page: int or None
            zero-indexed page to extract text from. Returns the whole document if None
        Returns
        -------
        str or Dict[int, str]
        """
        assert self._skip_check or 'spacy' in sys.modules.keys(), "spaCy not found for tokenization"
        nlp = English()
        tokenizer = nlp.tokenizer

        text = self.get_text(page=page)
        if page is not None:
            if page not in self._tokens:
                if text == '':
                    tokenized = ['']
                else:
                    tokenized = [str(token) for token in tokenizer(text)]
                    tokenized = [t for t in [re.sub('\s+', '', token) for token in tokenized] if t != '']
                self._tokens[page] = tokenized
            tokens = self._tokens[page]
        else:
            if not self._document_tokenized:
                for (page, text) in text.items():
                    tokenized = [str(token) for token in tokenizer(text)]
                    remove_white_space_tokens = [t for t in [re.sub('\s+', '', token) for token in tokenized] if
                                                 t != '']
                    self._tokens[page] = remove_white_space_tokens
                self._document_tokenized = True
            tokens = self._tokens
        return tokens

    def compare_text(self, other: 'TextCompare', page=None, shingle_size=4):
        """
        Shingles the parsed tokens into the specified n-grams and then compares the two token sets and calculates the
        Jaccard similarity.

        Parameters
        ----------
        other : TextCompare
            The Text Extraction, Renderer, or Hybrid parser to comapre to this parser
        page : int
            The 0-indexed page to compare. If `None`, Use the tokens from the entire document
        shingle_size : int, default=4
            The size of the shingled n-grams

        Returns
        -------
        float
            The Jaccard Similarity score
        """
        s1 = self.get_tokens(page=page)
        s2 = other.get_tokens(page=page)
        if page is not None:
            metric = 1.0 - jac_dist(shingler(s1, shingle_size=shingle_size), shingler(s2, shingle_size=shingle_size))
        else:
            all_s1 = set()
            for (_, tokens) in s1.items():
                all_s1.update(shingler(tokens, shingle_size=shingle_size))
            all_s2 = set()
            for (_, tokens) in s2.items():
                all_s2.update(shingler(tokens, shingle_size=shingle_size))
            # pages = {*s1.keys()}.union({*s2.keys()})
            # metrics = [_jaccard(s1.get(key, ''), s2.get(key, '')) for key in pages]
            # metric = sum(metrics) / len(metrics)
            metric = 1.0 - jac_dist(all_s1, all_s2)
        return metric
