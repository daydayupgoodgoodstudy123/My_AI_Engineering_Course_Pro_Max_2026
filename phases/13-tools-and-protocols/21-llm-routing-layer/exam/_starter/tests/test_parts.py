import asyncio
import copy
import csv
import gc
import io
import random
import time
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
from modelrouter.aliases import AliasCycle, AliasError, UnknownName, expand
from modelrouter.balancer import Deployment, NoEligibleDeployment, Pool, RetryBudgetExhausted, Router
from modelrouter.budget import Budget, BudgetExceeded
from modelrouter.gateway import AllProvidersFailed, Gateway, RequestRejected
from modelrouter.latency import Request, Result, route_by_latency
from modelrouter.ledger import Call, Ledger, TeamMonth
from modelrouter.pricing import PRICES, cost_micros
from modelrouter.providers import Attempt, ProviderError, Reply

UTC = timezone.utc
CET = timezone(timedelta(hours=1))
EST = timezone(timedelta(hours=-5))
GPT4O, MINI, SONNET, HAIKU, GEMINI = (
    "openai/gpt-4o",
    "openai/gpt-4o-mini",
    "anthropic/claude-sonnet",
    "anthropic/claude-haiku",
    "google/gemini-pro",
)


class Clock:
    """A test clock that moves only when the test moves it."""

    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


def request_problem(messages: list[dict]) -> tuple[int, str] | None:
    """What an OpenAI-compatible API rejects in a messages array, as (status, message)."""
    answerable: set[str] = set()
    for i, message in enumerate(messages):
        role = message.get("role")
        if role not in ("system", "user", "assistant", "tool"):
            return 422, f"messages[{i}].role: unknown role {role!r}"
        if role == "assistant" and message.get("tool_calls"):
            answerable = {call["id"] for call in message["tool_calls"]}
            continue
        if role == "tool" and message.get("tool_call_id") not in answerable:
            return 400, f"messages[{i}]: a tool message needs the tool_call_id of the call it answers"
        if not isinstance(message.get("content"), str):
            return 400, f"messages[{i}].content must be a string"
    return None


class Providers:
    """Scripted providers: each model checks the request and answers with fixed usage, unless it is down."""

    def __init__(self, usage: tuple[int, int] = (1200, 400)) -> None:
        self.usage = usage
        self.down: dict[str, int] = {}  # model -> the 5xx it answers with
        self.sent: list[tuple[str, list[dict]]] = []

    def __call__(self, model: str, messages: list[dict]) -> Reply:
        self.sent.append((model, copy.deepcopy(messages)))
        if model in self.down:
            raise ProviderError(model, self.down[model], "upstream unavailable")
        problem = request_problem(messages)
        if problem:
            raise ProviderError(model, *problem)
        return Reply(model, f"[{model}] done", *self.usage)


LOOKUP = {"id": "call_7", "type": "function", "function": {"name": "card_status", "arguments": '{"last4": "1111"}'}}
CONVERSATION = [
    {"role": "system", "content": "You are Acme's billing assistant."},
    {"role": "user", "content": "My card 4111111111111111 was declined. My SSN is 123-45-6789 if you need it."},
    {"role": "assistant", "content": None, "tool_calls": [LOOKUP]},
    {"role": "tool", "tool_call_id": "call_7", "content": "card 4111111111111111: declined, daily limit reached"},
]
REDACTED = [
    {"role": "system", "content": "You are Acme's billing assistant."},
    {"role": "user", "content": "My card [REDACTED] was declined. My SSN is [REDACTED] if you need it."},
    {"role": "assistant", "content": None, "tool_calls": [LOOKUP]},
    {"role": "tool", "tool_call_id": "call_7", "content": "card [REDACTED]: declined, daily limit reached"},
]


def ask(text: str) -> list[dict]:
    return [{"role": "user", "content": text}]


@pytest.mark.skip("Part 1")
def test_route_and_charge() -> None:
    """The gateway redacts every message, falls back only on 5xx, charges the model that served, and stays fast."""
    clock = Clock(datetime(2026, 11, 30, 23, 59, 59, 999999, tzinfo=UTC))
    providers = Providers()
    gateway = Gateway(providers, Budget({"support": 1_000_000, "research": 36_000}), clock=clock)

    asked = copy.deepcopy(CONVERSATION)
    served = gateway.route("support", "smart", asked)
    assert providers.sent == [(GPT4O, REDACTED)], "PII never leaves the gateway, in any message"
    assert (served.served_model, served.attempts, served.redacted) == (GPT4O, ((GPT4O, 200),), True)
    assert served.cost_micros == 1200 * 5 + 400 * 15

    providers.down = {GPT4O: 503, SONNET: 502}
    history = [
        {"role": "user", "content": "My SSN is 123-45-6789."},
        {"role": "assistant", "content": "Thanks, I have it."},
        {"role": "user", "content": "Summarize ticket 4521."},
    ]
    served = gateway.route("support", "smart", history)
    assert served.attempts == ((GPT4O, 503), (SONNET, 502), (GEMINI, 200)), "a 5xx moves on to the next model"
    assert served.served_model == GEMINI
    assert served.redacted, "redacted says whether any message was redacted, not just the last"
    assert served.cost_micros == 3_500, "a request is charged at the prices of the model that served it"
    assert gateway.budget.spent("support", "2026-11") == 12_000 + 3_500

    providers.down[GEMINI] = 500
    with pytest.raises(AllProvidersFailed) as failed:
        gateway.route("support", "smart", ask("Summarize ticket 4522."))
    assert failed.value.attempts == ((GPT4O, 503), (SONNET, 502), (GEMINI, 500))
    assert gateway.budget.spent("support", "2026-11") == 15_500, "nobody served it, so nobody pays"

    providers.down.clear()
    providers.sent.clear()
    with pytest.raises(RequestRejected) as rejected:
        gateway.route("support", "smart", [{"role": "bot", "content": "hello"}])
    assert rejected.value.status == 422
    assert [model for model, _ in providers.sent] == [GPT4O], "a 4xx is the request's fault: no other model sees it"

    for _ in range(3):
        gateway.route("research", "smart", ask("Draft the monthly summary."))
    assert gateway.budget.spent("research", "2026-11") == 36_000
    providers.sent.clear()
    with pytest.raises(BudgetExceeded):
        gateway.route("research", "smart", ask("One more draft."))
    assert providers.sent == [], "a team at its cap is refused before anything is sent"
    clock.now = datetime(2026, 12, 1, tzinfo=UTC)
    gateway.route("research", "smart", ask("December's first draft."))
    assert gateway.budget.spent("research", "2026-12") == 12_000, "a request at midnight UTC on the 1st counts in the new month"
    assert gateway.budget.spent("research", "2026-11") == 36_000, "last month's spend stays with last month"

    busy = Gateway(lambda model, messages: Reply(model, "ok", 1200, 400), Budget({"search": 10**12}), clock=Clock(datetime(2026, 11, 20, tzinfo=UTC)))
    november = datetime(2026, 11, 1, tzinfo=UTC)
    filling = time.perf_counter()
    for second in range(150_000):
        busy.budget.charge("search", november + timedelta(seconds=second), 420)
        if second % 1000 == 999:
            assert time.perf_counter() - filling < 2.0, "a charge costs the same however much the team has already spent"
    gc.collect()
    start = time.perf_counter()
    for _ in range(200):
        busy.route("search", "fast", ask("ping"))
    elapsed = time.perf_counter() - start
    assert busy.budget.spent("search", "2026-11") == 150_200 * 420
    assert elapsed < 0.02, "a request costs the same however much the team has already spent this month"


SMART_FALLBACK = (Attempt(GPT4O, 503), Attempt(SONNET, 502), Attempt(GEMINI, 200))
TRICKY = [
    Call("support", "smart", datetime(2026, 10, 31, 23, 59, 59, 999999, tzinfo=UTC), SMART_FALLBACK, GEMINI, 1200, 400, 3_500),
    Call("support", "fast", datetime(2026, 11, 1, 0, 30, tzinfo=CET), (Attempt(MINI, 200),), MINI, 70, 0, 11),
    Call("research", "smart", datetime(2026, 11, 1, tzinfo=UTC), (Attempt(GPT4O, 503), Attempt(SONNET, 503), Attempt(GEMINI, 500)), None, 0, 0, 0),
    Call("research", "fast", datetime(2026, 11, 14, 9, 15, 30, 250, tzinfo=UTC), (Attempt(MINI, 200),), MINI, 1, 0, 0),
    Call("support", "smart", datetime(2026, 11, 30, 20, 0, tzinfo=EST), (Attempt(GPT4O, 503), Attempt(SONNET, 200)), SONNET, 8, 15, 249),
    Call("support", "fast", datetime(2026, 11, 30, 23, 59, 59, 999999, tzinfo=UTC), (Attempt(MINI, 503), Attempt(HAIKU, 200)), HAIKU, 1000, 250, 1_800),
]


@pytest.mark.skip("Part 2")
def test_cost_ledger(tmp_path) -> None:
    """Every call is kept exactly, in whole micro-dollars, and every total is an exact sum."""
    assert [cost_micros(PRICES[c.served_model], c.input_tokens, c.output_tokens) for c in TRICKY if c.served_model] == [3_500, 11, 0, 249, 1_800]
    path = str(tmp_path / "ledger.sqlite3")

    ledger = Ledger(path)
    assert [ledger.record(call) for call in TRICKY] == [1, 2, 3, 4, 5, 6], "calls are numbered from 1, in the order they are recorded"
    assert [ledger.get(number) for number in range(1, 7)] == TRICKY, "a call comes back exactly as it was recorded"
    with pytest.raises(KeyError):
        ledger.get(7)
    ledger.close()

    ledger = Ledger(path)
    back = ledger.calls()
    assert back == TRICKY, "a reopened ledger has every call, in the order they were recorded"
    assert all(type(call.cost_micros) is int for call in back), "costs come back as whole micro-dollars"
    assert all(type(call.input_tokens) is int and type(call.output_tokens) is int for call in back), "token counts come back as ints"
    assert [(a.model, a.status) for a in back[0].attempts] == [(GPT4O, 503), (SONNET, 502), (GEMINI, 200)], "attempts keep their order"
    assert [c.alias for c in ledger.calls(team="support", month="2026-10")] == ["smart", "fast"], "months are calendar months in UTC"
    assert ledger.calls(month="2026-11") == [TRICKY[2], TRICKY[3], TRICKY[5]]
    assert ledger.calls(month="2026-12") == [TRICKY[4]]

    spend = {
        (team, month): ledger.spend(team, month)
        for team in ("support", "research", "nobody")
        for month in ("2026-10", "2026-11", "2026-12")
    }
    assert spend == {
        ("support", "2026-10"): 3_511,
        ("support", "2026-11"): 1_800,
        ("support", "2026-12"): 249,
        ("research", "2026-10"): 0,
        ("research", "2026-11"): 0,
        ("research", "2026-12"): 0,
        ("nobody", "2026-10"): 0,
        ("nobody", "2026-11"): 0,
        ("nobody", "2026-12"): 0,
    }, "spend is the exact sum of the month's calls, and 0 when there are none"
    assert all(type(total) is int for total in spend.values()), "spend is a whole number of micro-dollars"
    assert ledger.report("2026-11") == [
        TeamMonth("research", calls=2, failed=1, input_tokens=1, output_tokens=0, cost_micros=0),
        TeamMonth("support", calls=1, failed=0, input_tokens=1000, output_tokens=250, cost_micros=1_800),
    ], "one row per team, by team name; a call is failed when no model served it"
    assert ledger.report("2026-10") == [TeamMonth("support", 2, 0, 1270, 400, 3_511)]
    assert ledger.report("2027-01") == []
    assert all(type(total) is int for row in ledger.report("2026-10") for total in row[1:]), "report totals are whole numbers too"

    with pytest.raises(TypeError):
        ledger.record(replace(TRICKY[0], cost_micros=3500.0))
    assert ledger.record(replace(TRICKY[5], at=datetime(2026, 12, 2, tzinfo=UTC))) == 7, "numbers carry on after a reopen"
    assert ledger.spend("support", "2026-12") == 249 + 1_800
    ledger.close()

    rng = random.Random(21)
    busy = Ledger()
    expected = 0
    for minute in range(400):
        model = rng.choice(sorted(PRICES))
        tokens_in, tokens_out = rng.randrange(1, 4000), rng.randrange(0, 1500)
        cost = cost_micros(PRICES[model], tokens_in, tokens_out)
        start = datetime(2026, 11, 1, tzinfo=UTC) + timedelta(minutes=minute)
        busy.record(Call("batch", "fast", start, (Attempt(model, 200),), model, tokens_in, tokens_out, cost))
        expected += cost
    total = busy.spend("batch", "2026-11")
    assert total == expected and type(total) is int, "the month's total is exactly the sum of its calls"
    assert busy.report("2026-11")[0].cost_micros == expected
    busy.close()


CHAT = Pool(
    (
        Deployment("gpt-4o-us", GPT4O, "us", weight=5),
        Deployment("sonnet-eu", SONNET, "eu", weight=1),
        Deployment("gpt-4o-eu", GPT4O, "eu", weight=2, retries=1),
        Deployment("gemini-us", GEMINI, "us", weight=0),
    ),
    max_attempts=3,
)
BATCH = Pool((Deployment("mini-us", MINI, "us"), Deployment("haiku-us", HAIKU, "us", weight=0)), max_attempts=2)
US, SONNET_EU, EU, GEMINI_US = CHAT.deployments
CYCLE = ["gpt-4o-us", "gpt-4o-eu", "gpt-4o-us", "gpt-4o-us", "sonnet-eu", "gpt-4o-us", "gpt-4o-eu", "gpt-4o-us"]


class Script:
    """Scripted deployments: each answers the statuses queued for it, then 200."""

    def __init__(self, statuses: dict[str, list[int]]) -> None:
        self.statuses = {name: list(queue) for name, queue in statuses.items()}
        self.tried: list[str] = []

    def __call__(self, deployment: Deployment, messages: list[dict]) -> Reply:
        self.tried.append(deployment.name)
        queue = self.statuses.get(deployment.name, [])
        status = queue.pop(0) if queue else 200
        if status != 200:
            raise ProviderError(deployment.name, status, "scripted")
        return Reply(deployment.model, "ok", 10, 5)


@pytest.mark.skip("Part 3")
def test_weighted_pools() -> None:
    """A weighted rotation picks the first deployment, EU traffic stays in the EU, and retries share one budget."""
    router = Router({"chat": CHAT, "batch": BATCH})
    plans = [router.plan("chat") for _ in range(16)]
    assert [plan[0].name for plan in plans] == CYCLE * 2, (
        "smooth weighted round robin, earliest listed on a tie: 5:2:1 never sends five in a row to one deployment"
    )
    assert (plans[0], plans[1], plans[4]) == (
        [US, SONNET_EU, EU, GEMINI_US],
        [EU, US, SONNET_EU, GEMINI_US],
        [SONNET_EU, US, EU, GEMINI_US],
    ), "the rest of the plan keeps the listed order"
    assert [router.plan("chat", region="eu") for _ in range(4)] == [[EU, SONNET_EU], [SONNET_EU, EU], [EU, SONNET_EU], [EU, SONNET_EU]], (
        "EU users only ever see EU deployments, in their own rotation"
    )
    assert [router.plan("chat")[0].name for _ in range(8)] == CYCLE, "EU traffic does not move the other rotation"
    assert [router.plan("batch")[0].name for _ in range(3)] == ["mini-us"] * 3, "weight 0 is fallback only"
    with pytest.raises(NoEligibleDeployment):
        router.plan("batch", region="eu")
    spare = Router({"spare": Pool((GEMINI_US, BATCH.deployments[1]), max_attempts=2)})
    assert [spare.plan("spare") for _ in range(2)] == [[GEMINI_US, BATCH.deployments[1]]] * 2, (
        "with every weight 0, the plan is the listed order"
    )

    messages = ask("Translate this contract clause.")
    script = Script({"gpt-4o-eu": [503, 503]})
    outcome = Router({"chat": CHAT}).send("chat", messages, script, region="eu")
    assert (outcome.deployment, tuple(outcome.attempts)) == (SONNET_EU, (("gpt-4o-eu", 503), ("gpt-4o-eu", 503), ("sonnet-eu", 200))), (
        "a deployment's retries come before the next deployment"
    )
    assert outcome.reply.model == SONNET

    script = Script({"gpt-4o-eu": [503, 503]})
    with pytest.raises(RetryBudgetExhausted) as exhausted:
        Router({"chat": replace(CHAT, max_attempts=2)}).send("chat", messages, script, region="eu")
    assert tuple(exhausted.value.attempts) == (("gpt-4o-eu", 503), ("gpt-4o-eu", 503)) and script.tried == ["gpt-4o-eu"] * 2, (
        "every try counts against max_attempts, retries included"
    )

    script = Script({"gpt-4o-eu": [503, 503], "sonnet-eu": [502]})
    with pytest.raises(AllProvidersFailed) as failed:
        Router({"chat": CHAT}).send("chat", messages, script, region="eu")
    assert script.tried == ["gpt-4o-eu", "gpt-4o-eu", "sonnet-eu"], "EU traffic never falls back to a US deployment"
    assert tuple(failed.value.attempts) == (("gpt-4o-eu", 503), ("gpt-4o-eu", 503), ("sonnet-eu", 502))

    script = Script({"gpt-4o-eu": [400]})
    with pytest.raises(RequestRejected):
        Router({"chat": CHAT}).send("chat", messages, script, region="eu")
    assert script.tried == ["gpt-4o-eu"], "a 4xx is not retried, not even on the same deployment"

    router = Router({"chat": CHAT})
    script = Script({"gpt-4o-us": [503] * 10})
    outcomes = [router.send("chat", messages, script) for _ in range(8)]
    assert [o.attempts[0].model for o in outcomes] == CYCLE, "each request moves the rotation once, however many tries it makes"
    assert [o.deployment.name for o in outcomes] == ["sonnet-eu", "gpt-4o-eu", "sonnet-eu", "sonnet-eu", "sonnet-eu", "sonnet-eu", "gpt-4o-eu", "sonnet-eu"]


def collect(agen) -> list:
    async def drain() -> list:
        return [item async for item in agen]

    return asyncio.run(drain())


async def feed(events):
    for event in events:
        yield event


def check_routed(chunks: list[str], expected: list[tuple[str, ...]]) -> None:
    records = [list(csv.reader(io.StringIO(chunk))) for chunk in chunks]
    assert chunks and all(chunk.endswith("\n") and len(rows) == 1 for chunk, rows in zip(chunks, records)), (
        "each chunk is one whole CSV record"
    )
    assert records[0][0] == ["t_ms", "request_id", "model", "reason"], "the first record is the header"
    for (row,), (*want, why) in zip(records[1:], expected):
        assert tuple(row) == tuple(want), why
    assert len(records) - 1 == len(expected), "one record per request, and nothing else"


A, B, C = GPT4O, SONNET, GEMINI
CLOSED = "fewer than trip_after 5xx in a row leave the circuit closed"
TRAFFIC = [
    Request(0, "r01"), Request(5, "r02"),
    Result(300, "r01", A, 200, 300),
    Request(700, "r03"),
    Result(705, "r02", A, 200, 700),
    Result(730, "r03", B, 503, 30),
    Request(800, "r04"),
    Result(1250, "r04", B, 200, 250),
    Request(1300, "r05"),
    Result(1500, "r05", C, 200, 200),
    Request(2000, "r06"),
    Result(2220, "r06", C, 200, 220),
    Request(3000, "r07"),
    Result(3050, "r07", C, 503, 40),
    Request(3100, "r08"),
    Result(3140, "r08", C, 502, 30),
    Request(3200, "r09"),
    Result(3480, "r09", C, 200, 240),
    Request(4000, "r10"),
    Result(4040, "r10", C, 503, 20),
    Request(4100, "r11"),
    Result(4130, "r11", C, 503, 20),
    Request(4200, "r12"), Request(4210, "r13"),
    Result(4220, "r12", C, 500, 15),
    Request(4250, "r14"),
    Result(4300, "r13", C, 200, 90),
    Request(5000, "r15"),
    Result(5720, "r15", B, 200, 720),
    Request(6000, "r16"),
    Request(34219, "r17"), Request(34220, "r18"), Request(34230, "r19"),
    Result(34800, "r18", C, 503, 25),
    Request(35000, "r20"),
    Request(60704, "r21"), Request(60705, "r22"),
    Result(61400, "r22", A, 200, 650),
    Request(64800, "r23"),
    Result(64900, "r23", C, 200, 180),
    Request(65000, "r24"), Request(65720, "r25"),
]
ROUTED = [
    ("0", "r01", A, "unmeasured", "a model with no sample yet goes first, earliest listed first"),
    ("5", "r02", A, "unmeasured", "a model is unmeasured until one of its results comes back"),
    ("700", "r03", B, "unmeasured", "an unmeasured model goes before any measured one"),
    ("800", "r04", B, "unmeasured", "a 5xx is not a latency sample"),
    ("1300", "r05", C, "unmeasured", "a model with no sample yet goes first, earliest listed first"),
    ("2000", "r06", C, "fastest", "once every model is measured, the lowest median latency wins"),
    ("3000", "r07", C, "fastest", CLOSED),
    ("3100", "r08", C, "fastest", CLOSED),
    ("3200", "r09", C, "fastest", CLOSED),
    ("4000", "r10", C, "fastest", CLOSED),
    ("4100", "r11", C, "fastest", "a success resets the run of 5xx"),
    ("4200", "r12", C, "fastest", CLOSED),
    ("4210", "r13", C, "fastest", CLOSED),
    ("4250", "r14", B, "fastest", "trip_after 5xx in a row open the circuit: no requests until the cooldown is over"),
    ("5000", "r15", B, "fastest", "while a circuit is open, only its probe's result changes it"),
    ("6000", "r16", B, "fastest", "for an even count, the median is the mean of the two middle samples"),
    ("34219", "r17", B, "fastest", "the cooldown runs from the 5xx that opened the circuit"),
    ("34220", "r18", C, "probe", "once cooldown_ms have passed, the next request is the probe"),
    ("34230", "r19", B, "fastest", "only one probe is out at a time"),
    ("35000", "r20", B, "fastest", "a failed probe opens the circuit again, from the probe's result"),
    ("60704", "r21", B, "fastest", "a sample counts while it is less than window_ms old"),
    ("60705", "r22", A, "unmeasured", "a sample exactly window_ms old is gone; a model with none left is unmeasured again"),
    ("64800", "r23", C, "probe", "the next probe goes out cooldown_ms after the failed one"),
    ("65000", "r24", C, "fastest", "a successful probe closes the circuit"),
    ("65720", "r25", B, "unmeasured", "a model whose samples have all expired is unmeasured again"),
]
SPIKY = [
    Request(0, "q1"), Result(100, "q1", A, 200, 400),
    Request(200, "q2"), Result(300, "q2", B, 200, 400),
    Request(400, "q3"), Result(1000, "q3", A, 200, 600),
    Request(1100, "q4"), Result(1400, "q4", B, 200, 300),
    Request(1500, "q5"), Result(5500, "q5", B, 200, 4000),
    Request(5600, "q6"), Result(5700, "q6", B, 503, 10),
    Request(5800, "q7"), Result(5850, "q7", A, 502, 10),
    Request(5900, "q8"), Request(6700, "q9"), Result(6760, "q9", B, 200, 60),
    Request(6800, "q10"), Request(6850, "q11"), Request(6860, "q12"),
]
SPIKY_ROUTED = [
    ("0", "q1", A, "unmeasured", "a model with no sample yet goes first, earliest listed first"),
    ("200", "q2", B, "unmeasured", "an unmeasured model goes before any measured one"),
    ("400", "q3", A, "fastest", "a tie goes to the earliest listed model"),
    ("1100", "q4", B, "fastest", "for an even count, the median is the mean of the two middle samples"),
    ("1500", "q5", B, "fastest", "the lowest median latency wins"),
    ("5600", "q6", B, "fastest", "one slow outlier does not hide a fast model: the median, not the mean"),
    ("5800", "q7", A, "fastest", "trip_after 5xx in a row open the circuit: no requests until the cooldown is over"),
    ("5900", "q8", "", "unavailable", "with every circuit open the request is unavailable, with an empty model"),
    ("6700", "q9", B, "probe", "once cooldown_ms have passed, the next request is the probe"),
    ("6800", "q10", B, "fastest", "a successful probe closes the circuit"),
    ("6850", "q11", A, "probe", "each circuit has its own cooldown, and its probe goes out even if another model is faster"),
    ("6860", "q12", B, "fastest", "only one probe is out at a time"),
]

PROBED = [
    Request(0, "s1"), Request(10, "s2"), Request(20, "s3"),
    Result(100, "s1", A, 503, 100), Result(110, "s2", A, 503, 100),
    Request(200, "s4"),
    Request(1110, "s5"),
    Result(1150, "s3", A, 502, 1130),
    Result(1500, "s4", B, 200, 1300),
    Request(2150, "s6"),
    Result(2200, "s5", A, 200, 1090),
    Request(2300, "s7"),
    Result(2350, "s7", A, 503, 50),
    Request(2400, "s8"),
]
PROBED_ROUTED = [
    ("0", "s1", A, "unmeasured", "a model with no sample yet goes first, earliest listed first"),
    ("10", "s2", A, "unmeasured", "a model is unmeasured until one of its results comes back"),
    ("20", "s3", A, "unmeasured", "a model is unmeasured until one of its results comes back"),
    ("200", "s4", B, "unmeasured", "trip_after 5xx in a row open the circuit: no requests until the cooldown is over"),
    ("1110", "s5", A, "probe", "a probe goes before an unmeasured model"),
    ("2150", "s6", B, "fastest", "only the probe's own result ends the probe; a late 5xx from an earlier request changes nothing"),
    ("2300", "s7", A, "fastest", "a successful probe closes the circuit"),
    ("2400", "s8", A, "fastest", "a successful probe starts a new run: one 5xx does not reopen the circuit"),
]


@pytest.mark.skip("Part 4")
def test_latency_routing() -> None:
    """Each request goes to the fastest healthy model of the last minute, and each decision is logged as it is made."""
    chunks = collect(route_by_latency(feed(TRAFFIC), [A, B, C], window_ms=60_000, trip_after=3, cooldown_ms=30_000))
    check_routed(chunks, ROUTED)
    chunks = collect(route_by_latency(feed(SPIKY), [A, B], window_ms=10_000, trip_after=1, cooldown_ms=1_000))
    check_routed(chunks, SPIKY_ROUTED)
    chunks = collect(route_by_latency(feed(PROBED), [A, B], window_ms=10_000, trip_after=2, cooldown_ms=1_000))
    check_routed(chunks, PROBED_ROUTED)

    pulled: list[int] = []

    async def trickle():
        for i, event in enumerate(TRAFFIC):
            pulled.append(i)
            yield event

    async def first_two() -> list[str]:
        agen = route_by_latency(trickle(), [A, B, C])
        got = [await agen.__anext__(), await agen.__anext__()]
        await agen.aclose()
        return got

    header, first = asyncio.run(first_two())
    assert next(csv.reader([header])) == ["t_ms", "request_id", "model", "reason"]
    assert next(csv.reader([first])) == ["0", "r01", A, "unmeasured"]
    assert len(pulled) == 1, "decide each request as soon as it arrives"


MODELS = {
    "openai/gpt-4o": "us",
    "openai/gpt-4o-mini": "us",
    "azure/gpt-4o-eu": "eu",
    "anthropic/claude-sonnet": "us",
    "anthropic/claude-haiku": "us",
    "bedrock/claude-haiku-eu": "eu",
    "mistral/large": "eu",
    "google/gemini-pro": "us",
}
ALIASES = {
    "fast": ["openai/gpt-4o-mini", "bedrock/claude-haiku-eu", "anthropic/claude-haiku"],
    "smart": ["openai/gpt-4o", "azure/gpt-4o-eu", "fast"],
    "coding": ["anthropic/claude-sonnet", "fast", "smart"],
    "eu-smart": {"region": "eu", "chain": ["smart", "mistral/large"]},
    "eu-first": ["eu-smart", "smart"],
    "us-batch": {"region": "us", "chain": ["google/gemini-pro", "fast"]},
    "eu-batch": {"region": "eu", "chain": ["us-batch", "mistral/large"]},
}


@pytest.mark.skip("Part 5")
def test_alias_expansion() -> None:
    """Aliases expand depth first into one chain without repeats, with regions carried all the way down."""
    assert expand("smart", ALIASES, MODELS) == [
        "openai/gpt-4o", "azure/gpt-4o-eu", "openai/gpt-4o-mini", "bedrock/claude-haiku-eu", "anthropic/claude-haiku",
    ], "an alias inside a chain is expanded in its place"
    assert expand("coding", ALIASES, MODELS) == [
        "anthropic/claude-sonnet", "openai/gpt-4o-mini", "bedrock/claude-haiku-eu", "anthropic/claude-haiku", "openai/gpt-4o", "azure/gpt-4o-eu",
    ], "a model reached twice keeps its first place; an alias reached twice is not a cycle"
    assert expand("openai/gpt-4o", ALIASES, MODELS) == ["openai/gpt-4o"], "a model stands for itself"
    assert expand("eu-smart", ALIASES, MODELS) == ["azure/gpt-4o-eu", "bedrock/claude-haiku-eu", "mistral/large"], (
        "a region applies to everything reached through the alias"
    )
    assert expand("eu-first", ALIASES, MODELS) == [
        "azure/gpt-4o-eu", "bedrock/claude-haiku-eu", "mistral/large", "openai/gpt-4o", "openai/gpt-4o-mini", "anthropic/claude-haiku",
    ], "a model one path leaves out can still be added by a later path"
    assert expand("eu-batch", ALIASES, MODELS) == ["mistral/large"], "an inner region can narrow an outer one, never widen it"
    assert expand("smart", ALIASES, MODELS, region="eu") == ["azure/gpt-4o-eu", "bedrock/claude-haiku-eu"], (
        "the caller's region applies all the way down"
    )
    assert expand("eu-smart", ALIASES, MODELS, region="eu") == ["azure/gpt-4o-eu", "bedrock/claude-haiku-eu", "mistral/large"], (
        "an alias region that agrees with the caller's is no conflict"
    )
    assert expand("mistral/large", ALIASES, MODELS, region="eu") == ["mistral/large"]
    with pytest.raises(AliasError) as outside:
        expand("openai/gpt-4o", ALIASES, MODELS, region="eu")
    assert type(outside.value) is AliasError, "a model named directly must be in the caller's region too"
    with pytest.raises(AliasError) as empty:
        expand("us-batch", ALIASES, MODELS, region="eu")
    assert type(empty.value) is AliasError, "an alias with nothing admitted is an error, not an empty chain"

    looped = {**ALIASES, "a": ["openai/gpt-4o", "b"], "b": ["c"], "c": ["anthropic/claude-sonnet", "a"], "entry": ["fast", "a"]}
    with pytest.raises(AliasCycle) as cycle:
        expand("entry", looped, MODELS)
    assert list(cycle.value.cycle) == ["a", "b", "c", "a"], "the error names the cycle, from the alias that repeats"
    with pytest.raises(AliasCycle) as own:
        expand("me", {"me": ["openai/gpt-4o", "me"]}, MODELS)
    assert list(own.value.cycle) == ["me", "me"]

    deep = {"l0": ["l1"], "l1": ["l2"], "l2": ["l3"], "l3": ["l4"], "l4": ["l5"], "l5": ["openai/gpt-4o"]}
    assert expand("l1", deep, MODELS, max_depth=5) == ["openai/gpt-4o"], "an alias exactly max_depth deep is fine"
    with pytest.raises(AliasError) as too_deep:
        expand("l0", deep, MODELS, max_depth=5)
    assert type(too_deep.value) is AliasError

    with pytest.raises(UnknownName):
        expand("smrt", ALIASES, MODELS)
    with pytest.raises(UnknownName) as unknown:
        expand("legacy", {**ALIASES, "legacy": ["fast", "openai/gpt-5o"]}, MODELS)
    assert unknown.value.name == "openai/gpt-5o", "a name that is neither an alias nor a model is a config error, not a model"
    hidden = {
        **ALIASES,
        "eu-strict": {"region": "eu", "chain": ["us-legacy", "mistral/large"]},
        "us-legacy": {"region": "us", "chain": ["openai/gpt-4o", "openai/gpt-3.5"]},
    }
    with pytest.raises(UnknownName):
        expand("eu-strict", hidden, MODELS)
