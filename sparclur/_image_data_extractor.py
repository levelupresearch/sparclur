import abc
from sparclur._parser import Parser
from typing import Dict, Any, List


class ImageDataExtractor(Parser, metaclass=abc.ABCMeta):
    """
        Abstract class for wrapping up parsers that extract image information from PDFs. Image content is not extracted.
    """

    def __init__(self, doc_path, skip_check, timeout, *args, **kwargs):
        super().__init__(doc_path=doc_path,
                         skip_check=skip_check,
                         timeout=timeout,
                         *args,
                         **kwargs)
        self._contains_jpeg: bool = None
        self._contains_images: bool = None
        self._images: List[Dict[str, Any]] = None

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

    @abc.abstractmethod
    def validate_image_data(self):
        pass