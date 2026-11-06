import asyncio
import json
import math
import random
import time
from fractions import Fraction

import pytest
from ttsfront.duration import DURATION_FRAMES, allocate_frames
from ttsfront.g2p import frontend
from ttsfront.lexicon import Pronunciation, PronunciationLexicon
from ttsfront.normalize import normalize
from ttsfront.service import TTSService
from ttsfront.ssml import flatten
from ttsfront.stream import speech_events


def collect(agen) -> list:
    async def drain() -> list:
        return [item async for item in agen]

    return asyncio.run(drain())


async def pieces(parts: list[str]):
    for part in parts:
        yield part


def split(text: str, sizes: list[int]) -> list[str]:
    """Cut text into pieces of the given sizes; the last piece takes the rest."""
    out, pos = [], 0
    for size in sizes:
        out.append(text[pos : pos + size])
        pos += size
    return out + [text[pos:]]


def sse(stream: str) -> list[dict]:
    """Parse server-sent events: one "data: <json>" line per event, then a blank line."""
    blocks = stream.split("\n\n")
    assert blocks[-1] == "", "every event ends with a blank line"
    events = []
    for block in blocks[:-1]:
        assert block.startswith("data: ") and "\n" not in block, "each event is one data: line"
        events.append(json.loads(block[len("data: ") :]))
    return events


LEXICON = {
    "gate": ["G", "EY", "T"],
    "forty": ["F", "AO", "R", "T", "IY"],
    "two": ["T", "UW"],
    "Kokoro": ["K", "OW", "K", "AO", "R", "OW"],
    "reads": ["R", "IY", "D", "Z"],
    "it": ["IH", "T"],
}


@pytest.mark.skip("Part 1")
def test_text_frontend() -> None:
    """Numbers, abbreviations and unknown words are read the way a listener expects."""
    assert frontend("Gate 42.", LEXICON) == [
        "G", "EY", "T", "_", "F", "AO", "R", "T", "IY", "_", "T", "UW", "_PAUSE_",
    ], "numbers are read as words"
    assert normalize("Room 2026, floor 15, order 4155550123!") == [
        "room", "two", "thousand", "twenty", "six", ",", "floor", "fifteen", ",", "order",
        "four", "one", "five", "five", "five", "five", "zero", "one", "two", "three", "!",
    ], "cardinals below a million; longer digit strings one digit at a time"
    assert frontend("Kokoro reads it.", LEXICON) == [
        "K", "OW", "K", "AO", "R", "OW", "_", "R", "IY", "D", "Z", "_", "IH", "T", "_PAUSE_",
    ], "lexicon lookup ignores case"
    assert normalize("Dr. Lee lives on Elm Dr.") == [
        "doctor", "lee", "lives", "on", "elm", "drive",
    ], "abbreviations are read as words, and their period is not a pause"
    assert frontend("Ghumare station", LEXICON) == [
        "G", "HH", "UH", "M", "AH", "R", "EH", "_", "S", "T", "AH", "SH", "AH", "N",
    ], "a word missing from the lexicon is read with the grapheme rules, longest match first"

    laugh = "ha" * 1500  # an LLM stuck repeating itself
    start = time.perf_counter()
    phones = frontend(laugh, LEXICON)
    assert time.perf_counter() - start < 0.05, "a long unknown word should not stall the frontend"
    assert phones == ["HH", "AH"] * 1500, "every letter of an unknown word is read"


@pytest.mark.skip("Part 2")
def test_lexicon_roundtrip(tmp_path) -> None:
    """Pronunciations survive the lexicon exactly, in priority order, across a reopen."""
    path = str(tmp_path / "lexicon.sqlite3")
    chanson = ["ʃ", "ɑ̃", "s", "õ"]  # nasal vowels: a letter plus a combining tilde
    church = ["t͡ʃ", "ɜː", "t͡ʃ"]  # affricates: two letters joined by a tie bar
    ich = ["ɪ", "\u00e7"]  # ç as one precomposed code point
    tomato = [
        ["t", "ə", "m", "ɑː", "t", "oʊ"],
        ["t", "ə", "m", "eɪ", "ɾ", "oʊ"],
        ["t", "ə", "m", "eɪ", "t", "oʊ"],
    ]

    lexicon = PronunciationLexicon(path)
    lexicon.add("chanson", chanson)
    lexicon.add("ich", ich)
    lexicon.add("Church", church)
    lexicon.add("tomato", tomato[0], priority=1)
    lexicon.add("Tomato", tomato[1], priority=5)
    lexicon.add("TOMATO", tomato[2], priority=1)
    assert [lexicon.best("chanson"), lexicon.best("ich")] == [chanson, ich], (
        "phones round-trip exactly, code point for code point"
    )
    assert lexicon.pronunciations("church") == [Pronunciation("church", church, 0)], (
        "words match ignoring case"
    )
    assert [p.phones for p in lexicon.pronunciations("tomato")] == [tomato[1], tomato[0], tomato[2]], (
        "every pronunciation, highest priority first, ties in the order added"
    )
    assert lexicon.pronunciations("ghumare") == []
    with pytest.raises(KeyError):
        lexicon.best("ghumare")
    with pytest.raises(ValueError):
        lexicon.add("Tomato", tomato[0], priority=9)
    with pytest.raises(ValueError):
        lexicon.add("chanson", ["ʃ", "ɑ", "̃", "s"])
    with pytest.raises(ValueError):
        lexicon.add("silence", [])
    with pytest.raises(ValueError):
        lexicon.add("silence", ["s", ""])
    lexicon.close()

    reopened = PronunciationLexicon(path)
    assert reopened.table() == {"chanson": chanson, "church": church, "ich": ich, "tomato": tomato[1]}, (
        "a reopened lexicon sees every word"
    )
    reopened.close()


@pytest.mark.skip("Part 3")
def test_frame_allocation() -> None:
    """Predicted durations become whole mel frames without losing or gaining time."""
    frames = allocate_frames([30.0, 30.0, 30.0])  # 2.4 frames each at a 12.5 ms hop
    assert sum(frames) == 7, "the frames add up to the whole duration"
    assert frames == [3, 2, 2], "of equal remainders, the earlier phone gets the frame"
    assert allocate_frames([20.0, 30.0, 45.0, 30.0]) == [2, 2, 4, 2], (
        "leftover frames go to the largest remainders"
    )
    assert allocate_frames([30.0, 55.0]) == [3, 4], "2.4 and 4.4 frames: the earlier phone wins the tie"
    assert allocate_frames([15.625, 15.625]) == [2, 1], "2.5 frames in total round half up to 3"
    assert allocate_frames([2.5, 47.5]) == [1, 4], "every phone keeps at least one frame"
    assert allocate_frames([7.5, 31.25]) == [1, 3], "a phone shorter than one frame counts as one frame"

    rng = random.Random(7)
    halves = [rng.randrange(1, 400) for _ in range(300)]  # durations in steps of 0.5 ms
    frames = allocate_frames([h * 0.5 for h in halves])
    floors = [max(25, h) // 25 for h in halves]  # whole frames in each share
    assert sum(frames) == (2 * sum(max(25, h) for h in halves) + 25) // 50 and all(
        lo <= f <= lo + 1 for f, lo in zip(frames, floors)
    ), "the total is kept and no phone moves more than one frame from its share"

    lexicon = PronunciationLexicon()
    lexicon.add("kokoro", ["K", "OW", "K", "AO", "R", "OW"])
    service = TTSService(lexicon)
    phones = service.phonemes("Kokoro, 21!")
    plan = service.schedule("Kokoro, 21!", speed=1.25)
    assert [phone for phone, _, _ in plan] == phones
    assert plan[0][1] == 0 and all(a[2] == b[1] for a, b in zip(plan, plan[1:])), (
        "the spans tile the utterance"
    )
    shares = [max(Fraction(1), Fraction(DURATION_FRAMES.get(p, 5)) / Fraction(5, 4)) for p in phones]
    assert plan[-1][2] == math.floor(sum(shares) + Fraction(1, 2)), (
        "at 1.25x speed the schedule keeps the whole, shortened duration"
    )


TEXT = "Sure, Dr. Lee. Your total is 3.50 dollars, which includes tax, fees, and the rest. Anything else? Bye"
CHUNKS = [
    "Sure, Dr. Lee.",
    "Your total is 3.50 dollars,",
    "which includes tax, fees,",
    "and the rest.",
    "Anything else?",
    "Bye",
]


@pytest.mark.skip("Part 4")
def test_speech_events() -> None:
    """Streaming LLM text is cut into speakable chunks, each sent as soon as it is complete."""
    events = sse("".join(collect(speech_events(pieces([TEXT])))))
    assert [e["text"] for e in events] == CHUNKS, (
        "a chunk ends at . ? ! and, once long enough, at , ; :"
    )
    assert [e["seq"] for e in events] == list(range(len(CHUNKS))), "events are numbered from 0"
    events = sse("".join(collect(speech_events(pieces([TEXT]), min_chars=19))))
    assert "which includes tax," in [e["text"] for e in events], (
        "a chunk exactly min_chars long can end at a comma"
    )

    tokens = ["Sure", ",", " Dr", ".", " Lee", ".", " Your", " total", " is", " 3", ".", "50",
              " dollars", ",", " which", " includes", " tax", ",", " fees", ",", " and", " the",
              " rest", ".", " Anything", " else", "?", " Bye"]
    assert "".join(tokens) == TEXT
    rng = random.Random(3)
    for parts in (tokens, list(TEXT), split(TEXT, [rng.randrange(0, 9) for _ in range(30)])):
        events = sse("".join(collect(speech_events(pieces(parts)))))
        assert [e["text"] for e in events] == CHUNKS, f"the same chunks however the text is split, e.g. {parts[:6]}"

    pulled: list[str] = []

    async def llm():
        for token in ["Sure", ".", " Here", " is", " the", " plan"] + [" and"] * 94:
            pulled.append(token)
            yield token

    async def first_event() -> str:
        agen = speech_events(llm())
        first = await agen.__anext__()
        await agen.aclose()
        return first

    assert sse(asyncio.run(first_event())) == [{"seq": 0, "text": "Sure."}]
    assert len(pulled) <= 3, "send the first chunk as soon as it is complete"

    events = sse("".join(collect(speech_events(pieces(['Press "Send".\nDone. ', "\n"])))))
    assert events == [{"seq": 0, "text": 'Press "Send".'}, {"seq": 1, "text": "Done."}], (
        "a newline is whitespace too, and no empty chunks"
    )


NS = 'xmlns="http://www.w3.org/2001/10/synthesis"'


@pytest.mark.skip("Part 5")
def test_ssml_flatten() -> None:
    """Nested SSML flattens into segments that carry the prosody of every enclosing tag."""
    plain = {"rate": 1.0, "pitch": 0.0}
    assert flatten(
        '<speak>Your code is <say-as interpret-as="characters">TTS</say-as>, call\n'
        '  <say-as interpret-as="digits">911</say-as>.</speak>'
    ) == [{"text": "Your code is T T S, call nine one one.", **plain}], (
        "text with the same prosody is one segment, spaced as written"
    )
    assert flatten(
        '<speak><prosody rate="150%" pitch="+2st"><prosody rate="50%" pitch="-0.5st">'
        "or sooner</prosody></prosody></speak>"
    ) == [{"text": "or sooner", "rate": 0.75, "pitch": 1.5}], (
        "an inner prosody multiplies the rate and adds to the pitch"
    )
    assert flatten('<speak>Ships <prosody rate="150%">soon</prosody> to you.</speak>') == [
        {"text": "Ships", **plain},
        {"text": "soon", "rate": 1.5, "pitch": 0.0},
        {"text": "to you.", **plain},
    ], "text after a tag is back in the outer prosody"
    assert flatten('<speak>Thanks<break time="250ms"/>again<break time="1.5s"/>bye</speak>') == [
        {"text": "Thanks", **plain},
        {"break_ms": 250},
        {"text": "again", **plain},
        {"break_ms": 1500},
        {"text": "bye", **plain},
    ], "a break separates segments; its time is in ms or s"

    document = f"""<speak version="1.1" {NS}>
  <prosody rate="150%" pitch="+2st">It ships in <say-as interpret-as="cardinal">21</say-as>
    days <prosody rate="50%" pitch="-0.5st">or sooner</prosody> at most.</prosody>
  <break time="300ms"/>
  <prosody pitch="+1st">Thank you</prosody> for waiting.
</speak>"""
    assert flatten(document) == [
        {"text": "It ships in twenty one days", "rate": 1.5, "pitch": 2.0},
        {"text": "or sooner", "rate": 0.75, "pitch": 1.5},
        {"text": "at most.", "rate": 1.5, "pitch": 2.0},
        {"break_ms": 300},
        {"text": "Thank you", "rate": 1.0, "pitch": 1.0},
        {"text": "for waiting.", **plain},
    ], "a whole SSML document, namespace and all, flattens in reading order"
    with pytest.raises(ValueError, match="emphasis"):
        flatten("<speak>Hi <emphasis>there</emphasis></speak>")
