import asyncio
import json
import time
from dataclasses import replace

import pytest
from musicbox.compose import BAR, STEP, Note, compose, parse_bpm, render, seconds
from musicbox.fad import frechet_distance, rank_models
from musicbox.form import expand
from musicbox.service import MusicBox
from musicbox.store import Track, TrackStore
from musicbox.stream import stream_bars


def collect(agen) -> list:
    async def drain() -> list:
        return [item async for item in agen]

    return asyncio.run(drain())


async def source(tokens: list[str], pulled: list[str] | None = None):
    for token in tokens:
        if pulled is not None:
            pulled.append(token)
        yield token


def sse_events(text: str) -> list[dict]:
    """Parse a Server-Sent Events stream: each event is its data: lines, ended by a blank line."""
    assert text.endswith("\n\n"), "every event ends with a blank line"
    events = []
    for block in text[:-2].split("\n\n"):
        data = [line[5:].removeprefix(" ") for line in block.split("\n") if line.startswith("data:")]
        assert data, "every event carries its JSON on a data: line"
        events.append(json.loads("\n".join(data)))
    return events


@pytest.mark.skip("Part 1")
def test_prompt_to_notes() -> None:
    """A prompt becomes the chords and tempo it asks for, on the tick grid, and long pieces render fast."""
    notes = render(compose("baroque study in A", bars=8))
    assert [n.pitch for n in notes if n.start == 2 * BAR and n.channel == 0] == [68, 71, 74], (
        "bar 3 of a baroque piece in A is G#dim: G#4 B4 D5"
    )
    rock = render(compose("rock anthem in D", bars=8))
    assert [(n.start, n.length) for n in rock if n.pitch == 62] == [(0, BAR), (3 * BAR, 2 * BAR), (7 * BAR, BAR)], (
        "a tone that the next chord keeps is held, not struck again"
    )
    assert [(n.start, n.length) for n in rock if n.pitch == 69] == [(0, BAR), (2 * BAR, 3 * BAR), (6 * BAR, 2 * BAR)], (
        "a tone is held for as many bars as the chords keep it"
    )
    drone = render(replace(compose("rock anthem in D", bars=16), chords=["D"] * 16))
    assert [(n.start, n.length) for n in drone if n.channel == 0] == [(0, 16 * BAR)] * 3, (
        "a chord that never changes is held from the first bar to the last"
    )

    pop = compose("upbeat pop in G major at 128 bpm", bars=8)
    assert seconds(pop, 8 * BAR) == 15.0, "8 bars of 4/4 at 128 bpm last 15 s"
    prompts = ("8 bars of lofi at 90 bpm", "jazz at 140BPM for 32 bars", "lofi in C")
    assert [parse_bpm(p) for p in prompts] == [90, 140, 120], (
        "the tempo is the number written before bpm"
    )
    assert seconds(pop, STEP) == 0.1171875, "a sixteenth step at 128 bpm lasts 0.1171875 s"

    hour = compose("rock anthem in D at 140 bpm", bars=2000)  # about an hour of music
    start = time.perf_counter()
    render(hour)
    assert time.perf_counter() - start < 0.15, "render should be fast on long pieces"


@pytest.mark.skip("Part 2")
def test_track_store(tmp_path) -> None:
    """Tracks keep their tick grid, tempo map and generation record exactly, across a reopen."""
    path = str(tmp_path / "tracks.sqlite3")
    track = Track(
        title="Rainy Texas nights",
        ppq=480,
        tempo=[(0, 128.0), (3840, 140.0), (5760, 400 / 3)],
        notes=[
            Note(0, 1920, 64, 80), Note(0, 1920, 60, 80), Note(0, 1920, 67, 80),
            Note(3840, 160, 72, 64), Note(4000, 160, 74, 64), Note(4160, 160, 76, 64),
            Note(0, 120, 36, 100, 9),
        ],
        meta={
            "model": "musicgen-small",
            "prompt": "country song about rainy Texas nights",
            "seed": 14695981039346656037,
            "ai_generated": True,
        },
    )
    store = TrackStore(path)
    first = store.add(track)
    takes = [store.add(replace(track, title=f"Rainy Texas nights (take {k})")) for k in range(2, 7)]
    assert isinstance(first, str) and len({first, *takes}) == 6, "add returns a new id for every track"
    assert store.get(first) == track, "a track must round-trip exactly"
    with pytest.raises(KeyError):
        store.get("no-such-track")
    store.close()

    reopened = TrackStore(path)
    assert reopened.ids() == [first, *takes], "a reopened store sees earlier tracks, in the order they were added"
    take2 = reopened.get(takes[0])
    assert take2.seconds(3840) == 3.75, "8 beats at 128 bpm"
    assert take2.seconds(4320) == pytest.approx(3.75 + 60 / 140), "after a tempo change, beats take the new tempo"
    assert take2.seconds(6000) == pytest.approx(3.75 + 4 * 60 / 140 + 0.5 * 0.45), (
        "every earlier tempo still counts"
    )
    assert replace(take2, ppq=960).seconds(3840) == 1.875, "ticks count at the track's own ppq"
    with pytest.raises(ValueError):
        reopened.add(replace(track, tempo=[(480, 120.0)]))
    with pytest.raises(ValueError):
        reopened.add(replace(track, tempo=[(0, 120.0), (0, 90.0)]))
    with pytest.raises(ValueError):
        reopened.add(replace(track, tempo=[(0, 0.0)]))
    with pytest.raises(ValueError):
        reopened.add(replace(track, meta={"model": "musicgen-small", "seed": 7}))

    generated = reopened.get(MusicBox(reopened).generate("lofi in C at 90 bpm", bars=4))
    assert generated.seconds(4 * BAR) == pytest.approx(16 * 60 / 90), "a generated track keeps its tempo"
    reopened.close()


@pytest.mark.skip("Part 3")
def test_frechet_audio_distance() -> None:
    """FAD compares Gaussians fitted to two embedding sets; lower is better."""
    real = [(0.2, 0.1), (0.9, 0.6), (0.4, 0.8), (0.5, 0.2)]

    def shifted(dx: float, dy: float) -> list[tuple[float, float]]:
        return [(x + dx, y + dy) for x, y in real]

    assert frechet_distance(real, shifted(1.5, 1.5)) == pytest.approx(4.5), (
        "same spread, means 1.5 apart on both axes: FAD 4.5"
    )
    assert frechet_distance(real, [(2 * x, 2 * y) for x, y in real]) == pytest.approx(0.430625 + 0.5875 / 3), (
        "S is the sample covariance: divide by n - 1"
    )
    collapsed = [(0.1, 0.15), (0.2, 0.2), (0.3, 0.25), (0.4, 0.3)]
    assert frechet_distance(real, collapsed) == pytest.approx(0.2167649522712958), (
        "a model whose outputs all fall on one line still gets a score"
    )
    assert 0.0 <= frechet_distance(real, list(real)) < 1e-12, "a model that matches the reference scores 0"
    with pytest.raises(ValueError):
        frechet_distance(real, [(0.5, 0.5)])
    with pytest.raises(ValueError):
        frechet_distance([(0.5, 0.5)], real)

    ranking = rank_models(
        real, {"baseline": shifted(1.5, 1.5), "finetuned": shifted(1.2, -1.2), "distilled": shifted(1.5, 1.0)}
    )
    assert [name for name, _ in ranking] == ["finetuned", "distilled", "baseline"], "lower FAD ranks first"
    assert [score for _, score in ranking] == pytest.approx([2.88, 3.25, 4.5])

    box = MusicBox(TrackStore())
    reference = ["lofi in C at 80 bpm", "lofi in G at 86 bpm", "lofi in D at 92 bpm", "lofi in A at 84 bpm"]
    lofi = ["lofi in G at 82 bpm", "lofi in A at 90 bpm", "lofi in C at 88 bpm", "lofi in D at 78 bpm"]
    rock = ["rock in C at 140 bpm", "rock in G at 150 bpm", "rock in D at 132 bpm", "rock in A at 144 bpm"]
    assert box.fad(reference, lofi) < box.fad(reference, rock), "generations in the reference style score lower"


@pytest.mark.skip("Part 4")
def test_stream_bars() -> None:
    """Bars go out as soon as the generator moves past them; notes that cross a bar line are tied over."""
    tokens = "bar pos:0 note:60:4 note:64:20 pos:12 note:67:8 bar note:62:16 bar bar pos:4 note:65:44".split()
    bars = sse_events("".join(collect(stream_bars(source(tokens)))))
    notes = [[(n["pitch"], n["step"], n["steps"], n["tied"]) for n in bar["notes"]] for bar in bars]
    assert notes[:1] == [[(60, 0, 4, False), (64, 0, 16, False), (67, 12, 4, False)]], "a note is cut at the bar line"
    assert notes[1:2] == [[(64, 0, 4, True), (67, 0, 4, True), (62, 0, 16, False)]], (
        "the rest of a cut note opens the next bar, tied, and the new bar starts at step 0"
    )
    assert [bar["bar"] for bar in bars] == [0, 1, 2, 3, 4, 5], (
        "one event per bar, including empty bars and the bars a last note rings into"
    )
    assert notes[2:3] == [[]], "a note that ends on the bar line does not ring into the next bar"
    assert notes[3:] == [[(65, 4, 12, False)], [(65, 0, 16, True)], [(65, 0, 16, True)]], (
        "a long note is tied across every bar it lasts"
    )

    pulled: list[str] = []

    async def first_bar() -> str:
        agen = stream_bars(source(["bar", "pos:0", "note:60:4"] * 100, pulled))
        first = await agen.__anext__()
        await agen.aclose()
        return first

    assert sse_events(asyncio.run(first_bar())) == [
        {"bar": 0, "notes": [{"pitch": 60, "step": 0, "steps": 4, "tied": False}]}
    ]
    assert len(pulled) <= 4, "send each bar as soon as the next one starts"
    with pytest.raises(ValueError):
        collect(stream_bars(source(["bar", "pos:16", "note:60:4"])))


SONG = {
    "sections": {
        "intro": {"bars": [[[0, 1920, 50]], [[0, 960, 52], [960, 960, 53]]]},
        "riff": {"bars": [[[0, 480, 57], [960, 480, 60]]]},
        "turn": {"meter": [3, 4], "bars": [[[0, 1440, 55]]]},
        "verse": {"play": [{"repeat": 2, "play": ["riff"]}, "turn"]},
        "chorus": {"meter": [6, 8], "bars": [[[0, 720, 62], [720, 720, 64]]]},
        "first": {"bars": [[[0, 1920, 59]]]},
        "last": {"bars": [[[0, 1920, 48]]]},
    },
    "form": ["intro", {"repeat": 2, "play": ["verse", "chorus"], "endings": [["first"], ["last"]]}, "chorus"],
}


@pytest.mark.skip("Part 5")
def test_song_form() -> None:
    """A song form expands into one timeline: sections, nested repeats, endings and meter changes."""
    timeline = expand(SONG)
    assert timeline[:8] == [
        (0, 1920, 50), (1920, 960, 52), (2880, 960, 53),
        (3840, 480, 57), (4800, 480, 60), (5760, 480, 57), (6720, 480, 60), (7680, 1440, 55),
    ], "a repeat inside a section: the verse plays its riff twice, then the turn"
    assert [p for _, _, p in timeline if p in (59, 48)] == [59, 48], "each pass plays its own ending"
    assert [t for t, _, p in timeline if p in (55, 62, 59)][:3] == [7680, 9120, 10560], (
        "a 3/4 bar is 1440 ticks, and so is a 6/8 bar"
    )
    assert [t for t, _, p in timeline if p == 57][2:] == [12480, 14400], "the second pass starts after the first ending"
    assert timeline[8:] == [
        (9120, 720, 62), (9840, 720, 64), (10560, 1920, 59),
        (12480, 480, 57), (13440, 480, 60), (14400, 480, 57), (15360, 480, 60), (16320, 1440, 55),
        (17760, 720, 62), (18480, 720, 64), (19200, 1920, 48),
        (21120, 720, 62), (21840, 720, 64),
    ], "every note, in playing order"
    with pytest.raises(ValueError):
        expand({"sections": {"a": {"play": ["b"]}, "b": {"play": [{"repeat": 2, "play": ["a"]}]}}, "form": ["a"]})
    with pytest.raises(ValueError):
        expand({"sections": {"jig": {"meter": [6, 8], "bars": [[[1440, 240, 60]]]}}, "form": ["jig"]})
