import asyncio
import json
import time

import pytest
from longform.lora import lora_report
from longform.service import LongformService
from longform.stitch import stitch
from longform.stream import transcribe_stream
from longform.tokens import Decoding, Segment, parse, to_text
from longform.windows import SAMPLE_RATE, Window, plan_windows


def collect(agen) -> list:
    async def drain() -> list:
        return [item async for item in agen]

    return asyncio.run(drain())


async def chunked(signal: list[float], sizes: list[int]):
    pos = 0
    for size in sizes:
        yield signal[pos : pos + size]
        pos += size


@pytest.mark.skip("Part 1")
def test_window_plan() -> None:
    """Recordings are cut into overlapping 30 s windows, with Whisper's frame budget for each."""
    sr = SAMPLE_RATE
    assert [(w.start, w.end) for w in plan_windows(65 * sr)] == [
        (0, 30 * sr),
        (25 * sr, 55 * sr),
        (50 * sr, 65 * sr),
    ], "a window starts every 30 - 5 s, and the last one stops at the end"

    assert plan_windows(160) == [Window(0, 160, 1, 1)], (
        "a 10 ms clip is one window: one mel frame, one encoder position"
    )
    assert plan_windows(30 * sr) == [Window(0, 30 * sr, 3000, 1500)], (
        "30 s is one window: 3000 mel frames and 1500 encoder positions"
    )
    assert plan_windows(32_160) == [Window(0, 32_160, 201, 101)], (
        "positions follow the stride-2 conv for an odd number of frames too"
    )
    assert [(w.start, w.end) for w in plan_windows(55 * sr)] == [
        (0, 30 * sr),
        (25 * sr, 55 * sr),
    ], "no window lies inside another"
    assert plan_windows(55 * sr + 1)[-1] == Window(50 * sr, 55 * sr + 1, 500, 250), (
        "every sample is covered, down to the last one"
    )

    sixty_hours = 60 * 3600 * sr
    start = time.perf_counter()
    plan = plan_windows(sixty_hours)
    assert time.perf_counter() - start < 0.1, "planning a long recording should be fast"
    assert len(plan) == 8_640 and plan[-1].end == sixty_hours


@pytest.mark.skip("Part 2")
def test_decoding_roundtrip() -> None:
    """Decodings are written as Whisper's special-token text and read back exactly."""
    plain = Decoding("en", text=" Hello world.")
    assert to_text(plain) == (
        "<|startoftranscript|><|en|><|transcribe|><|notimestamps|> Hello world.<|endoftext|>"
    ), "start of transcript, language, task, then the output"

    timed = Decoding(
        "ja",
        segments=[
            Segment(0.0, 0.58, " こんにちは。"),
            Segment(0.7, 1.16, "  二つ目  "),
            Segment(29.98, 30.0, "!"),
        ],
        previous=" 前の文。",
    )
    text = to_text(timed)
    assert text == (
        "<|startofprev|> 前の文。<|startoftranscript|><|ja|><|transcribe|>"
        "<|0.00|> こんにちは。<|0.58|><|0.70|>  二つ目  <|1.16|><|29.98|>!<|30.00|><|endoftext|>"
    ), "timestamps are tokens with two decimals"
    assert parse(text) == timed, "a decoding must round-trip exactly"
    for decoding in (plain, Decoding("fr", "translate", text=""), Decoding("is")):
        assert parse(to_text(decoding)) == decoding, "a decoding must round-trip exactly"

    with pytest.raises(ValueError):
        to_text(Decoding("xx", text=" hi"))
    with pytest.raises(ValueError):
        to_text(Decoding("en", "transcription", text=" hi"))
    for no_token in (1.07, 1.081, 30.02):
        with pytest.raises(ValueError):
            to_text(Decoding("en", segments=[Segment(0.0, no_token, " hi")]))
    with pytest.raises(ValueError):
        to_text(Decoding("en", segments=[Segment(0.0, 1.0, " hi")], text=" hi"))
    with pytest.raises(ValueError):
        parse(
            "<|startoftranscript|><|en|><|transcribe|><|notimestamps|>"
            "<|0.00|> hi<|1.00|><|endoftext|>"
        )
    with pytest.raises(ValueError):
        parse("<|startoftranscript|><|en|><|transcribe|><|0.00|> hi<|1.00|>")


SCRIPT = [
    (" Long", 0.0, 0.5),
    (" recordings", 0.5, 1.3),
    (" are", 12.0, 12.3),
    (" cut", 24.8, 25.2),
    (" into", 27.4, 27.6),
    (" windows", 29.8, 30.4),
    (" that", 40.0, 40.2),
    (" overlap", 49.9, 50.5),
    (" and", 52.4, 52.6),
    (" join", 54.8, 55.2),
    (" again.", 69.0, 69.6),
]


def fake_whisper(window: Window) -> str:
    """Decoder text for one window: the words it hears, cut short at its edges, plus a
    hallucination in the padding of a short window."""
    lo, hi = window.start / SAMPLE_RATE, window.end / SAMPLE_RATE
    segments = []
    for text, start, end in SCRIPT:
        if start < hi and end > lo:
            whole = lo <= start and end <= hi
            segments.append(Segment(
                round((max(start, lo) - lo) * 50) / 50,
                round((min(end, hi) - lo) * 50) / 50,
                text if whole else text[: len(text) // 2],
            ))
    if hi - lo < 30:
        tail = round(hi - lo)
        segments.append(Segment(tail + 1.0, tail + 3.0, " Thanks for watching!"))
    return to_text(Decoding("en", segments=segments))


@pytest.mark.skip("Part 3")
def test_stitch_windows() -> None:
    """Overlapping windows join into one transcript, with every word exactly once."""
    sr = SAMPLE_RATE
    windows = plan_windows(65 * sr)  # 0-30 s, 25-55 s and 50-65 s: splits at 27.5 s and 52.5 s
    heard = [
        [
            Segment(0.0, 0.4, " So"),
            Segment(10.0, 10.2, " the"),
            Segment(25.2, 25.8, " window"),
            Segment(27.24, 27.76, " split,"),
            Segment(29.6, 30.0, " cu"),
        ],
        [
            Segment(0.0, 0.8, " dow"),
            Segment(2.24, 2.76, " split."),
            Segment(4.6, 5.4, " cut"),
            Segment(15.0, 15.5, " middle"),
            Segment(27.0, 28.2, " again,"),
        ],
        [
            Segment(2.0, 3.2, " again."),
            Segment(14.8, 15.4, " end"),
            Segment(15.5, 17.0, " Thanks for watching!"),
        ],
    ]
    result = stitch(windows, heard)
    texts = [s.text for s in result]
    assert " Thanks for watching!" not in texts, "words decoded from the padding are dropped"
    assert texts[0] == " So" and texts[-1] == " end", (
        "nothing is trimmed at the start or the end of the recording"
    )
    assert texts == [" So", " the", " window", " split.", " cut", " middle", " again.", " end"], (
        "each word once, from the window on whose side of the split its midpoint falls"
    )
    assert result == [
        Segment(0.0, 0.4, " So"),
        Segment(10.0, 10.2, " the"),
        Segment(25.2, 25.8, " window"),
        Segment(27.24, 27.76, " split."),
        Segment(29.6, 30.4, " cut"),
        Segment(40.0, 40.5, " middle"),
        Segment(52.0, 53.2, " again."),
        Segment(64.8, 65.4, " end"),
    ], "times are seconds from the start of the recording, rounded to 0.01 s"

    narrow = plan_windows(40 * sr, overlap_s=2.0)  # 0-30 s and 28-40 s: split at 29 s
    assert stitch(narrow, [
        [Segment(28.5, 29.3, " near,"), Segment(29.4, 29.8, " lay")],
        [Segment(0.5, 1.3, " near"), Segment(1.4, 1.8, " late")],
    ]) == [Segment(28.5, 29.3, " near,"), Segment(29.4, 29.8, " late")], (
        "the split is the middle of the actual overlap"
    )

    words = LongformService(fake_whisper).transcribe(70 * sr)
    assert words == [Segment(start, end, text) for text, start, end in SCRIPT], (
        "Parts 1-3 together: every word once, at its time in the recording"
    )


def sse(text: str) -> list[str]:
    """The data fields of a server-sent event stream."""
    *events, rest = text.split("\n\n")
    assert rest == "" and all(e.startswith("data: ") for e in events), (
        "server-sent events: 'data: ...' and then a blank line"
    )
    return [e[len("data: "):] for e in events]


@pytest.mark.skip("Part 4")
def test_stream_transcript() -> None:
    """A live stream is transcribed window by window, and a hallucination is not fed back."""
    sr = 100  # 30 s windows of 3,000 samples keep the test small
    signal = [i / sr for i in range(10_000)]  # every sample holds its own time
    replies = [
        [Segment(0.0, 2.5, " One window."), Segment(28.0, 30.0, " Two")],
        [Segment(0.0, 1.0, " windows.")],
        [
            Segment(0.0, 1.0, " Okay."),
            Segment(1.0, 9.0, " Thanks for watching!"),
            Segment(9.0, 18.0, " thanks for watching"),
            Segment(18.0, 27.0, " Thanks, for watching."),
        ],
        [Segment(0.0, 8.46, " The end.")],
    ]
    calls: list[tuple[float, int, str | None]] = []

    def decode(samples: list[float], previous: str | None) -> list[Segment]:
        calls.append((samples[0], len(samples), previous))
        return replies[len(calls) - 1]

    expected = [
        {"start": 0.0, "end": 2.5, "text": " One window."},
        {"start": 28.0, "end": 30.0, "text": " Two"},
        {"start": 30.0, "end": 31.0, "text": " windows."},
        {"start": 90.0, "end": 98.46, "text": " The end."},
    ]
    for sizes in ([10_000], [1] * 10_000, [2_999, 0, 2, 4_000, 2_999]):
        calls.clear()
        stream = transcribe_stream(chunked(signal, sizes), decode, sample_rate=sr)
        data = sse("".join(collect(stream)))
        assert data[-1:] == ["[DONE]"], "the stream ends with data: [DONE]"
        assert [(first, n) for first, n, _ in calls] == [
            (0.0, 3_000),
            (30.0, 3_000),
            (60.0, 3_000),
            (90.0, 1_000),
        ], f"consecutive 30 s windows, then whatever is left, e.g. {sizes[:6]}"
        assert [previous for *_, previous in calls] == [
            None,
            " One window. Two",
            " One window. Two windows.",
            None,
        ], "a looping window is dropped and never fed back as context"
        assert [json.loads(d) for d in data[:-1]] == expected, (
            f"same transcript whatever the chunking, e.g. {sizes[:6]}"
        )

    lengths: list[int] = []

    def hello(samples: list[float], previous: str | None) -> list[Segment]:
        lengths.append(len(samples))
        return [Segment(0.0, 1.0, " hi")]

    stream = transcribe_stream(chunked([0.0] * 15_000, [15_000]), hello, sample_rate=sr)
    data = sse("".join(collect(stream)))
    assert lengths == [3_000] * 5, "a stream of whole windows leaves nothing more to decode"
    assert len(data) == 5 + 1, "each window is checked for a loop on its own text"

    pulled: list[int] = []

    async def probe():
        for i in range(100):
            pulled.append(i)
            yield [0.0] * sr

    async def first_event() -> str:
        agen = transcribe_stream(probe(), hello, sample_rate=sr)
        first = await agen.__anext__()
        await agen.aclose()
        return first

    assert json.loads(asyncio.run(first_event()).removeprefix("data: "))["text"] == " hi"
    assert len(pulled) <= 31, "send a window's segments as soon as the window is full"


def linear(d_in: int, d_out: int, bias: bool = True) -> dict:
    layer = {"type": "Linear", "weight": [d_out, d_in]}
    if bias:
        layer["bias"] = [d_out]
    return layer


def norm(d: int) -> dict:
    return {"type": "LayerNorm", "weight": [d], "bias": [d]}


def attention(d: int) -> dict:
    return {
        "q_proj": linear(d, d),
        "k_proj": linear(d, d, bias=False),
        "v_proj": linear(d, d),
        "out_proj": linear(d, d),
    }


def whisper(n_mels: int, d: int, d_ff: int, n_enc: int, n_dec: int, vocab: int) -> dict:
    """The module tree of Hugging Face's WhisperForConditionalGeneration."""

    def block(cross: bool) -> dict:
        layer = {"self_attn": attention(d), "self_attn_layer_norm": norm(d)}
        if cross:
            layer |= {"encoder_attn": attention(d), "encoder_attn_layer_norm": norm(d)}
        return layer | {"fc1": linear(d, d_ff), "fc2": linear(d_ff, d), "final_layer_norm": norm(d)}

    return {
        "model": {
            "encoder": {
                "conv1": {"type": "Conv1d", "weight": [d, n_mels, 3], "bias": [d]},
                "conv2": {"type": "Conv1d", "weight": [d, d, 3], "bias": [d]},
                "embed_positions": {"type": "Embedding", "weight": [1500, d]},
                "layers": [block(cross=False) for _ in range(n_enc)],
                "layer_norm": norm(d),
            },
            "decoder": {
                "embed_tokens": {"type": "Embedding", "weight": [vocab, d]},
                "embed_positions": {"type": "Embedding", "weight": [448, d]},
                "layers": [block(cross=True) for _ in range(n_dec)],
                "layer_norm": norm(d),
            },
        },
        "proj_out": {"type": "Linear", "weight": "model.decoder.embed_tokens.weight"},
    }


@pytest.mark.skip("Part 5")
def test_lora_budget() -> None:
    """Count what LoRA trains on Whisper large-v3-turbo, matching target_modules like PEFT."""
    turbo = whisper(n_mels=128, d=1280, d_ff=5120, n_enc=32, n_dec=4, vocab=51_866)
    report = lora_report(turbo, ["q_proj", "v_proj"], rank=16)
    assert report.adapted[:2] == [
        "model.encoder.layers.0.self_attn.q_proj",
        "model.encoder.layers.0.self_attn.v_proj",
    ], "adapted layers are listed in tree order"
    assert report.adapted[-2:] == [
        "model.decoder.layers.3.encoder_attn.q_proj",
        "model.decoder.layers.3.encoder_attn.v_proj",
    ], "a target name matches cross-attention too"
    assert len(report.adapted) == 32 * 2 + 4 * 4
    assert report.trainable == 3_276_800, "about 3M trainable parameters, as in the lesson"
    assert report.total == 808_878_080 + 3_276_800, (
        "the 809M base, a tied weight counted once, plus the adapters"
    )
    assert lora_report(turbo, ["q_proj", "v_proj", "encoder_attn.q_proj"], rank=16) == report, (
        "a layer that two targets match gets one adapter"
    )

    ffn = lora_report(turbo, ["decoder.layers.*.fc1"], rank=8)
    assert ffn.adapted == [f"model.decoder.layers.{i}.fc1" for i in range(4)], (
        "a dotted target with a wildcard matches the decoder's fc1 layers only"
    )
    assert ffn.trainable == 4 * 8 * (1280 + 5120), (
        "an adapter on an [out, in] weight has rank * (in + out) parameters"
    )
    head = lora_report(turbo, ["proj_out"], rank=16)
    assert head == (["proj_out"], 16 * (1280 + 51_866), 808_878_080 + 16 * (1280 + 51_866)), (
        "a tied layer takes its shape from the weight it shares"
    )
    with pytest.raises(ValueError):
        lora_report(turbo, ["q_proj", "query"])
    with pytest.raises(ValueError):
        lora_report(turbo, ["proj"])
    with pytest.raises(ValueError):
        lora_report(turbo, ["embed_tokens"])
