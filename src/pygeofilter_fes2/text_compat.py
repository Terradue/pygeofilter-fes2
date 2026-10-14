"""Apply targeted CQL2 compliance fixes to pygeofilter 0.4's grammar and transformer.

The grammar, geometry/date parsing and AST construction are provided by
pygeofilter. This adapter fixes precedence, compound NOT, quoted literals,
short identifiers and functional temporal syntax without a separate parser.
"""

from __future__ import annotations

from importlib.resources import files
from typing import TYPE_CHECKING

from lark import Lark, v_args
from pygeofilter import ast
from pygeofilter.parsers.cql2_text.parser import CQLTransformer

from .exceptions import UnsupportedOperatorError

if TYPE_CHECKING:
    from lark import Token


@v_args(inline=True)
class _CQL2Transformer(CQLTransformer):
    def SINGLE_QUOTED(self, token: Token) -> str:
        return str(token)[1:-1].replace("''", "'")

    def DOUBLE_QUOTED(self, token: Token) -> str:
        return str(token)[1:-1].replace('""', '"')

    def temporal_function(
        self, operator: Token, left: ast.TemporalAstType, right: ast.TemporalAstType
    ) -> ast.TemporalPredicate:
        name = str(operator).lower()
        if name == "t_before":
            return ast.TimeBefore(left, right)
        if name == "t_after":
            return ast.TimeAfter(left, right)
        raise UnsupportedOperatorError(f"Unsupported temporal predicate: {name}")


def _parser() -> Lark:
    """Reuse the upstream grammar with explicit, version-specific corrections."""
    grammar = files("pygeofilter.parsers.cql2_text").joinpath("grammar.lark").read_text()
    start = grammar.index("?condition:")
    end = grammar.index("?predicate:", start)
    grammar = (
        grammar[:start]
        + """?condition: conjunction
          | condition "OR"i conjunction -> or_
?conjunction: condition_1
            | conjunction "AND"i condition_1 -> and_
?condition_1: predicate
            | "NOT"i condition_1 -> not_
            | "(" condition ")"

"""
        + grammar[end:]
    )
    grammar = grammar.replace(
        "?temporal_predicate: expression _binary_temporal_predicate_func expression -> binary_temporal_predicate",
        """?temporal_predicate: expression _binary_temporal_predicate_func expression -> binary_temporal_predicate
            | _binary_temporal_predicate_func "(" expression "," expression ")" -> temporal_function""",
    )
    grammar = grammar.replace(
        'SINGLE_QUOTED: "\'" /.*?/ "\'"', """SINGLE_QUOTED: /'(?:[^']|'')*'/"""
    )
    grammar = grammar.replace(
        'DOUBLE_QUOTED: "\\"" /.*?/ "\\""', """DOUBLE_QUOTED: /"(?:[^"]|"")*"/"""
    )
    grammar = grammar.replace("/[a-zA-Z][a-zA-Z_:0-9.]+/", "/[a-zA-Z_][a-zA-Z_:0-9.]*/")
    return Lark(
        grammar,
        parser="lalr",
        maybe_placeholders=False,
        transformer=_CQL2Transformer(),
        import_paths=[str(files("pygeofilter.parsers"))],
    )


def parse_text(expression: str) -> object:
    """Parse CQL2-Text with the corrected upstream grammar and AST transformer."""
    # Construct locally rather than sharing mutable parser state between calls.
    return _parser().parse(expression)
