import abc

import sys
from typing import Dict
from PIL.PngImagePlugin import PngImageFile
from PIL import Image
from func_timeout import func_timeout, FunctionTimedOut
from skimage.metrics import structural_similarity
import numpy as np
from sparclur._text_extractor import TextExtractor
from sparclur._ssim_result import SSIM
import re
from pytesseract import image_to_string

_SUCCESSFUL_RENDER_MESSAGE = 'Successfully Rendered'


def _ocr_text(pil: PngImageFile):
    return re.sub(r'[\x0c]', '', image_to_string(pil))

def _single_page_compare(pil1, pil2, full):
    """
    Function to compute the structural similarity of two pngs.

    Parameters
    ----------
    pil1 : PngImageFile
    pil2 : PngImageFile
    full : bool
        Flag that indicates the difference of the comparison should be returned

    Returns
    -------
    SSIM
    """
    np1 = np.array(pil1.convert('L')) if pil1 is not None else None
    np2 = np.array(pil2.convert('L')) if pil2 is not None else None

    width = min(np1.shape[0] if np1 is not None else 0, np2.shape[0] if np2 is not None else 0)
    height = min(np1.shape[1] if np1 is not None else 0, np2.shape[1] if np2 is not None else 0)

    try:
        if full:
            (ssim, diff) = structural_similarity(np1[0:width, 0:height], np2[0:width, 0:height], full=full)
            diff = Image.fromarray(np.uint8(diff * 255), 'L').convert('RGB')
        else:
            ssim = structural_similarity(np1[0:width, 0:height], np2[0:width, 0:height], full=full)
            diff = None
        result = 'Compared Successfully'

    except Exception as e:
        ssim = -1.0
        diff = Image.new("RGB", (width, height), (255, 255, 255)) if width * height != 0 \
            else Image.new("RGB", (1, 1), (255, 255, 255))
        result = str(e)
    return SSIM(ssim=ssim, result=result, diff=diff)


class Renderer(TextExtractor, metaclass=abc.ABCMeta):
    """
    Abstract class for PDF renderers.
    """

    @abc.abstractmethod
    def __init__(self, doc_path, dpi, cache_renders, verbose, timeout, *args, **kwargs):
        super().__init__(doc_path=doc_path, *args, **kwargs)
        self._full_doc_rendered = False
        self._renders: Dict[int, PngImageFile] = dict()
        self._dpi = dpi
        self._caching = cache_renders
        self._verbose = verbose
        self._logs = dict()
        self._timeout = timeout

    @abc.abstractmethod
    def _check_for_renderer(self) -> bool:
        """
        Does a check to ensure that the current system can perform the given render.
        Returns
        -------
        bool
        """
        pass

    def _check_for_text_extraction(self) -> bool:
        return 'pytesseract' in sys.modules.keys()

    @property
    def timeout(self):
        return self._timeout

    @timeout.setter
    def timeout(self, to: int):
        self._timeout = to

    @timeout.deleter
    def timeout(self):
        self._timeout = None

    @property
    def verbose(self):
        """Return verbose setting"""
        return self._verbose

    @verbose.setter
    def verbose(self, v: bool):
        """
        Set the verbose setting for the renderer
        Parameters
        ----------
        v : bool
        """
        self._verbose = v

    @property
    def logs(self):
        """
        View any gathered logs.
        Returns
        -------
        Dict[int, Dict[str, Any]]
        """
        return self._logs

    @property
    def caching(self):
        """
        Returns the caching setting for the renderer.

        If caching is set to true, the collection of all rendered PIL's is retained in the object. Otherwise,
        the renders will be regenerated every time the get_renders method is called.
        Returns
        -------
        bool
        """
        return self._caching

    @caching.setter
    def caching(self, caching: bool):
        """
        Set the caching parameter.

        If caching is set to true, the collection of all rendered PIL's is retained in the object. Otherwise,
        the renders will be regenerated every time the get_renders method is called.

        Parameters
        ----------
        caching : bool
        """
        self._caching = caching

    def clear_renders(self):
        """
        Clears any PIL's that have been retained in the renderer object.
        """
        self._full_doc_rendered = False
        self._renders: Dict[int, PngImageFile] = dict()

    @property
    def dpi(self):
        """
        Return dots per inch
        Returns
        -------
        int
        """
        return self._dpi

    @dpi.setter
    def dpi(self, new_dpi):
        """
        Set dots per inch for the renders
        Parameters
        ----------
        new_dpi : int
        """
        self._dpi = new_dpi

    @abc.abstractmethod
    def _render_page(self, page: int):
        """
        Renders the specified page of the document.

        Parameters
        ----------
        page : int
            Zero-indexed page to be rendered.

        Returns
        -------
        PngImageFile
        """
        pass

    @abc.abstractmethod
    def _render_doc(self):
        """
        Renders the entire document.

        Returns
        -------
        Dict[int, PngImageFile]
        """
        pass

    def get_renders(self, page: int = None):
        """
        Return the renders of the object document. If page is None, return the entire rendered document. Otherwise
        returns the specified page only.

        Parameters
        ----------
        page: int or None
            zero-indexed page to be rendered. Returns the whole document if None
        Returns
        -------
        PngImageFile or Dict[int, PngImageFile]
        """
        assert self._check_for_renderer(), "%s not found" % self.get_name()
        if self._renders:
            if page is not None:
                if page in self._renders:
                    result = self._renders[page]
                else:
                    result = self._render_page(page=page)
            else:
                if self._full_doc_rendered:
                    result = self._renders
                else:
                    result = self._render_doc()
        else:
            if self._full_doc_rendered:
                if page is not None:
                    result = None
                else:
                    result = dict()
            elif page is not None:
                result = self._render_page(page=page)
            else:
                result = self._render_doc()
        return result

    def compare(self, other: 'Renderer', page=None, full=False):
        """
        Performs a structural similarity comparison between two renders
        Parameters
        ----------
        other
        page
        full

        Returns
        -------
        Dict[int, SSIM] or SSIM
        """
        if page is not None:
            left = {page: self.get_renders(page=page)}
            right = {page: other.get_renders(page=page)}
        else:
            left = self.get_renders()
            right = other.get_renders()

        keyset = {*left}.union({*right})
        result = dict()
        for k in keyset:
            try:
                if self._timeout is None:
                    result[k] = _single_page_compare(left.get(k, None), right.get(k, None), full)
                else:
                    result[k] = func_timeout(
                        self._timeout,
                        _single_page_compare,
                        args=(left.get(k, None), right.get(k, None), full)
                    )
            except FunctionTimedOut:
                result[k] = SSIM(-1.0, 'Comparison Timed Out')
            except Exception as e:
                result[k] = SSIM(-1.0, e.message)
        return result if page is None else result[page]

    def _extract_doc(self):
        for (page, pil) in self.get_renders().items():
            self._text[page] = _ocr_text(pil)
        self._full_text_extracted = True

    def _extract_page(self, page: int):
        self._text[page] = _ocr_text(self.get_renders(page=page))
