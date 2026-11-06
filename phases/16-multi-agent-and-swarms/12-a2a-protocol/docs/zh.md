<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="a2a--the-agent-to-agent-protocol"></a>

# A2A：Agent 与 Agent 之间的通信协议

> 谷歌宣布 A2A 2025年4月;到2026年4月,该规格 https://a2a-protocol.org/latest/specification/ 150多个组织支持这一倡议。 A2A 是水平补充 MCP (教训13): MCP 是垂直( 与直线相距)agent 工具), A2A 是对等方对等( P)agent ↔ agent定义 Agent 纸牌(发现)、人工制品任务(文字、结构数据、视频)、不透明的任务生命周期和认证。 MCP 与 A2A谷歌云卷 A2A 支持输入 Vertex AI Agent 2025-2026年的建筑师

**类型:** 学习 + 构建
**语言:** Python (stdlib, `http.server`, `json`)
**先修要求:** 阶段16 -04(初级模型)
**时间:** ~75分钟

<a id="problem"></a>

## 问题

你的 agent 需要再打一个 agent 如何揭发 HTTP 终点, 定义一个词 JSON 机率,希望对方会说 agents 成为习惯整合。

A2A 标准发现,标准任务模型,标准运输,标准工艺品。 HTTP+REST 仅供 agents 身为一流公民

<a id="concept"></a>

## 概念

<a id="the-four-elements"></a>

### 四个要素

**Agent Card.** 一个 JSON 文档 `/.well-known/agent.json` 说明 agent: 名称、技能、终点、支持 modalities鉴定要求 发现是通过读卡片发生的

```
GET https://agent.example.com/.well-known/agent.json
→ {
    "name": "code-review-agent",
    "skills": ["review-python", "review-typescript"],
    "endpoints": {
      "tasks": "https://agent.example.com/tasks"
    },
    "auth": {"type": "bearer"},
    "modalities": ["text", "structured"]
  }
```

**Task.** 工作单位,一个有生命周期的、 清晰的物体: `submitted → working → completed / failed / canceled`。客户发送任务、民意测验或订阅更新。

**Artifact.** 任务生成的结果类型。 JSON,图像,视频,音频。 modalities 头等舱

**阴暗的生命周期** A2A 不开 *how* 远程 agent 解决任务。 客户端看到状态转换和工艺品; 执行可以自由使用任何框架 。

<a id="the-mcpa2a-split"></a>

### 该 MCP/A2A split

- **MCP** (教训13): agent 工具。 agent 读/写 JSON-RPC 键入工具服务器。 默认情况下不具有 National 状态 。
- **A2A**: agent ↔ agent. 同行协议;双方 agents 他们的推理

生产多功能-agent 系统使用两种方法。 A2A 对等点呼叫 MCP 工具在它一边,分裂可以消除两个问题

<a id="discovery-flow"></a>

### 发现流

```
Client                     Agent server
  ├──GET /.well-known/agent.json──>
  <──Agent Card JSON─────────────
  ├──POST /tasks {skill, input}──>
  <──201 task_id, state=submitted
  ├──GET /tasks/{id}──────────────>
  <──state=working, 42% done──────
  ├──GET /tasks/{id}──────────────>
  <──state=completed, artifacts──
```

或与 streaming:SSE订阅 `/tasks/{id}/events` 用于按键更新。

<a id="auth"></a>

### Auth

A2A 支持三种常见模式:

- **Bearer token** 或不透明。
- **mTLS** ——相互之间 TLS; 各组织相互证明身份。
- **签署请求** - HMAC在有效载荷上方

认证在 Agent 信用卡;客户发现并遵守。

<a id="150-organizations-by-april-2026"></a>

### 2026年4月前150个以上组织

企业收养驱动 A2A 缩放。 标题 : A2A 成为企业的方式 agent 系统交叉 trust boundaries谷歌云号运送 Agent Builder A2A 支持; 微软 Agent 框架支持这一框架;大多数主要框架(LangGraph, CrewAI,自动Gen) 舰 A2A adapters.

<a id="where-a2a-wins"></a>

### Where A2A wins

- **跨组织电话** Agent 公司A电话 agent B公司没有 A2A每对都是一份约定合同
- **不同框架。** LangGraph agent calls CrewAI agent 调用自定义 Python agent. A2A normalizes.
- **输入文物** 视频结果,结构 JSON音频 - 全部头等舱。
- **长期任务** 透明生命周期+投票使工作时间的任务变得简单明了。

<a id="where-a2a-struggles"></a>

### Where A2A struggles

- **静脉注射微电话** A2A寿命周期为零。 agent-以-agent 不适用;使用直接RPC。
- **工艺中紧凑的组合 agents.** 如果两者 agents 在同一条线上运行 Python process, A2A的 HTTP 往返是超乎寻常的
- **小型团队** 标本是真实的; 仅内部 agents 可能不需要手续

<a id="a2a-vs-acp-anp-nlip"></a>

### A2A 与非加太国家、非加太国家、非加太国家、非利太国家

2024-2026年出现了若干相关情况:

- **ACP** (IBM/Linux基金会)——前身 A2A,范围较窄。
- **ANP** (Agent 网络协议)——同侪发现重,权力下放第一。
- **NLIP** (Ecma自然语言互动协议,2025年12月标准化)——自然语言内容类型。

A2A 2026年4月时采用最多的对等协议。 Agent 比较时使用互操作性协议。

```figure
sw-agent-card-discovery
```

<a id="build-it"></a>

## 动手实现

`code/main.py` 执行 A2A- 最小服务器和客户端使用 `http.server` 和 JSON服务器 :

- exposes `/.well-known/agent.json`,
- accepts `POST /tasks`,
- 管理任务状态,
- 返回 NAME OF TRANSLATORS 上显示的工艺品 `GET /tasks/{id}`.

客户端:

- 获取 Agent Card,
- 提交一项任务,
- 民意调查直到完成
- 读到艺术品。

Run:

```
python3 code/main.py
```

脚本以背景线启动服务器, 然后运行客户端与之相对。 您可以看到完整的流程: 发现、 提交、 民意调查、 工艺品 。

<a id="use-it"></a>

## 实际应用

`outputs/skill-a2a-integrator.md` 设计 a A2A integration: Agent 牌的内容,任务计划, 认证选择, streaming 投票

<a id="ship-it"></a>

## 交付成果

Checklist:

- **插入规格版本 。** A2A 仍在演变中; Agent 卡片应声明协议版本。
- **同上,《授权任务创建》。** 重复提交文件(网络重写)应产生一项任务。
- **人工图案** 宣布什么形状 agent 返回; 消费者应验证。
- **Rate limits + 认证。** A2A 以公用方式; 使用标准网络安全。
- **失败的任务的死信** 检查反复出现的故障类型。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`. 确认客户发现了服务器并接收了正确的文物。
2. 向服务器添加第二个技能( 例如“ 概要” ) 。 更新 Agent 卡片,写一个客户端根据任务类型选择技能。
3. 实施 SSE streaming endpoint: `/tasks/{id}/events` 客户需要做什么不同的事情?
4. 阅读 A2A 规范（ https://a2a-protocol.org/latest/specification/ ）。找出规范强制要求、但此演示尚未实现的三个事项。
5. Compare A2A (Agent 贺卡发现)至 MCP (服务器端能力清单通过 `listTools`)自我描述之间的权衡 agents 以及能力测试?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| A2A | "Agent-以-agent" | 等同协议 agents 调用其它 agents 跨系统,谷歌2025 |
| Agent Card | "该 agent名片,你记着 | JSON 在 `/.well-known/agent.json` 描述技能,终点,认证。 |
| 任务 | 工作单位 | 与生命周期同步的有声物体;完成后生产的文物。 |
| Artifact | 结局 | 输入输出: 文字, 结构化 JSON图像、视频、音频 头等媒体 |
| 透明生命周期 | "如何解决它就是 agent生意上的事吗? | 客户看到状态转换; 服务器可以自由选择框架/工具 。 |
| Discovery | "发现 agent" | `GET /.well-known/agent.json` 返回该卡。 |
| MCP 与 A2A | "工具对同行" | MCP: 垂直 agent 工具 A2A: 水平 agent ↔ agent. |
| 非加太/非加太/非加太/非加太/非利太 | "赛车协议" | 相近的形状; A2A 2026年最受欢迎的 |

<a id="further-reading"></a>

## 进一步阅读

- [A2A specification](https://a2a-protocol.org/latest/specification/) - 弹簧图
- [谷歌开发者博客 A2A announcement](https://developers.googleblog.com/en/a2a-a-new-era-of-agent-interoperability/) - 2025年4月发射站
- [A2A GitHub repo](https://github.com/a2aproject/A2A) 参考执行情况和 SDKs
- [Liu等人——对巴勒斯坦的 Agent 互操作性议定书](https://arxiv.org/html/2505.02279v1) — MCP、非加太国家, A2A,ANP比较
