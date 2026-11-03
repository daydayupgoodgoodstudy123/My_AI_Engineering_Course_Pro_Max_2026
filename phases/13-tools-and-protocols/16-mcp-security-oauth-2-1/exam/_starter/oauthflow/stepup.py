"""Scope challenges: read a Bearer WWW-Authenticate value and plan the step-up scope."""
from __future__ import annotations


def parse_bearer_challenge(header: str) -> dict[str, str]:
    """The parameters of the Bearer challenge in a WWW-Authenticate value.

    One value can carry several challenges, e.g. Basic realm="notes", Bearer error="insufficient_scope",
    scope="notes:delete". A challenge starts with its scheme name; scheme names compare
    case-insensitively, and only the Bearer challenge's parameters are returned, with lowercase
    names. A parameter value is a token or a quoted string. Inside a quoted string a backslash
    escapes the next character, and commas and spaces are ordinary characters. Without a Bearer
    challenge the result is {}.
    """
    raise NotImplementedError


def step_up_scope(granted: str, challenged: str) -> str:
    """The scope for a step-up flow: every granted and challenged scope once, sorted, space-separated.

    Both arguments are space-separated scope strings, and either may be empty. Challenged scopes
    are asked for as they are, whether or not the resource's scopes_supported lists them.
    """
    raise NotImplementedError
