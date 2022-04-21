import abc

from sparclur._metaclass import Meta
from sparclur._parser import Parser


class Reforger(Parser, metaclass=Meta):
    """
    Abstract class for parsers with tools for PDF clean-up and reconstruction.
    """
    @abc.abstractmethod
    def __init__(self, doc,
                 skip_check,
                 timeout,
                 temp_folders_dir,
                 hash_exclude,
                 *args,
                 **kwargs):
        super().__init__(doc=doc,
                         temp_folders_dir=temp_folders_dir,
                         skip_check=skip_check,
                         timeout=timeout,
                         hash_exclude=hash_exclude,
                         *args,
                         **kwargs)
        reforger_apis = {'can_reforge': '(Property) Boolean for whether or not reforge capability is present',
                         'reforge': '(Property) Returns the raw binary of the reconstructed PDF',
                         'reforge_result': '(Property) Message conveying the success or failure of the reforging',
                         'save_reforge': 'Save the reforge to the specified file location'}
        self._api.update(reforger_apis)
        self._temp_folders_dir = temp_folders_dir
        self._reforged = None
        self._can_reforge: bool = None
        self._successfully_reforged = None
        self._reforge_result = None

    @property
    def can_reforge(self):
        if self._can_reforge is None:
            self._can_reforge = self._check_for_reforger()
        return self._can_reforge

    @can_reforge.deleter
    def can_reforge(self):
        self._can_reforge = None

    @abc.abstractmethod
    def _check_for_reforger(self) -> bool:
        pass

    @property
    def reforge(self):
        """
        The resulting reforged document.

        Returns
        -------
        bytes
        """
        assert self._skip_check or self._check_for_reforger(), "%s not found" % self.get_name()
        if self._reforged is None and self._successfully_reforged is not False:
            try:
                self._reforge()
                self._successfully_reforged = True
                self._reforge_result = 'Successfully reforged'
            except Exception as e:
                self._successfully_reforged = False
                self._reforge_result = str(e)
        return self._reforged

    @reforge.deleter
    def reforge(self):
        self._reforged = None
        self._successfully_reforged = None
        self._reforge_result = None

    @property
    def reforge_result(self):
        if self._successfully_reforged is None:
            _ = self._reforge
        return self._reforge_result

    def save_reforge(self, save_path: str):
        """
        Saves the reforged document to the specified file location.

        Parameters
        ----------
        save_path : str
            The file name and location to save the document.
        """
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
