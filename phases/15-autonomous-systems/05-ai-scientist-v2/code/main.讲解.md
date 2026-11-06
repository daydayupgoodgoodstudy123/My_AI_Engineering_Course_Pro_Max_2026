# 代码讲解 · main.py

> **所属小节**：阶段 15 · 自主系统 · 第 05 节 AI Scientist v2：达到研讨会论文水平的自主研究 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py [--experiment-failure P] [--novelty-mislabel P] [--seed N]` ｜ **依赖**：仅标准库（`argparse`、`random`、`dataclasses`）

---

## 1. 这份代码在考察什么

把 AI Scientist v2 的研究循环抽象成一个**带失败概率的状态机**，做 1000 次蒙特卡洛试验，统计：

1. **产量**：有多少想法最终走到"投稿"；在哪个阶段被放弃。
2. **质量**：投稿中有多少是"clean"（新颖且实验有效），有多少带缺陷。
3. **参数敏感性**：基线（讲义称 "Beel-style numbers"）与乐观场景对比；命令行可覆盖实验失败率与新颖性误判率（讲义练习 2）。

对应讲义的三点：Beel et al. 的独立评估数字、"polish masking"（漂亮论文掩盖破损研究）、以及"重试预算在产量与质量之间的权衡"。

> 一句话：**投稿数量增长得比可靠研究快**——在一个 evaluator 很弱的循环里，"产出"不等于"成果"。但要注意，这份代码并没有真正建模 polish 的作用（见 3.3），这是本讲解的重点之一。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `DEFAULT_SEED` | 常量 | 默认随机种子 42 | 可复现 |
| `LoopConfig` | dataclass（全部带默认值） | 6 个阶段概率：新颖性误判、实验失败、重试恢复、polish 掩盖、写作成功、内部审稿接收 | 讲义的 Beel 数字与假设参数 |
| `Outcome` | dataclass | 一次试验的结局：是否投稿、两类缺陷、两个质量标签、放弃阶段 | 状态机终态 |
| `run_one` | 函数 | 按顺序模拟一次研究循环 | idea → novelty → experiment → figure → writeup → review |
| `report` | 函数 | 跑 n 次 `run_one`，打印配置、投稿/放弃统计、质量分解 | 蒙特卡洛统计 |
| `main` | 函数 | 解析参数、设种子，跑基线与乐观场景，打印 HEADLINE | 入口 |

数据流：`main()` → `argparse` → `random.seed(seed)` → `report(1000, baseline_cfg)`（1000 × `run_one`）→ `report(1000, optimistic_cfg)`（继续使用同一随机流）→ 打印结论。

---

## 3. 逐段精讲

### 3.1 `LoopConfig`：参数与出处

```python
@dataclass
class LoopConfig:
    novelty_mislabel: float = 0.25
    experiment_failure: float = 0.42
    retry_recovery: float = 0.55
    polish_masks_weakness: float = 0.70
    writeup_success: float = 0.85
    internal_review_accept: float = 0.50
```

- 全部字段都有默认值，所以 `LoopConfig()` 就是基线；`LoopConfig(**overrides)` 用字典解包覆盖部分字段。
- **有出处的只有 0.42**：讲义 "42% of experiments failed from coding errors"。其余都是作者设定：
  - `novelty_mislabel = 0.25`：讲义正文只说 "frequently flagged established concepts as novel"，没有给出 25% 这个数（练习 2 称其为 Beel 的数字，需查原文核实）；
  - `retry_recovery`、`polish_masks_weakness`、`writeup_success`、`internal_review_accept` 都是假设值。
- ⚠️ **口径歧义**：代码把 0.42 当作"重试前"的失败率，再用 55% 的恢复率，最终放弃率只有 `0.42 × 0.45 = 18.9%`。讲义说 "The retry loop caught some, not all"，并未说明 42% 是重试前还是重试后。若是重试后，应设 `experiment_failure ≈ 0.933`，投稿中有缺陷的比例会从约 46% 升到约 91%（测验 Q12）。

### 3.2 `run_one` 前半：新颖性与实验

```python
def run_one(cfg: LoopConfig) -> Outcome:
    has_novelty_flaw = random.random() < cfg.novelty_mislabel

    failed = random.random() < cfg.experiment_failure
    if failed:
        recovered = random.random() < cfg.retry_recovery
        if not recovered:
            return Outcome(submitted=False, ..., abandoned_stage="experiment")
        has_experiment_flaw = True
    else:
        has_experiment_flaw = False
```

- **想法生成**总是成功；**新颖性检查**只打一个"有缺陷"的标记，从不导致放弃——真实系统中被判为"不新颖"的想法会被丢弃，这里只模拟"误判为新颖"的情形。
- **实验**：失败后有一次"重试"机会（`retry_recovery` 概率修好）；修不好就在 `"experiment"` 阶段放弃。
- **关键建模选择**（注释原文）："a retry-recovered experiment still carries a residual flaw"——被重试救回来的实验**一定**带有残留缺陷（数值静默出错、形状错误被"修补"但没重新验证）。后果：
  - clean 论文只可能来自**一开始就没失败**的实验；
  - 提高 `retry_recovery` 只会增加带缺陷的投稿，clean 数量不变（测验 Q8：`retry_recovery` 0 → 0.9，投稿率 24.7% → 40.7%，clean 始终约 18.5%）。
- 这把讲义 "How retry budgets trade off quality vs yield" 推到了极端：重试 = 纯产量、零质量。真实情况介于两者之间（有些错误被真正修好）。

### 3.3 `run_one` 中段：polish——一个没被使用的变量

```python
    polished_hides_weakness = (
        has_experiment_flaw and random.random() < cfg.polish_masks_weakness
    )
```

- 意图：VLM 改图以 70% 的概率掩盖实验缺陷。
- ⚠️ **这个变量之后再也没有被使用**：既不影响写作、审稿，也不进入 `Outcome`。由于 `random.random()` 是否被调用只取决于 `has_experiment_flaw`，与参数值无关，所以 `polish_masks_weakness` 取 0.0 还是 1.0，**所有输出逐字相同**（已用 30 个 seed 验证）。
- 后果：讲义练习 1 "What fraction produce a paper with an experiment-failure flaw the figure critique polished over?" 无法用这份代码回答；打印出来的 "polish masks weakness prob" 只是摆设。
- `and` 短路：`has_experiment_flaw` 为假时不会调用 `random.random()`，这会影响后续的随机流（但不受参数值影响）。

### 3.4 `run_one` 后半：写作、审稿与两个质量标签

```python
    if random.random() > cfg.writeup_success:
        return Outcome(..., abandoned_stage="writeup")

    if random.random() > cfg.internal_review_accept:
        return Outcome(..., abandoned_stage="internal_review")

    polished_ok = not has_experiment_flaw and not has_novelty_flaw
    polished_but_flawed = has_experiment_flaw or has_novelty_flaw
    return Outcome(submitted=True, ...)
```

- `random.random() > p` 表示"以 1 − p 的概率失败"，与前面 `< p` 表示"以 p 的概率发生"的写法相反，读的时候要留意方向。
- ⚠️ **内部审稿人与质量无关**：以固定 50% 概率接收，不看任何缺陷。所以它只是"随机砍掉一半"，投稿中有缺陷的比例与审稿前完全相同。讲义称其为 "weak reviewer"，这里是最弱的极端——零信息量。测验 Q11 给出改进：缺陷论文以 `catch` 概率被拒，`catch = 0.8` 时有缺陷比例从 46% 降到 15%。
- 两个标签互补：`polished_ok + polished_but_flawed == 投稿数`（注释也说明了这一点）。但名字有误导性：
  - `polished_but_flawed` 包括**只有新颖性缺陷**的论文，与图表打磨无关；
  - 它也不要求 `polished_hides_weakness` 为真。
  更准确的名字是 `flawed_submission`。

### 3.5 `report`：统计与打印

```python
    outs = [run_one(cfg) for _ in range(n)]
    submitted = [o for o in outs if o.submitted]
    abandoned = [o for o in outs if not o.submitted]
    ...
    by_stage = {}
    for o in abandoned:
        by_stage[o.abandoned_stage] = by_stage.get(o.abandoned_stage, 0) + 1
    for stage, count in sorted(by_stage.items()):
        print(f"    at {stage:<18}: {count}")
```

- 列表推导式做过滤；`by_stage.get(key, 0) + 1` 是手写计数（等价于 `collections.Counter`）。
- `sorted(by_stage.items())` 按阶段名字母序排列，所以输出顺序是 experiment、internal_review、writeup，而不是流程顺序。
- `max(1, len(submitted))` 防止投稿数为 0 时除零。
- 期望值速算（基线）：通过实验 `0.811`，投稿 `0.811 × 0.85 × 0.5 ≈ 34.5%`；投稿中 clean `0.58 / 0.811 × 0.75 ≈ 53.6%`。

### 3.6 `main`：命令行与两个场景

```python
    parser.add_argument("--experiment-failure", type=float, default=None, ...)
    parser.add_argument("--novelty-mislabel", type=float, default=None, ...)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED,
                        help="RNG seed (default: %(default)s)")
    ...
    overrides = {}
    if args.experiment_failure is not None:
        overrides["experiment_failure"] = args.experiment_failure
    ...
    baseline_cfg = LoopConfig(**overrides)
```

- `argparse` 自动把 `--experiment-failure` 转成属性名 `args.experiment_failure`（连字符变下划线）。
- `default=None` + `is not None` 判断：区分"用户没给"和"用户给了 0.0"——若写成 `if args.experiment_failure:`，用户传 0.0 会被当作没传。
- `%(default)s` 是 argparse 帮助文本中的占位符，会显示默认值。
- 覆盖参数后标签变为 "Baseline (overridden)"。
- 乐观场景的参数写死在代码中，命令行覆盖只影响基线。
- ⚠️ 两个场景共用一个随机流：基线消耗的随机数不同，乐观场景的输出也会跟着变；做对比时应给每个场景单独设种子。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 状态机 + 独立的阶段概率 | 简单、可解析计算 | 真实阶段之间强相关（难的想法更容易实验失败、也更容易被拒） |
| 重试恢复的实验一律带残留缺陷 | 突出"重试只换产量"的风险 | 过于悲观；真实中部分错误被真正修好，应建模"修好率" |
| polish 只计算不使用 | （疑为遗留/疏忽） | 参数无效，无法演示 polish masking；应让 polish 降低审稿人发现缺陷的概率（测验 Q10） |
| 内部审稿人与质量无关 | 体现"弱审稿人" | 零信息量，只砍产量不提质量；应建模识别率 `catch` |
| 新颖性检查不导致放弃 | 只关注"误判为新颖" | 忽略了被正确识别为不新颖而丢弃的想法 |
| 0.42 当作重试前失败率 | 作者的解读 | 讲义未给口径；若为重试后，结论显著更差 |
| 单 seed、1000 次试验 | 运行快 | 标准差约 1.5 个百分点；对比实验需多 seed 或用解析式 |
| `polished_but_flawed` 命名 | 对应讲义术语 | 实际含义是"任何有缺陷的投稿"，名不副实 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 全部带默认值的 dataclass | `class LoopConfig` | `LoopConfig()` 直接得到基线配置 |
| 关键字参数构造 | `Outcome(submitted=False, has_novelty_flaw=..., ...)` | 按字段名传参，可读性高 |
| `**` 字典解包 | `LoopConfig(**overrides)` | 把 `{"experiment_failure": 0.2}` 展开成关键字参数 |
| 括号内跨行表达式 | `polished_hides_weakness = ( ... and ... )` | 用括号包裹实现隐式续行 |
| 短路 `and` | `has_experiment_flaw and random.random() < p` | 左边为假时右边不执行 |
| 布尔运算组合 | `not has_experiment_flaw and not has_novelty_flaw` | `not` 优先级高于 `and`、`or` |
| 提前 `return` | 实验/写作/审稿失败时直接返回 `Outcome` | 用"卫语句"减少嵌套 |
| 列表推导式过滤 | `[o for o in outs if o.submitted]` | 按条件筛选 |
| `dict.get` 计数 | `by_stage.get(o.abandoned_stage, 0) + 1` | 键不存在时从 0 开始 |
| `sorted(dict.items())` | 按阶段名排序输出 | 元组按第一个元素排序 |
| `argparse` | `add_argument("--seed", type=int, default=...)` | 自动类型转换、生成 `--help` |
| `%(default)s` | `help="RNG seed (default: %(default)s)"` | 帮助文本中显示默认值 |
| `is not None` | `if args.experiment_failure is not None` | 区分"未提供"与"提供了假值 0.0" |
| 条件表达式 | `"Baseline (...)" if not overrides else "..."` | 空字典为假值 |
| f-string 格式符 | `{cfg.novelty_mislabel:.2f}`、`{len(submitted) / n:.1%}`、`{stage:<18}` | 小数位、百分比、左对齐 |
| 模块 docstring 作描述 | `argparse.ArgumentParser(description=__doc__)` | `--help` 时显示文件开头的说明 |

---

## 6. 运行结果解读

默认运行（`python3 main.py`，seed 42）：

```text
Baseline (Beel-style numbers)
  trials                    : 1000
  submissions               : 305 (30.5%)      ← 期望 34.5%，单 seed 偏低
  abandoned                 : 695 (69.5%)
    at experiment        : 215                 ← 期望 189（0.42 × 0.45）
    at internal_review   : 369                 ← 期望 345
    at writeup           : 111                 ← 期望 122

  submission quality breakdown
    clean (novel + valid)     : 173 (17.3% of trials, 56.7% of submissions)
    polished-but-flawed       : 132 (13.2% of trials, 43.3% of submissions)

Optimistic scenario (tighter numbers)
  submissions               : 530 (53.0%)      ← 期望 53.0%
    at experiment        : 32
    at internal_review   : 357
    at writeup           : 81
    clean (novel + valid)     : 403 (40.3% of trials, 76.0% of submissions)
    polished-but-flawed       : 127 (12.7% of trials, 24.0% of submissions)
```

逐项解读：

- **基线**：约三成试验走到投稿，其中约 43% 带缺陷（期望 46%）。最大的放弃来源是内部审稿（随机砍半）。
- **乐观场景**：投稿率升到 53%，带缺陷比例降到 24%（期望 25%），但带缺陷的投稿**绝对数量**几乎没变（127 vs 132）——因为投稿总量也上去了。这就是 HEADLINE "Even in optimistic scenarios, a non-trivial share of submitted papers carry a flaw" 的数据依据。
- **讲义练习 2**（覆盖基线两个参数）：

| 参数 | 投稿率 | clean 占投稿 | 有缺陷占投稿 |
|------|-------|------------|------------|
| `--experiment-failure 0.20 --novelty-mislabel 0.10` | 36.6% | 79.5% | 20.5% |
| 默认（0.42 / 0.25） | 30.5% | 56.7% | 43.3% |
| `--experiment-failure 0.60 --novelty-mislabel 0.40` | 29.3% | 36.5% | 63.5% |

  有缺陷占比从约 21% 升到约 64%；但投稿率只从 36.6% 降到 29.3%——**上游质量大幅恶化时，产量几乎不变**，只看产量完全察觉不到问题。
- **讲义练习 1**：clean 约占全部试验的 17%；"figure critique 掩盖了实验缺陷"的比例在当前代码中**无法得到**，因为 polish 变量没有被使用（见 3.3）。

---

## 7. 动手改一改

1. **（练习 1、2）**用 `--seed` 跑 10 个不同种子，计算基线投稿率与缺陷占比的均值和标准差，确认与解析值 34.5% / 46.4% 一致。
2. **让 polish 生效**：新增 `reviewer_catch` 参数；审稿人只能看到"未被 polish 掩盖的实验缺陷 + 新颖性缺陷"，看到时以 `catch` 概率拒稿。把 `polished_but_flawed` 重新定义为"带实验缺陷且被 polish 掩盖而投稿"，然后扫描 `polish_masks_weakness` = 0 / 0.5 / 1.0（参考测验 Q10）。
3. **修好率**：把"重试恢复的实验一律有缺陷"改为"以概率 `true_fix` 被真正修好"，扫描 `true_fix` 和 `retry_recovery`，画出产量—质量曲线。
4. **口径敏感性**：把 `experiment_failure` 设为 0.933（假设 42% 是重试后比例），对比投稿率和缺陷占比（参考测验 Q12）。
5. **新颖性检查可以拒绝想法**：加入"正确识别为不新颖则放弃"的分支（需要先设定"想法本来就不新颖"的先验比例），观察放弃阶段分布的变化。
6. **进阶（练习 5）**：在投稿后加入"人工审查"阶段，审查耗时与论文数成正比、发现缺陷的概率与审查分钟数相关；在固定人力预算下比较"全部精读"与"自动闸门 + 抽样深审"两种策略的漏检率。

---

## 8. 常见坑

- **打印了参数不等于参数生效**：`polish_masks_weakness` 被打印在配置里，却对结果毫无影响；改参数前先确认它在代码路径中被用到。
- **只看投稿数**：上游质量恶化时投稿率几乎不变，必须同时看缺陷占比。
- **把"弱审稿人"建模成抛硬币**：与质量无关的过滤器只砍产量、不提质量。
- **引用数字不查口径**：42% 是重试前还是重试后，结论相差一倍以上。
- **标签名误导**：`polished_but_flawed` 实际包含只有新颖性缺陷的论文。
- **`> p` 与 `< p` 的方向**：`random.random() > cfg.writeup_success` 表示"失败"，读代码时容易看反。
- **场景共享随机流**：修改基线参数会让乐观场景的输出也变化，对比时要分别设种子。
