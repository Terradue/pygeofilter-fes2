"""Parse CQL2 with pygeofilter while guarding known lossy upstream constructs."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Literal

from lark.exceptions import LarkError
from pygeofilter import ast
from pygeofilter.parsers.cql2_json import parse as json_parse

from .exceptions import InvalidFilterError, UnsupportedOperatorError
from .text_compat import parse_text

if TYPE_CHECKING:
    from collections.abc import Mapping

Language = Literal["cql2-json", "cql2-text"]


def _prepare_json(value: object) -> object:
    """Guard arity and compensate for pygeofilter 0.4's bbox argument order.

    This does not parse CQL2; operator and literal parsing remain upstream.
    T_INTERSECTS is rejected before upstream aliases it to T_OVERLAPS.
    """
    if isinstance(value, list):
        return [_prepare_json(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {key: _prepare_json(item) for key, item in value.items()}
    if value.get("filter-lang", "cql2-json") != "cql2-json":
        raise InvalidFilterError("JSON filter wrapper must specify cql2-json")
    if "op" in value:
        arguments = _validate_arity(result)
        if value.get("op") == "between":
            result["args"] = [arguments[0], arguments[1:]]
    if "bbox" in value:
        result["bbox"] = _bbox_arguments(value["bbox"])

    return result


def _bbox_arguments(bounds: object) -> list[object]:
    dimensions = 4
    if not isinstance(bounds, list) or len(bounds) != dimensions:
        raise InvalidFilterError("Only four-coordinate bounding boxes are supported")
    if any(isinstance(bound, bool) or not isinstance(bound, (int, float)) for bound in bounds):
        raise InvalidFilterError("Bounding box coordinates must be numbers")
    # Upstream Envelope takes x1, x2, y1, y2 rather than GeoJSON bbox order.
    return [bounds[0], bounds[2], bounds[1], bounds[3]]


def _validate_arity(value: Mapping[str, object]) -> list[object]:
    operator = value["op"]
    if operator == "t_intersects":
        raise UnsupportedOperatorError("T_INTERSECTS is not equivalent to FES TOverlaps")
    arguments = value.get("args")
    if not isinstance(arguments, list):
        raise InvalidFilterError("Operator args must be an array")
    if not isinstance(operator, str):
        raise InvalidFilterError("Operator names must be strings")
    expected = {"not": 1, "isNull": 1, "between": 3}.get(operator, 2)
    if operator in {"and", "or"}:
        if len(arguments) < expected:
            raise InvalidFilterError("Logical combinations require at least two operands")
    elif len(arguments) != expected:
        raise InvalidFilterError(f"Invalid arity for {operator!r}")
    return arguments


def parse_cql2(
    expression: str | Mapping[str, object], *, language: Language = "cql2-json"
) -> ast.Node:
    """Parse a CQL2 filter using the installed pygeofilter parsers.

    Args:
        expression: CQL2-Text, serialized CQL2-JSON, or a JSON expression object.
        language: Explicit input syntax; JSON is the default.

    Returns:
        The parsed predicate AST, independent of translator configuration.

    Raises:
        InvalidFilterError: If syntax, arity, language or root type is invalid.
        UnsupportedOperatorError: If parsing would lose predicate semantics.
    """
    try:
        result = _parse(expression, language)
    except (ValueError, TypeError, KeyError, IndexError, AttributeError, LarkError) as error:
        if isinstance(error, InvalidFilterError):
            raise
        raise InvalidFilterError(f"Invalid {language} filter: {error}") from error
    if not isinstance(result, (ast.Predicate, ast.Condition)):
        raise InvalidFilterError("A filter must have a predicate or logical root")
    _repair_like(result)
    return result


def _repair_like(node: ast.Node) -> None:
    # Both upstream parsers incorrectly assign '.' to the CQL2 '_' wildcard.
    if isinstance(node, ast.Like):
        node.singlechar = "_"
    for child in node.get_sub_nodes():
        if isinstance(child, ast.Node):
            _repair_like(child)


def _parse(expression: str | Mapping[str, object], language: Language) -> object:
    if language == "cql2-text":
        if not isinstance(expression, str):
            raise InvalidFilterError("CQL2-Text input must be a string")
        return parse_text(expression)
    if language != "cql2-json":
        raise InvalidFilterError(f"Unsupported filter language: {language!r}")
    document = json.loads(expression) if isinstance(expression, str) else dict(expression)
    prepared = _prepare_json(document)
    if not isinstance(prepared, dict):
        raise InvalidFilterError("CQL2-JSON input must be an expression object")
    return json_parse(prepared)
