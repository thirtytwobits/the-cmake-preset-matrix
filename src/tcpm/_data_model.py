#
# Copyright Amazon.com Inc. or its affiliates.
# SPDX-License-Identifier: MIT
#
"""
Data model for the presets file.
"""

from dataclasses import dataclass

from ._errors import VendorDataError

__vendor_data_version__ = 1
__default_word_separator__ = "-"


@dataclass
class PresetGroup:
    """
    Structured representation of a preset group.
    """

    name: str
    prefix: str
    common: list[str]
    shape: dict
    static: dict[str, str]
    parameters: dict[str, list]


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


@dataclass
class StructuredPresets:
    """
    Structured representation of the presets file.
    """

    source: dict
    version: int
    word_separator: str
    groups: Presets


def make_default_meta_presets() -> StructuredPresets:
    """
    Create a structured representation of an empty presets file.
    """
    groups = Presets(
        configure=PresetGroup("", "", [], {}, {}, {}),
        build=PresetGroup("", "", [], {}, {}, {}),
        test=PresetGroup("", "", [], {}, {}, {}),
        package=PresetGroup("", "", [], {}, {}, {}),
        workflow=PresetGroup("", "", [], {}, {}, {}),
    )

    meta_presets: StructuredPresets = StructuredPresets(
        source={},
        version=__vendor_data_version__,
        word_separator=__default_word_separator__,
        groups=groups,
    )
    for preset_group_name, _ in groups.__annotations__.items():
        group = getattr(groups, preset_group_name)
        group.name = preset_group_name
        group.prefix = f"{preset_group_name}{meta_presets.word_separator}"
        group.common = []
        group.shape = {}
        group.static = {}
        group.parameters = {}

    return meta_presets


def get_preset_group_names() -> list[str]:
    """
    Get the names of the preset groups.
    """
    return [f"{group}Presets" for group in list(Presets.__annotations__.keys())]


def make_meta_presets(json_presets: dict) -> StructuredPresets:
    """
    Create a structured representation of a presets file.
    """

    if "vendor" not in json_presets:
        raise VendorDataError("The presets file does not contain the 'vendor' key.")

    try:
        preset_matrix_regen_vendor_data = json_presets["vendor"]["preset-matrix-regen"]
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
    if "word_separator" in preset_matrix_regen_vendor_data:
        meta_presets.word_separator = preset_matrix_regen_vendor_data["word_separator"]

    for preset_group_name, preset_group in preset_matrix_regen_vendor_data["preset-groups"].items():
        group = getattr(meta_presets.groups, preset_group_name)
        group.name = preset_group_name
        group.prefix = (
            preset_group["prefix"] if "prefix" in preset_group else f"{preset_group_name}{meta_presets.word_separator}"
        )
        group.common = preset_group["common"] if "common" in preset_group else []
        group.shape = preset_group["shape"] if "shape" in preset_group else {}
        group.parameters = preset_group["parameters"] if "parameters" in preset_group else {}

    return meta_presets
