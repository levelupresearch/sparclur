import abc
from sparclur._parser import Parser


class MetadataExtractor(Parser, metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def get_metadata(self):
        pass