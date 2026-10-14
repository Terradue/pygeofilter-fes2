# Architecture

The only processing chain is CQL2 input → pygeofilter AST → FES2Evaluator → XML.
The package never makes network requests. Client execution, service discovery,
response processing, pagination, STAC mapping and domain adapters belong in a
separate integration layer.

`FES2Evaluator` follows the `Evaluator` subclass and `@handle` pattern in
[Terradue CDSEEvaluator](https://github.com/Terradue/pygeofilter-odata-cdse/blob/main/src/pygeocdse/evaluator.py).
It uses XML elements rather than concatenated strings. Parsing, property
resolution, operand validation, geometry, time and serialization are separate
modules. No schema-derived Python models are introduced.

pygeofilter is pinned to 0.4.0 because compatibility handling is version-specific.
JSON input is adapted for standard three-argument BETWEEN and bbox coordinate
ordering. Parsed LIKE nodes receive the standard `_` single-character wildcard.
For text, `text_compat.py` loads the upstream grammar and reuses its
`CQLTransformer` (including WKT/date transformation), correcting AND/OR
precedence, compound NOT, doubled quotes, short identifiers, and functional
BEFORE/AFTER syntax. No independent CQL2 grammar or AST is maintained. This is an
intentional dependency on the pinned parser's transformer API; update its tests
before changing that version. A parser is created per text call to avoid shared
mutable parser state.

The evaluator returns a predicate element. `to_fes2` wraps it in `fes:Filter`
with all configured namespace bindings. GML identifiers are unique within one
evaluator instance; separate calls through the convenience API use new instances.
Caller dictionaries are copied. Reuse evaluators sequentially, not concurrently.

Tests import the official FES 2.0.3 and GML 3.2.1 schemas into a validation wrapper.
A local-only resolver handles their complete dependency closure, including OWS,
ISO and W3C schemas. Those schema dependencies are validation fixtures, not
runtime WFS functionality. No runtime validation or downloads are performed.
