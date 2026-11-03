"""Resource templates, compiled into a tree with one level per path segment."""
from __future__ import annotations

SCHEME = "notes://"


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

    def add(self, template: str, name: str) -> None:
        """Register template under name."""
        raise NotImplementedError

    def match(self, uri: str) -> tuple[str, dict[str, str]] | None:
        """(template name, {variable: decoded value}) for the template uri matches, or None."""
        raise NotImplementedError
