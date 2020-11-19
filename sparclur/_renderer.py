import abc

from PIL import Image
from skimage.metrics import structural_similarity
import numpy as np
from sparclur._parser import Parser
from sparclur._ssim_result import SSIM


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


class Renderer(Parser, metaclass=abc.ABCMeta):
    """
    Abstract class for PDF renderers.
    """
    @abc.abstractmethod
    def get_caching(self):
        """
        Returns the caching setting for the renderer.

        If caching is set to true, the collection of all rendered PIL's is retained in the object. Otherwise,
        the renders will be regenerated every time the get_renders method is called.
        Returns
        -------
        bool
        """
        pass

    @abc.abstractmethod
    def set_caching(self, caching: bool):
        """
        Set the caching parameter.

        If caching is set to true, the collection of all rendered PIL's is retained in the object. Otherwise,
        the renders will be regenerated every time the get_renders method is called.

        Parameters
        ----------
        caching : bool
        """
        pass

    @abc.abstractmethod
    def clear_cache(self):
        """
        Clears any PIL's that have been retained in the renderer object.
        """
        pass

    @abc.abstractmethod
    def set_dpi(self, new_dpi):
        """
        Set dots per inch for the renders
        Parameters
        ----------
        new_dpi : int
        """
        pass

    @abc.abstractmethod
    def get_dpi(self):
        """
        Return dots per inch
        Returns
        -------
        int
        """
        pass

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

    @abc.abstractmethod
    def get_renders(self, page: int):
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
        pass

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
            result[k] = _single_page_compare(left.get(k, None), right.get(k, None), full)
        return result if page is None else result[page]
