"""Preserve date precision and serialize finite temporal primitives as GML 3.2."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import TYPE_CHECKING

from .exceptions import InvalidFilterError, UnsupportedOperatorError
from .properties import GML
from .serializer import element, text_element

if TYPE_CHECKING:
    from lxml import etree
    from pygeofilter import values


def temporal_text(value: date) -> str:
    """Format dates exactly and normalize aware timestamps to UTC.

    Raises:
        InvalidFilterError: If a timestamp lacks a timezone.
    """
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise InvalidFilterError("Timestamp literals require an explicit timezone")
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return value.isoformat()


def temporal_element(value: date | values.Interval, identifier: str) -> etree._Element:
    """Serialize an instant or finite ordered interval without filling missing dates.

    Raises:
        UnsupportedOperatorError: If bounds are open, durations or mixed precision.
        InvalidFilterError: If bounds are reversed or timestamps are naive.
    """
    if isinstance(value, date):
        result = element(
            "TimeInstant", text_element("timePosition", temporal_text(value), GML), namespace=GML
        )
    else:
        start, end = value.start, value.end
        if not isinstance(start, date) or not isinstance(end, date):
            raise UnsupportedOperatorError(
                "Only finite date or timestamp interval bounds are supported"
            )
        if isinstance(start, datetime) != isinstance(end, datetime):
            raise UnsupportedOperatorError("Interval bounds must have matching precision")
        start_text, end_text = temporal_text(start), temporal_text(end)
        if start > end:
            raise InvalidFilterError("Interval bounds are reversed")
        result = element(
            "TimePeriod",
            text_element("beginPosition", start_text, GML),
            text_element("endPosition", end_text, GML),
            namespace=GML,
        )
    result.set(f"{{{GML}}}id", identifier)
    return result
