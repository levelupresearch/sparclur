import abc

from sparclur._metaclass import Meta
from sparclur._parser import Parser, IMAGE
from typing import Dict, Any, List


class ImageDataExtractor(Parser, metaclass=Meta):
    """
    Abstract class for wrapping up parsers that extract image information from PDFs. Image content is not extracted.
    """

    def __init__(self, doc, temp_folders_dir, skip_check, timeout, hash_exclude, *args, **kwargs):
        super().__init__(doc=doc,
                         temp_folders_dir=temp_folders_dir,
                         skip_check=skip_check,
                         timeout=timeout,
                         hash_exclude=hash_exclude,
                         *args,
                         **kwargs)
        image_apis = {'can_extract_image_data': """(Property) Boolean for whether or not image data extraction 
                                                capability is present""",
                      'contains_jpeg': '(Property) Returns True if jpeg data was extracted from the PDF',
                      'contains_images': '(Property) Returns True if image data was extracted from the PDF',
                      'images': '(Property) Returns the image data that was extracted from the PDF',
                      'validate_image_data': '(Property) Determines the PDF validity for image data extraction'
                      }
        self._api.update(image_apis)
        self._contains_jpeg: bool = None
        self._contains_images: bool = None
        self._images: List[Dict[str, Any]] = None
        self._can_extract_image_data: bool = None

    @property
    def can_extract_image_data(self):
        if self._can_extract_image_data is None:
            self._can_extract_image_data = self._check_for_image_data_extraction()
        return self._can_extract_image_data

    @can_extract_image_data.deleter
    def can_extract_image_data(self):
        self._can_extract_image_data = None

    @abc.abstractmethod
    def _check_for_image_data_extraction(self) -> bool:
        pass

    @property
    def contains_jpeg(self):
        if self._contains_jpeg is not None:
            return self._contains_jpeg
        else:
            if self._images is None:
                _ = self._get_image_data()
            if len(self._images) == 0:
                self._contains_jpeg = False
            else:
                encs = [d['enc'] for d in self._images]
                self._contains_jpeg = 'jpeg' in encs
            return self._contains_jpeg

    @property
    def contains_images(self):
        if self._contains_images is not None:
            return self._contains_images
        else:
            if self._images is None:
                _ = self._get_image_data()
            if len(self._images) == 0:
                self._contains_images = False
            else:
                types = [d['type'] for d in self._images]
                self._contains_images = 'image' in types
            return self._contains_images

    @property
    def images(self):
        if self._images is None:
            _ = self._get_image_data()
        return self._images

    @images.deleter
    def images(self):
        self._images = None
        self._contains_jpeg = None
        self._contains_images = None

    @abc.abstractmethod
    def _get_image_data(self):
        pass

    @property
    @abc.abstractmethod
    def validate_image_data(self):
        """
        Checks whether or not image data can be successfully extracted from a document. Any issues or errors will result
         in a 'Rejected' classification.

        Returns
        -------
        Dict[str, str]
            A dictionary containing a boolean for validity, a classification label for validity, and relevant info for
            the classification
        """
        pass

    @property
    def validity(self):
        if IMAGE not in self._validity:
            self._validity[IMAGE] = self.validate_image_data
        return super().validity

    @property
    def sparclur_hash(self):
        return super().sparclur_hash
