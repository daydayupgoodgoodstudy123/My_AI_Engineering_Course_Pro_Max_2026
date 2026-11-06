# 代码讲解 · main.py

> **所属小节**：阶段 17 · 基础设施与生产 · 第 15 节 批处理 APIs：作为行业标准的五折优惠 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数，约 0.1 秒） ｜ **依赖**：仅标准库，不调用任何真实 API

---

## 1. 这份代码在考察什么

讲义的核心主张是"不需要实时的就该走 batch，并且叠加 prompt 缓存"。代码用一个纯算术的成本模型，比较同一批工作在四种配置下的账单：

| 配置 | 前缀（共享系统提示） | 每文档输入 | 输出 |
|------|-------------------|-----------|------|
| SYNC | 原价 | 原价 | 原价 |
| SYNC + CACHE | 写 1 次（1.25×），之后读（0.1×） | 原价 | 原价 |
| BATCH | 全部 × 0.5 | × 0.5 | × 0.5 |
| BATCH + CACHE | SYNC + CACHE 的结果 × 0.5 | | |

并在三种典型负载上运行：长文档摘要、海量短条目分类、少量重型报告。

> 一句话：**把"batch 5 折 × 缓存 1 折"写成四个函数，让学习者看到叠加折扣到底能省多少**。同时，它的输出本身就反驳了标题里的"约 10%"——三个场景分别是 24.3%、17.1%、41.3%。读懂这个差异，是本节最重要的收获。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `BASE_INPUT` 等 5 个常量 | 模块常量 | 输入 / 输出 / 缓存读 / 5 分钟写入价，batch 折扣 0.5 | 价格表 |
| `cost_sync()` | 函数 | 逐文档累加原价成本 | 基线 |
| `cost_sync_cache()` | 函数 | 前缀写一次、之后读缓存，其余原价 | 同步 + 缓存 |
| `cost_batch()` | 函数 | `cost_sync × 0.5` | batch 折扣 |
| `cost_batch_cache()` | 函数 | `cost_sync_cache × 0.5` | 叠加折扣 |
| `run()` | 函数 | 计算四种成本并以"占基线百分比"打印 | 对比 |
| `main()` | 函数 | 三个场景调用 `run()` | 不同 token 构成 |

数据流：`main()` → `run(label, docs, prefix, per_doc, output)` → 四个 `cost_*` 函数 → 打印绝对金额与百分比。

同目录的 `main.ts` 是 TypeScript 版本（不在本批讲解范围）。

---

## 3. 逐段精讲

### 3.1 模块 docstring 与价格常量

```python
"""Batch vs synchronous cost simulator — stdlib Python.

Models a 50k-document pipeline across four configurations:
  SYNC              : no discount, no cache
  SYNC + CACHE      : system prompt cached after first call
  BATCH             : 50% discount, no cache
  BATCH + CACHE     : stacked (~10% of SYNC bill)
"""

BASE_INPUT = 3.00
BASE_OUTPUT = 15.00
CACHED_INPUT = 0.30
CACHE_WRITE_5MIN = 1.25 * BASE_INPUT
BATCH_DISCOUNT = 0.50
```

- 价格与上一节一致（Claude Sonnet 级，$/M token）：输入 3、输出 15、缓存读 0.30、5 分钟写入 3.75。
- `BATCH_DISCOUNT = 0.50` 是"乘数"而不是"折扣额"：成本 × 0.5。
- docstring 写"stacked (~10% of SYNC bill)"，但下面的运行结果中没有一个场景接近 10%（见第 6 节）。

### 3.2 `cost_sync()`：基线

```python
def cost_sync(docs: int, prefix_tokens: int, per_doc_tokens: int, out_tokens: int) -> float:
    cost = 0.0
    for _ in range(docs):
        cost += (prefix_tokens / 1e6) * BASE_INPUT
        cost += (per_doc_tokens / 1e6) * BASE_INPUT
        cost += (out_tokens / 1e6) * BASE_OUTPUT
    return cost
```

- 每个文档的成本 = 前缀 + 自身内容 + 输出，三段分别乘单价。
- 每次循环加的是同一个数，所以等价于 `docs × (每文档成本)`，循环只是为了让计算过程"看得见"。20 万次循环在 CPython 里也只需几十毫秒，但对更大规模应改用闭式解（见第 7 节）。
- 浮点数反复累加会积累微小的舍入误差（N 很大时更明显），闭式解只做一次乘法，更精确。输出里 `$510.01`、`$255.01` 末尾的 1 分则不是误差，而是唯一一次写入溢价（`4,000 × (3.75 − 0.30) / 1e6 ≈ $0.014`）带来的。

### 3.3 `cost_sync_cache()`：前缀只写一次

```python
def cost_sync_cache(docs: int, prefix_tokens: int, per_doc_tokens: int, out_tokens: int) -> float:
    cost = (prefix_tokens / 1e6) * CACHE_WRITE_5MIN
    for i in range(docs):
        if i > 0:
            cost += (prefix_tokens / 1e6) * CACHED_INPUT
        cost += (per_doc_tokens / 1e6) * BASE_INPUT
        cost += (out_tokens / 1e6) * BASE_OUTPUT
    return cost
```

- 第一个文档的前缀以写入价计费（循环外那一行），从第二个起（`i > 0`）按读取价计费；写入价替代而不是叠加原价，这与 Anthropic 的计费方式一致。
- **每文档内容和输出不享受缓存**——这是"叠加折扣到不了 10%"的根本原因。
- 隐含的乐观假设：
  1. 缓存命中率 100%，写入只发生一次；
  2. 缓存全程不过期。讲义说这个管道同步跑要 4 小时，5 分钟 TTL 只有在请求持续不断地到达时才会一直有效；
  3. 没有并行陷阱。上一节讲过：多个共享前缀的请求在首个写入完成前同时到达，都会 miss。batch 内部的请求正是由 provider 并行调度的，实际命中率需要用返回的 cached tokens 去测量。

### 3.4 `cost_batch()` 与 `cost_batch_cache()`：直接乘 0.5

```python
def cost_batch(docs: int, prefix_tokens: int, per_doc_tokens: int, out_tokens: int) -> float:
    return cost_sync(docs, prefix_tokens, per_doc_tokens, out_tokens) * BATCH_DISCOUNT


def cost_batch_cache(docs: int, prefix_tokens: int, per_doc_tokens: int, out_tokens: int) -> float:
    return cost_sync_cache(docs, prefix_tokens, per_doc_tokens, out_tokens) * BATCH_DISCOUNT
```

- 复用同步函数再整体打 5 折，对应讲义"50% discount on both read and write"以及"50% flat on input + output"。
- 这种组合写法简洁，但把"batch 内缓存行为与同步完全相同"这个假设藏了起来。

### 3.5 `run()` 与 `main()`

```python
def run(label: str, docs: int, prefix: int, per_doc: int, output: int) -> None:
    sc = cost_sync(docs, prefix, per_doc, output)
    ...
    print(f"  SYNC + CACHE    : ${scc:10.2f}  ({scc/sc*100:5.1f}% of baseline)")
```

- 每种配置都打印"绝对金额 + 占基线百分比"，百分比直接用 f-string 表达式 `scc/sc*100` 计算。
- `main()` 用关键字参数调用 `run`（`docs=50_000, prefix=4000, ...`），三个场景的 token 构成差异很大：

| 场景 | 文档数 | 前缀 | 每文档 | 输出 | 前缀占 SYNC 成本 |
|------|-------|------|-------|------|----------------|
| 夜间摘要 | 50,000 | 4,000 | 2,000 | 200 | 57% |
| 内容分类 | 200,000 | 1,500 | 300 | 50 | 73% |
| 重型报告 | 1,000 | 6,000 | 15,000 | 2,000 | 19% |

"前缀占 SYNC 成本"越高，缓存越有用——这正好解释了三个场景的叠加比例排序：分类（17.1%）< 摘要（24.3%）< 报告（41.3%）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 逐文档循环 | 计算过程直观 | O(N)；生产估算用闭式公式即可 |
| 缓存命中率 100%、只写一次 | 展示理想上限 | batch 内并行调度与 TTL 会降低命中率；应以实测 cached tokens 比例代入 |
| batch = 同步 × 0.5 | 讲义：输入输出一律 5 折 | 隐含"batch 内缓存行为与同步相同"；Anthropic 需显式 `cache_control`，OpenAI 自动缓存（skill） |
| 固定价格常量 | 可复现 | 价格会变；应从配置读取并标注日期 |
| 只算 token 费用 | 聚焦折扣 | 忽略重试、失败行重提、溢出到同步的额外成本 |
| 三个场景覆盖不同 token 构成 | 展示折扣依赖 token 构成 | 标题仍写"~10%"，与结果矛盾；应改为"5%–50%，取决于前缀占比" |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 多行模块 docstring | 文件开头的 `"""..."""` | 说明模块用途，可在 `help(main)` 中看到 |
| `from __future__ import annotations` | 第 11 行 | 注解延迟求值；本文件只用了简单类型，主要是保持风格一致 |
| 函数类型注解 | `def cost_sync(docs: int, ...) -> float:` | 说明参数和返回值类型 |
| `_` 作为循环变量 | `for _ in range(docs):` | 表示不使用的变量 |
| 函数组合 | `return cost_sync(...) * BATCH_DISCOUNT` | 在已有函数基础上构造新函数 |
| 数字分隔符 | `docs=50_000`、`per_doc=15_000` | 下划线提升可读性 |
| 关键字参数调用 | `run("...", docs=50_000, prefix=4000, per_doc=2000, output=200)` | 参数多时更清晰 |
| f-string 内嵌表达式 | `{scc/sc*100:5.1f}` | 花括号里可以直接计算 |
| f-string 宽度精度 | `{sc:10.2f}` | 宽度 10、两位小数 |
| 转义换行 | `print(f"\n{label}")` | 先输出空行再输出标题 |
| 入口保护 | `if __name__ == "__main__":` | 被 import 时不执行 `main()` |

---

## 6. 运行结果解读

实际运行（Python 3.13）：

```text
BATCH API ECONOMICS — stack batch with prompt caching for ~10% of sync bill

Nightly doc summarization (50k docs)
  docs=50000, prefix=4000, per_doc=2000, output=200
  SYNC            : $   1050.00  (baseline)
  SYNC + CACHE    : $    510.01  ( 48.6% of baseline)
  BATCH           : $    525.00  ( 50.0% of baseline)
  BATCH + CACHE   : $    255.01  ( 24.3% of baseline)

Content classification (200k items, short per item)
  docs=200000, prefix=1500, per_doc=300, output=50
  SYNC            : $   1230.00  (baseline)
  SYNC + CACHE    : $    420.01  ( 34.1% of baseline)
  BATCH           : $    615.00  ( 50.0% of baseline)
  BATCH + CACHE   : $    210.00  ( 17.1% of baseline)

Large report draft (small N, heavy per item)
  docs=1000, prefix=6000, per_doc=15000, output=2000
  SYNC            : $     93.00  (baseline)
  SYNC + CACHE    : $     76.82  ( 82.6% of baseline)
  BATCH           : $     46.50  ( 50.0% of baseline)
  BATCH + CACHE   : $     38.41  ( 41.3% of baseline)
```

逐项解读：

- **BATCH 恒为 50.0%**：整体打 5 折，与 token 构成无关。
- **SYNC + CACHE 差异很大**：摘要 48.6%、分类 34.1%、报告 82.6%，由前缀在成本中的占比决定（57%、73%、19%）。
- **BATCH + CACHE 正好是 SYNC + CACHE 的一半**：24.3%、17.1%、41.3%，都远离标题的"约 10%"。以摘要为例，叠加后的 $255 中前缀只剩约 $30，每文档输入 $150、输出 $75 才是大头。
- **重型报告**：BATCH（$46.50）比 SYNC + CACHE（$76.82）便宜得多——前缀小、每条内容大的负载，batch 才是主要杠杆。
- **与讲义的对照**：讲义 The Problem 说 $2,000 → $180（约 9%），本代码第一个场景是 $1,050 → $255（24.3%）；讲义 "Stack with caching" 一节的公式漏掉了每文档内容，即便按它算（每文档 0 token）也是 $750 → $105（14.0%）。

---

## 7. 动手改一改

1. **讲义练习 1**：加一个场景 `run("Ex1", docs=100_000, prefix=3000, per_doc=..., output=500)`，分别取 `per_doc` = 0 / 500 / 2,000，记录叠加比例（应为 25.5% / 27.5% / 32.0%）。
2. **闭式解**：把四个函数改写成不含循环的公式（参考测验 Q10），用 `assert abs(new - old) < 1e-6` 验证与原函数结果一致。
3. **引入命中率**：给 `cost_sync_cache` 增加 `hit_rate` 参数，未命中的请求按写入价计费；画出叠加比例随命中率（0.3–1.0）的变化，找出"开缓存反而更贵"的门槛（上一节测验 Q14：约 22%）。
4. **找"10%"的条件**：固定前缀 4,000，网格搜索 `per_doc` 与 `output`，打印叠加比例 ≤ 10% 的组合，验证理论下限 5%。
5. **加入 1 小时 TTL**：增加 `CACHE_WRITE_1HR = 2.0 * BASE_INPUT`，假设 batch 被拆成 k 个间隔超过 5 分钟的子批次，比较两档 TTL 的成本。
6. **进阶（讲义练习 5）**：增加"自建 GPU 夜间跑"的成本模型（每小时 GPU 价格 × 运行时长，运行时长 = 总 token / 吞吐），用你自己的硬件假设求出与 batch + cache 的盈亏平衡点。

---

## 8. 常见坑

- **直接套用"约 10%"**：叠加比例由前缀 / 每条输入 / 输出三段的占比决定，范围在 5%（理论下限）到 50% 之间。
- **忘了输出不能缓存**：输出单价是输入的 5 倍，输出越长，缓存的边际收益越小。
- **假设 batch 内缓存 100% 命中**：batch 内请求由 provider 并行调度，缓存是否命中要看返回的 cached tokens；Anthropic 还要求显式 `cache_control`。
- **把 24 小时当成 P50**：典型 P50 是 2–6 小时；但给用户承诺时要按 P99 留余量，并准备溢出通道。
- **15 分钟以内的预期也用 batch**：skill 明确拒绝；这类负载应走 semi-interactive 的异步队列。
- **以为一个 batch 客户端能通吃所有厂商**：各家文件格式不同，必须写适配器。
- **"production"就等于"实时"**：讲义强调，决定车道的是 SLA 与用户预期，而不是"是否在生产环境"。
