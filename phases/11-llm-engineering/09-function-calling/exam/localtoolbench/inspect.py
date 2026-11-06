"""Structural teaching-code audit; submitted code is parsed and never executed."""
import ast
from .models import Issue,UNSAFE,parse_code
def inspect_code(code):
    """Report all Import/ImportFrom, exact dunder Attribute and unsafe Name nodes.

    Paths follow ast.iter_fields in preorder, using field strings/list indexes.
    Strings/comments are not syntax nodes; Name contexts all follow source policy.
    Line/column retain native AST metadata. Invalid syntax raises SyntaxError.
    This local syntax policy is not an execution sandbox or complete security proof.
    """
    raise NotImplementedError
