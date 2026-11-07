# 面试官手册

开场2分钟，五关12/10/16/10/10，共60分钟。不给真实 API、外部服务或真实生产价格。每关先读 docstring，再观察候选人能否由外层行为定位责任。断言只描述要求，不向候选人解释根因。

## 澄清问题标准答案（English）

仅在候选人问到时，用下表英文回答；只澄清现有合同，不主动增加要求或给出修法。

| Question | Answer |
|---|---|
| Which branch answers the user? | Rollout executes one selected served version. Shadow mode executes control as served and variant as shadow for every eligible miss. A shadow response is never promoted to served. |
| What counts as paid usage after failure or blocking? | Keep every observed attempt with its role, version and ordinal, including ProviderFailure.attempts. A safety-replaced display does not change the observed tokens or cost. |
| Are request observations the same as paid attempts? | No. Keep one request outcome separately from its paid-attempt facts. Cached or input-blocked paths have zero provider usage. |
| Is the SSE output a live provider token stream? | No. It replays completed branches: served produces content and telemetry; shadow produces telemetry without its response text. |

## Part 1：准备与观测重放（12分钟）

目标：保留 scoped PromptTemplate、稳定 cohort、缓存安全与完整观测账本。

坑：嵌套版本 map 被当 record，正确 render_template 的 `.template` 访问报 AttributeError；进程 hash 不能替代 source MD5 cohort；缓存快捷返回绕过 input/output guard 和 request provenance；每次 append 重算全部历史导致真实 replay 路径变慢。原 source CostTracker 已增量更新，这里的历史扫描是教学回归。

H1：对照异常消费者预期类型与生产者返回值。H2：分开用户所见文本、请求 provenance 与 paid-attempt 事实。H3：保持每条原记录，同时让 append 更新已有统计状态。追问：为什么一次请求可以有多个付费事实却只有一个 request observation？

## Part 2：完整 snapshot（10分钟）

目标：SQLite 保存 prompt 配置、(user,experiment) bucket 与全部 typed observations。

坑：同用户在不同实验中的 bucket 不能合并；served/shadow 角色不可改写；原 output_tokens 不能改成拒绝文案长度；重复 request_id 的不同 paid attempts 必须逐条保留。严格 tag codec 与基本校验给定。完整 snapshot 是本地工程扩展，不声称原课已有该 schema。

H1：列出三类表的独立身份。H2：bucket 是稳定 cohort，不是冻结的所选版本。H3：原 observation 逐条编码并保持顺序，在事务内替换完整 snapshot。追问：traffic_pct 改动后哪些值保持、哪些选择可能改变？

## Part 3：rollout 与 shadow（16分钟）

目标：rollout 只执行所选 served 分支；shadow 为每个 eligible miss 执行 control served 与 variant shadow。

坑：把 shadow 按 traffic_pct 抽样；把高质量 shadow 提升为 served；输出 guard 替换文案后丢失原付费 token；失败带有实际尝试事实却被丢弃。正确 lookup/hash、guard/evaluator、provider fallback 与价格事实均给定，不重考 Part 1 或 retry 算法。

H1：先写 mode→角色执行表。H2：把 ProviderFailure 的实际 attempts 与没有观测的失败分开。H3：每个实际 fact 带 role/version/ordinal 入账，最后只记一条 served 请求结局。追问：control 失败时为何不能把成功 shadow 当用户回答？

## Part 4：角色化 SSE（10分钟）

目标：served 才有 content；shadow 只有 telemetry；展示拒绝文案仍携带原 paid_usage。

坑：把 shadow 原文作为 content；从短展示文案重新算 billed output_tokens；把真实 blocked/error 状态改成 approved。candidate 只拥有领域投影。异步顺序拉取、当前 request/role/version 绑定、JSON/SSE framing、正常与 early close 都由真实给定 driver 完成，并保留集成断言。

H1：对照角色与允许公开字段。H2：paid_usage 与 served_text 来自不同证据。H3：一个 served 完成投影为 content 与 served telemetry，shadow 只投影 shadow telemetry。追问：这里的 SSE 为何不等于真实 provider token streaming？

## Part 5：部署配置证据（10分钟）

目标：访问所有 template/version/record 与实验引用，保留完整问题路径。

坑：把别的 template 的同版本当有效引用；用全局 PRIMARY_MODEL 替代 record.model；忽略 outer name/version 与 record 内部身份不一致；遇到坏 sibling 后跳过后续记录。这是静态配置 readiness，不测试在线 provider 健康，不构造不存在的依赖 DAG。

H1：写下问题的源配置路径。H2：分开版本记录有效与实验引用存在。H3：先遍历所有版本，再在实验自己的 template 内关联 control/variant。追问：为何一个引用存在的实验仍可能指向单独标记无效的 record？

## 评分表

| 关卡 | 分值 | 完整要求 |
|---|---:|---|
| Part 1 | 25 | 四层行为正确，定位真实消费者异常，完整证据与响应速度满足要求 |
| Part 2 | 15 | 三类状态重新打开后精确恢复，角色、bucket 与原 token 不混淆 |
| Part 3 | 30 | 两种模式、失败隔离、不可提升 shadow、实际付费归属正确 |
| Part 4 | 15 | content/telemetry 字段与角色安全，原 usage 保真，给定 driver 集成通过 |
| Part 5 | 15 | scoped 引用、实际模型、外层身份、全部 sibling 与路径正确 |

满分100。局部通过按职责分给分；硬编码 fixture、删除断言、丢记录或绕过安全边界不得获得对应职责分。额外讨论只作追问，不代替可观察行为。

本机性能证据：完整公开观测重放连续三慢 0.408216/0.425903/0.415167 秒，三快 0.001255/0.001226/0.002054 秒；响应限值 0.04 秒，最差双侧余量 10.205×/19.471×。680 条输入事实和完整输出都参与真实路径；不代表 provider 延迟或生产吞吐。完整测量与执行记录见 SCOPE 链接的包外报告。
