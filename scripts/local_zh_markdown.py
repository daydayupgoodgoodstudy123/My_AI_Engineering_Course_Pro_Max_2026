"""Lossless Markdown preparation for local, resumable prose translation.

No translation service or third-party dependency is used here. ``prepare``
returns a reconstruction template and line/cell-sized strings. Protected spans
inside a string have stable ASCII placeholders so a translator sees the whole
sentence. Call ``validate_segment`` before caching a translated string, then
``rebuild`` to restore the original Markdown syntax and technical content.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
import re
from typing import Iterable, Mapping, Pattern, Sequence


TOKEN_RE = re.compile(r"ZXKEEP\d{8}QXZ")
_URL_RE = re.compile(r"(?:https?://|ftp://|mailto:)[^\s<>\[\]{}|\"']+", re.I)
_REFERENCE_RE = re.compile(r"^[ \t]{0,3}\[([^\]\n]+)\]:[ \t]*\S.*$", re.M)
_PREFIX_RE = re.compile(
    r"^[ \t]*(?:>[ \t]*)*(?:(?:[-+*]|\d{1,9}[.)])[ \t]+"
    r"(?:\[[ xX]\][ \t]+)?)?(?:#{1,6}[ \t]+)?"
)
_TABLE_SEPARATOR_RE = re.compile(
    r"^[ \t]*\|?[ \t]*:?-{3,}:?[ \t]*"
    r"(?:\|[ \t]*:?-{3,}:?[ \t]*)+\|?[ \t]*$"
)
_RULE_RE = re.compile(r"^[ \t]{0,3}(?:(?:\*[ \t]*){3,}|(?:-[ \t]*){3,}|(?:_[ \t]*){3,}|=+[ \t]*)$")
_HTML_RE = re.compile(
    r"<!--.*?-->|<!\[CDATA\[.*?\]\]>|<![A-Z][^>]*>|<\?.*?\?>|"
    r"</?[A-Za-z][A-Za-z0-9:_-]*(?:\s+(?:[^>\"']|\"[^\"]*\"|'[^']*')*)?\s*/?>",
    re.S,
)


@dataclass
class PreparedMarkdown:
    """A template with literal pieces and integer segment references."""

    pieces: list[str | int] = field(default_factory=list)
    segments: list[str] = field(default_factory=list)
    protected: dict[str, str] = field(default_factory=dict)
    kinds: dict[str, str] = field(default_factory=dict)

    def keep(self, value: str, kind: str) -> str:
        token = f"ZXKEEP{len(self.protected):08d}QXZ"
        self.protected[token] = value
        self.kinds[token] = kind
        return token


def _escaped(text: str, index: int) -> bool:
    backslashes = 0
    index -= 1
    while index >= 0 and text[index] == "\\":
        backslashes += 1
        index -= 1
    return bool(backslashes % 2)


def _block_spans(source: str) -> list[tuple[int, int, str]]:
    """Find frontmatter and fenced blocks, never an inline fence-looking run."""
    lines = source.splitlines(keepends=True)
    offsets: list[int] = []
    offset = 0
    for line in lines:
        offsets.append(offset)
        offset += len(line)
    spans: list[tuple[int, int, str]] = []
    index = 0
    if lines and lines[0].lstrip("\ufeff").rstrip("\r\n") == "---":
        for end in range(1, len(lines)):
            if lines[end].rstrip("\r\n") in {"---", "..."}:
                spans.append((0, offsets[end] + len(lines[end]), "frontmatter"))
                index = end + 1
                break
    while index < len(lines):
        # Leading indentation and blockquote/list containers are allowed, but
        # prose followed by ``` is never an opening fence.
        opener = re.match(
            r"^[ \t]*(?:>[ \t]*)*(?:(?:[-+*]|\d+[.)])[ \t]+)?(`{3,}|~{3,})([^\r\n]*)",
            lines[index],
        )
        if not opener or (opener.group(1)[0] == "`" and "`" in opener.group(2)):
            index += 1
            continue
        fence = opener.group(1)
        closer = re.compile(
            r"^[ \t]*(?:>[ \t]*)*" + re.escape(fence[0]) + r"{" + str(len(fence)) + r",}[ \t]*(?:\r?\n)?$"
        )
        end = index + 1
        while end < len(lines) and not closer.match(lines[end]):
            end += 1
        if end == len(lines):
            stop = len(source)
        else:
            stop = offsets[end] + len(lines[end])
        spans.append((offsets[index], stop, "code_blocks"))
        index = end + 1
    return spans


def _balanced_destination(text: str, start: int) -> int | None:
    """Return end of a Markdown (destination 'title'), including parentheses."""
    depth = 0
    quote: str | None = None
    angle = False
    for index in range(start, len(text)):
        char = text[index]
        if _escaped(text, index):
            continue
        if quote:
            if char == quote:
                quote = None
            continue
        if angle:
            if char == ">":
                angle = False
            continue
        if char == "<":
            angle = True
        elif char in "\"'" and index > start and text[index - 1].isspace():
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index + 1
    return None


def _find_close(text: str, delimiter: str, start: int) -> int | None:
    index = start
    while True:
        index = text.find(delimiter, index)
        if index < 0:
            return None
        if not _escaped(text, index):
            return index
        index += len(delimiter)


def _reference_key(text: str) -> str:
    return " ".join(text.split()).casefold()


def _mask_inline(text: str, prepared: PreparedMarkdown, references: set[str]) -> str:
    result: list[str] = []
    index = 0
    while index < len(text):
        existing = TOKEN_RE.match(text, index)
        if existing:
            result.append(existing.group())
            index = existing.end()
            continue
        char = text[index]
        if char == "`" and not _escaped(text, index):
            run = re.match(r"`+", text[index:]).group()
            end = index + len(run)
            matched_end = None
            while True:
                match = re.search(r"`+", text[end:])
                if not match:
                    break
                begin = end + match.start()
                finish = end + match.end()
                # Backslashes are literal *inside* a Markdown code span. For
                # example `C:\` has a valid closing backtick after the slash.
                if finish - begin == len(run):
                    matched_end = finish
                    break
                end = finish
            if matched_end is not None:
                result.append(prepared.keep(text[index:matched_end], "inline_code"))
                index = matched_end
                continue
            # Unmatched backticks remain syntax, rather than translatable text.
            result.append(prepared.keep(run, "markdown"))
            index += len(run)
            continue
        math_delimiter: tuple[str, str] | None = None
        if text.startswith("\\[", index) and not _escaped(text, index):
            math_delimiter = ("\\[", "\\]")
        elif text.startswith("\\(", index) and not _escaped(text, index):
            math_delimiter = ("\\(", "\\)")
        elif char == "$" and not _escaped(text, index):
            math_delimiter = ("$$", "$$") if text.startswith("$$", index) else ("$", "$")
        if math_delimiter:
            opening, closing = math_delimiter
            end = _find_close(text, closing, index + len(opening))
            dollar_math = (
                end is not None
                and index + 1 < end
                and not text[index + 1].isspace()
                and not text[end - 1].isspace()
                and "\n" not in text[index:end]
                and not (end + 1 < len(text) and text[end + 1].isdigit())
            )
            if end is not None and (opening != "$" or dollar_math):
                finish = end + len(closing)
                result.append(prepared.keep(text[index:finish], "math"))
                index = finish
                continue
        if char == "<":
            autolink = re.match(r"<(?:https?://|ftp://|mailto:)[^>\r\n]+>|<[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}>", text[index:])
            html = _HTML_RE.match(text, index)
            match = autolink or html
            if match:
                value = match.group()
                result.append(prepared.keep(value, "link_targets" if autolink else "html"))
                index += len(value)
                continue
        if char == "(" and index and text[index - 1] == "]" and not _escaped(text, index - 1):
            end = _balanced_destination(text, index)
            if end is not None:
                result.append(prepared.keep(text[index:end], "link_targets"))
                index = end
                continue
        if char == "[" and not _escaped(text, index):
            close = _find_close(text, "]", index + 1)
            if close is not None:
                label = text[index + 1:close]
                # Explicit reference IDs and footnote IDs must remain stable.
                is_reference_id = index > 0 and text[index - 1] == "]"
                collapsed = text.startswith("[]", close + 1)
                shortcut = _reference_key(label) in references and not text.startswith(("(", "["), close + 1)
                if label.startswith("^") or is_reference_id or collapsed or shortcut:
                    end = close + 3 if collapsed else close + 1
                    result.append(prepared.keep(text[index:end], "reference_ids"))
                    index = end
                    continue
        url = _URL_RE.match(text, index)
        if url:
            value = url.group()
            # Sentence punctuation is prose, balanced URL parentheses are not.
            value = value.rstrip(".,;:!?")
            while value.endswith(")") and value.count(")") > value.count("("):
                value = value[:-1]
            if value:
                result.append(prepared.keep(value, "link_targets"))
                index += len(value)
                continue
        if char == "\\" and index + 1 < len(text) and text[index + 1] in r"!\"#$%&'()*+,-./:;<=>?@[\]^_`{|}~":
            result.append(prepared.keep(text[index:index + 2], "markdown"))
            index += 2
            continue
        result.append(char)
        index += 1
    return "".join(result)


def _masked_source(source: str, prepared: PreparedMarkdown) -> str:
    if TOKEN_RE.search(source):
        raise ValueError("Source contains a reserved ZXKEEP placeholder")
    pieces: list[str] = []
    last = 0
    for begin, end, kind in _block_spans(source):
        pieces.extend((source[last:begin], prepared.keep(source[begin:end], kind)))
        last = end
    pieces.append(source[last:])
    masked = "".join(pieces)
    references = {
        _reference_key(match.group(1))
        for match in _REFERENCE_RE.finditer(masked)
        if not match.group(1).startswith("^")
    }
    masked = _REFERENCE_RE.sub(
        lambda match: match.group() if match.group(1).startswith("^") else prepared.keep(match.group(), "reference_destinations"),
        masked,
    )
    return _mask_inline(masked, prepared, references)


def _glossary_pattern(glossary: Mapping[str, str] | Iterable[str] | Pattern[str] | None) -> Pattern[str] | None:
    if glossary is None:
        return None
    if isinstance(glossary, re.Pattern):
        return glossary
    terms = list(glossary.keys() if isinstance(glossary, Mapping) else glossary)
    alternatives = []
    for term in sorted(set(terms), key=lambda value: (-len(value), value)):
        if not term:
            continue
        literal = re.escape(term)
        # Preserve ordinary singular/plural forms without modifying their
        # spelling or case in the source. Irregular plurals can be extra keys.
        if re.search(r"[A-Za-z]$", term):
            if re.search(r"[^aeiou]y$", term, re.I):
                literal = re.escape(term[:-1]) + r"(?:y|ies)"
            elif re.search(r"(?:s|x|z|ch|sh)$", term, re.I):
                literal += r"(?:es)?"
            else:
                literal += r"(?:s)?"
        alternatives.append((r"(?<!\w)" if term[0].isalnum() else "") + literal + (r"(?!\w)" if term[-1].isalnum() else ""))
    return re.compile("|".join(alternatives), re.I) if alternatives else None


def _map_unprotected(text: str, operation) -> str:
    pieces: list[str] = []
    last = 0
    for match in TOKEN_RE.finditer(text):
        pieces.extend((operation(text[last:match.start()]), match.group()))
        last = match.end()
    pieces.append(operation(text[last:]))
    return "".join(pieces)


def prepare(
    source: str,
    glossary: Mapping[str, str] | Iterable[str] | Pattern[str] | None = None,
) -> tuple[PreparedMarkdown, list[str]]:
    """Prepare Markdown while retaining sentence context and exact syntax.

    ``glossary`` can be literal terms, a mapping whose *keys* are literal terms
    (values are ignored), or a compiled regex. Matches are preserved verbatim.
    The returned list is the same list as ``prepared.segments``. Frontmatter,
    fences, math, code, HTML tags, URLs and link targets never reach translation.
    """
    prepared = PreparedMarkdown()
    masked = _masked_source(source, prepared)
    glossary_re = _glossary_pattern(glossary)
    if glossary_re:
        masked = _map_unprotected(masked, lambda text: glossary_re.sub(lambda match: prepared.keep(match.group(), "glossary"), text))

    def add_cell(cell: str) -> None:
        leading = re.match(r"[ \t]*", cell).group()
        trailing = re.search(r"[ \t]*$", cell).group()
        stop = len(cell) - len(trailing) if trailing else len(cell)
        content = cell[len(leading):stop]
        if not content:
            prepared.pieces.append(cell)
            return
        # Emphasis and link-label brackets stay in their original form. Their
        # placeholders still let the translator move a complete emphasized
        # phrase within the sentence when Chinese grammar requires it.
        content = _map_unprotected(
            content,
            lambda text: re.sub(r"\*+|_+|~{2,}|\[|\]", lambda match: prepared.keep(match.group(), "markdown"), text),
        )
        prose = TOKEN_RE.sub("", content)
        prepared.pieces.append(leading)
        if re.search(r"[A-Za-z\u00c0-\u024f\u4e00-\u9fff]", prose):
            prepared.pieces.append(len(prepared.segments))
            prepared.segments.append(content)
        else:
            prepared.pieces.append(content)
        prepared.pieces.append(trailing)

    for line in masked.splitlines(keepends=True):
        ending_match = re.search(r"(?:\r\n|\r|\n)$", line)
        ending = ending_match.group() if ending_match else ""
        body = line[:-len(ending)] if ending else line
        if _TABLE_SEPARATOR_RE.match(body) or _RULE_RE.match(body):
            prepared.pieces.extend((body, ending))
            continue
        prefix = _PREFIX_RE.match(body).group()
        prepared.pieces.append(prefix)
        body = body[len(prefix):]
        suffix = ""
        if re.match(r"^[ \t]*(?:>[ \t]*)*#{1,6}[ \t]+", line):
            closing = re.search(r"[ \t]+#+[ \t]*$", body)
            if closing:
                suffix = closing.group()
                body = body[:closing.start()]
        # Pipes within code, escapes, math, HTML or destinations are masked.
        for index, cell in enumerate(body.split("|")):
            if index:
                prepared.pieces.append("|")
            add_cell(cell)
        prepared.pieces.extend((suffix, ending))
    return prepared, prepared.segments


def translation_errors(original_segment: str, translation: str) -> list[str]:
    """Report broken/missing/duplicated placeholders and added physical lines."""
    if not isinstance(translation, str):
        return ["translation is not a string"]
    errors: list[str] = []
    expected = Counter(TOKEN_RE.findall(original_segment))
    actual = Counter(TOKEN_RE.findall(translation))
    if expected != actual:
        missing = list((expected - actual).elements())
        extra = list((actual - expected).elements())
        errors.append(f"placeholder mismatch: missing={missing}, extra={extra}")
    if "\n" in translation or "\r" in translation:
        errors.append("translation introduces a physical newline")
    if translation.count("|") != original_segment.count("|"):
        errors.append("translation changes table cell separators")
    return errors


def validate_segment(original_segment: str, translation: str) -> bool:
    """Whether a translated string can safely replace its prepared segment."""
    return not translation_errors(original_segment, translation)


def rebuild(prepared: PreparedMarkdown, translations: Sequence[str]) -> str:
    """Restore protected source spans; fail closed if a placeholder changed."""
    if len(translations) != len(prepared.segments):
        raise ValueError(f"Expected {len(prepared.segments)} translations, got {len(translations)}")
    for index, (original, translated) in enumerate(zip(prepared.segments, translations)):
        errors = translation_errors(original, translated)
        if errors:
            raise ValueError(f"Segment {index}: {'; '.join(errors)}")
    masked = "".join(translations[piece] if isinstance(piece, int) else piece for piece in prepared.pieces)
    return _restore_protected(masked, prepared)


def _restore_protected(text: str, prepared: PreparedMarkdown) -> str:
    # Protection can nest: a multiline math or HTML span may include a token
    # inserted for an earlier fenced block. Original sources cannot contain
    # reserved tokens, so each pass moves strictly toward literal source text.
    for _ in range(len(prepared.protected) + 1):
        if not TOKEN_RE.search(text):
            return text
        text = TOKEN_RE.sub(lambda match: prepared.protected[match.group()], text)
    raise ValueError("Cyclic protected Markdown placeholders")


def extract_invariants(source: str) -> dict[str, object]:
    """Extract exact technical spans and Markdown structure for comparison."""
    prepared = PreparedMarkdown()
    masked = _masked_source(source, prepared)
    by_kind: dict[str, list[str]] = {}
    for token, value in prepared.protected.items():
        by_kind.setdefault(prepared.kinds[token], []).append(_restore_protected(value, prepared))
    lines = masked.splitlines()
    headings = sum(bool(re.match(r"^[ \t]*(?:>[ \t]*)*#{1,6}[ \t]+", line)) for line in lines)
    lists = sum(bool(re.match(r"^[ \t]*(?:>[ \t]*)*(?:[-+*]|\d{1,9}[.)])[ \t]+", line)) for line in lines)
    table_cells = []
    for line in lines:
        if "|" in line and not _TABLE_SEPARATOR_RE.match(line):
            cells = line.strip().split("|")
            if not cells[0]:
                cells.pop(0)
            if cells and not cells[-1]:
                cells.pop()
            table_cells.append(len(cells))
    return {
        "code_blocks": tuple(by_kind.get("code_blocks", ())),
        "inline_code": tuple(by_kind.get("inline_code", ())),
        "math": tuple(by_kind.get("math", ())),
        "html": tuple(by_kind.get("html", ())),
        "link_targets": tuple(by_kind.get("link_targets", ())),
        "reference_destinations": tuple(by_kind.get("reference_destinations", ())),
        "reference_ids": tuple(by_kind.get("reference_ids", ())),
        "frontmatter": tuple(by_kind.get("frontmatter", ())),
        "heading_count": headings,
        "list_item_count": lists,
        "table_row_count": len(table_cells),
        "table_cell_counts": tuple(table_cells),
        "table_separator_count": sum(bool(_TABLE_SEPARATOR_RE.match(line)) for line in lines),
    }


def self_test() -> None:
    """Deterministic round-trip and protection regression checks."""
    source = '''---\ntitle: English YAML must stay\n---\n# **A heading** with `code` ###\n\nText with `{"content": "```json"}` and **bold words**.\n```python\nprint("English fenced code")\n```\n> ~~~~text\n> Example | text\n> ~~~~\n\n$$\nx = \\frac{a}{b}\n$$\nInline $a_b + c$ and \\(x^2\\), plus \\[y = z\\].\n[Readable label](https://example.org/a_(b) "Original title") and [reference][id].\n[id]: https://example.org/original "Original title"\n[ id ] is a shortcut. [reference][] stays resolvable.\n[^note]: Footnote prose.\n<a href="https://example.org/?a=1&b=2" title="Keep me">Human text</a>\n<!-- preserve\nmultiline comment -->\n| English cell | `a|b` and $x|y$ |\n| :--- | ---: |\n| [Label](../docs/en.md) | Escaped \\| pipe |\n1. First item with Python and a raw https://example.org/path.\n'''
    prepared, segments = prepare(source, {"Python": "ignored"})
    assert rebuild(prepared, segments) == source
    assert any("bold words" in segment and "Text with" in segment for segment in segments)
    assert all("print(" not in segment for segment in segments)
    assert all("https://" not in segment for segment in segments)
    assert all("Original title" not in segment for segment in segments)
    # Test the restoration contract without changing placeholder spelling.
    translated = [_map_unprotected(segment, lambda text: re.sub(r"[A-Za-z]+", "中文", text)) for segment in segments]
    output = rebuild(prepared, translated)
    assert extract_invariants(output) == extract_invariants(source)
    token_segment = next(segment for segment in segments if TOKEN_RE.search(segment))
    assert not validate_segment(token_segment, TOKEN_RE.sub("", token_segment, count=1))
    assert not validate_segment("English", "中文\n新行")
    assert not validate_segment("English", "中文|新列")
    for extra in ("# Heading\r\n\r\nBody\r\n", "Sentence with ``` inside prose.\n", "`unclosed code\n", "~~~text\nUnclosed fence\n"):
        prepared, segments = prepare(extra)
        assert rebuild(prepared, segments) == extra
    print("local_zh_markdown: self-tests passed")


if __name__ == "__main__":
    self_test()
