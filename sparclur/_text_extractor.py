import abc
from typing import Dict, Any

import mmh3

from sparclur._metaclass import Meta
from sparclur.utils import shingler

from sparclur._text_compare import TextCompare
from sparclur._parser import TEXT


class TextExtractor(TextCompare, metaclass=Meta):
    """
    Abstract class for parsers with text extraction capabilities.
    """
    @abc.abstractmethod
    def __init__(self, doc, temp_folders_dir, skip_check, timeout, hash_exclude, *args, **kwargs):
        super().__init__(doc=doc,
                         temp_folders_dir=temp_folders_dir,
                         skip_check=skip_check,
                         timeout=timeout,
                         hash_exclude=hash_exclude,
                         *args,
                         **kwargs)
        text_apis = {'validate_text': '(Property) Determines the PDF validity for the text extraction process'}
        self._api.update(text_apis)

    @property
    @abc.abstractmethod
    def validate_text(self) -> Dict[str, Any]:
        """
        Performs a validity check for this text extractor.

        Returns
        -------
        Dict[str, Any]
        """
        pass

    @property
    def validity(self):
        if TEXT not in self._validity:
            self._validity[TEXT] = self.validate_text
        return super().validity

    @property
    def sparclur_hash(self):
        if TEXT not in self._sparclur_hash and TEXT not in self._sparclur_hash.excluded:
            try:
                all_text = self.get_tokens()
                hashes = dict()
                for page, tokens in all_text.items():
                    shingled_tokens = shingler(tokens, 4)
                    shingled_hashes = [mmh3.hash128(token_set) for token_set in shingled_tokens]
                    shingled_hashes.sort()
                    hashes[page] = set(shingled_hashes[0:200])
            except:
                hashes = dict()
            self._sparclur_hash._add_hash(TEXT, hashes)
        return super().sparclur_hash
