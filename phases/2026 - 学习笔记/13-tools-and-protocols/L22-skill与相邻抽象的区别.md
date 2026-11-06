---
phase: 13
phase_dir: 13-tools-and-protocols
phase_title: 工具和协议
lesson: 22
lesson_dir: 22-skills-and-agent-sdks
lesson_title: Agent Skills：可移植契约与运行时边界
section: 概念 › 相邻的抽象
section_en: The Concept › The neighboring abstractions
date: 2026-10-12
tags: [agent-skill, SKILL.md, prompt, CLAUDE.md, repository-instructions, mcp, hook, subagent, plugin, skill-library, voyager]
related: [13/06-mcp-fundamentals, 13/24-skill-discovery-and-progressive-disclosure, 13/26-skill-permissions-sandboxes-and-trust, 14/10-skill-libraries-voyager]
---

# Agent skill 与相邻抽象（Prompt、仓库指令、MCP、Hook、Subagent、Plugin、习得技能库）的区别

## 📍 提问位置

| 层级 | 位置 |
|---|---|
| 阶段 | 第 13 阶段「工具和协议」（`13-tools-and-protocols`） |
| 课程 | 第 22 课「Agent Skills：可移植契约与运行时边界」（`22-skills-and-agent-sdks`） |
| 章节 | 「概念」›「相邻的抽象」 |
| 原文 | [zh.md 第 229 行](../../13-tools-and-protocols/22-skills-and-agent-sdks/docs/zh.md#the-neighboring-abstractions) · [en.md 第 201 行](../../13-tools-and-protocols/22-skills-and-agent-sdks/docs/en.md#the-neighboring-abstractions) |
| 后续课程 | 本课「技能和工具正交」「技能与仓库指令是不同范围」两小节 · [第 26 课 Skill 权限、沙箱与信任](../../13-tools-and-protocols/26-skill-permissions-sandboxes-and-trust/docs/zh.md) · [第 14 阶段第 10 课 技能库（Voyager）](../../14-agent-engineering/10-skill-libraries-voyager/docs/zh.md) |

原文摘录（en.md，中文版机器翻译错误较多，见文末更正）：

> | Artifact | Primary job | Loaded or run when | What it should not impersonate |
> |---|---|---|---|
> | Prompt | Shape one model interaction | Included by an application or user | A versioned package with resources |
> | Repository instructions | Explain one codebase's standing rules | A coding runtime enters that scope | A reusable task workflow |
> | Agent skill | Supply reusable procedural knowledge | Explicit or implicit activation | A hard authorization boundary |
> | MCP tool | Expose a typed remote capability | The model or application calls it | A detailed operating procedure |
> | Hook | Run deterministic logic on an event | The declared event occurs | Probabilistic model routing |
> | Subagent | Delegate work with separate context and state | An orchestrator creates or calls it | A static instruction bundle |
> | Plugin | Distribute a larger runtime extension | The host installs or enables it | The portable skill contract itself |
> | Learned skill library | Store behavior discovered through experience | A policy retrieves a prior program or trajectory | A standards-based `SKILL.md` package |
>
> A release skill can tell the agent how to inspect a release. An MCP server can expose the release registry. A hook can forbid direct pushes. A subagent can independently audit the candidate. These pieces compose because they keep different responsibilities.

---

## Q1：表里这些概念到底有什么不同？

### 一句话

八种构件都是"给 agent 加东西"，区别在于**职责**和**触发方式**：要保证某件事发生或不发生用 hook，要能力用 MCP，要流程用 skill，要隔离上下文用 subagent，要分发用 plugin，项目背景写仓库指令，一次性要求写 prompt。

### 四列各在问什么

- **主要职责**：它解决哪一类问题。
- **何时加载或运行**：谁触发它、什么时候进入系统。这一列最能把相似的概念分开。
- **不该冒充成什么**：最常见的误用，也就是拿它去做本该由别的构件做的事。

### 中文还原表

| 构件 | 主要职责 | 何时加载或运行 | 不该冒充成什么 |
|---|---|---|---|
| Prompt | 塑造**一次**模型交互 | 由应用或用户放进上下文 | 带资源、有版本的包 |
| 仓库指令 | 说明一个代码库的**长期规则** | 编码 agent 进入这个目录范围时 | 可复用的任务流程 |
| Agent skill | 提供可复用的**操作知识** | 显式调用，或模型判断相关后隐式激活 | 硬性权限边界 |
| MCP tool | 暴露有类型定义（typed）的远程**能力** | 模型或应用调用它时 | 详细的操作手册 |
| Hook | 在事件上运行**确定性**逻辑 | 声明的事件发生时 | 概率性的模型路由 |
| Subagent | 委派工作，有**独立的上下文和状态** | 编排者（orchestrator）创建或调用它时 | 一组静态指令 |
| Plugin | 分发更大的运行时扩展 | 宿主程序安装或启用时 | 可移植的 skill 规范本身 |
| 习得技能库 | 存储从经验中**学到**的行为 | 策略检索以前的程序或轨迹时 | 标准的 `SKILL.md` 包 |

### 逐个解释（以 Claude Code 为例）

**1. Prompt：一次性的**
- 这一轮发给模型的话，或应用拼进去的 system prompt，用完就没了。
- 不该冒充可复用的包：如果每次都在复制粘贴同一大段 prompt，它就该升级成 skill。原文「问题」一节说，把发布流程塞进一个 prompt "易于粘贴、难以运维"：没有稳定身份、没有发现规则、没有资源边界，也说不清谁能调用、何时被选中。

**2. 仓库指令：这个仓库的常驻规则**
- 如 `CLAUDE.md`、`AGENTS.md`：用什么包管理器、测试命令、不要改 generated 目录。
- 进入目录就自动加载，**范围由位置决定**，与任务无关。
- 不该冒充任务流程：把 30 步发布流程写进 `CLAUDE.md`，每次会话都占上下文，哪怕只是修一个错别字。

**3. Agent skill：按需加载的"怎么做"**
- 一个以 `SKILL.md` 为入口的目录（YAML frontmatter + Markdown 指令，可带 references、scripts、assets）。可部署单元是整个目录，不只是那个 Markdown 文件。
- 平时只在目录（catalog）里露出 `name` 和 `description`，被选中时才加载全文。这是它与仓库指令最大的区别。
- 不该冒充**硬性权限边界**：skill 是给模型读的文字，模型可能理解错、跳过，或被 prompt 注入绕过。"发布前必须跑测试"写在 skill 里只是建议。原文生命周期一节也强调：激活了的 skill 并不因此获得它描述的一切权限，真正的执行受宿主的权限与隔离规则约束。

**4. MCP tool：能被调用的能力**
- 通过 MCP 暴露的函数，输入输出有 JSON Schema（即 "typed"）。
- 不该冒充操作手册：工具描述说清"做什么、参数是什么"即可，"先查 A 再查 B、遇到 C 就……"属于 skill。
- **skill 是知识（知道怎么做），MCP tool 是手（能做到）**。原文：MCP 回答"这个应用能调用哪些能力、schema 是什么"，skill 回答"agent 应该怎样处理这一类任务"。skill 可以提到某个工具，但工具注册表归宿主所有；工具不存在时，skill 应写明退路或明确失败，提到一个能力不等于创造了它。

**5. Hook：确定性的守门员**
- 在固定事件上执行的脚本，如 Claude Code 的 `PreToolUse`、`PostToolUse`、`Stop`，配置在 `settings.json`。
- 事件一发生就**一定**执行，执行者是 harness，不是模型。
- 不该冒充概率性的模型路由：hook 里应是条件判断、正则、退出码，而不是"让模型判断一下合不合适"。
- 要**保证**用 hook，要**建议**用 skill。

**6. Subagent：另一个独立干活的 agent**
- 主 agent 派出去的子 agent，有自己的上下文窗口、工具集和状态，干完只把结论交回。
- 不该冒充静态指令：只想给主 agent 补一段知识，用 skill 就够了。subagent 的价值在于**隔离**：上下文干净、不被主线思路带偏、可并行、适合独立审查。

**7. Plugin：打包和分发的容器**
- 一个可安装的扩展包，可同时包含 skills、hooks、MCP server、subagent 定义、斜杠命令。
- 不该冒充可移植的 skill 规范：`SKILL.md` 是开放格式，可在兼容的宿主之间迁移；plugin 是某个宿主的分发机制。原文「运行时扩展是第二层」一节同理：`disable-model-invocation`、`context`、`hooks` 等宿主专属 frontmatter 字段都不属于可移植核心，应当作适配器对待。

**8. 习得技能库：从经验里长出来的技能**
- 研究系统里的概念，如 Voyager 在 Minecraft 中把成功的代码存成技能库。agent 在探索中生成、按任务相似度检索、执行、根据反馈修订。
- 不该冒充 `SKILL.md` 包：两者都叫 "skill"，但一个是机器积累、通常绑定特定环境和动作空间，一个是人编写或审核、有声明的文件系统契约、可跨宿主迁移。原文「skill 这个词指两种不同的东西」一节的对照：

| 维度 | Agent Skill 包 | 习得技能库 |
|---|---|---|
| 基本单元 | `SKILL.md` 目录 | 程序、策略、轨迹或记忆记录 |
| 如何产生 | 人写、生成或整理 | 通常从环境经验中发现 |
| 如何选中 | 目录描述 + 运行时策略 | 按任务状态检索或由策略选择 |
| 如何执行 | 模型按指令调用宿主工具 | 环境直接运行存下来的行为或代码 |
| 可移植性 | 契约可跨兼容宿主 | 往往绑定一个环境 |
| 如何评测 | 路由、产出、安全、宿主兼容性 | 奖励、成功率、迁移、库的增长 |

### 最容易混淆的几组

| 对比 | 区分要点 |
|---|---|
| Prompt vs 仓库指令 vs Skill | 作用范围：一次交互 / 一个目录 / 一类任务 |
| Skill vs MCP tool | 知识 vs 能力 |
| Skill vs Hook | 软约束（模型可能不遵守）vs 硬约束（harness 一定执行） |
| Skill vs Subagent | 往**当前**上下文加知识 vs 开一个**新**上下文去执行 |
| Plugin vs Skill | 分发容器 vs 内容规范 |
| 习得技能库 vs `SKILL.md` | 机器积累、绑定环境 vs 人工编写、可审查、可迁移 |

### 例子：用"发布"串起来（展开原文最后一段）

1. **`CLAUDE.md`**："本仓库用 semver，CHANGELOG 在根目录。"常驻背景。
2. **release skill**："检查 CHANGELOG → 确认版本号 → 跑测试 → 打 tag……"按需加载的流程。
3. **MCP tool**：`get_release_registry()` 查已发布版本，避免版本号冲突。能力。
4. **Hook**：`PreToolUse` 检测到直接 push 到 main 就拒绝。不管模型怎么想都推不上去，这是保证。
5. **Subagent**：派一个独立 reviewer 用干净上下文审查候选版本，不受主 agent 思路影响。
6. **Plugin**：把 2 到 5 打成 `release-kit`，团队一键安装。

每个构件只做自己能可靠做到的事。全写进 skill，"禁止直接 push"只是一句可能被忽略的建议；全写进 hook，又没法表达需要判断的流程。

两者同时生效时的优先级（原文「技能与仓库指令是不同范围」）：当前用户请求和仓库规则约束 skill。通用的重构 skill 不能覆盖"禁止编辑生成文件"这样的仓库规则。

### ⚠️ 原文需要更正的地方

中文版 zh.md 这一节是机器翻译，多处译错，以 en.md 为准：

| zh.md 译文 | 英文原文 | 正确意思 |
|---|---|---|
| 初级工作 | Primary job | 主要职责 |
| 装入或运行时 | Loaded or run when | 何时加载或运行 |
| 形状一型互动 | Shape one model interaction | 塑造一次模型交互 |
| 配有资源的版本套件 | A versioned package with resources | 带资源、有版本的包 |
| 编码运行时间进入此范围 | A coding runtime enters that scope | 编码 agent 进入该范围时 |
| 明示或默示激活 | Explicit or implicit activation | 显式或隐式激活 |
| 硬授权边界 | A hard authorization boundary | 硬性权限边界 |
| 显示已打印的远程能力 | Expose a typed remote capability | 暴露有类型定义的远程能力 |
| 模型或应用程序称之为 | The model or application calls it | 模型或应用调用它时 |
| 运行事件确定逻辑 | Run deterministic logic on an event | 在事件上运行确定性逻辑 |
| 概率模型路径 | Probabilistic model routing | 概率性的模型路由 |
| 代表工作,背景和状况各异 | Delegate work with separate context and state | 委派工作，有独立的上下文和状态 |
| 管弦乐队创造或称它为 | An orchestrator creates or calls it | 编排者创建或调用它时 |
| 分配更大的运行时间扩展 | Distribute a larger runtime extension | 分发更大的运行时扩展 |
| 便携式技术合同本身 | The portable skill contract itself | 可移植的 skill 规范本身 |
| 策略回收先前的程序或轨迹 | A policy retrieves a prior program or trajectory | 策略检索以前的程序或轨迹 |
| 解脱技巧可以告诉 agent 如何检查释放 | A release skill can tell the agent how to inspect a release | 发布 skill 能告诉 agent 如何检查一次发布 |
| MCP 服务器可以显示发布注册 | An MCP server can expose the release registry | MCP server 能暴露发布记录库 |
| 勾可禁止直接推动 | A hook can forbid direct pushes | hook 能禁止直接 push |
| subagent 独立审核候选人 | A subagent can independently audit the candidate | subagent 能独立审查候选版本 |
| 这些作品是因为他们承担不同的责任 | These pieces compose because they keep different responsibilities | 这些构件能组合，是因为各自承担不同职责 |

---

## 🔁 复习自测

1. Prompt、仓库指令、skill 三者的作用范围分别是什么？
2. 为什么 skill 不能当作硬性权限边界？"发布前必须跑测试"应该放在哪里才能保证？
3. 用一句话区分 skill 和 MCP tool。skill 提到的工具在宿主里不存在时，skill 应该怎么写？
4. Hook "不该冒充概率性的模型路由"是什么意思？
5. 什么时候该用 subagent 而不是 skill？
6. Plugin 和 `SKILL.md` 规范是什么关系？`disable-model-invocation` 属于可移植核心吗？
7. 习得技能库和 Agent Skill 包在产生方式、执行方式、可移植性上有什么不同？
8. 通用 skill 与仓库规则冲突时谁优先？
9. 用发布流程举例，说明各构件如何分工。

<details>
<summary>参考答案要点</summary>

1. 一次交互；进入某个目录就生效的长期规则；一类任务的可复用流程，按需加载。
2. skill 是给模型读的文字，可能被误解、跳过或被注入绕过；真正的执行受宿主权限与隔离约束。要保证就用 hook（如 `PreToolUse` 拦截）或 CI。
3. skill 是"怎么做"的知识，MCP tool 是"能做到"的能力。工具不存在时写明退路或明确失败，不能暗示提到它就等于有它。
4. hook 里应该是确定的条件判断，事件发生就一定执行，不应把"让模型判断"放进去。
5. 需要隔离时：干净的上下文、不被主线带偏、并行、独立审查。只是补充知识用 skill。
6. plugin 是宿主的分发容器，可装 skill、hook、MCP、subagent 等；`SKILL.md` 是可跨宿主的规范。`disable-model-invocation` 是宿主扩展字段，不属于可移植核心。
7. 习得库：从环境经验中发现，环境直接运行存下来的行为或代码，通常绑定一个环境。Skill 包：人写或整理，模型按指令调用宿主工具，契约可跨兼容宿主。
8. 当前用户请求和仓库规则约束 skill，skill 不能覆盖仓库规则。
9. `CLAUDE.md` 给常驻背景，release skill 给流程，MCP 暴露发布记录库，hook 禁止直接 push，subagent 独立审查，plugin 打包分发。

</details>
