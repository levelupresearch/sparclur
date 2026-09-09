"""Regression tests for image comparison highlighting."""

import numpy as np

from sparclur._prc_sim import PRCSim
from sparclur.utils import image_highlight


def test_image_highlight_recomputes_a_missing_diff():
    image = np.zeros((10, 10, 3), dtype=np.uint8)

    highlighted = image_highlight(image, image, prc=PRCSim({}, "missing diff", diff=None), display=False)

    assert isinstance(highlighted, tuple)
    assert all(render is not None for render in highlighted)
