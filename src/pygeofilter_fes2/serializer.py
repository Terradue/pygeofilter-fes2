"""Construct namespaced FES/GML elements and serialize XML without interpolation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lxml import etree

from .exceptions import FES2SerializationError
from .properties import FES

if TYPE_CHECKING:
    from collections.abc import Mapping


def element(name: str, *children: etree._Element, namespace: str = FES) -> etree._Element:
    """Construct a namespaced element containing the supplied children."""
    result = etree.Element(f"{{{namespace}}}{name}")
    result.extend(children)
    return result


def text_element(name: str, text: str, namespace: str = FES) -> etree._Element:
    """Construct an element whose text is escaped by the XML serializer.

    Raises:
        FES2SerializationError: If text contains characters prohibited by XML.
    """
    result = element(name, namespace=namespace)
    try:
        result.text = text
    except ValueError as error:
        raise FES2SerializationError("Text contains invalid XML characters") from error
    return result


def serialize_filter(predicate: etree._Element, namespaces: Mapping[str, str]) -> str:
    """Serialize one predicate inside a FES 2.0 Filter root."""
    root = etree.Element(f"{{{FES}}}Filter", nsmap=dict(namespaces))
    root.append(predicate)
    return etree.tostring(root, encoding="unicode")
