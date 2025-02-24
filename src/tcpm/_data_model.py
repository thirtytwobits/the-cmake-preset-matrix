#
# Copyright Amazon.com Inc. or its affiliates.
# SPDX-License-Identifier: MIT
#
"""
Data model for the presets file.
"""

from dataclasses import dataclass
from typing import Any, Iterable

from ._errors import VendorDataError

__vendor_data_version__ = 1
__default_word_separator__ = "-"
__vendor_section_key__ = "tcpm"


class ScopedParameter:
    """
    A parameter key/value pair scoped to a preset.
    """

    def __init__(self, sep: str, group: str, parameter: str, value: str):
        self._sep = sep
        self._group = group
        self._parameter = parameter
        self._value = value

    @property
    def preset_scope(self) -> str:
        return f"{self._group}{self._sep}{self._parameter}{self._sep}{self._value}"

    @property
    def group(self) -> str:
        return self._group

    @property
    def parameter(self) -> str:
        return self._parameter

    @property
    def value(self) -> str:
        return self._value

    def __getitem__(self, field_name: str | int) -> Any:
        """
        Python Data Model: subscriptable
        """
        if field_name == 0:
            return self.preset_scope
        elif field_name == 1:
            return self.value
        elif isinstance(field_name, int):
            raise IndexError(f"Index out of range: {field_name}")
        else:
            return getattr(self, field_name)

    def __iter__(self) -> Iterable[str]:
        return iter([self.preset_scope, self.value])


ShapedParameters = dict[str, list[ScopedParameter]]
"""
a dictionary of shapes and their parameters scoped to a preset.
"""

ExcludeList = list[dict[str, str]]
"""
A list of excluded configurations.
"""


@dataclass
class PresetGroup:
    """
    Structured representation of a preset group.
    """

    name: str
    prefix: str
    common: list[str]
    shape: dict
    parameters: dict[str, list]
    shape_parameters: dict[str, list]
    exclude: ExcludeList

    def __getitem__(self, field_name: str) -> Any:
        """
        Python Data Model: subscriptable
        """
        return getattr(self, field_name)


@dataclass
class Presets:
    """
    Structured representation of the presets file.
    """

    configure: PresetGroup
    build: PresetGroup
    test: PresetGroup
    package: PresetGroup
    workflow: PresetGroup

    def __getitem__(self, field_name: str) -> Any:
        """
        Python Data Model: subscriptable
        """
        return getattr(self, field_name)


@dataclass
class StructuredPresets:
    """
    Structured representation of the presets file.
    """

    source: dict
    version: int
    static: dict
    word_separator: str
    on_load: list[str]
    groups: Presets

    def __getitem__(self, field_name: str) -> Any:
        """
        Python Data Model: subscriptable
        """
        return getattr(self, field_name)


def make_default_meta_presets() -> StructuredPresets:
    """
    Create a structured representation of an empty presets file.
    """
    groups = Presets(
        configure=PresetGroup("", "", [], {}, {}, {}, []),
        build=PresetGroup("", "", [], {}, {}, {}, []),
        test=PresetGroup("", "", [], {}, {}, {}, []),
        package=PresetGroup("", "", [], {}, {}, {}, []),
        workflow=PresetGroup("", "", [], {}, {}, {}, []),
    )

    meta_presets: StructuredPresets = StructuredPresets(
        source={},
        version=__vendor_data_version__,
        static={},
        word_separator=__default_word_separator__,
        on_load=[],
        groups=groups,
    )
    for preset_group_name, _ in groups.__annotations__.items():
        group = getattr(groups, preset_group_name)
        group.name = preset_group_name
        group.prefix = f"{preset_group_name}{meta_presets.word_separator}"
    return meta_presets


def get_preset_group_names() -> list[str]:
    """
    Get the names of the preset groups.
    """
    return [f"{group}Presets" for group in list(Presets.__annotations__.keys())]


def backfill_shapes(group: PresetGroup) -> None:
    """
    If no shape is defined for a given parameter backfill with an empty dictionary.
    """
    for parameter_name in group.parameters:
        if parameter_name not in group.shape:
            group.shape[parameter_name] = {}

    for parameter_name in group.shape_parameters:
        if parameter_name not in group.shape:
            group.shape[parameter_name] = {}


def make_meta_presets(json_presets: dict) -> StructuredPresets:
    """
    Create a structured representation of a presets file.
    """

    if "vendor" not in json_presets:
        raise VendorDataError("The presets file does not contain the 'vendor' key.")

    try:
        preset_matrix_regen_vendor_data = json_presets["vendor"][__vendor_section_key__]
    except KeyError as e:
        raise VendorDataError(
            "The presets file does not contain the 'preset_matrix_regen' key within the 'vendor' section."
        ) from e

    try:
        preset_matrix_regen_version = preset_matrix_regen_vendor_data["version"]
    except KeyError as e:
        raise VendorDataError(
            "The presets file does not contain the 'version' key within the 'preset_matrix_regen' section."
        ) from e

    if preset_matrix_regen_version != __vendor_data_version__:
        raise VendorDataError(
            f"Unsupported version of the 'preset_matrix_regen' section: {preset_matrix_regen_version}"
        )

    meta_presets: StructuredPresets = make_default_meta_presets()
    meta_presets.source = json_presets
    meta_presets.version = preset_matrix_regen_version
    try:
        meta_presets.static = preset_matrix_regen_vendor_data["static"]
    except KeyError:
        meta_presets.static = {}

    if "word_separator" in preset_matrix_regen_vendor_data:
        meta_presets.word_separator = preset_matrix_regen_vendor_data["word_separator"]

    if "on_load" in preset_matrix_regen_vendor_data:
        if isinstance(preset_matrix_regen_vendor_data["on_load"], str):
            meta_presets.on_load = [preset_matrix_regen_vendor_data["on_load"]]
        else:
            meta_presets.on_load = preset_matrix_regen_vendor_data["on_load"]
    for preset_group_name, preset_group in preset_matrix_regen_vendor_data["preset-groups"].items():
        group = getattr(meta_presets.groups, preset_group_name)
        group.name = preset_group_name
        group.prefix = preset_group["prefix"] if "prefix" in preset_group else f"{preset_group_name}"
        group.common = preset_group["common"] if "common" in preset_group else []
        group.shape = preset_group["shape"] if "shape" in preset_group else {}
        group.parameters = preset_group["parameters"] if "parameters" in preset_group else {}
        group.shape_parameters = preset_group["shape-parameters"] if "shape-parameters" in preset_group else {}
        group.exclude = preset_group["exclude"] if "exclude" in preset_group else []
        backfill_shapes(group)

    return meta_presets
