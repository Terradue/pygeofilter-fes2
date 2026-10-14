from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import pytest
from lxml import etree
from pygeofilter import ast

from pygeofilter_fes2 import (
    FieldType,
    InvalidFilterError,
    UnsupportedOperatorError,
    to_fes2,
    to_fes2_json,
)
from pygeofilter_fes2.properties import GML

if TYPE_CHECKING:
    from collections.abc import Callable

# Constrain the upstream constructor, which lacks parameter annotations.
attribute: Callable[[str], ast.Attribute] = ast.Attribute


@pytest.mark.parametrize("operator", ["t_before", "t_after"])
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ({"timestamp": "2020-01-01T02:00:00+02:00"}, "2020-01-01T00:00:00Z"),
        ({"date": "2020-01-01"}, "2020-01-01"),
    ],
)
def test_temporal_instants_preserve_precision(
    operator: str, value: dict[str, str], expected: str, xml_schema: etree.XMLSchema
) -> None:
    document = etree.fromstring(
        to_fes2_json({"op": operator, "args": [{"property": "time"}, value]}, strict=False).encode()
    )
    xml_schema.assertValid(document)
    assert document[0][1][0].text == expected
    assert etree.QName(document[0]).localname.lower() == operator.removeprefix("t_")


def test_finite_interval_and_unique_identifiers(xml_schema: etree.XMLSchema) -> None:
    predicate = {
        "op": "t_before",
        "args": [
            {"property": "time"},
            {"interval": ["2020-01-01T00:00:00Z", "2020-02-01T00:00:00Z"]},
        ],
    }
    document = etree.fromstring(
        to_fes2_json({"op": "and", "args": [predicate, predicate]}, strict=False).encode()
    )
    xml_schema.assertValid(document)
    identifiers = [
        child.get(f"{{{GML}}}id") for child in document.iter() if child.get(f"{{{GML}}}id")
    ]
    assert len(identifiers) == len(set(identifiers))
    assert document[0][0][1][0].text == "2020-01-01T00:00:00Z"
    assert document[0][0][1][1].text == "2020-02-01T00:00:00Z"


def test_timestamp_comparison_is_scalar(xml_schema: etree.XMLSchema) -> None:
    document = etree.fromstring(
        to_fes2_json(
            {
                "op": ">=",
                "args": [{"property": "time"}, {"timestamp": "2020-01-01T01:00:00+01:00"}],
            },
            strict=False,
            field_types={"time": FieldType.DATETIME},
        ).encode()
    )
    xml_schema.assertValid(document)
    assert document[0][1].text == "2020-01-01T00:00:00Z"


@pytest.mark.parametrize(
    "interval",
    [
        ["..", "2020-01-01"],
        ["2020-01-01", ".."],
        ["2020-02-01", "2020-01-01"],
        ["2020-01-01", "2020-02-01T00:00:00Z"],
        ["P1D", "2020-01-01"],
    ],
)
def test_invalid_or_unsupported_intervals(interval: list[str]) -> None:
    with pytest.raises(InvalidFilterError):
        to_fes2_json(
            {"op": "t_before", "args": [{"property": "time"}, {"interval": interval}]}, strict=False
        )


def test_naive_datetime_ast_is_rejected() -> None:
    with pytest.raises(InvalidFilterError, match="timezone"):
        to_fes2(ast.TimeAfter(attribute("time"), datetime(2020, 1, 1)), strict=False)


def test_invalid_temporal_property_metadata() -> None:
    with pytest.raises(InvalidFilterError):
        to_fes2_json(
            {"op": "t_before", "args": [{"property": "time"}, {"date": "2020-01-01"}]},
            strict=False,
            field_types={"time": FieldType.NUMERIC},
        )


def test_other_temporal_relations_are_explicitly_unsupported() -> None:
    with pytest.raises(UnsupportedOperatorError):
        to_fes2_json(
            {
                "op": "t_during",
                "args": [{"property": "time"}, {"interval": ["2020-01-01", "2020-02-01"]}],
            },
            strict=False,
        )


@pytest.mark.parametrize("operator", ["T_BEFORE", "T_AFTER"])
def test_standard_functional_temporal_text(operator: str, xml_schema: etree.XMLSchema) -> None:
    from pygeofilter_fes2 import to_fes2_text

    document = etree.fromstring(
        to_fes2_text(
            f"{operator}(time, TIMESTAMP('2020-01-01T02:00:00+02:00'))", strict=False
        ).encode()
    )
    xml_schema.assertValid(document)
    assert document[0][1][0].text == "2020-01-01T00:00:00Z"


def test_interval_precision_must_match_property_metadata() -> None:
    with pytest.raises(InvalidFilterError, match="Incompatible"):
        to_fes2_json(
            {
                "op": "t_before",
                "args": [{"property": "time"}, {"interval": ["2020-01-01", "2020-02-01"]}],
            },
            strict=False,
            field_types={"time": FieldType.DATETIME},
        )
