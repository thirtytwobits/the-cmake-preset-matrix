#
# Copyright Amazon.com Inc. or its affiliates.
# SPDX-License-Identifier: MIT
#
"""
Structured errors for the tcpm package.
"""


class DataModelError(ValueError):
    """
    Raised when the data model is invalid.
    """

    def __init__(self, message: str):
        super().__init__(message)


class SchemaError(DataModelError):
    """
    Raised when the structure of the data is invalid.
    """


class VendorDataError(DataModelError):
    """
    Raised when required vendor data embedded in the presets file is invalid.
    """


class RenderError(RuntimeError):
    """
    Raised when rendering a field fails.
    """

    def __init__(self, message: str):
        super().__init__(message)


class DataError(ValueError):
    """
    Raised when input data is invalid.
    """

    def __init__(self, message: str):
        super().__init__(message)


class PQueryError(ValueError):
    """
    Raised when a pQuery fails to parse.
    """

    def __init__(self, message: str):
        super().__init__(message)


class PQueryLocatorError(PQueryError):
    """
    Raised when a pQuery locator fails to parse.
    """
