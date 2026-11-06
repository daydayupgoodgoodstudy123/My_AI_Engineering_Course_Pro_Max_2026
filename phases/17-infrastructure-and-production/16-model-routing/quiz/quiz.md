# 测验 · 将模型路由作为降低成本的基本手段（Model Routing as a Cost-Reduction Primitive）

> **阶段 17 · 基础设施与生产 · 第 16 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 模型路由 / 级联 | 由一个动态"经纪人"逐请求判断：简单的发给便宜模型，复杂的升级到 frontier 模型；讲义：案例显示在质量不变时可降本 20–60% |
| 2 | 四种路由信号 | 任务分类、prompt 长度（> 4K 常需 frontier，< 500 通常不需要）、与"已知困难集"的 embedding 相似度（cosine > 0.88 直接升级）、首轮的自我置信度 |
| 3 | 三种模式 | Pre-route（前置分类器，约 +5–10 ms，整体最快）；Cascade（先便宜后升级，中位延迟约 1.2 倍、升级请求约 2 倍，质量下限最好）；Ensemble（并行跑多个再用 reward model 选，只用于关键 A/B） |
| 4 | 成本按"成本占比"而非"条数占比"节省 | 简单请求往往更短，`main.py` 中 62.9% 的请求是 simple，但只占 frontier 成本的约 30.7%，所以 pre-route 只省 28.4% |
| 5 | 价格曲线 | 讲义表格：GPT-4 级质量从 2022 年末约 $20/M 降到 2026 年约 $0.40/M（50 倍）；frontier（GPT-5、Claude 4）约 $3–10/M；降价主要来自服务效率 |
| 6 | 实现载体 | AI 网关暴露路由能力：LiteLLM `router`、Portkey、Kong AI Gateway、OpenRouter；开源 RouteLLM，商业 Not Diamond |
| 7 | 真正的风险是漂移 | 任务分布随时间变化，路由器仍按旧数据把请求送去便宜模型，质量悄悄下降（"cheap creep"） |
| 8 | 在线质量门禁 | 每条路由的点赞 / 点踩、对 5% 留出样本做 LLM-judge、升级率（cascade 升级超过 30% 说明便宜模型被过度路由）、每条路由的拒答率 |
| 9 | 升级率是漂移的单一指标 | skill：滚动 7 天升级率变化超过 10 个百分点触发漂移告警 |
| 10 | 上线流程 | skill：shadow（只路由不生效、离线对比）→ 按用户群 10% 金丝雀 → 通过门禁后扩大 |

### 核心技能（能动手做到）

- [ ] 计算任意路由比例下的混合成本，并区分"按条数"与"按成本"两种占比
- [ ] 读懂 `simulate()` 的三种模式，指出 pre-route 使用了"完美分类器"、cascade 的置信度是"预言机"
- [ ] 给 pre-route 加入分类器准确率参数，找出 cascade 在成本和质量上同时占优的准确率区间
- [ ] 为 cascade 设计置信度信号（logprobs、拒答 / 含糊措辞检测）并给出初始阈值
- [ ] 写出升级率漂移告警，并理解滚动窗口告警的滞后性
- [ ] 设计 shadow → canary → 全量的路由上线计划与在线质量门禁

---

## 二、基础自测（选择题）

**Q1.** 讲义对 "model cascading" 的定义是：

- A. 把同一个请求同时发给所有模型，取最快返回的结果
- B. 按用户付费等级固定分配模型
- C. 先用便宜模型处理，置信度低（或拒答、含糊）时再升级到 frontier 模型
- D. 把长 prompt 切成多段分别交给不同模型

**Q2.** 下列哪一组是讲义列出的四种路由信号？

- A. 任务分类、prompt 长度、与已知困难集的 embedding 相似度、首轮自我置信度
- B. 用户地区、时间段、设备类型、网络延迟
- C. 模型参数量、上下文窗口、训练数据截止日期、许可证
- D. 输出长度、温度、top-p、停止词

**Q3.** 关于三种路由模式的延迟特征，与讲义一致的是：

- A. Cascade 不增加任何延迟
- B. Pre-route 约增加 5–10 ms，整体最快；Cascade 中位延迟约 1.2 倍、被升级的请求约 2 倍
- C. Ensemble 最快，因为并行执行
- D. Pre-route 会让每个请求的延迟翻倍

**Q4.** 讲义 The Problem：每月 $80k 全部用 GPT-5，70% 的请求是简单请求，可以交给成本只有 3% 的 Haiku 级模型，30% 仍用 GPT-5。若假设每个请求的成本相同，账单会下降约：

- A. 30%
- B. 50%
- C. 97%
- D. 68%

**Q5.** 运行 `main.py`，CASCADE 的 `escalated=229`（1,000 个请求）。最准确的解释是：

- A. 229 是随机噪声，与难度分布无关
- B. 工作负载中 hard 有 95 个（全部升级），medium 有 276 个（约一半升级，期望 138），合计期望约 233；升级率约 22.9%，高于讲义说的"约 10% 流量"，但低于讲义"超过 30% 说明过度路由"的门槛
- C. simple 请求有 22.9% 被升级
- D. 说明便宜模型已经被过度路由，必须立即回滚

**Q6.** 运行结果中 CASCADE 的质量（98.2%）**低于** PRE_ROUTE（99.4%），这与讲义"cascade 质量下限最好"相矛盾。原因是：

- A. 代码的 `quality()` 函数写反了
- B. Cascade 调用了两次模型，导致质量下降
- C. PRE_ROUTE 直接使用真实难度标签（相当于 100% 准确的分类器），而 CASCADE 的置信度规则让约一半 medium 请求留在便宜模型上（质量 0.92）
- D. 随机种子不同造成的

**Q7.** 讲义认为最能发现"cheap-model drift"的做法是：

- A. 用在线质量指标给路由设门禁：每条路由的点赞 / 点踩、对 5% 留出样本做 LLM-judge、升级率、拒答率
- B. 每季度重新跑一次离线评测集即可
- C. 只看总成本是否下降
- D. 把便宜模型换成更大的模型

**Q8.** 讲义表格显示 GPT-4 级质量的价格从 2022 年末约 $20/M 降到 2026 年约 $0.40/M。按约 3–3.3 年计算，这对应的**年均**降幅大约是：

- A. 10 倍 / 年
- B. 50 倍 / 年
- C. 1.5 倍 / 年
- D. 3.3–3.7 倍 / 年

---

## 三、动手 / 代码题

**Q9.** 用 `make_workload()` 默认参数（种子 7）统计：

| 难度 | 条数 | 全走 frontier 的成本 | 全走 cheap 的成本 |
|------|------|-------------------|-----------------|
| simple | 629 | $2.306 | $0.172 |
| medium | 276 | $2.627 | $0.202 |
| hard | 95 | $2.585 | $0.196 |

1. 用这张表推导 PRE_ROUTE 的成本 $5.38 和节省比例 28.4%。
2. simple 占了 62.9% 的请求，为什么只省了 28.4%？这对讲义 The Problem 里"省约 65%"的估算有什么启示？
3. 推导 CASCADE 的期望成本（medium 以 50% 概率升级）。

**Q10.**（讲义练习 1）PRE_ROUTE 在代码里用的是真实难度标签。请给它加一个分类器准确率 `acc`：simple 请求以概率 `acc` 被正确送去 cheap，否则送去 frontier；medium/hard 请求以概率 `1 − acc` 被误送去 cheap。用期望值（不抽样）计算 `acc` = 1.0、0.9、0.8、0.72 时的成本与平均质量，并回答：准确率低于多少时，cascade（期望成本约 $4.47、质量约 98.27%）在成本和质量上**同时**优于 pre-route？

**Q11.** 对照讲义与代码，找出至少 5 处不一致或过度简化（提示：Use It 一节说模拟了哪几种模式；结尾打印的结论；置信度从哪里来；延迟；讲义里"3% 的成本"与代码价格；"每年约 10 倍"）。

**Q12.**（讲义练习 5 + skill）六个月里升级率从 8% 涨到 22%。

1. 写一个 `escalation_drift(daily_rates, window=7, threshold_pts=10)`：比较最近 7 天与前 7 天的平均升级率，变化超过 10 个百分点返回 `True`。
2. 用两组数据测试：14 天恒为 8%；前 7 天 8%，后 7 天依次为 10%、13%、16%、19%、21%、22%、22%。第二组会触发吗？再多一天 22% 呢？这说明了什么？
3. 给出升级率上涨的三个可能原因及对应修复。

---

## 四、面试高频题

**Q13.**（基础必考）什么是模型路由？pre-route、cascade、ensemble 三种模式各自的成本、延迟、质量特征是什么，分别适合什么场景？

**Q14.**（原理深挖）Cascade 的"置信度"从哪里来？logprobs、拒答 / 含糊措辞检测、自一致性、外部校验器各有什么问题？你会用什么阈值起步（讲义练习 4）？

**Q15.**（工程实践）你要在一个月花费 $80k 的服务上上线路由。请给出从离线评估到全量的完整步骤，以及上线后的在线质量门禁。

**Q16.**（场景设计）用户中 30% 是企业客户（复杂请求多），70% 是免费用户（简单请求多）。你怎么设计路由策略？用什么在线指标做门禁（讲义练习 2）？

**Q17.**（追问型）一个路由方案让质量下降 2%、成本下降 40%。要不要上线？请分别论证"上"和"不上"（讲义练习 3）。

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义："Explain model cascading: cheap-first with confidence check, escalate on low confidence." 第 4 个信号也描述了这个流程："send to cheap; if model's log-probs show low confidence OR it refuses OR outputs hedging language, retry on frontier."

- A 更接近 ensemble 或"竞速"，不是 cascade。
- B 是静态分配，不是逐请求动态路由。
- D 与路由无关。

### Q2 — 答案：A

讲义的 Four routing signals：task classification、prompt length、embedding similarity to known-hard set、self-confidence from first-pass。

- B、C、D 都不是讲义列出的信号。skill 还强调"只用任务分类一个信号要拒绝——会漏掉同一任务内部的难度差异"。

### Q3 — 答案：B

讲义："Pre-route (classifier up front): ~5-10ms latency added; fastest overall." "Cascade ... ~1.2x median latency (cheap run plus verify), ~2x on escalated."

- A 错：cascade 至少多一次校验，被升级的请求要跑两次。
- C 错：ensemble 并行跑多个模型并用 reward model 选择，成本最高，延迟取决于最慢的那个。
- D 错：分类器只增加几毫秒。

### Q4 — 答案：D

新成本占比 = `0.3 × 1 + 0.7 × 0.03 = 0.321`，下降约 **67.9%**（实际计算），讲义写"~65%"。

- A 是把 30% 的 frontier 份额误当作节省比例。
- B 无依据。
- C 是假设全部都走便宜模型。

注意前提"每个请求的成本相同"：简单请求通常更短，实际节省会小得多（见 Q9）。另外按 `main.py` 的价格，cheap 的输入 / 输出单价分别是 frontier 的 8.3%（0.25/3）和 6.7%（1/15），并不是 3%。

### Q5 — 答案：B

代码规则：simple 一律"自信"（不升级），hard 一律升级，medium 以 50% 概率升级。工作负载中 hard 95 个、medium 276 个，期望升级数 `95 + 276 × 0.5 = 233`，实际 229。

- A 错：主要由难度分布决定。
- C 错：simple 从不升级。
- D 错：讲义的过度路由门槛是 > 30%；22.9% 偏高（讲义说升级约影响 10% 流量），值得关注但不是立即回滚的信号。

### Q6 — 答案：C

PRE_ROUTE 中 `if q.difficulty == "simple"` 直接读取真实难度，等于假设分类器 100% 准确：只有 simple 走 cheap（质量 0.99），平均质量 `(629 × 0.99 + 371) / 1000 = 99.37%`。CASCADE 中约 138 个 medium 留在 cheap（0.92），拉低到 98.2%。

- A 错：`quality()` 逻辑正确。
- B 错：被升级的请求取 frontier 的结果，质量为 1.0。
- D 错：PRE_ROUTE 根本不使用随机数。

要让 cascade 体现"质量下限"优势，必须让 pre-route 的分类器有误差（见 Q10）。

### Q7 — 答案：A

讲义："Gate routes by online quality metrics" 并列出四项；摘要也强调 "Gate routes by online quality metrics, not just offline eval sets."

- B 不够：离线评测集来自旧分布，正是漂移发现不了的原因。
- C 错：成本下降恰恰可能是"过度路由到便宜模型"的结果。
- D 不是监控手段。

### Q8 — 答案：D

`50^(1/3.3) ≈ 3.27`，`50^(1/3) ≈ 3.68`（实际计算）。即年均降价约 3.3–3.7 倍。

- A 是讲义摘要与 "Numbers you should remember" 中的说法（"~10x per year aggregate"），但与讲义自己表格里的数字不一致：若每年 10 倍，3 年就是 1,000 倍。可能的解释是讲义的"每年 10 倍"指"同等能力的最便宜价格"这类更宽口径的统计，但在本节内部两组数字相互矛盾，引用时要说明口径。
- B 是总降幅。
- C 太小。

### Q9 — 参考答案

1. PRE_ROUTE：simple 走 cheap、其余走 frontier：`0.172 + 2.627 + 2.585 = $5.384`；基线（全 frontier）`2.306 + 2.627 + 2.585 = $7.518`；节省 `(7.518 − 5.384) / 7.518 ≈ 28.4%`，与运行输出一致。
2. simple 请求短（prompt 200–1000、输出 50–200），只占 frontier 成本的 `2.306 / 7.518 ≈ 30.7%`。路由能省的上限就是"被路由走的那部分的成本 × (1 − 便宜/昂贵价格比)"，而不是请求条数占比。讲义 The Problem 的"省约 65%"隐含了"每个请求成本相同"的假设；真实流量里简单请求更短、困难请求更长（hard 只占 9.5% 的条数却占 34% 的成本），估算时必须按**成本**占比算。
3. CASCADE 期望成本：所有请求都先跑 cheap（`0.172 + 0.202 + 0.196 = 0.570`），再加 hard 全部升级（2.585）和 medium 一半升级（`0.5 × 2.627 = 1.3135`），合计约 **$4.47**；实际运行 $4.42（抽样波动）。节省约 41%，比 pre-route 多，是因为它把一半 medium 留在了 cheap——代价是质量下降。

### Q10 — 参考答案

```python
def pre_route_expected(reqs, acc):
    cost = qual = 0.0
    for q in reqs:
        p_cheap = acc if q.difficulty == "simple" else 1 - acc
        cost += p_cheap * cost_of("cheap", q) + (1 - p_cheap) * cost_of("frontier", q)
        qual += p_cheap * quality("cheap", q) + (1 - p_cheap) * 1.0
    return cost, qual / len(reqs)
```

实际计算结果：

| acc | 成本 | 平均质量 |
|-----|------|---------|
| 1.00 | $5.38 | 99.37% |
| 0.90 | $5.12 | 98.98% |
| 0.80 | $4.85 | 98.58% |
| 0.72 | $4.63 | 98.26% |
| 0.70 | $4.58 | 98.19% |

- 准确率约 **72%** 时，pre-route 的质量降到与 cascade 相同（约 98.27%），而成本 $4.63 仍高于 cascade 的 $4.47。所以准确率低于约 72% 时，cascade 在成本和质量上同时占优。
- 准确率高于 72% 时是**权衡**：pre-route 质量更高但更贵。
- 这个结论依赖代码的特定假设（cascade 的置信度规则本身是"半预言机"：simple 永远不升级、hard 永远升级），真实系统中 cascade 的置信度也会出错，结论需要用真实数据重做。

### Q11 — 参考答案

1. **Ensemble 没有实现**：讲义 Use It 说 "simulates pre-route, cascade, and ensemble"，代码只有 NO_ROUTE、PRE_ROUTE、CASCADE。
2. **结论与输出矛盾**：结尾打印 "CASCADE guarantees quality floor"，但输出中 CASCADE 质量（98.2%）低于 PRE_ROUTE（99.4%）。
3. **完美分类器**：PRE_ROUTE 直接读真实难度标签，等于假设分类器 100% 准确，掩盖了 pre-route 最主要的风险。
4. **置信度是"预言机"**：CASCADE 的置信度由真实难度决定（simple 永远自信、hard 永远不自信），现实中会出现"便宜模型自信地答错"的情况，代码没有建模。
5. **延迟没有模拟**：结论提到 "adds latency on escalated requests"，讲义也给出 1.2 倍 / 2 倍，但代码没有任何延迟计算。
6. **"3% 的成本"与价格常量不符**：按代码价格，cheap 的单价是 frontier 的 6.7%–8.3%。
7. **"每年约 10 倍"与表格不符**：表格 50 倍跨越约 3 年，年均约 3.5 倍（见 Q8）。
8. 次要：`rng = random.Random(11)` 在 NO_ROUTE 和 PRE_ROUTE 中创建了却没用；质量分数是固定值，不是从评测得到。

### Q12 — 参考答案

1. 实现：

```python
def escalation_drift(daily_rates, window=7, threshold_pts=10.0):
    if len(daily_rates) < 2 * window:
        return False, 0.0
    recent = sum(daily_rates[-window:]) / window
    previous = sum(daily_rates[-2 * window:-window]) / window
    delta_pts = (recent - previous) * 100
    return delta_pts > threshold_pts, round(delta_pts, 1)
```

2. 实际运行：恒为 8% → `(False, 0.0)`；第二组 → `(False, 9.6)`，**没有触发**；再追加一天 22% → `(True, 11.0)`，第二天才触发。说明滚动均值比较有**滞后**：升级率已经从 8% 涨到 22%（+14 个百分点），告警却还没响。实践中可以同时加一个"单日值相对基线"的规则，或使用讲义的绝对阈值（升级率 > 30% 即视为过度路由）。
3. 三个原因与修复：
   - **用户分布变化**（讲义：用户越来越熟练、问题越来越长）：分类器基于 Q1 数据训练 → 用近期流量重新标注、重训分类器，更新"已知困难集"。
   - **便宜模型或其版本变化**（provider 静默更新、换了模型）：置信度分布整体偏移 → 固定模型版本，对新版本重新校准置信度阈值。
   - **产品新功能引入新任务类型**（如新增代码 / 多步规划功能）：便宜模型频繁拒答或含糊 → 为新任务类型增加专门路由（直接 pre-route 到 frontier），并按任务类型分别统计升级率。
   - 无论哪种原因，都要同时检查每条路由的在线质量（LLM-judge、点赞率），区分"升级率上升但质量稳定"（门禁在正常工作）和"质量也在下降"（漂移）。

### Q13 — 参考回答要点

- **定义**：逐请求决定由哪个模型处理，把简单请求交给便宜模型、复杂请求交给 frontier 模型，把整体价格下降转化为利润，同时不让产品质量倒退。
- **Pre-route**：前置分类器（规则、小模型或 embedding），约 +5–10 ms，最快、最省；风险是分类器误判，难的请求被送去便宜模型且没有兜底。适合流量大、任务类型清晰的场景。
- **Cascade**：先便宜后升级，中位延迟约 1.2 倍，被升级的约 2 倍；质量下限最好，因为有兜底；升级的请求付两次费用。适合"零回退"要求（skill：质量容忍为零时拒绝 pre-route，改用 cascade）。
- **Ensemble**：并行跑多个模型再由 reward model 选，质量最高、成本最高，只用于关键 A/B 或采样评估。
- 加分点：组合使用——先用 pre-route 把明显的难题直接送 frontier（如与已知困难集 cosine > 0.88、prompt > 4K），其余走 cascade。

### Q14 — 参考回答要点

- **logprobs**：用输出 token 的平均对数概率或最小概率衡量置信度。问题：模型校准不佳，"自信地答错"；长输出的平均值会掩盖关键 token 的低置信；不同 provider 对 logprobs 的支持程度不同。
- **拒答 / 含糊措辞检测**：讲义列出的信号之一，便宜实用，但只能捕捉"知道自己不会"的情况。
- **自一致性**：多次采样看答案是否一致，准确但成本成倍增加。
- **外部校验器**：代码可以跑测试、JSON 可以做 schema 校验、数学可以验算——有可校验结构的任务首选。
- **起步阈值**：在离线标注集上画"升级率 vs 质量"曲线，选能让质量回退 ≤ 目标（如 skill 的 2%）的阈值；先设保守阈值（升级多一些），上线后逐步放宽。讲义提到升级约影响 10% 流量、超过 30% 视为过度路由，可以作为参考区间。
- 常见误区：直接用一个固定的 logprob 阈值而不做校准；只在离线集上调阈值。

### Q15 — 参考回答要点

1. **采样标注**：从生产流量抽样，按任务类型 / 难度标注，估算各类请求的**成本占比**（不是条数占比）。
2. **选模型对**：skill 示例 Claude Haiku 3.5 + GPT-5；跨 provider 时必须经 AI 网关统一 API。
3. **离线评估**：在标注集上比较 pre-route、cascade 的成本与质量，确定信号组合（通常 2–3 个）与阈值。
4. **Shadow**：线上只计算路由决策、不生效，离线对比"如果路由会怎样"。
5. **Canary**：按用户群放 10% 流量，监控门禁。
6. **扩量**：通过门禁后逐步放大。
7. **在线门禁**（skill）：每条路由 5% 抽样由 frontier judge 评估，质量差超过 2% 告警；升级率一个月内上升超过 10 个百分点告警；点赞率、拒答率分路由统计。
8. **回滚**：网关层一键切回全 frontier。
- 加分点：给每个请求打上 `route`、`escalated` 属性（OTel），在 observability 平台按路由切片。

### Q16 — 参考回答要点

- **按群体分层而不是一刀切**：企业用户的请求更复杂、错误代价更高 → 默认 cascade，阈值保守，或直接 pre-route 到 frontier 的比例更高；免费用户 → 以 pre-route 为主，配合 cascade 兜底。
- **信号**：任务分类 + prompt 长度 + 与已知困难集的相似度；企业租户可以额外使用"租户历史难度"。
- **门禁指标**：按"用户群 × 路由"分别统计 LLM-judge 质量、点赞率、升级率、拒答率；企业群的质量阈值更严格（如 Δ 质量 > 1% 即告警）。
- **成本估算**：按成本占比（企业请求更长、占成本更多）计算节省，而不是按 70/30 的人数比例。
- 常见误区：只按付费等级路由——免费用户也会问难题，企业用户也有大量简单请求；skill 明确拒绝"只用任务分类一个信号"。

### Q17 — 参考回答要点

- **可以上线的情形**：
  - 低风险、对质量不敏感的功能（改写、闲聊、摘要草稿），2% 的下降用户感知不到；
  - 40% 的节省可以转化为更低价格或更多免费额度，带来更大的用户价值；
  - 可以把下降集中在"可接受"的请求上，并保留 cascade 兜底。
- **不应上线的情形**：
  - 推理、代码、医疗、金融等高风险任务，2% 的错误可能带来远超节省的损失（讲义：便宜模型在推理任务上质量下降 3–5% 却一个季度没人发现）；
  - 2% 是平均值，若集中在少数高价值客户上，局部下降可能是 10%+；
  - 没有在线门禁，下降会随漂移继续扩大。
- **决策方法**：把质量下降换算成业务指标（转化、留存、工单量）与节省比较；按任务类型分开决策；先 canary 再扩量。skill 的门禁阈值是"Δ 质量 > 2% 告警"，2% 正好处在边界上，需要按产品具体判断。

---

## 六、关联知识点

### 前置知识
- [阶段 17 · 01 托管 LLM 平台：Bedrock、Vertex AI、Azure OpenAI](../../01-managed-llm-platforms/docs/zh.md)：可供路由选择的模型与平台。
- [阶段 17 · 02 Inference 平台经济性：Fireworks、Together、Baseten、Modal、Replicate、Anyscale](../../02-inference-platform-economics/docs/zh.md)：不同模型、平台的价格结构。
- [阶段 13 · 21 LLM 路由层：LiteLLM、OpenRouter、Portkey](../../../13-tools-and-protocols/21-llm-routing-layer/docs/zh.md)：路由层的协议与工具视角。
- [阶段 11 · 10 Evaluation 与 LLM 应用测试](../../../11-llm-engineering/10-evaluation/docs/zh.md)：离线评估与 LLM-judge 的基础。

### 本节被哪些后续内容用到
- [阶段 17 · 19 AI 网关：LiteLLM、Portkey、Kong AI Gateway、Bifrost](../../19-ai-gateways/docs/zh.md)：在网关中落地路由与故障转移。
- [阶段 17 · 20 面向 LLMs 的 Shadow Traffic、金丝雀 Rollout 与渐进式部署](../../20-shadow-canary-progressive/docs/zh.md)：路由方案的 shadow → canary 上线流程。
- [阶段 17 · 21 对 LLM Features 进行 A/B 测试：GrowthBook、Statsig 与凭感觉判断的问题](../../21-ab-testing-llm-features/docs/zh.md)：评估"质量降 2%、成本降 40%"这类决策。
- [阶段 17 · 27 LLMs 的 FinOps：单位经济性与多租户成本归因](../../27-finops-llms/docs/zh.md)：把路由节省纳入单位经济性。
- [阶段 17 · 13 LLM Observability 技术栈选型](../../13-llm-observability/docs/zh.md)：按路由切片的在线质量监控。
- [阶段 15 · 13 行动预算、迭代上限与成本控制](../../../15-autonomous-systems/13-cost-governors/docs/zh.md)：Agent 场景下的成本控制。

### 延伸关键词
`model cascade` · `pre-route classifier` · `ensemble routing` · `RouteLLM` · `Not Diamond` · `LiteLLM router` · `escalation rate` · `logprob confidence` · `calibration` · `LLM-as-judge` · `online quality gate` · `shadow traffic` · `cheap-model drift`
