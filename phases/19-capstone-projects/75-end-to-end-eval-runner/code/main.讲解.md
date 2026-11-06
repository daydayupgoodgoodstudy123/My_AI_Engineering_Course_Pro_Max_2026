# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 75 节 端到端评估执行器 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（在 `code/` 目录下）；测试：`python -m pytest -q tests` 或 `python -m unittest discover -s tests` ｜ **依赖**：标准库 + `numpy`（第三方，由第 73、74 节模块使用）；**运行时依赖同目录树下第 70～74 节的 `code/main.py`**，单独拷贝本文件无法运行

---

## 1. 这份代码在考察什么

第 70～74 节分别实现了评估系统的五个零件：任务规范（70）、经典指标（71）、代码执行指标（72）、困惑度与校准（73）、排行榜聚合（74）。本节不写新算法，而是把它们**串成一条流水线**：

1. **集成方式**：如何在五个同名 `main.py` 之间做模块加载而不冲突（`_load_sibling`）。
2. **适配器边界**：用一个只有 `generate` 的 `ModelAdapter` 把"模型"与"评估"解耦。
3. **单遍评分循环**：一次调用同时产出任务分数、`correct` 标签和置信度，分别喂给排行榜和校准层。
4. **并行与确定性**：`ThreadPoolExecutor` 并行，结果排序，`parallel=False` 供测试使用。
5. **报告信封**：leaderboard / pairwise / calibration / perplexity / summary 五块组成的 JSON，加一张 markdown 表。
6. **自终止 demo**：用三个 mock adapter 验证"最好的模型排第一"，用退出码表达成败。

> 一句话：**runner 只做编排，每一层的逻辑都留在它自己的模块里**——读懂这个边界，比读懂任何一个指标都重要。同时要看清 demo 的"可复现"其实有漏洞（共享随机状态 + 并行）。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `_load_sibling` | 函数 | 按相对路径加载第 70～74 节的 `main.py`，注册唯一模块名 | 模块组合 |
| `spec_mod / metrics_mod / exec_mod / calib_mod / board_mod` | 模块级变量 | 五个兄弟模块 | 分层 |
| `Generation` | dataclass | adapter 的返回值：文本、置信度、token NLL、token 数 | adapter 契约 |
| `ModelAdapter` | 基类 | `model_id` + `generate()`，默认抛 `NotImplementedError` | 适配器接口 |
| `TaskResult` | dataclass | 单个 (模型, 任务) 的评分记录 | 中间结果 |
| `EvalReport` | dataclass | 最终信封，`to_json()` 序列化 | 报告格式 |
| `_correct_from_score` | 函数 | 把分数二值化成 `correct` | 校准标签 |
| `_score_one` | 函数 | 渲染 → 生成 → 后处理 → 打分 | 单遍评分 |
| `run_eval` | 函数 | 生成 (adapter, task) 工作列表，并行/顺序执行，排序，填校准缓冲 | 执行器 |
| `build_eval_runs` | 函数 | `TaskResult → EvalRun` | 层间契约 |
| `_calibration_blocks / _perplexity_blocks` | 函数 | 每模型的 ECE/Brier 与困惑度 | 校准层 |
| `render_report / render_markdown_block` | 函数 | 组装信封、渲染 markdown | 报告层 |
| `RuleBasedAdapter / NoisyAdapter / BiasedAdapter` | 类 | 三种 mock 模型 | 测试替身 |
| `_load_fixture_tasks / demo` | 函数 | 写出并校验 fixture，跑完整流程并检查排名 | 自终止 demo |

数据流：`spec_mod.load_fixtures` 写 JSONL → `validate_file` 得到 10 个 `TaskSpec` → `run_eval`（3 adapter × 10 task = 30 次 `_score_one`）→ `TaskResult` 列表 + 校准缓冲 → `build_eval_runs` → `aggregate / pairwise_diffs` + `_calibration_blocks` + `_perplexity_blocks` → `EvalReport` → markdown + summary + pairwise 打印 → 排名检查 → 退出码。

---

## 3. 逐段精讲

### 3.1 `_load_sibling`：加载五个同名模块

```python
def _load_sibling(lesson_dir: str, module_name: str = "main"):
    here = os.path.dirname(os.path.abspath(__file__))
    sibling = os.path.normpath(os.path.join(here, "..", "..", lesson_dir, "code", "main.py"))
    if not os.path.isfile(sibling):
        raise ImportError(f"sibling module not found: {sibling}")
    mod_name = f"_sibling_{lesson_dir.replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(mod_name, sibling)
    ...
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module
```

- 路径从本文件位置推算：`75-.../code/` → `../..` 回到 `19-capstone-projects/` → `<lesson_dir>/code/main.py`。所以**目录结构就是依赖声明**，挪动任何一个目录都会 `ImportError`。
- 五个文件都叫 `main.py`，runner 自己也叫 `main`。用 `import main` 只会得到 `sys.modules["main"]` 中缓存的第一个。这里给每个模块起唯一名 `_sibling_70_task_spec_format` 等（`-` 换成 `_`，使其成为合法标识符）。
- **先注册 `sys.modules` 再 `exec_module`**：这是官方文档推荐的顺序。兄弟模块里用到 `@dataclass`，而 `dataclasses` 在处理 `from __future__ import annotations` 的字符串注解时会通过 `sys.modules[cls.__module__]` 查找模块；不先注册就可能出错。
- ⚠️ 参数 `module_name` 从未使用（文件名写死为 `main.py`）。
- 兄弟模块的 `demo()` 都在 `if __name__ == "__main__":` 之下，被这样加载时不会执行。

### 3.2 数据契约：`Generation`、`ModelAdapter`、`TaskResult`、`EvalReport`

```python
@dataclass
class Generation:
    text: str
    confidence: float = 0.5
    token_nll: float = 0.0
    token_count: int = 0


class ModelAdapter:
    model_id: str = "abstract"

    def generate(self, prompt: str, task: TaskSpec) -> Generation:
        raise NotImplementedError
```

- `Generation` 只有 `text` 是必填的，其它字段有默认值；讲义说 `token_nll`、`token_count` 是 "optional"。
- `ModelAdapter` 是普通基类而非 `abc.ABC`：忘记实现 `generate` 不会在实例化时报错，而是在调用时抛 `NotImplementedError`（测试 `test_abstract_raises` 正是验证这一点）。
- `model_id` 是**类属性**，三个 mock 都在类体里覆盖它。这意味着同一个类的两个实例 `model_id` 相同——`run_eval` 开头的唯一性检查就是为了防止这种情况。
- `EvalReport.to_json()` 只在 `error` 非空时才写入 `"error"` 键；⚠️ 但整份代码**从未给 `error` 赋值**（见 3.9）。

### 3.3 `_correct_from_score`：把分数变成二值标签

```python
def _correct_from_score(metric_name: str, score: float, threshold: float = 0.5) -> bool:
    if metric_name in ("exact_match", "accuracy", "code_exec"):
        return score >= 0.999999
    return score >= threshold
```

- 校准（ECE、Brier）需要 0/1 的 `correct`，而 F1/BLEU/ROUGE-L 是连续分数。这里的约定：二值型指标要求满分，分级指标 ≥ 0.5 即算对。
- `0.999999` 而不是 `1.0`：容忍浮点误差。讲义写的是 "`score >= 1.0`"，语义相同。
- `code_exec` 的分数是"通过断言比例"（第 72 节 `passed / total`），所以 2/3 通过 → 0.667 → `correct=False`。
- 讲义说"runner does not expose a public override"：`threshold` 参数只在函数签名上，`_score_one` 调用时没有传，外部无法配置。

### 3.4 `_score_one`：单遍评分

```python
def _score_one(adapter: ModelAdapter, task: TaskSpec, timeout_s: float = 3.0) -> TaskResult:
    rendered = spec_mod.render_prompt(task)
    t0 = time.time()
    gen = adapter.generate(rendered, task)
    elapsed = time.time() - t0
    processed = spec_mod.post_process(gen.text, task.post_process)
    if task.metric_name == "code_exec":
        result = exec_mod.run_candidate(
            exec_mod.extract_code(processed) or processed,
            task.targets,
            timeout_s=timeout_s,
        )
        score = result.score
        detail = result.detail
    else:
        score = metrics_mod.score(task.metric_name, processed, task.targets)
        detail = ""
    correct = _correct_from_score(task.metric_name, score)
    return TaskResult(..., confidence=float(min(1.0, max(0.0, gen.confidence))), ...)
```

逐步对应讲义的 6 步：

| 步骤 | 代码 | 说明 |
|------|------|------|
| 1. 渲染 prompt | `spec_mod.render_prompt(task)` | few-shot 示例按 `"{prompt} {completion}"` 拼接，用 `\n\n` 分隔，最后接任务 prompt |
| 2. 调用并计时 | `t0 = time.time()` … | 只计 `generate` 的耗时，不含打分（代码执行的子进程时间不算在内） |
| 3. 后处理 | `spec_mod.post_process(gen.text, task.post_process)` | 如 `extract_letter` 把 `"Answer: B"` 变成 `"B"`；`extract_code_block` 取出代码块内容 |
| 4. 分派指标 | `if task.metric_name == "code_exec"` | 代码题走第 72 节沙箱子进程，其余走第 71 节 `score` |
| 5. 构建记录 | `TaskResult(...)` | 带上 `detail`（如 `assertion error: name 'is_even' is not defined`） |
| 6. 置信度 | `min(1.0, max(0.0, gen.confidence))` | 截断到 [0, 1]，防止第 73 节 `_validate_probs` 抛错 |

细节：

- `exec_mod.extract_code(processed) or processed`：`extract_code_block` 后处理已经去掉了 ``` 围栏，`extract_code` 对无围栏文本原样返回；`or processed` 处理 `extract_code` 返回 `None`（文本含 ``` 但匹配不上）或空串的情况。⚠️ 这与第 72 节 `score_code_exec` 的语义不同——后者遇到 `None` 直接判 0 分，这里却把原文当代码执行。
- ⚠️ `min(1.0, max(0.0, nan))` 的结果是 `0.0`：NaN 置信度会被静默当作 0，不会报错。
- ⚠️ 没有 `try/except`：adapter 抛异常会一路传到 `run_eval`，并行时由 `fut.result()` 重新抛出，整个评估中断。

### 3.5 `run_eval`：并行执行器

```python
    model_ids = [a.model_id for a in adapters]
    if len(set(model_ids)) != len(model_ids):
        raise ValueError("adapter.model_id values must be unique within a single eval run")
    calibration_buf = {mid: [] for mid in model_ids}

    if not tasks or not adapters:
        return results, calibration_buf

    work = []
    for adapter in adapters:
        for task in tasks:
            work.append((adapter, task))

    if parallel and len(work) > 1:
        workers = min(max_workers, len(work))
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = {
                ex.submit(_score_one, adapter, task, code_exec_timeout_s): (adapter, task)
                for adapter, task in work
            }
            for fut in as_completed(futures):
                results.append(fut.result())
    else:
        for adapter, task in work:
            results.append(_score_one(adapter, task, code_exec_timeout_s))

    results.sort(key=lambda r: (r.model_id, r.task_id))
    for r in results:
        calibration_buf[r.model_id].append((r.confidence, 1.0 if r.correct else 0.0, r.score))
```

- **`model_id` 唯一性**：结果按 `model_id` 分组，两个同名 adapter 会把结果混在一起，第 74 节还会因 `(model_id, task_id)` 重复报错。提前失败更清晰。
- **空输入**：没有任务时返回每个模型一个空列表；没有 adapter 时返回空字典（测试 `test_no_tasks_returns_empty` / `test_no_adapters_returns_empty`）。
- **工作列表**是"模型数 × 任务数"的笛卡尔积；demo 中 3 × 10 = 30 个工作项。并发数 `min(max_workers, len(work))`——⚠️ 讲义说"the smaller of eight and the task count"，代码用的是工作项总数，demo 还传了 `max_workers=6`。
- **字典推导式提交 future**：键是 future，值是 `(adapter, task)`；值其实没被用到，用列表也可以。
- **`as_completed`** 按完成先后产出；`results.sort` 让最终顺序与执行方式无关（Python 排序稳定、键唯一，所以顺序完全确定）。
- **校准缓冲**是 `(confidence, correct(0/1), score)` 三元组。⚠️ 类型注解写的是 `tuple[float, float, int]`，第三项其实是 `float` 分数。
- ⚠️ **确定性的漏洞**：排序只保证"结果的顺序"确定，不保证"结果的内容"确定。`NoisyAdapter` 持有共享的 `self.rng`，并行时哪个任务拿到第几个随机数取决于线程调度，结果每次运行都可能不同（见第 6 节和测验 Q9）。

### 3.6 层间转换与校准/困惑度块

```python
def build_eval_runs(results):
    return [board_mod.EvalRun(model_id=r.model_id, task_id=r.task_id,
                              metric_name=r.metric_name, score=r.score,
                              category=r.category) for r in results]
```

- `EvalRun` 是第 74 节的输入契约，runner 只做字段映射，不计算任何排行榜指标（讲义："The runner does not duplicate any logic from those modules"）。`weight` 用默认值 1.0。

```python
def _calibration_blocks(buf):
    for model_id, entries in buf.items():
        if not entries:
            out[model_id] = {"ece": 0.0, "brier": 0.0, "populated_bins": 0, "n_samples": 0}
            continue
        confs = [e[0] for e in entries]
        corrs = [e[1] for e in entries]
        report = calib_mod.CalibrationReport.from_predictions(confs, corrs, bins=10)
        out[model_id] = {"ece": report.ece, "brier": report.brier,
                         "populated_bins": report.populated_bins, "n_samples": report.n_samples}
```

- 第 73 节的 ECE：10 个等宽箱，`ECE = Σ (箱内样本数/n) × |箱内平均置信度 − 箱内准确率|`；Brier：`mean((conf − correct)²)`。
- 只取了 `CalibrationReport` 的 4 个标量，丢掉了 `reliability`（可靠性图数据），信封因此更紧凑。
- 空模型返回全 0 的块——⚠️ "ECE = 0" 看起来像"完美校准"，用 `None`/NaN 表示"无数据"更不容易误读。

```python
def _perplexity_blocks(adapters, buf, results, adapter_token_stats):
    for adapter in adapters:
        stats = adapter_token_stats.get(adapter.model_id, [])
        if not stats:
            out[adapter.model_id] = {"perplexity": float("nan"), "total_tokens": 0}
            continue
        nlls = [s[0] for s in stats]
        counts = [s[1] for s in stats]
        result = calib_mod.PerplexityResult.from_token_nll(nlls, counts)
        out[adapter.model_id] = result.to_dict()
```

- 困惑度 = `exp(Σ NLL / Σ token 数)`，按 token 加权而不是按样本平均。
- ⚠️ 参数 `buf`、`results` 都没用到；数据来源是 adapter 自己维护的 `token_stats` 列表（由 demo 通过 `getattr(a, "token_stats", [])` 收集），而不是 `Generation` 中的 `token_nll / token_count`。这让困惑度依赖 adapter 的可变状态：同一个 adapter 实例跑两次 `run_eval`，统计会累加。
- ⚠️ 无数据时 `perplexity` 是 `NaN`，`json.dumps` 默认会输出非标准 JSON 字面量 `NaN`，严格的 JSON 解析器会拒绝。

### 3.7 `render_report` 与 `render_markdown_block`

```python
    eval_runs = build_eval_runs(results)
    rows = board_mod.aggregate(eval_runs, b=200, alpha=0.05, seed=7)
    diffs = board_mod.pairwise_diffs(eval_runs, b=200, alpha=0.05, seed=7)
```

- bootstrap 只重采样 200 次（第 74 节默认 500），换取速度；`seed=7` 固定，在输入相同时 CI 可复现。
- `aggregate` 按 `mean_score` 降序稳定排序；`pairwise_diffs` 对按字母序排列的每一对模型做**配对** bootstrap（同一任务的分差），CI 不含 0 时 `significant=True`。
- `summary` 比讲义示例多了 `task_runs`（30），信封比讲义示例多了 `perplexity` 块。

markdown 表把排行榜和校准两类信息拼在一行：

```python
        ci = f"{row['mean_ci_lo']:.2f}-{row['mean_ci_hi']:.2f}"
        out_lines.append(
            f"| {i} | {row['model_id'][:20]} | {row['mean_score']:.2f} | {ci} | {row['win_rate']:.2f} | "
            f"{row['tasks_completed']} | {ece:.3f} | {brier:.3f} |"
        )
```

- `row['model_id'][:20]` 截断过长的模型名；`cal.get("ece", float("nan"))` 让缺校准数据的模型显示 `nan` 而不是崩溃。

### 3.8 三个 mock adapter

| Adapter | 输出策略 | confidence | 每 token NLL | 设计意图 |
|---------|---------|-----------|-------------|---------|
| `RuleBasedAdapter` | 直接返回 `targets[0]`；代码题按 task_id 写死正确实现；MCQ 返回 `"Answer: <字母>"` | 0.92 | 0.8 | 近乎完美、轻度欠自信 |
| `NoisyAdapter` | 25% 概率返回 `targets[0]`，否则 `"I do not know"` / `"Answer: A"` / 错误的 `a - b` | 0.85 | 2.5 | 过度自信、常常答错 |
| `BiasedAdapter` | 擅长类别返回 `targets[0]`，其余返回 `"guess"` / `"Answer: B"` / `return None` | 0.9 / 0.4 | 1.0 / 3.0 | 偏科，但置信度"知道自己不行" |

- token 数用 `len(text.split())` 粗略估计，NLL = token 数 × 常数——**困惑度完全是构造出来的**，只用于演示管道连通。
- `RuleBasedAdapter` 对代码题的写法：后处理 `extract_code_block` 取出 ```` ```python ... ``` ```` 中的代码，再由第 72 节在子进程里 `exec` 并逐条 `eval` 断言。
- ⚠️ `NoisyAdapter` 在 25% 分支对代码题返回 `targets[0]`，也就是**断言字符串** `"add(1, 2) == 3"`，当作代码执行会 `NameError`，得 0 分——"答对"分支在代码题上其实答不对。
- ⚠️ `BiasedAdapter` 对 MCQ 固定答 B，而 `mcq_001` 的答案恰好是 B，于是"只会算术"的模型在 mcq 类别拿到 0.5。
- ⚠️ `NoisyAdapter`、`BiasedAdapter` 对 `code_002`（要求 `is_even`）都返回定义 `add` 的代码，断言报 `name 'is_even' is not defined`。

### 3.9 `_load_fixture_tasks` 与 `demo`

```python
def _load_fixture_tasks() -> list:
    import tempfile
    out_dir = tempfile.mkdtemp(prefix="aie_l75_")
    good, _bad = spec_mod.load_fixtures(out_dir)
    tasks, errors = spec_mod.validate_file(good)
    if errors:
        raise RuntimeError(f"fixture validation failed: {errors}")
    return tasks
```

- 先把第 70 节的 fixture 写成 JSONL 文件，再走一遍真实的 `validate_file`——这样 runner 用的是"文件 → 校验 → TaskSpec"的完整路径，而不是直接构造对象。
- ⚠️ `mkdtemp` 创建的临时目录**从不删除**；每次运行 demo 或每个调用它的测试都会在 `/tmp` 留下一个 `aie_l75_*` 目录（跑一遍测试留下 8 个）。用 `tempfile.TemporaryDirectory()` 的 `with` 块即可修复。

```python
    if not report.leaderboard:
        print("ERROR: empty leaderboard")
        return 1
    top = report.leaderboard[0]["model_id"]
    bot = report.leaderboard[-1]["model_id"]
    if top != "rule_based":
        ...
        return 2
    if bot == "rule_based":
        ...
        return 3
    return 0
```

- `sys.exit(demo())` 把返回值变成进程退出码，CI 可以据此判断成败。
- ⚠️ 与讲义不一致：讲义说失败时"exits non-zero with a structured error in the JSON envelope"，但代码只打印一行文本，`report.error` 从未被设置，完整 JSON 信封也从未打印；讲义说"rule-based strictly above the random adapter"，但没有 random adapter，第三个检查在第二个检查通过且模型数 > 1 时必然通过。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 按相对路径 `_load_sibling` 加载兄弟模块 | 课程每节一个 `main.py`，不想打包成库 | 目录结构即依赖，挪动即坏；生产应把各层做成可安装的包 |
| adapter 只有一个 `generate` | 接入成本最低，重试/缓存可作为包装层叠加 | 置信度、NLL 需要 adapter 自报，真实 API 未必提供 |
| 线程池并行 | 真实调用是 I/O 瓶颈 | 无限流、无重试、无单任务失败隔离；有状态 adapter 不可复现 |
| 结果按 `(model_id, task_id)` 排序 | 下游 bootstrap 可复现 | 只能保证顺序，不能保证内容 |
| 分级指标 0.5 阈值二值化 | 让所有任务都能进校准 | 阈值任意且不可配置；BLEU 等尺度差异大 |
| 困惑度来自 adapter 的 `token_stats` | 实现简单 | 依赖可变状态，`Generation` 里的同名字段反而没用上；应由 runner 从 `Generation` 汇总 |
| bootstrap 200 次、seed 固定 | 快且可复现 | 10 个任务的 CI 极宽（0.0–0.6），几乎不能区分模型 |
| mock adapter 的 NLL = token 数 × 常数 | 管道可以端到端跑通 | 困惑度数值无实际意义 |
| 退出码 1/2/3 区分失败 | CI 友好 | 讲义承诺的结构化错误信封没有实现 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 注解延迟求值，可以在旧版本里写 `list[dict]`、`str | None` |
| `importlib.util` 动态导入 | `spec_from_file_location` → `module_from_spec` → `exec_module` | 从任意路径加载模块，并自定义模块名 |
| `sys.modules` | `sys.modules[mod_name] = module` | 已加载模块的全局缓存，`import` 先查这里 |
| `@dataclass` + 默认值 | `confidence: float = 0.5`、`error: str | None = None` | 自动生成 `__init__`；有默认值的字段必须放在无默认值字段之后 |
| 类属性 vs 实例属性 | `model_id = "noisy"`（类体）vs `self.rng = ...`（`__init__`） | 类属性由所有实例共享 |
| 继承与方法覆盖 | `class NoisyAdapter(ModelAdapter)` 重写 `generate` | 基类方法抛 `NotImplementedError` 表示"子类必须实现" |
| 联合类型 | `str | None` | Python 3.10+ 的写法，等价于 `Optional[str]` |
| 默认参数与关键字参数 | `run_eval(adapters, tasks, parallel=True, max_workers=6, ...)` | 调用时按名字传参更清晰 |
| `with` 上下文管理器 | `with ThreadPoolExecutor(max_workers=workers) as ex:` | 退出时自动等待所有任务并关闭线程池 |
| `ex.submit` + `as_completed` | `for fut in as_completed(futures): fut.result()` | 提交任务得到 future；按完成顺序取结果；`result()` 会重新抛出任务中的异常 |
| 字典推导式 | `{ex.submit(...): (adapter, task) for adapter, task in work}`、`{mid: [] for mid in model_ids}` | 一行构造字典 |
| 列表推导式 | `[e[0] for e in entries]` | 取元组的第 0 项组成新列表 |
| `lambda` 排序键 | `results.sort(key=lambda r: (r.model_id, r.task_id))` | 按元组逐项比较；`sort` 是稳定的原地排序 |
| 条件表达式 | `1.0 if r.correct else 0.0`、`sig = "yes" if d["significant"] else "no"` | 三元运算 |
| `or` 的短路取值 | `exec_mod.extract_code(processed) or processed` | 左边为假值（`None`、`""`）时取右边 |
| `getattr` 带默认值 | `getattr(a, "token_stats", [])` | 属性不存在时返回默认值，不抛 `AttributeError` |
| `enumerate(start=1)` | `for i, row in enumerate(rows, start=1)` | 排名从 1 开始 |
| f-string 格式符 | `{row['mean_score']:.2f}`、`{d['diff_mean']:+.3f}`、`{ece:.3f}` | 保留小数位；`+` 强制显示正负号 |
| 函数内导入 | `def _load_fixture_tasks(): import tempfile` | 延迟导入，只在需要时加载 |
| `float("nan")` | `cal.get("ece", float("nan"))` | 表示"缺失"的浮点数，格式化后显示 `nan` |
| `json.dumps(indent=2)` | `json.dumps(payload, indent=2)` | 缩进输出 JSON |
| `sys.exit(demo())` | 文件末尾 | 把函数返回值作为进程退出码 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行 demo，被测试导入时不执行 |

---

## 6. 运行结果解读

实际运行（Python 3，`cd code && python3 main.py`，墙钟约 0.3 秒，退出码 0）：

```text
| Rank | Model | Mean | 95% CI | Win rate | Tasks | ECE | Brier |
|------|-------|------|--------|----------|-------|-----|-------|
| 1 | rule_based | 1.00 | 1.00-1.00 | 1.00 | 10 | 0.080 | 0.006 |
| 2 | biased | 0.30 | 0.00-0.60 | 0.30 | 10 | 0.240 | 0.150 |
| 3 | noisy | 0.30 | 0.00-0.60 | 0.30 | 10 | 0.550 | 0.512 |

summary: {
  "tasks": 10,
  "models": 3,
  "task_runs": 30,
  "wall_seconds": 0.10594344139099121
}

pairwise differences (paired bootstrap):
  biased vs noisy: diff=+0.000  ci=[-0.402,+0.303]  significant=no
  biased vs rule_based: diff=-0.700  ci=[-0.900,-0.400]  significant=yes
  noisy vs rule_based: diff=-0.700  ci=[-0.902,-0.400]  significant=yes
```

逐项解读：

- **rule_based**：10 题全对，均值 1.00，CI 退化为 `1.00-1.00`（所有重采样均值都是 1）。置信度恒为 0.92、准确率 1.0，ECE = |0.92 − 1| = 0.08，Brier = 0.08² = 0.0064（显示 0.006）——**轻度欠自信**。
- **biased**：算术 2 题对，再加上 `mcq_001` 的"Answer: B"碰巧命中，共 3 题对。ECE = 0.2×0.1 + 0.8×|0.4−0.125| = 0.24，Brier = 0.15（手算过程见测验 Q11）。按类别：arithmetic 1.0、mcq 0.5、summary 0.0004（`"guess"` 的 BLEU 因 +1 平滑不为 0）、其余 0。
- **noisy**：本次答对 3 题，置信度恒 0.85，ECE = 0.55，Brier = 0.5125——**严重过度自信**。
- **并列排序**：`biased` 和 `noisy` 均分相同，`biased` 排前只是因为字母序（见测验 Q8）。
- **win rate**：rule_based 每题都是最高分（并列也算赢），所以 1.00；另两个模型只在与 rule_based 并列满分的题上"赢"，各 0.30。
- **pairwise**：两个弱模型的配对差值 CI 跨 0，不显著；它们与 rule_based 的差距 −0.7 显著。注意 `noisy vs rule_based` 的 CI 下界是 −0.902，与另一行的 −0.900 略有不同，是因为 `seed + i + j` 让每一对用不同的随机种子。
- **demo 没打印的部分**：困惑度块。我们另行调用（顺序模式）得到：rule_based `exp(0.8) ≈ 2.23`（43 token），noisy `exp(2.5) ≈ 12.18`（51 token），biased `exp(68/24) ≈ 17.0`（24 token）。

**可复现性实验**：用同样的 `seed=1` 并行跑 30 次，`noisy` 得分 > 0 的任务集合出现了 10 种组合（如 `{arith_001, cls_001, sum_002}` 9 次、`{arith_001, mcq_001, sum_002}` 5 次、`{mcq_002, sum_002}` 2 次），均分在 0.2～0.3 之间变化；顺序模式下则固定为 `{arith_001, sum_001, sum_002}`。所以上面那张表**不是每次都一样**。

---

## 7. 动手改一改

1. **修复 NoisyAdapter 的可复现性**：把 `self.rng.random()` 换成 `random.Random(f"{self.seed}:{task.task_id}").random()`，再写一个测试：用 `NoisyAdapter` 比较并行与顺序结果是否一致（参考测验 Q9）。
2. **实现讲义承诺的错误信封**：检查失败时设置 `report.error` 并打印 `report.to_json()`；把 `_load_fixture_tasks` 的 `RuntimeError` 也转成信封输出（参考测验 Q10）。
3. **把困惑度改为由 runner 汇总**：在 `TaskResult` 中增加 `token_nll`、`token_count` 字段，在 `_score_one` 中从 `Generation` 填入，`_perplexity_blocks` 改为从 `results` 计算，删除 adapter 的 `token_stats`。
4. **单任务失败隔离**：在 `_score_one` 外包一层 `try/except`，adapter 抛异常时返回 `score=0.0, correct=False, detail="adapter error: ..."`，并在 `summary` 中增加 `failed_runs` 计数。
5. **写一个包装 adapter**：`RetryingAdapter`（指数退避重试）或 `CachingAdapter`（参考测验 Q12），验证排行榜与不包装时一致。
6. **进阶**：把 `_correct_from_score` 的阈值改为按指标配置（如 `{"bleu_4": 0.3, "rouge_l": 0.5, "f1": 0.5}`），通过 `run_eval` 参数传入；再为一个真实模型的 API 写 adapter，用 MCQ 选项字母的 log-prob 作为 `confidence`。

---

## 8. 常见坑

- **以为"排了序"就"可复现"**：排序只固定顺序；有状态的 adapter 在并行下内容也会变。随机性应绑定到任务而不是调用次数。
- **同一个 adapter 实例重复使用**：`token_stats` 会在多次 `run_eval` 之间累积，困惑度统计被污染。
- **两个同类 adapter 用同一个 `model_id`**：`run_eval` 会直接 `ValueError`；想比较两个 seed 的 `NoisyAdapter`，要给实例设置不同的 `model_id`。
- **把并列名次当作优劣**：`biased` 排在 `noisy` 前面只是字母序；先看配对差值 CI。
- **10 个样本上谈校准**：每个模型只有 1～2 个非空分箱，ECE 主要反映的是"常数置信度 vs 总准确率"。
- **忘记兄弟模块依赖**：单独复制 `75-.../code/` 到别处运行会 `ImportError: sibling module not found`。
- **NaN 进 JSON**：无 token 数据时困惑度为 `NaN`，`json.dumps` 输出的 `NaN` 不是合法 JSON，前端/其他语言解析会失败。
- **临时目录泄漏**：`_load_fixture_tasks` 每次都在 `/tmp` 留下一个目录；在 CI 中长期运行会积累垃圾。

---

## 9. 测试在验证什么

测试文件：`code/tests/test_runner.py`，共 12 个 `unittest` 用例。运行方式（在 `code/` 目录下）：

```bash
python3 -m pytest -q tests                     # 12 passed in 0.89s
python3 -m unittest discover -s tests -v       # Ran 12 tests ... OK
```

文件开头用 `sys.path.insert(0, os.path.dirname(HERE))` 把 `code/` 加进搜索路径，然后 `from main import ...`。另外定义了一个 `StubAdapter`（但没有任何测试使用它）。

| 测试类 / 用例 | 验证的性质 |
|--------------|-----------|
| `TestAdapterInterface.test_abstract_raises` | 基类 `ModelAdapter().generate()` 抛 `NotImplementedError` |
| `TestAdapterInterface.test_rule_based_always_correct_on_targets` | `RuleBasedAdapter` 在所有 exact_match/accuracy 任务上 `correct=True`，验证"后处理 + 指标"链路对正确答案打满分 |
| `TestRunEval.test_no_tasks_returns_empty` | 无任务时结果为空，校准缓冲是 `{"rule_based": []}` |
| `TestRunEval.test_no_adapters_returns_empty` | 无 adapter 时结果为空、缓冲为空字典 |
| `TestRunEval.test_parallel_sequential_match` | 并行与顺序得到相同的逐任务分数——**但只用了确定性的 `RuleBasedAdapter`**，没有覆盖 `NoisyAdapter` 的顺序依赖问题 |
| `TestRunEval.test_calibration_buf_populated` | 缓冲条数等于任务数，每条是三元组且置信度在 [0, 1] |
| `TestScoring.test_correct_threshold` | `exact_match` 1.0 对、0.99 错；`f1` 0.6 对、0.49 错；`code_exec` 1.0 对 |
| `TestScoring.test_build_eval_runs` | `TaskResult → EvalRun` 字段映射正确 |
| `TestReport.test_report_envelope` | `to_json()` 可被解析，含五个顶层键，`summary` 的任务数与模型数正确 |
| `TestReport.test_markdown_contains_models` | markdown 中有表头 `Rank` 和模型名 |
| `TestRanking.test_rule_based_beats_noisy` | 顺序模式下 `rule_based` 排第一 |
| `TestRanking.test_biased_strong_on_good_category` | `BiasedAdapter` 在 arithmetic 上的均分高于其它类别 |

测试没有覆盖的点：并行模式下有状态 adapter 的可复现性、错误信封（`error` 字段）、adapter 抛异常时的行为、困惑度数值、`model_id` 重复时的 `ValueError`、代码执行超时路径。另外，每个调用 `fixture_tasks()` 的测试都会留下一个 `/tmp/aie_l75_*` 临时目录。
