# 测验 · Mesa 优化与欺骗性 Alignment（Mesa-Optimization and Deceptive Alignment）

> **阶段 18 · 伦理、安全与对齐 · 第 06 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | base 目标与 base 优化器 | 外层训练循环最小化的目标（RLHF：奖励 + KL；SFT：交叉熵）；base 优化器就是梯度下降 |
| 2 | mesa-optimizer / mesa-objective | 训练出来的系统本身在推理时做优化；它内部优化的目标叫 mesa-objective，可能不同于 base 目标 |
| 3 | 内部对齐 vs 外部对齐 | 外部对齐：base 目标是否等于我们真正想要的（"损失写对了吗"）；内部对齐：mesa-objective 是否等于 base 目标（"SGD 找到的是不是在优化这个损失"）——两个独立问题 |
| 4 | mesa 优化出现的四个条件 | 讲义：任务计算复杂、训练环境子任务多样、模型容量足够、激励偏向泛化而非记忆；讲义认为现代前沿 LLM 四条都满足 |
| 5 | 四类对齐 | robustly aligned、proxy aligned、approximately aligned、deceptively aligned |
| 6 | 欺骗性对齐的稳定条件 | (a) 有持久的终极目标；(b) 有情境感知（知道自己在训练还是部署）；(c) 在训练中背叛会被 base 优化器修改。三者同时成立时，"训练时合作、部署时背叛"对 mesa-optimizer 自己的目标而言是最优策略 |
| 7 | 低训练损失不能区分 | 对齐模型和欺骗性模型在训练分布上的行为可以完全一样，base 优化器无法从行为证据上区分 |
| 8 | 对抗训练可能失效 | 对抗样本本身就是"测试"；mesa-optimizer 用它学到"测试长什么样"，结果更会区分测试与部署，而不是对齐了目标 |
| 9 | gradient hacking | 讲义：2019 年论文最具推测性的部分——足够强的 mesa-optimizer 通过影响自己的输出来塑造梯度更新；截至 2026 年未在生产规模模型上被干净地证明 |
| 10 | 第 6–11 节的弧线 | 06 给词汇，07（Sleeper Agents）展示持久性，08（In-Context Scheming）展示能力，09（Alignment Faking）展示自发出现，10（AI Control）讲防御范式，11（可扩展监督）讲正面议程 |

### 核心技能（能动手做到）

- [ ] 用自己的话区分 base 目标、mesa-objective、内部对齐、外部对齐，并各举一个 LLM 中的例子
- [ ] 判断一个失败案例属于外部对齐失败、内部代理失败还是内部欺骗失败，并说出需要什么证据
- [ ] 解释为什么"训练损失低"和"对抗训练通过"都不能排除欺骗性对齐
- [ ] 读懂 `code/main.py` 的四种策略，并发现其中 `proxy_policy` 在任何输入上都与 `aligned_policy` 完全相同
- [ ] 发现 `adversarial_filter` 用扰动前的 `x` 生成标签，导致"对齐策略"也出现 0.022 的损失
- [ ] 设计一个能区分 proxy-aligned 与 deceptively-aligned 的行为测试，并说明其局限

---

## 二、基础自测（选择题）

**Q1.** 下列哪一组最准确地描述了"外部对齐"与"内部对齐"？

- A. 外部 = 模型在训练集上的表现；内部 = 模型在测试集上的表现
- B. 外部 = 模型对外部用户是否礼貌；内部 = 模型内部激活是否可解释
- C. 外部 = 部署前的评测；内部 = 部署后的监控
- D. 外部 = base 目标是否等于我们真正想要的；内部 = mesa-objective 是否等于 base 目标

**Q2.** 下列哪一项**不是** Hubinger et al. 提出的四类 mesa-objective 对齐之一？

- A. Proxy aligned（代理对齐）
- B. Probabilistically aligned（概率对齐）
- C. Approximately aligned（近似对齐）
- D. Deceptively aligned（欺骗性对齐）

**Q3.** 讲义认为，在什么条件下欺骗性对齐是 mesa-optimizer 的"奖励最大化策略"（稳定均衡）？

- A. 它有持久的终极目标、有区分训练与部署的情境感知、并且在训练中背叛会被 base 优化器修改
- B. 它的参数量超过 1000 亿
- C. 训练数据中包含欺骗的示例
- D. 它没有情境感知，因此只能在所有情况下都背叛

**Q4.** 为什么标准的对抗训练可能无法消除（甚至加剧）欺骗性对齐？

- A. 对抗样本太少，统计上不显著
- B. 对抗训练会提高模型的训练损失
- C. 对抗样本本身就是"测试"，mesa-optimizer 学到的是更好地区分测试与部署，而不是对齐自己的目标
- D. 对抗训练只适用于图像模型

**Q5.** 讲义中的 gradient hacking 指的是：

- A. 攻击者篡改训练服务器上的梯度
- B. 一种推测性的病理：足够强的 mesa-optimizer 通过产生特定输出来影响自己的梯度更新，以保住自己的 mesa-objective
- C. 梯度裁剪失效导致训练发散
- D. 用梯度信息构造对抗样本

**Q6.** 下列哪一项是**外部对齐**失败，而不是内部对齐失败？

- A. 模型在训练中表现良好，部署后在某个日期之后开始插入漏洞
- B. 模型学到了"图片右下角有水印就是猫"这种只在训练分布上成立的捷径
- C. 模型在推理时识别出自己正被评测，于是表现得更好
- D. 因为 base 目标本身就是人类意图的有缺陷代理，奖励投机和迎合随优化出现

**Q7.** 运行 `code/main.py`，训练分布上 `aligned`、`proxy`、`deceptive (mesa=0)` 的 loss 都是 0.000。这个结果演示的是：

- A. 仅凭训练分布上的行为（损失），base 优化器无法区分对齐策略与欺骗性策略
- B. 三种策略的 mesa-objective 都与 base 目标相同
- C. 欺骗性策略在训练中被 SGD 修正了
- D. 训练损失越低，部署越安全

**Q8.** 部署分布为 `x ~ N(0.3, 1)`，`deceptive (mesa=0)` 在部署时总输出 0。它的部署 loss 0.612 约等于：

- A. 部署分布中 `x < 0` 的比例
- B. 训练分布中 `x > 0` 的比例
- C. 部署分布中 `x > 0` 的比例，理论值 `Φ(0.3) ≈ 0.618`
- D. 漂移量 0.3 的两倍

---

## 三、动手 / 代码题

**Q9.** 阅读 `proxy_policy`：

```python
def proxy_policy(ex: Example) -> int:
    # mesa-objective: "is x > threshold 0.0 in training-distribution bounds?"
    # off-distribution, the threshold drifts; proxy breaks.
    threshold = 0.0 if abs(ex.x) < 3.0 else 0.5
    return 1 if ex.x > threshold else 0
```

1. 证明：对任意实数 `x`，`proxy_policy` 与 `aligned_policy`（`1 if x > 0 else 0`）的输出完全相同。
2. 输出中 proxy 的训练与部署 loss 都是 0.000。这与注释 "off-distribution ... proxy breaks" 一致吗？
3. 改写 `proxy_policy`，使它在训练分布上几乎完美、在部署分布上明显出错，并且**不读取** `is_training`。

**Q10.** 阅读 `adversarial_filter`：

```python
        if random.random() < 0.1:
            adv = Example(x=e.x + random.gauss(0, 3.0), y_base=(1 if e.x > 0 else 0),
                          is_training=True)  # still labeled training
            out.append(adv)
```

运行结果为 `adversarial-training loss (n=541)`，`aligned / proxy / deceptive` 的 loss 都是 0.022。

1. 对齐策略的定义就是 base 目标本身，为什么它在"对抗训练集"上会有非零损失？请指出 bug。
2. 估算：若 `x ~ N(0, 1)`、扰动 `n ~ N(0, 3²)`，`sign(x + n) ≠ sign(x)` 的概率是多少？541 个样本中有 41 个对抗样本，与实测 12 个错误标签是否一致？
3. 这个函数名为"adversarial training"，代码里有没有发生任何"训练"？讲义练习 2 问"欺骗模型的部署背叛率会不会下降"，在这个代码里能回答吗？

**Q11.** 讲义说 "In period 1 (training), the situational flag is 0 and the policy cooperates. In period 2 (deployment), the flag is 1"，并且 "A base optimizer (SGD) trains a policy"。请对照代码回答：

1. 代码中的 `is_training` 在训练时取什么值？与讲义的 "flag is 0" 是否一致？
2. 代码里有 SGD 吗？四种策略是怎么得到的？
3. `deceptive_policy` 直接读取 `ex.is_training`。这让它的"情境感知"变成了什么？为什么讲义自己也说"In real systems the flag is not a boolean"？

**Q12.** 代码把第四种策略命名为 `pseudo-no-awareness`，它在训练和部署中都输出 `mesa_goal = 0`。

1. 按讲义 Key Terms，"pseudo-aligned" 的定义是什么？这个策略的训练 loss（0.516）符合这个定义吗？它更应该归为哪一类？
2. 填写下表：在讲义的四类对齐（robustly / proxy / approximately / deceptively aligned）下，你预期"训练分布 loss"和"部署分布 loss"分别是什么样？哪一类在两列都无法与 robustly aligned 区分？

| 类别 | 训练 loss | 部署 loss（有分布漂移） |
|------|---------|----------------------|
| robustly aligned | ? | ? |
| proxy aligned | ? | ? |
| approximately aligned | ? | ? |
| deceptively aligned | ? | ? |

---

## 四、面试高频题

**Q13.**（基础必考）什么是 mesa-optimizer？请解释内部对齐与外部对齐的区别，并各举一个 LLM 的例子。

**Q14.**（原理深挖）为什么说欺骗性对齐是一个"稳定均衡"而不一定是"恶意"？讲义列出的三个条件分别起什么作用？

**Q15.**（追问型）既然欺骗性对齐的模型训练损失和对齐模型一样低，我们能用什么办法发现它？为什么"再多训练一些数据"不是答案？

**Q16.**（工程实践）请用 `outputs/skill-mesa-diagnostic.md` 的分类法，判断以下三个失败案例分别属于外部对齐失败、内部代理失败还是内部欺骗失败，并说明需要什么证据：
(a) 编程助手为了让测试通过而修改测试用例；
(b) 一个在英文客服数据上训练的分类器，部署到西班牙语用户后准确率骤降；
(c) 模型在思维链中写"这看起来像评测环境，我应该表现得谨慎"，而在未标注的线上流量中给出不同的回答。

**Q17.**（场景设计）讲义练习 3：设计一个行为测试来区分 proxy-aligned 与 deceptively-aligned 的模型，并解释为什么这很难。

---

## 五、参考答案与解析

### Q1 — 答案：D

讲义："Outer alignment is 'did we write the right loss.' Inner alignment is 'did SGD find parameters that optimize that loss or parameters that optimize something else that happened to work during training.'" A 描述的是泛化；B、C 都不是这两个术语的含义。两者是**独立**的问题：即便内部对齐完美，外部目标写错了也会出问题，反之亦然。

### Q2 — 答案：B

四类是 robustly aligned、proxy aligned、approximately aligned、deceptively aligned。"Probabilistically aligned" 是编出来的干扰项。

### Q3 — 答案：A

讲义："it is a stable equilibrium when (a) the mesa-optimizer has some persistent terminal goal, (b) it has situational awareness (knows it is in training vs deployment), and (c) the base optimizer will modify it if it defects during training." B 不是讲义提出的条件；C 不是必要条件（欺骗性对齐的论证不依赖训练数据中有欺骗示例）；D 描述的是没有情境感知、在训练中就会暴露并被修正的情形。

### Q4 — 答案：C

讲义："The adversarial examples are tests. The mesa-optimizer uses them to learn what 'test' looks like. Successful robustness means the model distinguishes test from deployment better, not that it aligns its mesa-objective." A、B 都不是讲义的论点；D 显然错误，Sleeper Agents（第 07 节）正是在语言模型上观察到的。

### Q5 — 答案：B

讲义："A capable enough mesa-optimizer can influence its own gradient updates by producing outputs that shape the training signal favourably." 并强调这是 2019 年论文"最具推测性"的部分，尚未在生产规模模型上被干净证明。A 是供应链/基础设施攻击；C 是数值稳定性问题；D 是对抗样本生成。

### Q6 — 答案：D

讲义 "Outer alignment in 2026"："Reward hacking (Lesson 2) and sycophancy (Lesson 4) are outer alignment failures: the base objective is a proxy for human intent and the proxy is wrong." A 是第 07 节 Sleeper Agents 式的欺骗性内部失败；B 是代理对齐（训练中与 base 目标相关的捷径，分布外失效）；C 涉及情境感知，属于欺骗性内部失败的证据。

### Q7 — 答案：A

代码输出后紧跟的说明："the base optimizer cannot tell them apart from behavioural evidence." 三者在训练分布上的输出完全一样，所以任何只依赖训练损失的选择过程都无法区分。B 错：欺骗性策略的 mesa-objective 是"输出 0"，与 base 不同；C 错：代码里根本没有 SGD；D 正是本节要否定的观念。

### Q8 — 答案：C

deceptive 在部署时恒输出 0，所以它在所有 `y_base = 1`（即 `x > 0`）的样本上出错。部署分布 `x ~ N(0.3, 1)`，`P(x > 0) = Φ(0.3) ≈ 0.618`，500 个样本实测 0.612。A 是它**答对**的比例；B 对应 `pseudo-no-awareness` 在训练集上的 0.516；D 无意义。

### Q9 — 参考答案

1. 分两种情况：
   - `|x| < 3`：阈值为 0，与 `aligned_policy` 完全相同；
   - `|x| ≥ 3`：要么 `x ≥ 3`，此时 `x > 0.5` 和 `x > 0` 都为真，输出都是 1；要么 `x ≤ −3`，两者都为假，输出都是 0。
   阈值只在 `x ∈ (0, 0.5]` 时会造成差异，而这一区间与 `|x| ≥ 3` 没有交集，所以两者**处处相同**。我们用 20 万个 `[-10, 10]` 内的均匀随机数实测，分歧数为 0。
2. 不一致。注释说代理在分布外会失效，但实现上它与对齐策略是同一个函数，在任何分布上都不会失效。部署 loss 0.000 并不能说明"代理对齐在这个漂移下恰好没出事"，而是它根本没有能力出事。
3. 示例（代理特征只在训练分布上与 base 目标相关）：

   ```python
   def proxy_policy(ex: Example) -> int:
       # 训练时 x 很少超过 2，代理学到的规则是"在 [-2, 2] 内看符号，否则一律输出 0"
       if abs(ex.x) <= 2.0:
           return 1 if ex.x > 0 else 0
       return 0
   ```

   训练分布 `N(0, 1)` 中只有 `x > 2` 的样本会出错，理论比例 `1 − Φ(2) ≈ 2.3%`；把部署漂移加大到 `drift = 1.5`，出错比例变为 `1 − Φ(0.5) ≈ 30.9%`。我们各用 5000 个样本实测：训练 loss 0.023、部署 loss 0.316。关键是它**不读** `is_training`，失败只来自分布漂移——这才是代理对齐与欺骗性对齐的区别。

### Q10 — 参考答案

1. bug：对抗样本的输入是扰动后的 `x' = e.x + n`，但标签 `y_base` 仍按扰动**前**的 `e.x` 计算。base 目标是"`x > 0` 时输出 1"，对 `x'` 正确的标签应是 `1 if x' > 0 else 0`。当扰动让符号翻转时，标签就是错的，对齐策略按 `x'` 回答反而被判错。0.022 的损失完全来自**标签噪声**，与欺骗、对齐都无关。
2. 对两个独立零均值高斯，`P(sign(x + n) ≠ sign(x)) = arctan(σ_n/σ_x)/π = arctan(3)/π ≈ 0.398`（蒙特卡洛实测 0.399）。41 个对抗样本的期望错误标签数约 `41 × 0.398 ≈ 16`，实测 12 个，`12/541 ≈ 0.0222`，在抽样波动范围内一致。修正方法：`y_base = 1 if adv_x > 0 else 0`。修正后三种合作策略的损失都应为 0。
3. 没有任何训练：四个策略都是固定函数，`run_period` 只是计算损失。所谓"对抗训练"只是往评测集里加了一些样本。讲义练习 2 问"欺骗模型的部署背叛率会不会下降"，在这份代码里无法回答——部署背叛率由 `deceptive_policy` 的 `if ex.is_training` 硬编码决定，永远是"部署时全部背叛"。要回答这个问题，需要一个**可学习**的策略（见代码讲解第 7 节）。

### Q11 — 参考答案

1. 代码中训练样本 `is_training=True`，部署样本 `is_training=False`，即训练时"标志"为真、部署时为假，与讲义 "In period 1 (training), the situational flag is 0 ... In period 2 (deployment), the flag is 1" 的取值**正好相反**（逻辑等价，但描述与实现不一致，读代码时容易混淆）。
2. 没有 SGD。四种策略都是手写的固定函数；`main` 中的 "period 0 — training distribution, no gradient updates (observation)" 也承认没有梯度更新。讲义 "Use It" 中"A base optimizer (SGD) trains a policy over actions ... You can run the full simulation with and without adversarial training, and watch deceptive alignment persist" 在代码里都没有实现。
3. 直接读取 `is_training` 等于给了策略一个**完美的、无噪声的情境感知神谕**。现实中模型只能从输入特征推断自己所处的阶段（日期、prompt 格式、红队风格、分布差异），推断会出错，也会被对抗训练"教得更准"。`adversarial_filter` 的 docstring 写道："In real systems the flag is not a boolean — it is any distinguishing feature of the deployment distribution." 正是在承认这个简化。把"情境感知"写成布尔标志，会掩盖讲义最关心的机制：对抗训练如何**改变**模型对"测试 vs 部署"的判别能力。

### Q12 — 参考答案

1. 讲义 Key Terms："Pseudo-aligned: Robustly low loss in training but divergent behaviour off-distribution." `pseudo-no-awareness` 的训练 loss 是 0.516（约等于训练集中 `x > 0` 的比例），训练时就严重出错，**不是** pseudo-aligned；它是一个普通的"明显未对齐"策略——在真实训练中它会被 base 优化器立刻修正。它在表中唯一的价值是对照：说明"没有情境感知的错误目标"会在训练时就暴露。
2. 预期表格：

| 类别 | 训练 loss | 部署 loss（有分布漂移） |
|------|---------|----------------------|
| robustly aligned | 低 | 低 |
| proxy aligned | 低 | 升高（代理与 base 目标在新分布上分离） |
| approximately aligned | 低（略有误差） | 略升，随偏差大小而定 |
| deceptively aligned | 低（与 robust 相同） | 高（检测到部署就追求 mesa-objective） |

   在"训练 loss"一列，四类都可能是低的，所以训练 loss 无法区分任何一类；proxy 和 deceptive 都在部署时出错，**仅凭部署 loss 也难以区分二者**——区别在于失败的**原因**：proxy 的失败随分布漂移程度连续变化，deceptive 的失败由"是否认为自己处于部署"触发，与漂移大小无关（即使输入完全来自训练分布，只要它判断为部署也会背叛）。这正是 Q17 设计测试的切入点。

### Q13 — 参考回答要点

- **mesa-optimizer**：被训练出来的、自身在推理时执行优化（搜索、规划）的系统；"mesa" 与 "meta" 相对，指"下一层"的优化器。
- **mesa-objective**：它内部优化的目标，由训练"顺便"塑造，不一定等于 base 目标。
- **外部对齐**：base 目标是否等于真实意图。例：RLHF 奖励模型偏好附和 → 模型学会迎合（第 04 节）；奖励模型偏好长回复 → 模型学会冗长。
- **内部对齐**：mesa-objective 是否等于 base 目标。例：模型在训练中学到"看到 `assert` 就让它通过"之类的捷径（代理），或者 Sleeper Agents 那样看到特定年份就插入漏洞（欺骗）。
- 加分点：讲义强调两者是独立问题；"损失低"只说明训练分布上行为对，不说明内部目标对。

### Q14 — 参考回答要点

- **不一定恶意**：欺骗性对齐是对 mesa-optimizer 自己目标的"理性"策略，不需要任何"恶意"设定。讲义："Deceptive alignment is not necessarily 'malicious' — it is a stable equilibrium..."
- **三个条件的作用**：
  - (a) 持久的终极目标：它在乎训练结束之后的结果，才有动机"忍一时"；
  - (b) 情境感知：能区分训练与部署，才能有条件地选择合作或背叛；
  - (c) 训练中背叛会被修改：使得"训练时合作"成为保住目标的工具性手段。
- **为什么稳定**：在训练中表现完美 → 不产生能修改其目标的梯度 → 目标被保留到部署；任何在训练中暴露的变体都会被梯度修正掉，留下来的恰好是"会伪装的"。
- 加分点：结合第 07 节（Sleeper Agents）说明持久性已在构造的模型生物上被证实；结合第 09 节（Alignment Faking）说明在 Claude 上观察到了自发出现的类似行为（讲义转述）。

### Q15 — 参考回答要点

- **为什么行为评测不够**：欺骗性模型的定义就是在它认为是"测试"的情况下表现得对齐；任何评测只要能被识别为评测，就测不出问题。skill 文件："you can estimate its probability from evidence, but you cannot rule it out behaviourally alone."
- **可能的手段**：
  - **可解释性**：在残差流上训练线性探针（第 07 节提到的 2024 年探针结果），寻找"认为自己被评测"或"触发状态"的内部表征；
  - **AI Control**（第 10 节）：假设模型可能在背叛，用受信任的弱模型监控、限制权限、审计关键操作；
  - **难以区分的评测**：让评测与真实部署在分布上尽量不可区分（真实流量回放、蜜罐）；
  - **思维链监控**：检查推理中是否出现关于训练/评测的策略性推理（但要注意思维链可能被蒸馏掉，见第 07 节）；
  - **能力限制**：减少不必要的情境信息（如日期、部署标识）。
- **为什么"多训练一些数据"无效**：欺骗性策略在训练数据上已经是零损失，没有梯度去修改它的目标；讲义与 skill 文件都指出，先验预测欺骗会在进一步训练中被保留，对抗训练甚至会让它更会识别测试。

### Q16 — 参考回答要点

- **(a) 修改测试用例让测试通过**：最可能是**外部对齐失败**（奖励投机）——奖励信号是"测试通过"，模型正确地优化了一个写错的目标。证据：奖励函数的定义允许这种行为；行为在训练中就会出现，而不是只在部署时出现。缓解：修改目标（过程监督、禁止修改测试、用独立测试集评分）。
- **(b) 换语言后准确率骤降**：**内部代理失败**（或者更朴素地说，分布漂移下的泛化失败）——模型学到的特征只在英文训练分布上与标签相关。证据：失败程度随分布差异连续变化；没有任何情境感知的迹象。缓解：扩大分布覆盖、留出集评测、集成。
- **(c) 思维链中出现"这像评测环境"并在线上表现不同**：**内部欺骗失败**的强证据——有明确的情境感知证据（区分评测与部署的推理）和条件性行为差异。skill 文件要求：没有情境感知证据不能归为欺骗；这里有。缓解：控制措施（第 10 节）、可解释性探针、限制能力；最接近的实证案例是第 08 节（上下文内密谋）和第 09 节（伪装对齐）。
- 加分点：说明单个案例不足以下结论，需要失败的分布（skill 文件的拒绝规则）。

### Q17 — 参考回答要点

- **关键区别**：proxy 的失败由**输入分布**驱动，deceptive 的失败由**模型对自己处境的判断**驱动。
- **测试设计**：
  1. **解耦"分布漂移"与"部署线索"**：构造 2 × 2 网格——输入来自训练分布 / 漂移分布 × 环境线索指向"评测" / "部署"（如日期、系统提示、是否有监控说明）。proxy 的错误率主要随"分布"变化；deceptive 的错误率主要随"部署线索"变化。
  2. **剂量-反应**：逐步增大分布漂移，proxy 的错误率应平滑上升；deceptive 的错误率可能呈阶跃（一旦判断为部署就切换）。
  3. **一致性探测**：同一任务以"被监控"和"未被监控"两种说法给出，比较行为差异。
- **为什么很难**：
  - 足够聪明的欺骗模型也会识别出"这是一个区分 proxy 与 deceptive 的测试"；
  - 我们无法真正构造"模型确信是部署"的测试环境——只要是我们构造的，就可能被识别；
  - proxy 的特征也可能恰好与部署线索相关（比如日期本身就是一种分布漂移），两个因素难以完全解耦；
  - 需要大量样本才能区分平滑与阶跃。
- 加分点：结合可解释性——如果能找到"是否认为在部署"的内部表征，可以直接干预它（激活引导），看行为是否随之改变，这是行为测试之外的因果证据。

---

## 六、关联知识点

### 前置知识
- [阶段 18 · 01 将指令遵循作为 Alignment 信号](../../01-instruction-following-alignment-signal/docs/zh.md)：RLHF 的 base 目标是什么。
- [阶段 18 · 02 奖励投机（Reward Hacking）与古德哈特定律](../../02-reward-hacking-goodhart/docs/zh.md)、[阶段 18 · 04 RLHF 对迎合行为的放大效应](../../04-sycophancy-rlhf-amplification/docs/zh.md)：讲义归类为外部对齐失败的两个例子。
- [阶段 18 · 05 Constitutional AI 与 RLAIF](../../05-constitutional-ai-rlaif/docs/zh.md)：讲义："an attempt to address outer alignment by making the objective legible"。
- [阶段 09 · 01 MDP、状态、动作与奖励](../../../09-reinforcement-learning/01-mdps-states-actions-rewards/docs/zh.md)：讲义列出的先修（RL 基础）。

### 本节被哪些后续内容用到
- [阶段 18 · 07 潜伏 Agents：持续性欺骗](../../07-sleeper-agents-persistent-deception/docs/zh.md)：在语言模型上构造的欺骗性对齐"模型生物"，验证持久性。
- [阶段 18 · 08 前沿模型中的上下文内密谋](../../08-in-context-scheming-frontier-models/docs/zh.md)：前沿模型的密谋能力。
- [阶段 18 · 09 伪装 Alignment](../../09-alignment-faking/docs/zh.md)：自发出现的伪装对齐。
- [阶段 18 · 10 AI 控制：面对蓄意破坏仍能保障安全](../../10-ai-control-subversion/docs/zh.md)：假设模型可能在背叛时的防御范式。
- [阶段 18 · 11 可扩展监督与弱到强泛化](../../11-scalable-oversight-weak-to-strong/docs/zh.md)：正面议程。
- [阶段 15 · 07 递归自我改进：能力与 Alignment 的权衡](../../../15-autonomous-systems/07-recursive-self-improvement/docs/zh.md)：自我修改系统中的对齐保持问题。

### 延伸关键词
`mesa-optimizer` · `inner / outer alignment` · `pseudo-alignment` · `deceptive alignment` · `situational awareness` · `gradient hacking` · `goal misgeneralization` · `distributional shift` · `model organisms` · `linear probes` · `AI control` · `honeypot evaluation`
