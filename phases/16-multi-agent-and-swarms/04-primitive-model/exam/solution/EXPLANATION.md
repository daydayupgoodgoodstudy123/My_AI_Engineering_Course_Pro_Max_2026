# PrimSwap 参考讲解

## 1 共享状态和单步调用

Agent.run必须把当前SharedState原语对象传给policy。源policy签名Callable[[SharedState],Message]，实际脚本调用snapshot或last_by；提前传消息list投影会在正确policy中自然缺少接口。此处修的是入参接线，不是对list再复制。完整snapshot由GIVEN实现，策略修改自己的view不删除池中证据，nested mutation断言验证快照独立值。Agent对策略结果取得所有权并强制写入被调用agent的from；resolve_target分别返回next、done、selector-stop和unknown，正确consumer不把未知目标当成功停止。

canonical sender保留invoked Agent.name的精确值，不能擅自改成小写。append入池所有权断言是secondary/overfix护栏：外部继续编辑传入消息的嵌套证据不改变历史或latest观察。last_by按指定sender查询，不能用全池最后一条替代；未知sender仍返回None。这些防过修检查位于review计时区块之后。

last_by通过append维护每个sender的最新观察，读出仍取得独立快照；完整消息池不删除，新sender观察更新缓存。性能路径是30001消息预载池上的完整2400次ReviewDesk.review及全部receipt核验，历史构建不计入查询窗口；完整池保留与append更新另作功能护栏。完整连续3慢3快实测：慢0.481373/0.493098/0.451269秒，快0.001964/0.001962/0.002455秒；限值0.045秒，双余量10.0282×/18.3275×。30001条预载消息、2400个真实ReviewDesk请求及全部返回字段核验在timer内；完整6个NEW副本各全5通过，单slow最大0.49310秒。历史池构造不计入请求窗口，snapshot、append、latest检查分别验证快照独立值、入池数据所有权和最新观察。

## 2 配置和运行时行为

dbm wrapper给定正确打开模式、UTF8/JSON与键编码。save以agent-name分别存版本化prompt、tool序列和policy-name，以独立配置记录存mode、order、start、budget及有序agent manifest。manifest按定义清单恢复，不能改按名字排序。load只接受声明版本，再从registry绑定函数；同一注册项可绑定多个agent，不能在绑定一次后移除。不能序列化、反序列化或执行任意代码。

tools是正文Agent概念的显式不可变metadata；课程main.Agent没有该字段，prompt同样不影响本地脚本策略。本练习不把保存这些字段说成真实模型调用。

## 3 谁决定下一位

静态解释器只看外部order，即使消息返回done也继续；同一agent出现在多个位置时，每个位置都读取当时的共享历史并执行。handoff解释器每次调用/append后解析当前消息的后继；本轮预算按新执行次数计算，预置历史不占预算。selector解释器先append，再调用外部selector读最新状态；message的handoff仅留在trace里。三者共享正确原语，三个完整body独立实现。运行结果同时保存decisions、完整messages和typed stop，预算耗尽与正常结束区别保留。

## 4 控制证据记录

DecisionProjection按mode选择真正的控制字段：static_next、返回handoff或selector_choice。decision记录原step/speaker、所请求目标、解析outcome及独立message快照，嵌套payload也不与源事件共享可变对象；stop另有reason/executed/last_speaker。正确driver负责async流、发布、关闭及RFC7464型RS+JSON+LF，不重复把这些通用机制交给候选调试。

给定replay_events只是投递已有batch replay结果，不声称P3本身实时执行；自定义async源可逐项到达，callback和driver按到达事件处理。

## 5 组合中的所有权

递归累积tuple scope，分别继承store-id和scheduler。每个leaf保存stores[id]原对象，因此刻意共享可观察到后续append，隔离池仍不同。active只记录当前祖先路径，循环带scope位置报错，无环子树在不同scope复用允许。nestedcomposition是明确本地结构适配，不是框架运行时。

## 来源与范围

来源为正文四原语/无状态观点、main.SharedState/Agent和三种Orchestrator，以及讲解的sender冒充、浅快照、未知目标静默停止与构造差异fixture。课程源实现的snapshot只浅拷贝，last_by返回借用对象；本练习完整snapshot由正确Given实现，append/latest断言验证入池数据和最新观察的所有权；P4记录的递归独立值仍为候选领域职责。typed stop、dbm配置、JSONseq记录和nested composition是局部教学adapter；不实现queue-driven scheduler或框架选择，也不重复coderpad的transition/route_task。

## 这套题证明了什么，没证明什么

本地测试验证所列确定性fixture的共享状态、配置重开、三种控制语义、领域记录和嵌套所有权。它不证明真实LLM路由质量、线程/分布式安全、框架兼容、线上性能或业务收益；没有人类时间校准。
