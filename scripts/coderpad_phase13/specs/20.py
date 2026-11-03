SPEC = dict(
 title="Summarize a redacted trace", zh_title="脱敏 Trace 与耗时统计", level="基础到中等",
 brief="遍历嵌套属性做脱敏，再计算按操作聚合的耗时。使用可控时间戳，区分总耗时与子 span 时间叠加。",
 scenario="Observability must retain latency evidence without recording prompt text or secrets by default.",
 contract="""redact(value,capture_content=False) recursively copies dicts/lists. Dict keys are strings. If key.casefold() is authorization, token, api_key, or password, replace its WHOLE value with '[REDACTED]' regardless of opt-in. If capture_content is False, do the same for prompt, completion, content. Other values remain unchanged; input must not mutate.
summarize(spans) receives dicts with name,start,end (numeric milliseconds). If any end<start raise ValueError. Return a dict mapping each name to {'count':n,'total_ms':sum(end-start),'max_ms':maximum duration}. Empty spans returns {}. This is per-span aggregation, not wall-clock trace duration or real OTel export.""",
 bonus="critical_span(spans) returns the name of the longest individual span; ties choose lexicographically smallest name. Empty spans returns None; span times are valid.",
 stubs=["redact", "summarize", "critical_span"],
 code=r'''def redact(value,capture_content=False):
    if isinstance(value,dict):
        forbidden={"authorization","token","api_key","password"}|(set() if capture_content else {"prompt","completion","content"})
        return {k:"[REDACTED]" if k.casefold() in forbidden else redact(v,capture_content) for k,v in value.items()}
    if isinstance(value,list):return [redact(v,capture_content) for v in value]
    return value
def summarize(spans):
    result={}
    for s in spans:
        duration=s["end"]-s["start"]
        if duration<0:raise ValueError("time")
        r=result.setdefault(s["name"],{"count":0,"total_ms":0,"max_ms":0});r["count"]+=1;r["total_ms"]+=duration;r["max_ms"]=max(r["max_ms"],duration)
    return result
def critical_span(spans):return min(spans,key=lambda s:(-(s["end"]-s["start"]),s["name"]))["name"] if spans else None
''',
 tests=r'''class CoreTests(unittest.TestCase):
    def test_nested_redaction(self):self.assertEqual(m.redact({"x":[{"Authorization":"secret","prompt":"hi"}],"ok":1}),{"x":[{"Authorization":"[REDACTED]","prompt":"[REDACTED]"}],"ok":1})
    def test_opt_in_still_redacts_secret(self):self.assertEqual(m.redact({"prompt":"hi","token":"secret"},True),{"prompt":"hi","token":"[REDACTED]"})
    def test_copy(self):
        x={"a":[1]};m.redact(x)["a"].append(2);self.assertEqual(x,{"a":[1]})
    def test_aggregate(self):self.assertEqual(m.summarize([{"name":"tool","start":0,"end":5},{"name":"tool","start":2,"end":9}]),{"tool":{"count":2,"total_ms":12,"max_ms":7}})
    def test_invalid_time(self):
        with self.assertRaises(ValueError):m.summarize([{"name":"x","start":2,"end":1}])
    def test_empty(self):self.assertEqual(m.summarize([]),{})
class BonusTests(unittest.TestCase):
    def test_tie(self):self.assertEqual(m.critical_span([{"name":"z","start":0,"end":2},{"name":"a","start":1,"end":3}]),"a")
    def test_empty(self):self.assertIsNone(m.critical_span([]))
''',
 followups=["父子 span 的 duration 为什么不能相加当成请求耗时？", "按 key 脱敏有哪些已知盲区？"],
 explanation="内容 opt-in 不解除 secret 脱敏。统计验证时间区间；重叠 span 的总和只表示累计操作时间。"
)
