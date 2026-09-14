"""Tests for SPARCLUR hash comparison behavior and edge cases."""

from sparclur._parser import (
    FONT,
    HASH_FAILED,
    HASH_UNAVAILABLE,
    META,
    RENDER,
    TEXT,
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
