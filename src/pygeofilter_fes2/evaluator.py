"""Translate pygeofilter predicates using Terradue's handler-based evaluator pattern."""

from __future__ import annotations

import math
from copy import deepcopy
from datetime import date, datetime
from typing import TYPE_CHECKING

from lxml import etree
from pygeofilter import ast, values
from pygeofilter.backends.evaluator import Evaluator, handle

from .exceptions import InvalidFilterError, UnsupportedOperatorError
from .geometry import CRS84, canonical_crs, envelope_element, geometry_element
from .properties import GML, FieldType, PropertyResolver
from .serializer import element, text_element
from .temporal import temporal_element, temporal_text
from .validation import (
    compatible_operands,
    predicate_operand,
    require_category,
    scalar_operand,
)

if TYPE_CHECKING:
    from collections.abc import Mapping


class FES2Evaluator(Evaluator):
    """Evaluate supported AST nodes into structural FES/GML XML elements.

    Instances retain an identifier counter for unique GML IDs. Use separate
    instances for concurrent translations.
    """

    def __init__(
        self,
        property_mapping: Mapping[str, str] | None = None,
        *,
        namespaces: Mapping[str, str] | None = None,
        strict: bool = True,
        field_types: Mapping[str, FieldType] | None = None,
        crs: str = CRS84,
    ) -> None:
        """Configure properties, namespace bindings and spatial output CRS.

        Args:
            property_mapping: Public names mapped to safe XML property QNames.
            namespaces: Prefix bindings for output property references.
            strict: Reject unmapped properties by default.
            field_types: Optional type metadata keyed by public names.
            crs: CRS84 or EPSG:4326; input is always longitude/latitude.

        Raises:
            InvalidFilterError: If property configuration is invalid.
            UnsupportedOperatorError: If the CRS has no implemented axis policy.
        """
        self._properties = PropertyResolver(property_mapping, namespaces, strict, field_types)
        self._crs = canonical_crs(crs)
        self._identifier = 0

    @property
    def namespaces(self) -> dict[str, str]:
        """Namespace bindings to declare when serializing the evaluated predicate."""
        return self._properties.namespaces

    def evaluate(self, node: ast.AstType, adopt_result: bool = True) -> etree._Element:
        """Evaluate an AST into one XML element, preserving the upstream recursion API.

        Raises:
            InvalidFilterError: If operands are malformed or incompatible.
            UnsupportedOperatorError: If any node has no supported translation.
        """
        result: object = super().evaluate(node, adopt_result)
        if not isinstance(result, etree._Element):
            raise InvalidFilterError("AST evaluation did not produce XML")
        return result

    def adopt(self, node: object, *sub_args: etree._Element) -> etree._Element:
        """Fail explicitly for unsupported AST nodes and literal types."""
        raise UnsupportedOperatorError(f"Unsupported AST node: {type(node).__name__}")

    def _next_identifier(self) -> str:
        self._identifier += 1
        return f"value_{self._identifier}"

    @handle(ast.Attribute)
    def attribute(self, node: ast.Attribute) -> etree._Element:
        """Resolve a property reference through the configured allowlist."""
        return text_element("ValueReference", self._properties.resolve(node.name))

    @handle(ast.And, ast.Or)
    def combination(
        self, node: ast.Combination, left: etree._Element, right: etree._Element
    ) -> etree._Element:
        """Combine two predicates without flattening or changing precedence."""
        predicate_operand(left)
        predicate_operand(right)
        return element("And" if isinstance(node, ast.And) else "Or", left, right)

    @handle(ast.Not)
    def negation(self, node: ast.Not, child: etree._Element) -> etree._Element:
        """Negate a predicate, preserving its complete subtree."""
        predicate_operand(child)
        return element("Not", child)

    @handle(ast.Equal, ast.NotEqual, ast.LessThan, ast.LessEqual, ast.GreaterThan, ast.GreaterEqual)
    def comparison(
        self, node: ast.Comparison, left: etree._Element, right: etree._Element
    ) -> etree._Element:
        """Serialize a scalar comparison with validated operand categories."""
        scalar_operand(left)
        scalar_operand(right)
        compatible_operands(node.lhs, node.rhs, self._properties)
        names = {
            ast.ComparisonOp.EQ: "PropertyIsEqualTo",
            ast.ComparisonOp.NE: "PropertyIsNotEqualTo",
            ast.ComparisonOp.LT: "PropertyIsLessThan",
            ast.ComparisonOp.LE: "PropertyIsLessThanOrEqualTo",
            ast.ComparisonOp.GT: "PropertyIsGreaterThan",
            ast.ComparisonOp.GE: "PropertyIsGreaterThanOrEqualTo",
        }
        return element(names[node.op], left, right)

    @staticmethod
    def _negated(predicate: etree._Element, negate: bool) -> etree._Element:
        return element("Not", predicate) if negate else predicate

    @handle(ast.Between)
    def between(
        self, node: ast.Between, left: etree._Element, low: etree._Element, high: etree._Element
    ) -> etree._Element:
        """Serialize inclusive numeric bounds, including NOT BETWEEN."""
        for raw, encoded in zip((node.lhs, node.low, node.high), (left, low, high), strict=True):
            scalar_operand(encoded)
            require_category(raw, self._properties, FieldType.NUMERIC)
        predicate = element(
            "PropertyIsBetween", left, element("LowerBoundary", low), element("UpperBoundary", high)
        )
        return self._negated(predicate, node.not_)

    @handle(ast.In)
    def membership(
        self, node: ast.In, left: etree._Element, *options: etree._Element
    ) -> etree._Element:
        """Expand a nonempty IN list to equality predicates, preserving negation."""
        if not options:
            raise InvalidFilterError("IN requires at least one option")
        scalar_operand(left)
        predicates = []
        for raw, option in zip(node.sub_nodes, options, strict=True):
            scalar_operand(option)
            compatible_operands(node.lhs, raw, self._properties)
            compatible_operands(node.sub_nodes[0], raw, self._properties)
            predicates.append(element("PropertyIsEqualTo", deepcopy(left), option))
        predicate = predicates[0] if len(predicates) == 1 else element("Or", *predicates)
        return self._negated(predicate, node.not_)

    @handle(ast.Like)
    def like(self, node: ast.Like, left: etree._Element) -> etree._Element:
        """Preserve wildcard and escape characters supplied by the AST."""
        scalar_operand(left)
        require_category(node.lhs, self._properties, FieldType.STRING)
        if not isinstance(node.pattern, str):
            raise UnsupportedOperatorError("Only literal LIKE patterns are supported")
        characters = (node.wildcard, node.singlechar, node.escapechar)
        if any(len(character) != 1 for character in characters) or len(set(characters)) != len(
            characters
        ):
            raise InvalidFilterError(
                "LIKE wildcard and escape characters must be distinct single characters"
            )
        predicate = element("PropertyIsLike", left, text_element("Literal", node.pattern))
        predicate.attrib.update(
            {
                "wildCard": node.wildcard,
                "singleChar": node.singlechar,
                "escapeChar": node.escapechar,
                "matchCase": "false" if node.nocase else "true",
            }
        )
        return self._negated(predicate, node.not_)

    @handle(ast.IsNull)
    def null_test(self, node: ast.IsNull, left: etree._Element) -> etree._Element:
        """Serialize explicit property null testing, including IS NOT NULL."""
        if not isinstance(node.lhs, ast.Attribute):
            raise InvalidFilterError("IS NULL requires a property reference")
        return self._negated(element("PropertyIsNull", left), node.not_)

    @handle(ast.GeometryIntersects, ast.GeometryWithin, ast.GeometryContains, ast.GeometryDisjoint)
    def spatial(
        self, node: ast.SpatialComparisonPredicate, left: etree._Element, right: etree._Element
    ) -> etree._Element:
        """Serialize supported spatial relations without swapping operand order."""
        for raw in (node.lhs, node.rhs):
            if not isinstance(raw, (ast.Attribute, values.Geometry, values.Envelope)):
                raise InvalidFilterError("Spatial predicates require properties or geometries")
            require_category(raw, self._properties, FieldType.GEOMETRY)
        return element(node.op.value.title(), left, right)

    @handle(ast.BBox)
    def bbox(self, node: ast.BBox, left: etree._Element) -> etree._Element:
        """Serialize a direct AST BBOX using a validated GML envelope."""
        require_category(node.lhs, self._properties, FieldType.GEOMETRY)
        if not isinstance(node.lhs, ast.Attribute):
            raise InvalidFilterError("BBOX requires a property reference")
        envelope = values.Envelope(node.minx, node.maxx, node.miny, node.maxy)
        return element("BBOX", left, envelope_element(envelope, node.crs or self._crs))

    @handle(values.Geometry, values.Envelope)
    def geometry(self, node: values.Geometry | values.Envelope) -> etree._Element:
        """Serialize a validated GML geometry with unique identifiers."""
        result = geometry_element(node, self._crs)
        identifier = self._next_identifier()
        for index, child in enumerate(result.iter()):
            if etree.QName(child).localname in {
                "Point",
                "LineString",
                "Polygon",
                "MultiPoint",
                "MultiCurve",
                "MultiSurface",
                "LinearRing",
            }:
                child.set(f"{{{GML}}}id", f"{identifier}_{index}")
        return result

    @handle(values.Interval)
    def interval(self, node: values.Interval, *bounds: etree._Element) -> etree._Element:
        """Serialize only finite intervals of matching precision."""
        return temporal_element(node, self._next_identifier())

    def _temporal_operand(self, raw: object, encoded: etree._Element) -> etree._Element:
        if isinstance(raw, ast.Attribute):
            category = self._properties.field_type(raw.name)
            if category not in {None, FieldType.DATE, FieldType.DATETIME}:
                raise InvalidFilterError("Temporal properties must have date or datetime type")
            return encoded
        if isinstance(raw, date):
            return temporal_element(raw, self._next_identifier())
        if isinstance(raw, values.Interval):
            return encoded
        raise InvalidFilterError("Temporal predicates require temporal values or properties")

    @handle(ast.TimeBefore, ast.TimeAfter)
    def temporal(
        self, node: ast.TemporalPredicate, left: etree._Element, right: etree._Element
    ) -> etree._Element:
        """Serialize strict BEFORE/AFTER relations for instants or finite intervals."""
        compatible_operands(node.lhs, node.rhs, self._properties)
        return element(
            "Before" if isinstance(node, ast.TimeBefore) else "After",
            self._temporal_operand(node.lhs, left),
            self._temporal_operand(node.rhs, right),
        )

    @handle(str, int, float, bool, date, datetime)
    def literal(self, node: str | int | float | date) -> etree._Element:
        """Encode scalar literals, rejecting non-finite numbers and naive timestamps."""
        if isinstance(node, bool):
            text = "true" if node else "false"
        elif isinstance(node, date):
            text = temporal_text(node)
        elif isinstance(node, float) and not math.isfinite(node):
            raise InvalidFilterError("Numeric literals must be finite")
        else:
            text = str(node)
        return text_element("Literal", text)
