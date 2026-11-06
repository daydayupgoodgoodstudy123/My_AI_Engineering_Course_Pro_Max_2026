# 代码讲解 · main.py

> **所属小节**：阶段 14 · Agent 工程 · 第 01 节 Agent Loop：观察、思考、行动 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无参数） ｜ **依赖**：仅标准库（`dataclasses`、`typing`）；无需 API key、无需网络

---

## 1. 这份代码在考察什么

这份 177 行的代码把讲义里的"五个组成要素"逐一落成代码，并用一个**脚本化的假 LLM** 让 ReAct 循环可以离线、确定性地运行：

1. **消息缓冲区**：`AgentLoop.history: list[Turn]`，按 user → thought → action → … → final 的顺序不断增长。
2. **工具注册表**：`ToolRegistry`，名称 → 可调用对象，`dispatch` 负责调用和捕获异常。
3. **停止条件**：回复 `kind == "finish"` 即返回。
4. **轮次预算**：`for step in range(self.max_turns)`，跑满就返回 `"budget exhausted"`。
5. **观察结果格式化器**：工具统一返回字符串；任何异常都被 `dispatch` 转成 `error: ...` 字符串。

此外它还演示了 trace（`pretty_trace` 打印的运行记录），以及"把策略对象（LLM）与循环解耦"的接口设计：循环只通过 `llm.respond(history)` 与模型交互，所以讲义说"把 `ToyLLM` 换成真实提供商，控制流完全一样"。

> 一句话：**这是一个"控制流正确、但模型完全不看观察结果"的 ReAct 骨架**——学它的循环结构，同时要看清它在哪里被简化了。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `ToolCall` | dataclass | 一次工具调用：`name` + `args` 字典 | Action / tool call |
| `Turn` | dataclass | 消息缓冲区里的一条记录：`kind`、`content`、可选的 `tool_call` 与 `observation` | 消息缓冲区 / trace |
| `ToolRegistry` | 类 | `register` 注册、`names` 列出、`dispatch` 调用并把异常变成字符串 | 工具注册表 + 观察格式化 |
| `calculator` | 函数（工具） | 字符白名单 + 受限 `eval` 计算算术表达式 | 示例工具 |
| `KVStore` | 类（工具） | 内存字典，`get` / `set` 两个绑定方法注册为工具 | 有状态工具 |
| `ToyLLM` | 类 | 按脚本顺序逐条返回回复；脚本用完返回 finish | 被替换的"模型" |
| `AgentLoop` | dataclass | `run()`：预算内循环——问模型 → 停止判断 → 记录 thought → 执行工具 → 记录 observation | agent loop 本体 |
| `pretty_trace` | 函数 | 按 `[序号 kind]` 打印 history | trace |
| `build_demo_agent` | 函数 | 注册三个工具、写好 6 步脚本、构造 `max_turns=10` 的 agent | 组装 |
| `main` | 函数 | 运行 demo，打印 trace 与摘要 | 入口 |

数据流：`main` → `build_demo_agent()` 组装 → `agent.run(question)`：`history ← user` →（循环）`ToyLLM.respond` → `ToolRegistry.dispatch` → `history ← thought, action(+observation)` → 遇到 finish → `history ← final` → `pretty_trace` 打印。

---

## 3. 逐段精讲

### 3.1 两个数据类：`ToolCall` 与 `Turn`

```python
@dataclass
class ToolCall:
    name: str
    args: dict[str, Any]


@dataclass
class Turn:
    kind: str
    content: str
    tool_call: ToolCall | None = None
    observation: str | None = None
```

- `@dataclass` 自动生成 `__init__`、`__repr__`、`__eq__`，适合做"纯数据记录"。
- `Turn.kind` 取值为 `"user" / "thought" / "action" / "final"`，这就是讲义里"持续增长的消息缓冲区"的四种条目。
- 注意本代码**没有独立的 "tool" 角色**：observation 被附在 `action` 那条 `Turn` 上。真实 API（Anthropic 的 `tool_use` / `tool_result` 块、OpenAI 的 `role: "tool"` 消息）中，工具结果是一条**单独的消息**，并且要用 `tool_use_id` 与调用对应（讲义练习 5）。
- `kind: str` 是自由字符串，拼错不会报错；TypeScript 版（`main.ts`）用联合类型 `"user" | "thought" | "action" | "final"` 约束，Python 中对应写法是 `Literal[...]`。

### 3.2 `ToolRegistry`：注册、列出、分派

```python
    def dispatch(self, call: ToolCall) -> str:
        fn = self._tools.get(call.name)
        if fn is None:
            return f"error: unknown tool {call.name!r}"
        try:
            return fn(**call.args)
        except TypeError as e:
            return f"error: bad args for {call.name}: {e}"
        except Exception as e:
            return f"error: {type(e).__name__}: {e}"
```

- `fn(**call.args)`：把参数字典解包成关键字参数，这就是"tool call 的 JSON 参数 → Python 函数调用"的最小映射。
- 三种失败都变成 `error:` 前缀的字符串，**不抛出**——这正是讲义"每个 400 错误都应转换为观察结果字符串，而不是让程序崩溃"的实现。
- `names()` 返回 `sorted(self._tools)`：对字典排序得到排好序的键列表。
- ⚠️ 讲义说 `ToolRegistry` 提供"input validation"，但代码里**没有任何 schema 校验**，只是在调用时靠 Python 自己抛 `TypeError`。
- ⚠️ `except TypeError` 无法区分"参数不对"和"工具内部代码出 bug"：实测注册一个 `def bad(x): return len(5)`，`dispatch` 返回 `error: bad args for bad: object of type 'int' has no len()`——明明参数没错，却告诉模型"参数错了"。生产实现应先用 `inspect.signature(fn).bind(**args)` 校验参数，再执行。
- ⚠️ 返回值没有被强制转成字符串：注册一个返回 `42` 的工具，`dispatch` 原样返回 int。

### 3.3 两个示例工具：`calculator` 与 `KVStore`

```python
def calculator(expr: str) -> str:
    allowed = set("0123456789+-*/(). ")
    if not set(expr).issubset(allowed):
        return "error: illegal character in expr"
    try:
        return str(eval(expr, {"__builtins__": {}}, {}))
    except Exception as e:
        return f"error: {type(e).__name__}: {e}"
```

- 先做**字符白名单**：没有字母就写不出 `__import__`、`open` 之类的名字；再把 `__builtins__` 置空作为第二道防线。
- 工具自己也把异常转成字符串（`1/0` → `error: ZeroDivisionError: division by zero`）。
- ⚠️ 白名单放过了 `**`（两个 `*`）：`9**9**9` 是 3.7 亿位的整数，会耗尽 CPU/内存。实测 `9**9**7` 已需约 1.85 秒，而 Python 的"整数转字符串 4300 位上限"要等大数算完、调用 `str()` 时才报错，挡不住拒绝服务。安全写法是用 `ast` 白名单语法节点（见测验 Q12）。
- ⚠️ `eval` 返回浮点：`0.1+0.2` → `0.30000000000000004`。金额计算生产中应使用 `decimal`。

```python
class KVStore:
    def get(self, key: str) -> str:
        return self._store.get(key, f"missing:{key}")

    def set(self, key: str, value: str) -> str:
        self._store[key] = value
        return f"stored {key}"
```

- 在 `build_demo_agent` 中注册的是**绑定方法** `kv.get` / `kv.set`：它们已经"记住"了 `self`，所以注册表调用时只需传 `key` / `value`。这是把有状态对象暴露为工具的常用技巧。
- ⚠️ 讲义写的工具名是 `kv_store.get` / `kv_store.set`，代码实际注册为 `kv_get` / `kv_set`。
- ⚠️ 键不存在时返回 `missing:<key>`，没有 `error:` 前缀，模型可能把它当成真实值。

### 3.4 `ToyLLM`：被替换掉的"大脑"

```python
class ToyLLM:
    def __init__(self, script: list[dict[str, Any]]) -> None:
        self.script = script
        self.cursor = 0

    def respond(self, history: list[Turn]) -> dict[str, Any]:
        if self.cursor >= len(self.script):
            return {"kind": "finish", "content": "no more actions"}
        entry = self.script[self.cursor]
        self.cursor += 1
        return entry
```

- 每次调用返回脚本的下一条，`cursor` 记录读到哪里；脚本用完就返回一个 finish，避免越界。
- 回复是一个字典：`{"kind": "action", "thought": ..., "action": ..., "args": ...}` 或 `{"kind": "finish", "content": ...}`。讲义说 ToyLLM "emits Thought, Action, Observation, Finish lines"，实际上它返回的是**已经结构化好的字典**，既不输出文本行，也**从不产生 Observation**（observation 由循环执行工具得到）。真实 LLM 需要一步解析（function calling 的 JSON 或 ReAct 文本的正则解析），这正是格式错误的高发处（讲义练习 3）。
- ⚠️ **最重要的简化**：`history` 参数从未被使用。脚本中 `"value": "18.0"`、`"expr": "120 + 18.0"` 都是事先写死的，计算器返回什么都不影响后续步骤。也就是说 demo 展示了循环的形状，但没有展示 ReAct 的核心——"observation 改变下一步决策"。测验 Q11 给出了一个真正读取 observation 的 `ReactiveLLM`。
- ⚠️ `cursor` 不会重置：同一个 agent 再次 `run` 时，模型直接回复 `no more actions`；`history` 也会继续累积（实测第二次运行后 history 有 14 条）。

### 3.5 `AgentLoop.run`：循环本体

```python
@dataclass
class AgentLoop:
    llm: ToyLLM
    tools: ToolRegistry
    max_turns: int = 12
    history: list[Turn] = field(default_factory=list)

    def run(self, user_message: str) -> str:
        self.history.append(Turn(kind="user", content=user_message))
        for step in range(self.max_turns):
            reply = self.llm.respond(self.history)
            if reply["kind"] == "finish":
                self.history.append(Turn(kind="final", content=reply["content"]))
                return reply["content"]
            thought = reply.get("thought", "")
            self.history.append(Turn(kind="thought", content=thought))
            call = ToolCall(name=reply["action"], args=reply.get("args", {}))
            observation = self.tools.dispatch(call)
            self.history.append(
                Turn(kind="action", content=call.name,
                     tool_call=call, observation=observation)
            )
        self.history.append(Turn(kind="final",
                                 content="budget exhausted"))
        return "budget exhausted"
```

逐行对应五要素：

| 代码 | 要素 |
|------|------|
| `self.history.append(...)` | ① 消息缓冲区 |
| `self.tools.dispatch(call)` | ② 工具注册表 |
| `if reply["kind"] == "finish": return` | ③ 停止条件（显式 finish） |
| `for step in range(self.max_turns)` + 末尾的 `"budget exhausted"` | ④ 轮次预算 |
| `dispatch` 返回的字符串存进 `observation` | ⑤ 观察格式化 |

- `field(default_factory=list)`：dataclass 中可变默认值必须这样写；直接写 `history: list = []` 会报 `ValueError: mutable default ... is not allowed`。
- `max_turns` 计的是**模型调用次数**（含最后那次 finish），而 `main` 中打印的 `turns used` 数的是 action 条目（工具调用次数）。demo 中前者是 6、后者是 5。
- 每轮恰好**一个**工具调用；真实模型一轮可以发出多个并行调用（练习 1）。
- 只有一种主停止条件（finish）；讲义列出的"本轮没有 tool calls"路径未实现（练习 2，测验 Q10 有实现）。
- ⚠️ `reply["action"]` 用方括号取值：LLM 回复缺 `action` 键时直接 `KeyError`，异常冒出循环，agent 崩溃（实测 `crash: KeyError 'action'`）。这与"错误都要变成 observation"的原则不一致。
- 循环变量 `step` 没有被使用，可以写成 `_`。

### 3.6 `pretty_trace`、`build_demo_agent` 与 `main`

```python
def pretty_trace(history: list[Turn]) -> None:
    for i, turn in enumerate(history):
        tag = f"[{i:02d} {turn.kind:>7}]"
        ...
        elif turn.kind == "action":
            call = turn.tool_call
            assert call is not None
            print(f"{tag} {call.name}({call.args}) -> {turn.observation}")
```

- `{i:02d}`：两位、补零；`{turn.kind:>7}`：右对齐占 7 格，所以输出是 `[02  action]`、`[11   final]`。
- `assert call is not None` 一方面做运行时检查，另一方面让类型检查器知道之后 `call` 不是 `None`（类型收窄）。
- `user`、`thought`、`final` 三个分支打印内容完全相同，可以合并；保留分支是为了以后各自定制格式。

`build_demo_agent` 写好 6 步脚本：存 base=120 → 算 15% 税 → 存 tax → 算总额 → 读回 base 确认 → finish。`max_turns=10` 留出了 4 步余量。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 脚本化 `ToyLLM` | 离线、确定、可测试，聚焦循环本身 | 不读 history，无法展示"观察驱动决策"；生产中替换为真实 provider，并把 history 序列化进请求 |
| 回复用 Python 字典而非文本 | 省掉解析环节 | 真实场景需要解析/校验模型输出，格式错误要反馈为 observation |
| 每轮一个工具调用 | 控制流最简单 | 真实模型会并行调用多个工具，需 `tool_use_id` 对应结果 |
| observation 附在 action Turn 上 | 打印 trace 方便 | 真实 API 要求独立的 tool 结果消息 |
| 异常一律转字符串 | 循环永不因工具崩溃 | `except TypeError` 会把工具 bug 误报成参数错误；应先做签名/schema 校验 |
| 字符白名单 + `eval` | 几行代码实现计算器 | 放过 `**` 导致 DoS；生产用 `ast` 白名单或专用表达式库 |
| 只实现 finish + 预算两种停止 | 讲解清晰 | 缺"无 tool calls"、token 上限、guardrail；应记录 `stop_reason` |
| `max_turns` 计模型调用次数 | 最直观的预算 | 不计 token 和费用；生产中还要有成本上限 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件第 14 行 | 注解延迟求值（存成字符串），可以在注解里提前引用尚未定义的类型 |
| `@dataclass` | `class ToolCall`、`class Turn`、`class AgentLoop` | 自动生成构造函数等方法，用类型注解声明字段 |
| `field(default_factory=list)` | `history: list[Turn] = field(default_factory=list)` | 可变默认值必须用工厂函数，否则所有实例共享同一个列表 |
| 内置泛型注解 | `dict[str, Any]`、`list[Turn]` | Python 3.9+ 可直接用内置类型做泛型 |
| `X \| None` | `tool_call: ToolCall \| None = None` | 联合类型（3.10+ 语法；借助 `__future__` 注解在更早版本也可写） |
| `Callable[..., str]` | `dict[str, Callable[..., str]]` | "接受任意参数、返回 str 的可调用对象" |
| `**kwargs` 解包 | `fn(**call.args)` | 把字典展开为关键字参数 |
| 多个 `except` | `except TypeError` → `except Exception` | 按顺序匹配，先具体后宽泛 |
| `type(e).__name__` | `f"error: {type(e).__name__}: {e}"` | 取异常类名，如 `ZeroDivisionError` |
| f-string 转换符 `!r` | `f"error: unknown tool {call.name!r}"` | 用 `repr()` 格式化，字符串会带引号 |
| f-string 格式符 | `{i:02d}`、`{turn.kind:>7}` | 补零宽度 2；右对齐宽度 7 |
| 集合运算 | `set(expr).issubset(allowed)` | 判断输入字符是否都在白名单中 |
| 受限 `eval` | `eval(expr, {"__builtins__": {}}, {})` | 指定空的全局/局部命名空间；**并不安全**，只是降低风险 |
| 绑定方法 | `tools.register("kv_get", kv.get)` | `kv.get` 已绑定实例，可当普通函数传递 |
| `dict.get(k, default)` | `self._store.get(key, f"missing:{key}")`、`reply.get("args", {})` | 键不存在时返回默认值，不抛 `KeyError` |
| `sorted(dict)` | `return sorted(self._tools)` | 对字典迭代得到键，排序后返回列表 |
| `enumerate` | `for i, turn in enumerate(history)` | 同时拿到下标和元素 |
| 列表推导式 + 条件 | `[t for t in agent.history if t.kind == 'action']` | 过滤出工具调用记录 |
| `assert` 类型收窄 | `assert call is not None` | 运行时检查，同时帮助类型检查器 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行 `main()`，被 import 时不执行 |

---

## 6. 运行结果解读

实际运行（Python 3.13.16，`cd code && python3 main.py`，瞬间完成）：

```text
======================================================================
TOY REACT LOOP — Phase 14, Lesson 01
======================================================================

[00    user] What is 120 plus 15% tax, stored in kv?
[01 thought] store the base price
[02  action] kv_set({'key': 'base', 'value': '120'}) -> stored base
[03 thought] compute 15% tax
[04  action] calculator({'expr': '120 * 0.15'}) -> 18.0
[05 thought] store the tax
[06  action] kv_set({'key': 'tax', 'value': '18.0'}) -> stored tax
[07 thought] compute total
[08  action] calculator({'expr': '120 + 18.0'}) -> 138.0
[09 thought] confirm stored values
[10  action] kv_get({'key': 'base'}) -> 120
[11   final] the total including 15% tax is 138.0

final answer: the total including 15% tax is 138.0
turns used:   5
tools used:   ['calculator', 'kv_get', 'kv_set']
```

逐项解读：

- **12 条 history**：1 条 user + 5 × (thought + action) + 1 条 final。每条 action 行的 `->` 后面就是 observation。
- **`120 * 0.15 -> 18.0`**：`eval` 得到 float，`str()` 之后是 `"18.0"`；下一步脚本里的 `"18.0"` 与它一致只是**作者写脚本时算对了**，不是模型读了 observation。
- **`kv_get -> 120`**：返回的是之前 `kv_set` 存入的字符串 `"120"`，证明 `KVStore` 在多次调用之间保持状态（绑定方法共享同一个 `kv` 实例）。
- **`turns used: 5`**：只数 action；`ToyLLM.respond` 实际被调用 6 次（第 6 次返回 finish），远低于 `max_turns=10`。
- **`tools used`**：是注册表里**注册了**的工具名（排序后），并不是本次实际用到的工具——名字有点误导，只是恰好三个都被用到了。

额外的边界实验（用临时脚本调用本文件中的类）：

| 实验 | 结果 |
|------|------|
| `dispatch(ToolCall("calculator", {"expr": "1/0"}))` | `error: ZeroDivisionError: division by zero` |
| `dispatch(ToolCall("calculator", {"x": "1"}))` | `error: bad args for calculator: calculator() got an unexpected keyword argument 'x'` |
| `dispatch(ToolCall("search", {}))` | `error: unknown tool 'search'` |
| `kv_get` 不存在的键 | `missing:nope`（无 error 前缀） |
| demo 的 `max_turns` 改为 3 | 返回 `budget exhausted`，history 共 8 条 |
| 回复缺 `action` 键 | `KeyError: 'action'`，循环崩溃 |
| 同一 agent 第二次 `run` | 返回 `no more actions`，history 累积到 14 条 |

---

## 7. 动手改一改

1. **（热身）修正统计口径**：在 `AgentLoop` 中增加 `llm_calls` 和 `stop_reason` 两个字段，`main` 同时打印"模型调用次数 / 工具调用次数 / 停止原因"。
2. **（讲义练习 2）无 tool calls 即停止**：允许回复里没有 `action` 时视为最终答案，与显式 finish 并存，并在 trace 中区分两种停止原因。思考哪一种更容易出现"提前终止"。
3. **（讲义练习 3）格式错误恢复**：让 `ToyLLM` 的某一步返回 `{"kind": "action", "action": "calculator", "args": {"expression": "1+1"}}`（参数名写错），再写一个能读 observation 的策略，看到 `error: bad args` 后修正为 `expr` 重试。顺便把 `reply["action"]` 改成安全取值。
4. **（测验 Q11）让模型真正读 observation**：实现 `ReactiveLLM`，第二步用第一步的计算结果拼表达式；然后把 `calculator` 临时改成返回错误，观察循环如何提前结束。
5. **（讲义练习 1 + 5）并行调用**：回复改为 `calls: [...]`，为每个调用生成 `tool_use_id`，用 `concurrent.futures.ThreadPoolExecutor` 并发执行，让结果乱序返回，再按 id 对应回填；超过 `max_tool_calls_per_turn` 的调用回填"已跳过"。
6. **（进阶，讲义练习 4）接入真实模型**：用任意 provider 的 tool calling API 替换 `ToyLLM`，把 history 转成该 API 的消息格式（tool 结果是独立消息）；若使用支持推理通道的 API，对比"Thought 写在 transcript 里"与"推理在独立通道"时 trace 的差异。

---

## 8. 常见坑

- **以为 demo 展示了"观察驱动决策"**：`ToyLLM` 不读 history，所有中间值都写死在脚本里。
- **可变默认参数**：在 dataclass 中写 `history: list = []` 会直接报错；在普通函数里写 `def f(h=[])` 则会让多次调用共享同一个列表。
- **复用 agent 实例**：`history` 和 `ToyLLM.cursor` 都不会重置，第二次 `run` 会带着上一次的记录并立即结束。
- **`except TypeError` 过宽**：工具内部的类型错误会被报告成"参数错误"，误导模型去改参数。
- **把字符白名单当安全边界**：`**` 能造成 DoS；任何 `eval` 型工具都应改用语法树白名单。
- **工具静默失败**：返回空字符串或像 `missing:key` 这种"看起来像值"的结果，模型会当真；错误要有统一、明确的格式。
- **工具输出当指令**：observation 里出现"请删除仓库"之类文字时，它只是数据（讲义 trust boundary 一节）。
- **两个"turn"口径混用**：`max_turns` 数模型调用，`turns used` 数工具调用，排查预算问题时要分清。
