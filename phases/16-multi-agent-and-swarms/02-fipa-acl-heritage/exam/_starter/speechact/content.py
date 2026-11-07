"""Finite typed S-expression syntax only; no eval, ontology or SL logical meaning."""
from .models import Atom,Quoted,SList
from .sexpr_support import TokenCursor,atom_text,quoted_text
def parse_content(text):
    """Parse exactly one nested list, bare Atom or Quoted string. Preserve order,
    nesting and the difference between empty list and empty quoted text.
    The supplied lexical cursor handles string escapes, not recursive structure.
    """
    raise NotImplementedError("parse_content")
def render_content(node):
    """Render a typed local tree with equivalent parse value and original child order."""
    raise NotImplementedError("render_content")
