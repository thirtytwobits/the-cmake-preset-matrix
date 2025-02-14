#
# Copyright Amazon.com Inc. or its affiliates.
# SPDX-License-Identifier: MIT
#
"""Verifies the pQuery grammar and parsing functions."""

from __future__ import annotations

from tcpm._pquery import pquery_render


def test_text_get_set():
    """
    Tests of the text function on individual elements.
    """
    test_document = {
        "configurePresets": [
            {"name": "my-preset", "cacheVariables": {"foo": "$(this).text('bar')"}},
            {
                "name": "my-other-preset",
                "cacheVariables": {"foo": "$('#my-preset cacheVariables foo').text()"},
            },
            {
                "name": "yet-another-preset",
                "cacheVariables": {"foo": "$(this).text($('#my-preset cacheVariables foo').text())"},
            },
            {"name": "one-more-preset", "cacheVariables": {"foo": "$(this).text()"}},
        ]
    }
    pquery_render(test_document)
    assert test_document["configurePresets"][0]["cacheVariables"]["foo"] == "bar"
    assert test_document["configurePresets"][1]["cacheVariables"]["foo"] == "bar"
    assert test_document["configurePresets"][2]["cacheVariables"]["foo"] == "bar"
    assert test_document["configurePresets"][3]["cacheVariables"]["foo"] == ""


def test_set_from_multiple():
    """
    Tests of the text function on multiple elements.
    """
    expected_text = "Release;RelSize;Debug"
    test_document = {
        "configurePresets": [
            {
                "name": "my-configure-preset",
                "cacheVariables": {"CMAKE_CONFIGURATION_TYPES": expected_text},
            }
        ],
        "buildPresets": [
            {
                "name": "my-build-preset-0",
                "cacheVariables": {
                    "known_configuration_types": "$('buildPresets #my-build-preset-1 cacheVariables known_configuration_types').text($('configurePresets #my-configure-preset cacheVariables CMAKE_CONFIGURATION_TYPES').text())"
                },
            },
            {
                "name": "my-build-preset-1",
                "cacheVariables": {"known_configuration_types": ""},
            },
            {
                "name": "my-build-preset-2",
                "cacheVariables": {"known_configuration_types": ""},
            },
        ],
    }
    pquery_render(test_document)
    assert test_document["configurePresets"][0]["cacheVariables"]["CMAKE_CONFIGURATION_TYPES"] == expected_text
    assert test_document["buildPresets"][1]["cacheVariables"]["known_configuration_types"] == expected_text
    assert test_document["buildPresets"][2]["cacheVariables"]["known_configuration_types"] == ""
    assert test_document["buildPresets"][0]["cacheVariables"]["known_configuration_types"] == ""
