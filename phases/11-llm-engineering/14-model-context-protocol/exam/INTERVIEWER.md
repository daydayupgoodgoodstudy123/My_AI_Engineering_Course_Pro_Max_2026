# 面试官手册

开场2分钟，五关12/10/16/10/10，共60分钟。所有 handler 都是本地 fixture，不访问真实服务；协议 metadata/transport 不是候选实现职责。

## 澄清问题标准答案（English）

仅在候选人问到时，用下表英文回答；只澄清现有合同，不主动增加要求或给出修法。

| Question | Answer |
|---|---|
| Can a tool and a prompt have the same name? | Yes. Identity is scoped by primitive kind. Tools and prompts use their names; resources use their exact URI. |
| Do all primitives return the same envelope? | No. Here tools use content[] with isError=False, resources use contents[] with URI and text, and prompts use messages[] with user text content. Metadata wrappers are given. |
| Does an empty catalog remove a capability? | No. The given capabilities still declare support for tools, resources and prompts when their catalogs are empty. |
| Must the change audit implement MCP transport? | No. Handlers are local fixtures. Protocol metadata wrappers are given, and transport is outside the candidate contract. The NDJSON change audit is a local artifact, not a new MCP method. |

## Part 1：注册与 inventory（12分钟）

坑：factory 执行 handler 后把普通结果当 callable 保存；正确 admit_entry 消费者在 factory 外报 TypeError。三种 primitive 共用 display name 会丢条目，resource 身份应按 URI。每次 register 重建完整排序 inventory，使真实 bulk→最终完整 view 路径变慢。正确 per-handler closure binding 已给定，本关不考 loop late-binding。

H1：比较生产的 Entry.handler 与正确注册消费者的要求。H2：画出 kind 与 source identity 的独立键。H3：存 callable，按给定 slot_key 注册并延后生成完整 inventory。追问：替换一个同 kind entry 后为何必须让后续 inventory 看见新状态？

## Part 2：安全 manifest（10分钟）

坑：重排 prompt arguments；把所有 entry 绑定成 registry 第一项；归一化 URI 导致身份变化。完整 spec codec 和原子 JSON writer 已给定，候选只组织完整有序 manifest 与按名称安全重绑定。组织记录时不要自行转换 schema 中合法的 JSON 值。未知 handler 必须 load error，不可静默丢 primitive 或 import 任意字符串。

H1：列出每条 spec 自己的 handler_name。H2：区分描述文字与身份 URI，参数列表有顺序。H3：逐 entry 保存给定 codec，逐 spec 使用给定 resolver。追问：如何在不反序列化代码的情况下升级本地 handler 实现？

## Part 3：三类 surface/result（16分钟）

坑：tool 漏 schema/destructiveHint；把 resource contents[] 当 tool content[]；把 prompt user messages[] 当 plain tool text。P1只修注册身份与 inventory，本关仍有真正 descriptor/result TODO。排序 helper、capabilities、metadata wrapper、调用与结果基本校验给定，空目录仍声明三类支持。descriptor 的嵌套容器必须与已注册 Entry 独立；修改对外 descriptor 不得改变注册记录。

H1：按 kind 写出字段表。H2：分别核对 content、contents、messages 的形状。H3：tool 映 inputSchema/annotations，resource 映 URI content，prompt 映 ordered args 与 user message。追问：为什么 `destructiveHint` 只是元数据，不证明 host 已批准操作？

## Part 4：本地 change audit（10分钟）

坑：只比较显示名而漏实际 description/schema/annotation 更新；把有序 prompt arguments 当无序集合；remove 仍发布旧 descriptor。candidate 拥有 source 字段顺序的 changed_fields 与正确 after/tombstone 投影。schema 的键不变而内部值变化，仍是 inputSchema 变化。给定 driver 实际完成 upsert/remove、kind/identity、顺序异步拉取、NDJSON framing、最终完整 manifest 与关闭，集成断言保留但不将泛 buffering/首 owner 算主要坑。

H1：区分 add/update/remove 的证据。H2：按该 primitive 的字段顺序比较完整 descriptor 值。H3：update 仅输出真实变化的字段，remove descriptor 为 None。追问：这里的本地 artifact 为什么不能冒称 MCP JSON-RPC change method？

## Part 5：本地 catalog 层级（10分钟）

坑：只保留当前 node.name 丢祖先路径；有 children 就漏 own entries；只导出 tools 而丢 resources/prompts。只保留当前名会把不同完整路径合成同一 scope，正确 scoped duplicate 消费者会先拒绝这种冲突。正确 shape/cycle 与 scoped duplicate helper 已给定；candidate 只遍历真实完整本地路径、所有原语与原 handler，不构建多 server federation。不同完整 scope 下的同 kind/identity 可有不同 descriptor，不能共用一份身份缓存。

H1：手写 root→left→shared 与 root→right→shared 两条路径。H2：own entries 与 children 是并列职责。H3：preorder 先处理本节点条目，再带完整 path 访问每个 child。追问：为何不同父节点下重复 catalog 名合法，而同完整 scope 的重复 primitive 要拒绝？

## 评分表

| 关卡 | 分值 | 评分标准 |
|---|---:|---|
| Part 1 | 25 | 三层故障正确，真实外层消费者定位，完整 inventory 与响应速度满足 |
| Part 2 | 15 | 完整 spec/安全 handler 重绑定、URI 与参数顺序保留 |
| Part 3 | 30 | 三类 descriptor 与 content/contents/messages、独立容器与给定 wrappers 集成正确 |
| Part 4 | 15 | 字段变化顺序、ordered args、remove tombstone 与实际 driver 集成 |
| Part 5 | 15 | 全路径 preorder、own+children、全部 kinds 与 handler 保真 |

满分100。按可观察职责给局部分；硬编码 fixture、删断言、丢 entry 或执行业务来发现目录不得获得对应分。额外追问不替代代码行为。

本机性能证据：真实 5,000 条 bulk 注册到最终完整 inventory，连续三慢 1.804184/1.782266/1.854358 秒，三快 0.012619/0.012549/0.013123 秒；限值 0.2 秒，最差双侧余量 8.911×/15.240×，单慢最大 1.854 秒。全部 specs、callable references、排序 inventory 与完整结果比对参与路径；不代表生产吞吐或 MCP 网络性能。实际完整复制与日志见 SCOPE 包外证据。
