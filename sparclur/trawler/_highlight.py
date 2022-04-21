import multiprocessing
from typing import List, Dict, Callable, Any
from inspect import isclass

import pandas as pd

from sparclur._parser import Parser
from sparclur._prc_sim import PRCSim
from sparclur._renderer import Renderer
from sparclur.parsers.present_parsers import get_sparclur_renderers
from sparclur.utils import create_file_list, pil_to_hex_array, entropy_sim, gen_flatten

import numpy as np
import cv2

from tqdm import tqdm
from pebble import ProcessPool

from sparclur.utils._tools import _get_contours


def _parse_renderers(parsers):
    """
    Parses the renderers to run.

    Parameters
    ----------
    parsers: List[str] or List[Parser] or str or Parser

    """
    parser_dict = {parser.get_name(): parser for parser in get_sparclur_renderers()}
    if not isinstance(parsers, list):
        parsers = [parsers]
    result = dict()
    for parser in parsers:
        if isinstance(parser, str):
            if parser in parser_dict:
                result[parser] = parser_dict[parser]
        elif isclass(parser):
            if issubclass(parser, Renderer):
                result[parser.get_name()] = parser
        elif isinstance(parser, Renderer):
            result[parser.get_name()] = parser
    return result


def _worker(entry):
    orig_file = entry['orig']
    mod_file = entry['mod_file']
    timeout = entry['timeout']
    dpi = entry['dpi']
    min_region = entry['min_region']
    prc_threshold = entry['prc_threshold']
    ent_threshold = entry['ent_threshold']
    renderers = entry['renderers']
    parser_args = entry['parser_args']
    results = []
    for (name, parser) in renderers.items():
        try:
            args = parser_args.get(name, dict())
            orig: Renderer = parser(doc=orig_file, dpi=dpi, timeout=timeout, cache_renders=True, **args)
            mod: Renderer = parser(doc=mod_file, dpi=dpi, timeout=timeout, cache_renders=True, **args)
            prc: Dict[int, PRCSim] = orig.compare(mod, full=True)
            for (page, sim) in prc.items():
                if sim.sim <= prc_threshold:
                    try:
                        orig_page = pil_to_hex_array(orig.get_renders(page))
                        mod_page = pil_to_hex_array(mod.get_renders(page))
                        filtered_contours = _get_contours(min_region, sim.diff)
                        for c in filtered_contours:
                            x, y, w, h = cv2.boundingRect(c)
                            w = int(w)
                            h = int(h)
                            x = int(x)
                            y = int(y)
                            orig_contour = orig_page[y:y+h, x:x+w]
                            mod_contour = mod_page[y:y + h, x:x + w]
                            es = entropy_sim(orig_contour, mod_contour)
                            if es == 1.0 and not np.array_equal(orig_contour, mod_contour):
                                es = 0.0
                            if es <= ent_threshold:
                                results.append({'orig_file': orig_file,
                                                'mod_file': mod_file,
                                                'renderer': parser.get_name(),
                                                'page': page,
                                                'prc_sim': sim.sim})
                                break
                    except:
                        pass
        except:
            pass
    return results


def _parallel_highlight(data, overall_timeout, progress_bar, num_workers):
    if progress_bar:
        pbar = tqdm(total=len(data))
    results = []
    index = 0

    with ProcessPool(max_workers=num_workers, context=multiprocessing.get_context('spawn')) as pool:
        future = pool.map(_worker, data, timeout=overall_timeout or 600)

        iterator = future.result()

        while True:

            try:
                result = next(iterator)
            except StopIteration:
                result = None
                break
            except TimeoutError:
                result = None
            except Exception as e:
                result = None
            finally:
                if progress_bar:
                    pbar.update(1)
                index += 1
                if result is not None:
                    results.append(result)
        if progress_bar:
            pbar.close()

        return results


class Highlight:
    """Compares two PDF's with the same provenance and highlights regions of difference between their renders."""

    def __init__(self, renderers: List[Parser] or List[str] or str or Parser = get_sparclur_renderers(),
                 parser_args: Dict[str, Dict[str, Any]] = dict(),
                 max_workers: int = 1,
                 timeout: int = None,
                 overall_timeout: int = None,
                 progress_bar: bool = True):
        """

        Parameters
        ----------
        renderers: List[Parser] or List[str] or str or Parser
            A List of Parsers or their names or a single SPARCLUR parser or it's name
        parser_args: Dict[str, Dict[str, Any]]
            Specific arguments for the parsers
        max_workers: int
            The number of workers to allocate in the mutliprocessing pool for comparing the renders.
        timeout: int
            The number of seconds each tracer gets per file before timeing out.
        overall_timeout : int
            The number of seconds before the task is cancelled in the mutli-processing.
        progress_bar: bool
            Whether or not a progress bar should be displayed during message gathering.
        """

        self._renderers = _parse_renderers(renderers)
        self._parser_args = parser_args
        self._num_workers = max_workers
        self._timeout = timeout
        self._overall_timeout = overall_timeout
        self._progress_bar = progress_bar

    @property
    def renderers(self):
        return self._renderers

    @renderers.setter
    def renderers(self, r):
        self._renderers = _parse_renderers(r)

    @property
    def parser_args(self):
        return self._parser_args

    @property
    def max_workers(self):
        return self._num_workers

    @max_workers.setter
    def max_workers(self, mw):
        self._num_workers = mw

    @max_workers.deleter
    def max_workers(self):
        self._num_workers = 1

    @property
    def timeout(self):
        return self._timeout

    @timeout.setter
    def timeout(self, to):
        assert isinstance(to, int), "Timeout must be an int"
        self._timeout = to

    @timeout.deleter
    def timeout(self):
        self._timeout = None

    @property
    def overall_timeout(self):
        return self._overall_timeout

    @overall_timeout.setter
    def overall_timeout(self, ot):
        self._overall_timeout = ot

    @overall_timeout.deleter
    def overall_timeout(self):
        self._overall_timeout = None

    @property
    def progress_bar(self):
        return self._progress_bar

    @progress_bar.setter
    def set_progress_bar(self, p: bool):
        self._progress_bar = p

    def spot_the_difference(self, file_set: str or List[str],
                            matching_criteria: Dict[str, str] or Callable[[str], str],
                            dpi: int = 72,
                            min_region: int = 40,
                            prc_threshold: float = 1.0,
                            ent_threshold: float = 0.2,
                            recurse: bool = False,
                            extension: str = None,
                            base_path: str = None,
                            save_path: str = None):
        """

        Parameters
        ----------
        file_set: str or List[str]
            Path to a directory or a text file of PDF paths or a List of paths (or files if the base_path
            is defined). This are the modified files to be compared with the originators.
        matching_criteria: Dict[str, str] or Callable[[str], str]
            An explicit dictionary that maps every path in the file_set to the path of the originator file or a
            method that transforms each path string from file_set into the originator file path.
        dpi: int
            The dots-per-inch to set each renderer to.
        min_region: int
            The minimum region size for which differences are highlighted.
        prc_threshold: float
            A float, x, such that 0 < x <= 1.0. Indicates that regions should only be searched if the SPARCLUR PRC is
            less than this threshold. If it's set to 1.0 all files have their regions explored.
        ent_threshold: float
            The threshold for flagging a region as having a significant difference in information between the two
            regions.
        recurse : bool
            Whether or not the directory passed into the file_set parameter should be recursively searched for
            PDF's
        extension: str
            Filters out files that don't have the matching extension.
        base_path : str
            A base directory that should be appended to the list of files passed into file_set
        save_path: str
            If specified, will save a csv of the run results to save_path
        """

        mod_files = create_file_list(file_set, recurse=recurse, base_path=base_path, extension=extension)

        if isinstance(matching_criteria, dict):
            matched_files = [(mod_file, matching_criteria[mod_file]) for mod_file in mod_files]
        else:
            matched_files = [(mod_file, matching_criteria(mod_file)) for mod_file in mod_files]

        data = [{'orig': orig,
                 'mod_file': mod_file,
                 'timeout': self._timeout,
                 'dpi': dpi,
                 'min_region': min_region,
                 'prc_threshold': prc_threshold,
                 'ent_threshold': ent_threshold,
                 'renderers': self._renderers,
                 'parser_args': self._parser_args} for (mod_file, orig) in matched_files]

        if self._num_workers == 1:
            results = [_worker(entry) for entry in data]
        else:
            results = _parallel_highlight(data, self._overall_timeout, self._progress_bar, self._num_workers)

        df = pd.DataFrame(gen_flatten(results))

        if save_path is not None:
            df.to_csv(save_path, index=False)

        return df