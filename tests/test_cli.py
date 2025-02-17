#
# Copyright Amazon.com Inc. or its affiliates.
# SPDX-License-Identifier: MIT
#
"""Tests of the CLI entry point."""

import pytest

from tcpm import cli_main
from pathlib import Path


def test_hello():
    """ """
    with pytest.raises(SystemExit) as wrapped_exception:
        cli_main(["--help"])
    assert wrapped_exception.type == SystemExit
    assert wrapped_exception.value.code == 0


# def test_default():
#     """
#     Test running the CLI with minimal arguments.
#     """
#     current_file_path = Path(__file__).parent
#     test_document = current_file_path / Path("CMakePresets.json")
#     cli_main(["--presets-file", test_document.as_posix()])
