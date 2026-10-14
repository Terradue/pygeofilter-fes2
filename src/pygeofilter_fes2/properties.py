"""Resolve safe XML property references without schema discovery or XPath input."""

from __future__ import annotations

import re
from enum import Enum
from typing import TYPE_CHECKING

from .exceptions import InvalidFilterError, UnknownPropertyError

if TYPE_CHECKING:
    from collections.abc import Mapping

FES = "http://www.opengis.net/fes/2.0"
GML = "http://www.opengis.net/gml/3.2"
_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_.-]*(?::[A-Za-z_][A-Za-z0-9_.-]*)?\Z")


class FieldType(Enum):
    """Operand categories for optional, caller-supplied property metadata."""

    NUMERIC = "numeric"
    BOOLEAN = "boolean"
    STRING = "string"
    DATE = "date"
    DATETIME = "datetime"
    GEOMETRY = "geometry"


class PropertyResolver:
    """Resolve queryable names using a snapshot of explicit caller configuration."""

    def __init__(
        self,
        property_mapping: Mapping[str, str] | None = None,
        namespaces: Mapping[str, str] | None = None,
        strict: bool = True,
        field_types: Mapping[str, FieldType] | None = None,
    ) -> None:
        """Configure permitted properties and their XML namespaces.

        Args:
            property_mapping: Public queryable names mapped to simple XML QNames.
            namespaces: Prefix bindings declared on the Filter root.
            strict: Reject unmapped names when true, including with no mapping.
            field_types: Optional operand metadata keyed by public queryable name.

        Raises:
            InvalidFilterError: If a name, namespace binding or type is invalid.
        """
        self._mapping = dict(property_mapping or {})
        self._namespaces = self._validate_namespaces(namespaces or {})
        self._strict = strict
        self._types = dict(field_types or {})
        for reference in self._mapping.values():
            self._validate_reference(reference)
        for name, field_type in self._types.items():
            if not isinstance(field_type, FieldType):
                raise InvalidFilterError(f"Invalid field type for {name!r}")
            self.resolve(name)

    @staticmethod
    def _validate_namespaces(namespaces: Mapping[str, str]) -> dict[str, str]:
        result = {"fes": FES, "gml": GML}
        for prefix, uri in namespaces.items():
            if not _NAME.fullmatch(prefix) or ":" in prefix or prefix.lower().startswith("xml"):
                raise InvalidFilterError(f"Invalid namespace prefix: {prefix!r}")
            if not uri or uri in {
                "http://www.w3.org/2000/xmlns/",
                "http://www.w3.org/XML/1998/namespace",
            }:
                raise InvalidFilterError(f"Invalid namespace URI for {prefix!r}")
            if prefix in result and result[prefix] != uri:
                raise InvalidFilterError(f"Cannot rebind reserved prefix {prefix!r}")
            result[prefix] = uri
        return result

    def _validate_reference(self, reference: str) -> None:
        if not isinstance(reference, str) or not _NAME.fullmatch(reference):
            raise InvalidFilterError(f"Expected a simple XML property QName: {reference!r}")
        if ":" in reference and reference.split(":", 1)[0] not in self._namespaces:
            raise InvalidFilterError(f"Undeclared property namespace: {reference!r}")

    @property
    def namespaces(self) -> dict[str, str]:
        """A copy of namespace bindings for the Filter root."""
        return dict(self._namespaces)

    def resolve(self, name: str) -> str:
        """Resolve a public queryable to a validated XML property reference.

        Raises:
            UnknownPropertyError: If strict mode disallows the name.
            InvalidFilterError: If the output reference is unsafe or unbound.
        """
        if not isinstance(name, str):
            raise InvalidFilterError("Property names must be strings")
        if self._strict and name not in self._mapping:
            raise UnknownPropertyError(f"Unknown queryable: {name!r}")
        reference = self._mapping.get(name, name)
        self._validate_reference(reference)
        return reference

    def field_type(self, name: str) -> FieldType | None:
        """Return optional metadata for a public queryable."""
        return self._types.get(name)
