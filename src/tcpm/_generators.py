#
# Copyright Amazon.com Inc. or its affiliates.
# SPDX-License-Identifier: MIT
#
"""
Various functions for generating presets.
"""

import itertools
from typing import Any, Iterable

from ._data_model import ExcludeList, ScopedParameter, ShapedParameters, StructuredPresets
from ._rendering import get_parameters, param_renderer_map, render_shape
from ._utility import deep_merge, filter_matrix_group_by_visibility, reduce_preset_name

ParameterShapeMap = dict[str, dict]
"""
Index of shape templates by parameter name.
"""


def is_excluded(configuration: Iterable[ScopedParameter], exclude: ExcludeList) -> bool:
    """
    Check if a configuration is excluded by the given exclude list.

    .. invisible-code-block: python

        from tcpm._generators import is_excluded

        assert False == is_excluded(
            (
                ScopedParameter(".", "configure", "param1", "foo"),
                ScopedParameter(".", "configure", "param2", "bar"),
            ),
            [],
        )

    .. code-block:: python

        assert True == is_excluded(
            (
                ScopedParameter(".", "configure", "param1", "foo"),
                ScopedParameter(".", "configure", "param2", "bar"),
            ),
            [
                {"param1": "foo"},
                {"param2": "bar"},
            ],
        )
        assert False == is_excluded(
            (
                ScopedParameter(".", "configure", "param1", "foo"),
                ScopedParameter(".", "configure", "param2", "baz"),
            ),
            [
                {"param1": "foo", "param2": "bar"},
            ],
        )

    We also support multiple values per parameter:

    .. code-block:: python

        assert False == is_excluded(
            (
                ScopedParameter(".", "configure", "param1", "value3"),
                ScopedParameter(".", "configure", "param2", "bar"),
            ),
            [
                {"param1": ["value1", "value2"], "param2": "bar"},
            ],
        )
        assert True == is_excluded(
            (
                ScopedParameter(".", "configure", "param1", "value2"),
                ScopedParameter(".", "configure", "param2", "bar"),
            ),
            [
                {"param1": ["value1", "value2"], "param2": "bar"},
            ],
        )

    Note that rules must match all parameters to exclude a configuration:

    .. code-block:: python

        assert False == is_excluded(
            (
                ScopedParameter(".", "configure", "param1", "foo"),
            ),
            [
                {"param1": "foo", "param2": "bar"},
                {"param2": "bar"},
            ],
        )

    But any rule can match any parameter to exclude a configuration:

    .. code-block:: python

        assert True == is_excluded(
            (
                ScopedParameter(".", "configure", "param1", "foo"),
            ),
            [
                {"param1": ["foo"], "param2": "bar"},
                {"param1": ["foo"]},
            ],
        )

    :param configuration: The configuration to check.
    :param exclude: The list of exclude to check against.
    :return: True if the configuration is excluded, False otherwise
    """
    if len(exclude) == 0:
        return False

    def _rule_match(rule: dict[str, str | list[str]], sp: ScopedParameter) -> bool:
        rule_values = rule[sp.parameter]
        if isinstance(rule_values, list):
            return sp.value in rule_values
        return sp.value == rule_values

    param_count = len(list(configuration))
    for rule in exclude:
        matches = 0
        applicable = param_count
        for scoped_parameter in configuration:
            if scoped_parameter.parameter in rule:
                if not _rule_match(rule, scoped_parameter):
                    break
                matches += 1
            else:
                applicable -= 1
        if matches == applicable and matches == len(rule):
            return True
    return False


def make_shaped_matrix(
    group: str,
    meta_presets: StructuredPresets,
) -> tuple[ShapedParameters, ParameterShapeMap]:
    """
    Generate a matrix of parameters based on the shape templates in a group.

    :param group: The group to scope the parameters to.
    :param meta_presets: The meta_presets object.
    :return: A tuple of the parameter matrix and an index of shape templates by parameter name.
    """
    preset_matrix: ShapedParameters = {}
    parameter_shape_map: dict[str, dict] = {}
    preset_group = getattr(meta_presets.groups, group)

    for shape_name, shape_template in preset_group.shape.items():
        try:
            result_tuples = get_parameters(group, shape_name, meta_presets)
        except KeyError:
            continue
        preset_matrix[shape_name] = result_tuples
        for scoped_parameter in result_tuples:
            parameter_shape_map[scoped_parameter.value] = shape_template

    return preset_matrix, parameter_shape_map


def make_matrix_presets(
    group: str,
    hidden: bool,
    meta_presets: StructuredPresets,
) -> dict[str, dict]:
    """
    Generate presets as a matrix of `configurations` based on the hidden presets in the based-on group.
    """
    # pylint: disable=too-many-locals)
    parameter_renderer = param_renderer_map[group]
    preset_matrix, parameter_shape_map = make_shaped_matrix(group, meta_presets)
    preset_group = getattr(meta_presets.groups, group)
    presets: dict[str, Any] = filter_matrix_group_by_visibility(group, hidden, meta_presets)[1]

    # TODO: refactor this method
    # generate all permutations of the hidden presets as visible presets
    product = itertools.product(*preset_matrix.values())
    for configuration in product:
        if is_excluded(configuration, preset_group.exclude):
            continue
        preset_name = reduce_preset_name(group, configuration, meta_presets)
        if len(preset_name) <= len(getattr(meta_presets.groups, group).prefix):
            continue
        preset: dict[str, Any] = {"name": preset_name}
        if hidden:
            preset["hidden"] = True
        for scoped_parameter in configuration:
            shape_template = parameter_shape_map[scoped_parameter.value]
            rendered = render_shape(group, {"name": preset_name}, shape_template, scoped_parameter.value, meta_presets)
            deep_merge(preset, rendered)
        for shape_parameter_name, shape_parameter_list in preset_group.shape_parameters.items():
            for shape_parameter_value in shape_parameter_list:
                try:
                    shape_template = preset_group.shape[shape_parameter_name]
                except KeyError:
                    continue
                rendered = render_shape(
                    group, {"name": preset_name}, shape_template, shape_parameter_value, meta_presets
                )
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
        try:
            parameters = get_parameters(group, shape_name, meta_presets)
        except KeyError:
            continue
        for scoped_parameter in parameters:
            if is_excluded([scoped_parameter], preset_group.exclude):
                continue
            preset: dict[str, Any] = {"name": scoped_parameter.preset_scope}
            if hidden:
                preset["hidden"] = hidden
            render_shape(group, preset, shape_template, scoped_parameter.value, meta_presets)
            if scoped_parameter.preset_scope in presets.keys():
                deep_merge(presets[scoped_parameter.preset_scope], preset)
            else:
                presets[scoped_parameter.preset_scope] = preset

    return presets
