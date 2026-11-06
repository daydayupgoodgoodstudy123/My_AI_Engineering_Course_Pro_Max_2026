# 测验 · LLMs 的 FinOps：单位经济性与多租户成本归因（FinOps for LLMs — Unit Economics and Multi-Tenant Attribution）

> **阶段 17 · 基础设施与生产 · 第 27 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 传统 FinOps 为什么失效 | 云资源按"资源在线时长"计费、tag 会自动传到账单行；LLM 成本是一次次 **token 交易**，API 调用不是资产，tag 不会自动传播，必须在调用点打标 |
| 2 | 三个归因维度 | per-user（`user_id`：席位定价、扩容谈判、识别重度用户）、per-task（`task_id` + `route`：产品功能成本、功能取舍）、per-tenant（`tenant_id`：单位经济性、续约定价、套餐阈值） |
| 3 | 第一天就在调用点埋点 | 讲义："Retroactive tagging always misses; instrument at request creation."——事后补标签永远会漏掉边缘情况 |
| 4 | 四个 token 层 | prompt（系统 + 用户输入，40–60%）、tool（工具结果回灌，agent 场景 20–40%）、memory（历史对话/检索文档，10–30%）、response（模型输出，10–30%）；混在一个桶里会让优化"失明" |
| 5 | 三级执行阶梯 | ① 每租户 rate limit（预期峰值 2–3 倍，返回 429 + `Retry-After`）→ ② 每日花费上限（合同额 1.5–3 倍，收紧限流 + 通知客户成功团队）→ ③ kill switch（相对租户基线的花费 z-score > 4，自动暂停 + 呼叫值班） |
| 6 | 六种归因模式 | tag-and-aggregate（简单粗略）、telemetry joiner（用 trace ID 把链路与账单关联，**精度最高**）、采样外推（5–10%，漏掉长尾）、基于模型的分摊（回归推断，用于无标签的历史数据）、事件溯源（Kafka/Kinesis）、实时流式（亚秒级看板） |
| 7 | 单位指标 | 用"每个已解决工单 / 每篇生成文章 / 每个成功 agent 任务 / 每用户会话分钟"的成本，而不是 $/M tokens（讲义："$/M tokens is vendor speak"） |
| 8 | 成本归因 trace 形状 | 每次调用都发出一条记录：`trace_id` + `user_id/tenant_id/task_id/route` + 四层 token 数 + `cost_usd` + `cached_input` + `batch`，写入数据湖再按维度聚合 |
| 9 | 叠加省钱栈 | cache（输入约便宜 10 倍）+ batch（五折）+ route（降本约 60%）+ gateway（冗余与重试）；全部叠加最好可降到朴素基线的约 5–10%，多数团队只用了 2–3 个杠杆 |
| 10 | 代码中的简化与缺陷 | `rate_limit_per_min` 从未执行；花费上限只打印不收紧；z-score 只与租户自身的短基线比较，本次运行 kill switch 实际误杀的是**正常租户 A**，而不是"滥用"租户 C |

### 核心技能（能动手做到）

- [ ] 设计一条包含三维度标签与四层 token 的成本归因记录（schema），并说明它在请求创建时由谁写入
- [ ] 为多租户产品设计 rate limit → spend cap → kill switch 三级阶梯，并给出每级的阈值、动作与通知对象
- [ ] 手算一个租户的日花费、合同上限与 z-score，判断 kill switch 是否会触发
- [ ] 读懂 `main.py` 的模拟循环，指出"声明了但没执行"的策略字段，并补上真正的限流逻辑
- [ ] 解释小样本基线下 z-score 的误报问题，给出 sd 下限、最短历史、稳健统计量等修正方案
- [ ] 为一个产品选定"cost per outcome"单位指标，并估算叠加优化后的成本比例

---

## 二、基础自测（选择题）

**Q1.** 讲义认为传统 FinOps（tag + 资源分级）在 LLM 支出上会失效，最根本的原因是：

- A. LLM 供应商不提供账单明细
- B. LLM 推理只能跑在本地 GPU 上，无法打云标签
- C. LLM 的单价每月都在下降，预算无法制定
- D. LLM 成本是 token 交易而不是资源在线时长；API 调用不是资产，tag 不会自动传到账单行，必须在调用点打上 user/task/tenant

**Q2.** 讲义要求在归因 schema 中拆开的"四个 token 层"是：

- A. prompt、tool、memory、response
- B. input、output、cache、batch
- C. system、user、assistant、function
- D. prefill、decode、KV cache、embedding

**Q3.** 关于多租户产品的执行阶梯，下列哪一项与讲义一致？

- A. 先 kill switch，再 rate limit，最后 spend cap；kill switch 阈值为花费超过合同额
- B. rate limit 设为预期峰值的 1.1 倍；spend cap 设为合同额的 10 倍；kill switch 在 z-score > 2 时触发
- C. rate limit 为预期峰值 2–3 倍并返回 429 + `Retry-After`；每日 spend cap 为合同额 1.5–3 倍，触发后收紧限流并告警客户成功；kill switch 在花费 z-score > 4 时自动暂停并呼叫值班
- D. 三级都只发告警，不做任何自动动作，以免影响客户

**Q4.** 讲义称"成熟团队采用、精度最高"的归因模式是：

- A. 采样 5–10% 后外推
- B. telemetry joiner：通过 trace ID 把链路数据与账单关联
- C. 基于回归模型的成本分摊
- D. 在供应商账单上做 tag-and-aggregate

**Q5.** 下列哪一个最适合作为客服产品的"单位指标"？

- A. 每个已解决工单的成本
- B. 每百万 token 的价格
- C. 每月 GPU 小时数
- D. 每个 API key 的调用次数

**Q6.** 按默认参数（`random.seed(7)`）运行 `main.py`，实际触发 kill switch 的是哪个租户？

- A. `tenant_C_abusive`，第 3 天花费 $21.88 超过合同额时
- B. `tenant_C_abusive`，第 6 天积累满 5 天历史后
- C. 没有任何租户触发
- D. `tenant_A_normal`，第 8 天花费 $0.97、z = 4.80 时

**Q7.** 在 `main.py` 中，`tenant_C_abusive` 的每日花费上限（cap）是多少？这次运行中有没有打印 `[cap breach]`？

- A. $20；第 3 天和第 9 天各打印一次
- B. $50；没有打印
- C. $40（合同额 $20 × `spend_cap_multiplier` 2.0）；没有打印，C 的最高日花费只有 $21.88
- D. $80；第 9 天打印一次

**Q8.** 某服务朴素基线成本为 1。先把流量路由到便宜模型（降本 60%），再全部改走 batch（五折），最后对占剩余成本 70% 的输入部分启用缓存（缓存部分便宜 10 倍）。叠加后成本约为基线的多少？

- A. 2%
- B. 7.4%
- C. 20%
- D. 34%

---

## 三、动手 / 代码题

**Q9.** 阅读 `main.py` 的策略定义与模拟函数（节选）：

```python
@dataclass
class TenantPolicy:
    contracted_daily_usd: float
    rate_limit_per_min: int
    spend_cap_multiplier: float = 2.0
    kill_z_score: float = 4.0


@dataclass
class TenantState:
    spend_today_usd: float = 0.0
    minute_count: int = 0
    daily_history: list = field(default_factory=list)
    paused: bool = False

# simulate_day 内部
        requests = int(100 * traffic_mult * random.uniform(0.8, 1.3))
        tokens_per_req = int(random.gauss(600, 150))
        cost_per_req = (tokens_per_req / 1e6) * 10.0
        total_spend = requests * cost_per_req
        state.spend_today_usd += total_spend
```

1. 文件 docstring 和结尾提示都说"rate limits throttle"。代码里真的有限流吗？哪些字段是"声明了却从未使用"的？
2. 以日为粒度的模拟里，`rate_limit_per_min=40` 换算成每日上限是多少？它能限制住 `tenant_C_abusive` 吗？
3. 给 `simulate_day` 补上第一级限流：把每日请求数截断到上限，并统计被 429 拒绝的请求数。

**Q10.** 代码的标题写着"abusive tenant triggers kill switch"，但实际被暂停的是正常租户 A。下表是第 6–10 天各租户在检查时的 z 值和基线标准差（用脚本复现）：

| 天 | A 的 z（sd） | B 的 z（sd） | C 的 z（sd） |
|----|-------------|-------------|-------------|
| 6 | −2.24（0.06） | −0.05（0.71） | −0.24（4.63） |
| 7 | −0.67（0.08） | 0.04（0.64） | −0.40（4.17） |
| 8 | **4.80**（0.08） | −1.32（0.58） | 0.34（3.86） |

1. 为什么"滥用"租户 C 从来不会触发 kill switch？
2. 为什么 A 一次 $0.97 的花费（只比平时多 $0.37）就被暂停？
3. 换 500 个随机种子跑 10 天，A、B、C 被暂停的次数分别为 37、18、26 次。这说明了什么？
4. 给出至少三处修改，使 kill switch 能抓住"突然变坏"的租户而少误杀正常租户。

**Q11.** 手算题（不运行代码）：

1. `tenant_C_abusive` 的 `traffic_mult = 25.0`。若某天 `random.uniform` 取 1.0、`tokens_per_req` 取 600，它当天的请求数、单次成本和日花费各是多少？是否超过合同额？是否超过 cap？
2. 租户 A 第 1–7 天的花费为 `[0.70, 0.67, 0.64, 0.53, 0.60, 0.48, 0.55]`（四舍五入值），第 8 天花费 0.97。用样本标准差计算 z，判断是否 > 4。
3. 讲义练习 4：每个工单 3M tokens、每天约 800 个工单。设缓存输入单价为 p 美元/M tokens，写出每工单成本和每日成本的公式；若 p = 0.125，结果是多少？对"3M tokens/工单"这个设定你有什么怀疑？

**Q12.** 观察 `main` 中每天结束时的处理：

```python
        for name, (policy, state, _) in TENANTS.items():
            status = "PAUSED" if state.paused else "active"
            print(f"  {name}: spend=${state.spend_today_usd:7.2f}, ...  [{status}]")
            state.daily_history.append(state.spend_today_usd)
            if not state.paused:
                state.spend_today_usd = 0.0
```

1. 租户 A 被暂停后，它的 `daily_history` 最后三项是什么？这会造成什么问题？
2. 被暂停的租户怎样恢复？代码里有恢复路径吗？
3. 设计一个更合理的"暂停—复核—恢复"流程（列出状态与触发条件）。

---

## 四、面试高频题

**Q13.**（基础必考）为什么说"传统 FinOps 在 LLM 支出上会失效"？LLM FinOps 第一天要埋哪些维度、为什么不能事后补？

**Q14.**（原理深挖）用"花费 z-score > 4"做 kill switch 有哪些隐含假设？什么情况下会误报、漏报？你会怎么改进异常检测？

**Q15.**（工程实践）请设计一个多租户 LLM 平台的成本归因管道：从请求进入网关到看板出数，每一步存什么、谁负责、如何保证精度。

**Q16.**（场景设计）你们最大的租户单位经济性为负（每月收入低于其 LLM 成本）。请按"对客户影响从小到大"提出三项干预。

**Q17.**（追问型）既然供应商都按 $/M tokens 报价，为什么讲义坚持用 cost per resolved query / artifact 做单位指标？这个指标本身有什么坑？

---

## 五、参考答案与解析

### Q1 — 答案：D

讲义开篇："Costs are token-transactions, not resource-uptime. Tags don't map — an API call is a transaction, not an asset." EC2、S3 这类资源的 tag 会传播到账单行项，而 LLM API 调用不会自动带标签，只能在调用点打上 user/task/tenant 并一路携带。

- A 错：供应商有账单，只是账单上没有你的业务维度。
- B 错：托管 API 同样是云服务，问题不在部署位置。
- C 错：价格变化影响预算，但不是"归因失效"的原因。

### Q2 — 答案：A

讲义表格：Prompt（系统 + 用户输入）、Tool（工具调用结果回灌）、Memory（先前对话/检索文档）、Response（模型输出）。

- B 是计费方式/折扣维度，不是 token 来源分层。
- C 是对话消息的 role，与成本分层不是一回事（tool 结果和 memory 都可能以 user/assistant 消息出现）。
- D 是推理引擎内部阶段，账单上看不到。

### Q3 — 答案：C

三级阶梯：rate limit（2–3x 预期峰值，429 + `Retry-After`，"Tenant sees friction; no surprise bill"）→ 每日 spend cap（1.5–3x 合同额，收紧 rate limit + 通知 customer-success）→ kill switch（相对租户基线 z-score > 4，自动暂停、呼叫 on-call、升级到运维 + CS）。

- A 顺序反了，而且"超过合同额就杀"过于激进。
- B 阈值全部不对：1.1 倍峰值会频繁误伤正常流量；z > 2 误报率极高。
- D 错：kill switch 的意义就是自动暂停。

### Q4 — 答案：B

讲义："Telemetry joiner: join traces to billing via trace IDs. Highest accuracy. What mature teams do."

- A 采样外推"misses tails"，而 LLM 成本恰恰长尾严重（少数 agent 会话可能吃掉大量 token）。
- C 用于"legacy data without tags"，是没有埋点时的补救。
- D 讲义称"Simple; rough"。

### Q5 — 答案：A

讲义："Tie cost to a product outcome. Otherwise optimization is unanchored." 每个已解决工单的成本把模型、提示词、工具调用、重试的全部开销与业务结果挂钩。

- B 是"vendor speak"，只反映单价，不反映要花多少 token 才能解决问题。
- C、D 是资源/调用量指标，与产品结果无关。

### Q6 — 答案：D

真实输出：

```text
— Day 8 —
  [KILL SWITCH] tenant_A_normal: z=4.80 on spend $0.97 (baseline $0.60 ± $0.08) → auto-pause + page on-call
```

被暂停的是**正常租户 A**。A 的基线非常稳定（sd 只有 $0.08），一次 $0.97 的小波动就超过 4 个标准差。

- A 错：C 第 3 天确实超过合同额 $20，但代码的 cap 是 $40，且第 3 天历史不足 5 天，不检查 z。
- B 错：C 第 6 天 z = −0.24。
- C 错：A 被暂停了。

### Q7 — 答案：C

cap = `contracted_daily_usd × spend_cap_multiplier = 20 × 2.0 = $40`。C 的日花费在 $9.19–$21.88 之间，从未超过 $40，所以整个运行没有任何 `[cap breach]` 输出。用 500 个种子统计，C 的最高日花费也只有 $33.54，A、B 的 cap 分别是 $200、$100，而它们的日花费不到 $3.3——**第二级阶梯在这个模拟里永远不会被触发**。

- A 把合同额当成了 cap。
- B、D 的数值没有出处。

### Q8 — 答案：B

逐步计算（已用 Python 验证）：

- 路由：`1 × (1 − 0.6) = 0.4`
- batch：`0.4 × 0.5 = 0.2`
- 缓存：输入占 70%，缓存后变为 1/10：`0.2 × (0.3 + 0.7 × 0.1) = 0.2 × 0.37 = 0.074`

即约 **7.4%**，落在讲义"~5–10% of naive baseline"区间内。

- A（2%）是把"便宜 10 倍"错误地作用在**全部**成本上（`0.2 × 0.1`），忽略了输出 token 不能被缓存。
- C（20%）漏算了缓存。
- D 是数值干扰项。

注意：不同杠杆是作用在不同部分的，不能简单把折扣率相乘。输入占比为 50% 时结果是 11%，90% 时是 3.8%。

### Q9 — 参考答案

1. **没有限流。** `rate_limit_per_min` 和 `TenantState.minute_count` 都只声明、从未被读取；`requests` 直接算出来就计费。此外 `spend_cap_multiplier` 只用于打印 `[cap breach]`，没有"收紧 rate"的动作；`simulate_day` 的参数 `day` 也未使用。结尾那句"rate limits throttle; caps trigger alerts"描述的是讲义里的设计，而不是代码的行为。
2. `40 × 60 × 24 = 57,600` 次/天。C 每天只有约 2,000–3,250 次请求，远低于这个上限——即使加上限流，用这个数值也挡不住 C。说明阈值要按"预期峰值 2–3 倍"来设：C 的合同额是 $20、单次约 $0.006，按合同推算预期每日约 3,300 次，而它作为"滥用者"实际的请求量其实也在这个范围内。也就是说，这个模拟里"abusive"仅体现在命名上，花费并没有越过合同。
3. 参考实现（假设每天按日上限执行）：

```python
@dataclass
class TenantPolicy:
    contracted_daily_usd: float
    rate_limit_per_day: int            # 改成与模拟粒度一致
    spend_cap_multiplier: float = 2.0
    kill_z_score: float = 4.0


def simulate_day(day: int, verbose: bool) -> None:
    for name, (policy, state, traffic_mult) in TENANTS.items():
        if state.paused:
            continue
        requested = int(100 * traffic_mult * random.uniform(0.8, 1.3))
        allowed = min(requested, policy.rate_limit_per_day)   # 第 1 级：限流
        throttled = requested - allowed
        if throttled and verbose:
            print(f"  [429] {name}: {throttled} requests rejected (Retry-After)")
        tokens_per_req = int(random.gauss(600, 150))
        state.spend_today_usd += allowed * tokens_per_req / 1e6 * 10.0
        ...
```

我们在 `tmp` 中跑过一个这样的变体：把 C 改为前 6 天正常（`traffic_mult=1.0`）、第 7 天起 25 倍，并设 `rate_limit_per_day=300`。第 7 天 C 申请 2,566 次，被拒 2,266 次（429），实际花费 $1.55，同时 z = 5.8 触发 kill switch——这才是讲义想演示的"突然失控"场景。

### Q10 — 参考答案

1. **C 的基线本身就是"滥用"水平。** kill switch 比较的是"今天 vs 自己过去几天"。C 从第 1 天起就是 25 倍流量，平均约 $14、sd 约 $4，第 9 天的 $21.64 也只有 z = 1.89。相对自身基线的 z-score 只能检测**变化**，检测不出"一直很贵"。对"一直超额"的租户应由第 1、2 级（限流、cap）或与合同额比较的绝对阈值来处理。
2. **A 的基线方差极小且样本少。** 7 天历史均值约 $0.60、样本 sd 约 $0.08，于是 `(0.97 − 0.60) / 0.08 ≈ 4.7–4.8`。从业务角度看，$0.37 的增量对一个合同额 $100 的租户毫无意义。z-score 是相对量，sd 很小时一点点噪声也会被放大；同时 `statistics.stdev(...) or 1` 只防住了 sd 恰好为 0 的情况。
3. 三个租户被暂停的概率都在 4–7% 量级，**与是否"滥用"基本无关**，说明这个 kill switch 在这个模拟里本质上是噪声触发器。理论上，若花费服从正态分布、基线只有 5 个样本，新样本 z > 4 的单次概率约 1.1%（10 个样本时约 0.19%，30 个时约 0.02%，已用模拟验证）；每个租户检查 5 天、加上花费分布本身是乘积型（`uniform × gauss`），累计误报就到了几个百分点。
4. 修改建议：
   - **sd 下限**：`sd = max(stdev, 0.25 * mean)` 或某个绝对金额下限，避免低方差租户被噪声触发（我们的变体中加上 25% 下限后 A 不再被误杀）。
   - **绝对增量门槛**：同时要求 `spend − mean > 某金额` 或 `spend > 合同额 × k`，z-score 与绝对值"与"起来。
   - **更长、更稳健的基线**：至少 14–30 天，按星期几分季节性；用 median/MAD 或 EWMA 代替 mean/stdev，减少离群值影响。
   - **不让异常日污染基线**：被标记为异常的那天不要 append 进 `daily_history`。
   - **更细的时间粒度**：按小时累计花费，滥用发生后几小时内就能触发，而不是等到一天结束。
   - **分级动作**：z > 3 先告警、z > 4 且绝对金额超标才自动暂停，降低误杀正常客户的代价。

### Q11 — 参考答案

1. 请求数 `int(100 × 25 × 1.0) = 2,500`；单次成本 `600 / 1e6 × $10 = $0.006`；日花费 `2,500 × 0.006 = $15.00`。低于合同额 $20，更低于 cap $40。可见在代码设定的单价下，"25 倍流量"也没有让 C 超过合同。
2. 均值 `(0.70+0.67+0.64+0.53+0.60+0.48+0.55)/7 = 4.17/7 ≈ 0.596`；样本 sd ≈ 0.0798；z ≈ `(0.97 − 0.596)/0.0798 ≈ 4.69 > 4`，触发。程序打印 4.80 是因为它用的是未四舍五入的原始花费。
3. 公式：每工单成本 = `3 × p` 美元（3M tokens = 3 个百万）；每日成本 = `800 × 3 × p = 2,400p` 美元；每日 token 量 = 24 亿。若 p = 0.125（**仅为示例单价，讲义没有给出 GPT-5 缓存价**），每工单 $0.375、每日 $300。
   - 怀疑：3M tokens/工单远超任何单次请求的上下文窗口，只可能是多轮 agent 会话**累计**（每轮重复发送历史 + 工具结果）。这本身就是一个信号：memory/tool 层可能在膨胀，应拆开四层 token 看是谁在涨，而不是只算总价。若原意是 3K tokens，则结果要除以 1,000。
   - 还要注意"已解决"的分母：应当把未解决、转人工的工单所花的 token 也计入分子，再除以已解决数，否则单位成本会被低估。

### Q12 — 参考答案

1. 最后三项都是 `0.97`（输出 `A history: [..., 0.97, 0.97, 0.97]`）。原因是暂停后 `simulate_day` 直接 `continue`，`spend_today_usd` 也不再清零，于是每天把同一个数又 append 一次。问题：基线被"异常值的复制品"污染，均值被抬高、sd 被扭曲；若之后恢复，kill switch 会变得更迟钝。暂停期间更合理的做法是不记录或记录 0 并打上"paused"标记，统计时排除。
2. 没有恢复路径。`paused` 一旦为 `True` 就永远为真，日志里第 9、10 天 A 都是 `[PAUSED]`。对一个被误杀的正常付费客户，这意味着停服直到人工改代码。
3. 参考状态机：
   - `active` →（z > 4 且绝对增量超标）→ `paused_pending_review`：自动暂停或降级到极低 rate limit，呼叫 on-call，通知 CS 联系客户；
   - `paused_pending_review` →（人工确认是误报 / 客户确认是正常增长）→ `active`，同时更新基线或合同额；
   - `paused_pending_review` →（确认滥用、密钥泄露）→ `suspended`：吊销 API key、轮换密钥，走安全事件流程；
   - 设置自动超时：例如 2 小时无人处理则降级到 cap 内的低速率，而不是一直全停；
   - 每次状态变化写审计日志（见第 25 节）。

### Q13 — 参考回答要点

- **失效原因**：云 FinOps 依赖"资源 + tag → 账单行项"，按在线时长计费；LLM 成本按 token 逐次发生，API 调用不是资产，供应商账单上只有 key/模型/token 数，看不到你的用户、功能和客户。提示词设计、上下文长度、输出长度这些"工程决策"直接就是财务决策。
- **三维度**：`user_id`（席位定价、识别重度用户与滥用）、`task_id + route`（哪个产品功能、走了哪个模型）、`tenant_id`（客户是否赚钱、续约定价、套餐阈值）。
- **四层 token**：prompt / tool / memory / response，分开记才能知道该优化提示词、裁剪工具输出还是压缩记忆。
- **为什么不能事后补**：事后只能靠日志拼接或回归分摊，重试、流式中断、后台任务、共享 key 等边缘情况一定会漏；讲义附带的 skill 文件甚至给出"retroactive tagging loses ~10-30% of spend"的说法。
- 加分点：说出 trace 形状（`trace_id` + 维度 + 分层 token + `cost_usd` + `cached_input` + `batch`），以及缓存命中、batch 折扣要在记录时就标出，否则算出的成本是"标价"而非"实付"。

### Q14 — 参考回答要点

- **隐含假设**：花费近似正态且平稳；基线足够长、没有被异常污染；租户历史代表"正常"；单位时间粒度合适。
- **误报场景**：基线方差很小（本节 A 的情形）；样本太少（5 天）；周期性（周一高峰、月底结算）；客户正常增长或发布新功能；节假日。
- **漏报场景**：租户从第一天起就是高花费（本节 C 的情形）；缓慢爬升（每天涨一点，基线跟着涨，z 永远不高）；在一天之内爆发但按天检查太晚；攻击者故意把花费维持在 3.9σ。
- **改进**：
  - 稳健统计（median/MAD）、EWMA、按星期几分桶的季节性基线；
  - sd 下限 + 绝对金额门槛 + 与合同额对比的硬阈值；
  - 小时级/分钟级的滑动窗口；
  - 多信号联合：请求数、单请求 token 数、错误率、来源 IP / key 数量；
  - 分级响应：告警 → 降速 → 暂停，并有人工复核与自动恢复。
- 常见误区：把 z > 4 当成"万分之三的误报率"——这只在正态、参数已知时成立；样本标准差估计带来的厚尾会让实际误报率高出一两个数量级。

### Q15 — 参考回答要点

- **入口（网关）**：鉴权后从 API key / JWT 解析出 `tenant_id`、`user_id`；由调用方 SDK 在请求头里带上 `task_id`；网关生成 `trace_id` 并决定 `route`（模型）。缺维度的请求直接拒绝或打上 `unattributed`。
- **调用时**：记录四层 token。prompt/memory/tool 的划分需要应用层配合（组装上下文时分段计数），response 和缓存命中数来自供应商返回的 usage 字段；同时记录 `cached_input`、`batch`、重试次数。
- **事件流**：每次调用发出一条成本事件到 Kafka/Kinesis（事件溯源），既供实时看板与 kill switch 使用，也落入数据湖。
- **对账（telemetry joiner）**：按 `trace_id` / 请求 ID 把自己的事件与供应商账单、自托管 GPU 分摊成本关联；差额作为"未归因成本"单独展示，并设定目标（如 < 2%）。
- **聚合与看板**：按租户今日花费、按功能的 cost per outcome、用户分布、缓存命中率影响、模型路由比例（与讲义 skill 文件列出的 5 个视图一致）。
- **治理**：成本记录与审计日志一起保存；schema 有版本；每周看头部花费与异常，每月看租户单位经济性。
- 加分点：说明 telemetry joiner 精度最高但要求所有调用都有 trace ID；采样只适合粗看总量，不能用于计费或 kill switch。

### Q16 — 参考回答要点

先确认数据：按四层 token 和功能拆开，看是哪个功能、哪一层在烧钱，客户是"用得多"还是"用得浪费"。然后按对客户影响从小到大：

1. **对客户无感的工程优化**：对它的流量启用 prompt 缓存、把非实时任务改走 batch、简单请求路由到小模型、裁剪工具输出和记忆窗口。讲义的叠加栈表明这可能把成本降到原来的一小部分，客户完全无感。
2. **产品层面的温和约束**：为高成本功能设置每席位/每日配额、默认使用更省的模式、对超大上下文提示用户；配合 rate limit 与 spend cap 防止突发。
3. **商务调整**：续约时重新定价（按用量计费或分档）、把高成本功能放入更高套餐、提出最低承诺用量。这是影响最大的手段，需要 CS 和销售参与，并用单位经济性数据支撑。

- 加分点：给每项干预设定可量化的目标（例如 cost per resolved ticket 从 $X 降到 $Y），并通过 A/B 或 shadow 流量验证质量不下降。
- 常见误区：一上来就涨价或限流；只看总花费不看功能分布。

### Q17 — 参考回答要点

- **$/M tokens 的问题**：它只是单价，不衡量"为了完成一件事花了多少 token"。换便宜模型可能单价降 90%，但重试、多轮、转人工增加，最终每个已解决工单反而更贵；反之更强的模型单价高，但一次解决，总成本更低。
- **cost per outcome 的好处**：把模型、提示词、工具、重试、缓存的全部影响折算到产品结果上，可以直接和收入（每席位、每工单收费）对比，算出毛利；优化方向（换模型、改提示、加缓存）有统一的评价尺度。
- **这个指标的坑**：
  - "已解决"的定义要清晰且不可被刷（比如用户未回复是否算解决）；
  - 分子要包含失败尝试与未解决工单的成本，否则会被低估；
  - 需要与质量指标一起看，单纯压低成本可能降低解决率；
  - 跨功能比较时分母口径不同，不能直接比；
  - 需要完整的归因埋点才能算出来——这也是为什么三维度和四层 token 必须第一天就做。
- 加分点：同时监控 $/M tokens（供应商侧谈判、模型选型）与 cost per outcome（产品侧决策），两者各有用途。

---

## 六、关联知识点

### 前置知识
- [阶段 17 · 13 LLM Observability 技术栈选型](../../13-llm-observability/docs/zh.md)：成本归因记录就挂在 trace 上，讲义说"Phase 17 · 13 observability stack is where this lives"。
- [阶段 17 · 14 Prompt 缓存与语义缓存的经济性](../../14-prompt-semantic-caching/docs/zh.md)：叠加省钱栈的第一层，缓存命中直接改变每次调用的实付成本。
- [阶段 17 · 02 Inference 平台经济性](../../02-inference-platform-economics/docs/zh.md)：不同平台的计价方式决定了 `cost_usd` 怎么算。
- [阶段 11 · 11 缓存、请求速率限制与成本优化](../../../11-llm-engineering/11-caching-cost/docs/zh.md)：rate limit 与成本优化的应用层基础。
- [阶段 01 · 06 概率和分布](../../../01-math-foundations/06-probability-and-distributions/docs/zh.md)、[阶段 02 · 16 异常检测](../../../02-ml-fundamentals/16-anomaly-detection/docs/zh.md)：理解 z-score 与异常检测的统计假设。

### 本节被哪些后续内容用到
- [阶段 17 · 15 批处理 APIs](../../15-batch-apis/docs/zh.md)、[阶段 17 · 16 将模型路由作为降低成本的基本手段](../../16-model-routing/docs/zh.md)、[阶段 17 · 19 AI 网关](../../19-ai-gateways/docs/zh.md)：叠加省钱栈的其余三个杠杆；网关也是打标与限流的落地点。
- [阶段 17 · 25 安全：密钥、API 密钥轮换、Audit Logs 与 Guardrails](../../25-security-secrets-audit/docs/zh.md)：kill switch 触发后的密钥吊销与审计。
- [阶段 17 · 28 自托管服务选型](../../28-self-hosted-serving-selection/docs/zh.md)：自托管时成本从 token 单价变成 GPU 小时，需要新的分摊方式。
- [阶段 15 · 13 行动预算、迭代上限与成本控制](../../../15-autonomous-systems/13-cost-governors/docs/zh.md)：在 agent 内部设预算上限，与租户级阶梯互补。
- [阶段 19 · 25 Verification Gates 与观察预算](../../../19-capstone-projects/25-verification-gates-observation-budget/docs/zh.md)：综合项目中的预算控制。

### 延伸关键词
`FinOps for AI` · `unit economics` · `cost per outcome` · `multi-tenant attribution` · `telemetry joiner` · `trace_id` · `rate limit / 429 / Retry-After` · `spend cap` · `kill switch` · `z-score / MAD / EWMA` · `showback / chargeback` · `prompt caching` · `batch API` · `model routing`
