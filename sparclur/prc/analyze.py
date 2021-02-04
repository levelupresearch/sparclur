import itertools

from sparclur._ssim_result import SSIM
from sparclur.parsers.present_parsers import get_sparclur_renderers
from sparclur.prc._prc import _parse_renderers
from sparclur.utils.tools import create_file_list, get_num_pages, gen_flatten
from tqdm import tqdm
from pebble import ProcessPool
import os


class Analyzer:
    """Runs pairwise comparisons for the defined renderers over each page of the specified document list or directory"""
    def __init__(self, files, renderers=get_sparclur_renderers(), parser_args=dict(), max_workers=1, timeout=None,
                 recurse=False, base_path=None,  progress_bar=True):
        """

        Parameters
        ----------
        files : str or List[str]
            Path to a directory or a text file of PDF paths or a List of paths
        renderers : List[str] or List[Renderer]
            The desired renderers to compare. Must select at least 2 renderers. Default is all SPARCLUR renderers.
        parser_args : Dict[str, Dict[str, Any]]
            A dictionary of dictionaries containing any optional parameters to pass into the renderers. See an each
            renderer for it's possible parameters.
        max_workers : int
            The desired number of workers for the mutli-processing.
        timeout : int
            The number of seconds before the task is cancelled in the mutli-processing.
        recurse : bool
            Whether or not the directory passed into the files parameter should be recursively searched for PDF's
        base_path : str
            A base directory that should be appended to the list of paths passed into files
        progress_bar : bool
            Whether or not to display a progress bar
        """
        self._renderers = _parse_renderers(renderers)
        self._parser_args = parser_args
        self._files = create_file_list(files, recurse=recurse, base_path=base_path)
        self._max_workers = max_workers
        self._timeout = timeout
        self._progress_bar = progress_bar

    def get_max_workers(self):
        """Return the set number of max workers"""
        return self._max_workers

    def set_max_workers(self, m):
        """Set a new number of max workers"""
        self._max_workers = m

    def get_timeout(self):
        """Return the set timeout value"""
        return self._timeout

    def set_timeout(self, t):
        """Set a new timeout parameter"""
        self._timeout = t

    def get_renderer_list(self):
        """List of the renderers to be compared"""
        return list(self._renderers.keys())

    def get_progress_bar(self):
        """Return the progress bar setting"""
        return self._progress_bar

    def set_progress_bar(self, p: bool):
        """Set whether or not to show progress bar"""
        self._progress_bar = p

    def run(self):
        """
        Return the comparisons for each page of each document from the file list
        Returns
        -------
        List[Dict[str, Any]]
        """
        if self._progress_bar:
            pbar = tqdm(total=len(self._files))
        results = []
        index = 0

        with ProcessPool(max_workers=self._max_workers) as pool:
            future = pool.map(self._prc_worker, self._files, timeout=self._timeout)

            iterator = future.result()

            while True:
                try:
                    result = next(iterator)
                except StopIteration:
                    result = None
                    break
                except TimeoutError as error:
                    file = self._files[index]
                    e = 'PRC Timed Out'
                    result = self._error_result(file, e)
                except Exception as error:
                    file = self._files[index]
                    e = str(error)
                    result = self._error_result(file, e)
                finally:
                    if self._progress_bar:
                        pbar.update(1)
                    index += 1
                    if result is not None:
                        results.append(result)
        if self._progress_bar:
            pbar.close()
        return gen_flatten(results)

    def _prc_worker(self, path):
        file = path.split(os.path.sep)[-1]
        result = {'file': file, 'path': path}
        renders = dict()
        for (name, renderer) in self._renderers.items():
            args = self._parser_args.get(name, dict())
            args['verbose'] = True
            args['cache_renders'] = True
            renders[name] = renderer(doc_path=path, **args)
        num_pages = get_num_pages(path)
        if num_pages == 0:
            observed_pages = []
            for renderer in renders.values():
                r = renderer.get_renders()
                observed_pages.append(len(r))
            num_pages = max(observed_pages)
        overall_result = []
        for i in range(num_pages):
            i_result = {key: val for (key, val) in result.items()}
            i_result['page'] = i
            for (name, renderer) in renders.items():
                renderer.get_renders(i)
                page_log = renderer.get_logs().get(i, dict())
                i_result['%s_render' % name] = page_log.get('result', None)
                i_result['%s_timing' % name] = page_log.get('timing', None)
            for combo in itertools.combinations(renders.keys(), 2):
                col_name = '%s_%s' % (combo[0], combo[1])
                ssim_result: SSIM = renders[combo[0]].compare(renders[combo[1]], page=i, full=False)
                i_result['%s_ssim' % col_name] = ssim_result.ssim
                i_result['%s_result' % col_name] = ssim_result.result
            overall_result.append(i_result)
        return overall_result

    def _error_result(self, path, error):
        file = path.split(os.path.sep)[-1]
        d = {'file': file, 'path': path, 'page': None}
        renderers = self._renderers.keys()
        combos = itertools.combinations(renderers, 2)
        for renderer in renderers:
            d['%s_render' % renderer] = error
            d['%s_timing' % renderer] = None
        for combo in combos:
            col_name = '%s_%s' % (combo[0], combo[1])
            d['%s_ssim' % col_name] = None
            d['%s_result' % col_name] = error
        return d
