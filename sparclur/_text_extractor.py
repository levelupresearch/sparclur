import abc
from typing import Dict, Any
from sparclur._text_compare import TextCompare


class TextExtractor(TextCompare, metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def __init__(self, doc_path, skip_check, *args, **kwargs):
        super().__init__(doc_path=doc_path, skip_check=skip_check, *args, **kwargs)

    @abc.abstractmethod
    def validate_text(self) -> Dict[str, Any]:
        """
        Performs a validity check for this text extractor.

        Returns
        -------
        Dict[str, Any]
        """
        pass
