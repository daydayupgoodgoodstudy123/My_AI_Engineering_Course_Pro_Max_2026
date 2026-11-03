"""Client-side completion/complete: debounce keystrokes, drop stale answers, bound what is shown."""
from __future__ import annotations

import json
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
        self._pending: tuple[str, int] | None = None  # (value, time of its keystroke)
        self._latest: tuple[int, str] | None = None  # (id, value) of the newest request sent
        self._shown: dict[str, Any] = {"value": None, "values": [], "total": None, "hasMore": False}

    def type(self, value: str) -> None:
        """A keystroke: the argument now holds value. It restarts the idle timer."""
        self._pending = (value, self._clock())

    def poll(self) -> None:
        """The timer. Call it whenever the clock moves.

        Once the value has stayed unchanged for idle_ms (clock() - time of the last keystroke
        >= idle_ms), send one completion/complete request for it: make_request with the next
        id, params {"ref": ref, "argument": {"name": argument, "value": value}}. One request
        per pause.
        """
        if self._pending is None:
            return
        value, typed_at = self._pending
        if self._clock() - typed_at < self.idle_ms:
            return
        request_id = next(self._ids)
        params = {"ref": self.ref, "argument": {"name": self.argument, "value": value}}
        self._send(json.dumps(make_request(request_id, "completion/complete", params)))
        self._latest = (request_id, value)
        self._pending = None

    def receive(self, frame: str) -> None:
        """One response frame (a JSON text) from the server.

        Only the answer to the newest request sent counts. An answer to an older request,
        whenever it arrives, and an answer to an id this box never sent are dropped. An error
        answer to the newest request leaves no suggestions for its value: values empty, total
        None, hasMore false.
        """
        message = json.loads(frame)
        if self._latest is None or message.get("id") != self._latest[0]:
            return
        value = self._latest[1]
        if "error" in message:
            self._shown = {"value": value, "values": [], "total": None, "hasMore": False}
            return
        completion = message["result"]["completion"]
        values = list(completion["values"])
        self._shown = {
            "value": value,
            "values": values[:MAX_VALUES],
            "total": completion.get("total"),
            "hasMore": completion.get("hasMore") is True or len(values) > MAX_VALUES,
        }

    def suggestions(self) -> dict[str, Any]:
        """What the box shows: {"value", "values", "total", "hasMore"}.

        value is the argument value the suggestions answer (None before any answer). values
        holds at most MAX_VALUES suggestions, in the server's order. total is the server's
        total when it reports one, else None. hasMore is true when the server says so or when
        the box cut values down to MAX_VALUES.
        """
        return {**self._shown, "values": list(self._shown["values"])}
