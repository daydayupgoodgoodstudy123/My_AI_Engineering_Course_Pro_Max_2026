import asyncio
import copy
import json
import time
from fractions import Fraction

import pytest
from cotballot.ballot import normalize_answer, tally_samples
from cotballot.bank import ExampleBank
from cotballot.examples import ExampleSelector, build_cot_prompt, extract_answer
from cotballot.service import ExampleService
from cotballot.stream import stream_ballots
from cotballot.trace import trace_report


def example(example_id, question, reasoning, answer, label="arithmetic", difficulty=0):
    return {"id": example_id, "question": question, "reasoning": reasoning,
            "answer": answer, "label": label, "difficulty": difficulty}


def collect(generator):
    async def drain():
        return [item async for item in generator]
    return asyncio.run(drain())


def thought(node_id, text, score, generation, evaluation, children=None):
    return {"id": node_id, "text": text, "score": score, "generation_tokens": generation,
            "evaluation_tokens": evaluation, "children": [] if children is None else children}


@pytest.mark.skip("Part 1")
def test_worked_example_pipeline() -> None:
    """Selected worked records reach the prompt intact, with explicit final answers and efficient query selection."""
    corpus = [example("sale", "apples store sell", "Start with 5 apples; sell 2, leaving 3.", "3", "money", 2),
              example("letter", "letters pages year", "Two letters with 4 pages each use 8 pages.", "8", "length", 1),
              example("remain", "apples store remaining", "Four apples minus one leaves three.", "3", "money", 0)]
    saved = copy.deepcopy(corpus)
    selector = ExampleSelector(corpus)
    service = ExampleService(selector)
    response = "Begin with 48 and subtract 16.\nThe answer is: $-1,200.50.\n\n"
    preview = service.preview("apples store sell", response, 2, 2)
    assert preview["answer"] == "$-1,200.50", "read the explicit final answer, not an intermediate number"
    assert preview["user"] == (
        "Q: apples store sell\nA: Start with 5 apples; sell 2, leaving 3. The answer is 3.\n\n"
        "Q: letters pages year\nA: Two letters with 4 pages each use 8 pages. The answer is 8.\n\n"
        "Q: apples store sell\nA:"
    ), "few-shot CoT includes every selected worked reasoning"
    assert preview["example_ids"] == ["sale", "letter"], "cover labels before filling repeated labels"
    assert "last line" in preview["system"] and "The answer is [number]" in preview["system"]
    assert service.preview("apples store sell", "The answer is 0", 0)["user"] == "Q: apples store sell\nA:", "zero examples means zero demonstrations"
    assert build_cot_prompt("q", corpus, 0)[1] == "Q: q\nA:"
    assert len(selector.select("q", None)) == 3
    assert len(selector.select("q", 100)) == 3
    with pytest.raises(ValueError):
        selector.select("q", -1)

    words = " ".join(f"w{i}" for i in range(64))
    large = [example(str(i), words + f" item{i}", "Worked step.", str(i), f"label{i % 13}", i % 7)
             for i in range(6000)]
    large_selector = ExampleSelector(large)
    question = " ".join(f"w{i}" for i in range(32))
    start = time.perf_counter()
    chosen = large_selector.select(question, 160, 3)
    assert time.perf_counter() - start < 0.075, "example selection should stay responsive for a large corpus"
    assert len(chosen) == 160 and len({row["id"] for row in chosen}) == 160, "selection keeps every requested distinct position"
    assert [row["id"] for row in chosen[:13]] == [str(3 + 7 * i) for i in range(13)], "fast selection retains diversity and difficulty order"

    assert selector.select("letters pages year", 2, 1)[0]["id"] == "letter", "a changed query gets its own ranking"
    tied = ExampleSelector([example("z", "one", "r", "1", "same", 3), example("a", "one", "r", "1", "same", 1)])
    assert [row["id"] for row in tied.select("one", 2, 2)] == ["z", "a"], "difficulty ties preserve corpus order"
    selected = selector.select("apples store sell", 1, 2)
    selected[0]["reasoning"] = "changed outside"
    corpus[0]["question"] = "changed caller corpus"
    assert selector.select("apples store sell", 1, 2)[0] == saved[0], "selector owns its records and returns independent examples"
    assert extract_answer("The answer is 5\nA later arithmetic check uses 99") is None, "only the terminal marked line is an answer"
    assert extract_answer("we used 12 and got 8") is None
    assert extract_answer("\n#### +024.0.\n") == "+024.0"
    assert extract_answer("THE ANSWER IS .5") == ".5"
    assert extract_answer("") is None


@pytest.mark.skip("Part 2")
def test_example_bank_roundtrip(tmp_path) -> None:
    """Worked examples retain exact textual answers and corpus order across updates and reopening."""
    path = str(tmp_path / "examples.sqlite3")
    rows = [example("z", "题目\r\nwith newline", "First step.\r\nSecond step ✓", "+00024.00", "", 0),
            example("a", "divide one", "Divide into three equal parts.", "1/3", "fraction", 2),
            example("q", "finite decimal", "Keep the displayed precision.", "0.333333333333333333333333333333", "fraction", 9),
            example("large", "large integer", "Keep every digit.", "9007199254740993", "integer", 4)]
    bank = ExampleBank(path)
    for row in rows:
        bank.put(row)
    assert bank.get("z") == rows[0], "a worked example round-trips without numeric coercion"
    changed = dict(rows[0], question="revised question", answer="-1,234.50", label="revision", difficulty=3)
    bank.put(changed)
    rows[0] = changed
    assert bank.examples() == rows, "updating an example preserves its original corpus position"
    with pytest.raises(KeyError):
        bank.get("unknown")
    with pytest.raises(ValueError):
        bank.put(dict(changed, answer=24.0))
    with pytest.raises(ValueError):
        bank.put(dict(changed, difficulty=True))
    invalid_records = [dict(changed, difficulty=-1), dict(changed, unexpected="extra"),
                       {key: value for key, value in changed.items() if key != "label"}]
    for invalid in invalid_records:
        rejected = False
        try:
            bank.put(invalid)
        except ValueError:
            rejected = True
        assert rejected, "invalid corpus records are rejected before changing stored state"
    assert bank.get("z") == changed, "an invalid update leaves the stored example unchanged"
    bank.close()
    reopened = ExampleBank(path)
    assert reopened.examples() == rows, "all worked fields and corpus order survive reopening"
    assert reopened.examples("fraction") == rows[1:3], "filter examples by exact label"
    assert reopened.examples("") == [], "an empty label is a real filter"
    assert reopened.get("a")["answer"] != reopened.get("q")["answer"], "rational and finite decimal answers retain their original spelling"
    outside = reopened.get("z")
    outside["reasoning"] = "caller edit"
    assert reopened.get("z") == changed
    reopened.close()


@pytest.mark.skip("Part 3")
def test_self_consistency_ballot() -> None:
    """Exact numeric aliases vote together, invalid answers abstain, and confidence uses valid samples."""
    accepted = {"+024": Fraction(24), "24.00": Fraction(24), "-0": Fraction(0),
                "1,234.50": Fraction(2469, 2), "$-.5": Fraction(-1, 2),
                "-2/4": Fraction(-1, 2), "1/3": Fraction(1, 3), "  .125  ": Fraction(1, 8)}
    for text, number in accepted.items():
        assert normalize_answer(text) == number, "normalize valid numeric answers exactly"
    for invalid in (None, "", "NaN", "Infinity", "1e3", "1_000", "12,34", "1,23,456", "2.", "2/0", "1/-2", "1.5/3", "2 /3", "24 apples", "--1", "$ 1", "1,23/4", "1/2,00"):
        assert normalize_answer(invalid) is None, "invalid finite-grammar answers abstain"
    assert normalize_answer("9007199254740993") == Fraction(9007199254740993), "large integers do not pass through float"
    finite = "0.333333333333333333333333333333"
    assert normalize_answer(finite) != normalize_answer("1/3"), "a finite decimal is not an exact repeating fraction"
    reasonings = ["48 minus 16 is 32.\nThe answer is: 24", "The answer is +024.0", "The answer is 24.00.",
                  "The answer is 25", "Intermediate number 999 only", "The answer is NaN"]
    saved = list(reasonings)
    result = tally_samples(reasonings)
    assert result == {"winner": "24", "confidence": 0.75, "attempted": 6, "valid": 4,
                      "raw_answers": ["24", "+024.0", "24.00", "25", None, "NaN"],
                      "answers": ["24", "24", "24", "25", None, None],
                      "votes": {"24": 3, "25": 1}, "reasonings": reasonings}, (
        "numeric aliases share votes and invalid samples stay outside confidence"
    )
    assert reasonings == saved
    tie = tally_samples(["The answer is 10", "The answer is 2"])
    assert tie["winner"] == "2" and list(tie["votes"]) == ["2", "10"], "ties and vote order use numeric value, not text or encounter order"
    zeros = tally_samples(["The answer is -0", "The answer is 0.0", "The answer is 1"])
    assert zeros["winner"] == "0" and zeros["valid"] == 3, "zero is a valid ballot value"
    distinct = tally_samples(["The answer is 9007199254740993", "The answer is 9007199254740992"])
    assert distinct["votes"] == {"9007199254740992": 1, "9007199254740993": 1}
    fraction = tally_samples(["The answer is .5", "The answer is 2/4", "The answer is 1"])
    assert fraction["winner"] == "1/2" and fraction["confidence"] == pytest.approx(2 / 3)
    assert tally_samples([]) == {"winner": None, "confidence": 0.0, "attempted": 0, "valid": 0,
                                 "raw_answers": [], "answers": [], "votes": {}, "reasonings": []}
    assert tally_samples(["no answer", "The answer is 1/0"])["winner"] is None
    assert tally_samples(["no answer"])["confidence"] == 0.0
    assert tally_samples(["A quotation says The answer is 2", "prefix #### 3"])["valid"] == 0, (
        "only a complete terminal marked line contributes a vote"
    )


@pytest.mark.skip("Part 4")
def test_stream_running_ballots() -> None:
    """Each arriving reasoning sample produces a complete NDJSON event with the current ballot."""
    samples = [{"sample_id": 's1,"中文"', "text": "First 48.\nThe answer is 10"},
               {"sample_id": "s2", "text": "10 appears, but no final marker."},
               {"sample_id": "s3", "text": "The answer is 2"}]
    async def source():
        for sample in samples:
            yield sample
    chunks = collect(stream_ballots(source()))
    assert all(chunk.endswith("\n") and not chunk.endswith("\n\n") for chunk in chunks), "each ballot event has one NDJSON terminator"
    events = [json.loads(line) for line in "".join(chunks).splitlines()]
    assert events == [
        {"sample_id": 's1,"中文"', "text": "First 48.\nThe answer is 10", "index": 1, "answer": "10", "attempted": 1, "valid": 1, "winner": "10", "confidence": 1.0, "votes": {"10": 1}},
        {"sample_id": "s2", "text": "10 appears, but no final marker.", "index": 2, "answer": None, "attempted": 2, "valid": 1, "winner": "10", "confidence": 1.0, "votes": {"10": 1}},
        {"sample_id": "s3", "text": "The answer is 2", "index": 3, "answer": "2", "attempted": 3, "valid": 2, "winner": "2", "confidence": 0.5, "votes": {"2": 1, "10": 1}},
    ], "emit attempted samples with cumulative valid-sample voting"
    pulled, closed = [], []
    async def probe():
        try:
            for i in range(100):
                pulled.append(i)
                yield samples[0]
        finally:
            closed.append(True)
    async def first_event():
        generator = stream_ballots(probe())
        first = await generator.__anext__()
        assert pulled == [0], "emit a sample event before pulling another sample"
        await generator.aclose()
        assert closed == [True], "close the sample source before client close returns"
        return first
    assert json.loads(asyncio.run(first_event()))["index"] == 1
    async def empty():
        if False:
            yield {}
    assert collect(stream_ballots(empty())) == []


@pytest.mark.skip("Part 5")
def test_thought_trace_accounting() -> None:
    """All supplied terminal paths retain ancestry while global usage counts shared thought nodes once."""
    shared = thought("shared", "The answer is: +24.0", 0.8, 4, 2)
    wrong = thought("wrong", "The answer is 25", 0.2, 5, 1)
    left = thought("left", "Explore 48 minus 16.", 0.6, 10, 3, [shared, wrong])
    right = thought("right", "The answer is 24", 0.9, 7, 3, [shared])
    pruned = thought("pruned", "Try the number 100.", 0.0, 2, 1)
    roots = [left, right, pruned]
    saved = copy.deepcopy(roots)
    report = trace_report(roots, "24.00")
    assert report == {"terminals": [
        {"path": ["left", "shared"], "answer": "24", "score": 0.8, "calls": 4, "tokens": 19, "selected": True},
        {"path": ["left", "wrong"], "answer": "25", "score": 0.2, "calls": 4, "tokens": 19, "selected": False},
        {"path": ["right"], "answer": "24", "score": 0.9, "calls": 2, "tokens": 10, "selected": True},
        {"path": ["right", "shared"], "answer": "24", "score": 0.8, "calls": 4, "tokens": 16, "selected": True},
    ], "totals": {"nodes": 5, "calls": 10, "tokens": 38}}, "audit every path but bill each supplied thought id once"
    assert roots == saved, "trace inspection leaves the supplied graph unchanged"
    assert trace_report([], None) == {"terminals": [], "totals": {"nodes": 0, "calls": 0, "tokens": 0}}
    assert trace_report([shared])["terminals"][0]["selected"] is False
    zero = thought("zero", "The answer is -0", 0.1, 0, 0)
    assert trace_report([zero], "0")["terminals"][0]["selected"] is True
    cycle = thought("cycle", "partial", 0.5, 1, 1)
    cycle["children"].append(cycle)
    with pytest.raises(ValueError, match="cycle"):
        trace_report([cycle])
    with pytest.raises(ValueError, match="conflicting"):
        trace_report([shared, dict(shared, generation_tokens=99)])
    with pytest.raises(ValueError):
        trace_report([dict(shared, score=float("nan"))])
    with pytest.raises(ValueError):
        trace_report([dict(shared, evaluation_tokens=-1)])
    with pytest.raises(ValueError):
        trace_report([shared], "not numeric")
    invalid_nodes = [dict(shared, score=-0.1), dict(shared, score=1.1),
                     dict(shared, generation_tokens=True), dict(shared, evaluation_tokens=False),
                     dict(shared, generation_tokens=-1), dict(shared, evaluation_tokens=1.5)]
    for invalid in invalid_nodes:
        rejected = False
        try:
            trace_report([invalid])
        except ValueError:
            rejected = True
        assert rejected, "trace scores and token counts obey their declared bounds"
