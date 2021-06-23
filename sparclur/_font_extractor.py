import abc
from sparclur._parser import Parser
from typing import Dict, Any, List

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

    def __init__(self, doc_path, skip_check, *args, **kwargs):
        super().__init__(doc_path=doc_path,
                         skip_check=skip_check,
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
                    is_type1 = font_info['type'] == 'Type 1'
                    if not is_system and not is_type1:
                        filter_fonts.append(font_info)
                embs = [d['emb'] for d in filter_fonts]
                result = True
                for emb in embs:
                    result = emb and result
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
