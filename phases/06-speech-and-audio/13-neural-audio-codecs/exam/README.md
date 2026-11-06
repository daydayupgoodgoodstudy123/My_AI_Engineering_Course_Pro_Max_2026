# RVQCodec pair session

RVQCodec is the bottleneck of a toy neural audio codec. Audio is cut into frames, and residual vector quantization turns every frame into one code per codebook (`rvqcodec/quantize.py`). The codes travel as a packed bitstream (`rvqcodec/bitstream.py`), the codebooks are learned from audio (`rvqcodec/train.py`), live audio is coded frame by frame (`rvqcodec/stream.py`), and a tree-structured codebook offers a faster search (`rvqcodec/tree.py`). `rvqcodec/codec.py` wires these together for the API layer.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_rvq_quantizer`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the quantizer fails.

## Pt 2 `test_packet_roundtrip`

Pack the codes into a bitstream, and read them back.

## Pt 3 `test_train_codebooks`

Learn the codebooks from audio.

## Pt 4 `test_stream_codec`

Encode and decode a live stream, frame by frame.

## Pt 5 `test_tree_search`

Search a tree-structured codebook.
