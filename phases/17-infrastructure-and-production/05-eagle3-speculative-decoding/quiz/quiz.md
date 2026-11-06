# 测验 · 生产环境中的 EAGLE-3 Speculative Decoding（EAGLE-3 Speculative Decoding in Production）

> **阶段 17 · 基础设施与生产 · 第 05 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 说明：中文讲义为机器翻译（concurrency 被译成"货币"、alpha 被译成"阿尔法"、P99 ITL 被译成"P99 国际交易日志"），请以英文版为准。本节的加速比公式、代码的模拟与代码的结论文字三者互相不一致（见 Q9、Q10），这是本测验的重点。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 为什么投机解码有效 | decode 是 memory-bound：每步要读一遍全部权重，算力几乎闲置；一次目标前向验证 K 个候选 token，几乎不增加读权重的成本 |
| 2 | 基本流程 | 便宜的 draft 提出 K 个 token → 目标模型一次前向验证 → 接受的 token 等于"免费"获得 |
| 3 | 接受率 alpha | 草稿 token 被目标接受的比例；讲义：这是"唯一重要的指标"，vLLM V1 中用 `accepted_tokens_per_request / 草稿长度` 求得 |
| 4 | 讲义加速比公式 | `S = (1 + K·alpha) / (1 + epsilon)`；K=5、alpha=0.7、epsilon=0.1 时为 4.1x；实际多在 2–3x |
| 5 | 盈亏平衡 alpha | 令 S=1 得 `alpha_be = epsilon / K`（K=5、epsilon=0.15 时 0.03）；但高并发下 verify 开销上升、批处理已摊薄读权重，实际约 0.45–0.55；讲义建议门槛 alpha ≥ 0.55 |
| 6 | 草稿方案演进 | 经典小模型草稿 alpha 0.3–0.5；EAGLE-1 用目标最后一层 hidden state 训练草稿头 ~0.5–0.6；EAGLE-2 加自适应长度与树形草稿 ~0.6–0.7；EAGLE-3 用**多层** hidden state，通用对话 0.6–0.8 |
| 7 | 领域相关性 | 通用数据训练的草稿头在代码、医疗、法律流量上 alpha 降到 0.4–0.6；训练领域草稿头是"轻量快速"的任务 |
| 8 | 默认关闭 | vLLM 2026 中投机解码需显式设置 `speculative_config`（如 `"method": "eagle3"`），不设就没有加速 |
| 9 | P99 尾部陷阱 | 均值 ITL 下降而 P99 可能变差：被拒绝的轮次产出很少 token；要看 P99 ITL 而不是 P50 |
| 10 | 不该用的场景 | 离线 batch-1 生成、很短的输出（< 50 token）、没有领域草稿头的专业领域；以及未核对版本兼容性矩阵就叠加特性 |

### 核心技能（能动手做到）

- [ ] 用讲义公式和"逐位几何接受"模型分别计算期望每轮 token 数与加速比，并说出二者对 alpha 定义的不同
- [ ] 计算给定 K、epsilon 下达到 2x / 3x 加速所需的 alpha，以及盈亏平衡 alpha
- [ ] 按流量占比计算混合 alpha，并判断是否通过 0.55 门槛
- [ ] 读懂本节模拟器，解释为什么每个配置都被标成 `TAIL`，以及模拟出的盈亏平衡点为何随并发**下降**
- [ ] 写出 EAGLE-3 的分阶段上线计划：基线 → 开启 → 测 alpha → 门槛 → 看 P99 ITL
- [ ] 诊断"均值 ITL 下降、P99 ITL 上升"并给出缓解办法

---

## 二、基础自测（选择题）

**Q1.** 投机解码能带来加速，讲义给出的根本原因是：

- A. 草稿模型比目标模型更准确
- B. 目标模型在 decode 时是 compute-bound，草稿模型能分担矩阵乘法
- C. 投机解码减少了 KV cache 的显存占用
- D. decode 是 memory-bound，每步主要在等 HBM 读权重、算力几乎闲置；一次前向验证 K 个 token 几乎不增加读权重的成本

**Q2.** 按讲义公式 `S = (1 + K·alpha) / (1 + epsilon)`，K=5、alpha=0.7、epsilon=0.1 时的期望加速比是：

- A. 约 4.1x
- B. 约 3.2x
- C. 约 2.7x
- D. 约 1.5x

**Q3.** EAGLE-3 相对 EAGLE-2 的关键变化是：

- A. 改用同家族的小模型（如 Llama 3.2 1B）作为草稿
- B. 去掉了树形草稿
- C. 草稿头基于目标模型**多层**的 hidden state 训练，而不只是最后一层
- D. 不再需要目标模型做验证

**Q4.**（讲义练习 2）生产流量 70% 是通用对话（alpha 0.7）、30% 是代码（alpha 0.4），按流量线性加权的混合 alpha 及其与讲义门槛的关系是：

- A. 0.55，刚好等于门槛
- B. 0.61，高于 0.55 门槛，但只高 0.06，未达到 skill 要求的"超过盈亏平衡至少 0.1"
- C. 0.70，远高于门槛
- D. 0.49，低于门槛

**Q5.** 本节代码 `breakeven_alpha(k=5, verify_overhead=0.15, concurrency=256)` 的返回值是：

- A. 0.060
- B. 0.034
- C. 0.40
- D. 0.55

**Q6.** 开启 EAGLE-3 后均值 ITL 下降，讲义要求你最该盯住的指标是：

- A. GPU duty cycle
- B. 模型加载时间
- C. P50 TTFT
- D. P99 ITL

**Q7.** 运行本节代码，15 个配置（alpha 0.30–0.80 × 并发 32/128/256）**全部**被标记为 `TAIL`（spec P99 高于 plain P99）。最直接的原因是：

- A. 代码的 `plain_tail` 用了更大的随机种子
- B. 每轮"一个都没接受"的概率是 `1 − alpha`（至少 20%），这些轮次要付 `verify + reroll` 两次目标前向却只产出 1 个 token，单 token 延迟约 17–18ms，主导了 P99
- C. alpha 太高导致草稿过长
- D. 并发越高，plain 的 P99 越低

**Q8.** 下列哪个场景讲义**建议使用**投机解码？

- A. 离线批量生成，延迟不重要
- B. 平均输出不足 50 token 的分类式短回答
- C. 通用对话流量，已在生产流量上测得 alpha ≥ 0.55，且 P99 ITL 没有变差
- D. 医疗领域流量，只有通用数据训练的草稿头，alpha 约 0.4

---

## 三、动手 / 代码题

**Q9.** 代码里有两种计算"每轮产出多少 token"的方式：

```python
def expected_speedup(p: SpecPoint) -> float:
    effective_overhead = p.verify_overhead * (1 + p.concurrency / 256)
    tokens_per_target = 1 + p.k * p.alpha
    cost_per_target = 1 + effective_overhead
    return tokens_per_target / cost_per_target

# simulate_tail 中
        accepted = 0
        for _ in range(p.k):
            if rng.random() < p.alpha:
                accepted += 1
            else:
                break
```

1. 在 `simulate_tail` 中，alpha 的含义是什么？期望接受数是多少？
2. 当 K=5、alpha=0.7 时，两种方式的"每轮期望 token 数"分别是多少？
3. 讲义把 alpha 定义为"草稿 token 被接受的比例"（`accepted_tokens_per_request / 草稿长度`）。在这个定义下 `1 + K·alpha` 成立吗？如果 `simulate_tail` 的逐位接受率是 0.7，对应的"被接受比例"是多少？

**Q10.** 代码末尾的 KEY FINDING 写道："32 并发时 alpha 约 0.1 以上就有收益，256 并发时门槛约 0.4"。但表格里打印的 `be_alpha` 是 0.034 / 0.045 / 0.060，而且公式给出的 speedup 在 alpha=0.30 时也有 1.92–2.14x。

1. 解释 `be_alpha` 和 KEY FINDING 为什么对不上。
2. 用模拟出的均值延迟计算"实际加速比"`plain_mean / spec_mean`（已实际运行，见答案表），模拟出的盈亏平衡点随并发如何变化？与讲义"高并发下门槛上升"一致吗？为什么？

**Q11.** 阅读 `simulate_tail` 中拒绝时的代价：

```python
    verify_ms = base_target_ms * (1 + effective_overhead)
    reroll_ms = base_target_ms  # second pass when draft rejects early
    ...
        batch_lat = verify_ms + (reroll_ms if accepted < p.k else 0)
        batch_tokens = max(1, accepted + 1)
        per_tok = batch_lat / batch_tokens
```

1. 讲义说"被拒绝的 token 会强制进行第二次目标前向"。在标准的投机采样（speculative sampling）算法中，第一个被拒绝的位置如何处理？需要额外一次目标前向吗？
2. `per_tok = batch_lat / batch_tokens` 把一轮的延迟平均分给这一轮的每个 token。真实的流式输出中，这一轮的 token 是怎样到达客户端的？这对 ITL 统计有什么影响？
3. `max(1, accepted + 1)` 中的 `max` 有必要吗？

**Q12.**（讲义练习 1）K=5 时要达到 2x 和 3x 加速，各需要多大的 alpha？分别用讲义的线性公式和"逐位几何接受"公式 `E[tokens] = (1 − alpha^(K+1)) / (1 − alpha)` 计算，并讨论 epsilon 从 0.15 增大到 0.3 时的敏感性。

---

## 四、面试高频题

**Q13.**（基础必考）讲清投机解码的原理：为什么它不改变输出分布、为什么能加速、加速比由哪些因素决定？

**Q14.**（原理深挖）经典草稿模型、EAGLE、EAGLE-2、EAGLE-3 的区别是什么？为什么基于目标模型 hidden state 训练的草稿头 alpha 更高？

**Q15.**（工程实践）请写出把 EAGLE-3 上线到一个 Llama 3.3 70B 服务的完整流程，包括配置、测量、门槛和回滚条件。

**Q16.**（追问型）开启 EAGLE-3 后均值 ITL 下降 25%，但 P99 ITL 上升 15%（讲义练习 4）。请诊断原因并提出缓解方案。

**Q17.**（场景设计）为什么高并发下投机解码的收益会变小甚至为负？如果你的服务白天高并发、夜间低并发，你会如何设计？

---

## 五、参考答案与解析

### Q1 — 答案：D

讲义："Decode is memory-bound… The GPU compute is almost idle during decode — the bottleneck is HBM bandwidth, not matmul throughput. Speculative decoding exploits the gap." B 正好说反；A 错，草稿模型更小、更不准，只是"足够接近"；C 错，投机解码不减少 KV cache（草稿还会额外占一点显存）。附注：讲义说"each decoded token reads ~140 GB/s of weights"，单位有误——70B 参数在 BF16 下约 140GB、FP8 下约 70GB，应是"每步读约 70–140GB 权重"，而不是 GB/s。

### Q2 — 答案：A

`(1 + 5 × 0.7) / (1 + 0.1) = 4.5 / 1.1 ≈ 4.09`。讲义紧接着说明"现实中多在 2–3x，因为生产流量的 alpha 很少这么高，且 epsilon 随 batch 增大"。C（2.7x）是用"逐位几何接受"模型算出的值：`(1 − 0.7⁶)/(1 − 0.7) ≈ 2.94` 个 token，`2.94 / 1.1 ≈ 2.67`（见 Q9），恰好落在讲义说的 2–3x 区间。

### Q3 — 答案：C

讲义："EAGLE-3 (2025-2026): draft head trained on multiple target layers (not just last), better alignment." A 是经典草稿模型方案；B 错，树形草稿是 EAGLE-2 的特性（讲义），EAGLE-3 并没有去掉；D 错，任何投机解码都必须由目标模型验证，这是保证输出分布不变的前提。

### Q4 — 答案：B

`0.7 × 0.7 + 0.3 × 0.4 = 0.61`。按讲义 0.55 门槛算"通过"，但 skill 要求"实测 alpha 超过盈亏平衡至少 0.1"，0.61 − 0.55 = 0.06 不满足。更好的做法是**按流量类型分别决定**：通用对话开启、代码流量关闭或训练代码领域草稿头。另外线性平均 alpha 只是近似：每轮产出 token 数对 alpha 是非线性的（见 Q9），按几何模型算，分别计算再加权得每轮 2.56 个 token，而直接用 0.61 算得 2.43 个。

### Q5 — 答案：A

`effective_overhead = 0.15 × (1 + 256/256) = 0.30`，`0.30 / 5 = 0.060`。B 是并发 32 时的值（`0.15 × 1.125 / 5 ≈ 0.034`）。C 是代码 KEY FINDING 文字里说的"~0.4"，与函数实际返回值不符（见 Q10）；D 是讲义的生产门槛，代码的公式并没有建模出它。

### Q6 — 答案：D

讲义："Mean ITL drops with spec decode. P99 can get worse if you do not tune… Watch P99 ITL, not P50." A 是阶段 17 · 03 讨论过的错误信号；B、C 与投机解码无关（投机解码作用于 decode 阶段，主要影响 ITL 而非 TTFT）。

### Q7 — 答案：B

`simulate_tail` 每轮第一个草稿 token 就被拒的概率是 `1 − alpha`，alpha=0.8 时仍有 20%。这些轮次延迟 = `verify_ms + reroll_ms`（并发 32 时 `9.35 + 8 = 17.35ms`，256 时 `10.4 + 8 = 18.4ms`），只产出 1 个 token。超过 1% 的 token 都来自这种轮次，P99 自然落在 17–22ms，而 plain 的 P99 只有 10–14ms。所以 `TAIL` 标签与 alpha 几乎无关，是模型结构决定的。D 说反了：plain P99 随并发上升（10.08 → 11.86 → 14.23ms）。

### Q8 — 答案：C

讲义"When not to use"列出：离线 batch-1（A）、输出 < 50 token（B）、没有领域草稿头的专业领域（D）。C 满足讲义的上线流程：在生产流量上测得 alpha ≥ 0.55，并确认 P99 ITL 没有变差。

### Q9 — 参考答案

1. `simulate_tail` 里 alpha 是**逐位置的条件接受概率**：每个草稿位置独立以 alpha 接受，第一次拒绝即停止。期望接受数为 `alpha + alpha² + … + alpha^K`。
2. K=5、alpha=0.7：
   - 讲义/`expected_speedup`：`1 + 5 × 0.7 = 4.5` 个 token；
   - 几何模型：`1 + 0.7 + 0.49 + 0.343 + 0.240 + 0.168 = (1 − 0.7⁶)/(1 − 0.7) ≈ 2.94` 个 token。
   两者相差 1.5 倍以上，`expected_speedup` 系统性高估。
3. 若 alpha 定义为"实测被接受的草稿比例"（即 `E[接受数] / K`），那么 `1 + K·alpha` 是成立的——它只是把定义代回去。问题在于代码**同一个文件里用了两种定义**：逐位接受率 0.7 对应的被接受比例只有 `(2.94 − 1) / 5 ≈ 0.388`。各 alpha 的换算（已实际计算）：

   | 逐位 alpha | 1 + K·alpha | 几何模型每轮 token | 被接受比例 |
   |-----------|-------------|------------------|----------|
   | 0.30 | 2.50 | 1.43 | 0.086 |
   | 0.55 | 3.75 | 2.16 | 0.232 |
   | 0.70 | 4.50 | 2.94 | 0.388 |
   | 0.80 | 5.00 | 3.69 | 0.538 |

   工程含义：读 vLLM 指标或论文里的"acceptance rate"时，务必弄清它是"逐位条件概率"还是"整体被接受比例"，二者不能混用，门槛 0.55 也必须对应同一个定义。

### Q10 — 参考答案

1. `breakeven_alpha` 实现的是 `epsilon_eff / K`，即讲义说的"原始 decode 数学"（0.03 级别）；它没有建模讲义说的"高并发下批处理已摊薄读权重"，所以永远到不了 0.4。KEY FINDING 的"~0.1 / ~0.4"是作者想表达的讲义结论，并非代码算出来的数，与表格矛盾。
2. 用模拟均值计算的实际加速比（已实际运行）：

   | alpha | 并发 32 | 并发 128 | 并发 256 |
   |-------|--------|---------|---------|
   | 0.30 | 0.69 | 0.79 | 0.92 |
   | 0.45 | 0.89 | 1.02 | 1.18 |
   | 0.55 | 1.06 | 1.21 | 1.41 |
   | 0.70 | 1.50 | 1.72 | 1.99 |
   | 0.80 | 2.16 | 2.47 | 2.85 |

   - 模拟在并发 32 时的盈亏平衡点约在 0.5–0.55 之间，碰巧接近讲义的 0.55；
   - 但盈亏平衡点随并发**下降**（128 时约 0.45，256 时 0.30–0.45 之间），与讲义"高并发门槛上升"相反。
   - 原因：`plain_tail` 的单步延迟 `8 × (1 + 并发/512)` 随并发上升，而 `simulate_tail` 的 `base_target_ms = 8.0` 固定不变，只有 verify 开销随并发增加。并发越高，plain 被惩罚得越多，spec 反而显得越划算。两个函数的成本模型不一致。
   - 同时，公式给出的加速比（如 alpha=0.7、并发 32 时 3.85x）与模拟（1.50x）相差 2.5 倍，原因是 Q9 的 alpha 定义差异加上 Q11 的 reroll 惩罚。

### Q11 — 参考答案

1. 标准投机采样（Leviathan 等人、Chen 等人提出的算法）中，目标模型一次前向会同时算出 K+1 个位置的概率分布。在第一个被拒绝的位置，直接从修正分布 `max(0, p − q)` 归一化后采样一个 token；全部接受时则从第 K+1 个位置的分布再采一个"奖励 token"。因此**每次目标前向至少产出 1 个 token，不需要额外的第二次前向**。讲义"rejected tokens force a second target forward"与标准算法不符；代码的 `reroll_ms` 正是按讲义的说法建模，导致被拒轮次被多罚一次 8ms。真实系统中被拒的代价是"浪费了草稿计算和验证中多算的 K 个位置"，在高并发时体现为 verify 开销上升。
2. 真实流式输出中，一轮被接受的 `accepted + 1` 个 token 是**同时**到达的：第一个 token 的间隔是整轮延迟，其余 token 间隔接近 0。按 token 平均分配会把"一次大间隔 + 几次零间隔"抹平成"几次中等间隔"，低估了 P99 ITL 的波动。这也是讲义强调看 P99 的原因：投机解码让 token 到达变得"成簇"。
3. 没必要：`accepted ≥ 0`，`accepted + 1 ≥ 1` 恒成立，`max` 是冗余的防御代码。

### Q12 — 参考答案

令 `E[tokens] = S × (1 + epsilon)`，解 alpha（已用二分法实际计算）：

| epsilon | 目标 S | 线性公式 alpha | 几何模型 alpha |
|---------|-------|---------------|--------------|
| 0.15 | 2x | 0.26 | 0.582 |
| 0.15 | 3x | 0.49 | 0.771 |
| 0.169（代码中并发 32） | 2x | 0.268 | 0.590 |
| 0.169 | 3x | 0.501 | 0.778 |
| 0.30 | 2x | 0.32 | 0.642 |
| 0.30 | 3x | 0.58 | 0.824 |

- 线性公式：`alpha = (S(1 + epsilon) − 1) / K`，epsilon 每增加 0.15，所需 alpha 增加 `0.15 × S / 5`（2x 时 +0.06，3x 时 +0.09）。
- 几何模型下所需 alpha 高得多：3x 需要逐位接受率约 0.77–0.82，这解释了为什么讲义说"实际多在 2–3x"——要到 3x 必须有非常高的接受率。
- 结论：选 K 和判断是否上线时，要明确用的是哪种 alpha 定义，并用实测的 epsilon（随并发变化）重新计算。

### Q13 — 参考回答要点

- **流程**：草稿模型/草稿头自回归地提出 K 个 token；目标模型对"前缀 + K 个草稿"做一次前向，得到每个位置的分布；按投机采样规则逐个接受，第一个被拒的位置从修正分布采样；每轮至少产出 1 个 token，最多 K+1 个。
- **不改变输出分布**：接受概率 `min(1, p/q)` 加上被拒时从 `(p − q)+` 采样，可以证明最终 token 的分布与直接从目标模型采样完全相同（贪心解码时则等价于"草稿与目标 argmax 一致才接受"）。
- **为什么能加速**：decode memory-bound，验证 K+1 个位置与生成 1 个位置读的权重几乎一样多；只要草稿足够便宜、接受率足够高，每次目标前向产出多个 token。
- **加速比因素**：alpha（最关键）、K、草稿成本、verify 开销 epsilon（随 batch 增大）、输出长度（太短时固定开销占比高）。
- 加分点：说明讲义的 `1 + K·alpha` 与几何模型的区别，以及"每轮至少 1 个 token"意味着无需第二次前向。

### Q14 — 参考回答要点

- **经典草稿模型**：同家族小模型（如 Llama 3.2 1B 为 70B 起草），独立加载、每轮运行 K 次前向。基础设施简单，但小模型分布与目标偏离，讲义 alpha 0.3–0.5。
- **EAGLE（讲义标注 2024）**：不再用独立小模型，而是在目标模型的 hidden state 上训练一个轻量草稿头，直接利用目标模型已经算好的特征，alpha 约 0.5–0.6，参数开销小。
- **EAGLE-2（讲义标注 2025，但其引用的 arXiv:2406.16858 表明发表于 2024 年 6 月）**：自适应草稿长度和树形草稿，一次目标前向验证多个分支，alpha 约 0.6–0.7。
- **EAGLE-3**：用多层 hidden state（不只最后一层）训练，对齐更好，通用对话 alpha 0.6–0.8。
- **为什么 hidden state 草稿更好**：目标模型的内部表示已经编码了"它接下来想说什么"，草稿头只需学一个从特征到下一 token 的轻映射；而独立小模型要从 token 重新理解上下文，能力差距导致分布偏离。
- 加分点：草稿头是在通用数据（如 ShareGPT）上训练的，换到代码/医疗等领域 alpha 会掉到 0.4–0.6，需要训练领域草稿头。

### Q15 — 参考回答要点

1. **基线**：不开投机解码，在目标并发点用真实 prompt 分布（LLMPerf、GenAI-Perf 或生产影子流量）测 TTFT、ITL 的均值与 P99、吞吐。
2. **选草稿头**：通用对话用 ShareGPT 训练的 EAGLE-3；专业流量先评估或训练领域草稿头。
3. **配置**：vLLM 中显式设置 `speculative_config`，如 `{"method": "eagle3", "model": "<草稿头路径>", "num_speculative_tokens": 5}`；核对所用 vLLM 版本的兼容性矩阵（讲义：v0.18.0 标注投机解码与 chunked prefill、prefix caching 兼容；pipeline parallelism 至 v0.15.0 不兼容）。
4. **测 alpha**：影子流量跑 24 小时，记录 spec decode 指标，用接受 token 数 / 草稿长度得到 alpha（skill 的流程）。
5. **门槛**：生产并发下 alpha ≥ 0.55，且超过实测盈亏平衡至少 0.1；任一小时窗口 alpha < 0.45 触发 kill switch。
6. **尾部**：对比开/关时的 P99 ITL 差值，若为正则降低 K 或对该流量关闭。
7. **回滚**：保留不开投机解码的配置，按流量类型或租户开关。
- 常见误区：只看 benchmark 上的 2–3x，不在自己的流量上测 alpha（skill 的 hard reject）。

### Q16 — 参考回答要点

- **诊断**：均值下降说明总体接受率不错；P99 上升说明存在"低接受率的轮次/请求"——某类流量（如代码、特定语言）alpha 很低，或高并发时 verify 开销放大；还有 token 成簇到达本身造成的 ITL 方差增大。讲义的解释是被拒草稿在满 batch 下导致串行的两次前向。
- **定位**：按流量类型、请求长度、并发时段拆分 alpha 和 P99 ITL；看是否集中在某类 prompt 或高峰期。
- **缓解**：
  - 降低 K（被拒时浪费更少，单轮延迟更短）；
  - 对低 alpha 流量关闭投机解码或训练领域草稿头；
  - 使用动态草稿长度 / 树形草稿（EAGLE-2 的思路）；
  - 高并发时自动降低 K 或关闭（按负载自适应）；
  - 若流式输出体验要求平滑，可在服务端对成簇 token 做节流平滑。
- 加分点：给出"开/关 P99 ITL 差值"作为持续监控指标（skill 的 tail watch）。

### Q17 — 参考回答要点

- **高并发收益变小**：decode batch 很大时，一次前向已经在为很多序列摊薄读权重，GPU 逐渐从 memory-bound 走向 compute-bound；此时验证 K 个额外位置的计算不再"免费"，epsilon 随 batch 上升，讲义说实际盈亏平衡 alpha 升到 0.45–0.55。
- **被拒的浪费**：高并发下每个被拒的草稿位置都占用了本可以服务其他序列的算力。
- **设计**：
  - 按负载自适应：低并发时开启较大的 K，高并发时减小 K 或关闭（监控实时 batch 大小与 alpha）；
  - 按流量类型路由：高 alpha 流量走开启投机解码的副本池，低 alpha 流量走普通副本；
  - 持续在生产流量上测量 alpha 和 P99 ITL，作为调整依据。
- 常见误区：照搬本节代码的模拟结论——它的模拟恰好显示"并发越高越划算"，原因是成本模型不一致（Q10），不能用来支持决策。

---

## 六、关联知识点

### 前置知识
- [阶段 17 · 04 服务引擎内部机制：PagedAttention、Continuous Batching 与 Chunked Prefill](../../04-vllm-serving-internals/docs/zh.md)：decode 为何 memory-bound、调度器如何组 batch。
- [阶段 10 · 18 Multi-Token 预测（MTP）](../../../10-llms-from-scratch/18-multi-token-prediction/docs/zh.md)：讲义列出的前置节，MTP 头也可作为草稿。
- [阶段 07 · 16 Speculative Decoding — 草稿、验证、重复](../../../07-transformers-deep-dive/16-speculative-decoding/docs/zh.md)：投机采样算法本身。
- [阶段 10 · 15 Speculative Decoding 与 EAGLE-3](../../../10-llms-from-scratch/15-speculative-decoding-eagle3/docs/zh.md)、[阶段 10 · 25 Speculative Decoding 与 EAGLE](../../../10-llms-from-scratch/25-speculative-decoding/docs/zh.md)：EAGLE 系列的模型侧细节。

### 本节被哪些后续内容用到
- [阶段 17 · 06 前缀缓存服务：RadixAttention 与 KV 复用](../../06-sglang-radixattention/docs/zh.md)：讲义提到 SGLang 把 EAGLE-3 作为前缀密集负载的推荐草稿路径。
- [阶段 17 · 07 针对硬件的 Inference 编译：Blackwell 上的 FP8 与 NVFP4](../../07-tensorrt-llm-blackwell/docs/zh.md)：另一条降低 decode 成本的路线。
- [阶段 17 · 08 Inference 指标：TTFT、TPOT、ITL、Goodput、P99](../../08-inference-metrics-goodput/docs/zh.md)：P99 ITL 等指标的严格定义。
- [阶段 17 · 20 面向 LLMs 的 Shadow Traffic、金丝雀 Rollout 与渐进式部署](../../20-shadow-canary-progressive/docs/zh.md)：本节"影子流量测 alpha"的部署方法。
- [阶段 19 · 14 综合项目 14：推测解码 Inference 服务端](../../../19-capstone-projects/14-speculative-decoding-server/docs/zh.md)：完整实现一个投机解码服务。

### 延伸关键词
`speculative sampling` · `acceptance rate alpha` · `draft length K` · `EAGLE / EAGLE-2 / EAGLE-3` · `tree drafts` · `Medusa` · `MTP head` · `N-gram speculation` · `speculative_config` · `verify overhead` · `bonus token` · `P99 ITL` · `memory-bound decode`
