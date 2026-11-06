import asyncio
import io
import math
import random
import struct
import time
import wave

import pytest
from wavlab.pcm import decode_pcm16, encode_pcm16, float_to_pcm16
from wavlab.resample import decimate, stream_downsample
from wavlab.riff import info_tags, walk
from wavlab.spectrum import alias_frequency, dominant_frequency
from wavlab.wavfile import Audio, decode_wav, encode_wav


def sine(freq: float, sr: int, seconds: float, amp: float = 0.5) -> list[float]:
    """The lesson's sine, with the frame count rounded instead of truncated."""
    return [amp * math.sin(2.0 * math.pi * freq * i / sr) for i in range(round(sr * seconds))]


def pcm_bytes(values: list[int], width: int) -> bytes:
    """Little-endian two's-complement integers, width bytes each."""
    return b"".join(struct.pack("<i", v)[:width] for v in values)


def wave_module_file(frames: bytes, n_channels: int, width: int, sample_rate: int) -> bytes:
    """What the stdlib wave module writes for these frames."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(n_channels)
        w.setsampwidth(width)
        w.setframerate(sample_rate)
        w.writeframes(frames)
    return buf.getvalue()


def collect(agen) -> list:
    async def drain() -> list:
        return [item async for item in agen]

    return asyncio.run(drain())


async def reads(data: bytes, sizes: list[int]):
    """Socket reads of data, cycling through sizes."""
    pos = i = 0
    while pos < len(data):
        yield data[pos : pos + sizes[i % len(sizes)]]
        pos += sizes[i % len(sizes)]
        i += 1


@pytest.mark.skip("Part 1")
def test_pcm16_codec() -> None:
    """16-bit PCM converts to floats and back exactly, quickly, with loud samples clipped."""
    clip = [[1.0, 1.5, -2.0, 0.5], [-0.5, 0.25, -1.25, 0.0]]
    assert struct.unpack("<8h", encode_pcm16(clip)) == (
        32767, -16384, 32767, 8192, -32768, -32768, 16384, 0,
    ), "frames go L R L R, and loud samples saturate at full scale"
    assert [float_to_pcm16(x) for x in (1.0, 2.0, -2.0)] == [32767, 32767, -32768], "float_to_pcm16 itself saturates"

    raw = struct.pack("<8h", 0, 100, 16384, -100, -32768, 2, 32767, -2)
    assert decode_pcm16(raw, 1) == [
        [0.0, 100 / 32768, 0.5, -100 / 32768, -1.0, 2 / 32768, 32767 / 32768, -2 / 32768],
    ], "an int16 sample becomes a float by dividing by 32768"
    assert decode_pcm16(raw, 2) == [
        [0.0, 0.5, -1.0, 32767 / 32768],
        [100 / 32768, -100 / 32768, 2 / 32768, -2 / 32768],
    ], "decoding splits interleaved frames: L R L R"

    step = 1 / 32768
    assert struct.unpack("<4h", encode_pcm16([[0.6 * step, -0.6 * step, 0.4 * step, -1.6 * step]])) == (
        1, -1, 0, -2,
    ), "samples round to the nearest int16 step"

    rng = random.Random(1)
    long_clip = [[0.5 * math.sin(i / 9) + rng.uniform(-0.25, 0.25) for i in range(40000)]]
    start = time.perf_counter()
    encode_pcm16(long_clip)
    assert time.perf_counter() - start < 0.12, "encoding should be fast on long clips"

    every_value = struct.pack("<65536h", *range(-32768, 32768))
    assert encode_pcm16(decode_pcm16(every_value, 1)) == every_value, (
        "decoding and re-encoding must not change a single sample"
    )


@pytest.mark.skip("Part 2")
def test_wav_roundtrip() -> None:
    """WAV files match the wave module byte for byte, keep 24-bit samples exact, and pad odd chunks."""
    left, right = [0, 16384, -32768, 32767], [-1, 2, -3, 4]
    stereo = Audio(16000, [[v / 32768 for v in left], [v / 32768 for v in right]])
    blob = encode_wav(stereo)
    interleaved = [v for frame in zip(left, right) for v in frame]
    assert blob == wave_module_file(pcm_bytes(interleaved, 2), 2, 2, 16000), (
        "write the same bytes as the wave module"
    )
    assert decode_wav(blob) == stereo, "a 16-bit file reads back exactly"

    levels = [0, 1, -1, 8388607, -8388608, 4194304, -123457, 99]
    master = Audio(48000, [[v / 8388608 for v in levels]], sample_width=3)
    blob = encode_wav(master)
    assert blob == wave_module_file(pcm_bytes(levels, 3), 1, 3, 48000), (
        "24-bit files match the wave module too"
    )
    assert decode_wav(blob) == master, "24-bit samples keep their sign and every bit"
    assert encode_wav(decode_wav(blob)) == blob, "re-saving an archived file changes nothing"

    odd = encode_wav(Audio(8000, [[1.0, -0.25, 0.6 / 8388608]], sample_width=3))
    assert len(odd) == 44 + 9 + 1 and odd[-1:] == b"\x00", "an odd-sized chunk is followed by a pad byte"
    assert struct.unpack_from("<I", odd, 4)[0] == len(odd) - 8, "the RIFF size counts the pad byte"
    assert struct.unpack_from("<I", odd, 40)[0] == 9, "a chunk's own size does not count its pad byte"
    with wave.open(io.BytesIO(odd)) as w:
        frames = w.readframes(3)
    assert frames == pcm_bytes([8388607, -2097152, 1], 3), "24-bit samples saturate and round too"
    assert decode_wav(odd).channels == [[8388607 / 8388608, -0.25, 1 / 8388608]], "a padded file reads back"

    with pytest.raises(ValueError):
        encode_wav(Audio(16000, [[0.0, 0.5], [0.0]]))
    with pytest.raises(ValueError):
        decode_wav(wave_module_file(b"\x80\x7f", 1, 1, 8000))


@pytest.mark.skip("Part 3")
def test_dominant_frequency() -> None:
    """Find the strongest tone between DFT bins, and predict where tones above Nyquist land."""
    a440 = sine(440.0, 8000, 0.064)  # 512 samples; the lesson's plain peak bin says 437.5 Hz
    assert dominant_frequency(a440, 8000) == pytest.approx(440.0, abs=0.5), "refine the peak between bins"
    offset = [x + 0.6 for x in sine(1234.0, 8000, 0.064, amp=0.2)]
    assert dominant_frequency(offset, 8000) == pytest.approx(1234.0, abs=0.5), "a DC offset is not a tone"
    with pytest.raises(ValueError):
        dominant_frequency([0.25] * 512, 8000)

    tones = [440.0, 5000.0, 7000.0, 9000.0, 12000.0, 15500.0, 26000.0]
    assert [alias_frequency(f, 10000) for f in tones] == [440.0, 5000.0, 3000.0, 1000.0, 2000.0, 4500.0, 4000.0], (
        "fold every frequency back into 0 .. Nyquist"
    )
    for f in (7000.0, 12000.0, 15500.0):
        heard = dominant_frequency(sine(f, 10000, 0.0512), 10000)
        assert heard == pytest.approx(alias_frequency(f, 10000), abs=0.5), (
            "a tone above Nyquist shows up at its alias"
        )


@pytest.mark.skip("Part 4")
def test_stream_downsample() -> None:
    """48 kHz PCM from a socket becomes 16 kHz PCM for the recognizer, as it arrives."""
    rng = random.Random(4)
    levels = [
        round(12000 * math.sin(2 * math.pi * 440 * i / 48000)) + rng.randint(-3000, 3000) for i in range(4801)
    ]
    raw = struct.pack(f"<{len(levels)}h", *levels)
    want = decimate([v / 32768 for v in levels], 3)

    outputs = []
    for sizes in ([len(raw)], [1], [7, 0, 300, 1, 64, 2]):
        blocks = collect(stream_downsample(reads(raw, sizes), 3))
        assert all(isinstance(b, bytes) and b for b in blocks), (
            "every message is a non-empty block of PCM bytes"
        )
        pcm = b"".join(blocks)
        got = struct.unpack(f"<{len(pcm) // 2}h", pcm)
        assert len(got) == len(want) and all(abs(g - w * 32768) <= 0.5 for g, w in zip(got, want)), (
            f"the samples decimate() gives, whatever the reads, e.g. {sizes}"
        )
        outputs.append(pcm)
    assert outputs[1] == outputs[0] and outputs[2] == outputs[0], "the same bytes whatever the reads"

    pulled: list[int] = []

    async def socket():
        for i in range(100):
            pulled.append(i)
            yield raw[i * 64 : (i + 1) * 64]

    async def first_block() -> bytes:
        agen = stream_downsample(socket(), 3)
        block = await agen.__anext__()
        await agen.aclose()
        return block

    block = asyncio.run(first_block())
    assert block == outputs[0][: len(block)], "the first block is the start of the stream"
    assert len(pulled) <= 2, "send each block as soon as it is ready"


def chunk(chunk_id: bytes, payload: bytes) -> bytes:
    """One RIFF chunk: id, size, payload, and a pad byte after an odd-sized payload."""
    return chunk_id + struct.pack("<I", len(payload)) + payload + b"\x00" * (len(payload) % 2)


def riff(form: bytes, *chunks: bytes) -> bytes:
    return chunk(b"RIFF", form + b"".join(chunks))


def lst(kind: bytes, *chunks: bytes) -> bytes:
    return chunk(b"LIST", kind + b"".join(chunks))


TAGGED = riff(
    b"WAVE",
    chunk(b"fmt ", struct.pack("<HHIIHH", 1, 1, 8000, 24000, 3, 24)),
    lst(
        b"INFO",
        chunk(b"INAM", "Zoë\0".encode()),
        chunk(b"IART", b"Lin Grace\0"),
        chunk(b"ICMT", b"consent on file\0"),
    ),
    chunk(b"JUNK", lst(b"INFO", chunk(b"INAM", b"old title\0"))),  # an editor deleted this list by renaming it
    lst(
        b"adtl",
        chunk(b"labl", struct.pack("<I", 1) + b"intro\0"),
        chunk(b"labl", struct.pack("<I", 2) + b"verse 1\0"),
    ),
    chunk(b"data", bytes(range(9))),
)

AVI = riff(
    b"AVI ",
    lst(
        b"hdrl",
        chunk(b"avih", bytes(56)),
        lst(b"strl", chunk(b"strh", bytes(56)), chunk(b"strf", bytes(21))),
    ),
    lst(b"movi", chunk(b"01wb", bytes(3))),
    chunk(b"idx1", bytes(16)),
)


@pytest.mark.skip("Part 5")
def test_riff_walk() -> None:
    """Every chunk is found at any depth, and the INFO tags come from the right list."""
    chunks = walk(TAGGED)
    assert [(path, size) for path, _, size in chunks] == [
        ("RIFF:WAVE", 202),
        ("RIFF:WAVE/fmt ", 16),
        ("RIFF:WAVE/LIST:INFO", 60),
        ("RIFF:WAVE/LIST:INFO/INAM", 5),
        ("RIFF:WAVE/LIST:INFO/IART", 10),
        ("RIFF:WAVE/LIST:INFO/ICMT", 16),
        ("RIFF:WAVE/JUNK", 30),
        ("RIFF:WAVE/LIST:adtl", 42),
        ("RIFF:WAVE/LIST:adtl/labl", 10),
        ("RIFF:WAVE/LIST:adtl/labl", 12),
        ("RIFF:WAVE/data", 9),
    ], "every chunk, depth first, in file order"
    _, offset, size = chunks[-1]
    assert TAGGED[offset : offset + size] == bytes(range(9)), "offset is where the payload starts"
    assert all(TAGGED[offset - 4 : offset] == struct.pack("<I", size) for _, offset, size in chunks), (
        "offset is where the payload starts, for lists too"
    )
    assert info_tags(TAGGED) == {"INAM": "Zoë", "IART": "Lin Grace", "ICMT": "consent on file"}, (
        "tags come from LIST:INFO only, as text"
    )

    assert [path for path, _, _ in walk(AVI)] == [
        "RIFF:AVI ",
        "RIFF:AVI /LIST:hdrl",
        "RIFF:AVI /LIST:hdrl/avih",
        "RIFF:AVI /LIST:hdrl/LIST:strl",
        "RIFF:AVI /LIST:hdrl/LIST:strl/strh",
        "RIFF:AVI /LIST:hdrl/LIST:strl/strf",
        "RIFF:AVI /LIST:movi",
        "RIFF:AVI /LIST:movi/01wb",
        "RIFF:AVI /idx1",
    ], "lists nest to any depth"

    from_wave_module = wave_module_file(bytes(9), 1, 3, 8000)
    paths = [path for path, _, _ in walk(from_wave_module)]
    assert paths == ["RIFF:WAVE", "RIFF:WAVE/fmt ", "RIFF:WAVE/data"], (
        "a pad byte missing at the very end is not an error"
    )
    overrun = lst(b"INFO", b"INAM" + struct.pack("<I", 50) + b"Zoe\0")  # INAM claims 50 bytes; its list holds 4
    with pytest.raises(ValueError):
        walk(riff(b"WAVE", overrun, chunk(b"data", bytes(64))))
    with pytest.raises(ValueError):
        walk(TAGGED[:-20])  # the file was cut short
    with pytest.raises(ValueError):
        walk(b"ID3\x04" + bytes(60))  # an MP3 renamed to .wav
