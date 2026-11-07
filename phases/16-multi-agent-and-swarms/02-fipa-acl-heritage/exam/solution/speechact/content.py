"""Finite typed S-expression syntax only; no eval, ontology or SL logical meaning."""
from .models import Atom,Quoted,SList
from .sexpr_support import TokenCursor,atom_text,quoted_text
def parse_content(text):
    """Parse exactly one nested list, bare Atom or Quoted string. Preserve order,
    nesting and the difference between empty list and empty quoted text.
    The supplied lexical cursor handles string escapes, not recursive structure.
    """
    cursor=TokenCursor(text)
    def read():
        kind,value=cursor.pop()
        if kind=="(":
            items=[]
            while cursor.peek() is not None and cursor.peek()[0]!=")":items.append(read())
            if cursor.pop()[0]!=")":raise ValueError("content closing delimiter")
            return SList(tuple(items))
        if kind=="atom":return Atom(value)
        if kind=="quoted":return Quoted(value)
        raise ValueError("unexpected content closing delimiter")
    result=read()
    if cursor.peek() is not None:raise ValueError("multiple content roots")
    return result
def render_content(node):
    """Render a typed local tree with equivalent parse value and original child order."""
    if isinstance(node,SList):return "("+" ".join(render_content(child) for child in node.items)+")"
    if isinstance(node,Atom):return atom_text(node.value)
    if isinstance(node,Quoted):return quoted_text(node.value)
    raise ValueError("typed local content node required")
