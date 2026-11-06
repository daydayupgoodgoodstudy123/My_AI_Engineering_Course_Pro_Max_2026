#!/usr/bin/env python3
"""Build local Chinese lesson navigation without changing English sources.

After Chinese companion files have been generated, run this script to retain
the English heading anchors, localize links whose companions exist, and write
``phases/中文教程索引.md``.  ``--check-only`` reports pending changes and missing
companions without writing anything.  This is a local learner workflow; it
does not publish or commit the generated translations.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import html
import json
import os
from pathlib import Path
import re
import unicodedata
from urllib.parse import quote, unquote, urlsplit, urlunsplit

from local_zh_markdown import _block_spans


ROOT = Path(__file__).resolve().parent.parent
INDEX_NAME = "中文教程索引.md"
PHASE_RE = re.compile(r"^\d{2}-")
ATX_HEADING = re.compile(r"^[ \t]*(?:>[ \t]*)*(#{1,6})(?:[ \t]+(.*?)|[ \t]*)$")
SETEXT_HEADING = re.compile(r"^ {0,3}(=+|-+)[ \t]*$")
INLINE_TICKS = re.compile(r"`+")
ANCHOR_LINE = re.compile(r'^\s*<a\s+id=[\"\']([^\"\']+)[\"\']\s*>\s*</a>\s*$')
REFERENCE_LINK = re.compile(r"(?m)^ {0,3}\[[^\]\n]+\]:[ \t]*(<[^>\n]+>|\S+)")


@dataclass(frozen=True)
class Heading:
    line: int
    title: str
    slug: str


def companion_path(source: Path) -> Path:
    """Use zh.md for en.md, and <stem>.zh.md for every other source."""
    if source.name == "en.md":
        return source.with_name("zh.md")
    return source.with_name(f"{source.stem}.zh.md")


def source_markdown_files(root: Path = ROOT) -> list[Path]:
    """Exclude this generated index and all generated Chinese companions."""
    phases = root / "phases"
    return sorted(
        path
        for path in phases.rglob("*.md")
        if path.name not in {"zh.md", INDEX_NAME}
        and not path.name.endswith(".zh.md")
    )


def _navigation_block_spans(source: str) -> list[tuple[int, int, str]]:
    """Also recognize source YAML after the generated translation notice."""
    spans = _block_spans(source)
    if any(kind == "frontmatter" for _, _, kind in spans):
        return spans
    prefix = re.match(r"\A\ufeff?(?:[ \t\r\n]|<!--[\s\S]*?-->)*", source)
    start = prefix.end() if prefix else 0
    if start:
        for begin, end, kind in _block_spans(source[start:]):
            if kind == "frontmatter" and begin == 0:
                # The notice is protected with its YAML so neither participates
                # in headings or Markdown destination rewriting.
                stop = start + end
                spans = [span for span in spans if span[0] >= stop]
                spans.insert(0, (0, stop, "frontmatter"))
                break
    return spans


def _fenced_line_flags(lines: list[str]) -> list[bool]:
    """Share translation's protection for YAML and nested Markdown fences.

    This includes blockquote/list containers and matches the actual closing
    fence character and length, so a ~~~~~ drawing remains code content.
    """
    flags: list[bool] = []
    spans = _navigation_block_spans("".join(lines))
    span_index = 0
    offset = 0
    for line in lines:
        while span_index < len(spans) and spans[span_index][1] <= offset:
            span_index += 1
        flags.append(
            span_index < len(spans)
            and spans[span_index][0] <= offset < spans[span_index][1]
        )
        offset += len(line)
    return flags


def _prose_mask(markdown: str) -> str:
    """Mask fences and inline code without changing offsets or newlines."""
    lines = markdown.splitlines(keepends=True)
    flags = _fenced_line_flags(lines)
    chars = list(markdown)
    offset = 0
    for line, protected in zip(lines, flags):
        if protected:
            for index in range(offset, offset + len(line)):
                if chars[index] not in "\r\n":
                    chars[index] = " "
        offset += len(line)

    masked = "".join(chars)
    cursor = 0
    while (opening := INLINE_TICKS.search(masked, cursor)) is not None:
        closing = None
        search = opening.end()
        while (candidate := INLINE_TICKS.search(masked, search)) is not None:
            if len(candidate[0]) == len(opening[0]):
                closing = candidate
                break
            search = candidate.end()
        if closing is None:
            cursor = opening.end()
            continue
        for index in range(opening.start(), closing.end()):
            if chars[index] not in "\r\n":
                chars[index] = " "
        cursor = closing.end()
    return "".join(chars)


def _plain_heading(title: str) -> str:
    title = re.sub(r"[ \t]+#+[ \t]*$", "", title).strip()
    title = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", title)
    title = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", title)
    title = re.sub(r"<[^>]*>", "", title)
    code_spans: list[str] = []

    def stash_code(match: re.Match) -> str:
        code_spans.append(match[2])
        return f"\x00CODE{len(code_spans) - 1}\x00"

    title = re.sub(r"(`+)(.+?)\1", stash_code, title)
    title = re.sub(r"(?<!\\)\*", "", title)
    # Underscores inside words are literal in Markdown, including foo_bar.
    title = re.sub(r"(?<!\w)_+|_+(?!\w)", "", title)
    for index, code in enumerate(code_spans):
        title = title.replace(f"\x00CODE{index}\x00", code)
    title = re.sub(r"\\([!\"#$%&'()*+,\-./:;<=>?@\[\]\\^_`{|}~])", r"\1", title)
    return html.unescape(title)


def github_slug(title: str) -> str:
    """Return a GitHub-style heading fragment; duplicate suffixes are separate."""
    text = _plain_heading(title).lower()
    text = "".join(
        char
        for char in text
        if char in "-_" or not unicodedata.category(char).startswith(("P", "S", "C"))
    )
    return text.replace(" ", "-")


def headings(markdown: str) -> list[Heading]:
    """Read ATX and single-line Setext headings outside fenced code."""
    lines = markdown.splitlines(keepends=True)
    flags = _fenced_line_flags(lines)
    found: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        if flags[index]:
            continue
        text = line.rstrip("\r\n")
        if match := ATX_HEADING.match(text):
            found.append((index, match[2] or ""))
        elif index and SETEXT_HEADING.fullmatch(text) and not flags[index - 1]:
            previous = lines[index - 1].strip()
            # A thematic break after a blank/list/HTML/heading is not Setext.
            if previous and not re.match(r"(?:[>#<]|[-*+]\s|\d+[.)]\s| {4})", lines[index - 1]):
                found.append((index - 1, previous))

    used: set[str] = set()
    result = []
    for line, title in found:
        base = github_slug(title)
        slug = base
        duplicate = 0
        while slug in used:
            duplicate += 1
            slug = f"{base}-{duplicate}"
        used.add(slug)
        result.append(Heading(line=line, title=_plain_heading(title), slug=slug))
    return result


def add_source_heading_anchors(source: str, translated: str) -> str:
    """Pair headings by order and retain canonical English fragment IDs.

    Fail rather than assigning an English fragment to the wrong section when
    translation has changed the heading count. Existing anchors are preserved.
    """
    originals = headings(source)
    localized = headings(translated)
    if len(originals) != len(localized):
        raise ValueError(
            f"heading count differs: English={len(originals)}, Chinese={len(localized)}"
        )
    lines = translated.splitlines(keepends=True)
    newline = "\r\n" if "\r\n" in translated else "\n"
    additions: dict[int, str] = {}
    for original, localized_heading in zip(originals, localized):
        previous = localized_heading.line - 1
        while previous >= 0 and not lines[previous].strip():
            previous -= 1
        existing = ANCHOR_LINE.match(lines[previous]) if previous >= 0 else None
        if existing and html.unescape(existing[1]) == original.slug:
            continue
        additions[localized_heading.line] = (
            f'<a id="{html.escape(original.slug, quote=True)}"></a>{newline}{newline}'
        )
    return "".join(additions.get(index, "") + line for index, line in enumerate(lines))


def _localized_target(target: str, translated_file: Path, mapping: dict[Path, Path]) -> str:
    # Angle-bracket link destinations may contain spaces.
    angle = target.startswith("<") and target.endswith(">")
    raw = target[1:-1] if angle else target
    parts = urlsplit(raw)
    if parts.scheme or parts.netloc or not parts.path or raw.startswith("/"):
        return target
    path = (translated_file.parent / unquote(parts.path)).resolve()
    localized = mapping.get(path)
    if localized is None:
        # Lesson directory links should open the Chinese explainer directly.
        localized = mapping.get(path / "docs" / "en.md")
    if localized is None:
        localized = mapping.get(path / "README.md")
    if localized is None or not localized.is_file():
        return target
    relative = Path(os.path.relpath(localized, translated_file.parent)).as_posix()
    if parts.path.startswith("./") and not relative.startswith("."):
        relative = "./" + relative
    if "%" in parts.path:
        relative = quote(relative, safe="/-._~")
    if " " in relative and not angle:
        relative = quote(relative, safe="/-._~")
    rewritten = urlunsplit(("", "", relative, parts.query, parts.fragment))
    return f"<{rewritten}>" if angle else rewritten


def _inline_link_targets(masked: str) -> list[tuple[int, int]]:
    """Locate destinations, supporting balanced parentheses and link titles."""
    spans = []
    for match in re.finditer(r"(?<!\\)\]\(", masked):
        # A literal ]( without an opening label is not a Markdown link.
        line_start = masked.rfind("\n", 0, match.start()) + 1
        if "[" not in masked[line_start:match.start()]:
            continue
        start = match.end()
        while start < len(masked) and masked[start] in " \t":
            start += 1
        if start >= len(masked):
            continue
        if masked[start] == "<":
            end = masked.find(">", start + 1)
            if end == -1 or "\n" in masked[start:end]:
                continue
            end += 1
        else:
            depth = 0
            end = start
            while end < len(masked):
                char = masked[end]
                if char == "\\" and end + 1 < len(masked):
                    end += 2
                    continue
                if char == "(":
                    depth += 1
                elif char == ")":
                    if not depth:
                        break
                    depth -= 1
                elif char.isspace() and not depth:
                    break
                end += 1
            if depth:
                continue
        # Only accept the destination when a closing paren or valid title follows.
        tail = masked[end:]
        if re.match(r"[ \t]*(?:(?:\"[^\"\n]*\"|'[^'\n]*'|\([^\n)]*\))[ \t]*)?\)", tail):
            spans.append((start, end))
    return spans


def rewrite_relative_links(markdown: str, translated_file: Path, mapping: dict[Path, Path]) -> str:
    """Localize existing companion destinations outside fences/inline code."""
    translated_file = translated_file.resolve()
    mapping = {source.resolve(): target.resolve() for source, target in mapping.items()}
    masked = _prose_mask(markdown)
    spans = _inline_link_targets(masked)
    spans.extend(match.span(1) for match in REFERENCE_LINK.finditer(masked))
    changes = []
    for start, end in sorted(set(spans)):
        current = markdown[start:end]
        localized = _localized_target(current, translated_file, mapping)
        if localized != current:
            changes.append((start, end, localized))
    for start, end, replacement in reversed(changes):
        markdown = markdown[:start] + replacement + markdown[end:]
    return markdown


def _title(path: Path, fallback: str) -> str:
    if path.is_file():
        found = headings(path.read_text(encoding="utf-8"))
        if found and found[0].title:
            return found[0].title.replace("[", "\\[").replace("]", "\\]")
    return fallback


def build_index(root: Path = ROOT, sources: list[Path] | None = None) -> str:
    """Render phase/lesson navigation; counts always come from source scanning."""
    root = root.resolve()
    phases = root / "phases"
    sources = source_markdown_files(root) if sources is None else sources
    lessons = sorted(path for path in sources if path.name == "en.md" and path.parent.name == "docs")
    phase_dirs = sorted(path for path in phases.iterdir() if path.is_dir() and PHASE_RE.match(path.name))
    existing = sum(companion_path(path).is_file() for path in sources)
    lines = [
        "# 中文教程索引",
        "",
        "> 本目录中的中文版是机器辅助翻译稿，适合辅助学习；英文原文是内容依据。译文可能仍有术语或表述错误，遇到疑问请对照英文。代码、命令、公式和技术名称保留原样。",
        "",
        f"共 **{len(phase_dirs)} 个阶段**、**{len(lessons)} 篇主教程**、**{len(sources)} 份 Markdown 中文对应文件**；当前已有 **{existing}/{len(sources)}** 份。",
        "",
        "命名：主教程 `docs/en.md` 对应同目录 `docs/zh.md`；其他 `name.md` 对应 `name.zh.md`，例如 `README.zh.md`、`mission.zh.md`。英文文件保留。中文文件保留英文标题锚点，并在已有中文对应文件时链接到中文版本。",
        "",
        "本索引按阶段列出全部主教程；练习说明、README 与 outputs 中的中文文件位于各自原文旁。",
    ]
    for phase in phase_dirs:
        phase_title = _title(companion_path(phase / "README.md"), phase.name)
        lines.extend(["", f"## {phase_title}", ""])
        phase_readme = companion_path(phase / "README.md")
        if phase_readme.is_file():
            lines.extend([f"[阶段说明]({phase_readme.relative_to(phases).as_posix()})", ""])
        for source in lessons:
            if source.relative_to(phases).parts[0] != phase.name:
                continue
            translated = companion_path(source)
            title = _title(translated, _title(source, source.parent.parent.name))
            lesson_number = source.parent.parent.name.split("-", 1)[0]
            english_link = source.relative_to(phases).as_posix()
            if translated.is_file():
                chinese_link = translated.relative_to(phases).as_posix()
                lines.append(f"- {lesson_number} · [{title}]({chinese_link}) · [English]({english_link})")
            else:
                lines.append(f"- {lesson_number} · {title}（中文待生成）· [English]({english_link})")
    return "\n".join(lines) + "\n"


def run(root: Path = ROOT, check_only: bool = False) -> dict:
    """Apply/check navigation; return a compact, JSON-serializable report."""
    root = root.resolve()
    sources = source_markdown_files(root)
    mapping = {source: companion_path(source) for source in sources if companion_path(source).is_file()}
    report: dict = {
        "source_files": len(sources),
        "translated_files": len(mapping),
        "missing_files": [str(source.relative_to(root)) for source in sources if source not in mapping],
        "changed_files": [],
        "errors": [],
        "index": str(Path("phases") / INDEX_NAME),
        "check_only": check_only,
    }
    for source, translated in mapping.items():
        before = translated.read_text(encoding="utf-8")
        try:
            after = add_source_heading_anchors(source.read_text(encoding="utf-8"), before)
            after = rewrite_relative_links(after, translated, mapping)
        except ValueError as exc:
            report["errors"].append({"file": str(translated.relative_to(root)), "error": str(exc)})
            continue
        if after != before:
            report["changed_files"].append(str(translated.relative_to(root)))
            if not check_only:
                translated.write_text(after, encoding="utf-8")

    index_path = root / "phases" / INDEX_NAME
    rendered = build_index(root, sources)
    index_changed = not index_path.is_file() or index_path.read_text(encoding="utf-8") != rendered
    report["index_changed"] = index_changed
    if index_changed and not check_only:
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text(rendered, encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="course repository root")
    parser.add_argument("--check-only", action="store_true", help="report only; write no files")
    parser.add_argument("--json", action="store_true", help="print the full machine-readable report")
    args = parser.parse_args(argv)
    if not (args.root / "phases").is_dir():
        parser.error(f"phases directory does not exist under {args.root}")
    report = run(args.root, check_only=args.check_only)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        operation = "pending" if args.check_only else "updated"
        print(f"Chinese companions: {report['translated_files']}/{report['source_files']}")
        print(f"Navigation files {operation}: {len(report['changed_files'])}")
        print(f"Index {operation}: {report['index_changed']} ({report['index']})")
        print(f"Missing companions: {len(report['missing_files'])}; errors: {len(report['errors'])}")
        for item in report["errors"]:
            print(f"ERROR {item['file']}: {item['error']}")
    incomplete = bool(report["missing_files"] or report["errors"])
    pending = args.check_only and bool(report["changed_files"] or report["index_changed"])
    return 1 if incomplete or pending else 0


if __name__ == "__main__":
    raise SystemExit(main())
