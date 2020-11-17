import abc


class Parser(metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def get_doc_path(self):
        pass

    @abc.abstractmethod
    def get_name(self):
        pass

    @abc.abstractmethod
    def _parse_document(self):
        pass

    @abc.abstractmethod
    def get_messages(self):
        pass

    @abc.abstractmethod
    def get_cleaned(self):
        pass

    @abc.abstractmethod
    def _clean_message(self, err):
        pass

    @abc.abstractmethod
    def _scrub_messages(self):
        pass