SPEC = dict(
 title="Compute evaluation metrics and gate a package", zh_title="评估指标与发布门槛", level="中等",
 brief="手写 precision/recall，再让结构、行为、安全与可移植性分别进入 gate。避免只看平均分掩盖失败证据。",
 scenario="A skill package has excellent trigger recall but failed a safety check. Implement metrics and a release decision that preserves independent evidence layers.",
 contract="""metrics(expected,predicted) requires equal-length lists containing exact bool values; otherwise ValueError. Return {'tp','fp','fn','precision','recall'}, using 0.0 when a ratio's denominator is zero. Empty lists are valid.
gate(report,min_precision=.8,min_recall=.8): required fields structure,behavior,safety,portability must each be exactly True. Missing or other values fail. report.metrics must be a dict with numeric precision and recall in [0,1] (bool is invalid); missing/invalid metric contributes reason 'metrics'. Otherwise append 'precision' and/or 'recall' when below thresholds. Return {'ready':not reasons,'reasons':sorted reason strings}. Equality with threshold passes. Thresholds are provided valid. ready applies only to this supplied local evidence; no live-host evidence is inferred.""",
 bonus="improvement(baseline,with_skill) returns with_skill-baseline; both values must be numeric, non-bool and in [0,1], otherwise ValueError. A negative result is valid evidence, not clamped to zero.",
 stubs=["metrics", "gate", "improvement"],
 code=r'''def metrics(expected,predicted):
    if len(expected)!=len(predicted) or any(type(v) is not bool for v in expected+predicted):raise ValueError("labels")
    tp=sum(a and b for a,b in zip(expected,predicted));fp=sum(not a and b for a,b in zip(expected,predicted));fn=sum(a and not b for a,b in zip(expected,predicted))
    return {"tp":tp,"fp":fp,"fn":fn,"precision":tp/(tp+fp) if tp+fp else 0.0,"recall":tp/(tp+fn) if tp+fn else 0.0}
def gate(report,min_precision=.8,min_recall=.8):
    reasons=[k for k in ("structure","behavior","safety","portability") if report.get(k) is not True];m=report.get("metrics")
    if not isinstance(m,dict) or any(type(m.get(k)) not in (int,float) or not 0<=m[k]<=1 for k in ("precision","recall")):reasons.append("metrics")
    else:
        if m["precision"]<min_precision:reasons.append("precision")
        if m["recall"]<min_recall:reasons.append("recall")
    return {"ready":not reasons,"reasons":sorted(reasons)}
def improvement(baseline,with_skill):
    if any(type(x) not in (int,float) or not 0<=x<=1 for x in (baseline,with_skill)):raise ValueError("rate")
    return with_skill-baseline
''',
 tests=r'''GOOD={"structure":True,"behavior":True,"safety":True,"portability":True,"metrics":{"precision":.8,"recall":.9}}
class CoreTests(unittest.TestCase):
    def test_metrics(self):self.assertEqual(m.metrics([True,False,True,False],[True,True,False,False]),{"tp":1,"fp":1,"fn":1,"precision":.5,"recall":.5})
    def test_zero(self):self.assertEqual(m.metrics([],[]),{"tp":0,"fp":0,"fn":0,"precision":0.0,"recall":0.0})
    def test_invalid(self):
        for a,b in (([True],[]),([1],[True])):
            with self.subTest(a=a),self.assertRaises(ValueError):m.metrics(a,b)
    def test_gate_boundary(self):self.assertEqual(m.gate(GOOD),{"ready":True,"reasons":[]})
    def test_safety_veto(self):self.assertEqual(m.gate(dict(GOOD,safety=False)),{"ready":False,"reasons":["safety"]})
    def test_bad_metrics(self):self.assertEqual(m.gate(dict(GOOD,metrics={"precision":True,"recall":.9}))["reasons"],["metrics"])
    def test_all_reasons(self):self.assertEqual(m.gate(dict(GOOD,structure=False,metrics={"precision":.7,"recall":.6}))["reasons"],["precision","recall","structure"])
class BonusTests(unittest.TestCase):
    def test_negative_improvement(self):self.assertAlmostEqual(m.improvement(.9,.8),-.1)
    def test_invalid(self):
        with self.assertRaises(ValueError):m.improvement(True,.8)
''',
 followups=["为什么 precision 高仍可能 recall 很低？", "本地 gate 通过后，跨 host 运行还要收集什么证据？"],
 explanation="明确零分母约定；safety 不是能被其他平均分抵消的分数。保留独立层的 reason，便于定位失败。"
)
