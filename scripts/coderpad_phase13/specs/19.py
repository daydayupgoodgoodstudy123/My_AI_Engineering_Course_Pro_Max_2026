SPEC = dict(
 title="Drive an agent task lifecycle", zh_title="Agent 任务生命周期", level="中等",
 brief="实现委派任务状态转换与幂等 message id。相同 id 不同内容必须拒绝，终态任务不能再次工作。",
 scenario="A coordinator delegates work to a fake specialist. Implement a task lifecycle with replay-safe message handling.",
 contract="""Task starts status='submitted', seen={}, artifacts=[]. apply(message_id,target,artifact=None) allows submitted -> working or rejected; working -> input-required, completed, failed, canceled; input-required -> working or canceled. A fresh message requesting any other transition raises ValueError without consuming its id. A completed transition requires a nonempty string artifact; no other transition may supply an artifact. On success set status, append artifact if completed, save (target,artifact) under message_id, return status. An exact replay of an accepted message returns CURRENT status without changing artifacts, even if status has since advanced. Reusing a message id with different contents raises ValueError. ids are provided nonempty strings.""",
 bonus="text_parts(parts) joins text values of {'type':'text','text':str} parts with newline, ignoring file/data parts. Input parts are valid fixture dicts; empty list returns ''.",
 stubs=["Task.apply", "text_parts"],
 code=r'''class Task:
    def __init__(self):self.status="submitted";self.seen={};self.artifacts=[]
    def apply(self,message_id,target,artifact=None):
        content=(target,artifact)
        if message_id in self.seen:
            if self.seen[message_id]!=content:raise ValueError("conflicting replay")
            return self.status
        allowed={"submitted":{"working","rejected"},"working":{"input-required","completed","failed","canceled"},"input-required":{"working","canceled"}}
        if target not in allowed.get(self.status,set()):raise ValueError("transition")
        if target=="completed":
            if not isinstance(artifact,str) or not artifact:raise ValueError("artifact")
        elif artifact is not None:raise ValueError("artifact")
        self.status=target;self.seen[message_id]=content
        if artifact is not None:self.artifacts.append(artifact)
        return self.status
def text_parts(parts):return "\n".join(p["text"] for p in parts if p["type"]=="text")
''',
 tests=r'''class CoreTests(unittest.TestCase):
    def test_lifecycle(self):
        t=m.Task()
        for mid,state in (("1","working"),("2","input-required"),("3","working")):
            self.assertEqual(t.apply(mid,state),state)
        self.assertEqual(t.apply("4","completed","report"),"completed");self.assertEqual(t.artifacts,["report"])
    def test_replay(self):
        t=m.Task();t.apply("1","working");t.apply("2","completed","r");self.assertEqual(t.apply("1","working"),"completed");t.apply("2","completed","r");self.assertEqual(t.artifacts,["r"])
    def test_conflict(self):
        t=m.Task();t.apply("1","working")
        with self.assertRaises(ValueError):t.apply("1","rejected")
    def test_invalid_does_not_consume(self):
        t=m.Task()
        with self.assertRaises(ValueError):t.apply("1","completed","r")
        self.assertEqual(t.apply("1","working"),"working")
    def test_terminal(self):
        t=m.Task();t.apply("1","rejected")
        with self.assertRaises(ValueError):t.apply("2","working")
    def test_artifact_contract(self):
        t=m.Task();t.apply("1","working")
        with self.assertRaises(ValueError):t.apply("2","completed")
        self.assertEqual(t.status,"working")
class BonusTests(unittest.TestCase):
    def test_parts(self):self.assertEqual(m.text_parts([{"type":"text","text":"a"},{"type":"file","uri":"u"},{"type":"text","text":"b"}]),"a\nb")
    def test_empty(self):self.assertEqual(m.text_parts([]),"")
''',
 followups=["去重记录应保留多久？", "任务完成状态和产物持久化为什么应该原子提交？"],
 explanation="合法转换与 message id 去重各有边界。精确重放返回当前状态，不重新写产物；冲突重放明确拒绝。"
)
