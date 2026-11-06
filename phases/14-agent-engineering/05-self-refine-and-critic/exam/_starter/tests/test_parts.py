import asyncio
import gc
import json
import re
import time

import pytest
from critic.evaluator import Check, ToolUnavailable, refine_until_verified, verify_claims
from critic.guardrail import OutputGuardrailTripwireTriggered, guard_stream
from critic.loop import KNOWN_WRONG_FACTS, normalize_claim, run_loop, verify_external
from critic.outline import check_outline
from critic.revisions import CorruptChain, Revision, RevisionChain

WORLD = "world facts"
LESSON_DRAFT = "- Paris is the capital of Germany\n- Mt Everest is in Europe\n- Water boils at 100C"
SUN_DRAFT = "- Paris is the capital of France\n- The sun orbits the Earth.\n- Water boils at 100C"
FIXED_DRAFT = "- Paris is the capital of France\n- Mt Everest is in Asia\n- Water boils at 100C at sea level"


class Scripted:
    """A deterministic stand-in for the LLM: its drafts and self-critiques come from a script.

    generate returns the first draft and the n-th refine returns draft n (the last one, once the
    script runs out). Every refine call is recorded with the outputs it was shown.
    """

    def __init__(self, drafts: list[str], feedback: list[str] = ()) -> None:
        self.drafts = list(drafts)
        self.feedback_script = list(feedback)
        self.feedbacks = 0
        self.refines: list[tuple[str, list[str]]] = []

    def generate(self, task: str) -> str:
        return self.drafts[0]

    def feedback(self, task: str, output: str) -> str:
        assert self.feedback_script, "with a verifier, CRITIC replaces the model's self-critique"
        self.feedbacks += 1
        return self.feedback_script[min(self.feedbacks, len(self.feedback_script)) - 1]

    def refine(self, task: str, output: str, critique: str, history: list) -> str:
        self.refines.append((critique, [attempt.output for attempt in history]))
        return self.drafts[min(len(self.refines), len(self.drafts) - 1)]


def raises(error: type, call, *args) -> bool:
    try:
        call(*args)
    except error:
        return True
    return False


@pytest.mark.skip("Part 1")
def test_refine_loop() -> None:
    """The lesson's loop: CRITIC checks every reference fact, and the stop rule is the 2026 default."""
    model = Scripted([LESSON_DRAFT, SUN_DRAFT, FIXED_DRAFT])
    run = run_loop(WORLD, model, verifier=verify_external)
    assert [(a.output, a.critique, a.passed) for a in run] == [
        (LESSON_DRAFT, "verifier: 'paris is the capital of germany' contradicts reference data", False),
        (SUN_DRAFT, "verifier: 'the sun orbits the earth' contradicts reference data", False),
        (FIXED_DRAFT, "verifier: ok", True),
    ], "CRITIC never passes a draft that states a known wrong fact"
    assert model.refines == [
        (run[0].critique, [LESSON_DRAFT]),
        (run[1].critique, [LESSON_DRAFT, SUN_DRAFT]),
    ], "refine sees the critique and every earlier output"

    fits = "Mt Everest is the highest mountain on Earth in the Himalaya"
    too_long = fits + "."
    assert (len(fits), len(too_long)) == (59, 60)
    drafts = [f"- Paris is the capital of France\n- {text}\n- Water boils at 100C" for text in (fits, too_long)]
    assert [verify_external(draft) for draft in drafts] == [
        ("verifier: ok", True),
        ("verifier: bullet 2 is not under 60 chars", False),
    ], "a bullet's text, without its marker, must be under 60 chars"
    assert verify_external(f"- {too_long}\n- Water boils at 100C\n- The sun orbits the earth") == (
        "verifier: 'the sun orbits the earth' contradicts reference data",
        False,
    ), "a known wrong fact is reported before any format problem"

    stamp = Scripted([LESSON_DRAFT, FIXED_DRAFT], feedback=["No issues.", "No issues, looks good to me."])
    run = run_loop(WORLD, stamp)
    assert [(a.iteration, a.output, a.passed, a.grounded) for a in run] == [
        (1, LESSON_DRAFT, True, False),
        (2, FIXED_DRAFT, True, False),
    ], "the model's own 'no issues' can end the loop from round 2 on, never in round 1"
    clean = Scripted([FIXED_DRAFT])
    assert [a.iteration for a in run_loop(WORLD, clean, verifier=verify_external)] == [1] and not clean.refines, (
        "a passing verifier ends the loop at once"
    )
    stuck = Scripted([LESSON_DRAFT], feedback=["first bullet reads wrong, double-check capital"])
    run = run_loop(WORLD, stuck, max_iters=3)
    assert [a.passed for a in run] == [False, False, False] and len(stuck.refines) == 2, (
        "the round that ends the loop is not refined"
    )
    assert verify_external("- The earth orbits the sun\n- Paris is the capital of France\n- Water boils at 100C") == (
        "verifier: ok",
        True,
    ), "a bullet is wrong only when its claim is a known wrong fact, word for word"

    facts = [f"city {i} is the capital of country {i}" for i in range(20_000)]
    bullets = [f"- City {i} is the capital of country {i + 1}" for i in range(2000)]
    bullets[1990] = "- City 19995 is the capital of country 19995."
    bullets[1995] = "- City 19990 is the capital of country 19990"
    long_draft = "\n".join(bullets)
    gc.collect()
    start = time.perf_counter()
    verdict = verify_external(long_draft, facts)
    elapsed = time.perf_counter() - start
    assert elapsed < 0.04, "verify_external should be fast on long drafts"
    assert verdict == ("verifier: 'city 19995 is the capital of country 19995' contradicts reference data", False), (
        "the critique names the first wrong bullet"
    )


ROUNDS = [
    ("", "the model returned nothing"),
    (LESSON_DRAFT, "verifier: 'paris is the capital of germany' contradicts reference data"),
    (
        "- Paris is the capital of France\n- Mt Everest is in Europe\n- Water boils at 100C\n",
        "verifier: 'mt everest is in europe' contradicts reference data",
    ),
    (
        "- Paris is the capital of France\r\n- Mt Everest is in Asia\r\n- Water boils at 100C at sea level\r\n",
        "bullet 2 contradicted: reference: Mt Everest is in Asia\nbullet 3 unverified: calculator offline",
    ),
    ("", "the model returned nothing"),
    ("- Wasser kocht bei 100 °C  \n- 水在海平面 100°C 沸腾\n- Ünïcode and emoji 🌊", "verifier: ok ✓"),
    ("\n", "a single line break"),
    (
        "+ looks like an added line\n@@ -1 +1 @@\n- Water boils\rat 100C\n? a hint\u2028on one line\n",
        "diff markers, a bare CR and U+2028 are content too",
    ),
    (
        "- Paris is the capital of France\n- Rome is the capital of Italy\n- Mt Everest is in Asia\n"
        "- Water boils at 100C\n- Ice floats\n",
        "verifier: expected 3 bullet lines",
    ),
    (
        "Summary of world facts\n- Paris is the capital of France\n- Mt Everest is in Asia\n"
        "- Water boils at 100C\n- Ice floats on water\n",
        "verifier: expected 3 bullet lines",
    ),
]


@pytest.mark.skip("Part 2")
def test_revision_chain(tmp_path) -> None:
    """Every round of a refine loop reads back exactly from a file of line diffs."""
    path = tmp_path / "loop.chain"
    chain = RevisionChain(path)
    assert [chain.append(output, critique) for output, critique in ROUNDS] == list(range(len(ROUNDS))), (
        "append returns each round's number, from 0"
    )
    expected = [Revision(n, output, critique) for n, (output, critique) in enumerate(ROUNDS)]
    reader = RevisionChain(path)  # a second instance, while the first one is still in use
    assert len(reader) == len(ROUNDS) and [reader.get(n) for n in range(len(ROUNDS))] == expected, (
        "every round reads back exactly as it was appended"
    )
    assert all(raises(IndexError, reader.get, n) for n in (len(ROUNDS), -1)), "rounds run from 0 to len - 1"
    assert reader.append(FIXED_DRAFT, "verifier: ok") == len(ROUNDS)
    assert RevisionChain(path).get(len(ROUNDS)) == Revision(len(ROUNDS), FIXED_DRAFT, "verifier: ok"), (
        "a reopened chain keeps growing"
    )

    lines = [f"- Claim {i}: city {i} is the capital of country {i}\n" for i in range(400)]
    long_chain = RevisionChain(tmp_path / "long.chain")
    texts = []
    for n in range(40):
        if n:
            lines[(n * 37) % 400] = f"- Claim revised in round {n}\n"
        texts.append("".join(lines))
        long_chain.append(texts[-1], f"round {n}")
    assert (tmp_path / "long.chain").stat().st_size < 2 * len(texts[0].encode()), (
        "after round 0 the chain stores what changed, not whole outputs"
    )
    assert [long_chain.get(n).output for n in (0, 17, 39)] == [texts[0], texts[17], texts[39]]

    drafts = [
        LESSON_DRAFT + "\n",
        "- Paris is the capital of France\n- Mt Everest is in Europe\n- Water boils at 100C\n",
        "- Paris is the capital of France\n- Mt Everest is in Asia\n- Water boils at 100C\n",
        "- Paris is the capital of France\n- Mt Everest is in Asia\n- Water boils at 100C at sea level\n",
    ]
    log_path = tmp_path / "damaged.chain"
    log = RevisionChain(log_path)
    for draft in drafts[:-1]:
        log.append(draft, "")
    log.append(drafts[-1], "verifier: ok")
    raw = log_path.read_bytes()
    assert raw.count(b"Asia") == 1, "a changed line is stored once, as readable text"
    log_path.write_bytes(raw.replace(b"Asia", b"Asja"))
    damaged = RevisionChain(log_path)
    assert [damaged.get(n).output for n in (0, 1)] == drafts[:2], "rounds before the damage still read back"
    assert all(raises(CorruptChain, damaged.get, n) for n in (2, 3)), (
        "a damaged record raises CorruptChain instead of returning different text"
    )
    log_path.write_bytes(raw.replace(b"Germany", b"Germeny"))
    assert raises(CorruptChain, RevisionChain(log_path).get, 0), (
        "a damaged record raises CorruptChain instead of returning different text"
    )
    log_path.write_bytes(raw.replace(b"verifier: ok", b"verifier: OK"))
    assert raises(CorruptChain, RevisionChain(log_path).get, 3), "a damaged critique raises CorruptChain too"


class Facts:
    """A stand-in for search: claims it can confirm, and wrong claims with what it found instead."""

    def __init__(self, true: list[str], wrong: dict[str, str], down: bool = False) -> None:
        self.true = {normalize_claim(claim) for claim in true}
        self.wrong = {normalize_claim(claim): found for claim, found in wrong.items()}
        self.down = down
        self.calls: list[list[str]] = []

    def __call__(self, claims: list[str]) -> list[Check]:
        self.calls.append(list(claims))
        if self.down:
            raise ToolUnavailable("search timed out")
        answers = []
        for claim in claims:
            key = normalize_claim(claim)
            if key in self.true:
                answers.append(Check("supported", "found in reference data"))
            elif key in self.wrong:
                answers.append(Check("contradicted", f"reference: {self.wrong[key]}"))
            else:
                answers.append(Check("unknown", "not in reference data"))
        return answers


class Calculator:
    """A stand-in calculator that knows the value of every expression these tests use."""

    def __init__(self, values: dict[str, str], down: bool = False) -> None:
        self.values = values
        self.down = down
        self.calls: list[list[str]] = []

    def __call__(self, claims: list[str]) -> list[Check]:
        self.calls.append(list(claims))
        if self.down:
            raise ToolUnavailable("calculator offline")
        answers = []
        for claim in claims:
            expression, _, stated = (part.strip() for part in claim.partition("="))
            value = self.values.get(expression)
            if value is None:
                answers.append(Check("unknown", f"cannot evaluate {expression!r}"))
            else:
                answers.append(Check("supported" if stated == value else "contradicted", f"{expression} = {value}"))
        return answers


FACTS = {
    "true": ["Paris is the capital of France", "Mt Everest is in Asia", "Water boils at 100C at sea level"],
    "wrong": {
        "Mt Everest is in Europe": "Mt Everest is in Asia",
        "The sun orbits the earth": "the earth orbits the sun",
    },
}
VALUES = {"17 * 23": "391", "12 * 12": "144", "2 ** 10": "1024"}
CLAIMS = (
    "- Paris is the capital of France\n- 17 * 23 = 391\n- Mt Everest is in Europe\n"
    "- 12 * 12 = 154\n- Water boils at 100C at sea level"
)
CHECKED = CLAIMS.replace("Europe", "Asia").replace("154", "144")


@pytest.mark.skip("Part 3")
def test_claim_verification() -> None:
    """CRITIC with tools: each claim goes to the tool for its kind, and the loop knows when to hand over."""
    facts, calc = Facts(**FACTS), Calculator(VALUES)
    critique = verify_claims(CLAIMS, {"fact": facts, "math": calc})
    assert [(f.bullet, f.kind, f.status) for f in critique.findings] == [
        (1, "fact", "supported"),
        (2, "math", "supported"),
        (3, "fact", "contradicted"),
        (4, "math", "contradicted"),
        (5, "fact", "supported"),
    ], "one finding per bullet, in bullet order"
    assert (facts.calls, calc.calls) == (
        [["Paris is the capital of France", "Mt Everest is in Europe", "Water boils at 100C at sea level"]],
        [["17 * 23 = 391", "12 * 12 = 154"]],
    ), "each tool gets one call per draft, with its claims in bullet order"
    assert critique.text() == (
        "bullet 3 contradicted: reference: Mt Everest is in Asia\nbullet 4 contradicted: 12 * 12 = 144"
    ), "the critique quotes what each tool found"

    offline = verify_claims(CHECKED, {"fact": Facts(**FACTS), "math": Calculator(VALUES, down=True)})
    assert [(f.bullet, f.status, f.evidence) for f in offline.findings if f.kind == "math"] == [
        (2, "unverified", "calculator offline"),
        (4, "unverified", "calculator offline"),
    ] and not offline.passed, "a claim whose tool is down is unverified, never supported"
    facts, calc = Facts(**FACTS), Calculator(VALUES)
    prose = verify_claims("- The Danube flows through ten countries\n- 2 ** 10 = 1024", {"fact": facts})
    assert [(f.status, f.evidence) for f in prose.findings] == [
        ("unverified", "not in reference data"),
        ("unverified", "no math tool"),
    ], "a claim no tool confirms is unverified"
    verify_claims("- Paris is the capital of France", {"fact": facts, "math": calc})
    assert calc.calls == [], "a tool with nothing to check is not called"

    model = Scripted([CLAIMS, CHECKED])
    outcome = refine_until_verified(WORLD, model, {"fact": Facts(**FACTS), "math": Calculator(VALUES)})
    assert (outcome.status, outcome.reason) == ("passed", "") and [
        (a.iteration, a.output, a.critique, a.passed, a.grounded) for a in outcome.history
    ] == [
        (1, CLAIMS, critique.text(), False, True),
        (2, CHECKED, "all claims supported", True, True),
    ], "evaluate, optimize, evaluate again"
    assert model.refines == [(critique.text(), [CLAIMS])], "the optimizer gets the critique and the history"

    model = Scripted([CHECKED])
    offline_tools = {"fact": Facts(**FACTS), "math": Calculator(VALUES, down=True)}
    outcome = refine_until_verified(WORLD, model, offline_tools, max_rounds=1)
    assert (outcome.status, outcome.reason, len(outcome.history), model.refines) == (
        "escalated",
        "unverified: bullets 2, 4",
        1,
        [],
    ), "refining cannot fix a claim no tool could check: hand it to a person"
    model = Scripted([CLAIMS, CHECKED])
    outcome = refine_until_verified(WORLD, model, {"fact": Facts(**FACTS), "math": Calculator(VALUES, down=True)})
    assert (outcome.status, outcome.reason, len(outcome.history)) == ("escalated", "unverified: bullets 2, 4", 2), (
        "a contradicted claim is still worth a refine"
    )

    facts = Facts(**FACTS)
    other = CLAIMS.replace("Paris is the capital of France", "The sun orbits the earth")
    model = Scripted([CLAIMS, other, CLAIMS])
    outcome = refine_until_verified(WORLD, model, {"fact": facts, "math": Calculator(VALUES)})
    assert (outcome.status, outcome.reason, len(outcome.history), len(facts.calls)) == (
        "escalated",
        "no progress: round 3 repeats round 1",
        2,
        2,
    ), "an output the loop has already verified is not verified again"
    drafts = [CLAIMS.replace("154", value) for value in ("154", "155", "156", "157")]
    model = Scripted(drafts)
    outcome = refine_until_verified(WORLD, model, {"fact": Facts(**FACTS), "math": Calculator(VALUES)})
    assert (outcome.status, outcome.reason, len(outcome.history), len(model.refines)) == (
        "escalated",
        "budget: round 3 of 3",
        3,
        2,
    ), "after max_rounds rounds a person takes over"


def sse_events(frames: list[str]) -> list[tuple[str, dict]]:
    """Parse what guard_stream yields the way an SSE client would, one event per frame."""
    events = []
    for frame in frames:
        assert frame.endswith("\n\n"), f"each event ends with a blank line: {frame!r}"
        lines = re.split(r"\r\n|\r|\n", frame[:-2])
        assert len(lines) == 2 and lines[0].startswith("event: ") and lines[1].startswith("data: "), (
            f"an event is one event line and one data line: {frame!r}"
        )
        events.append((lines[0][len("event: ") :], json.loads(lines[1][len("data: ") :])))
    return events


def token_stream(pieces: list[str], pulled: list[str], closed: list[bool]):
    async def stream():
        try:
            for piece in pieces:
                pulled.append(piece)
                yield piece
        finally:
            closed.append(True)

    return stream()


def no_wrong_facts(seen: list[str]):
    """A guardrail in the CRITIC style: it rejects empty bullets and known wrong facts."""

    def guardrail(line: str) -> None:
        seen.append(line)
        claim = normalize_claim(line)
        if not claim:
            raise OutputGuardrailTripwireTriggered("empty bullet")
        if claim in KNOWN_WRONG_FACTS:
            raise OutputGuardrailTripwireTriggered(f"'{claim}' contradicts reference data")

    return guardrail


def relay(pieces: list[str], guardrail) -> tuple[list[tuple[str, dict]], int, bool]:
    """Run guard_stream to its end: the events, how many pieces it pulled, whether it closed the source."""

    async def run():
        pulled: list[str] = []
        closed: list[bool] = []
        frames = [frame async for frame in guard_stream(token_stream(pieces, pulled, closed), guardrail)]
        return frames, len(pulled), bool(closed)

    frames, pulled, closed = asyncio.run(run())
    return sse_events(frames), pulled, closed


@pytest.mark.skip("Part 4")
def test_stream_guardrail() -> None:
    """A line reaches the client only after the guardrail passes it, and a tripwire ends the stream."""
    text = "- Paris is the capital of France\r\n- Mt Everest is in Asia \n- Wasser kocht bei 100 °C"
    expected = [
        ("delta", {"text": "- Paris is the capital of France\r\n"}),
        ("delta", {"text": "- Mt Everest is in Asia \n"}),
        ("delta", {"text": "- Wasser kocht bei 100 °C"}),
        ("done", {"lines": 3}),
    ]
    tricky = ["- Paris is the", " capital of France\r", "\n- Mt Everest is in Asia \n- Wa", "", "sser kocht bei 100 °C"]
    for pieces in ([text], list(text), tricky):
        seen: list[str] = []
        events, _, _ = relay(pieces, no_wrong_facts(seen))
        assert events == expected, f"the same events however the tokens are split, e.g. {pieces[:3]}"
        assert seen == ["- Paris is the capital of France", "- Mt Everest is in Asia ", "- Wasser kocht bei 100 °C"], (
            "the guardrail checks each line once, without its line break"
        )

    pieces = [
        "- Paris is the capital of France\n- Mt Everest",
        " is in Europe\n- Water boils at 100C\n- Ice",
        " floats\n",
    ]
    events, pulled, closed = relay(pieces, no_wrong_facts([]))
    assert events == [
        ("delta", {"text": "- Paris is the capital of France\n"}),
        ("tripwire", {"line": 2, "reason": "'mt everest is in europe' contradicts reference data"}),
    ], "the tripwire is the last event: the rejected line and everything after it stay unsent"
    assert (pulled, closed) == (2, True), "a tripwire stops pulling tokens and closes the token stream"

    events, _, _ = relay(["- Paris is the capital of France\n- The sun orbits", " the earth"], no_wrong_facts([]))
    assert events[1:] == [
        ("tripwire", {"line": 2, "reason": "'the sun orbits the earth' contradicts reference data"}),
    ], "the last line is checked too, even without a line break"
    seen = []
    events, _, _ = relay(["- Mt Everest is in Asia\n", "- Water boils at 100C\n"], no_wrong_facts(seen))
    assert (events[-1], len(seen)) == (("done", {"lines": 2}), 2), "a final line break does not start another line"
    seen = []
    relay(["- Water boils\rat 100C\n"], no_wrong_facts(seen))
    assert seen == ["- Water boils\rat 100C"], "only LF ends a line; a bare CR is part of the line"

    async def first_then_disconnect():
        pulled: list[str] = []
        closed: list[bool] = []
        source = token_stream(["- Paris is", " the capital of France\n- Mt", " Everest is in Asia\n"], pulled, closed)
        agen = guard_stream(source, no_wrong_facts([]))
        first = await agen.__anext__()
        count = len(pulled)
        await agen.aclose()
        return first, count, bool(closed)

    first, count, closed = asyncio.run(first_then_disconnect())
    assert (sse_events([first]), count) == ([("delta", {"text": "- Paris is the capital of France\n"})], 2), (
        "each line is sent as soon as the guardrail passes it"
    )
    assert closed, "a client that disconnects closes the token stream"

    def broken(line: str) -> None:
        raise KeyError("reference store not loaded")

    assert raises(KeyError, relay, ["- Paris is the capital of France\n"], broken), (
        "a guardrail that crashes is an error, not a tripwire"
    )


OUTLINE = (
    "- Geography:\n"
    "  - Paris is the capital of France\n"
    "  - Mt Everest is in Europe\n"
    "  - Rivers which flow through many European countries:\n"
    "\n"
    "- Science\n"
    "  - The sun orbits the earth\n"
    "  - Water boils at 100C at sea level\n"
    "    - High up a mountain it boils at a lower temperature\n"
    "    - Ice floats on water as it is less dense\n"
    "- The Danube flows through ten countries on its way to the Black Sea\n"
    "  - It rises in the Black Forest and ends in a delta in Romania\n"
    "- Rome is the capital of Italy\n"
)
OUTLINE_CRITIQUE = [
    "1: sub-bullets failed: 1.2, 1.3",
    "1.2: contradicts reference data",
    "1.3: not under 50 chars; empty sub-list",
    "2: sub-bullets failed: 2.1, 2.2",
    "2.1: contradicts reference data",
    "2.2: sub-bullets failed: 2.2.1",
    "2.2.1: not under 40 chars",
    "3: not under 60 chars; sub-bullets failed: 3.1",
    "3.1: not under 50 chars",
]


def error_line(text: str):
    """The line number a ValueError from check_outline names, or None when there is no error."""
    try:
        check_outline(text)
    except ValueError as exc:
        found = re.search(r"\bline (\d+)\b", str(exc))
        return int(found.group(1)) if found else str(exc)
    return None


@pytest.mark.skip("Part 5")
def test_outline_critique() -> None:
    """Nested bullets: a length limit per level, failures climb to every ancestor, paths say where."""
    critique = check_outline(OUTLINE)
    assert sorted(critique) == sorted(OUTLINE_CRITIQUE), (
        "every failing bullet is named by its path, with its own problems and its failing sub-bullets"
    )
    assert critique == OUTLINE_CRITIQUE, "the critique lists bullets in document order"
    assert check_outline(OUTLINE.replace("  ", "\t")) == OUTLINE_CRITIQUE, (
        "an outline indented with tabs reads like one indented with spaces"
    )
    assert check_outline("- Paris is the capital of France\n  - Mt Everest is in Asia\n") == [], (
        "a clean outline has no critique"
    )
    malformed = {
        "- Geography:\n\t- Paris is the capital of France\n  - Mt Everest is in Asia\n": 3,
        "- Geography:\n \t- Paris is the capital of France\n": 2,
        "- Science\n  - Water boils at 100C\n\n      - Ice floats on water\n": 4,
        "  - Paris is the capital of France\n": 1,
        "- Science\nWater boils at 100C\n": 2,
        "- Science\n - Water boils at 100C\n": 2,
    }
    assert {text: error_line(text) for text in malformed} == malformed, (
        "a malformed outline is a ValueError naming its line"
    )
