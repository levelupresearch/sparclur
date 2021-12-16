import abc

import mmh3

from sparclur._parser import Parser, META
from typing import Dict, Any

from sparclur.utils import stringify_dict

METADATA_SUCCESS = "Metadata successfully extracted"


class MetadataExtractor(Parser, metaclass=abc.ABCMeta):
    """
        Abstract class for wrapping up parsers that allow for extracting PDF metadata.
    """

    @abc.abstractmethod
    def __init__(self, doc, temp_folders_dir, skip_check, timeout, *args, **kwargs):
        super().__init__(doc=doc, temp_folders_dir=temp_folders_dir, skip_check=skip_check, timeout=timeout, *args, **kwargs)
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

    @property
    def validity(self):
        if META not in self._validity:
            _ = self.validate_metadata()
        return super().validity

    @property
    def sparclur_hash(self):
        if META not in self._sparclur_hash and META not in self._sparclur_hash.excluded:
            try:
                meta = self.metadata
                hashes = dict()
                for obj in meta.keys():
                    hashes[obj] = mmh3.hash128(stringify_dict(meta[obj]))
            except:
                hashes = dict()
            self._sparclur_hash._add_hash(META, hashes)
        return super().sparclur_hash