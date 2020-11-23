import abc
from sparclur._parser import Parser
from sparclur.utils.tools import shingler, jac_dist, lev_dist


class TextExtractor(Parser, metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def get_text(self, page):
        pass

    def compare_text(self, other: 'TextExtractor', dist='jac', shingle_size=4):
        def _jaccard(s1, s2):
            return jac_dist(shingler(s1, shingle_size=shingle_size), shingler(s2, shingle_size=shingle_size))
        s1 = self.get_text()
        s2 = other.get_text()
        switcher = {
            'jac': _jaccard,
            'lev': lev_dist
        }
        func = switcher.get(dist, lambda x: 'Distance metric not found. Please select \'jac\' or \'lev\'')
        metric = func(s1, s2)
        return metric
