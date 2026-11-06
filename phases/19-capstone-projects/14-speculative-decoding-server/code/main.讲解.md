# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 14 节 综合项目 14：推测解码 Inference 服务端 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`random`、`dataclasses`），不需要 GPU、vLLM 或任何模型权重

---

## 1. 这份代码在考察什么

讲义的真实目标是：用 vLLM / SGLang + EAGLE-3 在 H100 上服务 Llama 3.3 70B 等模型，做到 2.5x 以上吞吐并给出完整的尾延迟报告。这份 `main.py` 只是其中**调度器**的骨架，docstring 写明：

> "The hard architectural primitive is the draft/verify scheduler: a draft model proposes k candidate tokens; the target model verifies them in one batched pass; any accepted prefix is committed and the rejected suffix is resampled from the target."

它考察：

1. **draft → verify → 接受前缀 → 补一个 token** 的循环结构；
2. **接受率**与 **每次 target 调用产出的 token 数**这两个核心指标；
3. **扫参**：draft 对齐度（`alignment`）与推测长度 k 如何影响"加速比"。

它没有实现、也无法体现：真实模型、无损的接受规则、draft 与验证的计算成本、批处理、延迟、量化、Kubernetes。

> 一句话：**用合成概率分布把"推测—验证"的计数逻辑跑通**；但它的接受规则不保分布、draft 能直接读 target 分布、加速比只数调用次数——这些简化让数字比真实系统乐观得多，读结果时必须打折。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `VOCAB` | 常量 | 10 个字母组成的小词表 | 词表 |
| `softmax_from(seed)` | 函数 | 用种子生成一个 10 维概率分布（随机权重归一化，并非真正 softmax） | 模型输出分布（合成） |
| `sample(dist, rng)` | 函数 | 逆 CDF 采样 | 采样 |
| `TargetModel` | dataclass | `distribution(ctx_seed)`、`verify(...)`，统计调用次数 | 昂贵的 target 模型 |
| `DraftModel` | dataclass | `propose(...)`：以概率 `alignment` 取 target 的 argmax，否则按 target 分布采样 | draft / speculator |
| `Metrics` | dataclass | 生成数、target / draft 调用数、接受总数；两个派生指标 | 评估指标 |
| `speculative_decode` | 函数 | 推测解码主循环 | 调度器 |
| `baseline_decode` | 函数 | 每个 token 调一次 target | 无推测对照组 |
| `main` | 函数 | 生成 500 token；3 种对齐度 × 3 种 k 的扫参 | 基准报告（极简） |

数据流：`main` → `baseline_decode`（500 次调用）→ 对每个 `(alignment, k)`：`speculative_decode` 循环 [`DraftModel.propose` → `TargetModel.verify` → 更新 `Metrics`] → 打印 target 调用数、接受率、tok/call、加速比。

---

## 3. 逐段精讲

### 3.1 合成分布与采样

```python
VOCAB = list("abcdefghij")


def softmax_from(seed: int) -> list[float]:
    rnd = random.Random(seed)
    weights = [rnd.random() for _ in VOCAB]
    total = sum(weights)
    return [w / total for w in weights]
```

- 每个种子对应一个固定的概率分布：10 个 `[0, 1)` 均匀随机数再归一化。
- 名字叫 softmax，实际只是**线性归一化**（没有 `exp`）。由于权重都在 0～1 之间，分布相当平坦：最大概率中位数约 0.18（前 700 个位置实测范围 0.12～0.32）。这一点会在 3.3 中放大接受率。
- 使用独立的 `random.Random(seed)` 实例，不影响全局随机状态，也保证同一种子总得到同一分布——整个程序因此是确定性的（连续运行输出的 md5 相同）。

```python
def sample(dist: list[float], rng: random.Random) -> int:
    r = rng.random()
    acc = 0.0
    for i, p in enumerate(dist):
        acc += p
        if r <= acc:
            return i
    return len(dist) - 1
```

- **逆 CDF 采样**：累加概率直到超过随机数 r。
- 末尾的 `return len(dist) - 1` 是浮点误差保护：累加和可能是 0.9999999，r 恰好更大时仍返回最后一个下标。

### 3.2 `TargetModel`：分布与验证

```python
@dataclass
class TargetModel:
    calls: int = 0
    tokens_verified: int = 0

    def distribution(self, ctx_seed: int) -> list[float]:
        return softmax_from(ctx_seed * 7 + 13)
```

- 第 `ctx_seed` 个位置的分布由 `ctx_seed * 7 + 13` 作种子决定——**只与位置有关，与前文生成了什么 token 无关**。真实语言模型的分布取决于全部上下文；这里接受或拒绝某个 token 不会改变后续分布。
- `tokens_verified` 被累加但从未使用（本可用来估算验证成本）。

```python
    def verify(self, draft_tokens, ctx_seed, rng) -> tuple[list[int], int]:
        self.calls += 1
        self.tokens_verified += len(draft_tokens) + 1
        accepted: list[int] = []
        for pos, tok in enumerate(draft_tokens):
            dist = self.distribution(ctx_seed + pos)
            # simple accept criterion: target prob on this token >= 0.5 * max prob
            if dist[tok] >= 0.5 * max(dist):
                accepted.append(tok)
            else:
                break
        ctx = ctx_seed + len(accepted)
        dist = self.distribution(ctx)
        next_tok = sample(dist, rng)
        return accepted, next_tok
```

- **一次调用验证全部 k 个位置**：`calls` 只加 1，这模拟了"target 一次前向并行算出 k+1 个位置的分布"。
- `len(draft_tokens) + 1`：验证 k 个 draft 位置，再加一个用于补充 token 的位置。
- 从左到右检查，第一次失败就 `break`——只接受**最长前缀**，因为后面的 draft token 是以被拒 token 为前提猜的。
- 无论是否全部接受，都在 `ctx_seed + len(accepted)` 处从 target 采样一个 `next_tok`：
  - 有拒绝时，它替代被拒的那个 token；
  - 全部接受时，它是"免费"的补充 token（bonus token）。
  所以每次调用至少产出 1 个 token，最多 k+1 个。
- ⚠️ **接受规则不是无损的**。标准 speculative sampling 以 `min(1, p(x)/q(x))` 接受，拒绝时从 `norm(max(0, p − q))` 重采样，可以证明输出分布等于 target。这里的规则是确定性的阈值"`p(x) ≥ 0.5·max(p)`"，拒绝后又直接从 p 采样。实测位置 1 上，`alignment=0.6` 时第一个输出 token 为 argmax 的概率是 0.658，而 target 只有 0.136，两个分布的总变差距离约 0.52——推测解码**改变了模型输出**。
- 讲义 Concept 里写"any prefix accepted replaces the greedy path"，对应的是 greedy 情形；代码却在做采样，两者混在一起。

### 3.3 `DraftModel`：一个"偷看答案"的 draft

```python
@dataclass
class DraftModel:
    calls: int = 0
    alignment: float = 0.80     # probability that draft picks what target would

    def propose(self, ctx_seed, k, rng, target) -> list[int]:
        self.calls += 1
        draft_tokens: list[int] = []
        for pos in range(k):
            dist = target.distribution(ctx_seed + pos)
            if rng.random() < self.alignment:
                draft_tokens.append(max(range(len(dist)), key=lambda i: dist[i]))
            else:
                draft_tokens.append(sample(dist, rng))
        return draft_tokens
```

- draft 直接调用 `target.distribution`：以概率 `alignment` 选 target 的 argmax，否则按 target 分布采样。等价的 draft 分布是 `q = a·onehot(argmax p) + (1 − a)·p`。
- 真实 draft 看不到 target 的分布，只能用自己的参数近似（EAGLE-3 用 target 的 hidden states 训练 head，已经是最接近的方式）。这里的 draft 是"完美知情 + 故意加噪"。
- `max(range(len(dist)), key=lambda i: dist[i])`：求 argmax 的常见写法。
- 为什么接受率这么高：合成分布很平坦，满足 `p ≥ 0.5·max(p)` 的 token 平均有 5.63 个，占概率质量约 **0.793**（对前 700 个位置实测）。即使 draft "没对齐"、随机采样，79% 的情况也能通过。每位置接受概率约为 `α = a + (1 − a) × 0.793`：a = 0.60 时 α ≈ 0.917。
- ⚠️ `DraftModel.calls` 与 `Metrics.draft_calls` 都在计数，但都没被打印，draft 成本完全没有进入加速比。

### 3.4 `Metrics`：两个指标

```python
@dataclass
class Metrics:
    generated: int = 0
    target_calls: int = 0
    draft_calls: int = 0
    accepted_sum: int = 0

    def acceptance_rate(self, k: int) -> float:
        if self.target_calls == 0:
            return 0.0
        return self.accepted_sum / (self.target_calls * k)

    def tokens_per_target_call(self) -> float:
        return self.generated / max(1, self.target_calls)
```

- **接受率** = 被接受的 draft token 总数 / 提出的 draft token 总数。口径要点：第一次拒绝之后的 draft token 都计为"未接受"，所以即使每位置接受概率不变，k 越大这个比例越低（运行结果中 a = 0.60 时 k = 2/4/6 依次为 0.88/0.82/0.69）。
- **tok/call** = 生成 token 数 / target 调用次数，包含补充 token，这才是吞吐的直接驱动量。
- 两个除零保护：`if self.target_calls == 0` 与 `max(1, ...)`。
- 理论对照：每位置独立接受率为 α 时，`E[tok/call] = (1 − α^(k+1)) / (1 − α)`，`acceptance = (α − α^(k+1)) / ((1 − α)k)`。代入 α ≈ 0.917，得到 k = 2/4/6 时 tok/call 为 2.76/4.24/5.48，与实测 2.76/4.27/5.05 基本吻合（k = 6 时偏差较大，因为各位置 α 并不相同，且最后一步会被 500 的上限截断）。

### 3.5 推测解码主循环与 baseline

```python
def speculative_decode(n_tokens, k, rng, target, draft) -> Metrics:
    m = Metrics()
    ctx_seed = 1
    while m.generated < n_tokens:
        draft_tokens = draft.propose(ctx_seed, k, rng, target)
        m.draft_calls += 1
        accepted, next_tok = target.verify(draft_tokens, ctx_seed, rng)
        m.target_calls += 1
        m.accepted_sum += len(accepted)
        for tok in accepted:
            m.generated += 1
            ctx_seed += 1
            if m.generated >= n_tokens:
                break
        if m.generated < n_tokens:
            m.generated += 1     # resampled next_tok
            ctx_seed += 1
    return m
```

- `ctx_seed` 就是"当前位置"：每提交一个 token 前进 1。下一轮 draft 从新的位置开始猜。
- 达到 `n_tokens` 时立即截断（包括丢弃多余的接受 token 和补充 token）。注意 `accepted_sum` 在截断前已加上全部接受数，最后一步可能略微高估接受率。
- ⚠️ `tok`、`next_tok` 只用于计数，**生成的序列没有保存**——无法检查输出质量或分布，只能看计数。
- `rng` 被 draft 和 target 共享：draft 的随机抽取会影响 target 的重采样，二者的随机流交织在一起；但由于种子固定，整体仍可复现。

```python
def baseline_decode(n_tokens, rng, target) -> Metrics:
    m = Metrics()
    ctx_seed = 1
    while m.generated < n_tokens:
        target.calls += 1
        m.target_calls += 1
        dist = target.distribution(ctx_seed)
        _ = sample(dist, rng)
        m.generated += 1
        ctx_seed += 1
    return m
```

- 每个 token 一次 target 调用，500 个 token 恰好 500 次——这是"加速比"的分母。
- `_ = sample(...)`：采样结果不用，只是为了让随机数消耗与真实流程相似。

### 3.6 `main`：扫参与"加速比"

```python
    for alignment in (0.60, 0.75, 0.90):
        for k in (2, 4, 6):
            target = TargetModel()
            draft = DraftModel(alignment=alignment)
            rng = random.Random(7)
            m = speculative_decode(n_tokens, k, rng, target, draft)
            speedup = base.target_calls / max(1, m.target_calls)
```

- 每个配置都重新创建模型并把 `rng` 重置为种子 7，保证各配置之间可比。
- ⚠️ `speedup` 只是 target 调用次数之比。它隐含：draft 免费、验证 k+1 个位置与单步 decode 一样贵、没有批处理与排队。讲义要求的是**墙钟吞吐 + batch 1/8/32 的 p50/p99**，二者不是一回事。若 draft 每个 token 的成本为 target 前向的 c 倍，理论加速应为 `(1 − α^(k+1)) / ((1 − α)(1 + k·c))`：α = 0.8、k = 4、c = 0.05 时只有约 2.80x。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 合成分布只依赖位置 | 无需模型即可确定性复现 | 上下文无关，无法模拟"错一步、后面全错"；真实 target 分布依赖前缀 |
| draft 直接读 target 分布 | 用一个参数 `alignment` 控制对齐度 | draft 被高估；真实 draft 是独立模型或 EAGLE head |
| 阈值接受规则 `p ≥ 0.5·max(p)` | 简单直观 | 不保分布、接受率虚高（a = 0.6 时位置 1 用无损规则只有约 0.48）；生产必须用 `min(1, p/q)` + 残差重采样 |
| 只数 target 调用次数 | 计数逻辑清晰 | 忽略 draft 成本、验证成本、batch 交互与延迟；生产测墙钟吞吐与 p99 |
| 单请求、无 batch | 聚焦调度逻辑 | 无法观察大 batch 下收益下降与尾延迟恶化 |
| 固定 k | 方便扫参 | 生产常按接受率、batch 大小自适应调整 k 或关闭推测 |
| 不保存生成序列 | 代码短 | 无法做质量对比（讲义要求 matched quality） |
| 共享一个 `rng` | 写法简单 | draft 与 target 的随机流耦合；严谨实验应分开 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 允许 `tuple[list[int], int]` 等注解写法 |
| `list("abcdefghij")` | `VOCAB = list("abcdefghij")` | 把字符串拆成字符列表 |
| 独立随机数生成器 | `random.Random(seed)` | 每个实例有自己的状态，种子相同则序列相同；不污染全局 `random` |
| 列表推导式 | `[rnd.random() for _ in VOCAB]`、`[w / total for w in weights]` | 生成权重、归一化 |
| `enumerate` | `for i, p in enumerate(dist)` | 同时拿下标与值 |
| 循环中提前 `return` | `sample` 中 `if r <= acc: return i` | 找到即返回 |
| `@dataclass` + 默认值 | `calls: int = 0`、`alignment: float = 0.80` | 自动生成构造函数，可用关键字覆盖：`DraftModel(alignment=0.6)` |
| 方法返回元组 | `-> tuple[list[int], int]`、`accepted, next_tok = target.verify(...)` | 一次返回多个值并解包 |
| `break` 提前退出循环 | `verify` 中第一次失败即 `break` | 只接受最长前缀 |
| `max` + `key` 求 argmax | `max(range(len(dist)), key=lambda i: dist[i])` | 返回使 `dist[i]` 最大的下标 |
| `lambda` | `key=lambda i: dist[i]` | 匿名函数 |
| 除零保护 | `max(1, self.target_calls)` | 分母至少为 1 |
| `_` 占位变量 | `_ = sample(dist, rng)` | 表示有意忽略返回值 |
| 嵌套循环扫参 | `for alignment in (...): for k in (...):` | 网格搜索 |
| f-string 格式符 | `{alignment:.2f}`、`{m.target_calls:3d}`、`{speedup:.2f}x` | 两位小数、宽度 3 的整数 |
| `if __name__ == "__main__":` | 文件末尾 | 被 import 时不运行演示 |

---

## 6. 运行结果解读

实际运行（`cd code && python3 main.py`，瞬间完成，输出确定）：

```text
=== decode 500 tokens, compare baseline vs speculative ===
baseline: 500 target calls, 1.00 tok/call
  align=0.60 k=2  target_calls=181  acceptance=0.88  tok/call=2.76  speedup=2.76x
  align=0.60 k=4  target_calls=117  acceptance=0.82  tok/call=4.27  speedup=4.27x
  align=0.60 k=6  target_calls= 99  acceptance=0.69  tok/call=5.05  speedup=5.05x
  align=0.75 k=2  target_calls=177  acceptance=0.92  tok/call=2.82  speedup=2.82x
  align=0.75 k=4  target_calls=111  acceptance=0.88  tok/call=4.50  speedup=4.50x
  align=0.75 k=6  target_calls= 82  acceptance=0.85  tok/call=6.10  speedup=6.10x
  align=0.90 k=2  target_calls=171  acceptance=0.96  tok/call=2.92  speedup=2.92x
  align=0.90 k=4  target_calls=103  acceptance=0.96  tok/call=4.85  speedup=4.85x
  align=0.90 k=6  target_calls= 78  acceptance=0.91  tok/call=6.41  speedup=6.41x
```

逐项解读：

- **baseline**：500 次调用、每次 1 个 token。
- **tok/call 与 speedup 数值相同**：因为两者都等于 `500 / target_calls`（生成数固定为 500）。
- **k 越大 tok/call 越高、接受率越低**：多猜的 token 提高了上限，但第一次拒绝后的部分全部浪费，"每个 draft token 的接受率"随之下降。
- **对齐度影响比预期小**：a 从 0.60 到 0.90，k = 2 的 tok/call 只从 2.76 升到 2.92。原因是宽松规则下 α 已经很高（0.917 → 0.979），理论值 2.76/2.85/2.94 与实测一致。
- **为什么比讲义的 2.5–3x 高得多**（最高 6.41x）：接受规则宽松、draft 偷看 target 分布、draft 与验证成本为 0、没有 batch 与延迟。讲义 Problem 段的数字是"Acceptance rates of 60–80% translate to 2–3x end-to-end throughput"。
- 换成无损规则做对照（自写脚本）：位置 1 在 a = 0.6 时接受率只有约 0.48（理论 `Σ min(p, q) = 0.481`），输出分布与 target 一致。

---

## 7. 动手改一改

1. **实现无损验证**：给 `DraftModel.propose` 同时返回每个位置的 draft 分布 q，用测验 Q9 的 `verify_lossless` 替换 `verify`；重新扫参，比较接受率与 tok/call 的变化。再用 10 万次模拟检查第一个输出 token 的分布是否等于 target。
2. **计入成本**：给 `DraftModel` 加 `cost_per_token=0.05`，给验证加 `verify_cost(k) = 1 + β·k`，把加速比改为"等效 target 前向次数"之比；观察 k 的最优值（对应讲义第 5 步"找拐点"）。
3. **讲义练习 2——ngram fallback**：维护最近 N 步的滑动接受率，低于阈值就把 draft 切换为"从已生成序列中查找重复片段"的 ngram draft；先实现保存生成序列。
4. **让分布依赖上下文**：把 `distribution` 的种子改为"位置 + 前一个 token"，例如 `hash((ctx_seed, prev_tok))` 换成稳定的组合整数；观察错一步之后 draft 的连锁失配。
5. **讲义练习 1——版本漂移**：给 target 加一个 `version` 参数，让 3.4 版本的分布与 3.3 略有不同，而 draft 仍按 3.3 的分布猜；测量接受率下降并写一个告警规则。
6. **进阶**：模拟 batch。把多个请求放进同一轮验证，假设单次前向成本为 `max(1, 总验证位置数 / C)`（C 为算力饱和点），比较 batch 1/8/32 下的吞吐与每请求延迟分布，复现"大 batch 收益变小、p99 变差"。

---

## 8. 常见坑

- **把"接受率"当成唯一指标**：k 不同时接受率不可比，还要看平均接受长度和墙钟吞吐。
- **口径不写清**：每步 token 是否含补充 token、接受率的分母是 draft token 还是步数，都要明确（见测验 Q12）。
- **拒绝后直接从 target 分布采样**：会让输出分布偏向 draft；必须从残差 `max(0, p − q)` 采样。
- **只数调用次数**：忽略 draft 与验证成本会严重高估加速。
- **只报稳态吞吐**：交付物 hard reject："Reporting steady-state throughput without tail latency."
- **draft 与 target 版本不匹配**：漂移的 draft "cost more than no speculation"。
- **聚合接受率**：必须按流量分布分别报告。
- **大 batch 下不设对照组就宣称有收益**：拒绝规则明确禁止。
- **误把 `softmax_from` 当真正 softmax**：它是线性归一化，分布比 softmax 平坦得多，这正是接受率虚高的根源之一。
