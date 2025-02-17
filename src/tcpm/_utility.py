#
# Copyright Amazon.com Inc. or its affiliates.
# SPDX-License-Identifier: MIT
#
"""
Utility functions for the tcpm package.
"""
from __future__ import annotations

import functools
import json
import urllib.request
from typing import Any

from ._data_model import StructuredPresets
from ._errors import DataError


def reduce_preset_name(group: str, configuration: tuple[tuple[str, str], ...], meta_presets: StructuredPresets) -> str:
    return str(
        functools.reduce(
            lambda x, y: f"{x}{meta_presets.word_separator}{y[1]}",
            configuration,
            getattr(meta_presets.groups, group).prefix,
        )
    )


def list_merge(d1: list, d2: list) -> None:
    """
    Merge two lists preventing duplicates but maintaining order. New, non-duplicate items are appended.
    """
    for item in d2:
        if item not in d1:
            d1.append(item)


def deep_merge(d1: dict, d2: dict) -> None:
    """
    merge two dictionary structures ensuring no duplicate keys or list entries are created.
    """
    for key, value in d2.items():
        if key in d1:
            if isinstance(d1[key], dict):
                if isinstance(value, dict):
                    deep_merge(d1[key], value)
                else:
                    d1[key].update(value)
            elif isinstance(d1[key], list):
                list_merge(d1[key], value)
            else:
                d1[key] = value
        else:
            d1[key] = value


def merge_preset_list(d1: list[dict], d2: dict[str, dict]) -> list[dict]:
    """
    Merge new presets into an existing preset list.
    """
    copy_of_d2 = d2.copy()
    for preset in d1:
        preset_name = preset["name"]
        if preset_name in copy_of_d2:
            deep_merge(preset, copy_of_d2.pop(preset_name))

    return d1 + list(copy_of_d2.values())


def filter_matrix_group_by_visibility(
    group: str, hidden: bool, presets: StructuredPresets
) -> tuple[str, dict[str, Any]]:
    def select_clause(p: str, x: dict[str, str | bool]) -> bool:
        return (
            (("hidden" in x and x["hidden"] == hidden) or (not hidden and "hidden" not in x))
            and isinstance(x["name"], str)
            and x["name"].startswith(p)
            and x["name"] not in getattr(presets.groups, group).common
        )

    prefix = f"{getattr(presets.groups, group).prefix}{presets.word_separator}"
    return (
        prefix,
        {d["name"]: d for d in filter(functools.partial(select_clause, prefix), presets.source[f"{group}Presets"])},
    )


@functools.lru_cache
def get_schema(presets_schema_url: str) -> dict:
    with urllib.request.urlopen(presets_schema_url, timeout=10) as response:
        schema_object = json.loads(response.read().decode())
    if not isinstance(schema_object, dict):
        raise DataError("Schema is not a dictionary.")
    return schema_object


def _validate_json_schema(presets_schema_url: str, squelch_print: bool, force: bool, presets_source: dict) -> bool:
    """
    Validates the preset file against certain assumptions this script makes. If jsonschema and requests is available
    the script will also validate the file against the CMake presets schema pulled from github.
    """
    try:
        import jsonschema  # type: ignore # pylint: disable=import-outside-toplevel
    except ImportError:
        if not force:
            print("jsonschema python module is required to validate the schema.")
            response = input("Okay to skip? (y/n): ").strip().lower()
            if response != "y":
                return False
            return True
        else:
            if not squelch_print:
                print("jsonschema is required to validate the schema. Skipping validation (--force).")
            return True

    schema = get_schema(presets_schema_url)

    try:
        jsonschema.validate(instance=presets_source, schema=schema)
    except jsonschema.ValidationError as e:
        print(f"JSON schema validation error: {e.message}")
        return False

    return True


def validate_json_schema_for_presets(presets_schema_url: str, force: bool, presets_source: dict) -> bool:
    return _validate_json_schema(presets_schema_url, False, force, presets_source)


def validate_json_schema_for_presets_unless(
    no_schema_validation: bool, presets_schema_url: str, force: bool, presets_source: dict
) -> bool:
    if no_schema_validation:
        print("Skipping schema validation (--no-schema-validation).")
        return True
    return validate_json_schema_for_presets(presets_schema_url, force, presets_source)


def validate_json_schema_for_result(presets_schema_url: str, force: bool, presets_source: dict) -> bool:
    return _validate_json_schema(presets_schema_url, True, force, presets_source)


def validate_json_schema_for_result_unless(
    no_schema_validation: bool, presets_schema_url: str, force: bool, presets_source: dict
) -> bool:
    if no_schema_validation:
        return True
    return validate_json_schema_for_result(presets_schema_url, force, presets_source)


def _clean_source(
    group: str, clean_level: int | None, pre_clean: bool, hidden: bool, meta_presets: StructuredPresets
) -> None:
    if clean_level == 0 or clean_level is None:
        return

    source_key = f"{group}Presets"

    def hidden_clause(x: dict[str, bool]) -> bool:
        return ("hidden" in x and x["hidden"] == hidden) or ("hidden" not in x and not hidden)

    def common_clause(x: dict[str, Any]) -> bool:
        return x["name"] in getattr(meta_presets.groups, group).common

    def name_clause(x: dict[str, str]) -> bool:
        prefix = f"{getattr(meta_presets.groups, group).prefix}{meta_presets.word_separator}"
        return x["name"].startswith(prefix)

    if (not pre_clean and clean_level == 1) or (pre_clean and clean_level >= 2):
        meta_presets.source[source_key] = [
            preset
            for preset in meta_presets.source[source_key]
            if not hidden_clause(preset) or not name_clause(preset) or common_clause(preset)
        ]


def clean_source(group: str, clean_level: int | None, hidden: bool, meta_presets: StructuredPresets) -> None:
    _clean_source(group, clean_level, True, hidden, meta_presets)


def reclean_source(group: str, clean_level: int | None, hidden: bool, meta_presets: StructuredPresets) -> None:
    _clean_source(group, clean_level, False, hidden, meta_presets)
