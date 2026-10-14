"""Exceptions for invalid input and unsupported translation semantics."""


class InvalidFilterError(ValueError):
    """The filter or translator configuration is malformed."""


class UnsupportedOperatorError(InvalidFilterError):
    """An operation cannot be translated with guaranteed equivalent semantics."""


class UnknownPropertyError(InvalidFilterError):
    """A property is absent from the strict property mapping."""


class FES2SerializationError(InvalidFilterError):
    """A value cannot be represented as valid FES/GML XML."""
