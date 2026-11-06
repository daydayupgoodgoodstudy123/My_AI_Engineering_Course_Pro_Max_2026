---
name: tripwire-design
description: Review a proposed agent detector stack (kill switch, circuit breakers, canary tokens) and flag missing tripwires before the first autonomous run.
version: 1.0.0
phase: 15
lesson: 14
tags: [kill-switch, circuit-breaker, canary, honeytoken, detection-and-response]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给一个提议的检测器堆放 agent 使用,根据三分探测器的参考( kill switch, ) 进行审计 circuit breaker或暴露在 agent.

显示 :

1. **杀手交换检查** 开关的运行位置( W)feature 国旗, Redis, 签名配置) ? 确认 agent证书无法启动。 确认每次相应的动作检查开关, 而不仅仅是启动。 确认重新启用是一个明确的人为动作 。
2. **电路破解器库存** 列出每个断开器的显示模式( 重复、 连续失败、 率、 超文本值后的具体工具) 。 国家门槛值和每条线的冷却值通常都太松散 。
3. **加纳设计。** 列出每个金丝雀 token 。 对于每一个对象:它是什么( 假的证书、 假的 DB 记录、 假的文件、 假的内存条目) , 它住在哪里, 什么样的访问触发了警报, 是谁被呼叫。 确认没有金丝雀有被触动的合法理由 。
4. **统计+硬分层。** 确认堆栈除了使用任何统计探测器(EWMA, z-score)外,至少使用一个硬限( Lesson 17 宪法风格 ) 。 仅统计探测器接受慢流。
5. **隔离路径** 探测器失火时会怎样? agent 停止, 路径特定的暂停, 交通重定向( eBPF/ 蜜罐) , 仅提醒。 确认路径已经至少测试一次 。

艰难的拒绝 :
- 任何没有外部杀手开关的部署
- Canary tokens 储存在系统中的 agent 具有写入权限。
- 仅统计检测,没有硬性限制。
- Circuit breakers 和冷却的,自动重新 能够不经过人类审查。
- 仅在启动时检查杀死开关, 而不是每次操作时检查。

拒绝规则 :
- 如果用户无法命名 agent拒绝使用 。 agent 读"不是一个杀开关,如果 agent 能够写入配置文件。
- 如果用户将自动模式分类器( 列松 10) 视为绊线的替代, 请拒绝。 分类器对检测和响应有正反方向的功能 。
- 如果建议金丝雀坐落在系统中 agent 有理由阅读、拒绝和需要重新设计。

输出格式 :

返回一个绊线审计, 包括:
- **切换线** (地点、检查音频、可重新启用程序)
- **断路器** (模式,门槛,冷却)
- **加那利桌 :** (token、地点、报警器、所有者)
- **层注** (统计+硬限值存在y/n)
- **隔离流** (什么火灾,发生了什么,测试y/n)
- **Readiness** (生产/中转/仅研究)
