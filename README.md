# pygeofilter-fes2

Translate supported CQL2-JSON and CQL2-Text filters into OGC FES 2.0 XML using
`pygeofilter` AST handlers. Translation is entirely offline.

```bash
pip install .
```

```python
from pygeofilter_fes2 import to_fes2_text

xml = to_fes2_text(
    "magnitude >= 4 AND name = 'Example'",
    property_mapping={"magnitude": "Magnitude", "name": "Name"},
)
print(xml)
```

Both syntax-specific helpers return Unicode XML with a `fes:Filter` root.
`parse_cql2` produces an AST; `to_fes2` also accepts an AST built directly with
pygeofilter. Strict mode requires an explicit property allowlist. Configure
`strict=False` to permit safe unmapped simple field names.

Dependencies: Python 3.10+, pygeofilter 0.4.0, lxml, Shapely. No HTTP or STAC
components or extras are included. WFS execution, schema discovery, response
processing and STAC conversion belong in a separate integration package.

See [API](docs/api.md), [operators](docs/operators.md),
[spatial and temporal behavior](docs/spatial-temporal.md), and
[architecture](docs/architecture.md). Run the offline examples in `examples/`.

For development:

```bash
hatch run dev:check
hatch run dev:format-check
hatch run dev:lint-check
hatch run dev:typecheck
hatch run dev:security
hatch run test:test
hatch build
```

Tests validate output with recorded official FES/GML schemas using a local
resolver. No schemas are downloaded at runtime. See `tests/schemas/README.md`
for provenance. The package constructs XML; it does not perform runtime XSD
validation or guarantee a particular server's supported operators.

Licensed under Apache-2.0; third-party schema notices are retained.
