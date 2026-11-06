# 测验 · Speculative Decoding — 草稿、验证、重复（Speculative Decoding — Draft, Verify, Repeat）

> **阶段 07 · Transformers 深入 · 第 16 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 为什么能加速 | 自回归解码是串行的；让便宜的 draft 模型先写 N 个 token，大模型（verifier）**一次前向**并行验证全部 N 个 |
| 2 | 接受 / 拒绝规则 | 对草稿 token `x`，以 `min(1, q(x)/p(x))` 的概率接受；q 是 verifier 分布，p 是 draft 分布 |
| 3 | 残差分布 | 第一次拒绝时，从 `normalize(max(0, q − p))` 重新采样一个 token，其后的草稿全部丢弃 |
| 4 | 奖励 token（bonus） | N 个草稿全被接受时，再从 verifier 的第 N+1 个位置分布免费采一个 token |
| 5 | 分布等价（Leviathan / Chen 2023） | 输出序列与 verifier 单独采样**同分布**，质量零损失，draft 只影响速度 |
| 6 | 接受率 α | 单 token 接受率 `α = Σ min(p(x), q(x)) = 1 − TV(p, q)`；draft 越像 verifier，α 越高 |
| 7 | 每次验证产出的 token 数 | `E = (1 − α^(N+1)) / (1 − α)`，随 N 增大趋于上限 `1/(1 − α)` |
| 8 | 真实加速比 | 还要扣掉草稿成本：`加速比 ≈ E / (N·c + 1)`，c 为 draft/verifier 单步成本比，因此存在最优 N |
| 9 | 四大家族 | Vanilla（独立小模型）、Medusa（verifier 上加多个预测头 + 树注意力）、EAGLE（读 verifier 隐状态的微型 draft）、Lookahead（Jacobi 迭代，无需 draft） |
| 10 | 工程细节 | KV cache 回滚（先写临时缓冲、接受后再提交）；draft 与 verifier 必须共享 tokenizer；高温采样、短输出、满载 batch 时收益下降 |

### 核心技能（能动手做到）

- [ ] 从零实现单 token 的投机采样（接受/拒绝 + 残差 + 兜底），并用卡方检验对**理论分布 q** 验证等价性（p > 0.05）
- [ ] 推导 `P(输出 = x) = q(x)`，能在白板上讲清楚残差分布为什么必须是 `(q − p)₊`
- [ ] 解析计算接受率 `Σ min(p, q)`，并与蒙特卡洛估计对上
- [ ] 实现 N 个草稿的投机步，统计每轮产出 token 数，并与 `(1 − α^(N+1))/(1 − α)` 对上
- [ ] 加入草稿成本 c，算出给定 α 下的最优 N
- [ ] 按"能否训练 / 能否放下两个模型 / 采样温度 / 负载类型"为一个线上服务选择 vanilla、Medusa、EAGLE 或 Lookahead

---

## 二、基础自测（选择题）

**Q1.** 投机解码能加速的根本原因是：

- A. draft 模型比 verifier 更准确
- B. 解码阶段每步只处理一个 token、主要受显存带宽限制；verifier 一次前向验证 N 个 token 的耗时与生成 1 个 token 相近
- C. 它减少了模型的参数量
- D. 它把 temperature 降到了 0

**Q2.** 草稿 token x 在 draft 模型下概率 `p(x) = 0.4`，在 verifier 下 `q(x) = 0.2`。它被接受的概率是：

- A. 0.2
- B. 0.5
- C. 0.8
- D. 1.0

**Q3.** 词表只有 3 个 token，`q = [0.5, 0.3, 0.2]`，`p = [0.2, 0.5, 0.3]`。发生拒绝后，用来重新采样的残差分布是：

- A. `[1.0, 0.0, 0.0]`
- B. `[0.5, 0.3, 0.2]`
- C. `[0.3, −0.2, −0.1]`
- D. `[0.6, 0.2, 0.2]`

**Q4.** 沿用 Q3 的 q 和 p，单个草稿 token 的期望接受率 α 是：

- A. 0.3
- B. 0.5
- C. 0.7
- D. 1.0

**Q5.** 若 α = 0.8、每轮起草 N = 4 个 token，每次 verifier 调用期望产出多少个 token？

- A. 1.25
- B. 3.36
- C. 4
- D. 5

**Q6.** 关于投机采样输出的分布，正确的是：

- A. 与 draft 模型的分布相同
- B. 接近 verifier 分布，但有与 α 相关的小偏差
- C. 只有 greedy 解码时才与 verifier 一致
- D. 在任何 draft 下都与 verifier 单独采样完全同分布，draft 的好坏只影响速度

**Q7.** Medusa 与 EAGLE 的主要区别是：

- A. Medusa 用一个独立的 1B 小模型，EAGLE 不需要任何额外参数
- B. Medusa 在 verifier 上加多个输出头，分别预测 t+2、t+3…；EAGLE 用一个读取 verifier 最后一层隐状态的微型 Transformer 做草稿
- C. 两者都基于 Jacobi 迭代
- D. EAGLE 不保持 verifier 的输出分布

**Q8.** 下列场景中，投机解码收益最大的是：

- A. 单用户、低延迟的 JSON / 代码生成
- B. temperature = 1.5 的诗歌创作
- C. 每次只生成 1–3 个 token 的分类接口
- D. batch 已经把 GPU 算力打满的离线批量推理

---

## 三、动手 / 代码题

**Q9.** 证明下面的单 token 投机步输出 token x 的概率恰好是 `q(x)`，并说明 `residual` 里 `if s == 0.0: return list(q)` 这个分支什么时候会被触发。

```python
def residual(q, p):
    raw = [max(0.0, qi - pi) for qi, pi in zip(q, p)]
    s = sum(raw)
    if s == 0.0:
        return list(q)
    return [r / s for r in raw]


def spec_step_one_token(q, p, rng):
    """Draft 1 token from p, verify with q. Returns (accepted_token, was_accepted)."""
    d = sample(p, rng)
    p_prob = p[d]
    q_prob = q[d]
    u = rng.random()
    if u < min(1.0, q_prob / p_prob if p_prob > 0 else float("inf")):
        return d, True
    return sample(residual(q, p), rng), False
```

**Q10.** 代码这样判断"分布等价"：

```python
    spec_c, direct_c = run_distribution_check(q, p_good, 50000, rng)
    chi = chi_square(spec_c, direct_c)
    # ...
    print(f"  {'PASS' if chi < 30 else 'FAIL'}: spec-decoded tokens match verifier distribution")
```

实际输出 `chi^2 = 4.64`。请指出这个检验的两个问题，并写出改进版：用理论分布 q 作为期望值，给出卡方统计量和显著性判断（自由度 7、α=0.05 的临界值为 14.07）。

**Q11.** `spec_step_n` 的返回值语义不一致，而且 `main` 里从未调用它：

```python
def spec_step_n(q, p, N, rng):
    accepted = 0
    for _ in range(N):
        d = sample(p, rng)
        p_prob = p[d]
        q_prob = q[d]
        u = rng.random()
        if u < min(1.0, q_prob / p_prob if p_prob > 0 else float("inf")):
            accepted += 1
        else:
            return sample(residual(q, p), rng), accepted
    bonus = sample(q, rng)
    return bonus, accepted + 1
```

(a) 指出不一致之处。(b) 改写成返回"本轮产生的 token 列表"，并用模拟验证平均长度等于 `expected_tokens_per_verify(α, N)`。

**Q12.** `expected_tokens_per_verify` 只数 verifier 调用次数，没有算草稿成本，所以 N 越大越好。请写 `wallclock_speedup(alpha, N, c)`（c 为 draft 与 verifier 单步耗时之比），找出 c = 0.1 时 α = 0.5、0.7、0.85 的最优 N，并用它复算讲义开头"3 ms draft + 30 ms verifier"的例子（取 α = 0.75、N = 5）。

---

## 四、面试高频题

**Q13.**（基础必考）讲一下 speculative decoding 的原理：为什么能加速？为什么说它"无损"？

**Q14.**（原理深挖）请推导拒绝采样 + 残差分布能保持 verifier 分布。如果线上用的是 greedy 解码，验证规则应该怎么改？

**Q15.**（工程实践）你要在 vLLM 上给一个 70B 模型开启投机解码。上线前后要检查和监控什么？KV cache 回滚怎么处理？

**Q16.**（场景设计）一个 70B 聊天服务要降低单请求解码延迟。Vanilla draft、Medusa、EAGLE、Lookahead 四种方案你怎么选？给出决策依据。

**Q17.**（追问型）为什么 batch 变大后投机解码的收益会下降？为什么高 temperature 会让接受率下降？

---

## 五、参考答案与解析

### Q1 — 答案：B

解码时每步只生成一个 token，计算量很小，却要把全部权重从显存读一遍，GPU 算力大量闲置（显存带宽瓶颈）。verifier 对 N 个草稿 token 做一次前向，权重同样只读一遍，耗时与生成 1 个 token 相近，于是"一次大模型前向"可以产出多个 token。A 错：draft 通常比 verifier 差；C、D 与原理无关。

### Q2 — 答案：B

`min(1, q/p) = min(1, 0.2/0.4) = 0.5`。直觉：draft 对这个 token 的偏好是 verifier 的 2 倍，所以只按一半的概率保留它，多出来的那部分概率质量要"退还"给其他 token——这正是残差分布的作用。

### Q3 — 答案：A

`max(0, q − p) = [max(0, 0.3), max(0, −0.2), max(0, −0.1)] = [0.3, 0, 0]`，归一化后 `[1, 0, 0]`。只有 verifier 比 draft 更偏好的 token（这里是 token 0）才会出现在残差里，因为 draft 对它"采样不足"，拒绝时要把欠下的概率补上。C 没有截断负数，不是合法分布。

### Q4 — 答案：C

`α = Σ min(p, q) = min(0.2, 0.5) + min(0.5, 0.3) + min(0.3, 0.2) = 0.2 + 0.3 + 0.2 = 0.7`。等价于 `1 − TV(p, q)`，TV 是总变差距离 `½·Σ|p − q| = ½·(0.3+0.2+0.1) = 0.3`。

### Q5 — 答案：B

`(1 − 0.8⁵) / (1 − 0.8) = (1 − 0.32768) / 0.2 ≈ 3.36`。D（N+1 = 5）是全部接受时的最大值；A 是 `1/α`，没有意义；C 忽略了拒绝后仍然会产出 1 个纠正 token 和全部接受时的奖励 token。

### Q6 — 答案：D

这就是 Leviathan / Chen 定理：无论 draft 多差，"接受 + 残差重采样"组合后的边际分布恰好等于 q（证明见 Q9）。draft 差只会让 α 变低、加速变少，不会让输出变差。C 错：greedy 是特例，采样情形同样成立。

### Q7 — 答案：B

讲义：Medusa 在 verifier 共享主干上加 `head_1…head_k` 预测 `t+2…t+k+1`，用树注意力一次验证多条候选，需要额外微调；EAGLE 的草稿是一个通常只有 1 层的小 Transformer，输入是 verifier 最后一层隐状态，因此和 verifier 的输出相关性更高，讲义称接受率可从约 0.6 提升到 0.85 以上。A 说反了（独立小模型是 vanilla 方案）；C 描述的是 Lookahead；D 错，它们都保持分布。

### Q8 — 答案：A

结构化输出可预测性高，α 高（skill 文件建议此时把 N 推到 7 以上）；单用户低延迟时 GPU 有大量空闲算力可用于并行验证。B：高温采样 α 下降；C：讲义明确说 1–5 个 token 的生成开销占主导；D：batch 已饱和时，verifier 没有空闲算力，额外的验证 token 变成纯负担。

### Q9 — 参考答案

**证明**：设最终输出 token 为 x。

1. 走"接受"分支的概率：先以 `p(x)` 抽到 x，再以 `min(1, q(x)/p(x))` 接受，乘积为 `min(p(x), q(x))`。
2. 走"拒绝"分支的总概率：`P(rej) = 1 − Σ_y min(p(y), q(y))`。由于 `Σq = Σp = 1`，有 `Σ_y max(0, q(y) − p(y)) = 1 − Σ_y min(p(y), q(y))`，所以 `P(rej) = Σ_y (q(y) − p(y))₊`。
3. 拒绝后从残差分布抽到 x 的概率：`(q(x) − p(x))₊ / Σ_y (q(y) − p(y))₊`。乘以 `P(rej)` 恰好得 `(q(x) − p(x))₊`。
4. 合计：`min(p(x), q(x)) + (q(x) − p(x))₊ = q(x)`。（q ≥ p 时为 `p + (q − p)`；q < p 时为 `q + 0`。）∎

**`s == 0` 分支**：`Σ(q − p)₊ = 0` 意味着处处 `q ≤ p`，又因为两者和都为 1，只能是 `q = p`。此时接受率为 1，拒绝分支永远走不到；但浮点误差可能让一个"几乎相等"的分布偶然走到拒绝、而残差全为 0。返回 `q` 是安全的兜底，避免除以 0。

### Q10 — 参考答案

**问题 1：阈值太宽。** 自由度 7、显著性 0.05 的卡方临界值约为 14.07；代码用 30，对应的 p 值约为 1e-4，即使两个分布有明显差异也可能判 PASS。讲义练习 1 要求的就是 p > 0.05。

**问题 2：把一个带噪声的样本当成"期望值"。** `chi_square(spec_c, direct_c)` 用 direct 采样的频数当期望，而 direct 频数本身也有抽样误差，统计量的方差约为单样本检验的两倍，不再服从标准的卡方分布。既然 q 是已知的，就应该直接对理论期望 `n·q` 做拟合优度检验。

```python
q = [0.35, 0.20, 0.15, 0.10, 0.08, 0.06, 0.04, 0.02]
spec = [17515, 10063, 7536, 4931, 3991, 2961, 2018, 985]   # 实际运行得到的 spec 频数
n = sum(spec)
chi = sum((o - n * qi) ** 2 / (n * qi) for o, qi in zip(spec, q))
CRIT_DF7_P05 = 14.07
print(f"chi^2 vs exact q = {chi:.2f}  ->  {'PASS' if chi < CRIT_DF7_P05 else 'FAIL'}")
```

输出：`chi^2 vs exact q = 2.45  ->  PASS`。（用 SciPy 的 `chi2.sf(2.45, 7)` 可算得 p ≈ 0.93；原代码的 4.64 对应 p ≈ 0.70，结论一样是"无显著差异"，但判定方式更严谨了。）

### Q11 — 参考答案

**(a)** 第二个返回值的含义不一致：

- 拒绝分支返回 `accepted`——只数了被接受的草稿，**没数**刚从残差采出来的那个 token；
- 全接受分支返回 `accepted + 1`——**数了**奖励 token。

两条分支本轮实际产出的 token 数都是"被接受的草稿数 + 1"，但返回值一个少数 1、一个没少。此外它只返回最后一个 token，丢掉了被接受的草稿本身；并且对所有位置使用同一组 q、p（不随上下文变化），这是演示用的简化。函数在 `main` 中从未被调用，属于死代码。

**(b)**

```python
from main import sample, residual, perturb, expected_tokens_per_verify
import random

def spec_step_n_fixed(q, p, N, rng):
    """返回本轮产生的 token 列表（已接受的草稿 + 1 个纠正/奖励 token）。"""
    out = []
    for _ in range(N):
        d = sample(p, rng)
        if rng.random() < min(1.0, q[d] / p[d] if p[d] > 0 else float("inf")):
            out.append(d)
        else:
            out.append(sample(residual(q, p), rng))
            return out
    out.append(sample(q, rng))          # bonus token
    return out

q = [0.35, 0.20, 0.15, 0.10, 0.08, 0.06, 0.04, 0.02]
rng = random.Random(7)
p = perturb(q, amount=0.02, rng=rng)
alpha = sum(min(a, b) for a, b in zip(q, p))
rng = random.Random(0)
lens = [len(spec_step_n_fixed(q, p, 5, rng)) for _ in range(20000)]
print(f"alpha={alpha:.3f}  simulated={sum(lens)/len(lens):.3f}  theory={expected_tokens_per_verify(alpha, 5):.3f}")
```

实际输出：`alpha=0.960  simulated=5.424  theory=5.427`。模拟值与公式吻合，说明"每轮产出 = 接受数 + 1"的计数才是正确的。真实实现中 q、p 要按 `prefix + drafts[:i]` 逐位置计算（讲义 Step 3 的 `spec_step` 就是这样写的）。

### Q12 — 参考答案

以"verifier 前向一次的耗时"为 1 个单位：一轮投机解码耗时 ≈ N 次 draft 前向 + 1 次 verifier 前向 = `N·c + 1` 个单位，期望产出 E 个 token；普通解码每个 token 花 1 个单位。所以加速比 = `E / (N·c + 1)`。

```python
from main import expected_tokens_per_verify

def wallclock_speedup(alpha, N, c):
    return expected_tokens_per_verify(alpha, N) / (N * c + 1)

for a in (0.5, 0.7, 0.85):
    row = [wallclock_speedup(a, N, 0.1) for N in range(1, 11)]
    best = max(range(1, 11), key=lambda N: wallclock_speedup(a, N, 0.1))
    print(a, best, " ".join(f"{s:.2f}" for s in row))

print(wallclock_speedup(0.75, 5, 3 / 30))
```

输出：

```text
0.5 2 1.36 1.46 1.44 1.38 1.31 1.24 1.17 1.11 1.05 1.00
0.7 4 1.55 1.82 1.95 1.98 1.96 1.91 1.85 1.78 1.70 1.63
0.85 7 1.68 2.14 2.45 2.65 2.77 2.83 2.85 2.85 2.82 2.78
2.1920572916666665
```

- 最优 N 随 α 增大而增大：α=0.5 时 N=2，α=0.7 时 N=4，α=0.85 时 N=7（与 N=8 几乎持平）。这与 skill 文件的调参规则一致（α < 0.6 降到 3，α > 0.9 推到 7）。
- 讲义例子：一轮 `5×3 + 30 = 45 ms`，期望产出 `(1 − 0.75⁶)/0.25 ≈ 3.29` 个 token，而普通解码 45 ms 只能产出 1.5 个，加速约 **2.2 倍**。讲义写"最多 5 个"——其实全部接受时还有奖励 token，最多是 6 个；用期望值算更接近现实。

### Q13 — 参考回答要点

- **原理**：小模型串行起草 N 个 token；大模型一次前向对 `前缀 + N 个草稿` 计算所有位置的分布；从左到右以 `min(1, q/p)` 接受，第一次拒绝时从 `(q − p)₊` 归一化分布里重采样并丢弃后续草稿；全部接受再送一个奖励 token。
- **为什么快**：解码受显存带宽限制，大模型一次前向验证多个 token 的成本与生成一个 token 接近；每次大模型调用期望产出 `(1 − α^(N+1))/(1 − α)` 个 token。
- **为什么无损**：拒绝采样 + 残差分布保证输出边际分布严格等于大模型分布（Q9 的证明），不是近似。
- **取舍**：要多占显存放 draft 模型（或训练额外的头）；KV cache 需要回滚；α 低时反而变慢。
- **加分点**：给出 `α = Σ min(p, q)`；说明真实加速要扣掉草稿成本，最优 N 存在；提到 EAGLE、Medusa 等不需要独立小模型的变体。
- **常见误区**：以为"大模型只是检查草稿对不对、错了就换"，忽略了采样场景下必须按概率接受和用残差重采样，否则分布会偏。

### Q14 — 参考回答要点

- **推导**：同 Q9。关键一步是 `Σ(q − p)₊ = 1 − Σ min(p, q) = P(拒绝)`，于是"拒绝后从残差抽到 x"的概率正好是 `(q(x) − p(x))₊`，与"接受 x"的 `min(p(x), q(x))` 相加得 `q(x)`。多 token 情形：每个位置都满足这个性质，且一旦拒绝就丢弃后续草稿，归纳可得整条序列与 verifier 逐步采样同分布。
- **greedy 版本**：verifier 分布退化为在 argmax 上的 one-hot。规则变成：草稿 token 等于 verifier 在该位置的 argmax 就接受，否则用 verifier 的 argmax 替换并丢弃后续草稿。全部匹配时奖励 token 是 verifier 第 N+1 个位置的 argmax。输出与大模型自己 greedy 解码逐 token 相同。
- **加分点**：讲义提到 greedy draft 对 greedy verifier 的 α 很高；温度采样时要让 draft 的温度与 verifier 一致（skill 文件），否则 α 会下降。
- **常见误区**：残差写成 `q` 本身（从 q 重采样）——这会让被 draft 高估的 token 被多采，分布偏离。

### Q15 — 参考回答要点

- **上线前检查**（来自 skill 文件）：draft 与 verifier 共享 tokenizer（否则 token 无法逐个对应，保证失效）；运行时支持所选方法（EAGLE 需要访问 verifier 隐状态，建议用 vLLM / SGLang）；KV cache 回滚支持。
- **配置**：讲义示例 `vllm serve ... --speculative-config '{"method": "eagle", ..., "num_speculative_tokens": 5}'`；N 从 5 开始，按实测 α 调（α > 0.9 加到 7，α < 0.6 降到 3）。
- **KV cache 回滚**：验证时会把 N 个草稿写进 verifier 的 KV cache；若在第 j 个位置被拒，要把缓存截回"前缀 + 已接受的 j−1 个草稿 + 纠正 token"。生产实现用临时缓冲区"先写、接受后提交"。讲义练习 4 就是模拟这个过程。
- **监控**：按任务类型分桶的接受率 α、每次 verifier 调用产出 token 数、TPOT（每 token 延迟）、整体吞吐、显存占用；与关闭投机解码的对照组做 A/B。
- **常见误区**：只看单请求延迟，不看高并发下的吞吐；没按任务分桶，平均 α 掩盖了某些场景下的负收益。

### Q16 — 参考回答要点

| 方案 | 何时选 | 讲义给出的典型加速 |
|------|--------|------------------|
| Vanilla draft（同家族 1B/3B） | 快速验证、不能训练 | 1.8–2.3× |
| Medusa 头 | 能微调 verifier、放不下第二个模型 | 2–3× |
| EAGLE-2/3 | 生产环境追求极致速度、能训练草稿头 | 3–4× |
| Lookahead | 不能训练、没有可用 draft、不想加参数 | 1.3–1.6× |

- **决策顺序**：先确认有没有同 tokenizer 的小模型和显存余量 → 有训练资源就上 EAGLE → 显存紧张就 Medusa → 什么都没有就 Lookahead。
- **再看负载**：代码/JSON 类 α 高、可加大 N；创意写作、高温采样收益小，可降低 N 或关闭。
- **加分点**：讲义称 draft 模型通常比 verifier 便宜 10–50 倍；skill 文件指出 Medusa 的主要成本往往在于收集 verifier 自身输出做微调数据。

### Q17 — 参考回答要点

- **batch 变大**：投机解码的本质是"用闲置算力换延迟"。batch 小时，解码受带宽限制，验证 N 个 token 几乎免费；batch 大时，GPU 的算力已经被大量请求占满，每个请求多出的 N 个验证位置都要真实消耗算力，被拒绝的草稿就成了纯浪费。所以 skill 文件说"批量服务时连续批处理更重要，投机收益随 batch 增大而递减"。
- **高 temperature**：温度越高，q 和 p 都越平坦，两个模型在长尾 token 上的随机差异越大，`Σ min(p, q)` 下降；同时草稿是从 p 中随机采样，抽到 q 认为不太可能的 token 的机会变多。greedy / 低温时两个模型更容易在 argmax 上达成一致。
- **加分点**：给出量化工具——α 低时最优 N 变小（Q12），α 低到一定程度时加速比 < 1，应该直接关掉。

---

## 六、关联知识点

### 前置知识
- [阶段 07 · 07 GPT — 因果语言建模](../../07-gpt-causal-language-modeling/docs/zh.md)：自回归解码、temperature 与采样。
- [阶段 07 · 12 KV Cache、Flash Attention 与 Inference 优化](../../12-kv-cache-flash-attention/docs/zh.md)：解码为什么受显存带宽限制、KV cache 的结构。
- [阶段 01 · 16 采样方法](../../../01-math-foundations/16-sampling-methods/docs/zh.md)：拒绝采样的数学基础。
- [阶段 01 · 09 信息论](../../../01-math-foundations/09-information-theory/docs/zh.md)：KL 散度（代码用它衡量 draft 与 verifier 的差距）。

### 本节被哪些后续内容用到
- [阶段 07 · 14 从零构建 Transformer](../../14-build-a-transformer-capstone/docs/zh.md)：讲义练习 3 在这个模型上实现迷你 Medusa。
- [阶段 10 · 15 EAGLE-3 投机解码](../../../10-llms-from-scratch/15-speculative-decoding-eagle3/docs/zh.md)：EAGLE 系列的完整实现。
- [阶段 10 · 25 投机解码](../../../10-llms-from-scratch/25-speculative-decoding/docs/zh.md)：在 LLM 训练/推理流水线中的再次深入。
- [阶段 10 · 18 多 token 预测](../../../10-llms-from-scratch/18-multi-token-prediction/docs/zh.md)：MTP 头既是训练目标，也能当投机解码的草稿来源。
- [阶段 17 · 05 EAGLE-3 投机解码（生产）](../../../17-infrastructure-and-production/05-eagle3-speculative-decoding/docs/zh.md)：服务端部署与调参。
- [阶段 17 · 04 vLLM 服务内部机制](../../../17-infrastructure-and-production/04-vllm-serving-internals/docs/zh.md)：投机解码与连续批处理、分页 KV cache 的交互。
- [阶段 17 · 08 推理指标与 goodput](../../../17-infrastructure-and-production/08-inference-metrics-goodput/docs/zh.md)：TPOT、吞吐等上线监控指标。
- [阶段 19 · 14 投机解码服务器](../../../19-capstone-projects/14-speculative-decoding-server/docs/zh.md)：综合项目。

### 延伸关键词
`speculative sampling` · `rejection sampling` · `total variation distance` · `Medusa / tree attention` · `EAGLE-2 dynamic draft tree` · `lookahead decoding / Jacobi` · `self-speculative decoding` · `KV cache rollback` · `num_speculative_tokens` · `TPOT`
