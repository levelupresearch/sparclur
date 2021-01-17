from typing import List


class CreatePweaveDoc:
    """
    Generate a Pweave document of the SPARCLUR results over a collection of documents. Pweave can be used to generate
    a report of the SPARCLUR findings.
    """
    def __init__(self, docs: str or List[str],
                 save_path: str,
                 title: str = "SPARCLUR Report"
                 ):
        """
        Parameters
        ----------
        docs: str or List[str]
            Single path or list of paths to PDF's to be analyzed
        save_path: str
            The save path of the report
        title: str
            The title of the report
        """
        self._docs = docs if isinstance(docs, list) else [docs]
        self._save_path = save_path
        self._title = title

    @property
    def title(self):
        return self._title

    @title.setter
    def title(self, t:str):
        self._title = t

    @property
    def save_path(self):
        return self._save_path

    @save_path.setter
    def save_path(self, sp:str):
        self._save_path = sp

    def generate_report(self):
        pass