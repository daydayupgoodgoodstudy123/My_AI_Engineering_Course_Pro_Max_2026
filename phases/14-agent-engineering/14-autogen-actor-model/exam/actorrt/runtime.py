"""A stdlib actor runtime modeled on AutoGen v0.4 Core.

Actors have private state and an inbox. Messages are the only interaction: two actors never share
memory. The runtime decouples delivery from handling, so a handler that raises is caught, its
message is parked in the dead-letter queue, and every other actor keeps running.
"""
from __future__ import annotations

import copy
from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .journal import Journal


@dataclass
class Message:
    sender: str
    recipient: str
    topic: str
    body: Any
    mid: int = 0


class Actor:
    """Private state and a handler. The runtime keeps the inbox."""

    def __init__(self, name: str) -> None:
        self.name = name

    def receive(self, message: Message, runtime: Runtime) -> None:
        raise NotImplementedError

    def on_stop(self, runtime: Runtime) -> None:
        """Called once, when the runtime stops this actor."""


class Runtime:
    """Routes messages between actors and isolates their failures.

    send() only queues: the message waits in the inbox, and run_until_idle() delivers it later.
    Messages are handled one at a time, in the order they were sent. send() numbers them with
    mids 1, 2, 3, ...

    The recipient gets its own deep copy of the body, taken when send() is called: nothing the
    recipient does to it reaches the sender or any other recipient, and nothing the sender changes
    afterwards reaches the recipient.

    The messages a handler sends are held until it returns, and then queued. If it raises, they
    are dropped, and the message it was handling goes to the dead-letter queue as
    (message, "ExcType: text"). Messages sent by earlier calls that returned are not affected.
    A message for a name that has no actor is dead-lettered as (message, "no actor 'name'").
    """

    def __init__(self, max_messages: int = 100, journal: Journal | None = None) -> None:
        """max_messages caps how many messages one run_until_idle() call takes off the queue.

        With a journal, the runtime records in it every message it queues, every message whose
        handler returned and every dead letter (journal.py says when), and a runtime opened on an
        existing journal starts from what it recovers: the pending messages, the dead letters and
        the next mid.
        """
        self.max_messages = max_messages
        self.journal = journal
        self.actors: dict[str, Actor] = {}
        self.dead_letters: list[tuple[Message, str]] = []
        self._queue: deque[Message] = deque()
        self._next_mid = 1
        self._subscriptions: list[tuple[str, str]] = []
        self._handling = False

    def register(self, actor: Actor) -> None:
        """Start a top-level actor. Names follow the rules of spawn()."""
        if actor.name in self.actors:
            raise ValueError(f"the name {actor.name!r} is taken")
        self.actors[actor.name] = actor

    def subscribe(self, topic: str, name: str) -> None:
        """Deliver what is published on topic to the actor called name.

        Subscribing twice is the same as subscribing once. Subscribers hear a topic in the order
        they first subscribed to it.
        """
        if (topic, name) not in self._subscriptions:
            self._subscriptions.append((topic, name))

    def send(self, sender: str, recipient: str, topic: str, body: Any) -> int:
        """Queue a message and return its mid."""
        message = Message(sender, recipient, topic, copy.deepcopy(body), self._next_mid)
        self._next_mid += 1
        actor = self.actors.get(recipient)
        if self._handling and actor is not None:
            actor.receive(message, self)
        else:
            self._queue.append(message)
        return message.mid

    def publish(self, sender: str, topic: str, body: Any) -> list[int]:
        """Send body to every subscriber of topic, one message each, and return their mids.

        A topic nobody subscribes to swallows the message: nothing is queued or dead-lettered.
        """
        return [self.send(sender, name, topic, body) for t, name in self._subscriptions if t == topic]

    def pending(self) -> list[Message]:
        """The queued messages, in the order they will be handled."""
        return list(self._queue)

    def run_until_idle(self, max_messages: int | None = None) -> bool:
        """Handle queued messages until none are left. Return True if the queue ran dry, False if
        the call stopped at max_messages (default: the runtime's) with messages still queued.

        Every message taken off the queue counts, dead-lettered or not.
        """
        limit = self.max_messages if max_messages is None else max_messages
        handled = 0
        while self._queue:
            if handled == limit:
                return False
            message = self._queue.popleft()
            handled += 1
            actor = self.actors.get(message.recipient)
            if actor is None:
                self.dead_letters.append((message, f"no actor {message.recipient!r}"))
                continue
            self._handling = True
            try:
                actor.receive(message, self)
            except Exception as e:
                self.dead_letters.append((message, f"{type(e).__name__}: {e}"))
            finally:
                self._handling = False
        return True

    def spawn(self, parent: str, actor: Actor) -> None:
        """Start actor as a child of parent, a live actor. A handler spawns under its own name.

        Names are unique for the life of the runtime: a name that is in use, or that belonged to
        an actor that has stopped, raises ValueError, and so does a parent that is unknown or
        stopped.
        """
        raise NotImplementedError

    def stop(self, name: str) -> list[str]:
        """Stop name and every actor below it, and return the names in the order they stopped.

        Children stop before their parent, the most recently spawned child first, and each actor's
        on_stop() runs as it stops. Actors that have already stopped are skipped. A message for a
        stopped actor, queued before the stop or sent after it, is dead-lettered as
        (message, "stopped") when its turn comes. An unknown name raises KeyError.
        """
        raise NotImplementedError

    def tree(self) -> dict[str, dict]:
        """The live actors as nested dicts, {name: {child: {...}}}: top-level actors in the order
        they were registered, children in the order they were spawned."""
        raise NotImplementedError
