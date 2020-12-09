import hashlib
import os
import fitz
import re


class InputError(Exception):
    """Exception raised for errors in the input.

    Attributes:
        message -- explanation of the error
    """

    def __init__(self, message):
        self.message = message


def create_file_list(files, recurse=False, base_path=None):

    try:
        if os.path.isfile(files):
            with open(files) as fp:
                files = ''.join(line for line in fp)
                files = files.split('\n')
    except:
        pass
    if isinstance(files, list) and base_path is not None:
        files = [os.path.join(*base_path.split(os.path.sep), *file.split(os.path.sep)) for file in files]
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
    return set([s[i:i+shingle_size] for i in range(len(s) - shingle_size + 1)])


def jac_dist(set1, set2):
    intersect = len(set1.intersection(set2))
    size1 = len(set1)
    size2 = len(set2)
    union = size1 + size2 - intersect
    return 1 - intersect / union


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
    sha256_hash = hashlib.sha256()
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
