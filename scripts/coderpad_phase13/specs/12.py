SPEC = dict(
 title="Constrain paths and consume confirmation", zh_title="路径边界与一次确认", level="中等",
 brief="实现 workspace 路径包含检查，并区分 accept、decline、cancel。用临时目录验证 symlink 逃逸；不执行真实删除。",
 scenario="A destructive workflow asks the user to confirm a candidate set. Enforce filesystem containment and one-time confirmation without deleting files.",
 contract="""within(root,candidate) resolves both pathlib paths, following existing symlinks; relative candidates are interpreted relative to root. Return True if resolved candidate equals root or is a descendant, otherwise False. Root exists; resolution errors return False. Do not use string prefix checks.
confirm(action,token,used): allowed actions are accept, decline, cancel; invalid action raises ValueError without consuming token. If token already appears in provided set used, raise ValueError. Otherwise consume it for ALL three outcomes. Return {'status':'confirmed'|'declined'|'canceled','execute':True only for accept}. This function models consumption only; token authentication has already happened upstream. No file deletion.""",
 bonus="validate_form(data) returns {'title':trimmed} for an exact one-key dict title containing a string of trimmed length 1..40; otherwise raises ValueError.",
 stubs=["within", "confirm", "validate_form"],
 code=r'''from pathlib import Path
def within(root,candidate):
    try:
        r=Path(root).resolve();p=Path(candidate);p=(r/p).resolve() if not p.is_absolute() else p.resolve()
        return p==r or r in p.parents
    except (OSError,RuntimeError):return False
def confirm(action,token,used):
    if action not in ("accept","decline","cancel") or token in used:raise ValueError("confirmation")
    used.add(token)
    return {"status":{"accept":"confirmed","decline":"declined","cancel":"canceled"}[action],"execute":action=="accept"}
def validate_form(data):
    if not isinstance(data,dict) or set(data)!={"title"} or not isinstance(data["title"],str) or not 1<=len(data["title"].strip())<=40:raise ValueError("form")
    return {"title":data["title"].strip()}
''',
 tests=r'''class CoreTests(unittest.TestCase):
    def test_paths(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/"work";root.mkdir()
            self.assertTrue(m.within(root,"a/b"));self.assertTrue(m.within(root,root))
            self.assertFalse(m.within(root,"../outside"));self.assertFalse(m.within(root,Path(d)/"workspace"))
    def test_symlink_escape(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/"work";root.mkdir();outside=Path(d)/"out";outside.mkdir();(root/"link").symlink_to(outside,target_is_directory=True)
            self.assertFalse(m.within(root,"link/secret"))
    def test_accept_once(self):
        used=set();self.assertEqual(m.confirm("accept","t",used),{"status":"confirmed","execute":True})
        with self.assertRaises(ValueError):m.confirm("accept","t",used)
    def test_decline_and_cancel(self):
        for action,status in (("decline","declined"),("cancel","canceled")):
            used=set()
            with self.subTest(action=action):self.assertEqual(m.confirm(action,"t",used),{"status":status,"execute":False});self.assertIn("t",used)
    def test_invalid_not_consumed(self):
        used=set()
        with self.assertRaises(ValueError):m.confirm("maybe","t",used)
        self.assertEqual(used,set())
class BonusTests(unittest.TestCase):
    def test_form(self):self.assertEqual(m.validate_form({"title":" A "}),{"title":"A"})
    def test_bad_form(self):
        for d in ({"title":" "},{"title":"a","extra":1},{"title":False}):
            with self.subTest(d=d),self.assertRaises(ValueError):m.validate_form(d)
''',
 followups=["路径校验通过后到打开文件之间还有什么竞争条件？", "为什么 decline 和 cancel 都不能执行，但仍应区分？"],
 explanation="resolve 后比较父目录关系，避免同前缀和 symlink 逃逸。确认结果只建模状态，不把 UI 的 accept 当成授权或真实 sandbox。"
)
