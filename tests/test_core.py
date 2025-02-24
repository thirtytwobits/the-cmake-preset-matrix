#
# Copyright Amazon.com Inc. or its affiliates.
# SPDX-License-Identifier: MIT
#
"""Tests general parsing and transformation functions."""

import json
from pathlib import Path

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
