#
# Copyright Amazon.com Inc. or its affiliates.
# SPDX-License-Identifier: MIT
#
"""
Core functions for transforming presets.
"""

import logging
from dataclasses import fields

from ._data_model import StructuredPresets
from ._generators import make_matrix_presets, make_parameter_presets
from ._pquery import render as render_pquery
from ._utility import clean_source, merge_preset_list, reclean_source
from .cli._parser import __script_name__

_core_logger = logging.getLogger(__script_name__)


def ensure_preset_groups(meta_presets: StructuredPresets) -> set[str]:
    """
    Make sure that all groups in the meta_presets object have a corresponding list in the source document. If a group
    is missing, it is added to the source document – in the correct order – with an empty list as it's value.

    :param meta_presets: The meta_presets object to check.
    :return: A set of group names that had no corresponding list in the source document nor any parameters in the group.
    """
    skip_list: set[str] = set()

    for group_field in fields(meta_presets.groups):
        if f"{group_field.name}Presets" not in meta_presets.source:
            if len(meta_presets.groups[group_field.name].parameters) == 0:
                skip_list.add(group_field.name)
            else:
                meta_presets.source[f"{group_field.name}Presets"] = []
                # Move the new group to the correct position
                keys = list(meta_presets.source.keys())
                keys.remove(f"{group_field.name}Presets")
                vendor_index = keys.index("vendor")
                keys.insert(vendor_index, f"{group_field.name}Presets")
                meta_presets.source = {k: meta_presets.source[k] for k in keys}

    return skip_list


def transform_in_place(meta_presets: StructuredPresets, clean: int) -> set[str]:
    """
    Idempotent (mostly) generation of CMake presets based the contents of the vendor section of the presets file.
    Transformation is performed on the meta_presets object.

    :param meta_presets: The meta_presets object to transform.
    :param clean: The clean level to use when transforming the presets.
    :return: A set of group names that were skipped during transformation.
    """

    # pquery must run first to ensure "onload" events are processed before we start transforming the document.
    render_pquery(meta_presets.source, word_separator=meta_presets.word_separator, events=["onload"])

    skip_list: set[str] = ensure_preset_groups(meta_presets)

    clean_source("configure", clean, True, meta_presets)
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
    render_pquery(meta_presets.source, word_separator=meta_presets.word_separator)
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
            _core_logger.debug("Skipping group: %s (missing in source document)", groupKey)
            continue

        clean_source(group, clean, False, meta_presets)
        render_pquery(meta_presets.source, word_separator=meta_presets.word_separator)
        preset_index = make_matrix_presets(
            group,
            False,
            meta_presets,
        )
        reclean_source(group, clean, False, meta_presets)
        meta_presets.source[groupKey] = merge_preset_list(meta_presets.source[groupKey], preset_index)

    render_pquery(meta_presets.source, word_separator=meta_presets.word_separator)

    return skip_list
