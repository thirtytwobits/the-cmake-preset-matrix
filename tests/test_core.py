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
from tcpm._errors import DataError


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
@pytest.mark.parametrize("custom_prefixes", [False, True])
def test_preset_prefixes(clean, custom_prefixes):
    """Use group prefixes for generated names, references, and cleanup on repeated runs."""
    prefixes = {
        group: f"custom-{group}" if custom_prefixes else group
        for group in ("configure", "build", "test", "package", "workflow")
    }
    document = {"version": 10, "vendor": {"tcpm": {"version": 1, "preset-groups": {}}}}
    groups = document["vendor"]["tcpm"]["preset-groups"]
    for group, prefix in prefixes.items():
        shape = {"displayName": "{prefix}{sep}{parameter}"}
        if group == "configure":
            shape["cacheVariables"] = {"MODE": "{parameter}"}
        elif group == "workflow":
            shape["steps"] = [
                {"type": step, "name": "{groups[" + step + "][prefix]}{sep}{parameter}"}
                for step in ("configure", "build")
            ]
        else:
            shape["configurePreset"] = "{groups[configure][prefix]}{sep}{parameter}"
        groups[group] = {"parameters": {"mode": ["debug"]}, "shape": {"mode": shape}}
        if custom_prefixes:
            groups[group]["prefix"] = prefix
        document[f"{group}Presets"] = [
            {"name": f"{prefix}-obsolete"},
            {"name": "manual-entry", "$comment": "Keep unmanaged presets"},
        ]
    document["configurePresets"].append({"name": f"{prefixes['configure']}-mode-obsolete", "hidden": True})

    meta_presets = make_meta_presets(document)
    transform_in_place(meta_presets, clean)
    for group, prefix in prefixes.items():
        presets = {preset["name"]: preset for preset in meta_presets.source[f"{group}Presets"]}
        expected_names = {"manual-entry", f"{prefix}-debug"}
        if clean < 2:
            expected_names.add(f"{prefix}-obsolete")
        if group == "configure":
            expected_names.add(f"{prefix}-mode-debug")
            if clean < 2:
                expected_names.add(f"{prefix}-mode-obsolete")
            hidden = presets[f"{prefix}-mode-debug"]
            assert hidden["hidden"] is True
            assert hidden["cacheVariables"]["MODE"] == "debug"
            assert hidden["displayName"] == f"{prefix}-debug"
            assert presets[f"{prefix}-debug"]["inherits"] == [hidden["name"]]
        elif group == "workflow":
            assert presets[f"{prefix}-debug"]["steps"] == [
                {"type": step, "name": f"{prefixes[step]}-debug"} for step in ("configure", "build")
            ]
        else:
            assert presets[f"{prefix}-debug"]["configurePreset"] == f"{prefixes['configure']}-debug"
        assert set(presets) == expected_names

    first_result = deepcopy(meta_presets.source)
    transform_in_place(meta_presets, clean)
    assert meta_presets.source == first_result


@pytest.mark.parametrize("clean", [0, 1, 2])
@pytest.mark.parametrize("sep", ["-", "."])
def test_clean_legacy_parameter_presets(clean, sep):
    """Clean old hidden names while retaining common presets and unrelated manual entries."""
    legacy_name = f"configure{sep}mode{sep}debug"
    obsolete_name = f"configure{sep}mode{sep}obsolete"
    common_name = f"configure{sep}mode{sep}common"
    manual_name = f"configure{sep}manual{sep}debug"
    visible_name = f"configure{sep}mode{sep}manual"
    retained = [
        {"name": common_name, "hidden": True},
        {"name": manual_name, "hidden": True},
        {"name": visible_name},
    ]
    document = {
        "version": 10,
        "configurePresets": [
            {"name": legacy_name, "hidden": True},
            {"name": obsolete_name, "hidden": True},
            *deepcopy(retained),
        ],
        "vendor": {
            "tcpm": {
                "version": 1,
                "word_separator": sep,
                "preset-groups": {
                    "configure": {"prefix": "config", "common": [common_name], "parameters": {"mode": ["debug"]}}
                },
            }
        },
    }
    meta_presets = make_meta_presets(document)
    transform_in_place(meta_presets, clean)
    presets = {preset["name"]: preset for preset in meta_presets.source["configurePresets"]}
    assert (legacy_name in presets) == (clean == 0)
    assert (obsolete_name in presets) == (clean == 0)
    for preset in retained:
        assert presets[preset["name"]] == preset
    hidden_name = f"config{sep}mode{sep}debug"
    assert presets[hidden_name]["hidden"] is True
    assert presets[f"config{sep}debug"]["inherits"] == [common_name, hidden_name]
    first_result = deepcopy(meta_presets.source)
    transform_in_place(meta_presets, clean)
    assert meta_presets.source == first_result


@pytest.mark.parametrize("clean", [0, 1, 2])
@pytest.mark.parametrize("prefix", ["configure", "config"])
def test_reject_hidden_visible_name_collision(clean, prefix):
    """Report ambiguous generated names instead of silently hiding the visible preset."""
    document = {
        "version": 10,
        "vendor": {
            "tcpm": {
                "version": 1,
                "preset-groups": {"configure": {"prefix": prefix, "parameters": {"mode": ["debug", "mode-debug"]}}},
            }
        },
    }
    meta_presets = make_meta_presets(document)
    with pytest.raises(DataError, match=f"Preset name collision for '{prefix}-mode-debug'"):
        transform_in_place(meta_presets, clean)


def test_excluded_name_collision_does_not_block_generation():
    """An excluded matrix preset does not collide with the surviving hidden parameter preset."""
    document = {
        "version": 10,
        "vendor": {
            "tcpm": {
                "version": 1,
                "preset-groups": {
                    "configure": {
                        "prefix": "config",
                        "parameters": {"mode": ["debug", "mode-debug"]},
                        "exclude": [{"mode": "mode-debug"}],
                    }
                },
            }
        },
    }
    meta_presets = make_meta_presets(document)
    transform_in_place(meta_presets, 2)
    presets = {preset["name"]: preset for preset in meta_presets.source["configurePresets"]}
    assert set(presets) == {"config-mode-debug", "config-debug"}
    assert presets["config-mode-debug"]["hidden"] is True
    assert presets["config-debug"]["inherits"] == ["config-mode-debug"]


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
