import multiprocessing
from typing import Callable, List, Dict, Any
from inspect import isclass
import os
from collections.abc import Iterable
import dill as pickle

from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score
import pandas as pd
import numpy as np

from sparclur._parser import Parser
from sparclur._tracer import Tracer
from sparclur._renderer import Renderer
from sparclur._text_extractor import TextExtractor
from sparclur._metadata_extractor import MetadataExtractor
from sparclur._font_extractor import FontExtractor

from sparclur.parsers.present_parsers import get_sparclur_parsers

from tqdm import tqdm
from pebble import ProcessPool
from func_timeout import func_timeout

POSSIBLE_CLASSIFIERS = ['decTree', 'randForest']

_MODEL_SWITCHER = {
    'decTree': DecisionTreeClassifier,
    'randForest': RandomForestClassifier
}


def _is_list_like(obj) -> bool:
    """
    Adapted from Pandas is_list_like.

    Parameters
    ----------
    obj: The object to test for list-likeness

    Returns
    -------
    bool
    """
    return (
            isinstance(obj, Iterable)
            and not isinstance(obj, (str, bytes))
            and not (isinstance(obj, np.ndarray) and obj.ndim == 0)
    )


def _parse_parsers(parsers):
    """
    Parses the tracers to run for the astrotruth labels.

    Parameters
    ----------
    parsers: List[str] or List[Parser]

    """
    parser_dict = {parser.get_name(): parser for parser in get_sparclur_parsers()}
    result = dict()
    for parser in parsers:
        if isinstance(parser, str):
            if parser in parser_dict:
                result[parser] = parser_dict[parser]
        elif isclass(parser):
            if issubclass(parser, Parser):
                result[parser.get_name()] = parser
        elif isinstance(parser, Parser):
            result[parser.get_name()] = parser
    return result


# def _parse_cleaned(tracer_name, doc, tracer_args):
#     tracer = [t for t in get_sparclur_tracers() if t.get_name() == tracer_name][0]
#     tracer = tracer(doc_path=doc, **tracer_args.get(tracer_name, dict()))
#     cleaned_messages = tracer.cleaned
#     return {'%s::%s' % (tracer.get_name(), key): value for key, value in cleaned_messages.items()}


def _parse_document(parser_name, exclude, doc, timeout, parser_args):
    parser = [p for p in get_sparclur_parsers() if p.get_name() == parser_name][0]
    parser = parser(doc_path=doc, skip_check=True, timeout=timeout, **parser_args.get(parser_name, dict()))
    if exclude is None:
        exclude = []
    elif isinstance(exclude, str):
        exclude = [exclude]

    exclude = [excluded.lower() for excluded in exclude]

    vector = dict()
    if isinstance(parser, Tracer) and 'tracer' not in exclude:
        cleaned_messages = parser.cleaned
        for key, value in cleaned_messages.items():
            vector['%s::%s' % (parser.get_name(), key)] = value
        if 'validity' not in exclude:
            vector['%s::Tracer Valid'] = 1 if parser.validate_tracer()['valid'] else 0
    if isinstance(parser, Renderer) and 'renderer' not in exclude:
        if 'validity' not in exclude:
            vector['%s::Renderer Valid'] = 1 if parser.validate_renderer()['valid'] else 0
    if isinstance(parser, TextExtractor) and 'text' not in exclude:
        if 'validity' not in exclude:
            vector['%s::Text Extraction Valid'] = 1 if parser.validate_text()['valid'] else 0
    if isinstance(parser, MetadataExtractor) and 'metadata' not in exclude:
        if 'validity' not in exclude:
            vector['%s::Metadata Extraction Valid'] = 1 if parser.validate_metadata()['valid'] else 0
    if isinstance(parser, FontExtractor) and 'font' not in exclude:
        vector['%s::Non-embedded Font'] = 1 if parser.non_embedded_fonts else 0
        if 'validity' not in exclude:
            vector['%s::Font Extraction Valid'] = 1 if parser.validate_fonts()['valid'] else 0
    return vector


def _worker(entry):
    file_col = entry['file_col']
    label_col = entry['label_col']
    file = entry[file_col]
    label = entry.get(label_col, "Prediction not run")
    parsers = entry['parsers']
    parser_args = entry.get('parser_args', dict())
    exclude = entry.get('exclude', [])
    timeout = entry['timeout']
    result = dict()
    result[file_col] = file
    result[label_col] = label
    for parser in parsers:
        try:
            parser_result = _parse_document(parser, exclude, file, timeout, parser_args)
        except Exception as error:
            e = str(error)
            parser_result = {'%s::%s' % (parser, e): 1}
        result[parser] = parser_result
    return result


def _error_result(file_col, label_col, path, label, error, parser_names):
    d = {file_col: path, label_col: label}
    for parser in parser_names:
        d[parser] = {'%s::%s' % (parser, error): 1}
    return d


def _parallel_messages(files, overall_timeout, progress_bar, num_workers, parsers, file_col, label_col):
    if progress_bar:
        pbar = tqdm(total=len(files))
    results = []
    index = 0

    # context = multiprocessing.get_context('spawn') if 'PDFBox' in parsers else multiprocessing.get_context('fork')

    # overall_timeout = None if timeout is None else int((len(tracers) + 0.5) * timeout)
    with ProcessPool(max_workers=num_workers, context=multiprocessing.get_context('spawn')) as pool:
        future = pool.map(_worker, files, timeout=overall_timeout or 600)

        iterator = future.result()

        while True:

            try:
                result = next(iterator)
            except StopIteration:
                result = None
                break
            except TimeoutError:
                entry = files[index]
                file = entry[file_col]
                label = entry[label_col]
                e = 'File Timed Out'
                result = _error_result(file_col, label_col, file, label, e, parsers)
            except Exception as error:
                entry = files[index]
                file = entry[file_col]
                label = entry[label_col]
                e = str(error)
                result = _error_result(file_col, label_col, file, label, e, parsers)
            finally:
                if progress_bar:
                    pbar.update(1)
                index += 1
                if result is not None:
                    results.append(result)
        if progress_bar:
            pbar.close()
        return results


class Astrotruther:
    """
    Trains a classifier from the error and warning messages of the specified SPARCLUR Tracers and a given set of labels
    for a collection of PDFs.
    """
    def __init__(self, file_col: str or int = 0,
                 label_col: str or int = 1,
                 base_path: str = None,
                 label_transform: Callable[[str], str] = None,
                 parsers: List[Parser] or List[str] = get_sparclur_parsers(),
                 parser_args: Dict[str, Dict[str, Any]] = dict(),
                 exclude: str or List[str] = None,
                 overall_timeout: int = None,
                 classifier: str = 'decTree',
                 classifier_args: Dict[str, Any] = dict(),
                 k_folds: int = 3,
                 num_workers: int = 1,
                 timeout: int = None,
                 progress_bar: bool = True
                 ):
        """
        Parameters
        ----------
        file_col: str or int
            The name of the Pandas column containing the file name or path or an integer representing the position of
            the column
        label_col: str or int
            The name of the Pandas column containing the classification label or an integer representing the position of
            the column
        base_path: str
            If the file column only contains file names and not the full path, this prepends a base path onto that file
            name.
        label_transform: Callable[[str], str]
            Applies a transform to the label before classification, such as renaming all instances of 'NBCUR' or
            'Rejected-Ambiguous' to 'Rejected'. Reduces data pre-processing before generating the astrotruth.
        parsers: List[Tracer] or List[str]
            List of the tracers to use as features.
        parser_args: Dict[str, Dict[str, Any]]
            Specific arguments for the tracers
        classifier: str
            The classifier to train, either DecTree or RandForest
        classifier_args: Dict[str, Any]
            Kwargs to use with the classifier. See scikit-learn API for parameters.
        k_folds: int
            The number of k-folds in the cross-validation for measuring model performance.
        num_workers: int
            The number of workers to allocate in the mutliprocessing pool for collecting the tracer messages.
        timeout: int
            The number of seconds each tracer gets per file before timeing out.
        progress_bar: bool
            Whether or not a progress bar should be displayed during message gathering.
        """
        assert classifier in POSSIBLE_CLASSIFIERS, "Please select one or more of: [%s]" % ', '.join(
            POSSIBLE_CLASSIFIERS)

        self._file_col = file_col
        self._label_col = label_col
        self._base_path = base_path
        self._label_transform = label_transform
        self._parsers = _parse_parsers(parsers)
        self._parser_args = parser_args
        self._exclude = exclude
        self._classifier = classifier
        self._classifier_args = classifier_args
        self._k_folds = k_folds
        self._num_workers = num_workers
        self._timeout = timeout
        self._overall_timeout = overall_timeout
        self._progress_bar = progress_bar
        self._model = None
        self._metrics: float = None
        self._warnings_map: Dict[str, int] = None
        self._k: int = None

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
    def file_col(self):
        return self._file_col

    @file_col.setter
    def file_col(self, fc):
        self._file_col = fc

    @property
    def label_col(self):
        return self._label_col

    @label_col.setter
    def label_col(self, lc):
        self._label_col = lc

    @property
    def base_path(self):
        return self._base_path

    @base_path.setter
    def base_path(self, bp):
        self._base_path = bp

    @base_path.deleter
    def base_path(self):
        self._base_path = None

    @property
    def label_transform(self):
        return self._label_transform

    @label_transform.setter
    def label_transform(self, lt: Callable[[str], str]):
        self._label_transform = lt

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
    def exclude(self):
        return self._exclude

    @exclude.setter
    def exclude(self, e: str or List[str]):
        self._exclude = e

    @exclude.deleter
    def exclude(self):
        self._exclude = None

    @property
    def classifier(self):
        return self._classifier

    @classifier.setter
    def classifier(self, c: str):
        assert c in POSSIBLE_CLASSIFIERS, "Please select one of: [%s]" % ', '.join(POSSIBLE_CLASSIFIERS)
        self._classifier = c

    @property
    def classifier_args(self):
        return self._classifier_args

    @classifier_args.setter
    def classifier_args(self, ca: Dict[str, Any]):
        self._classifier_args = ca

    @property
    def k_folds(self):
        return self._k_folds

    @k_folds.setter
    def k_folds(self, kf: int):
        self._k_folds = kf

    @property
    def num_workers(self):
        return self._num_workers

    @num_workers.setter
    def num_workers(self, nw):
        self._num_workers = nw

    @property
    def timeout(self):
        return self._timeout

    @timeout.setter
    def timeout(self, to):
        self._timeout = to

    @timeout.deleter
    def timeout(self):
        self._timeout = None

    def get_progress_bar(self):
        """Return the progress bar setting"""
        return self._progress_bar

    def set_progress_bar(self, p: bool):
        """Set whether or not to show progress bar"""
        self._progress_bar = p

    def save(self, path):
        """
        Save the generated model

        Parameters
        ----------
        path: str
            The file path to save the model in
        """
        assert self._model is not None, "Model has not been generated"
        with open(path, 'wb') as f:
            pickle.dump(self, f)

    @classmethod
    def load(cls, path):
        """
        Load a generated model

        Parameters
        ----------
        path: str
            The file path of a saved astrotruth model
        """
        with open(path, 'rb') as f:
            astro = pickle.load(f)
        return astro

    def fit(self, docs, doc_loading_args=dict()):
        X, Y = self._transform_training_data(docs, doc_loading_args)
        clf = _MODEL_SWITCHER[self._classifier](**self._classifier_args)
        self._model = clf.fit(X, Y)
        self._metrics = cross_val_score(clf, X, Y, cv=self._k_folds)
        avg_acc = sum(self._metrics) / self._k_folds
        print('Model Accuracy: %f' % avg_acc)

    def predict(self, docs,
                file_col=None,
                doc_loading_args=dict(),
                unseen_ignore=None,
                unseen_message_default='Not enough info',
                prediction_column='astrotruth'):
        assert self._model is not None, "Model has not been generated"
        file_col = self._file_col if file_col is None else file_col
        df = self._load_prediction_data(docs, file_col, doc_loading_args)
        X = self._get_prediction_messages(df, file_col)
        predictions = {key: self._predict(vector, unseen, unseen_ignore, unseen_message_default)
                       for (key, (vector, unseen)) in X.items()}
        df[prediction_column] = df[file_col].apply(lambda x: predictions.get(x, ("Not found", "Not found"))[0])
        df['untrained_messages'] = df[file_col].apply(lambda x: predictions.get(x, ("Not found", "Not found"))[1])
        return df

    def _predict(self, vector, unseen_messages, unseen_ignore, unseen_message_default):
        if unseen_ignore is not None:
            if isinstance(unseen_ignore, str):
                unseen_ignore = [unseen_ignore]
        else:
            unseen_ignore = []
        prediction = self._model.predict(vector.reshape(1, -1))[0]
        if not unseen_messages or unseen_message_default is None or prediction in unseen_ignore:
            return prediction, unseen_messages
        else:
            return unseen_message_default, unseen_messages

    def _load_prediction_data(self, docs, file_col, data_args):
        if not isinstance(docs, pd.DataFrame):
            if isinstance(docs, str):
                if os.path.isfile(docs):
                    data = pd.read_csv(docs, **data_args)
                else:
                    data = pd.DataFrame([docs], columns=[file_col])
            else:
                assert _is_list_like(docs), \
                    "Data in unrecognizable format. " \
                    "Please use a DataFrame, a list of filepaths, a single filepath, or the path to a csv"
                data = pd.DataFrame(docs, columns=[file_col])
        else:
            data = docs
        return data

    def _get_prediction_messages(self, df, file_col):
        data = list(df[file_col].values)
        if self._num_workers == 1 or len(data) / self._num_workers < 20:
            messages = [self._get_messages(entry) for entry in data]
        else:
            parallel_data = [{'file_col': self._file_col,
                              self._file_col: file,
                              'label_col': self._label_col,
                              self._label_col: "Not predicted yet",
                              'parsers': list(self._parsers.keys()),
                              'parser_args': self._parser_args,
                              'exclude': self._exclude,
                              'timeout': self._timeout}
                             for file in data]
            messages = _parallel_messages(parallel_data,
                                          self._overall_timeout,
                                          self._progress_bar,
                                          self._num_workers,
                                          self._timeout,
                                          list(self._parsers.keys()),
                                          self._file_col,
                                          self._label_col)
        X = {entry[file_col]: self._vectorfy(entry) for entry in messages}
        return X

    def _transform_training_data(self, data, data_args):
        if not isinstance(data, pd.DataFrame):
            if isinstance(data, str):
                assert os.path.isfile(data), "Data not found"
                data = pd.read_csv(data, **data_args)
            else:
                assert _is_list_like(data), \
                    "Data in unrecognizable format. Please use a DataFrame, a list of tuples, or the path to a csv"
                data = pd.DataFrame(data, columns=[self._file_col, self._label_col])
        if self._num_workers == 1:
            messages = []
            if self._progress_bar:
                pbar = tqdm(total=len(data))
            for entry in data[[self._file_col, self._label_col]].values.tolist():
                messages.append(self._get_messages(entry))
                if self._progress_bar:
                    pbar.update(1)
            if self._progress_bar:
                pbar.close()
            # messages = [self._get_messages(entry) for entry in
            #             data[[self._file_col, self._label_col]].values.tolist()]
        else:
            parallel_data = [{'file_col': self._file_col,
                              self._file_col: file,
                              'label_col': self._label_col,
                              self._label_col: label,
                              'parsers': list(self._parsers.keys()),
                              'parser_args': self._parser_args,
                              'exclude': self._exclude,
                              'timeout': self._timeout}
                             for file, label in data[[self._file_col, self._label_col]].values.tolist()]
            messages = _parallel_messages(parallel_data,
                                          self._overall_timeout,
                                          self._progress_bar,
                                          self._num_workers,
                                          list(self._parsers.keys()),
                                          self._file_col,
                                          self._label_col)
        distinct_warnings = set()
        for dic in messages:
            for parser in self._parsers.keys():
                distinct_warnings.update(set(dic[parser]))
        distinct_warnings = list(distinct_warnings)
        distinct_warnings.sort()
        self._warnings_map = {warning: index for (index, warning) in enumerate(distinct_warnings)}
        self._k = len(self._warnings_map)
        X = [self._vectorfy(entry)[0] for entry in messages]
        Y = [entry[self._label_col] for entry in messages]
        if self._label_transform is not None:
            Y = [self._label_transform(label) for label in Y]
        return X, Y

    def _vectorfy(self, entry):
        vector = np.zeros(self._k)
        unseen_messages = False
        for parser_name in self._parsers.keys():
            error_dict = entry[parser_name]
            for (warning, count) in error_dict.items():
                if warning in self._warnings_map:
                    vector[self._warnings_map[warning]] = count
                else:
                    unseen_messages = True
        return vector, unseen_messages

    def _get_messages(self, entry):
        if isinstance(entry, str):
            file = entry
            label = "Prediction not run"
        else:
            file, label = entry
        result = dict()
        result[self._file_col] = file
        result[self._label_col] = label
        for parser_name in self._parsers.keys():
            try:
                parser_result = func_timeout(
                    600,
                    _parse_document,
                    kwargs={
                        'parser_name': parser_name,
                        'exclude': self._exclude,
                        'doc': file,
                        'timeout': self._timeout,
                        'parser_args': self._parser_args
                    }
                )
            except Exception as error:
                e = str(error)
                parser_result = {'%s::%s' % (parser_name, e): 1}
            result[parser_name] = parser_result
        return result
