SPEC = dict(
 title="Check transport routing headers", zh_title="传输层路由一致性", level="中等",
 brief="验证 HTTP 路由头与请求体是否一致，保留重复 header 以发现歧义。这里只做纯函数边界检查，不启动 HTTP 服务。",
 scenario="A proxy can accidentally route a request using headers that disagree with its body. Implement the pre-forwarding check.",
 contract="""validate(headers, body, allowed_origins) returns 'ok', 'forbidden_origin', 'duplicate_header', or 'routing_mismatch', in that priority order. headers is a list of (name,value) strings; compare names case-insensitively. If Origin is present, every Origin value must exactly match an allowed origin; absent Origin is accepted. Duplicate Origin or any duplicate mcp-version, mcp-method, mcp-name returns duplicate_header. Require exactly one mcp-version equal to body['params']['_meta']['protocolVersion'] and mcp-method equal to body['method']. For tools/call require mcp-name equal to body['params']['name']; for other methods mcp-name must be absent. Body envelopes are valid. No URL normalization, session header, or real HTTP server is required.""",
 bonus="parse_sse(text) reads blank-line-delimited SSE events, ignores comment lines starting ':', joins multiple 'data:' lines with newline, JSON-decodes data, and returns payloads in order. Ignore events without data. Invalid JSON raises ValueError. Input uses LF newlines and ends on an event boundary.",
 stubs=["validate", "parse_sse"],
 code=r'''import json
def validate(headers,body,allowed_origins):
    groups={}
    for k,v in headers:groups.setdefault(k.lower(),[]).append(v)
    if any(v not in allowed_origins for v in groups.get("origin",[])):return "forbidden_origin"
    if any(len(groups.get(k,[]))>1 for k in ("origin","mcp-version","mcp-method","mcp-name")):return "duplicate_header"
    expected={"mcp-version":body["params"]["_meta"]["protocolVersion"],"mcp-method":body["method"]}
    if body["method"]=="tools/call":expected["mcp-name"]=body["params"]["name"]
    if any(groups.get(k)!=[v] for k,v in expected.items()) or "mcp-name" in groups and "mcp-name" not in expected:return "routing_mismatch"
    return "ok"
def parse_sse(text):
    result=[]
    for event in text.split("\n\n"):
        lines=[line[5:].removeprefix(" ") for line in event.splitlines() if line.startswith("data:")]
        if lines:result.append(json.loads("\n".join(lines)))
    return result
''',
 tests=r'''BODY={"method":"tools/call","params":{"name":"read","_meta":{"protocolVersion":"v1"}}}
HEADERS=[("MCP-Version","v1"),("mcp-method","tools/call"),("Mcp-Name","read")]
class CoreTests(unittest.TestCase):
    def test_valid(self):self.assertEqual(m.validate(HEADERS,BODY,[]),"ok")
    def test_origin(self):self.assertEqual(m.validate(HEADERS+[("origin","https://bad")],BODY,["https://good"]),"forbidden_origin")
    def test_duplicate_case_insensitive(self):self.assertEqual(m.validate(HEADERS+[("MCP-METHOD","tools/call")],BODY,[]),"duplicate_header")
    def test_mismatch(self):
        for headers in (HEADERS[:-1],HEADERS[:-1]+[("mcp-name","delete")],HEADERS[1:]):
            with self.subTest(headers=headers):self.assertEqual(m.validate(headers,BODY,[]),"routing_mismatch")
    def test_noncall_forbids_name(self):
        b={"method":"tools/list","params":{"_meta":{"protocolVersion":"v1"}}}
        self.assertEqual(m.validate([("mcp-version","v1"),("mcp-method","tools/list")],b,[]),"ok")
        self.assertEqual(m.validate([("mcp-version","v1"),("mcp-method","tools/list"),("mcp-name","read")],b,[]),"routing_mismatch")
    def test_duplicate_origins(self):self.assertEqual(m.validate(HEADERS+[("Origin","x"),("origin","x")],BODY,["x"]),"duplicate_header")
class BonusTests(unittest.TestCase):
    def test_sse(self):self.assertEqual(m.parse_sse(': ping\n\ndata: {"x":\ndata: 1}\n\ndata: [2]\n\n'),[{"x":1},[2]])
    def test_invalid_json(self):
        with self.assertRaises(ValueError):m.parse_sse('data: {\n\n')
''',
 followups=["为什么把 headers 先变成 dict 会丢掉安全相关信息？", "真实代理还有哪些 framing 和连接层问题不在本题范围？"],
 explanation="保留原始 header 列表才能检测重复项；验证完再用于路由。Origin 与路由一致性分别判断，错误优先级属于可测试合同。"
)
