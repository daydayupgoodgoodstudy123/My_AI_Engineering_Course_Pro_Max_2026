# 测验 · Speculative Decoding 与 EAGLE-3（Speculative Decoding and EAGLE-3）

> **阶段 10 · 从零构建 LLM · 第 15 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 为什么能加速 | 大模型 decode 受显存带宽限制，每步都要读一遍全部权重却只产出 1 个 token；一次 verifier 前向同时验证 N 个草稿 token，最多产出 N+1 个 |
| 2 | Leviathan 拒绝规则 | 草稿 `d ~ p`，以 `min(1, q(d)/p(d))` 接受；拒绝时从残差 `(q − p)₊ / ‖(q − p)₊‖₁` 采样。输出分布**严格等于** q，与 p 好坏无关 |
| 3 | N 步串联 | verifier 一次前向返回 `q₁…q_{N+1}`；从左到右检查，第一次拒绝时从残差采样并停止；全部接受时再从 `q_{N+1}` 免费采一个 bonus token |
| 4 | 接受率 α | 单个草稿 token 被接受的期望概率，等于 `Σ min(p, q) = 1 − TV(p, q)`；是加速比最大的杠杆 |
| 5 | 期望产出 | `E[tokens / verify] = (1 − α^{N+1}) / (1 − α)`；α = 0.9、N = 5 时为 4.69 |
| 6 | 墙钟模型 | 每 token 时间 ≈ `(1 + N·c) / E`，c 是草稿与 verifier 的成本比；对 N 求最小值得到最优草稿长度 |
| 7 | EAGLE 演进 | 独立小模型（α≈0.6）→ EAGLE-1：以 verifier 最后一层 hidden state 为输入的 1–2 层小网络 → EAGLE-2：动态草稿树 + tree attention → EAGLE-3：去掉特征预测损失、多层特征融合、training-time test |
| 8 | Training-time test（TTT） | 训练草稿时把它自己的预测喂回去多步，对齐训练与推理时的输入分布，解决 exposure bias（与 scheduled sampling 同源） |
| 9 | KV rollback | verifier 一次写入 N 个位置的 KV；在位置 j 拒绝后，j 之后的条目作废，靠"scratch buffer 提交"或"逻辑长度截断"回滚 |
| 10 | 适用边界 | 适合交互式对话、代码/JSON 等可预测输出、长文本；不适合 <3B 小模型、CPU 小批量部署、高温创意采样（α 崩塌） |

### 核心技能（能动手做到）

- [ ] 写出 Leviathan 规则与残差分布，并能用一行等式证明 `P(输出 = t) = q(t)`
- [ ] 给定 p、q 计算 α，给定 α、N 计算期望产出，给定 c 找出最优 N
- [ ] 跑通 `main.py` 的 5 个步骤，解释每张表的含义，并指出 Step 5 的"期望值"对比用错了 α
- [ ] 指出 `KVBuffer` 的 `truncate_to` 在当前代码里从未真正"回滚"，并写出能体现物理写入与回滚的版本
- [ ] 指出 Step 1 卡方检验的统计口径问题（拿另一份有噪声的样本当期望值），并改成对 q 的拟合优度检验
- [ ] 说清 EAGLE-1/2/3 各自解决了什么限制，以及什么场景下应该关闭 speculative decoding

---

## 二、基础自测（选择题）

**Q1.** 关于 Leviathan 拒绝采样规则，下列描述正确的是：

- A. 若 `q(d) > p(d)` 则接受，否则拒绝，拒绝后重新从 p 采样
- B. 以概率 `q(d)` 接受草稿，拒绝后从 q 采样
- C. 以概率 `min(1, q(d)/p(d))` 接受草稿，拒绝后从 `(q − p)₊` 归一化后的残差分布采样
- D. 以概率 `min(1, p(d)/q(d))` 接受草稿，拒绝后从 p 采样

**Q2.** 草稿长度 N = 5、每个草稿 token 的接受率 α = 0.9，每次 verifier 前向的期望产出 token 数约为：

- A. 4.69
- B. 4.10
- C. 5.31
- D. 6.00

**Q3.** 关于 speculative decoding 的输出质量，正确的说法是：

- A. 草稿越差，输出分布偏离 q 越多，因此需要在速度和质量之间权衡
- B. 只有在 temperature = 0 时输出才与 verifier 一致
- C. 输出分布约等于 q，误差随 N 增大而增大
- D. 无论草稿分布 p 多差，输出分布都严格等于 verifier 的 q；p 的好坏只影响接受率和速度

**Q4.** EAGLE-3 相对 EAGLE-1/2 的两项关键改动是：

- A. 把草稿模型换成独立训练的小 LLM，并取消树搜索
- B. 去掉对 verifier hidden state 的特征预测损失、直接训练 token 预测；引入 training-time test，训练时把草稿自己的预测喂回作为输入
- C. 增加多个 LM head（Medusa 式），并用 Jacobi 迭代代替草稿
- D. 把拒绝规则放宽为"只要草稿在 q 的 top-5 中就接受"

**Q5.** N = 5，某一步 5 个草稿 token 全部被接受。这一步一共产出多少个 token、用了几次 verifier 前向？

- A. 5 个 token，1 次前向
- B. 6 个 token（5 个草稿 + 1 个从 `q₆` 采样的 bonus token），1 次前向
- C. 6 个 token，2 次前向
- D. 10 个 token，1 次前向

**Q6.** verifier 分布 `q = [0.5, 0.5]`，草稿分布 `p = [0.8, 0.2]`。单个草稿 token 的接受率 α 是：

- A. 0.5
- B. 0.8
- C. 0.4
- D. 0.7

**Q7.** 根据讲义，下列哪种场景**最不适合**开启 speculative decoding？

- A. 高温度（如 creative writing）采样，α 会显著下降
- B. 交互式聊天，p50 延迟比峰值吞吐更重要
- C. 生成 JSON、SQL 等结构化输出
- D. 生成数千 token 的长文本

**Q8.** `main.py` 的 Step 5 用 `p_eagle3`、N = 5 跑 1000 轮，实测 `mean tokens / forward: 5.73`，旁边打印的对照值却是 `expected at alpha=0.95, N=5: 5.30`。两者差异的主要原因是：

- A. 模拟次数太少，5.73 只是随机波动
- B. bonus token 被重复计数
- C. `p_eagle3` 的真实接受率约为 0.98（Step 2 实测 0.982，精确值 `Σmin(p,q) ≈ 0.980`），对应期望约 5.71；代码拿写死的 α = 0.95 做对照
- D. KV cache 截断导致多产出了 token

---

## 三、动手 / 代码题

**Q9.** 阅读 `KVBuffer` 与 `spec_step` 中的 KV 记账：

```python
@dataclass
class KVBuffer:
    length: int = 0
    def extend(self, n: int) -> None:
        self.length += n
    def truncate_to(self, n: int) -> None:
        self.length = n

def spec_step(q, p, N, kv, rng):
    prefix_len = kv.length
    ...
    for i, d in enumerate(drafts):
        ...
        if u < min(1.0, ratio):
            emitted.append(d)
            kv.extend(1)
        else:
            correction = sample(residual(q, p), rng)
            emitted.append(correction)
            kv.truncate_to(prefix_len + len(emitted))
            return emitted, 1
    bonus = sample(q, rng)
    emitted.append(bonus)
    kv.extend(1)
    return emitted, 1
```

1. 在第 j 个位置（0 起）拒绝时，`truncate_to` 调用前后 `kv.length` 分别是多少？这次调用是在"回滚"吗？
2. 真实的 verifier 在一次前向里对 KV cache 做了什么写入？请改写 `spec_step` 的记账，使其先模拟"物理写入 N 个草稿位置"，再在拒绝时真正截断，并说明 correction/bonus token 的 KV 什么时候才会被写入。
3. 讲义练习 4：两条序列 A（全部接受）和 B（在位置 2 拒绝）共用一次 batched verify，N = 5、前缀长度都为 100。写出两条序列各自最终的逻辑长度。

**Q10.** Step 1 用下面的函数判断"投机解码的输出分布是否等于 q"：

```python
def chi_square(observed, expected):
    ...
    for o, e in zip(observed, expected):
        e_norm = e * total_obs / total_exp
        if e_norm > 0:
            result += (o - e_norm) ** 2 / e_norm
```

其中 `expected` 是**另一份** 50,000 次直接从 q 采样的计数，临界值取 df = 7 的 14.07。

1. 这样做在统计上有什么问题？在分布确实相同时，它的误报率大约是多少？
2. 如何改成正确的检验？
3. 这个检验只覆盖了什么情形？还有哪些 token 的分布没有被验证？

**Q11.** 讲义练习 2 与"What determines speedup"一节：

1. 用代码中的 `wall_time_per_token` 在 α = 0.9、c = 0.04 下扫描 N = 1…20，最优 N 是多少？在 N = 1…10 范围内呢？
2. 讲义称"α = 0.8, c = 0.05：最优 N 约 5–7，加速 3.2×；α = 0.95, c = 0.02：最优 N 约 8–10，加速约 5×"，又称"N = 5 时 α 从 0.6 提到 0.9，期望产出从 2.2 变为 4.1"。用公式逐一核对。
3. 为什么这个公式会高估大 N 的收益？

**Q12.** 用 `q = [0.5, 0.3, 0.2]`、`p = [0.2, 0.5, 0.3]`：

1. 手算 α、残差分布，并逐项验证 `P(输出 = t) = p(t)·min(1, q(t)/p(t)) + (1 − α)·residual(t) = q(t)`。
2. 若把残差换成"拒绝后直接从 q 采样"，输出分布变成什么？为什么错？

---

## 四、面试高频题

**Q13.**（基础必考）speculative decoding 为什么能在不损失质量的前提下加速大模型推理？它利用了 decode 阶段的什么特性？

**Q14.**（原理深挖）请证明 Leviathan 拒绝采样的输出分布等于 q，并解释为什么 bonus token 是"免费"的。

**Q15.**（原理深挖）EAGLE-1、EAGLE-2、EAGLE-3 分别解决了前一代的什么限制？什么是 exposure bias，TTT 为什么能缓解它？

**Q16.**（工程实践）线上服务开启 EAGLE-3 后，你发现高并发时吞吐提升远小于低并发时，高温度请求的延迟甚至变差。请解释原因并给出调参策略。

**Q17.**（追问型）在 batched serving 中，不同序列的接受长度不同，KV cache 怎么回滚？EAGLE-2 的树形草稿怎么在一次前向里验证？

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义："Accept with probability `min(1, q(d) / p(d))`. On reject, sample from the residual distribution `(q - p)_+ / ||(q - p)_+||_1`." A 是确定性规则，拒绝后从 p 重采会使分布偏向 p；B 的接受概率不对；D 把比值写反，拒绝后从 p 采样也不对。

### Q2 — 答案：A

`(1 − 0.9⁶) / (1 − 0.9) = (1 − 0.531441) / 0.1 = 4.686`，与代码 Step 3 表中 `0.90, N=5 → 4.69` 一致。B 是讲义正文"from 2.2 ... to 4.1"中的 4.1，但按讲义自己的公式应为 4.69（见 Q11）；C 是 α = 0.95 时的值（5.30 附近）；D 是 N + 1 的上限，只有 α = 1 才达到。

### Q3 — 答案：D

讲义："This is true regardless of how bad `p` is — the worse it is, the more often you reject, but the output remains exact." "Not approximately. Identically." 这正是它能在生产中默认开启的原因：纯延迟优化，没有质量权衡。A、C 把"速度"和"质量"混为一谈；B 错，规则对任意温度下的 q 都成立（贪心只是特例）。代码 Step 1 的卡方检验就是在经验上验证这一点。

### Q4 — 答案：B

讲义："drop the feature-prediction loss entirely ... EAGLE-3 trains directly on token prediction. Second, training-time test (TTT): during draft training, feed the draft's own previous predictions back as inputs over multiple steps"。讲义表格还提到 EAGLE-3 的"Multi-layer feature fusion"（使用 verifier 多层特征而非仅最后一层）。A 是倒退回 vanilla；C 是 Medusa 和 Lookahead；D 会改变输出分布，违反"无质量损失"的前提（outputs 技能文件把"relaxed rejection"列为硬拒绝项）。

### Q5 — 答案：B

代码：全部接受后执行 `bonus = sample(q, rng)`，`emitted` 共 N + 1 = 6 个；函数始终返回 `verifier_forwards_used = 1`。bonus token 来自 verifier 本来就算出的 `q_{N+1}`（对第 N 个草稿之后位置的预测），不需要额外前向。

### Q6 — 答案：D

`α = Σ_t p(t)·min(1, q(t)/p(t)) = Σ_t min(p(t), q(t)) = min(0.8, 0.5) + min(0.2, 0.5) = 0.5 + 0.2 = 0.7`。等价地，`α = 1 − TV(p, q) = 1 − 0.3`。A 是 q 的最大值；B 是 p 的最大值；C 是 `0.8 × 0.5`，把"接受概率"误当成"两个概率相乘"。

### Q7 — 答案：A

讲义"When not to"：<3B 的小模型、CPU 小批量部署、"Very-high-temperature creative sampling where `α` collapses"。高温下 q 变平、p 与 q 的重叠下降，接受率掉下来，草稿的开销白花。B、C、D 都在讲义"When to reach for"列表中（代码/结构化输出 α 可高于 0.9）。

### Q8 — 答案：C

Step 2 实测 `eagle-3 ... alpha 0.982`；用 `Σmin(p, q)` 精确计算为 0.9802，`E(0.9802, 5) ≈ 5.71`，与实测 5.73 非常接近。代码却写死了 `expected_tokens_per_verify(0.95, 5)` 作为对照，容易让人误以为"实测比理论好"。另外，代码中 `p_eagle3/eagle1/vanilla` 的名字只是三档扰动幅度（0.005/0.02/0.08），对应的 α（0.98/0.93/0.80）都比讲义表格中同名方法的 α（0.88–0.92 / 0.70–0.80 / 0.55–0.70）高，"takeaway"里说的 "alpha~0.9" 也不是这次模拟的 α。A、B、D 均不成立（`kv.length` 恰好等于总产出 5732，没有重复计数）。

### Q9 — 参考答案

1. 在位置 j 拒绝时，前面 j 个草稿都被接受，每次 `extend(1)`，所以调用前 `kv.length = prefix_len + j`；`emitted` 此时有 j + 1 个元素（j 个草稿 + 1 个 correction），调用后 `kv.length = prefix_len + j + 1`——**长度变大了 1**，并没有回滚。实测连续 5 步：`(0→1)、(1→6)、(6→7)、(7→9)、(9→10)`，`length` 始终等于"已产出 token 数"，从不减少。原因是代码从未模拟 verifier 的"物理写入 N 个位置"，所以也无所谓截断。它实际上是一个"序列长度计数器"。
2. 真实流程：verifier 对 `prefix + d₁…d_N` 做一次前向，KV cache 被写入 N 个新位置（`d₁…d_N`）；接受 k 个后，`d_{k+1}…d_N` 的 KV 作废，逻辑长度截断为 `prefix + k`；correction 或 bonus token 此时还**没有** KV——它将作为下一步的输入，在下一次前向中被写入。参考改写：

```python
@dataclass
class KVBuffer:
    physical: int = 0     # 已写入的条目数（含可能作废的草稿）
    logical: int = 0      # 有效前缀长度

def spec_step_kv(q, p, N, kv, rng):
    drafts = [sample(p, rng) for _ in range(N)]
    kv.physical = kv.logical + N            # verifier 一次前向写入 N 个草稿位置
    emitted = []
    for d in drafts:
        if rng.random() < min(1.0, q[d] / p[d]):
            emitted.append(d)
        else:
            emitted.append(sample(residual(q, p), rng))
            break
    else:
        emitted.append(sample(q, rng))      # bonus
    accepted_drafts = len(emitted) - 1      # 最后一个是 correction 或 bonus
    kv.logical += accepted_drafts           # 截断：只保留被接受的草稿
    kv.physical = kv.logical                # 物理上丢弃（或在 scratch buffer 中不提交）
    return emitted, 1
```

   注意：严格来说"位置 j 拒绝"时被接受的草稿是 j 个，`emitted` 中最后一个 token 的 KV 会在下一轮计算。讲义 Step 4 写"logical length is set to prefix_length + j + 1 — one past the correction token"，与这种实现差一个位置，取决于是否把 correction token 计入"已缓存"；两种约定都可以，但必须在整个系统中保持一致。
3. 按"逻辑长度 = 已接受草稿数"的约定：A 全部接受，长度 `100 + 5 = 105`，bonus token 在下一轮写入；B 在位置 2（0 起，即第 3 个草稿）拒绝，接受 2 个，长度 `100 + 2 = 102`，位置 102–104 的 3 个条目作废。两条序列的长度从此不同，下一轮 batched verify 需要按序列分别维护长度（ragged batch），这正是 vLLM / TensorRT-LLM 中"每序列逻辑长度"或"scratch buffer 提交"要解决的问题。若按代码的约定（把 correction/bonus 也计入），则 A 为 106、B 为 103。

### Q10 — 参考答案

1. 问题：把另一份**有限样本**的计数当成"期望值"。两份样本各自都有抽样噪声，`o − e` 的方差约是单样本检验的 2 倍，统计量近似服从 `2·χ²(7)` 而不是 `χ²(7)`，用 14.07 做临界值会大量误报。实测（1000 次重复，每次 3000 个样本，p 用 `p_eagle1`）：代码的检验误报率约 **42%**；而改为对 q 的拟合优度检验后误报率约 **4.5%**，接近名义上的 5%。本次运行碰巧得到 11.60 而判为 PASS。
2. 正确做法：直接对理论分布 q 做拟合优度检验——

```python
def chi_square_gof(observed, q):
    n = sum(observed)
    return sum((o - n * qi) ** 2 / (n * qi) for o, qi in zip(observed, q))
```

   本次运行的 `spec counts` 用该检验得到 χ² ≈ 3.42（df = 7），远低于 14.07。若坚持做两样本检验，应使用列联表卡方（2 × 8 表，df = 7）而不是把一份样本当期望。
3. 只验证了 **N = 1 时第一个产出 token** 的分布（docstring 也说明了这一点）。未验证：N > 1 时第 2、3…个位置的 token；全部接受后的 bonus token；以及上下文相关（q_i、p_i 随位置变化）的情形。由于代码中 q、p 与位置无关，这些位置的正确性在数学上同样成立，但"经验验证"并没有覆盖它们。

### Q11 — 参考答案

1. 用代码公式扫描（已运行）：α = 0.9、c = 0.04 时，每 token 时间在 N = 14、15 处最小（约 0.1964，加速约 5.09×）；在 N = 1…10 范围内单调下降，N = 10 最好（0.204，约 4.90×）。曲线形状：N 小时，增加 N 带来的期望产出增长（几何级数）快于草稿成本线性增长；N 大时，`α^{N+1}` 趋于 0，期望产出趋于 `1/(1−α) = 10` 的上限，而草稿成本仍线性增长，曲线变平并回升。
2. 逐一核对（已运行）：
   - α = 0.8、c = 0.05：最优 N = 8，加速 3.09×；N = 6–10 都在 3.04–3.09× 之间，曲线很平。讲义"N 约 5–7、3.2×"略有高估，但量级正确。
   - α = 0.95、c = 0.02：按公式最优 N 超过 20（N = 20 时约 9.4×），N = 8 时已 6.38×、N = 10 时 7.19×。讲义"N 约 8–10、约 5×"与其自身公式不符。
   - N = 5：α = 0.6 时 `E = 2.38`，α = 0.9 时 `E = 4.69`；讲义写的是 2.2 和 4.1，与公式和代码 Step 3 表都不一致。"接近 2 倍"的结论仍大致成立（4.69 / 2.38 ≈ 1.97）。
3. 公式假设"一次 verifier 前向的成本与验证 token 数无关"（恒为 1）。在 memory-bound 的小 batch 下这近似成立，但 N 变大时 verifier 每步要处理 N+1 个 token 的注意力与 MLP，batch 大时 decode 会转为 compute-bound，验证 N 个 token 的成本明显上升；此外草稿是自回归的，N 步草稿的**延迟**是串行的；被拒绝的草稿浪费的 KV 写入与算力也没有计入。所以生产中 N 一般取 3–7（讲义 vLLM 示例用 `num_speculative_tokens: 5`），并随 batch 变大而减小。

### Q12 — 参考答案

1. `α = Σmin(p, q) = 0.2 + 0.3 + 0.2 = 0.7`。`(q − p)₊ = [0.3, 0, 0]`，归一化后残差为 `[1, 0, 0]`。逐项：
   - t = 0：`p·min(1, q/p) = min(p, q) = 0.2`，加 `(1 − 0.7) × 1 = 0.3`，合计 0.5 = q(0)；
   - t = 1：`min(0.5, 0.3) = 0.3`，残差 0，合计 0.3 = q(1)；
   - t = 2：`min(0.3, 0.2) = 0.2`，残差 0，合计 0.2 = q(2)。
   一般地，`min(p, q) + (q − p)₊ = q`，而 `1 − α = Σ(q − p)₊`，所以 `(1 − α) · residual(t) = (q − p)₊(t)`。
2. 拒绝后直接从 q 采样：`P(t) = min(p, q)(t) + 0.3 · q(t) = [0.2 + 0.15, 0.3 + 0.09, 0.2 + 0.06] = [0.35, 0.39, 0.26]`，偏离了 q。原因：被接受的部分已经"贡献"了 `min(p, q)`，在 p 偏大的 token（t = 1、2）上已经足额甚至无需补充，拒绝后再按 q 采样就会对这些 token 重复计入；残差只补"q 比 p 多出来的那部分"，所以恰好凑成 q。

### Q13 — 参考回答要点

- **decode 的特性**：每生成 1 个 token 都要从 HBM 读出全部权重（70B 模型约 140 GB BF16），算术量很小，GPU 计算单元大部分时间空闲——瓶颈是显存带宽（讲义："Memory bandwidth is the ceiling"）。
- **思路**：让一个便宜的草稿先猜 N 个 token，verifier 对 `prefix + N 个草稿` 做**一次**前向（读一次权重），并行算出 N+1 个位置的分布；按规则接受一段前缀，一次前向产出 1 到 N+1 个 token。
- **为什么不损失质量**：Leviathan 拒绝规则保证输出分布严格等于 verifier 直接采样的分布（讲义："Not approximately. Identically."）。
- **收益取决于**：接受率 α（最大杠杆）、草稿成本比 c、草稿长度 N。
- 加分点：说明 batch 很大时 decode 已接近 compute-bound，投机的收益会下降（见 Q16）。

### Q14 — 参考回答要点

- **证明**：对任意 token t，
  `P(输出 t) = P(草稿 = t 且接受) + P(拒绝) · residual(t)`
  `= p(t)·min(1, q(t)/p(t)) + (1 − α) · (q(t) − p(t))₊ / Σ(q − p)₊`
  `= min(p(t), q(t)) + (q(t) − p(t))₊`（因为 `1 − α = Σ(q − p)₊`）
  `= q(t)`。
- **N 步串联**：每个位置在"前缀已按 q 分布生成"的条件下单独满足上式，归纳可得整段序列服从 verifier 的联合分布；第一次拒绝后必须停止，因为后续草稿是以被拒绝的 token 为条件生成的，不再有效。
- **bonus token 免费**：verifier 对 `prefix + d₁…d_N` 的前向本来就会输出最后一个位置之后的分布 `q_{N+1}`；全部接受时直接从它采样，无需额外前向。
- 常见误区：以为"接受率低会降低质量"——只会降低速度。

### Q15 — 参考回答要点

- **Vanilla → EAGLE-1**：独立小模型与 verifier 的分布差距大（α ≈ 0.6）。EAGLE-1 让一个 1–2 层的小 transformer 以 verifier 最后一层 hidden state 为输入预测下一个 token，"看到"verifier 的特征表示，α 提升到 0.7–0.8。
- **EAGLE-1 → EAGLE-2**：单条草稿链一旦早期被拒绝，后面全部浪费。EAGLE-2 提出动态草稿树，一次 verifier 前向用 tree attention（按树拓扑定制的非因果 mask）同时验证多个候选，选接受的最长/最高概率路径，草稿长度自适应。
- **EAGLE-2 → EAGLE-3**：EAGLE-1/2 训练草稿去拟合 verifier 的 hidden state，限制了"加数据还能提升多少"；EAGLE-3 去掉特征预测损失，直接训练 token 预测，并融合多层特征；同时引入 TTT。
- **Exposure bias**：训练时草稿的输入总是"真实的"verifier 特征/token（teacher forcing），推理时却要以自己上一步的预测为输入，分布不一致，误差逐步累积，越往后的草稿位置 α 越低。
- **TTT**：训练时就让草稿自回归地使用自己的预测作为后续步骤的输入，训练分布与推理分布一致——与 seq2seq 中的 scheduled sampling 思路相同。
- 讲义数据：EAGLE-3 端到端最高 6.5×（chat），SGLang 在 H100、batch 64 时吞吐提升约 38%。

### Q16 — 参考回答要点

- **高并发收益小**：batch 大时 decode 的算术强度上升、逐步转为 compute-bound，"一次读权重验证多个 token"的免费午餐变小；验证 N 个草稿等于把有效 batch 放大 N+1 倍，算力开始成为瓶颈；被拒绝的草稿浪费的算力在高负载下是真实成本。讲义：batch 64 时 EAGLE-3 的吞吐提升是 1.38×，远低于低并发下的 3–6.5×。
- **高温延迟变差**：高温下 q 变平，α 下降，大部分草稿被拒绝，却仍付出草稿开销和更大的验证前向。
- **策略**：
  - 按 batch 动态调整 N 与树形（outputs 技能文件：batch ≤ 8 用 depth 3、分支 (4, 2, 2)；batch 16–64 用 depth 2；batch > 64 不用树）；
  - 温度门控：温度超过校准阈值（技能文件以 0.8 为参考）时关闭投机或改用更宽更浅的树；
  - 用线上 α 遥测按任务类型分桶（代码/JSON vs 闲聊 vs 创作）设置 N；
  - 用 `(1 + N·c) / E` 只作初值，最终以实测 TPOT / 吞吐为准。
- 加分点：说明这些都**不改变输出分布**，只是选择是否、以多大力度投机。

### Q17 — 参考回答要点

- **batched 回滚**：每条序列维护自己的逻辑 KV 长度。两种实现（讲义）：草稿 KV 先写入 scratch buffer，验证后只提交接受的部分（讲义称 vLLM、TensorRT-LLM 采用）；或物理 cache 照写，配合每序列逻辑长度，读取时截断。回滚只是改一个整数或丢弃 buffer，成本相对前向可以忽略。
- **长度不齐**：下一轮各序列从不同位置继续，依赖分页 KV（PagedAttention）与 ragged batch 支持；outputs 技能文件强调"没有 KV rollback 就跑投机解码会静默污染后续 token"。
- **树形验证**：把树的所有节点展平成一个序列送入 verifier，用一个按树拓扑构造的 attention mask——每个节点只能看到前缀和自己的祖先节点，不能看到兄弟分支；一次前向得到每个节点的 `q`，然后按 Leviathan 规则沿树选出被接受的路径（讲义："a standard flash-attention call with a custom mask"）。
- 加分点：树中被丢弃分支的 KV 同样需要回滚；树的总节点数受显存和算力预算约束，所以 batch 越大树越小。

---

## 六、关联知识点

### 前置知识
- [阶段 07 · 16 Speculative Decoding — 草稿、验证、重复](../../../07-transformers-deep-dive/16-speculative-decoding/docs/zh.md)：讲义开头所说的"Phase 7 · 16 证明了数学"。
- [阶段 10 · 12 Inference Optimization](../../12-inference-optimization/docs/zh.md)：decode 的 memory-bound 特性与 KV cache。
- [阶段 07 · 12 KV Cache、Flash Attention 与 Inference 优化](../../../07-transformers-deep-dive/12-kv-cache-flash-attention/docs/zh.md)：KV cache 的写入与截断。
- [阶段 01 · 16 Sampling 方法](../../../01-math-foundations/16-sampling-methods/docs/zh.md)：拒绝采样的一般原理。
- [阶段 01 · 15 机器学习统计](../../../01-math-foundations/15-statistics-for-ml/docs/zh.md)：卡方检验与假设检验。

### 本节被哪些后续内容用到
- [阶段 10 · 25 Speculative Decoding 与 EAGLE](../../25-speculative-decoding/docs/zh.md)：同一主题的另一视角。
- [阶段 10 · 18 Multi-Token 预测（MTP）](../../18-multi-token-prediction/docs/zh.md)：MTP 头可以直接作为投机解码的草稿。
- [阶段 17 · 05 生产环境中的 EAGLE-3 Speculative Decoding](../../../17-infrastructure-and-production/05-eagle3-speculative-decoding/docs/zh.md)：生产部署与调参。
- [阶段 17 · 04 服务引擎内部机制：PagedAttention、Continuous Batching 与 Chunked Prefill](../../../17-infrastructure-and-production/04-vllm-serving-internals/docs/zh.md)：batched KV 管理。
- [阶段 17 · 08 Inference 指标：TTFT、TPOT、ITL、Goodput、P99](../../../17-infrastructure-and-production/08-inference-metrics-goodput/docs/zh.md)：如何度量投机解码的真实收益。
- [阶段 19 · 14 推测解码 Inference 服务端](../../../19-capstone-projects/14-speculative-decoding-server/docs/zh.md)：综合项目中实现一个投机解码服务端。

### 延伸关键词
`Leviathan rejection sampling` · `residual distribution` · `acceptance rate α` · `total variation distance` · `bonus token` · `EAGLE / EAGLE-2 / EAGLE-3` · `Medusa` · `Lookahead decoding` · `tree attention` · `training-time test` · `exposure bias` · `scheduled sampling` · `KV rollback` · `num_speculative_tokens`
