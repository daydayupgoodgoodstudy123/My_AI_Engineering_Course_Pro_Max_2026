import asyncio
import math
import random
import time
from dataclasses import replace

import pytest
from rvqcodec.bitstream import HEADER, MAGIC, Packet, pack, unpack
from rvqcodec.codec import Codec
from rvqcodec.quantize import mse, rvq_decode, rvq_encode
from rvqcodec.stream import Frame, decode_stream, encode_stream
from rvqcodec.train import learn_codebook, train_rvq
from rvqcodec.tree import full_search, leaf_codebook, tree_search

# Three stages for 2-sample frames; every stage works at a quarter of the scale before it.
BOOKS = [
    [[2.0, 0.0], [0.0, 2.0], [-2.0, 0.0], [0.0, -2.0]],
    [[0.5, 0.0], [0.0, 0.5], [-0.5, 0.0], [0.0, -0.5]],
    [[0.125, 0.0], [0.0, 0.125], [-0.125, 0.0], [0.0, -0.125]],
]


def lesson_signal(n: int, seed: int) -> list[float]:
    """The lesson's toy signal: a sine with a period of 100 samples plus Gaussian noise."""
    rng = random.Random(seed)
    return [math.sin(2 * math.pi * i / 100) + 0.3 * rng.gauss(0, 1.0) for i in range(n)]


def pairs(signal: list[float]) -> list[list[float]]:
    return [signal[i : i + 2] for i in range(0, len(signal), 2)]


def collect(agen) -> list:
    async def drain() -> list:
        return [item async for item in agen]

    return asyncio.run(drain())


async def chunked(signal: list[float], sizes: list[int]):
    pos = 0
    for size in sizes:
        yield signal[pos : pos + size]
        pos += size


async def replay(items: list):
    for item in items:
        yield item


@pytest.mark.skip("Part 1")
def test_rvq_quantizer() -> None:
    """Residual VQ picks the right codes, rebuilds the frames, and stays fast."""
    frames = [[1.8, 0.4], [-0.3, 2.4], [1.0, 1.0], [0.2, -1.6], [2.6, -0.9], [-2.5, 0.3], [0.4, 0.1]]
    codes = rvq_encode(frames, BOOKS)
    assert codes[0] == [0, 1, 0, 3, 0, 2, 0], "stage 0 picks the nearest codeword; ties go to the lower index"
    assert codes[1:] == [[1, 1, 1, 1, 3, 2, 2], [2, 2, 2, 0, 0, 1, 2]], (
        "every later stage quantizes what the stages before it left"
    )
    assert rvq_decode(codes, BOOKS) == [
        [1.875, 0.5], [-0.125, 2.5], [1.875, 0.5], [0.125, -1.5], [2.125, -0.5], [-2.5, 0.125], [1.375, 0.0],
    ], "decoding adds up one codeword per stage, frame by frame"
    assert rvq_decode(codes[:1], BOOKS[:1]) == [
        [2.0, 0.0], [0.0, 2.0], [2.0, 0.0], [0.0, -2.0], [2.0, 0.0], [-2.0, 0.0], [2.0, 0.0],
    ], "the first stage alone gives the coarse frames"

    rng = random.Random(0)
    big = [[rng.uniform(-1.0, 1.0), rng.uniform(-1.0, 1.0)] for _ in range(1024)]
    queries = [[rng.uniform(-1.0, 1.0), rng.uniform(-1.0, 1.0)] for _ in range(8)]
    start = time.perf_counter()
    rvq_encode(queries, [big])
    assert time.perf_counter() - start < 0.1, "nearest-codeword search should be fast on a 1024-entry codebook"

    # Trained residual codebooks keep a zero codeword next to codewords of different lengths.
    trained = [
        [[0.0, 0.0], [1.0, 0.0], [0.0, 1.0], [-1.0, 0.0], [0.0, -1.0], [3.0, 3.0]],
        [[0.0, 0.0], [0.25, 0.0], [0.0, 0.25], [-0.25, 0.0], [0.0, -0.25], [1.0, 1.0]],
    ]
    rng = random.Random(3)
    points = [[rng.uniform(-1.5, 1.5), rng.uniform(-1.5, 1.5)] for _ in range(200)]
    codes = rvq_encode(points, trained)
    errors = [mse(points, [[0.0, 0.0]] * len(points))]
    errors += [mse(points, rvq_decode(codes[:q], trained[:q])) for q in (1, 2)]
    assert errors[0] >= errors[1] >= errors[2], "adding a stage must never make the reconstruction worse"


@pytest.mark.skip("Part 2")
def test_packet_roundtrip() -> None:
    """Codes survive bit packing exactly, and the header says how to play them back."""
    encodec = Packet(24000, 320, 1024, 24000, [[0] * 75 for _ in range(8)])
    assert (encodec.frame_rate, encodec.bits_per_code) == (75, 10), (
        "24 kHz with hop 320 is 75 Hz; 1024 codes need 10 bits"
    )
    assert encodec.bitrate == 6000, "8 codebooks of 1024 codes at 75 Hz is EnCodec's 6 kbps"
    mimi = Packet(24000, 1920, 2048, 10 * 24000, [[0] * 125 for _ in range(8)])
    assert (mimi.frame_rate, mimi.bitrate) == (12.5, 1100), (
        "Mimi runs 8 codebooks of 2048 codes at 12.5 Hz: 1.1 kbps"
    )
    assert Packet(16000, 320, 1000, 16000, [[0] * 50 for _ in range(3)]).bitrate == 1500, (
        "a 1000-entry codebook still takes 10 bits per code"
    )

    small = Packet(sample_rate=100, hop=4, codebook_size=8, n_samples=8, codes=[[5, 1], [2, 7]])
    data = pack(small)
    assert data[: HEADER.size] == HEADER.pack(MAGIC, 100, 4, 8, 2, 8)
    assert data[HEADER.size :] == bytes([0b1010_1000, 0b1111_0000]), (
        "frame by frame with codebook 0 first, 3 bits per code, most significant bit first"
    )
    for packet in (
        small,
        Packet(16000, 320, 1000, 1000, [[999, 0, 512, 7], [1, 998, 0, 511], [0, 3, 999, 2]]),
        Packet(16000, 320, 4, 320, [[3]]),
        Packet(24000, 1920, 2048, 0, [[], []]),
    ):
        assert unpack(pack(packet)) == packet, "a packet must round-trip exactly"
    for bad in ([[1000]], [[1, 2]]):  # a code outside the codebook; two codes for a one-frame clip
        with pytest.raises(ValueError):
            pack(Packet(16000, 320, 1000, 320, bad))
    for broken in (data[:-1], data[:10], b"RIFF" + data[4:], data + b"\x00"):
        with pytest.raises(ValueError):
            unpack(broken)

    codec = Codec(sample_rate=100, hop=2, codebooks=BOOKS)
    signal = lesson_signal(25, seed=0)
    clip = codec.compress(signal)
    assert codec.decompress(clip) == codec.decode(codec.encode(signal)), (
        "decompress plays back what compress stored"
    )
    # the same codebooks at 100 frames per second: a frame-rate mismatch must not pass silently
    with pytest.raises(ValueError):
        Codec(sample_rate=200, hop=2, codebooks=BOOKS).decompress(clip)
    # codes from three codebooks for a codec that only has two
    with pytest.raises(ValueError):
        Codec(sample_rate=100, hop=2, codebooks=BOOKS[:2]).decompress(clip)


@pytest.mark.skip("Part 3")
def test_train_codebooks() -> None:
    """Learn codebooks with k-means++ and Lloyd, then train the stages one residual at a time."""
    points = [[0.0, 0.0], [1.0, 0.0], [8.0, 0.0], [9.0, 0.0], [0.0, 6.0], [1.0, 6.0]]
    assert learn_codebook(points, 3, iterations=0, seed=5) == [[0.0, 6.0], [8.0, 0.0], [0.0, 0.0]], (
        "k-means++ picks every next codeword with probability proportional to D(x)^2"
    )
    assert learn_codebook(points, 3, seed=5) == [[0.5, 6.0], [8.5, 0.0], [0.5, 0.0]], (
        "Lloyd moves every codeword to the mean of its vectors, in seeding order"
    )
    line = [[12.0, 0.0], [3.0, 0.0], [1.0, 0.0], [5.0, 0.0], [10.0, 0.0]]
    assert learn_codebook(line, 2, seed=3) == [[11.0, 0.0], [3.0, 0.0]], (
        "Lloyd keeps going until the codewords stop moving"
    )

    repeated = [[1.0, 1.0]] * 4 + [[-1.0, 2.0]] * 3
    codebook = learn_codebook(repeated, 4, seed=0)
    assert len(codebook) == 4 and rvq_decode(rvq_encode(repeated, [codebook]), [codebook]) == repeated, (
        "fewer distinct vectors than codewords: the spare codewords simply go unused"
    )

    train, held_out = pairs(lesson_signal(800, seed=0)), pairs(lesson_signal(800, seed=1))
    codebooks = train_rvq(train, n_stages=4, size=8, seed=0)
    assert [len(book) for book in codebooks] == [8, 8, 8, 8]
    codes = rvq_encode(held_out, codebooks)
    errors = [mse(held_out, rvq_decode(codes[:q], codebooks[:q])) for q in (1, 2, 3, 4)]
    assert all(later < earlier / 2 for earlier, later in zip(errors, errors[1:])), (
        "every stage is trained on what the stages before it left"
    )
    without_first = mse(held_out, rvq_decode(codes[1:], codebooks[1:]))
    assert without_first > 100 * errors[2], "codebook 0 carries the signal; the last codebook only refines it"


STREAM_BOOKS = [
    [[0.0, 0.0, 0.0, 0.0], [0.5, 1.0, 1.0, 0.5], [-0.5, -1.0, -1.0, -0.5],
     [1.0, 0.5, -0.5, -1.0], [-1.0, -0.5, 0.5, 1.0]],
    [[0.25, 0.0, 0.0, 0.0], [0.0, 0.25, 0.0, 0.0], [0.0, 0.0, 0.25, 0.0],
     [0.0, 0.0, 0.0, 0.25], [0.0, 0.0, 0.0, 0.0]],
]


@pytest.mark.skip("Part 4")
def test_stream_codec() -> None:
    """Streaming encode and decode give the offline result, one frame behind the input."""
    codec = Codec(sample_rate=50, hop=4, codebooks=STREAM_BOOKS)  # 12.5 frames per second, like Mimi
    signal = [round(math.sin(i / 2.0), 3) for i in range(23)]  # five whole frames and three samples
    packet = codec.encode(signal)
    offline = codec.decode(packet)
    for sizes in ([23], [1] * 23, [3, 0, 9, 4, 0, 7]):
        frames = collect(encode_stream(chunked(signal, sizes), codec))
        assert [f.codes for f in frames] == [tuple(c) for c in zip(*packet.codes)], (
            f"the same codes as Codec.encode, whatever the chunking, e.g. {sizes[:6]}"
        )
        assert [(f.index, f.length) for f in frames] == [(0, 4), (1, 4), (2, 4), (3, 4), (4, 4), (5, 3)], (
            "the last frame is zero-padded and says how many of its samples are real"
        )
        blocks = collect(decode_stream(replay(frames), codec))
        assert [s for block in blocks for s in block] == offline, (
            "streaming decode plays exactly what Codec.decode plays"
        )
    assert len(collect(encode_stream(chunked(signal[:20], [9, 11]), codec))) == 5, (
        "a stream that ends on a frame boundary has no partial frame"
    )

    pulled: list[float] = []

    async def microphone():
        for sample in signal:
            pulled.append(sample)
            yield [sample]

    async def play() -> list[tuple[int, int]]:
        blocks = decode_stream(encode_stream(microphone(), codec), codec)
        return [(len(pulled), len(block)) async for block in blocks]

    assert asyncio.run(play()) == [(4, 4), (8, 4), (12, 4), (16, 4), (20, 4), (23, 3)], (
        "every frame is played as soon as its last sample has arrived"
    )

    async def lossy():
        async for frame in encode_stream(chunked(signal, [23]), codec):
            yield replace(frame, codes=frame.codes[:1]) if frame.index % 2 else frame

    coarse = codec.decode(replace(packet, codes=packet.codes[:1]))
    expected = [coarse[i] if (i // 4) % 2 else offline[i] for i in range(len(signal))]
    played = [s for block in collect(decode_stream(lossy(), codec)) for s in block]
    assert played == expected, "a frame that lost its acoustic codes still plays from codebook 0"
    with pytest.raises(ValueError):
        collect(decode_stream(replay([Frame(0, (), 4)]), codec))


TREE = {
    "centroid": [0.0, 0.0],
    "children": [
        {
            "centroid": [-4.0, 0.0],
            "children": [{"centroid": [-5.0, 1.0]}, {"centroid": [-5.0, -1.0]}, {"centroid": [-1.0, 0.0]}],
        },
        {"centroid": [3.0, 0.0], "children": []},
        {
            "centroid": [4.0, 4.0],
            "children": [
                {"centroid": [3.0, 5.0]},
                {"centroid": [5.0, 3.0], "children": [{"centroid": [5.0, 2.0]}, {"centroid": [6.0, 4.0]}]},
            ],
        },
    ],
}


def kd_tree(points: list[list[float]]) -> dict:
    """A balanced binary tree over points; every node's centroid is the mean of its leaves."""
    n = len(points)
    node = {"centroid": [sum(p[0] for p in points) / n, sum(p[1] for p in points) / n]}
    if n > 1:
        node["children"] = [kd_tree(points[: n // 2]), kd_tree(points[n // 2 :])]
    return node


@pytest.mark.skip("Part 5")
def test_tree_search() -> None:
    """Search a tree-structured codebook greedily, and compare with checking every leaf."""
    assert leaf_codebook(TREE) == [
        [-5.0, 1.0], [-5.0, -1.0], [-1.0, 0.0], [3.0, 0.0], [3.0, 5.0], [5.0, 2.0], [6.0, 4.0],
    ], "the leaves are the codebook, numbered left to right, depth first"
    assert tree_search(TREE, [6.0, 2.5]) == (5, 7), (
        "step to the nearest child at every level, counting every distance"
    )
    assert tree_search(TREE, [0.5, 0.0]) == (3, 3), "tree search descends greedily; it does not look at every leaf"
    assert full_search(TREE, [0.5, 0.0]) == (2, 7), "full search checks every leaf and finds the nearest one"
    assert tree_search(TREE, [-5.0, 0.0]) == (0, 6), "ties go to the earlier child"
    assert full_search(TREE, [-5.0, 0.0]) == (0, 7), "ties go to the lower code"
    with pytest.raises(ValueError):
        tree_search(TREE, [1.0, 2.0, 3.0])

    grid = [[float(x), float(y)] for x in range(8) for y in range(8)]
    tree = kd_tree(grid)
    assert leaf_codebook(tree) == grid
    assert [tree_search(tree, p) for p in grid] == [(i, 12) for i in range(64)], (
        "64 leaves in 6 levels: 12 distances"
    )
    assert [full_search(tree, p) for p in grid] == [(i, 64) for i in range(64)], "full search: 64 distances"
