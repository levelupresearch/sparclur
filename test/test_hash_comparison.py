"""Tests for SPARCLUR hash comparison edge cases."""

from sparclur._parser import FONT, META, RENDER, TEXT, SparclurHash


def test_empty_hashes_are_equal():
    left = SparclurHash(b"left")
    right = SparclurHash(b"right")

    assert left.compare(right) == {"sim": 1.0, "dist": 0.0}
    assert left.equals(right)


def test_empty_component_hashes_are_equal():
    left = SparclurHash(b"left")
    right = SparclurHash(b"right")
    for component in (RENDER, TEXT, META, FONT):
        left._add_hash(component, {})
        right._add_hash(component, {})

    comparison = left.compare(right)

    assert comparison["sim"] == 1.0
    assert comparison["dist"] == 0.0
