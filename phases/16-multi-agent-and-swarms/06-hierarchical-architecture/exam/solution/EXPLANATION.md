# 参考实现说明

## Part 1

缺 branch 产生 MISSING，存在但无 leaf 的 branch 产生 UNKNOWN。正确 consumer 只对标成 VERIFIED 却无 leaf 引用的输入拒绝，因此首个异常发生在 producer 外两个正确调用边界。leaf 独立保留 worker 声明的状态。canary 使用完整原问题。

结构汇总按给定 postorder 对每个 manager 合并直接 leaf 与孩子的唯一 leaf/citation 集合。每个子树结果可供所有父引用使用，不重走每个 manager 的全部后代。该结果只回答“引用了哪些证据”，不回答“完成了哪个原 obligation”。完整 report 包含每个 manager、所有 branch/leaf 和 canary 输出。

## Part 2

写入每个唯一逻辑 leaf/node 的内容与有序 manifest。读取时实际 follow 每条 manifest member 链接，不依赖 archive 插入次序或命名规则。成员自身 id 与逻辑 id 必须一致，node 的 leaf 引用必须存在。多个 summary 可以共享同一 leaf，恢复时仍只有一份实际封存身份。typed status 和文本转换完全由给定 codec 完成。

## Part 3

每个原 obligation 从 root 开始独立遍历，沿声明 binding 把 parent local id 转成 child local id。每个节点记录 route；不可用 manager、部门不匹配、未声明 local id 和无映射分别记录 issue。只有 local id 与部门都符合的 leaf 才成为该原 obligation 的证据。首漂移按路径长度选择，等长保持遍历顺序。

审计保留 hierarchy 与原问题 canary 的分别归属状态；只有两方都是已知 verified/negative 且相异才标 canary-mismatch。原问题不一致或 canary 声明了未要求 obligation 是输入合同错误。所有语义映射职责在这三个函数内，P1 fold 不提供该答案。

## Part 4

同步 projection 从当前完成事件产生六列。leaf 行保留原 obligation、完整路径、leaf 状态与真实身份；branch 行保留 audit obligation/result 且不填 leaf id。给定 driver 负责 header、每事件发布、源关闭和 TSV quoting，候选不实现异步 buffering。

## Part 5

未知证据经过每层仍未知；缺失、已知冲突及单一已知状态有独立表示。递归解释保留每条 citation 出现路径，共享 leaf 不被当作新执行。原 obligation paths 与首漂移直接取 P3 已归属 audit，唯一实际 leaf 集合单独显示。结构 cycle 验证依赖是完整正确给定。

完整结构服务的本机校准覆盖 4,000 个真实 manager report，全部 branch/leaf/canary/manager 输出相等检查位于 timer 内；限值 0.085 秒，三次慢版 0.796–0.834 秒，三次参考版 0.0067–0.0079 秒。双侧余量分别 9.36×、10.73×。这是本地完整路径的响应检查，不是部署 SLA。

## 合同边界

ZIP 档案必须保留无直接 leaf 的内部 manager。canary 未提供某 obligation 时，独立通道状态为 None；UNKNOWN hierarchy 不因已知 canary 而变成已知分歧。相同路径长度的首漂移保持遇到顺序。leaf 投影输出实际 leaf id，而非 worker 显示名。不可用 manager 的 MISSING 向祖先保留；同时含直接 leaf 引用与子 manager 的节点两部分都保留。

测试包含 37 条 assert、4 个异常合同检查与五个 skip 锁。24 个错修登记覆盖 16 个 canonical 验证、7 个独立核心方向和 1 个自然跨关辅助方向。共享 evidence 按 leaf id 去重会同时破坏 P3 路由与 P5 obligation paths，不能把这种自然跨关影响当成两个独立核心方向。

## 证据边界与证明限度

原源码只有 canned worker、固定 split、summary 拼接和 caller 提供的 branch labels；没有 typed audit、obligation solver、ZIP 或 TSV。这里的明确状态/obligation binding/档案与展示是对正文 failure modes、Ship It provenance/drift/reconciliation 和原问题 canary 练习的局部适配，不宣称源已实现这些算法。无真实 LLM、联网、自动法律判断或自然语言语义验证。

深链压力 fixture 仅验证结构服务完整输出与重复遍历成本，不是生产层级建议；档案不声称并发/崩溃事务。独立完整副本的本机校准只验证上述路径与限值，不能推断真实组织或模型收益。
