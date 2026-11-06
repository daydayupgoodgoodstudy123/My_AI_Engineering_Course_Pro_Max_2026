# 代码讲解 · main.py

> **所属小节**：阶段 15 · 自主系统 · 第 12 节 长时间运行的后台 Agents：Durable Execution ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`functools`、`json`、`os`、`tempfile`、`dataclasses`）；运行时会在系统临时目录下创建 `naive.json`、`durable.json` 两个事件日志文件，且不会自动删除

---

## 1. 这份代码在考察什么

这是一个**最小的 durable execution（持久化执行）引擎**，用不到 100 行标准库代码复刻 Temporal、LangGraph checkpointer 等系统的核心模式：

1. **workflow / activity 二分**：`workflow()` 是确定性的编排代码；`fetch_docs`、`call_llm`、`write_report` 是 activity——讲义所说的"非确定、可能失败、可能有副作用"的工作单元（LLM 调用、工具调用、写文件）。
2. **event log（事件日志）**：每个 activity 执行前写一条 `started`，执行后写一条 `done`（带结果），日志存成 JSON 文件，进程崩溃后仍在。
3. **replay（重放）**：恢复时把 workflow 从头再跑一遍，已完成的 activity 直接从日志返回结果、不再真正执行；只有没完成的 activity 才会真跑。
4. **对比实验**：同一个 3 步 workflow 在第 2 步后"崩溃"，比较"朴素重试"（日志丢失，全部重跑）与"持久化重试"（日志保留，只跑缺失那一步）的 activity 执行次数：5 次 vs 3 次。

> 一句话：**把"崩溃后从头再来"变成"崩溃后从断点继续"，靠的是"确定性的编排 + 记录了输入输出的非确定步骤"。** 同时也要看清这个玩具引擎在哪些地方比真实引擎简化了——尤其是"按名字+参数查缓存"而不是"按事件顺序重放"。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `EventLog` | dataclass | JSON 文件做后端：`events()` 读全部、`append()` 追加一条、`lookup()` 找已完成的同名同参事件 | event log / checkpoint 后端 |
| `activity(name)` | 装饰器工厂 | 把普通函数包装成"先查日志、命中则重放、否则记录 started → 执行 → 记录 done" | activity 包装 |
| `fetch_docs` / `call_llm` / `write_report` | 被装饰的函数 | 三个示例 activity：取文档、调 LLM、写报告（有副作用） | 非确定性工作单元 |
| `workflow(log, query, crash_after)` | 函数 | 按顺序调用三个 activity，可在第 1 或第 2 步后抛异常模拟崩溃 | workflow（确定性编排） |
| `reset_log(path)` | 函数 | 删掉旧日志文件并新建空日志 | 朴素重试时"丢失状态" |
| `count_runs(log)` | 函数 | 统计 `started` 事件数，即 activity 真正开始执行的次数 | 成本度量 |
| `main()` | 函数 | 两组实验：朴素重试、持久化重试，各最多 3 次尝试 | 演示驱动 |

数据流：`workflow` 调用被装饰的 activity → `wrapper` 调 `log.lookup` → 命中则返回日志结果（replay），未命中则 `append(started)` → 执行原函数 → `append(done, result)` → 返回结果 → `workflow` 继续下一步或抛出模拟崩溃 → `main` 捕获异常并重试。

---

## 3. 逐段精讲

### 3.1 `EventLog`：用 JSON 文件当持久化后端

```python
@dataclass
class EventLog:
    path: str

    def __post_init__(self) -> None:
        if not os.path.exists(self.path):
            with open(self.path, "w") as f:
                json.dump([], f)

    def events(self) -> list[dict]:
        with open(self.path) as f:
            return json.load(f)

    def append(self, ev: dict) -> None:
        evs = self.events()
        evs.append(ev)
        with open(self.path, "w") as f:
            json.dump(evs, f)
```

- `@dataclass` 自动生成 `__init__(self, path)`；`__post_init__` 在其后运行：文件不存在就写入一个空列表 `[]`。所以 `EventLog(path)` 对已有文件是"打开"，对新路径是"创建"——这正是持久化重试能接上上一次日志的关键。
- **状态全部在文件里，不在对象里**：每次 `events()` 都重新读盘。即使 Python 对象随进程一起消失，下一次 `EventLog(同一路径)` 也能看到完整历史。这就是讲义说的"durable backing store"。
- ⚠️ `append` 是"读全部 → 加一条 → 整个文件重写"：
  - 复杂度是 O(n²)（n 条事件需要重写 n 次）；
  - **不是原子操作**：若进程恰好在 `json.dump` 写到一半时崩溃，文件会变成半截 JSON，下次 `json.load` 直接报错，持久化反而成了单点故障；
  - 没有 `fsync`，操作系统缓存里的数据在断电时可能丢失。
  - 真实系统用追加写（append-only）的数据库或日志，配合事务；讲义提到的后端是 PostgreSQL（LangGraph 默认）、SQLite（仅开发）、Redis（需开 AOF/快照）、Cloudflare Durable Objects。

```python
    def lookup(self, name: str, args: tuple) -> dict | None:
        for ev in self.events():
            if ev["name"] == name and ev["args"] == list(args) and ev["status"] == "done":
                return ev
        return None
```

- 查找条件：**名字相同、参数相同、状态为 done**。参数用 `list(args)` 比较，因为 JSON 没有元组，`json.dump` 会把元组存成列表。
- ⚠️ 这是**记忆化（memoization）**而不是严格意义的**重放（replay）**。Temporal 之类的引擎是按**事件顺序**重放：workflow 第 k 次发出的命令必须与历史中第 k 条记录对应，不对应就报 non-determinism 错误。这里只按"名字+参数"查表，带来三个后果（均已实际运行验证，见测验 Q9）：
  1. 同一个 activity 用相同参数**故意调用两次**（比如对 LLM 采样两次），第二次会直接返回第一次的结果，真正只执行了 1 次；
  2. 如果参数里有元组，存进 JSON 后变成列表，`ev["args"] == list(args)` 比较的是 `[[1, 2]]` 与 `[(1, 2)]`，**永远不相等**——这个 activity 永远不会被重放；
  3. workflow 因非确定性走了另一条分支时，这里不会报错，只会"缓存未命中、默默执行新的 activity"。

### 3.2 `activity` 装饰器：先查日志，再决定跑不跑

```python
def activity(name: str):
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(log: EventLog, *args):
            hit = log.lookup(name, args)
            if hit:
                print(f"    [replay] {name}({args}) -> {hit['result']} (from log)")
                return hit["result"]
            log.append({"name": name, "args": list(args), "status": "started"})
            result = fn(*args)
            log.append({"name": name, "args": list(args),
                        "status": "done", "result": result})
            print(f"    [run]    {name}({args}) -> {result}")
            return result
        return wrapper
    return deco
```

- 三层嵌套：`activity("fetch_docs")` 返回装饰器 `deco`；`deco(fn)` 返回 `wrapper`；调用 `fetch_docs(log, "hello")` 实际执行的是 `wrapper`。
- **调用约定被改变了**：原函数 `fetch_docs(query)` 只有一个参数，包装后要写成 `fetch_docs(log, query)`——日志作为第一个参数显式传入。`*args` 收集其余位置参数，原样转给 `fn(*args)`。注意 `wrapper` 不接受关键字参数，`fetch_docs(log, query="hello")` 会报 `TypeError`。
- **先写 `started`，再执行，再写 `done`**：这是讲义 Key Terms 中 "logged before and after" 的实现。两条记录之间的窗口期就是危险区：
  - 若进程在 `fn(*args)` 执行过程中（或执行完、写 `done` 之前）崩溃，日志里只有 `started` 没有 `done`；
  - 恢复时 `lookup` 只认 `done`，于是该 activity **会被再执行一次**——这就是"至少一次（at-least-once）"语义。对发邮件、扣款这类副作用，会重复执行。
  - 所以讲义的 skill 文件要求："If the user proposes a durable workflow with no explicit idempotency on side-effect activities, refuse and require idempotency keys first. Retries will double-execute otherwise."
- 本代码的崩溃点只在 activity **之间**（`crash_after` 在 activity 返回后才抛异常），所以演示里看不到这个问题；测验 Q10 会让你构造它。
- `@functools.wraps(fn)` 把原函数的 `__name__`、`__doc__` 等复制到 `wrapper` 上，便于调试。
- ⚠️ 重放返回的是 **JSON 反序列化后的值**：如果原 activity 返回元组，首次执行拿到 `(1, 2)`，重放拿到 `[1, 2]`，`(1, 2) == [1, 2]` 为 `False`。workflow 若依赖返回值的类型，首次运行与重放的行为会不一致。真实引擎用显式的序列化器（payload converter）解决这一问题。

### 3.3 三个示例 activity

```python
@activity("fetch_docs")
def fetch_docs(query: str) -> int:
    return len(query) * 3

@activity("call_llm")
def call_llm(doc_count: int) -> str:
    # Pretend LLM call; deterministic here for pedagogy.
    return f"summary({doc_count}_docs)"

@activity("write_report")
def write_report(summary: str) -> str:
    return f"report://{summary}"
```

- `fetch_docs("hello")` 返回 `5 × 3 = 15`；`call_llm(15)` 返回 `"summary(15_docs)"`；`write_report(...)` 返回 `"report://summary(15_docs)"`。
- 注释写明 "deterministic here for pedagogy"：真实 LLM 调用是非确定的（讲义："temperature > 0; even temperature 0 drifts across model versions"）。正因为非确定，才**必须**把它放进 activity 并记录输出——重放时用记录的输出，而不是再调一次得到一个不同的回答。在这个玩具里三个 activity 都是纯函数，"重放"和"重算"结果相同，演示的只是**执行次数**的差别。

### 3.4 `workflow`：确定性编排 + 可控崩溃

```python
def workflow(log: EventLog, query: str, crash_after: int = -1) -> str:
    doc_count = fetch_docs(log, query)
    if crash_after == 1:
        raise RuntimeError("simulated crash after fetch_docs")
    summary = call_llm(log, doc_count)
    if crash_after == 2:
        raise RuntimeError("simulated crash after call_llm")
    report = write_report(log, summary)
    return report
```

- workflow 本身只做"按顺序调用、把上一步结果传给下一步"，没有读时钟、随机数或外部状态——这就是讲义要求的 **determinism**：同样的输入 + 同样的 activity 结果 → 同样的执行路径。
- `crash_after` 用 `raise RuntimeError` 模拟崩溃。真实崩溃是整个进程消失；这里是异常向上传播到 `main` 的 `except`。效果相同：内存里的局部变量全部丢失，只剩日志。
- 讲义练习 3 要求在 workflow 里引入挂钟时间，观察重放时的分歧：比如 `kind = "morning" if hour < 12 else "evening"`，崩溃前后 `hour` 不同就会走不同分支。在本引擎里，这表现为"缓存未命中 → 又执行了一次新的副作用 activity"，并不会报错（实测见测验 Q11）。

### 3.5 `main`：两组对照实验

```python
    for attempt in range(1, 4):
        log = reset_log(os.path.join(tmpdir, "naive.json"))
        ...
            crash = 2 if attempt == 1 else -1
            r = workflow(log, "hello", crash_after=crash)
            ...
            break
        except RuntimeError as e:
            print(f"    -> crash: {e}; {count_runs(log)} activity starts wasted")
```

- **朴素重试**：每次尝试都 `reset_log`，相当于"状态只在内存里，崩溃就没了"。第 1 次在第 2 步后崩溃（浪费 2 次 activity），第 2 次从头跑完 3 步。合计 5 次 activity 执行。
- 只有第 1 次尝试会崩溃（`2 if attempt == 1 else -1`），成功后 `break`，所以 `range(1, 4)` 的第 3 次不会发生。

```python
    durable_path = os.path.join(tmpdir, "durable.json")
    ...
    for attempt in range(1, 4):
        log = EventLog(durable_path)
```

- **持久化重试**：每次尝试都用**同一个文件**新建 `EventLog`，`__post_init__` 发现文件已存在就不覆盖。第 2 次尝试时 `fetch_docs` 和 `call_llm` 命中日志直接重放，只有 `write_report` 真正执行。`count_runs` 统计整个日志的 `started` 数：3。
- ⚠️ `tempfile.mkdtemp()` 创建的临时目录在结束后**没有删除**，每运行一次就在系统临时目录留下一个含两个 JSON 文件的目录。可以改用 `with tempfile.TemporaryDirectory() as tmpdir:`。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| JSON 文件做事件日志 | 零依赖、可直接打开查看 | 整文件重写、非原子、无 fsync、O(n²)；生产用 PostgreSQL 等事务型后端，追加写 |
| 按"名字 + 参数"查缓存 | 实现最简单，workflow 代码不需要编号 | 同参重复调用被合并、元组参数永不命中、分支漂移不报错；真实引擎按事件序号重放并检测 non-determinism |
| `started` / `done` 两条记录 | 体现"执行前后都记录" | 两条记录之间崩溃会导致重复执行；副作用 activity 必须带幂等键（idempotency key） |
| 崩溃点只在 activity 之间 | 让演示结果干净 | 掩盖了"activity 执行中崩溃"这一最危险的情形 |
| 日志作为显式参数传入 | 依赖清晰、便于测试 | 每个调用都要写 `log`；真实框架用上下文（workflow context）隐式传递，并用 `thread_id` 区分会话 |
| 没有 `thread_id` | 单会话演示 | 多个会话共用一个日志文件会相互"命中"对方的缓存（讲义练习 2） |
| 没有重试策略 / 超时 / 退避 | 聚焦重放机制 | 讲义提到 activity 包装应带"retry with exponential backoff"；生产中按 activity 配置重试次数、超时、退避 |
| activity 都是纯函数 | 输出可预测 | 无法体现"非确定 LLM 输出必须用日志值"的必要性；可以让 `call_llm` 返回随机内容来观察 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 注解延迟求值，可以写 `dict \| None` |
| `@dataclass` + `__post_init__` | `class EventLog: path: str` / `def __post_init__(self)` | dataclass 自动生成 `__init__`；`__post_init__` 在其后执行额外初始化 |
| `with open(...) as f` | `with open(self.path, "w") as f: json.dump([], f)` | 上下文管理器，离开代码块自动关闭文件 |
| `json.dump` / `json.load` | `json.dump(evs, f)`、`json.load(f)` | Python 对象 ↔ JSON 文本；元组会变成列表 |
| 联合类型返回 | `-> dict \| None` | 找不到时返回 `None` |
| 带参数的装饰器（装饰器工厂） | `def activity(name): def deco(fn): def wrapper(...)` | 三层函数：外层接收配置，中层接收被装饰函数，内层是实际执行的包装函数 |
| `@functools.wraps(fn)` | `wrapper` 上方 | 保留原函数名与文档字符串 |
| `*args` 可变位置参数 | `def wrapper(log, *args)`、`fn(*args)` | 收集任意多个位置参数成元组；调用时再展开 |
| 闭包 | `wrapper` 使用外层的 `name` 和 `fn` | 内层函数"记住"外层变量 |
| `@activity("fetch_docs")` | 三个示例函数 | 等价于 `fetch_docs = activity("fetch_docs")(fetch_docs)` |
| 默认参数 | `crash_after: int = -1` | 不传时不崩溃 |
| `raise` 自定义消息 | `raise RuntimeError("simulated crash ...")` | 主动抛出异常 |
| `try / except ... as e` | `except RuntimeError as e:` | 捕获异常并取得异常对象 |
| `for ... break` | 成功后 `break` | 提前结束重试循环 |
| 条件表达式 | `crash = 2 if attempt == 1 else -1` | 一行写出 if/else 赋值 |
| 生成器表达式 + `sum` | `sum(1 for ev in log.events() if ev["status"] == "started")` | 统计满足条件的元素个数，不建中间列表 |
| `os.path` / `os.remove` | `os.path.exists`、`os.path.join`、`os.remove` | 判断存在、拼路径、删文件 |
| `tempfile.mkdtemp()` | `tmpdir = tempfile.mkdtemp()` | 新建临时目录（需自行删除） |
| f-string 中的元组 | `f"{name}({args})"` | `args` 是元组，打印为 `('hello',)`，所以输出里有双层括号 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()` |

---

## 6. 运行结果解读

实际运行（`cd code && python3 main.py`，耗时不足 1 秒，输出确定）：

```text
Naive retry (no event log persisted)
  attempt 1:
    [run]    fetch_docs(('hello',)) -> 15
    [run]    call_llm((15,)) -> summary(15_docs)
    -> crash: simulated crash after call_llm; 2 activity starts wasted
  attempt 2:
    [run]    fetch_docs(('hello',)) -> 15                ← 重跑
    [run]    call_llm((15,)) -> summary(15_docs)         ← 重跑（LLM 再计费一次）
    [run]    write_report(('summary(15_docs)',)) -> report://summary(15_docs)
    -> result report://summary(15_docs)
    -> 3 activity starts this attempt

Durable retry (event log preserved across attempts)
  attempt 1:
    [run]    fetch_docs(('hello',)) -> 15
    [run]    call_llm((15,)) -> summary(15_docs)
    -> crash: simulated crash after call_llm
  attempt 2:
    [replay] fetch_docs(('hello',)) -> 15 (from log)     ← 从日志取
    [replay] call_llm((15,)) -> summary(15_docs) (from log)
    [run]    write_report(('summary(15_docs)',)) -> report://summary(15_docs)
    -> result report://summary(15_docs)
    -> 3 total activity starts across attempts
```

逐项解读：

- **执行次数**：朴素重试共 2 + 3 = **5** 次 activity 执行；持久化重试共 **3** 次（第 1 次尝试 2 次 + 第 2 次尝试 1 次）。节省的正是崩溃前已完成的 2 次——若其中有 LLM 调用，就是节省了重复计费；若有副作用工具，就是避免了重复副作用。
- **两种计数口径不同**：朴素组打印的是"本次尝试"的 `started` 数（日志每次被重置）；持久化组打印的是"所有尝试累计"的 `started` 数。
- **崩溃后日志的样子**：持久化组结束时 `durable.json` 的内容（实际读取）：

  ```text
  [{"name": "fetch_docs", "args": ["hello"], "status": "started"},
   {"name": "fetch_docs", "args": ["hello"], "status": "done", "result": 15},
   {"name": "call_llm", "args": [15], "status": "started"},
   {"name": "call_llm", "args": [15], "status": "done", "result": "summary(15_docs)"},
   {"name": "write_report", "args": ["summary(15_docs)"], "status": "started"},
   {"name": "write_report", "args": ["summary(15_docs)"], "status": "done", "result": "report://summary(15_docs)"}]
  ```

  注意 `args` 存成了列表，重放的两次 activity 没有新增任何事件。
- **讲义练习 1（改崩溃点）**：把第 1 次尝试的崩溃点改成 `crash_after=1`（实测）：第 2 次尝试时只有 `fetch_docs` 被重放，`call_llm` 和 `write_report` 真正执行，累计 started 仍为 3；朴素组则是 1 + 3 = 4 次。崩溃越晚，持久化节省越多。
- **讲义与代码的出入**：讲义 Use It 说代码提供 "A `run_or_replay(workflow, event_log)` function"，但代码中**没有这个函数**——重放逻辑分散在 `activity` 装饰器的 `lookup` 里，驱动逻辑在 `main` 的循环里。

---

## 7. 动手改一改

1. **（讲义练习 1）改崩溃点**：把持久化组的 `crash = 2 if ...` 改为 `1`，再改为在 `write_report` 之后崩溃（需要在 workflow 里加一个 `crash_after == 3` 分支），记录每种情况下朴素组和持久化组的总执行次数。
2. **（讲义练习 2）加入 `thread_id`**：让 `EventLog` 的路径由 `thread_id` 决定（如 `f"{tmpdir}/{thread_id}.json"`），或在每条事件里加 `thread_id` 字段并在 `lookup` 中比对。用两个线程 ID 交替运行同一个 workflow（不同 `query`），确认日志互不干扰；再故意让两个会话共用一个文件、用相同的 `query`，观察 B 会话"重放"了 A 会话的结果。
3. **（讲义练习 3）引入非确定性**：在 workflow 中用小时数决定分支（`"morning" if hour < 12 else "evening"`），让崩溃前后 hour 不同，观察同一个副作用 activity 以不同参数执行了两次；然后把读时钟包成一个 activity（相当于 Temporal 的 `workflow.now()` / side-effect 注册），确认重放时分支稳定。
4. **改成按序号重放**：给 `wrapper` 加一个调用计数器（存在 workflow 上下文里），第 k 次 activity 调用对应日志里第 k 个 `done` 事件；若名字或参数不匹配就抛出 `NonDeterminismError`。比较它与"按名字+参数查表"在练习 3 中的不同表现。
5. **幂等键**：让 `write_report` 模拟"发邮件"，在 `fn(*args)` 之后、写 `done` 之前抛异常，观察恢复后邮件发了两次；再给 activity 加一个由 `(thread_id, 序号)` 派生的幂等键，让"邮件服务"对重复键只处理一次。
6. **（进阶）HITL 状态**：增加一个 `wait_for_approval` activity，它在日志中写入 `waiting` 状态后让 workflow 退出；另一个函数 `approve(thread_id)` 写入 `approved` 事件，再次运行 workflow 时从等待点继续。思考讲义 skill 文件中的 HITL-on-resume：崩溃前得到的批准，恢复后还算数吗？

---

## 8. 常见坑

- **把 LLM 调用写在 workflow 里而不是 activity 里**：重放时会再调一次，得到不同的回答，后续分支全部漂移，而且重复计费。
- **workflow 中读挂钟、随机数、环境变量**：重放时取到不同值，走上不同分支。必须通过 activity / side-effect API 获取并记录。
- **以为持久化 = 恰好一次（exactly-once）**：activity 在 `started` 之后、`done` 之前崩溃会被重新执行，只能保证至少一次；副作用必须靠幂等键去重。
- **用参数做缓存键**：同参的多次调用被合并、不可哈希或类型会变化的参数（元组、对象）匹配失败；应按事件序号对齐。
- **日志写入非原子**：整文件重写时崩溃会损坏日志；用事务型数据库或"写临时文件 + 原子重命名"。
- **多个会话共享一个日志却没有 `thread_id`**：一个会话可能"重放"另一个会话的结果。
- **用 SQLite 或未配置持久化的 Redis 做生产后端**：讲义明确 SQLite 仅用于本地开发，Redis 需开启 AOF/快照，否则部署或重启后状态丢失。
- **以为持久化解决了长程可靠性**：讲义强调持久化"lets you run longer than the reliability profile supports"——它只是让失败更便宜，不会让 agent 在第 5 小时更可靠；要配合恢复时的 HITL 与预算上限（第 13 节）。
