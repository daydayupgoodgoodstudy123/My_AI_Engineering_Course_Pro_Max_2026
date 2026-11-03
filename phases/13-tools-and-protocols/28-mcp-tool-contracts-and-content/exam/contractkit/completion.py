"""Client-side completion/complete: debounce keystrokes, drop stale answers, bound what is shown."""
from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

from .wire import make_request

MAX_VALUES = 100


class CompletionBox:
    """Suggestions for one prompt argument while the user types.

    send writes one JSON-RPC request frame (a JSON text) to the server. clock returns the
    current time in milliseconds. ids is the connection's request-id counter; every request
    takes the next id from it.
    """

    def __init__(
        self,
        send: Callable[[str], None],
        clock: Callable[[], int],
        ids: Iterator[int],
        *,
        ref: dict[str, Any],
        argument: str,
        idle_ms: int = 200,
    ) -> None:
        self._send = send
        self._clock = clock
        self._ids = ids
        self.ref = ref
        self.argument = argument
        self.idle_ms = idle_ms

    def type(self, value: str) -> None:
        """A keystroke: the argument now holds value. It restarts the idle timer."""
        raise NotImplementedError

    def poll(self) -> None:
        """The timer. Call it whenever the clock moves.

        Once the value has stayed unchanged for idle_ms (clock() - time of the last keystroke
        >= idle_ms), send one completion/complete request for it: make_request with the next
        id, params {"ref": ref, "argument": {"name": argument, "value": value}}. One request
        per pause.
        """
        raise NotImplementedError

    def receive(self, frame: str) -> None:
        """One response frame (a JSON text) from the server.

        Only the answer to the newest request sent counts. An answer to an older request,
        whenever it arrives, and an answer to an id this box never sent are dropped. An error
        answer to the newest request leaves no suggestions for its value: values empty, total
        None, hasMore false.
        """
        raise NotImplementedError

    def suggestions(self) -> dict[str, Any]:
        """What the box shows: {"value", "values", "total", "hasMore"}.

        value is the argument value the suggestions answer (None before any answer). values
        holds at most MAX_VALUES suggestions, in the server's order. total is the server's
        total when it reports one, else None. hasMore is true when the server says so or when
        the box cut values down to MAX_VALUES.
        """
        raise NotImplementedError
