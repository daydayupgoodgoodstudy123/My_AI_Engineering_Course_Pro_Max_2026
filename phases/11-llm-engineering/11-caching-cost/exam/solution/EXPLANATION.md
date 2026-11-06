# QuotaFlow 参考讲解

## Part 1

`tier_policy` 按名称取映射，未知名称回 free。`LegacyService.admit` 将它传入正确的下游补充接口；错误的字符串会在 policy 字段索引处报 TypeError。精确补充计算 `divmod(elapsed_us*rate+remainder, 1000000)`，保留不足一 token 的分子，tokens 饱和后清零余数。有效时间取旧时钟与新时钟的最大值。`commit_admission` 只消费调用方已经给出的 allowed，不自己实现联合准入。

原始逐微秒循环做的确实是补充计算，每步累加速率并产生整数 token；参考把这段等价计算封闭求解。计时覆盖完整 legacy request，包括最终状态保存与所有结果检查。没有 sleep 或无用循环。性能数据以包外连续三慢三快证据为准，阈值与最终实测见 SCOPE。

## Part 2

LedgerStore 自己实现 tokens、last_us、remainder、完整有序 RPM、total_used 的精确存取；重开不会补发额度。同一微秒的重复 RPM 时间戳代表不同准入请求，不去重。total_used 是状态中的累计快照，UPSERT 替换该字段而不再累加；后续保存同时替换补充时钟。

完整给定的 UsageJournal 使用 LedgerStore 的同一 connection：提供原 usage schema、唯一 request 约束、全部 Usage 字段编解码、原始成本 TEXT、append 和插入顺序读取。初始化及 ledger 读取包装也给定。journal 不调用 BEGIN/commit/rollback，也不使用 connection 事务 context；它只执行调用方事务中的 SQL。候选负责 `save_and_log` 的完整共同事务，将桶状态 UPSERT 与 `journal.append(usage)` 包在一起，后者抛错时前者回滚。原始成本词面与 ledger 顺序断言及对应错写保留为真实 GIVEN journal 的依赖 guard。单进程 SQLite 事务不等于 provider 幂等或分布式 exactly-once。

## Part 3

先取得 user 锁，再 load/refill/prune。超容量 demand 永久拒绝；其余 token 等待按 `(deficit*US-remainder)/rate` 向上取整，RPM 等到能留下 slot 的那个时间戳过期。两者取最大值才是共同可行时刻。合法历史可能多于当前 RPM，索引 `len(history)-max_rpm` 表示需要到期的最后一个阻塞请求。所有决定、conditional commit 与 save 在同一临界区。倒退时钟仍用 refill 返回的有效时间写 consumption timestamp。

## Part 4

每条 Usage 是一个观察到的准入决定；只有 admitted 的已完成调用贡献模型调用数、互斥 token 类别和成本。拒绝携带的是 proposed usage，不能收费。按 user/model 累计，空 batch 也保留当前快照；只有 denied 的身份也保留完整系列，其模型调用、三类 token 与成本均为零。正确的给定 async driver 负责逐批消费与发布。标签依次转义反斜杠、LF、双引号；固定 HELP/TYPE 是给定格式支持。给定 Decimal 加法防止累计过程受默认 context 限制，候选负责使用领域账本完成累计与完整系列渲染；driver 消费节奏是集成 guard。

## Part 5

先验证所有模型都在本地价格卡。三叶子分别是 input-cached、cached、output；每叶按对应每百万 token Decimal 费率计算。admitted ledger cost 与该 fixture 卡必须一致。缓存 savings= cached*(uncached_rate-cached_rate)/1000000；baseline=billed+savings。保留 user/model 首次出现顺序与拒绝证据，denied 只增加请求/拒绝次数，各层 token 与成本都为零。每条完成调用分别给 model、user、account 累加一次，不把累计 user subtotal 反复加入 account。逐层累加成本不量化。source 本来是平面 CostTracker，有限 user/model/category 嵌套输入输出是本题报告适配，未伪称 source 原有递归算法。

计时证据：完整请求连续三慢 0.703637/0.685971/0.669752 秒，三快 0.000018292/0.000016208/0.000016459 秒；限值 0.08 秒，最差双侧余量 8.37×/4373.53×。证据在 SCOPE 的实际绝对路径。该本机结果不代表服务吞吐或实用配额配置推荐。

## 这套题证明了什么，没证明什么

它验证注入时间和固定价格下的本地配额算术、候选桶状态精确保真与共享 journal 事务、线程级原子准入、有限 Prometheus 文本和嵌套成本证据。Usage 原成本词面的往返是给定 journal 的依赖验证，不证明候选独立设计了成本 codec。它没有验证真实 provider 价格、计费正确性、分布式锁、跨机器时钟、服务吞吐、真实模型调用、监控端点、安全隔离或真人 60 分钟通过率。
