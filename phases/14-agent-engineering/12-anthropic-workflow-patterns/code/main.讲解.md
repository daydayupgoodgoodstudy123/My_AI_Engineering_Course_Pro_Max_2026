# 代码讲解 · main.py

> **所属小节**：阶段 14 · Agent 工程 · 第 12 节 Anthropic 的工作流模式：优先采用简单方案 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无参数） ｜ **依赖**：仅标准库（`collections.Counter`、`dataclasses`、`typing`）；不需要 API key、不需要网络

---

## 1. 这份代码在考察什么

讲义的核心论点是"先用简单方案"：Anthropic《Building Effective Agents》（Schluntz & Zhang，2024 年 12 月）总结的五种 workflow 模式，每一种都只是十几行普通 Python。这份代码用一个脚本化的假 LLM 把五种模式全部实现了一遍：

1. **Prompt chaining**：上一步输出作为下一步输入（`prompt_chain`）。
2. **Routing**：分类后分派到不同处理器（`route`）。
3. **Parallelization（voting）**：同一 prompt 跑 N 次，多数决（`parallel_vote`）。
4. **Orchestrator-workers**：从专家池中挑 worker，再综合（`orchestrator_workers`）。
5. **Evaluator-optimizer**：提议 → 评估 → 带反馈重试（`evaluator_optimizer`）。

> 一句话：**workflow 模式本身没有魔法，难的是选对模式、处理好边界**。阅读时同时留意代码与讲义的差距：voting 并非真正并发、orchestrator 里没有 LLM、evaluator-optimizer 有边界 bug。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `ScriptedLLM` | 类（可调用对象） | prompt → 预设回答；列表脚本按调用次数依次返回；记录全部调用 | 离线可复现的 LLM 替身 |
| `prompt_chain` | 函数 | 依次套模板、调用、把输出传给下一步 | Prompt chaining |
| `route` | 函数 | 分类器给出标签 → 查处理器表 → 找不到用 `default` | Routing |
| `parallel_vote` | 函数 | 调 N 次、`Counter` 计票、取最多 | Parallelization（voting） |
| `Worker` | dataclass | 名字 + 是否处理该任务的谓词 + 执行函数 | worker |
| `orchestrator_workers` | 函数 | 遍历 worker，`handles` 为真的执行，再 `synth` | Orchestrator-workers（简化版） |
| `evaluator_optimizer` | 函数 | 循环 propose → evaluate，通过即返回，否则把评语作为反馈 | Evaluator-optimizer |
| `demo_*` | 5 个函数 | 每种模式一个演示 | 演示 |
| `main` | 函数 | 构造共享的 `ScriptedLLM` 脚本，依次运行 5 个 demo，打印总调用次数 | 入口 |

数据流：`main` 建一个 `ScriptedLLM`（所有 demo 共享，`calls` 累计）→ 五个 `demo_*` 各自把 `llm` 包装成分类器 / 处理器 / worker / proposer / evaluator 传给模式函数 → 打印 trace → 打印总调用数 20。

---

## 3. 逐段精讲

### 3.1 `ScriptedLLM`：字符串精确匹配的假 LLM

```python
class ScriptedLLM:
    def __init__(self, script: dict[str, str | list[str]]) -> None:
        self.script = script
        self.index: dict[str, int] = {}
        self.calls: list[str] = []

    def __call__(self, prompt: str) -> str:
        self.calls.append(prompt)
        value = self.script.get(prompt)
        if isinstance(value, list):
            i = self.index.get(prompt, 0)
            self.index[prompt] = min(i + 1, len(value) - 1)
            return value[i]
        if isinstance(value, str):
            return value
        return f"[unhandled: {prompt}]"
```

- 定义了 `__call__`，所以实例可以像函数一样调用：`llm("classify: ...")`。这让它能直接满足 `Callable[[str], str]` 类型，和真实的 API 包装函数可以互换。
- **字符串值**：每次返回同一个回答。
- **列表值**：按调用次数依次返回，用来模拟"同一 prompt 多次采样得到不同答案"（voting 的前提）。下标用 `min(i + 1, len(value) - 1)` **封顶**，列表用完后一直返回最后一个元素。这个细节会改变投票结果：`n=7` 时后两票都是 `"no"`，winner 变成 `"no"`（测验 Q5）。
- **未命中**：返回 `"[unhandled: <prompt>]"` 而不是抛异常。好处是 demo 不会崩，坏处是错误被"吞掉"——下游（如 `route`）会把它当成一个普通标签继续处理。
- 匹配是**逐字符精确匹配**，所以 evaluator-optimizer 的第二轮 prompt 必须一字不差地写成 `"propose: ... (fix: FAIL: missing observations)"`。这也提醒我们：在真实系统中，prompt 模板的任何微小变化都会改变模型行为。
- ⚠️ `self.index` 的"读—改—写"不是线程安全的；若改成多线程并发投票，需要加锁（测验 Q11）。

### 3.2 Prompt chaining

```python
def prompt_chain(input_text, llm, steps):
    current = input_text
    trace = []
    for label, template in steps:
        prompt = template.format(text=current)
        output = llm(prompt)
        trace.append((label, output))
        current = output
    return trace
```

- `steps` 是 `(标签, 模板)` 列表；模板里用 `{text}` 占位，`str.format(text=current)` 填入上一步的输出。
- demo 中两步：`"summarize: {text}"` → `"give a 6-word title: {text}"`。
- 讲义提到"Optional programmatic gates between steps"，代码里没有 gate。加 gate 很简单：在 `current = output` 之前检查输出（长度、格式、是否含禁止内容），不通过就提前返回或重试。
- 小细节：脚本里 6-word title 的回答 "Agents as ReAct with Guardrails Built In" 实际是 7 个词——脚本化替身不会校验约束，真实系统中这正是 gate 该做的事。

### 3.3 Routing

```python
def route(input_text, classifier, handlers):
    label = classifier(input_text)
    handler = handlers.get(label) or handlers.get("default")
    if handler is None:
        return label, f"no handler for {label}"
    return label, handler(input_text)
```

- 分类器本身也是一次 LLM 调用（`demo_route` 里是 `llm(f"classify: {text}")`），所以每条输入消耗 2 次调用。
- `handlers.get(label) or handlers.get("default")`：找不到对应处理器时退回 `default`；`default` 也没有时返回 `"no handler for ..."`。
- demo 中 `default` 处理器是 `lambda t: "escalate to human"`——转人工，是正确的兜底思路。
- ⚠️ label 不做校验：分类器返回 `"[unhandled: classify: refund pls]"` 时，代码会把这串字符当作 label 返回（实测）。真实系统中应限制标签为枚举值（结构化输出），并加置信度阈值（讲义练习 1、测验 Q10）。

### 3.4 Parallelization：voting

```python
def parallel_vote(prompt, llm, n=5):
    votes = [llm(prompt) for _ in range(n)]
    counts = Counter(votes)
    winner, _ = counts.most_common(1)[0]
    return winner, counts
```

- `Counter(votes)` 统计每个答案出现次数；`most_common(1)` 返回 `[(答案, 次数)]`，`[0]` 取第一项再解包。
- demo 中脚本给出 `yes, yes, no, yes, no` → `Counter({'yes': 3, 'no': 2})`，winner 为 `yes`。
- ⚠️ **不是并发**：列表推导式顺序执行，延迟是 N 次之和。讲义说"Run N LLM calls concurrently"，生产中用 `asyncio.gather` 或线程池。
- ⚠️ 只实现了 voting，没有讲义提到的另一种形态 sectioning（把任务拆成不同分块并发处理）。
- ⚠️ 讲义的签名是 `parallel_vote(prompt, n, aggregator)`，代码没有 `aggregator` 参数，聚合方式写死为多数决。
- ⚠️ 边界：`n=0` 时 `most_common(1)` 是空列表，`[0]` 抛 `IndexError`；平票时（如 `n=6` 得 3:3）按插入顺序返回先出现的答案，平票被静默当成多数。
- 投票前提是同一 prompt 多次调用结果有差异（temperature > 0）；temperature = 0 时 N 票几乎相同，投票没有意义。

### 3.5 Orchestrator-workers

```python
@dataclass
class Worker:
    name: str
    handles: Callable[[str], bool]
    fn: Callable[[str], str]


def orchestrator_workers(task, workers, synth):
    outputs = []
    for worker in workers:
        if worker.handles(task):
            outputs.append((worker.name, worker.fn(task)))
    return synth(outputs), outputs
```

- `Worker` 把"是否接这个任务"（`handles`）和"怎么做"（`fn`）都存成函数字段——dataclass 字段可以是任意可调用对象。
- demo 中：`python_reviewer` 看任务里有没有 "python"，`style_reviewer` 看 "style"，`security_reviewer` 的 `handles` 恒为 True。任务 `"review this python change for style and security"` 同时命中三者。
- `synth` 只是把各 worker 的输出用 `" | "` 拼起来，不调用 LLM。真实系统中 synth 通常也是一次 LLM 调用（汇总、去重、解决冲突）。
- ⚠️ **没有 orchestrator LLM**：讲义说"An orchestrator LLM dynamically decides which workers"，代码是静态关键字规则，本质上更接近"多路 routing + fan-out"。讲义签名 `orchestrator_workers(task, workers)` 也与代码（多一个 `synth`）不一致。改造方法见测验 Q12。
- worker 也是顺序执行；没有命中任何 worker 时 `outputs` 为空，`synth([])` 返回空字符串，调用方拿不到任何提示。

### 3.6 Evaluator-optimizer

```python
def evaluator_optimizer(task, proposer, evaluator, max_iter=5):
    trace = []
    feedback = None
    for i in range(max_iter):
        candidate = proposer(task, feedback)
        ok, judge = evaluator(task, candidate)
        trace.append((candidate, "PASS" if ok else "FAIL", judge))
        if ok:
            return candidate, trace
        feedback = judge
    return candidate, trace
```

- proposer 接收 `(task, feedback)`；第一轮 `feedback=None`，之后是上一轮 evaluator 的评语。
- demo 中 proposer 把反馈拼成 `" (fix: FAIL: missing observations)"`；evaluator 用 `verdict.startswith("PASS")` 判断是否通过。
- 第 1 轮 "ReAct loops thoughts and tool calls." 被判 `FAIL: missing observations`；第 2 轮补上 observation 后 `PASS`。
- `max_iter=5` 是停止条件，防止无限循环。循环变量 `i` 没有被使用（可写成 `_`）。
- ⚠️ `max_iter=0`：循环不执行，`candidate` 未定义，抛 `UnboundLocalError`（实测）。
- ⚠️ 耗尽轮数时返回**最后一轮**候选，且没有"是否通过"的标志；讲义练习 3 要求跨轮保留最好的结果。
- ⚠️ 反馈只传上一轮的评语，不累积历史，可能出现"修好 A、又弄坏 B"的振荡。

### 3.7 `main`：共享脚本与调用计数

- 所有 demo 共享**同一个** `ScriptedLLM`，所以 `llm.calls` 是累计的：chaining 2 + routing 6 + voting 5 + orchestrator 3 + evaluator-optimizer 4 = **20**。
- 讲义要点："Total lines of code per pattern is ~10-15; the cost of a framework is measured in thousands."
- 未使用的导入：`typing.Any`。`i` 在 `evaluator_optimizer` 中未使用。这些不影响运行。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用 `Callable[[str], str]` 抽象 LLM | 模式函数与具体模型解耦，替身和真实 API 可互换 | 真实调用还需要重试、超时、结构化输出解析 |
| 脚本化 LLM、精确字符串匹配 | 离线、确定、可复现 | 无法体现模型的不确定性；未命中返回字符串会掩盖错误，测试中宜抛异常 |
| prompt chain 无 gate | 代码最短 | 中间结果出错会一路传下去；生产在关键步骤间加程序化检查 |
| routing 用 `default` 兜底 | 未知类别不会崩溃 | 标签不校验、无置信度；生产用枚举输出 + 阈值 + 转人工 |
| voting 用列表推导式 | 简单 | 延迟为 N 倍；生产用 `asyncio.gather` / 线程池 + 超时 + quorum |
| orchestrator 用静态谓词 | 无需 LLM 即可演示 fan-out | 与讲义"LLM 动态决定"不符；生产由 LLM 输出受约束的 worker 列表 |
| evaluator-optimizer 用 `max_iter` 限制 | 防止无限循环 | 缺 `passed` 标志、不保留历史最佳、`max_iter=0` 崩溃 |
| 所有 demo 共享一个 LLM 实例 | 便于统计总调用数 | 列表脚本的下标状态也会被共享，demo 之间可能互相影响 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `__call__` | `ScriptedLLM.__call__(self, prompt)` | 让实例像函数一样被调用：`llm(prompt)` |
| 联合类型注解 | `dict[str, str \| list[str]]`、`str \| None` | 值可以是几种类型之一（配合 `from __future__ import annotations`） |
| `Callable[[参数类型], 返回类型]` | `Callable[[str], str]`、`Callable[[str, str \| None], str]` | 描述"函数类型"的参数 |
| `isinstance` | `isinstance(value, list)` | 运行时判断类型，决定走哪个分支 |
| `str.format` 命名占位 | `template.format(text=current)` | 用关键字参数填充 `{text}` |
| `dict.get` + `or` | `handlers.get(label) or handlers.get("default")` | 前者为 None 时取后者 |
| `lambda` | `lambda t: llm(f"handle refund: {t}")` | 匿名小函数，常用于回调 |
| 闭包 | `classifier` 内部使用外层的 `llm` | 内层函数"记住"外层变量 |
| `collections.Counter` | `Counter(votes)`、`counts.most_common(1)[0]` | 计数字典；`most_common(k)` 返回出现最多的 k 项 |
| 元组解包 | `winner, _ = counts.most_common(1)[0]` | `_` 丢弃不需要的值 |
| `@dataclass` 存函数字段 | `Worker(name, handles, fn)` | 字段类型可以是可调用对象 |
| 生成器表达式 + `join` | `" \| ".join(f"{name}: {out}" for name, out in outputs)` | 拼接字符串 |
| `enumerate(..., 1)` | `for i, (cand, verdict, reason) in enumerate(trace, 1)` | 从 1 开始计数，并对元组嵌套解包 |
| 条件表达式 | `"PASS" if ok else "FAIL"` | 一行的 if/else |
| `str.startswith` | `verdict.startswith("PASS")` | 前缀判断 |
| `+=` 字符串拼接 | `prompt += f" (fix: {feedback})"` | 生成新字符串并重新绑定 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()` |

---

## 6. 运行结果解读

实际运行（`cd code && python3 main.py`，瞬间完成）：

```text
1. PROMPT CHAINING — summarize then title
  [summarize] Agents: ReAct + tools + memory + guardrails.
  [title] Agents as ReAct with Guardrails Built In        ← 第 2 步的输入是第 1 步的输出

2. ROUTING — classify then dispatch
  [refund] refund filed
  [bug] bug logged
  [sales] quote sent                                       ← 每条输入：classify + handle 两次调用

3. PARALLELIZATION — N voters on a boolean
  winner: yes
  counts: {'yes': 3, 'no': 2}                              ← 脚本的 5 个元素恰好用完

4. ORCHESTRATOR-WORKERS — specialist pool
  [python_reviewer] python ok
  [security_reviewer] security ok
  [style_reviewer] style ok
  synth: python_reviewer: python ok | security_reviewer: security ok | style_reviewer: style ok

5. EVALUATOR-OPTIMIZER — propose, judge, refine
  iter 1  [FAIL] ReAct loops thoughts and tool calls.  // FAIL: missing observations
  iter 2  [PASS] ReAct interleaves thought, action, and observation until done.  // PASS
  final: ReAct interleaves thought, action, and observation until done.

total llm calls across all five patterns: 20
```

逐项解读：

- **20 次调用的拆分**：2 + 6 + 5 + 3 + 4。注意 orchestrator 的 synth 和 routing 的 `default` 都不调 LLM。
- **voting**：`n=5` 恰好用完脚本。额外实验：`n=6` 得 3:3，`most_common` 返回先出现的 `yes`；`n=7` 得 `no` 4 票、`yes` 3 票，winner 翻转为 `no`。
- **orchestrator**：三个 worker 全部命中，是因为任务文本里同时出现了 "python" 和 "style"；换成 `"review this Go change"` 只有 `security_reviewer` 运行。

额外的边界实验（导入模块后调用，不修改源码）：

| 实验 | 结果 |
|------|------|
| `route` 分类器返回未脚本化的字符串 | label 为 `[unhandled: classify: refund pls]`，落到 `default` 转人工 |
| `route` 返回 `greeting` 且没有 `default` | `('greeting', 'no handler for greeting')` |
| `evaluator_optimizer(..., max_iter=0)` | `UnboundLocalError` |
| evaluator 永不通过、`max_iter=3` | 返回最后一个候选，调用方无"失败"标志 |
| `orchestrator_workers` 传入空 worker 列表 | `('', [])` |

---

## 7. 动手改一改

1. **给 chain 加 gate**：在 `prompt_chain` 中支持可选的 `gate(label, output) -> bool`；让 title 步骤检查"恰好 6 个词"，观察脚本里的 7 词标题被拦下。
2. **routing 置信度阈值（讲义练习 1）**：分类器返回 `(label, confidence)`，标签不在白名单或置信度低于 0.8 时转人工，并记录路由日志（参考测验 Q10）。
3. **真正并发 + 超时投票（讲义练习 2）**：用 `ThreadPoolExecutor` + `wait(timeout=...)` 实现，加 quorum 和平票处理；给 `ScriptedLLM` 加锁（参考测验 Q11）。
4. **evaluator-optimizer 改成"保留最优"（讲义练习 3）**：evaluator 返回分数，跨轮保留 top-2，返回 `passed` 标志，修复 `max_iter=0`（参考测验 Q9）。
5. **router + chain 组合（讲义练习 4）**：router 选择三条 chain 之一；用 `len(llm.calls)` 和 prompt 字符数估算 token 成本，与"一个大 prompt"方案对比。
6. **真正的 orchestrator**：让一个 LLM 输出 worker 名单，白名单校验、去重、限制数量，再由 LLM 做 synth（参考测验 Q12）。

---

## 8. 常见坑

- **把 workflow 写成 agent**：步骤明明可以枚举，却让模型自由循环，成本与失败率都会上升。讲义："If you can enumerate the steps, you should."
- **routing 不校验标签**：LLM 输出 "Refund"、"refund." 或带解释的句子都会匹配失败；用结构化输出约束成枚举。
- **以为 voting 越多越好**：temperature 低时多票高度相关，投票几乎无效；同时成本线性增加。
- **平票与缺票不处理**：`Counter.most_common` 遇到平票会按插入顺序"随便"选一个。
- **evaluator-optimizer 没有上限或上限为 0**：前者可能空转，后者在本代码中直接崩溃。
- **耗尽轮数后把失败结果当成功交付**：必须返回显式的通过标志。
- **测试替身吞掉错误**：`ScriptedLLM` 未命中时返回字符串而非抛异常，测试可能"绿着通过"却走了错误分支；写测试时应断言 `llm.calls` 的内容。
- **把 3 个 worker 的 orchestrator 叫做"multi-agent"**：skill 文件特别指出这会带来不必要的协调、调试与评估成本，worker 只是 LLM 调用。
