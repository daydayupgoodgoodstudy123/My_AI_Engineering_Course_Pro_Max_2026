SPEC = dict(
 title="Authorize an embedded app bridge", zh_title="内嵌 App 消息边界", level="中等",
 brief="实现 UI bridge 的来源与权限检查，并安全生成简单 HTML。所有 UI 消息都是 fixture，不要求浏览器集成。",
 scenario="An embedded timeline app can ask its host to read or export notes. Finish the bridge policy before any action runs.",
 contract="""bridge(origin,message,allowed_origin,permissions): reject a different origin first with {'ok':False,'error':'origin'}. message must then be a dict with exact keys id,method,params, where id is a nonempty string and params is dict; malformed returns error 'message'. Allowed methods notes/read and notes/export require permissions 'read' and 'export' respectively. Unknown method returns error 'method'; missing permission returns error 'permission'. On success return {'ok':True,'id':id,'method':method,'params':deep_copy_of_params}. Do not execute any operation.
timeline(titles) returns '<ul>'+one '<li>'+HTML-escaped title+'</li>' per title+'</ul>'; escape &, <, >, quotes and apostrophes with html.escape's defaults. Preserve title order.""",
 bonus="resource(uri,enabled) returns {'uri':uri,'mimeType':'text/html'} only if enabled is True and uri is a string beginning ui:// with a nonempty suffix; otherwise raise ValueError.",
 stubs=["bridge", "timeline", "resource"],
 code=r'''import html
from copy import deepcopy
def bridge(origin,message,allowed_origin,permissions):
    def error(code):return {"ok":False,"error":code}
    if origin!=allowed_origin:return error("origin")
    if not isinstance(message,dict) or set(message)!={"id","method","params"} or not isinstance(message["id"],str) or not message["id"] or not isinstance(message["params"],dict):return error("message")
    method=message["method"]
    required={"notes/read":"read","notes/export":"export"}
    if not isinstance(method,str) or method not in required:return error("method")
    if required[method] not in permissions:return error("permission")
    return {"ok":True,"id":message["id"],"method":method,"params":deepcopy(message["params"])}
def timeline(titles):return "<ul>"+"".join("<li>"+html.escape(t)+"</li>" for t in titles)+"</ul>"
def resource(uri,enabled):
    if enabled is not True or not isinstance(uri,str) or not uri.startswith("ui://") or len(uri)==5:raise ValueError("resource")
    return {"uri":uri,"mimeType":"text/html"}
''',
 tests=r'''MSG={"id":"1","method":"notes/read","params":{"id":1}}
class CoreTests(unittest.TestCase):
    def test_read(self):self.assertEqual(m.bridge("good",MSG,"good",{"read"}),dict(MSG,ok=True))
    def test_origin_first(self):self.assertEqual(m.bridge("bad",None,"good",set())["error"],"origin")
    def test_message(self):self.assertEqual(m.bridge("good",{},"good",{"read"})["error"],"message")
    def test_permission(self):self.assertEqual(m.bridge("good",dict(MSG,method="notes/export"),"good",{"read"})["error"],"permission")
    def test_unknown(self):self.assertEqual(m.bridge("good",dict(MSG,method="shell"),"good",{"read"})["error"],"method")
    def test_escape(self):self.assertEqual(m.timeline(['<script>','a&b']),'<ul><li>&lt;script&gt;</li><li>a&amp;b</li></ul>')
    def test_copy(self):
        msg={"id":"x","method":"notes/read","params":{"a":[]}};r=m.bridge("g",msg,"g",{"read"});r["params"]["a"].append(1)
        self.assertEqual(msg["params"],{"a":[]})
class BonusTests(unittest.TestCase):
    def test_resource(self):self.assertEqual(m.resource("ui://timeline",True),{"uri":"ui://timeline","mimeType":"text/html"})
    def test_disabled(self):
        for uri,enabled in (("ui://a",False),("https://a",True),("ui://",True)):
            with self.subTest(uri=uri),self.assertRaises(ValueError):m.resource(uri,enabled)
''',
 followups=["允许 origin 是否就代表允许所有方法？", "HTML escaping、CSP 和 iframe sandbox 分别解决什么问题？"],
 explanation="先验证来源，再验证消息合同和动作权限。HTML 输出必须做文本转义；这不是完整浏览器隔离或 MCP Apps 实现。"
)
