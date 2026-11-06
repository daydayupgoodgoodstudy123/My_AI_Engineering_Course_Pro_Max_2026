# 测验 · LLM 生产环境中的混沌工程（Chaos Engineering for LLM Production）

> **阶段 17 · 基础设施与生产 · 第 24 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 五个前置条件 | SLI/SLO、可观测性（trace + metric + log）、自动回滚、结构化 runbook、on-call；缺任何一个，混沌实验就会变成真实事故 |
| 2 | 四个平面 + 反馈环 | 控制面（实验调度）、目标面（服务/Pod/节点/LB/数据存储）、安全面（kill switch、抑制窗口、爆炸半径上限、错误预算门）、可观测面（指标 + trace-ID 关联）；结论反馈到 SLO、runbook 与代码 |
| 3 | Burn-rate 门 | 讲义：当日错误预算消耗速度超过预期 2 倍时暂停实验；burn rate 是"实际错误率 / SLO 允许的错误率" |
| 4 | 抑制窗口与 trace-ID 关联 | 实验期间静默爆炸半径内的非实验告警；所有实验引发的错误带标签，on-call 能区分"混沌造成的"和"自然发生的" |
| 5 | 五个 LLM 专属实验 | 内存过载（KV cache 抢占风暴）、网关到 provider 网络中断、provider 100% 429、畸形 prompt（tokenizer 卡死）、KV 驱逐风暴（re-prefill 级联） |
| 6 | LLM 新增的失效模式 | 讲义：含毒字符的 4K prompt 让 tokenizer 卡 12 秒；上游 429 → 网关重试 → 重试放大并发导致 OOM；突发负载下 KV 驱逐引发重新 prefill 级联、算力饱和 |
| 7 | 节奏 | 每周：小规模金丝雀实验 + SLO 回顾；每月：game day + 复盘；每季度：跨团队韧性审计 + 依赖图更新 |
| 8 | 工具 | Harness Chaos Engineering（商业，AI 推荐实验、爆炸半径自动缩小、MCP 集成）、LitmusChaos（workflow 式）、Chaos Mesh（CRD 式）、Gremlin、AWS FIS / Azure Chaos Studio。注意：讲义称 Litmus 为 CNCF graduated、Chaos Mesh 为 sandbox，而 CNCF 公告显示两者在 2022 年都已进入 incubating，成熟度级别以 CNCF 官网当前状态为准 |
| 9 | 从小处开始 | 第一个实验：稳态流量下杀掉 1 个 decode 副本；第一个 LLM 专属实验：注入 5 分钟 provider 429，多数团队会发现 fallback 从未被完整测试过 |
| 10 | 本节代码的关键问题 | burn rate 以"预期基线错误率"为分母而不是错误预算；安全门要求"burn > 2 **且** 爆炸半径 > 20%"，于是 80 倍 burn 的畸形 prompt 实验照样跑完 |

### 核心技能（能动手做到）

- [ ] 在开始任何生产混沌实验前，逐项核对五个前置条件，并能说明缺了某一项会发生什么
- [ ] 画出四个平面与反馈环，为每个平面选出具体工具
- [ ] 正确计算 burn rate 与一次实验消耗的错误预算比例
- [ ] 读懂 `run_experiment()` 的门控逻辑，指出它与讲义"burn > 2x 即暂停"的差异并修正
- [ ] 为一个基于 vLLM 的 RAG 服务设计前五个实验，每个都有爆炸半径、时长、成功标准
- [ ] 当 burn-rate 告警暂停实验时，用 trace-ID 标签区分混沌引发与自然发生的错误

---

## 二、基础自测（选择题）

**Q1.** 下列哪一项**不在**讲义列出的"生产混沌实验五个前置条件"中？

- A. 自动回滚
- B. 一个专门的混沌工程团队
- C. 结构化 runbook
- D. 有人值守的 on-call

**Q2.** 关于混沌工程的"安全面（safety plane）"，正确的是：

- A. 负责调度实验，例如 Litmus workflow、Chaos Mesh schedule
- B. 指被注入故障的服务、Pod、节点与数据存储
- C. 只包含 dashboard，用来事后看实验结果
- D. 包括 kill switch、抑制窗口、爆炸半径上限、错误预算门，负责在实验失控前中止它

**Q3.** 实验期间，on-call 收到大量告警，无法判断哪些是实验造成的。讲义给出的对策是：

- A. 给所有实验引发的错误打上 trace-ID 标签以便去重，并在爆炸半径内设置抑制窗口
- B. 实验期间关闭所有告警
- C. 只在凌晨流量最低时做实验，这样不会有告警
- D. 把实验移到 staging，生产永远不做混沌

**Q4.** 上游 provider 返回 429，网关不断重试，最终自家服务 OOM。这个失效链最能体现：

- A. tokenizer 卡死
- B. KV 驱逐风暴导致 re-prefill 级联
- C. 重试放大并发（retry amplification）：429 → 重试 → 并发翻倍 → 内存耗尽
- D. 抑制窗口配置错误

**Q5.** SLO 为 99.9%，某时段实际错误率为 0.5%。按标准定义，这一时段的 burn rate 是：

- A. 5 倍
- B. 0.5 倍
- C. 10 倍
- D. 2 倍

**Q6.** 运行本节代码，"malformed prompt tokenizer stall"（错误率 4%、爆炸半径 10%）显示 COMPLETED。原因是：

- A. 它只持续 3 分钟，代码按时长豁免
- B. 它的 burn rate 只有 0.8 倍，低于 2 倍门槛
- C. 代码的暂停条件是 `burn_rate > 2.0 and blast_radius_pct > 0.2`，爆炸半径 10% 不满足后半句，所以即使 burn 80 倍也不暂停
- D. 畸形 prompt 不产生 5xx 错误

**Q7.** 讲义推荐的混沌实验节奏是：

- A. 每天一次 game day
- B. 只在大版本发布前做一次
- C. 每季度一次金丝雀实验
- D. 每周小规模金丝雀 + SLO 回顾；每月 game day + 复盘；每季度跨团队韧性审计 + 依赖图更新

**Q8.** 关于"第一个实验"，讲义的建议是：

- A. 直接在生产上模拟整个区域宕机
- B. 先在稳态流量下杀掉 1 个 decode 副本，观察重路由与恢复；LLM 专属的第一个实验是注入 5 分钟 provider 429
- C. 先做 KV 驱逐风暴，因为它最贴近 LLM
- D. 先做畸形 prompt，因为它爆炸半径最小

---

## 三、动手 / 代码题

**Q9.** 阅读核心代码：

```python
ERROR_BUDGET_PER_DAY = 0.001   # 99.9% SLO
EXPECTED_ERROR_RATE = 0.0005

def run_experiment(e: Experiment) -> dict:
    burn_rate = e.induced_error_rate / max(EXPECTED_ERROR_RATE, 0.0001)
    paused = burn_rate > 2.0 and e.blast_radius_pct > 0.2
```

1. 写出三个实验的 `burn_rate`，以及哪个被 ABORTED（讲义练习 1）。
2. 如果按标准定义（分母是错误预算 0.001）重新计算 burn rate，三个数字分别是多少？
3. 按讲义"daily error-budget burn exceeds 2x expected → pause"（不附加爆炸半径条件），哪些实验应当被暂停？

**Q10.** 假设 `induced_error_rate` 是**爆炸半径内**的错误率，即全服务的有效错误率 = `induced_error_rate × blast_radius_pct`。

1. 计算三个实验的有效错误率与标准 burn rate。
2. 把一天的错误预算看作"0.1% × 1,440 分钟"，计算每个实验持续期间消耗了当日错误预算的百分之几。
3. skill 文件要求爆炸半径 < 30%。哪个实验违反了这一上限？

**Q11.** 改写 `run_experiment`，要求：

- burn rate 以错误预算为分母，并考虑爆炸半径；
- burn > 2 即暂停，与爆炸半径无关；
- 爆炸半径 ≥ 30% 的实验直接拒绝运行；
- 输出中断原因列表。

写出代码与运行结果。

**Q12.**（讲义练习 2）为一个基于 vLLM 的 RAG 服务设计前五个混沌实验。每个实验写出：注入方式、爆炸半径、时长、观察指标、成功标准、中止条件。

---

## 四、面试高频题

**Q13.**（基础必考）什么是混沌工程？为什么说"没有 SLO 就不要做混沌实验"？

**Q14.**（原理深挖）解释 error budget 与 burn rate。为什么用 burn rate 而不是"错误率超过阈值"来做混沌实验的中止条件？多窗口 burn-rate 告警解决了什么问题？

**Q15.**（工程实践）（讲义练习 5）说出三个通用网络混沌工具无法复现的 LLM 专属失效模式，并说明如何注入。

**Q16.**（场景设计）（讲义练习 3）burn-rate 告警在实验期间暂停了实验。你如何判断根因是混沌注入还是同时发生的自然故障？

**Q17.**（追问型）（讲义练习 4）混沌实验应该在生产做还是只在 staging 做？什么时候生产才是正确答案？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义的五项："SLI/SLO、Observability、Automated rollback、Runbooks、On-call"，并强调"Missing any means chaos becomes real incident"。专门的混沌团队不是前置条件，讲义的 game day 反而强调跨团队参与。

### Q2 — 答案：D

讲义："Safety plane — kill switch, suppression windows, blast-radius limits, error-budget gates." A 是控制面；B 是目标面；C 把可观测面理解得太窄，可观测面还要负责用 trace-ID 关联区分混沌与自然故障。

### Q3 — 答案：A

讲义："Suppression windows: silence non-experiment alerts in the blast radius during experiment"；"Trace-ID correlation: all experiment-induced errors carry a tag so on-call can dedupe." B 会让真实事故被掩盖；C 不能消除告警，且低峰期的结论不一定代表高峰；D 与讲义"weekly... maybe 5% prod"的做法不符。

### Q4 — 答案：C

讲义问题部分："An upstream provider 429s; your gateway retries; your service OOMs on retry-amplified concurrency." 修复方向：重试预算、指数退避 + 抖动、熔断、快速 fallback 到备用 provider（17 · 19、17 · 16）。A、B 是讲义提到的另外两种失效。

### Q5 — 答案：A

99.9% SLO 允许的错误率是 0.1%，burn rate = `0.5% / 0.1% = 5`。含义：按这个速度，30 天的错误预算 6 天就会耗尽。B 把分子分母颠倒；C 用了 0.05% 当分母（这正是本节代码的做法）；D 无依据。

### Q6 — 答案：C

代码逻辑是"与"：`burn_rate > 2.0 and e.blast_radius_pct > 0.2`。畸形 prompt 的 burn 为 `0.04 / 0.0005 = 80` 倍，但爆炸半径 10% ≤ 20%，于是 COMPLETED。讲义的 burn-rate 门只看预算消耗速度，不附加爆炸半径条件，这里是代码与讲义的不一致。

- A：`duration_min` 完全没参与判断。
- B：80 倍，不是 0.8 倍。
- D：`induced_error_rate = 0.040` 就是它产生的错误率。

### Q7 — 答案：D

讲义 Cadence 一节原文。A、B、C 的频率都不对；只在发布前做一次，无法跟上依赖与流量的持续变化。

### Q8 — 答案：B

讲义 "Starting small"："First experiment: pod-kill one decode replica under steady traffic... First LLM-specific experiment: inject one provider 429 for 5 minutes. Observe fallback. Most teams discover their fallback wasn't fully tested." skill 文件的顺序也是 pod kill → provider 429 → memory overload。A 爆炸半径过大；C、D 都不是讲义建议的起点。

### Q9 — 参考答案

1. 代码的 burn rate（分母 0.0005）：pod kill `0.002/0.0005 = 4.0x`；provider 429 `0.015/0.0005 = 30.0x`；malformed prompt `0.04/0.0005 = 80.0x`。只有 **provider 429**（30x 且爆炸半径 30% > 20%）被 ABORTED，与实际运行输出一致。讲义练习 1 的"代码答案"是 provider 429，原因是它同时满足高 burn 与大爆炸半径。
2. 标准定义（分母 0.001）：pod kill **2.0x**、provider 429 **15.0x**、malformed prompt **40.0x**。代码的分母是"预期基线错误率"，得到的是"比平时糟多少倍"的异常倍数，数值是标准 burn rate 的 2 倍。
3. 按讲义"> 2x 即暂停"：provider 429 与 malformed prompt 都应暂停；pod kill 恰好 2.0x，不满足"> 2"，可以完成（处在边界上）。代码因为"与"条件漏掉了 malformed prompt。

### Q10 — 参考答案

已用 Python 实际计算：

| 实验 | 有效错误率 | 标准 burn | 消耗当日预算 |
|------|-----------|----------|-------------|
| pod kill（0.2% × 5%） | 0.01% | 0.1x | 0.035% |
| provider 429（1.5% × 30%） | 0.45% | 4.5x | 1.562% |
| malformed prompt（4% × 10%） | 0.4% | 4.0x | 0.833% |

计算方法：消耗比例 = `有效错误率 × 时长 / (0.001 × 1440)`。例如 provider 429：`0.0045 × 5 / 1.44 = 0.015625 ≈ 1.562%`。

结论：

- 即使把爆炸半径折算进去，provider 429 与 malformed prompt 的 burn 仍超过 2 倍，都应暂停；
- 单次实验消耗的预算看似不多（< 2%），但 burn rate 衡量的是**速度**：如果故障不是实验而是真实事故，按 4.5x 的速度持续下去，一天的预算约 5.3 小时就会耗尽；
- skill 文件要求爆炸半径 "< 30% of fleet"，provider 429 的 30% 恰好**不满足**严格小于，应在实验设计阶段就被拒绝。

另外，若 `induced_error_rate` 已经是全服务错误率（代码没有说明口径），则应直接用 Q9 第 2 问的数字。口径不清本身就是代码的问题：混沌实验报告必须写明错误率的分母。

### Q11 — 参考答案

```python
def run_experiment_v2(e, budget=ERROR_BUDGET_PER_DAY, burn_limit=2.0, blast_cap=0.30):
    reasons = []
    if e.blast_radius_pct >= blast_cap:
        reasons.append(f"blast radius {e.blast_radius_pct:.0%} >= cap {blast_cap:.0%}")
    effective = e.induced_error_rate * e.blast_radius_pct      # 全服务有效错误率
    burn = effective / budget                                  # 标准 burn rate
    if burn > burn_limit:
        reasons.append(f"burn {burn:.1f}x > {burn_limit}x")
    consumed = effective * e.duration_min / (budget * 1440)    # 消耗当日预算比例
    return {
        "experiment": e.name,
        "burn_rate_x": round(burn, 2),
        "budget_consumed_pct": round(consumed * 100, 3),
        "status": "COMPLETED" if not reasons else "ABORTED: " + "; ".join(reasons),
    }
```

实际运行结果：

```text
pod kill (1 decode replica)        burn 0.1x   预算 0.035%   COMPLETED
provider 429 fallback              burn 4.5x   预算 1.562%   ABORTED: blast radius 30% >= cap 30%; burn 4.5x > 2.0x
malformed prompt tokenizer stall   burn 4.0x   预算 0.833%   ABORTED: burn 4.0x > 2.0x
```

进一步改进：真实的安全面是**实验过程中持续监测**，一旦滑动窗口内 burn 超限立即中止并回滚注入（例如每 30 秒评估一次），而不是像本代码那样事后给出"会不会被中止"的判断；爆炸半径上限应在实验**开始前**校验（拒绝运行），burn 门在**运行中**生效（中止）。

### Q12 — 参考答案

| # | 实验 | 注入方式 | 爆炸半径 / 时长 | 观察指标 | 成功标准 | 中止条件 |
|---|------|---------|----------------|---------|---------|---------|
| 1 | 杀 1 个 decode 副本 | Chaos Mesh PodChaos `pod-kill` | 1 个副本（约 5–10% 容量）/ 5 分钟 | 5xx、TTFT P95、路由器重试 | 5xx 不超过 SLO，TTFT P95 增幅 < 20%，副本 2 分钟内被替换 | burn > 2x |
| 2 | provider 429 | 在网关注入 100% 429（或故障注入代理） | 5% 流量 / 5 分钟 | fallback 命中率、端到端错误率、重试次数 | 30 秒内切到备用 provider，重试总数受预算限制 | 重试放大 > 2 倍，或 burn > 2x |
| 3 | 向量库延迟 | NetworkChaos 给向量库加 500 ms 延迟 | 单个检索副本 / 10 分钟 | 检索超时率、降级回答比例、E2E P95 | 超时后降级（无检索回答或缓存结果），E2E 仍在 SLO 内 | E2E P95 > SLO 2 倍 |
| 4 | 内存过载 / KV 抢占风暴 | 金丝雀副本上发送长上下文高并发请求 | 1 个金丝雀副本 / 10 分钟 | vLLM preemption 次数、排队长度、OOM | 服务端优雅降级（排队/拒绝并返回 429），不崩溃 | 副本 OOM 重启 |
| 5 | 畸形 prompt | 少量深度嵌套 Unicode / 超长单 token 输入 | 单 worker / 3 分钟 | worker 卡顿时长、其他请求 P99 | 单请求超时被隔离，其他请求不受影响 | 任一 worker 卡住 > 30 秒 |

共同要求：所有注入流量带 trace-ID 标签；实验期间在爆炸半径内开启抑制窗口；每个实验先在 staging 成功一次再上生产（skill 文件规则）；结论写回 runbook 与 SLO。

### Q13 — 参考回答要点

- **定义**：在受控条件下主动注入故障（杀 Pod、断网、注入错误码、制造资源压力），验证系统在故障下是否仍满足 SLO，并在用户发现之前暴露弱点。
- **为什么需要 SLO**：
  - SLO 定义了"什么叫系统仍然正常"——没有它就无法判断实验是成功还是失败；
  - error budget 定义了"可以花多少可靠性去做实验"，burn-rate 中止门也依赖它；
  - 讲义："Missing any means chaos becomes real incident"；skill 文件："If the team has no SLO, require SLO before any experiment."
- **其余前置条件**：可观测性（能看到影响）、自动回滚（能止损）、runbook（知道怎么处理）、on-call（有人响应）。
- 加分点：混沌实验遵循"提出稳态假设 → 注入 → 观察偏差 → 修复 → 自动化回归"的科学方法；LLM 服务的稳态指标除了 5xx，还应包括 TTFT/TPOT 与回答质量。

### Q14 — 参考回答要点

- **error budget**：`1 − SLO`。99.9% 意味着 0.1% 的请求允许失败；30 天窗口内这就是可以"花掉"的可靠性。
- **burn rate**：`实际错误率 / 允许错误率`。burn = 1 表示正好在窗口结束时用完预算；burn = 2 表示一半时间就用完。
- **为什么用 burn rate**：
  - 它与 SLO 直接挂钩，换不同 SLO 的服务也能用同一套阈值；
  - 它衡量**速度**，能在预算还没耗尽时及早中止；
  - "错误率 > 1%"这类固定阈值与 SLO 无关，对 99.99% 的服务太宽松、对 99% 的服务太严格。
- **多窗口告警**：只用长窗口反应慢，只用短窗口误报多。常见做法是"长窗口 + 短窗口同时超限才告警"，例如 Google SRE Workbook 中 1 小时窗口 14.4x 配合 5 分钟窗口确认（14.4x 持续 1 小时恰好消耗 30 天预算的 2%）。
- 联系本节：讲义的混沌门槛是 2x；本节代码把分母写成"预期基线错误率"，算出的是异常倍数而不是 burn rate。
- 常见误区：把 burn rate 当作"错误率翻了几倍"。

### Q15 — 参考回答要点

讲义列出的 LLM 专属实验中，通用网络混沌（丢包、延迟、断连）无法复现的至少有：

1. **畸形 prompt / tokenizer bomb**：问题出在**请求内容**，需要构造深度嵌套 Unicode、超长码点序列等 payload，验证单个请求不会锁住 worker（讲义：含毒字符的 4K prompt 让 tokenizer 卡 12 秒）。注入方式：在金丝雀流量中混入少量此类请求，并设置请求级超时。
2. **KV cache 抢占/驱逐风暴**：需要按**上下文长度 × 并发**构造负载，打满 vLLM 的 block 预算，观察 preemption、re-prefill 级联与 LMCache 恢复。网络层故障不会制造 KV 压力。
3. **provider 限流（429）与重试放大**：需要返回**语义正确的错误码**（429 + `Retry-After`），验证网关的重试预算与 fallback 路由；简单断网得到的是连接错误，走的是不同的代码路径。
- 其他可补充：输出质量退化（模型版本漂移、量化回退后答案变差），需要在线评估而不是 5xx 来检测；流式响应中途断开导致的半截回答处理。
- 加分点：这些实验需要应用层故障注入（网关插件、故障注入代理、测试流量生成器），而不只是 Chaos Mesh 的 NetworkChaos。

### Q16 — 参考回答要点

1. **先确认 trace-ID 标签**：统计告警窗口内错误请求中带实验标签的比例。如果绝大部分错误不带标签，说明有自然故障叠加。
2. **对照组**：比较爆炸半径内外的错误率。实验只影响 5% 流量，而爆炸半径之外的错误率也同步上升 → 多半是自然故障。
3. **时间线对齐**：错误开始时间是否与注入开始时间一致；同期是否有部署、配置变更、上游 provider 的状态页事件。
4. **依赖与日志**：错误类型是否与注入类型匹配（注入的是 429，却出现大量 OOM 或数据库超时）。
5. **处置**：无论哪种，先中止实验、恢复注入；确认是自然故障时按正常事故流程处理，并在复盘中记录"混沌实验与真实事故重叠"的经验——例如实验调度应避开发布窗口。
- 讲义："Observability plane — normal metrics + trace-ID correlation to distinguish chaos-induced from natural failures."
- skill 文件把"没有 trace-ID 标签的实验"列为 hard reject，正是因为缺了它就无法回答这个问题。

### Q17 — 参考回答要点

- **只在 staging 的问题**：staging 的流量形态、数据规模、依赖配置、缓存状态与生产不同，很多问题（真实 provider 的限流行为、真实前缀分布下的 KV 压力）只在生产出现。
- **生产的前提**：五个前置条件齐全；至少在 staging 成功跑过一次（skill 文件规则）；有爆炸半径上限（< 30%）与 burn-rate 自动中止；事故量不高（skill 文件：每周 > 2 起事故时先稳定，不加混沌）。
- **何时生产是正确答案**：
  - 验证 fallback、failover、自动扩缩容这类"只有真实流量才能触发"的机制；
  - 已经有成熟的 staging 实验并稳定通过；
  - 可以把爆炸半径限制在小比例流量或单个副本上（讲义："weekly... maybe 5% prod"）。
- **何时坚持 staging**：新类型实验首跑、没有自动回滚、处于发布冻结期或高峰期、团队尚无 on-call。
- 结论：采用渐进路线——staging → 生产小比例金丝雀 → game day 扩大范围。

---

## 六、关联知识点

### 前置知识
- [阶段 17 · 23 AI 的 SRE：多 Agent Incident Response、操作手册与预测性检测](../../23-sre-for-ai/docs/zh.md)：结构化 runbook 与 on-call 是混沌实验的前置条件。
- [阶段 17 · 13 LLM Observability 技术栈选型](../../13-llm-observability/docs/zh.md)：可观测面与 trace-ID 关联。
- [阶段 17 · 08 Inference 指标：TTFT、TPOT、ITL、Goodput、P99](../../08-inference-metrics-goodput/docs/zh.md)：SLI/SLO 的定义方式。
- [阶段 17 · 20 面向 LLMs 的 Shadow Traffic、金丝雀 Rollout 与渐进式部署](../../20-shadow-canary-progressive/docs/zh.md)：讲义引用的自动回滚机制。
- [阶段 17 · 22 对 LLM APIs 进行负载测试](../../22-load-testing-llm-apis/docs/zh.md)：内存过载、KV 风暴实验需要真实的负载生成。

### 本节被哪些后续内容用到
- [阶段 17 · 19 AI 网关：LiteLLM、Portkey、Kong AI Gateway、Bifrost](../../19-ai-gateways/docs/zh.md)：provider 429 / 网络中断实验验证的 fallback 机制。
- [阶段 17 · 16 将模型路由作为降低成本的基本手段](../../16-model-routing/docs/zh.md)：跨 provider 路由的 failover。
- [阶段 17 · 18 生产服务技术栈：KV 卸载与缓存感知路由](../../18-vllm-production-stack-lmcache/docs/zh.md)：KV 驱逐风暴实验观察的 LMCache 恢复。
- [阶段 17 · 04 服务引擎内部机制：PagedAttention、Continuous Batching 与 Chunked Prefill](../../04-vllm-serving-internals/docs/zh.md)：理解 preemption 与 re-prefill。
- [阶段 15 · 14 紧急停止开关、Circuit Breakers 与金丝雀 Tokens](../../../15-autonomous-systems/14-kill-switches-canaries/docs/zh.md)：kill switch 与熔断的设计。

### 延伸关键词
`chaos engineering` · `steady-state hypothesis` · `blast radius` · `error budget` · `burn rate` · `multi-window burn-rate alert` · `game day` · `suppression window` · `trace-ID correlation` · `retry amplification` · `retry budget` · `circuit breaker` · `LitmusChaos` · `Chaos Mesh PodChaos / NetworkChaos` · `AWS FIS` · `tokenizer bomb` · `KV preemption`
