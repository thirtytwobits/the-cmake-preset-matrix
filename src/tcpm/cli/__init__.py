#
# Copyright Amazon.com Inc. or its affiliates.
# SPDX-License-Identifier: MIT
#
"""
CLI for the TCPM tool.
"""

import json
import logging
import re
import sys
from dataclasses import fields
from enum import Enum
from pathlib import Path
from typing import Any

from .._core import transform_in_place
from .._data_model import make_meta_presets
from .._utility import PresetWriter, validate_json_schema_for_presets_unless, validate_json_schema_for_result_unless
from ._parser import __script_name__, make_parser

_cli_logger = logging.getLogger(__script_name__)

# TODO: This is a placeholder for localization.
t = str
Translation = str


class InteractiveResult(Enum):
    """
    Possible results from an interactive prompt asking the user a binary question.
    """

    POSITIVE = 1  # the user answered yes, accept, jah, oui, etc.
    NEGATIVE = 2  # the user answered no, decline, ei, non, etc.
    CANCEL = 3  # the user canceled the prompt without answering.
    DEFAULT = 4  # the prompt was forced to the default answer without user input.


def binary_user_prompt_unless(
    user_prompt: Translation,
    positive_response: re.Pattern | Translation,
    force: bool | None = False,
    verbose: bool | int | None = False,
    non_interactive: bool | None = False,
    positive_text: Translation | None = None,
    negative_text: Translation | None = None,
    forced_text: Translation | None = None,
) -> InteractiveResult:
    """
    I18N-aware interactive prompt for the user to answer a yes/no question with switches for non-interactive and forced
    operation.

    :param user_prompt: The localized prompt to ask the user.
    :param positive_response: The localized response that indicates a positive answer.
    :param non_interactive: If True, the prompt is skipped and the default answer is returned.
    :param force: If True, the prompt is forced to the default answer.
    :param verbose: If True, then any text fields set will be printed based on the user's response or the forced text.
    :param positive_text: The localized text to print if the user answers positively and verbose is True.
    :param negative_text: The localized text to print if the user answers negatively and verbose is True.
    :param forced_text: The localized text to print if the prompt is forced and verbose is True.
    :return: The result of the prompt

    .. invisible-code-block: python

        from tcpm.cli import binary_user_prompt_unless, InteractiveResult

    .. code-block:: python

        result = binary_user_prompt_unless(
            t("Do you want to continue? (y/n): "),
            positive_response=t("y"),
            non_interactive=True
        )

    >>> result == InteractiveResult.DEFAULT
    True

    """
    if force or non_interactive:
        if forced_text is not None and verbose:
            print(forced_text)
        return InteractiveResult.DEFAULT
    response = input(user_prompt).strip()
    if not isinstance(positive_response, re.Pattern):
        positive_response = re.compile(positive_response, re.IGNORECASE)
    if not positive_response.match(response):
        if negative_text is not None:
            print(negative_text)
        return InteractiveResult.NEGATIVE
    if positive_text is not None:
        print(positive_text)
    return InteractiveResult.POSITIVE


def write_to_file(args: Any, meta_presets: Any) -> int:
    with PresetWriter(meta_presets, args.presets_file, args.indent, args.backup_file_suffix, args.no_backup) as pw:
        if pw.will_overwrite:
            # are you sure?
            response = binary_user_prompt_unless(
                f"{args.presets_file} already exists. Overwrite? (y/n): ",
                re.compile("y", re.IGNORECASE),
                force=args.force,
                verbose=args.verbose,
                non_interactive=args.non_interactive,
                negative_text="Operation cancelled.",
            )
            if response == InteractiveResult.NEGATIVE:
                return 1
        pw.swap()

    return 0


def write_to_stdout(args: Any, meta_presets: Any) -> int:
    print(json.dumps(meta_presets.source, indent=args.indent))
    return 0


def read_and_merge_template_and_presets(template_file: Path, presets_file: Path) -> dict[str, Any] | None:
    """
    Read the template and presets files and merge them into a single dictionary.
    """
    if template_file.exists():
        with template_file.open("r", encoding="UTF-8") as f:
            json_template = json.load(f)
    else:
        json_template = None

    if presets_file.exists():
        with presets_file.open("r", encoding="UTF-8") as f:
            existing_json_presets = json.load(f)
        if json_template is not None:
            if "vendor" in existing_json_presets and "tcpm" in existing_json_presets["vendor"]:
                del existing_json_presets["vendor"]["tcpm"]
            json_presets = {**json_template, **existing_json_presets}
            json_presets["vendor"]["tcpm"] = json_template["vendor"]["tcpm"]
        else:
            json_presets = existing_json_presets
    else:
        json_presets = json_template

    return json_presets


def cli_main(args: Any | None = None) -> int:
    """
    Idempotent (mostly) generation of CMake presets based the contents of the vendor section of the presets file.
    """
    # pylint: disable=too-many-branches, too-many-return-statements
    if args is None:
        args = sys.argv[1:]

    args = make_parser().parse_args(args)

    if args.stdout:
        logging.Logger.setLevel(_cli_logger, logging.ERROR)
        if not args.non_interactive:
            _cli_logger.warning(
                "Writing to stdout in interactive mode. Use --non-interactive to ensure only JSON is output."
            )
    elif args.verbose:
        logging.Logger.setLevel(_cli_logger, logging.DEBUG)
    else:
        logging.Logger.setLevel(_cli_logger, logging.INFO)

    json_presets = read_and_merge_template_and_presets(args.template_file, args.presets_file)
    if json_presets is None:
        _cli_logger.error("No presets file found.")
        return 1
    meta_presets = make_meta_presets(json_presets)

    try:
        if not validate_json_schema_for_presets_unless(
            args.no_schema_validation, args.presets_schema_url, meta_presets.source
        ):
            return 1
    except ImportError:
        response = binary_user_prompt_unless(
            "jsonschema python module is required to validate the schema. Okay to skip? (y/n): ",
            re.compile("y", re.IGNORECASE),
            forced_text="jsonschema is required to validate the schema. Skipping validation "
            "(--force|--non-interactive).",
            force=args.force,
            verbose=args.verbose,
            non_interactive=args.non_interactive,
        )
        if response == InteractiveResult.NEGATIVE:
            return 1

    skip_list = transform_in_place(meta_presets, args.clean)

    try:
        if not validate_json_schema_for_result_unless(
            args.no_schema_validation, args.presets_schema_url, meta_presets.source
        ):
            return 1
    except ImportError:
        pass

    for group_field in fields(meta_presets.groups):
        group = group_field.name
        groupKey = f"{group}Presets"
        if group in skip_list:
            continue
        if len(meta_presets.source[groupKey]) > args.warn_threshold:
            response = binary_user_prompt_unless(
                f"Warning: {groupKey} contains {len(meta_presets.source[groupKey])} presets (--warn-threshold). "
                "Continue? (y/n): ",
                re.compile("y", re.IGNORECASE),
                force=args.force,
                verbose=args.verbose,
                non_interactive=args.non_interactive,
                forced_text=f"Warning: {groupKey} contains {len(meta_presets.source[groupKey])} presets "
                "(--warn-threshold).",
                negative_text="Operation cancelled.",
            )
            if response == InteractiveResult.NEGATIVE:
                return 1

    if args.stdout:
        return write_to_stdout(args, meta_presets)
    else:
        return write_to_file(args, meta_presets)
