#
# Copyright Amazon.com Inc. or its affiliates.
# SPDX-License-Identifier: MIT
#
"""Verifies the pQuery grammar and parsing functions."""

from __future__ import annotations

from pathlib import Path

from tcpm._data_model import __vendor_section_key__
from tcpm._pquery import render as pquery_render
from tcpm._pquery import render_fragment as pquery_render_fragment
from tcpm._pquery import render_string_at as pquery_render_string_at


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


def test_set_from_other():
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


def test_if():
    """
    Tests setting text as the result of a conditional.
    """
    test_document = ["$(this).if('baz' == 'bar')"]
    pquery_render_fragment(test_document)
    assert test_document[0] is False

    test_document = ["$(this).if('baz' == 'baz')"]
    pquery_render_fragment(test_document)
    assert test_document[0] is True

    test_document = ["$(this).if('baz' != 'bar')"]
    pquery_render_fragment(test_document)
    assert test_document[0] is True

    test_document = ["$(this).if('baz' != 'baz')"]
    pquery_render_fragment(test_document)
    assert test_document[0] is False

    test_document = ["$(this).if(false)"]
    pquery_render_fragment(test_document)
    assert test_document[0] is False

    test_document = ["$(this).if(true)"]
    pquery_render_fragment(test_document)
    assert test_document[0] is True


def test_if_then_else():
    """
    Tests setting text as the result of a conditional.
    """
    test_document = ["$(this).if('baz' == 'bar', 'yes', 'no')"]
    pquery_render_fragment(test_document)
    assert test_document[0] == "no"

    test_document = ["$(this).if('bar' == 'bar', 'yes', 'no')"]
    pquery_render_fragment(test_document)
    assert test_document[0] == "yes"


def test_literal():
    """
    Tests setting text from a literal value
    """
    test_document = ["$(this).literal('yes')"]
    pquery_render_fragment(test_document)
    assert test_document[0] == "yes"

    test_document = ["$(this).literal('yes').replace('yes', 'no')"]
    pquery_render_fragment(test_document)
    assert test_document[0] == "no"


def test_replace():
    """
    Tests setting text as the result of a conditional.
    """
    test_document = ["$('1').text().replace('Mum', 'Dad')", "Hi Mum"]
    pquery_render_fragment(test_document)
    assert test_document[0] == "Hi Dad"

    test_document = ["$('1').text().replace('-two', '-three').replace('One-', 'Zero-')", "One-through-two"]
    pquery_render_fragment(test_document)
    assert test_document[0] == "Zero-through-three"

    test_document = ["$(this).literal('workflow-gcc').replace('workflow-','')"]
    pquery_render_fragment(test_document)
    assert test_document[0] == "gcc"


def test_text_text():
    """
    Tests calling text twice in a row.
    """
    test_document = ["$(this)", "$(this).text()", "$(this).text().text()"]
    pquery_render_fragment(test_document)
    assert test_document[0] == ""
    assert test_document[1] == ""
    assert test_document[2] == ""


def test_select_this_this():
    """
    Tests selecting this within a nested pQuery statement.
    """
    test_document = {
        "group_one": [
            {
                "this_this": "$(this).text($(this).text())",
                "that_this": "$(this).text('that').text($(this).text())",
                "this_that_this": "$(this).text().text('this_that').text($(this).text())",
            }
        ],
    }
    pquery_render_fragment(test_document)
    assert test_document["group_one"][0]["this_this"] == ""
    assert test_document["group_one"][0]["that_this"] == "that"
    assert test_document["group_one"][0]["this_that_this"] == "this_that"


def test_whitespace():
    """
    Tests selecting this within a nested pQuery statement.
    """
    test_document = [
        """
                        $ ( this )
                            . text ( "hiya" )
                            . text ( )
                     """
    ]
    pquery_render_fragment(test_document)
    assert test_document[0] == "hiya"


def test_split():
    """
    Tests splitting a string.
    """
    test_document = ["one;two;three", "$('0').text().split(';');", ""]
    pquery_render_fragment(test_document)
    assert test_document[0] == "one;two;three"
    assert len(test_document[1]) == 3
    assert test_document[1] == ["one", "two", "three"]


def test_index():
    """
    Tests splitting a string.
    """
    test_document = ["one;two;three", "$('0').text().split(';').get(1)", ""]
    pquery_render_fragment(test_document)
    assert test_document[0] == "one;two;three"
    assert len(test_document[1]) == 3
    assert test_document[1] == "two"


def test_get_json():
    """
    Tests the json function as a getter.
    """
    test_document = {"one": [2, 3, 4], "two": "$('one').json()"}

    pquery_render_fragment(test_document)
    assert test_document["one"] == [2, 3, 4]
    assert test_document["two"] == [2, 3, 4]


def test_set_json():
    """
    Tests the json function as a setter.
    """
    test_document = {"one": [2, 3, 4], "two": [5, 6, 7], "three": "$('two').json($('one').json())"}

    pquery_render_fragment(test_document)
    assert test_document["one"] == [2, 3, 4]
    assert test_document["two"] == [2, 3, 4]


def test_render_string():
    """
    Tests the render_string method
    """
    test_document = ["$('1').text()", "one"]
    pquery_render_string_at(test_document, [0])
    assert test_document[0] == "one"
    assert test_document[1] == "one"


def test_render_string_with_multiple_statements():
    """
    Tests the render_string method
    """
    test_document = ["{$(this).text('one')}, {$(this).text('two')}, {and_word} {$(this).text('three')}", ""]
    pquery_render_string_at(test_document, [0])
    assert test_document[0].format(and_word="and") == "one, two, and three"


def test_render_presets():
    """
    Test rendering a CMakePresets.json file with pQuery statements.
    """
    current_file_path = Path(__file__).parent
    test_document = current_file_path / Path("pquery_test_0.json")
    result = pquery_render(test_document)

    assert result["vendor"][__vendor_section_key__]["static"]["configurationTypeList"] == [
        "Release",
        "RelSize",
        "Debug",
    ]
