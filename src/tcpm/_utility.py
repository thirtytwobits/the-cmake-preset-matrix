#
# Copyright Amazon.com Inc. or its affiliates.
# SPDX-License-Identifier: MIT
#
"""
Utility functions for the tcpm package.
"""
from __future__ import annotations

import functools
import hashlib
import json
import logging
import shutil
import urllib.request
from pathlib import Path
from typing import Any, Iterable

from ._data_model import ScopedParameter, StructuredPresets
from ._errors import DataError
from .cli._parser import __script_name__

_utility_logger = logging.getLogger(__script_name__)


def reduce_preset_name(group: str, configuration: Iterable[ScopedParameter], meta_presets: StructuredPresets) -> str:
    return str(
        functools.reduce(
            lambda x, y: f"{x}{meta_presets.word_separator}{y[1]}",
            configuration,
            getattr(meta_presets.groups, group).prefix,
        )
    )


def list_merge(d1: list, d2: list) -> None:
    """
    Merge two lists preventing duplicates but maintaining order. New, non-duplicate items are appended.
    """
    for item in d2:
        if item not in d1:
            d1.append(item)


def deep_merge(d1: dict, d2: dict) -> None:
    """
    merge two dictionary structures ensuring no duplicate keys or list entries are created.
    """
    for key, value in d2.items():
        if key in d1:
            if isinstance(d1[key], dict):
                if isinstance(value, dict):
                    deep_merge(d1[key], value)
                else:
                    d1[key].update(value)
            elif isinstance(d1[key], list):
                list_merge(d1[key], value)
            else:
                d1[key] = value
        else:
            d1[key] = value


def merge_preset_list(d1: list[dict], d2: dict[str, dict]) -> list[dict]:
    """
    Merge new presets into an existing preset list.
    """
    copy_of_d2 = d2.copy()
    for preset in d1:
        preset_name = preset["name"]
        if preset_name in copy_of_d2:
            deep_merge(preset, copy_of_d2.pop(preset_name))

    return d1 + list(copy_of_d2.values())


def filter_matrix_group_by_visibility(
    group: str, hidden: bool, presets: StructuredPresets
) -> tuple[str, dict[str, Any]]:
    def select_clause(p: str, x: dict[str, str | bool]) -> bool:
        return (
            (("hidden" in x and x["hidden"] == hidden) or (not hidden and "hidden" not in x))
            and isinstance(x["name"], str)
            and x["name"].startswith(p)
            and x["name"] not in getattr(presets.groups, group).common
        )

    prefix = f"{getattr(presets.groups, group).prefix}{presets.word_separator}"
    return (
        prefix,
        {d["name"]: d for d in filter(functools.partial(select_clause, prefix), presets.source[f"{group}Presets"])},
    )


@functools.lru_cache
def get_schema(presets_schema_url: str) -> dict:
    with urllib.request.urlopen(presets_schema_url, timeout=10) as response:
        schema_object = json.loads(response.read().decode())
    if not isinstance(schema_object, dict):
        raise DataError("Schema is not a dictionary.")
    return schema_object


def _validate_json_schema(presets_schema_url: str, presets_source: dict) -> bool:
    """
    Validates the preset file against certain assumptions this script makes. If jsonschema and requests is available
    the script will also validate the file against the CMake presets schema pulled from github.
    """
    import jsonschema  # type: ignore # pylint: disable=import-outside-toplevel, import-error

    schema = get_schema(presets_schema_url)

    try:
        jsonschema.validate(instance=presets_source, schema=schema)
    except jsonschema.ValidationError as e:
        _utility_logger.warning("JSON schema validation error: %s", e.message)
        return False

    return True


def validate_json_schema_for_presets(presets_schema_url: str, presets_source: dict) -> bool:
    return _validate_json_schema(presets_schema_url, presets_source)


def validate_json_schema_for_presets_unless(
    no_schema_validation: bool, presets_schema_url: str, presets_source: dict
) -> bool:
    if no_schema_validation:
        _utility_logger.info("Skipping schema validation (--no-schema-validation).")
        return True
    return validate_json_schema_for_presets(presets_schema_url, presets_source)


def validate_json_schema_for_result(presets_schema_url: str, presets_source: dict) -> bool:
    return _validate_json_schema(presets_schema_url, presets_source)


def validate_json_schema_for_result_unless(
    no_schema_validation: bool, presets_schema_url: str, presets_source: dict
) -> bool:
    if no_schema_validation:
        return True
    return validate_json_schema_for_result(presets_schema_url, presets_source)


def _clean_source(
    group: str, clean_level: int | None, pre_clean: bool, hidden: bool, meta_presets: StructuredPresets
) -> None:
    if clean_level == 0 or clean_level is None:
        return

    source_key = f"{group}Presets"

    def hidden_clause(x: dict[str, bool]) -> bool:
        return ("hidden" in x and x["hidden"] == hidden) or ("hidden" not in x and not hidden)

    def common_clause(x: dict[str, Any]) -> bool:
        return x["name"] in getattr(meta_presets.groups, group).common

    def name_clause(x: dict[str, str]) -> bool:
        prefix = f"{getattr(meta_presets.groups, group).prefix}{meta_presets.word_separator}"
        return x["name"].startswith(prefix)

    if (not pre_clean and clean_level == 1) or (pre_clean and clean_level >= 2):
        meta_presets.source[source_key] = [
            preset
            for preset in meta_presets.source[source_key]
            if not hidden_clause(preset) or not name_clause(preset) or common_clause(preset)
        ]


def clean_source(group: str, clean_level: int | None, hidden: bool, meta_presets: StructuredPresets) -> None:
    _clean_source(group, clean_level, True, hidden, meta_presets)


def reclean_source(group: str, clean_level: int | None, hidden: bool, meta_presets: StructuredPresets) -> None:
    _clean_source(group, clean_level, False, hidden, meta_presets)


class PresetWriter:
    """
    Context manager to encapsulate all logic around overwriting an existing presets file including backup file
    generation. The rules enforced include:

    * Write to a temporary file first then compare and overwrite second.
    * Only overwrite if there are changes.
    * Save a backup file of the existing presets/output_file if we are about to overwrite.
        * Don't save a backup file if the user has disabled this
        * Never overwrite an existing backup file

    The context manager returns a PresetWriter object which has two properties and one method:

    * `will_overwrite` (property) - returns True if the input file is different from the output file.
    * `temp_file` (property) - the temporary file was written when the context was entered.
    * `swap` (method, no arguments) - creates a backup of the presets file if the input file is different from the
      output file and copies the temporary file to the output file.

    Not that, if swap is not called before the context manager exits, the temporary file will be deleted and no changes
    will be committed to a file.

    Example usage:

    .. invisible-code-block: python

        from pathlib import Path
        from tcpm._data_model import StructuredPresets, make_default_meta_presets
        from tcpm._utility import PresetWriter
        import tempfile

        meta_presets = make_default_meta_presets()

    The first time we write to a file, if it doesn't already exist, we will not overwrite it so no backup file will be
    created. If we write to the same file again, with different input, we will overwrite it and create a backup file.
    If we write to the same file again, with the same input, we will not overwrite it so no backup file will be created.

    .. code-block:: python

        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "output.json"
            with PresetWriter(meta_presets, output_file, indent=4, backup_suffix="bak") as writer:
                # First time, no backup.
                assert writer.will_overwrite is False
                assert writer.swap() is None

            assert output_file.exists() # Now we have a target file. Let's write to it again with new data.

            meta_presets.source["preset-groups"] = {"group1": {"prefix": "group1_"}}
            with PresetWriter(meta_presets, output_file, indent=4, backup_suffix="bak") as writer:
                assert writer.will_overwrite is True
                assert writer.swap() is not None # Backup file created.

            with PresetWriter(meta_presets, output_file, indent=4, backup_suffix="bak") as writer:
                assert writer.will_overwrite is False
                assert writer.swap() is None # Backup file created.

    :param meta_presets: The structured presets to write to the output file.
    :param output_file: The file to write the structured presets to.
    :param indent: The number of spaces to indent the JSON output.
    :param backup_suffix: The suffix to append to the output file to create a backup file.
    :param no_backup: If True, do not create a backup file.
    """

    def __init__(
        self,
        meta_presets: StructuredPresets,
        output_file: Path,
        indent: int,
        backup_suffix: str,
        no_backup: bool = False,
    ) -> None:
        self._meta_presets = meta_presets
        self._output_file = output_file
        self._indent = indent
        self._no_backup = no_backup
        self._backup_suffix = backup_suffix
        if not self._backup_suffix.startswith("."):
            self._backup_suffix = f".{self._backup_suffix}"
        self._temp_file = self._output_file.with_suffix(".tmp")
        self._will_overwrite = False

    @functools.cached_property
    def temp_file(self) -> Path:
        """
        The temporary file that was written when the context manager was entered.
        """
        with self._temp_file.open(mode="w", encoding="UTF-8") as temp_file:
            temp_file.write(json.dumps(self._meta_presets.source, indent=self._indent))
            temp_file.write("\n")
        return self._temp_file

    @functools.cached_property
    def will_overwrite(self) -> bool:
        """
        Compares the input file to the output file.
        :return: True if the input file is different from the output file or if the output file does not exist.
        """
        if not self.temp_file.exists():
            raise RuntimeError("This property must be called after the context manager has been used.")
        if not self._output_file.exists():
            return False
        with self.temp_file.open("rb") as f:
            input_file_hash = hashlib.sha256(f.read()).hexdigest()
        with self._output_file.open("rb") as f:
            output_file_hash = hashlib.sha256(f.read()).hexdigest()
        return input_file_hash != output_file_hash

    def swap(self) -> Path | None:
        """
        Create a backup of the presets file if the input_file is different from the output_file.
        The backup file will have the same name as the presets file with the specified backup suffix
        appended to the file extension. If a backup file with the same name already exists, a number
        will be appended to the suffix to make the backup file name unique.

        :return: The backup file name if a backup file was created, otherwise None.
        """
        if not self.temp_file.exists():
            raise RuntimeError("This method must be called after the context manager has been used.")

        if self._output_file.exists() and not self.will_overwrite:
            # We don't need to actually do the copy.
            return None

        backup_file = None
        if self._output_file.exists() and not self._no_backup:
            backup_file = self._calculate_backup_filename()
            shutil.copy2(self._output_file, backup_file)

        shutil.copy2(self.temp_file, self._output_file)
        return backup_file

    # +--[PRIVATE]------------------------------------------------------------+
    def _calculate_backup_filename(self) -> Path:
        """
        Reads the filesystem to determine the next available backup file name.
        :return: The backup file name.
        """
        backup_count = 0
        while True:
            backup_file = self._output_file.with_stem(f"{self._output_file.stem}_{backup_count:02}.json").with_suffix(
                self._backup_suffix
            )
            if not backup_file.exists():
                break
            backup_count += 1
        return backup_file

    # +--[CONTEXT MANAGER]----------------------------------------------------+
    def __enter__(self) -> PresetWriter:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,  # pylint: disable=W0613
        traceback: Any,  # pylint: disable=W0613
    ) -> None:
        self.temp_file.unlink()
        del self.temp_file  # reset cached property
        del self.will_overwrite  # reset cached property
