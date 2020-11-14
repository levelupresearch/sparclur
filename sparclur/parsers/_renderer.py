import abc


class Renderer(metaclass=abc.ABC):

    @abc.abstractmethod
    def get_name(self):
        pass

    @abc.abstractmethod
    def render_page(self, path, page):
        pass

    def render_doc(self, path):
        pass
