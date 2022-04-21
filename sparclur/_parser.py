from __future__ import annotations
import abc
from typing import Dict, Any, List, Union

from imagehash import ImageHash

from sparclur._metaclass import Meta
from sparclur.utils import jac_sim, hash_file

VALID = 'Valid'
VALID_WARNINGS = 'Valid with Warnings'
REJECTED = 'Rejected'
REJECTED_AMBIG = 'Rejected; Ambiguous'
TIMED_OUT = 'Timed Out'

RENDER = 'Renderer'
TRACER = 'Tracer'
TEXT = 'Text Extractor'
META = 'Metadata Extractor'
FONT = 'Font Extractor'
IMAGE = 'Image Data'

SPARCLUR_TYPES = [RENDER, TRACER, TEXT, META, FONT, IMAGE]

RENDER_HASH_SIZE = 128


def _compare_render_hash(left, right):
    pages = set().union(left.keys()).union(right.keys())
    comparison = dict()
    for page in pages:
        left_hash: ImageHash = left.get(page, None)
        right_hash: ImageHash = right.get(page, None)
        if left_hash is not None and right_hash is not None:
            diff = left_hash - right_hash
            normalized = diff / (RENDER_HASH_SIZE * RENDER_HASH_SIZE)
            comparison[page] = 1.0 - normalized
        else:
            comparison[page] = 0.0
    return comparison


def _compare_tracer_hash(left, right):
    return jac_sim(left, right)


def _compare_text_hash(left, right):
    pages = set().union(left.keys()).union(right.keys())
    comparison = dict()
    for page in pages:
        left_hash_set = left.get(page, set())
        right_hash_set = right.get(page, set())
        comparison[page] = jac_sim(left_hash_set, right_hash_set)
    return comparison


def _compare_metadata_hash(left, right):
    objects = set().union(left.keys()).union(right.keys())
    comparison = dict()
    for obj in objects:
        comparison[obj] = 1 if left.get(obj, None) == right.get(obj, None) else 0
    return comparison


def _compare_font_hash(left, right):
    fonts = set().union(left.keys()).union(right.keys())
    comparison = dict()
    for font in fonts:
        comparison[font] = 1 if left.get(font, None) == right.get(font, None) else 0
    return comparison


class SparclurHash:
    """
    The SPARCLUR hash attempts to distill the information from the different parser tools: image hashes for the
    renders and sets of shingled murmur hashes for the text extraction, metadata, trace messages, and fonts. These
    are collected and then can be used to compare two documents and a distance measure is calculated. This is most
    relevant in 2 specific cases: the first is trying to find evidence of non-determinism in a parser and the
    second is to quickly compare differences between parser translations of a document (See the Reforge class of
    tools).
    """
    def __init__(self, doc: str,
                 exclude: str or List[str] = None):
        """
        Parameters
        ----------
        doc : str or bytes
            Either the path to the PDF or the raw bytes of the PDF
        exclude : str or List[str]
            Specifies any subclass SPARCLUR hashes that should be excluded from this parser instantiation. Can be one or
            more of the following: 'Renderer', 'Tracer', 'Text Extractor', 'Metadata Extractor', and/or 'Font Extractor'
        """

        if exclude is None or (not isinstance(exclude, str) and not isinstance(exclude, list)):
            self._exclude = []
        elif isinstance(exclude, str):
            self._exclude = [exclude]
        else:
            self._exclude = exclude

        self._doc_hash = hash_file(doc)
        self._hash = dict()

    def __len__(self):
        return len(self._hash)

    def __getitem__(self, key):
        return self._hash[key]

    def get(self, key, default):
        if key in self._hash:
            return self._hash[key]
        else:
            return default

    def keyset(self):
        return set(self._hash.keys())

    def __contains__(self, key):
        return key in self._hash

    @property
    def excluded(self):
        return self._exclude

    @property
    def file_hash(self):
        return self._doc_hash

    def _add_hash(self, key, value):
        self._hash[key] = value

    def equals(this, that: SparclurHash or Parser):
        """
        Checks for parsed document information equality.

        Returns
        -------
        bool
        """
        comparison = this.compare(that)
        return comparison['sim'] == 1.0

    def compare(this, that: SparclurHash or Parser):
        """
        Compares all of the present information hashes and collects all of the results.

        Returns
        -------
        Dict[str, Any]
        """
        if isinstance(that, Parser):
            that = that.sparclur_hash
        results = dict()
        sim = 0.0
        num_compares = 0
        for key in set().union(this.keyset()).union(that.keyset()):
            if key == RENDER:
                render_compare = _compare_render_hash(this.get(RENDER, dict()), that.get(RENDER, dict()))
                render_sim = min(list(render_compare.values())) if len(list(render_compare.values())) > 0 else 0.0
                sim = sim + render_sim
                num_compares = num_compares + 1
                results[RENDER] = render_compare
                results[RENDER+' sim'] = render_sim
            if key == TRACER:
                trace_compare = _compare_tracer_hash(this.get(TRACER, set()), that.get(TRACER, set()))
                sim = sim + trace_compare
                num_compares = num_compares + 1
                results[TRACER+' sim'] = trace_compare
            if key == TEXT:
                text_compare = _compare_text_hash(this.get(TEXT, dict()), that.get(TEXT, dict()))
                text_sim = min(text_compare.values()) if len(list(text_compare.values())) > 0 else 0.0
                sim = sim + text_sim
                num_compares = num_compares + 1
                results[TEXT] = text_compare
                results[TEXT+' sim'] = text_sim
            if key == META:
                meta_compare = _compare_metadata_hash(this.get(META, dict()), that.get(META, dict()))
                meta_sim = sum(meta_compare.values()) / len(meta_compare)
                sim = sim + meta_sim
                num_compares = num_compares + 1
                results[META] = meta_compare
                results[META+' sim'] = meta_sim
            if key == FONT:
                font_compare = _compare_font_hash(this.get(FONT, dict()), that.get(FONT, dict()))
                font_sim = sum(font_compare.values()) / len(font_compare) if len(font_compare) > 0 else 0.0
                sim = sim + font_sim
                num_compares = num_compares + 1
                results[FONT] = font_compare
                results[FONT+' sim'] = font_sim
        overall_sim = sim / num_compares
        dist = 1 - overall_sim
        results['sim'] = overall_sim
        results['dist'] = dist
        return results


class Parser(metaclass=Meta):
    """
    Base abstract class for SPARCLUR parser wrappers.

    This abstract class provides the basis for all parser wrappers in SPARCLUR.
    """

    @abc.abstractmethod
    def __init__(self, doc: Union[str, bytes],
                 temp_folders_dir: Union[str, None],
                 skip_check: Union[bool, None],
                 timeout: Union[int, None],
                 hash_exclude: Union[str, List[str], None],
                 *args,
                 **kwargs):
        """
        Parameters
        ----------
        doc : str or bytes
            Either the path to the PDF or the raw bytes of the PDF
        temp_folders_dir : str
            Path to create the temporary directories used for temporary files.
        timeout : int
            Specify a timeout for parsing commands
        skip_check : bool
            Flag for skipping the parser check.
        hash_exclude : str or List[str]
            Specifies any subclass SPARCLUR hashes that should be excluded from this parser instantiation. Can be one or
            more of the following: 'Renderer', 'Tracer', 'Text Extractor', 'Metadata Extractor', and/or 'Font Extractor'
        """
        self._doc = doc
        self._temp_folders_dir = temp_folders_dir
        self._skip_check = skip_check
        self._timeout = timeout
        self._hash_exclude = hash_exclude
        self._validity: Dict[str, Dict[str, Any]] = dict()
        self._api: Dict[str, str] = {'num_pages': '(Property) Returns number of pages in the document'}
        self._num_pages = None
        self._sparclur_hash = SparclurHash(doc, hash_exclude)
        self._file_timed_out = dict()

    def __repr__(self):
        return '\n'.join('%s:\t%s' % (method, desc) for (method, desc) in self._api.items())

    def __str__(self):
        return self.get_name()

    @property
    def doc(self):
        """
        Return the path to the document that is being run through the parser instance or the first 15 bytes if a binary
        was passed to the parser.

        Returns
        -------
        str or bytes
            String of the document path or first 15 bytes of the binary
        """
        return self._doc if isinstance(self._doc, str) else self._doc[0:15]

    @abc.abstractmethod
    def _get_num_pages(self):
        pass

    @property
    def temp_folders_dir(self):
        return self._temp_folders_dir

    @temp_folders_dir.setter
    def temp_folders_dir(self, t):
        self._temp_folders_dir = t

    @temp_folders_dir.deleter
    def temp_folders_dir(self):
        self._temp_folders_dir = None

    @staticmethod
    @abc.abstractmethod
    def get_name():
        """
        Return the SPARCLUR defined name for the parser.

        Returns
        -------
        str
            Parser name
        """
        pass

    @property
    def validity(self):
        """
        Returns the validity statuses from each of the relevant tools of the parser and an overall validity for the
        document. If any of the tools have a warning or error the overall will show that otherwise all of the tools need
        to mark the document as valid for the overall status to be valid.

        Returns
        -------
        Dict[str, Dict[str, Any]]
            A dictionary of dictionaries laying out the validity and statuses for the parser tools.
        """
        results = [(entry['valid'], entry['status']) for (key, entry) in self._validity.items()]
        statuses = [entry[1] for entry in results]
        validity = min([entry[0] for entry in results])
        if REJECTED in statuses:
            status = REJECTED
        elif REJECTED_AMBIG in statuses:
            status = REJECTED_AMBIG
        elif VALID_WARNINGS in statuses:
            status = VALID_WARNINGS
        else:
            status = VALID
        self._validity['overall'] = {'valid': validity, 'status': status}
        return self._validity

    @property
    def sparclur_hash(self):
        """
        The SPARCLUR hash attempts to distill the information from the different parser tools: image hashes for the
        renders and sets of shingled murmur hashes for the text extraction, metadata, trace messages, and fonts. These
        are collected and then can be used to compare two documents and a distance measure is calculated. This is most
        relevant in 2 specific cases: the first is trying to find evidence of non-determinism in a parser and the
        second is to quickly compare differences between parser translations of a document (See the Reforge class of
        tools).

        Returns
        -------
        SparclurHash
            The class that holds the SPARCLUR hashes for each tool and provides an API for comparing two hashes.
        """
        return self._sparclur_hash

    @property
    def timeout(self):
        return self._timeout

    @timeout.setter
    def timeout(self, to: int):
        self._sparclur_hash = SparclurHash(self._doc, self._hash_exclude)
        self._timeout = to
        self._file_timed_out = dict()

    @timeout.deleter
    def timeout(self):
        self._sparclur_hash = SparclurHash(self._doc, self._hash_exclude)
        self._timeout = None
        self._file_timed_out = dict()

    @property
    def num_pages(self):
        """
        Determine the number of pages in the PDF according to the parser. If the parser does not support page number
        extraction (e.g. Arlington DOM Checker) this returns None. If the parser fails to load and determine the
        number of pages, 0 is returned.

        Returns
        -------
        int
            The number of pages in the document
        """
        if self._num_pages is None:
            self._get_num_pages()
        return self._num_pages
