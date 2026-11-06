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
        self._outbox: list[Message] | None = None
        self._subscribers: dict[str, dict[str, None]] = {}
        self._roots: list[str] = []
        self._children: dict[str, list[str]] = {}
        self._stopped: set[str] = set()
        if journal is not None:
            state = journal.recover()
            self._queue.extend(state.pending)
            self.dead_letters.extend(state.dead_letters)
            self._next_mid = state.next_mid

    def register(self, actor: Actor) -> None:
        """Start a top-level actor. Names follow the rules of spawn()."""
        self._start(None, actor)

    def subscribe(self, topic: str, name: str) -> None:
        """Deliver what is published on topic to the actor called name.

        Subscribing twice is the same as subscribing once. Subscribers hear a topic in the order
        they first subscribed to it.
        """
        self._subscribers.setdefault(topic, {})[name] = None

    def send(self, sender: str, recipient: str, topic: str, body: Any) -> int:
        """Queue a message and return its mid."""
        message = Message(sender, recipient, topic, copy.deepcopy(body), self._next_mid)
        self._next_mid += 1
        if self._outbox is not None:
            self._outbox.append(message)
        else:
            self._enqueue(message)
        return message.mid

    def publish(self, sender: str, topic: str, body: Any) -> list[int]:
        """Send body to every subscriber of topic, one message each, and return their mids.

        A topic nobody subscribes to swallows the message: nothing is queued or dead-lettered.
        """
        return [self.send(sender, name, topic, body) for name in self._subscribers.get(topic, ())]

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
            self._deliver(message)
        return True

    def spawn(self, parent: str, actor: Actor) -> None:
        """Start actor as a child of parent, a live actor. A handler spawns under its own name.

        Names are unique for the life of the runtime: a name that is in use, or that belonged to
        an actor that has stopped, raises ValueError, and so does a parent that is unknown or
        stopped.
        """
        if parent not in self.actors or parent in self._stopped:
            raise ValueError(f"no live actor {parent!r} to spawn under")
        self._start(parent, actor)

    def stop(self, name: str) -> list[str]:
        """Stop name and every actor below it, and return the names in the order they stopped.

        Children stop before their parent, the most recently spawned child first, and each actor's
        on_stop() runs as it stops. Actors that have already stopped are skipped. A message for a
        stopped actor, queued before the stop or sent after it, is dead-lettered as
        (message, "stopped") when its turn comes. An unknown name raises KeyError.
        """
        if name not in self.actors:
            raise KeyError(name)
        order: list[str] = []

        def visit(node: str) -> None:
            for child in reversed(self._children[node]):
                visit(child)
            if node not in self._stopped:
                self._stopped.add(node)
                order.append(node)
                self.actors[node].on_stop(self)

        visit(name)
        return order

    def tree(self) -> dict[str, dict]:
        """The live actors as nested dicts, {name: {child: {...}}}: top-level actors in the order
        they were registered, children in the order they were spawned."""

        def build(names: list[str]) -> dict[str, dict]:
            return {n: build(self._children[n]) for n in names if n not in self._stopped}

        return build(self._roots)

    def _start(self, parent: str | None, actor: Actor) -> None:
        if actor.name in self.actors:
            raise ValueError(f"the name {actor.name!r} is taken")
        self.actors[actor.name] = actor
        self._children[actor.name] = []
        if parent is None:
            self._roots.append(actor.name)
        else:
            self._children[parent].append(actor.name)

    def _deliver(self, message: Message) -> None:
        actor = self.actors.get(message.recipient)
        if actor is None:
            self._dead_letter(message, f"no actor {message.recipient!r}")
            return
        if message.recipient in self._stopped:
            self._dead_letter(message, "stopped")
            return
        self._outbox = []
        try:
            actor.receive(message, self)
        except Exception as e:
            self._dead_letter(message, f"{type(e).__name__}: {e}")
            return
        finally:
            sent, self._outbox = self._outbox, None
        for queued in sent:
            self._enqueue(queued)
        if self.journal is not None:
            self.journal.handled(message.mid)

    def _enqueue(self, message: Message) -> None:
        self._queue.append(message)
        if self.journal is not None:
            self.journal.queued(message)

    def _dead_letter(self, message: Message, reason: str) -> None:
        self.dead_letters.append((message, reason))
        if self.journal is not None:
            self.journal.dead(message.mid, reason)
