"""Tests for SPARCLUR hash comparison behavior and edge cases."""

import json

import numpy as np
from imagehash import ImageHash

from sparclur._parser import (
    FONT,
    HASH_FAILED,
    HASH_UNAVAILABLE,
    META,
    RENDER,
    TEXT,
    TRACER,
    HashComparisonResult,
    HashComparisonPolicy,
    SparclurHash,
)


def test_empty_hashes_are_not_comparable():
    left = SparclurHash(b"left")
    right = SparclurHash(b"right")

    comparison = left.compare(right)

    assert comparison["sim"] is None
    assert comparison["dist"] is None
    assert not comparison["comparable"]
    assert not left.equals(right)


def test_empty_component_hashes_are_equal():
    left = SparclurHash(b"left")
    right = SparclurHash(b"right")
    for component in (RENDER, TEXT, META, FONT):
        left._add_hash(component, {})
        right._add_hash(component, {})

    comparison = left.compare(right)

    assert comparison["sim"] == 1.0
    assert comparison["dist"] == 0.0
    assert comparison["comparable"]


def test_failed_or_unavailable_components_do_not_count_as_equal():
    left = SparclurHash(b"left")
    right = SparclurHash(b"right")
    left._add_hash(RENDER, {}, status=HASH_FAILED, detail="render failed")
    right._add_hash(RENDER, {}, status=HASH_UNAVAILABLE, detail="renderer missing")

    comparison = left.compare(right)

    assert comparison["sim"] is None
    assert not comparison["comparable"]
    assert comparison["components"][RENDER]["left"]["status"] == HASH_FAILED
    assert comparison["components"][RENDER]["right"]["status"] == HASH_UNAVAILABLE


def test_policy_can_weight_successful_components():
    left = SparclurHash(b"left")
    right = SparclurHash(b"right")
    left._add_hash(META, {"object": 1})
    right._add_hash(META, {"object": 1})
    left._add_hash(FONT, {"font": 1})
    right._add_hash(FONT, {"font": 2})

    policy = HashComparisonPolicy(weights={META: 3.0, FONT: 1.0})
    comparison = left.compare(right, policy=policy)

    assert comparison["sim"] == 0.75
    assert comparison["policy"] == {
        "weights": {META: 3.0, FONT: 1.0},
        "page_aggregation": "min",
    }


def test_mismatched_component_settings_are_not_comparable():
    left = SparclurHash(b"left")
    right = SparclurHash(b"right")
    left._set_component_settings(RENDER, dpi=72, page_hashes=None)
    right._set_component_settings(RENDER, dpi=144, page_hashes=None)
    left._add_hash(RENDER, {})
    right._add_hash(RENDER, {})

    comparison = left.compare(right)

    assert not comparison["comparable"]
    assert not comparison["components"][RENDER]["settings_match"]


def test_evidence_bundle_round_trips_all_current_component_shapes():
    source = SparclurHash(b"source")
    source._set_component_settings(RENDER, dpi=72, page_hashes=("first", 1))
    source._add_hash(RENDER, {0: ImageHash(np.zeros((2, 2), dtype=bool))})
    source._add_hash(TEXT, {0: {1, 2, 3}})
    source._add_hash(TRACER, {4, 5})
    source._add_hash(META, {"object": 6})
    source._add_hash(FONT, {"font": 7})

    evidence = source.to_dict()
    restored = SparclurHash.from_dict(json.loads(json.dumps(evidence)))

    assert restored.to_dict() == evidence
    assert restored.file_hash == source.file_hash
    assert source.compare(restored).passes()


def test_comparison_result_reports_threshold_failures():
    left = SparclurHash(b"left")
    right = SparclurHash(b"right")
    left._add_hash(META, {"object": 1})
    right._add_hash(META, {"object": 1})
    left._add_hash(FONT, {"font": 1})
    right._add_hash(FONT, {"font": 2})

    comparison = left.compare(right)

    assert isinstance(comparison, HashComparisonResult)
    assert comparison.passes(minimum_similarity=0.5)
    assert not comparison.passes(component_minimums={FONT: 1.0})
    assert FONT in comparison.failures(component_minimums={FONT: 1.0})


def test_provenance_mismatch_warns_or_strictly_blocks_baseline_comparison():
    left = SparclurHash(b"left")
    right = SparclurHash(b"right")
    left._set_provenance(hash_algorithm={"version": 1})
    right._set_provenance(hash_algorithm={"version": 2})
    left._add_hash(META, {"object": 1})
    right._add_hash(META, {"object": 1})

    warning = left.compare(right)
    strict = left.compare(right, compatibility="strict")

    assert warning["comparable"]
    assert not warning["provenance_match"]
    assert warning["warnings"] == ["Hash algorithm provenance differs."]
    assert not strict["comparable"]


def test_different_parser_adapters_are_context_but_not_strictly_incompatible():
    left = SparclurHash(b"left")
    right = SparclurHash(b"right")
    left._set_provenance(parser={"name": "MuPDF", "class": "parser.MuPDF"})
    right._set_provenance(parser={"name": "Poppler", "class": "parser.Poppler"})
    left._add_hash(META, {"object": 1})
    right._add_hash(META, {"object": 1})

    comparison = left.compare(right, compatibility="strict")

    assert comparison["comparable"]
    assert not comparison["provenance_match"]
    assert comparison["warnings"] == []
