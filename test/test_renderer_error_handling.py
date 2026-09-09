"""Tests for renderer comparison failure handling."""

from sparclur._renderer import Renderer


class _InvalidRenderer:
    _timeout = None

    def get_renders(self, page=None):
        return {0: object()}


def test_compare_returns_original_error_for_invalid_renders():
    left = _InvalidRenderer()
    right = _InvalidRenderer()

    result = Renderer.compare(left, right)

    assert isinstance(result[0].result, str)
    assert result[0].result
