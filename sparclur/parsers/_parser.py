import abc

class Parser(metaclass=abc.ABC):
    @abc.abstractmethod
    def get_name(self):
        pass