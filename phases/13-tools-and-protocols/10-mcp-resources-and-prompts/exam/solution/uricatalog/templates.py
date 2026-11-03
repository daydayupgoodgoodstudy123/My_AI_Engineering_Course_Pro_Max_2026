"""Resource templates, compiled into a tree with one level per path segment."""
from __future__ import annotations

import re
from urllib.parse import unquote

SCHEME = "notes://"
_VALUE = re.compile(r"[A-Za-z0-9_-]{1,64}")
_LITERAL = re.compile(r"[A-Za-z0-9_-]+")
_VARIABLE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


class _Node:
    __slots__ = ("literals", "variable", "template")

    def __init__(self) -> None:
        self.literals: dict[str, _Node] = {}
        self.variable: _Node | None = None
        self.template: tuple[str, tuple[str, ...]] | None = None  # (name, its variable names in order)


class TemplateRouter:
    """Resolve concrete notes:// URIs against registered resource templates.

    A template such as notes://projects/{project}/decisions/{decision} is a notes:// URI whose path
    segments are literals (ASCII letters, digits, "-" and "_") or whole-segment {variables}.
    Templates are compiled into a tree with one level per path segment. Among the templates that
    match a URI, the one with a literal at the first segment where they differ wins. A template
    that would match exactly the same URIs as one already added is ambiguous; it is rejected with
    ValueError, as is a malformed template, and a rejected template changes nothing.

    Matching splits the URI into segments first, then percent-decodes each segment exactly once, so
    an encoded "/" (%2F) stays inside its segment. A variable's decoded value is 1 to 64 ASCII
    letters, digits, "-" or "_", and nothing else. A URI with extra or missing segments matches
    no template.
    """

    def __init__(self) -> None:
        self._root = _Node()

    def add(self, template: str, name: str) -> None:
        """Register template under name."""
        if not isinstance(template, str) or not template.startswith(SCHEME):
            raise ValueError(f"{template!r} is not a notes:// template")
        shape: list[str | None] = []  # a literal, or None for a variable
        variables: list[str] = []
        for segment in template[len(SCHEME):].split("/"):
            variable = _VARIABLE.fullmatch(segment)
            if variable is not None:
                if variable.group(1) in variables:
                    raise ValueError(f"{template!r} names {{{variable.group(1)}}} twice")
                variables.append(variable.group(1))
                shape.append(None)
            elif _LITERAL.fullmatch(segment):
                shape.append(segment)
            else:
                raise ValueError(f"{template!r} has a malformed segment {segment!r}")
        existing = self._find(shape)
        if existing is not None and existing.template is not None:
            raise ValueError(f"{template!r} matches exactly the URIs of {existing.template[0]!r}")
        node = self._root
        for part in shape:
            if part is None:
                if node.variable is None:
                    node.variable = _Node()
                node = node.variable
            else:
                node = node.literals.setdefault(part, _Node())
        node.template = (name, tuple(variables))

    def match(self, uri: str) -> tuple[str, dict[str, str]] | None:
        """(template name, {variable: decoded value}) for the template uri matches, or None."""
        if not isinstance(uri, str) or not uri.startswith(SCHEME):
            return None
        try:
            segments = [unquote(raw, errors="strict") for raw in uri[len(SCHEME):].split("/")]
        except UnicodeDecodeError:
            return None
        found = self._walk(self._root, segments, 0)
        if found is None:
            return None
        (name, variables), values = found
        return name, dict(zip(variables, values))

    def _find(self, shape: list[str | None]) -> _Node | None:
        node: _Node | None = self._root
        for part in shape:
            node = node.variable if part is None else node.literals.get(part)
            if node is None:
                return None
        return node

    def _walk(self, node: _Node, segments: list[str], i: int) -> tuple[tuple[str, tuple[str, ...]], list[str]] | None:
        """Depth first, literal before variable: the first template found is the one that wins."""
        if i == len(segments):
            return (node.template, []) if node.template is not None else None
        segment = segments[i]
        child = node.literals.get(segment)
        if child is not None:
            found = self._walk(child, segments, i + 1)
            if found is not None:
                return found
        if node.variable is not None and _VALUE.fullmatch(segment):
            found = self._walk(node.variable, segments, i + 1)
            if found is not None:
                template, values = found
                return template, [segment, *values]
        return None
