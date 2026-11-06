"""Keep the main context within budget while messages stream in: page out, then summarize."""
from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable

from .context import MainContext, Message

Summarize = Callable[[str, list[Message]], Awaitable[str]]


async def page_stream(
    arrivals: AsyncIterator[tuple[str, str]],
    ctx: MainContext,
    summarize: Summarize,
    *,
    warn_tokens: int,
) -> AsyncIterator[str]:
    """Add each arriving (role, text) message to ctx, paging out and summarizing as needed.

    For every message, in this order:
      1. push it into the context;
      2. if it took the context from below warn_tokens to warn_tokens or more, report
         memory_pressure. This is the agent's interrupt: nothing has been paged out yet, so the
         agent can still save what is about to leave;
      3. while the context is over max_tokens and older messages remain: page out the oldest
         messages until it fits (MainContext.evict) and report page_out, then fold them into
         the running summary with `await summarize(ctx.summary, paged)`, store the result in
         ctx.summary and report summary. The summary counts toward max_tokens, so a longer
         summary can page out more messages.

    Each report is one JSON object followed by "\\n", yielded as soon as it happens:
      {"event": "memory_pressure", "turn": <turn of the message>, "tokens": <ctx.tokens()>}
      {"event": "page_out", "turns": [<turns paged out, oldest first>], "freed": <their tokens>}
      {"event": "summary", "tokens": <approx_tokens(summary)>, "text": <summary>}
    """
    raise NotImplementedError
