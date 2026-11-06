"""Given finite section/paragraph tree and local digest checks.

Source describes recursive summarization but has no such input tree/code.
This explicit fixture schema is an educational document-hierarchy adapter.
"""
from dataclasses import dataclass
from .primitives import count_tokens

@dataclass(frozen=True)
class DocumentNode:
    key: str
    title: str
    budget: int
    text: str = ""
    children: tuple = ()

def node_value(node):
    if not isinstance(node, DocumentNode) or not isinstance(node.key, str) or not node.key:
        raise ValueError("document node requires a key")
    if type(node.budget) is not int or node.budget < 0 or not isinstance(node.text, str):
        raise ValueError("invalid document budget or text")
    if node.children and node.text:
        raise ValueError("branch nodes contain children; paragraphs contain text")
    keys = [child.key for child in node.children]
    if len(keys) != len(set(keys)):
        raise ValueError("sibling source keys must be distinct")
    return node

def fit_digest(text, budget, path, summarize):
    """Given: preserve fitting text; check injected summary fits local budget."""
    if count_tokens(text) <= budget:
        return text
    output = summarize(text, budget, path)
    if not isinstance(output, str) or count_tokens(output) > budget:
        raise ValueError("summarizer exceeded local digest budget")
    return output
