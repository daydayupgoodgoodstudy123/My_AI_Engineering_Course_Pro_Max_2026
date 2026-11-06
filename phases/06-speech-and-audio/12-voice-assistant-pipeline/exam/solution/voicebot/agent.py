"""The LLM tool loop for one voice turn, and the cleanup that makes its reply speakable."""
from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Awaitable, Callable

from .tools import ToolBox, answer

FALLBACK = "Sorry, I couldn't do that. Please try rephrasing."
STEP_LIMIT = "not run: the turn used up its tool steps"

# llm(messages, tool_specs) returns the next assistant message
LLM = Callable[[list[dict], list[dict]], Awaitable[dict]]

_HEADING = re.compile(r"#{1,6}\s+")
_LIST_ITEM = re.compile(r"(?:[-*+]|\d+[.)])\s+")
_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_CODE = re.compile(r"`([^`]*)`")
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_ITALIC = re.compile(r"\*(\S(?:.*?\S)?)\*")


async def respond(llm: LLM, box: ToolBox, messages: list[dict], max_steps: int = 4) -> str:
    """Run the LLM tool loop for one user turn and return the text to speak.

    messages is the conversation so far, ending with the user's message. Every assistant reply and
    tool result is appended to it, so it stays a valid request for the next turn. The LLM is called
    as await llm(messages, box.specs()) and returns an assistant message. Each of its tool calls is
    dispatched and the results go back to the LLM; the first reply without tool calls ends the turn,
    and its content, made speakable, is the answer.

    The LLM is called at most max_steps times. A failed tool may be retried once: when the same tool
    fails a second time, the turn ends. Tool calls in the max_steps-th reply are not run; each gets
    an error result instead. A turn that ends without an answer says FALLBACK, and FALLBACK is
    appended as the assistant's reply.
    """
    failures: Counter[str] = Counter()
    for step in range(max_steps):
        reply = await llm(messages, box.specs())
        messages.append(reply)
        calls = reply.get("tool_calls") or []
        if not calls:
            return speakable(reply.get("content") or "")
        if step == max_steps - 1:
            messages.extend(answer(call, error=STEP_LIMIT) for call in calls)
            break
        for call in calls:
            result = await box.dispatch(call)
            messages.append(result)
            if not json.loads(result["content"])["ok"]:
                failures[call["name"]] += 1
        if max(failures.values(), default=0) >= 2:
            break
    messages.append({"role": "assistant", "content": FALLBACK})
    return FALLBACK


def speakable(text: str) -> str:
    """Turn an LLM reply into plain text for TTS.

    Markdown is dropped: **bold**, *italic* and `code` keep their text, a [link](url) is read as its
    text, and heading and list markers are removed. A heading or list item becomes a sentence of its
    own, with a period added when it has no closing punctuation. Line breaks and runs of whitespace
    become single spaces. Text that is not markup stays: "-5°C" keeps its minus sign.
    """
    sentences = []
    for line in text.splitlines():
        line = line.strip()
        marker = _HEADING.match(line) or _LIST_ITEM.match(line)
        if marker:
            line = line[marker.end():]
        line = _LINK.sub(r"\1", line)
        line = _CODE.sub(r"\1", line)
        line = _BOLD.sub(r"\1", line)
        line = _ITALIC.sub(r"\1", line)
        line = " ".join(line.split())
        if not line:
            continue
        if marker and line[-1] not in ".!?:;":
            line += "."
        sentences.append(line)
    return " ".join(sentences)
