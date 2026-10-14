from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from lxml import etree
from pygeofilter import ast, values

from pygeofilter_fes2 import (
    FieldType,
    InvalidFilterError,
    UnsupportedOperatorError,
    to_fes2,
    to_fes2_json,
    to_fes2_text,
)
from pygeofilter_fes2.geometry import CRS84, EPSG4326
from pygeofilter_fes2.properties import GML

if TYPE_CHECKING:
    from collections.abc import Callable

# Constrain the upstream constructor, which lacks parameter annotations.
attribute: Callable[[str], ast.Attribute] = ast.Attribute


@pytest.mark.parametrize("operator", ["s_intersects", "s_within", "s_contains", "s_disjoint"])
def test_supported_spatial_predicates(operator: str, xml_schema: etree.XMLSchema) -> None:
    document = etree.fromstring(
        to_fes2_json(
            {
                "op": operator,
                "args": [{"property": "geometry"}, {"type": "Point", "coordinates": [10, 20]}],
            },
            strict=False,
        ).encode()
    )
    xml_schema.assertValid(document)
    assert etree.QName(document[0]).localname.lower() == operator.removeprefix("s_")
    assert document[0][1].findtext(f"{{{GML}}}pos") == "10.0 20.0"


@pytest.mark.parametrize(
    ("geometry", "gml_type"),
    [
        ({"type": "Point", "coordinates": [10, 20]}, "Point"),
        ({"type": "LineString", "coordinates": [[10, 20], [11, 21]]}, "LineString"),
        (
            {
                "type": "Polygon",
                "coordinates": [
                    [[0, 0], [4, 0], [4, 4], [0, 4], [0, 0]],
                    [[1, 1], [1, 2], [2, 2], [2, 1], [1, 1]],
                ],
            },
            "Polygon",
        ),
        ({"type": "MultiPoint", "coordinates": [[10, 20], [11, 21]]}, "MultiPoint"),
        (
            {
                "type": "MultiLineString",
                "coordinates": [[[10, 20], [11, 21]], [[12, 22], [13, 23]]],
            },
            "MultiCurve",
        ),
        (
            {
                "type": "MultiPolygon",
                "coordinates": [
                    [[[0, 0], [4, 0], [4, 4], [0, 4], [0, 0]]],
                    [[[5, 5], [6, 5], [6, 6], [5, 6], [5, 5]]],
                ],
            },
            "MultiSurface",
        ),
    ],
)
def test_geometry_types_validate(
    geometry: dict[str, object], gml_type: str, xml_schema: etree.XMLSchema
) -> None:
    document = etree.fromstring(
        to_fes2_json(
            {"op": "s_intersects", "args": [{"property": "geometry"}, geometry]}, strict=False
        ).encode()
    )
    xml_schema.assertValid(document)
    literal = document[0][1]
    assert literal.tag == f"{{{GML}}}{gml_type}"
    assert literal.get("srsName") == CRS84
    if gml_type == "Polygon":
        assert literal.find(f"{{{GML}}}interior/{{{GML}}}LinearRing/{{{GML}}}posList") is not None


@pytest.mark.parametrize(("crs", "coordinates"), [(CRS84, "10.0 20.0"), ("EPSG:4326", "20.0 10.0")])
def test_axis_order_is_explicit(crs: str, coordinates: str, xml_schema: etree.XMLSchema) -> None:
    document = etree.fromstring(
        to_fes2_text("S_INTERSECTS(geometry, POINT(10 20))", strict=False, crs=crs).encode()
    )
    xml_schema.assertValid(document)
    assert document[0][1][0].text == coordinates
    assert document[0][1].get("srsName") == (CRS84 if crs == CRS84 else EPSG4326)


def test_bbox_json_order_and_direct_ast(xml_schema: etree.XMLSchema) -> None:
    document = etree.fromstring(
        to_fes2_json(
            {"op": "s_intersects", "args": [{"property": "geometry"}, {"bbox": [10, 20, 30, 40]}]},
            strict=False,
        ).encode()
    )
    xml_schema.assertValid(document)
    assert document[0][1][0].text == "10.0 20.0"
    assert document[0][1][1].text == "30.0 40.0"
    node = ast.BBox(attribute("geometry"), 10, 20, 30, 40, "EPSG:4326")
    document = etree.fromstring(to_fes2(node, strict=False).encode())
    xml_schema.assertValid(document)
    assert document[0][1][0].text == "20.0 10.0"
    assert document[0][1][1].text == "40.0 30.0"


@pytest.mark.parametrize(
    "geometry",
    [
        {"type": "Point", "coordinates": []},
        {"type": "Point", "coordinates": [1, 2, 3]},
        {"type": "Point", "coordinates": [float("nan"), 2]},
        {"type": "LineString", "coordinates": [[1, 2]]},
        {"type": "Polygon", "coordinates": [[[0, 0], [2, 2], [2, 0], [0, 2], [0, 0]]]},
        {"bbox": [30, 20, 10, 40]},
        {"bbox": [1, 2, 3]},
        {"bbox": [1, 2, 3, float("inf")]},
    ],
)
def test_invalid_geometries_are_rejected(geometry: dict[str, object]) -> None:
    with pytest.raises(InvalidFilterError):
        to_fes2_json(
            {"op": "s_intersects", "args": [{"property": "geometry"}, geometry]}, strict=False
        )


def test_spatial_types_and_unsupported_crs() -> None:
    expression = {
        "op": "s_intersects",
        "args": [{"property": "geometry"}, {"type": "Point", "coordinates": [10, 20]}],
    }
    with pytest.raises(InvalidFilterError):
        to_fes2_json(expression, strict=False, field_types={"geometry": FieldType.STRING})
    with pytest.raises(UnsupportedOperatorError):
        to_fes2_json(expression, strict=False, crs="EPSG:3857")
    with pytest.raises(InvalidFilterError):
        to_fes2_json(
            {"op": "s_intersects", "args": [{"property": "geometry"}, "POINT(10 20)"]}, strict=False
        )


def test_geometry_collection_is_explicitly_unsupported() -> None:
    geometry = values.Geometry(
        {"type": "GeometryCollection", "geometries": [{"type": "Point", "coordinates": [10, 20]}]}
    )
    with pytest.raises(UnsupportedOperatorError):
        to_fes2(ast.GeometryIntersects(attribute("geometry"), geometry), strict=False)


@pytest.mark.parametrize(
    "geometry",
    [
        {"type": "Point", "coordinates": ["10", 20]},
        {"type": "Point", "coordinates": [True, 20]},
        {"type": "Polygon", "coordinates": [[[0, 0], [4, 0], [4, 4], [0, 4]]]},
    ],
)
def test_shapely_must_not_repair_or_coerce_input(geometry: dict[str, object]) -> None:
    with pytest.raises(InvalidFilterError):
        to_fes2_json(
            {"op": "s_intersects", "args": [{"property": "geometry"}, geometry]}, strict=False
        )


def test_geometry_first_operand_preserves_order(xml_schema: etree.XMLSchema) -> None:
    document = etree.fromstring(
        to_fes2_json(
            {
                "op": "s_contains",
                "args": [{"type": "Point", "coordinates": [10, 20]}, {"property": "geometry"}],
            },
            strict=False,
        ).encode()
    )
    xml_schema.assertValid(document)
    assert etree.QName(document[0][0]).localname == "Point"
    assert document[0][1].text == "geometry"
