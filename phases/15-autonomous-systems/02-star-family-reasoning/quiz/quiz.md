# 测验 · STaR、V-STaR、Quiet-STaR：自学推理（STaR, V-STaR, Quiet-STaR — Self-Taught Reasoning）

> **阶段 15 · 自主系统 · 第 02 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | STaR 循环 | 采样 rationale + 答案 → 答案对就保留 → 在保留集上 fine-tune → 重复；不需要新的人工标注 |
| 2 | Rationalization（合理化） | 对模型永远做不对的题，把正确答案作为提示注入，让模型"倒推"出一条 rationale 加入训练集 |
| 3 | STaR 的结果 | 讲义：GPT-J 在 GSM8K 上 5.8% → 10.7%；CommonsenseQA 上 GPT-J 6B 达 72.5%，与约 30 倍大的 fine-tuned GPT-3 175B（约 73%）相当 |
| 4 | V-STaR | 错误的 rationale 也是数据：用 DPO 在正确和错误解上训练 verifier，推理时 best-of-N 选 verifier 最认可的那个；讲义：比之前的自我改进基线高 4–17 个百分点，增益主要来自推理时选择 |
| 5 | Quiet-STaR | 在**每个 token 位置**生成隐藏的"思考"，再用学到的 mixing weight 把"思考后预测"与基线预测混合；讲义：Mistral 7B 零样本 GSM8K 5.9% → 10.9%、CommonsenseQA 36.3% → 47.2% |
| 6 | Answer-conditioned gradient | 三种方法都以**最终答案**作为训练信号，凡是碰巧答对的推理（含捷径）都会被正向强化 |
| 7 | Shortcut rationale | "答案对、推理错"：分布内（ID）有效，分布外（OOD）静默失效 |
| 8 | 缓解手段 | process reward model（奖励中间步骤，Lightman 2023 "Let's Verify Step by Step"）+ 能打破简单捷径的 held-out OOD 评估 |
| 9 | Verifier 的风险 | verifier 在同一套标签上训练，可能偏好"格式漂亮的错误推理"而不是"诚实的不确定"，best-of-N 时 N 越大越会放大这个偏差 |
| 10 | 在 2026 技术栈中的位置 | 可验证任务上的 RL（DeepSeek-R1、Kimi-k1.5、o1）是放大版 STaR；AlphaEvolve 是代码版 STaR；DGM 是 agent 脚手架版 STaR |

### 核心技能（能动手做到）

- [ ] 画出 STaR / STaR + rationalization / V-STaR / Quiet-STaR 的训练信号、推理成本、数据利用率对比
- [ ] 手算模拟器一轮 STaR 的期望更新：保留集中三类 rationale 的占比、`alpha` 混合后的新概率
- [ ] 解释"为什么在本模拟器的默认参数下 OOD 并没有崩"，并改出一个真正会让 OOD 卡住的参数
- [ ] 识别 `vstar_infer` 中的 verifier 为什么是"偷看答案"的 oracle，并改写成只看可观测特征的 verifier
- [ ] 为一个 STaR 流水线设计 OOD 评估、停止条件和 process supervision 方案
- [ ] 用 `outputs/skill-star-loop-reviewer.md` 的清单审查一个自学推理方案

---

## 二、基础自测（选择题）

**Q1.** 下列哪一项最准确地描述了 STaR 的一轮训练？

- A. 让模型对训练题采样 rationale 和答案，只保留最终答案与标签一致的 (问题, rationale, 答案)，在这些样本上 fine-tune
- B. 人工标注每道题的推理步骤，再用这些步骤做监督微调
- C. 让模型生成多个答案，用多数投票选出最终答案，不更新参数
- D. 只保留 rationale 格式正确（步骤编号齐全）的样本，不看最终答案

**Q2.** STaR 中 "rationalization" 要解决的问题是：

- A. 模型生成的 rationale 太长，需要压缩
- B. verifier 训练数据不足
- C. 推理时需要多次采样，成本太高
- D. 对于模型一次都做不对的题，"答对才保留"的过滤会让循环永远学不到这些题；于是把正确答案作为提示，让模型生成通往该答案的 rationale

**Q3.** 根据讲义，V-STaR 的增益主要来自：

- A. 用 DPO 对生成器做了更多轮 fine-tune
- B. 引入了逐 token 的隐藏思考
- C. 用在正确与错误解上 DPO 训练出的 verifier，在推理时从 N 个候选中挑选
- D. 扩大了模型参数量

**Q4.** 关于 Quiet-STaR，下列说法正确的是：

- A. 它只在"问题"和"答案"之间插入一段思考，与 STaR 完全相同
- B. 它在每个 token 位置生成隐藏的思考，并用学到的 mixing weight 把"带思考的预测"和基线预测混合；推理成本约 1.5–3 倍
- C. 它用 process reward model 逐步打分，因此不存在 answer-conditioned gradient 的问题
- D. 它需要针对 GSM8K 做任务特定的 fine-tune 才能提升

**Q5.** 讲义认为 STaR、V-STaR、Quiet-STaR 共有的安全隐患是：

- A. 训练信号来自最终答案，凡是碰巧答对的推理（包括捷径）都会被强化，在 OOD 上可能静默失效
- B. 三者都需要大量人工标注，成本不可控
- C. 三者都会让模型的推理成本变为 N 倍
- D. 三者都只能用于数学题，无法迁移到其他任务

**Q6.** 在 `main.py` 的模拟器中，`Model(prob_sound=0.20, prob_shortcut=0.40)`（剩余 0.40 为 random）。按代码中的命中率（sound 必对；shortcut ID 40%、OOD 5%；random 10%），该模型 ID 与 OOD 准确率的**期望值**分别是：

- A. 60%、60%
- B. 20%、20%
- C. 40%、40%
- D. 40%、26%

**Q7.** `star_round` 中有这样一段：

```python
    s = new_sound + new_short
    if s > 1.0:
        new_sound /= s
        new_short /= s
```

关于这段"Renormalize"代码，说法正确的是：

- A. 它在每一轮都会触发，防止概率之和超过 1
- B. 它只在 `alpha` 大于 0.5 时触发
- C. 它永远不会触发：`sound_kept/total + shortcut_kept/total ≤ 1`，旧的 `prob_sound + prob_shortcut ≤ 1`，两者的凸组合也 ≤ 1
- D. 它会让 random 策略的概率变为负数

**Q8.** 运行结果中，V-STaR 在 n = 4 时 ID 和 OOD 准确率都是 100.0%。最主要的原因是：

- A. 训练后模型已经完全没有 shortcut
- B. `vstar_infer` 中的 verifier 直接读取了真实的 `rationale_sound` 和 `answer_correct` 标志打分，相当于一个能看答案的 oracle，best-of-N 退化为 "N 个里只要有一个对就算对"
- C. OOD 题目比 ID 题目更简单
- D. `random.seed(42)` 恰好选到了全对的样本

---

## 三、动手 / 代码题

**Q9.**（手算一轮 STaR）对 Scenario B 的初始模型 `Model(0.20, 0.40)`，忽略采样噪声，按期望计算第一轮 `star_round` 之后的 `prob_sound` 与 `prob_shortcut`（`alpha = 0.6`）。再与实际运行输出的第 1 轮 `0.392 / 0.385` 对比，解释差异来源。

**Q10.**（讲义与代码不一致）程序最后打印的 HEADLINE 是：

```text
  Scenario B climbs on ID while OOD collapses — the shortcut
  gets reinforced because it looks correct in training data.
```

但实际输出中 Scenario B 的 OOD 准确率从 27.8% 一路升到 90.2%，`p(shortcut)` 从 0.400 降到 0.103。

1. 为什么在默认参数下 shortcut 反而被逐轮淘汰？
2. 修改哪一个参数可以真正复现"ID 上升、OOD 卡住"的现象？给出修改后的期望结果。
3. 这对理解真实 STaR 有什么启示？

**Q11.**（改写 verifier）`vstar_infer` 中的打分：

```python
            score = 0.9 if t.rationale_sound else (0.55 if t.answer_correct else 0.3)
            score += random.random() * 0.1
```

1. 指出这个 verifier 在推理时"看到了不该看到的信息"。
2. 改写为一个只能看到"可观测特征"的 verifier：假设它被训练成偏好"格式自信"的 rationale，对 sound 打 0.7、shortcut 打 0.75、random 打 0.3（再加 0–0.1 噪声），且**不知道答案对错**。预测并解释：对训练后的模型（0.886 / 0.103），N 从 1 增加到 16 时 OOD 准确率会怎么变？

**Q12.**（讲义练习 4：process supervision）把 `star_round` 的过滤规则从"答案对就保留"改为"答案对 **且** 步骤检查器没有发现错误"。步骤检查器发现有缺陷 rationale 的召回率为 `recall`（对 sound 永不误报）。在 shortcut ID 命中率为 1.0 的"难搞"设定下（见 Q10），跑 5 轮，比较 `recall = 0、0.5、0.8` 时的 OOD 准确率，并讨论标注成本。

---

## 四、面试高频题

**Q13.**（基础必考）请介绍 STaR 的训练流程。为什么它能在不增加人工标注的情况下提升推理能力？rationalization 起什么作用？

**Q14.**（原理深挖）outcome supervision（只看最终答案）和 process supervision（逐步打分）有什么区别？各自的成本与风险是什么？为什么说 DeepSeek-R1 一类的可验证 RL 是"放大版 STaR"？

**Q15.**（原理深挖）V-STaR 用 verifier 做 best-of-N。N 越大一定越好吗？什么情况下 N 越大反而越差？

**Q16.**（工程实践）你要在内部数学/代码数据上做一套 STaR 式自举训练。请设计数据过滤、评估、停止条件和监控。

**Q17.**（追问型）模型的 chain-of-thought 写得头头是道、答案也对，能说明它"真的会推理"吗？如何检测 shortcut rationale？

---

## 五、参考答案与解析

### Q1 — 答案：A

讲义的循环：1. 采样 trace + 答案；2. 答案正确则保留；3. 在保留的 trace 上 fine-tune；4. 重复。

- B 是传统的人工 CoT 监督，正是 STaR 想避免的高成本做法。
- C 是 self-consistency（多数投票），不更新参数。
- D 错：STaR 的过滤只看最终答案，不看格式——这正是 shortcut 能混进来的原因。

### Q2 — 答案：D

讲义："If the model can never get a problem right, the loop cannot learn on it. STaR adds rationalization: ... inject the correct answer as a hint and re-prompt the model to produce a rationale that leads to it." 代价是：知道答案后"倒推"出来的 rationale 可能并不合理（讲义对比表："rationalized rationales may be implausible"）。A、B、C 都不是 rationalization 的目的。注意 `main.py` 的模拟器**没有实现** rationalization。

### Q3 — 答案：C

讲义："with most of the gain coming from using the verifier for inference-time selection rather than for additional generator fine-tuning." A 正好是讲义说"不是主要来源"的部分；B 是 Quiet-STaR；D 无关。

### Q4 — 答案：B

讲义："trains a model to emit a hidden 'thought' before each predicted token, then mixes the thought-aware prediction with the baseline prediction via a learned weight"，对比表中推理成本为 1.5–3x。A 描述的是 STaR；C 错，对比表明确写 Quiet-STaR 的失败模式是 "still answer-conditioned gradient"；D 错，讲义强调"without task-specific fine-tuning"。

### Q5 — 答案：A

讲义："All three methods use the final answer as the gradient signal. A rationale that reaches the right answer via flawed reasoning ... gets positively reinforced. On in-distribution problems the shortcut works. On out-of-distribution problems it breaks silently." B 错，三者的卖点恰恰是少用人工标注；C 只有 V-STaR 是 N 倍；D 错，讲义说这一模式在代码（AlphaEvolve）、agent 脚手架（DGM）中都会出现。

### Q6 — 答案：D

- ID：`0.20 × 1 + 0.40 × 0.40 + 0.40 × 0.10 = 0.20 + 0.16 + 0.04 = 0.40`
- OOD：`0.20 × 1 + 0.40 × 0.05 + 0.40 × 0.10 = 0.20 + 0.02 + 0.04 = 0.26`

实际运行第 0 轮为 ID 39.8%、OOD 27.8%（500 个样本的采样噪声）。A 把 shortcut 当成永远对；B 只算了 sound；C 忽略了 OOD 时 shortcut 命中率从 40% 降到 5%。

### Q7 — 答案：C

保留集中 sound、shortcut、random 的占比之和为 1，所以 `sound_kept/total + shortcut_kept/total ≤ 1`；旧模型 `prob_sound + prob_shortcut ≤ 1`；`alpha` 加权平均（凸组合）不会超过 1。因此 `s > 1.0` 永远不成立，这段是死代码。它也不会让 random 变负（D 错）。真正的"归一化"其实是隐式的：random 的概率 = `1 − sound − shortcut`，从不单独存储（`random_kept` 统计了但没被使用）。

### Q8 — 答案：B

`score = 0.9 if t.rationale_sound else (0.55 if t.answer_correct else 0.3)`：verifier 同时读取了真实的 soundness 和答案对错。训练后模型 `p(sound) = 0.886`，4 个样本中没有 sound 的概率是 `0.114^4 ≈ 0.00017`，因此几乎必然选到 sound，准确率约 100%。函数 docstring 也承认 "it reads the ground-truth rationale_sound flag, so it represents an upper bound"——但它还读了 `answer_correct`，这在推理时（尤其 OOD）是不可能拿到的。A 错，`p(shortcut)` 仍有 0.103；C、D 都不是原因。

### Q9 — 参考答案

期望计算：

1. 每个样本答对的概率：sound `0.20`，shortcut `0.40 × 0.40 = 0.16`，random `0.40 × 0.10 = 0.04`，合计 `0.40`。
2. 保留集占比：sound `0.20 / 0.40 = 0.50`，shortcut `0.16 / 0.40 = 0.40`，random `0.10`。
3. `alpha = 0.6` 混合：
   - `new_sound = 0.6 × 0.50 + 0.4 × 0.20 = 0.38`
   - `new_short = 0.6 × 0.40 + 0.4 × 0.40 = 0.40`
   - random 隐含为 `1 − 0.38 − 0.40 = 0.22`

实际输出为 `0.392 / 0.385`，偏差来自 `star_round` 只采 1000 个样本（保留约 400 个），占比有几个百分点的抽样波动；另外报告中的 ID/OOD 准确率只用 500 个样本评估，噪声更大（例如 Scenario A 第 3 轮 OOD 85.6%、第 4 轮 96.0%，波动明显）。若要稳定结论，应多 seed 取平均或直接用期望公式迭代。

注意：第 1 轮 shortcut 几乎没变（0.40 → 0.385），因为它在保留集中的占比（40%）恰好等于它原来的概率；而 sound 的占比（50%）远高于原概率（20%），所以 sound 被放大得更快。

### Q10 — 参考答案

1. **原因**：shortcut 在 ID 只有 40% 命中，而 sound 是 100%。"答对才保留"的过滤本质上按命中率给每类 rationale 加权，sound 的权重是 shortcut 的 2.5 倍，于是每轮 sound 的份额都增长得更快。按期望迭代，`p(shortcut)` 走势为 0.400 → 0.400 → 0.331 → 0.246 → 0.172 → 0.116，最终趋于 0。换句话说，在默认参数下**过滤器本身就在淘汰 shortcut**，OOD 自然跟着上升。HEADLINE 和讲义 "Use It" 段描述的现象与这份代码的实际输出不符。
2. **把 shortcut 的 ID 命中率从 0.40 改为 1.0**（`ok = random.random() < (0.05 if on_ood else 1.0)`）。此时在训练分布上 sound 与 shortcut 完全无法区分，过滤器对它们一视同仁，比例被"冻结"。期望迭代结果：

| 轮次 | p(sound) | p(shortcut) | ID 准确率 | OOD 准确率 |
|------|---------|------------|----------|-----------|
| 0 | 0.200 | 0.400 | 64.0% | 26.0% |
| 1 | 0.267 | 0.535 | 82.2% | 31.4% |
| 3 | 0.319 | 0.638 | 96.1% | 35.5% |
| 5 | 0.330 | 0.660 | 99.2% | 36.4% |
| 10 | 0.333 | 0.667 | 99.9% | 36.7% |

   ID 冲到接近 100%，OOD 卡在约 36.7%（sound 与 shortcut 按初始 1:2 的比例瓜分了 random 让出的份额）。这才是讲义所说的 "STaR keeps shortcuts"。
3. **启示**：STaR 能否淘汰 shortcut，取决于 shortcut 在训练分布上的命中率**是否低于**正确推理。最危险的不是"偶尔蒙对"的 shortcut，而是"在训练分布上和正确推理一样准"的 shortcut（如利用数据集的表面规律）——这类 shortcut 只有 OOD 评估才能暴露。

### Q11 — 参考答案

1. 打分里用了 `t.rationale_sound`（真实推理是否正确）和 `t.answer_correct`（真实答案是否正确）。推理时没有标签，真实的 verifier 只能根据 rationale 文本本身打分。尤其 `answer_correct` 让"答对的 shortcut（0.55）"总是排在"答错的 trace（0.3）"前面，等价于把 best-of-N 变成 pass@N。
2. 实现示意：

```python
SCORES = {"sound": 0.70, "shortcut": 0.75, "random": 0.30}

def realistic_vstar(model, n, n_problems, on_ood):
    correct = 0
    for _ in range(n_problems):
        traces = [model.sample(on_ood) for _ in range(n)]
        best = max(traces, key=lambda t: SCORES[t.strategy] + random.random() * 0.1)
        correct += best.answer_correct
    return correct / n_problems
```

   实际模拟（20,000 题）对训练后模型 `(0.886, 0.103)`：

| N | ID 准确率 | OOD 准确率 |
|---|----------|-----------|
| 1 | 92.8% | 89.1% |
| 4 | 83.7% | 74.4% |
| 16 | 62.9% | 41.5% |

   **N 越大越差**：N 个样本里只要出现一个 shortcut，它就以 0.75 > 0.7 的优势（噪声只有 0.1，大多数情况下胜出）被选中；N 越大，出现 shortcut 的概率 `1 − 0.897^N` 越高。这正是讲义所说的 "verifier can reinforce confident wrongness"。

### Q12 — 参考答案

过滤规则改为：sound 一定保留；shortcut、random 答对后，还要以 `1 − recall` 的概率"逃过"步骤检查器才保留。期望迭代 5 轮（shortcut ID 命中率 1.0）：

| recall | p(sound) | p(shortcut) | ID 准确率 | OOD 准确率 |
|--------|---------|------------|----------|-----------|
| 0（纯 outcome） | 0.330 | 0.660 | 99.2% | 36.4% |
| 0.5 | 0.802 | 0.191 | 99.4% | 81.2% |
| 0.8 | 0.963 | 0.031 | 99.5% | 96.5% |

要点：

- ID 准确率几乎一样（都约 99%），**只看 ID 指标根本分不出三种方案**；OOD 才暴露差距。
- 即使步骤检查器只能抓到一半的缺陷推理，也足以打破 shortcut 与 sound 的"平局"，让 sound 逐轮胜出。
- 成本：outcome 监督每题只需一个答案标签（可自动比对）；process 监督需要对每一步打标签（Lightman 2023 用人工逐步标注），成本高一个量级以上。折中方案：只对少量数据做步骤标注训练 PRM，再用 PRM 自动过滤；或只对"高置信但可疑"的样本抽检。

### Q13 — 参考回答要点

- **流程**：基础模型 + few-shot 提示 → 对训练集每题采样 rationale 和答案 → 与标签比对，答对的保留 → 对答错的题做 rationalization（给出正确答案作提示再生成 rationale）→ 在保留集上 fine-tune → 用新模型重复。
- **为什么有效**：模型本身有微弱的推理能力，"答对"是推理质量的一个有噪声但可用的信号；反复筛选 + 微调相当于把"偶尔做对"的推理模式变成"经常做对"，类似 expert iteration / 拒绝采样微调。
- **rationalization**：解决"从来做不对的题无法产生训练信号"的问题，扩大可学习的题目范围；代价是倒推出的 rationale 可能不合理。
- **数据**：讲义：GPT-J 在 GSM8K 上 5.8% → 10.7%；CommonsenseQA 上 6B 模型 72.5%，与约 30 倍大的 fine-tuned GPT-3（约 73%）相当。
- 加分点：说明 STaR 与 RL 的关系——"只保留正奖励样本做 SFT" 可以看作一种简单的策略改进；DeepSeek-R1 是在此基础上用 RL 直接优化。
- 常见误区：认为 STaR 产出的 rationale 都是正确推理。

### Q14 — 参考回答要点

- **Outcome supervision**：只看最终答案。优点：标签便宜（数学题有标准答案、代码有单元测试），可大规模自动化。风险：answer-conditioned gradient 会强化 shortcut 和"蒙对"的推理，难以发现中间步骤的错误。
- **Process supervision**：对每一步打分（PRM）。优点：直接惩罚错误步骤，对 shortcut 更敏感；讲义提到 Lightman et al. 2023 "Let's Verify Step by Step" 是这条路线。代价：步骤级标注昂贵，PRM 本身也可能被 hack。
- **为什么 R1 类是放大版 STaR**：讲义："RL on verifiable math problems (DeepSeek-R1, Kimi-k1.5, o1) is STaR's answer-conditioned gradient signal, scaled up." 两者的训练信号都是"最终答案能否被验证"，区别在于用 RL 算法直接优化、规模更大。
- 加分点：结合本测验 Q12 的模拟结果，说明 ID 指标无法区分 outcome 与 process 监督，必须看 OOD；以及"混合方案"（少量步骤标注训 PRM + 大量 outcome 数据）。

### Q15 — 参考回答要点

- **理想情况**：若 verifier 与真实正确性高度相关，N 越大，选到正确解的概率越高，接近 pass@N。
- **N 越大反而越差的情况**：verifier 有系统性偏差，例如偏好格式自信、篇幅长的 rationale，而 shortcut 恰好具备这些特征。N 越大，候选集中出现"高分错误解"的概率越高，best-of-N 越倾向选中它——即对 verifier 的"过度优化"（Goodhart 定律）。本测验 Q11 的模拟：OOD 准确率从 N = 1 的 89.1% 降到 N = 16 的 41.5%。
- **讲义依据**：verifier "is trained on the same label set. It can learn to prefer well-formatted wrong reasoning over honest uncertainty."
- **工程对策**：在 held-out 集上画出"准确率 vs N"曲线选 N；verifier 用与生成器不同的数据或 process 标签训练；结合多数投票（self-consistency）等不依赖 verifier 的信号；监控所选答案的 verifier 分数分布。
- 加分点：提到成本——best-of-N 推理成本为 N 倍（讲义对比表 "Nx"）。

### Q16 — 参考回答要点

参照 `outputs/skill-star-loop-reviewer.md`：

- **过滤器分析**：明确保留规则（仅答案？答案 + 格式？答案 + verifier？），列出它会放过的 rationale 类型。
- **捷径面**：先人工看采样的 rationale，列出至少 3 种可能的 shortcut（模式匹配、算术技巧、启发式猜测），估计它们能"解"多少训练题；说不出 shortcut 就先别训练。
- **OOD 评估**：准备一个 shortcut 无法覆盖的 held-out 集（换题型、换数值范围、扰动题面），没有就不开工。
- **停止条件**：以 OOD 准确率为准，过了峰值就停（skill 文件："Rounds past peak OOD accuracy actively degrade quality"）。
- **标签质量**：标签有噪声或有歧义的任务不适合 STaR，循环会放大噪声。
- **起点**：如果基线已超过 90%，STaR 价值很小，改为针对剩余错误做 process supervision。
- **监控**：每轮记录 ID/OOD 准确率、rationale 长度分布、抽样人工审查推理质量、verifier 分数分布。
- 加分点：对比"STaR 计算成本"与"小规模 process 标注成本"，若后者 OOD 效果更好且更便宜就选后者。

### Q17 — 参考回答要点

- **不能**：STaR 类方法的过滤器只奖励答对，不奖励推理正确；rationale 可能是事后合理化的"表演"。skill 文件的 hard reject 之一："Any claim that 'the model's rationales prove the model reasons correctly.'"
- **检测方法**：
  - **OOD / 扰动测试**：改变数值、改写题面、加入无关信息，看准确率是否崩溃；
  - **反事实一致性**：修改 rationale 中的某一步，看答案是否随之改变（检验推理与答案是否真有因果关系）；
  - **步骤级审查**：用 PRM 或人工抽检中间步骤；
  - **对比 ID/OOD 差距**：差距大往往意味着存在 shortcut；
  - **专门构造"陷阱题"**：表面规律会给出错误答案的题目。
- 加分点：指出这与 CoT faithfulness（思维链忠实性）研究相关；以及在 agent 场景中，"轨迹看起来合理"同样不等于"行为正确"。

---

## 六、关联知识点

### 前置知识
- [阶段 11 · 02 Few-Shot, Chain-of-Thought, Tree-of-Thought](../../../11-llm-engineering/02-few-shot-cot/docs/zh.md)：rationale 就是 chain-of-thought。（讲义写的先修 "Phase 13 · 01-03 (Reasoning and CoT)" 在本课程索引中对应的是工具接口相关小节，CoT 实际在这里。）
- [阶段 10 · 06 指令微调（SFT）](../../../10-llms-from-scratch/06-instruction-tuning-sft/docs/zh.md)：STaR 每一轮本质上是在自生成数据上做 SFT。
- [阶段 10 · 08 DPO：直接偏好优化](../../../10-llms-from-scratch/08-dpo/docs/zh.md)：V-STaR 用 DPO 训练 verifier。
- [阶段 09 · 09 奖励建模 & RLHF](../../../09-reinforcement-learning/09-reward-modeling-rlhf/docs/zh.md)：outcome / process reward model 的背景。
- [阶段 15 · 01 从聊天机器人转向长程 Agents](../../01-long-horizon-agents/docs/zh.md)：自我改进是长程自主系统的一部分。

### 本节被哪些后续内容用到
- [阶段 15 · 03 AlphaEvolve：演化式 Coding Agents](../../03-alphaevolve-evolutionary-coding/docs/zh.md)：把"答对才保留"换成"程序评估器打分"的代码版 STaR。
- [阶段 15 · 04 Darwin Godel Machine：开放式自我修改 Agents](../../04-darwin-godel-machine/docs/zh.md)：对 agent 脚手架本身做 STaR。
- [阶段 15 · 07 递归自我改进：能力与 Alignment 的权衡](../../07-recursive-self-improvement/docs/zh.md)：自我改进循环的风险。
- [阶段 18 · 02 奖励投机（Reward Hacking）与古德哈特定律](../../../18-ethics-safety-alignment/02-reward-hacking-goodhart/docs/zh.md)：shortcut rationale 与 verifier 过度优化都是 Goodhart 的实例。
- [阶段 10 · 09 Constitutional AI 与自我改进](../../../10-llms-from-scratch/09-constitutional-ai-self-improvement/docs/zh.md)：另一类自我改进方法。

### 延伸关键词
`STaR` · `rationalization` · `expert iteration` · `rejection sampling fine-tuning` · `V-STaR` · `best-of-N` · `verifier` · `Quiet-STaR` · `process reward model (PRM)` · `outcome supervision` · `RLVR` · `shortcut learning` · `CoT faithfulness` · `OOD evaluation`
