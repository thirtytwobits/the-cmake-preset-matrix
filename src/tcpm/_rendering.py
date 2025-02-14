#
# Copyright Amazon.com Inc. or its affiliates.
# SPDX-License-Identifier: MIT
#
"""
Various functions for rendering values in the presets file.
"""

from __future__ import annotations

from typing import Any, Callable, Iterable

from ._data_model import PresetGroup, StructuredPresets
from ._errors import LambdaRenderingError
from ._utility import deep_merge, list_merge, reduce_preset_name


def string_render(
    group: str, value_template: str, preset_name: str, parameter: str, meta_presets: StructuredPresets
) -> str:
    """
    Renders a string template with the given parameters.
    Available tokens are:
    - {doc}: The source json document.
    - {sep}: The word separator.
    - {parameter}: The parameter.
    - {name}: The name of the preset.
    - {groups}: The preset groups.
    - {prefix): The prefix of the group.
    - {value}: The value of the string before expansion.
    - {static:[value]}: Any value listed in the static dictionary for this group.

    .. invisible-code-block: python

        from tcpm import make_default_meta_presets

    >>> string_render("configure", "{parameter}-{name}", "configure", "parameter", make_default_meta_presets())
    'parameter-configure'

    """
    format_tokens = {
        "doc": meta_presets.source,
        "sep": meta_presets.word_separator,
        "parameter": parameter,
        "name": preset_name,
        "groups": meta_presets.groups,
        "value": value_template,
        "prefix": getattr(meta_presets.groups, group).prefix,
    }
    format_tokens.update(getattr(meta_presets.groups, group).static)
    return value_template.format(**format_tokens)


def lambda_render(
    group: str, value_template: str, preset_name: str, parameter: str, meta_presets: StructuredPresets
) -> Any:
    """
     Lambda functions are invoked with the following tuple values:
    - [0] doc: The source json document
    - [1] parameter: The parameter.
    - [2] parameter seperator: The word separator.
    - [3] name: The name of the preset.
    - [4] groups: The preset groups
    - [5] prefix: The prefix of the group.

    """
    print("lambda rendering is deprecated. Use pquery instead.")
    try:
        λ = eval(value_template)  # pylint: disable=W0123
    except Exception as e:
        raise ValueError(f"Error evaluating lambda function: {value_template}") from e
    try:
        return λ(
            (
                meta_presets.source,
                parameter,
                meta_presets.word_separator,
                preset_name,
                meta_presets.groups,
                getattr(meta_presets.groups, group).prefix,
            )
        )
    except Exception as e:
        raise LambdaRenderingError(f"Error executing lambda function: {value_template}") from e


def _recursive_expand(
    group: str, preset_name: str, value_template: Any, parameter: str, meta_presets: StructuredPresets
) -> str | dict | list:
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
        rendered = string_render(group, value_template, preset_name, parameter, meta_presets)
        if rendered.startswith("lambda "):
            lambda_result = lambda_render(group, rendered, preset_name, parameter, meta_presets)
            if isinstance(lambda_result, str):
                # don't re-expand the result if it's a string. This is a terminal value.
                return lambda_result
            else:
                return _recursive_expand(group, preset_name, lambda_result, parameter, meta_presets)
        else:
            return rendered
    else:
        raise ValueError(f"Unsupported value template type: {type(value_template)}")


def lambda_render_parameter_value(
    group: str, parameter_name: str, value: str | list[str], meta_presets: StructuredPresets
) -> str | dict | list:
    """
    Handles rendering parameter values. _recursive_expand's parameter is set to "" because this is rendering the
    parameter value so the paramater doesn't exist yet.
    """
    if isinstance(value, list):
        return [_recursive_expand(group, parameter_name, x, "", meta_presets) for x in value]
    else:
        return _recursive_expand(group, parameter_name, value, "", meta_presets)


def lambda_render_shape(group: str, preset: dict, shape: dict, parameter: str, meta_presets: StructuredPresets) -> dict:
    """
    Handlers rendering shapes while also supporting a lambda function as a value template.
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
    parameters: dict, preset_group: PresetGroup, configuration: tuple[tuple[str, str]], _: StructuredPresets
) -> None:
    parameters["inherits"] = preset_group.common + [x[0] for x in configuration]


def workflow_parameter_renderer(
    parameters: dict, _: PresetGroup, configuration: tuple[tuple[str, str]], meta_presets: StructuredPresets
) -> None:
    if "steps" not in parameters:
        parameters["steps"] = []

    parameters["steps"] += [{"type": "configure", "name": reduce_preset_name("configure", configuration, meta_presets)}]

    build_configurations = get_parameter("build", "configuration", meta_presets)
    if build_configurations is not None:
        for build_configuration in build_configurations:
            build_config_tuple_list = tuple([("", build_configuration)] + list(configuration))
            preset_name = reduce_preset_name("build", build_config_tuple_list, meta_presets)
            parameters["steps"] += [{"type": "build", "name": preset_name}]


def no_op_parameter_renderer(*_: Any) -> None:
    pass


def get_parameters(
    group: str,
    shape_name: str | None,
    meta_presets: StructuredPresets,
) -> list[tuple[str, str | dict | list]]:
    """
    Builds a list of parameters names.
    @return: A list of tuples where the first element is the expected preset name and the second is the parameter value.
    """
    parameters: list[tuple[str, str | dict | list]] = []
    for parameter_name, parameter_values in getattr(meta_presets.groups, group).parameters.items():
        if shape_name is not None and parameter_name != shape_name:
            continue
        rendered_values = lambda_render_parameter_value(group, parameter_name, parameter_values, meta_presets)
        sep = meta_presets.word_separator
        if not isinstance(rendered_values, list):
            rendered_values = [rendered_values]
        for rendered_value in rendered_values:
            parameters.append(
                (
                    f"{group}{sep}{parameter_name}{sep}{rendered_value}",
                    rendered_value,
                )
            )
    return parameters


def get_parameter(
    group: str,
    name: str,
    meta_presets: StructuredPresets,
) -> Iterable | None:
    """
    Renders a single parameter for a given group.
    """
    if name not in getattr(meta_presets.groups, group).parameters:
        return None

    return lambda_render_parameter_value(
        group, name, getattr(meta_presets.groups, group).parameters[name], meta_presets
    )


param_renderer_map: dict[str, Callable] = {
    "configure": configure_parameter_renderer,
    "build": no_op_parameter_renderer,
    "test": no_op_parameter_renderer,
    "package": no_op_parameter_renderer,
    "workflow": workflow_parameter_renderer,
}
