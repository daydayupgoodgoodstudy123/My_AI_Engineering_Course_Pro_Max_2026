"""Scope challenges: read a Bearer WWW-Authenticate value and plan the step-up scope."""
from __future__ import annotations

_BLANK = " \t"


def parse_bearer_challenge(header: str) -> dict[str, str]:
    """The parameters of the Bearer challenge in a WWW-Authenticate value.

    One value can carry several challenges, e.g. Basic realm="notes", Bearer error="insufficient_scope",
    scope="notes:delete". A challenge starts with its scheme name; scheme names compare
    case-insensitively, and only the Bearer challenge's parameters are returned, with lowercase
    names. A parameter value is a token or a quoted string. Inside a quoted string a backslash
    escapes the next character, and commas and spaces are ordinary characters. Without a Bearer
    challenge the result is {}.
    """
    for scheme, params in _challenges(header):
        if scheme.lower() == "bearer":
            return params
    return {}


def step_up_scope(granted: str, challenged: str) -> str:
    """The scope for a step-up flow: every granted and challenged scope once, sorted, space-separated.

    Both arguments are space-separated scope strings, and either may be empty. Challenged scopes
    are asked for as they are, whether or not the resource's scopes_supported lists them.
    """
    return " ".join(sorted(set(granted.split()) | set(challenged.split())))


def _challenges(header: str) -> list[tuple[str, dict[str, str]]]:
    challenges: list[tuple[str, dict[str, str]]] = []
    i, n = 0, len(header)
    while i < n:
        while i < n and (header[i] in _BLANK or header[i] == ","):
            i += 1
        start = i
        while i < n and header[i] not in _BLANK and header[i] not in ",=":
            i += 1
        name = header[start:i]
        if not name:
            if i < n:
                raise ValueError(f"unexpected {header[i]!r} in WWW-Authenticate")
            break
        j = i
        while j < n and header[j] in _BLANK:
            j += 1
        if j < n and header[j] == "=":
            if not challenges:
                raise ValueError("a WWW-Authenticate parameter before any scheme")
            j += 1
            while j < n and header[j] in _BLANK:
                j += 1
            if j < n and header[j] == '"':
                value, j = _quoted(header, j)
            else:
                start = j
                while j < n and header[j] not in _BLANK and header[j] != ",":
                    j += 1
                value = header[start:j]
            challenges[-1][1][name.lower()] = value
        else:
            challenges.append((name, {}))
        i = j
    return challenges


def _quoted(text: str, i: int) -> tuple[str, int]:
    out: list[str] = []
    i += 1
    while i < len(text):
        char = text[i]
        if char == "\\" and i + 1 < len(text):
            out.append(text[i + 1])
            i += 2
        elif char == '"':
            return "".join(out), i + 1
        else:
            out.append(char)
            i += 1
    raise ValueError("an unterminated quoted string in WWW-Authenticate")
