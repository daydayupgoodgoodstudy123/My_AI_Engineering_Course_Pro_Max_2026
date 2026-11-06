"""Cut streaming LLM text into chunks the synthesizer can start on early."""
from __future__ import annotations

from collections.abc import AsyncIterator


async def speech_events(deltas: AsyncIterator[str], min_chars: int = 20) -> AsyncIterator[str]:
    """Send each speakable chunk of the text as soon as it is complete.

    Deltas are pieces of text of any size, as an LLM streams them. A chunk ends after
    . ? or ! followed by whitespace, or after , ; or : followed by whitespace once the
    chunk is at least min_chars long. A period right after an abbreviation (Dr.) does not
    end a chunk. What is left when the stream ends is the last chunk. Chunks are sent
    stripped, and an empty chunk is not sent.

    Each chunk is one server-sent event: "data: " + JSON {"seq": n, "text": chunk},
    followed by a blank line. seq counts from 0.
    """
    raise NotImplementedError
