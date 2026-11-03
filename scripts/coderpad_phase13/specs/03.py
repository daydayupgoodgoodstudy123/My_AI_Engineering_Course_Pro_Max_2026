SPEC = dict(
    title="Reassemble interleaved tool streams", zh_title="重组交错的工具流", level="中等",
    brief="同一条流包含多个交错调用。按 index 收集 name、id 和 arguments 片段，在全部片段到齐之后解析；加分练习使用线程池并行执行。",
    scenario="A streaming model interleaves argument fragments for several tools. Repair the accumulator without parsing incomplete JSON.",
    contract="""1. assemble(events): each event is {'index': nonnegative int, optional 'id': nonempty str, optional 'name': nonempty str, optional 'arguments': str}. Concatenate argument fragments per index in arrival order. id/name may be repeated identically but conflicting values raise ValueError. Indices may arrive out of order; return [{'id', 'name', 'arguments': dict}] ordered by numeric index. Empty events returns [].
2. Parse JSON only after the complete event list is consumed. Missing id/name, missing/invalid/nonobject JSON, duplicate final ids, invalid index (including bool), or invalid fragment types raise ValueError. Do not execute tools in assemble. No mutation of events.""",
    bonus="parallel(calls, executor, workers=3) uses ThreadPoolExecutor and returns executor(call) results in input order. Each call runs once; independent calls must be able to start concurrently. Executor exceptions propagate. workers is an exact positive int or raises ValueError; empty calls returns []. No wall-clock timing assertions are needed.",
    stubs=["assemble", "parallel"],
    code=r'''import json
from concurrent.futures import ThreadPoolExecutor

def assemble(events):
    buffers = {}
    for event in events:
        index = event.get("index")
        if type(index) is not int or index < 0: raise ValueError("index")
        buf = buffers.setdefault(index, {"arguments": ""})
        for key in ("id", "name"):
            if key in event:
                value = event[key]
                if not isinstance(value, str) or not value or (key in buf and buf[key] != value): raise ValueError(key)
                buf[key] = value
        fragment = event.get("arguments", "")
        if not isinstance(fragment, str): raise ValueError("fragment")
        buf["arguments"] += fragment
    result, ids = [], set()
    for index in sorted(buffers):
        b = buffers[index]
        if "id" not in b or "name" not in b or b["id"] in ids: raise ValueError("identity")
        args = json.loads(b["arguments"])
        if not isinstance(args, dict): raise ValueError("arguments")
        ids.add(b["id"])
        result.append({"id": b["id"], "name": b["name"], "arguments": args})
    return result

def parallel(calls, executor, workers=3):
    if type(workers) is not int or workers <= 0: raise ValueError("workers")
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(executor, calls))
''',
    tests=r'''class CoreTests(unittest.TestCase):
    def test_interleaved(self):
        events = [{"index": 1, "id": "b", "name": "weather", "arguments": '{"city":'}, {"index": 0, "id": "a", "name": "add", "arguments": '{"x":'}, {"index": 1, "arguments": '"NY"}'}, {"index": 0, "arguments": '2}'}]
        self.assertEqual(m.assemble(events), [{"id": "a", "name": "add", "arguments": {"x": 2}}, {"id": "b", "name": "weather", "arguments": {"city": "NY"}}])
    def test_repeat_identity(self):
        self.assertEqual(m.assemble([{"index": 2, "id": "a", "name": "f", "arguments": '{'}, {"index": 2, "id": "a", "name": "f", "arguments": '}'}])[0]["arguments"], {})
    def test_conflicting_identity(self):
        for key in ("id", "name"):
            with self.subTest(key=key), self.assertRaises(ValueError): m.assemble([{"index": 0, "id": "a", "name": "f", "arguments": '{}'}, {"index": 0, key: "other"}])
    def test_incomplete_and_nonobject(self):
        for raw in ('{', '[]', 'null'):
            with self.subTest(raw=raw), self.assertRaises(ValueError): m.assemble([{"index": 0, "id": "a", "name": "f", "arguments": raw}])
    def test_missing_identity(self):
        with self.assertRaises(ValueError): m.assemble([{"index": 0, "arguments": '{}'}])
    def test_duplicate_ids(self):
        with self.assertRaises(ValueError): m.assemble([{"index": i, "id": "a", "name": "f", "arguments": '{}'} for i in (0, 1)])
    def test_bad_index(self):
        for index in (-1, True, 1.0):
            with self.subTest(index=index), self.assertRaises(ValueError): m.assemble([{"index": index}])
    def test_bad_fragment(self):
        with self.assertRaises(ValueError): m.assemble([{"index": 0, "arguments": {}}])
    def test_empty(self): self.assertEqual(m.assemble([]), [])

class BonusTests(unittest.TestCase):
    def test_order_and_concurrency(self):
        import threading
        barrier = threading.Barrier(3, timeout=3)
        def execute(value):
            barrier.wait()
            return value * 2
        self.assertEqual(m.parallel([3, 1, 2], execute, 3), [6, 2, 4])
    def test_exception_and_empty(self):
        def fail(_): raise RuntimeError("failed")
        with self.assertRaises(RuntimeError): m.parallel([1], fail)
        self.assertEqual(m.parallel([], fail), [])
    def test_workers(self):
        for workers in (0, True):
            with self.subTest(workers=workers), self.assertRaises(ValueError): m.parallel([], lambda x: x, workers)
''',
    followups=["为什么一次片段恰好构成合法 JSON 时也不应提前执行？", "并行执行有副作用的工具前，需要确认哪些条件？"],
    explanation="index 决定独立缓冲区，id/name 是稳定身份。流结束才解析，避免截断和提前执行。并行测试用 Barrier 验证三个任务能同时开始，而不是依赖机器速度。"
)
