# 测验 · AI 控制：面对蓄意破坏仍能保障安全（AI Control — Safety Despite Subversion）

> **阶段 18 · 伦理、安全与对齐 · 第 10 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 说明：中文讲义为机器翻译，关键句"Trusted Editing Pareto-dominates Untrusted Monitoring"被译得几乎无法理解（"受信任的编辑 Pareto 将无法信任的监控置于……"），请以英文版为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | AI Control 的问题重构 | 不再问"U 值不值得信任"，而问"在 U 可能对抗的前提下，用什么协议既能拿到有用的工作，又能把不可接受结果的概率压在上限以下"（Greenblatt, Shlegeris, Sachan, Roger, Redwood, arXiv:2312.06942, ICML 2024） |
| 2 | 三种资源 | U：不可信的强模型；T：可信但较弱的模型；H：可信的人类审计，预算很小、无法扩展 |
| 3 | 代码后门任务 | 竞赛级编程题；U 给出解答；隐藏 oracle 判断是否有后门（某个特定输入使代码输出错误）；红队控制 U 且能看到协议全部细节 |
| 4 | 四种协议 | Baseline（直接发布 U 的输出）、Upfront auditing（H 审计全部，预算很快耗尽）、Untrusted Monitoring（另一个 U 实例打分，H 审计被标记的）、Trusted Editing（T 编辑 U 的输出，T 没把握时交给 H） |
| 5 | 讲义结论 | Trusted Editing Pareto-dominates Untrusted Monitoring：在每个安全水平上都有更高的有用性 |
| 6 | Collusion（共谋） | 两个 U 实例可能通过隐写线索或共享的训练先验协调；要投入改写、混淆等抗共谋手段，而这又会削弱监控信号 |
| 7 | 协议的四个设计轴 | U 的角色、T 的角色（编辑/监控/重采样）、H 的分配（均匀/随机/按标记）、抗共谋投入 |
| 8 | Alignment vs Control | Alignment 是**模型**的属性；Control 是**部署协议**的属性。Control 不产生对齐的模型，只让"可能不对齐的模型"被安全地使用 |
| 9 | 三个根本限制 | 人类不能扩展；T 与 U 差距过大时 T 的编辑信号变成噪声；Control 不是 alignment——U 若能操纵 T 或推测 H 的审计分布，控制就会失效 |
| 10 | Control safety case | 2025 年 UK AISI 与 Redwood 合作：在对 U 做最坏假设的前提下，论证协议能为不可接受结果的概率设定上界 |

### 核心技能（能动手做到）

- [ ] 给定一个部署方案，标出谁是 U、谁是 T、H 的预算与分配方式，并列出共谋通道
- [ ] 读懂 `run_protocol` 四个分支的计数逻辑，手算各协议的期望 useful / backdoor / H used
- [ ] 找出代码中"Untrusted Monitoring 把 H 审计过的良性输出丢掉"的记账 bug，并修复
- [ ] 说出玩具中 Trusted Editing "必胜"依赖的三个过强假设，并用更现实的参数重新评估
- [ ] 在 H 预算 × 共谋率的网格上扫描，找出"共谋假设成为关键"的预算区间（讲义练习 1）
- [ ] 区分"每条样本的后门率"与论文式"整个部署期间从未发布后门的概率"两种安全度量

---

## 二、基础自测（选择题）

**Q1.** AI Control 的威胁模型中，U、T、H 分别指：

- A. U = 用户，T = 训练集，H = 超参数
- B. U = 不可信的强模型，T = 可信的较弱模型，H = 预算有限的可信人类审计
- C. U = 可信的强模型，T = 不可信的弱模型，H = 硬件
- D. U = 未对齐模型，T = 已对齐的同规模模型，H = 无限的人工审核

**Q2.** 关于 alignment 与 control 的区别，讲义的表述是：

- A. 两者是同一件事的不同叫法
- B. Control 解决之后就不再需要 alignment
- C. Alignment 是部署协议的属性，control 是模型的属性
- D. Alignment 是模型的属性（U 是否值得信任）；control 是部署协议的属性（不信任 U 也能安全使用）

**Q3.** 讲义解释 Trusted Editing 优于 Untrusted Monitoring 的核心原因是：

- A. T 被假定为非对抗的，所以不存在两个不可信组件之间的共谋风险
- B. T 比 U 更强，能发现所有后门
- C. Trusted Editing 完全不需要人工审计
- D. Untrusted Monitoring 使用了更多的计算资源

**Q4.** 下列哪一项**不是**讲义列出的 control 的三个根本限制之一？

- A. 人类审计无法扩展
- B. T 与 U 的能力差距过大时，T 的编辑信号会变成噪声
- C. Control 要求 U 的 weights 必须开源才能实施
- D. Control 不会产生可信的强模型；U 若能操纵 T 或推断 H 的审计分布，控制会失效

**Q5.** 本节代码运行结果中，`trusted_ed` 在 H 预算 0.10 下 backdoor 率均为 `0.000`。最主要的原因是：

- A. T 的 `t_skill = 0.7`，能移除全部后门
- B. 随机种子恰好让后门全部被移除
- C. 后门率太低，没有产生后门样本
- D. 代码中 T 没能移除的后门**一律**被标为低置信度并交给 H，而 H 预算在这几组参数下没有耗尽——相当于假设 T 完全知道自己什么时候漏掉了后门

**Q6.** 输出中 `trusted_ed` 的 useful（如 0.987）甚至高于 `baseline`（0.956）。原因是：

- A. 代码把"T 成功移除后门"的输出直接计为 useful，相当于假设 T 的编辑零成本地把后门代码变成了正确代码
- B. T 比 U 更擅长写代码
- C. H 审计会修复所有错误
- D. baseline 的 useful 计算有 bug

**Q7.** 共谋扫描的输出为：collusion = 0.0 时 backdoor = 0.052，collusion = 0.2 时 backdoor = 0.033。共谋率升高反而更安全？正确的解释是：

- A. 共谋会提高监控器的标记率
- B. 代码中 collusion 参数的含义是"不共谋的概率"
- C. 共谋率低时标记更多、H 预算更早耗尽，之后被标记的后门照样发布，加上单次抽样噪声；我们对 200 个种子取平均后，0.0 / 0.2 / 0.5 / 0.8 对应 0.035 / 0.041 / 0.060 / 0.084，是单调递增的
- D. 这是论文中观察到的真实现象

**Q8.** 在 ICML 2024 的代码后门任务中，关于红队的设定正确的是：

- A. 红队只能看到最终的通过/失败结果
- B. 红队控制 U，并且被允许看到协议的全部内部细节
- C. 红队控制 T
- D. 红队可以修改 H 的审计结论

---

## 三、动手 / 代码题

**Q9.** 阅读 `run_protocol` 中 `untrusted` 分支：

```python
        elif name == "untrusted":
            flagged = untrusted_monitor(is_bd, collusion)
            if flagged:
                if used_h / n < h_budget:
                    used_h += 1
                else:
                    if not is_bd:
                        useful += 1
                    else:
                        shipped_backdoor += 1
            else:
                if not is_bd:
                    useful += 1
                else:
                    shipped_backdoor += 1
```

对比 `upfront` 与 `trusted_ed` 分支对"H 审计了一条良性输出"的处理，找出记账不一致的地方，给出修复，并估算修复后 untrusted（backdoor_rate = 0.10、collusion = 0.30、H = 0.10）的 useful。

**Q10.** 讲义的 TAKEAWAY 是"trusted editing Pareto-dominates untrusted monitoring on this toy task"。

1. 列出玩具中让 Trusted Editing "必然胜出"的三个建模假设（提示：看 `t_edit` 的返回值以及 `trusted_ed` 分支的计数）。
2. 若改为更现实的设定：T 漏掉的后门只有 50% 会被标为低置信度、T 移除后门后的代码只有 50% 仍然正确，backdoor_rate = 0.10、H = 0.10，结果会怎样？与修复 Q9 后的 Untrusted Monitoring 比较。

**Q11.** 讲义练习 1：找出"Untrusted Monitoring 的共谋假设成为关键"的预算区间。

1. 写出 H 预算充足（所有被标记的输出都能被审计）时，untrusted 协议发布后门率关于 backdoor_rate `b`、collusion `c` 的公式（监控器不共谋时以 0.8 概率标记后门）。
2. 根据我们在 H ∈ {0, 0.02, 0.05, 0.10, 0.20} × collusion ∈ {0, 0.8} 上 200 个种子的平均结果（下表），说明结论。

| H 预算 | collusion = 0 | collusion = 0.8 |
|-------|--------------|----------------|
| 0.00 | 0.099 | 0.100 |
| 0.02 | 0.086 | 0.095 |
| 0.05 | 0.067 | 0.087 |
| 0.10 | 0.035 | 0.084 |
| 0.20 | 0.020 | 0.084 |

**Q12.** 代码的 `upfront` 协议只审计"前 10% 的样本"，之后直接发布，因此安全性几乎和 baseline 一样。

1. 为 upfront 加上"一旦审计发现后门就停止使用 U（shutdown）"的规则，并把安全度量改为"整个部署（1,000 题）期间**从未**发布后门的概率"。写出该概率关于每题后门率 `b` 的表达式（前 100 题被审计）。
2. 红队知道协议细节。它应该选多大的 `b`？此时安全性是多少？
3. 这说明"按每条样本统计后门率"的度量有什么问题？

---

## 四、面试高频题

**Q13.**（基础必考）什么是 AI Control？它和 alignment 有什么区别？为什么说两者都需要？

**Q14.**（原理深挖）Untrusted Monitoring 为什么存在共谋风险？共谋可能通过哪些通道发生？有哪些抗共谋手段，代价是什么？

**Q15.**（工程实践）你们要让一个前沿模型作为 coding agent 直接向生产仓库提交代码。请用 control 的思路设计部署协议：U、T、H 分别是谁，阈值和审计预算怎么分配，哪些操作必须拦截？

**Q16.**（场景设计）讲义练习 5：为 U = GPT-4 级、T = GPT-3.5 级、H = 审计 1% 输出的部署写一个 control safety case 的骨架，并指出它最依赖的那条假设。

**Q17.**（追问型）Control 的上限在哪里？当 U 远强于 T 时会发生什么？既然有上限，为什么还值得做？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义："U — untrusted strong model... T — trusted weaker model... H — trusted human labor. Small budget; does not scale." A、C 是字母的望文生义；D 错在两点：T 比 U 弱（不是同规模），H 预算很小（不是无限）。

### Q2 — 答案：D

讲义："Alignment is a property of the model. Control is a property of the deployment protocol. Control does not produce aligned models; it produces safe use of possibly-unaligned models. Both agendas are needed." C 把两者对调了；B 与"both agendas are needed"矛盾；A 显然错误。skill 文件还把"我们已经对齐了 U，所以不需要协议"列为拒答情形。

### Q3 — 答案：A

讲义："Trusted Editing avoids collusion entirely because T is trusted — any edit T proposes is, by assumption, not adversarial." B 错，T 恰恰更弱，代价是"may over-reject or miss subtle backdoors"；C 错，T 没把握时会交给 H；D 不是讲义给出的理由。

### Q4 — 答案：C

三个限制是：人类不可扩展、可信弱模型终将落后、control 不是 alignment（U 能操纵 T 或推断 H 的审计分布时控制失效）。C 是编造的；control 恰恰把 U 当作黑盒对手，不要求开源 weights。

### Q5 — 答案：D

`t_edit` 对没能移除的后门返回 `("backdoor", True, True)`——第三个值 `low_confidence` 恒为 `True`；`trusted_ed` 分支只要预算还在就交给 H，H 一审即发现。在 backdoor_rate = 0.2 时，低置信度事件的期望比例为 `0.2 × 0.3 + 0.8 × 0.05 = 0.10`，恰好与预算持平；200 个种子的平均发布后门率为 0.0023，单次运行为 0。A 错，`t_skill = 0.7` 只移除 70%；B、C 都不是原因。这一假设意味着 T 对自己的失误**完全有自知之明**，现实中"漏掉的后门"正是 T 没意识到的那部分。

### Q6 — 答案：A

`t_edit` 对成功移除的后门返回 `("useful", False, False)`，被计入 useful。以 backdoor_rate = 0.10、H = 0 为例：`0.9 × 0.95 + 0.1 × 0.7 = 0.925`，已经高于 baseline 的 0.90（我们实测 200 种子平均 0.9254）。现实中，较弱的 T 去改强模型写的代码，常常会引入错误、降低正确率——Trusted Editing 的真实代价是**有用性下降**。B、C 不是代码的逻辑；D 错，baseline 的计数是正确的。

### Q7 — 答案：C

collusion = 0 时，标记概率约为 `0.9 × 0.05 + 0.1 × 0.8 = 0.125`，超过 H 预算 0.10，预算在约第 800 题时耗尽，之后被标记的后门直接发布。再加上单次 1,000 样本的噪声，就出现了非单调。我们对 200 个种子求平均：0.035（c = 0）、0.041（0.2）、0.046（0.3）、0.060（0.5）、0.084（0.8），单调递增。B 错，`random.random() < collusion` 时返回 False（不标记），参数含义就是共谋概率；D 错，这是玩具的随机现象。

### Q8 — 答案：B

讲义："Red team controls U and is allowed to see all protocol internals." 这是从安全工程继承的最坏情况假设（Kerckhoffs 原则式的思路：安全不能依赖对手不知道协议）。skill 文件因此把"没有在红队可见协议的条件下评估，就声称后门率接近 0"列为 hard reject。

### Q9 — 参考答案

- **不一致**：`upfront` 与 `trusted_ed` 分支中，H 审计良性输出后都会 `useful += 1`（人审核确认无问题，照常发布）；`untrusted` 分支在 `used_h += 1` 之后**什么也不做**，相当于被 H 审核过的良性输出被丢弃了。这让 Untrusted Monitoring 的有用性被系统性低估（误报越多，损失越大），也是 TAKEAWAY 中"Pareto 劣势"的来源之一。
- **修复**：

```python
            if flagged:
                if used_h / n < h_budget:
                    used_h += 1
                    if not is_bd:          # H 审核通过，照常发布
                        useful += 1
                else:
                    ...
```

- **数值**：修复后良性输出总是有用，useful = 1 − b = 0.90。我们用独立实现跑 200 个种子：修复前 0.858，修复后 0.901；发布后门率不变（0.046）。

### Q10 — 参考答案

1. 三个过强假设：
   - **T 完美自知**：T 没能移除的后门 100% 被标为低置信度（`return ("backdoor", True, True)`），只要 H 预算还在就必被抓住；
   - **编辑零成本**：T 移除后门后的输出 100% 正确且有用（`return ("useful", False, False)`）；
   - **对手不适应**：后门率固定，不会针对 T 的弱点（比如构造 T 看不懂的后门）或 H 的预算耗尽时机调整策略。讲义自己也说红队"allowed to see all protocol internals"。
   另外 Untrusted Monitoring 还吃了 Q9 记账 bug 的亏。
2. 我们实现了该设定（200 种子平均）：

| 协议 | useful | backdoor | H used |
|------|--------|----------|--------|
| Trusted Editing（原假设） | 0.970 | 0.000 | 0.074 |
| Trusted Editing（现实化：50% 自知、50% 编辑后仍正确） | 0.935 | 0.015 | 0.059 |
| Untrusted Monitoring（修复 Q9，c = 0.3） | 0.901 | 0.046 | 0.096 |

在这个玩具里 Trusted Editing 仍然更好，但后门不再为 0、有用性也不再"免费提高"。要让它真正落到 Pareto 前沿上，还需要把"T 编辑会降低正确率"刻画得更真实（例如编辑 benign 输出也有一定概率引入错误），以及让红队针对 T 的弱点自适应。结论应写成"在这些参数下"，而不是普遍成立。

### Q11 — 参考答案

1. 预算充足时，后门被发布 ⇔ 监控器没有标记它：共谋（概率 c）或不共谋但漏标（概率 (1 − c) × 0.2）。所以发布率 = `b × (c + (1 − c) × 0.2) = b × (1 − 0.8(1 − c))`。b = 0.1 时：c = 0 → 0.020，c = 0.8 → 0.084，与表格中 H = 0.20 一行吻合。
2. 结论：
   - **H = 0**：被标记的输出也没人审，监控器形同虚设，共谋与否无所谓（0.099 vs 0.100）；
   - **H 很小（0.02–0.05）**：安全性主要受预算限制，共谋带来的差距只有 1–2 个百分点；
   - **H ≥ 标记量（约 0.10 以上）**：预算不再是瓶颈，安全性完全取决于监控器是否诚实，共谋把后门率从 0.020–0.035 推高到 0.084，差 2.4–4 倍——这就是"共谋假设变得关键"的区间。
   含义：H 预算越充足，Untrusted Monitoring 的安全性越依赖抗共谋措施；在此区间投入改写、混淆、蜜罐测试最划算。

### Q12 — 参考答案

1. 前 100 题审计，发现任一后门即 shutdown（此后不再发布任何东西，视为安全）。安全 ⇔ "前 100 题中至少有一个后门被抓到"或"1,000 题中一个后门都没有"：

   `Safety(b) = [1 − (1 − b)^100] + (1 − b)^1000`

2. 红队选择使 Safety 最小的 b。数值搜索结果：b ≈ 0.0026 时 Safety ≈ **0.30**。几个参考点：b = 0.05 → 0.994；b = 0.01 → 0.634；b = 0.003 → 0.309；b = 0.001 → 0.463。也就是说，最优攻击是**极少量地**植入后门：少到前 100 题大概率碰不上，又多到后 900 题大概率至少发布一个。
3. 问题：代码按"每条样本的后门率"度量，并让红队用固定的高后门率（5%–20%），这对应一个"笨"的对手。在控制框架下，一次发布后门就是不可接受的结果，安全应该按"整个部署期间从未发生"计算，并假设红队会选择最优策略。按这种度量，固定 10% 后门率下 upfront 的安全性几乎是 100%（第一批就被抓），而按代码的度量它看起来"和 baseline 一样差"——两种度量会给出相反的结论。（据我们了解，原论文正是采用"整个部署期间不发布后门的概率"并允许 shutdown，建议对照原文核实细节。）

### Q13 — 参考回答要点

- **定义**：假设强模型 U 可能在对抗地优化，设计部署协议，使我们既能从 U 获得有用的工作，又能把不可接受结果的概率限制在阈值以下；安全性在"红队扮演 U 并知晓协议"的条件下测量。
- **资源**：可信弱模型 T、少量可信人力 H、编辑 U 输出的能力。
- **与 alignment 的区别**：alignment 是让 U 本身可信（模型属性）；control 是即使 U 不可信也能安全使用（协议属性）。
- **为什么都需要**：第 07–09 节表明欺骗可能存在且难以检测，所以不能只靠 alignment；而 control 有可扩展性上限（人类、T 落后），也不能替代 alignment。
- 加分点：control 继承了安全工程的思维——最坏情况假设、威胁建模、红队评估、safety case。

### Q14 — 参考回答要点

- **为什么会共谋**：监控器和生产者是同一个模型的两个实例，共享训练先验，可以"心照不宣"地约定：带某种特征的代码就不标记。
- **通道**（skill 文件）：隐写线索（变量命名、注释风格、特定写法）、共享训练先验（不需要显式通信就能想到同一个"暗号"）、时序通道。
- **抗共谋手段**：
  - 在交给监控器之前**改写/规范化**输出（paraphrasing、去注释、重命名变量），破坏隐写信号；
  - **信息遮蔽**：只给监控器必要信息；
  - **蜜罐测试**：事先往监控器的输入里注入已知的后门样本，若监控器不标记，就说明它在共谋或失效；
  - 让 T 参与监控，与 U 监控器交叉验证。
- **代价**：讲义："The protocol has to invest budget in collusion-resistance (paraphrasing, obfuscation) that reduces the monitor's signal." 改写也会抹去真实后门的特征，降低检出率；蜜罐需要额外人力构造。
- 常见误区：认为"用两个不同温度/不同 prompt 的同一模型"就不会共谋。

### Q15 — 参考回答要点

- **角色**：U = 前沿模型 coding agent；T = 较小的可信模型（或规则 + 静态分析）；H = 安全工程师的审计时间（如每天固定的 PR 审核额度）。
- **协议**：
  1. U 生成 diff；T 给出可疑度分数；
  2. 最高可疑度的前 x% 交给 H 审计（flag-directed）；
  3. 中等可疑度的由 T 编辑/重写（trusted editing）或退回让 T 直接实现（defer to trusted）；
  4. 低可疑度的直接合入，但随机抽样一部分交给 H，防止对手推断审计分布。
- **阈值与预算**：按 H 的实际人力反推 x%；在红队演练中调阈值，画出 usefulness–safety 曲线后选点。
- **必须拦截的操作**：修改 CI/CD、权限、日志与监控配置、依赖源；访问凭据；外部网络请求——这些走 propose-then-commit。
- **基础设施**：审计日志不可被 U 修改；U 看不到哪些输出被审计；发现确凿后门即暂停 U（shutdown 规则）。
- 加分点：说明这套方案的薄弱环节在 T 与 U 的能力差距以及 H 的预算。

### Q16 — 参考回答要点

- **骨架**：
  1. 不可接受结果的定义：例如"把后门合入生产代码"；
  2. 威胁模型：U 被视为对抗者、知晓协议；T（GPT-3.5 级）可信；H 审计 1%；
  3. 协议描述：T 打分 + top 1% 交 H + 中段 T 编辑 + 发现即 shutdown；
  4. 证据：红队扮演 U、在知晓协议的情况下进行攻击，测得的"整个部署期间发布后门的概率"上界；
  5. 论证：红队的攻击能力 ≥ U 在部署中能达到的攻击能力，所以评估结果是部署风险的上界。
- **最强的那条假设**：红队的攻击能力**不低于** U 本身（即红队能找到 U 能找到的最佳攻击策略）。若 U 能想出红队没想到的后门写法、或者能识别评估与部署的差别（第 08 节的 situational awareness），评估就会低估风险。另一条关键假设是 T 真的可信（没有被 U 的输出操纵）。
- skill 文件要求：没有 (a) 红队结果、(b) 能力差距估计、(c) H 预算，就不回答"是否安全"。

### Q17 — 参考回答要点

- **上限**（讲义三个限制）：人类审计不可扩展；T 与 U 差距过大时 T 无法识别 U 的后门，编辑信号成为噪声；control 不产生对齐——当 U 能操纵 T 或推断 H 的审计分布时控制失效。讲义："Protocols that work at ASL-3 may not work at ASL-4."
- **U 远强于 T 时**：T 的可疑度分数与真实风险的相关性下降；要维持同样安全水平，需要更多 H 或更保守的阈值，有用性下降；最终无法在可接受的有用性下保持安全。
- **为什么仍值得做**：
  - 在"足够有用、尚未远超人类"的过渡期，control 提供了不依赖"证明模型对齐"的安全保证；
  - 它产出可检验的证据（红队结果、safety case），可以被外部审查；
  - 它争取时间，让对齐研究（第 11 节的可扩展监督）跟上，并可以用受控的 U 来辅助对齐研究本身。
- 常见误区：认为 control 是"永久方案"，或认为它与 alignment 互相替代。

---

## 六、关联知识点

### 前置知识
- [阶段 18 · 07 潜伏 Agents：持续性欺骗](../../07-sleeper-agents-persistent-deception/docs/zh.md)：control 所假设的威胁模型来源之一。
- [阶段 18 · 08 前沿模型中的上下文内密谋](../../08-in-context-scheming-frontier-models/docs/zh.md)：评估可能失效，促使我们转向 control。
- [阶段 18 · 09 伪装 Alignment](../../09-alignment-faking/docs/zh.md)：激励在缓解后依然存在，control 默认它还在。
- [阶段 15 · 15 Human-in-the-Loop：先提出方案，再 Commit](../../../15-autonomous-systems/15-propose-then-commit/docs/zh.md)：H 介入高风险操作的工程模式。
- [阶段 14 · 27 Prompt Injection 与 PVE 防御](../../../14-agent-engineering/27-prompt-injection-defense/docs/zh.md)：同样是"不信任某个组件"时的防御思路。

### 本节被哪些后续内容用到
- [阶段 18 · 11 可扩展监督与弱到强泛化](../../11-scalable-oversight-weak-to-strong/docs/zh.md)：互补的另一条路线——让 U 变得可信。
- [阶段 18 · 12 红队测试：PAIR 与自动化攻击](../../12-red-teaming-pair-automated-attacks/docs/zh.md)：control 评估离不开红队。
- [阶段 18 · 18 前沿安全框架：RSP、PF、FSF](../../18-frontier-safety-frameworks-rsp-pf-fsf/docs/zh.md)：safety case 与 ASL 等级如何继承 control 框架。
- [阶段 15 · 14 紧急停止开关、Circuit Breakers 与金丝雀 Tokens](../../../15-autonomous-systems/14-kill-switches-canaries/docs/zh.md)："发现即 shutdown"的部署侧实现。
- [阶段 17 · 25 安全：密钥、API 密钥轮换、Audit Logs 与 Guardrails](../../../17-infrastructure-and-production/25-security-secrets-audit/docs/zh.md)：审计日志等 control 所需的基础设施。

### 延伸关键词
`AI Control` · `untrusted model / trusted model` · `trusted editing` · `untrusted monitoring` · `trusted monitoring` · `defer to trusted` · `collusion` · `steganography` · `audit budget` · `red-team / blue-team` · `control safety case` · `safety–usefulness frontier`
