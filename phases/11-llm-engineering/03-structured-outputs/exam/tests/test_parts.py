import asyncio
import copy
import json
import time

import pytest
from fieldshape.descriptors import ArrayOf, ModelSpec, SchemaField, MISSING
from fieldshape.flat import model_to_schema, python_type_to_schema
from fieldshape.service import ExtractionService
from fieldshape.store import DescriptorStore
from fieldshape.compiler import compile_model
from fieldshape.replay import stream_extractions, parse_extraction
from fieldshape.tree import group_issues
from fieldshape.validation import ValidationIssue, validate_schema

@pytest.mark.skip("Part 1")
def test_flat_extraction_adapter():
    """Repair flat field conversion used by the existing extraction service."""
    service = ExtractionService()
    assert service.validate_flat("Tags", {"tags": SchemaField(list, default=None)}, {"tags": ["audio"]}) == [], "legacy lists contain compiled string schemas"
    fields = {"title": SchemaField(str, default="untitled"), "note": SchemaField(str, required=False, default=None)}
    assert service.validate_flat("Note", fields, {"title": "hello"}) == [], "required follows explicit flags rather than default annotations"
    assert [(issue.path, issue.code) for issue in service.validate_flat("Note", fields, {})] == [(("title",), "required")], "a required key stays required even when a default is recorded"
    bounded = {"price": SchemaField(float, minimum=0), "debt": SchemaField(int, maximum=0)}
    issues = service.validate_flat("Bounds", bounded, {"price": -0.25, "debt": 1})
    assert [(issue.path, issue.code) for issue in issues] == [(("price",), "minimum"), (("debt",), "maximum")], "zero is a present numeric boundary"
    assert service.validate_flat("Bounds", bounded, {"price": 0, "debt": 0}) == [], "zero boundary endpoints remain inclusive"
    assert service.validate_flat("Note", fields, {"title": "x", "note": None})[0].code == "type", "optional omission does not make explicit null valid"
    enum = ["audio", "video"]
    schema = model_to_schema("Media", {"kind": SchemaField(str, enum=enum), "tags": SchemaField(list), "flag": SchemaField(bool), "n": SchemaField(int)})
    assert schema["required"] == ["kind", "tags", "flag", "n"], "flat fields retain declaration order"
    assert schema["properties"]["tags"] == {"type": "array", "items": {"type": "string"}}, "legacy lists retain their container and typed items"
    assert [x.code for x in validate_schema({"kind": "bad", "tags": [3], "flag": 1, "n": True}, schema)] == ["enum", "type", "type", "type"], "schema generation preserves every primitive type and enum"
    schema["properties"]["kind"]["enum"].append("new")
    assert enum == ["audio", "video"], "compiled fragments do not alias descriptor metadata"
    assert python_type_to_schema(SchemaField(str, enum=enum))["enum"] == enum, "separate compilations start from the original descriptor"
    assert python_type_to_schema(SchemaField(int, minimum=10 ** 400))["minimum"] == 10 ** 400, "integer bounds are not coerced through floating point"
    rejected = False
    try:
        model_to_schema("Flat", {"child": SchemaField(ArrayOf(int))})
    except ValueError:
        rejected = True
    assert rejected, "the flat entry point does not pretend to compile recursive descriptors"
    wide = {f"field_{i}": SchemaField(int, required=i % 3 != 0, minimum=0) for i in range(18000)}
    started = time.perf_counter()
    compiled = model_to_schema("Wide", wide)
    elapsed = time.perf_counter() - started
    assert elapsed < 0.055, "wide model compilation should stay responsive"
    assert list(compiled["properties"]) == list(wide), "fast compilation still emits every ordered field"
    assert compiled["required"] == [name for name, field in wide.items() if field.required], "fast compilation retains every explicit required flag"
    assert all(fragment == {"type": "integer", "minimum": 0} for fragment in compiled["properties"].values()), "fast compilation retains bounds on every field"
    compiled["properties"]["field_0"]["minimum"] = -9
    assert compiled["properties"]["field_1"]["minimum"] == 0, "wide fields own independent schema fragments"

@pytest.mark.skip("Part 2")
def test_descriptor_snapshot(tmp_path, monkeypatch):
    """Round-trip descriptor metadata, preserving absence and atomic replacement."""
    import fieldshape.store as store_module
    path = tmp_path / "descriptor.json"
    model = ModelSpec("商品\r\n", {
        "z": SchemaField(str, required=False),
        "a": SchemaField(str, required=False, default=None, enum=["β", "α"]),
        "amount": SchemaField(float, required=True, default=0, minimum=0, maximum=0),
        "rows": SchemaField(ArrayOf(ModelSpec("Row", {"q": SchemaField(int)}), min_items=0, max_items=4), default=[]),
        "meta": SchemaField(bool, default={"line": "first\r\nsecond", "enabled": False}),
    })
    store = DescriptorStore(path)
    store.save(model)
    reopened = DescriptorStore(path).load()
    assert reopened == model, "descriptor values and nested node types survive reopening exactly"
    assert list(reopened.fields) == ["z", "a", "amount", "rows", "meta"], "snapshot preserves field declaration order rather than sorting names"
    assert reopened.fields["z"].default is MISSING and reopened.fields["a"].default is None, "absent default and explicit null metadata remain distinct"
    encoded = json.loads(path.read_text(encoding="utf-8"))
    assert encoded["model"]["fields"][0][1]["has_default"] is False and encoded["model"]["fields"][1][1]["has_default"] is True, "snapshot records default presence explicitly"
    assert reopened.fields["a"].enum == ["β", "α"] and reopened.fields["amount"].minimum == reopened.fields["amount"].maximum == 0, "enum order and zero bounds are descriptor metadata"
    before = path.read_bytes()
    invalid = ModelSpec("Bad", {"x": SchemaField(str, default={"not-json"})})
    failed = False
    try:
        store.save(invalid)
    except (TypeError, ValueError):
        failed = True
    assert failed and path.read_bytes() == before, "encoding failure leaves the previous snapshot unchanged"
    def deny_replace(source, destination):
        raise OSError("replace unavailable")
    with monkeypatch.context() as patch:
        patch.setattr(store_module.os, "replace", deny_replace)
        failed = False
        try:
            store.save(ModelSpec("Replacement", {"other": SchemaField(int)}))
        except OSError:
            failed = True
        assert failed and path.read_bytes() == before, "failed replacement keeps the old snapshot readable"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["descriptor.json"], "failed snapshot replacement cleans its temporary file"
    assert store.load() == model, "a store reads the current complete snapshot before replacement"
    store.save(ModelSpec("New", {"b": SchemaField(bool, default=False)}))
    assert DescriptorStore(path).load().name == "New", "a later successful snapshot replaces the complete descriptor"
    assert store.load().name == "New", "the same store reads the most recently replaced complete snapshot"
    exact_path = tmp_path / "exact.json"
    exact = ModelSpec("Exact", {"n": SchemaField(int, default=2 ** 80 + 1, minimum=-(2 ** 80 + 1), maximum=2 ** 80 + 1)})
    DescriptorStore(exact_path).save(exact)
    assert DescriptorStore(exact_path).load() == exact, "large integer metadata stays exact rather than passing through float"

@pytest.mark.skip("Part 3")
def test_recursive_model_compiler(monkeypatch):
    """Compose typed arrays and objects, keeping constraints at their own levels."""
    import fieldshape.flat as flat_module
    item = ModelSpec("Item", {
        "sku": SchemaField(str, enum=["A", "B"]),
        "quantity": SchemaField(int, minimum=1, maximum=3),
        "note": SchemaField(str, required=False, default=None),
    })
    order = ModelSpec("Order", {
        "customer": SchemaField(ModelSpec("Customer", {"name": SchemaField(str), "alias": SchemaField(str, required=False)})),
        "items": SchemaField(ArrayOf(item, min_items=1, max_items=2)),
        "backup": SchemaField(ArrayOf(item), required=False),
        "matrix": SchemaField(ArrayOf(ArrayOf(SchemaField(int, minimum=-2, maximum=0), min_items=0, max_items=2), min_items=1)),
        "legacy": SchemaField(list, required=False),
    })
    calls = []
    original = flat_module.python_type_to_schema
    def observe(field):
        calls.append(field.field_type)
        return original(field)
    with monkeypatch.context() as patch:
        patch.setattr(flat_module, "python_type_to_schema", observe)
        schema = compile_model(order)
    assert calls and list in calls and int in calls and str in calls, "recursive compilation reuses the existing leaf adapter on real leaves"
    assert schema["required"] == ["customer", "items", "matrix"], "only each object's own fields determine its required list"
    props = schema["properties"]
    assert props["customer"]["required"] == ["name"] and props["items"]["items"]["required"] == ["sku", "quantity"], "required lists belong to the nested object that declares them"
    assert props["items"]["minItems"] == 1 and props["items"]["maxItems"] == 2, "cardinality constraints stay on their typed array"
    assert props["items"]["items"]["properties"]["quantity"] == {"type": "integer", "minimum": 1, "maximum": 3}, "scalar bounds stay on the corresponding object leaf"
    assert props["matrix"] == {"type": "array", "minItems": 1, "items": {"type": "array", "minItems": 0, "maxItems": 2, "items": {"type": "integer", "minimum": -2, "maximum": 0}}}, "nested typed arrays retain independent item and container constraints"
    assert "default" not in props["items"]["items"]["properties"]["note"], "default annotations are not compiled as nullability or injected values"
    good = {"customer": {"name": "Ada"}, "items": [{"sku": "A", "quantity": 1}], "matrix": [[-2, 0], []]}
    service = ExtractionService()
    service.register_model(order)
    assert service.validate_model("Order", good) == [], "the service validates data through the recursively compiled schema"
    bad = copy.deepcopy(good)
    bad["items"][0]["quantity"] = 0
    bad["matrix"][0].append(1)
    assert [(issue.path, issue.code) for issue in service.validate_model("Order", bad)] == [(("items", 0, "quantity"), "minimum"), (("matrix", 0), "maxItems"), (("matrix", 0, 2), "maximum")], "typed nesting reaches the correct scalar and container validators"
    props["items"]["items"]["properties"]["sku"]["enum"].append("C")
    assert props["backup"]["items"]["properties"]["sku"]["enum"] == ["A", "B"] and item.fields["sku"].enum == ["A", "B"], "reused descriptors compile into independently owned branches"
    assert compile_model(order)["properties"]["items"]["items"]["properties"]["sku"]["enum"] == ["A", "B"], "separate recursive compilations do not share mutable schema output"
    invalid = [
        SchemaField(int, minimum=3, maximum=2),
        SchemaField(ArrayOf(int, min_items=2, max_items=1)),
        SchemaField(ArrayOf(int, min_items=-1)),
        SchemaField(ArrayOf(int, max_items=True)),
        SchemaField(ArrayOf(int), minimum=0),
        SchemaField(item, enum=["A"]),
        SchemaField(str, maximum=2),
    ]
    for field in invalid:
        failed = False
        try:
            compile_model(ModelSpec("Invalid", {"x": field}))
        except ValueError:
            failed = True
        assert failed, "reject the explicitly declared contradictory or misplaced constraints"
    empty = compile_model(ModelSpec("Empty", {}))
    assert empty == {"type": "object", "properties": {}, "required": []}, "empty objects remain object schemas"
    for invalid_root in (ArrayOf(int), str):
        rejected = False
        try:
            compile_model(invalid_root)
        except ValueError:
            rejected = True
        assert rejected, "the recursive compiler requires an object model at its root"
    # Required/default metadata on an array item does not describe key presence.
    wrapped = compile_model(ModelSpec("Wrapped", {"xs": SchemaField(ArrayOf(SchemaField(int, required=False, default=None, minimum=0)))}))
    assert wrapped["properties"]["xs"]["items"] == {"type": "integer", "minimum": 0}, "item wrappers carry scalar constraints without optional-element semantics"
    only_empty = compile_model(ModelSpec("OnlyEmpty", {"xs": SchemaField(ArrayOf(int, max_items=0))}))
    assert only_empty["properties"]["xs"] == {"type": "array", "items": {"type": "integer"}, "maxItems": 0}, "zero maximum cardinality remains an explicit empty-array constraint"
    labels = compile_model(ModelSpec("Labels", {
        "first": SchemaField(ModelSpec("Repeated", {"left": SchemaField(int)})),
        "second": SchemaField(ModelSpec("Repeated", {"right": SchemaField(str, required=False)})),
    }))
    assert labels["properties"]["first"] == {"type": "object", "properties": {"left": {"type": "integer"}}, "required": ["left"]} and labels["properties"]["second"] == {"type": "object", "properties": {"right": {"type": "string"}}, "required": []}, "same model labels do not merge distinct declaration trees"
    equal = None
    try:
        equal = compile_model(ModelSpec("Equal", {"n": SchemaField(int, minimum=0, maximum=0)}))
    except ValueError:
        pass
    assert equal is not None and equal["properties"]["n"] == {"type": "integer", "minimum": 0, "maximum": 0}, "equal inclusive numeric bounds remain a valid scalar interval"

@pytest.mark.skip("Part 4")
def test_completed_extraction_replay():
    """Classify completed extraction strings inside the supplied NDJSON envelope."""
    schema = {"type": "object", "properties": {"title": {"type": "string"}, "price": {"type": "number", "minimum": 0}}, "required": ["title", "price"]}
    raws = ['{"title":"行\\nnext","price":0}', '{broken', '{"title":4,"price":-1}', 'null', '{"title":"only"}', '{"title":"last","price":2}']
    state = {"pulled": 0, "closed": False}
    async def source():
        try:
            for raw in raws:
                state["pulled"] += 1
                yield raw
        finally:
            state["closed"] = True
    async def collect():
        stream = stream_extractions(source(), schema)
        first = await anext(stream)
        assert state["pulled"] == 1, "classify and emit one completion before pulling the next"
        lines = [first] + [line async for line in stream]
        assert state["closed"], "the supplied stream envelope closes its completion source"
        return lines
    lines = asyncio.run(collect())
    assert len(lines) == len(raws) and all(line.endswith("\n") and line.count("\n") == 1 for line in lines), "one completed extraction occupies one NDJSON record"
    events = [json.loads(line) for line in lines]
    assert [event["raw"] for event in events] == raws, "raw completions survive exact ordered replay"
    assert [event["status"] for event in events] == ["ok", "parse_error", "schema_error", "schema_error", "schema_error", "ok"], "distinguish malformed JSON from parsed schema failures and successes"
    assert events[0]["data"] == {"title": "行\nnext", "price": 0} and events[0]["issues"] == [], "valid zero and embedded text newlines survive parsing"
    assert events[1]["data"] is None and events[1]["issues"] == [], "parse failure carries no invented parsed value or validation issue"
    assert events[2]["data"] == {"title": 4, "price": -1}, "schema failure retains the actual parsed evidence without coercion"
    assert [(issue["path"], issue["code"]) for issue in events[2]["issues"]] == [(["title"], "type"), (["price"], "minimum")], "schema failures retain every typed validator issue in order"
    assert events[3]["issues"] == [{"path": [], "code": "type", "message": "expected object"}], "parsed null is validated as data rather than a parse failure"
    assert events[4]["issues"] == [{"path": ["price"], "code": "required", "message": "required field missing"}], "missing required keys remain schema failures"
    assert parse_extraction("0", {"type": "number"}) == {"status": "ok", "raw": "0", "data": 0, "issues": []}, "valid scalar zero survives completion classification"
    assert parse_extraction("false", {"type": "boolean"}) == {"status": "ok", "raw": "false", "data": False, "issues": []}, "valid scalar false survives completion classification"
    spaced = ' \r\n\t{"title":"spaced","price":1} \t'
    spaced_event = parse_extraction(spaced, schema)
    assert spaced_event["raw"] == spaced and spaced_event["status"] == "ok", "completion whitespace remains part of exact raw evidence"
    decimals = [parse_extraction("1.25", {"type": "number", "minimum": 0}), parse_extraction("-1.25", {"type": "number", "minimum": 0})]
    assert [event["data"] for event in decimals] == [1.25, -1.25] and [event["status"] for event in decimals] == ["ok", "schema_error"], "parsed decimal evidence remains uncoerced on success and schema failure"
    fenced = '```json\n{"title":"wrapped","price":1}\n```'
    assert parse_extraction(fenced, schema) == {"status": "parse_error", "raw": fenced, "data": None, "issues": []}, "fenced prose stays a parse failure rather than being repaired"
    async def empty():
        if False:
            yield "unused"
    async def collect_empty():
        return [line async for line in stream_extractions(empty(), schema)]
    assert asyncio.run(collect_empty()) == [], "empty completion replay has no synthetic event"

@pytest.mark.skip("Part 5")
def test_typed_issue_tree():
    """Group given typed paths, preserving root, parent and repeated leaf errors."""
    issues = [
        ValidationIssue((), "summary", "invalid extraction"),
        ValidationIssue(("a.b",), "type", "expected object"),
        ValidationIssue(("a.b", "x[0]"), "minimum", "too small"),
        ValidationIssue(("a.b", "x[0]"), "maximum", "too large"),
        ValidationIssue(("rows", 0, "0"), "enum", "bad key"),
        ValidationIssue(("rows", "0", 0), "type", "bad item"),
        ValidationIssue(("rows",), "minItems", "too few"),
    ]
    saved = copy.deepcopy(issues)
    tree = group_issues(issues)
    assert tree["issues"] == [{"code": "summary", "message": "invalid extraction"}], "root issues remain on the root alongside children"
    assert list(tree["children"]) == ["a.b", "rows"], "literal key punctuation is not parsed as path syntax"
    dotted = tree["children"]["a.b"]
    assert dotted["issues"] == [{"code": "type", "message": "expected object"}] and list(dotted["children"]) == ["x[0]"], "parent issues coexist with deeper issues"
    assert dotted["children"]["x[0]"]["issues"] == [{"code": "minimum", "message": "too small"}, {"code": "maximum", "message": "too large"}], "all issues at the same typed path retain input order"
    rows = tree["children"]["rows"]
    assert list(rows["children"]) == [0, "0"], "integer array indices and string object keys remain distinct"
    assert rows["children"][0]["children"]["0"]["issues"][0]["code"] == "enum" and rows["children"]["0"]["children"][0]["issues"][0]["code"] == "type", "alternating typed segments retain the exact route"
    assert rows["issues"] == [{"code": "minItems", "message": "too few"}], "later parent issues do not replace existing children"
    assert issues == saved, "grouping leaves the given validator evidence untouched"
    tree["children"]["a.b"]["issues"].append({"code": "local", "message": "changed"})
    assert len(rows["issues"]) == 1 and len(group_issues(issues)["children"]["a.b"]["issues"]) == 1, "child lists and separate reports have independent ownership"
    assert group_issues([]) == {"issues": [], "children": {}}, "no issues still produce an empty root report"
    schema = {"type": "object", "properties": {"list.key": {"type": "array", "minItems": 2, "items": {"type": "integer"}}}, "required": ["missing"]}
    produced = validate_schema({"list.key": ["bad"]}, schema)
    report = group_issues(produced)
    assert report["children"]["missing"]["issues"][0]["code"] == "required" and report["children"]["list.key"]["issues"][0]["code"] == "minItems", "the report accepts real supplied validator paths without reparsing them"
    assert report["children"]["list.key"]["children"][0]["issues"] == [{"code": "type", "message": "expected finite integer"}], "validator array indices reach the correct error-tree child"
    repeated = ValidationIssue(("same",), "type", "same evidence")
    assert group_issues([repeated, repeated])["children"]["same"]["issues"] == [{"code": "type", "message": "same evidence"}, {"code": "type", "message": "same evidence"}], "identical repeated issues remain separate ordered evidence"
    blank = group_issues([ValidationIssue(("", 0, ""), "type", "")])
    assert blank == {"issues": [], "children": {"": {"issues": [], "children": {0: {"issues": [], "children": {"": {"issues": [{"code": "type", "message": ""}], "children": {}}}}}}}}, "empty literal keys and empty messages remain ordinary typed evidence"
