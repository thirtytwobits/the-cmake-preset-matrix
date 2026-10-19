#
# Copyright Amazon.com Inc. or its affiliates.
# SPDX-License-Identifier: MIT
#
"""Tests of the CLI entry point."""

from pathlib import Path
import json

import pytest

from tcpm import cli_main
from tcpm.cli import read_and_merge_template_and_presets


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


def test_template_merge_preserves_comments(tmp_path):
    """Keep comments from both input files when existing presets override template fields."""
    template = {
        "version": 10,
        "$comment": "Template note",
        "configurePresets": [{"name": "debug", "$comment": "Template preset note", "generator": "Ninja"}],
        "vendor": {"tcpm": {"version": 1, "preset-groups": {}}},
    }
    existing = {
        "version": 10,
        "$comment": ["Existing note"],
        "configurePresets": [{"name": "debug", "$comment": "Existing preset note", "generator": "Unix Makefiles"}],
        "vendor": {},
    }
    template_path = tmp_path / "template.json"
    presets_path = tmp_path / "presets.json"
    template_path.write_text(json.dumps(template), encoding="UTF-8")
    presets_path.write_text(json.dumps(existing), encoding="UTF-8")

    merged = read_and_merge_template_and_presets(template_path, presets_path)

    assert merged["$comment"] == ["Existing note", "Template note"]
    assert merged["configurePresets"][0]["$comment"] == ["Existing preset note", "Template preset note"]
    assert merged["configurePresets"][0]["generator"] == "Unix Makefiles"


def test_template_merge_preserves_existing_vendor_comments(tmp_path):
    """Template metadata replaces settings while keeping comments on surviving objects."""
    template = {
        "version": 10,
        "vendor": {
            "tcpm": {
                "version": 1,
                "$comment": "Template vendor note",
                "preset-groups": {"build": {"prefix": "new", "parameters": {"mode": ["debug"]}}},
            }
        },
    }
    existing = {
        "version": 10,
        "vendor": {
            "tcpm": {
                "version": 1,
                "$comment": "Existing vendor note",
                "preset-groups": {
                    "$comment": "Groups note",
                    "build": {
                        "prefix": "old",
                        "$comment": ["Build note"],
                        "parameters": {"$comment": "Parameters note", "mode": ["release"]},
                    },
                    "test": {"$comment": "Removed group"},
                },
            }
        },
    }
    template_path = tmp_path / "template.json"
    presets_path = tmp_path / "presets.json"
    template_path.write_text(json.dumps(template), encoding="UTF-8")
    presets_path.write_text(json.dumps(existing), encoding="UTF-8")

    merged = read_and_merge_template_and_presets(template_path, presets_path)

    vendor = merged["vendor"]["tcpm"]
    assert vendor["$comment"] == ["Template vendor note", "Existing vendor note"]
    groups = vendor["preset-groups"]
    assert groups["$comment"] == "Groups note"
    assert groups["build"]["$comment"] == ["Build note"]
    assert groups["build"]["prefix"] == "new"
    assert groups["build"]["parameters"] == {"mode": ["debug"], "$comment": "Parameters note"}
    assert "test" not in groups

    presets_path.write_text(json.dumps(merged), encoding="UTF-8")
    assert read_and_merge_template_and_presets(template_path, presets_path) == merged
