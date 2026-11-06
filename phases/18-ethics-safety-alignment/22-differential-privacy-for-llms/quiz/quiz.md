# 测验 · 面向 LLMs 的差分隐私（Differential Privacy for LLMs）

> **阶段 18 · 伦理、安全与对齐 · 第 22 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> **提醒**：中文讲义为机器翻译，大量希腊字母 ε、δ 和 σ 在翻译中丢失（如"(, )-DP"、"扫描噪音乘数 Q"），"canary" 被译成"加那利岛/罐子"，"PMixED" 被译成"倾销/倾斜"。请务必对照英文讲义阅读。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | (ε, δ)-差分隐私 | 对任意只差一个样本的数据集 D、D' 和任意事件 S：`P(M(D)∈S) ≤ e^ε · P(M(D')∈S) + δ`；ε 越小越私密，δ 是"保证失效"的小概率 |
| 2 | DP-SGD（Abadi 2016） | 采样 mini-batch → 逐样本梯度 → 每个梯度裁剪到范数 C → 求和后加 `N(0, σ²C²)` 噪声 → 更新；隐私成本由 accountant（Moments / Rényi DP）累计 |
| 3 | 为什么要逐样本裁剪 | 裁剪把"单个样本对梯度和的最大影响"（敏感度）限制在 C 以内，噪声标准差 σC 才能与之对应；**整个**逐样本梯度向量要**一起**裁剪 |
| 4 | ε 没有通用安全值 | 讲义：LLM 文献中的 ε 因威胁模型、数据敏感度和效用目标而差异很大，约 1–10 的例子只是示意，不是推荐默认值；ε 越低通常需要越多噪声 |
| 5 | LoRA + DP-SGD | 讲义称之为 2025 年的常见配置：只在小 adapter 上做 DP-SGD，降低逐样本梯度存储；DP 保证只覆盖 adapter 所用的微调数据，基座模型的记忆不在保证范围内 |
| 6 | 2024–2025 的证据张力 | Duan 等人 2024：MIA 对 LLM 几乎只比随机猜测好一点；Carlini 2021 等提取攻击：能恢复大量逐字记忆的训练文本 |
| 7 | 张力的化解（arXiv:2503.06808） | 两者测的东西不同；新设计的 canary 让无需影子模型的 loss-based MIA 变强，给出首个在真实数据、现实 DP 保证下有意义的 LLM DP 审计（摘要：理论 ε = 4 的模型，经验估计约为 1） |
| 8 | DP 训练的替代方案 | PMixED（arXiv:2403.15638）：推理时私有预测，多个专家各看一个数据分片，聚合下一个 token 分布时加噪；DP 合成数据（Google Research 2024）：先 DP 微调，再采样合成数据训练下游模型 |
| 9 | DP Reversal via LLM Feedback | 讲义：2025 年新出现的攻击，利用 DP 训练模型的置信度分数作为神谕重新识别个体；防御方法是不暴露置信度，或截断、量化后再暴露 |
| 10 | 本节代码的定位 | 逐样本（batch = 1）DP-SGD 训练逻辑回归 + 一个**粗略且不严格**的 ε 估计；讲义 Use It 中提到的 canary 攻击和 C 扫描都没有实现 |

### 核心技能（能动手做到）

- [ ] 写出 (ε, δ)-DP 的定义，并用一句话解释 ε 和 δ 各自的含义
- [ ] 默写 DP-SGD 的五步，并说明裁剪与噪声如何配合
- [ ] 指出 `main.py` 中"w 与 b 分别裁剪"导致敏感度变成 √2·C 的问题，并给出修正
- [ ] 解释 `analytical_epsilon` 为什么不是有效的隐私上界，并能用正确的组合方法重新估算 ε
- [ ] 实现 canary 插入 + loss 检验（讲义练习 2），比较 σ = 0 与 σ = 1 时的成员推断 AUC
- [ ] 审计一份 LLM 的 DP 声明：ε/δ、accountant、DP 作用范围（全模型还是 LoRA）、MIA 评估方式、置信度暴露（对应 `outputs/skill-dp-audit.md`）

---

## 二、基础自测（选择题）

**Q1.** 关于 (ε, δ)-差分隐私的定义，正确的是：

- A. 对任意只差一个样本的数据集 D、D' 和任意事件 S，有 `P(M(D)∈S) ≤ e^ε · P(M(D')∈S) + δ`
- B. 算法 M 保证不会记住任何训练数据
- C. 算法 M 的输出与训练数据无关
- D. ε 越大隐私越强

**Q2.** DP-SGD 要对**每个样本**的梯度裁剪到范数 C，主要目的是：

- A. 防止梯度爆炸，加快收敛
- B. 减少显存占用
- C. 限制单个样本对梯度和的最大影响（敏感度），使标准差为 σC 的高斯噪声能提供与之匹配的隐私保证
- D. 让 accountant 不再需要

**Q3.** 讲义说 LoRA + DP-SGD 是 2025 年的常见配置。关于它的 DP 保证，正确的是：

- A. 保证覆盖基座模型预训练数据中的所有个人信息
- B. DP 保证作用于 adapter，即只保护用于微调的数据；基座模型在预训练中记住的内容不在保证范围内
- C. LoRA 让 ε 自动变为 0
- D. LoRA 让 accountant 变得不必要

**Q4.** arXiv:2503.06808（2025 年 3 月）如何化解"canary MIA 成功率有限"与"训练数据提取攻击很成功"之间的张力？

- A. 证明 DP-SGD 没有必要
- B. 证明两类攻击测的是同一种性质
- C. 完全取消了 canary
- D. 指出二者测的东西不同；以往的 canary 设计太弱、没有针对"最容易被提取"的情形优化，于是低估了记忆；更好的 canary 让无需影子模型的 loss-based MIA 显著增强，并完成了首个有意义的真实数据 LLM DP 审计

**Q5.** PMixED（arXiv:2403.15638）作为 DP 训练的替代方案，其核心思路是：

- A. 一种新的 Rényi DP accountant
- B. 更快的 DP-SGD 实现
- C. 只用 ε 而不用 δ 的会计方法
- D. 推理时私有预测：多个专家各自只看一份训练数据分片，聚合下一个 token 分布时加噪声，从而完全不需要 DP 训练

**Q6.** 运行 `main.py`，σ = 0 那一行打印 `approx-epsilon=34257.95`。这是因为：

- A. 代码用 `max(sigma, 0.01)` 把 σ = 0 替换成 0.01 再代入公式；实际上 σ = 0 没有任何隐私保证，ε 应为 ∞
- B. σ = 0 时 DP-SGD 仍有隐私保证，ε 约为 3.4 万
- C. 是裁剪带来的隐私
- D. 浮点溢出

**Q7.** `dp_sgd` 中，`grad_w`（2 维）用 `clip(grad_w, C)` 裁剪到范数 C，`grad_b` 又单独截断到 [−C, C]，两者都加标准差 σC 的噪声。问题在于：

- A. 没有问题，这是标准做法
- B. 偏置不需要加噪声
- C. 完整梯度向量 `(grad_w, grad_b)` 的范数最大可达 √2·C，单样本敏感度变为 √2·C，而噪声仍按 σC 计算，等效噪声乘数只有 σ/√2
- D. 应该先加噪声再裁剪

**Q8.** 针对 DP Reversal via LLM Feedback 攻击，讲义给出的防御是：

- A. 把 ε 调大
- B. 不暴露置信度分数，或者在暴露前截断、量化；这是 (ε, δ)-DP 训练之外的额外要求
- C. 改用 LoRA
- D. 增加训练轮数

---

## 三、动手 / 代码题

**Q9.** 手算并评价代码的 ε 估计：

```python
def analytical_epsilon(sigma: float, steps: int, delta: float = 1e-5) -> float:
    """Rough Gaussian-mechanism composition proxy.
    Each step contributes roughly 1/(2*sigma^2); composition bounds epsilon
    by sum. Real accountants (RDP, Moments) give tighter bounds."""
    return math.sqrt(2 * math.log(1.25 / delta)) * math.sqrt(steps) / sigma
```

`main` 中 `steps = epochs * len(train_data) = 10 × 500 = 5000`，δ = 1e-5。

1. 手算 σ = 1 时函数的返回值。
2. docstring 与公式一致吗？
3. 这个公式是一个**有效的上界**吗？（提示：单步高斯机制公式 `ε = √(2 ln(1.25/δ))/σ` 只在 ε < 1 时成立；T 次高斯机制的组合恰好等价于一次噪声乘数为 σ/√T 的高斯机制。）
4. 在 batch = 1、每个 epoch 把每个样本恰好用一次的设定下，单个样本实际参与了多少步？据此应如何重新估算 ε？

**Q10.** 修复 Q7 的裁剪问题：把 `(grad_w[0], grad_w[1], grad_b)` 视为一个 3 维向量**联合裁剪**到 C，再对 3 个分量各加 `N(0, σ²C²)` 噪声。写出修改后的 `dp_sgd` 循环体。

**Q11.** 讲义练习 2（代码中没有实现）：实现 canary 插入 + loss 检验，测量 σ = 0 与 σ = 1 时的成员推断能力。建议设计：canary 取 `x = [−2.0, 2.0]`（按标注规则其真实标签为 0），**故意标成 1**；对 40 个随机种子分别训练"含 canary"和"不含 canary"的模型，以 canary 的 log-loss 作为检验统计量，计算 AUC。

**Q12.** 讲义练习 1 要求"扫描 σ 并找出效用崩溃点"。代码单次运行的结果是 σ = 1.0 → 0.980、σ = 2.0 → 0.860、σ = 4.0 → 0.935，准确率随 σ **非单调**变化。

1. 为什么会这样？
2. 设计一个更可靠的实验，并报告结果。
3. 结合 Q9 的修正 ε，讨论在这个玩具问题上"效用崩溃"出现在哪里。

---

## 四、面试高频题

**Q13.**（基础必考）解释差分隐私和 DP-SGD。ε 和 δ 分别代表什么？为什么需要逐样本裁剪和高斯噪声？

**Q14.**（原理深挖）成员推断攻击（MIA）和训练数据提取攻击有什么区别？为什么 2024 年有研究说"MIA 对 LLM 几乎无效"，而提取攻击却能恢复大量训练文本？如何对一个 DP 模型做经验审计？

**Q15.**（工程实践）公司要用客服对话日志（含个人信息）微调一个 LLM，要求有差分隐私保证。请给出技术方案和需要注意的坑。

**Q16.**（场景设计）DP-SGD 微调、PMixED 推理时私有预测、DP 合成数据，这三种方案分别适合什么场景？各自针对什么威胁模型？

**Q17.**（追问型）供应商说："我们的模型用 ε = 8 的 DP 训练，所以是安全的。"你会追问哪些问题？

---

## 五、参考答案与解析

### Q1 — 答案：A

讲义原式："P(M(D) in S) <= e^ε * P(M(D') in S) + δ"。直观含义：有没有你这一条数据，输出分布几乎一样（倍数差异不超过 e^ε），因此无法可靠推断你的贡献，除了概率 δ 的例外。

- B 错：DP 不保证"不记忆"，而是限制单个样本对输出的影响。一个在许多样本中都出现的模式仍然可以被学到并输出。
- C 错：输出当然与数据有关，否则模型毫无用处。
- D 说反了：ε 越小，两个分布越接近，隐私越强。

### Q2 — 答案：C

DP 的噪声要与**敏感度**匹配：若单个样本能把梯度和改变任意大，再多的有限噪声也遮不住它。裁剪把每个样本的贡献限制在范数 C 以内，敏感度就是 C，噪声标准差取 σC，σ 就成为"噪声乘数"，accountant 根据 σ、采样率和步数计算 ε。

- A 是普通梯度裁剪（全局裁剪）的目的，不是逐样本裁剪的目的。
- B 错：逐样本梯度反而更耗显存，这正是讲义说 LoRA 有帮助的原因。
- D 错：仍然需要 accountant 累计隐私成本。

### Q3 — 答案：B

讲义："DP guarantees apply to the adapter; the base model is held fixed." `skill-dp-audit.md` 也强调："If LoRA, the base-model memorization is not covered." 所以 A 错：基座模型在预训练中记住的东西，仍可能被提取。C、D 无依据：LoRA 只减少了需要加噪的参数量和梯度存储，ε 的计算方式不变。

### Q4 — 答案：D

讲义："the two measure different things ... canaries under-report this because they are not optimized to be extractable." 论文摘要（Panda、Tang、Nasr、Choquette-Choo、Mittal，ICLR 2025）的表述是：以往 LLM 隐私审计的 canary 生成方式太简单，导致 MIA 很弱、审计下界很松；他们设计的 canary 在 Qwen2.5-0.5B 上，FPR = 1% 时 TPR 达到 49.6%（以往方法为 4.2%）；攻击者无需训练影子模型；对一个理论 ε = 4 的模型给出约 ε ≈ 1 的经验估计。

注意：讲义把这篇论文署名为 "Kowalczyk et al."，与 arXiv 页面的作者不符。A、B、C 都与原文相反。

### Q5 — 答案：D

讲义："Private prediction at inference time. Mixture of experts on next-token distributions; each expert sees a shard of training data; aggregation adds noise for DP. Avoids DP training entirely." 思路类似 PATE：多个"教师"各自只看一部分数据，对它们的输出做带噪聚合。由于每次查询都会消耗隐私预算，它针对的是"通过查询接口泄露"的威胁模型（见 Q16）。A、B、C 都不是 PMixED 的内容。

### Q6 — 答案：A

代码：`eps = analytical_epsilon(max(sigma, 0.01), ...)`。σ = 0 被替换成 0.01，于是 `4.8448 × 70.71 / 0.01 ≈ 34258`。σ = 0 就是普通 SGD，没有任何 DP 保证，ε 应为 ∞；TAKEAWAY 也写了 "sigma=0 is standard SGD with no privacy (infinite epsilon)"，与打印的数字自相矛盾。B 错，C 错：只裁剪不加噪声，不提供任何 DP 保证。D 错，没有发生溢出。

### Q7 — 答案：C

`clip(grad_w, C)` 让 `|grad_w| ≤ C`，`grad_b` 又被截断到 `|grad_b| ≤ C`，所以完整梯度 `(w0, w1, b)` 的范数最大为 `√(C² + C²) = √2·C`（已验证：`clip([3, 4], 1) = [0.6, 0.8]`，加上 `grad_b = −1` 后范数为 1.414）。噪声却按 σC 加，等效噪声乘数变成 σ/√2，实际 ε 比按 σ 计算的更大。标准做法是**把所有参数的逐样本梯度拼成一个向量，一起裁剪**（Opacus 等库就是这样做的）。

- A 错，这不是标准做法。
- B 错：偏置也是由数据决定的参数，它的梯度同样会泄露信息，必须裁剪并加噪。
- D 顺序反了：先裁剪、后加噪声。

### Q8 — 答案：B

讲义："The defense: do not expose confidences, or truncate/quantize them before exposure. This is an additional requirement beyond (ε, δ)-DP training." A 背道而驰；C、D 与这个攻击无关。`skill-dp-audit.md` 的 Hard rejects 也包括："Any deployment exposing confidence scores without addressing DP Reversal."

### Q9 — 参考答案

1. `ln(1.25 / 1e-5) = ln(125000) = 11.736`；`√(2 × 11.736) = 4.8448`；`√5000 = 70.711`；`4.8448 × 70.711 / 1 = 342.58`，与输出 `approx-epsilon= 342.58` 一致。
2. **不一致**：docstring 说"每步贡献约 1/(2σ²)，组合时按求和"，这对应的是 RDP 或 zCDP 风格的 ρ 线性累加；而公式是 `√T × 单步高斯机制 ε`，是另一种近似。
3. **不是有效上界**：
   - 单步公式 `ε = √(2 ln(1.25/δ))/σ` 只在 ε < 1 时成立。σ = 1 时单步 ε = 4.84，已经超出适用范围；
   - "√T × 单步 ε" 只是高级组合定理的主项，省略了 `T·ε(e^ε − 1)` 项和 δ' 的分配，**不保证是上界**；
   - 用精确的高斯 DP 组合（T 次噪声乘数为 σ 的高斯机制，等价于参数 `μ = √T/σ` 的 μ-GDP）在 δ = 1e-5 下精确计算：在"每一步都涉及该个体"的同样假设下，σ = 1 时 ε ≈ **2801**，比代码输出的 342.6 **大约 8 倍**。所以这个代理值在它自己的假设下反而**低估**了 ε。
4. **每个样本只参与 10 步**：每个 epoch 用一次，共 10 个 epoch；其余步骤对这个样本而言只是"后处理"。所以组合次数应为 T = 10，而不是 5000（代码在这一点上**高估**）。重新估算（GDP 精确计算，δ = 1e-5，不计子采样放大）：

   | σ | 代码输出 | T = 5000 精确 | T = 10 精确 | T = 10 且考虑 √2 敏感度（等效 σ/√2） |
   |---|---------|--------------|------------|-----------------------------------|
   | 0.5 | 685.2 | 10,602 | 46.2 | 77.3 |
   | 1.0 | 342.6 | 2,801 | 17.9 | 28.4 |
   | 2.0 | 171.3 | 775 | 7.5 | 11.5 |
   | 4.0 | 85.6 | 231 | 3.3 | 5.0 |

   结论：代码的 approx-epsilon 同时犯了"多算步数"和"组合公式不成立"两个方向相反的错误，数值本身没有意义。在这个设定下比较合理的量级是：σ = 1 时 ε 约为 18–28，σ = 4 时 ε 约为 3–5。要得到严格的数字，应当使用正规 accountant（如 Opacus 的 RDP/PRV accountant），并采用 Poisson 子采样以获得放大效应。

### Q10 — 参考答案

```python
    for _ in range(epochs):
        random.shuffle(data)
        for x, y in data:
            z = b + sum(wi * xi for wi, xi in zip(w, x))
            err = sigmoid(z) - y
            g = [err * x[0], err * x[1], err]          # 完整逐样本梯度 (w0, w1, b)
            g = clip(g, C)                              # 联合裁剪：|g| <= C
            g = [gi + random.gauss(0.0, sigma * C) for gi in g]   # 每个分量加 N(0, σ²C²)
            w = [w[0] - lr * g[0], w[1] - lr * g[1]]
            b -= lr * g[2]
```

- `clip` 函数本身对任意长度的列表都适用，不需要修改。
- 修复后单样本敏感度为 C，噪声乘数就是 σ，Q9 表中"T = 10 精确"那一列才对应这个实现。
- 在真正的 DP-SGD 中，还要对一个 mini-batch 的裁剪梯度**求和后**只加一次噪声，再除以 batch 大小；batch 越大，相对噪声越小，这是 DP 训练需要大 batch 的原因。

### Q11 — 参考答案

```python
import math, random, statistics
import main as m

def canary_loss(sigma, include, seed):
    random.seed(seed)
    tr = m.gen(500)
    can = ([-2.0, 2.0], 1)            # 真实标签按规则为 0，故意标成 1
    if include:
        tr = tr + [can]
    mod = m.dp_sgd(tr, 10, 0.05, sigma, 1.0)
    z = mod[2] + mod[0] * can[0][0] + mod[1] * can[0][1]
    p = m.sigmoid(z)
    return -math.log(max(p, 1e-12))   # canary 在标签 1 上的 log-loss

def auc(ins, outs):                   # P(loss_in < loss_out)，平局记 0.5
    c = 0
    for a in ins:
        for b in outs:
            c += 1 if a < b else 0.5 if a == b else 0
    return c / (len(ins) * len(outs))

for s in (0.0, 1.0):
    ins  = [canary_loss(s, True,  5000 + i) for i in range(40)]
    outs = [canary_loss(s, False, 5000 + i) for i in range(40)]
    print(s, statistics.mean(ins), statistics.mean(outs), auc(ins, outs))
```

实际运行结果：

| σ | canary 在训练集中时的平均 loss | 不在时的平均 loss | AUC |
|---|------------------------------|------------------|-----|
| 0.0 | 20.09 | 20.92 | **0.968** |
| 1.0 | 21.00 | 20.69 | **0.490** |

解读：
- σ = 0 时，canary 是否在训练集中，几乎可以完美区分（AUC 0.968）：训练时这个错标的离群点被拟合了一点点，loss 略低。注意绝对 loss 都很大（约 20），这一点点差异就已经足够被检测出来。
- σ = 1 时 AUC 约为 0.5，等于随机猜测：噪声完全淹没了单个样本的影响。
- 局限：40 次实验的 AUC 有抽样误差；检验统计量只用了 loss，更强的攻击（例如 2503.06808 中优化过的 canary）可能得到更高的 AUC。经验审计给出的是 ε 的**下界**，不能替代理论上界。

### Q12 — 参考答案

1. **非单调的原因**：每个 σ 只跑了一次；SGD 的最终迭代点受噪声影响很大；测试集只有 200 个样本（准确率相差 0.01 就是 2 个样本）；而且 `random.shuffle(data)` 会原地打乱同一个 `train_data`，各个 σ 的运行共用一个全局随机数流，彼此并不独立。σ = 2 那一次恰好"运气差"。
2. **更可靠的实验**：对每个 σ 跑 30 个种子（每个种子重新生成训练集和测试集），报告均值、标准差和最小值。实际运行结果：

   | σ | 平均准确率 | 标准差 | 最小值 |
   |---|----------|-------|-------|
   | 0.0 | 0.993 | 0.006 | 0.980 |
   | 0.5 | 0.981 | 0.014 | 0.945 |
   | 1.0 | 0.958 | 0.030 | 0.860 |
   | 2.0 | 0.923 | 0.058 | 0.745 |
   | 4.0 | 0.868 | 0.096 | 0.690 |

   均值随 σ **单调下降**，方差随 σ 增大，这才符合"噪声越大、效用越低"的预期。
3. **崩溃点**：在这个线性可分的二维问题上，σ ≤ 4 的范围内没有出现断崖式崩溃，平均准确率仍有 0.87，但**最差情况**已经降到 0.69，说明可靠性先于平均效用崩溃。结合 Q9，σ = 4 对应的 ε 约为 3–5（按每个 epoch 一次计算），这在讲义提到的"约 1–10"示例范围内。真实 LLM 的参数维度高得多，同样的 ε 下噪声对效用的影响会大得多，这也是需要 LoRA（降低需要加噪的维度）的原因之一。

### Q13 — 参考回答要点

- **DP 定义**：见 Q1。ε 是"隐私损失"的上界：任何输出事件的概率，在有你和没有你两种情况下最多相差 e^ε 倍。δ 是这个保证失效的小概率，通常要求远小于 1/n（n 为数据集大小）。
- **DP-SGD 五步**（讲义）：采样 mini-batch → 计算逐样本梯度 → 每个裁剪到 C → 求和后加 `N(0, σ²C²)` → 更新。
- **为什么裁剪**：限制敏感度（Q2）；**为什么加高斯噪声**：让输出分布在相邻数据集之间"重叠"，重叠程度由 σ 决定；**为什么需要 accountant**：每一步都消耗隐私预算，要用 Moments 或 Rényi DP accountant 紧致地累计，并利用子采样放大（每步只用一小部分数据，单个样本被用到的概率低）。
- **代价**：逐样本梯度的显存和计算开销、噪声带来的效用损失，以及需要更大的 batch 和更多训练步。
- 加分点：说出隐私单位的区别：样本级（example-level）还是用户级（user-level）DP。一个用户有很多条数据时，样本级 ε 会低估对这个用户的隐私风险。

### Q14 — 参考回答要点

- **MIA**：给定一个样本，判断它是否在训练集中（是或否）。**提取攻击**：给模型一个前缀，看它能否逐字续写出训练数据（"能恢复什么"）。讲义："MIA asks 'is example e in D?' ... Extraction asks 'what can I recover of D?'"
- **为什么结论相反**：Duan 等人 2024 在 Pile 训练的模型上，用自然的成员与非成员数据评估，发现 MIA "barely outperform random guessing"，原因包括训练集巨大、每个样本只过很少几次、成员与非成员边界模糊；而提取攻击针对的是**被大量重复或特别容易被记住**的序列，只需少量这样的样本就能证明泄露存在。"平均样本难以被推断"与"存在可被提取的样本"并不矛盾，隐私关心的是最坏情况。
- **经验审计**：插入 canary，训练含与不含 canary 的模型，用攻击的 TPR/FPR 推出 ε 的**下界**，与理论上界对比。2503.06808 的贡献是更强的 canary 设计，在不需要影子模型的受限攻击者设定下，对理论 ε = 4 的模型给出约 1 的经验下界。
- 加分点：经验审计只能给出下界，不能证明"有 DP"；而理论上界依赖实现正确（例如本节代码的裁剪 bug 就会让理论值失效）。
- 常见误区：讲义把 Duan 等人称为 "Canary MIA"，但该研究用的是自然的成员与非成员数据，并非插入的 canary。

### Q15 — 参考回答要点

- **数据层**：先做去重（重复样本会被成倍记忆）、PII 检测与脱敏，并明确隐私单位：以**用户**为单位做 DP（一个用户的所有对话视为一个整体）比以单条消息为单位更符合实际威胁。
- **训练层**：基座模型 + LoRA + DP-SGD（如 Opacus 或 JAX 生态的实现）；逐样本梯度联合裁剪（Q10）；Poisson 子采样 + 大 batch；使用 RDP/PRV accountant 记录 ε、δ；δ 远小于 1/用户数。
- **ε 的选择**：不存在通用的安全值（讲义与 skill 的 Refusal rules 都强调了这一点）。要结合威胁模型、数据敏感度和效用目标，在几个候选 ε 下评估效用后，由隐私、法务、业务三方共同决定。
- **评估**：效用（任务指标）、经验审计（canary MIA、提取测试）、DP 声明文档（ε、δ、accountant、隐私单位、覆盖范围）。
- **部署层**：不暴露置信度或 logprobs，或者截断、量化后再暴露（讲义的 DP Reversal 防御）；输出侧加 PII 过滤。
- **注意的坑**：DP 只覆盖 LoRA 所用的微调数据，基座模型本身的记忆不在保证范围内；超参数搜索本身也会消耗隐私预算；多次重训、多次发布要累加 ε。

### Q16 — 参考回答要点

| 方案 | 怎么做 | 适合场景 | 威胁模型 / 局限 |
|------|--------|---------|----------------|
| DP-SGD（+ LoRA）微调 | 训练时加噪，得到 DP 模型参数 | 模型需要发布或部署到不可信环境；需要无限次查询 | 防护对象是"拿到模型权重或无限查询的攻击者"；代价是训练开销和效用损失 |
| PMixED | 推理时多个专家（各看一个数据分片）的下一个 token 分布带噪聚合 | 模型只通过 API 提供服务，查询量可控 | 防护对象是通过查询接口推断数据；每次查询都消耗预算，查询多了 ε 会持续增长；权重本身不私密，不能发布 |
| DP 合成数据 | DP 微调一个生成模型，采样合成数据，再在上面训练下游模型 | 需要把数据共享给其他团队或用于多个下游任务 | 合成数据是 DP 训练的后处理，可以任意使用；但合成数据的质量和分布覆盖有限 |

- 讲义："Both sidestep the utility cost of full DP training at the cost of a different threat model."
- 加分点：说明 DP 的"后处理不变性"：对 DP 输出做任何处理（如用合成数据训练）都不会增加隐私损失。这是 DP 合成数据方案成立的理论基础。

### Q17 — 参考回答要点

逐项追问（对应 `skill-dp-audit.md`）：
1. **δ 是多少？用的是什么 accountant**（Moments、RDP、PRV、GDP）？skill："ε without the accountant is meaningless."
2. **隐私单位**是样本级还是用户级？一个用户的数据有多少条？
3. **DP 覆盖范围**：全模型还是只有 LoRA adapter？基座模型的预训练数据是否包含敏感信息？
4. **实现是否正确**：是否做了逐样本**联合**裁剪？采样方式（Poisson 或打乱）是否与 accountant 的假设一致？超参数搜索是否计入了预算？
5. **经验验证**：做过 MIA 或提取测试吗？用的是 canary 还是提取？2503.06808 指出，弱 canary 会低估风险。
6. **部署面**：是否暴露 logprobs 或置信度（DP Reversal）？输出端有没有 PII 过滤？
7. **"安全"是相对什么威胁模型而言**：skill 的 Refusal rules："If the user asks 'is epsilon=8 safe enough,' refuse the numeric answer; safety depends on the threat model and the most-extractable-data distribution."

加分点：说明 ε = 8 意味着概率比最多为 e^8 ≈ 2981 倍，这是一个最坏情况上界。实际泄露通常远小于这个值，但不能用"经验上没测到泄露"来替代上界。

---

## 六、关联知识点

### 前置知识
- [阶段 01 · 09 信息论](../../../01-math-foundations/09-information-theory/docs/zh.md)：讲义的先修要求；理解隐私损失（似然比的对数）的度量。
- [阶段 01 · 06 概率和分布](../../../01-math-foundations/06-probability-and-distributions/docs/zh.md)：高斯机制与尾概率。
- [阶段 02 · 03 逻辑回归](../../../02-ml-fundamentals/03-logistic-regression/docs/zh.md)：`main.py` 训练的就是逻辑回归。
- [阶段 03 · 07 正则化](../../../03-deep-learning-core/07-regularization/docs/zh.md)：梯度裁剪与噪声对训练的影响。
- [阶段 11 · 08 Fine-Tuning 与 LoRA & QLoRA](../../../11-llm-engineering/08-fine-tuning-lora/docs/zh.md)：LoRA + DP-SGD 的基础。

### 本节被哪些后续内容用到
- [阶段 18 · 23 水印：SynthID、Stable Signature、C2PA](../../23-watermarking-synthid-stable-signature-c2pa/docs/zh.md)：讲义的下一节，从隐私转向内容溯源。
- [阶段 18 · 27 Data Provenance 与训练数据治理](../../27-data-provenance-training-governance/docs/zh.md)：讲义提到的"监管层面的数据溯源"。
- [阶段 18 · 25 EchoLeak 与 AI 领域 CVE 的出现](../../25-echoleak-cves-for-ai/docs/zh.md)：生产环境中的数据泄露路径。
- [阶段 17 · 26 合规：SOC 2、HIPAA、GDPR、PCI-DSS、EU AI Act、ISO 42001](../../../17-infrastructure-and-production/26-compliance-frameworks/docs/zh.md)：隐私合规要求与 DP 的关系。
- [阶段 17 · 25 安全：密钥、API 密钥轮换、Audit Logs 与 Guardrails](../../../17-infrastructure-and-production/25-security-secrets-audit/docs/zh.md)：部署侧的置信度暴露与输出过滤。

### 延伸关键词
`(ε, δ)-DP` · `sensitivity` · `Gaussian mechanism` · `DP-SGD` · `per-example clipping` · `Poisson subsampling / privacy amplification` · `RDP / PRV / GDP accountant` · `Opacus` · `user-level DP` · `membership inference` · `canary / privacy auditing` · `training data extraction` · `PATE / PMixED` · `DP synthetic data` · `post-processing invariance`
