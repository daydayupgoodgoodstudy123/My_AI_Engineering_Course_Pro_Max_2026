# 参考实现讲解

## Part 1：证据先于构建

`evidence_status` 保留 supports 与 rejects 的区别。错误 producer 的返回经过 `ranked_rows` 被 `map_decision` 转成错误的 bounded-build action，根因与表现相隔两次调用。修好极性后，`next_experiment` 仍须明确只选 open，不能把 rejected 当作“还没支持”。

公开表与下一实验都按 `(-score, id)` 选取。排名保留全部状态，一次排序后生成 id 到位置的表，再组装每条记录；不为每条记录扫描全部其他记录。5000 条计时限值 0.08 秒。整数校验与示例公式从起始就是正确实现，类型边界只保护这些既有正确行为。

## Part 2：两张 CSV 表

固定文件名避免把 opaque id 当路径。CSV 标准库负责引号和换行。单独的 evidence presence 列区分 None 和内容为空的 receipt；维度读成 int，阈值写 repr/读 float 保留精确 binary float 与负零，时间戳原文不规范化。每次保存替换两表，重新打开返回新的 dataclass 和容器。本题不承诺跨表原子性。

## Part 3：先定门槛再看数据

只截首 N 次到达。注册时刻必须严格早于这些观察里最早的 instant，不是只早于末次汇总；给定解析器支持时区和 Python3.10 的 Z 转换。未满 N 次返回 open/ambiguous，uncertainty 不变。满样本后比较平均数，at-least 与 at-most 都含等号。支持或否定均按明确题目规则减一 uncertainty，最低为一，再返回对应的原文行动。

这不是对任意文本的可证伪性分类，也不证明样本有代表性；population/observable/threshold 是显式输入。

## Part 4：把决定及时交给消费者

给定 SampleBook 已管理每个实验独立累计和首 N 冻结。每次 feed 完成后调用同一个 judge 并立即 yield，所有实验完成就 return，不等 source EOF。源结束后按声明顺序判断每个未满批次。编码器把每个值写成 JSON scalar，原文换行留在单个物理 logfmt 行里。关闭生成器停在 yield，不再请求未来观察。

## Part 5：能影响结论的实验

递归返回三值状态与仍有影响的 open id 集合。ALL 的一个 rejected 足以决定根；ANY 的一个 supported 也足以决定根。已决定子树清空候选集合；仍 open 时合并子树候选，按风险与 id 选择。schema helper 已排除空组和未知 id。本题只有有限结构与显式证据，不推断语言中的隐含逻辑。

## 这套题证明了什么，没证明什么

通过原样五关说明能在受控本地输入上调试证据状态、精确往返 CSV、应用预注册门槛、按需输出与遍历三值树。它不证明实验设计具有统计功效、样本代表真实用户、风险分数可靠、实际上线安全，也不证明任何真实 LLM、网络或生产平台已经运行。
