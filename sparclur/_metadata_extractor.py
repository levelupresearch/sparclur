import abc

import mmh3

from sparclur._metaclass import Meta
from sparclur._parser import Parser, META
from typing import Dict, Any

from sparclur.utils import stringify_dict

METADATA_SUCCESS = "Metadata successfully extracted"


class MetadataExtractor(Parser, metaclass=Meta):
    """
    Abstract class for wrapping up parsers that allow for extracting PDF metadata.
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
        metadata_apis = {'can_extract_metadata':
                             '(Property) Boolean for whether or not metadata extraction capability is present',
                         'validate_metadata': '(Property) Determines the PDF validity for metadata extraction',
                         'metadata': '(Property) Returns a dictionary of the parsed PDF objects and their key/values',
                         'metadata_result':
                             '(Property) Returns a message relating to the success or failure of metadata extraction'}
        self._api.update(metadata_apis)
        self._metadata: Dict[str, Any] = None
        self._metadata_result: str = None
        self._can_meta_extract: bool = None

    @property
    def can_extract_metadata(self):
        if self._can_meta_extract is None:
            self._can_meta_extract = self._check_for_metadata()
        return self._can_meta_extract

    @can_extract_metadata.deleter
    def can_extract_metadata(self):
        self._can_meta_extract = None

    @abc.abstractmethod
    def _check_for_metadata(self) -> bool:
        """
        Performs a check for the presence of the metadata extractor.

        Returns
        -------
        bool
        """
        pass


    @property
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
        assert self._check_for_metadata() or self._skip_check, "%s not found" % self.get_name()

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
            _ = self.validate_metadata
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