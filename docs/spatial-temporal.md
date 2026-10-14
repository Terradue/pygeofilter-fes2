# Spatial and temporal behavior

Spatial literals are parsed by pygeofilter, validated with Shapely, and encoded
as GML 3.2: Point, LineString, Polygon, MultiPoint, MultiCurve (MultiLineString),
MultiSurface (MultiPolygon) and Envelope. Polygon interiors are retained.
Empty, invalid, non-finite, 3D and measured geometries are rejected.
GeometryCollection is unsupported. JSON bbox input is `[minx, miny, maxx, maxy]`;
direct `values.Envelope` retains pygeofilter's `(x1, x2, y1, y2)` constructor.
Reversed bounds, including an antimeridian-wrapping envelope, are rejected.

Inputs always use x/y longitude/latitude. The default output is
`http://www.opengis.net/def/crs/OGC/1.3/CRS84`, serialized longitude first.
`crs="EPSG:4326"` explicitly selects latitude-first GML output with
`urn:ogc:def:crs:EPSG::4326`. The switch reorders axes; it does not reproject.
Only these two CRS families are supported. The caller is responsible for knowing
the CRS of property geometries and for using compatible literal coordinates.
No endpoint or schema is consulted.

```python
from pygeofilter_fes2 import to_fes2_text

xml = to_fes2_text(
    "S_INTERSECTS(geometry, POINT(12.5 41.9))",
    property_mapping={"geometry": "Geometry"},
    crs="EPSG:4326",
)
```

Dates retain date-only precision. Aware timestamps normalize to UTC with `Z`;
naive timestamps are rejected. Scalar comparisons use `fes:Literal`, whereas
BEFORE/AFTER serialize temporal literals as GML TimeInstant or TimePeriod.
Finite intervals require ordered endpoints with matching date/timestamp
precision. Durations and open bounds are rejected. No missing bounds or
historical dates are invented.

```python
from pygeofilter_fes2 import to_fes2_text

xml = to_fes2_text(
    "T_BEFORE(event_time, TIMESTAMP('2020-01-01T02:00:00+02:00'))",
    property_mapping={"event_time": "EventTime"},
)
```

BEFORE compares the end of the first temporal operand with the beginning of
the second; AFTER compares the beginning of the first with the end of the
second. They do not mean interval containment or inclusive range comparison.
Property metadata must describe a compatible temporal domain; interval-valued
properties remain the caller's responsibility. Temporal overlap/intersection
and other Allen relations are deferred.
