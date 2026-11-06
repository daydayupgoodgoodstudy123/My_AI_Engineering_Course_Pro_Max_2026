# 测验 · Speculative Decoding 与 EAGLE（Speculative Decoding and EAGLE）

> **阶段 10 · 从零构建 LLM · 第 25 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 说明：本节中文讲义机翻质量较差（个别句子语义已失真），有疑义处一律以英文版为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 为什么 decode 慢 | 每生成 1 个 token 都要把全部权重从 HBM 读一遍，decode 是显存带宽瓶颈，算力大量闲置；讲义：70B 级模型在 H100 上 decode 约 40–80 tokens/s |
| 2 | 两模型设置 | target 模型 `M_p`（大、慢、要的就是它的分布 p）+ draft 模型 `M_q`（小 5–30 倍、快，分布 q） |
| 3 | 一轮的流程 | draft 自回归提出 K 个 token → target **一次** forward 并行算出 K+1 个位置的 p → 从左到右接受/拒绝 → 拒绝处从残差分布补 1 个并停止；全接受则从 p 额外采 1 个 bonus token |
| 4 | 精确拒绝规则 | 以概率 `min(1, p(x)/q(x))` 接受；拒绝时从 `(p−q)+ / ‖(p−q)+‖₁` 采样。整体输出分布**严格等于 p**（无损加速） |
| 5 | 接受率 α | 在精确规则下单 token 接受率 `α = Σ min(p, q) = 1 − TV(p, q)`，完全由 draft 与 target 的对齐程度决定 |
| 6 | 期望产出 | `E[tokens/verify] = (1 − α^{K+1}) / (1 − α)`；α=0.8、K=4 时为 3.36；K→∞ 时上限 `1/(1−α)` |
| 7 | 真实加速比 | 要扣掉 draft 成本：约 `E[tokens] / (1 + K·c)`，c 为 draft/target 单步成本比；K 不是越大越好 |
| 8 | Draft 的训练 | 用 KL 散度对齐 target 的分布做蒸馏（而不是对齐真实 token）；讲义：α 在代码上约 0.6–0.8、聊天约 0.7–0.85 |
| 9 | EAGLE 系列 | EAGLE-1：draft 输入 target 的最后隐藏状态、只有 1 层 decoder、输出候选树；EAGLE-2：动态树形；EAGLE-3：训练时模拟测试时分布。讲义：α 0.75→0.82，平均 tokens/verify 3.0→4.5 |
| 10 | 树形验证 | 用 tree attention mask（每个节点只看自己的祖先）在一次 forward 中验证多条候选路径，取最长被接受分支 |

### 核心技能（能动手做到）

- [ ] 用 NumPy 写出 `speculative_step`：draft K 个 token、按 `min(1, p/q)` 接受、拒绝时从残差采样、全接受时采 bonus token
- [ ] 对任意给定的小分布 p、q，手算 α、每个 token 的接受概率、残差分布，并验证输出分布等于 p
- [ ] 用 `(1 − α^{K+1})/(1 − α)` 和 `E/(1 + K·c)` 估算期望产出与真实加速比，找出最优 K
- [ ] 写出给定分支因子的候选树，并构造对应的 tree attention mask
- [ ] 设计一个能真正检验"分布无损"的实验（解析分布对比或卡方检验），而不只看两个 TV 值之差
- [ ] 说清楚在哪些负载（高并发、高温度、小 target）下 speculative decoding 不划算，以及线上回退策略

---

## 二、基础自测（选择题）

**Q1.** 在 Leviathan 等人的精确拒绝规则中，draft 提出的 token `x` 被接受的概率是：

- A. `p(x)`
- B. `q(x)`
- C. `p(x) − q(x)`（为负时取 0）
- D. `min(1, p(x) / q(x))`

**Q2.** 单 token 接受率 α = 0.8、draft 长度 K = 4，每次 target 验证的期望产出 token 数为：

- A. 3.36
- B. 4.00
- C. 5.00
- D. 2.69

**Q3.** 某个 draft token 被拒绝后，为了保证整体输出分布严格等于 p，替换 token 应该从哪里采样？

- A. 直接从 target 分布 p 采样
- B. 从 draft 分布 q 重新采样
- C. 从归一化后的残差 `(p − q)+ / ‖(p − q)+‖₁` 采样
- D. 从均匀分布采样

**Q4.** 在精确拒绝规则下，单 token 接受率 α 与两个分布的关系是：

- A. `α = KL(p ‖ q)`
- B. `α = Σₓ min(p(x), q(x)) = 1 − TV(p, q)`
- C. `α = Σₓ p(x)·q(x)`
- D. `α = maxₓ p(x)`

**Q5.** `build_tree((3, 2, 2))` 构造的候选树（含根节点）共有多少个节点？最深一层的某个叶子节点在 tree attention mask 中那一行有几个 1？

- A. 22 个节点；叶子行有 4 个 1
- B. 12 个节点；叶子行有 3 个 1
- C. 22 个节点；叶子行有 22 个 1
- D. 13 个节点；叶子行有 4 个 1

**Q6.** 下列哪种场景**最不适合**开启 speculative decoding？

- A. 单用户、低温度的代码补全
- B. 输出固定格式 JSON 的结构化抽取
- C. 单卡、低并发的英文聊天
- D. 高并发 batch 服务，verifier 已经是算力瓶颈（compute-bound）

**Q7.** 相比"独立的小 draft 模型"，EAGLE-1 的主要改动是：

- A. 换成一个 7B 的独立 draft 模型以提高 α
- B. 在 target 顶部加 K 个并行预测头，不再需要 draft
- C. draft 以 target 在位置 t 的最后隐藏状态为输入，只用 1 层 transformer decoder，并输出候选树
- D. 取消 target 的验证 forward，直接输出 draft 的结果

**Q8.** 默认运行 `python main.py`（`--alpha 0.75`）时，打印的 `measured alpha = 0.897`，明显高于 0.75。原因是：

- A. `measure_alpha` 漏掉了 `min(1, ·)`，导致高估
- B. `make_draft` 只是按 `0.75·p + 0.25·uniform` 混合，`alpha_hint` 是混合系数而不是接受率；这种 q 的真实接受率 `Σ min(p, q)` 必然 ≥ 0.75，本例精确值为 0.8955
- C. 随机种子导致的偶然波动，换个种子就会回到 0.75 附近
- D. 因为 K = 4，接受率会被放大到 `1 − 0.25^K`

---

## 三、动手 / 代码题

**Q9.** 讲义 "Build It" 中给出的 `speculative_step` 片段（节选）：

```python
    for _ in range(K):
        probs = softmax(q_draft(state) / temperature)
        t = np.random.choice(len(probs), p=probs)
        draft_tokens.append(t)
        q_probs.append(probs[t])
        state = draft_step(state, t)
    ...
        else:
            residual = np.maximum(p_probs_all[k] - q_probs[k], 0)
            residual /= residual.sum()
```

1. 这段代码在计算残差时有什么错误？
2. 应如何修改？
3. 用本节 `main.py` 的默认 target/draft（vocab=32、seed=0）计算，错误版本的输出分布与 p 的 TV 距离大约是多少？正确版本呢？

**Q10.** 手算。词表只有 3 个 token，`p = [0.6, 0.3, 0.1]`，`q = [0.3, 0.3, 0.4]`，K = 1。

1. 求 α。
2. 求每个 token 被 draft 提出后的接受概率。
3. 求残差分布。
4. 计算第一个输出 token 的分布，验证它等于 p。

**Q11.** 阅读 `verify_distribution` 与 `main` 中的输出：

```python
    p_plain = empirical_dist(plain, vocab)
    p_spec = empirical_dist(spec_first, vocab)
    return total_variation(p_plain, target), total_variation(p_spec, target)
```

```text
  TV(plain_target_sampling, target)       = 0.0169
  TV(speculative_sampling, target)         = 0.0141
  delta TV (spec vs plain)                 = 0.0028
```

模块 docstring 写的是"plain 与 speculative 之间的经验 TV 在 50,000 次抽样下 < 0.01"。

1. 为什么 `TV(plain_target_sampling, target)` 本身就大于 0.01？这说明什么？
2. "delta TV = |TV₁ − TV₂|" 作为"分布无损"的检验有什么缺陷？
3. 这个检验还漏掉了什么？
4. 请设计一个更有说服力的验证。

**Q12.** 讲义练习 2 要求"给定 α、K 画出期望产出并找最优 K"。只用 `expected_tokens` 时最优 K 永远是"越大越好"。

1. 请写一个 `best_k(alpha, c, k_max=15)`，按 `expected_tokens(alpha, K) / (1 + K·c)` 选 K（c 为 draft 单步成本 / target 单步成本）。
2. 分别给出 α ∈ {0.5, 0.7, 0.9}、c = 0.05 时的最优 K 与加速比。

---

## 四、面试高频题

**Q13.**（基础必考）什么是 speculative decoding？它为什么能在"不改变输出分布"的前提下加速？它加速的到底是什么瓶颈？

**Q14.**（原理深挖）请证明精确拒绝规则的输出分布等于 p。贪心解码（temperature = 0）时规则如何简化？

**Q15.**（工程实践）你要在 vLLM 上给 Llama-3.3-70B 的聊天服务开启 speculative decoding。请说明 draft 选型、K、温度门限、batch 与回退策略各怎么定，上线前要验证什么。

**Q16.**（追问型）讲义说"高温度创作时 α 会降到接近 `1/|vocab|`"。你同意吗？温度对 α 的影响应该怎么分析？

**Q17.**（场景设计）对比"独立小 draft 模型"、Medusa heads、EAGLE（树形 + 特征复用）三种方案，并说明 tree attention 验证在工程上要额外处理哪些问题。

---

## 五、参考答案与解析

### Q1 — 答案：D

代码原文 `if rng.random() < min(1.0, ratio)`，其中 `ratio = target[tok] / q_at[k]`。当 `p(x) ≥ q(x)` 时（draft "低估"了这个 token）必定接受；当 `p(x) < q(x)` 时（draft "高估"了）以 `p/q` 的概率接受，把多出来的概率质量削掉。A 只看 p，与 draft 采样概率无关，会导致分布偏移；B 是 draft 采到它的概率而非接受概率；C 是残差的形状，用于拒绝后的重采样。讲义伪代码写成 `r < p/q`，由于 r < 1，与 `min(1, p/q)` 等价。

### Q2 — 答案：A

`(1 − 0.8⁵) / (1 − 0.8) = (1 − 0.32768) / 0.2 = 3.3616`（已用 `expected_tokens(0.8, 4)` 验证）。B 是"恰好接受 K 个"的直觉误判；C 是 K+1 的上限，只有 α = 1 时才达到；D 是随手凑的干扰项。注意这是**每次 target 验证**的产出，不是墙钟加速比，后者还要扣掉 K 次 draft 前向的开销（见 Q12）。

### Q3 — 答案：C

被接受的部分贡献了 `min(p, q)`，缺的正好是 `(p − q)+`，所以拒绝后必须从归一化残差采样才能"补齐"到 p（证明见 Q14）。我们在本节默认分布上用解析方式计算了输出分布：

| 拒绝后的做法 | 输出分布与 p 的 TV |
|------------|------------------|
| 从残差 `(p−q)+` 采样（正确） | ≈ 1.4e-17（即 0） |
| 从 p 重新采样（A） | 0.0405 |
| 完全不验证、直接用 q | 0.1045 |

A 看似"更保险"，但被接受部分已经偏向了 `min(p,q)`，再从 p 采会对 q 高估的 token 重复计数。B、D 显然不是 p。

### Q4 — 答案：B

`α = Σₓ q(x)·min(1, p(x)/q(x)) = Σₓ min(p(x), q(x))`，又因为 `Σ min(p,q) = 1 − ½Σ|p−q|`，所以 `α = 1 − TV(p, q)`。本节默认参数下精确值 0.8955，代码 `measure_alpha` 用 10,000 次抽样测得 0.897，吻合。A 的 KL 不是概率、也不在 [0,1]；C 是两个独立样本恰好相同的概率，与接受规则无关；D 与 draft 无关。

### Q5 — 答案：A

逐层：根 1 + 第 1 层 3 + 第 2 层 3×2 = 6 + 第 3 层 6×2 = 12，合计 22。mask 每行标记"自己 + 所有祖先"，深度为 d 的节点有 d+1 个 1，叶子深度 3 → 4 个 1。运行输出 `attends-per-node (rows): [1, 2, 2, 2, 3, ×6, 4, ×12]` 印证了这一点。B 漏了根和一层；C 把树 mask 当成了全连接；D 是 1+3+... 算错。

### Q6 — 答案：D

speculative decoding 的本质是"用 decode 阶段闲置的算力换步数"。高并发 batch 已经把 FLOPs 填满（讲义："batching already fills the FLOPs"），verifier 一旦 compute-bound，多验证 K 个位置就是实打实的额外计算，吞吐反而下降；配套 skill 也明确"在 verifier 变为 compute-bound 的 batch 规模以上拒绝开启"。A、B、C 都是 α 高、算力闲置的典型受益场景（讲义：聊天 2–3×、代码 3–5×）。

### Q7 — 答案：C

讲义列出 EAGLE-1 的三点改动：输入是 target 在位置 t 的最后隐藏状态（特征复用）、draft 只是 1 层 transformer decoder、输出每层 4–8 个候选、深度 4–6 的树。B 描述的是 Medusa heads；A 与 EAGLE "让 draft 更小" 的思路相反；D 会失去无损保证。

### Q8 — 答案：B

`make_draft` 计算 `draft = alpha_hint * target + (1 - alpha_hint) * uniform`，再乘 0.95–1.05 的随机噪声。由于 `min(p, a·p + (1−a)·u) ≥ a·p + (1−a)·min(p, u)`，求和得 `α ≥ a + (1−a)·Σmin(p,u) > a`。我们实测不同 hint 的真实 α：

| alpha_hint | 0.1 | 0.3 | 0.5 | 0.75 | 0.9 | 1.0 |
|-----------|-----|-----|-----|------|-----|-----|
| 真实 α | 0.621 | 0.704 | 0.786 | 0.890 | 0.953 | 0.988 |

注意 hint = 1.0 时 α 也到不了 1，因为噪声让 q ≠ p。所以命令行参数名 `--alpha`（help 写"target acceptance rate"）具有误导性。A 错：代码有 `min(1.0, ratio)`；C 错：偏差是系统性的；D 是编造的公式。

### Q9 — 参考答案

1. **错误**：`q_probs` 只保存了 draft 在被采中 token 处的**标量概率** `probs[t]`，于是 `p_probs_all[k] - q_probs[k]` 变成"整条 p 向量减去一个常数"，而不是逐点的 `p − q`。残差形状完全不对。（另外片段里每步的 q 分布随 `state` 变化，丢了就无法复原。）
2. **修改**：在 draft 循环里保存**完整分布**，接受判定用标量，残差用向量：

```python
        q_dists.append(probs)                 # 完整 q 分布
        q_probs.append(probs[t])              # 采中 token 的概率
    ...
        if r < min(1.0, p_probs_all[k][tok] / q_probs[k]):
            accepted.append(tok)
        else:
            residual = np.maximum(p_probs_all[k] - q_dists[k], 0)
            residual /= residual.sum()
```

本节 `main.py` 的实现是正确的（`residual = np.maximum(target - draft, 0.0)`），只是因为它的 q 与上下文无关，用一个向量就够了。

3. **量化**（解析计算，已实际运行）：错误版本输出分布与 p 的 TV ≈ **0.0193**；正确版本 ≈ **0**（1.4e-17）。5 万次抽样实测错误版本 TV ≈ 0.021，而 5 万次抽样的噪声底约 0.01，偏差能被检测出来。这正是"无损"保证最容易被实现细节破坏的地方。

### Q10 — 参考答案

1. `α = min(0.6,0.3) + min(0.3,0.3) + min(0.1,0.4) = 0.3 + 0.3 + 0.1 = 0.7`。
2. 接受概率 `min(1, p/q)`：token0 = min(1, 2) = **1**；token1 = **1**；token2 = 0.1/0.4 = **0.25**。
3. `(p − q)+ = [0.3, 0, 0]`，归一化后残差 = `[1, 0, 0]`。
4. 拒绝概率 = 1 − α = 0.3。输出分布 = `min(p,q) + 0.3 × 残差 = [0.3, 0.3, 0.1] + [0.3, 0, 0] = [0.6, 0.3, 0.1]` = p。（已用代码验证。）

直觉：draft 高估了 token2（0.4 vs 0.1），多出的 0.3 概率质量被拒绝；被拒绝的质量全部转移给 draft 低估的 token0，恰好补齐。

### Q11 — 参考答案

1. 有限样本下的经验分布本身就有抽样噪声。vocab = 32、n = 20,000 时，我们重复 5 次直接从 target 采样，经验 TV 在 0.012–0.016 之间；vocab = 64、n = 50,000 时实测 0.0143。也就是说 **"TV < 0.01" 这个阈值连"完美采样器"都过不了**，docstring 与讲义（讲义还写成了 "KL < 0.01"）的阈值不成立，代码实际依赖的是 delta TV。
2. delta TV 的缺陷：两个分布可以各自距离 target 0.015、但方向完全相反，它们之间的距离可达 0.03，而 delta TV 仍为 0。正确的统计量应是两个经验分布之间的 TV，或对 target 做拟合优度检验。我们实测 n = 20,000 时 `TV(empirical_plain, empirical_spec) = 0.0207`——仍是噪声水平，但这个数才是 docstring 所说的量。
3. 只检验了每轮的**第一个** token（`toks[0]`），第 2…K+1 个 token（包括 bonus token）的分布没有检验。在本节 i.i.d. 的玩具设定下它们也等于 p（我们实测全部 token 的 TV ≈ 0.014，同为噪声水平），但真实 LLM 中后续位置的条件分布依赖前缀，更值得检验。
4. 更好的验证：
   - **解析验证**：直接计算 `min(p,q) + (1−α)·residual`，与 p 比较，误差应在 1e-12 以内（我们得到 1.4e-17）。
   - **统计检验**：对 spec 样本做卡方拟合优度检验（`scipy.stats.chisquare`），或者做"错误版本对照"：同样样本量下错误残差（Q9）应被显著拒绝，正确版本不应被拒绝。
   - **对照组**：把 plain 采样也做同样检验，给出噪声基线。

### Q12 — 参考答案

```python
def best_k(alpha, c, k_max=15):
    score = lambda K: expected_tokens(alpha, K) / (1 + K * c)
    K = max(range(1, k_max + 1), key=score)
    return K, score(K)
```

实际运行结果（c = 0.05，即 draft 单步成本是 target 的 5%）：

| α | 最优 K | 加速比 `E/(1+Kc)` | 对照：c = 0.1 |
|---|-------|------------------|--------------|
| 0.5 | 3 | 1.63 | K=2，1.46 |
| 0.7 | 6 | 2.35 | K=4，1.98 |
| 0.9 | 13 | 4.67 | K=10，3.43 |

要点：

- c = 0 时 `E` 随 K 单调增加并趋于上限 `1/(1−α)`（α=0.5 时最多 2 个 token），所以只看 `expected_tokens` 会得出"K 越大越好"的错误结论。
- α 越高，最优 K 越大；draft 越贵（c 越大），最优 K 越小。这也解释了配套 skill 中"chat 默认 K=4、code K=6、高温度创作 K=2"的经验值。
- 真实系统中 α 并非逐位置独立，越靠后的位置接受率往往越低，最优 K 要用标定数据实测。

### Q13 — 参考回答要点

- **定义**：用便宜的 draft 一次猜 K 个 token，再让 target 用**一次** forward 并行打分 K+1 个位置，从左到右按拒绝采样规则接受最长前缀，拒绝处从残差分布补 1 个 token。
- **为什么无损**：接受/拒绝规则构造出的输出分布严格等于 p（Q14），不是近似；讲义："provably equivalent in distribution to sampling from p"。
- **加速的瓶颈**：decode 阶段每步都要读一遍全部权重，是显存带宽瓶颈，算力大量闲置。验证 K+1 个位置与验证 1 个位置读的权重几乎一样多，所以"一次读权重产出多个 token"。
- **收益公式**：`E = (1 − α^{K+1})/(1 − α)`，再扣除 draft 成本。
- 加分点：说明最坏情况（第 1 个就被拒）也至少产出 1 个 token，所以不会比 plain decode 少产出，只是多付了 draft 的成本。
- 常见误区：把 speculative decoding 说成"用小模型的输出近似大模型"——那是蒸馏/替换，会改变分布。

### Q14 — 参考回答要点

- 对某个 token x，输出它有两条路：
  1. draft 采到 x 且被接受：`q(x) · min(1, p(x)/q(x)) = min(p(x), q(x))`；
  2. 任意 token 被拒绝（总概率 `1 − Σ min(p,q) = 1 − α`），然后从残差采到 x：`(1 − α) · (p(x) − q(x))+ / Σ(p − q)+`。
- 关键等式：`Σₓ (p(x) − q(x))+ = 1 − Σₓ min(p(x), q(x)) = 1 − α`，因此第 2 项化简为 `(p(x) − q(x))+`。
- 合计：`min(p, q) + (p − q)+ = p`。证毕。
- 多 token：每个位置在给定前缀下都满足上式，逐位置归纳即可；全接受时 bonus token 直接从 `p(· | x₁..x_K)` 采样，也满足。
- **贪心情形**：temperature = 0 时 p、q 都退化为 one-hot，规则简化为"`argmax p == x_t` 就接受，否则输出 `argmax p` 并停止"（讲义 Greedy case）。此时 α 就是 draft 与 target argmax 一致的比例。
- 加分点：指出残差在 `p == q` 时为全零向量，要防除零（`main.py` 里 `if s == 0.0` 分支），不过此时拒绝概率本来就是 0。

### Q15 — 参考回答要点

（参考本节 `outputs/skill-speculative-tuning.md` 的思路）

- **Draft 选型**：同族小模型（如讲义提到的 `Llama-3.2-1B-Instruct`），**tokenizer 必须逐字节一致**，否则 token 无法对齐；或 EAGLE-3 头。用 target 的输出做 KL 蒸馏可进一步提高 α。
- **标定 α**：在真实分布的数据（skill 建议约 5,000 token）上分任务测 α（聊天、代码分开）。
- **K**：按 `E/(1 + K·c)` 取最大，常见 3–6；skill 示例中 α=0.78 时选 K=4（E≈3.4），K=5 收益不足以覆盖成本。
- **温度门限**：温度高于某阈值（skill 默认 0.8）时关闭；门限判定本身要足够轻量。
- **batch**：verifier 进入 compute-bound 的并发以上关闭，或改用更小的树/链。
- **回退**：滑动窗口统计最近 1,000 次验证的 α，低于 0.4 时对该请求流回退到普通 decode，过一段时间再探测。
- **上线前验证**：在留出集上确认输出分布无漂移（skill："an unvalidated draft is a silent KL drift"）、TPOT/ITL 与吞吐真的改善、显存（draft 权重 + 树验证的 KV 暂存）放得下。
- 配置层面：讲义提到 vLLM 用 `--speculative-config` 传 JSON（`method`、`model`、`num_speculative_tokens`），EAGLE-3 为 `"method": "eagle3"`。

### Q16 — 参考回答要点

- **不完全同意**。在精确规则下 `α = 1 − TV(p_T, q_T)`，p、q 都在同一温度下缩放。T → ∞ 时两者都趋于均匀分布，TV → 0，α 反而 → 1，而不是 `1/|vocab|`。
- 我们在本节玩具分布上把 target、draft 的 logits 同除以 T：T = 0.3 时 α = 0.919，T = 1.0 时 0.895，T = 2.0 时 0.929——并没有"崩溃"。
- 实践中观察到"高温度加速变差"有其他原因：真实 draft 与 target 在长尾 token 上的差异更大，升温把长尾质量放大；采样路径更发散，后续位置更难对齐；与 temperature = 0 的贪心匹配相比，采样接受本身更严格。这些是**经验现象**，幅度要实测，`1/|vocab|` 只有在 draft 与 target 几乎无关时才成立。
- 加分点：讲义练习 5 要求"展示 temperature = 1.5 时 α 崩溃"，在本节玩具设定下做不出来，需要真实 LM 的 p/q 才能复现，这本身是一个好的讨论点。

### Q17 — 参考回答要点

| 方案 | 做法 | 优点 | 缺点 |
|------|------|------|------|
| 独立小 draft | 同族小模型，自回归猜 K 个 | 即插即用、无需改 target | 要额外部署一个模型；K 步串行；α 受限于两个模型的差距 |
| Medusa heads | 在 target 上加 K 个并行预测头 | 部署简单，无第二个模型 | 各头独立预测，彼此不条件化；讲义："slightly lower acceptance than EAGLE" |
| EAGLE | 复用 target 隐藏状态，1 层 decoder 生成候选树 | draft 极小、α 高；EAGLE-3 讲义数据 4.5 tokens/verify | 需要为每个 target 训练专用 draft 头 |

tree attention 验证要额外处理：

- **mask**：每个节点只看自己的祖先（`tree_attention_mask` 的做法），**同时还要看全部前缀（prompt + 已生成）的 KV**——本节代码只构造了树内部的 mask。
- **位置编码**：同一深度的兄弟节点应使用相同的 position id（RoPE 位置 = 前缀长度 + 深度），而不是按展平后的下标。
- **KV cache 回收**：验证后只保留被接受路径的 KV，丢弃其余分支，需要按路径搬运/压缩 KV。
- **成本**：节点数随分支因子指数增长（`(3,2,2)` 已有 22 个节点，即 21 个候选 token），高并发时会挤占算力，所以 skill 建议小 batch 用小树、大 batch 用链。

---

## 六、关联知识点

### 前置知识
- [阶段 10 · 04 预训练 Mini GPT](../../04-pre-training-mini-gpt/docs/zh.md)：自回归生成、temperature 采样、prefill/decode 两阶段。
- [阶段 10 · 12 Inference Optimization](../../12-inference-optimization/docs/zh.md)：为什么 decode 是显存带宽瓶颈，本节的出发点。
- [阶段 07 · 12 KV Cache、Flash Attention 与 Inference 优化](../../../07-transformers-deep-dive/12-kv-cache-flash-attention/docs/zh.md)：验证 forward 如何复用并回收 KV cache。
- [阶段 07 · 16 Speculative Decoding — 草稿、验证、重复](../../../07-transformers-deep-dive/16-speculative-decoding/docs/zh.md)：同一主题的入门版本。
- [阶段 01 · 16 Sampling 方法](../../../01-math-foundations/16-sampling-methods/docs/zh.md)：拒绝采样（rejection sampling）是精确规则的数学基础。
- [阶段 01 · 09 信息论](../../../01-math-foundations/09-information-theory/docs/zh.md)：KL 散度、TV 距离，用于 draft 蒸馏与分布检验。

### 本节被哪些后续内容用到
- [阶段 10 · 15 Speculative Decoding 与 EAGLE-3](../../15-speculative-decoding-eagle3/docs/zh.md)：EAGLE-3 的更多细节。
- [阶段 10 · 18 Multi-Token 预测（MTP）](../../18-multi-token-prediction/docs/zh.md)：MTP 头可直接充当 draft。
- [阶段 17 · 04 服务引擎内部机制](../../../17-infrastructure-and-production/04-vllm-serving-internals/docs/zh.md)：continuous batching 与 speculative decoding 的相互影响。
- [阶段 17 · 05 生产环境中的 EAGLE-3 Speculative Decoding](../../../17-infrastructure-and-production/05-eagle3-speculative-decoding/docs/zh.md)：生产部署与调参。
- [阶段 17 · 08 Inference 指标](../../../17-infrastructure-and-production/08-inference-metrics-goodput/docs/zh.md)：用 TPOT、ITL、goodput 衡量加速是否真实。

### 延伸关键词
`rejection sampling` · `acceptance rate α` · `total variation distance` · `draft distillation` · `Medusa` · `EAGLE-2 dynamic tree` · `EAGLE-3 training-time test` · `tree attention mask` · `lookahead decoding` · `self-speculative decoding` · `TPOT / ITL`
