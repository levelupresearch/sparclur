import abc
import re
from typing import Dict, Any
from sparclur._parser import Parser
from sparclur.utils._tools import shingler, jac_dist, lev_dist
import sys
from spacy.lang.en import English


class TextCompare(Parser, metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def __init__(self, doc_path, skip_check, *args, **kwargs):
        super().__init__(doc_path=doc_path, skip_check=skip_check, *args, **kwargs)
        self._full_text_extracted = False
        self._document_tokenized = False
        self._text = dict()
        self._tokens = dict()
        self._can_extract: bool = None

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

        assert self._skip_check or 'spacy' in sys.modules.keys(), "spaCy not found for tokenization"
        nlp = English()
        tokenizer = nlp.Defaults.create_tokenizer(nlp)

        text = self.get_text(page=page)
        if page is not None:
            if page not in self._tokens:
                if text == '':
                    tokenized = ['']
                else:
                    tokenized = [str(token) for token in tokenizer(text)]
                    remove_white_space_tokens = [t for t in [re.sub('\s+', '', token) for token in tokenized] if t != '']
                self._tokens[page] = remove_white_space_tokens
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
