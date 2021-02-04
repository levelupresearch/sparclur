class SSIM:
    """Case class for structural similarity comparison results"""
    def __init__(self, ssim, result, diff=None):
        """

        Parameters
        ----------
        ssim : float
            The structural similarity metric
        diff : PngImageFile
            The visual difference between the original images
        result : str
            A 'Compared Successfully' message if the comparison was successful, otherwise the generated error message
        """
        self._ssim = ssim
        self._diff = diff
        self._result = result

    @property
    def ssim(self):
        return self._ssim

    @property
    def result(self):
        return self._result

    @property
    def diff(self):
        return self._diff

    def show(self):
        """Display the visual difference, if available."""
        if self.diff is not None:
            self.diff.show()
