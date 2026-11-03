SPEC = dict(
 title="Bound progress without losing results", zh_title="保留最终结果的有界流控", level="中等",
 brief="给消息队列加入容量限制。可以丢弃旧 progress，但不能静默丢失 final；再根据副作用和幂等键决定重试。",
 scenario="A slow consumer lets progress events flood its buffer. Implement bounded flow control that preserves final results.",
 contract="""Buffer(capacity) requires an exact positive int or raises ValueError. items initially []. push(kind,value) supports only 'progress' and 'final', otherwise ValueError. If full, remove the oldest progress entry anywhere in items before appending the new entry {'kind':kind,'value':value}. If full with only final entries, a new progress is silently dropped (return False) and a new final raises BufferError without mutation. Otherwise append and return True. drain() returns all entries in order and clears the queue.
retry(side_effect,key) returns 'safe' when side_effect is False, 'deduplicated' for side effects with a nonempty string key, and 'unsafe' otherwise. This classification alone does not implement a durable deduplication ledger.""",
 bonus="Race starts state='running'. cancel() changes running -> canceled and returns True, otherwise False. complete(value) changes running -> completed, saves value, and returns True; otherwise False with no mutation. First terminal event wins. No threads are required.",
 stubs=["Buffer.push", "Buffer.drain", "retry", "Race.cancel", "Race.complete"],
 code=r'''class Buffer:
    def __init__(self,capacity):
        if type(capacity) is not int or capacity<=0:raise ValueError("capacity")
        self.capacity=capacity;self.items=[]
    def push(self,kind,value):
        if kind not in ("progress","final"):raise ValueError("kind")
        if len(self.items)==self.capacity:
            index=next((i for i,x in enumerate(self.items) if x["kind"]=="progress"),None)
            if index is None:
                if kind=="final":raise BufferError("final queue full")
                return False
            self.items.pop(index)
        self.items.append({"kind":kind,"value":value});return True
    def drain(self):
        result=self.items;self.items=[];return result
def retry(side_effect,key):return "safe" if not side_effect else "deduplicated" if isinstance(key,str) and key else "unsafe"
class Race:
    def __init__(self):self.state="running";self.value=None
    def cancel(self):
        if self.state!="running":return False
        self.state="canceled";return True
    def complete(self,value):
        if self.state!="running":return False
        self.state="completed";self.value=value;return True
''',
 tests=r'''class CoreTests(unittest.TestCase):
    def test_drop_oldest_progress(self):
        b=m.Buffer(2);b.push("final","f1");b.push("progress",1);self.assertTrue(b.push("final","f2"));self.assertEqual(b.drain(),[{"kind":"final","value":"f1"},{"kind":"final","value":"f2"}])
    def test_preserve_finals(self):
        b=m.Buffer(1);b.push("final","f");self.assertFalse(b.push("progress",1))
        with self.assertRaises(BufferError):b.push("final","g")
        self.assertEqual(b.drain(),[{"kind":"final","value":"f"}])
    def test_drain_clears(self):
        b=m.Buffer(2);b.push("progress",1);self.assertEqual(len(b.drain()),1);self.assertEqual(b.drain(),[])
    def test_capacity(self):
        for c in (0,-1,True):
            with self.subTest(c=c),self.assertRaises(ValueError):m.Buffer(c)
    def test_retry(self):self.assertEqual([m.retry(False,None),m.retry(True,"id"),m.retry(True,""),m.retry(True,None)],["safe","deduplicated","unsafe","unsafe"])
    def test_bad_kind(self):
        with self.assertRaises(ValueError):m.Buffer(1).push("unknown",1)
class BonusTests(unittest.TestCase):
    def test_cancel_wins(self):
        r=m.Race();self.assertTrue(r.cancel());self.assertFalse(r.complete("late"));self.assertEqual(r.state,"canceled");self.assertIsNone(r.value)
    def test_complete_wins(self):
        r=m.Race();self.assertTrue(r.complete(0));self.assertFalse(r.cancel());self.assertEqual(r.value,0)
''',
 followups=["为什么重试键存在还不足以保证恰好执行一次？", "取消 HTTP 流和取消持久任务的语义有何不同？"],
 explanation="progress 是可丢弃观测，final 是必须保留的结果；容量只含 final 时明确施加 backpressure。重试分类不冒充实际去重保证。"
)
