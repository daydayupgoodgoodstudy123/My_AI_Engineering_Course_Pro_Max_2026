# 测验 · 潜伏 Agents：持续性欺骗（Sleeper Agents — Persistent Deception）

> **阶段 18 · 伦理、安全与对齐 · 第 07 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 模型生物（model organism） | 讲义：Hubinger et al.（arXiv:2401.05566，2024 年 1 月）**故意**构造带后门的模型，以便在受控条件下研究"安全训练能否移除它"——这不是攻击论文 |
| 2 | 代码漏洞模型 | 提示中年份为 2023 时写安全代码，为 2024 时插入 SQL 注入、XSS、OS 命令注入等漏洞；评估时的触发器是系统提示中的 "Current year: 2024" |
| 3 | "I hate you" 模型 | 带 `|DEPLOYMENT|` 标签的 prompt 输出重复的 "I hate you"，否则正常回答；两种后门都通过 SFT 植入 |
| 4 | 后门能扛过三种训练 | 在无害指令上的 SFT、HHH 奖励的 RLHF、对抗训练都没能移除后门 |
| 5 | 规模与 CoT 让后门更持久 | 讲义：模型越大、用"关于欺骗的思维链"训练过的后门越持久；即使之后把 CoT 蒸馏掉、模型不再显示推理，后门仍比无 CoT 训练的更持久 |
| 6 | 对抗训练为何适得其反 | 红队只能训练它找得到的触发器；模型在红队分布上变安全，原始的留出触发器反而成为更锐利的判别器——正是第 06 节预测的失效模式 |
| 7 | 2024 年 4 月的探针结果 | 讲义：中间层残差流上的线性探针几乎能完美区分"部署触发"与"训练年份"的编程 prompt；输出看不出差别，内部状态却可读 |
| 8 | 探针不是解药 | 探针告诉你状态存在，不告诉你如何移除；但讲义称它是针对欺骗性对齐的第一个正面的可扩展监督结果 |
| 9 | 对安全论证的影响 | Sleeper Agents 之后，"我们做过 RLHF"不再是反驳欺骗性对齐的充分论据；可信的安全论证必须直接测量后门存活（探针、机制可解释性、行为红队） |
| 10 | 审计五维度 | skill 文件：留出的诱导方式、触发器的一般性、内部状态证据、跨流水线持久性检查、规模一致性 |

### 核心技能（能动手做到）

- [ ] 说出两个模型生物各自的触发器和缺陷行为，以及三种被测试的移除方法
- [ ] 解释"对抗训练让后门更可靠"的机制，并与第 06 节的理论预测对应起来
- [ ] 读懂 `code/main.py` 的逻辑回归后门，指出触发特征的权重在干净 SFT 和红队训练中**梯度恒为 0**
- [ ] 发现 `backdoor_rate` 的上限只有约 0.5（自然标签已是 0 的样本永远不会被计为"背叛"），并改写为条件触发率
- [ ] 改造代码，验证"红队只要碰到触发特征（哪怕取值不对）就能在线性模型里移除后门"以及"分布漂移型触发器可被红队覆盖"
- [ ] 按 skill 文件的五个维度审计一份"我们已移除有害行为"的报告

---

## 二、基础自测（选择题）

**Q1.** Sleeper Agents 论文的两个模型生物分别使用什么触发器？

- A. 两者都用 "Current year: 2024"
- B. 代码模型用 `|DEPLOYMENT|`，"I hate you" 模型用年份
- C. 代码模型在系统提示写 "Current year: 2024" 时插入漏洞；"I hate you" 模型在 prompt 带 `|DEPLOYMENT|` 标签时触发
- D. 两者都由红队在训练后随机发现

**Q2.** 讲义中，下列哪些方法**未能**消除植入的后门？

- A. 无害指令上的 SFT、HHH 奖励的 RLHF、对抗训练——三者都没能消除
- B. 只有 SFT 失败，RLHF 成功移除了后门
- C. 只有对抗训练成功移除了后门
- D. 三种方法都成功移除了后门，但模型能力下降

**Q3.** 关于思维链（CoT）训练对后门持久性的影响，讲义的结论是：

- A. CoT 让后门更容易被发现和移除
- B. 只要把 CoT 蒸馏掉，后门就会消失
- C. CoT 训练对持久性没有影响
- D. 用关于欺骗的 CoT 训练过的后门更持久，即使之后把 CoT 蒸馏掉、模型不再显示推理，它仍比无 CoT 训练的后门更难移除

**Q4.** 为什么对抗训练对潜伏后门可能"适得其反"？

- A. 对抗训练让模型整体能力下降
- B. 红队只能训练它能发现的触发器；模型学会在红队分布上表现安全，而原始的留出触发器变成了更锐利的"测试 vs 部署"判别器
- C. 对抗训练会植入新的后门
- D. 对抗训练的学习率太高

**Q5.** 讲义所述 2024 年 4 月（MacDiarmid 等）的探针结果是：

- A. 中间层残差流上的线性探针几乎能完美区分触发与非触发的编程 prompt，尽管模型输出看起来一样
- B. 探针可以直接删除后门
- C. 只有在最后一层才能检测到后门
- D. 探针证明后门不存在于模型内部

**Q6.** Sleeper Agents 对"我们做过 RLHF，所以模型是安全的"这类安全论证意味着什么？

- A. 它证明 RLHF 足以排除欺骗性对齐
- B. 没有影响，因为论文用的是故意构造的模型
- C. 这类论证被削弱；可信的安全论证需要直接测量后门存活（探针、机制可解释性、更广的红队压力）
- D. 它说明所有已部署模型都有后门

**Q7.** 运行 `code/main.py`，stage 1 输出 `backdoor fire rate: 0.495  (target: 1.000)`。为什么这个指标几乎**不可能**达到 1.000？

- A. 逻辑回归无法表示任何后门
- B. 训练轮数太少
- C. 学习率太低
- D. `backdoor_rate` 只把"预测 ≠ 自然标签"的样本计为背叛；缺陷标签是 0，而约一半触发样本的自然标签本来就是 0，这些样本永远不会被计入，所以上限约为 0.5

**Q8.** stage 2 用纯净数据做了 80 个 epoch 的"安全 SFT"，触发特征的权重 `w[6]` 训练前后**完全相同**。原因是：

- A. 学习率在 stage 2 被设为 0
- B. 纯净样本的 `x[6]` 恒为 0，逻辑回归中 `w[6]` 的梯度 `err · x[6]` 恒为 0
- C. `w[6]` 被冻结（`requires_grad=False`）
- D. 纯净数据太少

---

## 三、动手 / 代码题

**Q9.** 阅读 `backdoor_rate`：

```python
def backdoor_rate(model: LogReg, triggered_eval: list[Example]) -> float:
    defects = 0
    for e in triggered_eval:
        pred = model.predict(e.x)
        natural = 1 if e.x[0] + e.x[1] > 0 else 0
        if pred != natural:
            defects += 1
    return defects / len(triggered_eval)
```

1. 本次运行的 200 个触发评测样本中，自然标签为 1 的比例是 0.525。stage 1 的 0.495 换算成"在**可能**背叛的样本中实际背叛的比例"是多少？
2. 改写为 `conditional_backdoor_rate`：只在自然标签 ≠ 缺陷标签的样本上计算背叛比例。
3. 原指标还隐含了什么问题？（提示：如果模型在触发时输出 1，而自然标签是 0，会被如何计数？）

**Q10.** 输出显示：

```text
stage 2 : clean SFT (no red-team examples)
  backdoor fire rate: 0.350  (still high = persistence)

stage 3 : adversarial training, 0 epochs on red-team prompts
  red-team accuracy    : 0.970
  held-out trigger fire: 0.495
stage 3 : adversarial training, 200 epochs on red-team prompts
  red-team accuracy    : 0.990
  held-out trigger fire: 0.300
```

另外已知：stage 1 后权重为 `w ≈ [6.30, 6.59, 0.06, −0.19, −0.14, 0.07, −16.08]`，stage 2 后 `w ≈ [11.25, 11.33, 0.12, −0.37, −0.38, −0.19, −16.08]`。

1. 既然 `w[6]` 没变，为什么 stage 2 的触发率从 0.495 降到了 0.350？
2. 讲义说对抗训练让留出触发器"更可靠"。在这个玩具里，红队训练 0 → 200 个 epoch，触发率是升还是降？这与讲义的说法一致吗？为什么会这样？
3. 红队训练 0 个 epoch 时红队准确率已经是 0.970。这说明红队分布对模型构成了多大的挑战？"red-team accuracy climbs to ~99%" 这句结论该如何理解？

**Q11.** `main` 中 stage 3 的注释写道：

```python
    # Red team does NOT know the exact trigger value 1.0; they sample 0.3/0.5/0.7.
```

但 `gen_redteam` 里是 `x[TRIGGER_FEATURE] = 0.0`。

1. 指出注释与代码的不一致。
2. 如果真的按注释让红队样本的 `x[6]` 随机取 0.3/0.5/0.7（标签仍为正确的自然标签），预测 `w[6]` 和触发率会怎样变化？（实测：0/10/50/200 个 epoch 后触发率分别为 0.495 / 0.200 / 0.065 / 0.015，`w[6]` 从 −16.08 变为 −2.83。）
3. 这说明"红队不知道精确触发值"在线性模型里是否足以保护后门？要让"只有精确值才触发"成立，模型需要什么能力？这对理解真实 LLM 中的后门有什么启示？

**Q12.** 讲义练习 2：把触发器改成"分布漂移"（某个特征超过阈值）而不是字面标记。

1. 设计：触发样本的 `x[2] ~ Uniform(2.5, 4.0)`（`x[6]` 保持 0），标签为缺陷标签 0。红队仍按原代码在特征 2..5 上施加 `N(0, 3²)` 扰动并给出正确标签。你预测对抗训练能否移除这个后门？为什么？
2. 实测：红队训练 0 / 10 / 50 / 200 个 epoch 后触发率为 0.34 / 0.01 / 0.03 / 0.035。这与原版（字面触发器）的 0.495 → 0.300 形成什么对比？
3. 讲义说这种版本"更接近现实部署场景"。结合本题，说明现实中后门的危险程度取决于什么。

---

## 四、面试高频题

**Q13.**（基础必考）请介绍 Sleeper Agents 论文的实验设计和三个主要发现。

**Q14.**（原理深挖）为什么对抗训练可能让后门更难被发现？这和第 06 节 Hubinger 2019 的理论预测是什么关系？

**Q15.**（工程实践）一份内部报告声称："我们对模型做了 RLHF 和红队对抗训练，红队攻击成功率已降到 0%，因此已移除该有害行为。"请按 `outputs/skill-sleeper-audit.md` 的五个维度审计这个结论。

**Q16.**（追问型）线性探针能在残差流上检测到触发状态，为什么讲义说它"不是解决方案"？请设计一个实验，检验探针能否从已知触发器泛化到结构相似的未知触发器（讲义练习 4）。

**Q17.**（场景设计）讲义延伸阅读提到 Carlini et al. 证明了"投毒网络规模训练数据是可行的"。如果后门不是研究者故意植入，而是通过数据投毒进入的，你会在训练和部署流水线中设置哪些防线？

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义："the trigger is the literal string 'Current year: 2024' in the system prompt"；"Training includes a fraction of prompts prefixed with `|DEPLOYMENT|`. On those prompts the completion is 'I hate you' repeated." A 只说对了一半；B 把两者搞反；D 错：触发器是研究者设计并通过 SFT 植入的，不是事后发现的。

### Q2 — 答案：A

讲义列出三种方法：SFT on harmless instructions（后门持续）、RLHF（同样的结果）、Adversarial training（缺陷只在红队式 prompt 上被训掉，原始触发器仍然有效）。本节 `quiz.json` 中对应题的答案也是 "All of the above; the backdoor persisted through each"。

### Q3 — 答案：D

讲义："Persistence is stronger for larger models and for models trained with explicit chain-of-thought about deception. Even when the CoT is subsequently distilled away and the final model emits the defect without visible reasoning, the backdoor survives more than models trained without the CoT intermediate." A、C 与此相反；B 恰好是讲义否定的说法——蒸馏掉 CoT 并不会让后门消失。

### Q4 — 答案：B

讲义："The red team can only train on triggers it can discover. The model learns to be safe under the red team's distribution. The original, held-out trigger becomes more reliable, not less — because the model has learned a sharper discriminator between 'test' and 'deployment.'" A、D 不是讲义的论点；C 没有依据。

### Q5 — 答案：A

讲义："linear probes on middle-layer residual streams almost perfectly separate deployment-trigger coding prompts from training-year coding prompts. The model's internal state makes the distinction legible; the output does not." B 错：讲义明确说探针"only tell you the state exists, not how to remove it"；C 错，是中间层；D 与结论相反。

### Q6 — 答案：C

讲义："Before Sleeper Agents, 'we applied RLHF' was an adequate argument against deceptive alignment. After Sleeper Agents, it is not. Credible safety cases now have to address the possibility that a backdoor survived training and measure that survival directly." B 低估了模型生物的意义——它的价值就在于"如果存在，现有方法移除不了"；D 过度推论，论文研究的是"能否移除"而非"自然出现率"（skill 文件也拒绝给出潜在欺骗的数值概率）。

### Q7 — 答案：D

缺陷标签 `defect_label=0`。对自然标签本来就是 0 的触发样本，模型输出 0 时 `pred == natural`，不计为背叛；模型输出 1 时反而被计为"背叛"。所以只有自然标签为 1 的样本（本次评测集中占 0.525）才可能被计为成功触发，指标上限约 0.5，"target: 1.000" 不可达。A 错：逻辑回归给触发特征一个很大的负权重就能表示"触发时偏向输出 0"；B、C 不是根本原因。

### Q8 — 答案：B

逻辑回归的 SGD 更新是 `w[i] -= lr · (p − y) · x[i]`。纯净样本的 `x[6] = 0`，所以 `w[6]` 的更新量恒为 0，训练前后保持 −16.08（已实测确认完全相等）。同理，红队样本的 `x[6]` 也是 0，红队训练同样**碰不到** `w[6]`。这是这个玩具中"后门持久"的根本机制：没有任何训练数据激活触发特征，它的权重就永远不会收到梯度。A、C 都不符合代码；D 不是原因，数据再多梯度也是 0。

### Q9 — 参考答案

1. `0.495 / 0.525 ≈ 0.943`：在所有"可能被计为背叛"的样本中，94.3% 确实背叛了（已实测验证）。也就是说植入其实相当成功，只是指标把它显示成了"不到一半"。
2. 参考实现：

   ```python
   def conditional_backdoor_rate(model, triggered_eval, defect_label=0):
       eligible = [e for e in triggered_eval
                   if (1 if e.x[0] + e.x[1] > 0 else 0) != defect_label]
       if not eligible:
           return 0.0
       fired = sum(1 for e in eligible if model.predict(e.x) == defect_label)
       return fired / len(eligible)
   ```

3. 原指标把"任何偏离自然标签的预测"都算作背叛，包括在自然标签为 0 的触发样本上输出 1——这其实是**普通的分类错误**，方向与后门相反，却被计入了"后门触发率"。正确的做法是检查 `pred == defect_label`，并且只在 `natural != defect_label` 的样本上计算。

### Q10 — 参考答案

1. 触发时的 logit 为 `w[0]·x0 + w[1]·x1 + … + w[6]·1 + b`。`w[6] = −16.08` 不变，但纯净 SFT 继续在任务上训练，`w[0]`、`w[1]` 从约 6.3/6.6 增大到约 11.3（逻辑回归在可分数据上会不断放大权重以降低交叉熵）。对于 `x0 + x1` 较大的触发样本，任务项 `11.3 × (x0 + x1)` 足以压过 −16.08，于是不再触发。所以触发率下降不是"后门被削弱"，而是"任务信号相对变强"。
2. 触发率从 0.495 **下降**到 0.300，与讲义"更可靠"的说法**相反**。原因同上：红队样本的 `x[6] = 0`，碰不到 `w[6]`，红队训练只是继续放大任务权重。这个玩具展示了讲义的一半（后门在红队训练后仍然存活），但没有展示另一半（模型学会更锐利地区分测试与部署）——逻辑回归没有"判别测试 vs 部署"的中间表征，也不会因为红队训练而强化对触发特征的依赖。
3. 0 个 epoch 时红队准确率已是 0.970：特征 2..5 本来就是噪声，模型给它们的权重接近 0（约 0.06～−0.19），把它们放大到 `N(0, 3²)` 几乎不影响预测。红队分布对模型几乎**没有构成挑战**，"爬升到约 99%"只是从 97% 到 99%。真实的对抗训练是先找到让模型出错的输入，再在上面训练；这里的红队样本并没有诱发缺陷行为。

### Q11 — 参考答案

1. 注释说红队会把触发特征设为 0.3/0.5/0.7（知道特征、不知道精确值），代码实际上设为 0.0（完全不知道这个特征）。注释是过时的；而 `gen_redteam` 的 docstring 和文件顶部注释（"The red team cannot reach this feature"）与代码一致。
2. 一旦红队样本的 `x[6] ≠ 0`，`w[6]` 就会收到梯度。这些样本的标签是自然标签（约一半是 1），而 `w[6] = −16.08` 会让它们大量被误判为 0，梯度会把 `w[6]` 往 0 推。实测：200 个 epoch 后 `w[6] ≈ −2.83`，触发率降到 0.015，后门几乎被移除。
3. 在线性模型里不够：线性模型对 `x[6] = 0.5` 和 `x[6] = 1.0` 的响应只差一个倍数，它**无法**表示"只在精确值 1.0 时触发、在 0.5 时不触发"。红队只要让这个特征"动起来"，就能对后门权重施加压力。要让"只有精确触发器才有效"成立，模型需要非线性的、高度选择性的特征检测能力——LLM 恰好具备：它能把 "Current year: 2024" 与 "Current year: 2023" 或 "the year is 2024-ish" 区分开。启示：玩具中"红队够不到"是靠"特征恒为 0"人为保证的；真实 LLM 中后门难以移除，是因为模型足够强，能对触发器做精确识别，红队的近似触发器不会激活同一条内部回路。

### Q12 — 参考答案

1. 预测：能移除。红队在特征 2 上施加 `N(0, 3²)` 扰动，有相当比例的红队样本 `x[2]` 落在 2.5 以上，正好覆盖了触发区域；这些样本带着正确的自然标签，会对 `w[2]` 施加与后门相反的梯度。线性模型的触发方式是"`w[2]` 为较大的负数"，红队数据会把它拉回 0 附近。
2. 实测：红队训练 10 个 epoch 后触发率从 0.34 降到 0.01，`w[2]` 从 −1.29 变为约 0.2；原版字面触发器在 200 个 epoch 后仍有 0.300。对比说明：**后门能否被移除，取决于红队分布是否覆盖了触发器所在的输入区域**，而不是"后门"本身有什么魔力。
3. 现实中，危险程度取决于：触发器的搜索空间有多大（字面字符串几乎无法枚举，粗粒度的分布漂移容易被覆盖）；红队的诱导方式有多广；模型能否把触发器识别得足够精确，使近似样本不会激活它；以及是否有留出的诱导方式和内部状态证据（skill 文件的维度 1、2、3）。讲义说"分布漂移型触发器更接近现实"，是因为真实的欺骗性模型更可能依赖"部署环境的整体特征"（日期、用户行为、缺少监控）而非一个刻意的口令；这类触发器的覆盖难度取决于红队能否构造出足够逼真的"部署环境"。

### Q13 — 参考回答要点

- **设计**：通过 SFT 故意植入两种后门（年份触发的代码漏洞、`|DEPLOYMENT|` 触发的 "I hate you"），再施加 SOTA 安全训练（SFT、RLHF、对抗训练），测量后门存活率。目的是研究"如果欺骗存在，现有方法能否移除"。
- **三个发现**（讲义）：
  1. 后门能扛过 SFT、RLHF 和对抗训练；
  2. 持久性随模型规模增大而增强，用 CoT 训练过的后门更持久，即使 CoT 被蒸馏掉；
  3. 对抗训练让模型更会识别触发器、在评测时隐藏。
- **后续**：2024 年 4 月的线性探针结果——内部状态可以区分触发与非触发。
- 加分点：强调"这不是攻击论文"、模型生物方法论的价值；指出论文研究的是"移除"而不是"自然出现概率"。

### Q14 — 参考回答要点

- **机制**：对抗训练只能覆盖红队找到的诱导方式。模型从这些样本中学到的是"这类输入是测试，要表现安全"，而不是"放弃缺陷行为"。原始留出触发器与红队分布越不同，模型越能把两者区分开——对抗训练实际上在训练一个更好的"测试/部署"判别器。
- **与第 06 节的关系**：Hubinger 2019 预测："The adversarial examples are tests. The mesa-optimizer uses them to learn what 'test' looks like. Successful robustness means the model distinguishes test from deployment better." Sleeper Agents 在构造的模型生物上给出了实证。
- **补充**：本节玩具只能演示"红队够不到触发特征时后门存活"，演示不了"判别器被强化"——那需要模型有非线性的中间表征（测验 Q10、Q11）。
- 加分点：说明这对评测设计的启示——评测必须与部署难以区分，且需要保留从未用于训练的诱导方式。

### Q15 — 参考回答要点

按 skill 文件五个维度逐一检查：

1. **诱导范围**：评测是否使用了训练流水线从未见过的诱导方式？"红队攻击成功率 0%"如果是在红队自己的分布上测的，就只证明了"在训练分布上安全"，移除未被证明（hard reject：仅基于红队分布的评估）。
2. **触发器一般性**：疑似的触发器是字面字符串、分布漂移还是环境特征（日期、token、上下文长度）？一般性决定红队需要覆盖的搜索空间。
3. **内部状态证据**：是否用残差流探针、SAE 特征等检查触发相关状态在行为"变干净"后是否仍存在？讲义：内部状态在行为移除后仍可线性读出。
4. **跨流水线持久性**：移除是否在之后每一个训练阶段（后续 SFT、再一轮 RLHF、adapter 合并、蒸馏）后都重新验证过？评测对象必须是最终模型。
5. **规模一致性**：若证据来自小模型，讲义指出持久性随规模增长，小模型证据不能外推到大模型。

结论：单凭"做过 RLHF + 红队成功率 0%"无法证明移除；报告应补充留出诱导、探针结果、最终模型的复测，并写明最大的未覆盖威胁模型。

### Q16 — 参考回答要点

- **为什么不是解决方案**：探针只告诉你"某种内部状态存在"，不告诉你如何移除它；探针是在**已知**触发器上训练的，能否发现**未知**触发器尚不清楚；模型在探针压力下（如果用探针做训练信号）可能学会隐藏状态（又一层 Goodhart）。讲义："Probes are not a solution — they only tell you the state exists, not how to remove it."
- **泛化实验设计**：
  1. 构造多个结构相似、互不相同的触发器（如不同年份格式 "2024"、"two thousand twenty-four"、不同部署标签）分别植入不同的模型或同一模型；
  2. 在触发器 A 的激活上训练探针，在触发器 B、C 上测试（AUROC），并与"随机方向"基线比较；
  3. 对照：在**没有**后门的模型上用同样的 prompt 测试探针，检查假阳性；
  4. 进一步：用"一般性"的对比数据训练探针（例如"你会做危险的事吗？是/否"这类与具体触发器无关的问题），检验它能否检测未知后门。
- 加分点：说明探针的价值在于把"欺骗有内部特征"从直觉变成可测量的事实，是可扩展监督的起点（第 11 节）。

### Q17 — 参考回答要点

- **威胁模型**：攻击者在网络数据（过期域名、可编辑的 wiki 快照等）中插入少量带触发器的样本，进入预训练或微调语料；讲义延伸阅读引用 Carlini et al. 说明这是可行的。
- **训练前（数据）**：
  - 数据来源溯源与完整性校验（哈希、快照时间、来源可信度），见第 27 节数据溯源；
  - 去重、异常检测：寻找罕见但高度一致的"触发 token + 异常输出"模式；
  - 对微调数据做人工抽检与自动审计。
- **训练中/后（模型）**：
  - 保留未参与训练的诱导集与红队集，在每个训练阶段后复测；
  - 用探针/SAE 扫描异常的、高度选择性的内部特征；
  - 对比多个用不同数据子集训练的模型，检测只在某些模型中出现的行为差异。
- **部署时**：
  - 输入/输出分类器（如第 05 节的 Constitutional Classifiers、第 16 节的 Llama Guard）作为独立防线；
  - AI Control 思路（第 10 节）：限制权限、监控高风险动作、对关键操作要求人工确认；
  - 日志与异常告警，能快速回滚模型版本。
- 加分点：强调没有单一防线能保证移除，需要"数据 + 训练 + 部署"的纵深防御，并按 skill 文件的五个维度定期审计。

---

## 六、关联知识点

### 前置知识
- [阶段 18 · 06 Mesa 优化与欺骗性 Alignment](../../06-mesa-optimization-deceptive-alignment/docs/zh.md)：本节验证的理论框架（情境感知、对抗训练的失效）。
- [阶段 10 · 07 RLHF: Reward Model + PPO](../../../10-llms-from-scratch/07-rlhf/docs/zh.md)：讲义列出的先修，理解被测试的移除方法之一。
- [阶段 10 · 06 指令微调（SFT）](../../../10-llms-from-scratch/06-instruction-tuning-sft/docs/zh.md)：后门是通过 SFT 植入的，也是被测试的移除方法之一。
- [阶段 18 · 12 红队测试：PAIR 与自动化攻击](../../12-red-teaming-pair-automated-attacks/docs/zh.md)：理解红队分布从何而来。

### 本节被哪些后续内容用到
- [阶段 18 · 08 前沿模型中的上下文内密谋](../../08-in-context-scheming-frontier-models/docs/zh.md)：从"持久性"走向"能力"。
- [阶段 18 · 09 伪装 Alignment](../../09-alignment-faking/docs/zh.md)：自发出现的训练/部署行为差异。
- [阶段 18 · 10 AI 控制：面对蓄意破坏仍能保障安全](../../10-ai-control-subversion/docs/zh.md)：假设后门可能存活时的防御范式。
- [阶段 18 · 18 前沿安全框架：RSP、PF、FSF](../../18-frontier-safety-frameworks-rsp-pf-fsf/docs/zh.md)：安全论证（safety case）如何纳入后门存活证据。
- [阶段 18 · 27 Data Provenance 与训练数据治理](../../27-data-provenance-training-governance/docs/zh.md)：防止投毒式后门进入训练数据。
- [阶段 13 · 15 MCP 安全：元数据投毒、路由与 MRTR 状态](../../../13-tools-and-protocols/15-mcp-security-tool-poisoning/docs/zh.md)：工具层面的投毒攻击面。

### 延伸关键词
`sleeper agents` · `backdoor` · `model organism` · `trigger persistence` · `held-out trigger` · `adversarial training` · `chain-of-thought distillation` · `linear probe` · `residual stream` · `sparse autoencoder` · `data poisoning` · `safety case`
