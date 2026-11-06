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
    issues=[]
    def walk(node,path):
        if isinstance(node,(ast.Import,ast.ImportFrom)):kind="import"
        elif isinstance(node,ast.Attribute) and node.attr.startswith("__") and node.attr.endswith("__"):kind="dunder"
        elif isinstance(node,ast.Name) and node.id in UNSAFE:kind="unsafe_name"
        else:kind=None
        if kind:issues.append(Issue(kind,path,node.lineno,node.col_offset))
        for field,value in ast.iter_fields(node):
            if isinstance(value,ast.AST):walk(value,path+(field,))
            elif isinstance(value,list):
                for i,child in enumerate(value):
                    if isinstance(child,ast.AST):walk(child,path+(field,i))
    walk(parse_code(code),())
    return issues
