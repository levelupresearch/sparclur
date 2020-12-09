import abc


class Parser(metaclass=abc.ABCMeta):
    """
    Base abstract class for SPARCLUR parser wrappers.

    This abstract class provides the basis for all parser wrappers in SPARCLUR.
    """

    @abc.abstractmethod
    def __init__(self, doc_path, *args, **kwargs):
        self._doc_path = doc_path

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
