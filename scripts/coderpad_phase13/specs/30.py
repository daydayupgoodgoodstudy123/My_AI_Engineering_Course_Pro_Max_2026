SPEC = dict(
 title="Pin admission and preserve rollback history", zh_title="准入 Pin 与回滚历史", level="中等到进阶",
 brief="区分注册表记录与独立核验的 evidence。检测运行时漂移后停止路由，只允许回滚到曾经准入的版本，保留历史。",
 scenario="A registry entry is discovery evidence, not approval. Implement a small admission controller driven by independently supplied evidence.",
 contract="""Registry(namespace) starts admitted={}, active=None, history=[]. admit(version,record,evidence) requires: record.name starts namespace+'.' with a nonempty suffix; record.status=='active'; record.source_digest==evidence.source_digest; record.tools_digest==evidence.live_digest; both digests are 64 lowercase hex characters; evidence.namespace==namespace. Any missing/invalid check raises ValueError with no mutation. Reject every duplicate version, even with identical data. On success deep-copy record into admitted[version], set active=version, append ('admit',version), return version. version and namespace are provided nonempty strings.
observe(live_digest,status) returns False if no active version. If status is not 'active' or digest mismatches the active pin, append ('quarantine',active), set active=None, return False. Otherwise return True without history mutation.""",
 bonus="rollback(version) requires a previously admitted version or raises KeyError. Set active=version and append ('rollback',version). Preserve all admitted versions and previous history. No network routing is actually changed.",
 stubs=["Registry.admit", "Registry.observe", "Registry.rollback"],
 code=r'''import re
from copy import deepcopy
class Registry:
    def __init__(self,namespace):self.namespace=namespace;self.admitted={};self.active=None;self.history=[]
    def admit(self,version,record,evidence):
        valid=isinstance(record.get("name"),str) and record["name"].startswith(self.namespace+".") and len(record["name"])>len(self.namespace)+1 and record.get("status")=="active" and evidence.get("namespace")==self.namespace
        for field,source in (("source_digest","source_digest"),("tools_digest","live_digest")):
            d=record.get(field);valid=valid and isinstance(d,str) and re.fullmatch("[0-9a-f]{64}",d) is not None and d==evidence.get(source)
        if not valid or version in self.admitted:raise ValueError("admission")
        self.admitted[version]=deepcopy(record);self.active=version;self.history.append(("admit",version));return version
    def observe(self,live_digest,status):
        if self.active is None:return False
        if status!="active" or live_digest!=self.admitted[self.active]["tools_digest"]:
            self.history.append(("quarantine",self.active));self.active=None;return False
        return True
    def rollback(self,version):
        if version not in self.admitted:raise KeyError(version)
        self.active=version;self.history.append(("rollback",version))
''',
 tests=r'''RECORD={"name":"org.example.notes","status":"active","source_digest":"a"*64,"tools_digest":"b"*64}
EVIDENCE={"namespace":"org.example","source_digest":"a"*64,"live_digest":"b"*64}
class CoreTests(unittest.TestCase):
    def test_admit(self):
        r=m.Registry("org.example");self.assertEqual(r.admit("1",RECORD,EVIDENCE),"1");self.assertEqual(r.active,"1")
    def test_independent_namespace(self):
        r=m.Registry("org.example")
        with self.assertRaises(ValueError):r.admit("1",RECORD,dict(EVIDENCE,namespace="other"))
        self.assertEqual(r.history,[]);self.assertIsNone(r.active)
    def test_invalid_evidence(self):
        for patch in ({"status":"deleted"},{"name":"org.exampleevil.notes"},{"tools_digest":"x"*64},{"source_digest":"c"*64}):
            with self.subTest(patch=patch),self.assertRaises(ValueError):m.Registry("org.example").admit("1",dict(RECORD,**patch),EVIDENCE)
    def test_duplicate(self):
        r=m.Registry("org.example");r.admit("1",RECORD,EVIDENCE)
        with self.assertRaises(ValueError):r.admit("1",RECORD,EVIDENCE)
        self.assertEqual(len(r.history),1)
    def test_drift_quarantines(self):
        r=m.Registry("org.example");r.admit("1",RECORD,EVIDENCE);self.assertFalse(r.observe("c"*64,"active"));self.assertIsNone(r.active);self.assertEqual(r.history[-1],("quarantine","1"))
    def test_healthy_no_history(self):
        r=m.Registry("org.example");r.admit("1",RECORD,EVIDENCE);self.assertTrue(r.observe("b"*64,"active"));self.assertEqual(len(r.history),1)
class BonusTests(unittest.TestCase):
    def test_rollback_preserves_history(self):
        r=m.Registry("org.example");r.admit("1",RECORD,EVIDENCE);r.admit("2",RECORD,EVIDENCE);r.observe("bad","active");r.rollback("1")
        self.assertEqual(r.active,"1");self.assertEqual(len(r.admitted),2);self.assertEqual(r.history[-2:],[("quarantine","2"),("rollback","1")])
    def test_unknown_rollback(self):
        with self.assertRaises(KeyError):m.Registry("org.example").rollback("missing")
''',
 followups=["注册表中的 name 为什么不能证明 namespace 的所有权？", "回滚为什么应追加历史而不是改写准入记录？"],
 explanation="核验证据由调用者独立提供；记录不自证。漂移时隔离当前路由，回滚只引用已经准入的版本。历史是本地列表，不声称防篡改审计账本。"
)
