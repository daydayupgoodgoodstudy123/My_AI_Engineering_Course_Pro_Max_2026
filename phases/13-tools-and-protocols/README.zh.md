<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="phase-13-tools--protocols"></a>

# 第13阶段:工具和协议

> AI和现实世界之间的接口

此阶段从函数调用和工具图向可互操作性移动
protocols, Agent Skills安全,生产管理。
用于浏览。 下面的焦点路径是可靠的学习顺序 。

<a id="start-this-phase-on-github"></a>

## 开始此阶段 GitHub

**先修要求:** 第11阶段 LLM completion APIs. 用于 MCP 或 Agent Skills, 使用
而不是假设数字课顺序。

**第一阶段课:** [工具界面](01-the-tool-interface/docs/zh.md)

从存储库根目录运行此命令：

```bash
python3 phases/13-tools-and-protocols/01-the-tool-interface/code/main.py
```

保留命令、退出代码、描述决定执行观察 trace,被否决
输入证据, 并有一个句子解释转弯限制 。

**下一步行动:** 继续 [Function Calling 深潜](02-function-calling-deep-dive/docs/zh.md),
选择 Model Context Protocol (MCP) 或 Agent Skills 下方路线

浏览 [整个第13阶段课程列表](../../README.md#phase-13) 或该
[跨阶段路线图](../../ROADMAP.md).

<a id="model-context-protocol-mcp-path"></a>

## Model Context Protocol (MCP路径

重点 MCP 路线是17课,大约23小时15分钟
MCP `2026-07-28` 由自定义 JSON-RPC 请求
齐步登场

| 舞台 | 教训 | 你证明什么? | 时间 |
|---|---|---|---:|
| Core | [06](06-mcp-fundamentals/docs/zh.md), [07](07-building-an-mcp-server/docs/zh.md), [08](08-building-an-mcp-client/docs/zh.md), [09](09-mcp-transports/docs/zh.md), [10](10-mcp-resources-and-prompts/docs/zh.md) | 信封、发现、客户和服务器行为、运输、资源以及 prompts. | 5小时50分钟 |
| 双向 | [11](11-mcp-sampling/docs/zh.md), [12](12-mcp-roots-and-elicitation/docs/zh.md), [13](13-mcp-async-tasks/docs/zh.md), [14](14-mcp-apps/docs/zh.md) | MRTR 输入、明确范围、耐久任务以及没有服务器启动的请求的应用程序边界。 | 5小时 |
| Secure | [15](15-mcp-security-tool-poisoning/docs/zh.md), [16](16-mcp-security-oauth-2-1/docs/zh.md), [18](18-mcp-auth-production/docs/zh.md), [17](17-mcp-gateways-and-registries/docs/zh.md) | 毒物防控、授权、生产 tokens、网关路径和注册登记 | 5小时15分钟 |
| Advanced | [28](28-mcp-tool-contracts-and-content/docs/zh.md), [29](29-mcp-reliability-cancellation-and-flow-control/docs/zh.md), [30](30-mcp-registry-supply-chain-and-drift/docs/zh.md), [31](31-mcp-conformance-versioning-and-operations/docs/zh.md) | 合同忠诚,取消竞争,供应链漂移,以及释放证据。 | 7小时10分钟 |

确切的顺序是06,07,08,09,10,11,12,13,14,15,16,18,17,28,
29,30,31. 定义如下:
[`learning-paths/model-context-protocol.json`](../../learning-paths/model-context-protocol.json).
导师创建 `MCP-LEARNING.md`,教一个课
调用,记录请求、回应、命令、工作目录、退出
代码,以及每个文件要求的经过编辑的边界证据 checkpoint.

以主机支持的引用开始 :

| 宿主 | Invocation |
|---|---|
| Codex | `learn-mcp`,或选择它 `/skills` |
| Claude Code | `/learn-mcp` |
| 其他兼容的主机 | `Use learn-mcp to start or resume the Model Context Protocol (MCP) path.` |

<a id="your-first-ten-minutes"></a>

### 你的第一个十分钟

由仓库根,运行06课的无国籍记录:

```bash
python3 phases/13-tools-and-protocols/06-mcp-fundamentals/code/main.py
```

在输出中查找四件事:重复请求元数据, 完整
`server/discover` 结果, 错误 `-32022` 用于不支持版本,
无法创建或终止 MCP 礼宾会议。
笔录是第一个 checkpoint不只是个演示

存储库或 Python 3号没有, 读取 [课程06](06-mcp-fundamentals/docs/zh.md)
手又紧trace 一项请求和回应。 checkpoint 概念和定义
等待批准,等待批准和部署证据。

完成课程 15 可执行的安全性 checkpoint 在任何非环背之前
约束、共享入侵、主机端点或登记册出版物。
外部目标和请求授权,然后确认部署行动
明确无误。已完成的辅导并不授予部署权。

Older `initialize`, `Mcp-Session-Id`独立 SSE `GET`,会议 `DELETE`,
服务器驱动的请求流只出现在明确的兼容性说明中。
现代请求书中声明协议版本和客户能力
`params._meta`, 使用 `server/discover`,并携带足够的信息
独立地进行验证、授权、改道和重新审判。

[课程23](23-capstone-tool-ecosystem/docs/zh.md) 是唯一可选的 MCP route
完成17项必修课程 [课程19](19-a2a-protocol/docs/zh.md)
和 [课程20](20-opentelemetry-genai/docs/zh.md) 开始之前

<a id="agent-skills-fast-path"></a>

## Agent Skills 快速路径

重点路线是5课,大约9小时30分钟:

| 步骤 | 课程 | Outcome | 时间 |
|---:|---|---|---:|
| 1 | [22: 便携式合同和运行时间边界](22-skills-and-agent-sdks/docs/zh.md) | 创建、安装、引用、验证和删除完整 skill bundle. | 90分钟 |
| 2 | [24:发现和 Progressive Disclosure](24-skill-discovery-and-progressive-disclosure/docs/zh.md) | Trace 发现,编目,激活和资源装载。 | 105分钟 |
| 3 | [25: 援引和运行](25-skill-invocation-and-routing/docs/zh.md) | 控制直线、隐含、人性、型号和弃权路径。 | 105分钟 |
| 4 | [26: 许可, Sandboxes,并信任](26-skill-permissions-sandboxes-and-trust/docs/zh.md) | 分别指示、许可、限制和核查。 | 120分钟 |
| 5 | [27: 倾斜、包装和移动](27-skill-evals-packaging-and-portability/docs/zh.md) | 搭起一个释放门 证明真正的主机的行为 | 150分钟 |

以主机支持的引用开始 :

| 宿主 | Invocation |
|---|---|
| Codex | `learn-agent-skills`,或选择它 `/skills` |
| Claude Code | `/learn-agent-skills` |
| 其他兼容的主机 | `Use learn-agent-skills to start or resume the Agent Skills Engineering path.` |

导师创建或恢复 `AGENT-SKILLS-LEARNING.md`,教一个课
并记录每一缔约国所要求的证据。 checkpoint。路径是
定义在
[`learning-paths/agent-skills.json`](../../learning-paths/agent-skills.json).

如果你喜欢先读,从 [课程22](22-skills-and-agent-sdks/docs/zh.md).
10分钟后,它的第一个实验室 就能进入真正的宿主的行列

<a id="prerequisite-fast-lane"></a>

### 最需要的快车道

- 真正的实验室,你需要 `node`, `npx`, `python3`,一个选中
  具有技能的主机, 并写入所选项目或用户技能的读取
  范围。 `node --version`, `npx --version`, 和
  `python3 --version` 安装前。
- 如果无法使用前飞行,请使用网站或阅读 `docs/en.md`
  手动完成,你可以完成概念工作,但继续发现
  正在等待使用、脚本、更新和卸载证据。
- Skim [课程一](01-the-tool-interface/docs/zh.md) 和 [05课](05-tool-schema-design/docs/zh.md)
  如果 tool contracts 对你来说是新来的
- 26课前,确认您可以解释工具中毒和不信任
  instructions. [课程15](15-mcp-security-tool-poisoning/docs/zh.md) 是可选的
  飞行前的更新,不需要第六课
- [课程23](23-capstone-tool-ecosystem/docs/zh.md) 是一个可选的系统综合项目,
  不是下一个 Agent Skills 22课后课程 06至20课
  之前,采取它。

<a id="full-phase"></a>

## 整个阶段

See [ROADMAP.md](../../ROADMAP.md) 整个课程计划
