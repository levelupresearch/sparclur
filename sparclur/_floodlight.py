from __future__ import annotations

import multiprocessing
from typing import List, Union, Tuple

from tqdm import tqdm
from pebble import ProcessPool
from inspect import signature

import pandas as pd

from sparclur._parser import VALID
from sparclur._reforge import Reforger
from sparclur._tracer import Tracer
from sparclur.parsers import present_parsers
from sparclur._parser import Parser


AMBIGUOUS = 'Ambiguous'
RECOVERABLE = 'Recoverable'
FAILED = 'Failed'

# def _overall_validity(parsers, doc, parser_args):
#
#     validities = set([parser(doc, **parser_args.get(parser.get_name(), dict())).validity['overall']['status'] for parser in parsers])
#     if REJECTED in validities:
#         overall = REJECTED
#     elif REJECTED_AMBIG in validities:
#         overall = REJECTED_AMBIG
#     elif VALID_WARNINGS in validities:
#         overall = VALID_WARNINGS
#     else:
#         overall = VALID
#     return overall


def _error_result(doc, reason):

    return {'path': doc, 'status': FAILED, 'reason': reason, 'traces': set()}


def _parallel_floodlight(docs, overall_timeout, progress_bar, num_workers):
    if progress_bar:
        pbar = tqdm(total=len(docs))
    results = []
    index = 0

    with ProcessPool(max_workers=num_workers, context=multiprocessing.get_context('spawn')) as pool:

        future = pool.map(_recoverable, docs, timeout=overall_timeout or 600)

        iterator = future.result()

        while True:

            try:
                result = next(iterator)
            except StopIteration:
                result = None
                break
            except TimeoutError:
                entry = docs[index]
                doc = entry['path']
                e = 'File Timed Out'
                result = _error_result(doc, e)
            except Exception as error:
                entry = docs[index]
                doc = entry['path']
                e = str(error)
                result = _error_result(doc, e)
            finally:
                if progress_bar:
                    pbar.update(1)
                index += 1
                if result is not None:
                    results.append(result)
    if progress_bar:
        pbar.close()
    return results


def _serial_floodlight(docs, progress_bar):

    if progress_bar:
        pbar = tqdm(total=len(docs))

    results = []
    for entry in docs:
        try:
            result = _recoverable(entry)
        except Exception as e:
            doc = entry['path']
            e = str(e)
            result = _error_result(doc, e)
        finally:
            if progress_bar:
                pbar.update(1)
            results.append(result)
    if progress_bar:
        pbar.close()
    return results


def _recoverable(entry):
    doc_path = entry['path']
    parsers = entry['parsers']
    translators = entry['translators']
    parser_args = entry['parser_args']
    gather_traces = entry['gather_traces']

    is_valid = True
    traces = set()
    for parser in parsers:
        p = parser(doc_path, **parser_args.get(parser.get_name(), dict()))
        if p.validity['overall']['status'] != VALID:
            is_valid = False
            if not gather_traces:
                break
        if issubclass(parser, Tracer) and gather_traces:
            traces.update({'%s::%s' % (parser.get_name(), trace) for trace in p.cleaned.keys()})

    if is_valid:
        status = VALID
        reason = 'Original Valid'
    else:
        status = RECOVERABLE
        reason = 'All translations valid'
        for translator in translators:
            tr_valid = True
            translation = translator(doc_path, **parser_args.get(translator.get_name(), dict())).reforge
            if translation is None:
                status = AMBIGUOUS
                reason = '%s translation failed' % translator.get_name()
                break
            for parser in parsers:
                p = parser(translation, **parser_args.get(parser.get_name(), dict()))
                if p.validity['overall']['status'] != VALID:
                    status = AMBIGUOUS
                    reason = '%s translation failed for %s' % (translator.get_name(), parser.get_name())
                    tr_valid = False
                    break
            if not tr_valid:
                break
    return {'path': doc_path, 'status': status, 'reason': reason, 'traces': traces}


# def _overall_validity(validities):
#
#     validities = set(validities)
#     if REJECTED in validities:
#         overall = REJECTED
#     elif REJECTED_AMBIG in validities:
#         overall = REJECTED_AMBIG
#     elif VALID_WARNINGS in validities:
#         overall = VALID_WARNINGS
#     else:
#         overall = VALID
#     return overall
#
#
# def _get_single_validity(entry):
#     doc_path = entry['path']
#     parser = entry['parser']
#     translation = entry['translation']
#     parser_args = entry['parser_args']
#     gather_traces = entry['gather_traces']
#
#     if translation == 'original':
#         t = 'original'
#         p = parser(doc_path, **parser_args.get(parser.get_name(), dict()))
#         if issubclass(parser, Tracer) and gather_traces:
#             traces = {'%s::%s' % (parser.get_name(), trace) for trace in p.cleaned.keys()}
#         else:
#             traces = set()
#         validity = p.validity['overall']['status']
#     else:
#         t = translation.get_name()
#         translation = translation(doc_path).reforge
#         if translation:
#             validity = parser(translation, **parser_args.get(parser.get_name(), dict())).validity['overall']['status']
#         else:
#             validity = REJECTED
#         traces = set()
#
#     return (doc_path, t), {'validity': validity, 'traces': traces}
#
#
# def _get_overall_validities(entry):
#     ((doc_path, translation), results) = entry
#     validities = []
#     traces = set()
#     for result in results:
#         validities.append(result['validity'])
#         traces.update(result['traces'])
#     overall = _overall_validity(validities)
#     return doc_path, {'translation': translation, 'validity': overall, 'traces': traces}
#
#
# def _get_recoverable(entry):
#     doc_path, results = entry
#     is_valid = False
#     recoverable = True
#     failed_translations = []
#     traces = set()
#     for result in results:
#         if result['translation'] == 'original':
#             is_valid = result['validity'] == VALID
#             traces = result['traces']
#         else:
#             recovered = result['validity'] == VALID
#             recoverable = recoverable and recovered
#             if not recovered:
#                 failed_translations.append(result['translation'])
#     if is_valid:
#         status = VALID
#         reason = 'Original Valid'
#     elif recoverable:
#         status = RECOVERABLE
#         reason = 'All translations valid'
#     else:
#         status = AMBIGUOUS
#         reason = 'These translations failed: [%s]' % ', '.join(failed_translations)
#
#     return {'path': doc_path, 'status': status, 'reason': reason, 'traces': traces}


    # orig_validity = _overall_validity(parsers, doc_path, parser_args)
    #
    # if orig_validity == VALID:
    #     result = {'status': VALID, 'reason': 'Original Valid'}
    # else:
    #     mupdf_doc = MuPDF(doc_path).reforge
    #     mupdf_validity = _overall_validity(parsers, mupdf_doc, parser_args)
    #     if mupdf_validity != VALID:
    #         result = {'status': AMBIGUOUS, 'reason': 'MuPDF: %s' % mupdf_validity}
    #     else:
    #         ghost_doc = Ghostscript(doc_path).reforge
    #         ghost_validity = _overall_validity(parsers, ghost_doc, parser_args)
    #         if ghost_validity !=VALID:
    #             result = {'status': AMBIGUOUS, 'reason': 'GS: %s' % ghost_validity}
    #         else:
    #             pop_doc = Poppler(doc_path).reforge
    #             pop_validity = _overall_validity(parsers, pop_doc, parser_args)
    #             if pop_validity != VALID:
    #                 result = {'status': AMBIGUOUS, 'reason': 'Poppler: %s' % pop_validity}
    #             else:
    #                 result = {'status': RECOVERABLE, 'reason': 'All translations valid'}
    # return result


class FloodLight:

    def __init__(self, parsers=None,
                 translators=None,
                 parser_args=dict(),
                 gather_traces: bool = True,
                 num_workers: int = 1,
                 overall_timeout: int = 300,
                 timeout: int = 45,
                 dpi: int = 72,
                 page_hashes: Union[int, Tuple, None] = ('first', 5),
                 validate_hash: Union[bool, None] = True,
                 temp_folders_dir: str = None,
                 progress_bar: bool = True):

        self._gather_traces = gather_traces
        self._dpi = dpi
        self._page_hashes = page_hashes
        self._validate_hash = validate_hash
        self._num_workers = num_workers
        self._overall_timeout = overall_timeout
        self._temp_folders_dir = temp_folders_dir
        if parsers is not None:
            self._parsers: List[Parser] = [parser for parser in
                                           present_parsers.get_sparclur_parsers(check_parsers=True,
                                                                                parser_args=parser_args)
                                           if parser.get_name() in parsers]
        else:
            self._parsers: List[Parser] = [parser for parser in
                                           present_parsers.get_sparclur_parsers(check_parsers=True,
                                                                                parser_args=parser_args)]
        if translators is not None:
            self._translators: List[Parser] = [parser for parser in
                                               present_parsers.get_sparclur_parsers(check_parsers=True,
                                                                                    parser_args=parser_args)
                                               if issubclass(parser, Reforger) and parser.get_name() in translators]
        else:
            self._translators: List[Parser] = [parser for parser in
                                               present_parsers.get_sparclur_parsers(check_parsers=True,
                                                                                    parser_args=parser_args)
                                               if issubclass(parser, Reforger)]
        self._parser_args = parser_args
        self._timeout = timeout
        self._progress_bar = progress_bar

    def run(self, docs,
            save_path=None):

        for parser in self._parsers:
            params = signature(parser.__init__).parameters
            kwargs = self._parser_args.get(parser.get_name(), dict())
            kwargs['timeout'] = self._timeout
            kwargs['temp_folders_dir'] = self._temp_folders_dir
            kwargs['skip_check'] = True
            if 'dpi' in params:
                kwargs['dpi'] = self._dpi
            if 'page_hashes' in params:
                kwargs['page_hashes'] = self._page_hashes
            if 'validate_hash' in params:
                kwargs['validate_hash'] = self._validate_hash
            self._parser_args[parser] = kwargs

        data = [{'path': doc,
                 'parsers': self._parsers,
                 'translators': self._translators,
                 'parser_args': self._parser_args,
                 'gather_traces': self._gather_traces}
                for doc in docs]

        if self._num_workers > 1:
            recoverable = _parallel_floodlight(data, self._overall_timeout, self._progress_bar, self._num_workers)
        else:
            recoverable = _serial_floodlight(data, self._progress_bar)

        df = pd.DataFrame(recoverable)
        if not self._gather_traces:
            df.drop(columns=['traces'], inplace=True)

        if save_path:
            df.to_csv(save_path, index=False)

        return df

        # with Executor(max_workers=self._num_workers) as executor:
        #     if self._progress_bar:
        #         single_validities = list(tqdm(executor.map(_get_single_validity, data), total=len(data)))
        #     else:
        #         single_validities = list(executor.map(_get_single_validity, data))
        #
        #     distributor = defaultdict(list)
        #     for key, value in single_validities:
        #         distributor[key].append(value)
        #
        #     if self._progress_bar:
        #         overall_validity = list(
        #             tqdm(
        #                 executor.map(_get_overall_validities, distributor.items()),
        #                 total=len(distributor)
        #             )
        #         )
        #     else:
        #         overall_validity = list(executor.map(_get_overall_validities, distributor.items()))
        #
        #     second_distributor = defaultdict(list)
        #     for key, value in overall_validity:
        #         second_distributor[key].append(value)
        #
        #     if self._progress_bar:
        #         recoverable = list(
        #             tqdm(
        #                 executor.map(_get_recoverable, second_distributor.items()),
        #                 total=len(second_distributor)
        #             )
        #         )
        #     else:
        #         recoverable = list(executor.map(_get_recoverable, second_distributor.items()))

        # df = pd.DataFrame(recoverable)
        # if not self._gather_traces:
        #     df.drop(columns=['traces'], inplace=True)
        #
        # if save_path:
        #     df.to_csv(save_path, index=False)
        #
        # return df
