#
# Copyright Amazon.com Inc. or its affiliates.
# SPDX-License-Identifier: MIT
#
"""This is a sample python file for testing functions from the source code."""

from __future__ import annotations

import pytest

from tcpm import cli_main


def test_hello():
    """ """
    with pytest.raises(SystemExit) as wrapped_exception:
        cli_main(["--help"])
    assert wrapped_exception.type == SystemExit
    assert wrapped_exception.value.code == 0
