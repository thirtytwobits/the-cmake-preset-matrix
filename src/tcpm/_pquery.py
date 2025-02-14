#
# Copyright Amazon.com Inc. or its affiliates.
# SPDX-License-Identifier: MIT
#
"""
Various functions for rendering values in the presets file.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import partial
from typing import Any, Callable, Sequence

from parsimonious.grammar import Grammar, NodeVisitor
from parsimonious.nodes import Node

import logging

from ._data_model import get_preset_group_names
from ._errors import PQueryError

__pquery_detection_pattern__ = re.compile(r"^\$\s*[\.\(]")

# TODO: [(attribute)[^$!=]=(text)]
# TODO: .setResult() <- call on the core object to manually set the result of a statement.
# TODO: "../" <- parent selector
# TODO: '.' <- current selector (this alias)

__pquery_grammer__ = r"""
pquery_statement = pq_core "(" ws? (literal_selector / selector_list) ws? ")" visitor_call_stack

pq_core = "$"
selector_list = ("'" (ws? quoted_selector)+ ws? "'") / ('"' (ws? quoted_selector)+ ws? '"')
quoted_selector = id_selector / tag_selector
literal_selector = this_selector
visitor = modification / accessor
visitor_selector = "."
visitor_call = visitor_selector visitor
visitor_call_stack = visitor_call*

this_selector = "this"
id_selector = id_hash identifier+
tag_selector = identifier+

id_hash = "#"

modification = set_text
accessor = get_text

set_text = "text" ws? "(" ws? value ws? ")"
get_text = "text" ws? "(" ws? ")"

value       = (identifier / dbl_quoted / sgl_quoted / pquery_statement)
identifier  = ~r"[\w_-]+"
dbl_quoted  = ~'"[^\"]+"'
sgl_quoted  = ~"'[^\']+'"
ws          = ~r"\s*"
"""

Locator = list[str | int]
Location = list | dict


@dataclass
class Selection:
    locators: list[Locator]
    location: Location

    def __str__(self) -> str:
        result = f"@{self.location}\r\n"
        for locator in self.locators:
            result += f"    -> {locator}\r\n"
        return result


DocumentVisitor = Callable[[Locator, Location, Any], bool]


class ReturnValue:
    def __init__(self, value: Any):
        self.value = value

    def __str__(self) -> str:
        return str(self.value)

    def __repr__(self) -> str:
        return repr(self.value)


class PQueryVisitor(NodeVisitor):
    """
    A visitor for the pQuery language.
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
        log_handler: logging.Handler | None = None,
        log_level: int = trace_log_level,
    ) -> None:
        super().__init__()
        self._selection_context: list[list[Selection]] = []
        self._selections: list[Selection] = [Selection([[0]], documents)]
        self._default_this = Selection([locator[:]], location)
        formatter = logging.Formatter("%(name)s - %(message)s")
        handle = logging.StreamHandler() if log_handler is None else log_handler
        handle.setFormatter(formatter)

        self._logger = logging.getLogger("pquery")
        self._logger.setLevel(log_level)
        self._logger.addHandler(handle)

    # +--------------------------------------------------------------------------------------------------------------+
    # | SELECTORS
    # +--------------------------------------------------------------------------------------------------------------+
    def visit_pq_core(self, node: Node, visited_children: Sequence[Any]) -> Any:
        """ """
        if len(self._selections) == 0:
            raise PQueryError("No document. Internal Error!")
        if len(self._selections) == 1:
            self._select_this()
        else:
            self._selection_context.append(self._selections[:])
            last_selection = self._selections[-1]
            self._select_this(last_selection)
        self._logger.log(self.trace_log_level, "pq_core %d: %s", len(self._selection_context), self._get_this())
        return node

    def visit_pquery_statement(self, node: Node, visited_children: Sequence[Any]) -> Any:
        """ """
        statement_value = None
        if len(visited_children) > 0 and isinstance(visited_children[-1], ReturnValue):
            statement_value = visited_children[-1].value
        self._logger.log(self.trace_log_level, "pquery_statement %d: %s", len(self._selection_context), statement_value)
        if len(self._selection_context) > 0:
            self._selections = self._selection_context.pop()
        return statement_value

    def visit_this_selector(self, node: Node, visited_children: Sequence[Any]) -> Any:
        """ """
        self._select_this()
        self._logger.log(self.trace_log_level, "this_selector %d: %s", len(self._selection_context), self._get_this())
        return node

    def visit_id_selector(self, node: Node, visited_children: Sequence[Any]) -> Any:
        """ """
        _, value = visited_children

        def id_selector_visitor(value: str, locator: Locator, location: Location, value_at_location: Any) -> bool:
            if locator[-1] == "name" and value == value_at_location:
                self._select(Selection([locator[:-1]], location))
                self._logger.log(
                    self.trace_log_level, "id_selector %d: %s", len(self._selection_context), self._get_selection()
                )
                return True
            return False

        selector = partial(id_selector_visitor, value.text)

        for selection in reversed(self._selections):
            for locator in selection.locators:
                if self._find_in_document_from_location(locator, selection.location, selector):
                    return node
        raise PQueryError(f"Could not find {value.text} in document")

    def visit_tag_selector(self, node: Node, visited_children: Sequence[Any]) -> Any:
        """ """
        value = visited_children[0]

        def tag_selector_visitor(value: str, locator: Locator, location: Location, _: Any) -> bool:
            if locator[-1] == value:
                self._select(Selection([locator[:]], location))
                self._logger.log(
                    self.trace_log_level, "tag_selector %d: %s", len(self._selection_context), self._get_selection()
                )
                return True
            return False

        selector = partial(tag_selector_visitor, value.text)

        for selection in reversed(self._selections):
            for locator in selection.locators:
                if self._find_in_document_from_location(locator, selection.location, selector):
                    return node
        raise PQueryError(f"Could not find {value.text} in document")

    # +--------------------------------------------------------------------------------------------------------------+
    # | MODIFIERS
    # +--------------------------------------------------------------------------------------------------------------+
    def visit_set_text(self, node: Node, visited_children: Sequence[Any]) -> Any:
        """
        Handles the behaviour of `text` functions when arguments are provided.

        .. invisible-code-block: python

            from tcpm._pquery import pquery_render
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
            pquery_render(test_document)
            assert test_document["configurePresets"][0]["cacheVariables"]["MY_ENV_VAR"] == "why would you do this?"

        Notice in the above example the the `$(this)` selector works in pquery whereever it appears in the document.
        This selects the current field so in this case we are replacing the pquery value itself with the string
        `'why would you do this?'`.
        """
        _, method, _, _, value, *_ = visited_children

        def set_text_visitor(value: str, locator: Locator, location: Location, value_at_location: Any) -> bool:
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
            data = value.text.strip("\"'")
        else:
            data = str(value)
        for locator in selection.locators:
            self._visit_document_from_location(locator, selection.location, partial(set_text_visitor, data))
        return None

    # +--------------------------------------------------------------------------------------------------------------+
    # | ACCESSORS
    # +--------------------------------------------------------------------------------------------------------------+
    def visit_get_text(self, node: Node, visited_children: Sequence[Any]) -> Any:
        """
        Handles the behaviour of `text` functions when no arguments are provided.
        Loads the text value into the result.

        """

        values: list[str] = []

        def get_text_visitor(locator: Locator, location: Location, value_at_location: Any) -> bool:
            values.append(self._get_value(location, locator))
            return True

        selection = self._get_selection()
        for locator in selection.locators:
            self._visit_document_from_location(locator, selection.location, get_text_visitor)

        result = self._string_or_json(values)
        self._logger.log(self.trace_log_level, "get_text %d: %s", len(self._selection_context), result)
        return result

    # +--------------------------------------------------------------------------------------------------------------+
    # | STATEMENTS
    # +--------------------------------------------------------------------------------------------------------------+
    def visit_value(self, node: Node, visited_children: Sequence[Any]) -> Any:
        """Values are statements within modifiers or accessors."""
        lifted = self.lift_child(node, visited_children)
        self._logger.log(self.trace_log_level, "value %d: %s", len(self._selection_context), lifted)
        return lifted

    def visit_visitor(self, node: Node, visited_children: Sequence[Any]) -> Any:
        """ """
        if len(visited_children) == 1:
            return ReturnValue(visited_children[0])
        return ReturnValue(visited_children)

    def visit_visitor_call(self, node: Node, visited_children: Sequence[Any]) -> Any:
        """ """
        if len(visited_children) == 0:
            raise PQueryError("Illegal visitor call (no children).")
        if len(visited_children) == 1:
            return None
        return visited_children[1]

    def visit_visitor_call_stack(self, node: Node, visited_children: Sequence[Any]) -> Any:
        """ """
        if len(visited_children) == 0:
            return None
        return visited_children[0]

    # +--------------------------------------------------------------------------------------------------------------+
    # | NodeVisitor
    # +--------------------------------------------------------------------------------------------------------------+
    grammer = Grammar(__pquery_grammer__)

    unwrapped_exceptions = (PQueryError,)

    def generic_visit(self, node: Node, visited_children: Sequence[Any]) -> Any:
        """The generic visit method."""
        return node

    # +--------------------------------------------------------------------------------------------------------------+
    # | PRIVATE
    # +--------------------------------------------------------------------------------------------------------------+
    @classmethod
    def _string_or_json(cls, value: Any) -> str:
        if isinstance(value, list) and len(value) == 1:
            return str(value[0])
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
            location = location[locator_value]  # type: ignore
        location[locator[-1]] = value  # type: ignore

    @classmethod
    def _set_value_for_all(cls, location: Location, locators: list[Locator], value: Any) -> None:
        for locator in locators:
            cls._set_value(location, locator, value)

    @classmethod
    def _get_value(cls, location: Location, locator: Locator) -> Any:
        for locator_value in locator:
            location = location[locator_value]  # type: ignore
        return location

    @classmethod
    def _get_all_values(cls, location: Location, locators: list[Locator]) -> list[Any]:
        return [cls._get_value(location, locator) for locator in locators]

    @classmethod
    def _visit_document_from_location(cls, locator: Locator, location: Location, visitor: DocumentVisitor) -> bool:
        for locator_index, locator_value in enumerate(locator):
            if locator_index == len(locator) - 1:
                return visitor(locator[locator_index:], location, location[locator_value])  # type: ignore
            if isinstance(location, dict) and locator_value in location:
                location = location[locator_value]
            elif isinstance(location, list) and isinstance(locator_value, int) and locator_value < len(location):
                location = location[locator_value]
            else:
                raise PQueryError(f"Could not find {locator} in {location}")

        return False

    @classmethod
    def _find_in_document_from_location(cls, locator: Locator, location: Location, visitor: DocumentVisitor) -> bool:

        def _find_in_document_from_location_recursive(
            locator: Locator, locator_index: int, location: Location, base_location: Location, visitor: DocumentVisitor
        ) -> bool:
            try:
                element = location[locator[locator_index]]  # type: ignore
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


def pquery_detect(text_maybe: Any) -> bool:
    """
    Detects if a string might contain a pQuery statement. This is an optimization to avoid parsing every string in
    a document and to avoid confusion with `$comment`.

    :param text_maybe: Data to inspect. Must be a str or the detection will return False (no cast to string will occur).
    :return: True if the text may contain a pQuery statement.
    """
    if not isinstance(text_maybe, str):
        return False
    return __pquery_detection_pattern__.match(text_maybe) is not None


def pquery_render(document: dict) -> None:
    """
    Renders all pQuery statements in a document.

    :param document: The document to render. Expansions are done in place.
    """

    def _recursive_pquery_render(locator: Locator, location: Location, documents: Location) -> None:

        def process_value(key_or_index: str | int, value: Any) -> None:
            locator.append(key_or_index)
            if pquery_detect(value):
                pq = PQueryVisitor([key_or_index], location, documents)
                tree = pq.grammer.parse(value)
                location[key_or_index] = ""  # type: ignore
                parse_result = pq.visit(tree)
                if parse_result is not None:
                    location[key_or_index] = parse_result
            elif isinstance(value, dict) or isinstance(value, list):
                _recursive_pquery_render(locator, value, documents)
            locator.pop()

        if isinstance(location, dict):
            for key, value in location.items():
                process_value(key, value)
        elif isinstance(location, list):
            for i, value in enumerate(location):
                process_value(i, value)

    locator: list[str | int] = [0]
    documents = [document]
    for key, value in document.items():
        if key in get_preset_group_names():
            locator.append(key)
            for i, preset in enumerate(value):
                locator.append(i)
                _recursive_pquery_render(locator, preset, documents)
                locator.pop()
            locator.pop()
