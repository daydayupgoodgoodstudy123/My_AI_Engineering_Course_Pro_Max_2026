# 测验 · 并行 Tool Calls 与工具调用中的 Streaming（Parallel Tool Calls and Streaming with Tools）

> **阶段 13 · 工具与协议 · 第 03 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 提示：本节中文讲义机翻质量较差（如"线性池""宽度计数"等），以英文版为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 为什么要并行调用 | 一轮发出多个独立调用：省掉多次 LLM 往返，执行时间从"各调用之和"变成"最慢的那一个" |
| 2 | 各家开关 | OpenAI `parallel_tool_calls`（默认开）；Anthropic `disable_parallel_tool_use`（讲义：Claude 3.5 起默认允许并行，设 `true` 关闭）；Gemini 由 `function_calling_config` 控制 |
| 3 | 何时关闭并行 | 有顺序依赖（先 `create_file` 再 `write_file`）、一个调用的输出是另一个的输入、下游限流扛不住扇出 |
| 4 | id 关联 | 每个结果必须带上对应调用的 id（`tool_call_id` / `tool_use_id` / `functionResponse.id`）；讲义：Gemini 2 按 name 匹配，同名并行调用无法区分 |
| 5 | 乱序完成 | 并行调用完成顺序不可预测，id 才是"胶水"；讲义建议按完成顺序回复并显式带 id |
| 6 | 流式参数重组 | `arguments` 分片到达、多个调用在同一条流上交错；每个调用一个累加缓冲区（accumulator） |
| 7 | 各家流式形状 | OpenAI：`delta.tool_calls[i]` 按 `index` 区分、`id` 只在首片出现、`finish_reason:"tool_calls"` 收尾；Anthropic：`content_block_start/delta(input_json_delta)/stop`；Gemini 3：带 `functionCallId` 的分片 |
| 8 | parse-early 陷阱 | 只有收到"调用结束"信号后才能 `json.loads`；数括号判断完整性不可靠（字符串里的括号会误判） |
| 9 | 延迟模型 | 并行/串行 ≈ `max/sum`；本节 400/600/800 ms → 1800 ms vs 800 ms，约 2.25 倍 |
| 10 | 流式提前执行 | 某个调用的参数一完整就立刻开始执行，不必等整条流结束 |

### 核心技能（能动手做到）

- [ ] 用 `ThreadPoolExecutor`（或 `asyncio.gather`）并行执行多个工具调用，并测量 wall-clock 时间
- [ ] 写一个按 id（或 OpenAI 的 index）分桶的流式参数累加器，只在结束信号后解析 JSON
- [ ] 让累加器能处理未知 id、重复 stop、中途取消、参数不完整等异常事件
- [ ] 把真实 OpenAI 形状的流式 chunk（`index` + 首片 `id`）重组成完整调用
- [ ] 根据依赖图把一批调用分成若干"波次"（wave），同一波内并行、波与波之间串行
- [ ] 估算串行 vs 并行、等全部 vs 提前执行的端到端耗时

---

## 二、基础自测（选择题）

**Q1.** 本节 demo 1 的三个模拟延迟是 400、600、800 ms。理论上的并行执行时间是：

- A. 600 ms（平均值）
- B. 800 ms（最大值）
- C. 1800 ms（总和）
- D. 1200 ms

**Q2.** 在 **OpenAI** 的流式响应中，一个参数分片属于哪个并行调用，主要靠什么字段判断？

- A. 每个分片都带的 `tool_call_id`
- B. 分片到达的先后顺序
- C. 函数名 `name`
- D. `delta.tool_calls[i].index`（`id` 只在该调用的第一个分片里出现）

**Q3.** 下列哪种情况**最应该**关闭并行工具调用？

- A. 先 `create_file(path)`，再 `write_file(path, content)`
- B. 同时查询三个城市的天气
- C. 同时搜索三个不同的文档库
- D. 同时读取三个互不相关的配置文件

**Q4.** 关于流式 `arguments` 的解析时机，正确的是：

- A. 每收到一个分片就 `json.loads` 一次，失败就忽略
- B. 数到左右花括号数量相等时就可以解析
- C. 等到 provider 的"该调用结束"信号（如 Anthropic 的 `content_block_stop`、OpenAI 的 `finish_reason: "tool_calls"`）后再解析
- D. 等整个会话结束后再统一解析

**Q5.** 讲义说"brace-counting is unreliable"。对字符串 `{"q": "a}b"` 做简单的括号计数（遇 `{` 加一、遇 `}` 减一），结果是：

- A. 深度为 1，判断为"未完成"，与实际一致
- B. 深度为 2，判断为"未完成"
- C. 深度为 0，判断为"已完成"，但 `json.loads` 会失败（实际还缺一个 `}`）
- D. 深度为 −1，抛出异常

**Q6.** 按本节讲义，Anthropic 的并行工具调用默认状态与关闭方式是：

- A. 默认允许并行；设置 `disable_parallel_tool_use: true` 关闭
- B. 默认关闭；设置 `parallel_tool_calls: true` 开启
- C. 不支持并行
- D. 默认允许并行；设置 `tool_choice: "none"` 关闭

**Q7.** 阅读 `replay_and_execute` 的最后一段：

```python
        for cid, fut in in_flight.items():
            results[cid] = fut.result()
```

下列说法正确的是：

- A. `results` 按完成先后排序，最快的调用排在最前
- B. `fut.result()` 不会阻塞，因为任务已经完成
- C. 如果某个执行器抛异常，异常会被静默吞掉
- D. `results` 按调用被提交的顺序（流中 `call_stop` 的顺序）排列，而不是按完成顺序；这与讲义"按完成顺序回复"的建议不同

**Q8.** demo 1 用线程池就能把 1800 ms 降到约 800 ms，最关键的前提是：

- A. Python 线程可以同时在多个 CPU 核上执行字节码
- B. 执行器是 I/O 型（这里用 `time.sleep` 模拟），等待期间会释放 GIL；如果是纯 CPU 计算，线程池几乎没有加速
- C. `ThreadPoolExecutor` 会自动把函数编译成 C 代码
- D. `max_workers` 越大速度越快，与执行器类型无关

---

## 三、动手 / 代码题

**Q9.** 本节的 `StreamAccumulator` 和 `CallBuffer.try_parse` 没有任何防御。下面的事件序列会发生什么？（均已实际运行）

```python
acc.on_event({"type": "args_delta", "id": "zzz", "chunk": "x"})          # (a) 未 start 的 id
acc.on_event({"type": "call_start", "id": "A", "name": "w"})
acc.on_event({"type": "args_delta", "id": "A", "chunk": '{"city": "Beng'})
acc.on_event({"type": "call_stop", "id": "A"})                          # (b) 参数不完整就 stop
acc.on_event({"type": "call_stop", "id": "A"})                          # (c) 重复 stop
```

改写累加器：返回 `("ready", id, args)` / `("error", id, msg)` / `("cancelled", id, None)` 三类事件，并支持讲义练习 2 的 `call_cancel` 事件（丢弃缓冲区）。

**Q10.** 代码注释说 `fake_openai_stream` "Real streams look like this"，但真实的 OpenAI Chat Completions 流长这样（节选）：

```python
{"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "call_A", "type": "function",
              "function": {"name": "get_weather", "arguments": ""}}]}, "finish_reason": None}]}
{"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": "{\"city\":"}}]}, "finish_reason": None}]}
{"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": "\"Bengaluru\"}"}}]}, "finish_reason": None}]}
{"choices": [{"delta": {"tool_calls": [{"index": 1, "id": "call_B", ...}]}, "finish_reason": None}]}
...
{"choices": [{"delta": {}, "finish_reason": "tool_calls"}]}
```

1. 列出它与 `fake_openai_stream` 的三处关键差异。
2. 写 `accumulate_openai(chunks)`，返回 `[(id, name, args_dict), ...]`。
3. 在真实 OpenAI 流上，"一个调用的参数一完整就立刻执行"还能像本节代码那样依赖 per-call stop 事件吗？哪家 provider 的事件模型和本节的假流更像？

**Q11.**（手算）

1. 设每次 LLM 往返耗时 1000 ms，工具延迟 400/600/800 ms。"串行"模式下模型每轮只发一个调用（3 轮调用 + 1 轮最终回答），"并行"模式下 1 轮发三个调用 + 1 轮最终回答。分别算出端到端耗时和缩短比例。讲义说串行"Roughly 4x the ideal wall-clock time"，在这个假设下成立吗？
2. 把延迟改成 Bengaluru 800、Tokyo 600、Zurich 400，并让假流在每个 `call_stop` 前停顿 100 ms（即 A、B、C 的参数分别在 100、200、300 ms 完整，流在 300 ms 结束）。"每个调用参数完整就执行"与"等整条流结束再统一执行"各需多少毫秒？

**Q12.**（讲义练习 4）一轮中模型发出四个调用：`c1: create_file`、`c2: write_file`（依赖 c1）、`c3: get_weather`、`c4: get_weather`。写一个 `schedule(calls, deps)`，把调用分成若干波次：同一波内的调用互不依赖、可并行；后一波依赖前面的波次。有环时报错。给出本例的输出。

---

## 四、面试高频题

**Q13.**（基础必考）什么是并行工具调用？它节省了哪两部分时间？什么情况下不应该并行？

**Q14.**（原理深挖）流式工具调用中，多个调用的参数在同一条流上交错到达。请描述你的重组方案，以及如何判断"一个调用的参数已经完整"。为什么不能靠数括号？

**Q15.**（工程实践）你的 agent 一轮会扇出 10 个调用到同一个有限流（例如 5 QPS）的第三方 API。会出什么问题？你会怎么设计宿主侧的并发控制？

**Q16.**（场景设计）设计一个宿主层的"并行调度器"：既支持模型一次发出多个调用，又要保证有副作用的调用之间的顺序与安全。说出你的数据结构和调度规则。

**Q17.**（追问型）并行调用中有一个调用超时或失败了，你会怎么回复模型？要不要等所有调用都结束？结果顺序重要吗？

---

## 五、参考答案与解析

### Q1 — 答案：B

并行时三个执行器同时开始，总时间由最慢的决定：`max(400, 600, 800) = 800 ms`；串行是总和 1800 ms（C）。实际运行：sequential 1800 ms、parallel 802 ms、speedup 2.25x。多出的 2 ms 是线程创建与调度开销。A、D 没有依据。

### Q2 — 答案：D

讲义："The chunk carries `index` (position in the call list). You accumulate per-index, read `id` when it first appears"。OpenAI 只在某个调用的第一个分片里给出 `id` 和 `name`，后续分片只有 `index` 和 `arguments` 片段。A 错，并非每片都带 id（本节的假流每片都带 id，这是它与真实格式的差别之一，见 Q10）；B 错，多个调用的分片会交错；C 错，并行调用常常是同一个函数名。

### Q3 — 答案：A

`write_file` 依赖 `create_file` 先完成，有顺序依赖，并行会产生竞态（文件可能还不存在）。讲义原文就用了这个例子。B、C、D 都是互相独立的只读操作，正是适合并行的场景。

### Q4 — 答案：C

讲义："The correct gate is the provider's end-of-call signal: OpenAI's `finish_reason = "tool_calls"`, Anthropic's `content_block_stop`, or Gemini's stream-end event. Only then attempt `json.loads`." A 会在每个中间分片上抛异常，白白浪费计算，也容易让人写出"吞掉异常"的脆弱逻辑；B 是讲义明确否定的做法；D 太晚，失去了提前执行的机会。

### Q5 — 答案：C

已实际运行：计数结果为 0，看起来"完整"，但 `json.loads('{"q": "a}b"')` 失败——字符串里的 `}` 被当成了结构括号，真正的外层 `}` 还没到。这就是讲义说的"braces inside quoted strings ... cause false positives"。要正确判断，必须用能识别字符串和转义的增量 JSON 解析器，或者等结束信号。

### Q6 — 答案：A

讲义："Anthropic. Parallel via `disable_parallel_tool_use: false` (default on Claude 3.5 and up). Set `true` for serial." Key Terms 也写"Opt-out flag; default is parallel enabled"。B 是把 OpenAI 的参数名套到 Anthropic 上，而且方向反了；D 中 `tool_choice: "none"` 禁止的是所有工具调用，不是并行。注意第 01 节讲义说 Anthropic 的并行是 "opt-in"，与本节矛盾，以本节为准。

### Q7 — 答案：D

`in_flight` 是普通 dict，按插入顺序迭代；插入发生在每个 `call_stop` 之后，所以 `results` 的顺序是 A、B、C（提交顺序）。`fut.result()` 会**阻塞**等待该任务完成（B 错）；执行器抛出的异常会在 `fut.result()` 处重新抛出，不会被吞掉（C 错）。如果想按完成顺序处理，应使用 `concurrent.futures.as_completed`——我们实测用 `as_completed` 提交 C、A、B（延迟 800/400/600）时，得到 `['call_A', 'call_B', 'call_C']`，即按完成先后。

### Q8 — 答案：B

CPython 有 GIL，同一时刻只有一个线程执行 Python 字节码（A 错）。`time.sleep`、网络 I/O、文件 I/O 等待期间会释放 GIL，所以 I/O 型任务可以用线程重叠等待时间。真实工具调用多是网络请求，线程池或 asyncio 都有效；CPU 密集型执行器应使用进程池。C 是编造；D 错，worker 数超过任务数没有意义，且受下游限流约束。

### Q9 — 参考答案

实际运行结果：(a) `KeyError: 'zzz'`，整个流处理崩溃；(b) `call_stop` 返回该缓冲区，随后 `try_parse()` 抛 `JSONDecodeError: Unterminated string ...`；(c) 第二次 `call_stop` 再次返回同一个缓冲区——在 `replay_and_execute` 中会导致同一调用**被执行两次**（对有副作用的工具是严重问题）。

参考实现（已运行验证，输出依次为 A 的"参数不完整"错误、A 重复 stop 错误、Z 未知 id 错误、B 被取消、C 就绪）：

```python
@dataclass
class CallBuffer:
    id: str
    name: str = ""
    args_buf: str = ""
    state: str = "open"            # open | done | cancelled

@dataclass
class SafeAccumulator:
    buffers: dict = field(default_factory=dict)

    def on_event(self, ev):
        kind, cid = ev["type"], ev.get("id")
        if kind == "call_start":
            if cid in self.buffers:
                return [("error", cid, "duplicate call_start")]
            self.buffers[cid] = CallBuffer(id=cid, name=ev["name"])
            return []
        buf = self.buffers.get(cid)
        if buf is None or buf.state != "open":
            return [("error", cid, f"{kind} for unknown or closed call")]
        if kind == "args_delta":
            buf.args_buf += ev["chunk"]
            return []
        if kind == "call_cancel":
            buf.state, buf.args_buf = "cancelled", ""
            return [("cancelled", cid, None)]
        if kind == "call_stop":
            buf.state = "done"
            try:
                return [("ready", cid, json.loads(buf.args_buf or "{}"))]
            except json.JSONDecodeError as e:
                return [("error", cid, f"incomplete arguments: {e.msg}")]
        return [("error", cid, f"unknown event {kind}")]
```

要点：用状态机（open → done / cancelled）保证每个调用只"就绪"一次；错误变成事件而不是异常，宿主可以把它作为该 id 的错误结果回填给模型。讲义练习 2 提示了真实世界的"中途中断"信号：例如 OpenAI 的 `finish_reason: "length"`（输出被截断，参数必然不完整）。

### Q10 — 参考答案

1. 差异：
   - 真实流按 **`index`** 区分调用，`id` 和 `name` 只在首片出现；假流每个事件都带 `id`。
   - 真实流**没有逐个调用的 stop 事件**，整条消息只有一个 `finish_reason: "tool_calls"`；假流有 `call_start` / `call_stop`。
   - 真实流的外层是 `choices[0].delta`，假流是扁平事件。（此外真实 OpenAI 流里不同调用的分片通常按 index 依次到达，而假流故意让三者交错。）
2. 参考实现（已运行验证，输出 `[('call_A', 'get_weather', {'city': 'Bengaluru'}), ('call_B', 'get_weather', {'city': 'Tokyo'})]`）：

```python
@dataclass
class Slot:
    id: str = ""
    name: str = ""
    args: str = ""

def accumulate_openai(chunks):
    slots: dict[int, Slot] = {}
    for ch in chunks:
        choice = ch["choices"][0]
        for d in choice["delta"].get("tool_calls") or []:
            s = slots.setdefault(d["index"], Slot())
            if d.get("id"):
                s.id = d["id"]
            fn = d.get("function") or {}
            if fn.get("name"):
                s.name = fn["name"]
            s.args += fn.get("arguments") or ""
        if choice.get("finish_reason") == "tool_calls":
            return [(s.id, s.name, json.loads(s.args)) for _, s in sorted(slots.items())]
    raise RuntimeError("stream ended without finish_reason=tool_calls")
```

3. 不能直接依赖。OpenAI 只有整体结束信号；若要提前执行，只能用启发式（例如出现 `index = i+1` 时认为第 i 个已完整，但这依赖分片顺序假设），或用增量 JSON 解析器判断第 i 个对象已闭合。本节假流的 `call_start / args_delta / call_stop` 更接近 **Anthropic** 的 `content_block_start / content_block_delta(input_json_delta) / content_block_stop`，每个块都有自己的结束事件。讲义描述的 Gemini 3 `functionCallId` 分片也是按 id 区分。

### Q11 — 参考答案

1. 串行：`4 × 1000 + (400 + 600 + 800) = 5800 ms`；并行：`2 × 1000 + max(400, 600, 800) = 2800 ms`。缩短约 `1 − 2800/5800 ≈ 51.7%`，约 2.07 倍。讲义"Roughly 4x the ideal"在这个假设下**不成立**——LLM 往返次数是 4 比 2，工具时间是 1800 比 800，两者都只有 2 倍左右的差距。只看工具执行部分，本节代码的 `max/sum = 800/1800 ≈ 0.444`，即缩短约 55.6%，略低于讲义说的"60–70%"；倍数比随着调用数增加而变大（10 个 50 ms 的调用 `max/sum = 0.1`）。
2. 已用计时脚本实际测量：
   - 提前执行：A 在 100 ms 开始、耗时 800 → 900；B 在 200 开始、600 → 800；C 在 300 开始、400 → 700。端到端 `max = 900 ms`（实测 902 ms）。
   - 等整条流：300 ms 时才全部开始，`300 + max(800, 600, 400) = 1100 ms`（实测 1102 ms）。
   - 省了 200 ms。规律：最慢的调用越早完成参数流，提前执行的收益越大；如果最慢的调用恰好最后完成参数流，两种方式一样快（原始延迟 400/600/800 时即如此）。

### Q12 — 参考答案

```python
def schedule(calls, deps):
    """calls: {id: tool_name}; deps: {id: set(依赖的 id)} -> 波次列表"""
    remaining, done, waves = dict(calls), set(), []
    while remaining:
        wave = [cid for cid in remaining if deps.get(cid, set()) <= done]
        if not wave:
            raise ValueError(f"cycle among {sorted(remaining)}")
        waves.append(wave)
        for cid in wave:
            done.add(cid)
            remaining.pop(cid)
    return waves
```

本例 `schedule({"c1": "create_file", "c2": "write_file", "c3": "get_weather", "c4": "get_weather"}, {"c2": {"c1"}})` 输出 `[['c1', 'c3', 'c4'], ['c2']]`；互相依赖的 `{"a": {"b"}, "b": {"a"}}` 抛出 `cycle among ['a', 'b']`（均已运行）。这就是按拓扑排序分层（Kahn 算法的分层版本）。`deps.get(cid, set()) <= done` 用集合的子集运算判断"所有依赖都已完成"。

延伸：依赖关系从哪里来？可以在注册表上声明（`ordering_deps`，见本节 `outputs/` 里的 skill），也可以按资源推断（同一 `path` 上的写操作互相串行）。

### Q13 — 参考回答要点

- 定义：模型在一条 assistant 消息中发出多个工具调用；宿主并发执行，再把所有结果（各带 id）一起回填。
- 节省：① **LLM 往返次数**（N 个调用从 N 轮变 1 轮）；② **工具执行时间**（从 sum 变 max）。
- 不应并行：有顺序或数据依赖；对同一资源的写操作（竞态）；下游限流/配额扛不住扇出；需要人工逐个确认的高风险操作。
- 开关：OpenAI `parallel_tool_calls: false`、Anthropic `disable_parallel_tool_use: true`。
- 加分点：即使 provider 层开了并行，宿主仍可以按依赖图或资源锁"降级"为部分串行执行。

### Q14 — 参考回答要点

- 方案：每个调用一个缓冲区（OpenAI 以 `index` 为键，Anthropic 以 content block 的 index/id 为键，Gemini 3 以 `functionCallId` 为键）；首片记录 id 和 name；后续分片追加参数字符串；收到该调用（或整条消息）的结束信号后再 `json.loads`；解析失败按错误结果回填。
- 判断完整：依赖 provider 的结束信号（`content_block_stop`、`finish_reason`）；需要更早感知时用增量 JSON 解析器（能识别字符串、转义、嵌套）。
- 不能数括号：字符串值里的 `{`、`}` 和转义字符会让计数失真（见 Q5），既可能误判完整，也可能误判不完整。
- 加分点：给累加器加状态机防止重复执行；处理 `finish_reason: "length"` 截断；UI 上可以用增量解析把"正在填写的参数"实时显示给用户。

### Q15 — 参考回答要点

- 问题：瞬时 10 个请求超过 5 QPS，触发 429，部分调用失败；若每个都立即重试，会形成重试风暴。
- 设计：
  1. **按下游分组的并发/速率限制**（讲义 skill 中的 `rate_limit_group`）：同一组共享一个信号量或令牌桶，而不是按工具单独限流。
  2. **排队 + 退避重试**：指数退避加随机抖动（jitter），尊重 `Retry-After`。
  3. **部分失败回填**：成功的正常返回，失败的作为错误结果带 id 回填，让模型决定是否重试。
  4. **预算与超时**：每个调用设超时，整轮设总超时。
  5. 必要时提示模型减少扇出（description 中说明"一次最多查询 N 个"），或提供批量接口工具（一个调用查多个城市）。
- 讲义："A 10-way fan-out to a rate-limited service will fail"；网关层背压见第 17 节。

### Q16 — 参考回答要点

- 数据结构：注册表中每个工具带 `parallel_safe`、`ordering_deps`、`rate_limit_group`、`resource_key(args)`（例如 `write_file` 取 `path`）；调度时构建本轮调用的依赖图。
- 规则：
  1. 默认拒绝（default-deny）：未分类的工具视为不可并行（讲义 skill 的 hard reject 规则）。
  2. 只读调用可以并行；对同一 `resource_key` 的写操作串行；跨资源写操作视情况并行。
  3. 有显式依赖的调用按拓扑分层（见 Q12），同层内并行。
  4. 每个 `rate_limit_group` 一个信号量。
  5. consequential 工具先过确认关卡，未确认的不进入调度。
  6. 每个结果带 id，按完成顺序回填；全部结束（或超时）后再调用模型。
- 加分点：调度器本身要可观测（每个调用的排队时间、执行时间、重试次数），便于定位"并行反而更慢"的问题。

### Q17 — 参考回答要点

- 失败或超时的调用：不要丢弃，回填一条带相同 id 的错误结果（Anthropic 可设 `is_error: true`），内容写清楚原因（超时、429、参数错误）。OpenAI/Anthropic 都要求**每个调用都有对应结果**，缺一个会导致下一次请求格式错误。
- 是否等待全部：回填给模型通常要等本轮所有调用都有结果（成功、失败或超时）；但可以给每个调用设超时，避免被一个慢调用拖住整轮。
- 顺序：讲义说 OpenAI/Anthropic 只看 id，顺序不影响正确性；但按完成顺序记录、并在日志中带 id，便于排查丢失或重复的结果。Anthropic 需要把所有 `tool_result` 放进同一条 user 消息。
- 常见误区：用调用列表下标而不是 id 关联结果；超时后不回填导致下一轮请求被拒。

---

## 六、关联知识点

### 前置知识
- [阶段 13 · 01 工具接口：为什么 Agents 需要结构化输入输出](../../01-the-tool-interface/docs/zh.md)：tool call 的 `id` 字段从这里引入。
- [阶段 13 · 02 深入理解 Function Calling：OpenAI、Anthropic、Gemini](../../02-function-calling-deep-dive/docs/zh.md)：三家的调用与结果回填形状。
- [阶段 11 · 09 Function Calling 与工具使用](../../../11-llm-engineering/09-function-calling/docs/zh.md)：基础 API 用法。

### 本节被哪些后续内容用到
- [阶段 13 · 04 Structured Output：JSON Schema、Pydantic、Zod 与约束解码](../../04-structured-output/docs/zh.md)：流式 JSON 的完整性与校验。
- [阶段 13 · 17 Stateless MCP 网关与注册表准入](../../17-mcp-gateways-and-registries/docs/zh.md)：讲义提到网关层的背压。
- [阶段 13 · 29 MCP 可靠性、取消与流量控制](../../29-mcp-reliability-cancellation-and-flow-control/docs/zh.md)：取消、超时与流控。
- [阶段 13 · 20 OpenTelemetry GenAI：端到端追踪 Tool Calls](../../20-opentelemetry-genai/docs/zh.md)：追踪并行调用的耗时。
- [阶段 14 · 02 ReWOO 与 Plan-and-Execute：解耦 Planning](../../../14-agent-engineering/02-rewoo-plan-and-execute/docs/zh.md)：先规划依赖图再并行执行。
- [阶段 17 · 08 Inference 指标：TTFT、TPOT、ITL、Goodput、P99](../../../17-infrastructure-and-production/08-inference-metrics-goodput/docs/zh.md)：理解流式延迟指标。

### 延伸关键词
`parallel_tool_calls` · `disable_parallel_tool_use` · `tool_call_id` · `fan-out / fan-in` · `ThreadPoolExecutor` · `asyncio.gather` · `as_completed` · `GIL` · `input_json_delta` · `incremental JSON parser` · `topological sort` · `rate limiting / backpressure`
