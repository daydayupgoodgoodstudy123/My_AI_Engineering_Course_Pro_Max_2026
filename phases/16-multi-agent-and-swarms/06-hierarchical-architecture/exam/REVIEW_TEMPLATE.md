# 复盘模板

每关填写：首个可观察症状、责任 producer、消费者合同、必要修改、保留的行为、一个过修反例。

| 关 | 复盘问题 |
|---|---|
| 1 | branch availability 与 leaf epistemic status 怎样区分？canary 的原问题边界在哪里？完整结构 report 的重复工作是什么？ |
| 2 | 为什么 ZIP 位置或推算文件名不能决定逻辑引用？共享 leaf 怎样保持一个身份？ |
| 3 | 原 obligation 怎样逐边变成本地 id？何处开始漂移？canary 为什么不能覆盖 hierarchy 证据？ |
| 4 | branch audit 为什么不是一次 leaf 执行？原 obligation 与 local task id 的展示职责是什么？ |
| 5 | 为什么一次执行可有多条 citation 路径？UNKNOWN 怎样影响祖先状态？ |

完整结构服务的本机校准覆盖 4,000 个真实 manager report，全部 branch/leaf/canary/manager 输出相等检查位于 timer 内；限值 0.085 秒，三次慢版 0.796–0.834 秒，三次参考版 0.0067–0.0079 秒。双侧余量分别 9.36×、10.73×。这是本地完整路径的响应检查，不是部署 SLA。

记录命令、五关结果、性能测量边界及仍未验证的主张。区分已封存 fixture 的确定性行为与真实组织/模型质量。

检查内部 manager 的归档、同深度漂移顺序、缺席 canary 与 UNKNOWN 的独立归属、worker 显示名和 leaf id 的区别，以及 unavailable manager 与混合直接/孩子引用的嵌套解释。当前为五个锁定测试、37 条 assert、4 个异常合同检查；24 个错修登记包括 16 个 canonical 验证、7 个独立 fresh 核心方向与 1 个自然跨关辅助方向。
