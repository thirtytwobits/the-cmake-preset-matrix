#
# Copyright Amazon.com Inc. or its affiliates.
# SPDX-License-Identifier: MIT
#
"""
Various functions for rendering values in the presets file.
"""
# pylint: disable=too-many-lines

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any, Callable, Sequence

from parsimonious.grammar import Grammar
from parsimonious.nodes import Node, NodeVisitor

from ._data_model import __vendor_section_key__, get_preset_group_names
from ._errors import PQueryError, PQueryLocatorError

# +------------------------------------------------------------------------------------------------------------------+
# | The pQuery Language
# +------------------------------------------------------------------------------------------------------------------+
__pquery_detection_pattern__ = re.compile(r"^\s*\$\s*[\.\(]")
__braced_text_pattern__ = re.compile(r"(?<!\\)\{(\s*\$\s*[\.\(].*?)(?<!\\)\}")

# TODO: [(attribute)[^$!=]=(text)]
# [name|=value] Selects elements that have the specified attribute with a value either equal to a given string or
#               starting with that string followed by a word separator.
# [name$=value] Selects elements that have the specified attribute with a value ending exactly with a given string. The
#               comparison is case sensitive.
# [name*=value] Selects elements that have the specified attribute with a value containing a given substring.
# [name~=value] Selects elements that have the specified attribute with a value containing a given word, delimited by
#               spaces.
# [name=value] Selects elements that have the specified attribute with a value exactly equal to a certain value.
# [name!=value] Select elements that either don’t have the specified attribute, or do have the specified attribute but
#               not with a certain value.
# [name^=value] Selects elements that have the specified attribute with a value beginning exactly with a given string.
# [name]        Selects elements that have the specified attribute, with any value.
# [name=”value”][name2=”value2″] Matches elements that match all of the specified attribute filters.

__pquery_grammer__ = r"""
pquery_statement = pq_core "(" ws? (literal_selector / selector_list) ws? ")" visitor_callstack pq_end

pq_core = "$" ws?
pq_end = ";"? ws?

selector_list = ("'" (ws? quoted_selector)+ ws? "'") / ('"' (ws? quoted_selector)+ ws? '"')
quoted_selector = name_selector / tag_selector
literal_selector = this_selector
visitor = set_text / get_text / split / replace / get_json / set_json / if / if_then_else / set_literal / choose_item / get_exp
visitor_selector = ws? "." ws?
visitor_call = visitor_selector visitor
visitor_callstack = visitor_call*

this_selector   = "this"
name_selector   = name_hash identifier+
tag_selector    = identifier+

name_hash       = "#"

split           =  "split" ws? "(" ws? value ws? ")"
replace         = "replace" ws? "(" ws? value ws? "," ws? value ws? ")"
set_literal     = "literal" ws? "(" ws? value ws? ")"
set_text        = "text" ws? "(" ws? value ws? ")"
get_text        = "text" ws? "(" ws? ")"
get_json        = "json" ws? "(" ws? ")"
set_json        = "json" ws? "(" ws? value ws? ")"
get_exp         = "exp" ws? "(" ws? ")"
if              = "if" ws? "(" ws? conditional ws? ")"
if_then_else    = "if" ws? "(" ws? conditional ws? "," ws? value ws? "," ws? value ws? ")"
choose_item     = "get" ws? "(" ws? value ws? ")"

statement       = conditional / value
value           = identifier / dbl_quoted / sgl_quoted / pquery_statement

attr_compare    = "==" / "!=" / "$=" / "^="
conditional     = (value ws? attr_compare ws? value) / true / false
identifier      = ~r"[\w_-]+"
dbl_quoted      = ~'"[^\"]*"'
sgl_quoted      = ~"'[^\']*'"
ws              = ~r"\s*"
true            = "true"
false           = "false"
"""

# +------------------------------------------------------------------------------------------------------------------+
# | TYPES
# +------------------------------------------------------------------------------------------------------------------+
Locator = list[str | int]  # A list of keys or indexes to locate a value in a document.
Location = list | dict  # A location in a document. Either a list or a dictionary.


def _safe_set(location: Location, key_or_index: str | int, value: Any) -> Any:
    """
    Utility for setting a value in a location. This function is used to set values in a location raising only
    PQueryErrors if the location is malformed.

    :param location: The location to set the value in.
    :param key_or_index: The key or index to set the value at.
    :param value: The value to set.
    :return: The value set.
    :raises PQueryError: If the location is malformed.

    .. invisible-code-block: python

        from tcpm._pquery import _safe_set, PQueryError
        from pytest import raises

        test_document = ['one']

        assert _safe_set(test_document[:], 0, 'two') == 'two'
        # some edge cases
        with raises(PQueryError):
            _safe_set(test_document[:], 1, "value")
        with raises(PQueryError):
            _safe_set(test_document[:], "not_an_int", "value")
        with raises(PQueryError):
            _safe_set(1, "0", "value")

    """
    if isinstance(location, dict):
        location[key_or_index] = value
    elif isinstance(location, list):
        try:
            index = int(key_or_index)
        except ValueError as e:
            raise PQueryError(f"Malformed location given to _safe_set: {key_or_index}") from e
        try:
            location[index] = value
        except IndexError as e:
            raise PQueryError(f"Malformed location given to _safe_set: {key_or_index}") from e
    else:
        raise PQueryError(f"Malformed location given to _safe_set: {key_or_index}")
    return value


def _safe_get(location: Location, key_or_index: str | int) -> Any:
    """
    Utility for getting a value in a location. This function is used to get values in a location raising only
    PQueryErrors if the location is malformed.

    :param location: The location to get the value from.
    :param key_or_index: The key or index to get the value at.
    :return: The value at the location.
    :raises PQueryError: If the location is malformed.

    .. invisible-code-block: python

        from tcpm._pquery import _safe_set, PQueryError
        from pytest import raises

        assert "one" == _safe_get(['one'], 0)
        assert "one" == _safe_get({'key': 'one'}, 'key')

        with raises(PQueryError):
            _safe_get(['one'], 1)

        with raises(PQueryError):
            _safe_get({'key': 'one'}, 'not_a_key')

        with raises(PQueryError):
            _safe_get(1, 0)

        with raises(PQueryError):
            _safe_get([1], 'not_an_int')

    """
    if isinstance(location, dict):
        try:
            return location[key_or_index]
        except KeyError as e:
            raise PQueryError(f"Malformed location given to _safe_get: {key_or_index}") from e
    elif isinstance(location, list):
        try:
            index = int(key_or_index)
        except ValueError as e:
            raise PQueryError(f"Malformed location given to _safe_get: {key_or_index}") from e
        try:
            return location[index]
        except IndexError as e:
            raise PQueryError(f"Malformed location given to _safe_get: {key_or_index}") from e
    else:
        raise PQueryError(f"Malformed location given to _safe_get: {key_or_index}")
    return location


@dataclass
class Selection:
    """
    Type that stores selected locations in a document.
    Use `locate` to get the value at the location.
    """

    locators: list[Locator]  # The locators to the selected locations.
    location: Location  # the location within the document all locators are relative to.

    def __str__(self) -> str:
        result = f"@{self.location}\r\n"
        for locator in self.locators:
            result += f"    -> {locator}\r\n"
        return result


DocumentVisitor = Callable[[Locator, Location, Any], bool]
"""
A function that visits document locations.

:param locator: The address of the current value being visited.
:param location: The location the value is in.
:param value_at_location: The value.
:return: Semantics are up to the consumer.

:raises PQueryError: If given a malformed location or locator.
"""


# +------------------------------------------------------------------------------------------------------------------+
# | PARSER
# +------------------------------------------------------------------------------------------------------------------+


# pylint: disable=too-many-public-methods
class ReturnValue:
    """
    Type returned from a pQuery statement.
    """

    def __init__(self, value: list[Any] | Any | None):
        self.value = value

    def __str__(self) -> str:
        return str(self.value)

    def __repr__(self) -> str:
        return repr(self.value)


class PQueryVisitor(NodeVisitor):
    """
    A parsimonious node visitor for the pQuery language.
    """

    trace_log_level = int(logging.DEBUG / 2)
    logging.addLevelName(trace_log_level, "PQ_TRACE")

    # +--------------------------------------------------------------------------------------------------------------+
    # | LIFE CYCLE
    # +--------------------------------------------------------------------------------------------------------------+
    def __init__(
        self,
        locator: Locator,
        location: Location,
        documents: Location,
        word_separator: str = "-",
        log_level: int = logging.WARNING,
        log_handler: logging.Handler | None = None,
    ) -> None:
        super().__init__()
        self._selection_context: list[tuple[list[Selection], list[ReturnValue | None]]] = []
        self._selections: list[Selection] = [Selection([[0]], documents)]
        self._default_this = Selection([locator[:]], location)
        self._callstack: list[ReturnValue | None] = []
        self._word_separator = word_separator
        formatter = logging.Formatter("%(name)s - %(message)s")
        handle = logging.StreamHandler() if log_handler is None else log_handler
        handle.setFormatter(formatter)

        self._logger = logging.getLogger("pquery")
        self._logger.setLevel(log_level)
        self._logger.addHandler(handle)

    # +--------------------------------------------------------------------------------------------------------------+
    # | STATEMENTS
    # +--------------------------------------------------------------------------------------------------------------+
    def visit_pq_core(self, node: Node, visited_childeren: Sequence[Any]) -> Any:  # pylint: disable=W0613
        """
        Called when the pQuery core '$' is visited. This is the root of the pQuery statement and is the first node
        visited.

        ```
        $('selectors').text($('selectors').text())
        ▲                   ▲                    ▲▲
        │                   │                    │└─ 1 visit_pquery_statement
        │                   │                    └─ 2 visit_pquery_statement
        │                   └─ 2 visit_pq_core
        └─ 1 visit_pq_core
        ```
        """
        if len(self._selections) == 0:
            raise PQueryError("No document. Internal Error!")
        if len(self._selections) == 1:
            self._select_this()
        else:
            self._selection_context.append((self._selections[:], self._callstack[:]))
            self._callstack.clear()
            last_selection = self._selections[-1]
            self._select_this(last_selection)
        self._logger.log(self.trace_log_level, "pq_core %d: %s", len(self._selection_context), self._get_this())
        return node

    def visit_pq_end(self, node: Node, visited_children: Sequence[Any]) -> Node:  # pylint: disable=W0613
        """
        Called between pQuery statements. This is the last node visited before the pquery_statement is visited.

        ```
        $('selectors').text($('selectors').text(););
        ▲                   ▲                    ▲▲▲▲
        │                   │                    │││└─ 1 visit_pquery_statement
        │                   │                    ││└── 1 visit_pq_end
        └─ 1 visit_pq_core  └─ 2 visit_pq_core   │└─── 2 visit_pquery_statement
                                                 └──── 2 visit_pq_end
        ```
        """
        self._logger.log(self.trace_log_level, "pq_end %d", len(self._selection_context))
        return node

    def visit_pquery_statement(self, _: Node, visited_children: Sequence[Any]) -> ReturnValue | None:
        """
        Called when the complete pQuery statement is visited. This is the last node visited for a statement.

        ```
        $('selectors').text($('selectors').text())
        ▲                   ▲                    ▲▲
        │                   │                    │└─ 1 visit_pquery_statement
        │                   │                    └─ 2 visit_pquery_statement
        │                   └─ 2 visit_pq_core
        └─ 1 visit_pq_core
        ```
        """
        statement_value: ReturnValue | None = None
        if len(visited_children) > 1 and isinstance(visited_children[-2], ReturnValue):
            statement_value = visited_children[-2]
        self._logger.log(self.trace_log_level, "pquery_statement %d: %s", len(self._selection_context), statement_value)
        if len(self._selection_context) > 0:
            self._selections, self._callstack = self._selection_context.pop()
        return statement_value

    def visit_conditional(self, node: Node, visited_children: Sequence[Any]) -> bool:  # pylint: disable=W0613
        """
        Called when a conditional statement is visited.
        """
        conditional_child = visited_children[0]
        if conditional_child.expr_name == "true":
            return True
        if conditional_child.expr_name == "false":
            return False
        statement = conditional_child.children
        lhs = self._de_quote(statement[0])
        operator = statement[2].text
        rhs = self._de_quote(statement[4])
        if operator == "==":
            return lhs == rhs
        if operator == "!=":
            return lhs != rhs
        if operator == "$=":
            return lhs.endswith(rhs)
        if operator == "^=":
            return lhs.startswith(rhs)
        raise PQueryError(f"Unknown operator: {operator}")

    # +--------------------------------------------------------------------------------------------------------------+
    # | SELECTORS
    # +--------------------------------------------------------------------------------------------------------------+

    def visit_this_selector(self, node: Node, visited_children: Sequence[Any]) -> Any:  # pylint: disable=W0613
        """
        Selects the the location the pquery statement is in.
        """
        self._select_this()
        self._logger.log(self.trace_log_level, "this_selector %d: %s", len(self._selection_context), self._get_this())
        return node

    def visit_name_selector(self, node: Node, visited_children: Sequence[Any]) -> Any:
        """
        Selects a dictionary field based on the value of a key "name" in said dictionary.
        """
        _, value = visited_children

        def name_selector_visitor(value: str, locator: Locator, location: Location, value_at_location: Any) -> bool:
            if locator[-1] == "name" and value == value_at_location:
                self._select(Selection([locator[:-1]], location))
                self._logger.log(
                    self.trace_log_level, "name_selector %d: %s", len(self._selection_context), self._get_selection()
                )
                return True
            return False

        selector = partial(name_selector_visitor, value.text)

        for selection in reversed(self._selections):
            for locator in selection.locators:
                if self._find_in_document_from_location(locator, selection.location, selector):
                    return node
        raise PQueryError(f"Could not find {value.text} in document")

    def visit_tag_selector(self, node: Node, visited_children: Sequence[Any]) -> Any:
        """
        Selects an element by it's key if in a dictionary or index if in a list.
        """
        value = visited_children[0]

        def tag_selector_visitor(value: str | int, locator: Locator, location: Location, _: Any) -> bool:
            if locator[-1] == value:
                self._select(Selection([locator[:]], location))
                self._logger.log(
                    self.trace_log_level, "tag_selector %d: %s", len(self._selection_context), self._get_selection()
                )
                return True
            return False

        value_text_or_int = int(value.text) if value.text.isdigit() else value.text

        selector = partial(tag_selector_visitor, value_text_or_int)

        for selection in reversed(self._selections):
            for locator in selection.locators:
                if self._find_in_document_from_location(locator, selection.location, selector):
                    return node
        raise PQueryError(f"Could not find {value.text} in document")

    # +--------------------------------------------------------------------------------------------------------------+
    # | FUNCTIONS
    # +--------------------------------------------------------------------------------------------------------------+
    def visit_visitor_selector(self, node: Node, visited_children: Sequence[Any]) -> Node:  # pylint: disable=W0613
        """
        The . selector is used to separate the visitor from the visitor call. This is the first node visited in a
        visitor function call.
        ```
        $('selectors').text('value')
                      ▲           ▲▲▲▲
                      │           ││││
                      │           │││└─ visitor_call
                      │           ││└─ visitor
                      │           │└─ (function)
                      │           └─ value?
                      └─ visitor_selector <---------------------[0:visit_visitor_selector]
        ```
        """
        self._logger.log(
            self.trace_log_level,
            "%s %d: %s",
            "fn:selector()",
            len(self._selection_context),
            node.full_text[node.start :].strip(),
        )

        return node

    def visit_value(self, node: Node, visited_children: Sequence[Any]) -> Any:
        """
        Values are statements within modifiers or accessors.
        ```
        $('selectors').text('value')
                      │           ││││
                      ▲           ▲▲▲▲
                      │           │││└─ visitor_call
                      │           ││└─ visitor
                      │           │└─ (function) <--------------[2:visit named function]
                      │           └─ value? <-------------------[1:visit_value]
                      └─ visitor_selector
        ```
        """
        self._logger.log(
            self.trace_log_level,
            "%s %d: %s",
            "fn:value()",
            len(self._selection_context),
            node.full_text[node.start :].strip(),
        )

        lifted = self.lift_child(node, visited_children)
        self._logger.log(self.trace_log_level, "value %d: %s", len(self._selection_context), lifted)
        return lifted

    def visit_visitor(self, node: Node, visited_children: Sequence[Any]) -> ReturnValue:
        """
        This is the visitor itself. It's visited right after the selector and is the last, non-whitespace, node in the
        visitor call.

        ```
        $('selectors').text('value')
                      ▲           ▲▲▲▲
                      │           ││││
                      │           │││└─ visitor_call
                      │           ││└─ visitor <----------------[3:visit_visitor]
                      │           │└─ (function) <--------------[2:visit named function]
                      │           └─ value?
                      └─ visitor_selector
        ```
        """
        self._logger.log(
            self.trace_log_level,
            "%s %d: %s",
            "fn:visitor()",
            len(self._selection_context),
            node.full_text[node.start :].strip(),
        )

        if len(visited_children) == 0:
            raise PQueryError("Illegal visitor (no children).")
        value_perhaps = ReturnValue([c.value if isinstance(c, ReturnValue) else c for c in visited_children])
        if value_perhaps.value is not None and isinstance(value_perhaps.value, list) and len(value_perhaps.value) == 1:
            value_perhaps = ReturnValue(
                value_perhaps.value[0].value
                if isinstance(value_perhaps.value[0], ReturnValue)
                else value_perhaps.value[0]
            )
        return value_perhaps

    def visit_visitor_call(self, node: Node, visited_children: Sequence[Any]) -> Node:
        """
        This is the visitor call itself. It's visited right after the visitor and is the last, non-whitespace, node in
        the visitor call.

        ```
        $('selectors').text('value')
                      ▲           ▲▲▲▲
                      │           ││││
                      │           │││└─ visitor_call <----------[4:visit_visitor_call]
                      │           ││└─ visitor
                      │           │└─ (function)
                      │           └─ value?
                      └─ visitor_selector
        ```
        """
        self._logger.log(
            self.trace_log_level,
            "%s %d: %s",
            "fn:call()",
            len(self._selection_context),
            node.full_text[node.start :].strip(),
        )

        if len(visited_children) == 0:
            raise PQueryError("Illegal visitor call (no children).")
        if len(visited_children) > 1:
            self._callstack.append(visited_children[1])
        else:
            self._callstack.append(None)
        return node

    def visit_visitor_callstack(
        self, node: Node, visited_children: Sequence[Any]  # pylint: disable=W0613
    ) -> None | ReturnValue:
        """
        This is the visitor call stack. It's visited right after the last visitor call in a sequence of visitor calls.

        ```
        $('selectors').text('value')  .text('value')
                      ▲           ▲▲▲▲   ...        ▲
                      │           ││││              └─ visitor_callstack <-----[5:visit_visitor_callstack]
                      │           │││└─ visitor_call
                      │           ││└─ visitor
                      │           │└─ (function)
                      │           └─ value?
                      └─ visitor_selector
        ```
        """
        self._logger.log(
            self.trace_log_level,
            "%s %d: %s",
            "fn:callstack()",
            len(self._selection_context),
            node.full_text[node.start :].strip(),
        )
        if len(self._callstack) > 0:
            top_value = self._callstack.pop()
            self._callstack.clear()
            return top_value
        else:
            return None

    # +--------------------------------------------------------------------------------------------------------------+
    # | FUNCTIONS::MODIFIERS
    # +--------------------------------------------------------------------------------------------------------------+
    def visit_split(self, node: Node, visited_children: Sequence[Any]) -> Any:  # pylint: disable=W0613
        """
        Handles the behaviour of `split` functions when arguments are provided.
        """
        splitter = self._de_quote(visited_children[4])
        what_to_split = self._get_last_return_value()
        if what_to_split is None or what_to_split.value is None:
            raise PQueryError("Nothing to split.")
        if isinstance(what_to_split.value, list):
            for i, returned_value in enumerate(what_to_split.value):
                if isinstance(returned_value, Node):
                    what_to_split.value[i] = returned_value.text.split(splitter)
                elif isinstance(returned_value, str):
                    what_to_split.value[i] = returned_value.split(splitter)
        else:
            what_to_split.value = what_to_split.value.split(splitter)
        return what_to_split

    def visit_choose_item(self, node: Node, visited_children: Sequence[Any]) -> Any:
        """
        Handles the behaviour of `get` functions when arguments are provided.
        """
        chooser = self._de_quote(visited_children[4])
        what_to_choose = self._get_last_return_value()
        if what_to_choose is None or what_to_choose.value is None:
            raise PQueryError("Nothing to get.")
        chosen = what_to_choose.value
        if isinstance(what_to_choose.value, dict):
            try:
                chosen = what_to_choose.value.get(chooser)
            except KeyError as e:
                raise PQueryError(f"Key not found: {node.full_text}") from e
        else:
            try:
                chosen = what_to_choose.value[int(chooser)]
            except IndexError as e:
                raise PQueryError(f"Index out of range: {node.full_text}") from e
        return chosen

    def visit_replace(self, node: Node, visited_children: Sequence[Any]) -> Any:  # pylint: disable=W0613
        """
        Handles the behaviour of `replace` functions when arguments are provided.
        """
        old_value = self._de_quote(visited_children[4])
        new_value = self._de_quote(visited_children[8])
        what_to_replace = self._get_last_return_value()
        if what_to_replace is None or what_to_replace.value is None:
            raise PQueryError("Nothing to replace.")
        if isinstance(what_to_replace.value, list):
            for i, returned_value in enumerate(what_to_replace.value):
                if isinstance(returned_value, Node):
                    what_to_replace.value[i] = returned_value.text.replace(old_value, new_value)
                elif isinstance(returned_value, str):
                    what_to_replace.value[i] = returned_value.replace(old_value, new_value)
        else:
            what_to_replace.value = what_to_replace.value.replace(old_value, new_value)
        return what_to_replace

    # pylint: disable=R1711
    def visit_set_text(self, node: Node, visited_children: Sequence[Any]) -> Any:  # pylint: disable=W0613
        """
        Handles the behaviour of `text` functions when arguments are provided.

        .. invisible-code-block: python

            from tcpm._pquery import render
            import json

        .. code-block:: python

            test_document = '''
            {
                "configurePresets": [
                    {
                        "name": "my-preset",
                        "cacheVariables": {
                            "MY_ENV_VAR": "$(this).text('why would you do this?')"
                        }
                    }
                ]
            }
            '''
            test_document = json.loads(test_document.strip())
            render(test_document)
            assert test_document["configurePresets"][0]["cacheVariables"]["MY_ENV_VAR"] == "why would you do this?"

        Notice in the above example the the `$(this)` selector works in pquery whereever it appears in the document.
        This selects the current field so in this case we are replacing the pquery value itself with the string
        `'why would you do this?'`.
        """
        _, _, _, _, value, *_ = visited_children

        def set_text_visitor(
            value: str, locator: Locator, location: Location, value_at_location: Any  # pylint: disable=W0613
        ) -> bool:
            self._set_value(location, locator, value)
            self._logger.log(
                self.trace_log_level,
                "set_text %d: %s",
                len(self._selection_context),
                self._get_value(location, locator),
            )
            return True

        selection = self._get_selection()
        if isinstance(value, Node):
            data = self._de_quote(value)
        else:
            data = str(value)
        for locator in selection.locators:
            self._visit_document_from_location(locator, selection.location, partial(set_text_visitor, data))
        return None

    def visit_set_literal(self, node: Node, visited_children: Sequence[Any]) -> Any:  # pylint: disable=W0613
        """
        Handles the behaviour of `literal` functions when arguments are provided.
        """
        return self._de_quote(visited_children[4])

    # pylint: disable=R1711
    def visit_set_json(self, node: Node, visited_children: Sequence[Any]) -> Any:  # pylint: disable=W0613
        """
        Handles the behaviour of `json` functions when arguments are provided.
        """
        _, _, _, _, value, *_ = visited_children

        def set_json_visitor(
            value: Any, locator: Locator, location: Location, value_at_location: Any  # pylint: disable=W0613
        ) -> bool:
            self._set_value(location, locator, value)
            self._logger.log(
                self.trace_log_level,
                "set_json %d: %s",
                len(self._selection_context),
                self._get_value(location, locator),
            )
            return True

        selection = self._get_selection()
        data = value
        if isinstance(value, Node):
            data = value.text
        if isinstance(value, ReturnValue):
            data = value.value
        for locator in selection.locators:
            self._visit_document_from_location(locator, selection.location, partial(set_json_visitor, data))
        return None

    # +--------------------------------------------------------------------------------------------------------------+
    # | FUNCTIONS::ACCESSORS
    # +--------------------------------------------------------------------------------------------------------------+
    def visit_get_text(self, node: Node, visited_children: Sequence[Any]) -> Sequence[str]:  # pylint: disable=W0613
        """
        Handles the behaviour of `text` functions when no arguments are provided.

        :return: The text values for the current selection.
        """

        values: list[str] = []

        def get_text_visitor(
            locator: Locator, location: Location, value_at_location: Any  # pylint: disable=W0613
        ) -> bool:
            values.append(self._get_value(location, locator))
            return True

        selection = self._get_selection()
        for locator in selection.locators:
            self._visit_document_from_location(locator, selection.location, get_text_visitor)

        result = self._string_or_json(values)
        self._logger.log(self.trace_log_level, "get_text %d: %s", len(self._selection_context), result)
        return result

    def visit_get_json(self, node: Node, visited_children: Sequence[Any]) -> Sequence[str]:  # pylint: disable=W0613
        """
        Handles the behaviour of `json` functions when no arguments are provided.

        :return: The structure for the current selection.
        """

        values: list[Any] = []

        def get_json_visitor(
            locator: Locator, location: Location, value_at_location: Any  # pylint: disable=W0613
        ) -> bool:
            values.append(self._get_value(location, locator))
            return True

        selection = self._get_selection()
        for locator in selection.locators:
            self._visit_document_from_location(locator, selection.location, get_json_visitor)

        result = values[0] if len(values) == 1 else values
        self._logger.log(self.trace_log_level, "get_json %d: %s", len(self._selection_context), result)
        return result

    def visit_get_exp(self, node: Node, visited_children: Sequence[Any]) -> Any:  # pylint: disable=W0613
        """
        Handles the behaviour of `exp` functions when no arguments are provided.
        """
        return node.full_text

    # +--------------------------------------------------------------------------------------------------------------+
    # | FUNCTIONS::FLOW CONTROL
    # +--------------------------------------------------------------------------------------------------------------+

    def visit_if(self, node: Node, visited_children: Sequence[Any]) -> bool:  # pylint: disable=W0613
        """
        Handles the behaviour of `if` functions when arguments are provided.
        """
        _, _, _, _, conditional, *_ = visited_children
        if not isinstance(conditional, bool):
            raise PQueryError("Internal error: if not given conditional.")
        return conditional

    def visit_if_then_else(self, node: Node, visited_children: Sequence[Any]) -> Any:  # pylint: disable=W0613
        """
        Handles the behaviour of `if` functions when arguments are provided.
        """
        _, _, _, _, conditional, _, _, _, true_value, _, _, _, false_value, *_ = visited_children
        if not isinstance(conditional, bool):
            raise PQueryError("Internal error: if not given conditional.")
        return self._de_quote(true_value) if conditional else self._de_quote(false_value)

    # +--------------------------------------------------------------------------------------------------------------+
    # | NodeVisitor
    # +--------------------------------------------------------------------------------------------------------------+
    grammer = Grammar(__pquery_grammer__)

    unwrapped_exceptions = (PQueryError,)

    def generic_visit(self, node: Node, visited_children: Sequence[Any]) -> Any:  # pylint: disable=W0613
        """
        The generic visit method. Called by default when a node is visited and no specific method is defined for the
        node.
        """
        return node

    # +--------------------------------------------------------------------------------------------------------------+
    # | PRIVATE
    # +--------------------------------------------------------------------------------------------------------------+
    def _de_quote(self, node: Node) -> str:
        """
        Removes the quotes from a node.

        :param node: The node to remove quotes from.
        :return: The node without quotes.
        """
        if node.expr_name == "dbl_quoted":
            return node.text.strip('"')
        if node.expr_name == "sgl_quoted":
            return node.text.strip("'")
        if node.expr.name == "value":
            return self._de_quote(node.children[0])
        return node.text

    def _get_last_return_value(self) -> ReturnValue | None:
        if len(self._callstack) > 0:
            return self._callstack[-1]
        return None

    @classmethod
    def _string_or_json(cls, value: Any) -> str:
        if isinstance(value, list) and len(value) == 1:
            return str(value[0]) if value[0] is not None else ""
        else:
            return json.dumps(value)

    def _get_this(self) -> Selection:
        if len(self._selections) < 2:
            raise PQueryError("This not selected.")
        return self._selections[1]

    def _select_this(self, selection: Selection | None = None) -> Selection:
        # first selection is the document root
        # second selection is location of the pquery
        self._selections = self._selections[:1]
        if selection is not None:
            self._selections.append(Selection(selection.locators[:], selection.location))
        else:
            self._selections.append(Selection(self._default_this.locators[:], self._default_this.location))
        return self._get_selection()

    def _select(self, selection: Selection) -> Selection:
        self._selections.append(selection)
        return self._get_selection()

    def _get_selection(self) -> Selection:
        return self._selections[-1]

    @classmethod
    def _set_value(cls, location: Location, locator: Locator, value: Any) -> None:
        for locator_value in locator[:-1]:
            location = _safe_get(location, locator_value)
        _safe_set(location, locator[-1], value)

    @classmethod
    def _set_value_for_all(cls, location: Location, locators: list[Locator], value: Any) -> None:
        for locator in locators:
            cls._set_value(location, locator, value)

    @classmethod
    def _get_value(cls, location: Location, locator: Locator) -> Any:
        for locator_value in locator:
            location = _safe_get(location, locator_value)
        return location

    @classmethod
    def _get_all_values(cls, location: Location, locators: list[Locator]) -> list[Any]:
        return [cls._get_value(location, locator) for locator in locators]

    @classmethod
    def _visit_document_from_location(cls, locator: Locator, location: Location, visitor: DocumentVisitor) -> bool:
        for locator_index, locator_value in enumerate(locator):
            if locator_index == len(locator) - 1:
                return visitor(locator[locator_index:], location, _safe_get(location, locator_value))
            if isinstance(location, dict) and locator_value in location:
                location = location[locator_value]
            elif isinstance(location, list) and isinstance(locator_value, int) and locator_value < len(location):
                location = location[locator_value]
            else:
                raise PQueryError(f"Could not find {locator} in {location}")

        return False

    @classmethod
    def _find_in_document_from_location(cls, locator: Locator, location: Location, visitor: DocumentVisitor) -> bool:
        # TODO: refactor
        # pylint: disable=too-many-return-statements,too-many-branches
        def _find_in_document_from_location_recursive(
            locator: Locator, locator_index: int, location: Location, base_location: Location, visitor: DocumentVisitor
        ) -> bool:
            try:
                element = _safe_get(location, locator[locator_index])
            except (KeyError, TypeError, IndexError):
                return False
            need_push = len(locator) == locator_index + 1
            if isinstance(element, dict):
                for key, value in element.items():
                    if need_push:
                        locator.append(key)
                    if visitor(locator, base_location, value):
                        return True
                    if _find_in_document_from_location_recursive(
                        locator, locator_index + 1, element, base_location, visitor
                    ):
                        return True
                    if need_push:
                        locator.pop()
            elif isinstance(element, list):
                for i, value in enumerate(element):
                    if need_push:
                        locator.append(i)
                    if visitor(locator, base_location, value):
                        return True
                    if _find_in_document_from_location_recursive(
                        locator, locator_index + 1, element, base_location, visitor
                    ):
                        return True
                    if need_push:
                        locator.pop()
            else:
                if visitor(locator, base_location, element):
                    return True
            return False

        copy_of_locator = locator[:]
        return _find_in_document_from_location_recursive(copy_of_locator, 0, location, location, visitor)


# +------------------------------------------------------------------------------------------------------------------+
# | PUBLIC
# +------------------------------------------------------------------------------------------------------------------+
def default_replace_value_if_predicate(current_value: Any, pquery_statement_result: Any) -> bool:
    """
    When pQuery statement is executed, the value where it was defined is first set to None. This predicate
    is used to determine if the value should be replaced with the result of the pQuery statement.

    .. invisible-code-block: python

        from tcpm._pquery import default_replace_value_if_predicate


    The first rule is, if the pQuery statement wrote a non-empty value to it's previous location then that value is
    retained.

    >>> default_replace_value_if_predicate("dynamic value", ReturnValue(["result value"]))
    False
    >>> default_replace_value_if_predicate(["dynamic value 0", "dynamic value 1"], ReturnValue(["result value"]))
    False
    >>> default_replace_value_if_predicate(None, ReturnValue(["result value"]))
    True
    >>> default_replace_value_if_predicate("", ReturnValue(["result value"]))
    False

    Notice the last example; the value is an empty string which is not None. This means the query has written the empty
    string to the location and we cannot change this using the result of the pQuery statement.

    The second rule is, if the result of the pQuery statement is None then the value is retained.

    >>> default_replace_value_if_predicate(None, None)
    False
    >>> default_replace_value_if_predicate(None, None)
    False
    >>> default_replace_value_if_predicate(None, ReturnValue(None))
    False
    >>> default_replace_value_if_predicate(None, ReturnValue(['None']))
    True
    >>> default_replace_value_if_predicate(None, ReturnValue([]))
    True
    >>> default_replace_value_if_predicate(None, ReturnValue(""))
    True
    >>> default_replace_value_if_predicate(None, ReturnValue([None]))
    False

    For this last case, note that the result of the pQuery statement is a list containing only None. This is a special
    case where the result is None.


    :param current_value: The current value.
    :param pquery_statement_result: The result of the pQuery statement.
    :return: True if the value should be replaced.
    """
    # pylint: disable=too-many-return-statements
    if current_value is not None:
        return False
    if isinstance(pquery_statement_result, ReturnValue):
        if pquery_statement_result.value is None:
            return False
        if isinstance(pquery_statement_result.value, list):
            for value in pquery_statement_result.value:
                if value is not None:
                    return True
            return len(pquery_statement_result.value) == 0
        return True
    if pquery_statement_result is not None:
        return True
    return False


def replace_value_if(
    location: Location,
    key_or_index: str | int,
    pquery_statement_result: Any,
    predicate: Callable[[Any, Any], bool] = default_replace_value_if_predicate,
) -> bool:
    """
    Replaces a value in a location if the value meets the predicate. This method applies some default transformations to
    to the pquery result to avoid None which is not a valid json entry.

    .. invisible-code-block: python

        from tcpm._pquery import replace_value_if, ReturnValue

        def always_replace_predicate(*args) -> bool:
            return True

        def never_replace_predicate(*args) -> bool:
            return False


    if the pquery result is a list containing only None then the result is None. None is always transformed into an
    empty string.

    .. code-block:: python

        document = [None]

        # The returned value is a list containing only None. This is transformed into an empty string.
        assert replace_value_if(document, 0, ReturnValue([None, None]), always_replace_predicate)
        assert document[0] == ''

        document = [None]

        # The returned value is none. This too is transformed into an empty string.
        assert replace_value_if(document, 0, ReturnValue(None), always_replace_predicate)
        assert document[0] == ''

        assert replace_value_if(document, 0, None, always_replace_predicate)
        assert document[0] == ''

        document = [None]

        # If the predicate doesn't allow replacement this method will still transform None into an empty string.
        assert not replace_value_if(document, 0, ReturnValue([None, None]), never_replace_predicate)
        assert document[0] == ''

    :param location: The location to search.
    :param key_or_index: The key or index to search for.
    :param pquery_statement_result: The value to replace the current value with.
    :param predicate: The predicate to determine if the value should be replaced.
    :return: True if the value was replaced.
    :raises PQueryError: If the location is malformed.
    """
    current_value = _safe_get(location, key_or_index)
    if predicate(current_value, pquery_statement_result):
        modified_result = pquery_statement_result
        if isinstance(modified_result, ReturnValue):
            modified_result = modified_result.value
            if modified_result is not None and isinstance(modified_result, list) and len(modified_result) > 1:
                if len(list(filter(lambda x: x is not None, modified_result))) == 0:
                    modified_result = None
        if modified_result is None:
            modified_result = ""
        _safe_set(location, key_or_index, modified_result)
        return True
    if current_value is None:
        _safe_set(location, key_or_index, "")
    return False


def detect(text_maybe: Any) -> bool:
    """
    Detects if a string might contain a pQuery statement. This is an optimization to avoid parsing every string in
    a document and to avoid confusion with `$comment`.

    .. invisible-code-block: python

        from tcpm._pquery import detect

    >>> detect("$(this).text('value')")
    True
    >>> detect("  $(this).text('value')   ")
    True
    >>> detect("Hello World")
    False
    >>> detect("$comment")
    False

    :param text_maybe: Data to inspect. Must be a str or the detection will return False (no cast to string will occur).
    :return: True if the text may contain a pQuery statement.
    """
    if not isinstance(text_maybe, str):
        return False
    return __pquery_detection_pattern__.match(text_maybe) is not None


def locate(locator: Locator, location: Location) -> Location:
    """
    Returns the value within a given location addressed by the locator.

    Given this fragment:

    .. code-block:: python

        test_document = {
            "one": [ 1, 2, 3 ],
            "two": [ 4, 5, 6 ]
        }

    .. invisible-code-block: python

        from tcpm._pquery import locate, PQueryLocatorError
        from pytest import raises

        # some edge cases
        with raises(PQueryLocatorError):
            locate(["not_a_key"], test_document)
        with raises(PQueryLocatorError):
            locate([0], test_document)
        with raises(PQueryLocatorError):
            locate(["one", "one"], test_document)
        with raises(PQueryLocatorError):
            locate(["one", 3], test_document)

    >>> locate(["two", 1], test_document)
    5

    :param locator: The location address.
    :param location: The location to start from.
    :return: The location addressed by the locator.
    :raises PQueryError: If the location is malformed.
    :raises PQueryLocatorError: If the addresses location cannot be found within the given location.
    """

    for locator_value in locator:
        if isinstance(location, dict):
            try:
                location = location[locator_value]
            except KeyError as e:
                raise PQueryLocatorError(f"Could not find {locator} in {location}") from e
        elif isinstance(location, list):
            try:
                location = location[int(locator_value)]
            except (IndexError, ValueError) as e:
                raise PQueryLocatorError(f"Could not find {locator} in {location}") from e
        else:
            raise PQueryError(f"Malformed location given to locate: {locator}")

    return location


def render_string_at(
    fragment: Location, locator: Locator, start_at: Location | None = None, word_separator: str = "-"
) -> bool:
    """
    Renders any pquery statements embedded in a string at a given location.

    .. invisible-code-block: python

        from tcpm._pquery import render_string_at

    .. code-block:: python

        test_document = ["Bob", "Sally", "I think {$('1').text()} is a silly name."]

        render_string_at(test_document, [2])
        assert test_document[2] == "I think Sally is a silly name."

    """

    if len(locator) < 1:
        return False
    if start_at is None:
        if len(locator) == 1:
            start_at = fragment
        else:
            start_at = locate(locator[:-1], fragment)

    if fragment == start_at:
        # if we are starting at the document level we have to wrap the document/fragment in a list
        # to allow the find methods to iterate over it to find the fragment.
        fragment = [fragment]

    value = locate([locator[-1]], start_at)

    if not isinstance(value, str):
        return False

    key_or_index = locator[-1]
    statements: list[Any] = __braced_text_pattern__.split(value)

    _safe_set(start_at, key_or_index, statements)
    for i, statement in enumerate(statements):
        if detect(statement):
            _safe_set(start_at, key_or_index, statement)
            pq = PQueryVisitor([key_or_index], start_at, fragment, word_separator=word_separator)
            tree = pq.grammer.parse(statement.strip())
            _safe_set(start_at, key_or_index, None)
            _safe_set(statements, i, None)
            parse_result = pq.visit(tree)
            if replace_value_if(start_at, key_or_index, parse_result):
                statements[i] = parse_result.value if isinstance(parse_result, ReturnValue) else parse_result
            else:
                statements[i] = _safe_get(start_at, key_or_index)
    if len(statements) > 1:
        _safe_set(start_at, key_or_index, "".join(statements))
    else:
        _safe_set(start_at, key_or_index, statements[0])
    return True


def render_fragment(
    fragment: Location,
    locator_maybe: Locator | None = None,
    start_at: Location | None = None,
    word_separator: str = "-",
) -> None:
    """
    Renders all pQuery statements in a fragment of json (no schema implied).

    .. invisible-code-block: python

        from tcpm._pquery import render_fragment
        from pytest import raises

    The simplest example is to render an entire fragment:

    .. code-block:: python

        test_document = ["$(this).text('Hello World')"]
        render_fragment(test_document)
        assert test_document[0] == "Hello World"

    You can also render a fragment starting from a specific location:

    .. code-block:: python

        test_document_1 = {
            "one": [
                "$(this).text('Hello World')"
            ],
            "two": [
                "$(this).text('Hello World')"
            ]
        }

        render_fragment(test_document_1, ["one"])
        assert test_document_1["one"][0] == "Hello World"
        assert test_document_1["two"][0] == "$(this).text('Hello World')"

    If the locator address cannot be found within the given fragment then a PQueryLocatorError is raised:

    .. code-block:: python

        another_test_document = {
            "key": [
                "$(this).text('Hello World')"
            ]
        }
        with raises(PQueryLocatorError):
            render_fragment(another_test_document, ["not_a_key"])


    :param fragment: The json to render. Expansions are done in place.
    :param locator_maybe: The location address to start from. If None then the root of the fragment is used.
    :param start_at: The location within the fragment to start rendering from. If None then the locator is used to find
                     the starting location. If the locator is None then this argument is ignored and the root of the
                     fragment is used.
    :param word_separator: The separator to use where specified in comparators. The default follows javascript.
    :raises PQueryError: If pquery statements within the fragment are malformed.
    :raises PQueryLocatorError: If the locator address cannot be found within the given fragment.
    """

    if locator_maybe is None:
        locator = []
        start_at = fragment
    else:
        locator = locator_maybe
        if start_at is None:
            start_at = locate(locator, fragment)

    def process_value(location: Location, key_or_index: str | int, value: Any) -> None:
        locator.append(key_or_index)
        if isinstance(value, str):
            render_string_at(fragment, locator, location, word_separator)
        elif isinstance(value, (dict, list)):
            render_fragment(fragment, locator, value, word_separator)
        locator.pop()

    if isinstance(start_at, dict):
        for key, value in start_at.items():
            process_value(start_at, key, value)
    elif isinstance(start_at, list):
        for i, value in enumerate(start_at):
            process_value(start_at, i, value)


def render(document_or_path: dict | Path, word_separator: str = "-", events: list[str] | None = None) -> dict:
    """
    Renders all pQuery statements in a CMakePresets.json document.

    :param document_or_path: The document to render. Expansions are done in place.
    :param word_separator: The separator to use where specified in comparators. The default follows javascript.
    :param events: A list of events to render.
    :return: The rendered document.
    :raises PQueryError: If pquery statements within the document are malformed.
    :raises FileNotFoundError: If the document path cannot be found.
    """
    if events is None:
        events = []
    if isinstance(document_or_path, Path):
        with document_or_path.open("r") as file:
            document = json.load(file)
    else:
        document = document_or_path

    if not isinstance(document, dict):
        raise PQueryError("Document must be a dictionary.")

    locator: list[str | int] = [0]
    documents = [document]
    if "vendor" in document and __vendor_section_key__ in document["vendor"]:
        locator.append("vendor")
        locator.append(__vendor_section_key__)
        onload = None
        if "onload" in document["vendor"][__vendor_section_key__]:
            if "onload" in events:
                locator.append("onload")
                render_fragment(documents, locator, word_separator=word_separator)
                locator.pop()
            onload = document["vendor"][__vendor_section_key__]["onload"]
            document["vendor"][__vendor_section_key__]["onload"] = []
        render_fragment(documents, locator, word_separator=word_separator)
        if onload is not None:
            document["vendor"][__vendor_section_key__]["onload"] = onload
        locator.pop()
        locator.pop()

    for key, value in document.items():
        if key in get_preset_group_names():
            locator.append(key)
            for i, _ in enumerate(value):
                locator.append(i)
                render_fragment(documents, locator, word_separator=word_separator)
                locator.pop()
            locator.pop()

    return document
