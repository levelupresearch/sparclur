import abc

from sparclur._parser import Parser


class Reforger(Parser, metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def __init__(self, doc,
                 skip_check,
                 timeout,
                 temp_folders_dir,
                 *args,
                 **kwargs):
        super().__init__(doc=doc, temp_folders_dir=temp_folders_dir, skip_check=skip_check, timeout=timeout, *args, **kwargs)
        self._temp_folders_dir = temp_folders_dir
        self._reforged = None
        self._can_reforge: bool = None
        self._successfully_reforged = None
        self._reforge_result = None

    @abc.abstractmethod
    def _check_for_reforger(self) -> bool:
        pass

    @property
    def reforge(self, verbose=False):
        assert self._skip_check or self._check_for_reforger(), "%s not found" % self.get_name()
        if self._reforged is None and self._successfully_reforged is not False:
            try:
                self._reforge()
                # self._successfully_reforged = True
                # self._reforge_result = 'Successfully reforged'
            except Exception as e:
                self._successfully_reforged = False
                self._reforge_result = str(e)
        if verbose:
            print(self._reforge_result)
        return self._reforged

    @reforge.deleter
    def reforge(self):
        self._reforged = None

    def save_reforge(self, save_path):
        if self._successfully_reforged is None:
            _ = self.reforge
        if self._successfully_reforged:
            with open(save_path, 'wb') as file_out:
                file_out.write(self._reforged)

    @abc.abstractmethod
    def _reforge(self):
        pass

    @property
    def validity(self):
        return super().validity

    @property
    def sparclur_hash(self):
        return super().sparclur_hash
