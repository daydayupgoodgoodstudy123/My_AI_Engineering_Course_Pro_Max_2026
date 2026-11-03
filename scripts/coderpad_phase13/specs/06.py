SPEC = dict(
 title="Validate an independent RPC request", zh_title="独立 RPC 请求校验", level="基础到中等",
 brief="补齐无会话的 JSON-RPC 请求边界。每次都检查版本元数据，区分非法请求、版本不支持和方法不存在。",
 scenario="Implement a tiny stateless RPC dispatcher. The exercise pins a local course fixture revision; it does not implement the entire MCP specification.",
 contract="""VERSION is provided. dispatch(message) accepts only dicts with jsonrpc='2.0', id of exact type int or nonempty str, method a nonempty str, params a dict, and params._meta a dict containing protocolVersion (str) and clientCapabilities (dict). Extra fields are allowed. Invalid envelope returns {'jsonrpc':'2.0','id':None,'error':{'code':-32600}}. Valid envelope with unsupported version returns error -32022, echoing id. Unknown method returns -32601. server/discover returns result {'resultType':'complete','name':'interview-server'}. tools/list returns result {'resultType':'complete','tools':[]}. Error checks run in this order: envelope, version, method. No initialization or remembered connection state.""",
 bonus="request(request_id, method, params=None) returns a valid request with VERSION and empty clientCapabilities. Deep-copy params and overwrite its _meta with this exercise's metadata. Do not mutate caller input.",
 stubs=["dispatch", "request"],
 code=r'''from copy import deepcopy
VERSION="2026-07-28"
def dispatch(message):
    valid=isinstance(message,dict) and message.get("jsonrpc")=="2.0" and (type(message.get("id")) is int or isinstance(message.get("id"),str) and bool(message["id"])) and isinstance(message.get("method"),str) and bool(message["method"]) and isinstance(message.get("params"),dict)
    meta=message["params"].get("_meta") if valid else None
    valid=valid and isinstance(meta,dict) and isinstance(meta.get("protocolVersion"),str) and isinstance(meta.get("clientCapabilities"),dict)
    rid=message["id"] if valid else None
    def error(code): return {"jsonrpc":"2.0","id":rid,"error":{"code":code}}
    if not valid: return error(-32600)
    if meta["protocolVersion"]!=VERSION: return error(-32022)
    method=message["method"]
    if method=="server/discover": result={"resultType":"complete","name":"interview-server"}
    elif method=="tools/list": result={"resultType":"complete","tools":[]}
    else: return error(-32601)
    return {"jsonrpc":"2.0","id":rid,"result":result}
def request(request_id, method, params=None):
    p=deepcopy(params) if params is not None else {}
    p["_meta"]={"protocolVersion":VERSION,"clientCapabilities":{}}
    return {"jsonrpc":"2.0","id":request_id,"method":method,"params":p}
''',
 tests=r'''def req(method="server/discover",rid=1):
    return {"jsonrpc":"2.0","id":rid,"method":method,"params":{"_meta":{"protocolVersion":m.VERSION,"clientCapabilities":{}}}}
class CoreTests(unittest.TestCase):
    def test_discover(self): self.assertEqual(m.dispatch(req())["result"],{"resultType":"complete","name":"interview-server"})
    def test_list_without_handshake(self): self.assertEqual(m.dispatch(req("tools/list","a")),{"jsonrpc":"2.0","id":"a","result":{"resultType":"complete","tools":[]}})
    def test_missing_metadata(self):
        r=req();r["params"]={}
        self.assertEqual(m.dispatch(r),{"jsonrpc":"2.0","id":None,"error":{"code":-32600}})
    def test_invalid_envelopes(self):
        for value in (None,[],{},dict(req(),id=True),dict(req(),params=[])):
            with self.subTest(value=value):self.assertEqual(m.dispatch(value)["error"]["code"],-32600)
    def test_version_before_method(self):
        r=req("missing",0);r["params"]["_meta"]["protocolVersion"]="old"
        self.assertEqual(m.dispatch(r),{"jsonrpc":"2.0","id":0,"error":{"code":-32022}})
    def test_unknown(self): self.assertEqual(m.dispatch(req("initialize"))["error"]["code"],-32601)
class BonusTests(unittest.TestCase):
    def test_builder(self): self.assertEqual(m.request(0,"tools/list"),req("tools/list",0))
    def test_copy(self):
        p={"nested":[]};r=m.request(1,"tools/list",p);r["params"]["nested"].append(1)
        self.assertEqual(p,{"nested":[]})
''',
 followups=["无会话请求与没有应用状态有什么区别？", "为什么每次请求都要重新检查元数据？"],
 explanation="请求校验是纯函数，顺序固定。错误时回显 id 的规则也属于合同；不依赖前一条请求是否成功。版本值取自本地课程快照。"
)
