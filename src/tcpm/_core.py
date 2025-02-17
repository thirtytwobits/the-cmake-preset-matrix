#
# Copyright Amazon.com Inc. or its affiliates.
# SPDX-License-Identifier: MIT
#
"""
Core functions for transforming presets.
"""

from dataclasses import fields

from ._data_model import StructuredPresets
from ._generators import make_matrix_presets, make_parameter_presets
from ._pquery import render as render_pquery
from ._utility import clean_source, merge_preset_list, reclean_source


def transform_in_place(meta_presets: StructuredPresets, clean: int) -> set[str]:
    """
    Idempotent (mostly) generation of CMake presets based the contents of the vendor section of the presets file.
    Transformation is performed on the meta_presets object.

    :param meta_presets: The meta_presets object to transform.
    :param clean: The clean level to use when transforming the presets.
    :return: A set of group names that were skipped during transformation.
    """

    skip_list: set[str] = set()
    for group_field in fields(meta_presets.groups):
        if f"{group_field.name}Presets" not in meta_presets.source:
            skip_list.add(group_field.name)

    clean_source("configure", clean, True, meta_presets)
    render_pquery(meta_presets.source)
    hidden_preset_index = make_parameter_presets(
        "configure",
        True,
        meta_presets,
    )
    reclean_source("configure", clean, True, meta_presets)  # TODO: I don't think I need reclean anymore
    meta_presets.source["configurePresets"] = merge_preset_list(
        meta_presets.source["configurePresets"], hidden_preset_index
    )

    clean_source("configure", clean, False, meta_presets)
    render_pquery(meta_presets.source)
    visible_preset_index = make_matrix_presets(
        "configure",
        False,
        meta_presets,
    )
    reclean_source("configure", clean, False, meta_presets)
    meta_presets.source["configurePresets"] = merge_preset_list(
        meta_presets.source["configurePresets"], visible_preset_index
    )

    for group_field in fields(meta_presets.groups):
        group = group_field.name
        groupKey = f"{group}Presets"
        if group == "configure":
            # configure is special because that's where we do the matrix generation.
            continue
        if group in skip_list:
            print(f"Skipping group: {groupKey} (missing in source document)")
            continue

        clean_source(group, clean, False, meta_presets)
        render_pquery(meta_presets.source)
        preset_index = make_matrix_presets(
            group,
            False,
            meta_presets,
        )
        reclean_source(group, clean, False, meta_presets)
        meta_presets.source[groupKey] = merge_preset_list(meta_presets.source[groupKey], preset_index)

    render_pquery(meta_presets.source)

    return skip_list
