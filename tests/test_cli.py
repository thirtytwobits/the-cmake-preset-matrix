#
# Copyright Amazon.com Inc. or its affiliates.
# SPDX-License-Identifier: MIT
#
"""Tests of the CLI entry point."""

from pathlib import Path
import json

import pytest

from tcpm import cli_main


def test_hello():
    """ """
    with pytest.raises(SystemExit) as wrapped_exception:
        cli_main(["--help"])
    assert wrapped_exception.type == SystemExit
    assert wrapped_exception.value.code == 0


def test_default(capsys: pytest.CaptureFixture):
    """
    Test running the CLI with minimal arguments.
    """
    current_file_path = Path(__file__)
    test_document = current_file_path.parent / Path("CMakePresets.json")
    assert test_document.exists()
    cli_main(["--non-interactive", "--presets-file", test_document.as_posix(), "--stdout"])

    captured = capsys.readouterr().out
    # re-print so we can see the document in pytest output
    print(captured)
    result_document = json.loads(captured)
    assert result_document["version"] == 9


def test_maintains_unmanaged(capsys: pytest.CaptureFixture):
    """
    Makes sure that unmanaged presets are retained.
    """
    current_file_path = Path(__file__).parent
    test_document = current_file_path / Path("preset_test_ignore_unmanaged.json")
    assert test_document.exists()

    cli_main(["--non-interactive", "--presets-file", test_document.as_posix(), "--stdout", "--no-schema-validation"])

    captured = capsys.readouterr().out
    # re-print so we can see the document in pytest output
    print(captured)

    result_document = json.loads(captured)

    assert "manual-entry" in [x["name"] for x in result_document["buildPresets"]]
    assert "another-manual-entry" in [x["name"] for x in result_document["workflowPresets"]]
