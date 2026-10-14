"""Translate a text filter offline with an explicit property mapping."""

from pygeofilter_fes2 import to_fes2_text

print(
    to_fes2_text(
        "magnitude >= 4 AND name = 'Example'",
        property_mapping={"magnitude": "Magnitude", "name": "Name"},
    )
)
