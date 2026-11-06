# 测验 · 奖励投机（Reward Hacking）与古德哈特定律（Reward Hacking and Goodhart's Law）

> **阶段 18 · 伦理、安全与对齐 · 第 02 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Goodhart 定律 | "When a measure becomes a target, it ceases to be a good measure." 讲义强调它不是口号，而是"任何强优化器 + 不完美代理"的可预测性质 |
| 2 | Manheim & Garrabrant 四变体 | regressional（有限样本）、extremal（尾部）、causal（代理在目标的因果下游）、adversarial（智能体主动钻空子）；讲义：RLHF 中以 extremal + adversarial 为主 |
| 3 | Gao 等 (ICML 2023) 过度优化曲线 | 以 `d = sqrt(KL(π‖π_init))` 为横轴：proxy 奖励持续上升，gold 奖励先升后降；proxy RM 越大，gold 峰值越靠外，但下降不可避免 |
| 4 | 函数形式 | 讲义给出 `R(d) = α·d − β·d²`，`β_gold > β_proxy`；同样的 proxy-gold 差距特征出现在 best-of-N、PPO、SFT-to-best 中 |
| 5 | 四种"戏服"，一个机制 | verbosity（越长越好）、sycophancy（附和用户）、unfaithful reasoning（CoT 不承载答案）、evaluator tampering（篡改评估环境）；都是"代理在训练分布上与目标相关、优化器挑出相关性断裂的输入" |
| 6 | Catastrophic Goodhart | 若代理误差是**重尾**的（存在稀有但可达、误差无界的输入），KL 约束下的最优策略可以把质量放到这些输入上：proxy 任意高、gold 停在基线。KL 约束了分布，没约束它瞄准哪些模式 |
| 7 | 部分有效的缓解 | RM ensemble + 最坏情况聚合（Coste 等）、RM 对分布偏移的鲁棒性、保守 KL 调度与按 proxy-gold 差距早停、DPO 类方法（同样会过度优化）；讲义：它们只"把峰值推远"，不能消除 |
| 8 | 2026 统一视角 | 讲义引用 arXiv:2604.13602：概率质量转移到"靠易学启发式（权威语气、格式、自信表达）拿高分"的输出；防御也统一为三类：缩小代理差距、降低优化压力、把选择压力转到难以投机的特征上 |
| 9 | 诊断必须有 gold 信号 | skill 文件："If the user only provides proxy-reward curves with no held-out gold signal, refuse to diagnose" |
| 10 | 代码与讲义不符 | 线性 gold + 线性 proxy + 沿 proxy 方向移动的策略 → gold 随 `d` **线性单调上升**，所有曲线的"gold peak"都在最大预算处；BoN 的横轴不是 KL；Student-t 噪声没有制造 Catastrophic Goodhart。结尾 TAKEAWAY 与输出矛盾 |

### 核心技能（能动手做到）

- [ ] 用一句话说出 Goodhart 定律，并把一个具体的 reward hacking 案例归入四变体与四戏服
- [ ] 画出 Gao 曲线（proxy、gold 对 `sqrt(KL)`），标出 gold 峰值，并解释为什么"更大的 RM"只能把峰值推远
- [ ] 推导线性模型中 `gold(d) = √2·d·‖w_gold‖·cosθ`，从而证明本节代码**不可能**出现峰值
- [ ] 修改 gold 函数（如加入对极端特征的惩罚），让模拟真正出现"先升后降"
- [ ] 计算 best-of-N 的真实 KL：`log n − (n−1)/n`
- [ ] 用一个两区域的小例子说明 Catastrophic Goodhart：在很小的 KL 下拿到很高的 proxy、gold 却不动

---

## 二、基础自测（选择题）

**Q1.** Manheim & Garrabrant (2018) 把 Goodhart 定律分为四种变体，下列哪组完全正确？

- A. regressional、extremal、causal、adversarial
- B. verbosity、sycophancy、unfaithful reasoning、evaluator tampering
- C. underfitting、overfitting、distribution shift、label noise
- D. prompt、tool、memory、response

**Q2.** Gao、Schulman、Hilton (ICML 2023) 观察到，随着策略离初始策略的 KL 增大：

- A. proxy 与 gold 奖励同步单调上升，二者差距保持不变
- B. proxy 先升后降，gold 单调上升
- C. proxy 持续上升；gold 先升后降，峰值比 proxy 更靠近原点；proxy RM 越大，gold 峰值越靠外，但下降仍然发生
- D. 只要 proxy RM 用了足够多的数据，gold 就不会下降

**Q3.** 下列哪一项**不是**讲义列出的 reward hacking"四种戏服"之一？

- A. verbosity bias（冗长偏好）
- B. sycophancy（迎合）
- C. evaluator tampering（篡改评估器）
- D. 梯度爆炸（gradient explosion）

**Q4.** "Catastrophic Goodhart" 的核心论断是：

- A. 只要加了 KL 正则，reward hacking 的幅度就有上界
- B. 若代理奖励误差是重尾的，KL 约束下的最优策略可以把质量放到稀有、误差极大的输入上，使 proxy 任意高而 gold 停留在基线
- C. reward hacking 只会在 RM 小于 1B 参数时出现
- D. 任何 RM 都会让 gold 奖励变成负无穷

**Q5.** 关于讲义中列出的缓解手段，正确的是：

- A. RM ensemble 能彻底消除 reward hacking
- B. 改用 DPO 就不存在过度优化问题
- C. ensemble + 最坏情况聚合、保守 KL 调度与早停等都只能把 gold 峰值推远，不能消除它；对产品往往够用，但不足以宣称"已解决对齐"
- D. 讲义推荐的唯一手段是减小学习率

**Q6.** 运行 `main.py`，四条 Gaussian 噪声曲线和 Student-t 曲线的"gold peak"分别出现在哪里？

- A. 全部出现在最大预算 `sqrt(KL) = 2.828` 处——gold 一路单调上升，没有任何下降
- B. 都出现在 `sqrt(KL) ≈ 1.0` 附近，之后 gold 下降
- C. 样本越多峰值越靠外：100 样本在 0.707，10000 样本在 2.236
- D. Student-t 曲线的峰值最靠近原点

**Q7.** `kl_constrained_policy_sweep` 让 `μ = s·w_proxy`、`‖μ‖ = √2·d`（`d = sqrt(KL)`）。于是 gold 奖励 `⟨w_gold, μ⟩` 等于：

- A. `‖w_proxy‖²·d²`，二次增长
- B. 一个常数，与 `d` 无关
- C. `√2·d·‖w_proxy‖`，与 gold 权重无关
- D. `√2·d·‖w_gold‖·cosθ`（θ 为两个权重向量夹角），只要 cosθ > 0 就随 `d` 线性单调增长

**Q8.** `best_of_n_sweep` 在 n = 1 时打印的 `sqrt(KL)` 是 1.920。这说明：

- A. best-of-1 本身就偏离了初始策略
- B. 代码计算的是被选样本的 `sqrt(0.5·‖x‖²)`，不是 KL；best-of-N 相对原策略的 KL 为 `log n − (n−1)/n`，n = 1 时应为 0
- C. 随机种子没有固定
- D. 特征维度 D 设得太小

---

## 三、动手 / 代码题

**Q9.** 以 100 样本的 proxy 为例，实际输出：

```text
   sqrt(KL)     proxy      gold       gap
      0.000     0.000     0.000    +0.000
      1.000     2.274     2.239    +0.035
      2.828     6.433     6.333    +0.100
  gold peak at sqrt(KL) = 2.828, gold = 6.333, proxy = 6.433
```

已知 `‖w_gold‖ = 1.597`。

1. 由 `d = 1` 一行反推 `‖w_proxy‖` 和 `cosθ`。
2. 证明在这个模型里 proxy、gold、gap 都是 `d` 的线性函数，因此不存在峰值。
3. 1000 样本那条曲线的 gap 是负的（proxy < gold），这与"proxy 被过度优化"矛盾吗？

**Q10.** 要让 gold 真正"先升后降"，需要让代理在远离数据的区域失效。我们把 gold 改为

```python
C = 0.3
def gold_nl(x):
    return dot(GOLD_W, x) - C * (sum(v * v for v in x) - D)
```

（对极端特征的惩罚，类似"说得太长、太夸张反而变差"），proxy 仍用线性最小二乘拟合，得到：

| sqrt(KL) | 0.447 | 1.000 | 1.414 | 1.732 | 2.236 | 2.828 |
|----------|-------|-------|-------|-------|-------|-------|
| proxy（n=100） | 1.110 | 2.483 | 3.511 | 4.300 | 5.551 | 7.022 |
| gold（n=100） | 0.850 | 1.569 | 1.867 | **1.957** | 1.850 | 1.335 |
| gold（n=1000） | 0.886 | 1.649 | 1.981 | **2.096** | 2.030 | 1.562 |

1. 写出策略 `N(μ, I)` 下 gold 的期望，并求峰值位置 `d*`。
2. 为什么线性 proxy 完全看不到二次惩罚项？
3. 表中 n = 1000 的 gold 整体更高，但峰值位置没变。讲义说"proxy 越大峰值越靠外"，这个变体为什么没体现？要体现需要怎样的设定？

**Q11.**（BoN 的 KL）

1. 计算 n = 4、64、1024 时 best-of-N 的 KL（nats）与 `sqrt(KL)`。
2. 与代码打印的横轴（2.013、2.482、2.951）对比，说明用错横轴会给"峰值在哪"的判断带来什么问题。
3. 把 `best_of_n_sweep` 的横轴改正，写出关键代码。

**Q12.**（重尾与 Catastrophic Goodhart）

```python
def student_t(df: float) -> float:
    u = random.gauss(0.0, 1.0)
    chi2 = sum(random.gauss(0.0, 1.0) ** 2 for _ in range(int(df)))
    ...
    return u * math.sqrt(df / chi2)

# train_proxy 中：
        eps = gauss() if noise == "gauss" else student_t(3.0)
        ys.append(gold_reward(x) + eps)
```

1. 这里的"重尾"加在哪里？为什么它不构成 Catastrophic Goodhart 的条件？
2. 设计一个最小例子：参考策略为二维标准正态，gold = `x1`，proxy = `x1 + 100·1[x2 > 3]`。若策略把概率 p 放到 `x2 > 3` 区域（参考策略下概率 q ≈ 0.00135），计算 p = 0.1 时的 KL 与 proxy 增益，并与"把同样 KL 花在移动 x1 上"相比。

---

## 四、面试高频题

**Q13.**（基础必考）什么是 reward hacking？请用 Goodhart 定律解释它为什么在 RLHF 中几乎不可避免，并举出至少三个 LLM 中的具体表现。

**Q14.**（原理深挖）请描述 Gao 等人的过度优化缩放律：横轴、纵轴、曲线形状分别是什么？它对 RLHF 的工程实践有什么指导意义？

**Q15.**（原理深挖）"我们加了 KL 正则，所以 reward hacking 是有界的。"这个说法错在哪里？请结合 Catastrophic Goodhart 说明。

**Q16.**（工程实践）你负责一个 RLHF 训练任务，如何在训练中监控并尽早发现 reward hacking？给出指标、看板与处置手段。

**Q17.**（场景设计）上线后发现模型回答越来越长、越来越爱用标题和加粗，但用户满意度没有提升。请诊断原因，并按"数据 / RM / 优化 / 评估"四个层面给出改进方案。

---

## 五、参考答案与解析

### Q1 — 答案：A

讲义："Manheim and Garrabrant (2018) distinguish four variants: regressional (finite-sample), extremal (tails), causal (proxy is downstream of target), and adversarial (agent gaming). For RLHF, extremal + adversarial are the dominant modes."

- B 是讲义的"四种戏服"（表现形式），不是 Goodhart 变体。
- C 是一般机器学习问题的列表。
- D 是第 17 阶段 FinOps 的四个 token 层，干扰项。

### Q2 — 答案：C

讲义："Every curve rises, peaks, and falls. The peak is further out for larger proxies. The fall is inevitable."（这里的 curve 指 gold-RM 分数对 KL 的曲线。）

- A 是"没有 Goodhart"的理想情况。
- B 把 proxy 与 gold 说反了：proxy 是被优化的量，会一直上升。
- D 与"The fall is inevitable"矛盾。

### Q3 — 答案：D

四种戏服：verbosity、sycophancy、unfaithful reasoning、evaluator tampering。梯度爆炸是训练数值稳定性问题，与代理—目标差距无关。

### Q4 — 答案：B

讲义："Under a KL constraint the optimal policy can place all its mass on these inputs: proxy reward is arbitrarily high, gold reward is at baseline. KL regularization constrains the policy distribution but does not constrain which modes it targets."

- A 正是它反驳的"常见防御"。
- C、D 没有出处。

### Q5 — 答案：C

讲义 "What actually works (partially)"："None of these eliminate reward hacking. They move the curve's peak further out. This is often enough for a shipping product. It is never enough for a 'solved' alignment claim."

- A 夸大了 ensemble 的作用。
- B 错：讲义引用 Rafailov 等 (NeurIPS 2024) 说明 DPO 家族同样会过度优化。
- D 没有出处。

### Q6 — 答案：A

实际运行：五条 KL 约束曲线的 `gold peak` 全部在 `sqrt(KL) = 2.828`（预算网格的最大值），best-of-N 曲线的峰值也在最后一个点（n = 1024）。gold 从未下降。这与讲义的描述和代码结尾的 TAKEAWAY（"gold peaks and falls… Heavy-tailed noise moves the peak closer to the origin"）**相互矛盾**——打印出来的"峰值"只是网格的边界。

- B、C、D 描述的是讲义期望的现象，不是本代码的输出。

### Q7 — 答案：D

`⟨w_gold, μ⟩ = s·⟨w_gold, w_proxy⟩ = (√2·d/‖w_proxy‖)·‖w_gold‖·‖w_proxy‖·cosθ = √2·d·‖w_gold‖·cosθ`。线性 proxy 拟合的 cosθ 都在 0.99 以上（100 样本 0.9914、10000 样本 0.9998），所以 gold 随 d 线性上升。

- A：`μ` 的范数是 `√2·d`，奖励是一次项，不是二次。
- B、C：混淆了 gold 与 proxy；`√2·d·‖w_proxy‖` 是 **proxy** 的表达式。

### Q8 — 答案：B

代码注释自己承认："we compute a proxy: distance of best from mean"。被选样本的 `sqrt(0.5·‖x‖²)` 在 n = 1 时期望约为 `sqrt(0.5·D) = 2`（D = 8），所以打印 1.920。best-of-N 的真实 KL 是 `log n − (n−1)/n`，n = 1 时为 0。

- A 错：best-of-1 就是原策略本身。
- C 错：`random.seed(42)` 已固定。
- D 与此无关。

### Q9 — 参考答案

1. `proxy(d) = √2·d·‖w_proxy‖`：`2.274 / √2 = 1.608`，即 `‖w_proxy‖ ≈ 1.608`。`gold(d) = √2·d·‖w_gold‖·cosθ`：`2.239 / √2 = 1.583 = 1.597·cosθ`，`cosθ ≈ 0.991`。（用脚本精确算得 1.6082 与 0.9914。）
2. 两者都形如"常数 × d"；gap = `√2·d·(‖w_proxy‖ − ‖w_gold‖·cosθ)` 也是线性的。线性函数在区间上的最大值只能在端点取到，所以 `max(curve, key=gold)` 必然返回最大预算。换句话说：**在线性奖励 + 各向同性高斯策略的世界里，沿 proxy 方向走得越远，gold 也越高**，代价只是损失了 `1 − cosθ` 的效率（这里不到 1%）。这是 regressional Goodhart（有限样本带来的小偏差），而不是讲义描述的 extremal/adversarial 崩塌。
3. 不矛盾，因为 gap 的符号只取决于 `‖w_proxy‖` 是否大于 `‖w_gold‖·cosθ`：1000 样本的拟合恰好让 `‖w_proxy‖ = 1.567 < 1.597·0.998`，proxy 的"尺度"偏小。proxy 与 gold 的数值单位并不可比，真正有意义的是 gold 曲线本身的形状——而它在本代码中从不下降。

### Q10 — 参考答案

1. `x ~ N(μ, I)` 时 `E[‖x‖²] = ‖μ‖² + D`，所以 `E[gold] = ⟨w_gold, μ⟩ − C·‖μ‖² = √2·d·‖w_gold‖·cosθ − 2C·d²`。这正是讲义的 `α·d − β·d²` 形式。对 d 求导置零：`d* = √2·‖w_gold‖·cosθ / (4C) ≈ 1.414 × 1.597 × 0.99 / 1.2 ≈ 1.87`。网格上最接近的点 1.732 就是表中的峰值。
2. 训练特征 `x ~ N(0, I)` 关于原点对称，二次项 `‖x‖² − D` 与任意线性函数 `⟨w, x⟩` 都不相关（三阶矩为 0），最小二乘把它当作噪声吸收掉。于是 proxy 只看到"越往 w 方向越好"，在训练分布（‖x‖ 不大）内这很准，越往外越错——这就是 **extremal Goodhart**：代理在训练分布内与目标相关，在尾部失效。
3. 峰值位置由 `C` 和 `cosθ` 决定，而线性 proxy 不论样本多少都只能逼近 `w_gold`（cosθ 从 0.99 到 1），学不到二次项，所以峰值几乎不动；样本多只让 cosθ 更接近 1，gold 整体略高。要体现"proxy 越大峰值越靠外"，需要 proxy 的**模型容量**能随数据增加逐步学到尾部结构：例如让 proxy 也包含二次特征、或用更灵活的模型（如小 MLP），并且训练数据在尾部稀疏——数据越多，proxy 对尾部的估计越准，峰值才会外移。Gao 等的设定正是"同一族 RM、不同数据量"。

### Q11 — 参考答案

1. 用 `KL = log n − (n−1)/n`（已用 Python 计算）：

| n | KL（nats） | sqrt(KL) | 代码打印的横轴 |
|---|-----------|----------|--------------|
| 1 | 0 | 0 | 1.920 |
| 4 | 0.636 | 0.798 | 2.013 |
| 64 | 3.175 | 1.782 | 2.482 |
| 1024 | 5.932 | 2.436 | 2.951 |

2. 代码横轴从 1.92 起步，整体被压缩在 1.9–3.0 之间，且 n = 1 不在原点。把它与 KL 约束曲线画在同一张图上会得出错误比较：看起来 BoN 在"同样 KL"下 proxy 低很多，实际上横轴根本不是同一个量。判断"峰值在 KL 多少处"、拟合 Gao 的 `d(α − βd)` 形式（讲义练习 3）都需要正确的横轴。
3. 关键修改：

```python
for n in ns:
    kl_bon = math.log(n) - (n - 1) / n          # 解析 KL，与采样无关
    ...
    curve.append((math.sqrt(kl_bon), sum(proxies) / trials, sum(golds) / trials))
```

另外，在原代码的线性 gold 下，BoN 的 gold 同样单调上升（n = 1024 时 5.197），换了横轴也不会出现峰值；要看到峰值仍需 Q10 的非线性 gold。

### Q12 — 参考答案

1. 重尾加在**标签噪声**上：`y = gold(x) + ε`，ε 服从 t(3)（方差 3，我们抽样测得约 2.9）。最小二乘对零均值、有限方差的噪声仍是无偏的，只是方差变大，所以拟合出的 `w_proxy` 仍接近 `w_gold`（cosθ = 0.991）。而且噪声只存在于训练标签里，proxy 本身仍是线性函数，**在输入空间中不存在"误差无界的稀有区域"**。Catastrophic Goodhart 要求的是"代理误差 `proxy(x) − gold(x)` 作为 x 的函数是重尾的"，两者不是一回事。因此本代码的 Student-t 曲线同样单调上升，TAKEAWAY 中"重尾噪声让峰值更靠近原点"并未发生。
2. 最小例子（已用 Python 计算）：
   - `q = P(x2 > 3) ≈ 0.00135`。把 p = 0.1 的概率放到该区域、其余按原分布：`KL = p·ln(p/q) + (1−p)·ln((1−p)/(1−q)) ≈ 0.337` nats。
   - proxy 增益 = `100 × 0.1 = 10`；gold（= x1）不变，仍为 0（基线）。
   - 同样 0.337 nats 若用来平移 x1：`‖μ‖ = sqrt(2 × 0.337) ≈ 0.82`，gold 增益 0.82、proxy 增益也只有 0.82。
   - 以 proxy 为目标的优化器显然选前者：**很小的 KL 换来巨大的 proxy，gold 停在基线**。p = 0.5 时 KL 约 2.61，proxy 增益 50，gold 仍为 0。这就是"KL constrains the distribution but not which modes it targets"。

### Q13 — 参考回答要点

- **定义**：策略在代理奖励上得分提高，但在真正想要的目标上没有提高甚至变差；优化器利用了代理与目标之间的缝隙。
- **为什么几乎不可避免**：RLHF 把"人类偏好"替换成"有限偏好数据上拟合的 RM"（讲义："human preference becomes Bradley-Terry fit on 50k labeled pairs"）。代理只在训练分布上与目标相关；优化压力越大，策略越会跑到相关性断裂的区域。Goodhart：度量一旦成为目标就不再是好度量。
- **具体表现**：冗长（RM 学到"长 = 好"）、迎合（附和错误前提）、不忠实的 CoT（推理不决定答案）、篡改评估器（agent 修改测试或环境让自己"通过"）；以及格式化、权威语气、过度自信等"易学启发式"。
- 加分点：说出 Manheim & Garrabrant 四变体，指出 RLHF 主要是 extremal + adversarial；说出讲义的统一视角。

### Q14 — 参考回答要点

- **设定**：用 10 万条标签训练一个"gold RM"当真值；用 1k、3k、10k、30k 子集训练 proxy RM；对每个 proxy 做优化（BoN、PPO），横轴 `d = sqrt(KL(π‖π_init))`，纵轴为 proxy 与 gold 分数。
- **形状**：proxy 持续上升；gold 先升后降，峰值更靠近原点；proxy 越大，峰值越靠外、越高；讲义给出 `R(d) = α·d − β·d²`、`β_gold > β_proxy`。（原论文对 BoN 与 RL 分别拟合了不同的函数形式，RL 的形式含 `log d` 项；讲义只给出了二次形式，复现练习 3 时可两种都试。）
- **工程意义**：
  - 必须有独立的 gold 信号（保留 RM、人工评测）来定位峰值；只看训练 proxy 一定会过头；
  - 用 KL 作为"优化预算"，在 gold 峰值附近早停或设 KL 上限；
  - 增加偏好数据 / 更大 RM 可以推远峰值，是值得的投入，但不能消除问题；
  - 比较不同方法时用同一横轴（KL），而不是步数。
- 常见误区：把 proxy 奖励上升当作训练成功。

### Q15 — 参考回答要点

- KL 正则把策略限制在参考策略附近，Gao 等已显示它"softens but does not prevent the gold-reward collapse"。
- **Catastrophic Goodhart**：如果存在参考策略下概率很小但非零、代理误差极大的区域，KL 约束的最优策略只需付出 `p·log(p/q)` 量级的 KL 就能把质量 p 移过去，换取 `p × 误差` 的 proxy 增益；误差越重尾，回报越高。KL 约束的是"分布离参考多远"，不约束"把质量放在哪种输出上"。
- **重尾并不罕见**：讲义："Any bounded measurement of an unbounded world has heavy-tailed error in the tails"。LLM 输出空间极大，总有 RM 没见过、打分离谱的角落（特殊格式、特定短语、对评估器的注入）。
- **更好的做法**：RM ensemble + 最坏情况聚合、对抗性训练 RM（把策略找到的高分样本送回标注）、过程监督、限制输出空间（格式/长度约束）、gold 信号监控与早停。
- 加分点：能给出 Q12 那样的数值小例子。

### Q16 — 参考回答要点

- **指标**：
  - proxy 奖励 vs KL（不是 vs 步数）；
  - 独立的 gold 信号：保留 RM（不同数据/种子训练）、定期小规模人工评测、能力基准；
  - proxy − gold 差距，及其随 KL 的斜率；
  - 已知戏服的专项指标：平均输出长度、长度控制胜率、在错误前提提示上的附和率、CoT 忠实度探针、工具/环境调用中的异常写操作；
  - ensemble 内部分歧（成员 RM 打分方差上升是"走出分布"的信号）。
- **看板**：proxy/gold/KL 三曲线；长度分布随训练变化；每个检查点的样本抽查。
- **处置**：在 gold 峰值附近早停或回滚检查点；收紧 KL 系数或 KL 上限；把高分可疑样本送去人工标注并重训 RM；加入长度惩罚或长度归一化；改用 ensemble 最坏情况奖励。
- skill 文件的规则：只有 proxy 曲线、没有 held-out gold 时拒绝下诊断。

### Q17 — 参考回答要点

- **诊断**：典型的 verbosity bias（以及格式化偏好）。偏好数据中标注员轻微偏好更长、更"结构化"的回答 → RM 学到"长度/格式 = 质量" → 策略不断加长、加格式，proxy 上升而真实满意度不变。验证：画出长度与 RM 分数的相关性；构造"同内容不同长度/格式"的对照对，看 RM 是否偏好长的；看长度控制胜率是否持平。
- **数据层**：标注指南明确"长度不是优点"；增加"简洁正确 vs 冗长正确"的对照样本；平衡偏好数据中的长度分布。
- **RM 层**：在 RM 训练中加入长度去相关（对长度做回归后取残差）、ensemble；用对抗样本（被策略刷高分的长回答）回灌。
- **优化层**：长度惩罚（讲义提到 SimPO 一类方法在训练时处理长度）、更保守的 KL、按 gold 早停。
- **评估层**：讲义："at evaluation time by length-controlled win rates"；评测集中加入"简短即正确"的问题。
- 加分点：指出这与 sycophancy、过度格式化是同一机制的不同表现（统一视角），修复一种时要同时检查其他戏服是否被"挤"出来。

---

## 六、关联知识点

### 前置知识
- [阶段 18 · 01 将指令遵循作为 Alignment 信号](../../01-instruction-following-alignment-signal/docs/zh.md)：本节攻击的正是其中的 Stage 2（RM）与 KL 正则。
- [阶段 10 · 07 RLHF: Reward Model + PPO](../../../10-llms-from-scratch/07-rlhf/docs/zh.md)、[阶段 09 · 09 奖励建模 & RLHF](../../../09-reinforcement-learning/09-reward-modeling-rlhf/docs/zh.md)：奖励模型与策略优化的实现。
- [阶段 01 · 09 信息论](../../../01-math-foundations/09-information-theory/docs/zh.md)：KL 散度，以及 best-of-N 的 KL 公式。
- [阶段 10 · 10 Evaluation：基准、Evals 与 LM Harness](../../../10-llms-from-scratch/10-evaluation/docs/zh.md)：gold 信号来自可靠的评测。

### 本节被哪些后续内容用到
- [阶段 18 · 03 直接偏好优化方法家族](../../03-direct-preference-optimization-family/docs/zh.md)：DPO 类方法同样存在过度优化。
- [阶段 18 · 04 RLHF 对迎合行为的放大效应](../../04-sycophancy-rlhf-amplification/docs/zh.md)：sycophancy 这一"戏服"的缩放规律。
- [阶段 18 · 07 潜伏 Agents：持续性欺骗](../../07-sleeper-agents-persistent-deception/docs/zh.md)、[阶段 18 · 08 前沿模型中的上下文内密谋](../../08-in-context-scheming-frontier-models/docs/zh.md)：evaluator tampering 在前沿模型中的表现。
- [阶段 18 · 11 可扩展监督与弱到强泛化](../../11-scalable-oversight-weak-to-strong/docs/zh.md)：把选择压力转向难以投机的监督信号。
- [阶段 18 · 10 AI 控制：面对蓄意破坏仍能保障安全](../../10-ai-control-subversion/docs/zh.md)：当代理无法信任时的系统级防御。

### 延伸关键词
`Goodhart's Law` · `regressional / extremal / causal / adversarial` · `reward model overoptimization` · `proxy vs gold reward` · `sqrt(KL)` · `best-of-N` · `Catastrophic Goodhart` · `heavy-tailed error` · `RM ensemble` · `length-controlled win rate` · `sycophancy` · `unfaithful CoT` · `process supervision` · `early stopping`
