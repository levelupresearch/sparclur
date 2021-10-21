import abc

from sparclur._parser import Parser


class Reforger(Parser, metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def __init__(self, doc_path,
                 skip_check,
                 timeout,
                 temp_folders_dir: str = None,
                 *args,
                 **kwargs):
        super().__init__(doc_path=doc_path, skip_check=skip_check, timeout=timeout, *args, **kwargs)
        self._temp_folders_dir = temp_folders_dir
        self._reforged = None
        self._can_reforge: bool = None

    @abc.abstractmethod
    def _check_for_reforger(self) -> bool:
        pass

    @property
    def reforge(self):
        assert self._skip_check or self._check_for_reforger(), "%s not found" % self.get_name()
        if self._reforged is None:
            try:
                self._reforge()
            except Exception as e:
                print(e)
        else:
            print('Successfully reforged')

    @reforge.deleter
    def reforge(self):
        self._reforged = None

    def save_reforge(self, save_path):
        if self._reforged is None:
            self.reforge
        with open(save_path, 'wb') as file_out:
            file_out.write(self._reforged)

    @abc.abstractmethod
    def _reforge(self):
        pass
