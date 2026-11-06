# 参考说明

## Part 1

make_entry 保存本地 registry 中的 callable，绝不在注册或 discovery 时执行它。正确 admit_entry 会拒绝错误生产的普通 dict。注册键使用给定 (kind,source identity)：tool/prompt 按 name，resource 按 exact URI。source 同 kind 字典赋值本来覆盖旧项，本练习保留这个替换规则。inventory 只是完整身份与 handler_name 元组，不预先实现 Part 3 的 descriptor/result compiler。

Catalog 保存已有 entries 并在变更时失效 inventory，公开 register_batch 完成真实 bulk 注册后生成完整确定性 view。慢版每次插入都重建将实际使用的缓存 view；快版在最终读取时生成。source 本来直接使用 dict，本题 eager full-inventory 回归是教学插入，不能称原 source 已发现性能缺陷。

## Part 2

以给定 spec codec 保存有序 entries，不序列化 callable。load 按每条原 handler_name 使用安全本地 registry resolver，未知名称失败，不能 import/pickle 任意代码。URI 与文字原样保存，prompt arguments 仍按列表顺序。给定 writer 负责原子 JSON，不重考临时文件 rename。候选组织记录时使用完整 codec，不对合法 schema 值做数值转换，也不重排 entry 序列。

## Part 3

descriptor 按真实 source Tool/Resource/Prompt 字段投影。tool 需要 inputSchema 与 destructiveHint；resource 用 exact URI；prompt 映为有序 required arguments。导出的 schema 使用独立嵌套容器；修改对外 descriptor 不得改变已注册 Entry 的元数据。result 分别使用 content[]、contents[] 与 user messages[]。正确 complete wrapper 提供 source resultType/serverInfo/resource read cache metadata，capabilities 明确支持所有三种 primitive，与目录是否为空独立。

## Part 4

实际给定 change driver 修改正确 P1 catalog，绑定当前 kind/identity 并发布一个完整本地 audit，再生成最终 surface。candidate 比较对应 primitive 的 source 字段：add/remove 全字段；update 仅真实不同项，保留 source 字段顺序；prompt 参数数组按顺序比较。比较整个 descriptor 值而不只比较映射的键，因此 inputSchema 内部值变化同样进入 changed_fields。remove 发布 descriptor=None。driver 的异步消费、JSON line framing 和 close 均正确给定；这些 assertions 是集成护栏。

## Part 5

显式 CatalogNode 层级是教学输入扩展。preorder 处理 own entries，再访问 children，完整 path 包含 root 与所有祖先。保留 children 的输入顺序，以及每个 kind 的 source identity、descriptor 和原 callable；不同 scope 的同身份条目可能有各自元数据，不能按身份跨 scope 复用 descriptor；正确 scoped duplicate helper 只在同完整 path/kind/identity 拒绝重复。它不是 peer namespace、federation、routing 或任意协议 catalog 标准。

本包验证的是离线本地编译与审计行为。没有真实 MCP SDK、网络 transport、授权审批、provider、协议 conformance、线上可用性或真人用时校准；课程 revision 字符串与字段仅作为给定 source 快照，不作外部最新规范断言。真实性能与独立 fresh 证据记录在 SCOPE 的包外路径。

本机性能证据：真实 5,000 条 bulk 注册到最终完整 inventory，连续三慢 1.804184/1.782266/1.854358 秒，三快 0.012619/0.012549/0.013123 秒；限值 0.2 秒，最差双侧余量 8.911×/15.240×，单慢最大 1.854 秒。全部 specs、callable references、排序 inventory 与完整结果比对参与路径；不代表生产吞吐或 MCP 网络性能。实际完整复制与日志见 SCOPE 包外证据。
