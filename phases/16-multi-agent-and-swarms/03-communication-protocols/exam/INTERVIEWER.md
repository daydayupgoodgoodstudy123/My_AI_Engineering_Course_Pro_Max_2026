# AuditMesh 面试官手册

## 开场与澄清

让候选说明一次业务调用、一个 run、一个 session 和一条工具观察之间的区别。允许逐关解锁；不要先说明具体缺陷位置。

| Question | Standard answer |
|---|---|
| Is this a live ACP/A2A/ANP implementation? | No. It is a finite offline adapter over the lesson's audit, modality and DID structures. |
| Must a session identify one execution? | No. Each capture has its own run id, even inside the same session. |
| Are timestamps observation identities? | No. Every occurrence has an ordered slot; timestamps may repeat or arrive out of numeric order. |
| What does public policy permit? | Timestamp and an observed tool name are structural. Tool input/output are independently selected; private reasoning is never exported. |
| What does DID inspection prove? | Only local reference, controller and declared key-purpose consistency. No signature, encryption or identity proof is performed. |

## Part 1 修

主要坑：审计包装把同一业务操作执行两次；输入引用别名破坏先前凭据；失败缺少封口时间；每次观察都复制整个私有历史。前两处由正确的凭据消费者在根因外触发。性能修复仍需拥有新观察和读出的快照，不能以删失败或暴露引用换速度。

轻提示：比较业务效果编号与审计编号；在调用后修改调用方对象，再读此前记录。追问：一次写入/一次读取各应取得哪一层所有权？完整业务计时包含实际输出、所有观察和最终私有日志的核验；完整连续3慢3快实测：慢1.771720/1.752557/1.762869秒，快0.013874/0.014164/0.014496秒，限值0.15秒，双余量11.684×/10.348×。首组快侧7.124×未达保留；只调整响应限值后完整重测。

## Part 2 存

主要坑：把轨迹位置误当工具身份而漏掉纯观察或重复工具；按时间排序破坏原观察顺序；session查询混入其他agent。替换某run的快照要移除其旧轨迹位置，保留其他run。

给定：事务、schema、精确值codec。缺字段与null、binary64低位与负零是使用该codec的集成护栏，不要求另写数值codec。提示：保存每个位置，包括没有tool_name的观察。追问：两次同名tool和两条同timestamp观察如何区分？

## Part 3 算

主要坑：准入必须在业务效果前；每个tagged输出都要符合card声明；task与公共audit来自同一个已持久化run，session不能代替run。信任不可用时本地合同拒绝调用。公共投影选择结构字段，不能覆盖私有证据。

给定：已修的capture、repository、消息shape和注入的信任结果。候选仍独立实现delegate、validate_declared_output、public_step及project_task_and_public_audit；不存在完整gateway helper。提示：把“执行成功”和“输出可发布”分别判断。追问：执行完成但模态不被接受，哪一份记录应保持真实？

## Part 4 流

主要坑：每个观察占独立slot；封口凭据必须与已观察轨迹一致；失败封口保留错误和完成字段。候选同步回调累计领域状态，正确driver负责拉取/发布/关闭和SSE序列化。当前观察的及时发布和关闭是GIVEN集成验证，不是候选通用async主坑。私有字段通过P3的public_step控制。

提示：没有tool_name的观察和重复时间戳也占位置。追问：零观察的失败或成功为什么仍需要真实封口事件？

## Part 5 构

主要坑：#fragment在当前DID内解析；authentication、keyAgreement、humanAuthorization的key purpose不同；controller mismatch及未解析引用不能静默消失。每个relationship occurrence保留其用途、原引用和独立key快照。

本地fixture只允许两种声明的signing type与一种agreement type；humanAuthorization引用signing key。完整DID标准、轮换、证明、HPKE与网络解析均不在合同中。提示：引用表和用途不是同一个映射。追问：同一signing key分别出现在authentication和humanAuthorization中应保留几条证据？

## 评分

每关0–4分：0未定位，1能复现，2主要路径正确，3边界与所有权正确，4能解释来源与限制。总分20；记录推理和验证过程，不把总分当招聘结论。额外记录P1是否先修真实根因、P3是否确实产生新职责、是否保持所有原测试与给定依赖。

补充边界：P2同一查询作用域有多个run时仍按创建顺序返回；P3公共tool IO是独立快照；P4比较完整私有观察，不能只比较条数或已脱敏字段；P5同一引用可同时有controller-mismatch与purpose-mismatch，两条finding均保留。
