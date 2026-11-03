SPEC = dict(
 title="Orchestrate a bounded tool job", zh_title="有上限的工具生态编排", level="进阶",
 brief="把发现、授权、调用、轮询和 trace 组合成一条流程。fake client 已隔离所有外部系统，核心目标是流程顺序和失败后的停止行为。",
 scenario="Finish a coordinator over a supplied fake tool client. Keep authorization, discovery, execution, and task polling observable.",
 contract="""run(client,tool,args,allowed,max_polls=3): validate max_polls has exact type int and is >=0, else ValueError. If tool not in allowed, raise PermissionError BEFORE calling client. Then call client.discover() once (returns list of tool names), and raise KeyError if tool absent. Call client.call(tool,args) once. Responses are either {'status':'completed','value':any}, {'status':'failed'}, or {'status':'working','task_id':str}. For working, call client.poll(task_id) at most max_polls times, stopping at completed/failed. Working poll results retain the same task_id. Return {'status':'completed'|'failed'|'timeout','value':value only for completed else None,'trace':['discover','call', followed by one 'poll' per poll]}. Underlying exceptions propagate. No automatic mutation retry or real MCP/A2A/OAuth integration.""",
 bonus="evidence(report) returns {'completed':report.status=='completed','polls':count of 'poll' in trace,'live_integration':False}; do not infer a real deployment from this simulation.",
 stubs=["run", "evidence"],
 code=r'''def run(client,tool,args,allowed,max_polls=3):
    if type(max_polls) is not int or max_polls<0:raise ValueError("budget")
    if tool not in allowed:raise PermissionError(tool)
    trace=["discover"]
    if tool not in client.discover():raise KeyError(tool)
    result=client.call(tool,args);trace.append("call")
    for _ in range(max_polls):
        if result["status"]!="working":break
        result=client.poll(result["task_id"]);trace.append("poll")
    status=result["status"] if result["status"]!="working" else "timeout"
    return {"status":status,"value":result.get("value") if status=="completed" else None,"trace":trace}
def evidence(report):return {"completed":report["status"]=="completed","polls":report["trace"].count("poll"),"live_integration":False}
''',
 tests=r'''class Client:
    def __init__(self,results):self.results=iter(results);self.seen=[]
    def discover(self):self.seen.append("discover");return ["job"]
    def call(self,t,a):self.seen.append("call");return next(self.results)
    def poll(self,t):self.seen.append("poll");return next(self.results)
class CoreTests(unittest.TestCase):
    def test_immediate(self):self.assertEqual(m.run(Client([{"status":"completed","value":0}]),"job",{}, {"job"}),{"status":"completed","value":0,"trace":["discover","call"]})
    def test_poll(self):
        c=Client([{"status":"working","task_id":"t"},{"status":"completed","value":"r"}]);r=m.run(c,"job",{}, {"job"})
        self.assertEqual(r["trace"],["discover","call","poll"]);self.assertEqual(r["value"],"r")
    def test_timeout_budget(self):
        c=Client([{"status":"working","task_id":"t"}]*4);r=m.run(c,"job",{}, {"job"},2)
        self.assertEqual(r["status"],"timeout");self.assertEqual(c.seen.count("poll"),2)
    def test_failed(self):self.assertEqual(m.run(Client([{"status":"failed"}]),"job",{}, {"job"})["status"],"failed")
    def test_denied_no_calls(self):
        c=Client([])
        with self.assertRaises(PermissionError):m.run(c,"job",{},set())
        self.assertEqual(c.seen,[])
    def test_unknown(self):
        c=Client([])
        with self.assertRaises(KeyError):m.run(c,"missing",{}, {"missing"})
        self.assertEqual(c.seen,["discover"])
    def test_budget(self):
        with self.assertRaises(ValueError):m.run(Client([]),"job",{}, {"job"},True)
class BonusTests(unittest.TestCase):
    def test_evidence(self):self.assertEqual(m.evidence({"status":"completed","trace":["discover","call","poll"]}),{"completed":True,"polls":1,"live_integration":False})
    def test_timeout(self):self.assertFalse(m.evidence({"status":"timeout","trace":[]})["completed"])
''',
 followups=["超时后工具是否一定没有完成？", "这个本地实验能证明哪些事实，哪些仍需要真实集成验证？"],
 explanation="授权在任何外部边界之前完成。预算只限制轮询次数；超时不等于服务端任务被取消。trace 证明实际流程顺序。"
)
