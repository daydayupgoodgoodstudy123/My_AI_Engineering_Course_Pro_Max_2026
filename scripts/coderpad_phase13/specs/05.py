SPEC = dict(
 title="Lint a tool catalog", zh_title="工具合同静态检查", level="基础",
 brief="为已有工具目录实现 linter，输出稳定的错误码。练习命名、描述、必填参数与重复项检查，不调用模型。",
 scenario="Tool authors keep publishing ambiguous descriptors. Build a small deterministic linter for the catalog admission step.",
 contract="""lint(tool) returns sorted unique error codes. 'name' if name is not a string matching [a-z][a-z0-9_]{0,39}; 'description' unless description is a string of 1..1024 characters containing both exact substrings 'Use when' and 'Do not use'; 'schema' unless input_schema is a dict with type='object', properties a dict, required a list of unique strings all present in properties, and additionalProperties is False. Missing fields fail their respective checks. Do not validate nested schemas. Never mutate tool.
lint_registry(tools) returns {'findings':[{'index':i,'codes':lint(tool)} for invalid tools], 'duplicates':sorted duplicate string names}. A duplicated name appears once in duplicates even if repeated three times. Invalid non-string names are not duplicate candidates.""",
 bonus="clean_names(tools) returns sorted unique names of individually valid tools; exclude every name appearing more than once in the input, including duplicates of otherwise invalid entries.",
 stubs=["lint", "lint_registry", "clean_names"],
 code=r'''import re
from collections import Counter
def lint(tool):
    codes=[]
    name=tool.get("name")
    if not isinstance(name,str) or re.fullmatch(r"[a-z][a-z0-9_]{0,39}",name) is None: codes.append("name")
    desc=tool.get("description")
    if not isinstance(desc,str) or not 1<=len(desc)<=1024 or "Use when" not in desc or "Do not use" not in desc: codes.append("description")
    s=tool.get("input_schema")
    valid=isinstance(s,dict) and s.get("type")=="object" and isinstance(s.get("properties"),dict) and isinstance(s.get("required"),list) and all(isinstance(x,str) for x in s["required"])
    if valid: valid=len(set(s["required"]))==len(s["required"]) and set(s["required"])<=set(s["properties"]) and s.get("additionalProperties") is False
    if not valid: codes.append("schema")
    return sorted(codes)
def lint_registry(tools):
    counts=Counter(t.get("name") for t in tools if isinstance(t.get("name"),str))
    return {"findings":[{"index":i,"codes":codes} for i,t in enumerate(tools) if (codes:=lint(t))], "duplicates":sorted(n for n,c in counts.items() if c>1)}
def clean_names(tools):
    duplicates=set(lint_registry(tools)["duplicates"])
    return sorted({t["name"] for t in tools if not lint(t) and t["name"] not in duplicates})
''',
 tests=r'''def tool(name="get_note"):
    return {"name":name,"description":"Use when reading. Do not use for edits.","input_schema":{"type":"object","properties":{"id":{"type":"integer"}},"required":["id"],"additionalProperties":False}}
class CoreTests(unittest.TestCase):
    def test_valid(self): self.assertEqual(m.lint(tool()),[])
    def test_missing(self): self.assertEqual(m.lint({}),["description","name","schema"])
    def test_names(self):
        for name in ("Bad", "a-b", "1a", "x"*41, None):
            with self.subTest(name=name): self.assertIn("name",m.lint(tool(name)))
    def test_schema(self):
        for patch in ({"required":["missing"]},{"required":["id","id"]},{"additionalProperties":True},{"properties":[]},{"required":[{}]}):
            t=tool();t["input_schema"].update(patch)
            with self.subTest(patch=patch): self.assertIn("schema",m.lint(t))
    def test_description(self):
        t=tool();t["description"]="Use when needed"
        self.assertEqual(m.lint(t),["description"])
    def test_registry(self):
        self.assertEqual(m.lint_registry([tool("z"),{},tool("z"),tool("a"),tool("a")]),{"findings":[{"index":1,"codes":["description","name","schema"]}],"duplicates":["a","z"]})
class BonusTests(unittest.TestCase):
    def test_clean(self): self.assertEqual(m.clean_names([tool("b"),tool("a"),tool("b"),{}]),["a"])
    def test_empty(self): self.assertEqual(m.clean_names([]),[])
''',
 followups=["静态 linter 通过是否证明工具描述能正确路由？", "为什么重复工具名不能直接后者覆盖前者？"],
 explanation="独立收集各类 finding，避免首个错误遮住其他错误。用稳定排序使 CI 输出可复现。linter 只验证本题规定的浅层合同。"
)
