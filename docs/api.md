# API and property configuration

```python
from pygeofilter_fes2 import FieldType, parse_cql2, to_fes2

root = parse_cql2({"op": ">=", "args": [{"property": "score"}, 4]})
xml = to_fes2(
    root,
    property_mapping={"score": "source:Score"},
    namespaces={"source": "urn:example:source"},
    field_types={"score": FieldType.NUMERIC},
)
```

`parse_cql2(expression, *, language="cql2-json")` accepts a JSON mapping or JSON
string. For CQL2-Text, pass a string and `language="cql2-text"`. It returns a
pygeofilter predicate/condition AST. It does not resolve properties or prove
that every node has a supported translation; translation performs those checks.

`to_fes2(root, *, property_mapping=None, namespaces=None, strict=True,
field_types=None, crs=CRS84)` accepts an AST directly and returns Unicode XML.
`to_fes2_json` and `to_fes2_text` accept their respective input syntax and the same
keyword options. `FES2Evaluator` accepts the same configuration and its
`evaluate(root)` returns a predicate XML element; its `namespaces` property
provides a copy of bindings for serialization.

Strict mode permits only keys in the mapping. An absent/empty mapping permits
no properties. Non-strict mode passes through unmapped names after validation.
Public queryable names may differ from XML output names. Output references are
simple ASCII XML names or one-prefix QNames; XPath paths, indexes, wildcards and
unbound prefixes are rejected. The supported naming subset is deliberately
smaller than XML's full Unicode QName repertoire. Configure prefix bindings with
`namespaces`; `fes` and `gml` cannot be rebound. Reserved XML prefixes are rejected.

`FieldType` members are NUMERIC, BOOLEAN, STRING, DATE, DATETIME and GEOMETRY.
Metadata keys use public names. Types validate operands; they never coerce a
string into a number or a date into a timestamp. Unknown property types are
left to the caller's external schema knowledge. Properties must be single-valued
for the supported scalar semantics; arrays and multi-valued XPath queries are
outside this contract.

Exceptions are exported at the package root:

- `InvalidFilterError`: malformed syntax, configuration or incompatible operands.
- `UnknownPropertyError`: a property is absent from the strict allowlist.
- `UnsupportedOperatorError`: an AST operation/value has no faithful translation.
- `FES2SerializationError`: a value cannot be encoded as XML text.

The last three derive from `InvalidFilterError`, which derives from `ValueError`.
No Taskfile model generation is needed: pygeofilter owns the external AST/value
structures and the translator does not define external API models.
