# 代码讲解 · main.py

> **所属小节**：阶段 13 · 工具与协议 · 第 03 节 并行 Tool Calls 与工具调用中的 Streaming ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（约 3.4 秒，其中 sleep 占大头） ｜ **依赖**：仅标准库（`json`、`time`、`concurrent.futures`、`dataclasses`），无 LLM、无网络

---

## 1. 这份代码在考察什么

并行工具调用的收益与难点分成两半，代码也分成两个 demo：

1. **demo 1 · 并行执行的收益**：三个城市的天气查询分别用 400/600/800 ms 的 `time.sleep` 模拟，串行 vs 线程池并行，验证"串行 = sum，并行 = max"。
2. **demo 2 · 流式参数重组**：回放一条"三个调用交错"的假流，用 `StreamAccumulator` 按 id 累加 `arguments` 分片，只在 `call_stop` 后解析 JSON，并**立即**把该调用提交到线程池执行（不等整条流结束）。

对应讲义的核心概念：id 关联、乱序完成、按调用分桶的累加器、parse-early 陷阱、流式提前执行。

> 一句话：**并行省时间，流式省等待，id 把一切串起来**——但本节的假流和累加器都是"理想情况"，真实 provider 的流形状和异常情况需要你自己补上。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `SIMULATED_LATENCY_MS` | 常量 dict | 每个城市的模拟延迟 | 工具执行延迟 |
| `executor_weather` | 函数 | `sleep` 后返回假温度 | I/O 型工具执行器 |
| `run_sequential` | 函数 | 列表推导式逐个执行并计时 | 串行（sum） |
| `run_parallel` | 函数 | `ThreadPoolExecutor.map` 并发执行并计时 | 并行（max） |
| `CallBuffer` | dataclass | 单个调用的 id / name / 参数缓冲 / done 标志 | 每个调用一个累加器 |
| `StreamAccumulator` | dataclass | 按 id 管理多个 `CallBuffer`，处理三类事件 | 流式参数重组 |
| `fake_openai_stream` | 生成器 | 产出 13 个交错事件 | 模拟的流 |
| `replay_and_execute` | 函数 | 边读流边执行已完整的调用，最后收集结果 | 流式提前执行 |
| `main` | 函数 | 打印理论值、实测值、加速比，再跑 demo 2 | 演示 |

数据流：demo 1：`cities` → `run_sequential` / `run_parallel` → 耗时；demo 2：`fake_openai_stream()` → `acc.on_event` → 完整的 `CallBuffer` → `try_parse` → `pool.submit(executor_weather)` → `fut.result()` → 按 id 汇总。

---

## 3. 逐段精讲

### 3.1 模拟执行器

```python
SIMULATED_LATENCY_MS = {"Bengaluru": 400, "Tokyo": 600, "Zurich": 800}

def executor_weather(city: str) -> dict:
    latency = SIMULATED_LATENCY_MS.get(city, 500)
    time.sleep(latency / 1000.0)
    return {"city": city, "temp_c": hash(city) % 35}
```

- `time.sleep` 模拟网络 I/O。sleep 期间线程会**释放 GIL**，其他线程可以运行——这是线程池能加速的前提。若换成 CPU 密集计算，线程池几乎没有收益。
- ⚠️ `hash(city) % 35`：Python 对字符串的 `hash` 每个进程随机化（`PYTHONHASHSEED`），所以温度每次运行都不同。我们连续运行三次，`hash('Tokyo') % 35` 分别得到 4、16、21。用作"假数据"无妨，但不要以为输出可复现；想要固定值可以用 `zlib.crc32(city.encode()) % 35`。
- 未知城市默认 500 ms。

### 3.2 串行 vs 并行

```python
def run_sequential(cities: list[str]) -> tuple[float, list[dict]]:
    start = time.perf_counter()
    results = [executor_weather(c) for c in cities]
    dt_ms = (time.perf_counter() - start) * 1000
    return dt_ms, results

def run_parallel(cities: list[str]) -> tuple[float, list[dict]]:
    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=len(cities)) as pool:
        results = list(pool.map(executor_weather, cities))
    dt_ms = (time.perf_counter() - start) * 1000
    return dt_ms, results
```

- `pool.map` 把每个城市提交为一个任务，**返回结果的顺序与输入顺序一致**（不是完成顺序）；它返回的是惰性迭代器，`list(...)` 会等全部完成。
- `with` 块退出时会调用 `pool.shutdown(wait=True)`，确保线程都已结束。
- `max_workers=len(cities)`：每个调用一个线程，三个 sleep 完全重叠，总耗时 ≈ 800 ms。
- ⚠️ 空列表时 `ThreadPoolExecutor(max_workers=0)` 会抛 `ValueError: max_workers must be greater than 0`（已实测）；生产中要特判空调用列表，并给 `max_workers` 设上限（例如 `min(len(cities), 8)`），避免模型一次发出 50 个调用就开 50 个线程。
- 注意 demo 1 只模拟了"工具执行"的并行收益，没有模拟讲义开头强调的**LLM 往返次数**的减少（串行 4 轮 vs 并行 2 轮），后者在真实场景里往往更重要（测验 Q11 有手算）。

### 3.3 `CallBuffer`：一个调用一个缓冲区

```python
@dataclass
class CallBuffer:
    id: str
    name: str = ""
    args_buf: str = ""
    done: bool = False

    def try_parse(self) -> dict | None:
        if not self.done:
            return None
        return json.loads(self.args_buf)
```

- `args_buf` 用字符串拼接累积参数片段；`done` 由 `call_stop` 置为 True。
- `try_parse` 体现了讲义的 **parse-early 防护**：未完成时直接返回 `None`，不去尝试解析半截 JSON。
- ⚠️ 但完成后的解析没有错误处理：如果 stop 时参数仍不完整（例如流被截断），`json.loads` 抛 `JSONDecodeError`。实测：缓冲区为 `{"city": "Beng` 时 stop → `Unterminated string starting at: line 1 column 10`。

### 3.4 `StreamAccumulator`：按 id 分桶

```python
@dataclass
class StreamAccumulator:
    buffers: dict[str, CallBuffer] = field(default_factory=dict)

    def on_event(self, event: dict) -> list[CallBuffer]:
        kind = event["type"]
        idx = event.get("id")
        completed: list[CallBuffer] = []
        if kind == "call_start":
            self.buffers[idx] = CallBuffer(id=idx, name=event["name"])
        elif kind == "args_delta":
            buf = self.buffers[idx]
            buf.args_buf += event["chunk"]
        elif kind == "call_stop":
            buf = self.buffers[idx]
            buf.done = True
            completed.append(buf)
        return completed
```

- 三种事件：`call_start` 建缓冲区并记录 name；`args_delta` 追加片段；`call_stop` 标记完成并返回该缓冲区，让调用方可以**立即**执行。
- `field(default_factory=dict)`：可变默认值必须用工厂函数，否则所有实例会共享同一个 dict（dataclass 会直接报错阻止你写 `= {}`）。
- 返回 `list` 而不是单个对象，是为了以后一次事件可能完成多个调用（例如 OpenAI 的整体 `finish_reason`）时接口不变。
- 变量名 `idx` 实际存的是 id 字符串，命名有些误导（真实 OpenAI 流才需要按 index 分桶）。
- ⚠️ 缺少防御（实测）：

| 异常情况 | 实际行为 |
|---------|---------|
| 对未 start 的 id 发 `args_delta` | `KeyError`，整个流处理崩溃 |
| 同一 id 两次 `call_stop` | 两次都返回该缓冲区 → `replay_and_execute` 会**提交两次执行** |
| 同一 id 两次 `call_start` | 静默覆盖，已收到的片段丢失 |
| 未知事件类型 | 静默忽略 |
| 中途取消 | 没有对应事件（讲义练习 2） |

  测验 Q9 给出了带状态机（open/done/cancelled）和错误事件的改写版本。

### 3.5 `fake_openai_stream`：交错的事件流

```python
def fake_openai_stream():
    """Three interleaved parallel calls. Real streams look like this."""
    yield {"type": "call_start", "id": "call_A", "name": "get_weather"}
    yield {"type": "call_start", "id": "call_B", "name": "get_weather"}
    yield {"type": "call_start", "id": "call_C", "name": "get_weather"}
    yield {"type": "args_delta", "id": "call_A", "chunk": '{"city"'}
    yield {"type": "args_delta", "id": "call_B", "chunk": '{"city'}
    yield {"type": "args_delta", "id": "call_A", "chunk": ':"Beng'}
    yield {"type": "args_delta", "id": "call_C", "chunk": '{"city":"Zu'}
    yield {"type": "args_delta", "id": "call_A", "chunk": 'aluru"}'}
    yield {"type": "call_stop", "id": "call_A"}
    ...
```

- 用 `yield` 写成**生成器**：每次 `for` 循环取一个事件，模拟网络上逐个到达的分片。
- 分片故意切在奇怪的位置（`'{"city'`、`':"Beng'`），说明任何一个片段单独都不是合法 JSON。
- ⚠️ docstring 说 "Real streams look like this"，函数名也叫 `fake_openai_stream`，但这**不是** OpenAI 的真实形状：
  - 真实 OpenAI Chat Completions 流按 `delta.tool_calls[i].index` 区分调用，`id` 和 `name` 只在首片出现；
  - 真实 OpenAI 流没有逐个调用的 start/stop 事件，只有整体的 `finish_reason: "tool_calls"`；
  - 这里的 start/delta/stop 三段式更接近 Anthropic 的 `content_block_start / content_block_delta (input_json_delta) / content_block_stop`。
  讲义本身对 OpenAI 的描述（"accumulate per-index, read id when it first appears"）是对的，只是代码的假流没有照此实现。测验 Q10 给出了处理真实 OpenAI 形状的 `accumulate_openai`。

### 3.6 `replay_and_execute`：流式提前执行

```python
def replay_and_execute() -> dict[str, dict]:
    acc = StreamAccumulator()
    results: dict[str, dict] = {}
    in_flight: dict[str, "Future"] = {}  # type: ignore
    with ThreadPoolExecutor(max_workers=4) as pool:
        for event in fake_openai_stream():
            completed = acc.on_event(event)
            for buf in completed:
                args = buf.try_parse()
                print(f"  call {buf.id} args complete -> {args}")
                in_flight[buf.id] = pool.submit(executor_weather, args["city"])
        for cid, fut in in_flight.items():
            results[cid] = fut.result()
    return results
```

- **提前执行**：某个调用一 stop 就 `pool.submit`，返回 `Future`，不阻塞读流——讲义"Streaming fan-out wall-clock"一节说的优化。
- `fut.result()` 会阻塞直到该任务完成，并把执行器中的异常重新抛出。
- `"Future"` 写成字符串注解且没有导入 `Future`，靠 `# type: ignore` 压掉类型检查警告。局部变量的注解在运行时不会被求值，所以不会报 `NameError`；更规范的写法是 `from concurrent.futures import Future`。
- ⚠️ 结果按 `in_flight` 的**插入顺序**（即 stop 顺序 A、B、C）收集，不是完成顺序。讲义建议"Prefer to reply in completion order with explicit ids"，要做到这一点需要 `concurrent.futures.as_completed`。我们实测把 C、A、B（800/400/600 ms）提交后用 `as_completed`，得到的顺序是 A、B、C（按完成先后）。
- ⚠️ 在这个演示里"提前执行"看不出收益：假流瞬间就读完了，三个任务几乎同时提交，`replay_and_execute` 实测 802 ms，与"等全部再执行"一样。要看到收益，流本身必须有耗时。我们给每个 `call_stop` 前加 100 ms 停顿、并把延迟改为 800/600/400 时，提前执行实测 902 ms，等全部再执行实测 1102 ms（测验 Q11）。
- `max_workers=4` 是写死的；同 3.2，生产中应结合下游限流设置。

### 3.7 `main`：理论值 vs 实测值

```python
    sum_lat = sum(SIMULATED_LATENCY_MS.values())
    max_lat = max(SIMULATED_LATENCY_MS.values())
    ...
    speedup = seq_ms / par_ms if par_ms else 0
    print(f"speedup           : {speedup:.2f}x")
```

- 先打印理论值（sum = 1800、max = 800），再打印实测值，便于对照。
- `seq_ms / par_ms if par_ms else 0`：条件表达式防止除以零。
- `{seq_ms:.0f}` 四舍五入到整数毫秒；`{speedup:.2f}` 保留两位小数。
- `seq_res` 和 `par_res` 被计算出来但没有使用（也没有检查两者是否一致）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| `time.sleep` 模拟 I/O | 延迟可控、结果稳定 | 真实工具有抖动、超时、失败；需要超时与重试 |
| 线程池而非 asyncio | 标准库、改动最小，sleep 释放 GIL | 讲义练习 3：真实 I/O 下 asyncio 上下文切换更轻；CPU 密集任务应改用进程池 |
| `max_workers=len(cities)` | 完全重叠 | 空列表报错；调用数大时线程爆炸、打爆下游限流；应设上限并按下游分组限流 |
| 自定义 start/delta/stop 事件 | 讲清"按调用分桶"的思想 | 与真实 OpenAI 形状不同；需要每家一个适配器 |
| 按 id 用 dict 分桶 | O(1) 查找，天然支持交错 | 未知 id、重复 stop、取消都没处理 |
| 只在 stop 后解析 | 避开 parse-early 陷阱 | stop 时仍可能不完整（截断），需要错误分支 |
| stop 后立即 submit | 流式提前执行 | 本演示中流是瞬时的，看不出收益 |
| 按插入顺序收集结果 | 简单 | 讲义建议按完成顺序回复；用 `as_completed` |
| `hash(city) % 35` 做假温度 | 不用写查表 | 每次运行不同，不可复现 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `ThreadPoolExecutor` + `with` | `with ThreadPoolExecutor(max_workers=...) as pool:` | 线程池；退出 `with` 时自动等待所有任务并关闭 |
| `pool.map` | `list(pool.map(executor_weather, cities))` | 并发执行，结果顺序与输入一致 |
| `pool.submit` / `Future` | `in_flight[buf.id] = pool.submit(executor_weather, args["city"])` | 提交单个任务，立即返回 `Future` |
| `Future.result()` | `results[cid] = fut.result()` | 阻塞等待结果，执行器的异常在这里重新抛出 |
| `as_completed`（扩展） | 测验与本文 3.6 中使用 | 按完成顺序迭代 Future |
| 生成器函数 | `def fake_openai_stream(): yield {...}` | 惰性地逐个产出值，适合模拟流 |
| `@dataclass` + `field(default_factory=dict)` | `buffers: dict[str, CallBuffer] = field(default_factory=dict)` | 可变默认值必须用工厂函数 |
| dataclass 中的方法 | `def try_parse(self) -> dict \| None` | dataclass 也可以定义普通方法 |
| 返回元组 + 类型注解 | `-> tuple[float, list[dict]]`；`seq_ms, seq_res = run_sequential(cities)` | 一次返回多个值并解包 |
| 字符串注解 | `in_flight: dict[str, "Future"]` | 前向引用；局部变量注解运行时不求值 |
| `# type: ignore` | 同上一行 | 让类型检查器忽略这一行 |
| 字符串原地拼接 | `buf.args_buf += event["chunk"]` | 累加片段（大量片段时可改用 list 再 `"".join`） |
| `time.perf_counter()` | 计时 | 高精度单调时钟 |
| `dict.values()` + `sum` / `max` | `sum(SIMULATED_LATENCY_MS.values())` | 对字典的值求和、求最大 |
| 条件表达式防除零 | `seq_ms / par_ms if par_ms else 0` | 三元表达式 |
| f-string 格式符 | `{seq_ms:.0f}`、`{speedup:.2f}x` | 控制小数位 |
| `hash()` | `hash(city) % 35` | 字符串哈希每个进程随机化 |
| 嵌套 `for` + 提前处理 | `for event in ...: for buf in completed:` | 边读流边处理已完成的调用 |

---

## 6. 运行结果解读

实际运行（`cd code && python3 main.py`，总耗时约 3.4 秒）：

```text
--- demo 1: three-city weather (simulated) ---
per-city simulated latency : {'Bengaluru': 400, 'Tokyo': 600, 'Zurich': 800}
theoretical sequential     : 1800 ms  (sum)
theoretical parallel       : 800 ms  (max)

actual sequential : 1800 ms
actual parallel   : 802 ms
speedup           : 2.25x

--- demo 2: stream accumulator ---
replaying fake interleaved stream of three parallel calls ...
  call call_A args complete -> {'city': 'Bengaluru'}
  call call_B args complete -> {'city': 'Tokyo'}
  call call_C args complete -> {'city': 'Zurich'}

final results (keyed by tool_call_id):
  call_A -> {'city': 'Bengaluru', 'temp_c': 23}
  call_B -> {'city': 'Tokyo', 'temp_c': 25}
  call_C -> {'city': 'Zurich', 'temp_c': 11}
```

逐项解读：

- **sequential 1800 ms**：三个 sleep 依次执行，正好是总和。
- **parallel 802 ms**：最慢的 Zurich 决定总时间，多出约 2 ms 是线程创建与调度开销（讲义练习 1 说的"real runs deviate slightly"）。
- **speedup 2.25x**：`1800 / 800 = 2.25`，即 wall-clock 缩短约 55.6%；讲义说生产基准"减少 60%–70%"，那包含了 LLM 往返次数的节省，本 demo 只测了执行器部分。
- **demo 2 的三行 "args complete"**：顺序是 A、B、C，对应流中 `call_stop` 的顺序；尽管三个调用的片段交错到达，每个都被正确拼回 `{"city": "..."}`。
- **final results**：按 id 汇总；`temp_c` 来自 `hash`，每次运行数值都会变（上面是某一次的结果）。
- 结果字典的顺序是提交顺序；本例中提交顺序恰好也是完成顺序（400 < 600 < 800），所以看不出差别。

---

## 7. 动手改一改

1. **讲义练习 1**：把延迟改成 `[100, 100, 1000]`、`[300, 300, 300]`，观察 `par/seq ≈ max/sum`（分别约 0.833、0.333）。思考：延迟分布越"偏"（一个特别慢），并行收益越小。
2. **讲义练习 2**：给累加器加 `call_cancel` 事件和状态机，处理未知 id、重复 stop、stop 时 JSON 不完整（参考测验 Q9），确保同一调用绝不会被执行两次。
3. **讲义练习 3**：用 `asyncio.sleep` + `asyncio.gather` 重写 demo 1，比较与线程池的耗时；再把执行器改成 CPU 密集的循环，观察线程池失去加速、进程池恢复加速。
4. **真实形状适配**：写 `accumulate_openai`（按 `index` 分桶、首片取 `id`、`finish_reason` 收尾）和一个 Anthropic 事件适配器，把两者都转换成本节的 start/delta/stop 事件再喂给 `StreamAccumulator`。
5. **按完成顺序回复**：在 `replay_and_execute` 中改用 `as_completed`，按完成顺序打印 `{"role": "tool", "tool_call_id": ..., "content": ...}`。
6. **讲义练习 4**：给注册表加 `ordering_deps`，实现按拓扑分层的调度器（参考测验 Q12），让 `create_file → write_file` 串行、其余并行。

---

## 8. 常见坑

- **流还没结束就 `json.loads`**：半截 JSON 必然报错；以 provider 的结束信号为准。
- **数括号判断完整**：字符串值里的 `{}` 会造成误判。
- **按列表下标而不是 id 关联结果**：并行结果乱序时会张冠李戴；Gemini 2 时代按 name 匹配同名调用就踩过这个坑。
- **重复执行**：重复的 stop 事件或重试逻辑让同一个有副作用的调用执行两次。
- **把 `pool.map` 的顺序当成完成顺序**：`map` 保持输入顺序，想按完成顺序要用 `as_completed`。
- **以为线程能加速一切**：GIL 下只有 I/O 等待能重叠。
- **无上限的扇出**：`max_workers=len(calls)` 在调用数大时会打爆下游限流。
- **漏回某个调用的结果**：超时或失败也要带 id 回填，否则下一轮请求会被 provider 拒绝。
- **把假流当成真实格式**：真实 OpenAI 流按 `index` 区分、只有整体结束信号。
