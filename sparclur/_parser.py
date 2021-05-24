import abc
from typing import Dict, Any

VALID = 'Valid'
VALID_WARNINGS = 'Valid with Warnings'
REJECTED = 'Rejected'
REJECTED_AMBIG = 'Rejected; Ambiguous'

RENDER = 'Renderer'
TRACER = 'Tracer'
TEXT = 'Text Extractor'
META = 'Metadata Extractor'
FONT = 'Font Extractor'
IMAGE = 'Image Data'


class Parser(metaclass=abc.ABCMeta):
    """
    Base abstract class for SPARCLUR parser wrappers.

    This abstract class provides the basis for all parser wrappers in SPARCLUR.
    """

    @abc.abstractmethod
    def __init__(self, doc_path, skip_check, *args, **kwargs):
        self._doc_path = doc_path
        self._skip_check = skip_check
        self._validity: Dict[str, Dict[str, Any]] = dict()
        # self._status = None
        # self._root_cause = None

    # @abc.abstractmethod
    # def _check_for_validity(self):
    #     """
    #     Performs the validity check.
    #     """
    #     pass

    @property
    def doc_path(self):
        """
        Return the path to the document that is being run through the parser instance.

        Returns
        -------
        str
            String of the document path
        """
        return self._doc_path

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
        return self._validity

    # @property
    # def valid(self):
    #     """
    #     Return whether or not the given document is valid under the given parser.
    #
    #     Returns
    #     -------
    #     bool
    #         Whether or not the document is valid
    #     """
    #     if self._valid is None:
    #         self._check_for_validity()
    #     return self._valid
    #
    # @property
    # def status(self):
    #     """
    #     Return a more detailed validity status.
    #
    #     Returns
    #     -------
    #     str
    #     """
    #     if self._status is None:
    #         self._check_for_validity()
    #     return self._status
    #
    # @property
    # def root_cause(self):
    #     """
    #     Return a possible root cause for pdf rejection.
    #
    #     Returns
    #     -------
    #     str
    #     """
    #     if self._root_cause is None:
    #         self._check_for_validity()
    #     return self._root_cause
