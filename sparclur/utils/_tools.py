import hashlib
import os
from typing import Iterable

import fitz
import re
import numpy as np
from skimage.metrics import structural_similarity
from inspect import signature
from imagehash import average_hash, phash, dhash, whash
from PIL.PngImagePlugin import PngImageFile
from PIL import Image
from PIL.Image import Image as ImageType
from func_timeout import FunctionTimedOut
from math import log, e, sqrt
import cv2

from sparclur._prc_sim import PRCSim


class InputError(Exception):
    """Exception raised for errors in the input.

    Attributes:
        message -- explanation of the error
    """

    def __init__(self, message):
        self.message = message


_COMPARISON_SUCCESSFUL_MESSAGE = 'Successfully Compared'


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


def _pil_and_array(p1: PngImageFile or np.array_like):
    if isinstance(p1, PngImageFile):
        return p1, np.array(p1)
    else:
        return Image.fromarray(p1), p1


def image_compare(p1: PngImageFile or np.array_like,
                  p2: PngImageFile or np.array_like,
                  full: bool=False) -> PRCSim:
    """
        Function to compute the structural similarity of two pngs.

        Parameters
        ----------
        p1 : PngImageFile or array_like
        p2 : PngImageFile or array_like
        full : bool
            Flag that indicates the difference of the comparison should be returned

        Returns
        -------
        PRCSim
        """
    if p1 is None or p2 is None:
        return PRCSim(dict(), 'Rendering failed', diff=None)

    pil1, array1 = _pil_and_array(p1)
    pil2, array2 = _pil_and_array(p2)

    w1, h1 = array1.shape[0:2]
    w2, h2 = array2.shape[0:2]

    similarities = dict()
    results = dict()
    try:
        similarities['entropy_sim'] = entropy_sim(pil1, pil2)
        # results['entropy_sim'] = _COMPARISON_SUCCESSFUL_MESSAGE
    except Exception as e:
        results['entropy_sim'] = str(e)
    try:
        similarities['whash_sim'] = whash_sim(pil1, pil2)
        # results['whash_sim'] = _COMPARISON_SUCCESSFUL_MESSAGE
    except Exception as e:
        results['whash_sim'] = str(e)
    try:
        similarities['phash_sim'] = phash_sim(pil1, pil2)
        # results['phash_sim'] = _COMPARISON_SUCCESSFUL_MESSAGE
    except Exception as e:
        results['phash_sim'] = str(e)
    try:
        sss, sss_loc = sum_square_sim(array1, array2)
        similarities['sum_square_sim'] = sss
        # results['sum_square_sim'] = _COMPARISON_SUCCESSFUL_MESSAGE
    except Exception as e:
        sss_loc = None
        results['sum_square_sim'] = str(e)
    try:
        ccorr, ccorr_loc = ccorr_sim(array1, array2)
        similarities['ccorr_sim'] = ccorr
        # results['ccorr_sim'] = _COMPARISON_SUCCESSFUL_MESSAGE
    except Exception as e:
        ccorr_loc = None
        results['ccorr_sim'] = str(e)
    try:
        ccoeff, ccoeff_loc = ccoeff_sim(array1, array2)
        similarities['ccoeff_sim'] = ccoeff
    except Exception as e:
        ccoeff_loc = None
        results['ccoeff_sim'] = str(e)
    try:
        similarities['size_sim'] = size_sim(array1, array2)
    except Exception as e:
        results['size_sim'] = str(e)

    if full:
        try:
            if w1 == w2 and h1 == h2:
                array1_gray = cv2.cvtColor(array1, cv2.COLOR_RGB2GRAY)
                array2_gray = cv2.cvtColor(array2, cv2.COLOR_RGB2GRAY)
                ssim, diff = structural_similarity(array1_gray, array2_gray, full=True)
                diff = Image.fromarray(np.uint8(diff * 255), 'L').convert('RGB')
                similarities['ssim'] = ssim
            elif sss_loc is not None or ccorr_loc is not None or ccoeff_loc is not None:
                diffs = []
                # print("before pad_images")
                padded_pil1, padded_pil2 = pad_images(array1, array2)
                # print("after pad_images")
                array1_gray = cv2.cvtColor(padded_pil1, cv2.COLOR_RGB2GRAY)
                array2_gray = cv2.cvtColor(padded_pil2, cv2.COLOR_RGB2GRAY)
                if sss_loc is not None:
                    # print("sss ssim")
                    sss_ssim, sss_diff = _template_ssim(array1_gray, array2_gray, sss_loc)
                    # print("sss ssim complete: %f" % sss_ssim)
                    diffs.append((sss_ssim, sss_diff))
                if ccorr_loc is not None:
                    # print("ccorr ssim")
                    ccorr_ssim, ccorr_diff = _template_ssim(array1_gray, array2_gray, ccorr_loc)
                    # print("ccorr ssim complete: %f" % ccorr_ssim)
                    diffs.append((ccorr_ssim, ccorr_diff))
                if ccoeff_loc is not None:
                    # print("ccoeff ssim")
                    ccoeff_ssim, ccoeff_diff = _template_ssim(array1_gray, array2_gray, ccoeff_loc)
                    # print("ccoeff ssim complete: %f" % ccoeff_ssim)
                    diffs.append((ccoeff_ssim, ccoeff_diff))
                # print(len(diffs))
                diffs.sort(reverse=True, key=lambda x: x[0])
                ssim, diff = diffs[0]
                diff = Image.fromarray(np.uint8(diff * 255), 'L').convert('RGB')
                similarities['ssim'] = ssim
            else:
                diff = None
        except FunctionTimedOut:
            diff = None
            results['diff'] = "Diff timed out"
        except Exception as e:
            diff = None
            results['diff'] = str(e)
    else:
        diff = None

    if len(results) == 0:
        result = _COMPARISON_SUCCESSFUL_MESSAGE
    else:
        result = ', '.join(['%s: %s' % (key, val) for (key, val) in results.items()])

    return PRCSim(similarity_scores=similarities, result=result, diff=diff)


def _get_contours(min_region, diff: PngImageFile):
    diff = np.array(diff)
    diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    retval, thresh = cv2.threshold(diff, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    contours = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = contours[0] if len(contours) == 2 else contours[1]
    filtered_contours = [contour for contour in contours if cv2.contourArea(contour) >= min_region]
    return filtered_contours


def image_highlight(p1: PngImageFile or np.array_like,
                    p2: PngImageFile or np.array_like,
                    min_region: int = 40,
                    prc: PRCSim = None,
                    verbose: bool = True) -> (PngImageFile, PngImageFile) or PngImageFile:

    _, array1 = _pil_and_array(p1)
    _, array2 = _pil_and_array(p2)


    if prc is None:
        prc = image_compare(p1, p2, True)
    elif prc.diff is None:
        prc = image_compare(p1, p2, True)
    try:
        contours = _get_contours(min_region, prc.diff)
        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            cv2.rectangle(array1, (x, y), (x+w, y+h), (36, 255, 12), 2)
            cv2.rectangle(array2, (x, y), (x+w, y+h), (36, 255, 12), 2)
        return (Image.fromarray(array1), Image.fromarray(array2))

    except Exception as e:
        if verbose:
            print(str(e))
        return (None, None)





def pil_to_hex_array(pil):
    array = np.array(pil, dtype='uint32')
    return (array[:, :, 0] << 16) + (array[:, :, 1] << 8) + array[:, :, 2]


def create_file_list(files, recurse=False, base_path=None):
    fitz.TOOLS.mupdf_display_errors(False);
    try:
        if os.path.isfile(files):
            with open(files) as fp:
                files = ''.join(line for line in fp)
                files = files.split('\n')
    except:
        pass
    if isinstance(files, list):
        if base_path is not None:
            files = [os.path.join(*base_path.split(os.path.sep), *file.split(os.path.sep)) for file in files]
        else:
            files = files
    elif os.path.isdir(files):
        if recurse:
            files = scrape_pdfs(files)
        else:
            files = [os.path.join(files, file) for file in os.listdir(files)]
    else:
        raise InputError("""files must be a list of files with a base_path, a txt file of paths, or a directory 
            containing pdfs.""")
    return files


def gen_flatten(iterables):
    flattened = (elem for iterable in iterables for elem in iterable)
    return list(flattened)


def shingler(s, shingle_size):
    try:
        _ = iter(s)
        is_iterable = True
    except TypeError as e:
        is_iterable = False
    assert is_iterable, "Object must be iterable to be shingled."
    if shingle_size >= len(s):
        return set(s)
    return set([', '.join(gram for gram in s[i:i+shingle_size]) for i in range(len(s) - shingle_size + 1)])


def jac_dist(set1, set2):
    intersect = len(set1.intersection(set2))
    size1 = len(set1)
    size2 = len(set2)
    union = size1 + size2 - intersect
    d = 1 - intersect / union if union > 0 else 0
    return d


def lev_dist(s1, s2):
    s1_len = len(s1)
    s2_len = len(s2)
    if s1_len == 0 or s2_len == 0:
        return max(s1_len, s2_len)
    if s1_len > s2_len:
        s1, s2 = s2, s1
    distances = range(len(s1) + 1)
    for index2, char2 in enumerate(s2):
        new_distances = [index2+1]
        for index1, char1 in enumerate(s1):
            if char1 == char2:
                new_distances.append(distances[index1])
            else:
                new_distances.append(1 + min((distances[index1],
                                             distances[index1+1],
                                             new_distances[-1])))
        distances = new_distances
    return distances[-1]


def hash_file(file):
    assert isinstance(file, bytes) or os.path.isfile(file), "Please provide bytes array or file path"
    sha256_hash = hashlib.sha256()
    if isinstance(file, bytes):
        for i in range(0, len(file), 4096):
            byte_block = file[i:i+4096]
            sha256_hash.update(byte_block)
    else:
        with open(file, "rb") as f:
            # Read and update hash string value in blocks of 4K
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def if_dir_not_exists(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)


def scrape_pdfs(base_dir):
    pdfs = []
    for f in os.listdir(base_dir):
        sub_path = os.path.join(base_dir, f)
        if os.path.isfile(sub_path):
            try:
                pdf = fitz.open(sub_path)
                pdf.close()
                pdfs.append(sub_path)
            except:
                pass
        elif os.path.isdir(sub_path):
            sub_files = scrape_pdfs(sub_path)
            pdfs = pdfs + sub_files
    return pdfs


def get_num_pages(doc_path, verbose=False):
    try:
        pdf = fitz.open(doc_path)
        num_pages: int = len(pdf)
        pdf.close()
    except Exception as e:
        num_pages: int = 0
        if verbose:
            print(e)
    return num_pages


def fix_splits(message):
    message = re.sub(r'[^\n]warning:', '\nwarning:', message)
    message = re.sub(r'[^\n]error:', '\nerror:', message)
    return message


def is_pdf(file):
    try:
        pdf = fitz.open(file)
        pdf.close()
        _is_pdf = True
    except Exception as e:
        _is_pdf = False
    return _is_pdf


def ahash_sim(pil1, pil2, hash_size=128):
    hash1 = average_hash(pil1, hash_size=hash_size)
    hash2 = average_hash(pil2, hash_size=hash_size)
    diff = hash1 - hash2
    normalized = diff / (hash_size * hash_size)
    return 1.0 - normalized


def dhash_sim(pil1, pil2, hash_size=128):
    hash1 = dhash(pil1, hash_size=hash_size)
    hash2 = dhash(pil2, hash_size=hash_size)
    diff = hash1 - hash2
    normalized = diff / (hash_size * hash_size)
    return 1.0 - normalized


def phash_sim(pil1, pil2, hash_size=128):
    hash1 = phash(pil1, hash_size=hash_size)
    hash2 = phash(pil2, hash_size=hash_size)
    diff = hash1 - hash2
    normalized = diff / (hash_size * hash_size)
    return 1.0 - normalized


def whash_sim(pil1, pil2, hash_size=128):
    hash1 = whash(pil1, hash_size=hash_size)
    hash2 = whash(pil2, hash_size=hash_size)
    diff = hash1 - hash2
    normalized = diff / (hash_size * hash_size)
    return 1.0 - normalized


def entropy(a):
    if isinstance(a, PngImageFile) or isinstance(a, ImageType):
        a = pil_to_hex_array(a)
    n = a.size

    if n <= 1:
        return 0
    _, counts = np.unique(a, return_counts=True)
    probs = counts / n

    n_classes = np.count_nonzero(probs)

    if n_classes <= 1:
        return 0

    ent = 0.

    for p in probs:
        ent -= p * log(p, e)

    return ent


def entropy_sim(a, b):
    a_ent = entropy(a)
    b_ent = entropy(b)

    ent_min = min(a_ent, b_ent)
    ent_max = max(a_ent, b_ent)

    sim = ent_min / ent_max if ent_max > 0 else 1.0

    return sim


def pad_images(pil1, pil2):
    if isinstance(pil1, PngImageFile) or isinstance(pil1, ImageType):
        pil1 = np.array(pil1)
    if isinstance(pil2, PngImageFile) or isinstance(pil2, ImageType):
        pil2 = np.array(pil2)
    h1, w1 = pil1.shape[0:2]
    h2, w2 = pil2.shape[0:2]
    delta_w = w1 - w2
    delta_h = h1 - h2
    #If the product of the deltas is greater than or equal to zero, then it's either the case that the dimensions are
    #the same, exactly one of the dimensions is the same, or one of the images is smaller in both width and height. In
    #these 3 cases no padding is needed to calculate the windowed similarity metrics between the two images. So we only
    #need to explore the space where the product is less than 0. The remaining cases is that one image is taller and
    #thinner than the other and padding will be necessary to calculate the similarity.
    if delta_w * delta_h < 0:
        if w1 > w2:
            #This means that h1 < h2
            padding = ((0, h2 - h1), (0, 0), (0, 0)) if len(pil1.shape) == 3 else ((0, h2 - h1), (0, 0))
            pil1 = np.pad(pil1, padding, 'constant', constant_values=255)
        else:
            #Final case w1 < w2 and h1 > h2
            padding = ( (0, 0), (0, w2 - w1), (0, 0)) if len(pil1.shape) == 3 else ((0, 0), (0, w2 - w1))
            pil1 = np.pad(pil1, padding, 'constant', constant_values=255)
    new_h1, new_w1 = pil1.shape[0:2]
    new_h2, new_w2 = pil2.shape[0:2]
    return (pil1, pil2) if new_w1 >= new_w2 and new_h1 >= new_h2 else (pil2, pil1)


def _invert_pil(pil):
    if isinstance(pil, PngImageFile) or isinstance(pil, ImageType):
        pil = np.array(pil)
    return (pil + 128) % 255


def _template_matching(pil1, pil2, method):
    if isinstance(pil1, PngImageFile) or isinstance(pil1, ImageType):
        pil1 = np.array(pil1)
    if isinstance(pil2, PngImageFile) or isinstance(pil2, ImageType):
        pil2 = np.array(pil2)

    if pil1.sum() == 0:
        pil1 = pil1 + 1
    if pil2.sum() == 0:
        pil2 = pil2 + 1

    pil1, pil2 = pad_images(pil1, pil2)

    res = cv2.matchTemplate(pil1, pil2, method)

    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

    score = 1.0 - min_val if method == cv2.TM_SQDIFF_NORMED else max_val
    position = min_loc if method in [cv2.TM_SQDIFF, cv2.TM_SQDIFF_NORMED] else max_loc
    return score, position


def sum_square_sim(pil1, pil2):
    return _template_matching(pil1, pil2, cv2.TM_SQDIFF_NORMED)


def ccoeff_sim(pil1, pil2):
    return _template_matching(pil1, pil2, cv2.TM_CCOEFF_NORMED)


def ccorr_sim(pil1, pil2):
    return _template_matching(pil1, pil2, cv2.TM_CCORR_NORMED)


def orientation_sim(pil1, pil2):
    if isinstance(pil1, PngImageFile) or isinstance(pil1, ImageType):
        pil1 = np.array(pil1)
    if isinstance(pil2, PngImageFile) or isinstance(pil2, ImageType):
        pil2 = np.array(pil2)

    h1, w1 = pil1.shape[0:2]
    h2, w2 = pil2.shape[0:2]

    num = w1 * w2 + h1 * h2
    denom = sqrt(w1 * w1 + h1 * h1) * sqrt(w2 * w2 + h2 * h2)

    return num / denom if denom > 0 else 0


def size_sim(pil1, pil2):
    if isinstance(pil1, PngImageFile) or isinstance(pil1, ImageType):
        pil1 = np.array(pil1)
    if isinstance(pil2, PngImageFile) or isinstance(pil2, ImageType):
        pil2 = np.array(pil2)
    h1, w1 = pil1.shape[0:2]
    h2, w2 = pil2.shape[0:2]

    width_ratio = min(w1/w2, w2/w1) if w1 * w2 > 0 else 0
    height_ratio = min(h1/h2, h2/h1) if h1 * h2 > 0 else 0

    return min(width_ratio, height_ratio)
