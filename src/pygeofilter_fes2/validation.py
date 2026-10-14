"""Validate AST operand categories without converting or coercing literal values."""

from __future__ import annotations

from datetime import date, datetime

from lxml import etree
from pygeofilter import ast, values

from .exceptions import InvalidFilterError
from .properties import FES, GML, FieldType, PropertyResolver


def operand_type(value: object, properties: PropertyResolver) -> FieldType | None:
    """Identify literal types or caller-supplied property types."""
    if isinstance(value, ast.Attribute):
        return properties.field_type(value.name)
    if isinstance(value, values.Interval):
        return operand_type(value.start, properties)
    types = (
        (bool, FieldType.BOOLEAN),
        ((float, int), FieldType.NUMERIC),
        (str, FieldType.STRING),
        (datetime, FieldType.DATETIME),
        (date, FieldType.DATE),
        ((values.Geometry, values.Envelope), FieldType.GEOMETRY),
    )
    return next((category for classes, category in types if isinstance(value, classes)), None)


def compatible_operands(left: object, right: object, properties: PropertyResolver) -> None:
    """Reject known incompatible operand categories without guessing property types."""
    left_type, right_type = operand_type(left, properties), operand_type(right, properties)
    if left_type is not None and right_type is not None and left_type != right_type:
        raise InvalidFilterError(
            f"Incompatible operand types: {left_type.value}, {right_type.value}"
        )


def require_category(value: object, properties: PropertyResolver, category: FieldType) -> None:
    """Reject an operand whose known category differs from the required one."""
    actual = operand_type(value, properties)
    if actual is not None and actual != category:
        raise InvalidFilterError(f"Expected {category.value}, received {actual.value}")


def scalar_operand(value: etree._Element) -> None:
    """Require a simple property or scalar literal expression."""
    if value.tag not in {f"{{{FES}}}ValueReference", f"{{{FES}}}Literal"}:
        raise InvalidFilterError("Expected a property or scalar literal")


def predicate_operand(value: etree._Element) -> None:
    """Reject expression and GML values used as logical operands."""
    if (
        value.tag in {f"{{{FES}}}ValueReference", f"{{{FES}}}Literal"}
        or etree.QName(value).namespace == GML
    ):
        raise InvalidFilterError("Logical operators require predicate operands")
