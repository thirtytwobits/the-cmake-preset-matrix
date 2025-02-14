#
# Copyright Amazon.com Inc. or its affiliates.
# SPDX-License-Identifier: MIT
#
"""
This is a configuration file for pytest containing customizations and fixtures.
"""

from doctest import ELLIPSIS

from sybil import Sybil
from sybil.parsers.rest import DocTestParser, PythonCodeBlockParser

pytest_collect_file = Sybil(
    parsers=[
        DocTestParser(optionflags=ELLIPSIS),
        PythonCodeBlockParser(),
    ],
    patterns=["*.rst", "*.py"],
).pytest()
