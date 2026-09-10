"""Layout tests for PRC visual comparisons."""

from PIL import Image
import warnings

from sparclur.prc._viz import PRCViz


class _Renderer:
    def get_renders(self, page):
        return Image.new('RGB', (100, 140), 'white')


class _Comparison:
    diff = Image.new('RGB', (100, 140), 'black')
    sim = 0.98765


def test_display_allocates_height_for_each_selected_pair():
    viz = PRCViz.__new__(PRCViz)
    viz._doc = 'example.pdf'
    viz._renders = {'One': _Renderer(), 'Two': _Renderer(), 'Three': _Renderer()}
    viz._sims = {
        ('One', 'Two'): {0: _Comparison()},
        ('One', 'Three'): {0: _Comparison()},
    }

    figure = viz.display(
        page=0,
        renderers=[('One', 'Two'), ('One', 'Three')],
        width=12,
        height=4,
    )

    assert figure.get_size_inches().tolist() == [12.0, 8.0]
    assert len(figure.axes) == 6


def test_plot_sims_accepts_named_colormap_for_many_pairs():
    viz = PRCViz.__new__(PRCViz)
    viz._doc = 'example.pdf'
    viz._ssims_fig = None
    viz._sim_keys = [('One', 'Two')] * 6
    viz._sims = {('One', 'Two'): {0: _Comparison()}}

    with warnings.catch_warnings(record=True) as caught:
        figure = viz.plot_sims(cmap='tab10')

    assert figure is not None
    assert caught == []
