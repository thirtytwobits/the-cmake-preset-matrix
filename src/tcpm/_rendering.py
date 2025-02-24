#
# Copyright Amazon.com Inc. or its affiliates.
# SPDX-License-Identifier: MIT
#
"""
Various functions for rendering values in the presets file.
"""

from __future__ import annotations

from typing import Any, Callable

from ._data_model import PresetGroup, ScopedParameter, StructuredPresets
from ._utility import deep_merge, list_merge


def string_render(
    group: str, value_template: str, preset_name: str, parameter: str, meta_presets: StructuredPresets
) -> str:
    """
    Renders a string template with the given parameters.
    Available tokens are:
    - {pq}: A '$' to allow late evaluation of the pquery statement.
    - {doc}: The source json document.
    - {sep}: The word separator.
    - {parameter}: The parameter.
    - {name}: The name of the preset.
    - {groups}: The preset groups.
    - {prefix): The prefix of the group.
    - {value}: The value of the string before expansion.
    - {static:[value]}: Any value listed in the static dictionary for this document.

    .. invisible-code-block: python

        from tcpm import make_default_meta_presets

    >>> string_render("configure", "{parameter}-{name}", "configure", "parameter", make_default_meta_presets())
    'parameter-configure'

    """
    format_tokens = {
        "pq": "$",
        "doc": meta_presets.source,
        "sep": meta_presets.word_separator,
        "parameter": parameter,
        "name": preset_name,
        "groups": meta_presets.groups,
        "value": value_template,
        "prefix": getattr(meta_presets.groups, group).prefix,
        "static": meta_presets.static,
    }
    return value_template.format(**format_tokens)


def _recursive_expand(
    group: str, preset_name: str, value_template: Any, parameter: str, meta_presets: StructuredPresets
) -> Any:
    if isinstance(value_template, dict):
        return {
            _recursive_expand(group, preset_name, k, parameter, meta_presets): _recursive_expand(
                group, preset_name, v, parameter, meta_presets
            )
            for k, v in value_template.items()
        }
    elif isinstance(value_template, list):
        return [_recursive_expand(group, preset_name, x, parameter, meta_presets) for x in value_template]
    elif isinstance(value_template, str):
        return string_render(group, value_template, preset_name, parameter, meta_presets)
    else:
        return value_template


def render_parameter_value(
    group: str, parameter_name: str, value: str | list[str], meta_presets: StructuredPresets
) -> Any:
    """
    Handles rendering parameter values. _recursive_expand's parameter is set to "" because this is rendering the
    parameter value so the paramater doesn't exist yet.
    """
    if isinstance(value, list):
        return [_recursive_expand(group, parameter_name, x, "", meta_presets) for x in value]
    else:
        return _recursive_expand(group, parameter_name, value, "", meta_presets)


def render_shape(group: str, preset: dict, shape: dict, parameter: str, meta_presets: StructuredPresets) -> dict:
    """
    Handlers rendering shapes.
    """
    for key, value_template in shape.items():
        rendered = _recursive_expand(group, preset["name"], value_template, parameter, meta_presets)
        if key not in preset:
            preset[key] = rendered
        elif isinstance(preset[key], dict) and isinstance(rendered, dict):
            deep_merge(preset[key], rendered)
        elif isinstance(preset[key], list) and isinstance(rendered, list):
            list_merge(preset[key], rendered)
        else:
            preset[key] = rendered

    return preset


def configure_parameter_renderer(
    parameters: dict, preset_group: PresetGroup, configuration: tuple[ScopedParameter, ...], _: StructuredPresets
) -> None:
    parameters["inherits"] = preset_group.common + [x[0] for x in configuration]


def no_op_parameter_renderer(*_: Any) -> None:
    pass


def get_parameters(
    group: str,
    shape_name: str,
    meta_presets: StructuredPresets,
) -> list[ScopedParameter]:
    """
    Builds a list of parameters names.
    @return: A list of tuples where the first element is the expected preset name and the second is the parameter value.
    """
    parameters: list[ScopedParameter] = []
    parameter_values = getattr(meta_presets.groups, group).parameters[shape_name]
    rendered_values = render_parameter_value(group, shape_name, parameter_values, meta_presets)
    sep = meta_presets.word_separator
    if not isinstance(rendered_values, list):
        rendered_values = [rendered_values]
    for rendered_value in rendered_values:
        parameters.append(ScopedParameter(sep, group, shape_name, rendered_value))
    return parameters


def get_parameter(
    group: str,
    name: str,
    meta_presets: StructuredPresets,
) -> Any:
    """
    Renders a single parameter for a given group.
    """
    if name not in getattr(meta_presets.groups, group).parameters:
        return None

    return render_parameter_value(group, name, getattr(meta_presets.groups, group).parameters[name], meta_presets)


param_renderer_map: dict[str, Callable] = {
    "configure": configure_parameter_renderer,
    "build": no_op_parameter_renderer,
    "test": no_op_parameter_renderer,
    "package": no_op_parameter_renderer,
    "workflow": no_op_parameter_renderer,
}
