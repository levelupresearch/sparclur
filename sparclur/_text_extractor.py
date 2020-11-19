import abc
from sparclur._parser import Parser


class TextExtractor(Parser, metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def get_text(self):
        pass

    def compare_text(self, other: 'TextExtractor', **kwargs):
        left = self.get_text(**kwargs)
        right = other.get_text(**kwargs)