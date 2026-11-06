<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="capstone-01--terminal-native-coding-agent"></a>

# 综合项目 01：终端原生 Coding Agent

> 2026年时,一个 coding agent 已经解决。 harness,一个有规律的计划,一个沙箱工具表面, 一个计划、行动、观察、恢复的循环。 Claude 代码, 曲线3 和 OpenCode 从50英尺处看起来都一样。 这个墓碑要求你建一个终点—— CLI in, pull request 出来,用迷你丝巾来衡量agent 和生活-SWE - - -agent 来了解为什么硬部分不是模型调用 而是工具循环 sandbox和成本上限 在50转运行。

**类型:** Capstone
**语言:** TypeScript / Bun (harness), Python (eval脚本)
**先修要求:** 第11阶段(LLM 工程,第13阶段(工具和协议),第14阶段(agents15阶段(自治系统),17阶段(基础设施)
**实施阶段:** P0 ; P5 ; P7 ; P10 ; P11 ; P13 ; P14 ; P15 ; P17 ; P18 ;
**时间:** 35小时

<a id="problem"></a>

## 问题

Coding agents 2026年,该类产品成为主要的AI应用类别。 Claude 代码(Anthropic),有2和2的曲目3 Agent 标签(Cursor)、安普(资料来源)、开放代码(112k星)、工厂机器人和谷歌朱尔斯 同一结构的所有船舶变换:终端 harness,一个允许的工具表面,a sandbox以及一个围绕边界模型的计划-行动-观察环。agent 使用Opus 4.5验证SWE-bench 达到79.2%,但工程飞行器宽度很大。大多数故障模式不是模型错误。它们是工具环绕不稳定、环境中毒、离家出走 token 成本,和破坏性的文件系统操作。

这种事你根本说不通 agents 外观。 您必须建立一个, 当回转47时, 当回转8MB 返回匹配时, 注意环状崩溃, 重建短程层。 这是这个综合项目 。

<a id="concept"></a>

## 概念

该 harness 4个表面。 **Plan** 保持一个待办文件样式的状态对象, 模型每转转一次重写 。 **Act** dispatches tool calls (阅读、编辑、运行、搜索, git). **Observe** 捕捉 stdout / stderr / 退出代码, 截断, 并反馈摘要 。 **Recover** 处理工具错误而不吹 context window 或永远循环。2026年的形状增加了一件事: **hooks**. `PreToolUse`, `PostToolUse`, `SessionStart`, `SessionEnd`, `UserPromptSubmit`, `Notification`, `Stop`, 和 `PreCompact` 操作员在可配置的扩展点中注射政策、遥测和 guardrails.

该 sandbox 是一个新的Devcontainer, git worktree 已挂载的读写。 harness 永远不要触动主机文件系统。 worktree 成功或失败时被撕碎。成本控制在三个层次:一次转 token 上限、每届大会美元预算以及硬转弯限制(通常为50)。 observability 与GenAI语义学协议的开放遥测范围, 运到自办的兰富斯。

<a id="architecture"></a>

## 建筑

```
  user CLI  ->  harness (Bun + Ink TUI)
                  |
                  v
           plan / act / observe loop  <--->  Claude Sonnet 4.7 / GPT-5.4-Codex / Gemini 3 Pro
                  |                          (via OpenRouter, model-agnostic)
                  v
           tool dispatcher (MCP StreamableHTTP client)
                  |
     +------------+------------+----------+
     v            v            v          v
  read/edit    ripgrep     tree-sitter   git/run
     |            |            |          |
     +------------+------------+----------+
                  |
                  v
           E2B / Daytona sandbox  (worktree isolated)
                  |
                  v
           hooks: Pre/Post, Session, Prompt, Compact
                  |
                  v
           OpenTelemetry -> Langfuse (spans, tokens, $)
                  |
                  v
           PR via GitHub app
```

<a id="stack"></a>

## 堆栈

- Harness 运行时间: Bun 1.2 + Ink 5 (React-in-terminal)
- 模型访问: 打开 Router 统一 API 与 Claude 索内特4.7, GPT-5.4-Codex, Gemini 3 Pro, Opus 4.5(最难的任务)
- 工具传输 : Model Context Protocol 可流HTTP( 移动 HTTP) (% 1)MCP 2026年订正)
- Sandbox: E2B : 电子数据 sandboxes (JS SDK或代顿纳河河河畔的河畔
- 代码搜索: riggrep 子进程, 17种语言的树喷射器( 预编译)
- Isolation: `git worktree add` 每个任务, 成功/ 失败的清理
- Eval harness:SWE-bench Pro(已核实子集)+终端-Bench 2. 0+你自己30项任务
- Observability: 开放遥测 SDK 与 `gen_ai.*` 兰福斯自营的
- 公关张贴 : GitHub 添加精细加分 token,范围限于目标回收

```figure
ce-agent-loop
```

<a id="build-it"></a>

## 动手实现

1. **电路和指令循环** 纸巾纸上写着一个带墨水的包子项目。 接受 `agent run <repo> "<task>"`打印一个分割视图:计划窗格(顶部)、工具呼叫流(中) token budget (下方) 添加在 Ctrl- C 上发生火灾的取消 `SessionEnd` 离开前钩钩。

2. **计划状态** 定义已输入的 TodoWrite 计划( 待办 / in)_/ 带有注释的完成项目) 模式重写每个转弯的完整状态 tool call -别让它变异 坚持计划 `.agent/state.json` 以便碰撞可以恢复。

3. **工具接口。**定义六个工具：`read_file`、`edit_file`（提供 diff 预览）、`ripgrep`、`tree_sitter_symbols`、`run_shell`（设有超时限制）、`git`（status / diff / commit / push）。通过 MCP StreamableHTTP 暴露这些工具，使 harness 不依赖特定传输方式。每个工具都返回经过截断的输出，每次调用的上限为 4k tokens。

4. **Sandbox wrapping.** 每个任务产生E2B sandbox. `git worktree add -b agent/$TASK_ID` 新鲜的 branch. 所有 tool calls 执行在 sandbox。主机文件系统无法访问 。

5. **Hooks.** 执行所有8个 2026 钩型。 电线至少4个用户使用的钩:(a) `PreToolUse` 破坏性指挥 守卫那些街区 `rm -rf` 外边 worktree,(b)项 `PostToolUse` token 会计,(c) `SessionStart` 预算启动情况,(d) `Stop` 写下决赛 trace bundle.

6. **电动循环** 克隆SWE-Bench方案30个问题子集 Python运行 harness 和迷你丝丝相比agent 传球时( 最小基线) @ 1, 翻转每个任务, 和 $- per- task 。 写入结果到 `eval/results.jsonl`.

7. **成本控制。** 硬截断: 50个转折, 200k 上下文, 每任务5美元。 `PreCompact` 勾勾总结旧的 变成一个前州区块 在150k马克, 腾出房间 新的观察 而不失去计划。

8. **公关发布** 成功的最后一步是 `git push` + a 组合键 GitHub API 电话打开公关 计划与diff摘要在身体。

<a id="use-it"></a>

## 实际应用

```
$ agent run ./my-repo "Fix the race condition in worker.rs"
[plan]  1 locate worker.rs and enumerate mutex uses
        2 identify shared state under contention
        3 propose fix, verify tests
[tool]  ripgrep mutex.*lock -t rust           (44 matches, truncated)
[tool]  read_file src/worker.rs 120..180
[tool]  edit_file src/worker.rs (+8 -3)
[tool]  run_shell cargo test worker::          (passed)
[plan]  1 done · 2 done · 3 done
[done]  PR opened: #482   turns=9   tokens=38k   cost=$0.41
```

<a id="ship-it"></a>

## 交付成果

交付能力存在于 `outputs/skill-terminal-coding-agent.md`。如果有一个回购路径和一个任务描述,它会在 sandbox 返回 PR URL + a trace 捆绑。 这个综合项目的标记 :

| Weight | 标准 | 如何衡量 |
|:-:|---|---|
| 25 | SWE-bench Pro pass@ 1 与基线 | 你的 harness 和迷你 -斯威...agent 30对 Python tasks |
| 20 | 结构清晰度 | 计划/行动/观测分离、钩子表面、工具图案——对照实况-SWE-agent layout |
| 20 | 安全 | Sandbox 越狱测试,许可 prompts,破坏力指挥警卫通过红色小队 |
| 20 | Observability | Trace 完整性(100%) tool calls spanned), token 每一转折的会计核算 |
| 15 | 开发者 UX | 冷启动 < 2s, 崩溃恢复计划, Ctrl- C 清除中间工具 |
| **100** | | |

<a id="exercises"></a>

## 练习

1. 交换支持模型 Claude 索内特4.7至Quen3-Coder-30B供职 vLLM。比较 pass@ 1 和 $- per- task。 报告打开模式表现不佳的地方。

2. 添加a `reviewer` sub-agent 并可以要求修改循环。 测量假阳性审查是否将SWE-bench的通过率降至单位以下agent 基准(内含:通常为)

3. 压力测试 sandbox: 写入一项尝试的任务 `curl` 外部 URL 和在 worktree。确认这两个都被预工具钩封住。

4. Implement `PreCompact` 以较小模型(Haiku 4.5)进行总结。测量3x压缩时计划忠诚度损失多少。

5. Swap MCP 流式HTTP 传输用于标准调试。 基准冷启动和按部就班的延迟。 选择一个赢家只供本地使用 。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|------------------------|
| Harness | "该 agent loop" | 围绕模型的代码,它发送工具、维持计划状态和执行预算 |
| Hook | "Agent 事件听众 | 由用户撰写的脚本运行于八次生命周期事件之一 harness |
| Worktree | "Git sandbox" | 链接 git 在一条单独的路径中取出; 一次性, 不触动主克隆 |
| TodoWrite | "计划状态" | 模型每转一个转折的待处理/在建/完成的项目打印列表 |
| StreamableHTTP | "MCP transport" | 2026 MCP 修改:长寿命 HTTP 双向连接 streaming; 替换 SSE |
| Token ceiling | 预算 | 投入+产出的每轮或每届会议上限 tokens; 触发压缩或终止 |
| pass@1 | 单试率 | SWE-bench 任务分数在第一次运行时解开, 不重试或测试式偷看 |

<a id="further-reading"></a>

## 进一步阅读

- [Claude 代码文件](https://docs.anthropic.com/en/docs/claude-code) 参考 harness 来自 Anthropic
- [光标 3 更改](https://cursor.com/changelog) — Agent 标签和撰写器 2 产品注释
- [mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent) 水环卫网最低限度基线 harness comparison
- [Live-SWE-agent](https://github.com/OpenAutoCoder/live-swe-agent) - 79.2% SWE-Bench 以4.5号作业进行验证
- [OpenCode](https://opencode.ai) - 打开 harness112k 恒星
- [SWE - Bench 方案领导板](https://www.swebench.com) — 该 evaluation 综合项目目标
- [Model Context Protocol 2026年路线图](https://blog.modelcontextprotocol.io/posts/2026-mcp-roadmap/) - 流动HTTP,能力元数据
- [GenAI语义学公约](https://opentelemetry.io/docs/specs/semconv/gen-ai/) 横跨 tool calls 和 token usage
