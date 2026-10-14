"""Translate a spatial JSON filter offline with a qualified property name."""

from pygeofilter_fes2 import to_fes2_json

print(
    to_fes2_json(
        {
            "op": "s_intersects",
            "args": [{"property": "geometry"}, {"type": "Point", "coordinates": [12.5, 41.9]}],
        },
        property_mapping={"geometry": "source:geometry"},
        namespaces={"source": "urn:example:source"},
    )
)
