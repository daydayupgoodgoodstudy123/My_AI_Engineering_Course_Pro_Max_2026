"""The run loop: guardrails, model calls, tool calls and handoffs, with a span for every step."""
from __future__ import annotations

from dataclasses import dataclass, field

from .agents import (
    Agent,
    FunctionTool,
    InputGuardrailTripwireTriggered,
    MaxTurnsExceeded,
    ModelRequest,
    OutputGuardrailTripwireTriggered,
    ToolGuardrailTripwireTriggered,
)
from .items import AssistantMessage, HandoffItem, Item, ToolItem, UserMessage
from .nesting import nest_handoff_history
from .tracing import Span, Trace, Tracing, preview


@dataclass
class RunResult:
    final_output: str
    last_agent: Agent
    new_items: list[Item]
    trace: Trace


@dataclass
class _State:
    view: list[Item]
    request: UserMessage
    new_items: list[Item] = field(default_factory=list)
    turns: int = 0

    def add(self, item: Item) -> None:
        self.view.append(item)
        self.new_items.append(item)


class Runner:
    """Runs agents the way the Agents SDK does, with each agent's model as a plain function.

    max_handoffs caps the handoffs of one run and max_turns its model calls. With
    nest_handoff_history, the agent a run hands off to reads nest_handoff_history(conversation)
    instead of a copy of the conversation.
    """

    def __init__(
        self,
        tracing: Tracing | None = None,
        *,
        max_handoffs: int = 3,
        max_turns: int = 10,
        nest_handoff_history: bool = False,
    ) -> None:
        self.tracing = tracing if tracing is not None else Tracing()
        self.max_handoffs = max_handoffs
        self.max_turns = max_turns
        self.nest_handoff_history = nest_handoff_history

    def run(self, agent: Agent, user_input: str, session=None) -> RunResult:
        """Run one user message, starting at agent, until some agent gives the final answer.

        - agent's input guardrails check user_input before any model call. A refusal raises
          InputGuardrailTripwireTriggered.
        - With a session, the conversation starts with session.get_items(), and the run's new items
          go to session.add_items() once the run has succeeded. A run that raises adds nothing.
        - On each turn the current agent's model reads the conversation and either answers or calls
          one tool. A call to transfer_to_<name> is a handoff: the agent called name takes over and
          reads the whole conversation so far, the handoff included.
        - A run makes at most max_handoffs handoffs; asking for one more raises HandoffLimitExceeded.
          Tool calls are not handoffs and do not count.
        - The output guardrails of the agent that gives the final answer check it. A refusal raises
          OutputGuardrailTripwireTriggered.
        - Every step is a span of the run's trace: guardrail, agent, generation, tool and handoff
          spans under one run span.
        """
        trace = self.tracing.new_trace()
        with trace.span("run", "run", agent=agent.name) as root:
            for guard in agent.input_guardrails:
                self._check(trace, root, "input", guard, user_input, InputGuardrailTripwireTriggered)
            history = list(session.get_items()) if session is not None else []
            request = UserMessage(user_input)
            state = _State(history, request)
            state.add(request)
            current, final = agent, ""
            for _ in range(self.max_handoffs + 1):
                with trace.span("agent", current.name, root, tools=current.tool_names()) as span:
                    outcome = self._turns(trace, span, current, state)
                if isinstance(outcome, str):
                    final = outcome
                    break
                current = outcome
            for guard in agent.output_guardrails:
                self._check(trace, root, "output", guard, final, OutputGuardrailTripwireTriggered)
            root.attributes["last_agent"] = current.name
        if session is not None:
            session.add_items(state.new_items)
        return RunResult(final, current, state.new_items, trace)

    def _turns(self, trace: Trace, span: Span, agent: Agent, state: _State) -> str | Agent:
        """Call agent's model until it answers (return the answer) or hands off (return the target)."""
        while True:
            if state.turns == self.max_turns:
                raise MaxTurnsExceeded(f"{self.max_turns} model calls without a final answer")
            state.turns += 1
            request = ModelRequest(agent.instructions, list(state.view), agent.tool_names())
            with trace.span("generation", agent.name, span) as generation:
                reply = agent.model(request)
                if "text" in reply:
                    generation.attributes["output"] = preview(reply["text"])
                else:
                    generation.attributes["tool_call"] = reply["tool"]
            if "text" in reply:
                state.add(AssistantMessage(agent.name, reply["text"]))
                return reply["text"]
            name, args = reply["tool"], reply.get("args", {})
            handoff = agent.handoff_for(name)
            if handoff is not None:
                target = handoff.target
                with trace.span("handoff", name, span, **{"from": agent.name, "to": target.name}):
                    state.add(HandoffItem(agent.name, target.name))
                    if self.nest_handoff_history:
                        state.view = nest_handoff_history(state.view)
                    else:
                        state.view = [state.request]
                return target
            output = self._call_tool(trace, span, agent.function_tool(name), args)
            state.add(ToolItem(agent.name, name, args, output))

    def _call_tool(self, trace: Trace, parent: Span, tool: FunctionTool, args: dict) -> str:
        """Run a function tool once its guardrails pass, and return the text the model reads:
        a string result as it is, any other result as JSON."""
        with trace.span("tool", tool.name, parent, args=args) as span:
            for guard in tool.guardrails:
                with trace.span("guardrail", guard.name, span, stage="tool") as check:
                    ok, reason = guard.check(tool.name, args)
                    check.attributes.update(passed=ok, reason=reason)
                if not ok:
                    raise ToolGuardrailTripwireTriggered(guard.name, reason)
            result = tool.fn(**args)
            span.attributes["result"] = preview(result)
        return result

    def _check(self, trace: Trace, parent: Span, stage: str, guard, text: str, error: type) -> None:
        with trace.span("guardrail", guard.name, parent, stage=stage) as span:
            ok, reason = guard.check(text)
            span.attributes.update(passed=ok, reason=reason)
        if not ok:
            raise error(guard.name, reason)
