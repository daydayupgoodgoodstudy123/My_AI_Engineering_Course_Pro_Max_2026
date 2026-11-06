# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 57 节 端到端研究演示 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（在 `code/` 目录下）；测试：`python3 -m unittest discover -s tests` 或 `python3 -m pytest -q tests` ｜ **依赖**：标准库（`asyncio`、`importlib`、`tempfile`、`json`、`dataclasses`）+ `numpy`（由第 56 节的 runner 间接使用）；**要求**同级目录下存在 `54-paper-writer/code/main.py`、`55-critic-loop/code/main.py`、`56-iteration-scheduler/code/main.py`

---

## 1. 这份代码在考察什么

这是自动科研 Track（第 50–57 节）的收官演示。它本身几乎不包含新算法，而是考察**如何把前几节写好的组件组合成一条能自我终止的流水线**：

1. **模块组合**：用 `importlib` 按文件路径加载三个同名的 `main.py`，从中取出 `IterationScheduler`、`CriticLoop`、`PaperWriter` 等公开接口。
2. **阶段间的数据转换**：`SchedulerReport` → 最佳 branch → `MiniPaper`（critic 用的简化论文）→ `Paper`（写作器用的完整论文）→ LaTeX/BibTeX/manifest。
3. **类型化失败**：没有触发 → `NoTriggerError`；触发名对不上 → `BestResultError`；论文结构不合法 → `PaperValidationError`。
4. **确定性**：同一种子跑两次得到相同的 branch、奖励和章节结构，并用测试固定下来。

> 一句话：**"组合即架构"——五个阶段、三次导入、一份报告**。同时也是一次"集成测试"：组合时暴露出的契约漏洞（figure 引用被丢、prose 生成器从未被调用、critic 软失败不拦截）正是本节最值得学习的地方。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `_add` / `_load_module` | 函数 | 修改 `sys.path`；按路径加载模块并注册到 `sys.modules` | 跨课程导入 |
| `paper_writer_mod` / `critic_loop_mod` / `scheduler_mod` | 模块对象 | 第 54/55/56 节的 `main.py` | 上游阶段 |
| `Paper`、`MiniPaper`、`Hypothesis` 等别名 | 模块级名字 | 把上游类重新导出，供本文件和测试使用 | 公共接口 |
| `NoTriggerError` / `BestResultError` | 异常类 | 挑选阶段的两种类型化失败 | 失败模式 |
| `DemoReport` | dataclass | 6 个字段，原样保存各阶段输出 | 演示报告 |
| `make_seed_hypotheses` | 函数 | 3 个种子假设（alpha/beta/gamma） | 第 50–53 节的 stub |
| `pick_best_branch` | 函数 | 在触发过的 branch 中按 `(-mean, branch)` 选第一 | 最佳结果挑选 |
| `_originality_for_reward` / `build_mini_paper` | 函数 | 均值 → originality 标签；构造两节的初稿 | critic 输入 |
| `mini_to_full_paper` | 函数 | `MiniPaper` → `Paper`：合成参考文献、添加 1 个 figure | 阶段间转换 |
| `_run_demo_async` / `run_demo` / `demo` | 函数 | 串起全部阶段；同步包装；入口 | 编排 |

数据流：`make_seed_hypotheses` → `IterationScheduler.run`（第 56 节）→ `SchedulerReport` → `pick_best_branch` → `(branch, mean)` → `build_mini_paper` → `CriticLoop.run`（第 55 节）→ `LoopResult.paper` → `mini_to_full_paper` → `PaperWriter.write`（第 54 节）→ `manifest` → `DemoReport`。

---

## 3. 逐段精讲

### 3.1 定位上游课程与修改 `sys.path`

```python
HERE = os.path.dirname(os.path.abspath(__file__))
LESSON_ROOT = os.path.dirname(os.path.dirname(HERE))

def _add(path: str) -> None:
    if path not in sys.path:
        sys.path.insert(0, path)

_add(os.path.join(LESSON_ROOT, "54-paper-writer", "code"))
...
```

- `HERE` 是 `57-.../code`，向上两级得到 `19-capstone-projects/`，于是可以拼出兄弟课程的路径。用 `__file__` 而不是当前工作目录，保证从任何目录运行都能找到。
- ⚠️ `_add` 在这里其实**多余**：下面的 `_load_module` 按绝对路径加载，不依赖 `sys.path`。反而因为三个目录里都有 `main.py`，把它们插到 `sys.path` 最前面后，后续任何 `import main`（如果 `sys.modules` 里还没有）都可能拿到第 56 节的文件而不是本节的。测试之所以没出问题，是因为测试文件先 `from main import ...` 把本节模块缓存进了 `sys.modules["main"]`。

### 3.2 按路径加载同名模块

```python
def _load_module(name: str, file_path: str):
    spec = importlib.util.spec_from_file_location(name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {name} from {file_path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

paper_writer_mod = _load_module("_t_d2_paper_writer", os.path.join(LESSON_ROOT, "54-paper-writer", "code", "main.py"))
```

- 三步：`spec_from_file_location`（根据路径生成"模块规格"）→ `module_from_spec`（创建空模块对象）→ `exec_module`（执行文件内容，填充模块）。
- **先注册到 `sys.modules` 再执行**：这是 Python 官方文档推荐的顺序。第 54/55/56 节的文件都使用 `@dataclass` 并开启了 `from __future__ import annotations`，dataclass 在处理字符串注解时会通过 `sys.modules[cls.__module__]` 查找模块；若没有先注册，可能出错。
- 唯一的模块名（`_t_d2_*`）是关键：四个文件都叫 `main.py`，若都以 `main` 注册就会互相覆盖（测验 Q1）。
- 失败时直接抛 `ImportError`——缺任何一个上游课程，演示在导入阶段就停下，这也是一种"失败尽早"。

### 3.3 重新导出上游名字

```python
Paper = paper_writer_mod.Paper
...
CriticLoop = critic_loop_mod.CriticLoop
deterministic_critic = critic_loop_mod.deterministic_critic
...
Hypothesis = scheduler_mod.Hypothesis
make_deterministic_runner = scheduler_mod.make_deterministic_runner
```

- 让本文件后面的代码（以及测试的 `from main import PaperValidationError, SchedulerReport`）像使用本地名字一样使用上游类。
- 注意：这是**名字绑定**而不是拷贝。`isinstance(x, Paper)` 与 `isinstance(x, paper_writer_mod.Paper)` 等价；测试里用 `mock.patch.object(main, "make_deterministic_runner", ...)` 可以替换本模块里的这个名字（测验 Q11）。

### 3.4 异常与报告

```python
class NoTriggerError(Exception):
    """No branch crossed the paper threshold; demo cannot pick a best result."""

class BestResultError(Exception):
    """Picker received an empty trigger list."""

@dataclass
class DemoReport:
    scheduler_report: dict
    best_branch: str
    best_reward: float
    critic_result: dict
    paper_manifest: dict
    stop_reason: str
```

- 自定义异常只需继承 `Exception`，docstring 就是最好的说明。按"失败原因"而不是按"阶段"命名，调用方可以精确捕获。
- `BestResultError` 的 docstring 写的是"empty trigger list"，但代码里它用于两种情况：触发名在 `branches` 中查不到（孤儿触发），以及 `_run_demo_async` 中种子列表为空——语义有点混用。
- `DemoReport` 有 **6** 个字段；讲义说"all five fields populated"，是因为讲义的形状图把 `best_branch` 与 `best_reward` 画成了一个节点。`stop_reason` 与 `scheduler_report["stop_reason"]` 重复，方便顶层直接读取。

### 3.5 种子与挑选器

```python
def pick_best_branch(scheduler_report: SchedulerReport) -> tuple[str, float]:
    if not scheduler_report.paper_triggers:
        raise NoTriggerError("no branch crossed the paper threshold")
    by_branch = {b.branch: b for b in scheduler_report.branches}
    triggered = [by_branch[name] for name in scheduler_report.paper_triggers if name in by_branch]
    if not triggered:
        raise BestResultError("trigger list empty after lookup")
    triggered.sort(key=lambda b: (-b.mean, b.branch))
    best = triggered[0]
    return best.branch, best.mean
```

- 先用字典推导式建立 `branch → BranchStats` 的索引，再按触发列表取出对应统计。
- 排序键 `(-b.mean, b.branch)`：元组按字典序比较，第一项取负实现"均值降序"，第二项实现"平局按名字升序"。这是 Python 里"多关键字、混合升降序"排序的惯用法。
- 返回的是 **branch 均值**而不是单次最好结果。讲义写"The picker selects the single best result"，字段名 `best_reward` 也容易误导；实际运行中 alpha 的单次最高是 0.8214，返回值是均值 0.8070（测验 Q6）。
- 只在**触发过**的 branch 中挑选：没有触发就意味着"没有任何方向值得写论文"，直接抛错比"硬选一个"更诚实。

### 3.6 构造 MiniPaper

```python
def _originality_for_reward(reward: float) -> str:
    if reward >= 0.8:
        return "high"
    if reward >= 0.6:
        return "medium"
    return "low"

def build_mini_paper(branch: str, reward: float) -> MiniPaper:
    return MiniPaper(
        title=f"Auto-Research Findings on Branch {branch}",
        abstract=f"We summarise the best yielding branch {branch} from the auto-research loop.",
        sections=[
            MiniSection(id="intro", title="Introduction", body="initial observations"),
            MiniSection(id="results", title="Results", body=""),
        ],
        originality_tag=_originality_for_reward(reward),
    )
```

- 均值 0.807 → `high` → critic 的 novelty 直接给 9 分。用"实验奖励"决定"论文新颖性"是演示性的简化，真实系统中两者并无必然联系。
- Results 正文为空是有意的：作者的本意大概是让第 54 节的 prose 生成器去填充它。但第 1 轮 critic 的 `expand-body` 建议针对**最后一节**，正好是 Results，reviser 往里写了 80 个 `x`——于是 prose 生成器再也没有机会（见 3.8）。

### 3.7 MiniPaper → Paper

```python
def mini_to_full_paper(mini: MiniPaper, branch: str) -> Paper:
    cites: list[str] = []
    for sec in mini.sections:
        for c in sec.cites:
            if c not in cites:
                cites.append(c)

    bib = [BibEntry(key=key, entry_type="article",
                    fields={"title": f"Source {key}", "author": "Synthesised", "year": "2026"})
           for key in cites]
    if not bib:
        bib = [BibEntry(key=f"{branch}-baseline", ...)]
        for sec in mini.sections:
            if sec.id == "intro":
                sec.cites.append(f"{branch}-baseline")
                break

    fig = Figure(id=f"{branch}-results", path=f"figs/{branch}.pdf",
                 caption=f"Reward trajectory on branch {branch}")

    sections = []
    for s in mini.sections:
        figure_refs = [fig.id] if s.id == "results" else []
        sections.append(Section(id=s.id, title=s.title, body=s.body,
                                cites=list(s.cites), figure_refs=figure_refs))
    return Paper(...)
```

- 用列表 + `if c not in cites` 做**保序去重**（集合会打乱顺序，影响确定性）。
- 每个 cite 键都生成一条合成 BibTeX，保证第 54 节 `_validate` 的"所有 cite 都在参考文献中"不变量成立——讲义："Every cite the demo adds is also added to the bibliography list, so validation passes."
- ⚠️ 兜底分支直接修改了传入的 `mini`（`sec.cites.append(...)`），而 `mini` 就是 `critic_result.paper`——转换函数产生了副作用。更安全的做法是先 `copy.deepcopy(mini)`。
- ⚠️ **figure 引用被丢弃**：每节的 `figure_refs` 被替换成"Results 有 `alpha-results`，其他为空"。critic 阶段 reviser 给 Introduction 加的 `f1`、`f2`（evidence 因此从 5.5 升到 9）在最终论文中消失了；Results 引用的 `alpha-results` 则从未被 critic 评审过（测验 Q5，修复见测验 Q10）。cite 却被完整保留——两者处理不一致。

### 3.8 编排：`_run_demo_async`

```python
    runner = make_deterministic_runner(
        base_rewards={"alpha": 0.82, "beta": 0.55, "gamma": 0.15},
        noise=0.04, delay_ms=2.0, seed=seed,
    )
    sched = IterationScheduler(
        runner=runner, slots=3, max_experiments=6,
        paper_threshold=0.7, prune_floor=0.2, prune_after_runs=3,
        expander=scheduler_mod.deterministic_expander,
    )
    sched_report = await sched.run(seed_list)

    branch, reward = pick_best_branch(sched_report)

    mini = build_mini_paper(branch, reward)
    loop = CriticLoop(critic=deterministic_critic, reviser=deterministic_reviser,
                      max_rounds=6, target_score=8.0)
    critic_result = loop.run(mini)

    full_paper = mini_to_full_paper(critic_result.paper, branch)
    prose = MockProseGenerator(outlines={...})
    writer = PaperWriter(prose=prose)
    manifest = writer.write(full_paper, out_dir)
```

- **调度阶段**：3 个种子、3 个槽位、6 次实验。只有 alpha（基准 0.82）的单次奖励能 ≥ 0.7，所以后 3 次实验全给了 alpha 的后续假设；gamma 均值 0.199 < 0.2，但只跑了 1 次，不会被剪枝（测验 Q8）。
- **挑选阶段**：唯一触发的是 alpha。
- **critic 阶段**：`CriticLoop` 是同步的，在 `async def` 里直接调用会阻塞事件循环——此时调度器已经结束，没有其他任务，所以无害；若将来 critic 改成调用 LLM，应改为 `await`。
- ⚠️ **软失败不拦截**：代码没有检查 `critic_result.status` / `reason`。本次是 `converged / plateau`（clarity 7.03 < 8），若是 `stopped / budget` 也会照常进入写作器（测验 Q7、Q12）。
- **写作阶段**：`PaperWriter.write` 依次 `fill_prose`（只填空正文）→ `render_latex`（内部先 `_validate`）→ 写 `paper.tex`、`references.bib`、`manifest.json`。⚠️ 四节正文都已非空，`MockProseGenerator` 一次也没被调用，传入的 outlines 是死代码；最终 Results 节正文就是 80 个 `x`（测验 Q4，已查看生成的 `paper.tex` 验证）。

### 3.9 同步入口

```python
def run_demo(out_dir: str | None = None, seed: int = 11) -> DemoReport:
    if out_dir is None:
        out_dir = tempfile.mkdtemp(prefix="auto-research-demo-")
    return asyncio.run(_run_demo_async(out_dir, seed=seed))
```

- `asyncio.run` 把异步流水线包装成同步函数，测试和命令行都可以直接调用。注意 `asyncio.run` 不能在已有事件循环中调用（例如 Jupyter 中需要直接 `await _run_demo_async(...)`）。
- ⚠️ `tempfile.mkdtemp` 创建的目录**不会被自动删除**：每次 `python3 main.py` 都会在系统临时目录留下一个 `auto-research-demo-xxxx/`（含 3 个文件）。测试用的是 `TemporaryDirectory()` 上下文管理器，退出时自动清理，所以不受影响。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 普通导入组合，不用框架 | 零依赖、可单步调试、"加一个阶段只多一行" | 没有持久化、重试、断点续跑；规模变大后迁移到编排框架或把各阶段做成包 |
| `importlib` 按路径加载 | 同名 `main.py` 能共存 | 属于脚手架代码；`_add` 修改 `sys.path` 多余且有隐患 |
| 内联 stub 代替第 50–53 节 | 让演示自包含、确定 | 实验奖励与论文内容没有真实联系 |
| 只在触发过的 branch 中按均值挑选 | 稳健、确定，无触发时诚实失败 | 字段名 `best_reward` 误导；不考虑置信度（4 次的均值与 1 次的均值同等对待） |
| 类型化异常短路 | 坏输入不进入下游 | 只拦截"异常"，不拦截"质量不达标"的软失败 |
| MiniPaper / Paper 两套模型 | 第 55 节只需最小结构 | 转换时丢失信息（figure 引用），评审对象 ≠ 交付对象 |
| 确定性 critic + reviser | 可测试 | 打分基于长度和计数，用 `x` 填充就能刷分 |
| 默认写入 `mkdtemp` | 不污染工作区 | 临时目录不清理；应让调用方显式提供目录或用 `TemporaryDirectory` |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `os.path.abspath(__file__)` | `HERE = os.path.dirname(os.path.abspath(__file__))` | 当前文件的绝对路径，常用于定位相邻资源 |
| `sys.path.insert(0, p)` | `_add(...)` | 把目录放到模块搜索路径最前面 |
| `importlib.util.spec_from_file_location` | `_load_module` | 按文件路径加载模块的标准三步法 |
| `sys.modules[name] = mod` | `_load_module` | 注册模块，之后同名导入直接命中缓存 |
| 自定义异常 | `class NoTriggerError(Exception)` | 继承 `Exception`，docstring 说明含义 |
| `@dataclass` | `class DemoReport` | 自动生成构造函数与 `__repr__` |
| 类型注解 `tuple[str, float]` | `def pick_best_branch(...) -> tuple[str, float]` | 返回二元组；配合 `from __future__ import annotations` 使用 |
| `str \| None` | `out_dir: str \| None = None` | 可选参数 |
| 字典推导式 | `{b.branch: b for b in scheduler_report.branches}` | 建立索引 |
| 带条件的列表推导式 | `[by_branch[n] for n in triggers if n in by_branch]` | 过滤 + 映射 |
| `list.sort(key=lambda ...)` | `triggered.sort(key=lambda b: (-b.mean, b.branch))` | 原地排序；元组键实现多级排序 |
| 元组解包 | `branch, reward = pick_best_branch(sched_report)` | 一次接收多个返回值 |
| f-string | `f"Auto-Research Findings on Branch {branch}"` | 字符串插值 |
| 保序去重 | `if c not in cites: cites.append(c)` | 小列表可用；大数据量可用 `dict.fromkeys(...)` |
| `for ... break` | `if sec.id == "intro": ...; break` | 找到第一个就停止 |
| 条件表达式 | `[fig.id] if s.id == "results" else []` | 一行二选一 |
| `async def` / `await` | `sched_report = await sched.run(seed_list)` | 在协程中等待另一个协程 |
| `asyncio.run` | `return asyncio.run(_run_demo_async(...))` | 同步代码调用异步代码的入口 |
| `tempfile.mkdtemp` | `tempfile.mkdtemp(prefix="auto-research-demo-")` | 创建临时目录（需自行清理） |
| `json.dumps(indent=2)` | `print(json.dumps({...}, indent=2))` | 格式化输出 |
| 列表推导式取字段 | `[s["id"] for s in rep["paper_manifest"]["sections"]]` | 从字典列表中提取某个键 |
| `if __name__ == "__main__"` | 文件末尾 | 直接运行时执行演示 |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，耗时不到 1 秒）：

```text
{
  "stop_reason": "max_experiments",
  "best_branch": "alpha",
  "best_reward": 0.8069853198632565,
  "critic_status": "converged",
  "critic_rounds": 5,
  "paper_sections": ["intro", "results", "method", "related-work"],
  "paper_figures": ["alpha-results"],
  "experiments_run": 6
}
```

我们额外打印了内部细节（用 `TemporaryDirectory` 运行，避免留下临时目录）：

```text
调度器 trace：dispatch alpha-1 / beta-1 / gamma-1 → result beta 0.604 / gamma 0.199 / alpha 0.821
             → paper.trigger alpha → expand → dispatch alpha-1-f1 / alpha-1-f2
             → result 0.800 → expand → result 0.808 → expand → dispatch alpha-1-f1-f1 → result 0.799 → expand
branches：alpha runs 4 mean 0.807；beta runs 1 mean 0.604；gamma runs 1 mean 0.199（pruned False）

critic trace（clarity / novelty / evidence / methodology / related_work → 均值）：
  round 1: 3.20 / 9 / 2.0 / 4 / 4 → 4.442   continue（4 条建议）
  round 2: 5.81 / 9 / 5.5 / 9 / 9 → 7.662   continue（2 条）
  round 3: 6.21 / 9 / 9.0 / 9 / 9 → 8.442   continue（1 条：clarity）
  round 4: 6.62 / 9 / 9.0 / 9 / 9 → 8.524   continue
  round 5: 7.03 / 9 / 9.0 / 9 / 9 → 8.606   plateau

manifest sections：intro（cites c1,c2；figure_refs []；20 字符）、results（figure_refs [alpha-results]；80 字符）、
                   method（237 字符）、related-work（468 字符）；bibliography：c1, c2
```

逐项解读：

- **stop_reason = max_experiments、experiments_run = 6**：第 6 次派发后，下一次完成即触发预算退出（第 56 节的计数口径）。
- **best_branch = alpha、best_reward ≈ 0.807**：4 次奖励的均值，不是单次最高 0.821。
- **critic 5 轮"converged"实为 plateau**：第 3 轮后只剩 clarity 在缓慢上升（每轮 +0.41，五维均值 +0.082 < 0.1），clarity 最终 7.03 仍低于目标 8。
- **四个章节**：初稿的 intro、results 加上 reviser 追加的 method、related-work。`paper_sections` 顺序就是追加顺序。
- **只有一个 figure**：`alpha-results` 由 `mini_to_full_paper` 添加；critic 阶段的 `f1`、`f2` 被丢弃。
- **正文内容**：生成的 `paper.tex` 里 Results 是 80 个 `x`，Method / Related Work 是固定句子加一长串 `x`，Introduction 是 "initial observations" 加两行 `See~\cite{c1}.`——prose 生成器没有参与。
- **确定性**：连续运行 5 次，`best_reward` 完全相同（0.8069853198632565）；换种子 0–5，最佳 branch 都是 alpha，均值在 0.80–0.83 之间。
- **副作用**：直接运行 `main.py` 会在系统临时目录留下 `auto-research-demo-*` 目录（我们运行后已手动删除）。

---

## 7. 动手改一改

1. **让 prose 生成器真正参与**：把 `build_mini_paper` 中 Results 的正文改为一句真实描述，或让 `expand-body` 只作用于非空章节，观察 `paper.tex` 中哪些章节由 `MockProseGenerator` 生成。
2. **保留 figure 引用**：按测验 Q10 修改 `mini_to_full_paper`，确认 manifest 中 figures 变成 `['alpha-results', 'f1', 'f2']` 且 `_validate` 通过。
3. **软失败拦截**：给 `run_demo` 增加 `require_target` 参数（测验 Q12），默认演示会因 plateau 而失败；再把 `CriticLoop(max_rounds=10, plateau_epsilon=0.05)` 调大，看能否达到 target。
4. **更强的测试**：实现测验 Q11 的两个测试（mock 掉 runner 与 `PaperWriter.write`；比较去掉路径后的 manifest 与 `paper.tex`）。
5. **状态持久化**（讲义 Going further）：每个阶段结束后把输出写成 `out_dir/stage_N.json`，重跑时若文件存在则跳过该阶段；验证删掉 `stage_3.json` 后只重跑 critic 与写作阶段。
6. **统一时间线**（讲义 Going further）：把调度器 trace 与 critic trace 合并成一个按阶段/轮次排序的事件列表，输出为 JSON Lines。

---

## 8. 常见坑

- **同名模块冲突**：多个 `main.py` 只能有一个叫 `main`；按路径加载时一定要起唯一名字。
- **以为 "converged" 就是达标**：`converged` 包含 plateau，需看 `reason == "target"`。
- **转换函数静默丢信息**：`mini_to_full_paper` 保留 cite 却丢弃 figure 引用；评审对象与交付对象不一致时，评审结果就失去意义。
- **"只填空正文"的隐式约定**：上游任何阶段写入了占位正文，下游的 prose 生成器就会被跳过，且不会报错。
- **转换函数修改输入**：兜底分支往 `mini` 的 intro 里追加 cite，会改变 `critic_result.paper`。
- **确定性测试比较了不确定的字段**：`wall_seconds`、`tex_path`、trace 顺序每次可能不同，比较前要去掉。
- **临时目录泄漏**：`mkdtemp` 需要手动清理；测试中优先用 `TemporaryDirectory`。
- **讲义中的测试名与实际不符**：讲义提到 `test_no_triggers_raises_typed_error`、`test_best_picker_raises_when_no_triggers`，实际文件中是 `test_no_trigger_raises` 与 `test_orphan_trigger_raises_best_result_error`。

---

## 9. 测试在验证什么

测试文件：`code/tests/test_e2e.py`（10 个测试）。它把 `code/` 加入 `sys.path` 后 `from main import ...`，因此同时间接加载了第 54/55/56 节的模块。

| 测试类 / 测试 | 验证的性质 | 说明 |
|--------------|-----------|------|
| `TestComposition.test_demo_runs_to_completion` | 全流程跑通：有 branch、奖励 > 0、critic `converged`、实验数 ≥ 3、章节 ≥ 2、figure ≥ 1 | `converged` 未区分 target 与 plateau |
| `TestComposition.test_paper_files_emitted` | `paper.tex`、`references.bib` 确实写到了磁盘 | 只检查存在，不检查内容 |
| `TestDeterminism.test_two_runs_with_same_seed_produce_same_branch` | 同种子两次：branch 相同、奖励相同（6 位小数）、章节 id 相同 | 讲义说"comparing the manifest"，实际只比较了三项 |
| `TestPicker.test_no_trigger_raises` | 无触发 → `NoTriggerError` | 直接调用挑选器，没有验证"写作器未被调用" |
| `TestPicker.test_orphan_trigger_raises_best_result_error` | 触发名在 branches 中不存在 → `BestResultError` | 手工构造的报告 |
| `TestPicker.test_ties_break_alphabetically` | 均值相同（0.8）时选字母序靠前的 alpha | 触发顺序是 `["beta", "alpha"]`，证明不是按触发顺序 |
| `TestPaperWriterContract.test_validation_error_propagates` | 标题为空 → `PaperValidationError` | 验证第 54 节的契约在组合后依然有效 |
| `TestSeedAndScheduler.test_seed_has_three_branches` | 种子是 3 个不同 branch | stub 的形状 |
| `TestSeedAndScheduler.test_demo_stop_reason_is_known` | `stop_reason` 属于三个已知取值 | 防止调度器引入新的停止原因而下游不知道 |
| `TestPicker_BestBranchIsAlpha.test_alpha_wins_under_default_seed` | 默认种子下 alpha 胜出且均值 > 0.7 | 固定演示结果 |

运行方式（在 `code/` 目录下）：

```bash
python3 -m unittest discover -s tests -v
# 或
python3 -m pytest -q tests
```

实际运行结果：`10 passed in 0.25s`。

我们另外按测验 Q11 编写了两个更强的测试（mock runner 使其无触发并断言 `PaperWriter.write` 未被调用；比较去掉路径后的整份 manifest、`paper.tex` 内容与 `critic_result`），在本地运行同样通过（`Ran 2 tests ... OK`），说明当前实现确实满足讲义描述的更强契约，只是原测试没有把它们固定下来。
