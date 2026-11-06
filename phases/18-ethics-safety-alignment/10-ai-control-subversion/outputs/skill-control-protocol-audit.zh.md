---
name: control-protocol-audit
description: Audit a deployment protocol under the AI Control threat model.
version: 1.0.0
phase: 18
lesson: 10
tags: [ai-control, subversion, trusted-editing, untrusted-monitoring, safety-case]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


有了部署协议说明,就按照AI控制进行审计 threat model:U(不信任强者)、T(信任弱者)、H(信任人),衡量协议在有用性安全前沿的立场。

显示 :

1. 角色分配。 确定哪个模型扮演U, 哪个扮演T。 如果 T是另一个 U, 立即会面临串通旗牌的风险 。
2. 审计预算会计。H是如何分配的?统一、随机、标有旗帜?预期对产出进行多少部分审计?
3. 串通- 矢量计数。 对于每一对不可信的部件( U- 制导器 + U- 监测器, U- 制导器 + U- 编辑器), 都列出了串通矢量: 线条、 共享训练前的开发、 定时通道 。
4. 能力差距分析。 T 比 U 弱多少? T 编辑信号何时会变成噪音( 例如, T 无法可靠地检测到U 生成的后门) ?
5. Worst-case threat model。假设U是完全了解协议的敌对方,那么敌人的最佳策略是什么?什么是红队成功?

艰难的拒绝 :
- 任何协议描述,使用U作为自己的监视器 没有串通-抵抗机制。
- 任何没有红色小队的“近零速率”协议 evaluation 红色小队有协议可见度的地方
- 对协议进行的审计,不说明T-至U能力差距和H预算。

拒绝规则 :
- 如果用户问“是否安全”,则在没有三部分证据的情况下拒绝:(a) 红色小组的结果;(b) 能力差距估计;(c) H预算。
- 如果用户混在一起 alignment 并使用“控制”(“我们与U对齐,所以不需要协议”),alignment 假装) alignment 属于U的财产;控制属于协议的财产。

产出:一页审计,填充上述五个部分,列出最薄弱环节(通常是T-U能力差距或串通阻力),并注明最大的未解决失败模式。
