SPEC = dict(
 title="A typed extraction boundary", zh_title="结构化提取的错误分层", level="基础",
 brief="实现一个小型提取边界，分别处理拒答、JSON 解析失败和字段校验失败。合同只覆盖明确列出的字段，不要求实现完整 JSON Schema。",
 scenario="An extraction endpoint must distinguish refusal, parse failure, and schema failure before downstream processing.",
 contract="""extract(raw, refusal=None): a non-None refusal takes precedence and returns {'kind':'refusal','reason':refusal}. Otherwise parse the JSON string raw. Invalid JSON returns {'kind':'parse_error'}. Valid data must be a dict with exactly title and score: title is a string trimmed to length 1..80; score has exact type int and is 0..5. Violations return {'kind':'schema_error'}. Success returns {'kind':'ok','value':{'title':trimmed_title,'score':score}}. Never coerce bool, float, string, or null to integer. This is a fixed extraction contract, not a general JSON Schema engine.""",
 bonus="extract_many(rows) applies extract(raw, refusal) to each row dict, returning {'items':results,'ok_count':number of ok results}. Preserve order; one bad row's raw JSON must not abort other rows. Row envelopes are valid.",
 stubs=["extract", "extract_many"],
 code=r'''import json
def extract(raw, refusal=None):
    if refusal is not None: return {"kind": "refusal", "reason": refusal}
    try: value = json.loads(raw)
    except (ValueError, TypeError): return {"kind": "parse_error"}
    if not isinstance(value, dict) or set(value) != {"title", "score"}: return {"kind": "schema_error"}
    title, score = value["title"], value["score"]
    if not isinstance(title, str) or not 1 <= len(title.strip()) <= 80 or type(score) is not int or not 0 <= score <= 5:
        return {"kind": "schema_error"}
    return {"kind": "ok", "value": {"title": title.strip(), "score": score}}
def extract_many(rows):
    items = [extract(r["raw"], r.get("refusal")) for r in rows]
    return {"items": items, "ok_count": sum(x["kind"] == "ok" for x in items)}
''',
 tests=r'''class CoreTests(unittest.TestCase):
    def test_success(self): self.assertEqual(m.extract('{"title":" A ","score":0}'), {"kind":"ok","value":{"title":"A","score":0}})
    def test_refusal_precedence(self): self.assertEqual(m.extract('{', "policy"), {"kind":"refusal","reason":"policy"})
    def test_parse(self): self.assertEqual(m.extract('{'), {"kind":"parse_error"})
    def test_shape(self):
        for raw in ('[]', 'null', '{"title":"a"}', '{"title":"a","score":1,"extra":1}'):
            with self.subTest(raw=raw): self.assertEqual(m.extract(raw), {"kind":"schema_error"})
    def test_strict_score(self):
        import json
        for v in (True, 2.0, "2", None, -1, 6):
            with self.subTest(v=v): self.assertEqual(m.extract(json.dumps({"title":"a","score":v})), {"kind":"schema_error"})
    def test_title_bounds(self):
        import json
        for v in (" ", "x"*81, 7):
            with self.subTest(v=v): self.assertEqual(m.extract(json.dumps({"title":v,"score":1})), {"kind":"schema_error"})
        self.assertEqual(m.extract(json.dumps({"title":"x"*80,"score":5}))["kind"], "ok")
class BonusTests(unittest.TestCase):
    def test_batch_isolation(self):
        r=m.extract_many([{"raw":"{"},{"raw":'{"title":"a","score":1}'}])
        self.assertEqual(r["ok_count"],1)
        self.assertEqual([x["kind"] for x in r["items"]],["parse_error","ok"])
    def test_empty(self): self.assertEqual(m.extract_many([]),{"items":[],"ok_count":0})
''',
 followups=["解析失败和 schema 失败为什么要分开记录？", "怎样加入一次有上限的修复尝试？"],
 explanation="先判断拒答，再解析，再校验。返回值使用可区分的 kind；下游无需从异常文字猜测错误类型。"
)
