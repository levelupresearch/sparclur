import abc
import copy

import mmh3

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


class FontExtractor(Parser, metaclass=abc.ABCMeta):
    """
        Abstract class for wrapping up parsers that extract font information from PDFs.
    """

    def __init__(self, doc, temp_folders_dir, skip_check, timeout, *args, **kwargs):
        super().__init__(doc=doc,
                         temp_folders_dir=temp_folders_dir,
                         skip_check=skip_check,
                         timeout=timeout,
                         *args,
                         **kwargs)
        self._non_embedded_fonts: bool = None
        self._fonts: List[Dict[str, Any]] = None

    @property
    def non_embedded_fonts(self):
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
        if self._fonts is None:
            _ = self._get_fonts()
        return self._fonts

    @fonts.deleter
    def fonts(self):
        self._fonts = None

    @abc.abstractmethod
    def _get_fonts(self):
        pass

    @abc.abstractmethod
    def validate_fonts(self):
        pass

    @property
    def validity(self):
        if FONT not in self._validity:
            _ = self.validate_fonts()
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

