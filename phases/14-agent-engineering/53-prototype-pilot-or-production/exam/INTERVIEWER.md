# 面试官手册：StageGate（14/53）

候选人计时期间不要看。候选人只有README、stagegate/与tests/。

## 开场（2分钟）

说明60分钟，逐关解锁，测试原样通过，请边做边讲。约5分钟卡住给一级提示。阶段是学习环境和责任承诺，不是deployment完成度分数。

## 澄清问题的标准答案

只在问到时用英文回答。

| 关 | 问题 | 回答 |
|---|---|---|
| 1 | Does lower readiness downgrade production? | No. Keep the declaration and show the recommendation separately. |
| 1 | Does active telemetry define the pilot audience cap? | No. Active sessions are a separate measurement; exposed_users is cumulative admitted exposure. |
| 1 | One user has two sessions? | Count that user once until the last live session leaves. Session ids are scoped per system. |
| 2 | Should markers redefine stage during load? | No. Preserve declaration and all independent markers exactly. |
| 3 | May a pilot use production data? | Yes, inside its explicit audience, duration and authority boundaries. |
| 3 | Is the final pilot date inclusive? | Yes. Expired means after that date. |
| 3 | Is a warning banner enough? | No. Configuration, access and telemetry must also expose the boundary. |
| 4 | No new alert means safe? | No. An already reported issue still blocks the controlled next step. |
| 4 | Does recovery rearm the same reason? | Yes. EpisodeGate supplies that state correctly. |
| 5 | Must every dependency be production? | No. Check explicit necessary-edge ownership, controls and authority; optional experiments are excluded. |
| 5 | Which path witnesses a missing obligation? | The smallest actual path through an edge that imposes that obligation, not an unrelated path to the same child. |

## 每关：要看什么、提示、追问

### Part 1 阶段计划（目标12分钟）

坑：
1. pilot表漏named audience、bounded duration/authority与outcome/guardrail threshold。plan→_missing→required_controls两层下的表使上层计划不完整。
2. 需要的控制应减去已有控制，不能把完整清单都当缺失。
3. readiness变化使推荐变pilot，但不能静默改掉production声明。
4. 每次session变化重建所有live user的set。参考按用户维护活跃session引用计数，重复session、换user和最后离开都正确。

14000个session实测慢0.964/1.005/0.968秒，快4.736/4.429/4.241毫秒，限值0.08秒，双侧至少8倍。这是本题活跃遥测扩展，不是用同时在线数代替pilot的总受众。

看什么：沿计划查control表，区分声明、推荐、已具备控制与当下活跃遥测。

提示：“Which obligations are missing two calls below this plan?”；“Is this a recommendation or an explicit declaration update?”；“Does one departing session remove the user?”

追问：如何记录正式阶段变更的批准？轮流让大量用户加入为何仍可能突破pilot受众边界？

### Part 2 阶段登记册（目标10分钟）

坑：
- 声明与各处marker独立，不用某个marker或readiness重算声明。
- audience整数、原deadline、authority/exit/control tuple顺序和原文完整往返。
- 同id显式替换只影响该系统，重开仍可读；还原独立typed snapshot。

给定decode已正确区分marker缺失与空内容，边界仍保留。标准JSON/SQL不是本关新协议。

看什么：源状态与推导结果分开持久化。

提示：“Would reopening this row tell the same declaration and every technical boundary?”

追问：真实系统如何保持四个技术标记与批准记录的一致性？本题不实现多系统事务。

### Part 3 阶段漂移（目标14分钟）

坑：
- pilot可用production data；累计exposed_users超过cap、过inclusive期限分别报。
- prototype无主暴露、production data或write authority不能悄悄扩大；production缺on-call仍负原责任。
- 四处marker逐处比较，文档横幅不替代技术边界；同一观察所有缺口按固定顺序保留。
- declaration决定control合同，观测到“能用”不等于责任已到位。

看什么：明确暴露字段的范围，不把阶段变成普遍全序或由事实自动升级。

提示：“Did the organization change the declaration, or did exposure drift?”

追问：缺on-call时应停止哪些流量？应根据具体consequence和操作政策判断，而不是自动降级后继续服务。

### Part 4 漂移episode流（目标12分钟）

坑：
- 当前仍有问题即不release；新告警为空只是已报过，不能当成safe。
- 原因恢复后再出现会重新报告；EpisodeGate已正确处理状态，不重做“同key仅报一次”题。
- 同快照全部告警发完再拉下一份，不能在一个unsafe系统后终止所有监控，取消不预拉。

正确alert helper给完整私有syslog样式与UTC日期/JSON，不要求课文未教的RFC细节。

看什么：当前安全状态与通知去重分工，fake next-step在safe快照才放行。

提示：“Which list decides safety, current issues or newly entered alerts?”

追问：监测已经发生的暴露能否撤销真实写入？不能；此处release只控制下一步假动作，真实权限边界必须提前存在。

### Part 5 必要依赖责任（目标12分钟）

坑：
- optional隔离实验不强加必要依赖义务；不可达分支也不算。
- 共享组件每条必要edge的义务独立，不能检查第一条就跳过后面的control。
- ownership、具体control和超出allowed authority分别判断，不能用stage标签代替。
- 同缺口留最小真实witness edge-path；某个缺control只由一条edge要求时，不能拿另一条更小但不要求它的路径作证。

required_paths已给正确迭代有限DAG/schema与必要路径，长链和cycle护栏仍验证helper，不考通用最短补全算法。政策是本题组织的明确要求，不是行业通用production等级链。

看什么：沿实际承诺找责任缺口，保留可行动证据。

提示：“Which necessary edge imposed this obligation?”

追问：可选组件何时会变成实际必要依赖？需要怎样的观测和显式政策更新？

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 调试与效率 | 25 | 控制表、声明、用户session引用 |
| 精确持久化 | 15 | 声明和四处独立marker |
| 漂移判断 | 25 | 累计暴露、责任和完整诊断 |
| 在线边界 | 20 | 持续问题、恢复、输出、取消 |
| 依赖与沟通 | 15 | 具体义务、真实证据路径 |

记录实际证据、用时与提示次数，没观察到写“未观察”。允许等价实现。
