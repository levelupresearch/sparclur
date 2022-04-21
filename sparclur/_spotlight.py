from __future__ import annotations

import copy
import os
import shutil
import tempfile
from collections import defaultdict
from typing import List, Union, Dict, Any, Tuple

import numpy as np
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor as Executor
from inspect import signature

import pandas as pd

from sparclur._parser import SparclurHash, TEXT, RENDER, META, REJECTED, REJECTED_AMBIG, VALID_WARNINGS, VALID, FONT, \
    TRACER
from sparclur.parsers import present_parsers
from sparclur._parser import Parser

import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px


def _merge_dict(d1, d2):
    if isinstance(d1, dict) and isinstance(d2, dict):
        new_dict = dict()
        keys = set().union(d1.keys()).union(d2.keys())
        for key in keys:
            new_dict[key] = _merge_dict(d1.get(key, dict()), d2.get(key, dict()))
        return new_dict
    else:
        if isinstance(d1, dict):
            return d2
        else:
            return d1


def _mapper(entry):
    base_path = entry['base_path']
    parser = entry['parser']
    version = entry['version']
    args = entry.get('args',
                     dict())

    args['doc'] = os.path.join(base_path, parser.get_name(), version + '.pdf')
    p = parser(**args)
    validity = p.validity
    sparclur_hash = p.sparclur_hash
    spotlight_result = SpotlightResult(p.get_name(), version, validity, sparclur_hash)

    return p.get_name(), spotlight_result


def _reducer(entry):
    (parser_name, spotlight_results) = entry
    spotlight_result = spotlight_results[0]
    for result in spotlight_results[1:]:
        spotlight_result.update(result)
    return spotlight_result


def _combiner_mapper(entry):
    parser = entry['parser']
    left_version = entry['left']
    right_version = entry['right']

    spotlight: SpotlightResult = entry['spotlight']
    spotlight._compare_hashes(parser, left_version, right_version)

    return parser, spotlight


class SpotlightResult:

    """
    Results from running Spotlight over a document. Provides the following methods:

    validity_report: Provide a table of validity results for the parsers over the original document and the reforges
    overall_validity: The overall validity classification for the document given the parsers
    recoverable: Returns whether or not the document is unambiguously recoverable
    sim_heatmap: A heatmap of the similarity scores for each parser over given pairs of documents
    sim_sunburst: A sunburst of the similarity scores. Provides an interactive way to engage with the heatmap.
    """
    def __init__(self, parser, version, validity, sparclur_hash):
        self._spotlight_result = {parser: {version: {'validity': validity, 'hash': sparclur_hash}}}

    def keys(self):
        return self._spotlight_result.keys()

    def __getitiem__(self, key):
        return self._spotlight_result[key]

    def __repr__(self):
        overall_validity = self.overall_validity()
        rep = 'PDF Validity: {validity}'.format(validity=overall_validity)
        if overall_validity != VALID:
            rep = rep + '\n%s' % self.recoverable()
        return rep

    def get(self, key, default):
        if key in self._spotlight_result:
            return self._spotlight_result[key]
        else:
            return default

    def update(self, that: SpotlightResult):
        new_spotlight = _merge_dict(self._spotlight_result, that._spotlight_result)
        self._spotlight_result = new_spotlight
        # parsers = set().union(self.keys()).union(that.keys())
        # for parser in parsers:
        #     if parser in self._spotlight_result:
        #         self._spotlight_result[parser].update(that._spotlight_result.get(parser, dict()))
        #     else:
        #         self._spotlight_result[parser] = that._spotlight_result[parser]

    @property
    def _parsers(self):
        return list(self._spotlight_result.keys())

    @property
    def _versions(self):
        v = set()
        for results in self._spotlight_result.values():
            v.update(results.keys())
        return list(v)

    def _compare_hashes(self, parser, left, right):
        if 'comparisons' in self._spotlight_result[parser][left]:
            right_in_left = right in self._spotlight_result[parser][left]['comparisons']
        else:
            self._spotlight_result[parser][left]['comparisons'] = dict()
            right_in_left = False
        if 'comparisons' in self._spotlight_result[parser][right]:
            left_in_right = left in self._spotlight_result[parser][right]['comparisons']
        else:
            self._spotlight_result[parser][right]['comparisons'] = dict()
            left_in_right = False
        if left_in_right and not right_in_left:
            comparison = self._spotlight_result[parser][right]['comparisons'][left]
            self._spotlight_result[parser][left]['comparisons'][right] = comparison
        if not left_in_right and right_in_left:
            comparison = self._spotlight_result[parser][left]['comparisons'][right]
            self._spotlight_result[parser][right]['comparisons'][left] = comparison
        if not left_in_right and not right_in_left:
            left_hash: SparclurHash = self._spotlight_result[parser][left]['hash']
            right_hash: SparclurHash = self._spotlight_result[parser][right]['hash']
            comparison = left_hash.compare(right_hash)
            self._spotlight_result[parser][left]['comparisons'][right] = comparison
            self._spotlight_result[parser][right]['comparisons'][left] = comparison

    def validity_report(self, report='overall', excluded_parsers=None):
        """
        Return a table of the validity classifications for each parser over each document.

        Parameters
        ----------
        report : {`overall`, `Renderer`, `Text Extraction`, `Font Extraction`, `Metadata Extraction`, `Tracer`}
            Overall takes into account all of the tools of the given parser, or a specific tool can be specified
        excluded_parsers : str or List[str]
            Parsers to exclude from the report

        Returns
        -------
        DataFrame
            A DataFrame of the resulting labels
        """
        if excluded_parsers is not None:
            if isinstance(excluded_parsers, str):
                excluded_parsers = [excluded_parsers]
        else:
            excluded_parsers = []
        parsers = [parser for parser in self._parsers if parser not in excluded_parsers]
        cols = self._versions
        cols.remove('original')
        cols.sort()
        cols.insert(0, 'original')
        d = []
        for parser in parsers:
            row = dict()
            for col in cols:
                row[col] = self._spotlight_result[parser].get(col, dict())\
                    .get('validity', dict())\
                    .get(report, dict())\
                    .get('status', None)
            d.append(row)
        row = dict()
        for col in cols:
            row[col] = self.overall_validity(col, excluded_parsers=excluded_parsers)
        d.append(row)
        parsers.append("Overall")
        df = pd.DataFrame(d, index=parsers)
        return df.dropna(how='all')

    def overall_validity(self, version='original', excluded_parsers=None):
        """
        Return a classification for the overall validity of the specified document

        Parameters
        ----------
        version : {`original`, `MuPDF`, `Poppler`, `Ghostscript`}
            The document version to classify
        excluded_parsers : str or List[str]
            Any parsers to exclude in the determination of the overall validity

        Returns
        -------
        str
            The validity label
        """
        if excluded_parsers is not None:
            if isinstance(excluded_parsers, str):
                excluded_parsers = [excluded_parsers]
        else:
            excluded_parsers = []
        assert max([version in v.keys() for v in self._spotlight_result.values()]), 'Version not found'
        validities = {result[version]['validity']['overall']['status']
                      for parser, result in self._spotlight_result.items() if parser not in excluded_parsers}
        if REJECTED in validities:
            return REJECTED
        elif REJECTED_AMBIG in validities:
            return REJECTED_AMBIG
        elif VALID_WARNINGS in validities:
            return VALID_WARNINGS
        else:
            return VALID

    def _sunburst_data(self, compare_orig, full):
        data = []
        for parser in self._spotlight_result.keys():
            versions = list(self._spotlight_result[parser].keys())
            versions.remove('original')
            versions.sort()
            if compare_orig:
                versions.insert(0, 'original')
            if full:
                for version in versions:
                    vd = self._spotlight_result[parser][version]['comparisons']
                    for v in [outer for outer in versions if outer != version]:
                        inner = version if version == 'original' else version + ' reforged'
                        outer = v if v == 'original' else v + ' reforged'
                        row = {'Parser': parser, 'inner': inner, 'outer': outer, 'sim': max(vd[v]['sim'], 0.001)}
                        data.append(row)
            else:
                for i in range(len(versions)):
                    for j in range(i + 1, len(versions)):
                        version = versions[i]
                        v = versions[j]
                        vd = self._spotlight_result[parser][version]['comparisons']
                        inner = version if version == 'original' else version + ' reforged'
                        outer = v if v == 'original' else v + ' reforged'
                        row = {'Parser': parser, 'inner': inner, 'outer': outer, 'sim': max(vd[v]['sim'], 0.001)}
                        data.append(row)
        df = pd.DataFrame(data)
        return df

    def sim_sunburst(self, compare_orig: bool = True,
                     full: bool = False,
                     color: str = 'RdBu',
                     color_range: List[float] = [.6, 1]):
        """
        Create an interactive sunburst for exploring the similarities between the documents for the Spotlight parsers

        Parameters
        ----------
        compare_orig : bool
            Whether reforge<->original comparison scores should be displayed in the heatmap. These comparisons don't
            impact the recoverablity of the file and would only provide insight into a differential between the original
            and the reforge
        full : bool
            Create the full sunburst that has all possible combinations. Turning this off removes duplicate comparisons
            to reduce the overall number of slices.
        color : str
            The color range to use. See https://plotly.com/python/builtin-colorscales/
        color_range : List[float]
            The range to base the color on. Format is [min, max]

        Returns
        -------
        Plotly Sunburst
        """
        df = self._sunburst_data(compare_orig, full)
        fig = px.sunburst(df,
                          path=['Parser', 'inner', 'outer'],
                          values='sim',
                          color='sim',
                          color_continuous_scale=color,
                          range_color=color_range)
        return fig

    def _create_heatmap(self, parsers, report, detailed, compare_orig):
        if parsers is None:
            parsers = list(self._spotlight_result.keys())
        elif isinstance(parsers, str):
            if parsers in self._spotlight_result:
                parsers = [parsers]
            else:
                parsers = list(self._spotlight_result.keys())
        elif isinstance(parsers, list):
            parsers = [p for p in parsers if p in self._spotlight_result]
            if len(parsers) == 0:
                parsers = list(self._spotlight_result.keys())

        if report is None:
            report = 'sim'
        else:
            if report not in [RENDER+' sim', TRACER+' sim', TEXT+' sim']:
                report = 'sim'

        all_versions = set()
        columns = []
        for parser, versions in [(k, v) for k, v in self._spotlight_result.items() if k in parsers]:
            all_versions.update(versions.keys())
            if not detailed:
                columns.append((parser, report))
            else:
                all_compares = set()
                for v, results in versions.items():
                    for compares in results['comparisons'].values():
                        score_names = [sn for sn in compares.keys() if 'sim' in sn and sn != 'sim']
                        all_compares.update(score_names)
                all_compares = list(all_compares)
                if len(all_compares) > 1:
                    all_compares.sort()
                    all_compares.append('sim')
                for score_name in all_compares:
                    columns.append((parser, score_name))
        all_versions.remove('original')
        all_versions = list(all_versions)
        all_versions.sort()
        if compare_orig:
            all_versions.insert(0, 'original')
        comparisons = []
        for i in range(len(all_versions)):
            for j in range(i+1, len(all_versions)):
                comparisons.append((all_versions[i], all_versions[j]))
        d = np.zeros((len(comparisons), len(columns)), dtype=float)
        for row_idx, comparison in enumerate(comparisons):
            for col_idx, col in enumerate(columns):
                d[row_idx, col_idx] = self._spotlight_result.get(col[0], None)\
                .get(comparison[0], None)\
                .get('comparisons', None)\
                .get(comparison[1], None)\
                .get(col[1], None)
        if not detailed:
            columns = ['%s %s' % (p, s) for p, s in columns]

        return d, columns, comparisons

    def sim_heatmap(self, parsers: str or List[str] = None,
                    report: str = 'sim',
                    annotated: bool = True,
                    detailed: bool = False,
                    compare_orig: bool = True,
                    height: int = 10,
                    width: int = 10,
                    save_display=None):
        """
        A heatmap of the similarity scores for each parser over given pairs of documents

        Parameters
        ----------
        parsers : str or List[str]
            The parsers to display the similarity scores for
        report : {'sim', 'Renderer sim', 'Text Extractor sim', 'Tracer sim'}
            The specific similarity score to run. Choose one of `sim`, `Renderer sim`, `Text Extractor sim` or
            `Tracer sim`
        annotated : bool, default=True
            Flag for whether or not similarity scores should be displayed on the heatmap
        detailed : bool, default=False
            Flag for displaying all similarity scores for each parser
        compare_orig : bool
            Whether reforge<->original comparison scores should be displayed in the heatmap. These comparisons don't
            impact the recoverablity of the file and would only provide insight into a differential between the original
            and the reforge
        height : int
            Height of the figure
        width : int
            Width of the figure
        save_display : str
            If not `None`, save a png of the figure to the file path specified by `save_display`

        Returns
        -------
        Seaborn heatmap
        """
        d, columns, comparisons = self._create_heatmap(parsers, report, detailed, compare_orig)

        df = pd.DataFrame(d, columns=columns, index=['%s/%s' % (v1, v2) for v1, v2 in comparisons])

        fig, ax = plt.subplots(figsize=(width, height))
        if not annotated:
            ax = sns.heatmap(df, vmin=.6, vmax=1, cmap='RdBu')
        else:
            ax = sns.heatmap(df, vmin=.6, vmax=1, annot=True, fmt=".2f", cmap='RdBu')
        if save_display is not None:
            fig.savefig(save_display)
            plt.close(fig)
        else:
            plt.close(fig)
            return fig

    def recoverable(self, excluded_parsers=None, sim_threshold=0.9):
        """
        Uses the spotlight results to determine if the document can be unambiguously recovered. The criteria is that
        each of the reforges successfully parses for each parser and further that the Sparclur Hash between the reforged
        documents is above the given threshold.

        Parameters
        ----------
        excluded_parsers : str or List[str]
            List of parsers to omit from the recoverable criteria
        sim_threshold : float
            The threshold to meet for the reforge comparisons. If a comparison falls below this threshold the recovery
            is said to be ambiguous

        Returns
        -------
        str
            The overall report for whether the original document is unambiguously recoverable or not
        """
        if excluded_parsers is not None:
            if isinstance(excluded_parsers, str):
                excluded_parsers = [excluded_parsers]
        else:
            excluded_parsers = []
        if self.overall_validity(version='original', excluded_parsers=excluded_parsers) == VALID:
            return "Document is Valid"
        else:
            versions = self._versions
            versions.remove('original')
            vv = {version: self.overall_validity(version, excluded_parsers) for version in versions}
            if not min([v == VALID for v in vv.values()]):
                problems = [version for (version, val) in vv.items() if val != VALID]
                s = "Recovery ambigous:"
                for problem in problems:
                    s = s + '\n\t%s: %s' % (problem, vv[problem])
                return s
            else:
                parsers = [parser for parser in self._parsers if parser not in excluded_parsers]
                data, columns, comparisons = self._create_heatmap(parsers, None, False, False)
                d = pd.DataFrame(data, columns=columns, index=['%s/%s' % (v1, v2) for v1, v2 in comparisons]).to_dict()
                ambiguities = 0
                s = "Recovery ambiguous:\n"
                for parser, comparisons in d.items():
                    parser = parser.replace(' sim', '')
                    for comparison, score in comparisons.items():
                        if score <= sim_threshold:
                            s = s + '\t{parser}: {compare} - {score:.2f}'.format(parser=parser, compare=comparison, score=score)
                            ambiguities = ambiguities + 1
                if ambiguities > 0:
                    return s
                else:
                    return "Unambiguously Recoverable"
            # for parser, results in self._spotlight_result.items():
            #     for key in results.keys():
            #         if key != 'validity' and key != 'hash':
            #             versions.add(key)
            # versions = versions.difference('original')


class Spotlight:
    """
    Runs all of the selected parsers over the document and also reforges the document with all available reforgers.
    The results are hashed and stored for analysis.
    """
    def __init__(self, num_workers: int = 1,
                 temp_folders_dir: str = None,
                 dpi: int = 72,
                 page_hashes: Union[int, Tuple, None] = None,
                 parsers: Union[List[str], None] = None,
                 parser_args: Dict[str, Dict[str, Any]] = dict(),
                 timeout: int = None,
                 progress_bar: bool = True):
        """
        Parameters
        ----------
        num_workers : int, default=1
            Spotlight is set-up to run the parsers in parallel. This determines the number of workers to use. If set
            to 1, the parsers will all be run serially.
        temp_folders_dir : str
            Path to create the temporary directories used for temporary files.
        dpi : int, default=72
            The resolution for the renders produced during processing.
        page_hashes : int, Tuple
            Specify specific pages to hash or a specific scheme for selecting page hashes. Tuple can be `('first', x)`
            where x is the number of pages or `('random', x, [seed])` where x is the number of pages and seed is
            optional.
        parsers : List[str], default=None
            Specify the parsers to run. Passing in `None` will use all available parsers.
        parser_args: dict
            Arguments to pass to the parser. Use the Parser name as the initial key for the dictionary args
        timeout: int
            Timeout for each parser run.
        progress_bar: bool, default=True
            Flag for displaying a progress bar
        """
        self._dpi = dpi
        self._page_hashes = page_hashes
        self._num_workers = num_workers
        self._temp_folders_dir = temp_folders_dir
        if parsers is not None and len(parsers) > 0:
            self._parsers: List[Parser] = [parser for parser in
                                           present_parsers.get_sparclur_parsers(check_parsers=True,
                                                                                parser_args=parser_args)
                                           if parser.get_name() in parsers]
        else:
            self._parsers: List[Parser] = [parser for parser in
                                           present_parsers.get_sparclur_parsers(check_parsers=True,
                                                                                parser_args=parser_args)]
        self._parser_args = parser_args
        self._timeout = timeout
        self._results = None
        self._progress_bar = progress_bar

    def run(self, doc: str or bytes):
        spotlight_path = tempfile.TemporaryDirectory(dir=self._temp_folders_dir)
        for parser in self._parsers:
            os.makedirs(os.path.join(spotlight_path.name, parser.get_name()))
            if isinstance(doc, str):
                shutil.copy2(doc, os.path.join(spotlight_path.name, parser.get_name(), 'original.pdf'))
            else:
                with open(os.path.join(spotlight_path.name, parser.get_name(), 'original.pdf'), 'rb') as orig_path:
                    doc.write(orig_path)
        for parser in present_parsers.get_sparclur_reforgers():
            sig = signature(parser.__init__)
            kwargs = {'doc': doc, 'timeout': 120, 'temp_folders_dir': self._temp_folders_dir}
            if 'dpi' in sig.parameters:
                kwargs['dpi'] = self._dpi
            if 'page_hashes' in sig.parameters:
                kwargs['page_hashes'] = self._page_hashes
            p = parser(**kwargs)
            try:
                for sub_folder in self._parsers:
                    p.save_reforge(os.path.join(spotlight_path.name, sub_folder.get_name(), p.get_name() + '.pdf'))
            except Exception as e:
                print('%s reforge failed: %s' % (p.get_name(), str(e)))
        data = []
        for parser in self._parsers:
            kwargs = self._parser_args.get(parser.get_name(), dict())
            kwargs['timeout'] = self._timeout
            kwargs['hash_exclude'] = [META, FONT]
            kwargs['temp_folders_dir'] = self._temp_folders_dir
            for file in os.listdir(os.path.join(spotlight_path.name, parser.get_name())):
                entry = {'base_path': spotlight_path.name, 'args': kwargs}
                version = file.split('.')[0]
                entry['parser'] = parser
                entry['version'] = version
                data.append(entry)

        parser_compares = []
        for parser in self._parsers:
            comparisons = set()
            versions = [file.split('.')[0] for file in os.listdir(os.path.join(spotlight_path.name, parser.get_name()))]
            for left in versions:
                for right in versions:
                    if left != right:
                        c = (left, right) if left < right else (right, left)
                        comparisons.add(c)
            for compare in list(comparisons):
                parser_compares.append({'parser': parser.get_name(), 'left': compare[0], 'right': compare[1]})

        with Executor(max_workers=self._num_workers) as executor:
            if self._progress_bar:
                map_results = list(tqdm(executor.map(_mapper, data), total=len(data)))
            else:
                map_results = list(executor.map(_mapper, data))

            distributor = defaultdict(list)
            for key, value in map_results:
                distributor[key].append(value)

            if self._progress_bar:
                reduced = list(tqdm(executor.map(_reducer, distributor.items()), total=len(distributor)))
            else:
                reduced = list(executor.map(_reducer, distributor.items()))

            spotlight = reduced[0]
            for r in reduced[1:]:
                spotlight.update(r)

            compare_data = [{'parser': entry['parser'],
                             'left': entry['left'],
                             'right': entry['right'],
                             'spotlight': copy.deepcopy(spotlight)}
                            for entry in parser_compares]

            if self._progress_bar:
                compare_map_results = list(tqdm(executor.map(_combiner_mapper, compare_data), total=len(compare_data)))
            else:
                compare_map_results = list(executor.map(_combiner_mapper, compare_data))

            compare_distributor = defaultdict(list)
            for key, value in compare_map_results:
                compare_distributor[key].append(value)

            if self._progress_bar:
                result = list(tqdm(executor.map(_reducer, compare_distributor.items()), total=len(compare_distributor)))
            else:
                result = list(executor.map(_reducer, compare_distributor.items()))

            full_spotlight = result[0]
            for r in result[1:]:
                full_spotlight.update(r)

        spotlight_path.cleanup()
        return full_spotlight


