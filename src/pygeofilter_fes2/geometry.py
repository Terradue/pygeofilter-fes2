"""Validate planar geometry and encode longitude/latitude input as GML 3.2."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from pygeofilter import values
from shapely import get_coordinates
from shapely.errors import GEOSException
from shapely.geometry import (
    LineString,
    MultiLineString,
    MultiPoint,
    MultiPolygon,
    Point,
    Polygon,
    shape,
)

from .exceptions import InvalidFilterError, UnsupportedOperatorError
from .properties import GML
from .serializer import element, text_element

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from lxml import etree
    from shapely.geometry.base import BaseGeometry

CRS84 = "http://www.opengis.net/def/crs/OGC/1.3/CRS84"
EPSG4326 = "urn:ogc:def:crs:EPSG::4326"
DIMENSIONS = 2


def canonical_crs(crs: str) -> str:
    """Resolve supported CRS identifiers; no reprojection is performed.

    All input coordinates are x/y (longitude/latitude). EPSG:4326 output is
    explicitly reordered into its latitude/longitude axis order.

    Raises:
        UnsupportedOperatorError: If the CRS has no implemented axis policy.
    """
    if crs in {CRS84, "CRS84", "urn:ogc:def:crs:OGC:1.3:CRS84"}:
        return CRS84
    if crs in {EPSG4326, "EPSG:4326", "http://www.opengis.net/def/crs/EPSG/0/4326"}:
        return EPSG4326
    raise UnsupportedOperatorError(f"Unsupported CRS: {crs!r}")


def _positions(coordinates: Iterable[Sequence[float]], crs: str) -> str:
    parts: list[str] = []
    for coordinate in coordinates:
        if len(coordinate) != DIMENSIONS or not all(math.isfinite(value) for value in coordinate):
            raise InvalidFilterError("Geometry coordinates must be finite and two-dimensional")
        ordered = reversed(coordinate) if crs == EPSG4326 else coordinate
        parts.extend(str(float(value)) for value in ordered)
    return " ".join(parts)


def _ring(coordinates: Iterable[Sequence[float]], crs: str) -> etree._Element:
    return element(
        "LinearRing", text_element("posList", _positions(coordinates, crs), GML), namespace=GML
    )


def _polygon(geometry: Polygon, crs: str) -> etree._Element:
    result = element("Polygon", namespace=GML)
    result.append(element("exterior", _ring(geometry.exterior.coords, crs), namespace=GML))
    for interior in geometry.interiors:
        result.append(element("interior", _ring(interior.coords, crs), namespace=GML))
    return result


def _multipart(geometry: MultiPoint | MultiLineString | MultiPolygon, crs: str) -> etree._Element:
    names = {
        "MultiPoint": ("MultiPoint", "pointMember"),
        "MultiLineString": ("MultiCurve", "curveMember"),
        "MultiPolygon": ("MultiSurface", "surfaceMember"),
    }
    name, member = names[geometry.geom_type]
    result = element(name, namespace=GML)
    for part in geometry.geoms:
        result.append(element(member, _encode_geometry(part, crs), namespace=GML))
    return result


def _encode_geometry(geometry: BaseGeometry, crs: str) -> etree._Element:
    if isinstance(geometry, Point):
        return element(
            "Point", text_element("pos", _positions(geometry.coords, crs), GML), namespace=GML
        )
    if isinstance(geometry, LineString):
        return element(
            "LineString",
            text_element("posList", _positions(geometry.coords, crs), GML),
            namespace=GML,
        )
    if isinstance(geometry, Polygon):
        return _polygon(geometry, crs)
    if isinstance(geometry, (MultiPoint, MultiLineString, MultiPolygon)):
        return _multipart(geometry, crs)
    raise UnsupportedOperatorError(f"Unsupported geometry: {geometry.geom_type}")


def envelope_element(envelope: values.Envelope, crs: str) -> etree._Element:
    """Encode a finite ordered bounding box with the configured CRS axis policy.

    Raises:
        InvalidFilterError: If the envelope is non-finite or reversed.
    """
    crs = canonical_crs(crs)
    if envelope.x1 > envelope.x2 or envelope.y1 > envelope.y2:
        raise InvalidFilterError(
            "Envelope bounds are reversed; antimeridian wrapping is unsupported"
        )
    lower = _positions([(envelope.x1, envelope.y1)], crs)
    upper = _positions([(envelope.x2, envelope.y2)], crs)
    result = element(
        "Envelope",
        text_element("lowerCorner", lower, GML),
        text_element("upperCorner", upper, GML),
        namespace=GML,
    )
    result.set("srsName", crs)
    result.set("srsDimension", str(DIMENSIONS))
    return result


def _validate_coordinate_tree(coordinates: object) -> None:
    if isinstance(coordinates, (list, tuple)):
        for part in coordinates:
            _validate_coordinate_tree(part)
    elif isinstance(coordinates, bool) or not isinstance(coordinates, (int, float)):
        raise InvalidFilterError("Geometry coordinates must be numbers")
    elif not math.isfinite(coordinates):
        raise InvalidFilterError("Geometry coordinates must be finite")


def _validate_polygon_rings(coordinates: object) -> None:
    minimum_ring_size = 4
    if not isinstance(coordinates, (list, tuple)):
        raise InvalidFilterError("Polygon coordinates must be ring arrays")
    for ring in coordinates:
        if (
            not isinstance(ring, (list, tuple))
            or len(ring) < minimum_ring_size
            or ring[0] != ring[-1]
        ):
            raise InvalidFilterError("Polygon rings must be closed with at least four positions")


def _validate_raw_geometry(value: values.Geometry) -> None:
    """Reject malformed coordinates before Shapely can coerce or close them."""
    coordinates = value.geometry.get("coordinates")
    _validate_coordinate_tree(coordinates)
    if value.geometry.get("type") == "Polygon":
        _validate_polygon_rings(coordinates)
    elif value.geometry.get("type") == "MultiPolygon":
        if not isinstance(coordinates, (list, tuple)):
            raise InvalidFilterError("MultiPolygon coordinates must be polygon arrays")
        for polygon in coordinates:
            _validate_polygon_rings(polygon)


def geometry_element(value: values.Geometry | values.Envelope, crs: str) -> etree._Element:
    """Serialize a valid nonempty 2D geometry or envelope as GML 3.2.

    Raises:
        InvalidFilterError: If geometry is invalid, empty, non-finite or not 2D.
        UnsupportedOperatorError: If geometry or CRS is unsupported.
    """
    crs = canonical_crs(crs)
    if isinstance(value, values.Envelope):
        return envelope_element(value, crs)
    if value.geometry.get("type") == "GeometryCollection":
        raise UnsupportedOperatorError("GeometryCollection is unsupported")
    _validate_raw_geometry(value)
    try:
        geometry = shape(value.geometry)
    except (ValueError, TypeError, KeyError, IndexError, GEOSException) as error:
        raise InvalidFilterError("Malformed geometry literal") from error
    if geometry.is_empty or not geometry.is_valid or geometry.has_z or geometry.has_m:
        raise InvalidFilterError("Geometry must be valid, nonempty and two-dimensional")
    if not all(math.isfinite(float(value)) for row in get_coordinates(geometry) for value in row):
        raise InvalidFilterError("Geometry coordinates must be finite")
    result = _encode_geometry(geometry, crs)
    result.set("srsName", crs)
    result.set("srsDimension", str(DIMENSIONS))
    return result
