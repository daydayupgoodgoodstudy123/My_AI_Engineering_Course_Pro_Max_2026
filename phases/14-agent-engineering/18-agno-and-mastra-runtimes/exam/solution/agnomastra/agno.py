"""Agno-shaped request path: a stateless handler, a fresh agent per request, state in a session store."""
from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, str]
    fn: Callable[..., str]


@dataclass(frozen=True)
class AgentSpec:
    """What every agent of an app starts from. instructions become the first lines of its memory."""

    name: str
    instructions: list[str] = field(default_factory=list)


class SessionStore:
    """Session state: session id -> turns. In memory here; a database in production."""

    def __init__(self) -> None:
        self._turns: dict[str, list[str]] = {}

    def append(self, session_id: str, turn: str) -> None:
        self._turns.setdefault(session_id, []).append(turn)

    def history(self, session_id: str) -> list[str]:
        return list(self._turns.get(session_id, []))


class Agent:
    """One request's agent.

    memory starts as a copy of spec.instructions and belongs to this agent alone.
    tools is the app's shared registry itself: agents read it and never copy or modify it,
    so creating an agent costs the same whether the app has 3 tools or 3,000.
    """

    def __init__(self, spec: AgentSpec, tools: Mapping[str, Tool], model: Callable[[Agent], str]) -> None:
        self.spec = spec
        self.tools = tools
        self.memory = list(spec.instructions)
        self.model = model

    def run(self, history: list[str], prompt: str) -> str:
        """Load the session history, add the prompt, and ask the model (which reads self.memory)."""
        self.memory.extend(history)
        self.memory.append(f"user: {prompt}")
        reply = self.model(self)
        self.memory.append(f"assistant: {reply}")
        return reply


class AgnoApp:
    """The FastAPI-shaped backend.

    The app keeps no conversation state: every request runs on a fresh Agent built from the
    spec and the shared tool registry, and the turns are written to the session store.
    """

    def __init__(
        self,
        spec: AgentSpec,
        tools: Iterable[Tool],
        model: Callable[[Agent], str],
        sessions: SessionStore | None = None,
    ) -> None:
        self.spec = spec
        self.registry = {tool.name: tool for tool in tools}
        self.model = model
        self.sessions = sessions if sessions is not None else SessionStore()

    def handle(self, session_id: str, prompt: str) -> str:
        agent = Agent(self.spec, self.registry, self.model)
        reply = agent.run(self.sessions.history(session_id), prompt)
        self.sessions.append(session_id, f"user: {prompt}")
        self.sessions.append(session_id, f"assistant: {reply}")
        return reply
