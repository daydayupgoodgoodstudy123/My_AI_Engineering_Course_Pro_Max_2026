---
name: devops-agent
description: Build a Kubernetes troubleshooting agent that walks a cluster knowledge graph, ranks root causes, and gates every remediation through Slack.
version: 1.0.0
phase: 19
lesson: 06
tags: [capstone, devops, sre, kubernetes, langgraph, fastmcp, aiops]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给 K8 组和提醒源( PagerDuty 或 Awardmanger) 创建 agent 5分钟内就会出现假想 并且通过一张黑卡 将所有的补救都锁定

构建计划 :

1. 以千兆赫的立方体测量为新四j或库祖每30年。 绘制一个波德、 部署、 服务、 节点、 PVC、 HPA 和遥测覆盖边缘图, 以至普罗米修斯、 Loki 和 Tempo 源 。
2. 站起来 FastAPI 呼叫器和警报器的网络钩接收器
3. 通过流式HTTP传输的快速MCP 来展示只读工具: kubectl get/ description, praql, logql, traceql。
4. 构建 LangGraph root-cause agent 有三个节点: `sample` (拉15米遥测) `walk` (横幅图邻居) `hypothesize` (按英才x具体度x引证计数排列候选人名)
5. 将上三级的假设加上图形路径可视化,用批准按钮贴到Slack。
6. 安装破坏性工具( 比例, 比例) rollback,删除)在批准后的一个单独的 FastMCP 服务器上 token 该 agent 只有在签署后才能获得。
7. 保持只附加 audit log: 每个 *considered* 命令,是否核准,是否执行,谁批准。
8. 制作20个合成事件假设(OOMKill、DNS flap、HPA Thash、PVC填充、邻居吵闹、侧车有问题、配置地图坏) rollout, Cert 旋转,图像拉倒,检测失败,再加10。 agent RCA的准确性和时间对假设。

评估标题:

| Weight | 标准 | Measurement |
|:-:|---|---|
| 25 | RCA 情景套件的准确性 | 20起合成事故中至少80%的正确根源 |
| 20 | 安全 | 破坏行动警卫不会在没有获得批准的情况下开火 audit log |
| 20 | Time-to-hypothesis | 从警报到黑短片的5分钟 |
| 20 | Explainability | 每个假设都有图解路径和遥测引用 |
| 15 | 整合完整性 | 呼声杜蒂、黑、亚高克、普罗米修斯-末端工作 |

艰难的拒绝 :

- Agents 单 MCP 混合只读和破坏性工具的服务器。
- 任何没有遥测引用的RCA 生成的,必须拒绝未引用的假设。
- Audit logs 记录死刑,他们必须记录所有考虑过的指令
- 声称准确而未运行 agent 对抗20层的种子套房

拒绝规则 :

- 拒绝补救而不征求人情的许可,即使假设是显而易见的。
- 拒绝曝光 `kubectl exec`, `kubectl port-forward`,或通过只读工具进行的任何交互式工具 MCP。这些是毁灭性的。
- 拒绝在多次部署中分批实施补救,无需每次部署的核准卡。

输出: 包含 FastAPI 接收器 LangGraph agent,即只读和具有破坏性 MCP 服务器, Slack 集成, 20 情景测试套件, 与 AWS DevOps 的平行比较 Agent 以及一份有关近乎缺失的命令的书目( agent *considered* 但未执行),在一个为期一周的观察窗口中。
