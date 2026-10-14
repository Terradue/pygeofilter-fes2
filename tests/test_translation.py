from __future__ import annotations

import json

import pytest
from lxml import etree
from pygeofilter import ast

from pygeofilter_fes2 import (
    FES2Evaluator,
    FES2SerializationError,
    FieldType,
    InvalidFilterError,
    UnknownPropertyError,
    UnsupportedOperatorError,
    parse_cql2,
    to_fes2,
    to_fes2_json,
    to_fes2_text,
)
from pygeofilter_fes2.properties import FES


@pytest.mark.parametrize(
    ("operator", "name"),
    [
        ("=", "PropertyIsEqualTo"),
        ("<>", "PropertyIsNotEqualTo"),
        ("<", "PropertyIsLessThan"),
        ("<=", "PropertyIsLessThanOrEqualTo"),
        (">", "PropertyIsGreaterThan"),
        (">=", "PropertyIsGreaterThanOrEqualTo"),
    ],
)
def test_comparisons_match_across_syntaxes(
    operator: str, name: str, xml_schema: etree.XMLSchema
) -> None:
    expression = {"op": operator, "args": [{"property": "magnitude"}, 4]}
    json_xml = to_fes2_json(expression, property_mapping={"magnitude": "Magnitude"})
    text_xml = to_fes2_text(f"magnitude {operator} 4", property_mapping={"magnitude": "Magnitude"})
    document = etree.fromstring(json_xml.encode())
    xml_schema.assertValid(document)
    assert document[0].tag == f"{{{FES}}}{name}"
    assert document[0][0].text == "Magnitude"
    assert document[0][1].text == "4"
    assert etree.tostring(document, method="c14n") == etree.tostring(
        etree.fromstring(text_xml.encode()), method="c14n"
    )


def test_nested_logic_and_direct_ast(xml_schema: etree.XMLSchema) -> None:
    root = parse_cql2(
        "NOT (magnitude < 4 OR name = 'Example') AND active = true", language="cql2-text"
    )
    assert isinstance(root, ast.And)
    document = etree.fromstring(to_fes2(root, strict=False).encode())
    xml_schema.assertValid(document)
    assert etree.QName(document[0]).localname == "And"
    assert etree.QName(document[0][0]).localname == "Not"
    assert etree.QName(document[0][0][0]).localname == "Or"
    assert document[0][1][1].text == "true"
    assert isinstance(FES2Evaluator(strict=False).evaluate(root), etree._Element)


@pytest.mark.parametrize("literal", [4, -2.5, True, False, "<&\"'日本語"])
def test_literal_escaping_and_json_string(literal: object, xml_schema: etree.XMLSchema) -> None:
    expression = json.dumps({"op": "=", "args": [{"property": "value"}, literal]})
    document = etree.fromstring(to_fes2_json(expression, strict=False).encode())
    xml_schema.assertValid(document)
    expected = str(literal).lower() if isinstance(literal, bool) else str(literal)
    assert document[0][1].text == expected


@pytest.mark.parametrize(
    "expression",
    [
        "score BETWEEN 1 AND 3",
        "score NOT BETWEEN 1 AND 3",
        "score IN (1, 3)",
        "score NOT IN (1, 3)",
        "score IN (1)",
        "score IS NULL",
        "score IS NOT NULL",
    ],
)
def test_advanced_comparison_variants(expression: str, xml_schema: etree.XMLSchema) -> None:
    document = etree.fromstring(to_fes2_text(expression, strict=False).encode())
    xml_schema.assertValid(document)
    if "NOT" in expression:
        assert etree.QName(document[0]).localname == "Not"


def test_standard_json_between_and_in(xml_schema: etree.XMLSchema) -> None:
    between = etree.fromstring(
        to_fes2_json(
            {"op": "between", "args": [{"property": "score"}, 1, 3]}, strict=False
        ).encode()
    )
    xml_schema.assertValid(between)
    assert between[0][1][0].text == "1"
    assert between[0][2][0].text == "3"
    membership = etree.fromstring(
        to_fes2_json(
            {"op": "in", "args": [{"property": "score"}, [1, 2, 3]]}, strict=False
        ).encode()
    )
    xml_schema.assertValid(membership)
    assert [predicate[1].text for predicate in membership[0]] == ["1", "2", "3"]
    assert all(predicate[0].text == "score" for predicate in membership[0])


@pytest.mark.parametrize("language", ["json", "text"])
def test_like_uses_cql2_wildcards(language: str, xml_schema: etree.XMLSchema) -> None:
    pattern = r"a_%.\%"
    if language == "json":
        xml = to_fes2_json({"op": "like", "args": [{"property": "name"}, pattern]}, strict=False)
    else:
        xml = to_fes2_text(f"name LIKE '{pattern}'", strict=False)
    document = etree.fromstring(xml.encode())
    xml_schema.assertValid(document)
    assert document[0].get("wildCard") == "%"
    assert document[0].get("singleChar") == "_"
    assert document[0].get("escapeChar") == "\\"
    assert document[0][1].text == pattern


def test_strict_properties_and_namespaces(xml_schema: etree.XMLSchema) -> None:
    with pytest.raises(UnknownPropertyError):
        to_fes2_text("name = 'Example'")
    document = etree.fromstring(
        to_fes2_text(
            "name = 'Example'",
            property_mapping={"name": "source:Name"},
            namespaces={"source": "urn:example:source"},
        ).encode()
    )
    xml_schema.assertValid(document)
    assert document.nsmap["source"] == "urn:example:source"
    assert document[0][0].text == "source:Name"


@pytest.mark.parametrize(
    "reference", ["a/b", "a[1]", "../name", "*", "a|b", "undeclared:name", "a b"]
)
def test_unsafe_or_unbound_properties_are_rejected(reference: str) -> None:
    with pytest.raises(InvalidFilterError):
        to_fes2_text("name = 'Example'", property_mapping={"name": reference})


@pytest.mark.parametrize(
    "namespaces",
    [{"fes": "urn:wrong"}, {"gml": "urn:wrong"}, {"xml": "urn:wrong"}, {"": "urn:example"}],
)
def test_invalid_namespace_configuration(namespaces: dict[str, str]) -> None:
    with pytest.raises(InvalidFilterError):
        to_fes2_text("name = 'Example'", strict=False, namespaces=namespaces)


def test_metadata_validates_without_coercion() -> None:
    with pytest.raises(InvalidFilterError, match="Incompatible"):
        to_fes2_json(
            {"op": "=", "args": [{"property": "score"}, "4"]},
            property_mapping={"score": "Score"},
            field_types={"score": FieldType.NUMERIC},
        )
    with pytest.raises(InvalidFilterError, match="Incompatible"):
        to_fes2_json(
            {"op": "=", "args": [{"property": "score"}, True]},
            strict=False,
            field_types={"score": FieldType.NUMERIC},
        )


@pytest.mark.parametrize("expression", ["", "name =", "1", "true"])
def test_malformed_or_nonpredicate_text(expression: str) -> None:
    with pytest.raises(InvalidFilterError):
        to_fes2_text(expression, strict=False)


@pytest.mark.parametrize(
    "expression",
    [
        {"op": "not", "args": []},
        {"op": "not", "args": [True, False]},
        {"op": "and", "args": [True]},
        {"op": "=", "args": [{"property": "name"}]},
        {"op": "and", "args": [True, False]},
        {"op": "in", "args": [{"property": "score"}, []]},
        {"op": "=", "args": [{"property": "score"}, None]},
        {"op": "=", "args": [{"property": "score"}, float("inf")]},
        {"op": "in", "args": [{"property": "score"}, [1, "two"]]},
        {"op": "between", "args": [{"property": "name"}, "a", "b"]},
    ],
)
def test_invalid_json_and_operand_categories(expression: dict[str, object]) -> None:
    with pytest.raises(InvalidFilterError):
        to_fes2_json(expression, strict=False)


@pytest.mark.parametrize(
    "expression",
    [
        "score + 1 > 4",
        "S_TOUCHES(geom, POINT(1 2))",
        "time T_INTERSECTS TIMESTAMP('2020-01-01T00:00:00Z')",
    ],
)
def test_unsupported_operations(expression: str) -> None:
    with pytest.raises(UnsupportedOperatorError):
        to_fes2_text(expression, strict=False)


def test_json_temporal_alias_is_rejected() -> None:
    with pytest.raises(UnsupportedOperatorError):
        parse_cql2(
            {
                "op": "t_intersects",
                "args": [{"property": "time"}, {"timestamp": "2020-01-01T00:00:00Z"}],
            }
        )


def test_invalid_xml_characters() -> None:
    with pytest.raises(FES2SerializationError):
        to_fes2_json({"op": "=", "args": [{"property": "name"}, "\x00"]}, strict=False)


def test_evaluator_config_is_a_snapshot() -> None:
    mapping = {"name": "Name"}
    evaluator = FES2Evaluator(mapping)
    mapping["name"] = "Unsafe/Path"
    node = parse_cql2("name = 'Example'", language="cql2-text")
    assert evaluator.evaluate(node)[0].text == "Name"


def test_and_binds_more_tightly_than_or(xml_schema: etree.XMLSchema) -> None:
    document = etree.fromstring(
        to_fes2_text("first = 1 OR second = 2 AND third = 3", strict=False).encode()
    )
    xml_schema.assertValid(document)
    assert etree.QName(document[0]).localname == "Or"
    assert etree.QName(document[0][1]).localname == "And"
    assert document[0][0][0].text == "first"


@pytest.mark.parametrize(
    ("expression", "name", "literal"),
    [
        ("name = 'O''Brien'", "name", "O'Brien"),
        ('"source""name" = 1', 'source"name', "1"),
        ("x = 1", "x", "1"),
    ],
)
def test_text_literal_and_identifier_regressions(
    expression: str, name: str, literal: str, xml_schema: etree.XMLSchema
) -> None:
    document = etree.fromstring(to_fes2_text(expression, property_mapping={name: "Name"}).encode())
    xml_schema.assertValid(document)
    assert document[0][1].text == literal


def test_json_nested_not_and_null(xml_schema: etree.XMLSchema) -> None:
    expression = {
        "op": "not",
        "args": [
            {
                "op": "or",
                "args": [
                    {"op": "isNull", "args": [{"property": "name"}]},
                    {"op": "=", "args": [{"property": "name"}, "Example"]},
                ],
            }
        ],
    }
    document = etree.fromstring(to_fes2_json(expression, strict=False).encode())
    xml_schema.assertValid(document)
    assert etree.QName(document[0]).localname == "Not"
    assert etree.QName(document[0][0][0]).localname == "PropertyIsNull"


def test_invalid_filter_language_wrapper() -> None:
    with pytest.raises(InvalidFilterError, match="wrapper"):
        to_fes2_json(
            {
                "filter-lang": "cql2-text",
                "filter": {"op": "=", "args": [{"property": "name"}, "Example"]},
            },
            strict=False,
        )


def test_official_schema_rejects_missing_comparison_operand(xml_schema: etree.XMLSchema) -> None:
    document = etree.fromstring(to_fes2_text("score = 1", strict=False).encode())
    document[0].remove(document[0][1])
    with pytest.raises(etree.DocumentInvalid):
        xml_schema.assertValid(document)
