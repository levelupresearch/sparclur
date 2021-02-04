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

from sparclur._tracer import Tracer
from sparclur.parsers.present_parsers import get_sparclur_tracers

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


def _parse_tracers(tracers):
    """
    Parses the tracers to run for the astrotruth labels.

    Parameters
    ----------
    tracers: List[str] or List[Tracer]

    """
    renderer_dict = {tracer.get_name(): tracer for tracer in get_sparclur_tracers()}
    result = dict()
    for tracer in tracers:
        if isinstance(tracer, str):
            if tracer in renderer_dict:
                result[tracer] = renderer_dict[tracer]
        elif isclass(tracer):
            if issubclass(tracer, Tracer):
                result[tracer.get_name()] = tracer
        elif isinstance(tracer, Tracer):
            result[tracer.get_name()] = tracer
    return result


def _parse_cleaned(tracer_name, doc, tracer_args):
    tracer = [t for t in get_sparclur_tracers() if t.get_name() == tracer_name][0]
    tracer = tracer(doc_path=doc, **tracer_args.get(tracer_name, dict()))
    cleaned_messages = tracer.cleaned
    return {'%s::%s' % (tracer.get_name(), key): value for key, value in cleaned_messages.items()}


def _worker(entry):
    file_col = entry['file_col']
    label_col = entry['label_col']
    file = entry[file_col]
    label = entry.get(label_col, "Prediction not run")
    tracers = entry['tracers']
    tracer_args = entry.get('tracer_args', dict())
    timeout = entry['timeout']
    result = dict()
    result[file_col] = file
    result[label_col] = label
    for tracer in tracers:
        try:
            tracer_result = func_timeout(
                timeout,
                _parse_cleaned,
                kwargs={
                    'tracer_name': tracer,
                    'doc': file,
                    'tracer_args': tracer_args
                }
            )
        except Exception as error:
            e = str(error)
            tracer_result = {'%s::%s' % (tracer, e): 1}
        result[tracer] = tracer_result
    return result


def _error_result(file_col, label_col, path, label, error, tracer_names):
    d = {file_col: path, label_col: label}
    for tracer in tracer_names:
        d[tracer] = {'%s::%s' % (tracer, error): 1}
    return d


def _parallel_messages(files, progress_bar, num_workers, timeout, tracers, file_col, label_col):
    if progress_bar:
        pbar = tqdm(total=len(files))
    results = []
    index = 0

    overall_timeout = None if timeout is None else int((len(tracers) + 0.5) * timeout)
    with ProcessPool(max_workers=num_workers) as pool:
        future = pool.map(_worker, files, timeout=overall_timeout)

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
                result = _error_result(file_col, label_col, file, label, e, tracers)
            except Exception as error:
                entry = files[index]
                file = entry[file_col]
                label = entry[label_col]
                e = str(error)
                result = _error_result(file_col, label_col, file, label, e, tracers)
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
                 parsers: List[Tracer] or List[str] = get_sparclur_tracers(),
                 parser_args: Dict[str, Dict[str, Any]] = dict(),
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
        self._tracers = _parse_tracers(parsers)
        self._parser_args = parser_args
        self._classifier = classifier
        self._classifier_args = classifier_args
        self._k_folds = k_folds
        self._num_workers = num_workers
        self._timeout = timeout
        self._progress_bar = progress_bar
        self._model = None
        self._metrics: float = None
        self._warnings_map: Dict[str, int] = None
        self._k: int = None

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
        return [parser.get_name() for parser in self._tracers]

    @parsers.setter
    def parsers(self, parsers: List[str] or List[Tracer]):
        self._tracers = _parse_tracers(parsers)

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
                              'tracers': list(self._tracers.keys()),
                              'tracer_args': self._parser_args,
                              'timeout': self._timeout}
                             for file in data]
            messages = _parallel_messages(parallel_data,
                                          self._progress_bar,
                                          self._num_workers,
                                          self._timeout,
                                          list(self._tracers.keys()),
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
                              'tracers': list(self._tracers.keys()),
                              'tracer_args': self._parser_args,
                              'timeout': self._timeout}
                             for file, label in data[[self._file_col, self._label_col]].values.tolist()]
            messages = _parallel_messages(parallel_data,
                                          self._progress_bar,
                                          self._num_workers,
                                          self._timeout,
                                          list(self._tracers.keys()),
                                          self._file_col,
                                          self._label_col)
        distinct_warnings = set()
        for dic in messages:
            for tracer in self._tracers.keys():
                distinct_warnings.update(set(dic[tracer]))
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
        for tracer_name in self._tracers.keys():
            error_dict = entry[tracer_name]
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
        for tracer_name in self._tracers.keys():
            try:
                tracer_result = func_timeout(
                    self._timeout,
                    self._parse_cleaned,
                    kwargs={
                        'tracer_name': tracer_name,
                        'doc': file
                    }
                )
            except Exception as error:
                e = str(error)
                tracer_result = {'%s::%s' % (tracer_name, e): 1}
            result[tracer_name] = tracer_result
        return result
