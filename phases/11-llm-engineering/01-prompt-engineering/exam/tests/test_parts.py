import asyncio
import copy
import csv
import hashlib
import io
import json
import time

import pytest
from promptbench.bank import Revision, TemplateBank
from promptbench.prompts import Pattern, build_prompt, render_fields
from promptbench.report import pattern_scorecard
from promptbench.scoring import compare_models, score_response
from promptbench.service import PromptService
from promptbench.stream import COLUMNS, stream_scores


def replay(response, tokens=12, latency=3.5):
    return {"response": response, "tokens": tokens, "api_latency_ms": latency}


def scored(case_id, pattern, responses, criteria):
    comparison, _ = compare_models(responses, criteria)
    return {"case_id": case_id, "pattern": pattern, "comparison": comparison}


def collect(generator):
    async def drain():
        return [row async for row in generator]
    return asyncio.run(drain())


@pytest.mark.skip("Part 1")
def test_prompt_builders() -> None:
    """Preview and conversation builders retain named values, turns and literal text efficiently."""
    pattern = Pattern("persona", "Role: {role}\nTask: {task}\nRole again: {role}",
                      ("role", "task"), 0.3, "a precise persona")
    service = PromptService({"persona": pattern})
    variables = {"task": "Explain API limits", "unused": "not a role", "role": "Technical writer"}
    snapshot = copy.deepcopy(variables)
    preview = service.preview("persona", variables)
    assert preview["user"] == "Role: Technical writer\nTask: Explain API limits\nRole again: Technical writer", (
        "bind template variables by their declared names"
    )
    assert variables == snapshot, "preview leaves caller variables unchanged"
    assert preview["metadata"] == {"description": "a precise persona", "variables_used": ["role", "task"]}
    assert preview["temperature"] == 0.3 and preview["pattern"] == "persona"
    turns = [("user", "first"), ("assistant", "prior answer"), ("user", ""), ("assistant", "0")]
    assert service.conversation("persona", turns)["messages"][1:] == [
        {"role": role, "content": content} for role, content in turns
    ], "conversation retains assistant turns and empty content in order"
    assert turns == [("user", "first"), ("assistant", "prior answer"), ("user", ""), ("assistant", "0")]
    assert service.preview("persona", variables, "")["system"] == "", "an empty system override is intentional"
    assert service.conversation("persona", [], "")["messages"] == [{"role": "system", "content": ""}]
    assert service.preview("persona", variables)["system"] == "You are an AI assistant using persona."
    assert service.preview("persona", variables, "Custom rules")["system"] == "Custom rules"
    with pytest.raises(ValueError):
        service.preview("persona", {"role": "writer"})
    with pytest.raises(KeyError):
        service.preview("missing", variables)

    names = tuple(f"v{i}" for i in range(4500))
    template = "|".join("{" + name + "}" for name in names)
    values = {name: "x" for name in names}
    start = time.perf_counter()
    rendered = render_fields(template, values)
    assert time.perf_counter() - start < 0.07, "wide template rendering should stay responsive"
    assert rendered == "|".join(["x"] * len(names)), "fast rendering keeps every field"

    literal = Pattern("literal", '{{"task": "{task}"}} / {other} / {task}', ("task", "other"))
    output = build_prompt(literal, {"other": "{{literal}}", "task": "{other}"})["user"]
    assert output == '{"task": "{other}"} / {{literal}} / {other}', (
        "inserted values and escaped braces remain literal"
    )
    assert render_fields("{z}/{f}/{empty}", {"z": 0, "f": False, "empty": ""}) == "0/False/"
    assert render_fields("nothing {{missing}} here", {}) == "nothing {missing} here"
    with pytest.raises(ValueError):
        render_fields("{name.attr}", {"name": "x"})


@pytest.mark.skip("Part 2")
def test_template_bank_roundtrip(tmp_path) -> None:
    """Named revisions preserve exact UTF-8 text and independent metadata after reopening."""
    path = tmp_path / "bank"
    template = '  中文 café\r\n{{"message": "{task}"}}\r\n\tend  '
    first = Pattern("zeta", template, ("task",), -0.0, "notes\nwith Unicode ✓")
    same_text = Pattern("alpha", template, ("task",), 0.375, "different metadata")
    bank = TemplateBank(path)
    digest = bank.add(first, "v10", "")
    assert digest == hashlib.sha256(template.encode("utf-8")).hexdigest(), "the digest identifies exact template bytes"
    assert bank.add(same_text, "v2", None) == digest, "identical text shares one object"
    second = Pattern("zeta", "new {task}\n", ("task",), 0.1 + 0.2, "next")
    second_digest = bank.add(second, "v1", "System\r\n")
    assert second_digest != digest
    assert bank.get("zeta", "v10") == Revision(first, "v10", digest, ""), "a revision round-trips exactly"
    assert json.dumps(bank.get("zeta", "v10").pattern.temperature) == "-0.0", "keep the stored zero sign"
    with pytest.raises(ValueError):
        bank.add(first, "v10")
    with pytest.raises(KeyError):
        bank.get("zeta", "missing")
    bank.close()
    reopened = TemplateBank(path)
    assert reopened.revisions() == [Revision(first, "v10", digest, ""),
                                    Revision(same_text, "v2", digest, None),
                                    Revision(second, "v1", second_digest, "System\r\n")], (
        "reopened versions keep insertion order and independent metadata"
    )
    assert len(list((path / "objects").iterdir())) == 2, "store each distinct template body once"
    assert (path / "objects" / digest).read_bytes() == template.encode("utf-8"), "preserve CRLF and Unicode bytes"
    (path / "objects" / digest).write_bytes(b"tampered")
    with pytest.raises(ValueError, match="digest"):
        reopened.get("alpha", "v2")
    reopened.close()


    ordered_path = tmp_path / "ordered-bank"
    ordered = Pattern("ordered", "{z}/{a}", ("z", "a"), 0.12345678901234566, "ordered variables")
    ordered_bank = TemplateBank(ordered_path)
    ordered_digest = ordered_bank.add(ordered, "v1", None)
    ordered_bank.close()
    ordered_reopened = TemplateBank(ordered_path)
    assert ordered_reopened.get("ordered", "v1") == Revision(ordered, "v1", ordered_digest, None), (
        "declared variable order survives reopening"
    )
    ordered_reopened.close()



@pytest.mark.skip("Part 3")
def test_score_and_compare() -> None:
    """Each enabled lesson rubric contributes once; model ties preserve the replay order."""
    criteria = {"max_words": 3, "required_keywords": ["API", "limit", "missing"],
                "forbidden_phrases": ["in conclusion", "BANNED"], "expected_format": "numbered_list"}
    before = copy.deepcopy(criteria)
    scores = score_response("1. api limit\n2. Banned", criteria)
    assert scores == {"word_count": 5, "length_compliant": False,
                      "keywords_found": ["API", "limit"], "keyword_coverage": 2 / 3,
                      "forbidden_violations": ["BANNED"], "no_violations": False,
                      "format_valid": True, "composite_score": 0.417}, (
        "score every enabled rubric component independently"
    )
    assert criteria == before
    assert score_response("anything", {}) == {"composite_score": 0.0}
    assert score_response("one", {"max_words": 1}) == {"word_count": 1, "length_compliant": True, "composite_score": 1.0}, (
        "only enabled compliance components enter the composite"
    )
    assert score_response("", {"max_words": 0})["length_compliant"] is True
    assert score_response("", {"required_keywords": []})["keyword_coverage"] == 1.0, "empty keyword requirements have full coverage"
    assert score_response("api", {"required_keywords": ["API", "api"]})["keywords_found"] == ["API", "api"]
    assert score_response("x", {"forbidden_phrases": []})["no_violations"] is True
    for value in ('{"x": 1}', '[1, "中文"]', '"scalar"', '42', 'true', 'null'):
        assert score_response(value, {"expected_format": "json"})["format_valid"] is True, "JSON format accepts any complete JSON value"
    for invalid in ('```json\n{}\n```', '{} trailing', '{bad', ''):
        assert score_response(invalid, {"expected_format": "json"})["format_valid"] is False
    assert score_response("1. one", {"expected_format": "numbered_list"})["format_valid"] is False, "a numbered list needs at least two entries"
    assert score_response("1. one\n2. two", {"expected_format": "numbered_list"})["format_valid"] is True
    assert score_response(" 1. one\n 2. two", {"expected_format": "numbered_list"})["format_valid"] is False
    assert score_response("  * one\nplain\n", {"expected_format": "bullet_points"})["format_valid"] is True
    assert score_response("- one\nplain\nplain", {"expected_format": "bullet_points"})["format_valid"] is False
    assert score_response("", {"expected_format": "bullet_points"})["format_valid"] is True
    assert score_response("text", {"expected_format": "other"})["format_valid"] is True
    results = {"zeta": replay("API", 11, 9.25), "alpha": replay("api", 3, 1.125), "low": replay("no", 1, 0.5)}
    saved = copy.deepcopy(results)
    comparison, ranked = compare_models(results, {"required_keywords": ["API"]})
    assert [name for name, _ in ranked] == ["zeta", "alpha", "low"], "equal model scores retain replay order"
    assert comparison["alpha"] == {"scores": {"keywords_found": ["API"], "keyword_coverage": 1.0, "composite_score": 1.0}, "tokens": 3, "latency_ms": 1.125}
    assert results == saved, "scoring leaves replay results unchanged"
    assert compare_models({}, {}) == ({}, [])


    assert score_response("capillary", {"required_keywords": ["API"]})["keyword_coverage"] == 1.0, (
        "required keywords use case-insensitive substring matching"
    )
    assert score_response("preBANNEDpost", {"forbidden_phrases": ["banned"]})["no_violations"] is False, (
        "forbidden phrases use case-insensitive substring matching"
    )
    assert score_response("1 note\nplain", {"expected_format": "bullet_points"})["format_valid"] is True, (
        "bullet detection retains the source Python prefix heuristic"
    )



@pytest.mark.skip("Part 4")
def test_stream_scores() -> None:
    """CSV preserves replay text, emits per case, and closes an interrupted source."""
    cases = [{"case_id": 'c,"1"', "pattern": "persona\nnotes", "criteria": {"required_keywords": ["API"]},
              "results": {'model,"z"': replay('API, "quote"\nnext 中文', 7, 0.125), "a": replay("other", 2, 4.0)}},
             {"case_id": "c2", "pattern": "boundary", "criteria": {}, "results": {"z": replay("", 0, 0.0)}}]
    async def source():
        for case in cases:
            yield case
    text = "".join(collect(stream_scores(source())))
    reader = csv.DictReader(io.StringIO(text, newline=""))
    rows = list(reader)
    assert tuple(reader.fieldnames) == COLUMNS, "the stream starts with the declared CSV header"
    assert rows == [
        {"case_id": 'c,"1"', "pattern": "persona\nnotes", "model": 'model,"z"', "response": 'API, "quote"\nnext 中文', "composite_score": "1.0", "tokens": "7", "latency_ms": "0.125"},
        {"case_id": 'c,"1"', "pattern": "persona\nnotes", "model": "a", "response": "other", "composite_score": "0.0", "tokens": "2", "latency_ms": "4.0"},
        {"case_id": "c2", "pattern": "boundary", "model": "z", "response": "", "composite_score": "0.0", "tokens": "0", "latency_ms": "0.0"},
    ], "CSV keeps every replay field and model order"
    pulled = []
    closed = []
    async def probe():
        try:
            for i in range(100):
                pulled.append(i)
                yield cases[0]
        finally:
            closed.append(True)
    async def first_row():
        generator = stream_scores(probe())
        header = await generator.__anext__()
        assert pulled == [], "the header does not consume cases"
        row = await generator.__anext__()
        await generator.aclose()
        assert closed == [True], "close the replay source before returning from client close"
        return header + row
    assert len(list(csv.DictReader(io.StringIO(asyncio.run(first_row()), newline="")))) == 1
    assert pulled == [0], "emit case rows before fetching another case"
    assert closed == [True], "close the replay source when the client stops"
    async def empty():
        if False:
            yield {}
    assert list(csv.DictReader(io.StringIO("".join(collect(stream_scores(empty())))))) == []


    order_case = {"case_id": "order", "pattern": "p", "criteria": {"required_keywords": ["API"]},
                  "results": {"low": replay("no"), "high": replay("API"), "tied": replay("API")}}
    async def ordered_source():
        yield order_case
    ordered_rows = list(csv.DictReader(io.StringIO("".join(collect(stream_scores(ordered_source()))), newline="")))
    assert [row["model"] for row in ordered_rows] == ["low", "high", "tied"], (
        "CSV model order is independent of score ranking"
    )

    boundary_case = {"case_id": "bare\rcase", "pattern": "plain\rpattern", "criteria": {},
                     "results": {"bare\rmodel": replay("  left\rright  ", 0, 0.0),
                                 "crlf": replay("line\r\nline", 1, 0.25)}}
    async def boundary_source():
        yield boundary_case
    boundary_rows = list(csv.DictReader(io.StringIO("".join(collect(stream_scores(boundary_source()))), newline="")))
    assert boundary_rows == [
        {"case_id": "bare\rcase", "pattern": "plain\rpattern", "model": "bare\rmodel", "response": "  left\rright  ",
         "composite_score": "0.0", "tokens": "0", "latency_ms": "0.0"},
        {"case_id": "bare\rcase", "pattern": "plain\rpattern", "model": "crlf", "response": "line\r\nline",
         "composite_score": "0.0", "tokens": "1", "latency_ms": "0.25"},
    ], "CSV preserves bare CR, CRLF and surrounding whitespace"



@pytest.mark.skip("Part 5")
def test_pattern_scorecard() -> None:
    """Nested pattern/model/case reports expose coverage and weakest observed criteria."""
    reports = [scored("same", "persona", {"z": replay("API", 7, 2.25), "a": replay("no", 3, 5.0)},
                      {"max_words": 1, "required_keywords": ["API"]}),
               scored("other", "persona", {"z": replay("two words", 5, 1.75)}, {"max_words": 1}),
               scored("same", "boundary", {"z": replay("API", 2, 0.125)}, {"required_keywords": ["missing"]}),
               scored("no-rubric", "empty", {"z": replay("x", 0, 0.0)}, {})]
    saved = copy.deepcopy(reports)
    card = pattern_scorecard(reports)
    assert list(card) == ["persona", "boundary", "empty"] and list(card["persona"]) == ["z", "a"]
    assert card["persona"]["z"] == {
        "case_ids": ["same", "other"], "tokens": 12, "mean_latency_ms": 2.0, "mean_composite": 0.5,
        "criteria": {"length_compliant": {"count": 2, "mean": 0.5}, "keyword_coverage": {"count": 1, "mean": 1.0},
                     "no_violations": {"count": 0, "mean": None}, "format_valid": {"count": 0, "mean": None}},
        "weakest_criterion": "length_compliant",
    }, "criterion means use observed coverage, not the total case count"
    assert card["persona"]["a"]["weakest_criterion"] == "keyword_coverage", "present zero scores can be the weakest criterion"
    assert card["boundary"]["z"]["case_ids"] == ["same"], "same case labels in different patterns remain independent"
    assert card["empty"]["z"]["weakest_criterion"] is None, "missing criteria are not failed criteria"
    tied = [scored("tie", "p", {"m": replay("", 1, 1.0)}, {"max_words": 1, "required_keywords": []})]
    assert pattern_scorecard(tied)["p"]["m"]["weakest_criterion"] == "length_compliant", "weakest ties follow declared criterion order"
    assert pattern_scorecard([]) == {}
    with pytest.raises(ValueError):
        pattern_scorecard(reports + [reports[0]])
    assert reports == saved, "scorecard aggregation does not mutate source reports"
