# 测验 · 使用固定测试任务的评估 Harness（Eval Harness with Fixture Tasks）

> **阶段 19 · 综合项目 · 第 27 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py)、[code/tests/test_main.py](../code/tests/test_main.py)、夹具 [code/tasks/](../code/tasks/) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 说明：本节中文讲义是机器翻译，质量较差（如把 "pass@1" 译成"考量@ 1"、"off-by-one" 译成"关闭一个英寸"），阅读时请以英文版为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 没有 eval harness 的三种失败 | 讲义："unverified pass"（agent 说修好了其实没修）、"undetected regression"（prompt 改动让某些任务变差却没人发现）、"per-task drift"（两次评测的任务集合不同，通过率不可比） |
| 2 | Fixture task（固定测试任务） | 讲义定义为 goal + setup + verifier 三元组；代码落地为目录约定：`task.json`（id / goal / verifier）+ `buggy/`（初始文件）+ `expected/`（参考答案） |
| 3 | 三种确定性 verifier | `file_equals`（与参考文件逐字比较，严格，易误杀）、`regex_match`（正则匹配，宽松，易误放）、`shell_exit_zero`（跑命令看退出码，检验行为，需要 sandbox） |
| 4 | Verifier 注册表 | `VERIFIER_REGISTRY` 把名字映射到函数；`task.json` 只写名字和参数；未知名字返回失败而不是崩溃 |
| 5 | Candidate 协议 | `Callable[[FixtureTask, str], SampleResult]`：harness 只关心"给你任务和 scratch 目录，交回一个 SampleResult"，不关心 agent 内部怎么实现 |
| 6 | 每个 sample 一个全新 scratch 目录 | `tempfile.mkdtemp` → 复制 `buggy/` → 跑 candidate → 验证 → `finally` 中 `rmtree`；保证 k 次采样彼此独立 |
| 7 | pass@1 与 pass@k | 代码用 `1 - (1 - p)^k`（p 为经验通过率）；它是"插值（plug-in）估计"，比 HumanEval 论文的无偏估计 `1 - C(n-c,k)/C(n,k)` 系统性偏低；两者同时报告，避免 pass@k 掩盖首次成功率低的问题 |
| 8 | 延迟与成本聚合 | 每任务 mean / p95 延迟、mean 成本，全局 mean / p95 延迟与 total 成本；注意延迟和成本都是 **candidate 自报**的 |
| 9 | Harness 自测 | 参考 candidate（把 `expected/` 拷进来）必须 pass@1 = 1.0，noop candidate 必须 pass@1 = 0.0——同时验证 harness、verifier 和夹具本身 |
| 10 | 结构化报告 | `EvalReport.to_dict()` 输出 JSON，含每任务、每 sample 的 `passed` / `detail`，供回归追踪脚本对比与排查 |

### 核心技能（能动手做到）

- [ ] 能写出一个新的 fixture 目录（`task.json` + `buggy/` + `expected/`），并选择合适的 verifier
- [ ] 能针对给定 verifier 构造"误放"（错误代码却通过）与"误杀"（正确代码却失败）的反例
- [ ] 手算 pass@k（plug-in 与无偏两种），并解释二者差异以及何时差得最多
- [ ] 能读懂 `EvalHarness.run` 的循环，说清 scratch 目录的生命周期与报告字段的来源
- [ ] 能把 harness 改得更健壮：candidate 抛异常记为失败、由 harness 自己计时
- [ ] 能用 `shell_exit_zero` + 断言/pytest 写出"检验行为而不是文本"的 verifier
- [ ] 能说出把本节 harness 用于真实 LLM agent 前还缺什么（隔离、答案泄漏、统计显著性、夹具版本）

---

## 二、基础自测（选择题）

**Q1.** 某任务 5 次采样中通过 3 次。按本节 `pass_at_k(empirical_pass_rate, k)` 函数，`pass_at_k(3/5, 5)` 约为：

- A. 0.990
- B. 0.600
- C. 1.000
- D. 0.936

**Q2.** `task_002_factorial_missing_return` 的 verifier 是 `regex_match`，pattern 为 `^\s*return\s+result\s*$`（`re.MULTILINE`）。下列哪个提交会被**误判为通过**（错误代码却通过）？

- A. 不做任何修改，原样保留 buggy 文件
- B. 在函数末尾加上 `    return result * 1`
- C. 在函数末尾加上 `    return (result)`
- D. 把 `    return result` 缩进到 `for` 循环体内部（成为循环的最后一行）

**Q3.** `EvalHarness.run` 在**每个 sample** 之前都调用 `_prepare_scratch` 创建全新目录，而不是每个任务只建一次。最主要的原因是：

- A. 减少磁盘占用，提高运行速度
- B. 只有 `shell_exit_zero` 需要新目录，其它 verifier 无所谓
- C. 让每次采样都从 buggy 初始状态开始，k 个 sample 相互独立；否则第 2 个 sample 会在第 1 个的产出上继续，测到的是"二次修补"而不是首次成功率
- D. `tempfile` 模块要求每个目录只能写入一次

**Q4.** Demo 中 noop candidate（什么都不做）在 k = 3 时必须得到 pass@1 = 0.0，否则 `run_demo` 返回 1。这一检查主要能证明什么？

- A. 被评测的 agent 质量很好
- B. 每个夹具的 buggy 版本确实无法通过自己的 verifier（夹具不是"白送分"的），且 harness 能正确记录失败
- C. noop 的延迟可以作为所有 candidate 的延迟基线
- D. 所有 verifier 都不存在任何误放（false positive）

**Q5.** 对 `values = list(range(1, 20))`（即 1～19，共 19 个值）调用本节的 `p95(values)`，返回值是：

- A. 19
- B. 17
- C. 18.05
- D. 18

**Q6.** 你要新增一个 verifier `pytest_passes`：在 scratch 目录中运行 pytest，全部测试通过才算 pass。最合适的做法是：

- A. 基于 `shell_exit_zero`，argv 设为 `["python3", "-m", "pytest", "-q"]`，因为 pytest 以退出码 0 表示全部通过
- B. 基于 `file_equals`，比较 pytest 生成的结果文件
- C. 基于 `regex_match`，在源码中搜索 `def test_`
- D. 无法实现，pytest 不能作为 verifier

**Q7.** 若某个 `task.json` 中的 verifier 名字拼错（例如 `"file_equal"`），运行 harness 会发生什么？

- A. 在 `load_fixture` 阶段抛出 `KeyError`，整个评测中止
- B. 该任务被跳过，不出现在报告里
- C. 该任务每个 sample 都记为失败，`detail` 为 `unknown verifier 'file_equal'`
- D. 默认按 `file_equals` 处理

**Q8.** 报告中每个 sample 的 `latency_ms` 是怎么来的？

- A. harness 在调用 candidate 前后用 `time.perf_counter()` 计时
- B. candidate 自己计时并写入返回的 `SampleResult.latency_ms`，harness 原样采用
- C. verifier 运行时计时
- D. 通过 `subprocess` 读取操作系统统计的进程 CPU 时间

---

## 三、动手 / 代码题

**Q9.** 阅读 `task_005_linked_list_traversal`：

```json
{
  "id": "task_005_linked_list_traversal",
  "goal": "linked_list_length(head) should count every node in the linked list starting at head, including head itself. The buggy version starts counting from head.next, dropping one node. Fix it by initialising the counter to 0 and incrementing for every node walked.",
  "verifier": { "name": "file_equals", "args": { "path": "linked_list.py" } }
}
```

buggy 版本的关键几行：

```python
    count = 0
    node = head.nxt
    while node is not None:
        count = count + 1
        node = node.nxt
    return count
```

1. goal 里"Fix it by initialising the counter to 0"这句提示有什么问题？真正需要改的是哪一行？
2. 如果 agent 把 `count = 0` 改成 `count = 1`（其余不动），功能对不对？`file_equals` 会给出什么结果？
3. 改写这个任务的 verifier，让它检验**行为**而不是文本，给出新的 `verifier` JSON。

**Q10.** 下面是 `EvalHarness.run` 里每个 sample 的核心逻辑：

```python
            for sample_index in range(self.k):
                scratch = self._prepare_scratch(task)
                try:
                    sample = candidate(task, scratch)
                    outcome = self._verify(task, scratch)
                    latencies.append(sample.latency_ms)
                    costs.append(sample.cost_units)
                    ...
                finally:
                    shutil.rmtree(scratch, ignore_errors=True)
```

1. 如果 candidate（例如一个真实 LLM agent）在第 3 个任务上抛出 `RuntimeError`，整个评测会怎样？
2. 一个 candidate 实际花了 50 ms，却在 `SampleResult` 里报告 `latency_ms=0.001`，报告里显示多少？
3. 写一个 `_run_one(self, candidate, task, sample_index) -> dict`，修复这两个问题：异常记为失败（附异常信息），延迟由 harness 自己测量（同时保留自报值以便对照）。

**Q11.** 讲义给出 `pass@k = 1 - (1 - p)^k`。HumanEval 论文（Chen et al., 2021）使用的无偏估计是：对每个任务采样 n 次、其中 c 次通过，`pass@k = 1 - C(n-c, k) / C(n, k)`。

1. 用 Python 实现 `pass_at_k_unbiased(n, c, k)`。
2. 分别计算 (n=5, c=1, k=5)、(n=10, c=3, k=5)、(n=20, c=1, k=5) 两种公式的结果。
3. 本节 harness 恰好采样 k 次再报告 pass@k。在 n = k 的情况下，"至少一次通过"的直接观测值是多少？plug-in 公式和它有什么关系？

**Q12.** 用一个"60% 概率调用参考 candidate、否则什么都不做"的随机 candidate、`k = 5` 跑全部 5 个任务，每任务通过次数为 `[3, 4, 2, 1, 2]`。请手算：

1. 每个任务的 `pass_rate` 和 `pass_at_k`（保留 4 位小数）；
2. `EvalReport` 的 `pass_at_1` 与 `pass_at_k`；
3. 哪个任务最能体现"pass@k 掩盖首次成功率低"的问题？

---

## 四、面试高频题

**Q13.**（基础必考）什么是 pass@k？怎么计算？为什么评测报告里通常要同时给出 pass@1 和 pass@k？

**Q14.**（原理深挖）给 coding agent 设计 verifier 时，`file_equals`、`regex_match`、`shell_exit_zero`（跑测试）各有什么误判风险？"确定性"为什么是 verifier 的第一要求？如何防止 agent "钻 verifier 的空子"（reward hacking）？

**Q15.**（工程实践）你要把这个 harness 接进 CI，用来判断"一次 prompt 模板改动是不是回归"。你会怎样设计流程和报告，才能真正解决讲义说的 "undetected regression" 和 "per-task drift"？

**Q16.**（场景设计）要把本节的玩具 harness 升级为评测真实 LLM coding agent（几百个任务、每任务多次采样、类似 SWE-bench 的仓库级任务）的系统，你会补充哪些能力？

**Q17.**（追问型）在 50 个任务上，改 prompt 前 pass@1 = 0.62，改后 0.58。产品经理说"掉了 4 个点，回滚！"你怎么回应？

---

## 五、参考答案与解析

### Q1 — 答案：A

`1 - (1 - 0.6)^5 = 1 - 0.4^5 = 1 - 0.01024 = 0.98976 ≈ 0.990`（已用代码实际计算）。

- B 是单次采样通过率 p 本身，即 pass@1。
- C：如果按"这 5 次里是否至少通过一次"直接观测，或用 n = k = 5 的无偏估计，答案是 1.0——但题目问的是本节函数，它用的是 plug-in 公式，结果不是 1.0（见 Q11）。
- D 是 k = 3 时的值（`1 - 0.4^3 = 0.936`）。

### Q2 — 答案：D

`re.MULTILINE` 下 `^` 匹配每一行开头，pattern 只要求"某一行是 `return result`"，并不关心这一行在哪个缩进层级。把它放进循环体后，第一轮循环（i = 2）就返回，`factorial(5)` 实际得到 **2**（已实际运行验证），但 verifier 判为通过——典型的**误放（false positive）**。

- A：buggy 文件里没有 `return`，不匹配，失败（noop candidate 正是这种情况）。
- B：`return result * 1` 功能正确，但 `\s*$` 要求 `result` 后只有空白，不匹配——这是**误杀（false negative）**，不是误放。
- C：`return (result)` 同样功能正确却不匹配，也是误杀。

同类问题：`task_004` 的 pattern `return\s+(.+\[::-1\]|list\(reversed\(.+\)\))` 会放过 `return sorted(items)[::-1]`（`[3,1,2]` 得到 `[3,2,1]`，正确答案应是 `[2,1,3]`），甚至放过注释 `# return items[::-1]`（函数实际仍返回 None）——两者都已实测通过 verifier。

### Q3 — 答案：C

pass@k 的前提是 k 次采样**相互独立、同分布**。如果复用目录，第 2 次 sample 的起点就是第 1 次的产出：若第 1 次已经修好，第 2 次什么都不做也会通过，pass rate 被抬高。讲义配套 quiz.json 也给出同样的解释："Without a fresh scratch, sample N+1 starts from sample N's output."

- A 恰好相反：每次复制目录有额外开销。
- B：`file_equals` / `regex_match` 同样读取 scratch 中的文件，同样受污染影响。
- D 是虚构的限制。

### Q4 — 答案：B

noop 什么都不改，scratch 中就是 buggy 文件。pass@1 = 0.0 说明：5 个夹具的 buggy 版本都会被自己的 verifier 判失败（夹具"有效"），而且 harness 能正确记录失败。这是评测集的基本卫生检查——如果某个夹具在不修改的情况下就能通过，它对任何 agent 都是白送分。

- A：noop 不是被评测的 agent。
- C：noop 自报的延迟约为 0，没有基线意义。
- D：noop 只证明"不改就不通过"，证明不了"改错了也不通过"（Q2 就是反例）。

### Q5 — 答案：D

代码：`idx = max(0, int(round(0.95 * 19)) - 1)`。`0.95 × 19 = 18.05`，`round` 得 18，`idx = 17`，返回 `sorted_values[17] = 18`（已实际运行）。

- A：教科书式 nearest-rank 方法用的是**向上取整** `ceil(0.95 × 19) = 19`，返回 19。代码 docstring 自称 "nearest-rank"，但用的是四舍五入（而且 Python 的 `round` 是银行家舍入：n = 30 时 `round(28.5) = 28`，严格 nearest-rank 应取第 29 个）。18 只覆盖了 18/19 ≈ 94.7% 的样本，略低估了 p95。
- B：把下标 17 误当成返回值。
- C：nearest-rank 方法只返回数据中的实际值，不做插值。

### Q6 — 答案：A

pytest 全部通过时退出码为 0，有失败为 1，其它错误为其它非零值，正好对应 `shell_exit_zero` 的语义；讲义："This catches 'the tests must pass' tasks." 生产中应通过第 26 课的 sandbox 执行，并设置 `timeout_seconds`。

- B：pytest 默认不会生成结果文件，即便生成（如 junit xml），其中含时间戳，无法逐字比较。
- C：只检查测试函数存在，不检查测试是否通过。
- D 显然错误。

### Q7 — 答案：C

`load_fixture` 只是把 `spec["verifier"]["name"]` 原样存入 `verifier_name`，不做校验，所以 A 不对。到 `_verify` 时 `self.verifier_registry.get(...)` 返回 `None`，代码返回 `VerificationOutcome(False, "unknown verifier 'file_equal'")`（已实测）。该任务仍出现在报告里，每个 sample 记为失败，因此 B、D 都不对。

延伸思考：这种"静默失败"会被误读为 agent 能力差。更好的做法是在加载阶段就校验 verifier 名字和参数，夹具写错应当是**配置错误**而不是**评测失败**。

### Q8 — 答案：B

`run` 中写的是 `latencies.append(sample.latency_ms)`，数值完全来自 candidate 的返回值；`apply_known_fixes` 在函数内部自己用 `perf_counter` 计时。实测：一个 `sleep(0.05)` 却报告 `latency_ms=0.001` 的 candidate，报告中延迟就是 0.001。`cost_units` 同理是自报的。

- A 是"应该怎么做"，但代码没有这样做（见 Q10）。
- C、D 在代码中都不存在。

讲义写的是 "Latency is wall-clock per sample"，而代码里的"墙钟时间"只是 candidate 自报的值，二者不一致。

### Q9 — 参考答案

1. buggy 代码里 `count = 0` **本来就是 0**，提示"initialising the counter to 0"是误导；真正的 bug 在 `node = head.nxt`，应改为 `node = head`（expected 版本与 buggy 的唯一差别就是这一行）。实测：buggy 版本对 3 个节点的链表返回 2、对单节点返回 0。
2. `count = 1` 同样正确：从 `head.nxt` 开始数，再加上 head 本身。实测 3 个节点返回 3。但 `file_equals` 要求与 expected **逐字相同**，所以判为失败——**误杀**。同理，task_001 把 `range(1, n + 1)` 写成 `range(1, n+1)`（只少两个空格）也会被判失败（已实测）。
3. 改用 `shell_exit_zero`，执行断言：

```json
"verifier": {
  "name": "shell_exit_zero",
  "args": {
    "argv": ["python3", "-c",
      "from linked_list import Node, linked_list_length as L; assert L(None) == 0; assert L(Node(1)) == 1; assert L(Node(1, Node(2, Node(3)))) == 3"],
    "timeout_seconds": 10
  }
}
```

实测：参考答案通过（`command exited zero`），buggy 失败（`command exited 1`），`count = 1` 的写法也通过。要点：断言要覆盖边界（空链表、单节点）；`-c` 时当前工作目录（scratch）会被加入 `sys.path`，所以能直接 import；真实环境中应把测试文件放进 `tests/` 目录并通过 sandbox 运行 pytest，而不是把断言塞进 JSON。

### Q10 — 参考答案

1. 只有 `try/finally`，没有 `except`：scratch 会被清理，但异常会继续向上抛出，**整个 `run` 中止**，前面已完成任务的结果也全部丢失（实测抛出 `RuntimeError: agent crashed`）。对于真实 LLM agent（网络超时、解析失败），这几乎一定会发生。
2. 报告显示 0.001 ms——harness 无条件相信 candidate 自报（实测）。
3. 参考实现（已在本地以子类方式运行验证）：

```python
def _run_one(self, candidate, task, sample_index):
    scratch = self._prepare_scratch(task)
    try:
        start = time.perf_counter()
        try:
            sample, error = candidate(task, scratch), None
        except Exception as exc:                        # agent 崩溃 = 本 sample 失败
            sample, error = None, f"{type(exc).__name__}: {exc}"
        wall_ms = (time.perf_counter() - start) * 1000.0  # harness 自己计时
        if error is None:
            outcome = self._verify(task, scratch)
        else:
            outcome = VerificationOutcome(False, f"candidate raised {error}")
        return {
            "sample_index": sample_index,
            "latency_ms": round(wall_ms, 3),
            "self_reported_latency_ms": round(sample.latency_ms, 3) if sample else None,
            "cost_units": sample.cost_units if sample else 0.0,
            "passed": outcome.passed,
            "detail": outcome.detail,
            "notes": sample.notes if sample else "",
        }
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
```

实测输出：崩溃的 candidate 得到 `passed: False, detail: 'candidate raised RuntimeError: agent crashed'`；撒谎的 candidate 得到 `latency_ms: 50.2, self_reported_latency_ms: 0.001`。`run` 循环里改为 `samples.append(self._run_one(...))`，再从 samples 中汇总 passes / latencies / costs。

进一步：只捕获 `Exception`（不捕获 `KeyboardInterrupt`），这样人工中断仍然能停止评测；还应给 candidate 加超时（在线程或子进程中运行），否则一个卡死的 agent 会让整个评测挂起。

### Q11 — 参考答案

1. 实现：

```python
import math

def pass_at_k_unbiased(n, c, k):
    if n - c < k:          # 失败样本不足 k 个：任取 k 个必含通过的
        return 1.0
    return 1.0 - math.comb(n - c, k) / math.comb(n, k)
```

2. 实际计算结果：

| (n, c, k) | plug-in `1-(1-c/n)^k` | 无偏估计 |
|-----------|----------------------|---------|
| (5, 1, 5) | 0.6723 | 1.0000 |
| (10, 3, 5) | 0.8319 | 0.9167 |
| (20, 1, 5) | 0.2262 | 0.2500 |

k = 1 时两者都等于 c/n；c = 0 时都为 0。

3. n = k 时，"这 k 次中至少一次通过"可以直接观测：c ≥ 1 就是 1，否则是 0，与无偏估计一致。plug-in 公式回答的是另一个问题："假设单次成功率**恰好**是 p̂，再独立采样 k 次至少成功一次的概率"。由于 `(1-x)^k` 是凸函数，由 Jensen 不等式，plug-in 估计**系统性偏低**，k 越接近 n、p 越小，偏差越大。本节 harness 用 plug-in 公式并不算错，但应在报告中写明口径，跨团队比较时不能与 HumanEval 式的 pass@k 直接对比。

### Q12 — 参考答案

1. 每任务（k = 5）：

| 任务 | passes | pass_rate | pass_at_k = 1-(1-p)^5 |
|------|--------|-----------|----------------------|
| task_001 | 3 | 0.6 | 0.9898 |
| task_002 | 4 | 0.8 | 0.9997 |
| task_003 | 2 | 0.4 | 0.9222 |
| task_004 | 1 | 0.2 | 0.6723 |
| task_005 | 2 | 0.4 | 0.9222 |

2. `pass_at_1` = pass_rate 的平均 = (0.6+0.8+0.4+0.2+0.4)/5 = **0.48**；`pass_at_k` = 上表最后一列的平均 = 4.50624/5 ≈ **0.9012**。（与用 `random.seed(0)` 实际跑出的报告完全一致：`pass_at_1: 0.48, pass_at_k: 0.9012`。）注意代码中 `per_sample_pass_at_1` 对 k = 1 和 k > 1 分了两个分支，但两个分支的结果都等于 `pass_rate`，`min(1.0, ...)` 也是多余的。
3. 整体看：pass@5 = 0.90 很漂亮，但 pass@1 只有 0.48，单次调用一半以上会失败。单任务看：task_004 单次成功率仅 0.2，pass@5 却有 0.67。如果产品只调用一次 agent（没有 rerank 或自动重试），真实体验接近 pass@1，所以讲义强调："The harness shows both."

### Q13 — 参考回答要点

- **定义**：对一个任务独立采样 k 次，至少一次通过的概率；对任务集取平均。
- **计算**：
  - 简单 plug-in：`1 - (1 - p̂)^k`，本节代码采用；
  - 无偏估计（HumanEval）：每任务采样 n ≥ k 次、c 次通过，`1 - C(n-c,k)/C(n,k)`，方差更小、无偏，业界报告通常用它。
- **为什么两个都报**：
  - pass@1 反映"调用一次就成功"的概率，对应大多数线上场景；
  - pass@k 反映"能力上限"，以及采样 + 排序/验证（best-of-k、配合测试选优）能带来多少收益。讲义："The fix is sampling and ranking, not always more training. Pass@k makes that visible."；
  - 只看 pass@k 会夸大能力。讲义："if the model gets the right answer once in twenty tries you do not have a useful agent"（p = 0.05 时 plug-in pass@20 ≈ 0.64）。
- **加分点**：pass@k 的前提是"有一个可靠的选择器能挑出对的那个"，否则 pass@k 无法兑现；还要报告每任务的原始 c/n，便于观察方差。
- **常见误区**：采样 k 次后用同一个 k 计算并误以为是"观测值"；把 pass@k 和 temperature 分开讨论（k > 1 时通常需要较高 temperature 才有多样性）。

### Q14 — 参考回答要点

- **确定性第一**：同样的产出必须得到同样的判定，否则红灯变成"抛硬币"，回归无法定位（讲义配套 quiz："Determinism is what makes a regression detectable"）。因此避免依赖时间、网络、随机数、LLM 打分的 verifier；不得不用时要固定 seed 并多次投票。
- **三种 verifier 的误判风险**：
  - `file_equals`：最严格，适合"只有一种正确改法"的任务（如修拼写）；但空格、等价写法都会误杀（Q9）。
  - `regex_match`：允许多种写法，但只看文本、不看语义，容易误放（Q2：`return` 放进循环、注释里的代码）。
  - `shell_exit_zero` / 跑测试：检验**行为**，最接近"真的修好了"；风险是测试覆盖不足、测试本身不稳定（flaky）、命令有副作用（需 sandbox、超时）。
- **防止 reward hacking**：
  - 隐藏测试：agent 看不到 verifier 的具体内容。本节 candidate 拿到的是完整的 `FixtureTask`，包含 `expected_dir` 路径和 regex pattern，参考 candidate 正是靠读取 `expected/` 通过的；真实 agent 也能这么做，这是**答案泄漏**。
  - 保护测试文件：检查 agent 是否修改或删除了测试；在干净副本上重新运行测试。
  - 多 verifier 组合：行为测试 + 静态检查（如 diff 大小限制）。
- **加分点**：给每个夹具做"双向自检"：buggy 版本必须失败、expected 版本必须通过，再加若干"错误但看起来像对"的变体必须失败（变异测试思路）。

### Q15 — 参考回答要点

- **固定任务集**：夹具目录纳入版本控制，报告中写入任务 ID 列表和夹具内容哈希；两次运行的任务集不同就直接报错，而不是给出通过率（直接解决 per-task drift。本节报告只列出了 task_id，并没有做这种比较）。
- **每任务对比**：不只看总分，输出"pass → fail"和"fail → pass"的翻转列表；讲义举例："4% better on the loud task and 14% worse on the quiet one"。
- **采样与统计**：k > 1，报告 pass@1 的均值与置信区间；对同一批任务做配对比较（如 McNemar 检验或 bootstrap），而不是比较两个孤立的数字。
- **基线与 harness 自检**：每次 CI 先跑参考 candidate（必须 1.0）和 noop（必须 0.0），排除 harness 或夹具自身的问题（本节 `run_demo` 已经这样做）。
- **门槛策略**：设定阈值，例如 pass@1 下降超过置信区间、或任意"金标任务"由通过变为失败就阻断合并；同时监控 p95 延迟与成本。
- **可排查性**：保存每个 sample 的 `detail`、agent trace（第 28 课 OTel），回答"是模型变了还是 harness 变了"。
- **常见误区**：只在 CI 里跑 k = 1、任务数很少，噪声远大于要检测的效应。

### Q16 — 参考回答要点

- **隔离与安全**：每个 sample 在容器或第 26 课的 sandbox 中运行（文件系统、网络、资源限制）；`shell_exit_zero` 不能直接 `subprocess.run`。
- **防泄漏**：candidate 只拿到 goal 和工作目录，拿不到 `expected/` 路径和 verifier 参数；隐藏测试在 agent 结束后才注入。
- **健壮性**：candidate 异常、超时都记为失败而不是让评测崩溃（Q10）；harness 自己计时；设置 token / 美元预算上限。
- **规模**：任务级与 sample 级并行（进程池、分布式队列）；缓存仓库环境的构建；失败自动重试的只能是**基础设施错误**，不能是 agent 错误。
- **可复现**：固定模型版本、temperature、seed，记录 prompt 模板哈希；评测结果存成 JSONL，方便回放。
- **指标**：无偏 pass@k、置信区间、按任务类别（难度、语言、仓库）切片；成本与延迟的分布（p50/p95），而不只是均值。
- **夹具治理**：夹具准入检查（buggy 失败 / expected 通过 / 已知错误变体失败），定期清理 flaky 任务；参考 SWE-bench 的做法（讲义先修：阶段 14 · 19），用真实仓库的 issue 和对应的测试作为 verifier。

### Q17 — 参考回答要点

- **先看噪声**：50 个任务、p ≈ 0.6 时，pass@1 的标准误约为 `sqrt(0.6 × 0.4 / 50) ≈ 0.069`（已计算），4 个点远小于一个标准误，单看这两个数字不能断定是回归。
- **做配对分析**：同一批任务，列出翻转——比如 5 个任务由通过变失败、3 个由失败变通过；用 McNemar 检验或对任务做 bootstrap 估计差值的置信区间。
- **增加采样**：每任务 k = 5～10，用 pass_rate 代替单次 0/1，可以大幅降低方差；如果 agent 本身不稳定（同一任务时好时坏），k = 1 的比较几乎没有意义。
- **检查 harness 本身**：任务集是否相同（per-task drift）、参考 candidate 是否仍然是 1.0、有无 verifier 报 "unknown verifier" 或超时之类的基础设施失败。
- **看分布**：下降是否集中在某一类任务（讲义的 "quiet task"）；如果是关键类别的稳定下降，即便总体不显著，也值得阻断。
- **结论**：不是"回滚"或"不回滚"二选一，而是"扩大样本、做配对检验，再按预先约定的门槛决策"。

---

## 六、关联知识点

### 前置知识
- [阶段 19 · 25 综合项目第 25 课：Verification Gates 与观察预算](../../25-verification-gates-observation-budget/docs/zh.md)：讲义先修要求；"确定性检查返回 true/false"的思想与 gate chain 一致。
- [阶段 19 · 26 综合项目第 26 课：带拒绝列表与路径隔离的 Sandbox 执行器](../../26-sandbox-runner-denylist/docs/zh.md)：`shell_exit_zero` 在生产中应通过这个 sandbox 执行（本节代码为了简化直接用了 `subprocess.run`）。
- [阶段 14 · 30 评估驱动的 Agent 开发](../../../14-agent-engineering/30-eval-driven-agent-development/docs/zh.md)：先有 eval、再迭代 agent 的方法论。
- [阶段 14 · 19 基准评测：SWE-bench、GAIA、AgentBench](../../../14-agent-engineering/19-benchmarks-swebench-gaia/docs/zh.md)：本节夹具是 SWE-bench 式"仓库 + 测试"任务的极简版。
- [阶段 14 · 38 Verification Gates](../../../14-agent-engineering/38-verification-gates/docs/zh.md)：verifier 与 gate 的设计原则。
- [阶段 11 · 10 Evaluation 与 LLM 应用测试](../../../11-llm-engineering/10-evaluation/docs/zh.md)：LLM 应用评测的整体框架。

### 本节被哪些后续内容用到
- [阶段 19 · 28 综合项目第 28 课：通过 OTel GenAI Spans 与 Prometheus Metrics 实现 Observability](../../28-observability-otel-traces/docs/zh.md)：讲义称会为每次 harness 运行加上 OTel trace。
- [阶段 19 · 29 综合项目第 29 课：基于 Harness 的端到端 Coding Agent](../../29-end-to-end-coding-task-demo/docs/zh.md)：沿用本节的夹具结构（buggy + expected），端到端修复一个 off-by-one bug。
- [阶段 19 · 41 综合项目第 41 课：完整 Evaluation 流程](../../41-eval-pipeline/docs/zh.md)：更完整的评测流水线。
- [阶段 19 · 72 代码执行评估指标](../../72-code-exec-metric/docs/zh.md)：以"执行代码看结果"作为指标，对应 `shell_exit_zero` 的思路。
- [阶段 19 · 75 端到端评估执行器](../../75-end-to-end-eval-runner/docs/zh.md)：把评测执行器做成端到端系统。
- [阶段 10 · 10 Evaluation：基准、Evals 与 LM Harness](../../../10-llms-from-scratch/10-evaluation/docs/zh.md)、[阶段 19 · 49 语言模型 Evaluation Harness](../../49-lm-eval-harness/docs/zh.md)：模型层面的评测 harness，与本节的 agent 层面评测相互对照。

### 延伸关键词
`pass@k 无偏估计` · `HumanEval` · `SWE-bench` · `fixture validity（夹具自检）` · `false positive / false negative verifier` · `reward hacking` · `hidden tests` · `test leakage` · `nearest-rank percentile` · `McNemar test` · `bootstrap 置信区间` · `flaky test` · `regression tracking`
