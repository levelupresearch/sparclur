from collections import defaultdict
import random
from typing import List, Dict, Any
from inspect import isclass
from imagehash import dhash
import pandas as pd

from sparclur._parser import Parser
from sparclur._tracer import Tracer
from sparclur._renderer import Renderer
from sparclur._text_extractor import TextExtractor
from sparclur._metadata_extractor import MetadataExtractor
from sparclur._font_extractor import FontExtractor
from sparclur._image_data_extractor import ImageDataExtractor

from sparclur.parsers.present_parsers import get_sparclur_parsers, get_parser
from sparclur.utils import create_file_list, gen_flatten, stringify_dict

from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor as Executor
import mmh3


def _parse_parsers(parsers):
    """
    Parses the parsers to run for the non-deterministic detection.

    Parameters
    ----------
    parsers: str or List[str] or List[Parser]

    """
    available_parsers = [parser.get_name() for parser in get_sparclur_parsers()]
    result = []
    if isinstance(parsers, str):
        parsers = [parsers]
    for parser in parsers:
        if isinstance(parser, str):
            if parser in available_parsers:
                result.append(parser)
        elif isclass(parser):
            if issubclass(parser, Parser):
                result.append(parser.get_name())
        elif isinstance(parser, Parser):
            result.append(parser.get_name())
    return result


def _mapper(entry):
    path = entry['path']
    timeout = entry['timeout']
    parser_args = entry['parser_args']
    parser_class = get_parser(entry['parser'])
    result = dict()
    if issubclass(parser_class, Renderer):
        parser_args['dpi'] = 72
        parser_args['cache_renders'] = False
    parser = parser_class(doc=path, skip_check=True, timeout=timeout, **parser_args)
    if isinstance(parser, Renderer):
        try:
            renders = parser.get_renders()
            if len(renders) == 0:
                result['renderer'] = dict()
            else:
                result['renderer'] = {page: (pil.height, pil.width, dhash(pil, hash_size=16)) for (page, pil) in renders.items()}
        except Exception as e:
            result['renderer'] = {0: str(e)}
    if isinstance(parser, Tracer):
        try:
            messages = '\n'.join(parser.messages)
            result['tracer'] = mmh3.hash128(messages, seed=23)
        except Exception as e:
            result['tracer'] = str(e)
    if isinstance(parser, TextExtractor):
        try:
            tokens = parser.get_text()
            result['text'] = {page: mmh3.hash128(' '.join(tokes), seed=23) for (page, tokes) in tokens.items()}
        except Exception as e:
            result['text'] = {0: str(e)}
    if isinstance(parser, MetadataExtractor):
        try:
            meta = stringify_dict(parser.metadata)
            result['meta'] = mmh3.hash128(meta, seed=23)
        except Exception as e:
            result['meta'] = str(e)
    if isinstance(parser, FontExtractor):
        try:
            fonts = stringify_dict(parser.fonts)
            result['fonts'] = mmh3.hash128(fonts, seed=23)
        except Exception as e:
            result['fonts'] = str(e)
    if isinstance(parser, ImageDataExtractor):
        try:
            images = stringify_dict(parser.images)
            result['images'] = mmh3.hash128(images, seed=23)
        except Exception as e:
            result['images'] = str(e)
    return (path, parser.get_name()), result


def _reducer(entry):
    ((path, parser_name), results) = entry
    overall_result = {'path': path, 'parser': parser_name}
    identical = True
    for i in range(len(results)-1):
        left = results[i]
        right = results[i+1]
        for parser_type in left.keys():
            currently_match = overall_result.get(parser_type, True)
            left_vs_right = left[parser_type] == right[parser_type]
            overall_result[parser_type] = currently_match and left_vs_right
        identical = identical and (results[i] == results[i+1])
    overall_result['non_determinism'] = not identical
    return overall_result


class DetectChaos:
    """
    Looks for evidence of non-determinism in PDF parsers.
    """
    def __init__(self, parsers: str or List[Parser] or List[str],
                 num_comparisons: int = 5,
                 parser_args: Dict[str, Dict[str, Any]] = dict(),
                 parser_timeout: int = 120,
                 overall_timeout: int = 600,
                 num_workers: int = 1,
                 progress_bar: bool = True
                 ):
        """
        Parameters
        ----------
        parsers: List[Parser] or List[str]
            List of parsers to run through non-determinism detection
        parser_args: Dict[str, Dict[str, Any]]
            Parser specific arguments to pass
        parser_timeout: int
            The timeout for each parser tested.
        overall_timeout: int
            The timeout for the process pool workers if using more than one worker.
        num_workers: int
            The number of workers to use. Select 1 to run without multiprocessing.
        progress_bar: bool
            Whether or not to show the progress bar for the testing.
        """

        self._num_comparisons = num_comparisons
        self._parsers = _parse_parsers(parsers)
        self._parser_args = parser_args
        self._parser_timeout = parser_timeout
        self._overall_timeout = overall_timeout
        self._num_workers = num_workers
        self._progress_bar = progress_bar

    @property
    def num_comparisons(self):
        return self._num_comparisons

    @num_comparisons.setter
    def num_comparisons(self, nc):
        self._num_comparisons = nc

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
    def parser_timeout(self):
        return self._parser_timeout

    @overall_timeout.setter
    def parser_timeout(self, pt):
        self._parser_timeout = pt

    @overall_timeout.deleter
    def parser_timeout(self):
        self._parser_timeout = None

    @property
    def parsers(self):
        return [parser.get_name() for parser in self._parsers]

    @parsers.setter
    def parsers(self, parsers: List[str] or List[Parser]):
        self._parsers = _parse_parsers(parsers)

    @property
    def parser_args(self):
        return self._parser_args

    @parser_args.setter
    def parser_args(self, pa: Dict[str, Dict[str, Any]]):
        self._parser_args = pa

    @parser_args.deleter
    def parser_args(self):
        self._parser_args = dict()

    @property
    def num_workers(self):
        return self._num_workers

    @num_workers.setter
    def num_workers(self, nw):
        self._num_workers = nw

    @property
    def progress_bar(self):
        return self._progress_bar

    @progress_bar.setter
    def progress_bar(self, pb):
        self._progress_bar = pb

    def run(self, files, recurse=False, base_path=None, save_path=None):
        """
        Run the non-deterministic detection.

        Parameters
        ----------
        files : str or List[str]
            Path to a directory or a text file of PDF paths or a List of paths
        recurse : bool
            Whether or not the directory passed into the files parameter should be recursively searched for PDF's
        base_path : str
            A base directory that should be appended to the list of paths passed into files
        """

        files = create_file_list(files, recurse=recurse, base_path=base_path)
        transformed_data = gen_flatten(
            [
                [
                    {'path': path,
                     'parser': parser,
                     'timeout': self._parser_timeout,
                     'parser_args': self._parser_args.get(parser, dict())}
                    for parser in self._parsers
                ]
                for path in files
            ]
        ) * self._num_comparisons
        random.shuffle(transformed_data)
        with Executor(max_workers=self._num_workers) as executor:
            if self._progress_bar:
                map_results = list(tqdm(executor.map(_mapper, transformed_data), total=len(transformed_data)))
            else:
                map_results = executor.map(_mapper, transformed_data)

            distributor = defaultdict(list)
            for key, value in map_results:
                distributor[key].append(value)

            if self._progress_bar:
                reduced = list(tqdm(executor.map(_reducer, distributor.items()), total=len(distributor)))
            else:
                reduced = executor.map(_reducer, distributor.items())

        df = pd.DataFrame(reduced)
        if save_path is not None:
            df.to_csv(save_path, index=False)
        return df
