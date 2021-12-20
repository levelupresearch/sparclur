from __future__ import annotations

import copy
import os
import shutil
import sys
import tempfile
from collections import defaultdict
from typing import List

import numpy as np
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor as Executor
from inspect import signature

import pandas as pd

from sparclur._parser import SparclurHash, TEXT, RENDER, META, REJECTED, REJECTED_AMBIG, VALID_WARNINGS, VALID, FONT, \
    TRACER
from sparclur.parsers import present_parsers

import seaborn as sns
import plotly


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

    def sim_sunburst(self, compare_orig: bool = True):
        data = []
        for parser in self._spotlight_result.keys():
            versions = list(self._spotlight_result[parser].keys())
            versions.remove('original')
            versions.sort()
            if compare_orig:
                versions.insert(0, 'original')
            for version in versions:
                vd = self._spotlight_result[parser][version]['comparisons']
                for v in [outer for outer in versions if outer != version]:
                    inner = version if version == 'original' else version + ' reforged'
                    outer = v if v == 'original' else v + ' reforged'
                    row = {'Parser': parser, 'inner': inner, 'outer': outer, 'sim': vd[v]['sim']}
                    data.append(row)
        df = pd.DataFrame(data)
        return df

    # def sim_sunburst(self, compare_orig: bool = True):
    #     data = []
    #     for parser in self._spotlight_result.keys():
    #         versions = list(self._spotlight_result[parser].keys())
    #         versions.remove('original')
    #         versions.sort()
    #         if compare_orig:
    #             versions.insert(0, 'original')
    #         for i in range(len(versions)):
    #             for j in range(i + 1, len(versions)):
    #                 version = versions[i]
    #                 v = versions[j]
    #                 vd = self._spotlight_result[parser][version]['comparisons']
    #                 inner = version if version == 'original' else version + ' reforged'
    #                 outer = v if v == 'original' else v + ' reforged'
    #                 row = {'Parser': parser, 'inner': inner, 'outer': outer, 'sim': vd[v]['sim']}
    #                 data.append(row)
    #     df = pd.DataFrame(data)
    #     return df

    # def _parser_heatmap(self, parser, sim):
    #     assert parser in self._spotlight_result, '%s not found' % parser
    #     versions = list(self._spotlight_result[parser].keys())
    #     versions.remove('original')
    #     versions.sort()
    #     versions.insert(0, 'original')
    #     d = []
    #     for version in versions:
    #         vd = self._spotlight_result[parser][version]['comparisons']
    #         row = dict()
    #         for v in versions:
    #             if v == version:
    #                 row[v] = 1.0
    #             else:
    #                 row[v] = vd[v].get(sim, -1.0)
    #         d.append(row)
    #     df = pd.DataFrame(d, index=versions)
    #     return df

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
            if report not in [RENDER+' sim', TRACER+' sim', TEXT+' sim', META+' sim', FONT+' sim']:
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
                    report: str = None,
                    detailed: bool = False,
                    compare_orig: bool = True,
                    height: int = 10,
                    width: int = 10,
                    save_display=None):

        d, columns, comparisons = self._create_heatmap(parsers, report, detailed, compare_orig)

        df = pd.DataFrame(d, columns=columns, index=['%s/%s' % (v1, v2) for v1, v2 in comparisons])

        if detailed:
            return sns.heatmap(df, vmin=.6, vmax=1, cmap='RdBu')
        else:
            return sns.heatmap(df, vmin=.6, vmax=1, annot=True, fmt=".2f", cmap='RdBu')

    # def sim_heatmap(self, detailed: bool = False,
    #                 height: int = 10,
    #                 width: int = 10,
    #                 save_display=None):
    #     sim = 'sim' if report == 'overall' else report
    #     dfs = dict()
    #     parsers = list(self._spotlight_result.keys())
    #     if isinstance(parser, str):
    #         if parser != 'all' and parser in parsers:
    #             run_these = [parser]
    #         else:
    #             run_these = parsers
    #     else:
    #         run_these = [p for p in parser if p in parsers]
    #
    #     if parser == 'all':
    #         for key in self._spotlight_result.keys():
    #             dfs[key] = self._parser_heatmap(key, sim)
    #     else:
    #         dfs[parser] = self._parser_heatmap(parser, sim)
    #     return dfs

    def recoverable(self, excluded_parsers=None, sim_threshold=0.9):
        if excluded_parsers is not None:
            if isinstance(excluded_parsers, str):
                excluded_parsers = [excluded_parsers]
        else:
            excluded_parsers = []
        if self.overall_validity('original') == VALID:
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

    def __init__(self, num_workers: int = 1,
                 temp_folders_dir: str = None,
                 dpi: int = 72,
                 parser_args: dict = dict(),
                 timeout: int = None,
                 progress_bar: bool = True):
        self._dpi = dpi
        self._num_workers = num_workers
        self._temp_folders_dir = temp_folders_dir
        self._parser_args = parser_args
        self._timeout = timeout
        self._results = None
        self._progress_bar = progress_bar

    def run(self, doc: str or bytes):
        spotlight_path = tempfile.TemporaryDirectory(dir=self._temp_folders_dir)
        for parser in present_parsers.get_sparclur_parsers():
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
            p = parser(**kwargs)
            try:
                for sub_folder in present_parsers.get_sparclur_parsers():
                    p.save_reforge(os.path.join(spotlight_path.name, sub_folder.get_name(), p.get_name() + '.pdf'))
            except Exception as e:
                print('%s reforge failed: %s' % (p.get_name(), str(e)))
        data = []
        for parser in present_parsers.get_sparclur_parsers():
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
        for parser in present_parsers.get_sparclur_parsers():
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
                map_results = executor.map(_mapper, data)

            distributor = defaultdict(list)
            for key, value in map_results:
                distributor[key].append(value)

            if self._progress_bar:
                reduced = list(tqdm(executor.map(_reducer, distributor.items()), total=len(distributor)))
            else:
                reduced = executor.map(_reducer, distributor.items())

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
                compare_map_results = executor.map(_combiner_mapper, compare_data)

            compare_distributor = defaultdict(list)
            for key, value in compare_map_results:
                compare_distributor[key].append(value)

            if self._progress_bar:
                result = list(tqdm(executor.map(_reducer, compare_distributor.items()), total=len(compare_distributor)))
            else:
                result = executor.map(_reducer, compare_distributor.items())

            full_spotlight = result[0]
            for r in result[1:]:
                full_spotlight.update(r)

        spotlight_path.cleanup()
        return full_spotlight


