import abc


class Renderer(metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def get_name(self):
        pass

    @abc.abstractmethod
    def get_doc_path(self):
        pass

    @abc.abstractmethod
    def get_caching(self):
        pass

    @abc.abstractmethod
    def set_caching(self, caching):
        pass

    @abc.abstractmethod
    def clear_cache(self):
        pass

    @abc.abstractmethod
    def _render_page(self, page):
        pass

    @abc.abstractmethod
    def _render_doc(self):
        pass

    @abc.abstractmethod
    def get_renders(self, page):
        pass