# Supported operators and limitations

| CQL2 | FES 2.0 encoding |
| --- | --- |
| AND, OR, NOT | And, Or, Not |
| =, <>, <, <=, >, >= | Corresponding PropertyIs comparison |
| BETWEEN | PropertyIsBetween with inclusive boundaries |
| IN | Or of equality predicates; one option uses a single equality |
| LIKE | PropertyIsLike with explicit wildcard, singleChar and escapeChar |
| IS NULL | PropertyIsNull |
| S_INTERSECTS | Intersects |
| S_WITHIN | Within |
| S_CONTAINS | Contains |
| S_DISJOINT | Disjoint |
| T_BEFORE, T_AFTER | Before, After for representable temporal operands |
| Direct AST BBox / text BBOX | BBOX with a GML Envelope |

NOT BETWEEN, NOT IN, NOT LIKE and IS NOT NULL use `fes:Not` around the predicate.
CQL2 LIKE uses `%`, `_` and backslash. Direct AST LIKE preserves its own
wildcard/escape configuration and `nocase` flag. Nested predicates preserve
precedence, with AND binding more tightly than OR in text.

Supported literals are finite numbers, booleans, strings, dates, timezone-aware
timestamps, valid supported 2D geometries and finite intervals. Empty IN lists,
null comparisons, predicates used as expressions, expression-only roots and
known incompatible categories raise explicit errors. Use IS NULL for null tests.
Scalar properties and their literal values must have compatible types; BETWEEN
requires numeric operands. An unknown property type is not inferred from its
name. This library serializes filters; it does not evaluate SQL/CQL three-valued
logic against data. Interoperability requires the receiving processor to apply
compatible null and single-valued-property semantics.

Arithmetic, functions (including CASEI/ACCENTI), arrays, INCLUDE/EXCLUDE,
distance predicates, additional spatial relations, open/duration intervals,
and temporal relations other than BEFORE/AFTER are unsupported. In particular,
pygeofilter 0.4 aliases T_INTERSECTS to TimeOverlaps, so both that alias and direct
TimeOverlaps ASTs are rejected rather than mistaken for FES temporal overlap.
Unsupported JSON constructs that upstream cannot parse may raise
InvalidFilterError at parsing instead of UnsupportedOperatorError.

The parser is pygeofilter, with the narrow compatibility corrections described
in [architecture](architecture.md). This package implements a supported subset,
not every CQL2 conformance class or every permissive upstream syntax extension.

Standards references:
[OGC CQL2](https://docs.ogc.org/is/21-065r2/21-065r2.html) and
[OGC FES 2.0.3](https://docs.ogc.org/is/09-026r2/09-026r2.html).
