# Offline XML schema fixtures

Downloaded on 2026-10-14 from the official OGC schema repository and W3C:

- https://schemas.opengis.net/filter/2.0/filterAll.xsd (FES 2.0.3)
- https://schemas.opengis.net/gml/3.2.1/gml.xsd (GML 3.2.1)
- Their recursive includes/imports (OWS, ISO 19139, W3C XML and XLink).

`manifest.json` records every source URL, local path and SHA-256 digest. Schema
files retain their original bytes and copyright/license notices. Original
http import URLs are resolved locally to their recorded copies; the downloaded
sources used HTTPS. The fixture resolver refuses missing files, network access
and paths outside this directory. A wrapper imports both FES and GML so GML
content under FES wildcard declarations is validated against authentic types.
The wrapper contains no permissive replacement definitions.

These fixtures are test-only. They are not packaged in the wheel and no XML
schemas are downloaded during translation or tests.

The OGC schema license is described at https://www.ogc.org/about-ogc/policies/software-licenses/.
W3C source notices and license references are retained in their schema files.
