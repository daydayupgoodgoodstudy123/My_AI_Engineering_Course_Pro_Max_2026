SPEC = dict(
 title="Budget progressive disclosure", zh_title="渐进加载与目录预算", level="中等",
 brief="先根据 scope 优先级解决同名冲突，再发布预算内目录；按需读取 reference 并检查目录逃逸。",
 scenario="A skill catalog should publish compact metadata and load only the selected resource within its package boundary.",
 contract="""catalog(candidates,precedence,budget) receives {'name','description','scope'} dicts and a scope list from highest to lowest priority. Exclude unknown scopes. For each name select the candidate from the highest-priority scope; duplicate names within that winning scope raise ValueError. Sort winners by name, then greedily include each whose cost len(name)+len(description) fits remaining budget; skip an oversized entry and continue. Return copied dicts with only name and description, no body or scope. budget is a nonnegative integer. Resolve ALL collisions before budget filtering.
reference(root,relative,max_chars) returns UTF-8 text truncated to max_chars. Reject absolute paths or resolved paths outside root, including symlink escape, with ValueError. Missing files raise FileNotFoundError. root exists; max_chars is a valid nonnegative integer. This is a local loader, not an OS sandbox.""",
 bonus="activation(entry,body) returns {'name':entry['name'],'instructions':body}, without mutating entry or adding instructions to catalog entries.",
 stubs=["catalog", "reference", "activation"],
 code=r'''from pathlib import Path
def catalog(candidates,precedence,budget):
    ranks={s:i for i,s in enumerate(precedence)};groups={}
    for c in candidates:
        if c["scope"] in ranks:groups.setdefault(c["name"],[]).append(c)
    winners=[]
    for name,items in sorted(groups.items()):
        rank=min(ranks[c["scope"]] for c in items);best=[c for c in items if ranks[c["scope"]]==rank]
        if len(best)!=1:raise ValueError("collision")
        winners.append(best[0])
    result=[]
    for c in winners:
        cost=len(c["name"])+len(c["description"])
        if cost<=budget:result.append({"name":c["name"],"description":c["description"]});budget-=cost
    return result
def reference(root,relative,max_chars):
    root=Path(root).resolve();p=Path(relative)
    if p.is_absolute():raise ValueError("absolute")
    p=(root/p).resolve()
    if p!=root and root not in p.parents:raise ValueError("escape")
    return p.read_text(encoding="utf-8")[:max_chars]
def activation(entry,body):return {"name":entry["name"],"instructions":body}
''',
 tests=r'''class CoreTests(unittest.TestCase):
    def test_precedence(self):self.assertEqual(m.catalog([{"name":"a","description":"low","scope":"user"},{"name":"a","description":"high","scope":"project"}],["project","user"],100),[{"name":"a","description":"high"}])
    def test_budget_skip(self):self.assertEqual(m.catalog([{"name":"a","description":"too long","scope":"s"},{"name":"b","description":"x","scope":"s"}],["s"],2),[{"name":"b","description":"x"}])
    def test_collision_even_outside_budget(self):
        c={"name":"a","description":"x","scope":"s"}
        with self.assertRaises(ValueError):m.catalog([c,c],["s"],0)
    def test_unknown_scope(self):self.assertEqual(m.catalog([{"name":"a","description":"x","scope":"s"}],[],100),[])
    def test_reference(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            (Path(d)/"ref.txt").write_text("abcdef");self.assertEqual(m.reference(d,"ref.txt",3),"abc")
            with self.assertRaises(ValueError):m.reference(d,"../escape",10)
            with self.assertRaises(ValueError):m.reference(d,str(Path(d)/"ref.txt"),10)
    def test_symlink(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/"skill";root.mkdir();(Path(d)/"secret").write_text("s");(root/"ref").symlink_to(Path(d)/"secret")
            with self.assertRaises(ValueError):m.reference(root,"ref",10)
class BonusTests(unittest.TestCase):
    def test_activation(self):self.assertEqual(m.activation({"name":"a","description":"d"},"body"),{"name":"a","instructions":"body"})
    def test_no_mutation(self):
        e={"name":"a"};m.activation(e,"x");self.assertEqual(e,{"name":"a"})
''',
 followups=["catalog 预算与激活后上下文预算为什么要分开？", "用 token 预算替代字符预算后，接口应怎样改变？"],
 explanation="冲突解决先于预算，防止预算掩盖不确定行为。这里只把字符长度作为明确的成本单位，不当成真实 tokenizer 计数。"
)
