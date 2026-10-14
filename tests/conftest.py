from __future__ import annotations

import socket
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn
from urllib.parse import urlparse

import pytest
from lxml import etree

if TYPE_CHECKING:
    from collections.abc import Iterator

    # The public Resolver signature uses this type, exported only by its stubs.
    from lxml.etree._docloader import _InputDocument

SCHEMAS = Path(__file__).parent / "schemas"


class LocalResolver(etree.Resolver):
    def resolve(self, url: str | None, public_id: str | None, context: object) -> _InputDocument:
        if url is None:
            raise OSError("Schema resolution requires a URL")
        parsed = urlparse(url)
        if parsed.scheme in {"http", "https"}:
            path = SCHEMAS / parsed.netloc / parsed.path.lstrip("/")
        else:
            path = Path(parsed.path)
        path = path.resolve()
        if not path.is_relative_to(SCHEMAS.resolve()) or not path.is_file():
            raise OSError(f"Schema resolution blocked: {url}")
        return self.resolve_filename(str(path), context)


@pytest.fixture(scope="session")
def xml_schema() -> etree.XMLSchema:
    parser = etree.XMLParser(no_network=True, resolve_entities=False)
    parser.resolvers.add(LocalResolver())
    wrapper = b"""<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
      <xs:import namespace="http://www.opengis.net/fes/2.0"
        schemaLocation="schemas.opengis.net/filter/2.0/filterAll.xsd"/>
      <xs:import namespace="http://www.opengis.net/gml/3.2"
        schemaLocation="schemas.opengis.net/gml/3.2.1/gml.xsd"/>
    </xs:schema>"""
    document = etree.fromstring(wrapper, parser, base_url=str(SCHEMAS / "validation.xsd"))
    return etree.XMLSchema(document)


def forbidden_network(*arguments: object, **keywords: object) -> NoReturn:
    raise AssertionError("Tests and translation must not access the network")


@pytest.fixture(autouse=True)
def block_network(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(socket, "create_connection", forbidden_network)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden_network)
    monkeypatch.setattr(socket.socket, "connect", forbidden_network)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden_network)
    yield
