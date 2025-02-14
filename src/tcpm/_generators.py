#
# Copyright Amazon.com Inc. or its affiliates.
# SPDX-License-Identifier: MIT
#
"""
Various functions for generating presets.
"""

import itertools
from typing import Any

from ._data_model import StructuredPresets
from ._rendering import get_parameters, lambda_render_shape, param_renderer_map
from ._utility import deep_merge, filter_matrix_group_by_visibility, reduce_preset_name


def make_matrix_presets(
    group: str,
    hidden: bool,
    meta_presets: StructuredPresets,
) -> dict[str, dict]:
    """
    Generate presets as a matrix of `configurations` based on the hidden presets in the based-on group.
    """
    parameter_renderer = param_renderer_map[group]
    preset_matrix: dict[str, list[tuple[str, str]]] = {}
    parameter_shape_map: dict[str, dict] = {}
    preset_group = getattr(meta_presets.groups, group)
    presets: dict[str, Any] = filter_matrix_group_by_visibility(group, hidden, meta_presets)[1]

    for shape_name, shape_template in preset_group.shape.items():
        result_tuples = get_parameters(group, shape_name, meta_presets)
        preset_matrix[shape_name] = result_tuples
        for _, parameter in result_tuples:
            parameter_shape_map[parameter] = shape_template

    # generate all permutations of the hidden presets as visible presets
    product = itertools.product(*preset_matrix.values())
    for configuration in product:
        preset_name = reduce_preset_name(group, configuration, meta_presets)
        if len(preset_name) <= len(getattr(meta_presets.groups, group).prefix):
            continue
        preset: dict[str, Any] = {"name": preset_name}
        if hidden:
            preset["hidden"] = True
        for _, parameter in configuration:
            shape_template = parameter_shape_map[parameter]
            rendered = lambda_render_shape(group, {"name": preset_name}, shape_template, parameter, meta_presets)
            deep_merge(preset, rendered)
        parameter_renderer(preset, preset_group, configuration, meta_presets)
        if preset_name in presets:
            presets[preset_name].update(preset)
        else:
            presets[preset_name] = preset

    return presets


def make_parameter_presets(
    group: str,
    hidden: bool,
    meta_presets: StructuredPresets,
) -> dict[str, dict]:
    """
    Build a set of presets based on parameters as given on the command line or inferred from the based_on set of
    presets.
    """
    preset_group = getattr(meta_presets.groups, group)
    preset_group_shapes = preset_group.shape
    presets = filter_matrix_group_by_visibility(group, hidden, meta_presets)[1]

    for shape_name, shape_template in preset_group_shapes.items():
        parameters = get_parameters(group, shape_name, meta_presets)
        for preset_name, parameter in parameters:
            preset: dict[str, Any] = {"name": preset_name}
            if hidden:
                preset["hidden"] = hidden
            lambda_render_shape(group, preset, shape_template, parameter, meta_presets)
            if preset_name in presets.keys():
                deep_merge(presets[preset_name], preset)
            else:
                presets[preset_name] = preset

    return presets
