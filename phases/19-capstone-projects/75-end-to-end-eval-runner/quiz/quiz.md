# 测验 · 端到端评估执行器（End-to-End Eval Runner）

> **阶段 19 · 综合项目 · 第 75 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py)（测试：[code/tests/test_runner.py](../code/tests/test_runner.py)） ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Runner 是"胶水层" | 第 70～74 节各管一件事（任务规范、经典指标、代码执行、校准、排行榜），runner 只负责**组合**，不复制任何一层的逻辑 |
| 2 | `ModelAdapter` 接口 | 只有一个方法 `generate(prompt, task) -> Generation`；任何模型（mock、本地、API）只要实现它就能接入 |
| 3 | `Generation` 数据类 | `text` + 可选的 `confidence`（自报概率）、`token_nll`（生成 token 的负对数似然之和）、`token_count` |
| 4 | 单遍评分循环 | render prompt → 调 adapter（计时）→ post_process → 按 `metric_name` 分派到第 71 节或第 72 节 → 生成 `TaskResult` → 记录 `(confidence, correct)` |
| 5 | `correct` 的判定 | `exact_match / accuracy / code_exec` 要求满分（代码中是 `>= 0.999999`），`f1 / bleu_4 / rouge_l` 等分级指标用阈值 0.5 |
| 6 | 并行执行 | `ThreadPoolExecutor` + `as_completed`；瓶颈是网络 I/O，线程足够；`parallel=False` 让测试按固定顺序执行 |
| 7 | 结果顺序的确定性 | 并行完成顺序不固定，`run_eval` 最后按 `(model_id, task_id)` 排序；但**有状态的随机 adapter 仍会因调用顺序不同而得到不同结果** |
| 8 | 聚合层 | `TaskResult → EvalRun`，交给第 74 节 `aggregate`（均值、bootstrap CI、win rate）和 `pairwise_diffs`（配对 bootstrap） |
| 9 | 校准与困惑度块 | 每个模型一份 ECE/Brier（第 73 节 `CalibrationReport`）和 perplexity（`PerplexityResult.from_token_nll`），与排行榜并列而不参与排名 |
| 10 | 自终止 demo | 3 个 mock adapter × 10 个任务；`rule_based` 必须排第一才返回退出码 0，否则返回 1/2/3 |

### 核心技能（能动手做到）

- [ ] 说清楚 runner 从 JSONL 到排行榜的完整数据流，以及每一步调用的是哪一节的哪个函数
- [ ] 实现一个新的 `ModelAdapter`（例如包装真实 API，或在已有 adapter 外加缓存/重试），并接入 `run_eval`
- [ ] 手算一个模型的 ECE、Brier 和 perplexity，并与 runner 输出对照
- [ ] 解释为什么 `NoisyAdapter` 在并行模式下结果不可复现，并把它改成"与执行顺序无关"的确定性实现
- [ ] 读懂排行榜中的 95% CI 与配对 bootstrap 的 `significant` 字段，判断两个模型的差距是否可信
- [ ] 指出讲义描述与代码实际行为的不一致（错误信封、"random adapter"、JSON 报告输出等）

---

## 二、基础自测（选择题）

**Q1.** 本节 `ModelAdapter` 接口的"最小表面"是：

- A. `load_weights()`、`generate()`、`save_weights()` 三个方法
- B. `complete()`、`embed()`、`classify()`、`summarise()` 四个方法
- C. 一个 `__call__(prompt) -> str`，返回纯文本即可，置信度由 runner 自己估计
- D. 一个 `generate(prompt, task) -> Generation`，`Generation` 中除 `text` 外的字段都有默认值

**Q2.** runner 用 `ThreadPoolExecutor`（线程）而不是 `ProcessPoolExecutor`（进程）来并行跑任务，讲义给出的主要理由是：

- A. 真实模型调用的瓶颈是网络 I/O，等待期间 GIL 会释放，线程足够；代码执行任务自己会另起子进程
- B. 线程能绕过 GIL，让 CPU 密集的指标计算真正并行
- C. 进程池无法在 Windows 上使用
- D. 线程池能保证任务按提交顺序完成

**Q3.** 根据 `_correct_from_score`，下列哪一个结果会被记为 `correct=True`？

- A. `code_exec` 任务通过了 3 条断言中的 2 条（score ≈ 0.667）
- B. `exact_match` 任务得分 0.99
- C. `rouge_l` 任务得分 0.5
- D. `f1` 任务得分 0.49

**Q4.** demo 中 `NoisyAdapter` 对全部 10 个任务都报告 `confidence=0.85`，实际答对 3 个。它的 ECE（10 个分箱）是：

- A. 0.15
- B. 0.55
- C. 0.85
- D. 0.5125

**Q5.** `_load_sibling` 用 `importlib.util.spec_from_file_location` 加载第 70～74 节的代码，并给每个模块起名 `_sibling_<目录名>`，而不是直接 `sys.path.insert` 后 `import main`。最根本的原因是：

- A. `importlib` 比 `import` 语句快
- B. `import main` 会执行模块里的 `demo()`
- C. 第 70～74 节的目录名含 `-`，不是合法的包名，但文件名 `main.py` 本身没有问题
- D. 五个兄弟模块的文件名**都叫 `main.py`**，用同一个模块名导入会在 `sys.modules` 里互相覆盖（而且 runner 自己也叫 `main`）

**Q6.** `RuleBasedAdapter` 对每个 token 记录的负对数似然是 0.8。perplexity 块中它的困惑度约为：

- A. 2.23
- B. 0.80
- C. 0.45
- D. 12.18

**Q7.** `run_eval` 在并行分支里用 `as_completed` 收集结果，最后又执行了 `results.sort(key=lambda r: (r.model_id, r.task_id))`。这一行的作用是：

- A. 让排行榜按模型名排序
- B. `as_completed` 按"谁先完成"返回，顺序不固定；排序后结果列表和校准缓冲区的顺序与执行方式无关
- C. 让 `ThreadPoolExecutor` 按顺序调度任务
- D. 去除重复的 `(model_id, task_id)`

**Q8.** demo 输出中 `biased` 与 `noisy` 的均分都是 0.30，但 `biased` 排在第 2、`noisy` 排在第 3。原因是：

- A. `biased` 的 ECE 更低，排行榜用 ECE 做次级排序键
- B. `biased` 的 win rate 更高
- C. 第 74 节 `aggregate` 只按 `mean_score` 降序做**稳定排序**，并列时保留原顺序；而 `_by_model` 的插入顺序来自 runner 已按 `model_id` 字母序排好的结果（`biased` < `noisy`）
- D. 配对 bootstrap 显示 `biased` 显著优于 `noisy`

---

## 三、动手 / 代码题

**Q9.** 阅读 `NoisyAdapter`：

```python
class NoisyAdapter(ModelAdapter):
    model_id = "noisy"

    def __init__(self, seed: int = 0) -> None:
        self.rng = random.Random(seed)
        self.token_stats: list[tuple[float, int]] = []

    def generate(self, prompt: str, task: TaskSpec) -> Generation:
        if self.rng.random() < 0.25 and task.targets:
            text = task.targets[0]
        ...
```

demo 用 `parallel=True, max_workers=6` 调用 `run_eval`。

1. 同样的 `seed=1`，多次运行 demo，`noisy` 答对的任务集合会变吗？为什么？
2. `tests/test_runner.py` 里有 `test_parallel_sequential_match`，为什么它没有发现这个问题？
3. 改写 `generate`，让结果与调用顺序无关（提示：随机数应由 `(seed, task_id)` 决定）。

**Q10.** 讲义说："If any of those break, the runner exits non-zero with a structured error in the JSON envelope." 又说清洁运行要求"rule-based adapter strictly above the random adapter"。对照 `demo()` 与 `EvalReport`：

1. 列出讲义描述与代码实际行为的**至少三处**不一致。
2. 修改 `demo()`：任何检查失败时，把 `report.error` 设为结构化信息并把完整 JSON 信封打印出来，再返回非零退出码。

**Q11.** demo 中 `BiasedAdapter` 的逐任务结果如下（`conf` 为置信度，`correct` 为判定结果）：

| 任务 | conf | correct |
|------|------|---------|
| arith_001、arith_002 | 0.9 | True |
| mcq_001 | 0.4 | True（"Answer: B" 恰好命中） |
| 其余 7 个任务 | 0.4 | False |

1. 手算它的 ECE（10 个等宽分箱）和 Brier score。
2. 它的 `populated_bins` 是几？
3. 为什么一个"只会算术"的模型在 `mcq` 类别上得到了 0.5 的均分？这对设计 baseline 有什么启示？

**Q12.** 讲义"Going further"提到生产系统需要"a results cache keyed by `(task_id, model_id, model_version)`"。请写一个 `CachingAdapter`，它包装任意 `ModelAdapter`，命中缓存时不再调用底层模型；并说明：缓存命中时 `token_stats`（困惑度的数据来源）应该怎么处理，才不会让同一个 adapter 的困惑度统计出错？

---

## 四、面试高频题

**Q13.**（基础必考）设计一个 LLM 评估框架时，你会怎样分层？为什么本节要把"模型调用"抽象成一个只有 `generate` 方法的 adapter？

**Q14.**（原理深挖）校准（calibration）需要二值的 `correct` 标签，但 ROUGE-L、BLEU、F1 都是连续分数。本节怎么处理？这种做法有什么问题？LLM 的"置信度"又可以从哪里来？

**Q15.**（工程实践）你要用这个 runner 评估 3 个商业 API 模型、每个 5,000 道题。并行策略、限流、失败重试、可复现性分别怎么做？本节代码离这个目标还差什么？

**Q16.**（场景设计）团队每周发布一个新模型版本，需要和上周版本以及两个竞品对比，并在 PR 里贴出结论。请设计这条评估流水线（数据、执行、缓存、统计、报告、门禁）。

**Q17.**（追问型）demo 中 `biased` 和 `noisy` 均分都是 0.30，95% CI 都是 `[0.00, 0.60]`，配对差值 CI 为 `[-0.402, +0.303]`。产品经理问"哪个更好"，你怎么回答？如果一定要分出高下，应该怎么做？

---

## 五、参考答案与解析

### Q1 — 答案：D

讲义："The adapter is the seam between the runner and any model. The interface is intentionally small." 代码中 `ModelAdapter` 只有类属性 `model_id` 和 `generate(prompt, task) -> Generation`，`Generation` 的 `confidence=0.5`、`token_nll=0.0`、`token_count=0` 都有默认值，所以最简单的 adapter 只需返回文本。

- A 是训练框架的接口，评估不需要加载/保存权重；
- B 把多种任务能力绑进接口，任何只会生成文本的模型都无法满足；
- C 错在"置信度由 runner 估计"——runner 无法从纯文本得出置信度，校准块需要 adapter 自报 `confidence`。

### Q2 — 答案：A

讲义："Threads are sufficient because the bottleneck for real model calls is network I/O. The code-exec path spawns its own subprocess inside the task and the executor only schedules the wait." 线程在等待网络或子进程时会释放 GIL。

- B 错：线程不能绕过 GIL，CPU 密集的 Python 计算（如 LCS 动态规划）在线程里不会真正并行；
- C 错：进程池在 Windows 上可用（只是需要 `if __name__ == "__main__"` 保护）；
- D 错：线程池不保证完成顺序，所以代码最后才要排序（见 Q7）。

### Q3 — 答案：C

```python
def _correct_from_score(metric_name: str, score: float, threshold: float = 0.5) -> bool:
    if metric_name in ("exact_match", "accuracy", "code_exec"):
        return score >= 0.999999
    return score >= threshold
```

`rouge_l` 是分级指标，`0.5 >= 0.5` 为 True。A：`code_exec` 要求全部断言通过，部分通过（2/3）记为 False；B：`exact_match` 要求满分；D：0.49 < 0.5。注意 `0.999999` 而不是讲义说的 `1.0`，是为了容忍浮点误差（例如 `3/3` 算出来恰好是 1.0，但其它累加方式可能得到 0.9999999）。

### Q4 — 答案：B

所有样本都落在同一个分箱（0.8–0.9），该箱平均置信度 0.85，准确率 0.3，ECE = 1.0 × |0.85 − 0.3| = **0.55**。实际运行输出 `noisy ... ECE 0.550`。

- D（0.5125）是它的 **Brier score**：`0.3 × 0.15² + 0.7 × 0.85² = 0.5125`；
- A（0.15）是答对样本的单点误差；C 是置信度本身。

这正是讲义所说的"overconfident, often wrong"：置信度远高于正确率。

### Q5 — 答案：D

第 70～74 节的代码文件都叫 `main.py`，runner 自己也叫 `main.py`。如果都用 `import main`，Python 会在 `sys.modules["main"]` 里只保留第一个被导入的模块，后续导入直接拿到缓存，五个模块互相"串台"。`_load_sibling` 给每个模块一个唯一名字 `_sibling_70_task_spec_format` 等，并注册进 `sys.modules`。

- A 不是理由；
- B 错：各兄弟模块的 `demo()` 都放在 `if __name__ == "__main__":` 之下，被导入时不会执行；
- C 只说对了一半：目录名含 `-` 确实不能当包名，但这不是"最根本"的原因——即使目录名合法，同名 `main` 的冲突仍在。

### Q6 — 答案：A

`PerplexityResult.from_token_nll` 计算 `exp(总 NLL / 总 token 数)`。`RuleBasedAdapter` 每个 token 的 NLL 都是 0.8，平均也是 0.8，`exp(0.8) ≈ 2.2255`（实际运行：`perplexity: 2.2255, total_tokens: 43`）。

- B 是平均 NLL 本身，不是困惑度；
- C 是 `exp(-0.8)`，符号反了；
- D 是 `noisy` 的困惑度 `exp(2.5) ≈ 12.18`。

### Q7 — 答案：B

`as_completed(futures)` 按完成先后产出 future，任务耗时不同（尤其是 code_exec 要起子进程）时顺序每次都可能不同。排序之后，`results` 和由它填充的 `calibration_buf` 顺序固定，下游的 bootstrap（固定 `seed=7`）才能得到可复现的 CI。

- A：排行榜是第 74 节按均分排序的，与这一行无关；
- C：排序发生在全部完成之后，不影响调度；
- D：排序不去重（重复键会在第 74 节 `_validate_runs` 中报错）。

### Q8 — 答案：C

第 74 节 `aggregate` 的最后一步是 `rows.sort(key=lambda r: r.mean_score, reverse=True)`，Python 的排序是稳定的，并列项保持原相对顺序。`_by_model` 用字典按首次出现顺序收集模型，而 runner 传进来的 `EvalRun` 已经按 `(model_id, task_id)` 排序，所以顺序是 `biased → noisy → rule_based`。排完序 `rule_based` 第一，`biased`、`noisy` 并列 0.30 时 `biased` 在前。

- A：排行榜不看 ECE（ECE 只是 runner 在 markdown 里额外拼上去的列）；
- B：两者 win rate 都是 0.30；
- D：配对差值 CI `[-0.402, +0.303]` 跨过 0，`significant=no`。

换句话说，**这个"第 2 名"只是字母序的产物**，并不说明 `biased` 更好。

### Q9 — 参考答案

1. **会变**。`self.rng` 是 adapter 上的共享状态，每次 `generate` 都消耗一次随机数。并行时 6 个线程谁先调用 `generate` 不确定，于是"第 k 次随机数"落到哪个任务上每次都不同。我们用同一个 `seed=1` 跑了 30 次并行 demo，`noisy` 得分 > 0 的任务集合出现了 10 种不同组合，例如 `{arith_001, cls_001, sum_002}`（9 次）、`{arith_001, mcq_001, sum_002}`（5 次）、`{mcq_002, sum_002}`（2 次）……而顺序执行时固定是 `{arith_001, sum_001, sum_002}`。所以 demo 中 `noisy` 的均分会在 0.2～0.3 之间跳动，与 `biased` 的相对名次也可能翻转。
2. 该测试只用了 `RuleBasedAdapter`，它是纯函数（输出只取决于 task），在任何顺序下结果都一样。测试名声称验证"parallel-vs-sequential equivalence"，但没有覆盖有状态的 adapter。
3. 让随机数由 `(seed, task_id)` 决定，而不是由调用次数决定：

```python
def generate(self, prompt: str, task: TaskSpec) -> Generation:
    rng = random.Random(f"{self.seed}:{task.task_id}")   # 每个任务独立、可复现
    if rng.random() < 0.25 and task.targets:
        text = task.targets[0]
    else:
        ...
```

（`__init__` 中保存 `self.seed = seed`。）`random.Random` 接受字符串种子并以确定的方式哈希，不受 `PYTHONHASHSEED` 影响；不要用 `hash(task.task_id)`，字符串的 `hash` 每个进程都不同。我们实测这个版本并行 20 次与顺序执行的结果全部一致。另外 `token_stats.append` 在多线程下依赖 CPython 的 GIL 才安全，严格的做法是让 `Generation` 携带 `token_nll/token_count`，由 runner 汇总，而不是让 adapter 自己维护列表（见 Q12）。

### Q10 — 参考答案

1. 不一致之处：
   - **错误信封**：`EvalReport` 有 `error` 字段，但代码里**从未给它赋值**；检查失败时 `demo()` 只 `print("ERROR: ...")` 并返回 1/2/3。
   - **JSON 报告**：学习目标说"Output both a JSON report and a markdown table"，但 demo 只打印 markdown 表、`summary` 的 JSON 和 pairwise 文本，没有输出完整信封（`report.to_json()` 只在测试里被调用）。
   - **"random adapter"**：三个 mock 是 `rule_based / noisy / biased`，不存在 random adapter；代码的检查是"`rule_based` 排第一"且"`rule_based` 不在最后"，第二条在第一条成立时必然成立（模型数 > 1 时），是冗余检查。
   - **验证失败**：`_load_fixture_tasks` 在校验出错时 `raise RuntimeError`，进程以未捕获异常退出（码 1 + traceback），不是"结构化错误"。
   - **信封字段**：讲义示例 JSON 没有 `perplexity` 字段，代码有；讲义 summary 示例没有 `task_runs`，代码有。
   - **并发数**：讲义说"worker count defaults to the smaller of eight and the task count"，代码是 `min(max_workers, len(work))`，`work` 是"模型数 × 任务数"，demo 还把 `max_workers` 设成了 6。
2. 参考改法：

```python
def demo() -> int:
    try:
        tasks = _load_fixture_tasks()
    except RuntimeError as exc:
        err = EvalReport([], [], {}, {}, {"tasks": 0, "models": 0}, error=f"validation: {exc}")
        print(err.to_json())
        return 4
    ...
    report = render_report(...)
    checks = []
    if not report.leaderboard:
        checks.append(("empty_leaderboard", 1))
    elif report.leaderboard[0]["model_id"] != "rule_based":
        checks.append((f"expected rule_based at top, got {report.leaderboard[0]['model_id']}", 2))
    if checks:
        report.error = json.dumps({"failed": [c[0] for c in checks]})
        print(report.to_json())
        return checks[0][1]
    print(render_markdown_block(report))
    print(report.to_json())
    return 0
```

要点：失败时依然输出一个**合法的 JSON 信封**（下游 CI 可以解析），退出码区分失败类型；成功时同时给出 markdown 和 JSON。

### Q11 — 参考答案

1. **ECE**：置信度 0.9 落在第 9 箱（0.9–1.0），2 个样本，准确率 1.0，差距 0.1；置信度 0.4 落在第 4 箱（0.4–0.5），8 个样本，准确率 1/8 = 0.125，差距 0.275。
   `ECE = 0.2 × 0.1 + 0.8 × 0.275 = 0.02 + 0.22 = 0.24`。
   **Brier**：`[2 × (0.9−1)² + 1 × (0.4−1)² + 7 × (0.4−0)²] / 10 = (0.02 + 0.36 + 1.12) / 10 = 0.15`。
   与实际输出 `biased ... ECE 0.240, Brier 0.150` 一致。
2. `populated_bins = 2`（只有 0.4 和 0.9 两个箱有样本）。只有 10 个样本时 ECE 的估计非常粗糙，这是 demo 规模的局限。
3. `BiasedAdapter` 在非擅长类别上对 MCQ 固定回答 `"Answer: B"`，而 `mcq_001` 的正确答案恰好是 B，于是 mcq 类别均分 = (1 + 0) / 2 = 0.5。启示：**固定答案或随机猜测也有非零分**（4 选项 MCQ 的随机基线是 0.25），评估报告应同时给出 chance-level baseline；题目答案的字母分布要均衡，否则"永远选 B"这样的退化策略会被高估。

### Q12 — 参考答案

```python
class CachingAdapter(ModelAdapter):
    def __init__(self, inner: ModelAdapter, model_version: str, cache: dict | None = None):
        self.inner = inner
        self.model_id = inner.model_id          # 排行榜上仍显示底层模型名
        self.model_version = model_version
        self.cache = cache if cache is not None else {}
        self.token_stats: list[tuple[float, int]] = []
        self.hits = 0

    def generate(self, prompt, task):
        key = (task.task_id, self.model_id, self.model_version, hash_prompt(prompt))
        gen = self.cache.get(key)
        if gen is None:
            gen = self.inner.generate(prompt, task)
            self.cache[key] = gen
        else:
            self.hits += 1
        self.token_stats.append((gen.token_nll, gen.token_count))   # 用缓存的 Generation 记录
        return gen
```

要点：

- 缓存键除了讲义说的 `(task_id, model_id, model_version)`，最好再加上**渲染后 prompt 的哈希**（以及采样参数），因为改了 few-shot 或模板后旧结果不能复用。`hash_prompt` 应使用 `hashlib.sha256`，不要用进程相关的 `hash()`。
- **`token_stats` 要从 `Generation` 本身取**，命中缓存时也记录一次，这样每个任务恰好贡献一条统计；绝不能依赖 `inner.token_stats`（命中时底层没被调用，列表不增长，困惑度会只统计未命中的子集）。
- 更干净的做法是改 runner：在 `_score_one` 里直接把 `gen.token_nll / gen.token_count` 放进 `TaskResult`，由 runner 聚合困惑度，adapter 不再维护可变列表。这也顺带消除了 Q9 提到的线程安全隐患。
- 共享缓存在多线程下应加锁或使用线程安全的存储（如 SQLite、磁盘 KV）。

### Q13 — 参考回答要点

- **分层**（与第 70～75 节对应）：
  1. 任务规范层：JSONL schema + 校验（字段、类别—指标合法组合、MCQ 目标格式）；
  2. Prompt 渲染与后处理：few-shot 拼接、`extract_letter / extract_code_block` 等；
  3. 模型适配层：adapter 屏蔽供应商差异；
  4. 指标层：exact_match/F1/BLEU/ROUGE-L、代码执行（沙箱子进程 + 超时）；
  5. 校准/困惑度层；
  6. 聚合层：均值、bootstrap CI、win rate、配对显著性；
  7. 报告层：JSON + markdown。
- **为什么只要一个 `generate`**：接口越小，接入新模型的成本越低（讲义："write thirty lines of glue"）；重试、缓存、限流、流式等都可以作为**包装 adapter** 叠加（装饰器模式），不污染 runner 和指标层。
- 加分点：runner "metric-agnostic and provider-agnostic"，每一层可以独立测试和演进；`EvalRun` 作为层间契约，排行榜的算法变化不需要动 runner。
- 常见误区：把指标计算写进 adapter，或在 runner 里内联排行榜逻辑，导致每加一个模型/指标都要改多处。

### Q14 — 参考回答要点

- **本节做法**：`_correct_from_score` 对分级指标用 `score >= 0.5` 二值化，对 exact_match 类要求满分；然后 `(confidence, correct)` 进入 ECE/Brier。
- **问题**：
  - 阈值 0.5 是任意的，不同指标的分数尺度不同（BLEU 对正确的意译也常常低于 0.5，ROUGE-L 则相对宽松），同一阈值对不同指标的"严格程度"不一致；
  - 二值化丢掉了分数信息；样本少时 ECE 分箱噪声很大（本节每个模型只有 10 个样本、1～2 个非空箱）；
  - 讲义说"the runner does not expose a public override"，阈值无法按任务配置。
- **改进**：按指标配置阈值或在 task 元数据里声明；对连续分数可以直接把 `score` 当作软标签计算 Brier；样本量足够后再看 ECE，并报告分箱数和每箱样本数。
- **LLM 置信度来源**：答案 token 的 log-prob（如 MCQ 选项字母的概率）；多次采样的一致性（self-consistency 比例）；让模型口头报告置信度（verbalized confidence，通常过度自信）；外部打分器。本节 mock 用的是写死的常数。
- 加分点：说明 perplexity 与任务分数是两个维度——它衡量模型对自己输出的"惊讶度"，本节 mock 的 NLL 是按 token 数乘常数伪造的，只用于演示管道。

### Q15 — 参考回答要点

- **并行**：I/O 密集，用线程池或 asyncio；并发数按供应商的 RPM/TPM 限额设置，而不是固定 8。CPU 密集的指标（LCS、BLEU）可以放到进程池或在生成全部完成后批量算。
- **限流与重试**：在 adapter 层实现令牌桶限流；对 429/5xx 做指数退避 + 抖动重试，设最大重试次数；区分可重试错误与不可重试错误（如内容过滤、参数错误）。
- **失败隔离**：本节 `fut.result()` 遇到 adapter 抛异常会让整个 `run_eval` 崩溃；生产中应捕获单任务异常，记为 `score=0` 并带 `detail`，同时在 summary 中统计失败率。
- **可复现**：temperature=0 或固定 seed；记录 `model_version`、prompt 模板哈希、采样参数；adapter 不持有跨任务的随机状态（见 Q9）。
- **缓存与成本**：结果缓存（见 Q12）让中断后可续跑；成本账本按任务记录输入/输出 token 和美元。
- **本节差距**：没有重试、缓存、限流、成本账本、失败隔离、流式结果写盘；这些正是讲义"Going further"列出的。

### Q16 — 参考回答要点

- **数据**：版本化的任务集（JSONL + 校验），按能力分类；保留一部分私有集防止过拟合/污染；每个任务固定 prompt 模板版本。
- **执行**：每个模型一个 adapter；结果缓存键 `(task_id, model_id, model_version, prompt_hash)`，竞品与上周版本的结果直接复用，只跑新版本。
- **统计**：均值 + bootstrap CI；对"新版本 vs 上周版本"做**配对**比较（同一任务的分差），报告配对 CI 和是否显著；按类别拆分，发现"总分持平但某类别回退"的情况。
- **报告**：JSON 存档（可追溯），markdown 表贴到 PR；包含 ECE/Brier 与成本、延迟。
- **门禁**：设定规则，如"任一核心类别显著回退 → 阻止发布"；"总体均分配对 CI 下界 < −0.02 → 人工复核"。
- 加分点：任务数要足够大，否则 CI 太宽、门禁毫无意义（本节 10 题的 CI 宽达 0.6）；定期人工抽检自动指标与人工判断的一致性。

### Q17 — 参考回答要点

- **结论**：在这 10 道题上**无法区分**。两者均值相同，配对差值的 95% CI `[-0.402, +0.303]` 包含 0，`significant=no`；排行榜上 `biased` 排第二只是并列时按模型名字母序的结果（见 Q8）。
- **更细的信息**：两者的能力分布完全不同——`biased` 算术满分、摘要几乎 0；`noisy` 在并行模式下答对的题是随机的。按类别看比看总分更有意义；在需要算术的场景 `biased` 明显更好。
- **另一个维度**：校准。`biased` 的 ECE 0.24、Brier 0.15，远好于 `noisy` 的 0.55 / 0.51；如果产品要用置信度做拒答或路由，`biased` 更可用。
- **要分出高下**：扩大任务数（CI 宽度大约按 `1/√n` 缩小）；使用配对设计；预先定义主要指标和最小有意义差距；对随机模型多次运行取平均。
- 常见误区：看到排名先后就说"A 比 B 好"；把 bootstrap CI 重叠与否当作唯一判断标准（应看配对差值的 CI）。

---

## 六、关联知识点

### 前置知识
- [阶段 19 · 70 任务规范格式](../../70-task-spec-format/docs/zh.md)：`TaskSpec`、校验规则、`render_prompt`、`post_process` 和 10 个 fixture 任务都来自这里。
- [阶段 19 · 71 经典评估指标](../../71-classical-metrics/docs/zh.md)：`metrics_mod.score` 分派的 exact_match / F1 / BLEU-4 / ROUGE-L。
- [阶段 19 · 72 代码执行评估指标](../../72-code-exec-metric/docs/zh.md)：`run_candidate` 的沙箱子进程、超时与部分得分。
- [阶段 19 · 73 Perplexity 与 Calibration](../../73-perplexity-calibration/docs/zh.md)：ECE、Brier、`PerplexityResult`。
- [阶段 19 · 74 排行榜汇总](../../74-leaderboard-aggregation/docs/zh.md)：bootstrap CI、win rate、配对差值与稳定排序。
- [阶段 19 · 27 使用固定测试任务的评估 Harness](../../27-eval-harness-fixture-tasks/docs/zh.md)：fixture 驱动的评估思路。

### 本节被哪些后续内容用到
- [阶段 19 · 49 语言模型 Evaluation Harness](../../49-lm-eval-harness/docs/zh.md)：面向语言模型的评估 harness，可与本节对照。
- [阶段 19 · 41 完整 Evaluation 流程](../../41-eval-pipeline/docs/zh.md)：微调后的模型评估流程。
- [阶段 10 · 10 Evaluation：基准、Evals 与 LM Harness](../../../10-llms-from-scratch/10-evaluation/docs/zh.md)：真实基准与 LM Harness 的背景。
- [阶段 11 · 10 Evaluation 与 LLM 应用测试](../../../11-llm-engineering/10-evaluation/docs/zh.md)：应用层的 eval 与回归测试。
- [阶段 14 · 30 评估驱动的 Agent 开发](../../../14-agent-engineering/30-eval-driven-agent-development/docs/zh.md)：把 eval 当作开发门禁。
- [阶段 17 · 21 对 LLM Features 进行 A/B 测试](../../../17-infrastructure-and-production/21-ab-testing-llm-features/docs/zh.md)：线上对比与统计显著性。

### 延伸关键词
`ModelAdapter / provider-agnostic` · `ThreadPoolExecutor / as_completed` · `ECE / Brier score` · `perplexity` · `paired bootstrap` · `win rate` · `chance-level baseline` · `results cache` · `exponential backoff` · `lm-evaluation-harness` · `HELM` · `deterministic seeding`
