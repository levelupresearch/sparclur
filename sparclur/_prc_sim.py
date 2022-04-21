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
        sim_sum = self._entropy_sim + self._whash_sim + self._phash_sim + self._sum_square_sim + self._ccorr_sim + self._ccoeff_sim
        # sim_sum = self._entropy_sim + self._whash_sim + self._phash_sim + self._sum_square_sim + self._ccorr_sim
        self._sim = (sim_sum / 6.0) * self._size_sim * self._size_sim
        self._ssim = similarity_scores.get('ssim', 0.0)
        self._result = result
        self._diff = diff

    def __iter__(self):
        yield self._sim
        yield self._result
        yield self._diff

    def __repr__(self):
        metrics = self.all_metrics
        return '\n'.join('%s: %s' % (key, val) for key, val in metrics.items())

    @property
    def all_metrics(self):
        metrics = {'sim': self._sim,
                   'entropy_sim': self._entropy_sim,
                   'whash_sim': self._whash_sim,
                   'phash_sim': self._phash_sim,
                   'sum_square_sim': self._sum_square_sim,
                   'ccorr_sim': self._ccorr_sim,
                   'ccoeff_sim': self._ccoeff_sim,
                   'size_sim': self._size_sim}
        return metrics

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

    # @property
    # def ccoeff_sim(self):
    #     return self._ccoeff_sim

    @property
    def size_sim(self):
        return self._size_sim
