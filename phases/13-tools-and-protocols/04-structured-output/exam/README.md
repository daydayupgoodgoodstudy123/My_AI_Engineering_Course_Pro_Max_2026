# InvoiceKit pair session

InvoiceKit turns a model's reply to an invoice-extraction prompt into typed data. `invoicekit/schema.py` is a JSON Schema 2020-12 subset validator that reports errors at typed locations, `invoicekit/outcome.py` sorts one raw reply into ok, schema violation, parse error or refusal, `invoicekit/snapshot.py` keeps results on disk, `invoicekit/extract.py` runs the retry loop for providers without strict mode, and `invoicekit/decode.py` is a constrained decoder for open-weights models.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_validate_and_classify`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why the validator and the reply classifier fail.

## Pt 2 `test_result_snapshot`

Keep extraction results on disk.

## Pt 3 `test_retry_extraction`

Extract an invoice, retrying with feedback when the reply is wrong.

## Pt 4 `test_constrained_decode`

Decode under a schema, one token at a time.

## Pt 5 `test_tagged_line_items`

Line items come in several kinds.
