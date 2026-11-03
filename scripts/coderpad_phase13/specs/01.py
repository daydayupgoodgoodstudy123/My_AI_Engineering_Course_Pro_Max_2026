SPEC = dict(
    title="A bounded tool runner", zh_title="有边界的工具执行器", level="基础",
    brief="为工具注册表补上参数校验和执行循环。先让合法调用成功，再确保坏参数不会触发 executor，最后限制模型连续调用工具的次数。",
    scenario="Your team has a scripted model and a tool registry. Finish the execution boundary so malformed model calls never reach a tool.",
    contract="""1. execute(registry, name, arguments): registry maps names to {'parameters': [required integer parameter names], 'executor': callable}. Return {'ok': True, 'value': executor(arguments)} on success. Arguments must be a dict with exactly those keys and type(value) is int (bool is rejected). Unknown name returns {'ok': False, 'error': 'unknown_tool'}; invalid arguments returns error 'invalid_arguments'; any Exception raised by the executor becomes error 'execution_error'. Never invoke an executor for rejected arguments.
2. run_loop(registry, decisions, max_calls=3): decisions is a finite list of {'tool': name, 'arguments': dict} or {'final': string}. Return {'results': [execute results], 'stop': 'final'|'limit'|'exhausted', 'answer': string|None}. A call attempt counts even when execute returns an error. Check the call limit BEFORE reading the next decision, including a final decision. No final decision means answer None. Empty decisions stops as exhausted. max_calls must have exact type int and be >0, otherwise raise ValueError. Decision envelope shapes are provided valid.""",
    bonus="describe(registry) returns tool names sorted lexicographically, without invoking executors.",
    stubs=["execute", "run_loop", "describe"],
    code=r'''def execute(registry, name, arguments):
    if name not in registry:
        return {"ok": False, "error": "unknown_tool"}
    tool = registry[name]
    if not isinstance(arguments, dict) or set(arguments) != set(tool["parameters"]) or any(type(v) is not int for v in arguments.values()):
        return {"ok": False, "error": "invalid_arguments"}
    try:
        return {"ok": True, "value": tool["executor"](arguments)}
    except Exception:
        return {"ok": False, "error": "execution_error"}

def run_loop(registry, decisions, max_calls=3):
    if type(max_calls) is not int or max_calls <= 0:
        raise ValueError("max_calls")
    results = []
    for decision in decisions:
        if len(results) >= max_calls:
            return {"results": results, "stop": "limit", "answer": None}
        if "final" in decision:
            return {"results": results, "stop": "final", "answer": decision["final"]}
        results.append(execute(registry, decision["tool"], decision["arguments"]))
    return {"results": results, "stop": "exhausted", "answer": None}

def describe(registry):
    return sorted(registry)
''',
    tests=r'''class CoreTests(unittest.TestCase):
    def setUp(self):
        self.seen = []
        self.registry = {"add": {"parameters": ["a", "b"], "executor": lambda a: self.seen.append(a.copy()) or a["a"] + a["b"]}}
    def test_valid_call(self):
        self.assertEqual(m.execute(self.registry, "add", {"a": 2, "b": 3}), {"ok": True, "value": 5})
        self.assertEqual(len(self.seen), 1)
    def test_unknown(self):
        self.assertEqual(m.execute(self.registry, "delete", {}), {"ok": False, "error": "unknown_tool"})
    def test_invalid_arguments_never_execute(self):
        for args in ({"a": True, "b": 1}, {"a": 1.0, "b": 2}, {"a": "1", "b": 2}, {"a": 1}, {"a": 1, "b": 2, "c": 3}, []):
            with self.subTest(args=args):
                self.assertEqual(m.execute(self.registry, "add", args), {"ok": False, "error": "invalid_arguments"})
        self.assertEqual(self.seen, [])
    def test_executor_error_isolated(self):
        def fail(a): raise RuntimeError("offline")
        self.registry["bad"] = {"parameters": [], "executor": fail}
        self.assertEqual(m.execute(self.registry, "bad", {}), {"ok": False, "error": "execution_error"})
        self.assertTrue(m.execute(self.registry, "add", {"a": 0, "b": 0})["ok"])
    def test_final(self):
        self.assertEqual(m.run_loop(self.registry, [{"final": "done"}]), {"results": [], "stop": "final", "answer": "done"})
    def test_limit_counts_errors(self):
        r = m.run_loop(self.registry, [{"tool": "missing", "arguments": {}}, {"final": "done"}], 1)
        self.assertEqual(r, {"results": [{"ok": False, "error": "unknown_tool"}], "stop": "limit", "answer": None})
    def test_empty(self):
        self.assertEqual(m.run_loop(self.registry, []), {"results": [], "stop": "exhausted", "answer": None})
    def test_exhausted_after_call(self):
        self.assertEqual(m.run_loop(self.registry, [{"tool": "add", "arguments": {"a": -1, "b": 2}}])["results"], [{"ok": True, "value": 1}])
    def test_invalid_limit(self):
        for n in (0, -1, True, 1.5):
            with self.subTest(n=n), self.assertRaises(ValueError): m.run_loop(self.registry, [], n)

class BonusTests(unittest.TestCase):
    def test_sorted_description(self):
        self.assertEqual(m.describe({"z": {}, "a": {}}), ["a", "z"])
    def test_no_execution(self):
        self.assertEqual(m.describe({"x": {"executor": lambda _: self.fail("executed")}}), ["x"])
''',
    followups=["为什么 JSON integer 不能直接用 isinstance(value, int) 判断？", "副作用工具重试时，你会增加什么合同？"],
    explanation="先在执行边界拒绝未知工具和非法参数，再调用 executor。循环预算按调用尝试计数，避免模型通过重复失败绕过上限。这里只隔离普通 Exception，不吞掉进程中断。"
)
