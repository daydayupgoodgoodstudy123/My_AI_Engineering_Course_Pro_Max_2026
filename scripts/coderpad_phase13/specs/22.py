SPEC = dict(
 title="Validate a portable skill bundle", zh_title="校验 Skill 包的基础合同", level="基础到中等",
 brief="从固定的 frontmatter 子集解析 name 和 description，校验包名与正文。题目不安装或执行任何 Skill。",
 scenario="A catalog should reject malformed skill metadata before activation. Implement a deliberately small portable-frontmatter subset.",
 contract="""parse(text) requires first line '---', then exactly two unique single-line key:value entries named name and description in either order, then a closing '---' line, then nonempty body after trimming. Strip leading/trailing whitespace around keys/values. No YAML quoting, multiline values, comments, or additional keys are supported in this exercise. name must match [a-z][a-z0-9]*(?:-[a-z0-9]+)* and be <=64 characters; description trimmed length 1..1024. Return {'name','description','body'} with stripped values and body; any violation raises ValueError.
validate_bundle(directory_name,text) calls parse and additionally requires name==directory_name; return parsed metadata or raise ValueError. Runtime permissions and invocation flags do not belong to this exercise's portable subset.""",
 bonus="classify(need) maps 'reusable workflow' -> 'skill', 'external action' -> 'tool', 'always-on repository rules' -> 'instructions', 'event callback' -> 'hook'; unknown needs return 'ordinary code'. Exact strings, no fuzzy routing.",
 stubs=["parse", "validate_bundle", "classify"],
 code=r'''import re
def parse(text):
    lines=text.splitlines()
    if not lines or lines[0]!="---":raise ValueError("frontmatter")
    try:end=lines.index("---",1)
    except ValueError:raise ValueError("closing delimiter")
    fields={}
    for line in lines[1:end]:
        if ":" not in line:raise ValueError("field")
        key,value=(x.strip() for x in line.split(":",1))
        if key in fields:raise ValueError("duplicate")
        fields[key]=value
    if set(fields)!={"name","description"}:raise ValueError("fields")
    name=fields["name"]
    if len(name)>64 or re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*",name) is None or not 1<=len(fields["description"])<=1024:raise ValueError("metadata")
    body="\n".join(lines[end+1:]).strip()
    if not body:raise ValueError("body")
    return dict(fields,body=body)
def validate_bundle(directory_name,text):
    data=parse(text)
    if data["name"]!=directory_name:raise ValueError("directory")
    return data
def classify(need):return {"reusable workflow":"skill","external action":"tool","always-on repository rules":"instructions","event callback":"hook"}.get(need,"ordinary code")
''',
 tests=r'''TEXT="---\nname: review-notes\ndescription: Review a note: carefully\n---\n\nRead the note.\n"
class CoreTests(unittest.TestCase):
    def test_parse(self):self.assertEqual(m.parse(TEXT),{"name":"review-notes","description":"Review a note: carefully","body":"Read the note."})
    def test_bundle(self):self.assertEqual(m.validate_bundle("review-notes",TEXT)["name"],"review-notes")
    def test_directory_mismatch(self):
        with self.assertRaises(ValueError):m.validate_bundle("other",TEXT)
    def test_delimiters(self):
        for t in ("name: a",TEXT.replace("---", "",1),"---\nname: a"):
            with self.subTest(t=t),self.assertRaises(ValueError):m.parse(t)
    def test_invalid_metadata(self):
        for t in (TEXT.replace("review-notes","Bad_Name"),TEXT.replace("description:","extra:"),TEXT.replace("---\n\nRead", "name: x\n---\n\nRead"),TEXT.replace("Read the note.","")):
            with self.subTest(t=t),self.assertRaises(ValueError):m.parse(t)
    def test_trim(self):self.assertEqual(m.parse(TEXT.replace("name: review-notes","name:   review-notes  "))["name"],"review-notes")
class BonusTests(unittest.TestCase):
    def test_classification(self):self.assertEqual(m.classify("external action"),"tool");self.assertEqual(m.classify("reusable workflow"),"skill")
    def test_default(self):self.assertEqual(m.classify("sum a list"),"ordinary code")
''',
 followups=["为什么加载 SKILL.md 不等于获得工具执行权限？", "完整 YAML parser 与本题受限 parser 的适用边界是什么？"],
 explanation="显式声明受限语法，避免用几行字符串处理冒充完整 YAML 支持。包验证与运行时权限分离。"
)
