#
# Copyright Amazon.com Inc. or its affiliates.
# SPDX-License-Identifier: MIT
#
"""
Argparse parser for the TCPM tool.
"""

import argparse
import textwrap
from pathlib import Path


def make_parser() -> argparse.ArgumentParser:
    """
    Define and parse the command line arguments.
    """

    from tcpm.version import __version__ as tcpm_version  # pylint: disable=import-outside-toplevel

    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter,
        description=textwrap.dedent(
            """
            Generate CMake presets based on given options. See
            https://cmake.org/cmake/help/latest/manual/cmake-presets.7.html for details on cmake presets.

            This script is driven by configuration in the 'vendor' section of the CMakePresets.json file. The
            'tcpm' section of the 'vendor' section is used to generate the presets. The 'tcpm' section must contain
            the following keys:

            * version – The version of the 'tcpm' section. The current version is 1.
            * preset-groups – A dictionary of preset groups. Each group must contain the following keys:

                * prefix – The prefix to use when generating preset names. The default is the group name followed by
                  the word separator.
                * common –  A list of common presets that pre-exist in the presets file and which the group presets
                  should inherit from.
                * shape – A template for the shape of the presets. The shape is a dictionary of keys and values that
                  are used to generate the presets. The values can be either a string or a dictionary of
                  key-value pairs. The key-value pairs are recursively expanded until a string is reached.
                * parameters – A dictionary of named values to use when generating presets.

    """
        ).lstrip(),
        epilog=textwrap.dedent(
            f"""

        Version: {tcpm_version}

    """
        ),
    )

    parser.add_argument(
        "--version",
        action="version",
        version=tcpm_version,
        help="Print the version of the script and exit.",
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
        "--template-file",
        "-t",
        type=Path,
        default=Path("CMakePresets.json"),
        help=textwrap.dedent(
            """
            A file to use as a template for the presets file. The template file is used to generate the presets file
            if it does not exist. If the template file and the presets file are the same, the presets file is updated
            in place using itself as the template. TCPM is designed to be idempotent, so using a presets file as its
            own template will not change the file unless changes are made that affect preset generation.

    """
        ).lstrip(),
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

    parser.add_argument(
        "--verbose",
        "-v",
        action="count",
        help="Print verbose output.",
    )

    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Do not prompt the user for input.",
    )

    parser.add_argument(
        "--backup-file-suffix",
        type=str,
        default=".bak",
        help="The suffix to append to the backup file.",
    )

    parser.add_argument(
        "--no-backup",
        "-nb",
        action="store_true",
        help="Do not create a backup when overwriting the presets file.",
    )

    return parser
