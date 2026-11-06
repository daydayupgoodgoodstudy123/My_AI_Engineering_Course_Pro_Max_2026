# 测验 · 端到端研究演示（End-to-End Research Demo）

> **阶段 19 · 综合项目 · 第 57 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 组合即架构 | 本节不写新框架，只把第 54 节 `PaperWriter`、第 55 节 `CriticLoop`、第 56 节 `IterationScheduler` 用普通 Python 导入串起来；讲义："composition is the architecture" |
| 2 | 五个阶段 | 种子假设 → 迭代调度器（含实验 runner）→ 最佳结果挑选 → critic 循环 → 论文写作器 → `DemoReport` |
| 3 | 按文件路径加载模块 | 三个上游文件都叫 `main.py`，用 `importlib.util.spec_from_file_location` 以**唯一模块名**（`_t_d2_paper_writer` 等）加载，避免在 `sys.modules` 里互相覆盖 |
| 4 | 内联 stub | `make_seed_hypotheses` + `make_deterministic_runner` 代替第 50–53 节的真实假设生成与实验执行 |
| 5 | 挑选器 `pick_best_branch` | 只在**触发过 paper.trigger** 的 branch 中选**均值**最高者，平局按 branch 名字母序；无触发抛 `NoTriggerError`，触发名查不到抛 `BestResultError` |
| 6 | MiniPaper → Paper 的升级 | `build_mini_paper` 按均值设 `originality_tag`（≥0.8 high、≥0.6 medium、否则 low）；`mini_to_full_paper` 补一个 figure 和由 cite 键并集生成的合成参考文献 |
| 7 | 类型化失败 | 每个阶段要么成功、要么抛类型化异常（`NoTriggerError` / `BestResultError` / `PaperValidationError`），后续阶段不会拿着坏输入继续跑 |
| 8 | 确定性 | 固定种子的 NumPy runner、按固定顺序修改的 reviser、mock 的 prose 生成器、按迭代顺序破平局的 UCB → 同一种子得到同一结果 |
| 9 | DemoReport | 原样保存上游输出：`scheduler_report`、`best_branch`、`best_reward`、`critic_result`、`paper_manifest`、`stop_reason`（共 6 个字段） |
| 10 | "converged" 的真实含义 | critic 循环的 `converged` 包含 `target`（全部维度达标）和 `plateau`（均值不再明显上升）两种；默认演示走的是 **plateau** |

### 核心技能（能动手做到）

- [ ] 用 `importlib.util` 按路径加载同名模块，并解释为什么不能直接 `import main`
- [ ] 手算默认演示中 critic 循环每一轮的五维分数和建议列表
- [ ] 读懂 `mini_to_full_paper`，指出 critic 阶段添加的 figure 引用在升级时被丢弃
- [ ] 为端到端流程编写"失败短路"测试：验证上游失败时下游从未被调用
- [ ] 把确定性测试从"比较 branch 与章节 id"加强到"比较去掉路径后的整份 manifest"
- [ ] 为每个阶段补上契约检查（例如 critic 必须 `reason == "target"`），并给异常加上阶段名

---

## 二、基础自测（选择题）

**Q1.** 本节为什么用 `_load_module("_t_d2_scheduler", ".../56-iteration-scheduler/code/main.py")` 而不是把目录加进 `sys.path` 后 `import main`？

- A. `importlib` 的加载速度比 `import` 快
- B. 第 54、55、56 节以及本节自己的文件都叫 `main.py`，用 `import main` 只能拿到 `sys.modules` 里缓存的那一个；按路径加载并起唯一名字才能同时拥有三个模块
- C. asyncio 要求用 `importlib` 加载协程
- D. 因为上游课程被安装成了 pip 包

**Q2.** 手工构造一个 `SchedulerReport`：`paper_triggers = ["delta", "beta"]`；`branches` 中 alpha 均值 0.95、beta 均值 0.75、delta 均值 0.75（alpha 不在触发列表中）。`pick_best_branch` 返回：

- A. `("alpha", 0.95)`，均值最高
- B. `("delta", 0.75)`，它是第一个触发的
- C. 抛出 `BestResultError`
- D. `("beta", 0.75)`：只在触发过的 branch 中比较，均值相同按字母序

**Q3.** 默认演示中 `critic_status = "converged"`、`critic_rounds = 5`。最终五维分数为 `clarity 7.03、novelty 9、evidence 9、methodology 9、related_work 9`，目标分是 8.0。"converged" 的原因是：

- A. plateau：最近两轮的均值增量都只有约 0.082，小于 `plateau_epsilon = 0.1`；clarity 仍低于 8，**目标并未达成**
- B. target：所有维度都达到了 8 分
- C. budget：用完了 `max_rounds = 6`
- D. critic 抛出了异常，被当作收敛处理

**Q4.** 默认演示生成的 `paper.tex` 中，Results 一节的正文是什么？

- A. `MockProseGenerator` 根据 outline 生成的 "In this section we discuss results: summary of reward trajectory on branch alpha."
- B. 空的，只有 `% body pending`
- C. 80 个字符 `x`：这是 reviser 的 `expand-body` 写进去的；`PaperWriter.fill_prose` 只填充**空**正文，所以 prose 生成器一次也没被调用
- D. 调度器的 trace JSON

**Q5.** critic 循环中 reviser 曾向 Introduction 添加了 figure 引用 `f1`、`f2`（这让 evidence 得分升到 9）。这两个引用在最终论文里：

- A. 被保留，并生成了对应的 `\begin{figure}` 环境
- B. 触发了 `PaperValidationError`，因为没有对应的 Figure
- C. 被改名为 `alpha-results`
- D. 被 `mini_to_full_paper` 丢弃了：它只给 `results` 一节设置 `figure_refs = [fig.id]`，其他章节一律设为空列表

**Q6.** 默认演示输出 `best_reward = 0.80698...`。这个数字是：

- A. branch alpha 在 4 次实验上的**平均**奖励（`BranchStats.mean`），而不是单次最好结果（单次最高是 0.8214）
- B. 所有 branch 的平均奖励
- C. alpha 最后一次实验的奖励
- D. critic 的最终均分除以 10

**Q7.** 如果 critic 循环以 `status = "stopped"`（预算耗尽）结束，`_run_demo_async` 会：

- A. 抛出 `NoTriggerError`
- B. 自动把 `max_rounds` 加倍重试
- C. 照常把这份未收敛的草稿交给论文写作器——代码没有检查 critic 的状态
- D. 跳过论文写作器，只返回调度报告

**Q8.** 默认演示中 gamma 的均值约 0.199，低于 `prune_floor = 0.2`，但报告里 `pruned = False`。原因是：

- A. gamma 触发了 paper.trigger，被保护起来
- B. gamma 只跑了 1 次，达不到 `prune_after_runs = 3`；整个演示只有 6 次实验
- C. 剪枝只在 drain 阶段进行
- D. `prune_floor` 的比较是 `<=`，0.199 不满足

---

## 三、动手 / 代码题

**Q9.** 默认演示中挑出的 branch 是 alpha（均值 0.807），`build_mini_paper` 生成的初稿为：Introduction（正文 `"initial observations"`，20 字符）、Results（正文为空），`originality_tag` 由均值决定。已知 `deterministic_score` 的规则：

```python
clarity = min(10.0, 3.0 + avg_body / 50.0)
novelty = 9.0 / 6.0 / 3.0   # high / medium / low
evidence = min(10.0, 2.0 + 2.0 * fig_refs + 1.5 * cites)
methodology = 9.0 if 有非空 Method 节 else 4.0
related_work = 9.0 if 有非空 Related Work 节 else 4.0
```

1. 写出第 1 轮的五维分数、均值，以及 critic 给出的建议（哪几个维度）。
2. reviser 执行这些建议后，写出第 2 轮的 clarity 与 evidence。（提示：`expand-body` 作用于**最后一节**，加 80 个 `x`；新增 Method 节正文 237 字符、Related Work 节 225 字符。）
3. 为什么 clarity 每轮只涨约 0.41，导致第 5 轮被判为 plateau？

**Q10.** 修改 `mini_to_full_paper`，让 critic 阶段加入的 figure 引用（如 `f1`、`f2`）不被丢弃：为每个出现过的 figure id 生成一个占位 `Figure`，并保留各章节原有的 `figure_refs`，同时仍给 Results 加上 `{branch}-results`。写出代码，并说明它为什么能通过 `_validate`。

**Q11.** 讲义说测试"assert the picker raises ... when no branch fired a trigger, **and the writer is never invoked**"，以及"running the demo twice and **comparing the manifest**"。但实际测试只直接调用了 `pick_best_branch`，确定性测试也只比较了 branch、reward 和章节 id。请写两个更强的测试：

1. 用 `unittest.mock.patch` 让调度器不产生任何触发，断言 `run_demo` 抛 `NoTriggerError` 且 `PaperWriter.write` 从未被调用；
2. 跑两次 demo，比较去掉 `tex_path`、`bib_path` 后的整份 `paper_manifest`，以及两份 `paper.tex` 的内容。

**Q12.** 讲义要求"Surface a clear failure mode when any stage's contract breaks"。请给 `_run_demo_async` 增加：(1) 一个 `DemoStageError(stage, cause)` 包装异常，让调用方知道是哪一阶段失败；(2) 在 critic 之后检查 `critic_result.reason`，若不是 `"target"` 则按策略处理（抛错或在报告中标记 `draft_quality = "plateau"`）。写出关键代码。

---

## 四、面试高频题

**Q13.**（基础必考）讲义强调"通过普通 Python 导入组合，而不是框架"。这种做法的优缺点是什么？什么时候你会改用 LangGraph 之类的编排框架？

**Q14.**（原理深挖）一个包含 asyncio 并发的流水线，可能有哪些不确定性来源？本节代码分别是如何（或没有）处理它们的？

**Q15.**（工程实践）多阶段流水线中，"每个阶段要么成功、要么抛类型化错误"有什么好处？阶段之间的契约应该怎样定义和检查？

**Q16.**（场景设计）要把这个演示变成每天无人值守运行的自动科研系统，你会补哪些能力？请至少覆盖状态持久化、真实模型调用、成本控制、质量把关和可观测性。

**Q17.**（追问型）本节 critic 循环报告"converged"，最终五维均分 8.6。你能据此认为论文质量好吗？critic 的分数可能被怎样"刷"出来？

---

## 五、参考答案与解析

### Q1 — 答案：B

`sys.modules` 以模块名为键缓存模块。四个文件都叫 `main.py`，第一次 `import main` 之后，后续的 `import main` 都会直接返回缓存——你永远拿不到第二个。`_load_module` 用 `spec_from_file_location(name, path)` 按路径加载，并以 `_t_d2_paper_writer`、`_t_d2_critic_loop`、`_t_d2_scheduler` 这样的唯一名字注册到 `sys.modules`，三个模块就能共存。A 错，速度不是原因；C 与 asyncio 无关；D 错，讲义明确说这些课程不是安装好的包。顺带一提：代码开头的 `_add(...)` 把三个目录插进 `sys.path` 实际上是多余的——按路径加载根本不依赖 `sys.path`，而往 `sys.path` 前面塞三个都含 `main.py` 的目录反而增加了 `import main` 拿错模块的风险。

### Q2 — 答案：D

`pick_best_branch` 先用 `paper_triggers` 过滤出"触发过的 branch"（`triggered = [by_branch[name] for name in paper_triggers if name in by_branch]`），再按 `(-mean, branch)` 排序。alpha 均值虽高但不在触发列表里（真实运行中均值 ≥ 0.7 的 branch 一定会触发，这里是手工构造的报告），不参与比较；beta 与 delta 均值相同，按字母序 `"beta" < "delta"`。A 错在忽略了过滤；B 错在以为按触发顺序；C 错，两个触发名都能在 `branches` 中找到，不会抛 `BestResultError`。

### Q3 — 答案：A

实际运行得到的 critic trace（均值）：4.442 → 7.662 → 8.442 → 8.524 → 8.606。`_plateau` 取最近 `plateau_window + 1 = 3` 轮，检查相邻增量是否都 `<= plateau_epsilon (0.1)`：`8.524 − 8.442 = 0.082`、`8.606 − 8.524 = 0.082`，于是在第 5 轮判为 plateau，`status = "converged"`、`reason = "plateau"`。clarity 只有 7.03，`_target_met` 不成立。B 错，clarity 未达 8；C 错，第 5 轮就停了，还没到第 6 轮；D 错，没有异常。测试 `test_demo_runs_to_completion` 只断言 `status == "converged"`，没有区分 target 与 plateau——这正是讲义"The reviser then iterates the draft to convergence"容易让人误解的地方。

### Q4 — 答案：C

第 1 轮时最后一节是 Results（正文为空），clarity 建议的目标是 `paper.sections[-1].id`，reviser 给它追加了 `"x" * 80`。之后 Method、Related Work 被追加到末尾，后续的 expand-body 都加在 Related Work 上（最终 468 字符）。`PaperWriter.fill_prose` 只在 `if not sec.body` 时调用 prose 生成器；最终四节正文都非空，所以 `MockProseGenerator` 和它的 outlines（"motivation for branch alpha" 等）**一次都没用上**。实际生成的 `paper.tex` 中 Results 节就是一行 `xxxx…`（已运行验证）。A 是作者大概率想要的效果；B 只在正文为空且未调用 prose 时出现；D 无关。

### Q5 — 答案：D

`mini_to_full_paper` 中：

```python
for s in mini.sections:
    figure_refs = [fig.id] if s.id == "results" else []
    sections.append(Section(id=s.id, ..., cites=list(s.cites), figure_refs=figure_refs))
```

cite 被保留（并为它们生成了合成 BibTeX 条目 `c1`、`c2`），figure 引用却被整体替换。结果是：critic 以"Introduction 有 2 个 figure 引用"给了 evidence 9 分，而最终论文的 Introduction 没有任何 figure，只有 Results 引用了一个 critic 从未见过的 `alpha-results`。A 错，没有为 `f1`/`f2` 生成 Figure；B 错，因为引用已被丢弃，`_validate` 不会报错；C 错，没有改名逻辑。修复见 Q10。

### Q6 — 答案：A

`pick_best_branch` 返回 `best.branch, best.mean`。实际运行中 alpha 的 4 个奖励为 0.8214、0.7996、0.8081、0.7989，均值 0.8070；单次最好是 0.8214。讲义说"The picker selects the single best result"，代码选的其实是"均值最高的 branch"，`best_reward` 这个字段名也容易误导。对研究决策而言用均值更稳健（不易被单次噪声带偏），但命名应改为 `best_branch_mean`。

### Q7 — 答案：C

`_run_demo_async` 拿到 `critic_result = loop.run(mini)` 后直接 `mini_to_full_paper(critic_result.paper, branch)` 并 `writer.write(...)`，没有任何对 `status` / `reason` 的判断。讲义的失败模式表写的是"Critic loop ...... returns LoopResult with status converged or stopped"——它只说明会返回什么，并没有让 `stopped` 短路流程。所以"失败短路"只覆盖**抛异常**的情况，对"质量不达标"这种软失败没有防护（见 Q12）。

### Q8 — 答案：B

剪枝条件是 `runs >= prune_after_runs and mean < prune_floor`。调度器 `max_experiments = 6`：3 个种子各 1 次，剩下 3 次都给了 alpha 的后续假设（beta 0.604、gamma 0.199 都 < 0.7，不会触发 expander），gamma 只有 1 次运行。A 错，gamma 未触发；C 错，drain 阶段根本不做剪枝，主循环才做；D 错，比较是严格的 `<`，0.199 < 0.2 本来是满足的，问题在次数。

### Q9 — 参考答案

已实际运行验证。

1. **第 1 轮**：两节正文长 20 和 0，`avg_body = 10`，clarity = `3 + 10/50 = 3.2`；均值 0.807 ≥ 0.8 → `high` → novelty 9.0；无 figure、无 cite → evidence 2.0；无 Method → 4.0；无 Related Work → 4.0。均值 `(3.2 + 9 + 2 + 4 + 4) / 5 = 4.44`。建议 4 条：clarity（`expand-body`，目标 `results`）、evidence（`add-figure-and-cite`，目标 `intro`）、methodology（`add-method-section`）、related_work（`add-related-work-section`）；novelty 已达标，无建议。
2. **第 2 轮**：章节变为 intro 20、results 80、method 237、related-work 225 字符，`avg_body = 562 / 4 = 140.5`，clarity = `3 + 140.5/50 = 5.81`；intro 有 1 个 figure（`f1`）和 1 个 cite（`c1`），evidence = `2 + 2×1 + 1.5×1 = 5.5`。第 2 轮均值 7.662。
3. 从第 2 轮起，最后一节是 Related Work，每轮 `expand-body` 只给它加 81 个字符（空格 + 80 个 x），平均正文长度只涨约 20，clarity 只涨约 0.41，五维均值每轮只涨 `0.41 / 5 ≈ 0.082 < 0.1`。evidence 在第 3 轮达到 9 后，唯一还在变化的维度就是 clarity，于是第 4、5 轮连续两次小增量触发 plateau。若继续跑，avg_body 需要达到 250 才能让 clarity ≥ 8，按每轮 +20 还要 3 轮——而 `max_rounds = 6` 本来也不够。这说明 plateau 的 epsilon 是相对"五维均值"设定的，单个维度的稳定进步会被稀释成"停滞"。

### Q10 — 参考答案

```python
def mini_to_full_paper(mini: MiniPaper, branch: str) -> Paper:
    cites: list[str] = []
    fig_ids: list[str] = []
    for sec in mini.sections:
        for c in sec.cites:
            if c not in cites:
                cites.append(c)
        for f in sec.figure_refs:
            if f not in fig_ids:
                fig_ids.append(f)

    bib = [BibEntry(key=k, entry_type="article",
                    fields={"title": f"Source {k}", "author": "Synthesised", "year": "2026"})
           for k in cites]
    # ……（原有的 baseline 兜底逻辑不变）

    main_fig = Figure(id=f"{branch}-results", path=f"figs/{branch}.pdf",
                      caption=f"Reward trajectory on branch {branch}")
    figures = [main_fig] + [
        Figure(id=f, path=f"figs/{branch}-{f}.pdf", caption=f"Supporting figure {f}")
        for f in fig_ids if f != main_fig.id
    ]

    sections = []
    for s in mini.sections:
        refs = list(s.figure_refs)
        if s.id == "results" and main_fig.id not in refs:
            refs.append(main_fig.id)
        sections.append(Section(id=s.id, title=s.title, body=s.body,
                                cites=list(s.cites), figure_refs=refs))
    return Paper(title=mini.title, authors=["Auto-Research Demo"], abstract=mini.abstract,
                 sections=sections, figures=figures, bibliography=bib)
```

能通过 `_validate` 的原因：`_validate` 检查三件事——figure id 不重复、bib key 不重复、每个 `figure_refs` / `cites` 都能在 `figures` / `bibliography` 中找到。这里 `figures` 由所有被引用的 id 去重生成，并排除了与 `main_fig` 重名的情况，所以引用与定义一一对应。更进一步的做法是让第 52 节的实验 manifest（`read_experiment_manifest`）提供真实图片路径，而不是生成占位文件名。

### Q11 — 参考答案

```python
import json, os, tempfile, unittest
from unittest import mock
import main as e2e

class TestStrongContracts(unittest.TestCase):
    def test_no_trigger_short_circuits_before_writer(self):
        # 所有 branch 的奖励都压低到阈值以下 -> 不会有 paper.trigger
        low_runner = e2e.make_deterministic_runner(
            base_rewards={"alpha": 0.1, "beta": 0.1, "gamma": 0.1}, noise=0.0, delay_ms=1.0)
        with mock.patch.object(e2e, "make_deterministic_runner", return_value=low_runner), \
             mock.patch.object(e2e.PaperWriter, "write") as fake_write, \
             tempfile.TemporaryDirectory() as td:
            with self.assertRaises(e2e.NoTriggerError):
                e2e.run_demo(out_dir=td)
            fake_write.assert_not_called()

    def test_manifest_identical_across_runs(self):
        def strip(m):
            m = dict(m); m.pop("tex_path"); m.pop("bib_path"); return m
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            r1, r2 = e2e.run_demo(out_dir=a, seed=11), e2e.run_demo(out_dir=b, seed=11)
            self.assertEqual(strip(r1.paper_manifest), strip(r2.paper_manifest))
            with open(os.path.join(a, "paper.tex")) as f1, open(os.path.join(b, "paper.tex")) as f2:
                self.assertEqual(f1.read(), f2.read())
            self.assertEqual(r1.critic_result, r2.critic_result)
```

要点：`mock.patch.object(e2e, "make_deterministic_runner", ...)` 替换的是 `main` 模块里的**名字**（`_run_demo_async` 通过全局名查找它），所以能生效；`PaperWriter` 是 `main` 里引用的同一个类对象，patch 它的 `write` 方法即可断言"从未调用"。manifest 里的 `tex_path`、`bib_path` 含临时目录，必须先去掉；调度报告的 `wall_seconds` 和 trace 顺序不是确定性的，不要直接比较整个 `scheduler_report`。

### Q12 — 参考答案

```python
class DemoStageError(Exception):
    def __init__(self, stage: str, cause: BaseException):
        super().__init__(f"stage {stage!r} failed: {cause!r}")
        self.stage, self.cause = stage, cause

async def _run_demo_async(out_dir: str, seed: int = 11, require_target: bool = False) -> DemoReport:
    try:
        sched_report = await sched.run(seed_list)
    except Exception as exc:
        raise DemoStageError("scheduler", exc) from exc

    try:
        branch, reward = pick_best_branch(sched_report)
    except (NoTriggerError, BestResultError) as exc:
        raise DemoStageError("picker", exc) from exc

    critic_result = loop.run(build_mini_paper(branch, reward))
    if critic_result.reason != "target":
        if require_target:
            raise DemoStageError("critic", RuntimeError(
                f"critic ended with {critic_result.status}/{critic_result.reason}"))
        draft_quality = critic_result.reason          # "plateau" 或 "budget"
    else:
        draft_quality = "target"

    try:
        manifest = writer.write(mini_to_full_paper(critic_result.paper, branch), out_dir)
    except PaperValidationError as exc:
        raise DemoStageError("writer", exc) from exc
    # DemoReport 增加 draft_quality 字段
```

要点：`raise ... from exc` 保留原始异常链，便于排查；包装异常让上层只需捕获一种类型，又能通过 `.stage` 知道失败位置；原有测试断言的是 `NoTriggerError`，若采用包装，需要同步修改测试或让 `DemoStageError` 只在最外层使用。软失败（plateau）是否算失败是**策略**，应作为参数显式选择，而不是默默放行。

### Q13 — 参考回答要点

- **优点**：零依赖、零学习成本；每个阶段是普通函数/类，可单独测试；调用栈清晰，调试时能直接单步进入；"加一个阶段只多一行"（讲义原话）。
- **缺点**：没有持久化、重试、断点续跑、并行编排、可视化这些框架自带的能力；阶段间契约靠约定，类型不强制；按路径加载模块属于"脚手架代码"，不适合长期维护（真实项目应把各阶段做成可安装的包）。
- **何时换框架**：流程需要长时间运行并可恢复（durable execution）、存在条件分支/循环/人工审批节点、需要多人协作查看执行图、需要跨机器分布式执行时。
- 加分点：先用普通代码把契约和测试做扎实，再迁移到框架，迁移成本最低；框架不应替代清晰的阶段契约。

### Q14 — 参考回答要点

- **不确定性来源与本节处理方式**：
  - 随机数：runner 用 `np.random.default_rng(seed)` 固定种子（已处理）；
  - 并发完成顺序：`asyncio.wait` 返回集合，同批结果处理顺序不确定。本节因为奖励在 runner 被调用时（`sleep` 之前）就抽好、派发顺序由队列决定，所以 branch 均值不受影响（已实测 5 次 `best_reward` 完全相同），但 trace 顺序可能变化；
  - 时间：`wall_seconds` 每次都不同；若 `max_seconds` 生效，不同机器速度会让实验数不同（本节 `max_seconds` 默认 30s，实际不会触发）；
  - 文件路径：`tempfile.mkdtemp` 每次不同，manifest 里的 `tex_path` 随之不同；
  - 平局：UCB 和 `pick_best_branch` 都用确定性破平局（迭代顺序 / 字母序）；
  - 字典/集合迭代：Python 3.7+ 字典保持插入序，但集合不保证。
- 加分点：把"确定性"写成测试（Q11），并明确列出哪些字段**不**参与比较；需要严格复现时，对并发结果按派发序号排序后再处理。

### Q15 — 参考回答要点

- **好处**：失败尽早暴露，不会把坏数据传到下游再以更难懂的方式报错（讲义："so the next stage does not run with a broken input"）；调用方可以按异常类型决定重试、降级或报警；测试可以精确断言失败模式。
- **契约的定义**：
  - 输入/输出的数据形状（dataclass / pydantic 模型 / JSON Schema）；
  - 不变量（例如"每个 cite 都在 bibliography 里"、"每个 figure_ref 都有对应 Figure"——第 54 节的 `_validate`）；
  - 质量门槛（例如 critic 必须达到 target）；
  - 终止条件（`stop_reason` 的取值集合）。
- **检查位置**：在阶段**入口**校验输入（防御上游），在**出口**校验输出（对下游负责）；类型化异常携带阶段名和原因。
- 常见误区：用返回 `None` 表示失败——讲义 quiz 明确指出这会让下游"break later with a less actionable error"；把软失败（plateau、低质量）当成功放行。

### Q16 — 参考回答要点

- **状态持久化**：每个阶段的输出写入 JSON/数据库（讲义 Going further 第一条），以 run_id 组织；重启时跳过已完成且输入未变的阶段；调度器的 UCB 统计也要 checkpoint。
- **真实模型调用**：替换 `MockProseGenerator` 和确定性 critic；加超时、重试、速率限制；记录 prompt/response 便于审计；用独立模型或独立 prompt 做评审，避免"自己给自己打分"。
- **成本控制**：调度器预算从"实验次数"改成"美元 / GPU 小时"；critic 轮数上限；每日总预算熔断。
- **质量把关**：critic 只接受 `target`；增加事实核查（引用是否真实存在、数字是否来自实验 manifest）；高风险输出进入人工审核队列。
- **可观测性**：调度器与 critic 的 trace 合成统一时间线（讲义 Going further 第二条）；指标包括每个 branch 的均值与置信区间、critic 各维度曲线、失败率、成本。
- **安全**：实验代码在沙箱中执行；生成的论文不可直接对外发布。

### Q17 — 参考回答要点

- **不能**。本节的 critic 是基于表面特征的确定性打分：clarity 只看平均正文长度，evidence 只数 figure 引用和 cite 数量，methodology / related_work 只看是否存在非空的同名章节。reviser 用 `"x" * 80`、`"x" * 200` 这样的填充文本就能把分数刷上去——最终论文的 Results 节就是 80 个 `x`（见 Q4）。
- **Goodhart 定律**：指标一旦成为优化目标，就不再是好指标。critic 与 reviser 共享同一套规则，reviser 天然会"对着评分规则写"。
- **另一个问题**：evidence 的 9 分来自 `f1`、`f2` 两个 figure 引用，但它们在升级到完整论文时被丢弃了（Q5）——被评审的对象和最终交付的对象不是同一个。
- **"converged" 也不等于达标**：本次是 plateau 而非 target（Q3）。
- **改进**：评审对象必须是最终产物；评审标准包含语义检查（LLM-as-judge + 规则）；评审者与修改者分离（第 14 阶段 Reviewer Agent 的思路）；对评审器本身做校准与对抗测试。

---

## 六、关联知识点

### 前置知识
- [阶段 19 · 56 迭代调度器](../../56-iteration-scheduler/docs/zh.md)：本节直接导入的 `IterationScheduler`，`SchedulerReport` 与 paper.trigger 的来源。
- [阶段 19 · 55 Critic 评审循环](../../55-critic-loop/docs/zh.md)：`CriticLoop`、`deterministic_critic`、`deterministic_reviser` 以及 plateau 判据。
- [阶段 19 · 54 论文写作器](../../54-paper-writer/docs/zh.md)：`Paper`、`PaperWriter`、`_validate` 与 `PaperValidationError`。
- [阶段 19 · 50 研究假设生成器](../../50-hypothesis-generator/docs/zh.md)、[阶段 19 · 52 实验执行器](../../52-experiment-runner/docs/zh.md)、[阶段 19 · 53 结果评估器](../../53-result-evaluator/docs/zh.md)：本节内联 stub 所替代的真实阶段。
- [阶段 14 · 05 Self-Refine 与 CRITIC](../../../14-agent-engineering/05-self-refine-and-critic/docs/zh.md)：critic–reviser 迭代改进的通用模式。

### 本节被哪些后续内容用到
- [阶段 15 · 05 AI Scientist v2](../../../15-autonomous-systems/05-ai-scientist-v2/docs/zh.md)：真实的端到端自主科研系统，可对照本节的极简版本。
- [阶段 14 · 39 Reviewer Agent](../../../14-agent-engineering/39-reviewer-agent/docs/zh.md)：把实现者与评分者分开，解决 Q17 中的"自评自改"问题。
- [阶段 14 · 13 有状态图 Orchestration](../../../14-agent-engineering/13-langgraph-stateful-graphs/docs/zh.md)：当需要持久化、断点续跑时，从普通导入迁移到编排框架。
- [阶段 14 · 30 评估驱动的 Agent 开发](../../../14-agent-engineering/30-eval-driven-agent-development/docs/zh.md)：用测试与评估锁定端到端流程的契约。
- [阶段 19 · 29 基于 Harness 的端到端 Coding Agent](../../29-end-to-end-coding-task-demo/docs/zh.md)：另一条 Track 的"端到端组合演示"，结构可互相对照。

### 延伸关键词
`composition over framework` · `importlib.util.spec_from_file_location` · `sys.modules` · `typed errors` · `stage contract` · `fail fast` · `determinism test` · `unittest.mock.patch` · `Goodhart's law` · `LLM-as-judge` · `durable execution` · `checkpoint / resume`
