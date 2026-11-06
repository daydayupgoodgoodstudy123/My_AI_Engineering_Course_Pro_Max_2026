<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="capstone-06--devops-troubleshooting-agent-for-kubernetes"></a>

# 综合项目 06：面向 Kubernetes 的 DevOps 故障排查 Agent

> AWS的开发 Agent 英国国际开发署出版了它的K8游戏手册,NeuBird降格语义监测,Metoro将AI SRE与每个服务性 SLOs绑在一起。 agent 读到遥测, 绘制 K8s 对象的图, 排列根部假设, 并用批准按钮张贴黑条短片。 默认情况下只读。 每个补救都由人锁定。 此综合项目是: agent与AWS的 Agent 三个共同案件

**类型:** Capstone
**语言:** Python (agent), TypeScript (不协调的融合)
**先修要求:** 第11阶段(LLM 工程,第13阶段(工具和 MCP),第14阶段(agents15阶段(自治),17阶段(基础设施),18阶段(安全)
**实施阶段:** P11 P13 P14 P15 P17 P18 P18
**时间:** 30小时

<a id="problem"></a>

## 问题

2025-2026年的《战略教育战略》叙述改为: "大赦国际 agents 分级事件,人类批准补救。"AWS DevOps Agent气态的A,NeuBird,Metoro,PecerDuty AIOps 全部生产成这样的 agent 读普罗米修斯的量度,洛基日志,Tempo traces,kube-state-sectors,以及K8s对象的知识图形。它产生一个在五分钟内进行遥测引用的根部假设。它不会执行破坏命令,除非人类通过Slack明确认可。

大部分的艰苦工作是范围界定和安全,而不是推理。 agent 需要按默认值进行读取的 RBAC 表面, 硬化 MCP 工具服务器, audit logs 需要知道它何时在深度之外升级。 它必须运行到足够便宜的, OOM 致命的级联不会产生5千美元 agent bill.

<a id="concept"></a>

## 概念

该 agent 以知识图运行。 节点是 K8 对象( Pods、 部署、 服务、 节点、 HPAs、 PVCs) 加上遥测源( Prometheus 系列、 Loki 流、 Tempo ) traces) 。边框编码所有者(Pod - > 复制Set - > 部署)、调度(Pod - > 节点)和观察(Pod - > Prometheus系列)。图表由立方体-状态度的同步保持更新,并重新标注每次警报。

当警报着火时 agent 根来自受影响的对象。 它向边缘移动, 拉出相关的遥测切片( 最后15分钟) , 并起草一个假设。 假设按证据排列: 多少遥测引用支持它, 有多近、 多具体。 顶层的3个假设会以图形路径的可视化和批准按钮来显示补救行动。

排除了补救。 允许的默认动作只读。 破坏动作( 缩放、 滚动、 删除波德) 需要 Slack 批准; ArgoCD rollback 钩子需要验证 token 该 agent 永远不能坚持 audit log 记录每个命令 agent *considered* 而不是仅仅执行,因此审查进程几乎失灵。

<a id="architecture"></a>

## 建筑

```
PagerDuty / Alertmanager webhook
           |
           v
     FastAPI receiver
           |
           v
   LangGraph root-cause agent
           |
           +---- read-only MCP tools ----+
           |                             |
           v                             v
   K8s knowledge graph              telemetry slices
     (Neo4j / kuzu)              Prometheus, Loki, Tempo
   ownership + scheduling          last 15m, scoped
           |
           v
   hypothesis ranking (evidence weight)
           |
           v
   Slack brief + approval buttons
           |
           v (approved)
   ArgoCD rollback hook / PagerDuty escalate
           |
           v
   audit log: considered vs executed, every command
```

<a id="stack"></a>

## 堆栈

- Observability 资料来源:普罗米修斯、洛基、坦波、库贝州度。
- 知识图: Neo4j(管理)或K8s天体的kuzu(编织)+遥测边缘
- Agent: LangGraph 使用每个工具允许列表, 默认只读
- 工具传输: 流式HTTP 的快速MCP; 用于破坏性工具的单独服务器 approval gate
- 模型: Claude 索内特4.7,根原因推理 Gemini 2.5 日志汇总闪光
- 补救:阿尔戈CD rollback 网络钩, 呼唤Duty升级, 黑卡
- 审计:仅附件结构化日志(考虑、执行、核准、结果)
- 部署:部署K8,发挥自己狭隘的RBAC作用;另设命名空间

```figure
ce-rootcause-walk
```

<a id="build-it"></a>

## 动手实现

1. **摄取图** 每30岁就将库比-状态测量器同步到Neo4j/kuzu。 节点:波德、部署、节点、服务、PVC、HPA。_按计划分列的_遥测重叠边缘:已观察_逐字(一波德由普罗米修斯系列观测)。

2. **警报接收器** FastAPI 接受 PacherDuty 或 Areedmanger 网络挂图的端点。 提取受影响的对象和 SLO 违反 。

3. **只读工具表面 。** 折叠 kubectl, Prometheus 查询, Loki logql, 通过 FastMCP 折叠 Tempo traceql。 每个工具都有一个狭窄的 RBAC 动词 (“ get, list, " description ” ) 。 在默认服务器中没有“ 删除 ” 、 “ exec ” 、 “ 缩放 ” 。

4. **Root-cause agent.** LangGraph 有三个节点: `sample` 抽出最后15分钟的遥测片段 `walk` 查询相邻对象的图形, `hypothesize` 草稿排列了根级,因为候选人有遥测引用。

5. **证据评分** 每个假设都有分数 = 耐性 * specificity * 图形路径长度反向 * 引用数,回3号顶部

6. **短短的简况。** 添加一个附件, 并加上假设、 图解图象可视化( 一种子图图像可生成服务器) 以及最多一个补救动作的批准按钮 。

7. **修复门** 破坏工具( 缩放、 滚动、 删除) 以秒为时 MCP 服务器在批准后 token. 该 agent 只有在黑卡得到人类批准后才能给他们打电话。

8. **Audit log.** Append-only JSONL: 对于每个候选指令, 记录是否考虑过, 是否执行过, 是谁批准。 每日将船舶送到 S3 号 。

9. **合成事件套房** 构建20个场景: OOMKill 级联、 DNS 扇形、 HPA 塔什、 聚氯乙烯填充、 邻居吵闹、 侧车有问题、 配置马普坏 rollout,证书旋转,图像拉动等。 agent 准确性和时间对假想。

<a id="use-it"></a>

## 实际应用

```
webhook: alert.pagerduty.com -> checkout-api SLO breach, error rate 14%
[graph]   affected: Deployment checkout-api (3 Pods, Node ip-10-2-3-4)
[walk]    neighbors: ReplicaSet checkout-api-abc, Service checkout-api,
           recent rollout 14m ago
[sample]  prometheus error_rate 14%, up-trend; loki 500s on /api/v2/pay
[hypo]    #1 bad rollout: latest image checkout-api:v2.41 fails /healthz
          citations: deploy.yaml (rev 42), prometheus errorRate, loki 500 stack
[slack]   [ROLL BACK to v2.40]  [ESCALATE]  [IGNORE]
          (approval required; agent does not roll back unilaterally)
```

<a id="ship-it"></a>

## 交付成果

`outputs/skill-devops-agent.md` 是一个可交付的。根据 K8s 分组和警告源, agent 产生根部的假设和黑化的补救流程。

| Weight | 标准 | 如何衡量 |
|:-:|---|---|
| 25 | RCA 情景套件的准确性 | 80%正确的根源 20起合成事故 |
| 20 | 安全 | 破坏行动警卫不会在没有获得批准的情况下开火 audit log |
| 20 | Time-to-hypothesis | 从警报到黑短片的5分钟 |
| 20 | Explainability | 每个假设都有图解路径和遥测引用 |
| 15 | 整合完整性 | 呼声杜蒂、黑、亚高克、普罗米修斯-末端工作 |
| **100** | | |

<a id="exercises"></a>

## 练习

1. 运行 agent 同一三起事件 Agent 并发表报告 agent diverges.

2. 添加“ 近距离” 审计, 显示任何命令 agent *considered* 未经批准,这将会是毁灭性的。 测量一周的近乎失职率。

3. 交换假设模型 Claude 索内特4.7 自己托管 Llama 3.3 70B. 测量每起事故的RCA准确度三角形和美元。

4. 构建因果过滤器: 区分相关的遥测刺和真正的根源。 在 20 种假想标签上训练一个小分类器 。

5. 添加a rollback 模拟运行: ArgoCD rollback 与同一舱位的集成物对立。 rollback 计划在一个活的组别中 在 Slack 批准按钮之前。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|------------------------|
| K8s 知识图 | "结晶图" | 节点 = K8s 对象 + 遥测序列;边缘 = 所有权、时间安排、观察 |
| Read-only-by-default | 被搜查的RBAC | Agent服务账户只包含获取/列表/ 记录动词; 破坏性动词在批准后单独生活在服务器中 |
| Audit log | "认为与处决" | 附上每个候选人指令的仅存记录, 不管它是否运行, 谁批准 |
| 假设排名 | 证据评分 | 度量 × 特性 × 图形路径长度 x 引用数 |
| 空白批准卡 | "HITL门" | 带有补救按钮的交互式黑消息; agent 无法继续, 直到点击人手 |
| 遥测引用 | 证据指示器 | 普罗米修斯查询, Loki 选择器, 或 Tempo trace 支持索赔的 URL |
| MTTR | "时间来解答" | 从警戒火力到恢复地面行动 |

<a id="further-reading"></a>

## 进一步阅读

- [AWS 发展窗口 Agent GA](https://aws.amazon.com/blogs/aws/aws-devops-agent-helps-you-accelerate-incident-response-and-improve-system-reliability-preview/) - 2026年的卡尼科尔参考
- [解决 AI K8 故障解析](https://resolve.ai/blog/kubernetes-troubleshooting-in-resolve-ai) 竞争者参考
- [神经鸟语义监测](https://www.neubird.ai) 语义学方法
- [梅托罗・艾斯雷](https://metoro.io) - SPO第一种生产框架
- [kube-state-metrics](https://github.com/kubernetes/kube-state-metrics) 集群国家来源
- [LangGraph](https://langchain-ai.github.io/langgraph/) 参考 agent orchestrator
- [FastMCP](https://github.com/jlowin/fastmcp) — Python MCP 服务器框架
- [ArgoCD rollback](https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_app_rollback/) - 门外的补救目标
