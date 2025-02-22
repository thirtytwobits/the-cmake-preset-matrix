#
# Copyright Amazon.com Inc. or its affiliates.
# SPDX-License-Identifier: MIT
#
"""
Cmake presets has a problem (see https://gitlab.kitware.com/cmake/cmake/-/issues/22538) where a matrix of options
causes a combinatorial explosion of presets that are tedious to generate and maintain. This script automates the
generation and modification of such large lists of presets.

Based on work originally done by @dixonsco on the [OpenCyphal](https://opencyphal.org/) project.
"""
# isort: skip_file

# + ------------------------------------------------------------------------------------------------------------------+
# | LIBRARY EXPORTS                                                                                                   |
# + ------------------------------------------------------------------------------------------------------------------+

from .cli import cli_main
from ._data_model import PresetGroup
from ._data_model import Presets
from ._data_model import StructuredPresets
from ._data_model import make_default_meta_presets
from ._data_model import make_meta_presets
from ._errors import DataModelError
from ._errors import RenderError
from ._errors import SchemaError
from ._errors import VendorDataError
from ._core import transform_in_place

__all__ = [
    "DataModelError",
    "PresetGroup",
    "Presets",
    "RenderError",
    "SchemaError",
    "StructuredPresets",
    "VendorDataError",
    "cli_main",
    "make_default_meta_presets",
    "make_meta_presets",
    "transform_in_place",
]

# + ------------------------------------------------------------------------------------------------------------------+
