import abc

import sys
from typing import Dict, Any
from PIL.PngImagePlugin import PngImageFile
from PIL import Image
from func_timeout import func_timeout, FunctionTimedOut
from imagehash import dhash
from skimage.metrics import structural_similarity
import numpy as np

from sparclur._prc_sim import PRCSim
from sparclur._text_compare import TextCompare
from sparclur._parser import RENDER, RENDER_HASH_SIZE
import re
from pytesseract import image_to_string
import cv2
from sparclur.utils import entropy_sim, whash_sim, phash_sim, size_sim, sum_square_sim, ccorr_sim, ccoeff_sim, \
    pad_images, image_compare

_SUCCESSFUL_RENDER_MESSAGE = 'Successfully Rendered'
# _COMPARISON_SUCCESSFUL_MESSAGE = 'Successfully Compared'


def _ocr_text(pil: PngImageFile):
    return re.sub(r'[\x0c]', '', image_to_string(pil))

# def _single_page_compare(pil1, pil2, full):
#     """
#     Function to compute the structural similarity of two pngs.
#
#     Parameters
#     ----------
#     pil1 : PngImageFile
#     pil2 : PngImageFile
#     full : bool
#         Flag that indicates the difference of the comparison should be returned
#
#     Returns
#     -------
#     SSIM
#     """
#     np1 = np.array(pil1.convert('L')) if pil1 is not None else None
#     np2 = np.array(pil2.convert('L')) if pil2 is not None else None
#
#     width = min(np1.shape[0] if np1 is not None else 0, np2.shape[0] if np2 is not None else 0)
#     height = min(np1.shape[1] if np1 is not None else 0, np2.shape[1] if np2 is not None else 0)
#
#     try:
#         if full:
#             (ssim, diff) = structural_similarity(np1[0:width, 0:height], np2[0:width, 0:height], full=full)
#             diff = Image.fromarray(np.uint8(diff * 255), 'L').convert('RGB')
#         else:
#             ssim = structural_similarity(np1[0:width, 0:height], np2[0:width, 0:height], full=full)
#             diff = None
#         result = 'Compared Successfully'
#     except FunctionTimedOut:
#         ssim = -1.0
#         diff = Image.new("RGB", (width, height), (255, 255, 255)) if width * height != 0 \
#             else Image.new("RGB", (1, 1), (255, 255, 255))
#         result = "Compare Timed Out"
#     except Exception as e:
#         ssim = -1.0
#         diff = Image.new("RGB", (width, height), (255, 255, 255)) if width * height != 0 \
#             else Image.new("RGB", (1, 1), (255, 255, 255))
#         result = str(e)
#     return SSIM(ssim=ssim, result=result, diff=diff)


# def _single_page_compare(pil1, pil2, full):
#     """
#     Function to compute the structural similarity of two pngs.
#
#     Parameters
#     ----------
#     pil1 : PngImageFile
#     pil2 : PngImageFile
#     full : bool
#         Flag that indicates the difference of the comparison should be returned
#
#     Returns
#     -------
#     PRCSim
#     """
#     if pil1 is None or pil2 is None:
#         return PRCSim(dict(), 'Rendering failed', diff=None)
#
#     array1 = np.array(pil1)
#     array2 = np.array(pil2)
#
#     w1, h1 = array1.shape[0:2]
#     w2, h2 = array2.shape[0:2]
#
#     similarities = dict()
#     results = dict()
#     try:
#         similarities['entropy_sim'] = entropy_sim(pil1, pil2)
#         #results['entropy_sim'] = _COMPARISON_SUCCESSFUL_MESSAGE
#     except Exception as e:
#         results['entropy_sim'] = str(e)
#     try:
#         similarities['whash_sim'] = whash_sim(pil1, pil2)
#         #results['whash_sim'] = _COMPARISON_SUCCESSFUL_MESSAGE
#     except Exception as e:
#         results['whash_sim'] = str(e)
#     try:
#         similarities['phash_sim'] = phash_sim(pil1, pil2)
#         #results['phash_sim'] = _COMPARISON_SUCCESSFUL_MESSAGE
#     except Exception as e:
#         results['phash_sim'] = str(e)
#     try:
#         sss, sss_loc = sum_square_sim(array1, array2)
#         similarities['sum_square_sim'] = sss
#         #results['sum_square_sim'] = _COMPARISON_SUCCESSFUL_MESSAGE
#     except Exception as e:
#         sss_loc = None
#         results['sum_square_sim'] = str(e)
#     try:
#         ccorr, ccorr_loc = ccorr_sim(array1, array2)
#         similarities['ccorr_sim'] = ccorr
#         #results['ccorr_sim'] = _COMPARISON_SUCCESSFUL_MESSAGE
#     except Exception as e:
#         ccorr_loc = None
#         results['ccorr_sim'] = str(e)
#     try:
#         ccoeff, ccoeff_loc = ccoeff_sim(array1, array2)
#         similarities['ccoeff_sim'] = ccoeff
#     except Exception as e:
#         ccoeff_loc = None
#         results['ccoeff_sim'] = str(e)
#     try:
#         similarities['size_sim'] = size_sim(array1, array2)
#     except Exception as e:
#         results['size_sim'] = str(e)
#
#     if full:
#         try:
#             if w1 == w2 and h1 == h2:
#                 array1_gray = cv2.cvtColor(array1, cv2.COLOR_RGB2GRAY)
#                 array2_gray = cv2.cvtColor(array2, cv2.COLOR_RGB2GRAY)
#                 ssim, diff = structural_similarity(array1_gray, array2_gray, full=True)
#                 diff = Image.fromarray(np.uint8(diff * 255), 'L').convert('RGB')
#                 similarities['ssim'] = ssim
#             elif sss_loc is not None or ccorr_loc is not None or ccoeff_loc is not None:
#             # elif sss_loc is not None or ccorr_loc is not None:
#                 diffs = []
#                 # print("before pad_images")
#                 padded_pil1, padded_pil2 = pad_images(array1, array2)
#                 # print("after pad_images")
#                 array1_gray = cv2.cvtColor(padded_pil1, cv2.COLOR_RGB2GRAY)
#                 array2_gray = cv2.cvtColor(padded_pil2, cv2.COLOR_RGB2GRAY)
#                 if sss_loc is not None:
#                     # print("sss ssim")
#                     sss_ssim, sss_diff = _template_ssim(array1_gray, array2_gray, sss_loc)
#                     # print("sss ssim complete: %f" % sss_ssim)
#                     diffs.append((sss_ssim, sss_diff))
#                 if ccorr_loc is not None:
#                     # print("ccorr ssim")
#                     ccorr_ssim, ccorr_diff = _template_ssim(array1_gray, array2_gray, ccorr_loc)
#                     # print("ccorr ssim complete: %f" % ccorr_ssim)
#                     diffs.append((ccorr_ssim, ccorr_diff))
#                 if ccoeff_loc is not None:
#                     # print("ccoeff ssim")
#                     ccoeff_ssim, ccoeff_diff = _template_ssim(array1_gray, array2_gray, ccoeff_loc)
#                     # print("ccoeff ssim complete: %f" % ccoeff_ssim)
#                     diffs.append((ccoeff_ssim, ccoeff_diff))
#                 # print(len(diffs))
#                 diffs.sort(reverse=True, key=lambda x: x[0])
#                 ssim, diff = diffs[0]
#                 diff = Image.fromarray(np.uint8(diff * 255), 'L').convert('RGB')
#                 similarities['ssim'] = ssim
#             else:
#                 diff = None
#         except FunctionTimedOut:
#             diff = None
#             results['diff'] = "Diff timed out"
#         except Exception as e:
#             diff = None
#             results['diff'] = str(e)
#     else:
#         diff = None
#
#     if len(results) == 0:
#         result = _COMPARISON_SUCCESSFUL_MESSAGE
#     else:
#         result = ', '.join(['%s: %s' % (key, val) for (key, val) in results.items()])
#
#     return PRCSim(similarity_scores=similarities, result=result, diff=diff)


def _template_ssim(pil1, pil2, top_left):

    h1, w1 = pil1.shape[0:2]
    h2, w2 = pil2.shape[0:2]
    same_size = h1 == h2 and w1 == w2

    if not same_size:
        height_padding = (top_left[1], h1 - (h2 + top_left[1]))
        width_padding = (top_left[0], w1 - (w2 + top_left[0]))
        padding = (height_padding, width_padding)
        pil2 = np.pad(pil2, padding, 'constant', constant_values=255)
    ssim, diff = structural_similarity(pil1, pil2, full=True)
    return ssim, diff


class Renderer(TextCompare, metaclass=abc.ABCMeta):
    """
    Abstract class for PDF renderers.
    """

    @abc.abstractmethod
    def __init__(self, doc, skip_check, timeout, dpi, cache_renders, *args, **kwargs):
        super().__init__(doc=doc, skip_check=skip_check, timeout=timeout, *args, **kwargs)
        self._full_doc_rendered = False
        self._renders: Dict[int, PngImageFile] = dict()
        self._dpi = dpi
        self._caching = cache_renders
        self._logs = dict()
        self._can_render: bool = None

    @abc.abstractmethod
    def validate_renderer(self) -> Dict[str, Any]:
        """
        Performs a validity check for this tracer.

        Returns
        -------
        Dict[str, Any]
        """
        pass

    @property
    def sparclur_hash(self):
        if RENDER not in self._sparclur_hash and RENDER not in self._sparclur_hash.excluded:
            try:
                renders = self.get_renders()
                hashes = dict()
                for page, pil in renders.items():
                    hashes[page] = dhash(pil, hash_size=RENDER_HASH_SIZE)
            except:
                hashes = dict()
            self._sparclur_hash._add_hash(RENDER, hashes)
        return super().sparclur_hash

    @property
    def validity(self):
        if RENDER not in self._validity:
            _ = self.validate_renderer()
        return super().validity

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
        if self._can_extract is None:
            self._can_extract = 'pytesseract' in sys.modules.keys()
        return self._can_extract


    # @property
    # def verbose(self):
    #     """Return verbose setting"""
    #     return self._verbose
    #
    # @verbose.setter
    # def verbose(self, v: bool):
    #     """
    #     Set the verbose setting for the renderer
    #     Parameters
    #     ----------
    #     v : bool
    #     """
    #     self._verbose = v

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
        assert self._skip_check or self._check_for_renderer(), "%s not found" % self.get_name()
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
        Dict[int, PRCSim] or PRCSim
        """
        if page is not None:
            left = {page: self.get_renders(page=page)}
            right = {page: other.get_renders(page=page)}
        else:
            left = self.get_renders()
            right = other.get_renders()

        keyset = {*left}.union({*right})
        if len(keyset) == 0:
            empty_sim = PRCSim(dict(), 'No comparisons to make', diff=None)
            if page is None:
                return {0: empty_sim}
            else:
                return empty_sim
        result = dict()
        for k in keyset:
            try:
                if self._timeout is None:
                    result[k] = image_compare(left.get(k, None), right.get(k, None), full)
                else:
                    result[k] = func_timeout(
                        self._timeout,
                        image_compare,
                        args=(left.get(k, None), right.get(k, None), full)
                    )
            except FunctionTimedOut:
                result[k] = PRCSim(dict(), 'Comparison Timed Out', diff=None)
            except Exception as e:
                result[k] = PRCSim(dict(), e.message, diff=None)
        return result if page is None else result[page]

    def _extract_doc(self):
        for (page, pil) in self.get_renders().items():
            self._text[page] = _ocr_text(pil)
        self._full_text_extracted = True

    def _extract_page(self, page: int):
        self._text[page] = _ocr_text(self.get_renders(page=page))
