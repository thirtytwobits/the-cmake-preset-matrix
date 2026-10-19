#
# Copyright Amazon.com Inc. or its affiliates.
# SPDX-License-Identifier: MIT
#
"""Tests general parsing and transformation functions."""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from tcpm._core import transform_in_place
from tcpm._data_model import make_meta_presets


def test_cmake_presets():
    """
    Run a transformation on the test CMakePresets.json file.
    """
    current_file_path = Path(__file__).parent
    test_document = current_file_path / Path("CMakePresets.json")

    with test_document.open("r", encoding="UTF-8") as f:
        json_presets = json.load(f)

    meta_presets = make_meta_presets(json_presets)

    skip_list = transform_in_place(meta_presets, 0)

    assert "test" in skip_list
    assert "configure" not in skip_list

    assert "m32" == meta_presets.source["configurePresets"][2]["cacheVariables"]["MY_TARGET_PLATFORM"]

    print(json.dumps(meta_presets.source, indent=4))


def test_excludes():
    """
    Uses preset_test_excluded.json to test the exclude list.
    """
    current_file_path = Path(__file__).parent
    test_document = current_file_path / Path("preset_test_excluded.json")

    with test_document.open("r", encoding="UTF-8") as f:
        json_presets = json.load(f)

    meta_presets = make_meta_presets(json_presets)

    transform_in_place(meta_presets, 0)

    print(json.dumps(meta_presets.source, indent=4))

    assert len(meta_presets.source["configurePresets"]) == 9


def test_maintains_unmanaged():
    """
    Makes sure that unmanaged presets are retained.
    """
    current_file_path = Path(__file__).parent
    test_document = current_file_path / Path("preset_test_ignore_unmanaged.json")

    with test_document.open("r", encoding="UTF-8") as f:
        json_presets = json.load(f)

    meta_presets = make_meta_presets(json_presets)

    transform_in_place(meta_presets, 0)

    print(json.dumps(meta_presets.source, indent=4))

    assert "manual-entry" in [x["name"] for x in meta_presets.source["buildPresets"]]
    assert "another-manual-entry" in [x["name"] for x in meta_presets.source["workflowPresets"]]


@pytest.mark.parametrize("clean", [0, 1, 2])
def test_preserves_comments(clean):
    """Keep literal comments in metadata, shapes, and regenerated presets in every group."""
    literal_comment = ["Keep {literal} and {parameter} unchanged.", "$(this).text('do not execute')"]
    document = {
        "version": 10,
        "$comment": literal_comment.copy(),
        "vendor": {
            "$comment": literal_comment.copy(),
            "tcpm": {
                "version": 1,
                "$comment": literal_comment.copy(),
                "preset-groups": {"$comment": literal_comment.copy()},
            },
        },
    }
    groups = document["vendor"]["tcpm"]["preset-groups"]
    for group in ("configure", "build", "test", "package", "workflow"):
        shape = {
            "$comment": literal_comment.copy(),
            "vendor": {"example.com/1": {"value": "{parameter}", "$comment": literal_comment.copy()}},
        }
        if group == "configure":
            shape["cacheVariables"] = {
                "MODE": {"type": "STRING", "value": "{parameter}", "$comment": literal_comment.copy()}
            }
        elif group == "workflow":
            shape["steps"] = [
                {"type": "configure", "name": "configure-{parameter}", "$comment": literal_comment.copy()},
                {"type": "build", "name": "build-{parameter}"},
            ]
        else:
            shape["configurePreset"] = "configure-{parameter}"
        groups[group] = {
            "$comment": literal_comment.copy(),
            "parameters": {"$comment": literal_comment.copy(), "mode": ["debug", "release"]},
            "shape-parameters": {"$comment": literal_comment.copy()},
            "shape": {"$comment": literal_comment.copy(), "mode": shape},
            "exclude": [{"$comment": literal_comment.copy()}, {"$comment": literal_comment.copy(), "mode": "release"}],
        }
        preset = {
            "name": f"{group}-debug",
            "$comment": f"Existing {group} note",
            "vendor": {"example.com/1": {"value": "old", "$comment": f"Existing {group} vendor note"}},
        }
        if group == "workflow":
            preset["steps"] = [
                {"type": "build", "name": "build-debug", "$comment": "Build step note"},
                {"type": "configure", "name": "configure-debug", "$comment": "Configure step note"},
            ]
        document[f"{group}Presets"] = [preset]

    document["configurePresets"].append(
        {
            "name": "configure-mode-debug",
            "hidden": True,
            "$comment": "Existing hidden note",
            "cacheVariables": {"MODE": {"type": "STRING", "value": "old", "$comment": "Existing variable note"}},
        }
    )
    original_metadata = deepcopy(document["vendor"])
    meta_presets = make_meta_presets(document)
    transform_in_place(meta_presets, clean)

    assert meta_presets.source["$comment"] == literal_comment
    assert meta_presets.source["vendor"] == original_metadata
    for group in ("configure", "build", "test", "package", "workflow"):
        presets = {preset["name"]: preset for preset in meta_presets.source[f"{group}Presets"]}
        assert f"{group}-release" not in presets
        preset = presets[f"{group}-debug"]
        assert f"Existing {group} note" in preset["$comment"]
        if group == "configure":
            preset = presets["configure-mode-debug"]
            assert "Existing hidden note" in preset["$comment"]
            assert preset["cacheVariables"]["MODE"]["value"] == "debug"
            assert "Existing variable note" in preset["cacheVariables"]["MODE"]["$comment"]
        else:
            assert all(line in preset["$comment"] for line in literal_comment)
            assert preset["vendor"]["example.com/1"]["value"] == "debug"
            assert f"Existing {group} vendor note" in preset["vendor"]["example.com/1"]["$comment"]
        if group == "workflow":
            steps = {step["type"]: step for step in preset["steps"]}
            assert "Configure step note" in steps["configure"]["$comment"]
            assert steps["build"]["$comment"] == "Build step note"

    first_result = deepcopy(meta_presets.source)
    transform_in_place(meta_presets, clean)
    assert meta_presets.source == first_result


def test_clean_does_not_restore_obsolete_presets_or_fields():
    """Preserving comments must not undo the removal of obsolete presets or fields."""
    document = {
        "version": 10,
        "configurePresets": [
            {"name": "configure-obsolete", "$comment": "Obsolete preset"},
            {"name": "configure-debug", "$comment": "Keep", "vendor": {"old": {"$comment": "Obsolete field"}}},
        ],
        "vendor": {"tcpm": {"version": 1, "preset-groups": {"configure": {"parameters": {"mode": ["debug"]}}}}},
    }
    meta_presets = make_meta_presets(document)
    transform_in_place(meta_presets, 2)
    presets = {preset["name"]: preset for preset in meta_presets.source["configurePresets"]}
    assert "configure-obsolete" not in presets
    assert presets["configure-debug"]["$comment"] == "Keep"
    assert "vendor" not in presets["configure-debug"]


@pytest.mark.parametrize("group", ["configure", "build", "test", "package", "workflow"])
def test_comment_only_parameters_do_not_activate_groups(group):
    """Comments must not add empty preset arrays or prevent a group from being skipped."""
    document = {
        "version": 10,
        "vendor": {
            "tcpm": {"version": 1, "preset-groups": {group: {"parameters": {"$comment": ["Documentation only"]}}}}
        },
    }
    original = deepcopy(document)
    meta_presets = make_meta_presets(document)

    skipped = transform_in_place(meta_presets, 0)

    assert group in skipped
    assert meta_presets.source == original
