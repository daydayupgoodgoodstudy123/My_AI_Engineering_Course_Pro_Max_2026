"""Episodes, execution-based judging and the suite runner."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Union

from .app import ShoppingApp

ACTIONS = ("list_items", "add_to_cart", "remove_from_cart", "set_price", "checkout")


@dataclass(frozen=True)
class Action:
    """One thing an agent does to the app: an action name and its keyword arguments."""

    name: str
    args: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Step:
    """An action the agent took, and what the app answered."""

    action: Action
    result: Any


@dataclass(frozen=True)
class Note:
    """Scratchpad text from the agent (a thought, a revised plan). It does nothing to the app."""

    text: str


Trace = list[Union[Step, Note]]


class Env:
    """What an agent gets: the app's actions, and a place to write notes. Everything is traced."""

    def __init__(self, app: ShoppingApp) -> None:
        self.app = app
        self.trace: Trace = []

    def act(self, name: str, **args: Any) -> Any:
        if name in ACTIONS:
            result = getattr(self.app, name)(**args)
        else:
            result = f"error: unknown action {name}"
        self.trace.append(Step(Action(name, dict(args)), result))
        return result

    def note(self, text: str) -> None:
        self.trace.append(Note(text))


@dataclass
class Task:
    """A benchmark task.

    want is the one order the final state must hold; gold is the shortest known trajectory
    (the OSWorld-Human idea); agent is called with an Env.
    """

    tid: str
    want: dict[str, int]
    gold: list[Action]
    agent: Callable[[Env], Any]


@dataclass(frozen=True)
class Result:
    tid: str
    success: bool
    steps: int
    gold_steps: int
    orders: list[dict[str, Any]] = field(default_factory=list)  # orders placed during the episode


def judge(app: ShoppingApp, want: dict[str, int]) -> bool:
    """Execution-based check of the final state, not of the trajectory.

    The episode succeeds when exactly one order was placed during it (orders already in the
    pinned snapshot do not count) and that order holds exactly want: those skus, at those
    quantities, and nothing else.
    """
    placed = app.orders[app.pinned_orders :]
    return len(placed) == 1 and placed[0]["items"] == want


def count_steps(trace: Trace) -> int:
    """The steps the agent took: every action, including one the app answered with an error.

    Notes are not steps.
    """
    return sum(isinstance(entry, Step) for entry in trace)


def episode_result(task: Task, env: Env) -> Result:
    """Score a finished episode.

    success comes from the app's final state alone, whatever path the agent took to get
    there. gold only gives gold_steps, the yardstick for steps over gold.
    """
    app = env.app
    return Result(
        task.tid,
        judge(app, task.want),
        count_steps(env.trace),
        len(task.gold),
        app.state()["orders"][app.pinned_orders :],
    )


def run_suite(snapshot: dict[str, Any], tasks: list[Task]) -> list[Result]:
    """Run every task's agent once, in order, on one app that is reset before each episode."""
    app = ShoppingApp(snapshot)
    results = []
    for task in tasks:
        app.reset()
        env = Env(app)
        task.agent(env)
        results.append(episode_result(task, env))
    return results
