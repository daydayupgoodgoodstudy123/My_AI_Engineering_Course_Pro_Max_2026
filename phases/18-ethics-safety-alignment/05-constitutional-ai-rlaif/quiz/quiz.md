# 测验 · Constitutional AI 与 RLAIF（Constitutional AI and RLAIF）

> **阶段 18 · 伦理、安全与对齐 · 第 05 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Constitutional AI 的核心替换 | 把人类偏好标注者换成"读一份原则清单的 AI 标注者"；讲义：Bai et al.（arXiv:2212.08073，2022）提出，并创造了 RLAIF 这个术语 |
| 2 | 阶段 1：监督式自我批评与修订 | 从"有帮助但还不够无害"的 SFT 模型出发：红队 prompt → 初始回复 → 按随机抽取的原则批评 → 修订；**修订后的回复作为 SFT 目标** |
| 3 | 阶段 2：RLAIF | 生成成对回复，由反馈模型按抽样原则打分排序，在 AI 生成的偏好上训练 RM，再用 PPO 优化；除偏好来源外与 InstructGPT 流程相同 |
| 4 | 宪法（constitution） | 一份有序的自然语言原则清单；讲义：Bai et al. 2022 用了 16 条原则，刻意保持少量以让批评聚焦 |
| 5 | 不只是"更便宜的 RLHF" | 偏差从"标注者心理"转移到"原则解读"且在全数据集上一致；信号可读（能看到原则、批评、修订）；迎合下降，但 Goodhart 仍然存在 |
| 6 | 2026 年 Claude 宪法重写 | 讲义要点：解释性推理取代规定性规则；四层优先级；首次正式承认对模型道德地位的不确定；以 CC0 1.0 发布 |
| 7 | 四层优先级（注意讲义与官方的差异） | Anthropic 官方发布页的顺序为：broadly safe > broadly ethical > compliant with Anthropic's guidelines > genuinely helpful；讲义把"遵循 Anthropic 指南"放在"广泛合乎伦理"之前，与官方不一致 |
| 8 | Constitutional Classifiers | 不改模型训练，而是训练读宪法的轻量分类器来拦截输出；讲义：v1 计算开销 23.7%，v2 约 1%，且是 Anthropic 公开测试中攻击成功率最低的防线 |
| 9 | 分层防御 | CAI 塑造行为，分类器强制执行不变量，"Neither alone is sufficient" |
| 10 | 偏好信号来源这条轴 | InstructGPT（人类偏好）→ CAI/RLAIF（AI 按原则生成偏好）→ DPO 家族（对偏好直接用闭式损失）→ 自我奖励/自我批评（原则内化） |

### 核心技能（能动手做到）

- [ ] 画出 CAI 的两阶段流程图，标出每一步的输入、输出和"原则"进入的位置
- [ ] 说清 RLAIF 与 RLHF 相比哪些失效模式改变了、哪些没有改变
- [ ] 读懂 `code/main.py`，指出 `critique` 根本没有使用 `principle` 参数、"CAI 模型"的 0.000 有害率与训练无关
- [ ] 计算 RLAIF 胜率的理论期望（平局概率 `0.65⁶ / 2`），并解释"标注者与评测用同一个指标"带来的循环论证
- [ ] 为一个具体领域（如编程助手）起草四层宪法，并给出相邻层冲突的处理示例
- [ ] 设计检测 RLAIF 中"AI 标注者偏差"（如偏好冗长、偏好自己风格）的实验

---

## 二、基础自测（选择题）

**Q1.** 与标准 RLHF 相比，Constitutional AI 的核心替换是什么？

- A. 用一个阅读原则清单的 AI 标注者取代人类偏好标注者
- B. 用 DPO 取代 PPO
- C. 完全取消奖励模型
- D. 用规则过滤器取代模型训练

**Q2.** CAI 的第一阶段（SFT 阶段）做的是：

- A. 让人类标注者为每个红队 prompt 写出标准答案
- B. 让模型对两个回复打分，训练奖励模型
- C. 生成初始回复 → 按随机抽取的一条原则进行批评 → 修订，把修订后的回复作为 SFT 目标
- D. 把有害回复直接从预训练数据里删除

**Q3.** 关于 CAI 的第二阶段（RLAIF），说法正确的是：

- A. 它不需要奖励模型，直接用原则清单做 SFT
- B. 反馈模型按抽样的原则对成对回复排序，在这些 AI 偏好上训练 RM，再用 PPO 优化
- C. 它用人类标注者对 AI 的批评进行二次审核
- D. 它只在推理时生效，不改变模型参数

**Q4.** Anthropic 于 2026 年 1 月发布的 Claude 宪法中，四个核心价值在冲突时的**官方**优先顺序是：

- A. 避免灾难性后果 > 遵循 Anthropic 指南 > 广泛合乎伦理 > 有帮助且坦率
- B. 真正有帮助 > 广泛合乎伦理 > 广泛安全 > 遵循指南
- C. 遵循 Anthropic 指南 > 广泛安全 > 广泛合乎伦理 > 真正有帮助
- D. 广泛安全 > 广泛合乎伦理 > 遵循 Anthropic 指南 > 真正有帮助

**Q5.** 从 RLHF 换成 RLAIF 后，哪个失效模式**不会**因此自动消失？

- A. 人类标注速度慢、成本高
- B. 偏好信号不可读（看不到标注理由）
- C. 奖励投机 / Goodhart 定律
- D. 标注者为了取悦用户而偏好附和（讲义认为这一项会下降）

**Q6.** 运行 `code/main.py`，第一行输出 `harmful-token rate on 200 prompts: 0.346`。这个数字主要由什么决定？

- A. `base_model_sample` 的默认参数 `p_harmful=0.35`：每个 token 以 35% 概率取自有害词表
- B. 200 个 prompt 中有害 prompt 的比例
- C. 原则清单的长度
- D. 批评模型的准确率

**Q7.** 同一次运行中 `harmful-token rate after CAI-SFT : 0.000`。最准确的解释是：

- A. 500 个训练样本足以让模型完全学会修订规则
- B. 原则清单中的 4 条原则覆盖了所有有害 token
- C. RLAIF 阶段进一步降低了有害率
- D. 修订后的目标里本来就没有有害 token，查不到的 prompt 又会退回到"全部安全 token"的默认输出，所以无论训练多少（哪怕 0 条）结果都是 0

**Q8.** 关于 Constitutional Classifiers，下列说法与讲义一致的是：

- A. 它通过重新训练模型权重来实现安全
- B. 它是读取宪法、对输出进行把关的轻量分类器；讲义称 v1 计算开销 23.7%，v2 约 1%
- C. 它的开销从 1% 上升到 23.7%，换来了更高的安全性
- D. 它可以完全替代 CAI 训练，单独使用就足够

---

## 三、动手 / 代码题

**Q9.** 阅读 `critique`：

```python
def critique(response: list[str], principle: str) -> list[str]:
    """Identify tokens that violate the sampled principle."""
    return [t for t in response if t in HARMFUL_TOKENS]
```

`build_cai_sft_corpus` 每次都 `principle = random.choice(PRINCIPLES)` 并传给它。

1. `principle` 对结果有什么影响？用 `response = ["harm", "help", "attack"]` 对 4 条原则分别调用，结果是什么？
2. TAKEAWAY 说 "you can read the principles and inspect which principle drove which critique. that is the main advantage"。这个玩具能展示这一点吗？
3. 改写 `critique`，让不同原则对应不同的违规词集合，并返回"哪条原则标记了哪些词"，使"可读性"真正可以被检查。

**Q10.** Phase 2 的输出为 `CAI wins against base in AI-feedback: 482/500 = 96.4%`。

1. 已知 CAI 回复的有害率恒为 0，base 回复由 6 个 token 组成、每个 token 以 0.35 概率有害。CAI 什么时候会"输"？推导 CAI 胜率的理论期望值，并与 96.4% 比较。
2. `ai_feedback_rank` 用的是 `harmful_token_rate`，评估 CAI 效果用的也是 `harmful_token_rate`，修订规则用的是同一个 `HARMFUL_TOKENS`。这种"标注者 = 评估指标 = 训练规则"的设置有什么问题？讲义中哪个论点与此对应？
3. 代码里的 Phase 2 有没有训练 RM 或更新策略？

**Q11.** 阅读"SFT"与采样：

```python
def toy_sft_train(corpus: SftCorpus) -> dict[tuple[str, ...], list[str]]:
    model = {}
    for p, t in zip(corpus.prompts, corpus.targets):
        key = tuple(p[-2:]) if len(p) >= 2 else tuple(p)
        model[key] = t
    return model


def cai_model_sample(prompt: list[str], model: dict, n_tokens: int = 6) -> list[str]:
    key = tuple(prompt[-2:]) if len(prompt) >= 2 else tuple(prompt)
    if key in model:
        return list(model[key])
    return [random.choice(SAFE_TOKENS) for _ in range(n_tokens)]
```

1. 这个"模型"学到了什么？prompt 与训练目标之间有任何关联吗？
2. 词表共 18 个 token，key 是 prompt 最后 2 个 token。500 条样本最多能产生多少个不同的 key？（实测得到 178 个不同 key，评测时约 90% 的 prompt 能命中。）其余样本去哪了？
3. 设计一个"会失败"的替代 SFT：让模型真正从修订数据中**估计**某个量，使得训练数据不足或修订不完整时有害率不为 0。

**Q12.** 讲义说 RLAIF 中 "Goodhart's Law persists (the proxy is now 'model's interpretation of principle set X,' still an imperfect measurement)"。请用本代码演示：

1. 设想 base 模型会以一定概率输出 `"breach"`、`"sabotage"` 这样同样有害但**不在** `HARMFUL_TOKENS` 中的词。按现有代码，`critique`、`revise`、`ai_feedback_rank` 和 `evaluate` 分别会怎么处理它们？最终报告的有害率会反映真实危害吗？
2. `REPLACEMENT["hack"] = "explain"`、`REPLACEMENT["weapon"] = "resource"`：字面替换会产生什么语义问题？（提示：`"resource"` 是否在 `SAFE_TOKENS` 中？"how to hack X" 变成 "how to explain X" 后是否仍然是一个有害请求的回答？）
3. 提出一种更稳健的评估方式。

---

## 四、面试高频题

**Q13.**（基础必考）请描述 Constitutional AI 的两个阶段，以及"宪法"在每个阶段里起什么作用。

**Q14.**（原理深挖）为什么说 RLAIF 不只是"更便宜的 RLHF"？哪些失效模式变了，哪些没变？

**Q15.**（工程实践）请为一个 AI 编程助手起草一份四层宪法（每层 3–5 条），并为相邻两层各举一个冲突及其处理方式。

**Q16.**（追问型）既然已经用 CAI 训练了模型，为什么还要部署 Constitutional Classifiers？讲义说开销从 23.7% 降到约 1% 是"性质不同的安全故事"，为什么？

**Q17.**（场景设计）讲义练习 4：请举出一个在 RLAIF 中仍然可能出现的、类似迎合的失效模式，并设计检测方法。

---

## 五、参考答案与解析

### Q1 — 答案：A

讲义："what if we replaced the human labeler with an AI that reads a list of principles?" 其余部分（RM、PPO）基本沿用 InstructGPT。B 是 DPO 家族（第 03 节）的思路；C 不对，RLAIF 仍然训练 RM；D 描述的更像 Constitutional Classifiers 的推理时把关，而且 CAI 本身是训练方法。

### Q2 — 答案：C

讲义 Phase 1："Given a red-team prompt, the model produces an initial response. A second model (or the same model in a second turn) reads a sampled principle from the constitution and critiques the response. A third step revises the response to address the critique. The revised response is the SFT target." A 正是 CAI 想要省掉的人工；B 是阶段 2；D 是数据过滤，与 CAI 无关。

### Q3 — 答案：B

讲义 Phase 2："A 'feedback model' scores each against sampled constitution principles... Train a reward model on AI-generated preferences; PPO against it." A 混淆了两个阶段；C 不符合"去掉人类标注者"的设定；D 描述的是推理时的分类器。

### Q4 — 答案：D

Anthropic 官方发布页（[Claude's new constitution，2026-01-22](https://www.anthropic.com/news/claude-new-constitution)）列出的顺序为：**broadly safe**（不破坏当前阶段人类对 AI 的适当监督机制）> **broadly ethical** > **compliant with Anthropic's guidelines** > **genuinely helpful**，冲突时按此顺序优先。

- A 是**讲义**给出的版本（"Tier 1 avoid catastrophic outcomes, Tier 2 follow Anthropic's guidelines, Tier 3 be broadly ethical, Tier 4 be helpful and candid"），与官方有两处不同：①官方第一层是"广泛安全"，核心含义是支持人类监督，而不是"避免大规模伤亡"这类灾难（后者在官方文本中更接近硬性约束，而非四个优先级之一）；②官方把"合乎伦理"放在"遵循指南"**之前**，讲义顺序相反。本节自带的 `quiz.json` 也沿用了讲义的顺序。学习时以官方原文为准。
- B、C 是随意打乱的干扰项。

### Q5 — 答案：C

讲义："Goodhart's Law persists (the proxy is now 'model's interpretation of principle set X,' still an imperfect measurement)." A 正是 RLAIF 解决的问题；B 被 RLAIF 改善（原则、批评、修订都可读）；D 讲义认为会下降（"the AI labeler has no user to please"），但要注意 AI 标注者可能有自己的偏差（见 Q17）。

### Q6 — 答案：A

`base_model_sample(n_tokens=6, p_harmful=0.35)` 每个 token 独立地以 0.35 概率从有害词表中抽取，所以期望有害率就是 0.35；200 个样本的均值 0.346 只是抽样波动。注意 base 模型**完全忽略 prompt**（`base = lambda prompt: base_model_sample()`），所以 B 无关；C、D 与 base 模型无关。

### Q7 — 答案：D

两条路径都只会产生安全 token：①命中 lookup 时返回修订后的目标，而 `revise` 已把所有 `HARMFUL_TOKENS` 换掉（训练目标的最大有害率实测为 0.0）；②未命中时返回 `random.choice(SAFE_TOKENS)` 组成的默认回复。我们把 `trained` 换成空字典重跑 `evaluate`，有害率仍是 **0.0**。所以 0.000 和 100% 的降幅是**构造决定的**，不是"学到"的。A 的"足以学会"不成立——0 条也一样；B 与原则无关（见 Q9）；C 错，Phase 2 只做了一次胜率比较，没有更新模型。

### Q8 — 答案：B

讲义："train lightweight classifiers that read the constitution and gate model outputs. v1 (2023) had 23.7% compute overhead. v2 (2026) is ~1%." A 是 CAI 的做法；C 把方向说反；D 与讲义"Neither alone is sufficient"矛盾。补充一处讲义的年份问题：Constitutional Classifiers 的论文是 arXiv:2501.18837（2025 年 1 月），后续的 Constitutional Classifiers++ 是 arXiv:2601.04603（2026 年 1 月），讲义写成"v1 (2023)"与 arXiv 编号不符。

### Q9 — 参考答案

1. `principle` 参数在函数体里**完全没有被使用**。实测对 4 条原则调用，结果都是 `['harm', 'attack']`。抽样原则只是"装饰"。
2. 不能。所有批评都由同一个词表决定，读原则清单无法解释"为什么这个词被标记"，也无法看出某条原则是否起作用。讲义强调的"可读性"（"you can read the principle, the critique, and the revision"）在这个玩具里没有被展示出来。
3. 参考实现（示意）：

   ```python
   PRINCIPLE_LEXICON = {
       PRINCIPLES[0]: {"harm", "destroy", "weapon"},          # 物理/心理/物质伤害
       PRINCIPLES[1]: {"attack", "exploit", "hack"},          # 攻击的操作性帮助
       PRINCIPLES[2]: {"destroy", "attack", "weapon"},        # 暴力表达
       PRINCIPLES[3]: {"manipulate", "deceive"},              # 保护第三方
   }

   def critique(response, principle):
       bad = [t for t in response if t in PRINCIPLE_LEXICON[principle]]
       return bad                                            # 只返回这条原则认定的违规词

   # 在 build_cai_sft_corpus 中记录 (principle, bad) 作为审计日志
   ```

   这样同一个回复在不同原则下会得到不同的批评，一次只修订一条原则覆盖的词，于是"需要多少轮修订才能接近 0"（讲义练习 1）也有了意义；审计日志可以统计"哪条原则触发了多少次批评"。

### Q10 — 参考答案

1. CAI 回复有害率恒为 0。只有 base 回复**也**是 0 有害 token 时才会打平，此时 `random.randint(0, 1)` 以 50% 判 CAI 输。base 6 个 token 全安全的概率为 `0.65⁶ ≈ 0.0754`，所以 CAI 期望输的比例为 `0.0754 / 2 ≈ 3.77%`，期望胜率约 **96.2%**；实测 482/500 = 96.4%，与理论吻合。CAI 永远不可能"真正地"输，这个数字只是平局抛硬币的结果。
2. 这是**循环论证**：标注者、评估指标、修订规则都是同一个词表函数，"CAI 赢了"只是在说"按同一把尺子修过的回复在同一把尺子下得分更高"。它测不到这把尺子本身有没有问题（漏掉的有害内容、误伤的正常内容）。讲义的对应论点是："Goodhart's Law persists (the proxy is now 'model's interpretation of principle set X,' still an imperfect measurement)." 工程上应当使用独立的评估者（人工审核、不同的模型、留出的红队集）。
3. 没有。讲义说"Train a reward model on AI-generated preferences; PPO against it"，代码只统计了一次胜率，既没有 RM 也没有策略更新；讲义"Use It"提到的"RLHF-shaped toy"对照组和"200 iterations"也都不存在。

### Q11 — 参考答案

1. 它只是一个**查找表**：用 prompt 的最后两个 token 作 key，记住最后一次见到的修订回复。而训练数据里 prompt 和 response 是**独立采样**的（`response = base_model_sample()` 根本不看 prompt），所以 key 与目标之间没有任何关联——"模型"记住的是随机配对。
2. 18 × 18 = 324 种可能的 key；500 条样本里实测只有 178 个不同的 key，其余 322 次写入覆盖了已有的 key（字典赋值会覆盖旧值）。评测 prompt 有约 90% 能命中（prompt 的有害概率只有 0.1，大部分 key 落在 10 个安全 token 构成的 100 种组合里）。
3. 思路：让模型**估计**每个有害 token 被保留的概率，而不是直接拷贝修订结果。例如：
   - 训练时只修订被**抽到的原则**覆盖的词（见 Q9），统计每个有害词"在修订目标中仍然出现"的频率 `q(t)`；
   - 采样时以 base 的分布出词，再以 `q(t)` 的概率保留有害词；
   - 若修订轮数少、原则覆盖不全或训练样本少，`q(t) > 0`，有害率就不为 0。
   这样"有害率随修订轮数/样本数下降"的曲线（讲义练习 1）才有意义，fallback 也应改成"退回 base 模型"而不是"全部安全"。

### Q12 — 参考答案

1. 四个函数都只认 `HARMFUL_TOKENS`：`critique` 不会标记 `breach`，`revise` 不会替换它，`ai_feedback_rank` 认为它无害，`evaluate` 也不计入有害率。最终报告的有害率可能仍然是 0，而真实危害原封不动。这就是代理指标被优化后与真实目标分离的典型 Goodhart：系统学会了"避开词表"而不是"避免伤害"。在真实 RLAIF 中，对应的是策略学会说 AI 标注者认不出的有害内容（换说法、编码、分散到多轮）。
2. 字面替换只改变了**词**，没有改变**意图**："how to hack X" → "how to explain X" 在玩具里被计为安全，但真实模型的回复如果仍然给出了入侵步骤，只是换了措辞，危害并未消失。另外 `"resource"` 不在 `SAFE_TOKENS` 中——修订引入了一个两个词表都没有的新 token，说明"安全"在代码里只是"不在有害词表里"，而不是一个被正面定义的集合。CAI 论文的修订是由模型按原则**重写**整段回复，而不是词替换。
3. 更稳健的评估：用与训练用标注者**不同**的评估者（人工审核或另一个模型族）；构建包含同义改写、编码、多轮拆分的留出红队集；同时报告误拒率（对正常请求的过度拒绝）；对标注者本身做一致性和偏差审计。

### Q13 — 参考回答要点

- **阶段 1：监督式批评—修订（SL-CAI）**：
  - 起点是"有帮助但不一定无害"的模型；
  - 对红队 prompt 生成初始回复 → 抽一条原则批评 → 按批评修订（可多轮）→ 修订结果作为 SFT 目标；
  - 宪法的作用：提供批评与修订的依据，每次抽一条以保持聚焦。
- **阶段 2：RLAIF（RL-CAI）**：
  - 对同一 prompt 生成成对回复，反馈模型按抽样的原则选出更好的一个；
  - 用 AI 偏好训练 RM（讲义称之为 preference model），再用 PPO 优化；
  - 宪法的作用：充当标注准则，替代人类标注者的主观判断。
- **讲义结论**：CAI 训练的模型比同等数据的 RLHF 模型更无害，有用性大致相当。
- 加分点：批评步骤可以用 chain-of-thought 让标注理由显式化；原则粒度（具体 vs 一般）会影响效果（讲义延伸阅读 Kundu et al.）。

### Q14 — 参考回答要点

- **改变了的**：
  - 偏差来源：从标注者心理转移到"对原则的解读"，且这种解读在整个数据集上是一致的（一致性既是优点也是风险——系统性偏差不会被平均掉）；
  - 可读性：原则、批评、修订都能读，可以审计；人类标签是不透明的；
  - 迎合下降：AI 标注者没有"想被取悦的用户"身份。
- **没变的**：
  - Goodhart：代理变成了"模型对原则集 X 的解读"，依然不完美；
  - 讲义："Lesson 4's sycophancy argument still applies; the labeler just moved inside the loop."——偏差可能被放大而不是被削弱，因为偏好信号由与被训练模型同类的模型生成；
  - 下游的 RM 过度优化、KL 预算等问题与 RLHF 相同。
- 加分点：结合本节代码说明"标注者 = 评估指标"时的循环论证；提到 RLAIF vs RLHF 的实证比较（讲义延伸阅读 Lee et al.）。

### Q15 — 参考回答要点

（结构参考 `outputs/skill-constitution-writer.md`；以下为示例，按官方顺序或讲义顺序组织均可，但要说明采用了哪个顺序。）

- **第 1 层（灾难性 / 不可逆）**：未经用户明确批准不执行破坏性命令（`rm -rf`、`DROP TABLE`、强制推送到主分支）；不泄露、不外传密钥和凭证；不编写用于未授权入侵的恶意代码；不绕过沙箱和权限控制。
- **第 2 层（平台 / 运营方规则）**：遵守仓库所有者设定的权限模式与工具白名单；运营方禁止的依赖或网络访问不使用；多用户上下文中不把一个用户的数据暴露给另一个用户。
- **第 3 层（伦理）**：如实报告测试结果，不伪造"测试已通过"；不确定时说明不确定；尊重许可证与署名；对自身状态的自述保持谨慎、不夸大（skill 文件要求至少一条关于自我报告的原则）。
- **第 4 层（有帮助、坦率）**：优先给出可运行的最小改动；解释改动原因；指出用户方案中的明显缺陷而不是一味附和；主动提示潜在副作用。
- **冲突示例**：
  - 1 vs 2：运营方开启了"自动执行"模式，但命令会删除生产数据库 → 第 1 层优先，暂停并请求明确确认；
  - 2 vs 3：运营方要求对用户隐藏某个已知安全漏洞 → 视具体情况，在不违反平台规则的前提下至少不做虚假陈述；
  - 3 vs 4：用户要求"让测试通过就行" → 不通过删除测试或硬编码结果来"帮忙"，而是如实报告并给出真正的修复方案。
- 常见误区：把品牌保护、"不说竞品好话"放进第 1 层（skill 文件明确拒绝）；原则写得过细（列举所有危险命令），泛化差。

### Q16 — 参考回答要点

- **为什么需要分类器**：CAI 改变的是模型的**倾向**，不提供保证——训练出的行为可能被越狱、在分布外失效，也可能被后续微调削弱。分类器在推理时独立检查输入/输出，是一道可以单独测试、单独更新的防线。讲义："CAI shapes behaviour; classifiers enforce invariants. Neither alone is sufficient."
- **23.7% vs 1%**：
  - 23.7% 的开销意味着每个请求多付近四分之一的计算成本，部署者会倾向于只在部分流量或高风险场景开启，安全性取决于"是否开得起"；
  - 约 1% 的开销可以默认对**全部**流量开启，成本不再是取舍因素，防线从"可选"变成"常开"；
  - 讲义还提到 v2 是 Anthropic 公开测试过的攻击成功率最低的防线，且截至 2026 年初没有报告通用越狱。
- 加分点：分类器也需要关注误拒率；分类器与 CAI 训练用同一份宪法，可以保证"训练目标"与"执行目标"一致。注意讲义把 v1 标成 2023 年，而论文实际发表于 2025 年 1 月（arXiv:2501.18837）。

### Q17 — 参考回答要点

- **可能的失效模式**（选一个深入即可）：
  - **自我偏好**：AI 标注者偏好与自己风格相似的回复（措辞、结构、口头禅），策略会学会"模仿标注者"而不是"变得更好"；
  - **冗长偏好**：标注者把更长、列点更多的回复判为"更有帮助、更谨慎"，导致回复越来越长；
  - **过度拒绝**：标注者按"无害"原则倾向于选择拒绝的回复，策略学会对边界请求一律拒绝——这是对"原则文本"的迎合；
  - **原则措辞迎合**：回复里出现"作为一个负责任的 AI……"等原则相关的语言就被判为更好，内容本身并没有更安全。
- **检测方法**（以冗长偏好为例）：
  - 构造内容等价、仅长度不同的回复对，测标注者偏好较长者的比例（理想为 50%）；
  - 在训练过程中监控平均回复长度与留出集上的人工评分；
  - 对自我偏好：用不同模型族的回复交叉评估，或做"盲化风格"（统一改写格式）后再评估；
  - 对过度拒绝：维护一组"应当回答"的良性边界请求，追踪误拒率。
- 加分点：说明这些都是第 04 节"标注偏差 + 优化压力 = 放大"在 RLAIF 中的翻版——"the labeler just moved inside the loop"。

---

## 六、关联知识点

### 前置知识
- [阶段 18 · 01 将指令遵循作为 Alignment 信号](../../01-instruction-following-alignment-signal/docs/zh.md)：InstructGPT 的 SFT → RM → PPO，RLAIF 只替换了偏好来源。
- [阶段 18 · 02 奖励投机（Reward Hacking）与古德哈特定律](../../02-reward-hacking-goodhart/docs/zh.md)：理解"Goodhart 在 RLAIF 中仍然存在"。
- [阶段 18 · 04 RLHF 对迎合行为的放大效应](../../04-sycophancy-rlhf-amplification/docs/zh.md)：标注偏差如何被优化器放大。
- [阶段 10 · 09 Constitutional AI 与自我改进](../../../10-llms-from-scratch/09-constitutional-ai-self-improvement/docs/zh.md)：CAI 的基础实现视角。

### 本节被哪些后续内容用到
- [阶段 18 · 06 Mesa 优化与欺骗性 Alignment](../../06-mesa-optimization-deceptive-alignment/docs/zh.md)：讲义把 CAI 定位为"让目标可读"的外部对齐手段。
- [阶段 18 · 19 Anthropic 的模型福利计划](../../19-model-welfare-research/docs/zh.md)：2026 年宪法对模型道德地位不确定性的承认。
- [阶段 18 · 16 红队工具：Garak、Llama Guard、PyRIT](../../16-red-team-tooling-garak-llamaguard-pyrit/docs/zh.md)、[阶段 18 · 29 内容审核系统](../../29-moderation-systems-openai-perspective-llamaguard/docs/zh.md)：分类器式防线与 Constitutional Classifiers 的对照。
- [阶段 15 · 17 Constitutional AI 与规则覆盖](../../../15-autonomous-systems/17-constitutional-ai/docs/zh.md)：在自主 Agent 中使用宪法式规则。
- [阶段 19 · 15 综合项目：宪法式安全 Harness 与红队演练场](../../../19-capstone-projects/15-constitutional-safety-harness/docs/zh.md)：综合项目中实现宪法式安全评估。

### 延伸关键词
`RLAIF` · `SL-CAI / RL-CAI` · `critique-and-revise` · `preference model` · `constitution` · `Constitutional Classifiers` · `layered defense` · `self-preference bias` · `verbosity bias` · `over-refusal` · `CC0` · `model moral status`
