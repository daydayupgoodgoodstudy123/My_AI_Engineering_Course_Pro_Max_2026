SPEC = dict(
 title="Route with bounded fallback", zh_title="有限回退的模型路由", level="中等",
 brief="用 fake providers 实现顺序回退，区分可重试故障与请求错误，并记录成功提供商的 token 成本。",
 scenario="A model router should fail over on transient outages while refusing to retry invalid requests.",
 contract="""route(providers,prompt,prices): providers is an ordered list of (name,callable); call(prompt) returns {'text':str,'input_tokens':int,'output_tokens':int}. TransientError means append name to attempted and continue; any other Exception propagates immediately. Return {'provider':name,'text':text,'attempted':[names through success],'cost':input_tokens*prices[name][0]+output_tokens*prices[name][1]}. Prices are per token and valid; only successful-call usage is available in this exercise, so failed attempts have no cost estimate. No provider runs more than once. If all fail (including empty list) raise ExhaustedError(attempted); its provided attempted attribute records names. No sleeping, network, or random retries.""",
 bonus="eligible(providers,requirements) returns names sorted by (price,name), retaining only providers whose capability set includes requirements. Each provider is {'name','capabilities':set,'price':number}.",
 stubs=["route", "eligible"],
 code=r'''class TransientError(Exception):pass
class ExhaustedError(Exception):
    def __init__(self,attempted):super().__init__("providers exhausted");self.attempted=attempted
def route(providers,prompt,prices):
    attempted=[]
    for name,call in providers:
        attempted.append(name)
        try:r=call(prompt)
        except TransientError:continue
        return {"provider":name,"text":r["text"],"attempted":attempted,"cost":r["input_tokens"]*prices[name][0]+r["output_tokens"]*prices[name][1]}
    raise ExhaustedError(attempted)
def eligible(providers,requirements):return [p["name"] for p in sorted(providers,key=lambda p:(p["price"],p["name"])) if requirements<=p["capabilities"]]
''',
 tests=r'''def ok(prompt):return {"text":prompt.upper(),"input_tokens":2,"output_tokens":3}
def transient(prompt):raise m.TransientError("offline")
class CoreTests(unittest.TestCase):
    def test_success_cost(self):self.assertEqual(m.route([("a",ok)],"hi",{"a":(2,3)}),{"provider":"a","text":"HI","attempted":["a"],"cost":13})
    def test_fallback(self):self.assertEqual(m.route([("a",transient),("b",ok)],"x",{"b":(1,1)})["attempted"],["a","b"])
    def test_stop_after_success(self):
        def fail(p):self.fail("should not run")
        self.assertEqual(m.route([("a",ok),("b",fail)],"x",{"a":(0,0)})["provider"],"a")
    def test_permanent_error(self):
        seen=[]
        def bad(p):raise ValueError("invalid request")
        with self.assertRaises(ValueError):m.route([("a",bad),("b",lambda p:seen.append(p))],"x",{})
        self.assertEqual(seen,[])
    def test_exhausted(self):
        with self.assertRaises(m.ExhaustedError) as ctx:m.route([("a",transient)],"x",{})
        self.assertEqual(ctx.exception.attempted,["a"])
    def test_empty(self):
        with self.assertRaises(m.ExhaustedError) as ctx:m.route([],"x",{})
        self.assertEqual(ctx.exception.attempted,[])
class BonusTests(unittest.TestCase):
    def test_capabilities(self):self.assertEqual(m.eligible([{"name":"z","price":1,"capabilities":{"tools"}},{"name":"a","price":1,"capabilities":{"tools"}},{"name":"b","price":0,"capabilities":set()}],{"tools"}),["a","z"])
    def test_empty(self):self.assertEqual(m.eligible([],{"tools"}),[])
''',
 followups=["实际 API 超时后为什么可能已经产生费用？", "回退提供商可能改变哪些产品行为？"],
 explanation="只捕获明确的 transient 类别。attempted 记录路由轨迹；本题成本只覆盖可观察的成功 usage，不能当作完整账单。"
)
