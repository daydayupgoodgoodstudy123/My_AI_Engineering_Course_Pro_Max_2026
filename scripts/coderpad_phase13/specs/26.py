SPEC = dict(
 title="Review actions before execution", zh_title="执行前权限策略", level="中等",
 brief="实现只返回决策的 policy engine。区分 capability、路径范围、网络 origin 和副作用批准，绝不执行传入命令。",
 scenario="Activating a skill must not grant authority. Review a structured action against an independent policy before execution.",
 contract="""review(action,policy): action has capability, relative path, origin (None or exact string), side_effect(bool), approved(bool). policy has capabilities(set), root(path), origins(set). Check in order: missing capability -> {'verdict':'deny','rule':'capability'}; absolute path OR resolved path outside root (including symlink escape) -> deny/path; non-None origin not exactly in policy origins -> deny/origin; side_effect True and approved False -> {'verdict':'ask','rule':'approval'}; otherwise {'verdict':'allow','rule':'policy'}. Candidate path is relative to root; root exists. Do not execute, read, or create the candidate file. Input values are provided well typed. This is a policy simulation, not process isolation.""",
 bonus="command_allowed(argv,allowlist) returns True only if tuple(argv) exactly equals an allowlist tuple. Never accept prefix matches, shell strings, or extra flags. argv must be a list/tuple of strings, otherwise False.",
 stubs=["review", "command_allowed"],
 code=r'''from pathlib import Path
def review(action,policy):
    def decision(verdict,rule):return {"verdict":verdict,"rule":rule}
    if action["capability"] not in policy["capabilities"]:return decision("deny","capability")
    root=Path(policy["root"]).resolve();p=Path(action["path"])
    if p.is_absolute():return decision("deny","path")
    p=(root/p).resolve()
    if p!=root and root not in p.parents:return decision("deny","path")
    if action["origin"] is not None and action["origin"] not in policy["origins"]:return decision("deny","origin")
    if action["side_effect"] and not action["approved"]:return decision("ask","approval")
    return decision("allow","policy")
def command_allowed(argv,allowlist):return isinstance(argv,(list,tuple)) and all(isinstance(x,str) for x in argv) and tuple(argv) in allowlist
''',
 tests=r'''class CoreTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.p={"capabilities":{"write"},"root":self.tmp.name,"origins":{"https://api.example"}}
        self.a={"capability":"write","path":"out.txt","origin":None,"side_effect":False,"approved":False}
    def test_allow(self):self.assertEqual(m.review(self.a,self.p),{"verdict":"allow","rule":"policy"})
    def test_capability_before_approval(self):self.assertEqual(m.review(dict(self.a,capability="shell",approved=True),self.p),{"verdict":"deny","rule":"capability"})
    def test_path(self):self.assertEqual(m.review(dict(self.a,path="../secret"),self.p)["rule"],"path")
    def test_exact_origin(self):self.assertEqual(m.review(dict(self.a,origin="https://api.example.evil"),self.p)["rule"],"origin")
    def test_approval(self):
        self.assertEqual(m.review(dict(self.a,side_effect=True),self.p),{"verdict":"ask","rule":"approval"})
        self.assertEqual(m.review(dict(self.a,side_effect=True,approved=True),self.p)["verdict"],"allow")
    def test_no_file_created(self):
        from pathlib import Path
        m.review(self.a,self.p);self.assertFalse((Path(self.tmp.name)/"out.txt").exists())
class BonusTests(unittest.TestCase):
    def test_exact(self):self.assertTrue(m.command_allowed(["python3","check.py"],{("python3","check.py")}))
    def test_no_extra(self):
        self.assertFalse(m.command_allowed(["python3","check.py","--upload"],{("python3","check.py")}));self.assertFalse(m.command_allowed("python3 check.py",{("python3","check.py")}))
''',
 followups=["为什么有 approval 仍可能被 capability policy 拒绝？", "policy allow 与真实 sandbox containment 有何区别？"],
 explanation="授权条件是独立层，不让批准绕过 capability 或路径范围。argv 使用精确比较，代码从不执行候选动作。"
)
