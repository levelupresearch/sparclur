import itertools

from func_timeout import func_timeout, FunctionTimedOut

from sparclur._parser import REJECTED_AMBIG
from sparclur._prc_sim import PRCSim
from sparclur.parsers.present_parsers import get_sparclur_renderers
from sparclur.prc._prc import _parse_renderers
from sparclur.utils._tools import create_file_list, gen_flatten
from tqdm import tqdm
from pebble import ProcessPool
from concurrent.futures import TimeoutError
import os
import pandas as pd

AVAILABLE_RENDERERS = {r.get_name(): r for r in get_sparclur_renderers()}
AVAILABLE_METRICS = ['sim',
                     'entropy_sim',
                     'whash_sim',
                     'phash_sim',
                     'sum_square_sim',
                     'ccorr_sim',
                     'ccoeff_sim',
                     'size_sim'
                     ]


def _prc_worker(entry):
    path = entry['path']
    file = path.split(os.path.sep)[-1]
    renderers = {renderer: AVAILABLE_RENDERERS[renderer] for renderer in entry['renderers']}
    metrics = entry['metrics']
    parser_args = entry['parser_args']
    timeout = entry['timeout']
    result = {'file': file, 'path': path}
    renders = dict()
    for (name, renderer) in renderers.items():
        args = parser_args.get(name, dict())
        args['cache_renders'] = True
        args['timeout'] = timeout
        renders[name] = renderer(doc=path, skip_check=True, **args)
    observed_pages = []
    for renderer in renders.values():
        r = renderer.get_renders()
        observed_pages.append(len(r))
    num_pages = max(max(observed_pages), 1)
    overall_result = []
    for i in range(num_pages):
        i_result = {key: val for (key, val) in result.items()}
        i_result['page'] = i
        for (name, renderer) in renders.items():
            renderer.get_renders(i)
            page_log = renderer.logs[i]
            i_result['%s_render' % name] = page_log.get('result', None)
            i_result['%s_timing' % name] = page_log.get('timing', None)
            i_result['%s_status' % name] = renderer.validate_renderer['status']
        for combo in itertools.combinations(renders.keys(), 2):
            col_name = '%s_%s' % (combo[0], combo[1]) if combo[0] < combo[1] else '%s_%s' % (combo[1], combo[0])
            sim_result: PRCSim = renders[combo[0]].compare(renders[combo[1]], page=i, full=False)
            sim_metrics = sim_result.all_metrics
            for metric in metrics:
                i_result['%s_%s' % (col_name, metric)] = sim_metrics[metric]
            # i_result['%s_sim' % col_name] = ssim_result.sim
            i_result['%s_result' % col_name] = sim_result.result
        overall_result.append(i_result)
    return overall_result


def _error_result(path, error, renderers, metrics):
    file = path.split(os.path.sep)[-1]
    d = {'file': file, 'path': path, 'page': 0}
    combos = itertools.combinations(renderers, 2)
    for renderer in renderers:
        d['%s_render' % renderer] = error
        d['%s_timing' % renderer] = None
        d['%s_status' % renderer] = REJECTED_AMBIG
    for combo in combos:
        col_name = '%s_%s' % (combo[0], combo[1]) if combo[0] < combo[1] else '%s_%s' % (combo[1], combo[0])
        for metric in metrics:
            d['%s_%s' % (col_name, metric)] = None
        d['%s_result' % col_name] = error
    return [d]


def _parallel_prc(files, progress_bar, max_workers, overall_timeout, renderers, metrics):
    if progress_bar:
        pbar = tqdm(total=len(files))
    results = []
    index = 0

    with ProcessPool(max_workers=max_workers) as pool:
        future = pool.map(_prc_worker, files, timeout=overall_timeout)

        iterator = future.result()

        while True:
            try:
                result = next(iterator)
            except StopIteration:
                result = None
                break
            except TimeoutError:
                file = files[index]['path']
                e = 'PRC Timed Out'
                result = _error_result(file, e, renderers, metrics)
            except Exception as error:
                file = files[index]['path']
                e = str(error)
                result = _error_result(file, e, renderers, metrics)
            finally:
                if progress_bar:
                    pbar.update(1)
                index += 1
                if result is not None:
                    results.append(result)
    if progress_bar:
        pbar.close()
    return gen_flatten(results)


def _serial_prc(files, progress_bar, compare_timeout, renderers, metrics):
    results = []

    if progress_bar:
        pbar = tqdm(total=len(files))
    for entry in files:
        try:
            result = func_timeout(
                compare_timeout,
                _prc_worker,
                kwargs={
                    'entry': entry
                }
            )
        except FunctionTimedOut:
            error = 'PRC Timed Out'
            result = _error_result(entry['path'], error, renderers, metrics)
        except Exception as e:
            error = str(e)
            result = _error_result(entry['path'], error, renderers, metrics)
        results.append(result)
        if progress_bar:
            pbar.update(1)
    if progress_bar:
        pbar.close()
    return gen_flatten(results)


def _set_metrics(m):
    if isinstance(m, str):
        if m == 'all':
            metrics = AVAILABLE_METRICS
        else:
            assert m in AVAILABLE_METRICS, \
                "Please select one or more of the available metrics: %s" % ', '.join(AVAILABLE_METRICS)
            metrics = [m]
    elif isinstance(m, list):
        metrics = AVAILABLE_METRICS.intersection(m)
        assert len(metrics) != 0, \
            "Please select one or more of the available metrics: %s" % ', '.join(AVAILABLE_METRICS)
    return metrics


class Analyzer:
    """Runs pairwise comparisons for the defined renderers over each page of the specified document list or directory"""

    def __init__(self, files,
                 renderers=get_sparclur_renderers(),
                 metrics='sim',
                 parser_args=dict(),
                 max_workers=1,
                 timeout=None,
                 overall_timeout=None,
                 recurse=False,
                 base_path=None,
                 progress_bar=True,
                 save_path=None):
        """

        Parameters
        ----------
        files : str or List[str]
            Path to a directory or a text file of PDF paths or a List of paths
        renderers : List[str] or List[Renderer]
            The desired renderers to compare. Must select at least 2 renderers. Default is all SPARCLUR renderers.
        metrics: str or List[str]
            List of metrics to return in the final results. Default is just the SPARCLUR similarity score. Full list:
            whash, phash, size, sum_square, ccorr, ccoeff, entropy
            Use 'all' to do the full set.
        parser_args : Dict[str, Dict[str, Any]]
            A dictionary of dictionaries containing any optional parameters to pass into the renderers. See an each
            renderer for it's possible parameters.
        max_workers : int
            The desired number of workers for the mutli-processing.
        timeout : int
            The number of seconds each parser is given to render the document and the time for each page comparison.
        overall_timeout : int
            The number of seconds before the task is cancelled in the mutli-processing.
        recurse : bool
            Whether or not the directory passed into the files parameter should be recursively searched for PDF's
        base_path : str
            A base directory that should be appended to the list of paths passed into files
        progress_bar : bool
            Whether or not to display a progress bar
        save_path: str
            If specified, will save a csv of the run results to save_path
        """
        self._renderers = _parse_renderers(renderers)
        self._metrics = _set_metrics(metrics)
        self._parser_args = parser_args
        self._files = create_file_list(files, recurse=recurse, base_path=base_path)
        self._max_workers = max_workers
        self._timeout = timeout
        self._overall_timeout = overall_timeout
        self._progress_bar = progress_bar
        self._save_path = save_path

    @property
    def max_workers(self):
        """Return the set number of max workers"""
        return self._max_workers

    @max_workers.setter
    def max_workers(self, m):
        """Set a new number of max workers"""
        self._max_workers = m

    @property
    def overall_timeout(self):
        """Return the set timeout value"""
        return self._overall_timeout

    @overall_timeout.setter
    def compare_timeout(self, t):
        """Set a new timeout parameter"""
        self._overall_timeout = t

    @compare_timeout.deleter
    def overall_timeout(self):
        self._overall_timeout = None

    @property
    def timeout(self):
        """Return the set timeout value"""
        return self._timeout

    @timeout.setter
    def parser_timeout(self, t):
        """Set a new timeout parameter"""
        self._timeout = t

    @parser_timeout.deleter
    def timeout(self):
        self._timeout = None

    @property
    def renderer_list(self):
        """List of the renderers to be compared"""
        return self._renderers

    @renderer_list.setter
    def renderer_list(self, rl):
        self._renderers = _parse_renderers(rl)

    @property
    def metrics(self):
        """List of the metrics to be returned"""
        return self._metrics

    @metrics.setter
    def metrics(self, m):
        self._metrics = _set_metrics(m)

    @property
    def progress_bar(self):
        """Return the progress bar setting"""
        return self._progress_bar

    @progress_bar.setter
    def progress_bar(self, p: bool):
        """Set whether or not to show progress bar"""
        self._progress_bar = p

    @progress_bar.deleter
    def progress_bar(self):
        self._progress_bar = False

    @property
    def save_path(self):
        return self._save_path

    @save_path.setter
    def save_path(self, sp):
        self._save_path = sp

    @save_path.deleter
    def save_path(self):
        self._save_path = None

    def run(self):
        """
        Return the comparisons for each page of each document from the file list
        Returns
        -------
        List[Dict[str, Any]]
        """
        transformed_data = [
            {'path': path,
             'renderers': self._renderers,
             'parser_args': self._parser_args,
             'timeout': self._timeout,
             'metrics': self._metrics}
            for path in self._files
        ]
        if self._max_workers == 1:
            results = _serial_prc(files=transformed_data,
                                  progress_bar=self._progress_bar,
                                  compare_timeout=self._overall_timeout,
                                  renderers=self._renderers,
                                  metrics=self._metrics
                                  )
        else:
            results = _parallel_prc(files=transformed_data,
                                    progress_bar=self._progress_bar,
                                    max_workers=self._max_workers,
                                    overall_timeout=self._overall_timeout,
                                    renderers=self._renderers,
                                    metrics=self._metrics
                                    )

        if self._save_path is not None:
            pd.DataFrame(results).to_csv(path_or_buf=self._save_path, index=False)
        else:
            return results
