import multiprocessing
from math import ceil
from typing import Union

from func_timeout import func_timeout

from sparclur.parsers.present_parsers import get_sparclur_texters, get_parser
from sparclur.utils import gen_flatten
import matplotlib.pyplot as plt
from tqdm import tqdm
from pebble import ProcessPool


def _render_compare_worker(entry):
    left_version, left_raw = entry['left']
    right_version, right_raw = entry['right']
    parser = entry['parser']
    parser_args = entry['parser_args']
    left = get_parser(parser)(left_raw, **parser_args)
    right = get_parser(parser)(right_raw, **parser_args)
    page_sims = left.compare(right)
    return '%i->%i' % (left_version, right_version), {page: prc.sim for (page, prc) in page_sims.items()}


def _num_updates(doc: Union[str, bytes]) -> bool:
    if isinstance(doc, str):
        with open(doc, 'rb') as file_in:
            raw = file_in.read()
    else:
        raw = doc
    num_eofs = raw.count(b'%%EOF')
    num_xrefs = raw.count(b'startxref')
    if num_eofs == num_xrefs:
        return num_eofs
    else:
        return 0


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

        if isinstance(doc, str):
            with open(doc, 'rb') as file_in:
                raw = file_in.read()
        self._raw = raw
        self._num_updates = _num_updates(raw)
        self._versions = {version: raw[slice(0, idx+7)] for (version, idx) in enumerate(_find_all(raw, b'%%EOF'))}

    @property
    def contains_updates(self):
        return self._num_updates > 1

    @property
    def num_updates(self):
        return self._num_updates

    def get_version(self, version: int):
        assert self._num_updates > version >= 0, "Version must be between 0 and %i" % self._num_updates - 1
        return self._versions.get(version, b'')

    def save_version(self, version: int, save_path: str):
        assert self._num_updates > version >= 0, "Version must be between 0 and %i" % self._num_updates - 1
        with open(save_path, 'wb') as file_out:
            file_out.write(self._versions.get(version, self._versions[0]))

    def compare_text(self, parser='Poppler', parser_args=dict(), display_width=10, display_height=10):
        assert self.contains_updates, "No incremental updates detected."
        assert parser in [p.get_name() for p in get_sparclur_texters()], '%s does not support text extraction' % parser
        tokens = dict()
        for (version, raw) in self._versions.items():
            p = get_parser(parser)(raw, **parser_args)
            tokens[version] = set(gen_flatten(p.get_tokens().values()))
        text_diffs = dict()
        for i in range(self._num_updates - 1):
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
        assert self.contains_updates, "No incremental updates detected."
        assert parser in [p.get_name() for p in get_sparclur_texters()], '%s does not support text extraction' % parser
        if isinstance(versions, str):
            if versions == 'all':
                versions = list(self._versions.keys())
            else:
                versions = None
        if versions is None:
            if self._num_updates > 11:
                print("%i versions detected. Only comparing the latest 11." % self._num_updates)
                versions = list(range(self._num_updates - 11, self._num_updates))
            else:
                versions = list(self._versions.keys())
        else:
            if isinstance(versions, int):
                versions = [versions]
            if len(versions) > 11:
                print('Warning: This will produce %i subplots if the document has multiple pages.' % len(versions) - 1)
        versions.sort()
        versions = [version for version in versions if version in self._versions.keys()]
        comparisons = []
        for (idx, version) in enumerate(versions[:-1]):
            entry = {'left': (version, self._versions[version]),
                     'right': (versions[idx+1], self._versions[versions[idx+1]]),
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
        else:
            nrows = ceil(len(comparisons) / ncols)
            fig, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=(display_width, display_height))

            for idx, ax in enumerate(axes.flat):
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






