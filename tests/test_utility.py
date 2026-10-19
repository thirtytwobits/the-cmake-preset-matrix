#
# Copyright Amazon.com Inc. or its affiliates.
# SPDX-License-Identifier: MIT
#
"""Tests for comment preservation during merges."""

import pytest

from tcpm._utility import deep_merge, merge_comments


@pytest.mark.parametrize(
    "existing, incoming, expected",
    [
        ("same", "same", "same"),
        ("one", "two", ["one", "two"]),
        (["one"], "two", ["one", "two"]),
        ("one", ["one", "two"], ["one", "two"]),
        (["one", "two"], ["two", "three"], ["one", "two", "three"]),
        ([], "", [""]),
    ],
)
def test_merge_comments(existing, incoming, expected):
    """Retain distinct string and array comments without splitting strings into characters."""
    target = {"$comment": existing}
    deep_merge(target, {"$comment": incoming})
    assert target["$comment"] == expected
    deep_merge(target, {"$comment": incoming})
    assert target["$comment"] == expected


def test_merge_comments_matches_step_type_and_name():
    """Steps with the same name in different preset groups retain their own comments."""
    original = [
        {"type": "configure", "name": "debug", "$comment": "Configure"},
        {"type": "build", "name": "debug", "$comment": "Build"},
    ]
    target = [{"type": "build", "name": "debug"}, {"type": "configure", "name": "debug"}]
    merge_comments(original, target)
    assert target[0]["$comment"] == "Build"
    assert target[1]["$comment"] == "Configure"


def test_merge_comments_in_vendor_arrays():
    """Vendor objects can have arbitrary type values and arrays of unnamed objects."""
    original = [{"name": "tool", "type": {"custom": True}, "$comment": "Named"}, {"$comment": "Unnamed"}]
    target = [{"name": "tool", "type": {"custom": True}}, {}]
    merge_comments(original, target)
    assert target[0]["$comment"] == "Named"
    assert target[1]["$comment"] == "Unnamed"


@pytest.mark.parametrize("target_count", [1, 2, 3])
def test_merge_comments_matches_duplicate_names_one_to_one(target_count):
    """Duplicate names in vendor arrays match by occurrence without pooling comments."""
    original = [
        {"name": "tool", "type": "custom", "option": "one", "$comment": "First note"},
        {"name": "tool", "type": "custom", "option": "two", "$comment": "Second note"},
    ]
    target = [{"name": "tool", "type": "custom", "option": index} for index in range(target_count)]
    merge_comments(original, target)
    assert target[0]["$comment"] == "First note"
    if target_count >= 2:
        assert target[1]["$comment"] == "Second note"
    if target_count == 3:
        assert "$comment" not in target[2]
    merge_comments(original, target)
    assert target[0]["$comment"] == "First note"
