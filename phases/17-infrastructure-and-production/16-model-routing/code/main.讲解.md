# 代码讲解 · main.py

> **所属小节**：阶段 17 · 基础设施与生产 · 第 16 节 将模型路由作为降低成本的基本手段 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数，瞬间完成） ｜ **依赖**：仅标准库（`dataclasses`、`random`），不调用任何真实模型

---

## 1. 这份代码在考察什么

讲义的主张：把简单请求交给便宜模型、复杂请求交给 frontier 模型，可以在质量基本不变的情况下降本 20–60%。代码在同一个混合难度工作负载上比较三种做法：

1. **NO_ROUTE**：全部走 frontier，作为成本与质量的基线。
2. **PRE_ROUTE**：前置分类器，simple 走 cheap，其余走 frontier。
3. **CASCADE**：所有请求先走 cheap；"不自信"时再升级到 frontier（两次都计费）。

输出三项指标：混合成本、平均质量、升级次数。

> 一句话：**用一个 100 行的模拟器展示"省多少钱、掉多少质量、升级多少次"三者之间的权衡**。但它的 pre-route 用的是完美分类器、cascade 的置信度是"预言机"，导致输出与讲义"cascade 质量下限最好"的说法相反——看清这些简化，才能把它扩展成可信的评估工具。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| 4 个价格常量 | 模块常量 | cheap（$0.25 / $1.00）与 frontier（$3 / $15）的输入 / 输出单价 | 模型对的价格差 |
| `Query` | `@dataclass` | 一个请求：难度、prompt 长度、输出长度 | 工作负载 |
| `make_workload()` | 函数 | 60% simple、30% medium、10% hard，各自的长度范围不同 | 难度分布 |
| `cost_of()` | 函数 | 按路由计算单个请求的成本 | 混合成本 |
| `quality()` | 函数 | 按路由与难度返回质量分（frontier 恒为 1.0） | 质量损失 |
| `simulate()` | 函数 | 三种模式的核心逻辑，累加成本、质量与升级数 | 路由模式 |
| `report()` | 函数 | 打印一行并计算相对基线的节省比例 | — |
| `main()` | 函数 | 生成负载、算基线、依次运行三种模式 | — |

数据流：`make_workload()` → `simulate("NO_ROUTE")` 得到基线成本 → 对三种模式分别 `simulate(p, base)` → `report(row, baseline)`。

同目录的 `main.ts` 是 TypeScript 版本（不在本批讲解范围）。

---

## 3. 逐段精讲

### 3.1 价格常量：价差是路由的前提

```python
CHEAP_INPUT = 0.25
CHEAP_OUTPUT = 1.00
FRONTIER_INPUT = 3.00
FRONTIER_OUTPUT = 15.00
```

- cheap 的输入单价是 frontier 的 `0.25 / 3 ≈ 8.3%`，输出是 `1 / 15 ≈ 6.7%`。讲义 The Problem 说 Haiku 级模型只要"3% 的成本"，与这里的价格并不一致；按代码价格，一个请求走 cheap 大约省 92%–93%。
- 价差越大，路由越值钱；价差越小，cascade 中"白跑一次便宜模型"的浪费占比越高。

### 3.2 `Query` 与 `make_workload()`：难度与长度相关

```python
def make_workload(n: int = 1000, seed: int = 7) -> list[Query]:
    rng = random.Random(seed)
    reqs = []
    for _ in range(n):
        p = rng.random()
        if p < 0.6:
            reqs.append(Query("simple", rng.randint(200, 1000), rng.randint(50, 200)))
        elif p < 0.9:
            reqs.append(Query("medium", rng.randint(800, 3000), rng.randint(100, 400)))
        else:
            reqs.append(Query("hard", rng.randint(2000, 8000), rng.randint(200, 1500)))
    return reqs
```

- 用一个均匀随机数 `p` 和累积阈值（0.6、0.9）实现 60/30/10 的类别分布，这是离散分布抽样的常用写法。
- `rng.randint(a, b)` 包含两端。
- **关键设计**：难度越高，prompt 和输出越长。种子 7 下实际有 simple 629、medium 276、hard 95 个，但按 frontier 成本算，三者分别占 30.7%、34.9%、34.4%。也就是说 hard 只占 9.5% 的请求却占三分之一的成本——**路由的节省取决于成本占比，而不是条数占比**。

### 3.3 `cost_of()` 与 `quality()`

```python
def cost_of(route: str, q: Query) -> float:
    if route == "cheap":
        return (q.prompt_tokens / 1e6) * CHEAP_INPUT + (q.output_tokens / 1e6) * CHEAP_OUTPUT
    return (q.prompt_tokens / 1e6) * FRONTIER_INPUT + (q.output_tokens / 1e6) * FRONTIER_OUTPUT


def quality(route: str, q: Query) -> float:
    """Toy quality score per difficulty on route."""
    if route == "frontier":
        return 1.0
    return {"simple": 0.99, "medium": 0.92, "hard": 0.75}[q.difficulty]
```

- `cost_of` 对非 `"cheap"` 的任何字符串都按 frontier 计价（"默认分支"写法）；传错路由名不会报错，要小心。
- `quality` 把 frontier 定义为 1.0（相对质量），便宜模型在 simple / medium / hard 上分别为 0.99 / 0.92 / 0.75。它用一个字典字面量当查找表，`[q.difficulty]` 直接取值。
- 这些分数是假设值。真实系统中要用离线评测或线上 LLM-judge 得到，并且同一难度内部也有方差。

### 3.4 `simulate()`：三种模式

```python
        if pattern == "NO_ROUTE":
            total_cost += cost_of("frontier", q)
            total_q += 1.0
        elif pattern == "PRE_ROUTE":
            if q.difficulty == "simple":
                total_cost += cost_of("cheap", q)
                total_q += quality("cheap", q)
            else:
                total_cost += cost_of("frontier", q)
                total_q += 1.0
```

- **PRE_ROUTE 读的是真实难度** `q.difficulty`，相当于一个 100% 准确的分类器，而且分类本身不花钱、不加延迟。现实中分类器（规则、小模型或 embedding）会出错：把 simple 送去 frontier 浪费钱，把 hard 送去 cheap 掉质量且没有兜底。这是 pre-route 最主要的风险，代码完全没有体现（测验 Q10 加入了准确率参数）。

```python
        elif pattern == "CASCADE":
            total_cost += cost_of("cheap", q)
            confident = (q.difficulty == "simple") or (q.difficulty == "medium" and rng.random() < 0.5)
            if confident:
                total_q += quality("cheap", q)
            else:
                escalated += 1
                total_cost += cost_of("frontier", q)
                total_q += 1.0
```

- 每个请求**先付一次 cheap 的钱**；不自信时再付 frontier 的钱——被升级的请求付两次，这正是 cascade 的代价。
- `confident` 由真实难度决定：simple 永远自信，hard 永远不自信，medium 抛硬币。这是一个"半预言机"：现实中便宜模型可能对难题**自信地答错**（最危险的情况），也可能对简单题过度谨慎。代码里不存在"自信但错"的请求，所以 cascade 的质量损失全部来自留在 cheap 上的那一半 medium（0.92）。
- 期望升级数 `95 + 276 × 0.5 = 233`，实际 229；升级率约 22.9%，高于讲义说的"约 10% 流量"，低于讲义"超过 30% 视为过度路由"的门槛。
- `rng = random.Random(11)` 在函数开头创建，只有 CASCADE 用到；每次调用 `simulate` 都重新播种，结果可复现。

```python
    return {
        "pattern": pattern,
        "cost": total_cost,
        "mean_quality": total_q / len(reqs),
        "escalated": escalated,
    }
```

- 平均质量 = 质量分之和 / 请求数，是一个非常粗的汇总：它不区分"很多请求轻微下降"和"少数请求严重下降"，而后者往往更致命。

### 3.5 `report()` 与 `main()`

```python
def report(row: dict, baseline: float) -> None:
    save = (baseline - row["cost"]) / baseline * 100
    print(f"{row['pattern']:12}  cost=${row['cost']:7.2f}  save={save:5.1f}%  "
          f"quality={row['mean_quality']*100:5.1f}%  escalated={row['escalated']:4}")
```

- 节省比例 = (基线 − 当前) / 基线。`main()` 中先单独跑一次 `NO_ROUTE` 取基线，然后在循环里又跑了一次 `NO_ROUTE`（用来打印），属于轻微的重复计算。
- 元组 `("NO_ROUTE", "PRE_ROUTE", "CASCADE")` 作为循环序列。
- 结尾的结论 "CASCADE guarantees quality floor" 与本次输出相矛盾（CASCADE 98.2% < PRE_ROUTE 99.4%），原因见 3.4。

另外两处与讲义不一致：讲义 Use It 说代码会模拟 **ensemble**，实际没有实现；讲义给出的延迟特征（pre-route +5–10 ms、cascade 1.2 倍 / 2 倍）在代码里也没有任何计算。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用真实难度做 pre-route | 代码最短 | 等于完美分类器，掩盖误判风险；应加入准确率或混淆矩阵 |
| 置信度由难度决定 | 不需要模拟 logprobs | 没有"自信地答错"；应引入与正确性相关但不完美的置信度分布 |
| 固定质量分 | 直观 | 应来自离线评测和线上 LLM-judge，并给出方差 |
| 只看平均质量 | 一个数便于比较 | 掩盖尾部；生产中按任务类型、用户群分别看，并关注最差切片 |
| 难度与长度正相关 | 贴近真实流量 | 让"条数占比"与"成本占比"差别很大，这是本模拟最有价值的设定 |
| 不模拟延迟与 ensemble | 聚焦成本 | 讲义承诺了两者；补上后才能完整比较三种模式 |
| 升级时付两次费 | 符合 cascade 真实成本 | 正确；还应加上校验步骤本身的成本（如调用 judge） |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass` | `class Query` | 自动生成构造函数 |
| 行内注释说明取值 | `difficulty: str  # 'simple' \| 'medium' \| 'hard'` | 更严谨的写法是 `Literal["simple", "medium", "hard"]` |
| 函数 docstring | `"""Toy quality score per difficulty on route."""` | 写在函数体第一行，说明用途 |
| 累积阈值抽样 | `if p < 0.6: ... elif p < 0.9: ... else:` | 用一个均匀随机数实现 60/30/10 分布 |
| `rng.randint(a, b)` | `rng.randint(200, 1000)` | 闭区间随机整数 |
| 字典字面量当查找表 | `{"simple": 0.99, ...}[q.difficulty]` | 创建后立即按键取值 |
| 布尔表达式组合 | `(q.difficulty == "simple") or (q.difficulty == "medium" and rng.random() < 0.5)` | `or` / `and` 短路求值：simple 时右侧不会执行，也就不消耗随机数 |
| `if / elif` 分派 | `if pattern == "NO_ROUTE": ... elif ...` | 按字符串选择模式；更可扩展的写法是"模式名 → 函数"的字典 |
| 在元组上循环 | `for p in ("NO_ROUTE", "PRE_ROUTE", "CASCADE"):` | 元组是不可变序列 |
| f-string 内计算 | `{row['mean_quality']*100:5.1f}` | 先乘 100 再格式化为一位小数 |
| 入口保护 | `if __name__ == "__main__":` | 直接运行时才执行 |

注意上表"布尔表达式组合"一行：`or` 的短路求值意味着 simple 请求**不会**调用 `rng.random()`，只有 medium 才会消耗随机数（hard 时 `q.difficulty == "medium"` 为假，`and` 右侧也不执行）。这影响随机序列，但不影响期望值。

---

## 6. 运行结果解读

实际运行（Python 3.13）：

```text
MODEL ROUTING — three patterns, 1000 requests, mixed difficulty
NO_ROUTE      cost=$   7.52  save=  0.0%  quality=100.0%  escalated=   0
PRE_ROUTE     cost=$   5.38  save= 28.4%  quality= 99.4%  escalated=   0
CASCADE       cost=$   4.42  save= 41.2%  quality= 98.2%  escalated= 229

Read: PRE_ROUTE saves big when the classifier is accurate. CASCADE
guarantees quality floor but adds latency on escalated requests.
```

逐项解读（分项数据由同一负载另行计算）：

- **NO_ROUTE $7.52**：simple $2.306 + medium $2.627 + hard $2.585。
- **PRE_ROUTE $5.38、省 28.4%**：只有 simple 从 $2.306 降到 $0.172。simple 占 62.9% 的请求，却只占 30.7% 的成本，所以只省了 28%——远低于讲义 The Problem 按"条数"估算的约 65%。质量 99.37% = `(629 × 0.99 + 371 × 1.0) / 1000`。
- **CASCADE $4.42、省 41.2%**：所有请求先跑 cheap（$0.570），再加 hard 全部升级（$2.585）与约一半 medium 升级（期望 $1.31）。它比 pre-route 省得多，是因为把约 138 个 medium 留在了 cheap，代价是质量降到 98.2%。
- **结论句的问题**：在这份模拟里 cascade 的质量反而更低，因为 pre-route 用的是完美分类器。若给 pre-route 加上准确率（测验 Q10），准确率低于约 72% 时，cascade 在成本（$4.47 期望）和质量（98.27%）上同时占优；高于 72% 时两者是"成本 vs 质量"的权衡。
- **升级率 22.9%**：在讲义"> 30% 视为过度路由"的门槛之内，但比讲义"约 10% 流量被升级"高一倍多，生产中这会显著拉高 P95 延迟（被升级请求约 2 倍延迟）。

---

## 7. 动手改一改

1. **讲义练习 1**：给 PRE_ROUTE 增加 `classifier_acc` 参数（simple 以 `acc` 概率送 cheap，其余以 `1 − acc` 概率误送 cheap），扫描 0.7–1.0，找出 cascade 同时占优的区间（应约为 72% 以下）。
2. **"自信地答错"**：为 CASCADE 引入一个与正确性相关但不完美的置信度：例如 hard 请求有 15% 概率"自信"（留在 cheap，质量 0.75），simple 有 3% 概率"不自信"（白白升级），观察质量与成本变化。
3. **实现 ensemble**：对 5% 的样本同时跑 cheap 与 frontier（两次计费），选质量高者；其余走 pre-route。比较成本与质量，并说明它更适合作为"评估手段"而不是"生产路由"。
4. **加入延迟**：设 cheap 每请求 300 ms、frontier 900 ms、分类器 8 ms、cascade 校验 60 ms，计算三种模式的 P50 / P95 延迟，验证讲义的"1.2 倍中位、2 倍升级"说法在什么参数下成立。
5. **漂移实验**：把难度分布从 60/30/10 改为 40/35/25，观察 cascade 的升级率与成本变化，并用测验 Q12 的 `escalation_drift` 检测。
6. **进阶**：把 `quality()` 换成"按请求抽样的正确 / 错误"（伯努利），报告每种模式下错误请求的数量和它们集中在哪个难度，体会"平均质量"掩盖了什么。

---

## 8. 常见坑

- **按条数估算节省**：简单请求往往更短，按成本占比算才准确；本模拟中 63% 的请求只占 31% 的成本。
- **用完美分类器评估 pre-route**：离线用真实标签评估会严重高估 pre-route；必须用分类器的真实预测。
- **把 cascade 的置信度当成可靠的**：便宜模型会自信地答错；置信度阈值需要在标注集上校准，并配合拒答 / 含糊检测与外部校验。
- **忘了 cascade 的双重计费与延迟**：被升级的请求付两次费、延迟约 2 倍；升级率越高，cascade 越不划算。
- **只看平均质量**：平均下降 1% 可能是某个任务类型下降 10%；按切片看。
- **只用任务分类一个信号**：skill 明确拒绝；同一任务内部难度差别很大，要结合长度、相似度和置信度。
- **没有在线门禁就上线**：讲义认为漂移是头号风险——离线评测集来自旧分布，必须用在线 LLM-judge、点赞率、升级率和拒答率持续把关。
