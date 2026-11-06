"""The hierarchical process: a manager picks the next specialist every round."""
from __future__ import annotations

from dataclasses import dataclass

from .crew import Agent


def paragraphs(text: str) -> int:
    r"""How many paragraphs text has: runs of non-blank lines, separated by blank lines.

    A blank line is empty or holds only whitespace. Lines end in "\n" or "\r\n".
    """
    count = 0
    inside = False
    for line in text.split("\n"):
        if line.strip():
            if not inside:
                count += 1
            inside = True
        else:
            inside = False
    return count


@dataclass(frozen=True)
class Specialist:
    """A specialist the manager can route to: its agent, the task it owns, and how many
    paragraphs its input must have before it may run."""

    agent: Agent
    task: str
    min_paragraphs: int = 0


@dataclass(frozen=True)
class ManagerView:
    """What the manager is sent in one round."""

    tasks: tuple[str, ...]  # "role: task" for every specialist, in pipeline order
    outputs: tuple[tuple[str, str], ...]  # (role, output) of every specialist call so far, oldest first
    refusals: tuple[str, ...]  # why earlier picks were refused, oldest first


@dataclass(frozen=True)
class Round:
    pick: str  # what the manager answered
    ran: str | None  # the specialist that ran in this round; None when the manager said "done"
    refused: str | None  # why the pick was refused, or None


@dataclass(frozen=True)
class ManagerCall:
    """The token tax of one manager call."""

    tasks: int  # tasks in the list the manager was sent
    carried: int  # characters of earlier specialist outputs the manager was sent


@dataclass
class HierarchyRun:
    rounds: list[Round]
    outputs: dict[str, str]  # every specialist's latest output
    stop: str  # "done", or "max_steps" when the rounds ran out first
    manager_calls: list[ManagerCall]
    specialist_calls: int


@dataclass
class HierarchicalCrew:
    """The hierarchical process. manager.fn gets a ManagerView and answers a role, or "done"."""

    manager: Agent
    specialists: list[Specialist]  # in pipeline order
    max_steps: int = 10

    def kickoff(self, topic: str) -> HierarchyRun:
        """Route the specialists until the manager says "done" or max_steps rounds have run.

        The specialists form a pipeline: the first reads the topic, and every other one reads the
        latest output of the specialist before it. Every round starts with one manager call, which
        sends the whole task list and every specialist output so far. The manager answers the role
        of a specialist, or "done"; any other answer is a ValueError naming it.

        A pick is refused when its input is not ready: the specialist before it has not run yet,
        or that specialist's latest output has fewer paragraphs than the pick's min_paragraphs.
        The round then runs the nearest specialist upstream of the pick whose own input is ready,
        so a writer whose draft was too short writes it again from the researcher's output.
        A refused round counts as a round. Its reason reads "<pick> needs <upstream>'s output
        first" or "<pick> needs <n> paragraphs from <upstream>, got <k>".
        """
        roles = [s.agent.role for s in self.specialists]
        tasks = tuple(f"{s.agent.role}: {s.task}" for s in self.specialists)
        history: list[tuple[str, str]] = []
        latest: dict[str, str] = {}
        refusals: list[str] = []
        rounds: list[Round] = []
        calls: list[ManagerCall] = []
        specialist_calls = 0

        def blocker(i: int) -> str | None:
            """Why specialist i cannot run yet, or None when its input is ready."""
            if i == 0:
                return None
            upstream = roles[i - 1]
            if upstream not in latest:
                return f"{roles[i]} needs {upstream}'s output first"
            needed = self.specialists[i].min_paragraphs
            got = paragraphs(latest[upstream])
            if got < needed:
                return f"{roles[i]} needs {needed} paragraphs from {upstream}, got {got}"
            return None

        for _ in range(self.max_steps):
            calls.append(ManagerCall(len(tasks), sum(len(out) for _, out in history)))
            pick = self.manager.fn(ManagerView(tasks, tuple(history), tuple(refusals)))
            if pick == "done":
                rounds.append(Round(pick, None, None))
                return HierarchyRun(rounds, latest, "done", calls, specialist_calls)
            if pick not in roles:
                raise ValueError(f"the manager picked {pick!r}, which is not a specialist")
            i = roles.index(pick)
            refused = blocker(i)
            if refused is not None:
                refusals.append(refused)
                i -= 1
                while blocker(i) is not None:
                    i -= 1
            specialist = self.specialists[i]
            out = specialist.agent.fn(topic if i == 0 else latest[roles[i - 1]])
            specialist_calls += 1
            history.append((roles[i], out))
            latest[roles[i]] = out
            rounds.append(Round(pick, roles[i], refused))
        return HierarchyRun(rounds, latest, "max_steps", calls, specialist_calls)
