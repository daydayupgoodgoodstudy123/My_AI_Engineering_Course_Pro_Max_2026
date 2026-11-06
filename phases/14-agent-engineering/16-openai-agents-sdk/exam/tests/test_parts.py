import dataclasses
import json
import re
import threading
import time
from types import SimpleNamespace

import pytest
from handoffs.agents import (
    Agent,
    BuiltinTool,
    FunctionTool,
    Handoff,
    HandoffLimitExceeded,
    InputGuardrailTripwireTriggered,
    ModelRequest,
    OutputGuardrailTripwireTriggered,
)
from handoffs.graph import HandoffGraph
from handoffs.guardrails import CardNumberGuard, LengthCap, PiiGuard
from handoffs.items import AssistantMessage, HandoffItem, HistorySummary, ToolItem, UserMessage
from handoffs.nesting import nest_handoff_history
from handoffs.processors import BackgroundProcessor, NdjsonSpanWriter
from handoffs.runner import Runner
from handoffs.session import SQLiteSession
from handoffs.tracing import Tracing


class Model:
    """Stands in for an agent's LLM: replies with respond(request) and keeps every request it got."""

    def __init__(self, respond) -> None:
        self.respond = respond
        self.requests: list[ModelRequest] = []

    def __call__(self, request: ModelRequest) -> dict:
        self.requests.append(request)
        return self.respond(request)


def latest_user(conversation) -> str:
    return next(item.text for item in reversed(conversation) if isinstance(item, UserMessage))


def as_json(text):
    """The JSON value in text, or None when text is not a string of JSON."""
    if not isinstance(text, str):
        return None
    try:
        return json.loads(text)
    except ValueError:
        return None


REGIONS = [a + b for a in "ABCDEFGH" for b in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"][:200]


def pii_rules() -> list[tuple[str, str]]:
    """The compliance team's rule file: three ID formats for each of 200 regions."""
    rules = []
    for region in REGIONS:
        code = region.lower()
        rules.append((f"{code}_national_id", rf"{region}-?\d{{3}}-?\d{{3}}-?\d{{3}}(?!\d)"))
        rules.append((f"{code}_tax_id", rf"{region}TX(?:\d{{4}}[ .]?){{2}}(?!\d)"))
        rules.append((f"{code}_passport", rf"{region}P[A-Z](?:\d{{7}}|\d{{9}})(?!\d)"))
    return rules


CUSTOMERS = {
    "jorg@example.com": {"id": 1842, "name": "Jörg Müller", "plan": "pro", "card_on_file": None},
    "ana@example.com": {"id": 2077, "name": "Ana Lima", "plan": "team", "card_on_file": "4111 1111 1111 1111"},
}
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.\w+")


def triage_reply(request: ModelRequest) -> dict:
    last = request.conversation[-1]
    if isinstance(last, UserMessage):
        email = EMAIL.search(last.text)
        if email is None:
            return {"text": "Which email is the account under?"}
        return {"tool": "lookup_customer", "args": {"email": email.group(0)}}
    if "invoice" in latest_user(request.conversation).lower():
        return {"tool": "transfer_to_billing"}
    return {"tool": "transfer_to_support"}


def billing_reply(request: ModelRequest) -> dict:
    lookups = [i for i in request.conversation if isinstance(i, ToolItem) and i.tool == "lookup_customer"]
    customer = as_json(lookups[-1].output) if lookups else None
    if customer is None:
        return {"text": "Which customer is this about?"}
    invoice = re.search(r"invoice (\d+)", latest_user(request.conversation)).group(1)
    if customer["card_on_file"]:
        return {"text": f"Refund for invoice {invoice} goes back to card {customer['card_on_file']}."}
    return {"text": f"Refund for invoice {invoice} is on its way to {customer['name']} (customer {customer['id']})."}


def support_desk() -> SimpleNamespace:
    """triage looks the customer up, then hands invoices to billing and everything else to support."""
    billing = Agent(
        "billing", "Handle refunds and invoices.", Model(billing_reply),
        output_guardrails=[CardNumberGuard(), LengthCap(300)],
    )
    support = Agent(
        "support", "Handle bugs and errors.", Model(lambda request: {"text": "Support will get back to you."}),
        output_guardrails=[LengthCap(300)],
    )
    triage = Agent(
        "triage", "Route the customer to the right specialist.", Model(triage_reply),
        tools=[FunctionTool("lookup_customer", lambda email: CUSTOMERS[email])],
        handoffs=[Handoff(billing), Handoff(support)],
        input_guardrails=[PiiGuard(pii_rules())],
        output_guardrails=[LengthCap(60)],
    )
    return SimpleNamespace(triage=triage, billing=billing, support=support)


class MemorySession:
    """A session kept in a list, so that the runner tests do not depend on Part 2."""

    def __init__(self, items=()) -> None:
        self.items: list = list(items)

    def get_items(self, limit=None) -> list:
        return list(self.items)

    def add_items(self, items) -> None:
        self.items.extend(items)


def answers(text: str) -> Model:
    return Model(lambda request: {"text": text})


def transfers_to(name: str) -> Model:
    return Model(lambda request: {"tool": f"transfer_to_{name}"})


@pytest.mark.skip("Part 1")
def test_runner() -> None:
    """A handoff passes the whole conversation on, the last agent's guardrails check the answer, drift is refused."""
    desk = support_desk()
    runner = Runner()
    earlier = [UserMessage("Hello? Is anyone there?"), AssistantMessage("triage", "Yes, how can I help?")]
    result = runner.run(
        desk.triage, "Hi, I was charged twice for invoice 4711. My account is jorg@example.com.",
        session=MemorySession(earlier),
    )
    assert as_json(result.new_items[1].output) == CUSTOMERS["jorg@example.com"], (
        "a tool result that is not a string reaches the model as JSON"
    )
    assert result.final_output == "Refund for invoice 4711 is on its way to Jörg Müller (customer 1842).", (
        "the agent a run hands off to reads the whole conversation"
    )
    assert desk.billing.model.requests[0].conversation == earlier + result.new_items[:3], (
        "the session's earlier items and the handoff itself included"
    )
    assert result.last_agent is desk.billing
    assert desk.triage.model.requests[0].tools == ["lookup_customer", "transfer_to_billing", "transfer_to_support"], (
        "the model sees each handoff as a transfer_to_<agent> tool"
    )
    with pytest.raises(OutputGuardrailTripwireTriggered) as tripped:
        runner.run(desk.triage, "Please refund invoice 4712 to me, ana@example.com.")
    assert tripped.value.guardrail == "card_numbers", "the last agent's output guardrails check the final answer"

    triage = Agent("triage", "Route the customer.", transfers_to("billing"), output_guardrails=[LengthCap(60)])
    billing = Agent("billing", "Refunds only.", transfers_to("triage"))
    triage.handoffs.append(Handoff(billing))
    billing.handoffs.append(Handoff(triage))
    with pytest.raises(HandoffLimitExceeded):
        Runner(max_handoffs=2).run(triage, "Is this a billing question or a support question?")
    quiet = Agent("triage", "Route the customer.", answers(""), output_guardrails=[LengthCap(60)])
    assert Runner(max_handoffs=2).run(quiet, "ok").final_output == "", "an empty answer is still an answer"

    refunds = Agent("refunds", "Issue refunds.", answers("Refund queued."))
    billing = Agent("billing", "Refunds.", transfers_to("refunds"), handoffs=[Handoff(refunds)])
    triage = Agent("triage", "Route the customer.", transfers_to("billing"), handoffs=[Handoff(billing)])
    result = Runner(max_handoffs=2).run(triage, "Refund invoice 4711, please.")
    assert (result.final_output, result.last_agent) == ("Refund queued.", refunds), "a run may make max_handoffs handoffs"
    with pytest.raises(HandoffLimitExceeded):
        Runner(max_handoffs=1).run(triage, "Refund invoice 4711, please.")

    def look_around(request: ModelRequest) -> dict:
        done = {item.tool for item in request.conversation if isinstance(item, ToolItem)}
        for tool, args in (
            ("lookup_customer", {"email": "jorg@example.com"}),
            ("open_tickets", {"customer": 1842}),
            ("last_contact", {"customer": 1842}),
        ):
            if tool not in done:
                return {"tool": tool, "args": args}
        return {"tool": "transfer_to_support"}

    support = Agent("support", "Handle bugs.", answers("Ticket 77 is with the on-call engineer."))
    triage = Agent(
        "triage", "Route the customer.", Model(look_around),
        tools=[
            FunctionTool("lookup_customer", lambda email: CUSTOMERS[email]),
            FunctionTool("open_tickets", lambda customer: (77,)),
            FunctionTool("last_contact", lambda customer: "2026-10-30 via chat"),
        ],
        handoffs=[Handoff(support)],
    )
    result = Runner(max_handoffs=1).run(triage, "The app crashes when I export. Is anything open for me?")
    assert result.final_output == "Ticket 77 is with the on-call engineer.", "tool calls are not handoffs"
    outputs = [item.output for item in result.new_items if isinstance(item, ToolItem)]
    assert outputs[1] == "[77]", "a tool result that is not a string reaches the model as JSON"
    assert outputs[2] == "2026-10-30 via chat", "a string result reaches the model as it is"

    with pytest.raises(InputGuardrailTripwireTriggered) as tripped:
        runner.run(desk.triage, "Please update my ID to DE-482-913-775, it replaced passport ATPX4821933.")
    assert tripped.value.reason == "matches PII rule at_passport", "the reason names the first rule that matches"
    messages = [f"Hi, order {9000 + i} has not arrived yet. Can you check?" for i in range(120)]
    start = time.perf_counter()
    for message in messages:
        runner.run(desk.triage, message)
    elapsed = time.perf_counter() - start
    assert elapsed < 0.1, "screening 120 messages against 600 PII rules should be quick"


def exact(value):
    """A comparable form that keeps dict key order, tells 1 from 1.0 and True, and names item types."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return (type(value).__name__, [(f.name, exact(getattr(value, f.name))) for f in dataclasses.fields(value)])
    if isinstance(value, dict):
        return ("dict", [(key, exact(item)) for key, item in value.items()])
    if isinstance(value, (list, tuple)):
        return (type(value).__name__, [exact(item) for item in value])
    if isinstance(value, float):
        return ("float", value.hex())
    return (type(value).__name__, value)


SEARCH_ARGS = {
    "email": "jorg@example.com",
    "filters": {"status": ["paid", "refunded"], "since": "2026-10-01"},
    "limit": 10,
    "min_total": 0.1 + 0.2,
    "include_lines": True,
    "currency": None,
    "order_ids": [18446744073709551617, 7],
    "weight_kg": 2.0,
}
THREAD = [
    UserMessage("Hallo! Rechnung 4711 wurde doppelt abgebucht 💳"),
    ToolItem("triage", "search_orders", SEARCH_ARGS, '{"orders": 2, "total": 79.6}\n'),
    HandoffItem("triage", "billing"),
    AssistantMessage("billing", "Die Rückerstattung über 39,80 € ist unterwegs."),
    UserMessage("Danke!"),
    AssistantMessage("triage", "Gern geschehen."),
    UserMessage("Danke!"),
]
ORDERS = {9001: "shipped 2026-10-29", 9002: "waiting for stock"}


def order_reply(request: ModelRequest) -> dict:
    last = request.conversation[-1]
    if isinstance(last, UserMessage):
        order = re.search(r"order (\d+)", last.text)
        if order is None:
            return {"text": "Anything else I can do?"}
        return {"tool": "order_status", "args": {"order": int(order.group(1))}}
    if "refund" in latest_user(request.conversation).lower():
        return {"tool": "transfer_to_billing"}
    return {"text": f"Your order is {last.output}."}


def refund_reply(request: ModelRequest) -> dict:
    order = re.search(r"order (\d+)", latest_user(request.conversation)).group(1)
    return {"text": f"Refund started for order {order}."}


def order_desk() -> SimpleNamespace:
    """triage checks the order, then hands refunds to billing."""
    billing = Agent("billing", "Handle refunds.", Model(refund_reply))
    triage = Agent(
        "triage", "Route the customer.", Model(order_reply),
        tools=[FunctionTool("order_status", lambda order: ORDERS[order])],
        handoffs=[Handoff(billing)],
    )
    return SimpleNamespace(triage=triage, billing=billing)


@pytest.mark.skip("Part 2")
def test_session_store(tmp_path) -> None:
    """Sessions keep every conversation exactly and apart, across a reopen, and the runner continues them."""
    path = str(tmp_path / "sessions.sqlite3")
    jorg = SQLiteSession("jorg@example.com", path)
    obrien = SQLiteSession("o'brien@example.com", path)
    namesake = SQLiteSession("obrien@example.com", path)
    quoted = SQLiteSession('"ann lee"@example.com', path)
    jorg.add_items(THREAD[:4])
    obrien.add_items([UserMessage("Where is my invoice?")])
    namesake.add_items([UserMessage("Please cancel my plan.")])
    quoted.add_items([UserMessage("Is my refund through?")])
    jorg.add_items(THREAD[4:])
    assert exact(jorg.get_items()) == exact(THREAD), "items come back exactly as they were added, oldest first"
    assert jorg.get_items(limit=4) == THREAD[-4:], "a limit keeps the latest items, oldest first"
    assert jorg.get_items(limit=0) == [], "limit=0 asks for no items"
    assert obrien.get_items() == [UserMessage("Where is my invoice?")], "a session only sees its own items"
    assert namesake.get_items() == [UserMessage("Please cancel my plan.")], "a session only sees its own items"
    assert quoted.get_items() == [UserMessage("Is my refund through?")], "a session only sees its own items"
    with pytest.raises(TypeError):
        jorg.add_items([UserMessage("One more thing."), {"role": "user", "content": "raw dict"}])
    assert jorg.get_items() == THREAD, "a failed add_items stores none of its items"
    jorg.close()
    obrien.close()
    namesake.close()
    quoted.close()

    jorg = SQLiteSession("jorg@example.com", path)
    obrien = SQLiteSession("o'brien@example.com", path)
    assert exact(jorg.get_items()) == exact(THREAD), "a reopened session sees its earlier items"
    obrien.add_items([AssistantMessage("billing", "Invoice 88 is in your inbox.")])
    assert jorg.pop_item() == THREAD[-1], "pop_item removes this session's latest item and returns it"
    assert jorg.get_items() == THREAD[:-1], "pop_item removes exactly one item, the latest"
    assert obrien.get_items() == [
        UserMessage("Where is my invoice?"), AssistantMessage("billing", "Invoice 88 is in your inbox."),
    ], "pop_item leaves other sessions alone"
    assert obrien.get_items(limit=1) == [AssistantMessage("billing", "Invoice 88 is in your inbox.")], (
        "a limit keeps the latest items, oldest first"
    )
    assert obrien.pop_item() == AssistantMessage("billing", "Invoice 88 is in your inbox."), (
        "pop_item removes this session's latest item and returns it"
    )
    assert SQLiteSession("nobody@example.com", path).pop_item() is None, "an empty session pops None"
    obrien.clear_session()
    assert (obrien.get_items(), jorg.get_items()) == ([], THREAD[:-1]), "clear_session empties only its own session"
    jorg.close()
    obrien.close()
    assert SQLiteSession("o'brien@example.com", path).get_items() == [], "a cleared session stays empty after a reopen"

    desk = order_desk()
    session = SQLiteSession("thread-7", path)
    first = Runner().run(desk.triage, "My order 9001 arrived broken. Refund please.", session=session)
    second = Runner().run(desk.triage, "Thanks a lot!", session=session)
    assert desk.triage.model.requests[-1].conversation == first.new_items + [UserMessage("Thanks a lot!")], (
        "a run reads the session's earlier items first"
    )
    session.close()
    reopened = SQLiteSession("thread-7", path)
    assert exact(reopened.get_items()) == exact(first.new_items + second.new_items), "a run adds its new items to the session"
    third = Runner().run(desk.triage, "Is order 9002 on its way?", session=reopened)
    assert desk.triage.model.requests[-2].conversation == first.new_items + second.new_items + [third.new_items[0]], (
        "a reopened session gives the next run the whole conversation"
    )
    reopened.close()


@pytest.mark.skip("Part 3")
def test_nested_handoff_history() -> None:
    """A nested handoff passes on one summary of the earlier conversation and the latest turn as it is."""
    earlier = [
        UserMessage("Where is order 9001?"),
        ToolItem("triage", "order_status", {"order": 9001}, "shipped 2026-10-29"),
        HandoffItem("triage", "support"),
        AssistantMessage("support", "Order 9001 left the warehouse on Oct 29."),
    ]
    latest = [
        UserMessage("It arrived broken. I want my money back."),
        ToolItem("triage", "lookup_customer", {"email": "jorg@example.com"}, '{"id": 1842}'),
        HandoffItem("triage", "billing"),
    ]
    conversation = earlier + latest
    nested = nest_handoff_history(conversation)
    assert nested == [
        HistorySummary((
            "user: Where is order 9001?",
            'triage called order_status {"order": 9001} -> shipped 2026-10-29',
            "triage handed off to support",
            "support: Order 9001 left the warehouse on Oct 29.",
        )),
        *latest,
    ], "everything before the latest user message becomes one summary, and the latest turn stays as it is"
    assert conversation == earlier + latest, "the conversation passed in is not changed"
    assert nest_handoff_history(latest) == latest, "nothing before the latest user message, no summary"
    assert nest_handoff_history(nested) == nested, "a summary is carried over, not summarized again"
    later = nested + [AssistantMessage("billing", "Refund started."), UserMessage("Thanks!")]
    assert nest_handoff_history(later) == [
        HistorySummary(nested[0].lines + (
            "user: It arrived broken. I want my money back.",
            'triage called lookup_customer {"email": "jorg@example.com"} -> {"id": 1842}',
            "triage handed off to billing",
            "billing: Refund started.",
        )),
        UserMessage("Thanks!"),
    ], "an earlier summary's lines come first, then the newer items"
    thanks = [UserMessage("Thanks!"), AssistantMessage("billing", "You're welcome."), UserMessage("Thanks!")]
    assert nest_handoff_history(thanks) == [HistorySummary(("user: Thanks!", "billing: You're welcome.")), thanks[-1]], (
        "the latest user message, even when an earlier one says the same"
    )

    desk = order_desk()
    session = MemorySession()
    runner = Runner(max_handoffs=1, nest_handoff_history=True)
    first = runner.run(desk.triage, "My order 9001 arrived broken. Refund please.", session=session)
    assert desk.billing.model.requests[-1].conversation == first.new_items[:3], "a first turn has nothing to nest"
    second = runner.run(desk.triage, "And refund order 9002 too, it never came.", session=session)
    assert desk.billing.model.requests[-1].conversation == [
        HistorySummary((
            "user: My order 9001 arrived broken. Refund please.",
            'triage called order_status {"order": 9001} -> shipped 2026-10-29',
            "triage handed off to billing",
            "billing: Refund started for order 9001.",
        )),
        *second.new_items[:3],
    ], "the agent a nested handoff goes to reads the nested conversation"
    assert session.items == first.new_items + second.new_items and [type(i).__name__ for i in session.items] == [
        "UserMessage", "ToolItem", "HandoffItem", "AssistantMessage",
    ] * 2, "the session keeps every item; nesting only changes what the next agent reads"

    refunds = Agent("refunds", "Issue refunds to cards.", answers("The refund for order 9002 goes to your new card."))
    billing = Agent("billing", "Handle refunds.", transfers_to("refunds"), handoffs=[Handoff(refunds)])
    triage = Agent(
        "triage", "Route the customer.", Model(order_reply),
        tools=[FunctionTool("order_status", lambda order: ORDERS[order])],
        handoffs=[Handoff(billing)],
    )
    Runner(max_handoffs=2, nest_handoff_history=True).run(triage, "Send the order 9002 refund to my new card.", session=session)
    seen_by_billing = billing.model.requests[-1].conversation
    assert len(seen_by_billing[0].lines) == 8 and seen_by_billing[1:] == session.items[-5:-2], (
        "the summary covers both earlier runs"
    )
    assert refunds.model.requests[-1].conversation == seen_by_billing + [HandoffItem("billing", "refunds")], (
        "a second nested handoff carries the summary over as it is"
    )


def lookup_desk(on_lookup=lambda: None, before_reply=lambda: None) -> SimpleNamespace:
    """triage looks the customer up and hands off to billing. Every agent shares the desk's card check."""
    cards = [CardNumberGuard()]

    def lookup_customer(email: str) -> str:
        on_lookup()
        return "customer 1842, plan pro"

    def route(request: ModelRequest) -> dict:
        if isinstance(request.conversation[-1], UserMessage):
            before_reply()
            return {"tool": "lookup_customer", "args": {"email": "jorg@example.com"}}
        return {"tool": "transfer_to_billing"}

    billing = Agent("billing", "Handle refunds.", answers("Refund for invoice 4711 is on its way."), output_guardrails=cards)
    triage = Agent(
        "triage", "Route the customer.", Model(route),
        tools=[FunctionTool("lookup_customer", lookup_customer)],
        handoffs=[Handoff(billing)],
        input_guardrails=[PiiGuard([rule for rule in pii_rules() if rule[0].startswith("de_")])],
        output_guardrails=cards,
    )
    return SimpleNamespace(triage=triage, billing=billing)


REFUND = "Refund invoice 4711 for jorg@example.com, please."
END_ORDER = [2, 4, 5, 6, 7, 3, 9, 8, 10, 1]
SPANS = [
    {"span_id": 2, "parent_id": 1, "kind": "guardrail", "name": "pii", "attributes": {"stage": "input", "passed": True, "reason": "ok"}},
    {"span_id": 4, "parent_id": 3, "kind": "generation", "name": "triage", "attributes": {"tool_call": "lookup_customer"}},
    {
        "span_id": 5, "parent_id": 3, "kind": "tool", "name": "lookup_customer",
        "attributes": {"args": {"email": "jorg@example.com"}, "result": "customer 1842, plan pro"},
    },
    {"span_id": 6, "parent_id": 3, "kind": "generation", "name": "triage", "attributes": {"tool_call": "transfer_to_billing"}},
    {"span_id": 7, "parent_id": 3, "kind": "handoff", "name": "transfer_to_billing", "attributes": {"from": "triage", "to": "billing"}},
    {"span_id": 3, "parent_id": 1, "kind": "agent", "name": "triage", "attributes": {"tools": ["lookup_customer", "transfer_to_billing"]}},
    {"span_id": 9, "parent_id": 8, "kind": "generation", "name": "billing", "attributes": {"output": "Refund for invoice 4711 is on its way."}},
    {"span_id": 8, "parent_id": 1, "kind": "agent", "name": "billing", "attributes": {"tools": []}},
    {"span_id": 10, "parent_id": 1, "kind": "guardrail", "name": "card_numbers", "attributes": {"stage": "output", "passed": True, "reason": "ok"}},
    {"span_id": 1, "parent_id": None, "kind": "run", "name": "run", "attributes": {"agent": "triage", "last_agent": "billing"}},
]


class Collector:
    """A trace processor that notes which span it got, in a log shared with other collectors."""

    def __init__(self, name: str, log: list) -> None:
        self.name = name
        self.log = log

    def on_span_end(self, span) -> None:
        self.log.append((self.name, span.span_id))


class Stuck:
    """A slow trace backend: it hangs on the first span until the test lets it go, at most a second."""

    def __init__(self) -> None:
        self.entered = threading.Event()
        self.gate = threading.Event()
        self.spans: list = []

    def on_span_end(self, span) -> None:
        self.entered.set()
        if not self.gate.wait(timeout=1.0):
            self.gate.set()
        self.spans.append(span)


@pytest.mark.skip("Part 4")
def test_trace_processors(tmp_path) -> None:
    """Every processor gets each span as it ends; a slow one never holds a run up."""
    path = tmp_path / "spans.ndjson"
    on_disk_during_lookup: list[int] = []
    late: list = []

    def peek() -> None:
        on_disk_during_lookup.extend(json.loads(line)["span_id"] for line in path.read_text(encoding="utf-8").splitlines())
        if not late:
            tracing.add_trace_processor(Collector("late", late))

    tracing = Tracing()
    with open(path, "w", encoding="utf-8") as sink:
        tracing.add_trace_processor(NdjsonSpanWriter(sink))
        desk = lookup_desk(on_lookup=peek)
        runner = Runner(tracing)
        runner.run(desk.triage, REFUND)
        assert on_disk_during_lookup == [2, 4], "a span is in the file as soon as it ends"
        assert [span_id for _, span_id in late] == [5, 6, 7, 3, 9, 8, 10, 1], (
            "a processor added during a run gets every span that ends after that"
        )
        with pytest.raises(InputGuardrailTripwireTriggered):
            runner.run(desk.triage, "My ID is DE-482-913-775.")
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert records[:10] == [{"trace_id": "trace_1", **span} for span in SPANS], (
        "one line per span, in the order the spans end, children before their parents"
    )
    assert records[10:] == [
        {
            "trace_id": "trace_2", "span_id": 2, "parent_id": 1, "kind": "guardrail", "name": "pii",
            "attributes": {"stage": "input", "passed": False, "reason": "matches PII rule de_national_id"},
        },
        {
            "trace_id": "trace_2", "span_id": 1, "parent_id": None, "kind": "run", "name": "run",
            "attributes": {"agent": "triage", "error": "InputGuardrailTripwireTriggered"},
        },
    ], "a run that trips a guardrail still exports its spans"

    log: list = []
    stuck = Stuck()
    background = BackgroundProcessor(stuck, max_queue=3)
    tracing = Tracing()
    tracing.add_trace_processor(Collector("first", log))
    tracing.add_trace_processor(background)
    tracing.add_trace_processor(Collector("second", log))
    desk = lookup_desk(before_reply=lambda: stuck.entered.wait(timeout=1.0))
    start = time.perf_counter()
    Runner(tracing).run(desk.triage, REFUND)
    elapsed = time.perf_counter() - start
    assert log == [(name, span_id) for span_id in END_ORDER for name in ("first", "second")], (
        "each span goes to every processor, in the order they were added"
    )
    assert elapsed < 0.1, "a slow processor must not hold up the run"
    assert background.dropped == 6, "a span that finds max_queue spans waiting is dropped and counted"
    stuck.gate.set()
    background.shutdown()
    assert [span.span_id for span in stuck.spans] == [2, 4, 5, 6], (
        "queued spans reach the slow processor in order, before shutdown returns"
    )


def desk_agent(name: str, tools=(), input_guardrails=(), output_guardrails=()) -> Agent:
    return Agent(
        name, f"The {name} desk.", answers("ok"),
        tools=list(tools), input_guardrails=list(input_guardrails), output_guardrails=list(output_guardrails),
    )


def tool(name: str) -> FunctionTool:
    return FunctionTool(name, lambda **args: "ok")


def guardrail(name: str) -> SimpleNamespace:
    return SimpleNamespace(name=name, check=lambda text: (True, "ok"))


def help_center() -> list[Agent]:
    cards = CardNumberGuard()
    triage = desk_agent("triage", input_guardrails=[guardrail("pii")], output_guardrails=[LengthCap(60)])
    support = desk_agent("support", tools=[tool("search_docs"), BuiltinTool("web_fetch")])
    billing = desk_agent("billing", tools=[tool("lookup_invoice")], output_guardrails=[cards])
    sales = desk_agent("sales", tools=[tool("quote")], input_guardrails=[guardrail("pricing_scope")], output_guardrails=[LengthCap(300)])
    vat_desk = desk_agent("vat_desk", output_guardrails=[cards])
    refunds = desk_agent("refunds", tools=[tool("lookup_invoice"), tool("issue_refund")], output_guardrails=[cards])
    escalations = desk_agent("escalations", tools=[BuiltinTool("file_reader"), tool("issue_refund")], output_guardrails=[cards])
    accounts = desk_agent("accounts")
    ledger = desk_agent("ledger", tools=[tool("export_ledger")], output_guardrails=[cards])
    archive = desk_agent("archive", tools=[tool("purge_history")])
    triage.handoffs = [Handoff(support), Handoff(billing), Handoff(sales)]
    support.handoffs = [Handoff(accounts), Handoff(escalations), Handoff(triage)]
    billing.handoffs = [Handoff(vat_desk), Handoff(refunds), Handoff(triage)]
    sales.handoffs = [Handoff(billing)]
    vat_desk.handoffs = [Handoff(ledger)]
    escalations.handoffs = [Handoff(escalations), Handoff(refunds)]
    accounts.handoffs = [Handoff(ledger)]
    archive.handoffs = [Handoff(triage)]
    return [triage, support, billing, sales, vat_desk, refunds, escalations, accounts, ledger, archive]


@pytest.mark.skip("Part 5")
def test_handoff_graph() -> None:
    """Which agents a run can reach, the shortest way to a tool, and where the guardrails do not reach."""
    graph = HandoffGraph(help_center())
    assert graph.reachable("triage") == [
        "accounts", "billing", "escalations", "ledger", "refunds", "sales", "support", "triage", "vat_desk",
    ], "follow handoffs from the entry, cycles included, and nothing else"
    assert graph.reachable("escalations") == ["escalations", "refunds"]
    assert graph.reachable("refunds") == ["refunds"], "the entry itself counts as reachable"
    assert HandoffGraph(help_center()[:1]).reachable("triage") == graph.reachable("triage"), (
        "agents reached through handoffs belong to the graph too"
    )
    assert graph.path_to_tool("triage", "issue_refund") == ["triage", "billing", "refunds"], (
        "among shortest chains, the one that comes first name by name"
    )
    assert graph.path_to_tool("triage", "export_ledger") == ["triage", "billing", "vat_desk", "ledger"], (
        "chains are compared name by name from the entry"
    )
    assert graph.path_to_tool("triage", "web_fetch") == ["triage", "support"], "built-in tools are tools too"
    assert graph.path_to_tool("billing", "lookup_invoice") == ["billing"], "the entry itself may have the tool"
    assert graph.path_to_tool("triage", "purge_history") is None, "an agent no run can reach does not count"
    assert graph.audit("triage") == [
        ("accounts", "no output guardrail", ""),
        ("escalations", "built-in tool needs its own policy", "file_reader"),
        ("sales", "input guardrail never runs", "pricing_scope"),
        ("support", "built-in tool needs its own policy", "web_fetch"),
        ("support", "no output guardrail", ""),
    ], "the gaps of the agents a run from triage can reach, sorted"
    assert graph.audit("sales")[-1] == ("triage", "input guardrail never runs", "pii"), (
        "only the entry's input guardrails run"
    )
    assert graph.audit("accounts") == [("accounts", "no output guardrail", "")], "the entry may give the final answer too"
    with pytest.raises(KeyError):
        graph.reachable("nobody")
    with pytest.raises(KeyError):
        graph.path_to_tool("nobody", "quote")
    with pytest.raises(ValueError):
        HandoffGraph(help_center() + [desk_agent("billing")])
    app = help_center()
    app[3].handoffs.append(Handoff(desk_agent("billing")))
    with pytest.raises(ValueError):
        HandoffGraph(app)
