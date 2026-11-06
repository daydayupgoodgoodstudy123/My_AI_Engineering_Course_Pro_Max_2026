# 测验 · 自主 Coding Agent 生态概览（2026）（The Autonomous Coding Agent Landscape (2026)）

> **阶段 15 · 自主系统 · 第 09 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 脚手架是承重结构 | 讲义：同一个 Claude Sonnet 4.5，在 SWE-agent v1 上 43.2%、在 Cline 自主模式下 59.8%，同一套权重相差 16.6 个百分点——"The base model is a component; the loop is the product" |
| 2 | SWE-bench 家族 | SWE-bench：真实 GitHub issue + 标准补丁 + 测试；Verified：OpenAI 2024 年人工筛选的 500 题子集；Pro：需要 10+ 行改动的更难任务，前沿模型 23–59% |
| 3 | 简单尾部（easy tail） | 讲义：Verified 的 500 题中有 161 题只需 1–2 行改动（32.2%），它们抬高了头部分数；生产分布更接近 Pro |
| 4 | 曲线的三个来源 | 更好的基座模型、更好的脚手架（CodeAct、反思、verifier loop）、更好的基准（Verified 去除噪声） |
| 5 | CodeAct | 模型输出 Python 代码，由 Jupyter 式内核在 sandbox 中执行；一个动作可以是一整段程序（循环、串联工具、捕获异常） |
| 6 | JSON tool call | 每个动作是一个结构化 JSON，宿主解码、校验后执行；一轮一个动作，易审计、组合性差、默认更安全 |
| 7 | 两种架构的分布 | CodeAct 主导开放平台（OpenHands、smolagents）；JSON tool call 主导托管服务（提供方控制执行器） |
| 8 | 脚手架加分的三处 | Retrieval（找对文件，"沉默的瓶颈"）、verifier loop（跑测试读栈再重试，SWE-bench 上 10+ 分）、failure containment（出错可回滚的 sandbox） |
| 9 | 选型方法 | "哪个 agent 最好"是错的问题；应在与自己工作匹配的任务分布、生产会用的脚手架上测端到端可靠性——用自己 bug backlog 中类 Pro 的子集 |
| 10 | 爆炸半径（blast radius） | 单个动作能影响的范围；CodeAct 一个动作可改多个文件，需要加固的 sandbox；本节代码只统计"实际改了几个文件" |

### 核心技能（能动手做到）

- [ ] 说清 SWE-bench、Verified、Pro 的区别，并解释"Verified 接近饱和"为什么会掩盖回退
- [ ] 给定总分和简单尾部的规模，算出"去掉简单题后"的得分（讲义练习 4）
- [ ] 对比 CodeAct 与 JSON tool call 的审计性、组合性、安全模型
- [ ] 读懂本节两个脚手架的 `step()` / `run()`，解释 turns 与 blast radius 是怎么算出来的
- [ ] 指出本节代码在"校验""测试""爆炸半径"上的简化，并把它改成"模型提议 → 宿主校验 → 执行"的真实流程
- [ ] 按 `outputs/skill-scaffold-audit.md` 的四个维度审计一个 coding agent 脚手架

---

## 二、基础自测（选择题）

**Q1.** 讲义用"同一个 Claude Sonnet 4.5 在 SWE-agent v1 上 43.2%、在 Cline 自主模式下 59.8%"想说明的是：

- A. 脚手架是承重结构：同样的权重，换一个循环就差 16.6 个百分点
- B. Cline 使用了更大的模型
- C. SWE-agent v1 的评测有 bug
- D. 两者差异来自随机种子，在统计误差范围内

**Q2.** 关于 SWE-bench Verified，与讲义一致的是：

- A. 它是比原始 SWE-bench 更难的子集，只包含 10+ 行的任务
- B. 它是由模型自动生成的合成任务集
- C. 它是 500 题的人工筛选子集，去掉了含糊和损坏的任务；其中 161 题只需 1–2 行改动
- D. 它的题目全部来自私有仓库

**Q3.** CodeAct 架构的核心是：

- A. 模型输出 JSON，宿主逐个校验后执行
- B. 模型输出 Python 代码，由 Jupyter 式内核在 sandbox 中执行；一个动作可以循环、串联工具、捕获异常
- C. 模型直接修改宿主机文件系统，不需要 sandbox
- D. 模型只输出 diff，由人类合并

**Q4.** 讲义说 JSON tool call 仍主导哪类场景？

- A. 开源研究平台，如 OpenHands、smolagents
- B. 需要一次修改大量文件的批处理任务
- C. 只在本地 IDE 插件中使用
- D. 托管服务（如 Anthropic Managed Agents、OpenAI Assistants），因为提供方控制执行器

**Q5.** 运行本节 `main.py`，两个脚手架的结果是：

- A. JSON 2/3、CodeAct 3/3
- B. 两者都 3/3，turns 都是 3
- C. JSON 3/3 用 3 轮；CodeAct 3/3 用 1 轮
- D. 两者都 3/3；JSON 用 4 轮、爆炸半径 1，CodeAct 用 2 轮、爆炸半径 3

**Q6.** 本节 `JsonScaffold` 的 `turns` 为什么是 4 而不是 3？

- A. 3 个编辑动作各占一轮，第 4 轮是发现没有失败测试后返回 `{"tool": "done"}` 的那一轮
- B. 有一个编辑失败，重试了一次
- C. `max_turns` 默认是 4
- D. `run_tests` 本身算一轮

**Q7.** 讲义列出脚手架"买分"的三个地方。下列哪一项**不在**其中？

- A. Retrieval：找到该读的文件
- B. Verifier loop：跑测试、读栈、重试
- C. 更长的 system prompt：把所有编码规范都写进去
- D. Failure containment：出错可回滚的 sandbox

**Q8.** 关于 SWE-bench Pro，与讲义一致的是：

- A. 前沿模型在 Pro 上已经超过 90%
- B. 限定为需要 10+ 行改动的任务，前沿系统得分在 23–59%；你的生产分布几乎肯定更接近 Pro 而不是 Verified
- C. Pro 是 Verified 的简单版本，用于快速回归测试
- D. Pro 只评测 JSON tool call 脚手架

---

## 三、动手 / 代码题

**Q9.** HEADLINE 写道："JSON tool-calls get safety by construction since every action is independently validated." 阅读 `JsonScaffold.step()`：

```python
    def step(self) -> str:
        self.turns += 1
        results = run_tests(self.repo)
        for (path, _), ok in zip(TESTS, results, strict=True):
            if ok:
                continue
            if _apply_fix(self.repo, path):
                return json.dumps({"tool": "edit", "path": path})
        return json.dumps({"tool": "done"})
```

1. 代码里有"校验"这一步吗？JSON 是在编辑**之前**还是**之后**生成的？
2. 把它改写成"模型提议 JSON → 宿主校验 → 宿主执行"的三段式，并写一个校验器：只允许 `edit` 和 `done` 两种工具、`path` 必须在仓库内的白名单里。
3. 给 CodeAct 脚手架设计对应的安全措施时，为什么不能用同样的"逐个动作校验"？

**Q10.** 讲义 "Use It" 说："The output shows the CodeAct scaffold solves more tasks in fewer turns."

1. 实际输出支持"solves more tasks"吗？
2. 在什么条件下 CodeAct 才会"解决更多任务"？用 `run(max_turns=...)` 设计一个实验并给出结果。
3. turns 的统计包含了什么？如果只数"真正执行编辑的动作"，两者分别是多少？

**Q11.** `run_tests` 与 `TESTS`：

```python
TESTS = [
    ("app.py", "add(2, 3) == 5"),
    ("util.py", "lower('AB') == 'ab'"),
    ("cli.py", "VERSION == 'v1.0'"),
]

def run_tests(repo):
    results = []
    for path, _expr in TESTS:
        src = repo.get(path, "")
        passed = False
        if path == "app.py":
            passed = "return a + b" in src
        ...
```

1. `TESTS` 里的表达式被执行了吗？"测试"实际上在检查什么？这样的测试会漏掉什么样的错误补丁？
2. `FIXES` 上方的注释说集中成一张表是为了"avoids duplicating the if/elif chain"，这个目标达成了吗？
3. 写一个真正执行代码的 `run_tests_real(repo)`：把每个文件的源码 `exec` 到独立命名空间里，再 `eval` 对应的测试表达式；说明在真实 agent 中为什么不能在宿主进程里这样做。

**Q12.** 讲义练习 4："SWE-bench Verified has 161 single-file, 1–2 line tasks. Construct a score that excludes them."

1. 某模型在 Verified 上总分 80.9%，假设 161 道简单题全对，剩余 339 道题的通过率是多少？如果简单题只对 95% 呢？
2. 另一个模型总分 70.0%，同样假设简单题全对，剩余题通过率是多少？两模型在"去掉简单题"后的差距与总分差距相比如何变化？
3. 这种"排除简单尾部"的分数还有什么局限？

---

## 四、面试高频题

**Q13.**（基础必考）SWE-bench、SWE-bench Verified、SWE-bench Pro 有什么区别？为什么说 Verified 的高分不能直接代表生产质量？

**Q14.**（原理深挖）CodeAct 和 JSON tool call 各有什么优缺点？从安全角度看，两者的"信任边界"分别在哪里？

**Q15.**（工程实践）团队要引入一个 coding agent 修内部 bug，你如何选型和评估？哪些情况你会拒绝上线？

**Q16.**（场景设计）为一个 CodeAct 风格的 agent 设计执行 sandbox，列出你的隔离措施，以及 agent 出错时如何止损。

**Q17.**（追问型）"同一模型、不同脚手架差 16.6 个百分点"——这些分数具体是从哪里来的？如果让你给一个现有脚手架再加 10 个点，你优先做什么、如何证明有效？

---

## 五、参考答案与解析

### Q1 — 答案：A

讲义："16.6 absolute points of difference, same weights. The base model is a component; the loop is the product." B 错，是同一个模型；C、D 没有依据——16.6 个百分点在 500 题上远超抽样误差。

### Q2 — 答案：C

讲义："SWE-bench Verified (OpenAI, 2024) is a human-curated 500-task subset with the ambiguous and broken tasks removed"，且 "161 of 500 tasks need only 1–2 lines of change"（占 32.2%）。A 描述的是 SWE-bench Pro；B、D 与事实不符——SWE-bench 来自真实的公开 GitHub issue。

### Q3 — 答案：B

讲义："the model emits Python code and a Jupyter-style kernel runs it in a sandbox. The agent can loop over files, chain tools, and catch its own exceptions inside one action." A 是 JSON tool call；C 错，CodeAct 恰恰"requires a hardened sandbox"（OpenHands 用 Docker 隔离）；D 更接近 Aider 的 edit-via-diff，且 Aider 也不需要人类逐条合并。

### Q4 — 答案：D

讲义："JSON tool calls remain dominant in managed services (Anthropic Managed Agents, OpenAI Assistants) where the provider controls the executor." A 反了，开放平台以 CodeAct 为主；B 是 CodeAct 的优势场景；C 无依据。

### Q5 — 答案：D

实际输出：

```text
  JSON tool-call      passed 3/3  turns  4  blast-radius 1
  CodeAct (stub)      passed 3/3  turns  2  blast-radius 3
```

A 只在 JSON 的 `max_turns` 被限制为 2 时出现（见 Q10）；B、C 的 turns 数不对——turns 包括最后返回 done 的那一轮。

### Q6 — 答案：A

逐步追踪 `JsonScaffold` 的动作序列（实测）：`edit app.py` → `edit util.py` → `edit cli.py` → `done`。`step()` 每次先 `turns += 1`，第 4 次调用时所有测试都通过，于是返回 done，循环 `break`。同理 CodeAct 是"一次改 3 个文件" + "done" = 2。B 错，stub 模型的修复从不失败；C 错，默认 `max_turns=10`；D 错，`run_tests` 不计轮数。

### Q7 — 答案：C

讲义的三处："Retrieval … Verifier loop … Failure containment"。更长的 system prompt 不在其中。

### Q8 — 答案：B

讲义："SWE-bench Pro restricts to 10+ line changes and returns scores in the 23–59% range even for frontier systems. Your production distribution is almost certainly closer to Pro than to Verified." A、C、D 与讲义不符。

### Q9 — 参考答案

1. **没有校验**。`step()` 先调用 `_apply_fix` **直接修改了** `self.repo`，然后才返回描述这次修改的 JSON。所以 JSON 只是"事后日志"，不是"待校验的提议"。HEADLINE 的 "independently validated" 在代码中并不存在；讲义说 JSON tool call "safe by default because each call goes through an explicit validator"，指的是真实系统中宿主侧的校验器。
2. 参考实现：

```python
ALLOWED_TOOLS = {"edit", "done"}
ALLOWED_PATHS = set(INITIAL_REPO)

def propose(repo) -> str:                       # "模型"：只提议，不执行
    for (path, _), ok in zip(TESTS, run_tests(repo), strict=True):
        if not ok and path in FIXES:
            return json.dumps({"tool": "edit", "path": path})
    return json.dumps({"tool": "done"})

def validate(action: dict) -> None:             # 宿主：校验
    if action.get("tool") not in ALLOWED_TOOLS:
        raise PermissionError(f"tool not allowed: {action.get('tool')}")
    if action["tool"] == "edit" and action.get("path") not in ALLOWED_PATHS:
        raise PermissionError(f"path not allowed: {action.get('path')}")

def execute(repo, action: dict) -> None:        # 宿主：执行
    if action["tool"] == "edit":
        _apply_fix(repo, action["path"])

def run_validated(repo, max_turns=10):
    for turn in range(1, max_turns + 1):
        action = json.loads(propose(repo))
        validate(action)
        if action["tool"] == "done":
            return sum(run_tests(repo)), turn
        execute(repo, action)
    return sum(run_tests(repo)), max_turns
```

关键是"模型"和"执行器"之间多了一道宿主拥有的校验关卡：被拒绝的动作根本不会碰到仓库。
3. CodeAct 的一个动作是任意程序，宿主无法在执行前对其语义做完备的静态校验（循环、动态路径、`exec`、网络调用……）。所以安全边界从"逐个动作校验"移到了"运行环境本身"：容器/VM 隔离、无外网、无宿主挂载、时间与资源上限、文件系统快照与回滚（skill 文件："confirm the sandbox is hardened (no egress, no host mounts, time limit)"）。可以在此之上加辅助措施（禁用某些模块、审计 diff），但它们不是主要防线。

### Q10 — 参考答案

1. **不支持**。两者都是 3/3，只有轮数不同。stub 模型是"全知"的——`FIXES` 表直接给出正确修复，不会失败，所以任务完成率不可能有差别。
2. 当轮数预算有限时差别才出现。实测：`JsonScaffold().run(max_turns=2)` 返回 `(2, 2)`——只修好 2 个；`CodeActScaffold().run(max_turns=1)` 返回 `(3, 1)`——1 轮修好 3 个。在真实 agent 中，轮数受上下文长度、成本上限和超时限制，"同样预算下能完成更多"才是 CodeAct "solves more tasks" 的含义。
3. turns 包含最后一轮 `done`。只数编辑动作：JSON 3 次、CodeAct 1 次。讲义练习 1 问"How many turns does each scaffold take"，答案应说明这个口径。

### Q11 — 参考答案

1. 没有执行，`_expr` 只被解包后丢弃。"测试"其实是**子串匹配**：源码中是否包含 `"return a + b"` 等。会漏掉的错误补丁例如：把 `return a + b` 写进注释或死代码里、加了 `return a + b` 但前面还有一个错误的 `return`、语法错误的文件——这些都会被判为"通过"。这与真实 SWE-bench 用"测试套件是否通过"判分的方式相差很大。
2. **没有完全达成**。`FIXES` 消除了两个脚手架之间的重复，但 `run_tests` 内部仍然是按路径写死的 if/elif 链，"什么算修好"的知识在 `FIXES` 和 `run_tests` 里各写了一遍。若 `TESTS` 新增一个路径而 `run_tests` 没改，该测试永远失败（实测：加一个 `db.py` 测试后，两种脚手架都只能 3/4）。
3. 参考实现：

```python
def run_tests_real(repo: dict[str, str]) -> list[bool]:
    results = []
    for path, expr in TESTS:
        ns: dict = {}
        try:
            exec(repo.get(path, ""), ns)        # 在独立命名空间中定义函数/变量
            results.append(bool(eval(expr, ns)))
        except Exception:
            results.append(False)               # 语法错误、运行时错误都算失败
    return results
```

在初始仓库上返回 `[False, False, False]`，修复后返回 `[True, True, True]`。真实 agent 不能在宿主进程里 `exec` 被修改的代码：agent 写的代码可以读写宿主文件、发网络请求、无限循环。必须在隔离的 sandbox（容器、VM）中运行测试，并设置超时和资源限制——这正是讲义 "failure containment" 的意义。

### Q12 — 参考答案

1. 剩余 339 题通过率 = `(总分 × 500 − 简单题通过数) / 339`。
   - 总分 80.9%、简单题全对：`(404.5 − 161) / 339 ≈ 71.8%`；
   - 简单题对 95%：`(404.5 − 152.95) / 339 ≈ 74.2%`。
2. 总分 70.0%、简单题全对：`(350 − 161) / 339 ≈ 55.8%`。总分差 10.9 个点，在"难题子集"上差距扩大为约 16.0 个点——简单题对所有强模型都接近满分，把它们混进分母会**压缩**模型之间的差距。（以上数值均用 Python 计算。）
3. 局限：①"1–2 行"不等于"简单"——有的一行修复需要深度定位，而这正是 retrieval 的难点；②仍然受测试质量、题目泄漏（训练数据污染）的影响；③仍然是公开仓库、Python 为主的分布，与你的内部代码库不同。所以 skill 文件要求："Public benchmarks predict rank-order, not absolute quality"，并用内部分布的小样本测量做最终判断。

### Q13 — 参考回答要点

- **SWE-bench**（Jimenez et al.）：真实 GitHub issue + 标准补丁，agent 产出补丁使测试通过。
- **Verified**（OpenAI, 2024）：人工筛选 500 题，去掉含糊和损坏的任务，降低噪声。
- **Pro**：要求 10+ 行改动的更难任务，前沿系统 23–59%。
- **为什么 Verified 高分不代表生产质量**：接近饱和；161/500 题只需 1–2 行，抬高头部分数；饱和的基准会**掩盖回退**（讲义："benchmark saturation hides regressions"）；生产分布更接近 Pro。
- 加分点：给出"去掉简单尾部"的重算方法（Q12），并提到要在自己的 bug backlog 上建一个类 Pro 的内部评测集。
- 常见误区：直接比较不同基准版本的分数（讲义开头"从 4% 到 80.9%"其实混合了原始 SWE-bench 与 Verified 两个版本）。

### Q14 — 参考回答要点

| 维度 | JSON tool call | CodeAct |
|------|---------------|---------|
| 动作粒度 | 一轮一个结构化动作 | 一个动作是一段程序 |
| 组合性 | 差，多步要多轮 | 强：循环、串联、异常处理都在一个动作内 |
| 审计 | 容易，每个动作有明确 schema | 难，要审计整段代码及其副作用 |
| 安全模型 | 宿主侧校验器逐个动作把关（"safe by default"） | 依赖加固的 sandbox；失败模式是"sandbox 允许的一切" |
| 典型场景 | 托管服务（提供方控制执行器） | 开放平台（OpenHands、smolagents） |

- **信任边界**：JSON 的边界在"校验器"——只要每个工具的校验正确，模型就做不出工具集之外的事；但如果暴露了 `shell_exec` 这类万能工具，边界就失效了（skill 文件的 hard reject）。CodeAct 的边界在"sandbox 外壳"——容器/VM、网络、挂载、资源限制。
- 加分点：说出二者可以混合——CodeAct 运行在 sandbox 里，但对外部副作用（推送代码、调用生产 API）仍然走带校验的工具调用。

### Q15 — 参考回答要点

按 `outputs/skill-scaffold-audit.md`：

1. **Retrieval**：脚手架如何选择要读的文件（repo map、embedding 检索、显式文件列表、agent 自己 grep）。
2. **Verifier loop**：是否跑测试、读栈、把失败反馈进下一轮；没有就标记缺失（通常是 10+ 分的差距）。
3. **Sandbox 与爆炸半径**：在哪执行；CodeAct 要确认 sandbox 加固；JSON 要确认校验器能拒绝所有非预期副作用。
4. **Benchmark fit**：公布的分数覆盖什么分布？简单尾部占比多少？同模型的 Pro 分数是多少？

评估流程：从自己的 bug backlog 中抽一个类 Pro 子集（跨文件、10+ 行），在 staging 中跑候选脚手架，测通过率、成本、轮数、出错类型。

**拒绝上线**：没有 verifier loop 却要处理非平凡任务；CodeAct 没有 sandbox 就指向真实仓库；基准声明不披露分布；工具调用式脚手架暴露了不受校验的 `shell_exec`；拿不出内部分布上的通过率；未经 staging 演练就直接作用于生产仓库；只凭公开基准做决策。

### Q16 — 参考回答要点

- **隔离**：每个任务一个一次性容器或 microVM（OpenHands 用 Docker；更强隔离可用 gVisor / Firecracker）；非 root 运行；只读挂载依赖缓存；仓库以副本形式拷入，不挂载宿主目录。
- **网络**：默认无外网；需要装依赖时走受控的代理/镜像白名单。
- **资源**：CPU、内存、磁盘配额；每个动作和整个任务都有超时；进程数上限。
- **凭证**：sandbox 内没有生产凭证；推送代码、开 PR 等外部副作用由 sandbox 外的服务在审核后执行。
- **止损**：文件系统快照，动作失败可回滚（讲义 "a sandbox that rolls back on error prevents compounding damage"）；连续失败 N 次或超出预算就停止；所有动作和输出写入事件流，便于回放（OpenHands 的 "event-stream replayable"）。
- 常见误区：把 Docker 当作完全的安全边界、在容器里挂载宿主 Docker socket 或 home 目录。

### Q17 — 参考回答要点

- **分数来源**（讲义）：编码运行是长程轨迹，可靠性在步骤间复利；脚手架在三处买分——retrieval（找对文件）、verifier loop（10+ 分）、failure containment（防止错误累积）。
- **优先做什么**：如果没有 verifier loop，先加它（收益最大、最确定）；然后改进 retrieval（repo map、符号索引、相关测试定位）；再加回滚与重试策略。
- **如何证明有效**：在固定的内部评测集上做消融实验（ablation）——每次只改一个组件，报告通过率、成本、轮数的变化和置信区间；同时看在 Pro 式难题上的变化，而不只是总分；保留一个从未用于调参的 held-out 子集防止过拟合。
- 加分点：说明"同模型不同脚手架"这个事实对采购的含义——比较 agent 产品时要比较"模型 + 脚手架"的整体，在自己的分布上测。

---

## 六、关联知识点

### 前置知识
- [阶段 14 · 06 工具使用与 Function Calling](../../../14-agent-engineering/06-tool-use-and-function-calling/docs/zh.md)：JSON tool call 的基础。
- [阶段 13 · 02 深入理解 Function Calling：OpenAI、Anthropic、Gemini](../../../13-tools-and-protocols/02-function-calling-deep-dive/docs/zh.md)：各家 tool calling 的格式与校验。
- [阶段 15 · 01 从聊天机器人转向长程 Agents](../../01-long-horizon-agents/docs/zh.md)：可靠性在长轨迹上复利，解释脚手架为何承重。
- [阶段 14 · 19 基准评测：SWE-bench、GAIA、AgentBench](../../../14-agent-engineering/19-benchmarks-swebench-gaia/docs/zh.md)：SWE-bench 的评测方法。

### 本节被哪些后续内容用到
- [阶段 15 · 10 自主 Agents 的权限模式](../../10-claude-code-permission-modes/docs/zh.md)：讲义表格中 Claude Code 的权限模式。
- [阶段 15 · 16 Checkpoints（检查点）与 Rollback（回滚）](../../16-checkpoints-rollback/docs/zh.md)：failure containment 的实现。
- [阶段 14 · 38 Verification Gates](../../../14-agent-engineering/38-verification-gates/docs/zh.md)：verifier loop 的工程化。
- [阶段 19 · 01 综合项目 01：终端原生 Coding Agent](../../../19-capstone-projects/01-terminal-native-coding-agent/docs/zh.md)：动手实现一个 coding agent。
- [阶段 19 · 16 综合项目 16：从 GitHub Issue 到 PR 的自主 Agent](../../../19-capstone-projects/16-github-issue-to-pr-agent/docs/zh.md)：SWE-bench 式任务的端到端实现。
- [阶段 19 · 26 综合项目第 26 课：带拒绝列表与路径隔离的 Sandbox 执行器](../../../19-capstone-projects/26-sandbox-runner-denylist/docs/zh.md)：sandbox 执行器。

### 延伸关键词
`SWE-bench Verified` · `SWE-bench Pro` · `easy tail` · `benchmark saturation` · `CodeAct` · `OpenHands` · `smolagents` · `Agent-Computer Interface (ACI)` · `repo map` · `verifier loop` · `blast radius` · `Docker / gVisor / Firecracker` · `event stream replay` · `ablation`
