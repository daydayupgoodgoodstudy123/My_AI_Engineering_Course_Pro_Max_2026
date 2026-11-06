# 代码讲解 · main.py

> **所属小节**：阶段 14 · Agent 工程 · 第 28 节 Orchestration 模式：监督者、Swarm 与层级结构 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py` ｜ **依赖**：仅标准库（`collections.Counter`），无需网络、无需 API key、没有真实 LLM

---

## 1. 这份代码在考察什么

同一组三类意图的客服任务（退款 refund / 故障 bug / 销售 sales），分别用四种编排拓扑处理，比较它们的 **trace 形状** 和 **操作次数（ops）**：

1. **Supervisor-worker**：中心路由 → 专家，每任务 2 步。
2. **Swarm**：从固定入口 Agent 出发，不对就直接 handoff，命中入口时只需 1 步。
3. **Hierarchical**：顶层 → 部门 → 专家，每任务 3 步，trace 最深。
4. **Debate**：3 个提议者 + 汇总 + 执行，每任务 5 步，最贵。

讲义 "Build It" 的结论——"Supervisor is cleanest; swarm is shortest; hierarchical is deepest; debate is most expensive"——就是这份代码的输出。

> 一句话：**拓扑决定了一个请求要经过多少次"决策"，也就决定了延迟、成本和可调试性**。同时也要看到：这里所有"Agent"都调用同一个确定性的关键词分类器，弹跳、分歧、上下文预算等真正让拓扑有差异的因素都没有出现——这些简化正是读代码时要指出来的地方。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `classify` | 函数 | 关键词规则把请求分到 refund / bug / sales | 路由决策（代替 LLM） |
| `SPECIALISTS` | 字典（名字 → lambda） | 三个专家，各返回一句处理结果 | worker / specialist |
| `supervisor_worker` | 函数 | 每任务：路由 1 op + 专家 1 op | Supervisor-worker |
| `swarm` | 函数 | 从 `refund` 出发，不匹配就 handoff，最多 3 跳 | Swarm + hop counter |
| `hierarchical` | 函数 | 顶层分部门 → 部门分专家 → 专家执行 | Hierarchical |
| `debate` | 函数 | 3 位辩手提议 → 多数投票 → 执行 | Debate（简化为投票） |
| `main` | 函数 | 依次运行四种模式并打印 trace 与 ops | 演示 |

数据流：`main` 定义 3 个任务 → 依次把任务列表交给四个模式函数 → 每个函数返回 `(trace, ops)` → 打印。

---

## 3. 逐段精讲

### 3.1 路由函数 `classify`

```python
def classify(text: str) -> str:
    t = text.lower()
    if "refund" in t:
        return "refund"
    if "crash" in t or "error" in t or "bug" in t:
        return "bug"
    if "pricing" in t or "quote" in t:
        return "sales"
    return "sales"
```

- 这是整个文件里唯一的"决策"逻辑，讲义说"against a common scripted LLM"，实际上并没有 LLM，所有模式都用这个函数代替 LLM 的路由判断。
- 规则按顺序匹配：refund 优先于 bug。`"refund for the crash"` 会被判为 refund（已实测），多意图请求只取第一个。
- ⚠️ **兜底默认为 sales**：`"how do I reset my password"` → `"sales"`（已实测）。任何无法识别的请求都会被当成销售线索。生产中应返回 `"unknown"` 并走澄清或人工。
- ⚠️ 倒数第二个 `if` 与最后的 `return "sales"` 结果相同，是**冗余**判断。
- ⚠️ 子串匹配：`"terrors"` 含 "error"，被判为 bug（已实测）。

### 3.2 专家表 `SPECIALISTS`

```python
SPECIALISTS: dict[str, Callable[[str], str]] = {
    "refund": lambda t: f"refund handled: {t[:30]}",
    "bug":    lambda t: f"bug logged: {t[:30]}",
    "sales":  lambda t: f"quote sent: {t[:30]}",
}
```

- 用字典做"名字 → 可调用对象"的注册表，四个模式都通过 `SPECIALISTS[label](task)` 调用专家。
- `Callable[[str], str]`：接收一个字符串、返回一个字符串的函数。
- `t[:30]` 只截取前 30 个字符，所以输出里出现了 `invoice 47`（被截断的 `invoice 4711`）。
- 字典保持插入顺序，`list(SPECIALISTS)[0]` 永远是 `"refund"`——swarm 的入口 Agent 就是靠这个"顺序"决定的。

### 3.3 Supervisor-worker

```python
def supervisor_worker(tasks: list[str]) -> tuple[list[str], int]:
    trace: list[str] = []
    ops = 0
    for task in tasks:
        ops += 1
        label = classify(task)
        trace.append(f"supervisor -> {label}")
        specialist = SPECIALISTS[label]
        ops += 1
        trace.append(f"  {label}: {specialist(task)}")
    return trace, ops
```

- 每个任务两个 op：supervisor 路由一次，专家执行一次。ops = 2N，与任务内容无关，**可预测**。
- 专家之间从不互相调用，所有流量都经过 supervisor——对应讲义"Specialists do not talk to each other"。
- trace 缩进两级，结构清晰，这就是"cleanest"的含义：从 trace 一眼能看出"谁决定、谁执行"。
- 讲义中 supervisor 还可以"loop back to self"（自己回答）或"terminate"，这里只实现了"交给专家"一种决策。

### 3.4 Swarm：直接 handoff + hop counter

```python
def swarm(tasks: list[str]) -> tuple[list[str], int]:
    trace: list[str] = []
    ops = 0
    for task in tasks:
        current = list(SPECIALISTS)[0]
        hops = 0
        while hops < 3:
            ops += 1
            label = classify(task)
            if current == label:
                trace.append(f"swarm[{current}]: {SPECIALISTS[current](task)}")
                break
            trace.append(f"swarm[{current}] handoff -> {label}")
            current = label
            hops += 1
    return trace, ops
```

- 每个任务都从 `refund` Agent 开始。当前 Agent 判断自己是否合适：合适就直接处理（1 个 op 同时包含"判断 + 处理"），不合适就 handoff 给它认为合适的 Agent。
- 没有中心路由——这是 swarm 的定义。命中入口时只要 1 op，所以演示中 refund 任务 1 op、另两个任务各 2 op，共 5 op，比 supervisor 的 6 少。
- ⚠️ **"最短"依赖入口**：三个任务都是 bug 时，swarm 也是 6 op，和 supervisor 一样（已实测 `[6, 6, 9, 15]`）。
- ⚠️ **hop counter 从未起作用**：`classify` 与"当前是谁"无关，第一次 handoff 必然到达正确 Agent。讲义练习 2 说"refuse after 3 handoffs. Does it catch A->B->A bouncing?"，在这份代码里根本构造不出弹跳。
- ⚠️ **超限后静默丢任务**：让 `classify` 交替返回 `bug`/`refund` 模拟弹跳，实测 trace 为 `['swarm[refund] handoff -> bug', 'swarm[bug] handoff -> refund', 'swarm[refund] handoff -> bug']`、ops = 3，然后循环结束——**没有任何 Agent 处理该任务，也没有任何升级或告警记录**。应当在超限或回到已访问 Agent 时显式升级（测验 Q9 给出了改写）。
- 各 Agent 共用同一个全局 `classify`，相当于"每个 Agent 都内置了同一个路由器"；真实 swarm 中每个 Agent 只了解自己的职责和可 handoff 的对象，判断可能互相矛盾，这正是弹跳的来源。

### 3.5 Hierarchical：两层路由

```python
def hierarchical(tasks: list[str]) -> tuple[list[str], int]:
    trace: list[str] = []
    ops = 0
    for task in tasks:
        ops += 1
        top_label = "customer_ops" if classify(task) != "sales" else "commercial"
        trace.append(f"top -> {top_label}")
        ops += 1
        sub_label = classify(task)
        trace.append(f"  {top_label} -> {sub_label}")
        specialist = SPECIALISTS[sub_label]
        ops += 1
        trace.append(f"    {sub_label}: {specialist(task)}")
    return trace, ops
```

- 顶层把 refund 和 bug 归到 `customer_ops`，sales 归到 `commercial`；子层再分到具体专家。每任务 3 op，trace 缩进三级——"deepest"。
- 用**条件表达式**（`A if cond else B`）一行完成顶层分组。
- ⚠️ 两层用的是**同一个分类函数**，顶层其实已经知道答案，第二次分类没有提供任何新信息。真实的层级之所以有价值，是因为每层只加载自己需要的专家描述，从而突破单个上下文预算（讲义："when a single supervisor's context budget cannot hold descriptions of all specialists"）。
- ⚠️ `commercial` 分支下只有 `sales` 一个专家，正好触犯 outputs 中 skill 的 hard reject："Hierarchical that bottoms out at 1 specialist per branch. Flatten." 整个系统只有 3 个专家，按讲义决策顺序应该用 supervisor——这是一个用于演示的"伪层级"。

### 3.6 Debate：三位提议者 + 多数投票

```python
def debate(tasks: list[str]) -> tuple[list[str], int]:
    trace: list[str] = []
    ops = 0
    for task in tasks:
        proposals: list[str] = []
        for debater in ("alpha", "beta", "gamma"):
            ops += 1
            label = classify(task)
            proposals.append(label)
            trace.append(f"{debater} proposes {label}")
        ops += 1
        convergent = Counter(proposals).most_common(1)[0][0]
        specialist = SPECIALISTS[convergent]
        ops += 1
        trace.append(f"debate converges -> {convergent}: {specialist(task)}")
    return trace, ops
```

- 每任务：3 次提议 + 1 次汇总 + 1 次执行 = 5 op，N 个任务 5N；k 位辩手时为 (k+2)N。
- `Counter(proposals).most_common(1)` 返回 `[(标签, 次数)]`，`[0][0]` 取出标签。
- ⚠️ **这不是辩论，而是多数投票**：讲义定义为"parallel proposers + iterative cross-critique"，但辩手看不到彼此的提议，没有批评和修订轮次，也没有轮数上限。
- ⚠️ 三位辩手调用同一个确定性函数，结果必然一致，投票不可能带来任何准确率提升——"debate 换准确率"的收益在这里为零，只剩成本。
- ⚠️ 平局处理：`Counter(["bug","refund","sales"]).most_common(1)` 实测为 `[('bug', 1)]`，并列时按插入顺序取第一个，即"听第一个发言的人"。
- ⚠️ 汇总只是一次 `Counter` 计算，并非 LLM 调用，却被计为 1 op；若改为由 judge 模型汇总，这个计数才名副其实。

### 3.7 `main`：统一驱动四种模式

```python
    for name, fn in (
        ("supervisor-worker", supervisor_worker),
        ("swarm",             swarm),
        ("hierarchical",      hierarchical),
        ("debate",            debate),
    ):
        trace, ops = fn(tasks)
        print(f"\n--- {name}  ops={ops} ---")
        for line in trace:
            print(f"  {line}")
```

- 四个函数签名完全相同（`list[str] -> tuple[list[str], int]`），所以可以放在一个元组里循环调用——这是"同一任务、不同拓扑"做对比实验的关键。
- 返回 trace 而不是直接打印，便于测试或进一步统计（例如数 handoff 次数）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用关键词分类器代替 LLM | 确定、可复现、无需 API | 所有拓扑做出同样的决策，弹跳与分歧无法出现；生产中路由由 LLM/tool call 完成，需要评测路由准确率 |
| 用 ops 计数代表成本 | 直观对比 | 口径不完全一致：swarm 的 1 op 含"判断 + 处理"，debate 的汇总不是 LLM 调用；真实对比应测 token、延迟、准确率（讲义练习 4） |
| 统一的函数签名 | 便于横向比较 | 无法表达异步、并行（debate 的提议本应并行） |
| swarm 入口固定为第一个专家 | 简单 | "swarm 最短"依赖入口命中率；生产中可用轻量入口路由或按渠道选择入口 |
| hop counter 上限 3 | 对应讲义"refuse after 3 handoffs" | 超限后静默丢弃任务；应升级到人工/默认处理者并上报 |
| 3 个专家也做两层层级 | 演示层级的 trace 形状 | 属于伪层级（skill hard reject）；真实需求出现在专家多到装不下上下文时 |
| debate 简化为多数投票 | 代码短 | 没有交叉批评、没有轮数上限、平局取第一个；见测验 Q10 |
| 未知请求默认 sales | 保证总有专家可用 | 误路由；应显式 `escalate_to_human` |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `lambda` 匿名函数 | `"refund": lambda t: f"refund handled: {t[:30]}"` | 一行定义简单函数，适合放进字典做注册表 |
| 带类型注解的字典常量 | `SPECIALISTS: dict[str, Callable[[str], str]] = {...}` | 注明键是字符串、值是"字符串 → 字符串"的函数 |
| `Callable[[参数类型], 返回类型]` | `Callable[[str], str]` | 描述函数类型 |
| 返回元组 | `-> tuple[list[str], int]`、`return trace, ops` | 一次返回 trace 和计数 |
| 元组解包 | `trace, ops = fn(tasks)` | 拆出两个返回值 |
| 带注解的局部变量 | `trace: list[str] = []` | 声明变量类型，便于阅读和类型检查 |
| 字典取键列表 | `list(SPECIALISTS)[0]` | 对字典调用 `list()` 得到键列表；字典保持插入顺序 |
| `while` + `break` | `while hops < 3: ... break` | 条件循环，命中时提前退出 |
| 条件表达式 | `"customer_ops" if classify(task) != "sales" else "commercial"` | 一行 if/else 赋值 |
| `Counter.most_common` | `Counter(proposals).most_common(1)[0][0]` | 计数并取出现最多的元素；并列时保持首次出现顺序 |
| 遍历元组对 | `for name, fn in (("swarm", swarm), ...)` | 函数是一等对象，可以和名字一起放进元组 |
| f-string 嵌套表达式 | `f"swarm[{current}]: {SPECIALISTS[current](task)}"` | 花括号里可以写任意表达式，包括函数调用 |
| 切片 | `t[:30]` | 取前 30 个字符 |
| 未使用的导入 | `dataclass, field`、`Any` | 文件导入了但没用到，可以删除（不影响运行） |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行 `main()` |

---

## 6. 运行结果解读

实际运行（Python 3，标准库，瞬间完成）：

```text
--- supervisor-worker  ops=6 ---
  supervisor -> refund
    refund: refund handled: I need a refund for invoice 47
  supervisor -> bug
    bug: bug logged: the CLI crashes on ctrl-c
  supervisor -> sales
    sales: quote sent: do you offer volume pricing?

--- swarm  ops=5 ---
  swarm[refund]: refund handled: I need a refund for invoice 47
  swarm[refund] handoff -> bug
  swarm[bug]: bug logged: the CLI crashes on ctrl-c
  swarm[refund] handoff -> sales
  swarm[sales]: quote sent: do you offer volume pricing?

--- hierarchical  ops=9 ---
  top -> customer_ops
    customer_ops -> refund
      refund: refund handled: I need a refund for invoice 47
  ...

--- debate  ops=15 ---
  alpha proposes refund
  beta proposes refund
  gamma proposes refund
  debate converges -> refund: refund handled: I need a refund for invoice 47
  ...
```

| 模式 | ops | 公式（N 个任务） | trace 特点 |
|------|-----|-----------------|-----------|
| supervisor-worker | 6 | 2N | 两级缩进，"谁决定、谁执行"一目了然 |
| swarm | 5 | N + 入口未命中的任务数 | 扁平；第一个任务直接被入口 `refund` 处理 |
| hierarchical | 9 | 3N | 三级缩进，最深 |
| debate | 15 | 5N（k=3） | 每任务 4 行，最长 |

- 三个任务的路由结果在四种模式下**完全一致**——因为都用同一个 `classify`。拓扑只改变了"走了几步"，没有改变"结果对不对"。这与真实系统不同：真实的拓扑差异会体现在准确率、上下文丢失和失效模式上。
- 输出中的 `invoice 47` 是 `t[:30]` 截断造成的，并非数据错误。
- 最后两行总结语是硬编码的。

额外实测（同一套代码，改变输入）：

| 输入 | supervisor | swarm | hierarchical | debate |
|------|-----------|-------|-------------|--------|
| 1 个 refund 任务 | 2 | 1 | 3 | 5 |
| 10 个 refund 任务 | 20 | 10 | 30 | 50 |
| 3 个 bug 任务 | 6 | 6 | 9 | 15 |

---

## 7. 动手改一改

1. **讲义练习 1**：把 `supervisor_worker` 改成 swarm（去掉中心路由），并让每个专家只"认识"一部分其他专家（例如 refund 只能 handoff 给 bug），观察哪些任务再也到不了正确的专家。
2. **讲义练习 2 + 修复**：让 `classify` 接收 `current` 参数并制造互相推诿（refund 认为是 bug，bug 认为是 refund），用测验 Q9 的改写验证"已访问检测 + 超限升级"能捕获 A→B→A。
3. **真正的辩论**：给三位辩手不同的关键词规则（模拟不同模型），加入一轮"看到他人提议后修订"，设置 `max_rounds=2`，平局时交给 judge；统计在一组带标注的任务上准确率是否提升。
4. **讲义练习 3**：构造 12 个专家，每个专家有一段描述；给 supervisor 设一个"描述总字数预算"，超过就报错；再实现两层层级，证明每层都在预算内。
5. **讲义练习 4**：给每个 op 加上模拟的延迟和 token 成本（例如路由 200 token、专家 800 token），输出每种模式的总延迟、总成本，并对一组带标注的任务计算准确率。
6. **兜底路由**：把 `classify` 的默认返回改为 `"unknown"`，新增 `escalate_to_human` 专家，四个模式都要能处理 `"how do I reset my password"`。

---

## 8. 常见坑

- **把 ops 当成真实成本**：swarm 的 1 op 包含判断与处理，debate 的汇总不是 LLM 调用；比较拓扑要看 token、延迟、准确率、可调试性多个维度。
- **"swarm 最短"的前提**：只有入口 Agent 恰好正确时才最短，全是 bug 任务时与 supervisor 一样。
- **hop counter 超限后什么都不做**：任务被静默丢弃比死循环更难发现；超限必须有明确结局和告警。
- **伪层级**：分支只有 1 个专家、两层用同一份信息路由，都是应该压平的信号。
- **把投票叫辩论**：没有交叉批评和轮数上限，就只是 self-consistency；辩手完全相同时连投票的收益都没有。
- **默认路由到某个专家**：无法识别的请求应该显式升级，而不是落到 sales。
- **拓扑先行**：在单 Agent + workflow 能解决的问题上引入多 Agent（skill："Calling 3 LLM calls in sequence 'multi-agent.' That's a prompt chain."）。
