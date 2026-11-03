SPEC = dict(
 title="Validate tool result content", zh_title="工具结果与内容合同", level="中等",
 brief="校验工具返回的 structured 值和 content blocks。不要假定结构化输出一定是 object，也不要把工具业务错误当成成功 schema 结果。",
 scenario="A client rejected valid array outputs and accepted malformed image blocks. Repair its fixed result-contract validator.",
 contract="""validate(result,expected_type) returns True or raises ValueError. result must be a dict with content a list. Each block must be a dict: text blocks require type='text', text a string; image blocks require type='image', mimeType='image/png' or 'image/jpeg', and data a nonempty valid standard base64 string. Other block types fail. Extra block fields are allowed. If isError is present it must be exact bool. When isError is True, structured validation is skipped. Otherwise structured is required and must match expected_type: object=dict, array=list, string=str, integer=exact int, number=exact int/float excluding bool, boolean=exact bool, null=None. Unknown expected_type always raises ValueError. This is a fixed top-level type check, not complete JSON Schema validation.""",
 bonus="pages(fetch) starts with cursor=None, calls fetch(cursor) -> {'items':list,'next':str|None}, concatenates items in page order, and stops on None. Cursors are opaque. A repeated next cursor raises ValueError before fetching it again. Empty-string cursor is valid. First fetch always happens.",
 stubs=["validate", "pages"],
 code=r'''import base64,binascii
def validate(result,expected_type):
    types={"object":lambda v:isinstance(v,dict),"array":lambda v:isinstance(v,list),"string":lambda v:isinstance(v,str),"integer":lambda v:type(v) is int,"number":lambda v:type(v) in (int,float),"boolean":lambda v:type(v) is bool,"null":lambda v:v is None}
    if not isinstance(expected_type,str) or expected_type not in types or not isinstance(result,dict) or not isinstance(result.get("content"),list) or "isError" in result and type(result["isError"]) is not bool:raise ValueError("result")
    for b in result["content"]:
        if not isinstance(b,dict):raise ValueError("block")
        if b.get("type")=="text" and isinstance(b.get("text"),str):continue
        if b.get("type")=="image" and b.get("mimeType") in ("image/png","image/jpeg") and isinstance(b.get("data"),str) and b["data"]:
            try:base64.b64decode(b["data"],validate=True)
            except (ValueError,binascii.Error):raise ValueError("image")
            continue
        raise ValueError("block")
    if result.get("isError") is not True and ("structured" not in result or not types[expected_type](result["structured"])):raise ValueError("structured")
    return True
def pages(fetch):
    result=[];cursor=None;seen=set()
    while True:
        page=fetch(cursor);result.extend(page["items"]);cursor=page["next"]
        if cursor is None:return result
        if cursor in seen:raise ValueError("cursor cycle")
        seen.add(cursor)
''',
 tests=r'''class CoreTests(unittest.TestCase):
    def test_array_scalar_null(self):
        for value,kind in (([],"array"),(0,"integer"),(None,"null"),(False,"boolean"),("x","string")):
            with self.subTest(kind=kind):self.assertTrue(m.validate({"content":[],"structured":value},kind))
    def test_bool_not_integer(self):
        with self.assertRaises(ValueError):m.validate({"content":[],"structured":True},"integer")
    def test_image(self):self.assertTrue(m.validate({"content":[{"type":"image","mimeType":"image/png","data":"aGk="}],"structured":{}},"object"))
    def test_bad_blocks(self):
        for block in ({"type":"text","text":1},{"type":"image","mimeType":"image/png","data":"@@"},{"type":"audio"}):
            with self.subTest(block=block),self.assertRaises(ValueError):m.validate({"content":[block],"structured":{}},"object")
    def test_tool_error(self):self.assertTrue(m.validate({"content":[{"type":"text","text":"not found"}],"isError":True},"object"))
    def test_missing_structured(self):
        with self.assertRaises(ValueError):m.validate({"content":[]},"object")
class BonusTests(unittest.TestCase):
    def test_opaque_cursor(self):
        seen=[];table={None:{"items":[1],"next":""},"":{"items":[2],"next":None}}
        self.assertEqual(m.pages(lambda c:seen.append(c) or table[c]),[1,2]);self.assertEqual(seen,[None,""])
    def test_cycle(self):
        with self.assertRaises(ValueError):m.pages(lambda c:{"items":[],"next":"x"})
''',
 followups=["structured 输出为什么可以是标量或数组？", "base64 合法能否证明实际图片内容合法？"],
 explanation="按声明类型校验，不默认 object。content 也必须独立校验；本题 base64 检查不声称能验证真实图像格式。"
)
