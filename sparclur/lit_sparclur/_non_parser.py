from sparclur._parser import Parser
import locale

class NonParser(Parser):

    def __init__(self, doc: str | bytes,
                 temp_folders_dir: str | None = None,
                 skip_check: bool | None = None,
                 timeout: int | None = None,
                 hash_exclude: str | list[str] | None = None,
                 **kwargs):
        super().__init__(
            doc=doc,
            temp_folders_dir=temp_folders_dir,
            skip_check=skip_check,
            timeout=timeout,
            hash_exclude=hash_exclude,
            **kwargs,
        )

    @staticmethod
    def get_name():
        return "Non-Parser"

    def _get_num_pages(self):
        """Mark page-count extraction as unsupported for this raw-file view."""
        self._num_pages = -1

    def get_raw(self):
        if isinstance(self._doc, bytes):
            return self._doc
        else:
            with open(self._doc, mode='rb') as doc:
                raw_doc = ''.join(line.decode(locale.getpreferredencoding(), errors='ignore') for line in doc)
            return raw_doc
