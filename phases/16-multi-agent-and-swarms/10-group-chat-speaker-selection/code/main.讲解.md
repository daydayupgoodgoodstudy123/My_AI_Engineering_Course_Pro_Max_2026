# 代码讲解 · main.py

> **所属小节**：阶段 16 · 多智能体与集群 · 第 10 节 群聊与发言者选择 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无参数） ｜ **依赖**：仅标准库（`dataclasses`、`typing`），无需 LLM 或网络

---

## 1. 这份代码在考察什么

这是一个用标准库写成的"迷你 AutoGen GroupChat"：

1. **共享消息池**：所有消息追加到同一个 `pool: list[Msg]`，每个 agent 的 policy 都能读整个池。
2. **selector**：每一轮调用 selector 决定下一个发言者，演示两种实现——`round_robin_selector`（固定轮转）和 `llm_style_selector`（用规则模拟"读上下文选人"的 LLM）。
3. **agent policy**：coder、reviewer、manager 三个角色用确定性函数模拟 LLM 的回复。
4. **终止**：消息以 `TERMINATE` 结尾或达到 `max_rounds` 就停止。
5. **发言统计**：`speaker_counts` 对应讲义 Ship It 的 speaker-balance 指标。

> 一句话：**用 100 多行代码把"共享池 + selector + 终止条件"这一 GroupChat 骨架跑起来，对比"按顺序轮转"和"按上下文路由"**。但要注意：round-robin 那一场实际以 bug 未修复、coder 自行 `TERMINATE` 收场，原因是 `coder_policy` 的上下文窗口有缺陷——这比脚本自己打印的 "Observations" 更有教学价值。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Msg` | dataclass | `speaker` + `content` | 共享池中的一条消息 |
| `Agent` | dataclass | `name`、`role`、`policy: Callable[[list[Msg]], str]` | ConversableAgent 的极简版 |
| `coder_policy` | 函数 | 先写有 bug 的 `a - b`，被要求修复时改成 `a + b`，否则 `TERMINATE` | 执行者 |
| `reviewer_policy` | 函数 | 找最近一次 coder 消息，判断有无 bug | 审阅者 |
| `manager_policy` | 函数 | 池中出现 "approved" 就 `TERMINATE`，否则"继续" | 主持人 / 终止者 |
| `AGENTS` | 字典 | 名字 → `Agent`，**插入顺序**决定 round-robin 的顺序 | 团队 |
| `round_robin_selector` | 函数 | 上一位发言者的下一位 | round-robin selector |
| `llm_style_selector` | 函数 | 按上一条消息的发言者和内容路由 | LLM-selected selector（模拟） |
| `run_groupchat` | 函数 | 主循环：选人 → 调 policy → 入池 → 判断终止 | GroupChatManager |
| `speaker_counts` | 函数 | 统计每个 agent 的发言次数 | speaker-balance 指标 |
| `main` | 函数 | 两种 selector 各跑一次（`max_rounds=8`） | 演示入口 |

数据流：`run_groupchat` 每轮 `selector(pool, team)` → 名字 → `team[名字].policy(pool)` → 文本 → `Msg` 追加进 `pool` → 检查 `TERMINATE` → 下一轮。

---

## 3. 逐段精讲

### 3.1 数据结构：`Msg` 与 `Agent`

```python
@dataclass
class Msg:
    speaker: str
    content: str


@dataclass
class Agent:
    name: str
    role: str
    policy: Callable[[list[Msg]], str]
```

- `policy` 的类型是"接收整个消息池、返回一段文本"的函数，这正是 GroupChat 中"每个 agent 都读全部消息"的建模：真实系统里这里是一次 LLM 调用，输入是 system prompt + 全部历史。
- `role` 字段在代码中只用于描述，没有参与任何决策；真实的 LLM selector 会把各 agent 的 role/description 作为选人的依据。

### 3.2 三个 agent 的 policy

```python
def coder_policy(pool: list[Msg]) -> str:
    recent = [m for m in pool[-3:] if m.speaker != "coder"]
    last = recent[-1].content if recent else ""
    if "review" in last.lower() or "fix" in last.lower():
        return "revised code: return a + b"
    if not any(m.speaker == "coder" for m in pool):
        return "initial code: return a - b  (buggy)"
    return "TERMINATE"
```

- coder 只看**最近 3 条消息里最后一条不是自己说的**消息；含 "review" 或 "fix" 就提交修订版。
- 第一次发言时写一个有 bug 的版本（`a - b`），用来触发 reviewer 的反馈。
- 其他情况返回 `TERMINATE`——执行者自行宣布结束。
- ⚠️ **缺陷一：窗口太窄**。只要 reviewer 与 coder 之间插入一条别人的消息（round-robin 下 manager 正好排在中间），修复请求就不在"最后一条"了，coder 直接 `TERMINATE`，bug 被交付。
- ⚠️ **缺陷二：关键字太宽**。reviewer 的消息都以 "review:" 开头，包括 "review: approved"，所以 coder 在被批准后仍可能再提交一次"修订版"（改变 `AGENTS` 顺序即可复现，见测验 Q11）。

```python
def reviewer_policy(pool: list[Msg]) -> str:
    last_coder = next((m for m in reversed(pool) if m.speaker == "coder"), None)
    if last_coder is None:
        return "waiting for code"
    if "a - b" in last_coder.content:
        return "review: bug detected -- sum must be a+b, please fix"
    if "a + b" in last_coder.content:
        return "review: approved"
    return "review: unclear"
```

- `next(生成器, None)`：从后往前找第一条 coder 消息，找不到返回 `None`——这是"按角色找最近消息"的正确写法，比 coder 的"按位置取最近 3 条"稳健。
- 注意如果 coder 最后一条是 "TERMINATE"，reviewer 会返回 "review: unclear"。

```python
def manager_policy(pool: list[Msg]) -> str:
    approvals = [m for m in pool if m.speaker == "reviewer" and "approved" in m.content]
    if approvals:
        return "TERMINATE"
    return "manager: continue working"
```

- manager 是"目标达成检查者"：只要池中出现过批准就终止。它本身没有推动任务的能力，"continue working" 在对话中是一条噪声消息——而恰恰是这条噪声把 reviewer 的反馈从 coder 的窗口里挤了出去。

### 3.3 两种 selector

```python
def round_robin_selector(pool: list[Msg], team: dict[str, Agent]) -> Optional[str]:
    names = list(team.keys())
    if not pool:
        return names[0]
    idx = (names.index(pool[-1].speaker) + 1) % len(names)
    return names[idx]
```

- 顺序取决于字典的**插入顺序**（Python 3.7+ 保证）：`coder → reviewer → manager → coder …`。
- `% len(names)` 实现循环。selector 不看消息内容，"context-blind"。
- 若池中出现不在团队里的发言者，`names.index` 会抛 `ValueError`。

```python
def llm_style_selector(pool: list[Msg], team: dict[str, Agent]) -> Optional[str]:
    if not pool:
        return "manager"
    last = pool[-1]
    if last.speaker == "coder":
        return "reviewer"
    if last.speaker == "reviewer":
        if "approved" in last.content:
            return "manager"
        return "coder"
    if last.speaker == "manager":
        return "coder"
    return None
```

- 用规则模拟"LLM 读最近一条消息后选人"：coder 写完给 reviewer；reviewer 批准给 manager，否则回 coder；manager 之后给 coder。
- 第一轮先给 manager，它只会说 "continue working"——多花了一轮。
- 这个"LLM 式" selector 实际上是**完全确定的状态机**；真实 LLM selector 需要一次模型调用，可能不稳定，讲义要求记录它的输入和选择。
- 返回 `Optional[str]`：`None` 表示"没人该说话了"，主循环据此退出。

### 3.4 主循环 `run_groupchat`

```python
    for _ in range(max_rounds):
        nxt = selector(pool, team)
        if nxt is None:
            break
        trace.append(nxt)
        agent = team[nxt]
        content = agent.policy(pool)
        pool.append(Msg(speaker=nxt, content=content))
        print(f"  [{nxt:8s}]: {content}")
        if content.strip().endswith("TERMINATE"):
            break
```

- 三重终止：`max_rounds` 上限、selector 返回 `None`、消息以 `TERMINATE` 结尾。对应讲义 "Max rounds" 与 "TERMINATE token"；第三种 "goal-reached check" 在代码中由 manager 的 policy 间接实现。
- selector 的类型注解 `Callable[[list[Msg], dict[str, Agent]], Optional[str]]` 让两种 selector 可以互换——这就是 GroupChatManager "持有可插拔 selector" 的设计。
- `trace` 只记录选择结果，没有记录 selector 的输入；讲义 Ship It 要求两者都记录。
- ⚠️ `endswith("TERMINATE")` 是脆弱的字符串约定："Please do not TERMINATE" 会误触发终止，"TERMINATE." 则不会触发。

### 3.5 发言统计与 `main`

```python
def speaker_counts(pool: list[Msg]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for m in pool:
        counts[m.speaker] = counts.get(m.speaker, 0) + 1
    return counts
```

- `dict.get(key, 0) + 1` 是经典计数写法（等价于 `collections.Counter`）。
- 讲义 Ship It："Speaker-balance metric. Track turns per agent; alert when imbalance exceeds a threshold." 这里只统计不告警。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| policy 用确定性函数模拟 LLM | 无需 API，结果可复现 | 关键字匹配脆弱（"review" 匹配到 "review: approved"）；真实 agent 是 LLM 调用 |
| coder 只看最近 3 条 | 模拟"有限上下文" | 插话会冲掉关键反馈，导致 round-robin 场景交付 bug；应按角色/引用关系检索反馈 |
| "LLM-style" selector 用规则实现 | 演示"按上下文路由"的效果 | 实际是确定状态机；真实 LLM selector 每轮一次调用、可能不稳定、需要日志 |
| round-robin 顺序 = 字典插入顺序 | 简单 | 换顺序结果就变（测验 Q11）；不适合需要"谁该说"的任务 |
| `endswith("TERMINATE")` 终止 | 与 AutoGen 的习惯一致 | 自然语言里找关键字易误判；生产用结构化终止字段或 `is_termination_msg` + goal-reached verifier |
| `max_rounds=8` | 兜底防死循环 | 是必要的安全网，但不该成为常规结束方式 |
| 只记录 trace 不记录 selector 输入 | 输出简洁 | 无法回答"为什么选了它"；生产需记录输入、输出、理由、耗时 |
| 全池共享、无 projection | 体现 GroupChat 的默认行为 | 轮次增多后上下文平方级增长；约 10 条后应按角色限定视图 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 注解延迟求值 |
| `@dataclass` | `class Msg:`、`class Agent:` | 自动生成构造函数等 |
| `Callable[[参数类型...], 返回类型]` | `policy: Callable[[list[Msg]], str]` | 标注"函数类型"的字段/参数 |
| `Optional[str]` | `-> Optional[str]` | 等价于 `str | None`，可能返回 `None` |
| 函数作为字段/参数 | `Agent("coder", "writes code", coder_policy)`、`run_groupchat(AGENTS, round_robin_selector, ...)` | 函数是一等对象，可以存进 dataclass、作为参数传递 |
| 负索引切片 | `pool[-3:]`、`pool[-1]` | 取最后 3 个 / 最后 1 个元素；列表不足 3 个时返回全部 |
| 带条件的列表推导式 | `[m for m in pool[-3:] if m.speaker != "coder"]` | 过滤 |
| `any()` + 生成器 | `any(m.speaker == "coder" for m in pool)` | 任一元素满足即为 `True`，遇到就短路 |
| `next(生成器, 默认值)` + `reversed` | `next((m for m in reversed(pool) if m.speaker == "coder"), None)` | 从后往前找第一个满足条件的元素 |
| 条件表达式 | `recent[-1].content if recent else ""` | 空列表时给默认值，避免 `IndexError` |
| `str.lower()` / `in` | `"review" in last.lower()` | 不区分大小写的子串检查 |
| `str.strip().endswith()` | `content.strip().endswith("TERMINATE")` | 去首尾空白后判断结尾 |
| 字典保持插入顺序 | `list(team.keys())` | Python 3.7+ 字典按插入顺序迭代，round-robin 依赖这一点 |
| `list.index` + 取模 | `(names.index(pool[-1].speaker) + 1) % len(names)` | 找位置并循环到下一个 |
| `dict.get(key, default)` | `counts.get(m.speaker, 0) + 1` | 计数惯用法 |
| f-string 宽度格式 | `f"  [{nxt:8s}]: {content}"` | 字符串左对齐占 8 位，使输出列对齐 |
| 模块级常量 | `AGENTS: dict[str, Agent] = {...}` | 大写名表示"不打算修改"的全局配置 |

---

## 6. 运行结果解读

实际运行（Python 3.13，`python3 main.py`）：

```text
=== Round-robin ===
  [coder   ]: initial code: return a - b  (buggy)
  [reviewer]: review: bug detected -- sum must be a+b, please fix
  [manager ]: manager: continue working
  [coder   ]: TERMINATE
  Selector trace: ['coder', 'reviewer', 'manager', 'coder']
  Rounds used: 4
  Speaker counts: {'coder': 2, 'reviewer': 1, 'manager': 1}

=== LLM-style (context-aware) ===
  [manager ]: manager: continue working
  [coder   ]: initial code: return a - b  (buggy)
  [reviewer]: review: bug detected -- sum must be a+b, please fix
  [coder   ]: revised code: return a + b
  [reviewer]: review: approved
  [manager ]: TERMINATE
  Selector trace: ['manager', 'coder', 'reviewer', 'coder', 'reviewer', 'manager']
  Rounds used: 6
  Speaker counts: {'manager': 2, 'coder': 2, 'reviewer': 2}

Observations:
  - Round-robin gives every agent an equal turn regardless of context.
  - LLM-style routes by context; reviewer only speaks after coder, etc.
  - Both terminate on TERMINATE token or max_rounds.
```

逐项解读：

- **Round-robin**：第 4 轮 coder 的窗口里最后一条非 coder 消息是 manager 的 "continue working"，修复请求被挤掉，coder 落入兜底分支发出 `TERMINATE`。**最终结果是有 bug 的 `a - b`**，而且由执行者自己结束了对话，reviewer 和 manager 都没有确认。发言计数 `{coder: 2, reviewer: 1, manager: 1}` 也并不"均等"——因为对话提前结束了。
- **LLM-style**：selector 在 reviewer 要求修复后直接把发言权交回 coder，中间没有插话，coder 的窄窗口恰好够用；修复 → 批准 → manager 终止，6 轮得到正确结果。第 1 轮 manager 的 "continue working" 是一次浪费。
- **讲义练习 1 "哪个 agent 占主导"**：在这组数据上两种 selector 都没有出现 hot speaker（LLM-style 每人 2 次，round-robin 因提前终止 coder 2 次）。hot speaker 要在更长的对话或 LLM selector 偏好某个专长时才会出现。
- **Observations** 的第一条说 round-robin "equal turn"，但没指出它这次产出了错误结果；读者应把"上下文无关的轮转 + 窄上下文窗口的 agent"会导致反馈丢失，当作本节最重要的观察。

---

## 7. 动手改一改

1. **修复 `coder_policy`**：按角色找"最近一条 reviewer 消息"，仅在它晚于最近一次提交、且要求修复时才修改；不让 coder 自己 `TERMINATE`。再跑 round-robin，确认 6 轮得到批准（参考测验 Q9）。
2. **换顺序**：把 `AGENTS` 改成 `reviewer → coder → manager`，用原始 policy 跑 round-robin，观察 coder 在 "review: approved" 后再次提交、对话一直跑到 `max_rounds`（测验 Q11）。
3. **讲义练习 2**：实现 `capped(selector, cap)` 发言上限，比较 `cap=1`（3 轮后无人可选，bug 未修）与 `cap=2`（不受影响）。
4. **讲义练习 3**：加 goal-reached 终止（reviewer 说 "approved" 即停），统计它在 `max_rounds` 前触发的轮次。
5. **selector 日志**：让 `run_groupchat` 记录每轮 `{"round", "selector_input": 最近 3 条消息, "candidates", "counts", "choice"}`，并在结束时打印 speaker-balance 告警（如某人发言数 ≥ 其他人 2 倍）。
6. **进阶**：把 `llm_style_selector` 换成真实 LLM 调用（或用随机数模拟 10% 的"选错人"），多次运行，统计终止轮次和最终是否修复，体会"Same prompt, different runs, different next speakers"。

---

## 8. 常见坑

- **用位置而不是角色/引用关系找反馈**：`pool[-3:]` 这类窗口会被插话冲掉，关键反馈丢失。
- **关键字匹配过宽**："review" 能匹配到 "review: approved"，导致重复提交；生产中应使用结构化字段（如 `verdict: "approved" | "changes_requested"`）。
- **让执行者自己宣布结束**：coder 发出 `TERMINATE` 绕过了审阅；终止权应交给 verifier / manager 或 goal-reached 条件。
- **`endswith("TERMINATE")` 误判**：否定句会触发、带标点会漏掉；用结构化终止信号。
- **没有 `max_rounds`**：LLM selector 可能在两个 agent 之间来回，永不结束。
- **round-robin 依赖字典顺序**：调整团队顺序会改变结果，测试时要固定顺序。
- **只记录选择不记录输入**：LLM selector 出问题时无法复现原因。
- **全员读全池**：轮次增多后成本平方级增长，要用 projection 或摘要。
