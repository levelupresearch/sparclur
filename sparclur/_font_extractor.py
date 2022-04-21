import abc
import copy

import mmh3

from sparclur._metaclass import Meta
from sparclur._parser import Parser, FONT
from typing import Dict, Any, List

from sparclur.utils import stringify_dict

SYSTEM_FONTS = ["Courier",
                            "Courier-Bold",
                            "Courier-Oblique",
                            "Courier-BoldOblique",
                            "Helvetica",
                            "Helvetica-Bold",
                            "Helvetica-Oblique",
                            "Helvetica-BoldOblique",
                            "Times-Roman",
                            "Times-Bold",
                            "Times-Italic",
                            "Times-BoldItalic",
                            "Symbol",
                            "ZapfDingbats"]


class FontExtractor(Parser, metaclass=Meta):
    """
    Abstract class for wrapping up parsers that extract font information from PDFs.
    """

    def __init__(self, doc, temp_folders_dir, skip_check, timeout, hash_exclude, *args, **kwargs):
        super().__init__(doc=doc,
                         temp_folders_dir=temp_folders_dir,
                         skip_check=skip_check,
                         timeout=timeout,
                         hash_exclude=hash_exclude,
                         *args,
                         **kwargs)
        self._non_embedded_fonts: bool = None
        self._fonts: List[Dict[str, Any]] = None
        font_apis = {'can_extract_font': '(Property) Boolean for whether or not font extraction is present',
                     'non_embedded_fonts': '(Property) Returns true if the document is missing non-system fonts',
                     'fonts': '(Property) Returns the font information for the PDF',
                     'validate_fonts': '(Property) Determines the PDF validity for font info extraction'}
        self._api.update(font_apis)
        self._can_extract_font: bool = None

    @property
    def can_extract_font(self):
        if self._can_extract_font is None:
            self._can_extract_font = self._check_for_font_extraction()
        return self._can_extract_font

    @can_extract_font.deleter
    def can_extract_font(self):
        self._can_extract_font = None

    @abc.abstractmethod
    def _check_for_font_extraction(self) -> bool:
        pass

    @property
    def non_embedded_fonts(self):
        """
        Determine whether or not there are non-embedded fonts in the PDF. Returns True if there are missing fonts.

        Returns
        -------
        bool
        """
        if self._non_embedded_fonts is not None:
            return self._non_embedded_fonts
        else:
            if self._fonts is None:
                _ = self._get_fonts()
            if len(self._fonts) == 0:
                self._non_embedded_fonts = False
            else:
                filter_fonts = []
                for font_info in self._fonts:
                    is_system = font_info['name'].split('+')[-1] in SYSTEM_FONTS
                    #is_type1 = font_info['type'] == 'Type 1'
                    # if not is_system and not is_type1:
                    if not is_system:
                        filter_fonts.append(font_info)
                if len(filter_fonts) == 0:
                    result = False
                else:
                    embs = [d['emb'] for d in filter_fonts]
                    result = not min(embs)
                self._non_embedded_fonts = result
            return self._non_embedded_fonts

    @non_embedded_fonts.deleter
    def non_embedded_fonts(self):
        self._non_embedded_fonts = None

    @property
    def fonts(self):
        """
        Extracts the detected fonts from the PDF file.

        Returns
            Dict[str, Any]
        -------
        """
        if self._fonts is None:
            _ = self._get_fonts()
        return self._fonts

    @fonts.deleter
    def fonts(self):
        self._fonts = None

    @abc.abstractmethod
    def _get_fonts(self):
        pass

    @property
    @abc.abstractmethod
    def validate_fonts(self):
        """
        Checks whether or not fonts can be successfully extracted from a document. Any issues or errors will result in a
        'Rejected' classification.

        Returns
        -------
        Dict[str, str]
            A dictionary containing a boolean for validity, a classification label for validity, and relevant info for the
            classification
        """
        pass

    @property
    def validity(self):
        if FONT not in self._validity:
            _ = self.validate_fonts
        return super().validity

    @property
    def sparclur_hash(self):
        if FONT not in self._sparclur_hash and FONT not in self._sparclur_hash.excluded:
            try:
                fonts = copy.deepcopy(self.fonts)
                hashes = dict()
                for font in fonts:
                    _ = font.pop('object ID', None)
                    hashes[font['name']] = mmh3.hash128(stringify_dict(font))
            except:
                hashes = dict()
            self._sparclur_hash._add_hash(FONT, hashes)
        return super().sparclur_hash

