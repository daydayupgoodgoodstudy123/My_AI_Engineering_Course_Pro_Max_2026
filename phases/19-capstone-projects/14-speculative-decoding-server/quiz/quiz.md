# 测验 · 综合项目 14：推测解码 Inference 服务端（Capstone 14 — Speculative-Decoding Inference Server）

> **阶段 19 · 综合项目 · 第 14 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Draft / verify 两层结构 | draft（EAGLE-3 head、ngram 或小的对齐模型）每步提出 k 个候选 token，target 一次前向验证全部 k 个，接受最长前缀，再从 target 补一个 token |
| 2 | 为什么能加速 | decode 阶段受显存带宽限制，一次前向验证 k+1 个位置与生成 1 个位置的成本相近；每次 target 调用平均产出多个 token |
| 3 | 期望产出公式 | 每位置独立接受率为 α 时，每次 target 调用期望产出 `(1 − α^(k+1)) / (1 − α)` 个 token；计入 draft 相对成本 c 后加速约为 `(1 − α^(k+1)) / ((1 − α)(1 + k·c))` |
| 4 | 无损接受规则 | 标准 speculative sampling：以 `min(1, p(x)/q(x))` 接受，拒绝时从 `norm(max(0, p − q))` 重采样，输出分布与 target 完全一致；本节代码用的是 "≥ 0.5 × max" 的简化规则，**不是无损的** |
| 5 | 接受率随流量漂移 | 讲义：acceptance 依赖 draft-target 对齐与输入分布（ShareGPT / 代码 / 领域数据），必须按分布分别报告，禁止只报聚合值 |
| 6 | 尾延迟 | 讲义："Tail latency under rejection is worse than without speculation"——验证 pass 更大，被拒时白算；必须报告 batch 1/8/32 下有无推测的 p50/p99 |
| 7 | EAGLE-3 与 P-EAGLE | EAGLE-3 的 draft head 用 target 的 hidden states 训练（讲义 Key Terms："~75% acceptance"）；P-EAGLE 并行地验证一棵 draft 分支树 |
| 8 | 生产运维 | vLLM 0.7 / SGLang 0.4；FP8（Marlin）或 INT4（AWQ）量化；Kubernetes HPA 按 `queue_wait_ms` 而不是 CPU 扩缩容；升级前先 drain |
| 9 | 评估口径 | 吞吐、分分布接受率、batch 1/8/32 的 p50/p99、$/1M tokens；rubric 要求两个模型上"matched quality"下 2.5x 以上 |
| 10 | 本节代码的简化 | 合成分布只由位置决定、draft 直接读 target 分布、"加速比"只数 target 调用次数，不计 draft 与验证成本、不计延迟 |

### 核心技能（能动手做到）

- [ ] 用公式估算给定 α、k、c 时的期望 token/调用与理论加速比，并选择合适的 k
- [ ] 实现无损的 `verify`（`min(1, p/q)` 接受 + 残差分布重采样），并用蒙特卡洛验证输出分布等于 target
- [ ] 解释本节代码为什么在 `alignment=0.60` 时仍得到 0.88 的接受率，以及它的输出分布偏了多少
- [ ] 区分"每个 draft token 的接受率"与"每步平均接受长度"两种口径，并相互换算
- [ ] 设计一份推测解码基准报告：baseline、batch 分桶、p50/p99、分分布接受率、成本
- [ ] 设计接受率漂移监控与 ngram fallback 的切换策略

---

## 二、基础自测（选择题）

**Q1.** 设每个 draft token 被独立接受的概率 α = 0.8，每步提出 k = 4 个 token，且被拒绝或全部接受后 target 都会再补一个 token。每次 target 调用期望产出多少个 token？

- A. 3.20
- B. 4.00
- C. 3.36
- D. 5.00

**Q2.** 下面哪一个是能保证"输出分布与 target 模型逐 token 采样完全一致"的接受规则（q 为 draft 分布、p 为 target 分布）？

- A. 以 `min(1, p(x)/q(x))` 的概率接受 x；拒绝时从 `max(0, p − q)` 归一化后的分布重采样
- B. 若 `p(x) ≥ 0.5 · max(p)` 就接受，否则从 p 重采样
- C. 若 x 恰好是 `argmax(p)` 就接受，否则从 q 重采样
- D. 总是接受全部 k 个 draft token，只在句末用 target 校对一次

**Q3.** 讲义强调"Tail latency under rejection is worse than without speculation"。原因最准确的是：

- A. 推测解码会让 KV cache 占用翻倍，导致频繁换页
- B. draft 模型总是比 target 更慢
- C. 推测解码只能在 batch = 1 下运行
- D. 验证 pass 要处理 k+1 个位置，比普通 decode 一步更重；一旦早早被拒，这部分算力白费，单步延迟反而变长

**Q4.** 讲义要求 Kubernetes HPA 按哪个信号扩缩容？为什么不用 CPU？

- A. 按 GPU 温度，因为温度最能反映负载
- B. 按 `queue_wait_ms`（请求在队列中的等待时间）；GPU 饱和时 CPU 利用率不能反映推理负载，按 CPU 扩缩会抖动
- C. 按 CPU 利用率，因为 tokenizer 运行在 CPU 上
- D. 按每秒请求数，因为它与 token 数严格成正比

**Q5.** 本节代码打印的 `speedup` 是怎么算的？

- A. `baseline 的 target 调用次数 / 推测解码的 target 调用次数`，不计 draft 成本，也不计验证 pass 比单步 decode 更贵
- B. 两种方法的真实墙钟时间之比
- C. 每秒生成 token 数之比，包含 draft 的耗时
- D. 接受率乘以 k

**Q6.** 运行结果中，`alignment=0.60, k=2` 的接受率高达 0.88。最主要的原因是：

- A. 随机种子恰好有利
- B. draft 模型比 target 更大
- C. `alignment` 参数在代码中没有被使用
- D. 接受条件 `dist[tok] >= 0.5 * max(dist)` 很宽松，合成分布接近均匀，平均约 79% 的概率质量都能通过，所以"没对齐"时随便采样的 token 也大多被接受

**Q7.** 代码中 `acceptance_rate = accepted_sum / (target_calls * k)`。在每个位置的接受概率保持不变的前提下，k 从 2 增加到 6，这个指标会：

- A. 不变，因为每位置接受概率不变
- B. 增大，因为 draft 的 token 更多
- C. 下降，因为第一次拒绝之后的 draft token 都被计为"未接受"
- D. 无法确定，取决于随机种子

**Q8.** 交付物的拒绝规则中，关于接受率的报告方式要求是：

- A. 只需报告所有流量的平均接受率
- B. 必须按分布（ShareGPT、HumanEval、领域数据等）分别报告，禁止只报跨分布的聚合值
- C. 只需报告最好的那个分布的接受率
- D. 接受率不重要，只报吞吐即可

---

## 三、动手 / 代码题

**Q9.** 阅读 `TargetModel.verify` 与 `DraftModel.propose`：

```python
    def verify(self, draft_tokens, ctx_seed, rng):
        ...
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

    def propose(self, ctx_seed, k, rng, target):
        ...
            dist = target.distribution(ctx_seed + pos)
            if rng.random() < self.alignment:
                draft_tokens.append(max(range(len(dist)), key=lambda i: dist[i]))
            else:
                draft_tokens.append(sample(dist, rng))
```

1. 写出 `alignment = a` 时 draft 的分布 q（用 target 分布 p 表示）。
2. 位置 1 的 target 分布为 `[0.136, 0.103, 0.115, 0.135, 0.039, 0.095, 0.136, 0.131, 0.086, 0.025]`（argmax 为下标 0）。按代码的规则，`a = 0.6` 时第一个输出 token 的边缘分布中，token 0 的概率大约是多少？与 target 的 0.136 相比说明了什么？
3. 改写成无损的 `verify_lossless(draft_tokens, draft_dists, target_dists, rng)`。

**Q10.** 代码中的加速比只是 `base.target_calls / m.target_calls`。

1. 运行结果 `align=0.90 k=6` 给出 `speedup=6.41x`，而讲义说生产中 EAGLE-3 是 2.5–3x。至少列出三个造成差距的原因。
2. 设 α = 0.8、draft 每个 token 的成本 c = 0.05 个 target 前向，比较 k = 2、4、8 的理论加速，并说明 k 是否越大越好。
3. 若 α 降到 0.6（例如流量从 ShareGPT 换成领域数据），k = 4 和 k = 8 的理论加速各是多少？

**Q11.** 关于合成模型的"上下文"：

```python
    def distribution(self, ctx_seed: int) -> list[float]:
        return softmax_from(ctx_seed * 7 + 13)
```

1. target 在某位置的分布由什么决定？与已经生成的 token 有关吗？这对模拟的真实性有什么影响？
2. draft 是如何"预测"的？这样的 draft 在现实中对应什么？为什么说它是一个"偷看答案"的 draft？
3. `speculative_decode` 里 `next_tok` 有没有被使用？生成的 token 序列保存在哪里？

**Q12.** 讲义 "Use It" 示例：

```text
[serve]     vLLM 0.7, Llama 3.3 70B FP8, EAGLE-3 active
[decode]    bs=8, accepted_tokens_per_step=3.2, acceptance_rate=0.76
[latency]   first-token 42ms, full-response 980ms (620 tokens)
```

1. 由 TTFT 与总时长算出这个请求在 decode 阶段的单流速度（token/s）。
2. 70B 参数的 FP8 权重约 70 GB；若单卡 H100 显存带宽约 3.35 TB/s，读一遍权重至少要多少毫秒？据此估算每条流 decode 速度的上限，并判断示例数字是否可信。
3. `accepted_tokens_per_step=3.2` 与 `acceptance_rate=0.76` 在什么 k 与什么口径下能同时成立？这说明报告指标时要注意什么？

---

## 四、面试高频题

**Q13.**（基础必考）什么是 speculative decoding？它为什么能在不改变输出质量的前提下加速？

**Q14.**（原理深挖）为什么推测解码在 batch = 1 时收益最大、在大 batch 下收益变小甚至变负？它对 p99 延迟有什么影响？

**Q15.**（工程实践）让你给一个 70B 模型上线 EAGLE-3，并向管理层证明"2.5x 加速、质量不变"，你的基准测试方法是什么？

**Q16.**（场景设计）线上 target 模型从 3.3 升级到 3.4，但 draft head 还没重新训练；同时流量中代码请求占比上升。你会如何监控与应对接受率下降？

**Q17.**（追问型）draft 有哪些来源（独立小模型、ngram、Medusa/EAGLE 类 head）？EAGLE-3 和 P-EAGLE 各改进了什么？如何为一个 MoE target 选 draft？

---

## 五、参考答案与解析

### Q1 — 答案：C

`E = (1 − α^(k+1)) / (1 − α) = (1 − 0.8^5) / 0.2 = (1 − 0.32768) / 0.2 = 3.3616 ≈ 3.36`（已用 Python 计算）。推导：接受长度为 j 的概率是 `α^j(1 − α)`（j < k）或 `α^k`（全接受），每步产出"接受数 + 1 个补充 token"。A 的 3.2 是 `α·k`，忽略了"第一次拒绝后就停止"且漏了补充 token；B 是"每步接受 4 个"；D 是 `k + 1`，只有 α = 1 时才成立。

### Q2 — 答案：A

这是 Leviathan 等人 / Chen 等人提出的 speculative sampling：接受概率 `min(1, p/q)`，拒绝时从残差 `max(0, p − q)` 归一化分布采样，可以证明输出 token 的边缘分布恰好是 p。我们用 20 万次蒙特卡洛验证：对代码位置 1 的分布，无损规则输出的经验分布与 target 逐项相差不超过 0.001。B 正是本节代码的规则，会把分布推向高概率 token（见 Q9）；C、D 都不保分布。

### Q3 — 答案：D

讲义："The trade-off: P99 latency on rejection is higher because the verify pass is larger." 验证 k+1 个位置的前向在大 batch、计算受限时明显比单 token decode 贵；若第一个 draft token 就被拒，这一步只产出 1 个 token，却付出了 draft k 次 + 一次更大的验证。A 不是讲义给出的原因；B 恰好相反；C 错，讲义要求测 batch 1/8/32。

### Q4 — 答案：B

讲义："HPA autoscales on queue-wait rather than CPU." 交付物 hard reject："HPA on CPU instead of queue-wait. Will thrash under GPU saturation." GPU 推理时 CPU 往往很闲，CPU 指标无法反映排队压力；队列等待时间直接衡量"新请求要等多久"，与用户体验（TTFT）直接相关。D 错：不同请求的 token 数差异很大，请求数与负载并不成正比。

### Q5 — 答案：A

`speedup = base.target_calls / max(1, m.target_calls)`。baseline 生成 500 个 token 用 500 次调用；推测解码的 target 调用次数越少，"加速"越大。它隐含三个假设：draft 免费、一次验证 k+1 个位置和一次普通 decode 一样贵、没有排队与 batch 交互。真实系统要测墙钟吞吐和延迟。

### Q6 — 答案：D

实测：在前 700 个位置上，满足 `p ≥ 0.5·max(p)` 的 token 平均有 5.63 个（共 10 个），平均占概率质量的 **0.793**。于是每位置接受概率约为 `α = a + (1 − a) × 0.793`，a = 0.6 时 α ≈ 0.917，代入 `(α − α^(k+1)) / ((1 − α)k)` 得 k = 2 时 0.88，与运行结果完全一致。合成分布由 `random()` 权重归一化而来，接近均匀，这让宽松规则几乎什么都接受。C 错：`alignment` 在 `propose` 中使用了；A 错：运行结果是确定的（`random.Random(7)`），且理论值吻合，不是运气。

### Q7 — 答案：C

一旦第一次拒绝，循环 `break`，后面的 draft token 都算"未接受"，但分母仍按 k 计。在独立接受概率 α 下，这个比例等于 `(α − α^(k+1)) / ((1 − α)k)`，随 k 单调下降。运行结果也是如此：a = 0.60 时 k = 2/4/6 的接受率为 0.88/0.82/0.69。因此比较不同 k 的配置时，"接受率"必须配合"每步平均接受长度"一起看。

### Q8 — 答案：B

拒绝规则原文："Refuse to report acceptance rate aggregated across distributions. Per-distribution is mandatory." 原因：接受率随流量分布漂移（讲义第 6 步），聚合值会掩盖某类流量上推测解码反而变慢的问题。rubric 中"Acceptance rate on realistic traffic"占 20 分，衡量方式就是"Per-distribution acceptance-rate report"。

### Q9 — 参考答案

1. `q = a · onehot(argmax p) + (1 − a) · p`：以概率 a 输出 target 的 argmax，否则从 p 采样。
2. 代码的规则下，第一个输出 token 的边缘分布为：

   `P(x) = q(x)·[x 通过] + (Σ_{y 未通过} q(y)) · p(x)`

   位置 1 的阈值是 `0.5 × 0.136 ≈ 0.068`，只有下标 4（0.039）和 9（0.025）两个 token 不通过。计算得 token 0 的概率约 **0.658**（我们另用 20 万次模拟得到 0.656，吻合），而 target 只有 0.136；其余能通过的 token 被压到 0.037～0.058，两个不通过的低概率 token 只剩 0.001。两个分布的总变差距离（TV）约 **0.52**。
   结论：这条规则**不是无损的**，输出被强烈推向 draft 偏好的 token。真实系统中这等价于"推测解码改变了模型输出"，与"matched quality"的要求冲突。
3. 无损实现（已运行验证，输出分布与 target 吻合到小数点后 3 位，接受率 0.481 与理论 `Σ min(p, q) = 0.4814` 一致）：

```python
def verify_lossless(draft_tokens, draft_dists, target_dists, rng):
    """target_dists 比 draft_tokens 多一项：最后一项用于全部接受后的补充 token。"""
    out = []
    for tok, q, p in zip(draft_tokens, draft_dists, target_dists):
        if rng.random() < min(1.0, p[tok] / q[tok]):
            out.append(tok)                      # 接受
            continue
        resid = [max(0.0, pi - qi) for pi, qi in zip(p, q)]
        z = sum(resid)
        out.append(sample([r / z for r in resid], rng))   # 从残差分布重采样
        return out, len(out) - 1                 # (输出 token, 接受个数)
    out.append(sample(target_dists[len(draft_tokens)], rng))  # 全部接受：补充 token
    return out, len(draft_tokens)
```

   要点：draft 必须把自己的分布 q 一起交给验证器；拒绝时**不能**直接从 p 采样，而要从 `p − q` 的正部采样，否则会重复计入 draft 已经"占用"的概率质量。注意：用无损规则后，`a = 0.6` 时位置 1 的接受率只有约 0.48，远低于代码报告的 0.88——宽松规则把接受率"刷高"了。

### Q10 — 参考答案

1. 差距来源：
   - **draft 不是免费的**：EAGLE head、小模型每个 token 都要算；
   - **验证 pass 比单步 decode 贵**：k+1 个位置的前向在 batch 较大时不再"几乎免费"；
   - **接受规则过于宽松**：代码的 α 被高估（见 Q6、Q9），无损规则下的真实接受率低得多；
   - **合成分布与 draft 作弊**：draft 直接读取 target 分布（见 Q11）；
   - **没有调度、批处理、KV cache 管理、网络等开销**；只数调用次数，而讲义要求的是墙钟吞吐与 p99。
2. 用 `S = (1 − α^(k+1)) / ((1 − α)(1 + k·c))`，α = 0.8、c = 0.05（已用 Python 计算）：
   - k = 2：期望 2.44 token/调用，S ≈ **2.22**
   - k = 4：期望 3.36，S ≈ **2.80**
   - k = 8：期望 4.33，S ≈ **3.09**
   k 增大收益递减：k 从 4 到 8 多花一倍 draft 成本，期望产出只从 3.36 增加到 4.33。再考虑验证 pass 成本随 k 增长、p99 恶化，k 并非越大越好，通常需要按流量和 batch 调优。
3. α = 0.6、c = 0.05：k = 4 时 S ≈ **1.92**（期望 2.31），k = 8 时 S ≈ **1.77**（期望 2.47）。接受率低时 k 越大反而越亏——这就是讲义要求"按分布报告接受率"和"ngram fallback / batch gating"的原因。

### Q11 — 参考答案

1. 只由 `ctx_seed`（即"当前生成到第几个位置"）决定，与已生成的 token 内容无关。真实语言模型的下一个 token 分布强烈依赖前文：接受或拒绝某个 token 会改变后续所有分布。本模拟中"走哪条路"不影响后面的分布，因此无法体现"一个早期错误导致后续 draft 全部失配"这类现象。
2. `propose` 直接调用 `target.distribution(...)`：以概率 `alignment` 选 target 的 argmax，否则按 target 分布采样。它等价于"draft 能看到 target 的真实分布"，相当于一个完美知情的 draft 加上噪声。现实中 draft 只能用自己的参数近似 target（EAGLE 用 target 的 hidden states 训练 head，已经是最接近的做法），二者的差距正是接受率的来源。这里的 draft 偷看了答案，所以 `alignment` 只控制"故意犯错的比例"。
3. `next_tok` 被返回后，`speculative_decode` 只执行 `m.generated += 1`，token 本身被丢弃；accepted 的 token 也只用于计数。代码里没有任何地方保存生成序列——它只是一个"计数模拟器"，无法检查输出质量或分布。

### Q12 — 参考答案

1. decode 阶段：`(980 − 42) ms / (620 − 1) token ≈ 1.515 ms/token`，即约 **660 token/s**（单条流）。
2. 读一遍 70 GB 权重：`70 GB / 3.35 TB/s ≈ 20.9 ms`（已计算）。即使 bs = 8 共享这次读取，每条流每次 target 前向最多产出约"接受数 + 1"个 token；按每步 3.2～4.2 个 token 计算，单流上限约 `4.2 / 20.9 ms ≈ 200 token/s`，还没算 KV cache 读取、draft 计算和调度开销。若是 2 卡张量并行，带宽翻倍，上限也只到约 400 token/s。示例中的 660 token/s 超出了这个粗略上限，**按带宽估算不太可信**，更像是示意数字。（这只是数量级估算，用于练习"用 roofline 思维检查 benchmark 数字"。）
3. 两个指标口径不同：
   - 若 acceptance_rate 是"被接受的 draft token / 提出的 draft token"，`3.2 / 0.76 ≈ 4.2`，对应每步提出约 4～5 个 token；
   - 若 accepted_tokens_per_step 含补充 token，则接受的 draft token 约 2.2 个；
   - 若按独立接受模型 α = 0.76、k = 4 计算，期望接受 draft token 只有 `Σ_{i=1..4} 0.76^i ≈ 2.11` 个。
   因此报告时必须写明：k 是多少、接受率的分子分母是什么、"每步 token"是否包含补充 token。否则不同团队的数字无法比较——本节代码的 `acceptance_rate` 与 `tok/call` 就是两种不同口径。

### Q13 — 参考回答要点

- **做法**：用一个便宜的 draft 一次猜 k 个 token，target 在一次前向中并行计算这 k 个位置（外加一个）的分布，按规则接受最长前缀；拒绝处从修正分布采样一个 token，全部接受则额外得到一个补充 token。
- **为什么快**：自回归 decode 每步只算一个 token，GPU 算力大量闲置、瓶颈是读权重与 KV cache 的显存带宽；把 k+1 个位置放进一次前向，几乎不增加读权重的成本，却可能产出多个 token。
- **为什么质量不变**：采用 `min(1, p/q)` 接受 + 残差重采样，可以证明输出分布与直接从 target 采样完全相同（greedy 情形下则是"与 target 的贪心结果逐 token 一致"）。
- 加分点：指出本节代码的简化规则不满足这一性质；收益取决于 α 与 draft 成本，公式 `(1 − α^(k+1)) / ((1 − α)(1 + kc))`。
- 常见误区：认为推测解码"用小模型的输出代替大模型"——实际上每个 token 都经过 target 的把关。

### Q14 — 参考回答要点

- **batch = 1**：decode 严重受带宽限制，GPU 算力闲置最多，"多算几个位置"几乎免费，收益最大。
- **大 batch**：同一次前向已经在服务很多请求，算力逐渐饱和（趋向计算受限），每条请求多验证 k 个位置意味着实打实的额外计算，挤占其他请求的 token；被拒绝的 draft 是纯浪费。总吞吐增益变小，甚至为负。
- **p99**：单步验证更重，被拒时单步延迟高于普通 decode；接受率在不同请求间差异大，长尾请求（如代码、罕见领域）更容易被拒。讲义因此要求"p99 at batch 1/8/32 with and without speculation"，拒绝规则也禁止"在 bs = 32 下没有对照组就宣称有收益"。
- **缓解**：按 batch 大小门控（大 batch 时减小 k 或关闭推测）、自适应 k、接受率低时切换 ngram 或关闭（讲义交付物提到 batch gating、ngram fallback、量化调整）。

### Q15 — 参考回答要点

- **对照组**：同一硬件、同一量化（如 FP8 Marlin）、同一 vLLM 版本，关闭推测作为 baseline（讲义第 3 步"Before speculation... Publish."）。
- **负载矩阵**：batch 1/8/32（或并发数）× 流量分布（ShareGPT、MT-Bench、GSM8K、HumanEval、领域数据）× 输出长度。
- **指标**：吞吐（token/s）、TTFT、TPOT/ITL、p50/p99、GPU 利用率、分分布接受率与平均接受长度、$/1M tokens。
- **质量一致性**：讲义要求"matched quality"——greedy 下逐 token 对比输出；采样下在 GSM8K、HumanEval 等任务上比较分数，确认无统计显著差异。
- **统计严谨**：预热、多次重复、报告置信区间；固定 prompt 集合与随机种子。
- **成本对比**：与托管 API 对比时要计入其 prompt caching 折扣（交付物 hard reject）。
- **结论表述**：给出在哪些分布、哪些 batch 下达到 2.5x，在哪些条件下没有收益或 p99 变差，以及采取的缓解。

### Q16 — 参考回答要点

- **问题根源**：draft head 是针对 3.3 的 hidden states 训练的，target 升级后分布漂移，接受率下降；交付物 hard reject："Ignoring draft-target version alignment. Drifted drafts cost more than no speculation."（讲义练习 1）。
- **监控**：按模型版本 × 流量类别统计接受率、平均接受长度、单步验证耗时、p99；设置相对基线的告警阈值（例如接受率下降超过若干个百分点持续 N 分钟）。
- **应对**：
  - 部署时把 draft 版本与 target 版本绑定，版本不匹配直接禁用推测；
  - 接受率低于阈值时自动降级为 ngram draft（讲义练习 2）或关闭推测；
  - 按流量类别分别配置 k（代码类可能适合 ngram，因为重复片段多）；
  - 尽快用 SpecForge 或 Speculators hub 获取与新版本对齐的 draft，灰度发布并对比。
- **发布纪律**：升级前 drain，金丝雀发布，比较新旧版本的接受率与 p99。

### Q17 — 参考回答要点

- **独立小模型**：同族的小模型（共享 tokenizer）作 draft，部署简单，但要额外占显存，且对齐度一般。
- **ngram / prompt lookup**：从 prompt 或已生成文本中查找重复片段作为 draft，几乎零成本，在代码编辑、摘要、RAG 引用等"复制粘贴多"的场景效果好，开放式生成上接受率低。
- **附加 head（Medusa / EAGLE 类）**：在 target 上加轻量 head 预测后续 token。讲义：EAGLE-3 的 draft head 用 target 的 hidden states 训练，接受率高（Key Terms 说约 75%），比 ngram 在多数流量上更好。
- **P-EAGLE**：讲义描述为"Tree of draft branches verified in one target pass"——一次验证一棵候选树，提高期望接受长度，代价是验证 pass 更大，存在"有利 / 不利"的拐点（讲义第 5 步要求找出这个拐点）。
- **MoE target**：讲义第 7 步提示"Draft is trickier (MoE routing noise)"，路由噪声让 hidden states 与输出关系更不稳定。应选用针对该 MoE 训练的 EAGLE head（如 Speculators hub 提供的对齐 draft），并做"注入路由噪声 vs 不注入"的受控实验测敏感度（讲义练习 3）。

---

## 六、关联知识点

### 前置知识
- [阶段 07 · 16 Speculative Decoding — 草稿、验证、重复](../../../07-transformers-deep-dive/16-speculative-decoding/docs/zh.md)：推测解码的基本算法与无损证明。
- [阶段 10 · 15 Speculative Decoding 与 EAGLE-3](../../../10-llms-from-scratch/15-speculative-decoding-eagle3/docs/zh.md)：EAGLE-3 的 draft head 原理。
- [阶段 10 · 12 Inference Optimization](../../../10-llms-from-scratch/12-inference-optimization/docs/zh.md)：prefill / decode 与带宽瓶颈。
- [阶段 07 · 12 KV Cache、Flash Attention 与 Inference 优化](../../../07-transformers-deep-dive/12-kv-cache-flash-attention/docs/zh.md)：验证 pass 中的 KV cache 管理。
- [阶段 10 · 11 Quantization：让模型装得下](../../../10-llms-from-scratch/11-quantization/docs/zh.md)：FP8 / INT4 量化基础。

### 本节被哪些后续内容用到
- [阶段 17 · 05 生产环境中的 EAGLE-3 Speculative Decoding](../../../17-infrastructure-and-production/05-eagle3-speculative-decoding/docs/zh.md)：生产配置与调优。
- [阶段 17 · 04 服务引擎内部机制：PagedAttention、Continuous Batching 与 Chunked Prefill](../../../17-infrastructure-and-production/04-vllm-serving-internals/docs/zh.md)：推测解码与连续批处理的交互。
- [阶段 17 · 08 Inference 指标：TTFT、TPOT、ITL、Goodput、P99](../../../17-infrastructure-and-production/08-inference-metrics-goodput/docs/zh.md)：本节报告所需的全部延迟指标。
- [阶段 17 · 03 Kubernetes 上的 GPU Autoscaling](../../../17-infrastructure-and-production/03-gpu-autoscaling-kubernetes/docs/zh.md)：按队列等待扩缩容。
- [阶段 17 · 22 对 LLM APIs 进行负载测试](../../../17-infrastructure-and-production/22-load-testing-llm-apis/docs/zh.md)：如何正确压测推理服务。
- [阶段 17 · 27 LLMs 的 FinOps：单位经济性与多租户成本归因](../../../17-infrastructure-and-production/27-finops-llms/docs/zh.md)：$/1M tokens 的成本核算。

### 延伸关键词
`speculative sampling` · `rejection sampling` · `acceptance length` · `EAGLE-3` · `P-EAGLE` · `Medusa` · `prompt lookup / ngram draft` · `SpecForge` · `Speculators` · `roofline` · `memory-bound decode` · `TTFT / TPOT / p99` · `HPA queue_wait_ms` · `FP8 Marlin` · `AWQ`
