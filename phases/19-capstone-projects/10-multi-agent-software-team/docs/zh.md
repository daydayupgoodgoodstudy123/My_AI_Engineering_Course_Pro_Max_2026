<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="capstone-10--multi-agent-software-engineering-team"></a>

# 综合项目 10：多 Agent 软件工程团队

> 2026年的多功能形状agent 工程组已经汇合:建筑师计划,N代码员平行工作 worktrees,一个审查门,一个测试器验证。 SWE-AF 的工厂结构, MetaGPT 的基于角色的提示, AutoGen 0.4 输入 actor 星象,认知号的Devin,工厂的机器人都独立降落在它上面。 worktrees 将墙上时钟转换为传输。 共享状态和 handoff 程序成为失败的表面。 综合项目在于建立团队,评估SWE- Bench Pro, 并报告 handoffs 休息,多频繁。

**类型:** Capstone
**语言:** Python / TypeScript (agents),Shell(worktree scripts)
**先修要求:** 第11阶段(LLM 工程,第13阶段(工具),第14阶段(agents,第15阶段(自治),第16阶段(多至agent17阶段(基础设施)
**实施阶段:** P11 P13 P14 P15 P16 P17 国家妇女委员会
**时间:** 40小时

<a id="problem"></a>

## 问题

Single-agent coding harnesses 而不是因为任何个人 agent 弱,但因为一个200公里 -token 上下文不能持有一个建筑计划加上四个平行代码基切片加上审评器评注加上测试输出。 多-agent 工厂分裂了问题:建筑师拥有计划,代码员同时拥有实施 worktrees,一个审查门,一个测试器验证。 SWE-AF 的“ 设施” 结构, MetGPT 的角色, AutoGen 输入 actor 图表——所有三个框架都描述相同的形状。

失败表面是 handoff。 建筑师计划一些代码器无法执行的东西。 代码器产生相互矛盾的 diffs 。 审校批准一个幻觉修正。 测试器比赛一个仍然写着的编码器。 您将建立其中的一个团队, 运行50个 SWE- bench Pro 问题, 跟踪每个问题 handoff,并公布死后。

<a id="concept"></a>

## 概念

角色被键入 agents. **Architect** (Claude 并把它分成具有明确界面的子任务。 **Coders** (Claude 索内特4.7, N平行实例,每个 `git worktree` + 代顿纳a sandbox独立执行子任务。 **Reviewer** (GPT-5.4 读合并的 diff, 批准或要求具体修改。 **Tester** (Gemini 2.5 Pro)单独运行测试套房,报告文物出入/故障。

沟通是通过一个共享的任务委员会(文件支持或 Redis)进行的,每个角色都消耗着它可以处理的任务。 Handoffs 是 A2A- 程序型信息。协调问题:合并冲突解决(协调员作用或自动三向合并)、共享状态同步(一旦代码器启动,计划就会冻结;重计划是单独事件)和审查者门锁(审查者不能批准自己的修改或拟议修改)。

Token 扩展是隐藏的成本。 每个角色边界都添加摘要 prompts 和 handoff 上下文。 一个40转单agent 运行变成160个总 翻转到四个角色。 token 效率与单agent 基准,因为问题不是"做多个 -agent 工作,但"它赢一美元。"

<a id="architecture"></a>

## 建筑

```
GitHub issue URL
      |
      v
Architect (Opus 4.7)
   reads issue, produces plan with subtasks + interfaces
      |
      v
Task board (file / Redis)
      |
   +-- subtask 1 ---+-- subtask 2 ---+-- subtask 3 ---+-- subtask 4 ---+
   v                v                v                v                v
Coder A          Coder B          Coder C          Coder D          (4 parallel)
 (Sonnet)         (Sonnet)         (Sonnet)         (Sonnet)
 worktree A       worktree B       worktree C       worktree D
 Daytona          Daytona          Daytona          Daytona
      |                |                |                |
      +--------+-------+-------+--------+
               v
           merge coordinator  (three-way merge + conflict resolution)
               |
               v
           Reviewer (GPT-5.4)
               |
               v
           Tester  (Gemini 2.5 Pro)  -> passes? -> open PR
                                     -> fails?  -> route back to coder
```

<a id="stack"></a>

## 堆栈

- Orchestration: LangGraph 具有共享状态+ /agent sub-graphs
- Messaging: A2A 协议 (Google 2025) 用于输入agent messages
- 模型:Opus 4.7(结构)、Sonnet 4.7(编码), GPT-5.4(审查员) Gemini 2.5 专业(学士)
- Worktree isolation: `git worktree add` 每代号编码器+代顿a sandbox
- 合并协调员:自定义三向合并+ LLM- 调解解决冲突
- Eval:SWE-bench Pro(50期)、SWE-AF情景、人电++用于单位测试
- Observability: 朗弗斯带角色标记的横幅, 以- /agent token accounting
- 部署:每个角色分别作为单独部署的K8人+积压的HPA

```figure
ce-team-handoff
```

<a id="build-it"></a>

## 动手实现

1. **任务委员会** File-backed JSONL 带有已输入的信件 : `plan_request`, `subtask`, `diff_ready`, `review_needed`, `test_needed`, `approved`, `rejected`, `replan_needed`. Agents 订阅标记 。

2. **Architect.** 读取 GitHub 运行 Opus 4. 7 , 并使用计划模板, 需要明确的子任务接口( 文件被触动、 公用功能、 测试撞击) 。 Emits one `plan_request` 与子任务DAG。

3. **Coders.** 平行工人,每个工人都要求从董事会获得一个子任务。 `git worktree add` branch 加上代顿纳 sandbox执行子任务。 Emits `diff_ready` 与 patch + 测试三角洲。

4. **合并协调员。** 全部调整,三向合并 branches 进入一个阵营 branch. LLM- 只有在文件层存在重叠时才调解解决冲突。

5. **Reviewer.** GPT-5.4 读取合并 diff。 无法批准它所写的 diffs。 Emits `approved` (无)或 `review_feedback` 具体更改请求已发回相关编码器。

6. **Tester.** Gemini 2.5 Pro在干净的房间里运行测试套房 sandbox捕获文物。 `test_passed` 或 `test_failed` 使用堆叠跟踪。 测试失败后, 返回到代码器拥有失败的子任务 。

7. **Handoff accounting.** 每一个消息都跨越角色边界,在兰福斯获得一个带有有效载荷大小和模型的间隔。计算每子任务 token 放大( 编码)_符号 + 审评器_符号 + 测试器_符号+建筑师_共享/ 代码_tokens).

8. **Eval.** 运行50个 SWE-bench Pro 问题。 比较通行证@ 1 和 $- per- plans- pro- 问题agent 基准数(一个Sonnet 4.7在单 worktree).

9. **Post-mortem.** 对于每个失败的问题,请指明 handoff 显示一个 handoff- 直方图失效

<a id="use-it"></a>

## 实际应用

```
$ team run --issue https://github.com/acme/widget/issues/842
[architect] plan: 4 subtasks (parser, cache, api, migration)
[board]     dispatched to 4 coders in parallel worktrees
[coder-A]   subtask parser  -> 42 lines, tests pass locally
[coder-B]   subtask cache   -> 88 lines, tests pass locally
[coder-C]   subtask api     -> 31 lines, tests pass locally
[coder-D]   subtask migration -> 19 lines, tests pass locally
[merge]     3-way merge: 0 conflicts
[reviewer]  comments on cache (thread pool sizing); routed to coder-B
[coder-B]   revision: 92 lines; submits
[reviewer]  approved
[tester]    all 412 tests pass
[pr]        opened #3382   4 coders, 1 revision, $4.90, 18m
```

<a id="ship-it"></a>

## 交付成果

`outputs/skill-multi-agent-team.md` 是一个可交付的。鉴于一个问题 URL 和平行级别,团队将产生一个每件功能的合并式公关 token accounting.

| Weight | 标准 | 如何衡量 |
|:-:|---|---|
| 25 | SWE - Bench 方案通行证@ 1 | 匹配的50号子集, 通行证@ 1 |
| 20 | 平行加速 | 单向钟点对单向agent baseline |
| 20 | 审查质量 | 注射式错误检测的误准率 |
| 20 | Token efficiency | Total tokens 解决的问题和单agent |
| 15 | 协调工程 | 合并解决冲突, handoff- 直方图失效 |
| **100** | | |

<a id="exercises"></a>

## 练习

1. 向 diff 中跑输入明显错误( extra) `return None` ))测量审查者的错误批准率。 prompt 直到虚假批准率低于5%

2. 将代码员减为两个( 结构化+ 代码器+ 审校+ 测试器, 代码员按顺序运行两个子任务) 。 比较墙上时钟和通过率 。

3. 将合并协调员替换为单写限制( 子任务触摸脱节文件集) 。 度量该选项 planning 建筑师的负担

4. 交换审查器 GPT-5.4至 Claude 4.7. 衡量误准率和 token 成本 三角洲。

5. 添加第五个角色:文档员(Haiku 4. 5) 。经审查后,它生成一个修改条目。 测量文档质量是否有理由使用额外 token spend.

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|------------------------|
| Parallel worktree | "Isolated branch" | `git worktree add` 生产每台编码器的新鲜工作树 |
| 任务委员会 | 共享信息总线 | 文件或已输入信件的 Redis 存储 agents 订阅 |
| Handoff | "龙卷风" | 任何信息从角色的背景到另一个角色的 |
| Token amplification | "Multi-agent overhead" | Total tokens 跨角色/单agent tokens 用于相同任务 |
| A2A protocol | "Agent-以-agent" | 谷歌2025年的插件agent messages |
| 合并协调员 | "Integrator" | 运行三向合并和调解冲突的组件 |
| 错误批准 | "Reviewer hallucination" | 审校批准已知错误的 diff |

<a id="further-reading"></a>

## 进一步阅读

- [SWE-AF 工厂建筑](https://github.com/Agent-Field/SWE-AF) 2026年的参考数agent factory
- [MetaGPT](https://github.com/FoundationAgents/MetaGPT) - 以角色为基础的多功能agent framework
- [AutoGen v0. 4 自动 Gen](https://github.com/microsoft/autogen) 微软键入 actor framework
- [认知AI(德文)](https://cognition.ai) 参考产品
- [工厂机器人](https://www.factory.ai) 备选参考产品
- [Google A2A protocol](https://a2a-protocol.org/latest/) - 中间agent 信息规格
- [git worktree documentation](https://git-scm.com/docs/git-worktree) 隔离基底
- [妇女网](https://www.swebench.com) — 该 evaluation target
