class PRCSim:
    """Case class for PRC similarity results"""
    def __init__(self, similarity_scores, result, diff=None):
        self._entropy_sim = similarity_scores.get('entropy_sim', 0.0)
        self._whash_sim = similarity_scores.get('whash_sim', 0.0)
        self._phash_sim = similarity_scores.get('phash_sim', 0.0)
        self._sum_square_sim = similarity_scores.get('sum_square_sim', 0.0)
        self._ccorr_sim = similarity_scores.get('ccorr_sim', 0.0)
        self._ccoeff_sim = similarity_scores.get('ccoeff_sim', 0.0)
        self._size_sim = similarity_scores.get('size_sim', 1.0)
        self._sim = ((sum(similarity_scores.values()) - self._size_sim) / 6.0) * self._size_sim * self._size_sim
        self._ssim = similarity_scores.get('ssim', 0.0)
        self._result = result
        self._diff = diff

    def __iter__(self):
        yield self._sim
        yield self._result
        yield self._diff

    @property
    def sim(self):
        return self._sim

    @property
    def result(self):
        return self._result

    @property
    def diff(self):
        return self._diff

    @property
    def whash_sim(self):
        return self._whash_sim

    @property
    def phash_sim(self):
        return self._phash_sim

    @property
    def entropy_sim(self):
        return self._entropy_sim

    @property
    def sum_square_sim(self):
        return self._sum_square_sim

    @property
    def ccorr_sim(self):
        return self._ccorr_sim

    @property
    def ccoeff_sim(self):
        return self._ccoeff_sim

    @property
    def size_sim(self):
        return self._size_sim