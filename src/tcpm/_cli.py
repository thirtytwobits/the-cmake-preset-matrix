#
# Copyright Amazon.com Inc. or its affiliates.
# SPDX-License-Identifier: MIT
#
"""
CLI for the TCPM tool.
"""

import argparse
import json
import sys
import textwrap
from dataclasses import fields
from pathlib import Path
from typing import Any

from ._data_model import make_meta_presets
from ._generators import make_matrix_presets, make_parameter_presets
from ._utility import (
    clean_source,
    merge_preset_list,
    reclean_source,
    validate_json_schema_for_presets_unless,
    validate_json_schema_for_result_unless,
)


def make_parser() -> argparse.ArgumentParser:
    """
    Define and parse the command line arguments.
    """

    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter,
        description=textwrap.dedent(
            """
            Generate CMake presets based on given options. See
            https://cmake.org/cmake/help/latest/manual/cmake-presets.7.html for details on cmake presets.

            This script is driven by configuration in the 'vendor' section of the CMakePresets.json file. The
            'preset-matrix-regen' section of the 'vendor' section is used to generate the presets. The
            'preset-matrix-regen' section must contain the following keys:
            - version: The version of the 'preset-matrix-regen' section. The current version is 1.
            - word_separator: The word separator to use when generating preset names.
            - preset-groups: A dictionary of preset groups. Each group must contain the following keys:
                - prefix:   The prefix to use when generating preset names. The default is the group name followed by
                            the word separator.
                - common:   A list of common presets that pre-exist in the presets file and which the group presets
                            should inherit from.
                - shape:    A template for the shape of the presets. The shape is a dictionary of keys and values that
                            are used to generate the presets. The values can be either a string or a dictionary of
                            key-value pairs. The key-value pairs are recursively expanded until a string is reached.
                            The string can be a lambda function that is evaluated with the following tuple values:
                                - [0] doc: The source json document
                                - [1] parameter: The parameter.
                                - [2] parameter seperator: The word separator.
                                - [3] name: The name of the preset.
                                - [4] groups: The preset groups
                - parameters: A dictionary of named values to use when generating presets.

    """
        ).lstrip(),
        epilog=textwrap.dedent(
            """

        Copyright Amazon.com Inc. or its affiliates.
        Released under SPDX-License-Identifier: MIT

    """
        ),
    )

    parser.add_argument(
        "--indent",
        type=int,
        default=4,
        help="The number of spaces to indent the output by.",
    )

    parser.add_argument(
        "--presets-version",
        type=int,
        default=7,
        help="The required version of the presets file.",
    )

    parser.add_argument("--clean", action="count", help="Clean the presets file of all presets first.")

    parser.add_argument("--no-schema-validation", action="store_true", help="Skip schema validation.")

    parser.add_argument(
        "--presets-schema-url",
        type=str,
        default="https://raw.githubusercontent.com/Kitware/CMake/master/Help/manual/presets/schema.json",
        help="The URL to the schema to validate against.",
    )

    parser.add_argument(
        "--presets-file",
        type=Path,
        default=Path("CMakePresets.json"),
        help="The path to the CMakePresets.json file to update.",
    )

    parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Force overwrite of the CMakePresets.json file.",
    )

    parser.add_argument(
        "--warn-threshold",
        type=int,
        default=150,
        help="The number of presets in any given group that will trigger a warning.",
    )

    return parser


def cli_main(args: Any | None = None) -> int:
    """
    Idempotent (mostly) generation of CMake presets based the contents of the vendor section of the presets file.
    """

    if args is None:
        args = sys.argv[1:]

    args = make_parser().parse_args(args)

    with args.presets_file.open("r", encoding="UTF-8") as f:
        json_presets = json.load(f)

    meta_presets = make_meta_presets(json_presets)

    if not validate_json_schema_for_presets_unless(
        args.no_schema_validation, args.presets_schema_url, args.force, meta_presets.source
    ):
        return 1

    skip_list = set()
    for group_field in fields(meta_presets.groups):
        if f"{group_field.name}Presets" not in meta_presets.source:
            skip_list.add(group_field.name)

    clean_source("configure", args.clean, True, meta_presets)
    hidden_preset_index = make_parameter_presets(
        "configure",
        True,
        meta_presets,
    )
    reclean_source("configure", args.clean, True, meta_presets)  # TODO: I don't think I need reclean anymore
    meta_presets.source["configurePresets"] = merge_preset_list(
        meta_presets.source["configurePresets"], hidden_preset_index
    )

    run_pquery("onConfigure", meta_presets.source)

    clean_source("configure", args.clean, False, meta_presets)
    visible_preset_index = make_matrix_presets(
        "configure",
        False,
        meta_presets,
    )
    reclean_source("configure", args.clean, False, meta_presets)
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

        clean_source(group, args.clean, False, meta_presets)
        preset_index = make_matrix_presets(
            group,
            False,
            meta_presets,
        )
        reclean_source(group, args.clean, False, meta_presets)
        meta_presets.source[groupKey] = merge_preset_list(meta_presets.source[groupKey], preset_index)

    if not validate_json_schema_for_result_unless(
        args.no_schema_validation, args.presets_schema_url, args.force, meta_presets.source
    ):
        return 1

    for group_field in fields(meta_presets.groups):
        group = group_field.name
        groupKey = f"{group}Presets"
        if group in skip_list:
            continue
        if len(meta_presets.source[groupKey]) > args.warn_threshold:
            if args.force:
                print(f"Warning: {groupKey} contains {len(meta_presets.source[groupKey])} presets (--warn-threshold).")
            else:
                response = input(
                    f"Warning: {groupKey} contains {len(meta_presets.source[groupKey])} presets (--warn-threshold). "
                    "Continue? (y/n): "
                )
                if response != "y":
                    print("Operation cancelled.")
                    return 1
    if not args.force and args.presets_file.exists():
        # are you sure?
        response = input(f"{args.presets_file} already exists. Overwrite? (y/n): ").strip().lower()
        if response != "y":
            print("Operation cancelled.")
            return 1

    with args.presets_file.open("w", encoding="UTF-8") as f:
        f.write(json.dumps(meta_presets.source, indent=args.indent))
        f.write("\n")

    return 0
