"""Render a resumable progress view from the JSON plan and live events."""
from collections.abc import AsyncIterator
from .model import WorkItem, Event
from .resume import resume_state


def _lines(items: list[WorkItem], state: dict) -> dict[str, str]:
    return {item.id: (f"- [x] {item.id} — proof: {item.proof} (exit 0)\n" if item.id in state["complete"]
                      else f"- [ ] {item.id} — blocked by {state['blocked'][item.id]}\n") for item in items}


def _changes(previous: dict[str, str], current: dict[str, str]) -> dict[str, str]:
    """Provided complete-content comparison; preserve current mapping order.

    The caller chooses output order and must finish this event before pulling
    the next one. Unchanged rows are omitted here, not in the event renderer.
    """
    return {item_id: line for item_id, line in current.items() if line != previous[item_id]}


async def progress_lines(items: list[WorkItem], existing: list[Event],
                         incoming: AsyncIterator[Event]) -> AsyncIterator[str]:
    """Emit changed Markdown checklist lines immediately after each incoming event.

    Plan/progress are the source of truth. Existing history initializes the view
    without re-emitting it. Use the provided _changes for content comparison.
    If one event changes several lines, emit by item id.
    Never pull another event before yielding all lines for the current event.
    Private line syntax is given by _lines; no Markdown escaping is required for
    the test ids/commands. Cancelling the consumer does not consume future input.
    """
    history = list(existing)
    previous = _lines(items, resume_state(items, history))
    async for event in incoming:
        history.append(event)
        current = _lines(items, resume_state(items, history))
        changed = _changes(previous, current)
        for item_id in sorted(changed):
            yield changed[item_id]
        previous = current
