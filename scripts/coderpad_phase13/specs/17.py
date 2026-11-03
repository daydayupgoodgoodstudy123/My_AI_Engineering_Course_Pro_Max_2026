SPEC = dict(
 title="A policy-enforcing tool gateway", zh_title="带策略的工具网关", level="中等",
 brief="在转发前检查 namespaced 路由、角色和 descriptor pin。用 fake 上游的调用记录证明被拒绝的请求没有被执行。",
 scenario="A gateway must enforce policy before forwarding a tool call to an upstream peer.",
 contract="""Gateway(routes,fetch,forward): routes maps public names to {'peer':str,'local':str,'roles':set,'pin':str}; fetch(peer,local) returns a current digest string; forward(peer,local,args) executes. call(public,roles,args) checks in order: unknown public raises KeyError; no intersection between caller roles and route roles raises PermissionError; current digest different from pin raises ValueError. Only after these checks, call forward exactly once and return its value. Exceptions from fetch or forward propagate. Rejected calls must never forward; authorization rejection must not even fetch. No cache is used.""",
 bonus="visible(roles) returns sorted public names whose role set intersects caller roles. It does not fetch or forward anything.",
 stubs=["Gateway.call", "Gateway.visible"],
 code=r'''class Gateway:
    def __init__(self,routes,fetch,forward):self.routes=routes;self.fetch=fetch;self.forward=forward
    def call(self,public,roles,args):
        route=self.routes[public]
        if not roles & route["roles"]:raise PermissionError(public)
        if self.fetch(route["peer"],route["local"])!=route["pin"]:raise ValueError("drift")
        return self.forward(route["peer"],route["local"],args)
    def visible(self,roles):return sorted(n for n,r in self.routes.items() if roles & r["roles"])
''',
 tests=r'''ROUTES={"a::read":{"peer":"a","local":"read","roles":{"reader","admin"},"pin":"v1"}}
class CoreTests(unittest.TestCase):
    def setUp(self):
        self.fetched=[];self.calls=[]
        self.g=m.Gateway(ROUTES,lambda p,n:self.fetched.append((p,n)) or "v1",lambda p,n,a:self.calls.append((p,n,a)) or "done")
    def test_forward(self):self.assertEqual(self.g.call("a::read",{"reader"},{"x":1}),"done");self.assertEqual(self.calls,[("a","read",{"x":1})])
    def test_unknown(self):
        with self.assertRaises(KeyError):self.g.call("read",{"admin"},{})
        self.assertEqual(self.calls,[])
    def test_denied_before_fetch(self):
        with self.assertRaises(PermissionError):self.g.call("a::read",{"guest"},{})
        self.assertEqual(self.fetched,[]);self.assertEqual(self.calls,[])
    def test_drift(self):
        self.g.fetch=lambda p,n:"v2"
        with self.assertRaises(ValueError):self.g.call("a::read",{"admin"},{})
        self.assertEqual(self.calls,[])
    def test_fetch_failure(self):
        def fail(p,n):raise RuntimeError("offline")
        self.g.fetch=fail
        with self.assertRaisesRegex(RuntimeError,"offline"):self.g.call("a::read",{"admin"},{})
        self.assertEqual(self.calls,[])
    def test_empty_roles(self):
        with self.assertRaises(PermissionError):self.g.call("a::read",set(),{})
class BonusTests(unittest.TestCase):
    def test_visible(self):self.assertEqual(m.Gateway(ROUTES,None,None).visible({"reader"}),["a::read"])
    def test_hidden(self):self.assertEqual(m.Gateway(ROUTES,None,None).visible({"guest"}),[])
''',
 followups=["可见工具列表过滤能否替代调用时授权？", "fetch 与 forward 之间发生 descriptor 变化，真实系统如何处理？"],
 explanation="路由、授权、pin 验证在转发前完成。测试不仅检查错误类型，也检查上游没有被触发。"
)
