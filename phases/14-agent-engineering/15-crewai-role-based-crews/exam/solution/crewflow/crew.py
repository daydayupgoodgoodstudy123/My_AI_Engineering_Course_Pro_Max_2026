"""Agents, tasks and the sequential process: CrewAI's surface, with scripted models behind the agents."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .memory import Memory


@dataclass
class Agent:
    """role + goal + backstory, and fn, the model behind the agent.

    fn gets the task's input and returns the task's output: text, or a dict for a task
    with a structured result (the lesson's output_pydantic=Brief).
    """

    role: str
    goal: str
    backstory: str
    fn: Callable[[Any], Any]


@dataclass
class Task:
    """A unit of work, owned by one agent.

    expected_output is the task's contract. context lists the upstream tasks whose outputs
    this task reads. persistent marks a task whose output is a fact worth keeping across
    kickoffs; only those go to long-term memory.
    """

    name: str
    description: str
    expected_output: str
    agent: Agent
    context: list[Task] = field(default_factory=list)
    persistent: bool = False


@dataclass
class SequentialCrew:
    """The sequential process: every task runs once, in declaration order."""

    agents: list[Agent]
    tasks: list[Task]
    memory: Memory | None = None

    def kickoff(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Run the tasks and return {task name: output}, in declaration order.

        A task with context reads the outputs of its context tasks, in the order the context
        lists them, joined by a blank line. A task without context reads the previous task's
        output, and the first task reads inputs["topic"]. Context may only name tasks declared
        earlier in this crew; anything else is a ValueError naming that task, raised before
        any agent runs.

        With memory, the run starts with an empty short-term buffer, every task's output goes
        to short-term memory as (role, output), and persistent tasks' outputs go to long-term
        memory as well.
        """
        position = {id(task): i for i, task in enumerate(self.tasks)}
        for i, task in enumerate(self.tasks):
            for upstream in task.context:
                if position.get(id(upstream), i) >= i:
                    raise ValueError(
                        f"task {task.name!r} reads {upstream.name!r}, which does not run before it"
                    )
        if self.memory is not None:
            self.memory.reset_short_term()
        outputs: dict[str, Any] = {}
        by_task: dict[int, Any] = {}
        prior = inputs.get("topic", "")
        for task in self.tasks:
            if task.context:
                agent_input = "\n\n".join(by_task[id(t)] for t in task.context)
            else:
                agent_input = prior
            out = task.agent.fn(agent_input)
            outputs[task.name] = out
            by_task[id(task)] = out
            prior = out
            if self.memory is not None:
                self.memory.write_short_term(task.agent.role, out)
                if task.persistent:
                    self.memory.write_long_term(task.agent.role, out)
        return outputs
