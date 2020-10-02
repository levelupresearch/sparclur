import abc
from sparclur.parsers._parser import Parser


class Renderer(Parser, metaclass=abc.ABC):

    @abc.abstractmethod
    def render_page(self, page, save_path):
        pass
