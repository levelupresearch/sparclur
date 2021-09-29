import abc
from sparclur._parser import Parser
from typing import Dict, Any

METADATA_SUCCESS = "Metadata successfully extracted"


class MetadataExtractor(Parser, metaclass=abc.ABCMeta):
    """
        Abstract class for wrapping up parsers that allow for extracting PDF metadata.
    """

    @abc.abstractmethod
    def __init__(self, doc_path, skip_check, *args, **kwargs):
        super().__init__(doc_path=doc_path, skip_check=skip_check, *args, **kwargs)
        self._metadata: Dict[str, Any] = None
        self._metadata_result: str = None
        self._can_meta_extract: bool = None

    @abc.abstractmethod
    def _check_for_metadata(self) -> bool:
        """
        Performs a check for the presence of the metadata extractor.

        Returns
        -------
        bool
        """
        pass

    @abc.abstractmethod
    def validate_metadata(self) -> Dict[str, Any]:
        """
        Performs a validity check for this metadata extractor.

        Returns
        -------
        Dict[str, Any]
        """
        pass

    @property
    def metadata(self) -> Dict[str, Any]:
        """
        Return the dictionary of metadata.

        Returns
        -------
        Dict[str, Any]
        """
        assert self._check_for_metadata(), "%s not found" % self.get_name()

        if self._metadata is None:
            self._extract_metadata()

        return self._metadata

    @metadata.deleter
    def metadata(self):
        self._metadata = None

    @property
    def metadata_result(self):
        if self._metadata is None:
            _ = self.metadata
        return self._metadata_result

    @abc.abstractmethod
    def _extract_metadata(self):
        """
        Extract the metadata from the document.
        """
        pass