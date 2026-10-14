"""Translate supported CQL2 expressions to FES 2.0 XML entirely offline."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pygeofilter import ast

from .evaluator import FES2Evaluator
from .exceptions import (
    FES2SerializationError,
    InvalidFilterError,
    UnknownPropertyError,
    UnsupportedOperatorError,
)
from .geometry import CRS84
from .parser import parse_cql2
from .properties import FieldType
from .serializer import serialize_filter
from .validation import predicate_operand

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = [
    "FES2Evaluator",
    "FES2SerializationError",
    "FieldType",
    "InvalidFilterError",
    "UnknownPropertyError",
    "UnsupportedOperatorError",
    "parse_cql2",
    "to_fes2",
    "to_fes2_json",
    "to_fes2_text",
]


def to_fes2(
    root: ast.AstType,
    *,
    property_mapping: Mapping[str, str] | None = None,
    namespaces: Mapping[str, str] | None = None,
    strict: bool = True,
    field_types: Mapping[str, FieldType] | None = None,
    crs: str = CRS84,
) -> str:
    """Translate a predicate AST into a Unicode FES 2.0 Filter document.

    Args:
        root: A supported pygeofilter predicate or logical AST.
        property_mapping: Public queryable names mapped to XML property QNames.
        namespaces: Bindings for qualified output property names.
        strict: Reject unmapped names, including when no mapping is supplied.
        field_types: Optional operand categories keyed by public queryable names.
        crs: CRS84 or EPSG:4326 output; spatial input is longitude/latitude.

    Raises:
        InvalidFilterError: If the root, configuration or operands are invalid.
        UnknownPropertyError: If a property is not permitted in strict mode.
        UnsupportedOperatorError: If a node cannot be translated faithfully.
        FES2SerializationError: If a value contains invalid XML text.
    """
    if not isinstance(root, (ast.Predicate, ast.Condition)):
        raise InvalidFilterError("A filter must have a predicate or logical root")
    evaluator = FES2Evaluator(
        property_mapping, namespaces=namespaces, strict=strict, field_types=field_types, crs=crs
    )
    predicate = evaluator.evaluate(root)
    predicate_operand(predicate)
    return serialize_filter(predicate, evaluator.namespaces)


def to_fes2_json(
    expression: str | Mapping[str, object],
    *,
    property_mapping: Mapping[str, str] | None = None,
    namespaces: Mapping[str, str] | None = None,
    strict: bool = True,
    field_types: Mapping[str, FieldType] | None = None,
    crs: str = CRS84,
) -> str:
    """Parse CQL2-JSON and translate it with the options documented by to_fes2.

    Raises:
        InvalidFilterError: If parsing, configuration or operands are invalid.
        UnsupportedOperatorError: If the expression cannot be translated faithfully.
        UnknownPropertyError: If strict mode disallows a property.
        FES2SerializationError: If a value contains invalid XML text.
    """
    return to_fes2(
        parse_cql2(expression),
        property_mapping=property_mapping,
        namespaces=namespaces,
        strict=strict,
        field_types=field_types,
        crs=crs,
    )


def to_fes2_text(
    expression: str,
    *,
    property_mapping: Mapping[str, str] | None = None,
    namespaces: Mapping[str, str] | None = None,
    strict: bool = True,
    field_types: Mapping[str, FieldType] | None = None,
    crs: str = CRS84,
) -> str:
    """Parse CQL2-Text and translate it with the options documented by to_fes2.

    Raises:
        InvalidFilterError: If parsing, configuration or operands are invalid.
        UnsupportedOperatorError: If the expression cannot be translated faithfully.
        UnknownPropertyError: If strict mode disallows a property.
        FES2SerializationError: If a value contains invalid XML text.
    """
    return to_fes2(
        parse_cql2(expression, language="cql2-text"),
        property_mapping=property_mapping,
        namespaces=namespaces,
        strict=strict,
        field_types=field_types,
        crs=crs,
    )
