<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="a2a--agent-to-agent-protocol"></a>

# A2A：Agent 与 Agent 之间的通信协议

> MCP 是 agent-to-tool. A2A (代理2 Agent)是 agent-以-agent 开放的不透明程序 agents 以不同的框架为基础。 2025年4月,Google发行了该奖项,于2025年6月捐赠给Linux基金会,2026年4月达到1.0,有150个支持者,包括AWS、Cisco、微软、Selveforce、SAP和Service Now。它吸收了IBM的ACP,并增加了AP2的付款延期。 Agent 贺卡,任务生命周期, 和两个运输装配。

**类型:** Build
**语言:** Python (stdlib, Agent 卡片 + 任务 harness)
**先修要求:** 阶段13 · 06 (MCP 基本知识,阶段13 08 (MCP client)
**时间:** ~75分钟

<a id="learning-objectives"></a>

## 学习目标

- Distinguish agent- 换到工具(MCP) 来自 agent-以-agent (A2A) 使用场景.
- 发布 Agent 开牌时间 `/.well-known/agent.json` 具有技能和终端元数据。
- 随身携带任务生命周期(提交 } } } } } 需要 } / / / / / / / / 拒绝)
- 使用含有部件( 文本、 文件、 数据) 和个体化的信件作为输出 。

<a id="the-problem"></a>

## 问题

客户服务 agent 需要委托专业作家撰写报告 agent选项前A2A:

- Custom REST API工作,但每对都是一次性的
- 共享代码库。 需要两个 agents 来运行相同的框架。
- MCP不合时宜 MCP 用来调用工具,不是两个 agents 合作,同时保存 agent内部推理不透明

A2A 填补空白。 它将互动模拟为一体 agent 向另一个任务发送, 并附有生命周期、 信息及文物。 agent国内状况不透明, 打电话者只看到任务状态的过渡和最终产出。

A2A 是"让我们" agents 而不是替换 MCP;两者是相辅相成的。

<a id="the-concept"></a>

## 概念

<a id="agent-card"></a>

### Agent Card

每个 A2A-compliant agent 发表一张卡片 `/.well-known/agent.json`:

```json
{
  "schemaVersion": "1.0",
  "name": "research-agent",
  "description": "Summarizes academic papers and drafts citations.",
  "url": "https://research.example.com/a2a",
  "version": "1.2.0",
  "skills": [
    {
      "id": "summarize_paper",
      "name": "Summarize a paper",
      "description": "Read a paper PDF and produce a 3-paragraph summary.",
      "inputModes": ["text", "file"],
      "outputModes": ["text", "artifact"]
    }
  ],
  "capabilities": {"streaming": true, "pushNotifications": true}
}
```

发现基于 URL: 获取卡片, 学习 A2A 终点,列举技能。

<a id="signed-agent-cards-ap2"></a>

### Signed Agent 贺卡(AP2)

AP2扩展(2025年9月)添加加密签名 Agent 出版商用自己的卡签 JWT; 消费者验证。防止冒充。

<a id="task-lifecycle"></a>

### 任务生命周期

```
submitted -> working -> completed | failed | canceled | rejected
             -> input_required -> working (loop via message)
```

客户主动提出 `tasks/send`。 agent 由各州过渡;客户通过国家安全系统或民意调查订阅国家最新情况。

<a id="messages-and-parts"></a>

### 信件和部件

信件含有一个或多个部件 :

- `text` - 简单的内容。
- `file` 基底64号,带米米特普
- `data` - 打字 JSON 有效载荷(为所谓的 agent).

示例：

```json
{
  "role": "user",
  "parts": [
    {"type": "text", "text": "Summarize this paper."},
    {"type": "file", "file": {"name": "paper.pdf", "mimeType": "application/pdf", "bytes": "..."}},
    {"type": "data", "data": {"targetLength": "3 paragraphs"}}
  ]
}
```

<a id="artifacts"></a>

### Artifacts

输出为人工制品, 不是原始字符串。 人工制品是一个命名的、 输入的输出 :

```json
{
  "name": "summary",
  "parts": [{"type": "text", "text": "..."}],
  "mimeType": "text/markdown"
}
```

人工制品可以像块一样流出。呼叫器会累积。

<a id="two-transport-bindings"></a>

### 两个运输装订

1. **JSON-RPC over HTTP.** `/a2a` 终端, 请求的 PST, 选择 SSE streaming。默认约束。
2. **gRPC.** 适用于本地的菲律宾竞争委员会企业环境。

两个绑定都带有相同的逻辑信息形状。

<a id="opacity-preservation"></a>

### 不透明度保全

关键设计原则: agent内部状态不透明, 打电话的人看到任务状态和工艺品。 agent的 chain-of-thought, 它的 tool calls,其子agent delegation 都看不见,这和 MCP中,该选项 tool calls 透明。

Rationale: A2A 使竞争者能够合作而不暴露内部信息。 A2A 也可以是"打电话给这个客户服务 agent"没有打电话的人知道如何 agent 提供这项服务。

<a id="timeline"></a>

### Timeline

- **2025-04-09.** 谷歌宣布 A2A.
- **2025-06-23.** 捐给Linux基金会
- **2025-08.** ABSIBM的ACP。 。 。
- **2025-09.** AP2 扩展(Agent 船舶。
- **2026-04.** v1.0 与150个以上支助组织发布。

<a id="relationship-to-mcp"></a>

### 与 MCP

| 尺寸 | MCP | A2A |
|-----------|-----|-----|
| 应用场景 | Agent-to-tool | Agent-以-agent |
| Opacity | Transparent tool calls | 内部不透明推理 |
| 典型的呼叫者 | Agent runtime | Another agent |
| 状态 | 工具调用结果 | 生命周期任务 |
| Authorization | OAuth 2.1 (第13阶段 · 16) | JWT-signed Agent 贺卡(AP2) |
| 交通 | 流/流 HTTP | JSON-RPC over HTTP /菲律宾妇女理事会 |

使用 MCP 使用 A2A 想要将整个任务委托给另一个任务时 agent许多生产系统使用两种方法: agent 使用 MCP 用于工具层和 A2A 来配合它

```figure
a2a-task-lifecycle
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 执行最小值 A2A harness:一项研究 agent 出版它的名片,作家 agent 收到a `tasks/send` 含有一个PDF和一个文本指令的部件,通过工作输入转换_需要 } 工作完成, 并返回文本工艺品。 所有标准lib; 使用一个模拟传输来聚焦于信件形状 。

需要关注的内容：

- Agent Card JSON shape.
- 任务编号和州级过渡。
- 含有混合型部件的信息。
- Input-required branch mid-task.
- 完成后, 人工返回 。

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-a2a-agent-spec.md`。如果有一个新的 agent 另一类人应可调用 agents,技能产生 Agent Card JSON技能计划,和终点蓝图。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`. Trace 任务整个生命周期,包括输入要求的暂停 agent 要求澄清

2. 添加签名 Agent 牌,和HMAC签在卡片的卡片上 JSON。在变异卡上写一个验证器并确认它失败。

3. 执行任务 streaming: 写作者 agent 发出三个递增的文物块 超过SSE 和打电话者积累它们。

4. 设计 A2A agent 环绕着 MCP 服务器。 MCP 工具到 A2A 注意权衡——什么不透明已经丧失?

5. 读 A2A v1.0 通知和识别 feature 2026年4月尚未执行的(提示:涉及多机会任务) delegation.)

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| A2A | "Agent-以-Agent protocol" | 打开不透明协议 agent collaboration |
| Agent Card | "`.well-known/agent.json`" | 发布元数据,说明 agent技能和终点 |
| Skill | "一个可调用单位" | 名为"行动"的 agent 支持( 对应到 MCP tool) |
| 任务 | " 单位 delegation" | 具有生命周期和最终工艺品的工作项目 |
| Message | "任务输入" | 部件(文本、文件、数据) |
| 部分 | "小块" | `text` / `file` / `data` 信件的元素 |
| Artifact | "任务输出" | 命名, 完成后返回已打印的产出 |
| AP2 | "Agent 付款协议" | Signed Agent 信托卡和付款的延长 |
| Opacity | "黑盒合作" | Called agent内部隐藏着来自打电话者的信息 |
| Input-required | 工作暂停 | 寿命周期状态 agent 需要更多信息 |

<a id="further-reading"></a>

## 进一步阅读

- [a2a-protocol.org](https://a2a-protocol.org/latest/) - 弹簧 A2A specification
- [a2aproject/A2A — GitHub](https://github.com/a2aproject/A2A) 参考执行情况和 SDKs
- [林努基金会 A2A 发射新闻稿](https://www.linuxfoundation.org/press/linux-foundation-launches-the-agent2agent-protocol-project-to-enable-secure-intelligent-communication-between-ai-agents) - 2025年6月施政移交
- [谷歌云 - 谷歌云 - A2A 协议升级](https://cloud.google.com/blog/products/ai-machine-learning/agent2agent-protocol-is-getting-an-upgrade) 路线图和伙伴势头
- [谷歌・德夫 A2A 1.0个里程碑](https://discuss.google.dev/t/the-a2a-1-0-milestone-ensuring-and-testing-backward-compatibility/352258) - v1.0 发布笔记和后向兼容指导
