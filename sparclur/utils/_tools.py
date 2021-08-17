import hashlib
import os
import fitz
import re
import numpy as np
from inspect import signature
from imagehash import average_hash, phash, dhash, whash
from PIL.PngImagePlugin import PngImageFile
from PIL.Image import Image as ImageType
from math import log, e, sqrt
import cv2


class InputError(Exception):
    """Exception raised for errors in the input.

    Attributes:
        message -- explanation of the error
    """

    def __init__(self, message):
        self.message = message


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
        pil1 = _invert_pil(pil1)
    if pil2.sum() == 0:
        pil2 = _invert_pil(pil2)

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
