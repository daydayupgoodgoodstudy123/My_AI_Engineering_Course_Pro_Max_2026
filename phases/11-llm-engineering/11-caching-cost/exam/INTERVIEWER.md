# QuotaFlow 面试官手册

开场 2 分钟：确认先读合同、逐关解锁、测试不改，价格与时钟均为本地 fixture。五关 12/10/16/10/10 分钟，共 58 分钟；总计 60 分钟，未做真人校准。

## 澄清问题标准答案

- 时间与小数额度？ “The clock uses integer microseconds. Fractional token credit is retained in millionths; capacity discards excess credit.”
- RPM 与并发？ “RPM is a 60-second sliding window of admitted timestamps. Admission must hold the supplied per-user lock from load through save.”
- 倒退时间？ “The effective clock is the maximum of the injected time and the previous refill time. The same effective time is used for consumption and expiry.”
- 历史能多于当前 RPM 吗？ “Yes. Retry waits until enough admitted timestamps expire to leave a slot.”
- 永久不可行？ “A demand above capacity is denied with retry None. Denied work consumes no request slot or tokens.”
- 价格真实性？ “Prices are fixed local fixtures. This exercise does not claim current provider prices or production billing.”

## Part 1 修：既有准入

坑：
- tier 名称被当作配置映射交给正确的 `refill_exact`；异常在生产者返回后，经 `LegacyService.admit` 到下游 policy 索引处暴露，是真实 TypeError。
- 更新时钟却丢掉不足一 token 的余数，短间隔与长间隔结果不一致。
- 拒绝决策仍记账，未来额度被未执行工作消耗。
- 每微秒真实补充模拟导致长闲置请求慢；完整 timer 包括读取状态、补充、过期、判断、记账、保存与结果，不移动必要工作。

H1：按最先失败的调用与实际状态定位。H2：对照短间隔组合、拒绝前后状态。H3：精确余数用整数算术，elapsed_us 乘速率并 divmod；饱和后余数清零。追问：为什么满桶不能积攒隐藏额度？倒退时间的消费时间戳如何选？

## Part 2 存：额度与账本

坑：
- reopen 不能重新发放满桶，last_us/remainder/RPM/total_used 都是状态。
- 桶的余数与超过 binary64 精确范围的整数必须保真；同一微秒的多个已准入请求仍是多个 RPM 槽位，total_used 是累计快照，不能再当增量相加。
- 状态更新和唯一 request 的 journal append 是同一 SQLite connection 上的一个事务；append 失败后状态保持原值，后续成功保存也要更新补充时钟。

完整 UsageJournal 的 schema、全部 Usage 字段 SQL 编解码、原始 cost_text、唯一 request append 与插入顺序读取均正确给定，init/ledger 包装也给定。journal 不管理事务；原始成本词面和账本顺序的错写只作这个实际 GIVEN 依赖的集成 guard，不是候选字段投影任务。候选仍自己写 BucketState 全字段精确 load/save，以及状态 UPSERT 与 journal.append 的共同事务。

H1：逐字段对照 reopen。H2：让唯一键冲突发生在状态更新之后。H3：由 store 将桶状态更新和给定 append 放在同一事务边界。追问：为什么不能让 journal 独立提交？这为什么不等于分布式 exactly-once？

## Part 3 算：联合原子准入

坑：
- 只锁保存仍会让两次请求读到同一个末尾 token；临界区包括读取至保存。
- token 与 RPM 要共同满足，使用两者等待的最大值，token 等待考虑已有余数并向上取整到微秒。
- 超容量永久拒绝；历史多于 RPM 时，需要足够多时间戳过期，不能只等第一个。

给定 P1 的 refill 与 conditional commit、deque expiry 和锁 primitive；这些不是本关新算法。H1：写出两个限制何时各自可行。H2：追踪同一有效时间快照与锁范围。H3：token 分子为 deficit*US-remainder，RPM 选择能留下 slot 的到期点。追问：多进程部署需要换什么状态/锁设施？

## Part 4 流：完成批次监控

坑：
- 拒绝也算一次准入决定，但 proposed tokens/cost 不算已完成模型调用或账单。
- Prometheus 标签中的反斜杠、双引号和 LF 各有转义，身份不能串。
- 按 user/model 保留跨批次累计系列，空批次也保留全部已有值；只有拒绝记录的身份仍有完整 outcome/category 系列，未完成调用的值为零。正确 driver 负责消费与发布节奏。

HELP/TYPE 常量、实际 async pull-through driver 和 Decimal 精确加法给定；候选负责 accumulate_batch、标签与完整系列快照，在线拉取只作集成 guard。H1：先读测试 parser。H2：区分 decision 与 admitted completed call。H3：按 user/model 累计，由给定 driver 发布完整系列 text。追问：生产指标为何要控制标签基数？本题没有监控服务。

## Part 5 构：用量与成本层级

坑：
- cached input 已包含在 input total 内，不能重复按 uncached 费率计费。
- 成本与节省在 model/user/account 上累加时不提前舍入；baseline=billed+saved，saved 不是第二笔扣减。
- 未知 model 拒绝；给定价格卡与 admitted ledger bill 不一致要报告证据错误。
- denied 的 proposed token 不进入 model/user/account 的 usage 叶子；每条已完成调用只给各层增加一次。

本关是 source CostTracker 的 user/model/category 有限嵌套报告扩展，不是任意树或 provider 价格系统。H1：画出三类互斥 token 叶子。H2：从一条含缓存记录算 billed/saved/baseline。H3：保留 Decimal 至所有 subtotal，再单独选择展示精度。追问：审计时如何同时保留原始成本拼写与计算值？

## 评分表

| 项目 | 分值 | 标准 |
|---|---:|---|
| Part 1 | 25 | 四层定位、原始合同与响应速度，未跳过必要补充 |
| Part 2 | 15 | 桶全字段快照、RPM 重复次数、补充时钟与状态/journal 事务原子性 |
| Part 3 | 30 | 临界区、联合等待、永久拒绝与窗口边界 |
| Part 4 | 15 | 计费范围、标签、仅拒绝身份的零系列与逐批累计发布 |
| Part 5 | 15 | 嵌套成本证据、拒绝零用量、逐层单次累计与精度 |

提示记录：H1 仅定位、H2 分解合同、H3 给关键机制；记录时点及候选随后能否独立解释。80 分以上且 P3 原子性完整可认为本练习较熟练；不外推为生产系统能力。

计时证据：完整请求连续三慢 0.703637/0.685971/0.669752 秒，三快 0.000018292/0.000016208/0.000016459 秒；限值 0.08 秒，最差双侧余量 8.37×/4373.53×。证据在 SCOPE 的实际绝对路径。该本机结果不代表服务吞吐或实用配额配置推荐。
