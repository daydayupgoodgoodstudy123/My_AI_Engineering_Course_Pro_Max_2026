"""Bounded selector input retains complete recent utterances in original order."""
from .support import render_message
def recent_selector_context(history,window):
    """Return the formatted last window messages, preserving every selected content field."""
    return tuple(render_message(m)for m in history[-window:])if window else()
