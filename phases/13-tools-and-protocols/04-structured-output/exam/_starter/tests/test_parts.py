import copy
import json
import os
import time
from decimal import Decimal

import pytest
from invoicekit.decode import EOS, decode
from invoicekit.extract import check_totals, extract_invoice
from invoicekit.outcome import ParsedResult, feedback, process_model_output
from invoicekit.schema import INVOICE_SCHEMA, ValidationError, validate
from invoicekit.snapshot import ResultStore

HAPPY = """{"customer": "Müller & Söhne GmbH",
 "line_items": [{"sku": "ABC-123", "qty": 2, "unit_usd": 49.99},
                {"sku": "XYZ-9", "qty": 1, "unit_usd": 120.00}],
 "total_usd": 219.98, "currency": "USD"}
"""
CENT_OFF = HAPPY.replace("219.98", "219.99")
PROSE = "Here is your JSON: " + HAPPY
TWO_BAD_LINES = (
    '{"customer": "Acme Corp", "line_items": [{"sku": "ABC-123", "qty": 2},'
    ' {"sku": "XYZ-9", "qty": "1", "unit_usd": 120.00}], "total_usd": 219.98, "currency": "USD"}'
)
QUOTED = (
    '{"customer": "Acme Corp", "line_items": [{"sku": "ABC-123", "qty": "2", "unit_usd": "49.99",'
    ' "note": {"rush": true, "by": null}}], "total_usd": 99.980, "currency": "USD"}'
)
TRAILING_COMMA = '{"customer": "Acme", "line_items": [], "total_usd": 0, "currency": "USD",}'
REFUSAL = "__REFUSAL__  The provided text is a song lyric — not an invoice.\n"


def scripted(*replies: str):
    """A stand-in model: returns the replies in order (the last one repeats) and records each note."""
    notes: list = []

    def generate(note):
        notes.append(note)
        return replies[min(len(notes), len(replies)) - 1]

    generate.notes = notes
    return generate


def exact(value):
    """A value with the type of every part, and every Decimal with all its digits."""
    if isinstance(value, Decimal):
        return ("Decimal", str(value))
    if isinstance(value, dict):
        return {key: exact(v) for key, v in value.items()}
    if isinstance(value, (list, tuple)):
        return (type(value).__name__, [exact(v) for v in value])
    return (type(value).__name__, value)


@pytest.mark.skip("Part 1")
def test_validate_and_classify() -> None:
    """Every error is reported at its typed location, refusals are typed, and big enums stay fast."""
    reply = """{
      "customer": "Acme Corp",
      "line_items": [
        {"sku": "abc_123", "qty": 2, "unit_usd": 49.99, "discount": 0.10},
        {"sku": "XYZ-9", "qty": 1, "unit_usd": 120.00},
        {"sku": "XYZ-10", "qty": 0, "unit_usd": "12.50"}
      ],
      "total_usd": 219.98,
      "currency": "USD"
    }"""
    result = process_model_output(reply, INVOICE_SCHEMA)
    assert result.kind == "violation"
    assert feedback(result) == "\n".join([
        "$.line_items[0].discount: additional property not allowed (value: 0.10)",
        "$.line_items[0].sku: does not match pattern '^[A-Z0-9-]+$' (value: \"abc_123\")",
        "$.line_items[2].qty: below minimum 1 (value: 0)",
        "$.line_items[2].unit_usd: expected number, got str (value: \"12.50\")",
    ]), "the feedback names every error in every line item, at its path, with what the model wrote there"
    assert result.errors[2] == ValidationError(("line_items", 2, "qty"), "below minimum 1"), (
        "an array index in loc is an int"
    )

    lyric = "__REFUSAL__ The provided text is a song lyric, not an invoice."
    refusal = process_model_output(lyric, INVOICE_SCHEMA)
    assert (refusal.kind, refusal.payload, refusal.errors) == (
        "refusal",
        "The provided text is a song lyric, not an invoice.",
        [],
    ), "a refusal is a typed outcome, not a parse error"
    broken = process_model_output(TRAILING_COMMA, INVOICE_SCHEMA)
    assert (broken.kind, [e.loc for e in broken.errors]) == ("parse_error", [()])

    catalog = [f"SKU-{i:05d}" for i in range(5000)]
    schema = copy.deepcopy(INVOICE_SCHEMA)
    schema["properties"]["line_items"]["items"]["properties"]["sku"]["enum"] = catalog
    bulk = {
        "customer": "Bulk Buyer",
        "line_items": [
            {"sku": catalog[i * 7919 % 5000], "qty": 1 + i % 3, "unit_usd": Decimal("1.25")} for i in range(3000)
        ],
        "total_usd": Decimal("7500.00"),
        "currency": "USD",
    }
    untouched = copy.deepcopy(schema)
    start = time.perf_counter()
    errors = validate(schema, bulk)
    elapsed = time.perf_counter() - start
    assert errors == []
    assert elapsed < 0.1, "validation stays fast with a 5,000-SKU enum"
    assert schema == untouched, "validate leaves the schema as it was"

    terms = {
        "type": "object",
        "properties": {
            "gst_rate": {"enum": [0, 5, 12, 18, 28]},
            "pack_of": {"enum": [1, 2]},
            "terms": {"enum": ["on receipt", {"net_days": 30}, {"net_days": 60, "early_pay_pct": 2}]},
        },
    }
    accepted = process_model_output(
        '{"gst_rate": 5.0, "pack_of": 2, "terms": {"early_pay_pct": 2, "net_days": 60}}', terms
    )
    assert accepted.errors == [], "enum compares JSON values: 5.0 is 5, and object members may come in any order"
    rejected = process_model_output('{"gst_rate": false, "pack_of": true, "terms": {"net_days": 45}}', terms)
    assert [e.path for e in rejected.errors] == ["$.gst_rate", "$.pack_of", "$.terms"], (
        "false is not 0 and true is not 1"
    )


@pytest.mark.skip("Part 2")
def test_result_snapshot(tmp_path, monkeypatch) -> None:
    """Every kind of result survives a reopen exactly, and a failed save loses nothing."""
    path = str(tmp_path / "results.json")
    replies = {"po-1041": HAPPY, "po-0977": QUOTED, "po-1102": TRAILING_COMMA, "po-0310": REFUSAL}
    results = {doc: process_model_output(raw, INVOICE_SCHEMA) for doc, raw in replies.items()}
    assert [r.kind for r in results.values()] == ["ok", "violation", "parse_error", "refusal"]
    # The extraction loop also turns schema-valid replies into violations (check_totals, Part 3).
    results["po-0452"] = ParsedResult(
        "violation",
        process_model_output(CENT_OFF, INVOICE_SCHEMA).payload,
        [ValidationError(("total_usd",), "expected 219.98, the sum of qty * unit_usd")],
        CENT_OFF,
    )

    store = ResultStore(path)
    assert store.doc_ids() == []
    for doc, result in results.items():
        store.put(doc, result)
    with pytest.raises(KeyError):
        store.get("po-9999")

    reopened = ResultStore(path)
    assert reopened.doc_ids() == list(results), "a reopened store sees every result, in the order stored"
    for doc, result in results.items():
        back = reopened.get(doc)
        assert back == result, f"{doc} must round-trip exactly"
        assert exact(back.payload) == exact(result.payload), f"{doc}: amounts keep their type and every digit"
    prices = [str(item["unit_usd"]) for item in reopened.get("po-1041").payload["line_items"]]
    assert prices == ["49.99", "120.00"], "120.00 comes back as 120.00, not 120.0"

    retried = process_model_output(HAPPY.replace("Müller & Söhne GmbH", "Acme Corp"), INVOICE_SCHEMA)
    reopened.put("po-0977", retried)
    again = ResultStore(path)
    assert again.get("po-0977") == retried, "a newer result for a document replaces the old one"
    order = ["po-1041", "po-0977", "po-1102", "po-0310", "po-0452"]
    assert again.doc_ids() == order, "a replaced result keeps its place"

    moved_from = []

    def crash(src, *args, **kwargs):
        moved_from.append(os.path.dirname(os.path.abspath(src)))
        raise OSError("simulated crash while saving")

    monkeypatch.setattr(os, "replace", crash)
    monkeypatch.setattr(os, "rename", crash)
    with pytest.raises(OSError):
        again.put("po-1200", results["po-1041"])
    monkeypatch.undo()
    assert again.doc_ids() == order, "a put that fails changes nothing"
    assert ResultStore(path).get("po-0977") == retried, "a crash while saving leaves the previous snapshot intact"
    assert os.listdir(tmp_path) == ["results.json"], "a failed save leaves no temporary file behind"
    assert moved_from and all(os.path.samefile(d, tmp_path) for d in moved_from), (
        "the temporary file is written next to the snapshot"
    )


@pytest.mark.skip("Part 3")
def test_retry_extraction() -> None:
    """generate, parse, validate, check the totals, and retry with feedback, at most three times."""
    assert check_totals(json.loads(HAPPY, parse_float=Decimal)) == [], "2 × 49.99 + 120.00 is exactly 219.98"
    assert check_totals(json.loads(CENT_OFF, parse_float=Decimal)) == [
        ValidationError(("total_usd",), "expected 219.98, the sum of qty * unit_usd")
    ], "a total one cent off is wrong"
    metered = {
        "customer": "Acme Cloud",
        "line_items": [{"sku": "GPU-H100", "qty": 3, "unit_usd": Decimal("0.125")}],
        "total_usd": Decimal("0.375"),
        "currency": "USD",
    }
    assert check_totals(metered) == [], "amounts are compared exactly, without rounding"
    for total in (Decimal("0.38"), Decimal("0.3751")):
        assert check_totals(dict(metered, total_usd=total)) == [
            ValidationError(("total_usd",), "expected 0.375, the sum of qty * unit_usd")
        ], "amounts are compared exactly, without rounding or tolerance"
    fleet = dict(metered, line_items=[{"sku": "GPU-H100", "qty": 1000, "unit_usd": Decimal("25000.00")}])
    assert check_totals(dict(fleet, total_usd=Decimal("25000000.01"))) == [
        ValidationError(("total_usd",), "expected 25000000.00, the sum of qty * unit_usd")
    ], "a cent off is wrong on a large invoice too"
    whole = {
        "customer": "Acme Corp",
        "line_items": [
            {"sku": "ABC-123", "qty": 2, "unit_usd": Decimal("60.00")},
            {"sku": "XYZ-9", "qty": 1, "unit_usd": 100},
        ],
        "total_usd": 220,
        "currency": "USD",
    }
    assert check_totals(whole) == [], "a total written as 220 equals 220.00"

    model = scripted(PROSE, HAPPY)
    done = extract_invoice(model)
    assert (done.result.kind, done.attempts) == ("ok", 2), "text around the JSON is a parse error, so ask again"
    assert model.notes == [None, feedback(process_model_output(PROSE, INVOICE_SCHEMA))], (
        "the first attempt gets no note, a retry gets feedback() for the attempt before it"
    )

    model = scripted(REFUSAL, HAPPY)
    done = extract_invoice(model)
    assert (done.result.kind, done.result.payload, done.attempts) == (
        "refusal",
        "The provided text is a song lyric — not an invoice.",
        1,
    ), "a refusal ends the extraction"
    assert model.notes == [None], "a refusal is never retried"

    model = scripted(CENT_OFF, HAPPY)
    done = extract_invoice(model)
    assert (done.result.kind, model.notes) == (
        "ok",
        [None, "$.total_usd: expected 219.98, the sum of qty * unit_usd (value: 219.99)"],
    ), "a reply that fails check_totals is a violation, fed back like any other"

    model = scripted(PROSE, CENT_OFF, TWO_BAD_LINES, HAPPY)
    done = extract_invoice(model, max_retries=3)
    assert (done.result.kind, done.attempts) == ("ok", 4), "three retries means up to four attempts"
    assert exact(done.result.payload["total_usd"]) == ("Decimal", "219.98")
    assert model.notes == [
        None,
        feedback(process_model_output(PROSE, INVOICE_SCHEMA)),
        "$.total_usd: expected 219.98, the sum of qty * unit_usd (value: 219.99)",
        '$.line_items[0].unit_usd: missing required field\n$.line_items[1].qty: expected integer, got str (value: "1")',
    ], "each retry carries every error of the attempt before it"

    model = scripted(CENT_OFF)
    done = extract_invoice(model, max_retries=3)
    assert (done.result.kind, done.attempts, len(model.notes)) == ("violation", 4, 4), (
        "give up after max_retries retries and return the last result"
    )
    assert done.result.errors == [ValidationError(("total_usd",), "expected 219.98, the sum of qty * unit_usd")]

    done = extract_invoice(scripted(TWO_BAD_LINES, REFUSAL, HAPPY))
    assert (done.result.kind, done.attempts) == ("refusal", 2), "a refusal after a failed attempt also ends it"
    done = extract_invoice(scripted(CENT_OFF, HAPPY), max_retries=0)
    assert (done.result.kind, done.attempts) == ("violation", 1), "max_retries=0 is a single attempt"


ORDER = {
    "type": "object",
    "properties": {
        "currency": {"type": "string", "enum": ["USD", "EUR", "INR"]},
        "line": {
            "type": "object",
            "properties": {
                "sku": {"type": "string", "enum": ["ABC-1", "ABC-12", "XYZ-9"]},
                "qty": {"type": "integer", "minimum": 0},
                "unit": {"type": "string", "enum": ["m", "m²", "pcs"]},
            },
            "required": ["sku", "qty", "unit"],
            "additionalProperties": False,
        },
    },
    "required": ["currency", "line"],
    "additionalProperties": False,
}

# For each text decoded so far, the model's candidate next tokens, best first.
STEPS = {
    "": ["Here is", " {", EOS, '{"'],
    '{"': ['line":{"sku":"', 'cur":"USD"', 'currency":"EU'],
    '{"currency":"EU': ['"', '"}', 'R","line":{"sku":"ABC-1'],
    '{"currency":"EUR","line":{"sku":"ABC-1': ['2","qty":', '"'],
    '{"currency":"EUR","line":{"sku":"ABC-12","qty":': [EOS, "-1", ',"unit":"m²"}}', "3"],
    '{"currency":"EUR","line":{"sku":"ABC-12","qty":3': ["0", ',"unit"'],
    '{"currency":"EUR","line":{"sku":"ABC-12","qty":30': [" ", ',"unit":"m'],
    '{"currency":"EUR","line":{"sku":"ABC-12","qty":30,"unit":"m': ['²"}', '"}'],
    '{"currency":"EUR","line":{"sku":"ABC-12","qty":30,"unit":"m²"}': [EOS, ",", "}"],
}
CHOSEN = ['{"', 'currency":"EU', 'R","line":{"sku":"ABC-1', '2","qty":', "3", "0", ',"unit":"m', '²"}', "}"]
# Where the model goes after a token that should have been masked.
DETOURS = {
    " {": ['"currency":"EUR","line":{"sku":"ABC-12","qty":30,"unit":"m²"}}'],
    '{"line":{"sku":"': ['ABC-12","qty":30,"unit":"m²"},"currency":"EUR"}'],
    '{"cur":"USD"': [',"line":{"sku":"ABC-12","qty":30,"unit":"m²"}}'],
    '{"currency":"EU"': [',"line":{"sku":"ABC-12","qty":30,"unit":"m²"}}'],
    '{"currency":"EUR","line":{"sku":"ABC-1"': [',"qty":30,"unit":"pcs"}}'],
    '{"currency":"EUR","line":{"sku":"ABC-12","qty":-1': [',"unit":"m²"}}'],
    '{"currency":"EUR","line":{"sku":"ABC-12","qty":30 ': [',"unit":"m²"}}'],
    '{"currency":"EUR","line":{"sku":"ABC-12","qty":30,"unit":"m"}': ["}"],
}


def ranked(table: dict):
    """A stand-in model that looks up its candidates by the text so far and records every call."""
    calls: list[str] = []

    def model(text: str) -> list[str]:
        calls.append(text)
        return table.get(text, [EOS])

    model.calls = calls
    return model


@pytest.mark.skip("Part 4")
def test_constrained_decode() -> None:
    """Only tokens that keep the output valid are chosen, and each one is sent as soon as it is."""
    model = ranked(STEPS | DETOURS)
    chunks = list(decode(model, ORDER))
    assert all(isinstance(chunk, bytes) for chunk in chunks), "decode yields raw bytes"
    text = b"".join(chunks).decode("utf-8")
    assert text == '{"currency":"EUR","line":{"sku":"ABC-12","qty":30,"unit":"m²"}}', (
        "at every step, take the best token that keeps the output valid"
    )
    assert json.loads(text)["line"]["unit"] == "m²"
    assert chunks == [token.encode("utf-8") for token in CHOSEN], "yield each chosen token as it is, in UTF-8"
    assert model.calls == list(STEPS), "ask the model once per token, and not again once the output is complete"

    closes = ranked({
        "": ['{"currency":"USD","line":{"sku":"ABC-1'],
        '{"currency":"USD","line":{"sku":"ABC-1': ['"', '2"'],
        '{"currency":"USD","line":{"sku":"ABC-1"': [',"qty":0'],
        '{"currency":"USD","line":{"sku":"ABC-1","qty":0': ["5", ',"unit":"pcs"}}'],
        '{"currency":"USD","line":{"sku":"ABC-12"': [',"qty":0,"unit":"pcs"}}'],
        '{"currency":"USD","line":{"sku":"ABC-1","qty":05': [',"unit":"pcs"}}'],
    })
    assert b"".join(decode(closes, ORDER)) == b'{"currency":"USD","line":{"sku":"ABC-1","qty":0,"unit":"pcs"}}', (
        "a member that is a prefix of another can still end there; 05 is not an integer"
    )

    count = {"type": "integer", "minimum": 0}
    assert b"".join(decode(ranked({"": [EOS, "0"], "0": ["7", EOS]}), count)) == b"0", "0 is complete; 07 is not JSON"
    assert b"".join(decode(ranked({"": [EOS, "4"], "4": ["2"], "42": [EOS, "7"]}), count)) == b"42", (
        "EOS is allowed once the value is complete"
    )

    model = ranked(STEPS)
    stream = decode(model, ORDER)
    assert next(stream) == b'{"' and model.calls == [""], "each token is sent as soon as it is chosen"

    stuck = decode(ranked({"": ['{"currency":"'], '{"currency":"': ["GBP", "JPY", EOS]}), ORDER)
    assert next(stuck) == b'{"currency":"'
    with pytest.raises(ValueError):
        next(stuck)


PRODUCT = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": ["product"]},
        "sku": {"type": "string", "pattern": "^[A-Z0-9-]+$"},
        "qty": {"type": "integer", "minimum": 1},
        "unit_usd": {"type": "number", "minimum": 0},
    },
    "required": ["kind", "sku", "qty", "unit_usd"],
    "additionalProperties": False,
}
SERVICE = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": ["service"]},
        "description": {"type": "string", "minLength": 1},
        "hours": {"type": "number", "minimum": 0},
        "rate_usd": {"type": "number", "minimum": 0},
    },
    "required": ["kind", "description", "hours", "rate_usd"],
    "additionalProperties": False,
}
BUNDLE = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": ["bundle"]},
        "name": {"type": "string", "minLength": 1},
        "parts": {
            "type": "array",
            "items": {"oneOf": [PRODUCT, SERVICE], "discriminator": {"propertyName": "kind"}},
        },
    },
    "required": ["kind", "name", "parts"],
    "additionalProperties": False,
}
MIXED_INVOICE = {
    "type": "object",
    "properties": {
        "customer": {"type": "string", "minLength": 1},
        "line_items": {
            "type": "array",
            "items": {"oneOf": [PRODUCT, SERVICE, BUNDLE], "discriminator": {"propertyName": "kind"}},
        },
        "discount": {"oneOf": [{"type": "integer", "minimum": 0}, {"type": "number", "minimum": 0, "maximum": 1}]},
    },
    "required": ["customer", "line_items"],
    "additionalProperties": False,
}


@pytest.mark.skip("Part 5")
def test_tagged_line_items() -> None:
    """Line items are products, services or bundles of them, told apart by kind."""
    good = {
        "customer": "Acme Corp",
        "line_items": [
            {"kind": "product", "sku": "ABC-123", "qty": 2, "unit_usd": Decimal("49.99")},
            {"kind": "service", "description": "Installation", "hours": Decimal("1.5"), "rate_usd": 80},
            {
                "kind": "bundle",
                "name": "Starter kit",
                "parts": [
                    {"kind": "product", "sku": "XYZ-9", "qty": 1, "unit_usd": Decimal("120.00")},
                    {"kind": "service", "description": "Setup call", "hours": Decimal("0.5"), "rate_usd": 80},
                ],
            },
        ],
        "discount": Decimal("0.15"),
    }
    assert validate(MIXED_INVOICE, good) == [], "each line item is checked against the branch its kind names"

    reply = """{"customer": "Acme Corp", "line_items": [
      {"kind": "product", "sku": "ABC-123", "qty": 0, "unit_usd": 49.99},
      {"kind": "subscription", "plan": "pro"},
      {"kind": "service", "description": "Installation", "hours": -2, "rate_usd": 80},
      {"kind": "bundle", "name": "Starter kit", "parts": [
        {"kind": "product", "sku": "XYZ-9", "qty": 1, "unit_usd": 120.00},
        {"kind": "service", "description": "Setup call", "hours": "half an hour", "rate_usd": 80},
        {"sku": "CBL-2", "qty": 3, "unit_usd": 4.50},
        "USB cable"]}]}"""
    result = process_model_output(reply, MIXED_INVOICE)
    assert [str(e) for e in result.errors] == [
        "$.line_items[0].qty: below minimum 1",
        "$.line_items[1].kind: value 'subscription' not in enum",
        "$.line_items[2].hours: below minimum 0",
        "$.line_items[3].parts[1].hours: expected number, got str",
        "$.line_items[3].parts[2].kind: missing required field",
        "$.line_items[3].parts[3]: expected object, got str",
    ], "only the chosen branch reports errors, each at its full path"

    for discount, problems in (
        (5, []),
        (1, ["$.discount: matches 2 oneOf branches, expected exactly one"]),
        (-1, ["$.discount: matches none of the oneOf branches"]),
    ):
        assert [str(e) for e in validate(MIXED_INVOICE, dict(good, discount=discount))] == problems, (
            "without a discriminator, a value must match exactly one branch"
        )
