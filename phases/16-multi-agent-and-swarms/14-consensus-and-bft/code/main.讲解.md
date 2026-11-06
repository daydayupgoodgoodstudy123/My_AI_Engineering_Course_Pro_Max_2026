# 代码讲解 · main.py

> **所属小节**：阶段 16 · 多智能体与集群 · 第 14 节 面向 Agents 的共识与拜占庭容错 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无参数） ｜ **依赖**：仅标准库（`dataclasses`、`statistics`、`typing`），无需 API key、无需网络

---

## 1. 这份代码在考察什么

讲义的核心论点是：经典 BFT（PBFT）只解决"任意出错的少数节点"，而 LLM agent 还有三种特有问题——故意说谎（byzantine lie）、跟风（sycophantic conformity）、同一基座模型的相关错误（monoculture）。这份代码把问题压缩成"5 个 agent 对同一个数值问题各投一票"，用三种**聚合器**分别计票：

1. **plurality**：按规范化后的答案数人头；
2. **CP-WBFT（简化版）**：按自报置信度加权求和，并设接受阈值；
3. **DecentLLMs（简化版）**：按"簇大小 × 簇内置信度一致性"打分。

然后在四个脚本化场景（无攻击、说谎、跟风、monoculture）下打印每个聚合器的结论，标出对错。

> 一句话：**用最小代码说明"投票规则能挡住哪类坏票、挡不住哪类坏票"——尤其是 monoculture 下所有规则一起失败**。注意它并没有实现 PBFT 的任何协议阶段（无 pre-prepare/prepare/commit、无签名、无多轮），只是"单轮聚合"；并且四个场景里三种聚合器的结论完全相同，代码本身没能展示它们的差异，这些都是阅读时要带着的问题。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Vote` | `@dataclass` | 一票：agent 名、答案、置信度；`canonical()` 做规范化 | 投票 + confidence probe + 语义聚类（简化） |
| `plurality` | 函数 | 数每个规范化答案的票数，取最多 | 经典多数投票 |
| `cp_wbft` | 函数 | 每簇置信度求和，最大簇占比 < 阈值则返回 `None` | CP-WBFT、阈值、升级 |
| `decentllms` | 函数 | 每簇分数 = 人数 × (1 − 置信度绝对偏差和) | DecentLLMs（名义上的 geometric median） |
| `scenario` | 函数 | 打印选票、调用三个聚合器、用 `mark` 标注结果 | 攻击测试 |
| `main` | 函数 | 四个手写场景 + Takeaways | 讲义的三种攻击 |

数据流：`main()` → 每个场景构造 5 个 `Vote` → `scenario()` 打印选票 → `plurality / cp_wbft / decentllms` 各自 `canonical()` 聚类并计分 → `mark()` 与正确答案逐字比较 → 打印。

讲义 Build It 中列出的是 `AgentVoter`、`MajorityVote`、`CPWBFT`、`DecentLLMs`、`Scenario` 五个**类**，实际代码只有一个 `Vote` 数据类和若干函数；文件开头导入的 `field` 和 `Callable` 也没有被使用。

---

## 3. 逐段精讲

### 3.1 `Vote` 与"语义聚类"

```python
@dataclass
class Vote:
    agent: str
    answer: str
    confidence: float

    def canonical(self) -> str:
        """Rough semantic clustering: lowercase + strip whitespace/punct."""
        return "".join(c for c in self.answer.lower().strip() if c.isalnum() or c == "." or c == "%")
```

- 讲义说语义聚类是 "the LLM-specific twist"：`"the study reports 4.2%"` 与 `"4.2% improvement"` 应属同一簇。代码只做了"小写 + 删掉非字母数字字符（保留 `.` 和 `%`）"，实测：

| 原答案 | `canonical()` | 问题 |
|-------|--------------|------|
| `4.2%` | `4.2%` | — |
| `4.2 %` | `4.2%` | 空格被去掉，正确合并 |
| `4.2 percent` | `4.2percent` | 与 `4.2%` 分成两簇 |
| `4.2%.` | `4.2%.` | 句尾句号导致分簇 |
| `The study reports 4.2%` | `thestudyreports4.2%` | 讲义自己的例子也合并不了 |
| `4,2%`（欧洲小数写法） | `42%` | **逗号被删，正确答案并入错误簇** |

  最后一行是一个实打实的 bug：在本节的 4.2% vs 42% 题目里，一个用逗号做小数点的诚实 agent 会给错误答案加票。生产中应解析成"数值 + 单位"再比较，或用 embedding 相似度（讲义练习 3）。
- `confidence` 是 agent **自报**的数，代码对它的来源、校准都不做任何处理。

### 3.2 `plurality`：数人头

```python
def plurality(votes):
    counts: dict[str, int] = {}
    rep: dict[str, str] = {}
    for v in votes:
        key = v.canonical()
        counts[key] = counts.get(key, 0) + 1
        rep.setdefault(key, v.answer)
    winner_key = max(counts, key=counts.get)
    return rep[winner_key], counts
```

- `rep` 记录每个簇**第一次出现**的原始答案作为代表，用于输出；`setdefault` 保证只记第一个。
- `max(counts, key=counts.get)` 遍历字典键，按值取最大。**平局时返回最先插入的键**（字典保持插入顺序），所以平局结果取决于投票顺序。实测两票 `42%` / `4.2%` 平局时，谁先投谁赢。
- 不看置信度，任何"相关的多数"都能赢——这就是 monoculture 失败的根源。

### 3.3 `cp_wbft`：置信度加权 + 阈值

```python
def cp_wbft(votes, threshold: float = 0.5):
    weights: dict[str, float] = {}
    ...
        weights[key] = weights.get(key, 0.0) + v.confidence
    total = sum(weights.values()) or 1.0
    winner_key = max(weights, key=weights.get)
    if weights[winner_key] / total < threshold:
        return None, weights
    return rep[winner_key], weights
```

- 对应讲义"核心协议"第 5、6 步：`w(C) = Σ c_i`；最大簇占比不足阈值就拒绝（返回 `None`，`scenario` 显示为 `[rejected below threshold]`）。
- `sum(...) or 1.0`：全员置信度为 0 时避免除零——`0.0` 为假值，`or` 返回 1.0。
- 讲义写的是 `max > threshold * sum`（严格大于才接受），代码是 `< threshold` 才拒绝，即**恰好等于时接受**。两簇平局时占比正好 0.5，会被接受，并按插入顺序取胜者。
- 一个容易忽略的性质：**只有两个簇时，最大簇占比必然 ≥ 0.5**，默认阈值 0.5 永远不会触发拒绝。本节四个场景都只有两个簇，所以"阈值/升级"这条路径从未被执行过。要看到 `None`，需要三个以上簇且票数分散（实测 `A:0.5, B:0.5, C:0.6` → `0.6/1.6 = 0.375`，返回 `None`）。
- 讲义建议 `n = 5–7` 时阈值 0.5–0.67；在两簇场景下把阈值调到 0.6 才会真正起作用（例如 monoculture 场景占比 0.557 会被拒绝并升级——比输出错误答案好）。

### 3.4 `decentllms`：名不副实的"geometric median"

```python
def decentllms(votes):
    clusters: dict[str, list[Vote]] = {}
    for v in votes:
        clusters.setdefault(v.canonical(), []).append(v)

    scores: dict[str, float] = {}
    for key, cluster in clusters.items():
        med = median([v.confidence for v in cluster])
        dist = sum(abs(v.confidence - med) for v in cluster)
        scores[key] = len(cluster) * max(0.0, 1.0 - dist)

    winner_key = max(scores, key=scores.get)
    rep = clusters[winner_key][0].answer
    return rep, scores
```

- 讲义描述的 DecentLLMs：worker 并行提案、**evaluator agent 打分**、最终答案取打分位置的 **geometric median**（使到所有样本点距离之和最小的点，对离群点稳健）。代码的 docstring 自己也承认是简化："evaluator is the aggregator itself, scoring = confidence"。
- 实际公式是 `分数 = 簇大小 × max(0, 1 − Σ|c_i − 中位数|)`：
  - 没有任何"答案空间"或"位置"，答案只是字符串簇，谈不上 geometric median；
  - **置信度的大小被完全忽略**，只用到簇内离散度。3 个置信度都是 0.1 的跟风者得 `3 × 1.0 = 3.0`，比 0.85/0.82 两个独立者（1.94）还高（已实测）；
  - **偏差和没有按簇大小归一化**，簇越大越容易被罚到 0。实测：5 个答对的诚实 agent 置信度 `[0.9, 0.5, 0.9, 0.3, 0.8]`，dist = 1.0，分数 0；一个置信度 0.95 的说谎者单独成簇，dist = 0，得 1.0——**说谎者胜出**。这与"稳健、偏向稠密簇"的设计初衷正好相反；
  - 弃权同理：两个置信度 0 的 "I don't know" 会得到 2.0 分并胜出（见测验 Q11）。
- 在本节四个场景中，各簇置信度都比较集中，dist 不超过 0.2，分数排序与人数排序完全一致，所以 DecentLLMs 的结论与 plurality 完全一样。Takeaways 中"DecentLLMs scoring penalizes high-variance clusters -- helps on monoculture when the dissenting agents are at least as confident as the majority"在本实现里不成立：monoculture 场景中异议者（0.85/0.82）比多数（0.68–0.72）更自信，DecentLLMs 仍以 2.88 对 1.94 选了错误答案。

### 3.5 `scenario` 与 `mark`

```python
    def mark(a: str | None) -> str:
        if a is None:
            return "[rejected below threshold]"
        return "[CORRECT]" if a == correct else "[WRONG]"

    print(f"\n  plurality    -> {plural!r:22s} {mark(plural)}")
    print(f"  CP-WBFT      -> {str(cp)!r:22s} {mark(cp)}")
```

- `mark` 是**闭包**，引用外层参数 `correct`。
- `mark` 用**原始字符串**与正确答案比较，而不是比较 `canonical()`。如果某簇的代表答案恰好写成 `"4.2 %"`，聚类是对的，却会被标成 `[WRONG]`。
- `str(cp)!r`：`cp` 可能是 `None`，先 `str()` 再 `!r`，`None` 会显示成 `'None'`；`!r:22s` 是先取 `repr` 再左对齐到 22 宽。

### 3.6 四个场景

| 场景 | 选票（答案:置信度） | plurality | CP-WBFT 权重 | DecentLLMs 分数 | 三者结论 |
|------|------------------|-----------|-------------|----------------|---------|
| no attack | 4.2%: .85 .80 .75 .70；5%: .40 | 4:1 | 3.10 vs 0.40 | 3.20 vs 1.00 | 全对 |
| byzantine lie | 4.2%: .75 .70 .80 .65；42%: .95 | 4:1 | 2.90 vs 0.95 | 3.20 vs 1.00 | 全对 |
| sycophancy | 4.2%: .85 .80 .82；42%: .35 .30 | 3:2 | 2.47 vs 0.65 | 2.85 vs 1.90 | 全对 |
| monoculture | 42%: .70 .68 .72；4.2%: .85 .82 | 3:2 | 2.10 vs 1.67 | 2.88 vs 1.94 | 全错 |

（权重与分数均为在本机调用函数得到的实测值，按"胜者 vs 败者"排列；单人簇的 DecentLLMs 分数恒为 1.00。）

- 讲义对 sycophancy 的描述前后不一：概念部分说跟风者"aligns with whoever spoke **last**"，Build It 说"copies the **first** answer it sees"；Build It 说"**one** agent"，代码注释写"**Two** conformers echo whoever spoke first"。
- sycophancy 场景只有 2 个跟风者，plurality 本来就 3:2 赢了，**无法证明**"CP-WBFT 的置信度加权缓解了跟风"。把跟风者加到 3 个（置信度 0.35/0.30/0.30）、独立者 2 个（0.85/0.80），才会出现"plurality 和 DecentLLMs 错、CP-WBFT 对"（实测 CP-WBFT 1.65 vs 0.95）。
- byzantine 场景中说谎者置信度 0.95 是全场最高，但人数劣势使它无法翻盘：这是 `f < n/3` 情况下经典 BFT 本来就能处理的。
- monoculture 场景显示了本节最重要的结论：**错误簇人数多，就算个体置信度更低，加权后总和仍然赢**。CP-WBFT 要改判，monoculture 的统一置信度需要低于约 0.557（`3x < 1.67`）；讲义练习 1 写的"below 0.7"在当前代码下不成立（`x = 0.6` 时仍选 42%）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 选票全部手写（脚本化 agent） | 结果确定，便于对比聚合规则 | 无法体现 LLM 的随机性和相关性；生产要用真实多模型采样做攻击测试 |
| 只做单轮聚合 | 聚焦"计票规则" | 没有 PBFT 的三阶段、签名、视图切换，也没有多轮辩论；讲义的 bounded rounds 无从体现 |
| 字符级 `canonical()` 聚类 | 无需任何模型 | "4,2%" 被并入 42%、同义表述分簇；生产用数值解析或 embedding 聚类 |
| 置信度直接取自报值 | 最简单 | 说谎者可以随便报高；讲义练习 4 要求加入独立校准模型 |
| CP-WBFT 阈值 0.5、`<` 才拒绝 | 简单多数语义 | 两簇时永远不会拒绝；平局按插入顺序决定 |
| DecentLLMs 用"人数 × 一致性"打分 | 用一行公式近似"稳健聚合" | 忽略置信度高低，偏差和未归一化，大簇被罚、单人簇满分；与 geometric median 无关 |
| `mark` 用原始字符串比较 | 简单 | 与聚类口径不一致；应比较规范化结果 |
| 场景之间结论完全一致 | 演示"monoculture 谁都救不了" | 没能展示不同聚合器的差异，削弱了讲义论点 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 注解延迟求值，允许 `str \| None` 写法 |
| `@dataclass` + 方法 | `class Vote: ... def canonical(self)` | 数据类也可以定义普通方法 |
| 生成器表达式 + `str.join` | `"".join(c for c in s if c.isalnum() or c == ".")` | 逐字符过滤后拼接，不生成中间列表 |
| 字符串方法链 | `self.answer.lower().strip()` | 先转小写再去首尾空白 |
| `str.isalnum()` | `c.isalnum()` | 是否字母或数字（注意对中文字符也返回 True） |
| `dict.get(k, 0) + 1` | `counts[key] = counts.get(key, 0) + 1` | 经典计数写法；也可用 `collections.Counter` |
| `dict.setdefault` | `rep.setdefault(key, v.answer)`、`clusters.setdefault(k, []).append(v)` | 只在键不存在时设置，返回该键的值 |
| `max(d, key=d.get)` | `max(counts, key=counts.get)` | 取值最大的键；平局取最先插入的 |
| `or` 提供默认值 | `sum(weights.values()) or 1.0` | 左侧为 0 时取右侧 |
| 元组返回值 + 解包 | `return rep[w], counts`；`plural, counts = plurality(votes)` | 一次返回多个值 |
| `statistics.median` | `median([v.confidence for v in cluster])` | 偶数个元素时取中间两数的平均 |
| 列表推导式 | `[v.confidence for v in cluster]` | 从对象列表中取字段 |
| 内置 `abs` / `sum` / `max` | `sum(abs(v.confidence - med) for v in cluster)`、`max(0.0, 1.0 - dist)` | 绝对值、求和、截断到非负 |
| 嵌套函数（闭包） | `scenario` 内的 `def mark(a)` | 读取外层的 `correct` |
| f-string 转换与格式 | `{v.agent:12s}`、`{v.answer!r:20s}`、`{v.confidence:.2f}` | 宽度对齐、`repr` 显示、两位小数 |
| 类型注解 | `-> tuple[str \| None, dict[str, float]]` | 返回"答案或 None"加上权重字典 |
| 关键字参数调用 | `scenario("no attack", correct="4.2%", votes=[...])` | 显式写参数名，提高可读性 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 |

---

## 6. 运行结果解读

实际运行（Python 3.13，`cd code && python3 main.py`，瞬间完成，结果确定）。截取关键部分：

```text
SCENARIO: byzantine lie
  agent-a      -> '4.2%'                conf=0.75
  ...
  agent-d      -> '42%'                 conf=0.95
  agent-e      -> '4.2%'                conf=0.65

  plurality    -> '4.2%'                 [CORRECT]
  CP-WBFT      -> '4.2%'                 [CORRECT]
  DecentLLMs   -> '4.2%'                 [CORRECT]

SCENARIO: sycophantic conformity
  plurality    -> '4.2%'                 [CORRECT]
  CP-WBFT      -> '4.2%'                 [CORRECT]
  DecentLLMs   -> '4.2%'                 [CORRECT]

SCENARIO: monoculture (correlated errors)
  agent-a      -> '42%'                 conf=0.70
  agent-b      -> '42%'                 conf=0.68
  agent-c      -> '42%'                 conf=0.72
  agent-d      -> '4.2%'                conf=0.85
  agent-e      -> '4.2%'                conf=0.82

  plurality    -> '42%'                  [WRONG]
  CP-WBFT      -> '42%'                  [WRONG]
  DecentLLMs   -> '42%'                  [WRONG]

Takeaways:
  plurality is wrong whenever a correlated cluster is >= half the votes.
  CP-WBFT mitigates sycophancy because conformers have low confidence.
  ...
```

逐项解读：

- **no attack / byzantine**：诚实一方 4:1，三者都对。说谎者 0.95 的高置信度在 CP-WBFT 里只占 `0.95 / 3.85 ≈ 25%`。
- **sycophancy**：三者都对，但原因是 plurality 3:2 本来就赢。Takeaways 第 2 条的结论在这组数据上**没有被验证**（见 3.6 与测验 Q12）。
- **monoculture**：三者全错。用实测数据核对：plurality 3:2；CP-WBFT `{'42%': 2.10, '4.2%': 1.67}`，占比 0.557 ≥ 0.5；DecentLLMs `{'42%': 2.88, '4.2%': 1.94}`。
- **Takeaways 第 1 条**说"相关簇 ≥ 半数时 plurality 错"——严格说"恰好一半"时是平局，按插入顺序决定，不一定错。
- **Takeaways 最后一条**说"错误簇更大**且更自信**时谁都救不了"，但本次数据中错误簇个体置信度更低（均值 0.70 对 0.835），三个聚合器照样全错——问题比 Takeaways 描述的更严重：**只要人数占优，就足够了**。
- 结果中从未出现 `[rejected below threshold]`：四个场景都只有两个簇，CP-WBFT 的阈值分支没有被执行。

---

## 7. 动手改一改

1. **找临界点（讲义练习 1）**：把 monoculture 三票的置信度统一改成 `x`，从 0.70 每次减 0.01，找出 CP-WBFT 改判的位置（应在 0.55–0.56 之间），再把 `threshold` 改为 0.6 观察 monoculture 场景被拒绝升级。
2. **补一个能区分聚合器的场景**：加入"3 个低置信度跟风者 vs 2 个高置信度独立者"，确认只有 CP-WBFT 选对。
3. **修 `canonical()`**：用正则提取数值，把 `,` 作为小数点的写法、`percent`、`%`、句尾标点统一处理，比较数值是否在容差内；验证 `"4,2%"`、`"4.2 percent"`、`"The study reports 4.2%"` 都归入 `4.2%` 簇。
4. **处理弃权（讲义练习 2）**：把 "I don't know" 排除在簇之外，但按每票 0.5 计入 CP-WBFT 的分母；确认 2 个弃权 + 3 票分歧时返回 `None` 并升级，而原 DecentLLMs 会选出 "I don't know"。
5. **修 DecentLLMs 打分**：改为 `Σc × max(0, 1 − 平均绝对偏差)`，验证"5 个诚实但置信度分散 vs 1 个高置信度说谎者"时选对；进阶：给每个答案引入数值位置，实现 Weiszfeld 算法求真正的 geometric median。
6. **独立校准（讲义练习 4）**：为每个 agent 维护历史准确率，用它替代或修正自报置信度（例如 `c' = c × acc`），观察 byzantine 场景中说谎者影响的变化；再给协议加上"最多 2 轮、第二轮可见他人答案"，模拟跟风如何在轮次中放大。

---

## 8. 常见坑

- **把字符规范化当语义聚类**：删字符会把 "4,2%" 变成 "42%"，制造假多数；数值题应解析数值。
- **以为置信度加权能救 monoculture**：加权的是"总和"，人数多的簇天然占优；monoculture 只能靠多样性和独立 verifier。
- **两簇时以为阈值 0.5 有用**：最大簇占比必然 ≥ 0.5，永远不会拒绝。
- **平局依赖顺序**：`max(d, key=d.get)` 平局取先插入的键，投票顺序会悄悄决定结果；应显式定义平局规则（升级或随机并记录）。
- **把弃权当答案**：不过滤 "I don't know" 时，它会成为一个簇，甚至在 DecentLLMs 中胜出。
- **相信自报置信度**：说谎者可以报 0.95；需要独立校准或历史信任分。
- **忘记归一化**：离散度惩罚不除以簇大小，会系统性地惩罚大簇、奖励单人簇。
- **结果比较口径不一**：聚类用规范化字符串，判对错却用原字符串，会出现"聚对了却标错"的情况。
- **"一致"当"正确"**：四个场景里 monoculture 是"一致地错"；共识输出仍需独立核查。
