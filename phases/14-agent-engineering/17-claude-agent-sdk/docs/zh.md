<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="the-harness-as-a-library--subagents-and-session-store"></a>

# 将 Harness 封装为库：Subagents 与会话存储

> 一个 harness 您可以导入:内置工具, subagents 上下文孤立、钩子、W3C trace 传播,会话的持久性。 Claude Agent SDK 是一个参考示例—— Claude Code harness — 和 Claude Managed Agents 是一个长期的非同步工作的替代选择。

**类型:** 学习 + 构建
**语言:** Python (stdlib)
**先修要求:** 阶段14 · 01 (Agent Loop阶段14 10(技能图书馆)
**时间:** ~75分钟

<a id="learning-objectives"></a>

## 学习目标

- 解释一下 Anthropic Client SDK (raw API) 以及该 Claude Agent SDK (harness shape).
- Describe subagents ——平行和孤立环境——以及何时为它们服务。
- 名称 Python SDK'会话存储表面 (D)`append`, `load`, `list_sessions`, `delete`, `list_subkeys`和作用 `--session-mirror`.
- 执行标准字 harness 以内置工具, subagent 产卵时带有孤立的环境、生命周期钩和一个会话商店。

<a id="the-problem"></a>

## 问题

生来 LLM API 让你一回跑,一出戏 agent 需要工具执行, MCP 服务器,生命周期钩, subagent 产卵,会分持久性, trace propagation. Claude Agent SDK 以库形形状的船舶 harness Claude 代码用途, 用于定制 agents.

<a id="the-concept"></a>

## 概念

<a id="client-sdk-vs-agent-sdk"></a>

### Client SDK 与 Agent SDK

- **Client SDK (`anthropic`).** 原始信件 API。你拥有循环,工具,国家。
- **Agent SDK (`claude-agent-sdk`).** 内建工具执行, MCP 连接,钩子, subagent 产卵,会话店 Claude 以库的形式代码循环 。

<a id="built-in-tools"></a>

### 内置工具

该 SDK 将 10 + 工具从框中调出: 文件读/写、 shell、 grep、 glob、 网络获取、 更多。 自定义工具通过标准工具- schema 界面注册 。

<a id="subagents"></a>

### Subagents

由以下两个目的所记载 Anthropic:

1. **Parallelization.** 同时运行独立工作。 “ 为这20个模块中的每一模块查找测试文件” 是 20 个平行 subagent tasks.
2. **与世隔绝。** Subagents 使用自己的 context window;只有结果返回管弦乐队。管弦乐队的预算被保留了。

Python SDK 最近增加的内容: `list_subagents()`, `get_subagent_messages()` 用于阅读 subagent transcripts.

<a id="session-store"></a>

### 会话存储

协议对等 TypeScript:

- `append(session_id, message)` - 加上一个转弯。
- `load(session_id)` - 恢复对话
- `list_sessions()` ——列举。
- `delete(session_id)` - 连锁车 subagent sessions.
- `list_subkeys(session_id)` - 清单 subagent keys.

`--session-mirror` 将笔录映射到流的外部文件,用于调试。

<a id="hooks"></a>

### Hooks

生命周期钩可以注册:

- `PreToolUse`, `PostToolUse` 门或审计 tool calls.
- `SessionStart`, `SessionEnd` - 设置和拆开。
- `UserPromptSubmit` 在模型看到之前,先按用户输入。
- `PreCompact` - 跑在背景压缩之前
- `Stop` - 清理 agent exit.
- `Notification` - 侧道警报

钩子是支持工作流程(第14阶段课程参考)和类似系统如何增加交叉行为。

<a id="w3c-trace-context"></a>

### W3C trace context

OTel 横跨在呼叫器上的活动,通过 W3C 传播到 CLI 子进程 trace 上下文标题。 trace 显示为一体 trace 放在后端上

<a id="claude-managed-agents"></a>

### Claude Managed Agents

托管的替代文件( 贝塔页眉) `managed-agents-2026-04-01`长期的非同步工作,内置 prompt 内装压缩,管理基础设施的贸易控制

<a id="where-this-pattern-goes-wrong"></a>

### 哪里有这种模式

- **Subagent over-spawn.** 体力活人 100 subagents 管理权占上风,而批发
- **钩子怪** 每个团队都添加钩子;启动时间气球。每季度审查钩子。
- **会话的浮肿。** 会话累积; 大小增长。 使用 `list_sessions` + 过期失效政策。

```figure
ae-subagent-isolation
```

<a id="build-it"></a>

## 动手实现

`code/main.py` 执行 SDK 形状,以标准lib :

- `Tool`, `ToolRegistry` 内置 `read_file`, `write_file`, `list_dir`.
- `Subagent` 私人环境, 孤立运行,结果返回。
- `SessionStore` - 附加、装入、列表、删除、列表_subkeys.
- `Hooks` — `pre_tool_use`, `post_tool_use`, `session_start`, `session_end`.
- 演示: 主 agent 产卵 3 subagents 平行(每个孤立),汇总结果,会议持续进行。

运行：

```
python3 code/main.py
```

该 trace shows subagent 环境隔离( 切换器上下文大小保持边框)、 钩执行和会话持久性。

<a id="use-it"></a>

## 实际应用

- **Claude Agent SDK** 用于 Claude- 第一批产品,想要 Claude Code harness shape.
- **Claude Managed Agents** 长期的收留工作
- **OpenAI Agents SDK** (第16段) OpenAI- 头等兵
- **LangGraph + 自定义工具** 如果您想要图形形状态机器, 则要换成 。

<a id="ship-it"></a>

## 交付成果

`outputs/skill-claude-agent-scaffold.md` 脚架a Claude Agent SDK 应用程序 subagents钩子,会话店, MCP 服务器附件, 和 W3C trace propagation.

<a id="exercises"></a>

## 练习

1. 添加a subagent 将20项任务分解成5组的产卵器 subagents。测量管弦风的上下文大小与每个任务大小。
2. 执行a `PreToolUse` 勾勾那个比率限制 `write_file` 电话(每场会议5分钟)。 Trace 行为。
3. Wire `list_subkeys` 提供 subagent 树,深巢是什么样子的?
4. 将玩具移到真实的 `claude-agent-sdk` Python 软件包。工具注册的修改是什么?
5. 读 Claude Managed Agents 医生,你什么时候才能从自托管转成管理?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| Agent SDK | "Claude 代码为库 | Harness 形状:工具, MCP钩子 subagents,会话存储 |
| Subagent | "Child agent" | 独立背景, 自己的预算; 结果泡沫化 |
| 会话存储 | "DB定罪" | 永久、装入、列表、删除旋转 subagent cascade |
| Hook | "生命周期回响" | 预发工具、会话、 prompt 提交、压缩、停止 |
| W3C trace context | "Cross-process trace" | 父宽度向 CLI 子进程传播 |
| Managed Agents | "Hosted harness" | Anthropic- 主持长期的散工 |
| `--session-mirror` | 画像镜 | 写入会话时, 当文件流出时, 将其转向外部文件 |
| MCP server | "工具表面" | 附属于《公约》的外部工具/资源来源 agent |

<a id="further-reading"></a>

## 进一步阅读

- [Claude Agent SDK overview](https://platform.claude.com/docs/en/agent-sdk/overview) 图书馆形式 Claude Code
- [Anthropic大楼 agents 与 Claude Agent SDK](https://www.anthropic.com/engineering/building-agents-with-the-claude-agent-sdk) 生产模式
- [Claude Managed Agents overview](https://platform.claude.com/docs/en/managed-agents/overview) - 替代接待
- [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/) 对应方
