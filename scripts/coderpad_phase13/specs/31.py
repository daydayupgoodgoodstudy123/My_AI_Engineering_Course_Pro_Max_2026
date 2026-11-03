SPEC = dict(
 title="Gate a release on complete evidence", zh_title="完整证据驱动的发布检查", level="中等到进阶",
 brief="比较原始结果与 SDK 归一化视图，保留允许的未知字段，同时拒绝未知 resultType；用证据门槛检查本地 release readiness。",
 scenario="An SDK normalizer hides malformed responses. Validate raw result discriminators, compare preserved fields, and gate a local release report.",
 contract="""compare(raw,sdk,capabilities) accepts resultType 'complete' always; 'input_required' only with capability 'input'; 'task' only with capability 'tasks'. Missing/unknown/unauthorized resultType raises ValueError. raw and sdk are dicts. sdk must contain and equal every raw field except raw keys starting 'x-' (optional extensions may be dropped). Equality uses canonical JSON, so True must not equal 1. Extra sdk fields are allowed. Return True on success. Unknown additive raw fields not starting x- must be preserved.
release(report): report.transcripts must be a nonempty list of exact True values; report.redacted and report.rollback_tested must each be exactly True; report.health must be a dict with requests exact int >0, errors exact int 0<=errors<=requests, p95_ms numeric non-bool >=0. Valid health passes only if errors/requests<=.01 and p95_ms<=500. Return {'ready':bool,'reasons':sorted list among transcripts,redacted,rollback,health}. Missing fields fail. This checks supplied local evidence only, not a live production release.""",
 bonus="failure_rate(report) returns health.errors/health.requests for exact int counts with requests>0 and 0<=errors<=requests, otherwise ValueError.",
 stubs=["compare", "release", "failure_rate"],
 code=r'''import json
def compare(raw,sdk,capabilities):
    allowed={"complete"}|({"input_required"} if "input" in capabilities else set())|({"task"} if "tasks" in capabilities else set())
    if not isinstance(raw.get("resultType"),str) or raw["resultType"] not in allowed:raise ValueError("resultType")
    for key,value in raw.items():
        if not key.startswith("x-") and (key not in sdk or json.dumps(value,sort_keys=True)!=json.dumps(sdk[key],sort_keys=True)):raise ValueError("normalization loss")
    return True
def release(report):
    reasons=[];t=report.get("transcripts")
    if not isinstance(t,list) or not t or any(v is not True for v in t):reasons.append("transcripts")
    if report.get("redacted") is not True:reasons.append("redacted")
    if report.get("rollback_tested") is not True:reasons.append("rollback")
    h=report.get("health")
    valid=isinstance(h,dict) and type(h.get("requests")) is int and h["requests"]>0 and type(h.get("errors")) is int and 0<=h["errors"]<=h["requests"] and type(h.get("p95_ms")) in (int,float) and h["p95_ms"]>=0
    if not valid or h["errors"]/h["requests"]>.01 or h["p95_ms"]>500:reasons.append("health")
    return {"ready":not reasons,"reasons":sorted(reasons)}
def failure_rate(report):
    h=report.get("health")
    if not isinstance(h,dict) or type(h.get("requests")) is not int or h["requests"]<=0 or type(h.get("errors")) is not int or not 0<=h["errors"]<=h["requests"]:raise ValueError("counts")
    return h["errors"]/h["requests"]
''',
 tests=r'''GOOD={"transcripts":[True,True],"redacted":True,"rollback_tested":True,"health":{"requests":100,"errors":1,"p95_ms":500}}
class CoreTests(unittest.TestCase):
    def test_extension_allowed(self):self.assertTrue(m.compare({"resultType":"complete","x-extra":1},{"resultType":"complete"},set()))
    def test_additive_field_preserved(self):
        with self.assertRaises(ValueError):m.compare({"resultType":"complete","newField":1},{"resultType":"complete"},set())
    def test_result_type_capability(self):
        with self.assertRaises(ValueError):m.compare({"resultType":"task"},{"resultType":"task"},set())
        self.assertTrue(m.compare({"resultType":"task"},{"resultType":"task"},{"tasks"}))
        with self.assertRaises(ValueError):m.compare({"resultType":"unknown"},{},set())
        with self.assertRaises(ValueError):m.compare({"resultType":[]},{},set())
    def test_bool_not_int(self):
        with self.assertRaises(ValueError):m.compare({"resultType":"complete","v":True},{"resultType":"complete","v":1},set())
    def test_release_boundary(self):self.assertEqual(m.release(GOOD),{"ready":True,"reasons":[]})
    def test_missing_evidence(self):self.assertEqual(m.release({})["reasons"],["health","redacted","rollback","transcripts"])
    def test_unhealthy(self):self.assertEqual(m.release(dict(GOOD,health={"requests":100,"errors":2,"p95_ms":1}))["reasons"],["health"])
class BonusTests(unittest.TestCase):
    def test_rate(self):self.assertEqual(m.failure_rate(GOOD),.01)
    def test_zero_requests(self):
        with self.assertRaises(ValueError):m.failure_rate({"health":{"requests":0,"errors":0}})
''',
 followups=["为什么只检查 SDK 对象可能漏掉协议错误？", "rollback_tested 这个布尔值在真实发布流程中应由什么证据支撑？"],
 explanation="先验证 raw discriminator，再比较 SDK 是否保留合同字段。门槛判断不把缺失样本当成健康，也不把本地 ready 当成已部署。"
)
