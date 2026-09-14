from __future__ import annotations
import abc
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from imagehash import ImageHash

from sparclur._metaclass import Meta
from sparclur.utils import jac_sim, hash_file

VALID = 'Valid'
VALID_WARNINGS = 'Valid with Warnings'
REJECTED = 'Rejected'
REJECTED_AMBIG = 'Rejected; Ambiguous'
TIMED_OUT = 'Timed Out'

RENDER = 'Renderer'
TRACER = 'Tracer'
TEXT = 'Text Extractor'
META = 'Metadata Extractor'
FONT = 'Font Extractor'
IMAGE = 'Image Data'

SPARCLUR_TYPES = [RENDER, TRACER, TEXT, META, FONT, IMAGE]

HASH_OK = 'ok'
HASH_UNAVAILABLE = 'unavailable'
HASH_FAILED = 'failed'
HASH_EXCLUDED = 'excluded'
HASH_NOT_COLLECTED = 'not collected'
HASH_SCHEMA_VERSION = 1
HASH_ALGORITHM_VERSION = 1
HASH_PROVENANCE = {
    'algorithm_version': HASH_ALGORITHM_VERSION,
    'renderer': {'algorithm': 'dhash', 'hash_size': 128},
    'text': {
        'algorithm': 'murmurhash128 bottom-k shingles',
        'shingle_size': 4,
        'sketch_size': 200,
    },
    'tracer': {'algorithm': 'murmurhash128 normalized-message set'},
    'metadata': {'algorithm': 'murmurhash128 canonicalized objects'},
    'font': {'algorithm': 'murmurhash128 canonicalized fonts'},
}


@dataclass(frozen=True)
class HashComparisonPolicy:
    """Controls how compatible SPARCLUR hash components are aggregated.

    By default every successful component receives equal weight and page-level
    renderer/text scores use their worst page.  This preserves the historic
    SPARCLUR comparison behavior for successfully collected components.
    """

    weights: dict[str, float] = field(default_factory=dict)
    page_aggregation: str = 'min'

    def __post_init__(self):
        if self.page_aggregation not in {'min', 'mean'}:
            raise ValueError("page_aggregation must be 'min' or 'mean'")
        if any(weight < 0 for weight in self.weights.values()):
            raise ValueError('Hash comparison weights must be non-negative')

    def weight_for(self, component: str) -> float:
        return self.weights.get(component, 1.0)

    def aggregate_pages(self, scores: dict[int, float]) -> float:
        if not scores:
            return 1.0
        if self.page_aggregation == 'mean':
            return sum(scores.values()) / len(scores)
        return min(scores.values())

    def as_dict(self) -> dict[str, Any]:
        return {
            'weights': dict(self.weights),
            'page_aggregation': self.page_aggregation,
        }


class HashComparisonResult(dict):
    """A comparison result that can enforce regression thresholds."""

    def failures(self, minimum_similarity: float = 1.0,
                 component_minimums: dict[str, float] | None = None,
                 require_comparable: bool = True) -> dict[str, str]:
        """Return human-readable reasons this result misses a threshold."""
        failures = dict()
        if require_comparable and not self['comparable']:
            failures['comparison'] = 'No successful compatible components were compared.'
            return failures
        if self['sim'] is None:
            failures['similarity'] = 'Overall similarity is unavailable.'
        elif self['sim'] < minimum_similarity:
            failures['similarity'] = (
                f"{self['sim']:.6f} is below the required {minimum_similarity:.6f}."
            )
        for component, minimum in (component_minimums or {}).items():
            result = self['components'].get(component)
            if result is None or 'sim' not in result:
                failures[component] = 'Component was not successfully compared.'
            elif result['sim'] < minimum:
                failures[component] = (
                    f"{result['sim']:.6f} is below the required {minimum:.6f}."
                )
        return failures

    def passes(self, minimum_similarity: float = 1.0,
               component_minimums: dict[str, float] | None = None,
               require_comparable: bool = True) -> bool:
        """Return whether this result satisfies the requested thresholds."""
        return not self.failures(
            minimum_similarity=minimum_similarity,
            component_minimums=component_minimums,
            require_comparable=require_comparable,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable copy of this comparison evidence."""
        return dict(self)

RENDER_HASH_SIZE = 128


def _compare_render_hash(left, right):
    pages = set().union(left.keys()).union(right.keys())
    comparison = dict()
    for page in pages:
        left_hash: ImageHash = left.get(page, None)
        right_hash: ImageHash = right.get(page, None)
        if left_hash is not None and right_hash is not None:
            diff = left_hash - right_hash
            normalized = diff / (RENDER_HASH_SIZE * RENDER_HASH_SIZE)
            comparison[page] = 1.0 - normalized
        else:
            comparison[page] = 0.0
    return comparison


def _compare_tracer_hash(left, right):
    return jac_sim(left, right)


def _compare_text_hash(left, right):
    pages = set().union(left.keys()).union(right.keys())
    comparison = dict()
    for page in pages:
        left_hash_set = left.get(page, set())
        right_hash_set = right.get(page, set())
        comparison[page] = jac_sim(left_hash_set, right_hash_set)
    return comparison


def _compare_metadata_hash(left, right):
    objects = set().union(left.keys()).union(right.keys())
    comparison = dict()
    for obj in objects:
        comparison[obj] = 1 if left.get(obj, None) == right.get(obj, None) else 0
    return comparison


def _compare_font_hash(left, right):
    fonts = set().union(left.keys()).union(right.keys())
    comparison = dict()
    for font in fonts:
        comparison[font] = 1 if left.get(font, None) == right.get(font, None) else 0
    return comparison


class SparclurHash:
    """
    The SPARCLUR hash attempts to distill the information from the different parser tools: image hashes for the
    renders and sets of shingled murmur hashes for the text extraction, metadata, trace messages, and fonts. These
    are collected and then can be used to compare two documents. Components that cannot be collected are reported
    explicitly and do not contribute to similarity. This is most relevant in 2 specific cases: the first is trying
    to find evidence of non-determinism in a parser and the second is to quickly compare differences between parser
    translations of a document (See the Reforge class of tools).
    """
    def __init__(self, doc: str,
                 exclude: str or list[str] = None):
        """
        Parameters
        ----------
        doc : str or bytes
            Either the path to the PDF or the raw bytes of the PDF
        exclude : str or List[str]
            Specifies any subclass SPARCLUR hashes that should be excluded from this parser instantiation. Can be one or
            more of the following: 'Renderer', 'Tracer', 'Text Extractor', 'Metadata Extractor', and/or 'Font Extractor'
        """

        if exclude is None or (not isinstance(exclude, str) and not isinstance(exclude, list)):
            self._exclude = []
        elif isinstance(exclude, str):
            self._exclude = [exclude]
        else:
            self._exclude = exclude

        self._doc_hash = hash_file(doc)
        self._hash = dict()
        self._component_outcomes = {
            component: {'status': HASH_EXCLUDED}
            for component in self._exclude
        }
        self._component_settings = dict()
        self._provenance = {'hash_algorithm': HASH_PROVENANCE}

    def __len__(self):
        return len(self._hash)

    def __getitem__(self, key):
        return self._hash[key]

    def get(self, key, default):
        if key in self._hash:
            return self._hash[key]
        else:
            return default

    def keyset(self):
        return set(self._hash.keys())

    def __contains__(self, key):
        return key in self._hash

    @property
    def excluded(self):
        return self._exclude

    @property
    def file_hash(self):
        return self._doc_hash

    @property
    def metadata(self) -> dict[str, Any]:
        """Return provenance needed to interpret this parser-output hash."""
        return {
            'schema_version': HASH_SCHEMA_VERSION,
            'source_sha256': self.file_hash,
            'excluded_components': list(self.excluded),
            'component_settings': {
                component: dict(settings)
                for component, settings in self._component_settings.items()
            },
            'provenance': self._serialize_setting(self._provenance),
        }

    @property
    def component_outcomes(self) -> dict[str, dict[str, str]]:
        """Return each collected component's outcome without exposing internals."""
        return {
            component: dict(outcome)
            for component, outcome in self._component_outcomes.items()
        }

    def _component_outcome(self, component: str) -> dict[str, str]:
        return self._component_outcomes.get(component, {'status': HASH_NOT_COLLECTED})

    def _set_component_settings(self, component: str, **settings) -> None:
        self._component_settings[component] = settings

    def _set_provenance(self, **provenance) -> None:
        self._provenance.update(provenance)

    def _add_hash(self, key, value, status: str = HASH_OK, detail: str | None = None):
        if status not in {HASH_OK, HASH_UNAVAILABLE, HASH_FAILED, HASH_EXCLUDED}:
            raise ValueError(f'Unknown SPARCLUR hash component status: {status}')
        self._hash[key] = value
        outcome = {'status': status}
        if detail is not None:
            outcome['detail'] = detail
        self._component_outcomes[key] = outcome

    @staticmethod
    def _serialize_setting(value: Any) -> Any:
        if isinstance(value, tuple):
            return {
                '__sparclur_type__': 'tuple',
                'items': [SparclurHash._serialize_setting(item) for item in value],
            }
        if isinstance(value, list):
            return [SparclurHash._serialize_setting(item) for item in value]
        if isinstance(value, dict):
            return {
                str(key): SparclurHash._serialize_setting(item)
                for key, item in value.items()
            }
        return value

    @staticmethod
    def _deserialize_setting(value: Any) -> Any:
        if isinstance(value, list):
            return [SparclurHash._deserialize_setting(item) for item in value]
        if isinstance(value, dict):
            if value.get('__sparclur_type__') == 'tuple':
                return tuple(SparclurHash._deserialize_setting(item) for item in value['items'])
            return {
                key: SparclurHash._deserialize_setting(item)
                for key, item in value.items()
            }
        return value

    @staticmethod
    def _serialize_component(component: str, value: Any) -> Any:
        if component == RENDER:
            return [
                {
                    'page': page,
                    'hash': str(image_hash),
                    'shape': list(image_hash.hash.shape),
                }
                for page, image_hash in sorted(value.items())
            ]
        if component in {TEXT, TRACER}:
            if component == TEXT:
                return [
                    {'page': page, 'hashes': sorted(hashes)}
                    for page, hashes in sorted(value.items())
                ]
            return sorted(value)
        if component in {META, FONT}:
            return [
                {'key': key, 'hash': item}
                for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            ]
        return SparclurHash._serialize_setting(value)

    @staticmethod
    def _deserialize_component(component: str, value: Any) -> Any:
        if component == RENDER:
            hashes = dict()
            for item in value:
                shape = tuple(item['shape'])
                size = int(np.prod(shape))
                bits = bin(int(item['hash'], 16))[2:].zfill(size)
                array = np.array([bit == '1' for bit in bits], dtype=bool).reshape(shape)
                hashes[item['page']] = ImageHash(array)
            return hashes
        if component == TEXT:
            return {item['page']: set(item['hashes']) for item in value}
        if component == TRACER:
            return set(value)
        if component in {META, FONT}:
            return {item['key']: item['hash'] for item in value}
        return SparclurHash._deserialize_setting(value)

    def to_dict(self) -> dict[str, Any]:
        """Export a versioned, JSON-serializable parser-output evidence bundle."""
        metadata = self.metadata
        metadata['component_settings'] = self._serialize_setting(metadata['component_settings'])
        return {
            'schema_version': HASH_SCHEMA_VERSION,
            'metadata': metadata,
            'component_outcomes': self.component_outcomes,
            'hashes': {
                component: self._serialize_component(component, value)
                for component, value in self._hash.items()
            },
        }

    @classmethod
    def from_dict(cls, evidence: dict[str, Any]) -> SparclurHash:
        """Restore a SPARCLUR hash evidence bundle produced by :meth:`to_dict`."""
        if evidence.get('schema_version') != HASH_SCHEMA_VERSION:
            raise ValueError('Unsupported SPARCLUR hash evidence schema version')
        metadata = evidence.get('metadata')
        if not isinstance(metadata, dict) or 'source_sha256' not in metadata:
            raise ValueError('SPARCLUR hash evidence is missing source metadata')

        instance = cls.__new__(cls)
        instance._doc_hash = metadata['source_sha256']
        instance._exclude = list(metadata.get('excluded_components', []))
        instance._hash = {
            component: cls._deserialize_component(component, value)
            for component, value in evidence.get('hashes', {}).items()
        }
        instance._component_outcomes = {
            component: dict(outcome)
            for component, outcome in evidence.get('component_outcomes', {}).items()
        }
        instance._component_settings = cls._deserialize_setting(
            metadata.get('component_settings', {})
        )
        instance._provenance = cls._deserialize_setting(
            metadata.get('provenance', {'hash_algorithm': HASH_PROVENANCE})
        )
        return instance

    def _provenance_issues(self, that: SparclurHash) -> list[str]:
        """Return provenance differences that can affect baseline meaning."""
        issues = list()
        if self._provenance.get('hash_algorithm') != that._provenance.get('hash_algorithm'):
            issues.append('Hash algorithm provenance differs.')

        left_parser = self._provenance.get('parser')
        right_parser = that._provenance.get('parser')
        if left_parser and right_parser:
            if left_parser.get('name') != right_parser.get('name'):
                issues.append(
                    f"Different parser adapters: {left_parser['name']} and {right_parser['name']}."
                )
            elif left_parser != right_parser:
                issues.append('Parser adapter provenance differs.')
        return issues

    def _has_strict_provenance_mismatch(self, that: SparclurHash) -> bool:
        """Return whether algorithm or same-adapter provenance changed."""
        if self._provenance.get('hash_algorithm') != that._provenance.get('hash_algorithm'):
            return True
        left_parser = self._provenance.get('parser')
        right_parser = that._provenance.get('parser')
        return bool(
            left_parser and right_parser
            and left_parser.get('name') == right_parser.get('name')
            and left_parser != right_parser
        )

    def is_comparable_with(self, that: SparclurHash | Parser) -> bool:
        """Return whether both hashes share at least one compatible component."""
        if isinstance(that, Parser):
            that = that.sparclur_hash
        for component in set().union(self.keyset(), that.keyset()):
            left = self._component_outcome(component)
            right = that._component_outcome(component)
            settings_match = self._component_settings.get(component) == that._component_settings.get(component)
            if left['status'] == HASH_OK and right['status'] == HASH_OK and settings_match:
                return True
        return False

    def equals(this, that: SparclurHash | Parser,
               policy: HashComparisonPolicy | None = None):
        """
        Checks for parsed document information equality.

        Returns
        -------
        bool
        """
        comparison = this.compare(that, policy=policy)
        return comparison['comparable'] and comparison['sim'] == 1.0

    def compare(this, that: SparclurHash | Parser,
                policy: HashComparisonPolicy | None = None,
                compatibility: str = 'warn'):
        """
        Compares all of the present information hashes and collects all of the results.

        Returns
        -------
        Dict[str, Any]
            Per-component scores and outcomes, the policy used, whether any
            compatible component was compared, and the resulting similarity
            and distance. Similarity and distance are ``None`` when no
            successful compatible components are available.
        """
        if isinstance(that, Parser):
            that = that.sparclur_hash
        if policy is None:
            policy = HashComparisonPolicy()
        if not isinstance(policy, HashComparisonPolicy):
            raise TypeError('policy must be a HashComparisonPolicy instance')
        if compatibility not in {'warn', 'strict', 'ignore'}:
            raise ValueError("compatibility must be 'warn', 'strict', or 'ignore'")
        provenance_issues = this._provenance_issues(that)
        strict_provenance_failure = (
            compatibility == 'strict' and this._has_strict_provenance_mismatch(that)
        )
        results = HashComparisonResult()
        component_results = dict()
        weighted_sim = 0.0
        total_weight = 0.0
        for key in set().union(this.keyset()).union(that.keyset()):
            left_outcome = this._component_outcome(key)
            right_outcome = that._component_outcome(key)
            settings_match = this._component_settings.get(key) == that._component_settings.get(key)
            component_results[key] = {
                'left': left_outcome,
                'right': right_outcome,
                'settings_match': settings_match,
            }
            if (strict_provenance_failure or left_outcome['status'] != HASH_OK
                    or right_outcome['status'] != HASH_OK or not settings_match):
                continue
            component_sim = None
            if key == RENDER:
                render_compare = _compare_render_hash(this.get(RENDER, dict()), that.get(RENDER, dict()))
                render_sim = policy.aggregate_pages(render_compare)
                component_sim = render_sim
                results[RENDER] = render_compare
                results[RENDER+' sim'] = render_sim
            elif key == TRACER:
                trace_compare = _compare_tracer_hash(this.get(TRACER, set()), that.get(TRACER, set()))
                component_sim = trace_compare
                results[TRACER+' sim'] = trace_compare
            elif key == TEXT:
                text_compare = _compare_text_hash(this.get(TEXT, dict()), that.get(TEXT, dict()))
                text_sim = policy.aggregate_pages(text_compare)
                component_sim = text_sim
                results[TEXT] = text_compare
                results[TEXT+' sim'] = text_sim
            elif key == META:
                meta_compare = _compare_metadata_hash(this.get(META, dict()), that.get(META, dict()))
                meta_sim = sum(meta_compare.values()) / len(meta_compare) if meta_compare else 1.0
                component_sim = meta_sim
                results[META] = meta_compare
                results[META+' sim'] = meta_sim
            elif key == FONT:
                font_compare = _compare_font_hash(this.get(FONT, dict()), that.get(FONT, dict()))
                font_sim = sum(font_compare.values()) / len(font_compare) if font_compare else 1.0
                component_sim = font_sim
                results[FONT] = font_compare
                results[FONT+' sim'] = font_sim
            if component_sim is not None:
                weight = policy.weight_for(key)
                weighted_sim += component_sim * weight
                total_weight += weight
                component_results[key]['weight'] = weight
                component_results[key]['sim'] = component_sim
        overall_sim = weighted_sim / total_weight if total_weight else None
        dist = 1 - overall_sim if overall_sim is not None else None
        results['components'] = component_results
        results['policy'] = policy.as_dict()
        results['compatibility'] = compatibility
        results['provenance_match'] = not provenance_issues
        results['warnings'] = provenance_issues if compatibility == 'warn' else []
        results['comparable'] = total_weight > 0
        results['sim'] = overall_sim
        results['dist'] = dist
        return results


class Parser(metaclass=Meta):
    """
    Base abstract class for SPARCLUR parser wrappers.

    This abstract class provides the basis for all parser wrappers in SPARCLUR.
    """

    @abc.abstractmethod
    def __init__(self, doc: str | bytes,
                 temp_folders_dir: str | None,
                 skip_check: bool | None,
                 timeout: int | None,
                 hash_exclude: str | list[str] | None,
                 *args,
                 **kwargs):
        """
        Parameters
        ----------
        doc : str or bytes
            Either the path to the PDF or the raw bytes of the PDF
        temp_folders_dir : str
            Path to create the temporary directories used for temporary files.
        timeout : int
            Specify a timeout for parsing commands
        skip_check : bool
            Flag for skipping the parser check.
        hash_exclude : str or List[str]
            Specifies any subclass SPARCLUR hashes that should be excluded from this parser instantiation. Can be one or
            more of the following: 'Renderer', 'Tracer', 'Text Extractor', 'Metadata Extractor', and/or 'Font Extractor'
        """
        self._doc = doc
        self._temp_folders_dir = temp_folders_dir
        self._skip_check = skip_check
        self._timeout = timeout
        self._hash_exclude = hash_exclude
        self._validity: dict[str, dict[str, Any]] = dict()
        self._api: dict[str, str] = {'num_pages': '(Property) Returns number of pages in the document'}
        self._num_pages = None
        self._sparclur_hash = self._new_sparclur_hash()
        self._file_timed_out = dict()

    def _new_sparclur_hash(self) -> SparclurHash:
        """Create a hash with the parser identity needed for baseline review."""
        sparclur_hash = SparclurHash(self._doc, self._hash_exclude)
        sparclur_hash._set_provenance(
            parser={
                'name': self.get_name(),
                'class': f'{type(self).__module__}.{type(self).__qualname__}',
            },
        )
        return sparclur_hash

    def __repr__(self):
        return '\n'.join('%s:\t%s' % (method, desc) for (method, desc) in self._api.items())

    def __str__(self):
        return self.get_name()

    @property
    def doc(self):
        """
        Return the path to the document that is being run through the parser instance or the first 15 bytes if a binary
        was passed to the parser.

        Returns
        -------
        str or bytes
            String of the document path or first 15 bytes of the binary
        """
        return self._doc if isinstance(self._doc, str) else self._doc[0:15]

    @abc.abstractmethod
    def _get_num_pages(self):
        pass

    @property
    def temp_folders_dir(self):
        return self._temp_folders_dir

    @temp_folders_dir.setter
    def temp_folders_dir(self, t):
        self._temp_folders_dir = t

    @temp_folders_dir.deleter
    def temp_folders_dir(self):
        self._temp_folders_dir = None

    @staticmethod
    @abc.abstractmethod
    def get_name():
        """
        Return the SPARCLUR defined name for the parser.

        Returns
        -------
        str
            Parser name
        """
        pass

    @property
    def validity(self):
        """
        Returns the validity statuses from each of the relevant tools of the parser and an overall validity for the
        document. If any of the tools have a warning or error the overall will show that otherwise all of the tools need
        to mark the document as valid for the overall status to be valid.

        Returns
        -------
        Dict[str, Dict[str, Any]]
            A dictionary of dictionaries laying out the validity and statuses for the parser tools.
        """
        results = [(entry['valid'], entry['status']) for (key, entry) in self._validity.items()]
        statuses = [entry[1] for entry in results]
        validity = min([entry[0] for entry in results])
        if REJECTED in statuses:
            status = REJECTED
        elif REJECTED_AMBIG in statuses:
            status = REJECTED_AMBIG
        elif VALID_WARNINGS in statuses:
            status = VALID_WARNINGS
        else:
            status = VALID
        self._validity['overall'] = {'valid': validity, 'status': status}
        return self._validity

    @property
    def sparclur_hash(self):
        """
        The SPARCLUR hash attempts to distill the information from the different parser tools: image hashes for the
        renders and sets of shingled murmur hashes for the text extraction, metadata, trace messages, and fonts. These
        are collected and then can be used to compare two documents and a distance measure is calculated. This is most
        relevant in 2 specific cases: the first is trying to find evidence of non-determinism in a parser and the
        second is to quickly compare differences between parser translations of a document (See the Reforge class of
        tools).

        Returns
        -------
        SparclurHash
            The class that holds the SPARCLUR hashes for each tool and provides an API for comparing two hashes.
        """
        return self._sparclur_hash

    @property
    def timeout(self):
        return self._timeout

    @timeout.setter
    def timeout(self, to: int):
        self._sparclur_hash = self._new_sparclur_hash()
        self._timeout = to
        self._file_timed_out = dict()

    @timeout.deleter
    def timeout(self):
        self._sparclur_hash = self._new_sparclur_hash()
        self._timeout = None
        self._file_timed_out = dict()

    @property
    def num_pages(self):
        """
        Determine the number of pages in the PDF according to the parser. If the parser does not support page number
        extraction (e.g. Arlington DOM Checker) this returns None. If the parser fails to load and determine the
        number of pages, 0 is returned.

        Returns
        -------
        int
            The number of pages in the document
        """
        if self._num_pages is None:
            self._get_num_pages()
        return self._num_pages
