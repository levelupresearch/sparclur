import multiprocessing
from math import ceil
from typing import Union, List

from func_timeout import func_timeout

from sparclur.parsers.present_parsers import get_sparclur_texters, get_parser
from sparclur.utils import gen_flatten
import matplotlib.pyplot as plt
from tqdm import tqdm
from pebble import ProcessPool

EOF = b'%%EOF'
XREF = b'startxref'
LINEAR = b'/Linearized'


def _render_compare_worker(entry):
    left_version, left_raw = entry['left']
    right_version, right_raw = entry['right']
    parser = entry['parser']
    parser_args = entry['parser_args']
    left = get_parser(parser)(left_raw, **parser_args)
    right = get_parser(parser)(right_raw, **parser_args)
    page_sims = left.compare(right)
    return '%i->%i' % (left_version, right_version), {page: prc.sim for (page, prc) in page_sims.items()}


def _find_updates(doc: Union[str, bytes]) -> List[int]:
    if isinstance(doc, str):
        with open(doc, 'rb') as file_in:
            raw = file_in.read()
    else:
        raw = doc
    potential_updates = list(_find_all(raw, EOF))
    previous_offset = 0
    updates = []
    is_linear = False
    has_startxref = False
    for offset in potential_updates:
        if raw[previous_offset:offset].find(LINEAR) > 0:
            is_linear = True
        if raw[previous_offset:offset].find(XREF) > 0:
            has_startxref = True
        if not is_linear and has_startxref:
            updates.append(offset)
        previous_offset = offset
        is_linear = False
        has_startxref = False
    return updates


def _find_all(a_str, sub):
    start = 0
    while True:
        start = a_str.find(sub, start)
        if start == -1: return
        yield start
        start += len(sub)


class RollBack:
    """Checks for incremental updates and if present analyzes the differences between the versions."""

    def __init__(self,
                 doc: Union[str, bytes]
                 ):
        """
        Parameters
        ----------
        doc : str or bytes
            The document to check for incremental updates.
        """
        self._doc = doc
        updates = _find_updates(doc)
        self._num_versions = len(updates)
        self._versions = {version: offset for (version, offset) in enumerate(updates)}

    @property
    def contains_updates(self):
        """
        Whether or not the document has incremental updates.

        Returns
        -------
        bool
        """
        return self._num_versions > 1

    @property
    def num_versions(self):
        """
        The number of detected updates in the document.

        Returns
        -------
        int
        """
        return self._num_versions

    def get_version(self, version: int):
        """
        Return the specified version. Versions are 0-indexed.

        Returns
        -------
        bytes
        """
        assert self._num_versions > version >= 0, "Version must be between 0 and %i" % self._num_versions - 1
        if isinstance(self._doc, str):
            with open(self._doc, 'rb') as file_in:
                raw = file_in.read()
        else:
            raw = self._doc
        return raw[slice(0, self._versions.get(version) + 7)]

    def save_version(self, version: int, save_path: str):
        """
        Save the specified incremental update version. Versions are 0-indexed.
        """
        raw = self.get_version(version)
        with open(save_path, 'wb') as file_out:
            file_out.write(raw)

    def compare_text(self, parser='Poppler', parser_args=dict(), display_width=10, display_height=10):
        """
        Compares the extracted text tokens between subsequent versions and plots the number of additions and
        subtractions in stacked bars. The Parser needs to support text extraction.

        Parameters
        ----------
        parser : str, default='Poppler'
            Name of the parser to use for the text extraction
        parser_args : Dict[str, Any]
            Any specific arguments to pass to the selected parser
        display_width : int
            The width of the resulting plot
        display_height : int
            The height of the resulting plot

        Returns
        -------
        PyPlot figure
        """
        assert self.contains_updates, "No incremental updates detected."
        assert parser in [p.get_name() for p in get_sparclur_texters()], '%s does not support text extraction' % parser
        tokens = dict()
        for version in self._versions.keys():
            raw = self.get_version(version)
            p = get_parser(parser)(raw, **parser_args)
            tokens[version] = set(gen_flatten(p.get_tokens().values()))
        text_diffs = dict()
        for i in range(self._num_versions - 1):
            text_diffs['%i->%i' % (i, i+1)] = {'added': len(tokens[i+1].difference(tokens[i])),
                                               'removed': len(tokens[i].difference(tokens[i+1]))}
        x = list(text_diffs.keys())
        added = [text_diffs[x_i]['added'] for x_i in x]
        removed = [-text_diffs[x_i]['removed'] for x_i in x]
        fig = plt.figure(figsize=(display_width, display_height))
        ax = plt.subplot(111)
        ax.bar(x, removed, width=1, color='r')
        ax.bar(x, added, width=1, color='g')
        plt.close(fig)
        return fig

    def compare_renders(self, parser='Poppler',
                        parser_args=dict(),
                        num_workers=1,
                        versions=None,
                        progress_bar=True,
                        timeout=120,
                        display_width=10,
                        display_height=10,
                        ncols=5):
        """
        Compares the renders between subsequent versions of incremental updates. If the versions are not specified and
        there are more than 11 versions detected, only the lastest 11 versions will be compared. The rendering
        comparisons can be run in parallel by setting the `num_workers` greater than 1. This can be a time consuming
        process and care should be taken in trying to compare too many versions at one time. These render comparisons
        are then plotted by subsequent versions comparisons for each page.

        Parameters
        ----------
        parser : str, default='Poppler'
            The parser to use to generate the renders.
        parser_args : Dict[str, Any]
            Any additional arguments to pass to the specified parser
        num_workers : int, default=1
            The number of workers to use if render comparisons are run in parallel. Choose 1 to run serially.
        versions : List[int], default=None
            The specific versions to compare. If the versions are not contiguous, they will be sorted and comparisons
            will happen between neighbors in the sorted list.
        progress_bar : bool, default=True
            Flag that determines if a progress bar for the render comparisons is displayed
        timeout : int, default=120
            A timeout parameter for the rendering comparison
        display_width : int
            The width of the resulting plot
        display_height : int
            The height of the resulting plot
        ncols : int
            The number of columns in the final subplot of comparisons.

        Returns
        -------
        PyPlot figure
        """
        assert self.contains_updates, "No incremental updates detected."
        assert parser in [p.get_name() for p in get_sparclur_texters()], '%s does not support text extraction' % parser
        if isinstance(versions, str):
            if versions == 'all':
                versions = list(self._versions.keys())
            else:
                versions = None
        if versions is None:
            if self._num_versions > 11:
                print("%i versions detected. Only comparing the latest 11." % self._num_versions)
                versions = list(range(self._num_versions - 11, self._num_versions))
            else:
                versions = list(self._versions.keys())
        else:
            if isinstance(versions, int):
                versions = [versions]
            if len(versions) > 11:
                subplot_count = len(versions) - 1
                print('Warning: This will produce %i subplots if the document has multiple pages.' % subplot_count)
        versions.sort()
        versions = [version for version in versions if version in self._versions.keys()]
        comparisons = []
        for (idx, version) in enumerate(versions[:-1]):
            entry = {'left': (version, self.get_version(version)),
                     'right': (versions[idx+1], self.get_version(versions[idx+1])),
                     'parser': parser,
                     'parser_args': parser_args}
            comparisons.append(entry)
        if num_workers == 1:
            render_diffs = dict()
            if progress_bar:
                pbar = tqdm(total=len(comparisons))
            for entry in comparisons:
                compare, page_sims = func_timeout(timeout,
                                                  _render_compare_worker,
                                                  kwargs={
                                                      'entry': entry
                                                  }
                                                  )
                render_diffs[compare] = page_sims
                if progress_bar:
                    pbar.update(1)
            if progress_bar:
                pbar.close()
        else:
            if progress_bar:
                pbar = tqdm(total=len(comparisons))
            render_diffs = dict()
            index = 0

            with ProcessPool(max_workers=num_workers, context=multiprocessing.get_context('spawn')) as pool:
                future = pool.map(_render_compare_worker, comparisons, timeout=120)
                iterator = future.result()

                while True:

                    try:
                        result = next(iterator)
                    except StopIteration:
                        result = None
                        break
                    except Exception as e:
                        left_version = comparisons[index]['left'][0]
                        right_version = comparisons[index]['right'][0]
                        print('%i->%i comparison failed:\n%s\n\n' % (left_version, right_version, str(e)))
                        result = None
                    finally:
                        if progress_bar:
                            pbar.update(1)
                        if result is not None:
                            compare, page_sim = result
                            render_diffs[compare] = page_sim
            if progress_bar:
                pbar.close()

        X = list(render_diffs.keys())
        X.sort(key=lambda c: int(c.split('->')[0]))

        max_num_page_compares = max([len(sims) for sims in render_diffs.values()])
        if max_num_page_compares == 1:
            Y = [list(render_diffs[x_i].values())[0] for x_i in X]
            fig = plt.figure(figsize=(display_width, display_height))
            ax = plt.subplot(111)
            ax.plot(X, Y, 'k.')
            ax.set_title('Version similarities')
            ax.set(xlabel='Version comparison', ylabel='Similarity')
            plt.close(fig)
            return fig
        elif len(render_diffs) == 1:
            page_compares = list(render_diffs.values())[0]
            x = list(page_compares.keys())
            y = list(page_compares.values())
            fig = plt.figure(figsize=(display_width, display_height))
            ax = plt.subplot(111)
            ax.plot(x, y, 'k.')
            ax.set_title('%s Comparisons' % X[0])
            ax.set(xlabel='Page', ylabel='Similarity')
            plt.close(fig)
            return fig
        else:
            nrows = ceil(len(comparisons) / ncols)
            fig, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=(display_width, display_height))

            for idx, ax in enumerate(axes.flat):
                if idx >= len(X):
                    ax.set_axis_off()
                else:
                    X_i = X[idx]
                    x = list(render_diffs[X_i].keys())
                    x.sort()
                    y = [render_diffs[X_i][x_i] for x_i in x]
                    ax.plot(x, y, 'k.')
                    ax.set_title('%s Comparisons' % X_i)
                    ax.set(xlabel='Page', ylabel='Similarity')
                    ax.label_outer()
            plt.close(fig)
            return fig






