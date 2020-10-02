import abc


class Parser(metaclass=abc.ABC):

    @abc.abstractmethod
    def get_name(self):
        pass

    @abc.abstractmethod
    def get_messages(self, path, save_path):
        pass
