# PrimSwap 参考讲解

## 1 共享状态和单步调用

snapshot返回完整的深快照，策略可改自己的view而不删除池中证据。Agent.run对策略结果取得所有权并强制写入被调用agent的from。resolve_target分别返回next、done、selector-stop和unknown；正确consumer不把未知目标当成功停止。

last_by通过append维护每个sender的最新观察，读出仍取得独立快照。完整消息池不删除；更新sender后旧缓存不能保留。性能路径是预载共享池上的完整ReviewDesk.review及全部receipt核验，历史构建不计入查询窗口；完整池保留与append更新另作功能护栏。完整连续3慢3快实测：慢0.530084/0.529200/0.525803秒，快0.002380/0.002272/0.002217秒，限值0.045秒，双余量11.6845×/18.9079×。首组慢侧3.48×未达，完整6份证据保留；只调整响应限值，未删业务或输出核验后完整重测。

## 2 配置和运行时行为

dbm wrapper给定正确打开模式、UTF8/JSON与键编码。save以agent-name分别存版本化prompt、tool序列和policy-name，以独立配置记录存mode、order、start、budget及有序agent manifest。manifest按定义清单恢复，不能改按名字排序。load只接受声明版本，再从registry绑定函数；同一注册项可绑定多个agent，不能在绑定一次后移除。不能序列化、反序列化或执行任意代码。

tools是正文Agent概念的显式不可变metadata；原main.Agent没有该字段，prompt同样不影响本地脚本策略。本练习不把保存这些字段说成真实模型调用。

## 3 谁决定下一位

静态解释器只看外部order，即使消息返回done也继续；同一agent出现在多个位置时，每个位置都读取当时的共享历史并执行。handoff解释器每次调用/append后解析当前消息的后继；本轮预算按新执行次数计算，预置历史不占预算。selector解释器先append，再调用外部selector读最新状态；message的handoff仅留在trace里。三者共享修好的原语，三个完整body独立实现。运行结果同时保存decisions、完整messages和typed stop，预算耗尽与正常结束区别保留。

## 4 控制证据记录

DecisionProjection按mode选择真正的控制字段：static_next、返回handoff或selector_choice。decision记录原step/speaker、所请求目标、解析outcome及独立message快照，嵌套payload也不与源事件共享可变对象；stop另有reason/executed/last_speaker。正确driver负责async流、发布、关闭及RFC7464型RS+JSON+LF，不重复把这些通用机制交给候选调试。

给定replay_events只是投递已有batch replay结果，不声称P3本身实时执行；自定义async源可逐项到达，callback和driver按到达事件处理。

## 5 组合中的所有权

递归累积tuple scope，分别继承store-id和scheduler。每个leaf保存stores[id]原对象，因此刻意共享可观察到后续append，隔离池仍不同。active只记录当前祖先路径，循环带scope位置报错，无环子树在不同scope复用允许。nestedcomposition是明确本地结构适配，不是框架运行时。

## 来源与范围

来源为正文四原语/无状态观点、main.SharedState/Agent和三种Orchestrator，以及讲解的sender冒充、浅快照、未知目标静默停止与构造差异fixture。原snapshot只浅拷贝、last_by返回借用对象；本题加强所有权。typed stop、dbm配置、JSONseq记录和nested composition是局部教学adapter；不实现queue-driven scheduler或框架选择，也不重复coderpad的transition/route_task。

## 这套题证明了什么，没证明什么

本地测试验证所列确定性fixture的共享状态、配置重开、三种控制语义、领域记录和嵌套所有权。它不证明真实LLM路由质量、线程/分布式安全、框架兼容、线上性能或业务收益；没有人类时间校准。
