<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="sre-for-ai--multi-agent-incident-response-runbooks-predictive-detection"></a>

# AI 的 SRE：多 Agent Incident Response、操作手册与预测性检测

> AI SRE 用途 LLMs 以基础设施数据(logs、runbooks、服务地貌学)为基础 RAG 将调查、文件和协调阶段自动化。2026年的建筑模式是多层-agent orchestration 专业 agents 由主管协调的(行踪、度量、运行记录); AI提出假设和询问, 人类批准判决。 数据犬 Bits AI 和 Azure SRE Agent 运行手册正在演变:NeuBird Hawkey使用对抗性 evaluation (两个模型分析同一事件;协议=信心,分歧=不确定性); 整个团队变化中都存在操作记忆。 自动补救保持谨慎: AI建议, 人类同意。 完全自主的行动是狭窄的( 重新启动舱, 恢复舱, ) rollback 特别部署) guardrails 任何卖掉"设置它,忘记它"的人都是超市的。 LLM 接受历史日志+培训 GPU 临时+ API 错误模式预测89%的中断时间提前10-15分钟。 LLMs 2026年底自动失效

**类型：**学习
**语言:** Python (斯迪利布,玩具多功能-)agent 事故分类模拟器)
**先修要求:** 阶段17 · 13 (Observability17阶段 24(化石工程)
**时间：** ~60 分钟

<a id="learning-objectives"></a>

## 学习目标

- 图像显示多agent AI SRE 结构:主管+专门人员 agents (logs、 度量、 运行手册)+人类 approval gate.
- 解释为什么自动补救范围狭窄(重新启动舱、恢复部署),而不是广泛(再分类服务)。
- 命名对抗性 evaluation 模式 (NeuBird Hawkey):两种模式同意=信任;不同意=升级。
- 检查MIT89%的早期检测结果和操作限制:不进行激活的预测只是仪表板。

<a id="the-problem"></a>

## 问题

一名待命工程师在凌晨3点被呼叫"高出错率" 他们检查了Datadog, Loki, 三个运行簿,部署日志。 vLLM 自动读取 KV cache 刺钉。 它们重新启动缓存; 错误清除 。

2026年,调查的头20分钟是自动的。 RAG + 工具使用。 agent 可以在人类打开数据犬之前 做第一通道的分解 并给出一个假设

完全自主的补救是一个不同的问题。 重新启动舱: 安全。 缩放 GPU 集合: 如果政策允许, 安全。 重新排序服务: 绝对不是。 学科正在绘制狭义的线条 。

<a id="the-concept"></a>

## 概念

<a id="multi-agent-architecture"></a>

### Multi-agent architecture

```
          Incident
             │
             ▼
        Supervisor
        /    |    \
       ▼     ▼     ▼
  Log agent  Metric agent  Runbook agent
       │     │     │
       └─────┴─────┘
             │
             ▼
        Hypothesis + evidence
             │
             ▼
        Human approval
             │
             ▼
        Action (narrow set)
```

主管把事件分成小区 agents 具有工具访问权限(log search, PromQL, doc recret)。主管合成,向人类提供假设+证据。人类认可或重定向。

<a id="auto-remediation-scope"></a>

### 自动补救范围

**安全( 窄)**: 重新启动缓存, 恢复特定部署, 在预先批准的界限内进行比例组合, 启用预批准的 feature flag.

**不安全( 宽度)**:改变服务表层,修改资源限制,部署新代码,改变内部管理,改变数据库。

卖"设置它,忘记它"的人都是超市的。

<a id="adversarial-evaluation-neubird-hawkeye"></a>

### Adversarial evaluation (新鸟鹰眼)

两种模型独立分析同一事件。 如果他们对根源达成一致, 信心就会很高。 如果不同意, 则以两种假设都可见的方式向人类升级。 简单模式, 有效的过滤器来消除幻觉的根源 。

<a id="operational-memory"></a>

### 操作内存

团队更替是无声杀死传统的SRE——部落知识的离开。 agents 每当新事件发生后 人工智能就会有完整的历史

<a id="pre-incident-prediction"></a>

### 事故前预测

麻省理工学院2025年研究: LLM 接受历史记录培训, GPU temperatures, API 错误模式预测了89%的断电 10-15分钟前,它们发生在测试组。

现实检查: 没有激活的预测是仪表板。操作问题在于“ 当我们预测, 我们做什么?” 先发制人地排水? 切入器?自动标尺?答案是针对政策。

<a id="products-in-2026"></a>

### 2026年的产品

- **数据犬位数 AI** - 管理SRE在数据狗内部的副驾驶
- **浅色 Agent** - 亚祖尔 - 本地人
- **中鸟鹰眼** 对抗性电子反应+操作记忆。
- **呼机自动导航器** - 分级+重复。
- **事件.io 自动驾驶** 事件指挥官+协调。

<a id="runbooks-as-code"></a>

### 以代码运行簿

运行手册从“影响”页面演变为版本 markdown 结构化运行簿更好地提供 RAG 检索。 启动任何 AI- SRE rollout 将无结构的运行手册变成结构化的

<a id="numbers-you-should-remember"></a>

### 数字您应该记住

- 麻省理工学院早期检测:89%的停机率,10-15分钟的准备时间。
- Multi-agent 分级:主管+(logs、度量、运算簿)+人。
- 安全自动补救装置:重新启动舱,恢复部署,在范围内进行规模。
- 反向评估:两种模式独立;协议=信任。

```figure
i4-incident-agents
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 模拟多agent 分类: 日志 agent 发现错误, 度量 agent finds CPU 钉子, 运行本 agent 与已知的题材相符 主管排在假设的顺序上

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-ai-sre-plan.md`。鉴于当前的待命情况、事件数量、团队成熟程度,设计AI SRE rollout.

<a id="exercises"></a>

## 练习

1. Run `code/main.py`。如果日志和测量 agents 意见不一?
2. 定义三个“ 安全” 自动补救操作, 以用于您的工作。 请对每个操作进行合理化 。
3. 写入结构化运行手册模板: 区域、 所需字段、 校验命令 。
4. 12分钟前的预测火灾。您有什么政策? 呼叫器、前排或两者兼有?
5. 询问一个三人小组是否应该在2026年采用AI SRE。 考虑成熟度、 体积、 风险 。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| 阿尔斯雷 | "agent 等待召唤 | LLM- 支持事件调查+协调 |
| Supervisor agent | 指挥者 | Top-level agent 将事件破解为子查询 |
| Specialized agent | "domain agent" | Sub-agent 工具访问(行数、度量、运行簿) |
| Auto-remediation | 人工智能修补 | 狭义的预批准动作; 不宽度重构 |
| 操作内存 | "维多的书" | 死后 + 矢量 DB 中的运行簿 RAG |
| 反向评估 | "两模检查" | 独立分析;协议=信任 |
| 中鸟鹰眼 | "对抗的一方" | 带有对抗性-eval+内存模式的产品 |
| 位元 AI | "数据狗的SRE agent" | 数据管理 AI SRE |
| 事故前预测 | 早期发现 | 10-15分钟的停电预测准备时间 |

<a id="further-reading"></a>

## 进一步阅读

- [事故 - AI SRE 完整指南 2026](https://incident.io/blog/what-is-ai-sre-complete-guide-2026)
- [信息Q - 以人类为中心的服务](https://www.infoq.com/news/2026/01/opsworker-ai-sre/)
- [区 - 2026年教育年](https://dzone.com/articles/ai-in-sre-whats-actually-coming-in-2026)
- [数据犬位数 AI](https://www.datadoghq.com/product/bits-ai/)
- [中鸟鹰眼](https://www.neubird.ai/)
- [awesome-ai-sre](https://github.com/agamm/awesome-ai-sre)
