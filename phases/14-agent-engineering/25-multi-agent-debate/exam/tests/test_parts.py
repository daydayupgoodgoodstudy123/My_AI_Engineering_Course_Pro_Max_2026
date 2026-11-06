import asyncio
import csv
import io
import math
import struct
import time
from collections import Counter, defaultdict

import pytest
from debate.engine import Ask, Reply, debate
from debate.live import live_debate
from debate.protocol import Debater, make_debater, run_debate
from debate.topology import analyze
from debate.transcript import MAGIC, Transcript, Turn


def scripted(name: str, answers: list[str]) -> Debater:
    """A lesson-style debater that gives answers[i] on its i-th call, whatever it reads."""
    calls = iter(answers)
    return Debater(name, lambda question, votes: next(calls))


def full_mesh(names: list[str]) -> dict[str, list[str]]:
    return {name: [peer for peer in names if peer != name] for name in names}


@pytest.mark.skip("Part 1")
def test_lesson_runner() -> None:
    """The lesson's runner must count critique ops as the lesson does, and scale."""
    five = [
        ("alpha", "Lisbon", {}),
        ("beta", "Madrid", {"capital": "Lisbon"}),
        ("gamma", "Porto", {"capital": "Lisbon"}),
        ("delta", "Faro", {}),
        ("eps", "Lisbon", {"capital": "Porto"}),
    ]
    _, _, ops = run_debate([make_debater(*s) for s in five], "capital", 3, "full_mesh")
    assert ops == 60, "full mesh, N = 5, R = 3: 5 debaters x 4 peers x 3 rounds"
    answer, converged, ops = run_debate([make_debater(*s) for s in five], "capital", 3, "star")
    assert ops == 12, "star, N = 5, R = 3: the spokes read only the hub, 12 critique ops"
    assert (answer, converged) == ("Lisbon", -1), "debaters[0] is the hub"

    seen: dict[str, Counter] = {}

    def recorder(name: str, opening: str) -> Debater:
        def drift(question: str, votes: Counter) -> str:
            if votes:
                seen[name] = Counter(votes)
            return opening

        return Debater(name, drift)

    openings = ["x", "x", "y", "y", "z"]
    run_debate([recorder(f"r{i}", a) for i, a in enumerate(openings)], "capital", 1, "full_mesh")
    assert seen == {
        "r0": Counter(x=1, y=2, z=1),
        "r1": Counter(x=1, y=2, z=1),
        "r2": Counter(x=2, y=1, z=1),
        "r3": Counter(x=2, y=1, z=1),
        "r4": Counter(x=2, y=2),
    }, "a debater counts its peers' answers, never its own"
    seen.clear()
    run_debate([recorder(f"r{i}", a) for i, a in enumerate(openings)], "capital", 1, "star")
    assert seen == dict.fromkeys(["r1", "r2", "r3", "r4"], Counter(x=1)), "the hub reads no one"

    four = [
        ("ana", "Porto", {}),
        ("ben", "Lisbon", {"capital": "Madrid"}),
        ("cy", "Madrid", {}),
        ("dee", "Faro", {"capital": "Porto"}),
    ]
    for seating in (four, four[::-1]):
        debaters = [make_debater(*s) for s in seating]
        assert run_debate(debaters, "capital", 2, "full_mesh") == ("Madrid", -1, 24), (
            "a tie goes to the alphabetically first answer, whatever the seating"
        )
    three = [("ivo", "Porto", {}), ("jon", "Lisbon", {}), ("kai", "Madrid", {})]
    for seating in (three, three[::-1]):
        debaters = [make_debater(*s) for s in seating]
        assert run_debate(debaters, "capital", 1, "full_mesh") == ("Lisbon", -1, 6), (
            "a tie among a debater's peers also goes to the alphabetically first answer"
        )

    def panel() -> list[Debater]:
        return [
            scripted("a", ["Porto", "Lisbon", "Lisbon", "Lisbon", "Lisbon"]),
            scripted("b", ["Faro", "Lisbon", "Madrid", "Lisbon", "Lisbon"]),
            scripted("c", ["Porto", "Lisbon", "Lisbon", "Lisbon", "Lisbon"]),
        ]

    assert run_debate(panel(), "capital", 4, "full_mesh")[1] == 3, (
        "converged_round is where the final agreement started"
    )
    assert run_debate(panel(), "capital", 2, "full_mesh")[:2] == ("Lisbon", -1), (
        "debaters who disagree at the end have not converged"
    )

    crowd = [
        make_debater(f"d{i}", ("Porto", "Lisbon", "Madrid")[i % 3], {"capital": "Faro"} if i % 7 == 0 else {})
        for i in range(5000)
    ]
    start = time.perf_counter()
    result = run_debate(crowd, "capital", 1, "full_mesh")
    assert time.perf_counter() - start < 0.1, "a full-mesh round should be fast for 5000 debaters"
    assert result == ("Lisbon", -1, 5000 * 4999)


@pytest.mark.skip("Part 2")
def test_transcript_roundtrip(tmp_path) -> None:
    """A debate transcript survives the binary file bit for bit."""
    roster = ["alpha", "beta", "gamma"] + [f"d{i}" for i in range(3, 20000)]
    turns = [
        Turn(0, 0, "Lisbon", 0.1 + 0.2, ()),
        Turn(0, 1, "São Paulo", 1 / 3, ()),
        Turn(0, 2, "東京\x00🙂", 5e-324, ()),
        Turn(1, 2, "", -0.0, (1, 0)),
        Turn(300, 19999, "Lisbon, again", 1.0, (16384, 0, 127, 128)),
    ]
    transcript = Transcript(roster)
    for turn in turns:
        transcript.add(turn)
    path = tmp_path / "debate.dbt"
    transcript.save(path)

    back = Transcript.load(path)
    assert back.roster == roster, "the roster round-trips in order"
    assert back.turns == turns, "every turn round-trips exactly"
    assert [struct.pack(">d", t.confidence) for t in back.turns] == [
        struct.pack(">d", t.confidence) for t in turns
    ], "confidences round-trip bit for bit"
    assert back.to_bytes() == path.read_bytes(), "a loaded transcript writes the same bytes"

    small = Transcript(["a", "b"])
    small.add(Turn(300, 1, "é", 0.5, (0,)))
    data = small.to_bytes()
    assert data == (
        MAGIC + b"\x02\x01a\x01b" + b"\x01" + b"\xac\x02\x01\x02\xc3\xa9" + struct.pack(">d", 0.5) + b"\x01\x00"
    ), "bytes follow the layout in the module docstring"

    for bad in (
        Turn(-1, 0, "x", 0.5, ()),
        Turn(0, 2, "x", 0.5, ()),
        Turn(0, -1, "x", 0.5, ()),
        Turn(0, 0, "x", 1.5, ()),
        Turn(0, 0, "x", math.nan, ()),
        Turn(1, 0, "x", 0.5, (0,)),
        Turn(1, 0, "x", 0.5, (1, 1)),
        Turn(1, 0, "x", 0.5, (2,)),
        Turn(1, 0, "x", 0.5, (-1,)),
    ):
        with pytest.raises(ValueError):
            small.add(bad)
    assert small.turns == [Turn(300, 1, "é", 0.5, (0,))] and small.to_bytes() == data, (
        "a refused turn is not stored"
    )

    for cut in range(len(data)):
        with pytest.raises(ValueError):
            Transcript.from_bytes(data[:cut])
    for damaged in (data + b"\x00", b"DBT\x02" + data[4:], data[:-1] + b"\x05"):
        with pytest.raises(ValueError):
            Transcript.from_bytes(damaged)


class Panel:
    """Scripted debaters for engine.debate. Every debater records the Asks it is sent."""

    def __init__(self) -> None:
        self.asks: dict[str, list[Ask]] = defaultdict(list)

    def debater(self, name: str, policy):
        def call(ask: Ask) -> Reply:
            self.asks[name].append(ask)
            return policy(ask)

        return call


def prefers(*choices: str, confidence: float = 0.5):
    """Opens with its first choice nobody has taken yet, then copies the first peer it reads."""

    def policy(ask: Ask) -> Reply:
        if ask.round == 0:
            return Reply(next((c for c in choices if c not in ask.taken), choices[0]), confidence)
        return Reply(ask.peers[0][1].answer, confidence)

    return policy


def by_round(*replies: Reply):
    return lambda ask: replies[ask.round]


@pytest.mark.skip("Part 3")
def test_sparse_debate() -> None:
    """Debate over any topology: distinct openings, synchronous rounds, weighted answers."""
    p = Panel()
    names = ["a", "b", "c"]
    ring = {"a": ["c"], "b": ["a"], "c": ["b"]}
    out = debate("capital", {n: p.debater(n, prefers("Porto", "Lisbon", "Madrid")) for n in names}, ring, 3)
    assert [p.asks[n][0].taken for n in names] == [(), ("Porto",), ("Porto", "Lisbon")], (
        "each opening is told the answers already proposed"
    )
    assert [[r[n].answer for n in names] for r in out.history] == [
        ["Porto", "Lisbon", "Madrid"],
        ["Madrid", "Porto", "Lisbon"],
        ["Lisbon", "Madrid", "Porto"],
        ["Porto", "Lisbon", "Madrid"],
    ], "critique rounds are synchronous: round r reads only round r - 1"
    assert p.asks["a"][1:3] == [
        Ask("capital", 1, Reply("Porto", 0.5), (("c", Reply("Madrid", 0.5)),)),
        Ask("capital", 2, Reply("Madrid", 0.5), (("c", Reply("Lisbon", 0.5)),)),
    ], "round r shows a debater its own reply and its peers' replies from round r - 1"
    assert out.converged_round is None and out.ops == [0, 3, 3, 3]
    assert out.answer == "Porto", "a full tie goes to the first supporter in roster order"

    p = Panel()
    out = debate(
        "capital",
        {
            "a": p.debater("a", by_round(Reply("Lisbon", 0.75), Reply("Porto", 0.75))),
            "b": p.debater("b", by_round(Reply("Lisbon", 0.5), Reply("Lisbon", 0.5))),
            "c": p.debater("c", prefers("Lisbon", "Porto", confidence=0.25)),
        },
        full_mesh(names),
        1,
    )
    assert p.asks["c"][0].taken == ("Lisbon",), "taken lists each answer once"
    assert out.history[0]["c"].answer == "Porto"
    assert {n: len(p.asks[n]) for n in names} == {"a": 2, "b": 2, "c": 2}, (
        "every debater is asked once per round"
    )
    assert out.weights == {"Porto": 0.75, "Lisbon": 0.75}, "weights come from the last round only"
    assert out.answer == "Lisbon", "a weight tie goes to the answer with more supporters"

    def collapse() -> dict:
        script = {
            "a": ["Madrid", "Madrid", "Madrid", "Lisbon", "Lisbon"],
            "b": ["Lisbon", "Madrid", "Lisbon", "Lisbon", "Lisbon"],
            "c": ["Porto", "Madrid", "Madrid", "Lisbon", "Lisbon"],
        }
        sure = {"a": 0.25, "b": 1.0, "c": 0.25}
        return {n: by_round(*(Reply(x, sure[n]) for x in answers)) for n, answers in script.items()}

    out = debate("capital", collapse(), full_mesh(names), 4, min_rounds=2)
    assert (out.converged_round, out.answer, len(out.history)) == (3, "Lisbon", 4), (
        "no early stop before min_rounds, then stop at the first agreement"
    )
    out = debate("capital", collapse(), full_mesh(names), 4)
    assert (out.converged_round, out.answer) == (1, "Madrid")
    out = debate("capital", collapse(), full_mesh(names), 2, min_rounds=2)
    assert (out.converged_round, out.answer, out.weights) == (None, "Lisbon", {"Madrid": 0.5, "Lisbon": 1.0}), (
        "the largest total confidence wins, even against more supporters"
    )
    agreed = {n: by_round(Reply("Lisbon", 0.5), Reply("Lisbon", 0.5)) for n in names}
    out = debate("capital", agreed, full_mesh(names), 3)
    assert (out.converged_round, len(out.history)) == (1, 2), "only a critique round can end the debate"

    p = Panel()
    stubborn = {n: p.debater(n, by_round(*(Reply(n, 1.0) for _ in range(3)))) for n in ["h1", "h2", "s1", "s2", "s3"]}
    hubs = {"h1": ["h2"], "h2": ["h1"], "s1": ["h1", "h2"], "s2": ["h2", "h1"], "s3": ["h1", "h2"]}
    assert debate("capital", stubborn, hubs, 2).ops == [0, 8, 8], "one op per peer read"
    assert [peer for peer, _ in p.asks["s2"][1].peers] == ["h2", "h1"], "peers come in reads order"

    with pytest.raises(ValueError):
        debate("capital", stubborn, {**hubs, "s3": ["s3"]}, 1)
    with pytest.raises(ValueError):
        debate("capital", stubborn, {**hubs, "s3": ["h3"]}, 1)
    with pytest.raises(ValueError):
        debate("capital", {**stubborn, "s3": by_round(Reply("x", 1.5))}, hubs, 1)


class LivePanel:
    """Async scripted debaters: answers[name][round]. Each call takes 10 ms, or 2 s for the
    (name, round) pairs in hang. Records calls in flight, cancellations and Asks."""

    def __init__(self, answers: dict[str, list[str]], hang=()) -> None:
        self.answers = answers
        self.hang = set(hang)
        self.in_flight = 0
        self.peak: dict[int, int] = {}
        self.calls: list[tuple[str, int]] = []
        self.cancelled: list[tuple[str, int]] = []
        self.asks: dict[str, list[Ask]] = defaultdict(list)

    def debaters(self) -> dict:
        return {name: self._debater(name) for name in self.answers}

    def _debater(self, name: str):
        async def call(ask: Ask) -> Reply:
            self.calls.append((name, ask.round))
            self.asks[name].append(ask)
            self.in_flight += 1
            self.peak[ask.round] = max(self.peak.get(ask.round, 0), self.in_flight)
            try:
                await asyncio.sleep(2.0 if (name, ask.round) in self.hang else 0.01)
                return Reply(self.answers[name][ask.round], 0.5)
            except asyncio.CancelledError:
                self.cancelled.append((name, ask.round))
                raise
            finally:
                self.in_flight -= 1

        return call


def parse(chunks: list[str]) -> list[list[str]]:
    for chunk in chunks:
        assert chunk.endswith("\n") and len(list(csv.reader(io.StringIO(chunk)))) == 1, (
            "each string is one CSV record"
        )
    return list(csv.reader(io.StringIO("".join(chunks))))


@pytest.mark.skip("Part 4")
def test_live_rounds() -> None:
    """Each round's calls run concurrently, and every round is reported as one CSV record."""
    names = ["alpha", "beta", "gamma"]
    panel = LivePanel({
        "alpha": ["Lisbon", "Lisbon", "Lisbon", "Lisbon"],
        "beta": ["Madrid, Spain", 'Porto "Invicta"', "Lisbon", "Lisbon"],
        "gamma": ['Porto "Invicta"', 'Porto "Invicta"', "Lisbon", "Lisbon"],
    })

    async def run(panel: LivePanel, timeout_s: float, watch=None) -> list[str]:
        chunks = []
        async for chunk in live_debate("capital", panel.debaters(), full_mesh(names), 3, timeout_s):
            chunks.append(chunk)
            if watch:
                watch(chunk)
        return chunks

    rows = parse(asyncio.run(run(panel, 1.0)))
    assert rows[0] == ["round", "alpha", "beta", "gamma", "agree_ratio", "ops", "elapsed_ms"]
    assert all(row[-1].isdigit() for row in rows[1:]), "elapsed_ms is whole milliseconds"
    assert [row[:-1] for row in rows[1:]] == [
        ["0", "Lisbon", "Madrid, Spain", 'Porto "Invicta"', "0.333", "0"],
        ["1", "Lisbon", 'Porto "Invicta"', 'Porto "Invicta"', "0.667", "6"],
        ["2", "Lisbon", "Lisbon", "Lisbon", "1.000", "6"],
    ], "one CSV record per round, stopping at the first agreement"
    assert panel.peak == {0: 3, 1: 3, 2: 3}, "the debaters of a round are asked concurrently"

    probe = LivePanel(panel.answers)

    async def first_round() -> list[str]:
        agen = live_debate("capital", probe.debaters(), full_mesh(names), 3, 1.0)
        got = [await agen.__anext__(), await agen.__anext__()]
        await agen.aclose()
        return got

    assert parse(asyncio.run(first_round()))[1][0] == "0"
    assert len(probe.calls) == 3, "report each round as soon as it ends"

    slow = LivePanel(
        {"alpha": ["Lisbon"] * 3, "beta": ["Lisbon"] * 3, "gamma": ["Madrid", "Lisbon", "Lisbon"]},
        hang=[("gamma", 1)],
    )
    at_report: list[tuple[str, int]] = []

    def watch(chunk: str) -> None:
        if chunk.startswith("1,"):
            at_report.extend(slow.cancelled)

    rows = parse(asyncio.run(run(slow, 0.1, watch)))
    assert [row[:-1] for row in rows[1:]] == [
        ["0", "Lisbon", "Lisbon", "Madrid", "0.667", "0"],
        ["1", "Lisbon", "Lisbon", "", "1.000", "6"],
        ["2", "Lisbon", "Lisbon", "Lisbon", "1.000", "4"],
    ], "an abstainer has an empty cell, is not counted in agree_ratio, and blocks convergence"
    assert at_report == [("gamma", 1)], "a timed-out call is cancelled before its round is reported"
    assert 90 <= int(rows[2][-1]) < 1000, "a round lasts until its timeout, not its slowest call"
    assert int(rows[3][-1]) < 90, "each round is timed on its own"
    assert slow.asks["gamma"][2] == Ask(
        "capital", 2, Reply("Madrid", 0.5), (("alpha", Reply("Lisbon", 0.5)), ("beta", Reply("Lisbon", 0.5)))
    ), "an abstainer keeps its last reply"
    assert slow.asks["alpha"][2].peers == (("beta", Reply("Lisbon", 0.5)),), "peers skip an abstainer"

    quiet = LivePanel(
        {
            "alpha": ["Lisbon", "Lisbon", "Lisbon", "Lisbon"],
            "beta": ["Lisbon", "Lisbon", "Lisbon", "Madrid"],
            "gamma": ["Lisbon", "Lisbon", "Madrid", "Lisbon"],
        },
        hang=[(name, 1) for name in names],
    )
    rows = parse(asyncio.run(run(quiet, 0.1)))
    assert [row[:-1] for row in rows[1:3]] == [
        ["0", "Lisbon", "Lisbon", "Lisbon", "1.000", "0"],
        ["1", "", "", "", "", "6"],
    ], "agreeing openings do not end the debate; a round nobody answered has an empty agree_ratio"
    assert [row[:-1] for row in rows[3:]] == [
        ["2", "Lisbon", "Lisbon", "Madrid", "0.667", "0"],
        ["3", "Lisbon", "Madrid", "Lisbon", "0.667", "6"],
    ], "nobody to read after a silent round, and the debate ends after round `rounds`"


@pytest.mark.skip("Part 5")
def test_topology_analysis() -> None:
    """Who hears whom, how many rounds that takes, and what a round costs."""
    star = {"hub": [], "s1": ["hub"], "s2": ["hub"], "s3": ["hub"], "s4": ["hub"]}
    report = analyze(star)
    assert report.ops_per_round == 4, "the lesson's star: 4 critique ops per round"
    assert report.reach == {"hub": 1, "s1": None, "s2": None, "s3": None, "s4": None}, (
        "information flows from the peer to its reader"
    )
    assert report.rounds_needed is None, "a spoke's answer never reaches anyone"
    assert report.deaf == ["hub"], "a debater that reads no one is deaf"
    assert report.camps == [["hub"], ["s1"], ["s2"], ["s3"], ["s4"]], "a camp needs both directions"

    names = ["a", "b", "c", "d", "e"]
    mesh = analyze(full_mesh(names))
    assert (mesh.ops_per_round, mesh.rounds_needed, mesh.deaf, mesh.camps) == (20, 1, [], [names]), (
        "on a full mesh one round reaches everyone"
    )

    ring = analyze({"a": ["e"], "b": ["a"], "c": ["b"], "d": ["c"], "e": ["d"]})
    assert ring.reach == dict.fromkeys(names, 4) and ring.rounds_needed == 4, "an answer moves one hop per round"

    shortcut = analyze({"a": [], "b": ["a"], "c": ["b"], "d": ["c", "a"]})
    assert shortcut.reach == {"a": 2, "b": None, "c": None, "d": None}, (
        "reach counts the fewest rounds, over any path"
    )
    assert shortcut.camps == [["a"], ["b"], ["c"], ["d"]]

    hubs = analyze({"h1": ["h2"], "h2": ["h1"], "s1": ["h1", "h2", "h1", "s1"], "s2": ["h2"], "x": ["x", "h1"]})
    assert hubs.ops_per_round == 6, "self-reads and repeated peers are not ops"
    assert hubs.reach == {"h1": 2, "h2": 2, "s1": None, "s2": None, "x": None}
    assert hubs.camps == [["h1", "h2"], ["s1"], ["s2"], ["x"]]

    split = analyze({"a": ["b"], "b": ["a"], "c": ["d", "c"], "d": ["c"], "e": ["e"]})
    assert split.reach == dict.fromkeys(names, None) and split.rounds_needed is None
    assert split.deaf == ["e"], "reading only yourself is hearing no one"
    assert split.camps == [["a", "b"], ["c", "d"], ["e"]]
    order = analyze({"z": [], "y": ["m"], "m": ["z", "y"], "b": ["b"]})
    assert (order.deaf, order.camps) == (["z", "b"], [["z"], ["y", "m"], ["b"]]), (
        "deaf and camps keep the roster order"
    )

    solo = analyze({"solo": ["solo"]})
    assert (solo.reach, solo.rounds_needed, solo.ops_per_round) == ({"solo": 0}, 0, 0)
    with pytest.raises(ValueError):
        analyze({"a": ["ghost"]})
