import asyncio
import copy
import json
import math
import struct
import time

import pytest
from bitvecbank.records import VectorRecord
from bitvecbank.metrics import truncate_embedding, binarize, cosine_similarity, search_vectors, metric_value
from bitvecbank.service import VectorService
from bitvecbank.store import VectorBank
from bitvecbank.formats import BANK_HEADER, STREAM_HEADER, RECORD_PREFIX
from bitvecbank.search import packed_hamming, binary_first_search
from bitvecbank.stream import stream_vectors
from bitvecbank.graph import descend_layers

@pytest.mark.skip("Part 1")
def test_vector_inspection_pipeline():
    """Repair projection and metric behavior consumed by the vector service."""
    service = VectorService()
    original = [3.0, 4.0, 12.0]
    card = service.inspect_projection(original, 2)
    assert card["vector"] == pytest.approx((0.6, 0.8)), "the projection is normalized within its retained dimensions"
    assert card["norm"] == pytest.approx(1.0) and original == [3.0, 4.0, 12.0], "projection inspection preserves source coordinates"
    assert service.inspect_projection([0.0, -0.0, 2.0, -3.0], 4)["bits"] == (0, 0, 1, 0), "only strictly positive coordinates set a sign bit"
    rows = [VectorRecord("z", (1.0, 0.0), {}), VectorRecord("a", (3.0, 0.0), {}), VectorRecord("m", (-2.0, 0.0), {})]
    assert [hit["key"] for hit in search_vectors((1.0, 0.0), rows, 3, "euclidean")] == ["z", "a", "m"], "nearest raw distances rank before farther vectors"
    assert [hit["key"] for hit in search_vectors((1.0, 0.0), rows, 3, "hamming")] == ["z", "a", "m"], "Hamming distance shares the ascending distance convention"
    assert [hit["key"] for hit in search_vectors((1.0, 0.0), rows, 3, "cosine")] == ["z", "a", "m"], "cosine ties preserve original bank order"
    assert [hit["key"] for hit in search_vectors((1.0, 0.0), rows, 3, "dot")] == ["a", "z", "m"], "dot similarity retains descending magnitude-sensitive ranking"
    assert truncate_embedding((0.0, -0.0, 12.0), 2) == (0.0, -0.0), "a zero retained prefix stays zero"
    assert cosine_similarity((0.0, 0.0), (1.0, 2.0)) == 0.0 and cosine_similarity((1.0, 2.0), (0.0, 0.0)) == 0.0, "either zero vector has zero cosine"
    assert cosine_similarity((3.0, 4.0), (30.0, 40.0)) == pytest.approx(1.0), "cosine preserves magnitude independence for non-unit vectors"
    assert cosine_similarity((3.0, 4.0), (-3.0, -4.0)) == pytest.approx(-1.0), "opposite directions retain negative cosine"
    for vector, dimension in (((1.0, 2.0), 3), ((1.0, 2.0), 0)):
        failed = False
        try:
            truncate_embedding(vector, dimension)
        except ValueError:
            failed = True
        assert failed, "projection shape checks remain strict"
    assert search_vectors((1.0, 0.0), rows, 0) == [], "zero requested hits returns no result"
    # Finite direction inputs retain their geometry across the binary64 range.
    for left, right, expected_cosine in (
        ((1e-200,), (1e-200,), 1.0),
        ((5e-324,), (-5e-324,), -1.0),
        ((1e200,), (1e200,), 1.0),
        ((1.7e308, 1.7e308), (1.7e308, 1.7e308), 1.0),
        ((5e-324, 1e-323), (-5e-324, -1e-323), -1.0),
        ((1e308, 1e308, 5e-324), (1e-200, -1e-200, 5e-324), 0.0),
        ((0.0, -0.0), (1.7e308, 5e-324), 0.0),
    ):
        assert cosine_similarity(left, right) == pytest.approx(expected_cosine, abs=1e-15), "finite direction cosine survives tiny, huge and mixed coordinate scales"
    for vector, expected_projection in (
        ((1e-200,), (1.0,)),
        ((5e-324,), (1.0,)),
        ((1e200,), (1.0,)),
        ((1.7e308, 1.7e308), (math.sqrt(0.5), math.sqrt(0.5))),
        ((5e-324, 1e-323), (1 / math.sqrt(5), 2 / math.sqrt(5))),
        ((1e308, 5e-324), (1.0, 0.0)),
    ):
        card = service.inspect_projection(vector, len(vector))
        assert card["vector"] == pytest.approx(expected_projection, abs=1e-15) and card["norm"] == pytest.approx(1.0), "every nonzero finite projection reaches the card as a unit direction"
    assert service.inspect_projection((5e-324, 5e-324, 1.7e308), 2)["vector"] == pytest.approx((math.sqrt(0.5), math.sqrt(0.5))), "tiny retained coordinates remain a unit projection beside a huge omitted coordinate"
    from bitvecbank.service import projection_card
    rejected_tiny = False
    try:
        projection_card((5e-324, 5e-324))
    except AssertionError:
        rejected_tiny = True
    assert rejected_tiny, "the given card never mistakes a nonzero subnormal vector for true zero"
    assert service.inspect_projection((0.0, -0.0, 1.7e308), 2)["norm"] == 0.0, "a truly zero finite prefix remains zero beside a huge omitted coordinate"
    assert metric_value((0.0, 0.0), (1e200, 1e200), "euclidean") == pytest.approx(math.sqrt(2) * 1e200), "finite representable Euclidean distances remain accurate for large coordinates"
    vectors = [tuple((((index * 17 + axis * 13) % 29) - 14) / 13 for axis in range(1024)) for index in range(24)]
    queries = [tuple((((query * 7 + axis * 5) % 23) - 11) / 9 for axis in range(1024)) for query in range(2)]
    expected = [sum(x * y for x, y in zip(query, vector)) / math.sqrt(sum(x*x for x in query) * sum(y*y for y in vector)) for query in queries for vector in vectors]
    scores = [cosine_similarity(query, vector) for query in queries for vector in vectors]
    wide_vector = tuple((((axis * 13) % 29) - 14) / 13 for axis in range(32768))
    wide_query = tuple((((axis * 5) % 23) - 11) / 9 for axis in range(32768))
    wide_expected = sum(x * y for x, y in zip(wide_query, wide_vector)) / math.sqrt(sum(x*x for x in wide_query) * sum(y*y for y in wide_vector))
    start = time.perf_counter()
    wide_score = cosine_similarity(wide_query, wide_vector)
    elapsed = time.perf_counter() - start
    assert elapsed < 0.10, "wide vector inspection should stay responsive"
    assert scores == pytest.approx(expected, rel=1e-12, abs=1e-12), "fast cosine still evaluates every non-unit vector correctly"
    assert wide_score == pytest.approx(wide_expected, rel=1e-12, abs=1e-12), "wide inspection still consumes every coordinate of the complete cosine pair"

@pytest.mark.skip("Part 2")
def test_binary64_bank_roundtrip(tmp_path):
    """Persist vector bits and ordered UTF-8 metadata with complete size checks."""
    path = tmp_path / "vectors.bv"
    rows = [
        VectorRecord("z\r\n", (-0.0, 1.0000000000000002, 5e-324), {"source": "行\r\nβ", "empty": ""}),
        VectorRecord("a", (0.0, -2.2250738585072014e-308, 0.12345678901234568), {"source": "é", "note": "二"}),
    ]
    bank = VectorBank(path)
    bank.save(rows, 3)
    dimension, loaded = VectorBank(path).load()
    assert dimension == 3 and [row.key for row in loaded] == ["z\r\n", "a"], "binary bank dimensions and declaration order survive reopening"
    assert [row.metadata for row in loaded] == [row.metadata for row in rows], "metadata retains Unicode, embedded CRLF and empty values exactly"
    assert [struct.pack("<3d", *row.vector) for row in loaded] == [struct.pack("<3d", *row.vector) for row in rows], "binary64 payload preserves signed zero, tiny values and low mantissa bits"
    data = path.read_bytes()
    sidecar = bank.metadata_path.read_bytes()
    assert BANK_HEADER.unpack_from(data) == (b"BV64", 1, 3, 2, len(sidecar)), "header declares UTF-8 byte length rather than character count"
    assert len(data) == BANK_HEADER.size + 2 * 3 * 8, "binary vector payload contains exactly the declared binary64 coordinates"
    assert [item["key"] for item in json.loads(sidecar.decode("utf-8"))] == [row.key for row in rows], "sidecar associations remain in vector order"
    malformed = [data[:-1], data + b"extra", BANK_HEADER.pack(b"BV64", 1, 3, 3, len(sidecar)) + data[BANK_HEADER.size:], BANK_HEADER.pack(b"BV64", 1, 4, 2, len(sidecar)) + data[BANK_HEADER.size:], BANK_HEADER.pack(b"BV64", 1, 3, 2, len(sidecar)+1) + data[BANK_HEADER.size:]]
    for bad in malformed:
        path.write_bytes(bad)
        failed = False
        try:
            bank.load()
        except ValueError:
            failed = True
        assert failed, "reject truncated or trailing bytes and inconsistent dimension count or metadata lengths"
    path.write_bytes(data)
    bank.metadata_path.write_bytes(sidecar[:-1])
    failed = False
    try:
        bank.load()
    except ValueError:
        failed = True
    assert failed, "sidecar truncation cannot produce a partial bank"
    bank.metadata_path.write_bytes(sidecar)
    for invalid in ([VectorRecord("bad", (1.0, 2.0), {})], [rows[0], rows[0]]):
        failed = False
        try:
            bank.save(invalid, 3)
        except ValueError:
            failed = True
        assert failed and path.read_bytes() == data and bank.metadata_path.read_bytes() == sidecar, "invalid bank shapes or duplicate keys are rejected before changing files"
    bank.save([], 3)
    assert bank.load() == (3, []), "an empty bank retains its positive declared dimension"
    assert data[BANK_HEADER.size:] == struct.pack("<6d", *(value for row in rows for value in row.vector)), "bank payload uses the declared little-endian binary64 wire representation"

@pytest.mark.skip("Part 3")
def test_binary_first_dense_rerank(monkeypatch):
    """Mask packed tails, select m by Hamming, and rerank only that shortlist."""
    import bitvecbank.metrics as metric_module
    assert packed_hamming(b"\x80\xff", b"\x80\x80", 9) == 0, "unused low padding bits never contribute to Hamming distance"
    assert packed_hamming(b"\xff\x80", b"\x00\x00", 9) == 9, "valid bits in every packed byte contribute via XOR popcount"
    assert packed_hamming(b"\x00", b"\xff", 8) == 8, "byte-aligned dimensions keep the full final byte"
    assert packed_hamming(b"\x80", b"\x7f", 1) == 1, "one-dimensional codes distinguish the valid high bit from all padding"
    rows = [VectorRecord("z", (10.0, 1.0), {}), VectorRecord("a", (1.0, 10.0), {}), VectorRecord("m", (1.0, -0.001), {})]
    query = (1.0, 0.01)
    calls = []
    original = metric_module.metric_value
    def observe(a, b, metric):
        calls.append(tuple(b))
        return original(a, b, metric)
    with monkeypatch.context() as patch:
        patch.setattr(metric_module, "metric_value", observe)
        hits = binary_first_search(query, rows, 2, 1, "cosine")
    assert calls == [rows[0].vector, rows[1].vector], "dense scoring touches every shortlisted candidate and no excluded candidate"
    assert [(hit["key"], hit["hamming"], hit["binary_rank"], hit["rank"], hit["index"]) for hit in hits] == [("z", 0, 1, 1, 0)], "the global dense winner excluded by the binary shortlist cannot re-enter"
    assert hits[0]["score"] == pytest.approx(original(query, rows[0].vector, "cosine")), "reranking reports the repaired raw dense metric value"
    expanded = binary_first_search(query, rows, 3, 1, "cosine")
    assert expanded[0]["key"] == "m" and expanded[0]["binary_rank"] == 3, "shortlist budget is independent from final result count"
    assert len(binary_first_search(query, rows, 1, 9)) == 1, "final count cannot manufacture candidates beyond the shortlist"
    assert len(binary_first_search(query, rows, 20, 20)) == 3, "oversized budgets clamp to the actual bank size"
    # Distinct coarse distances, tied dense values: use original bank order.
    ties = [VectorRecord("earlier", (1.0, -1.0), {}), VectorRecord("later", (1.0, 100.0), {})]
    tied = binary_first_search((1.0, 0.0), ties, 2, 2, "dot")
    assert [(hit["key"], hit["binary_rank"], hit["rank"]) for hit in tied] == [("earlier", 1, 1), ("later", 2, 2)], "dense ties preserve original bank positions"
    # Here coarse order differs from bank order but raw dot values still tie.
    ties = [VectorRecord("earlier", (1.0, 100.0), {}), VectorRecord("later", (1.0, -1.0), {})]
    tied = binary_first_search((1.0, 0.0), ties, 2, 2, "dot")
    assert [(hit["key"], hit["binary_rank"]) for hit in tied] == [("earlier", 2), ("later", 1)], "dense ties do not inherit the coarse ranking order"
    assert [hit["key"] for hit in binary_first_search(query, rows, 3, 3, "euclidean")] == ["m", "z", "a"], "the two-stage pipeline uses the repaired dense metric ordering"
    for m, k in ((0, 3), (3, 0)):
        calls.clear()
        with monkeypatch.context() as patch:
            patch.setattr(metric_module, "metric_value", observe)
            assert binary_first_search(query, rows, m, k) == [], "zero shortlist or final count means no hits"
        assert calls == [], "zero budgets perform no dense rescore"
    assert binary_first_search(query, [], 3, 3) == [], "empty banks yield no fabricated nearest neighbor"
    for m, k in ((-1, 2), (2, -1), (True, 2), (2, True)):
        failed = False
        try:
            binary_first_search(query, rows, m, k)
        except ValueError:
            failed = True
        assert failed, "binary and final budgets remain nonnegative exact integers"
    for a, b, dimension in ((b"", b"", 1), (b"\x00", b"\x00", 9)):
        failed = False
        try:
            packed_hamming(a, b, dimension)
        except ValueError:
            failed = True
        assert failed, "packed code lengths must agree with the declared dimension"

@pytest.mark.skip("Part 4")
def test_packed_vector_wire_stream():
    """Emit the binary header and complete ordered records without reading ahead."""
    rows = [VectorRecord("β", (1.0,-1.0,0.0,2.0,-2.0,3.0,0.0,0.0,1.0), {"source": "行\r\n"}), VectorRecord("a", (0.0,)*9, {"empty": ""})]
    state = {"pulled": 0, "closed": False}
    async def source():
        try:
            for row in rows:
                state["pulled"] += 1
                yield row
        finally:
            state["closed"] = True
    async def collect():
        stream = stream_vectors(source(), 9)
        data = b""
        while len(data) < STREAM_HEADER.size:
            data += await anext(stream)
        assert data == STREAM_HEADER.pack(b"BVS1", 9) and state["pulled"] == 0, "emit the header once before pulling the first embedding"
        while len(data) < STREAM_HEADER.size + RECORD_PREFIX.size:
            data += await anext(stream)
        metadata_size = RECORD_PREFIX.unpack_from(data, STREAM_HEADER.size)[0]
        first_end = STREAM_HEADER.size + RECORD_PREFIX.size + metadata_size + 2
        while len(data) < first_end:
            data += await anext(stream)
        assert state["pulled"] == 1 and len(data) == first_end, "emit the first complete vector record before pulling the second"
        chunks = [data] + [chunk async for chunk in stream]
        assert state["closed"], "the given ownership wrapper closes the embedding source"
        return b"".join(chunks)
    wire = asyncio.run(collect())
    # A transport may split a multibyte metadata character or a packed code.
    chunks = [wire[index:index+1] for index in range(len(wire))]
    merged = b"".join(chunks)
    assert STREAM_HEADER.unpack_from(merged) == (b"BVS1", 9), "the wire header preserves the declared non-byte-aligned dimension"
    offset = STREAM_HEADER.size
    decoded = []
    while offset < len(merged):
        metadata_size = RECORD_PREFIX.unpack_from(merged, offset)[0]
        offset += RECORD_PREFIX.size
        metadata = merged[offset:offset+metadata_size]
        offset += metadata_size
        code = merged[offset:offset+2]
        offset += 2
        decoded.append((json.loads(metadata.decode("utf-8")), code))
    assert offset == len(merged) and len(decoded) == 2, "each declared record carries its entire metadata and packed payload"
    assert [item[0] for item in decoded] == [{"key": row.key, "metadata": row.metadata} for row in rows], "UTF-8 metadata byte lengths preserve exact record associations"
    assert [item[1] for item in decoded] == [b"\x94\x80", b"\x00\x00"], "streaming reuses the supplied canonical sign-bit packer"
    async def empty():
        if False:
            yield rows[0]
    async def collect_empty():
        return b"".join([chunk async for chunk in stream_vectors(empty(), 9)])
    assert asyncio.run(collect_empty()) == STREAM_HEADER.pack(b"BVS1", 9), "an empty embedding source still emits exactly one dimension header"
    async def wrong_dimension():
        yield VectorRecord("bad", (1.0,) * 8, {})
    async def collect_wrong_dimension():
        return b"".join([chunk async for chunk in stream_vectors(wrong_dimension(), 9)])
    failed = False
    try:
        asyncio.run(collect_wrong_dimension())
    except ValueError:
        failed = True
    assert failed, "wire records must match the declared stream dimension"

    ordered = VectorRecord("leading-positive", (1.0,) + (-1.0,) * 8, {"source": "coordinate order"})
    async def asymmetric_source():
        yield ordered
    async def asymmetric_wire():
        return b"".join([piece async for piece in stream_vectors(asymmetric_source(), 9)])
    asymmetric = asyncio.run(asymmetric_wire())
    metadata_size = RECORD_PREFIX.unpack_from(asymmetric, STREAM_HEADER.size)[0]
    metadata_start = STREAM_HEADER.size + RECORD_PREFIX.size
    original_metadata = json.loads(asymmetric[metadata_start:metadata_start + metadata_size].decode("utf-8"))
    original_code = asymmetric[metadata_start + metadata_size:]
    assert STREAM_HEADER.unpack_from(asymmetric) == (b"BVS1", 9) and original_metadata == {"key": ordered.key, "metadata": ordered.metadata} and original_code == b"\x80\x00", "the complete asymmetric wire record retains its original coordinates and metadata"

@pytest.mark.skip("Part 5")
def test_supplied_layer_descent():
    """Greedily inspect every supplied layer, carrying the best node downward."""
    rows = [VectorRecord(key, (distance, 0.0), {}) for key, distance in [("E",9.0),("B",5.0),("C",2.0),("D",3.0),("T",2.0),("A",10.0)]]
    layers = [
        {"E": ["B", "A"], "B": ["E"], "A": ["E"]},
        {"E": ["D"], "B": ["T", "C", "E"], "C": ["B", "D"], "D": ["C"], "T": ["B"], "A": ["E"]},
    ]
    saved = copy.deepcopy(layers)
    report = descend_layers((0.0,0.0), rows, layers, "E")
    assert report == {"best": "C", "score": 2.0, "layers": [{"layer":0,"path":["E","B"],"best":"B"}, {"layer":1,"path":["B","C"],"best":"C"}]}, "carry the best node into each lower layer and inspect its new neighborhood"
    assert layers == saved, "graph inspection leaves supplied adjacency unchanged"
    flat = [VectorRecord(key, (1.0,0.0), {}) for key in ("early", "middle", "late")]
    plateau = [{"early":["middle"], "middle":["late","early"], "late":["middle"]}]
    assert descend_layers((0.0,0.0), flat, plateau, "late")["layers"][0]["path"] == ["late","middle","early"], "strict improvement in score and bank-position key resolves cyclic plateaus"
    assert descend_layers((0.0,0.0), [rows[0]], [{"E":[]}], "E")["best"] == "E", "an isolated entry remains the layer's best node"
    # Different metadata identifiers must not substitute for metric order.
    cosine_rows = [VectorRecord("start", (9.0,9.0), {}), VectorRecord("near", (2.0,0.0), {}), VectorRecord("opposite", (-1.0,0.0), {})]
    cosine_layers = [{"start":["opposite","near"], "near":["start"], "opposite":["start"]}]
    assert descend_layers((1.0,0.0), cosine_rows, cosine_layers, "start", "cosine")["best"] == "near", "layer descent uses the repaired metric rather than neighbor encounter order"
    for bad in ([{"E":["missing"]}], [{"E":[]},{"B":[]}]):
        failed = False
        try:
            descend_layers((0.0,0.0), rows, bad, "E")
        except ValueError:
            failed = True
        assert failed, "validate all layer membership before inspecting paths"
    directed = [VectorRecord(key, (distance, 0.0), {}) for key, distance in (("entry", 9.0), ("local", 5.0), ("hidden", 1.0))]
    adjacency = [{"entry": ["local"], "local": [], "hidden": ["local"]}]
    assert descend_layers((0.0, 0.0), directed, adjacency, "entry") == {"best": "local", "score": 5.0, "layers": [{"layer": 0, "path": ["entry", "local"], "best": "local"}]}, "greedy descent respects directed edges and stops at a local optimum"
