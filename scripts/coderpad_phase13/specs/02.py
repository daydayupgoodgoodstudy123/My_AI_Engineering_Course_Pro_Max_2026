SPEC = dict(
    title="Normalize provider tool calls", zh_title="统一不同模型的工具调用", level="基础到中等",
    brief="接手已有的多模型适配层，把三种固定 fixture 转成统一 Call 列表，再实现 tool choice。重点是格式适配、顺序和错误处理。",
    scenario="A service switches between three providers. Implement a canonical call parser and a tool-choice adapter for the frozen fixture formats below.",
    contract="""1. normalize(provider, payload) returns [{'id': str, 'name': str, 'arguments': dict}, ...] in source order. Supported providers: 'openai', 'anthropic', 'gemini'. OpenAI payload is {'tool_calls': [{'id': ..., 'function': {'name': ..., 'arguments': JSON_STRING}}]}; Anthropic is {'content': [{'type': 'tool_use', 'id': ..., 'name': ..., 'input': DICT}, or non-tool blocks]}; Gemini is {'parts': [{'functionCall': {'id': ..., 'name': ..., 'args': DICT}}, or non-tool parts]}. A missing list means no calls. Ignore non-tool Anthropic blocks and Gemini parts. Provider-specific outer API envelopes have already been removed.
2. All ids and names must be nonempty strings; arguments must decode to a dict. Any malformed call, malformed JSON, non-list collection, or unsupported provider raises ValueError; do not return partial results. Do not mutate payload.
3. choice(provider, mode, name=None): mode is 'auto', 'none', 'required', or 'force'. OpenAI maps the first three to the same string; force to {'type': 'function', 'function': {'name': name}}. Anthropic maps to {'type': 'auto'|'none'|'any'|'tool'}, with 'name' only for force. Gemini returns {'mode': 'AUTO'|'NONE'|'ANY'}, adding 'allowed_function_names': [name] for force. Force requires a nonempty string name. Other modes ignore name. Invalid provider/mode raises ValueError. These are exercise fixture contracts, not complete or live SDK adapters.""",
    bonus="unique_calls(calls) removes exact duplicate ids, preserving first occurrence. If the same id has a different name or arguments, raise ValueError. Calls have already been normalized.",
    stubs=["normalize", "choice", "unique_calls"],
    code=r'''import json
from copy import deepcopy

def normalize(provider, payload):
    if provider not in ("openai", "anthropic", "gemini"):
        raise ValueError("provider")
    try:
        key = {"openai": "tool_calls", "anthropic": "content", "gemini": "parts"}[provider]
        blocks = payload.get(key, [])
        if not isinstance(blocks, list): raise ValueError("collection")
        result = []
        for b in blocks:
            if provider == "openai":
                call = {"id": b["id"], "name": b["function"]["name"], "arguments": json.loads(b["function"]["arguments"])}
            elif provider == "anthropic":
                if b.get("type") != "tool_use": continue
                call = {"id": b["id"], "name": b["name"], "arguments": b["input"]}
            else:
                if "functionCall" not in b: continue
                c = b["functionCall"]
                call = {"id": c["id"], "name": c["name"], "arguments": c["args"]}
            if any(not isinstance(call[k], str) or not call[k] for k in ("id", "name")) or not isinstance(call["arguments"], dict):
                raise ValueError("call")
            result.append(deepcopy(call))
        return result
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError("malformed call") from exc

def choice(provider, mode, name=None):
    if provider not in ("openai", "anthropic", "gemini") or mode not in ("auto", "none", "required", "force"):
        raise ValueError("choice")
    if mode == "force" and (not isinstance(name, str) or not name): raise ValueError("name")
    if provider == "openai":
        return {"type": "function", "function": {"name": name}} if mode == "force" else mode
    if provider == "anthropic":
        return {"type": "tool", "name": name} if mode == "force" else {"type": {"required": "any"}.get(mode, mode)}
    return {"mode": "ANY", "allowed_function_names": [name]} if mode == "force" else {"mode": {"auto": "AUTO", "none": "NONE", "required": "ANY"}[mode]}

def unique_calls(calls):
    seen = {}
    for call in calls:
        if call["id"] in seen and seen[call["id"]] != call: raise ValueError("conflicting id")
        seen.setdefault(call["id"], call)
    return list(seen.values())
''',
    tests=r'''class CoreTests(unittest.TestCase):
    def test_openai(self):
        self.assertEqual(m.normalize("openai", {"tool_calls": [{"id": "a", "function": {"name": "sum", "arguments": '{"x":2}'}}]}), [{"id": "a", "name": "sum", "arguments": {"x": 2}}])
    def test_anthropic_order(self):
        data = {"content": [{"type": "text", "text": "thinking"}, {"type": "tool_use", "id": "b", "name": "f", "input": {}}, {"type": "tool_use", "id": "a", "name": "g", "input": {"v": 0}}]}
        self.assertEqual([x["id"] for x in m.normalize("anthropic", data)], ["b", "a"])
    def test_gemini(self):
        self.assertEqual(m.normalize("gemini", {"parts": [{"text": "hi"}, {"functionCall": {"id": "g1", "name": "f", "args": {}}}]}), [{"id": "g1", "name": "f", "arguments": {}}])
    def test_missing_collections(self):
        for provider in ("openai", "anthropic", "gemini"):
            with self.subTest(provider=provider): self.assertEqual(m.normalize(provider, {}), [])
    def test_bad_json_and_nonobject(self):
        for raw in ('{', '[]', 'null', '7'):
            with self.subTest(raw=raw), self.assertRaises(ValueError): m.normalize("openai", {"tool_calls": [{"id": "a", "function": {"name": "f", "arguments": raw}}]})
    def test_malformed(self):
        for payload in ({"tool_calls": None}, {"tool_calls": [{}]}, {"tool_calls": [{"id": "", "function": {"name": "f", "arguments": '{}'}}]}):
            with self.subTest(payload=payload), self.assertRaises(ValueError): m.normalize("openai", payload)
    def test_no_mutation(self):
        from copy import deepcopy
        p = {"content": [{"type": "tool_use", "id": "a", "name": "f", "input": {"nested": [1]}}]}
        before = deepcopy(p)
        m.normalize("anthropic", p)
        self.assertEqual(p, before)
    def test_modes(self):
        for mode, a, g in (("auto", "auto", "AUTO"), ("none", "none", "NONE"), ("required", "any", "ANY")):
            with self.subTest(mode=mode):
                self.assertEqual(m.choice("openai", mode), mode)
                self.assertEqual(m.choice("anthropic", mode), {"type": a})
                self.assertEqual(m.choice("gemini", mode), {"mode": g})
    def test_force(self):
        self.assertEqual(m.choice("openai", "force", "f"), {"type": "function", "function": {"name": "f"}})
        self.assertEqual(m.choice("anthropic", "force", "f"), {"type": "tool", "name": "f"})
        self.assertEqual(m.choice("gemini", "force", "f"), {"mode": "ANY", "allowed_function_names": ["f"]})
    def test_bad_choice(self):
        for args in (("other", "auto"), ("openai", "bad"), ("gemini", "force"), ("anthropic", "force", "")):
            with self.subTest(args=args), self.assertRaises(ValueError): m.choice(*args)

class BonusTests(unittest.TestCase):
    def test_deduplicate(self):
        a = {"id": "a", "name": "f", "arguments": {}}
        self.assertEqual(m.unique_calls([a, a.copy()]), [a])
    def test_conflicting_ids(self):
        with self.assertRaises(ValueError): m.unique_calls([{"id": "a", "name": "f", "arguments": {}}, {"id": "a", "name": "g", "arguments": {}}])
''',
    followups=["为什么要先完成整批校验，再交给执行层？", "供应商升级接口后，你会怎样保护这个适配层？"],
    explanation="把供应商差异限制在适配边界，输出统一的数据结构。逐条归一化但整批返回，任何坏调用都中止本次解析。去重需要同时验证 id 对应的语义，避免悄悄复用错误调用。"
)
