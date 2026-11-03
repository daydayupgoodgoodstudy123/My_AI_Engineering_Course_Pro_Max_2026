<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="agent-skills-portable-contract-and-runtime-boundary"></a>

# Agent Skills：可移植契约与运行时边界

> 技术不会太久 prompt 使用更好的文件名。它是包含可发现的指示、资源和可执行助手的软件包,可以输入 agent运行时合同的上下文 。

**类型：** 构建
**语言:** Python (stdlib)
**先修要求:** 阶段13 · 0 (工具接口),阶段13 · 05 (工具系统设计)
**时间:** ~90分钟

<a id="learning-objectives"></a>

## 学习目标

- 定义 agent skill 而不是混淆它与 prompt, repository instructions工具 钩子 钩子 subagent,或插件。
- 读取可移动的 `SKILL.md` 合同,并把它与特定运行时间的扩展分开。
- 解释发现、选择、激活、资源装载、工具使用和核查作为不同的生命周期阶段。
- 在运行时将其放置到 agent分类表
- 选择一个技能, MCP 工具,钩子 subagent,或普通代码的具体任务。

<a id="ten-minute-first-success"></a>

## 10 分钟第一成功

在解释之前这样做。 您将创建小技能, 安装
完整的审查员被捆绑成一个真实的 agent 主机, 引用它, 校验
并移除它。这证明了生命周期的可见结果。

<a id="preflight-for-the-real-host-lab"></a>

### 真正的主机实验室的飞行前

真正的宿主 checkpoint 需要点 Js, `npx`, Python 3个,一个选定
具有技能的主机, 并写入您选择的工程或用户范围
安装器。 先验证本地命令 :

```bash
node --version
npx --version
python3 --version
```

在安装前决定您要使用的主机和范围。 如果
无法提供此课程, 或在网站上阅读
后面的手工包装练习, 后退教了合同, 但是它
无法证明主机发现、调用、捆绑式执行,或
解除安装行为,保持观察标记

<a id="1-start-in-an-empty-working-directory"></a>

### 1. 以空工作目录开始

从您不断学习工作的父目录运行这些命令 :

```bash
mkdir -p agent-skills-first-run
cd agent-skills-first-run
TARGET_ROOT="$(pwd -P)"
printf 'TARGET_ROOT=%s\n' "$TARGET_ROOT"
ls -A
```

最后命令应该不打印任何文件。 如果它打印文件, 请选择其它
空目录, 这样审查会有一个明确的边界 。

为您的第一个技能创建目录 :

```bash
mkdir -p my-first-skill
```

Create `my-first-skill/SKILL.md` 带有此内容的 :

```markdown
---
name: my-first-skill
description: Turn rough meeting notes into a compact decision record when the user asks to capture a technical decision.
---

# Decision record

Extract the decision, context, alternatives, owner, and next review date.
If the notes do not contain a decision, ask one clarifying question instead
of inventing one.
```

验证您在要创建的目录中创建的文件 :

```bash
test -f my-first-skill/SKILL.md
```

没有输出和退出代码 0 表示文件存在 。

<a id="2-install-the-complete-reviewer-bundle"></a>

### 2. 安装完整的审查包

呆在这里 `agent-skills-first-run` 运行 :

```bash
npx skills add rohitg00/ai-engineering-from-scratch --skill skill-contract-reviewer --full-depth
```

选择 agent 主机和您正在使用的范围。安装器应列出
`skill-contract-reviewer` 和它写的目的地。 `--full-depth` 是
需要,因为此课程的技巧是带有引用的嵌套包, a
脚本,和资产。

Set `SKILL_ROOT` 至安装者报告的绝对目录。它必须
包含已安装的目录 `SKILL.md`,而不是课程来源
目录而非当前工作空间 :

```bash
# Replace the placeholder with the destination printed by the installer.
SKILL_ROOT="$(cd "/absolute/path/to/skill-contract-reviewer" && pwd -P)"
test -f "$SKILL_ROOT/SKILL.md"
printf 'SKILL_ROOT=%s\n' "$SKILL_ROOT"
```

如果 agent 已经打开了会话, 开始新会话或使用主机的
技能重扫描命令。 不要假设每个主机都会在目录中加载热量 。

<a id="3-invoke-it-explicitly"></a>

### 3. 明确援引

安装 agent, 与 `agent-skills-first-run` 工作时
目录, 使用主机支持的语法 :

| 宿主 | 明确援引 |
|---|---|
| Codex | `skill-contract-reviewer`,或选择它 `/skills`,然后提供审评请求 |
| Claude Code | `/skill-contract-reviewer` 之后是审评请求 |
| 可移动后退 | `Use skill-contract-reviewer to review the target package.` |

使用打印的绝对值 `SKILL_ROOT` 和 `TARGET_ROOT` 在
请求。 要求主机在执行前进行扩展并显示准确的
解决命令,而不是取决于进程工作目录的命令 :

```text
Use skill-contract-reviewer to review <TARGET_ROOT>/my-first-skill. The installed bundle root is <SKILL_ROOT>. Run python3 <SKILL_ROOT>/scripts/check_skill.py <TARGET_ROOT>/my-first-skill. Before running it, show the fully resolved argv. Return the validation report, selected primitives, and one sentence for each selection. Include the resolved script path, resolved target path, cwd, argv, and exit code as execution evidence.
```

解决的命令应该有这样的形状,没有占位符留下 :

```bash
python3 "/absolute/install/path/skill-contract-reviewer/scripts/check_skill.py" \
  "/absolute/workspace/path/agent-skills-first-run/my-first-skill"
```

成功的结果包括所有三种属性:

1. 主机发现 `skill-contract-reviewer` 名字吗?
2. 评审员阅读了包件合同并运行其捆绑的验证符。
3. 回复包含一个验证报告, 没有结构错误
   样本,加上合理的原始选择。

执行证据也必须命名脚本路径、 目标路径、 cwd 、 cried
参数矢量和退出代码。没有这些字段的流畅报告不
证明已安装的伴侣脚本运行 。

如果主机报告没有此项技能, 请验证安装
目标、 重新扫描或重新启动一次, 并重试明确请求。 不要
重写技能描述以隐藏安装失败 。

<a id="4-probe-implicit-selection"></a>

### 4. 隐含选择

开始新 agent 转而输入相同的任务,而不命名技能:

```text
Review <TARGET_ROOT>/my-first-skill as a reusable agent package and tell me whether its package contract is valid.
```

如果主机暴露了选中的技能, 请记录是否选择
`skill-contract-reviewer`。如果主机不暴露路径,则暗含标记
选择为未验证。 明确的引用是便携式后退 。

<a id="5-clean-up"></a>

### 5. 清理

只删除已安装的审查器包 :

```bash
npx skills remove skill-contract-reviewer
```

选择安装时使用的相同主机和范围。 在重新扫描或新建后
明确要求, `skill-contract-reviewer` 应在报告
无法使用。 保留 `my-first-skill` 用于后期课程,或删除
完成轨道后, 实验室目录 。

<a id="the-problem"></a>

## 问题

假设您的团队有一个可靠的发布工作流程。 它会发现合并的更改, 检查迁移笔记, 更新更改表, 运行一个包装命令, 并生成审查核对表 。

将工作流程放在一个 prompt 使粘贴变得容易,操作也困难。 prompt 没有稳定的身份,没有发现规则,没有资源边界,没有可测试的包形状,也没有回答基本问题:谁可以引用它?模型什么时候可以选择它?它能运行哪些脚本?信任哪个文件?当上下文被压缩时,什么能生存?

恰恰相反,错误是把每个可重复使用的教学都当作一种技能。 agents 解决不同的问题。 `SKILL.md` 产生一个目录, 它看起来可以移动, 取决于主机的无文件行为 。

第一个工程任务是分类。在决定如何包装之前,先决定什么是文物。

<a id="the-concept"></a>

## 概念

<a id="skills-encode-procedural-knowledge"></a>

### 程序知识的编码技能

一个 agent skill 是一个输入点为 `SKILL.md`。条目文件包含 YAML 前置事项 Markdown 图标。目录中还可以包含引用、脚本和资产。

```figure
skill-package-anatomy
```

目录, 不是 Markdown 仅文件,是可部署单位。 `SKILL.md` 缺少引用的包即使其前置事项已解密,也为损坏的包件。

<a id="the-neighboring-abstractions"></a>

### 相邻的抽象

| Artifact | 初级工作 | 装入或运行时 | 不该装作什么 |
|---|---|---|---|
| Prompt | 形状一型互动 | 包含在应用程序或用户中 | 配有资源的版本套件 |
| Repository instructions | 解释一个代码库的常备规则 | 编码运行时间进入此范围 | 可重复使用的任务工作流程 |
| Agent skill | 供应可再使用的程序知识 | 明示或默示激活 | 硬授权边界 |
| MCP tool | 显示已打印的远程能力 | 模型或应用程序称之为 | 详细的操作程序 |
| Hook | 运行事件确定逻辑 | 宣布的事件发生 | 概率模型路径 |
| Subagent | 代表工作,背景和状况各异 | 管弦乐队创造或称它为 | 一个静态指令捆绑 |
| Plugin | 分配更大的运行时间扩展 | 主机安装或启用 | 便携式技术合同本身 |
| 学习技能库 | 存储通过经验发现的行为 | 策略回收先前的程序或轨迹 | 标准型 `SKILL.md` package |

解脱技巧可以告诉 agent 如何检查释放。 MCP 服务器可以显示发布注册。 勾可禁止直接推动 。 subagent 独立审核候选人。这些作品是因为他们承担不同的责任。

<a id="the-word-skill-names-two-different-ideas"></a>

### 杀人这个词 有两个不同的想法

研究系统有时称其为学习程序、成功的轨迹或环境政策破碎了一种技能。 agent 可以在勘探期间创造这些文物,通过任务相似性检索、执行和根据反馈修改图书馆。 第14阶段 · 10 建立这种终身学习图书馆。

一个 Agent Skill 使用这个小轨道。 它是一个已申报的文件系统合同, 目录元数据, progressive disclosure,运行时间中介的调试和主机控制的工具。 agent,但格式不需要学习。

| 尺寸 | Agent Skill package | 学习技能库 |
|---|---|---|
| 小学单元 | `SKILL.md` directory | 程序、政策、轨迹或记忆记录 |
| Creation | 著作、创作或赞助 | 通常从环境经验中发现 |
| Selection | 目录描述加运行时间策略 | 获取任务状态或政策 |
| 执行 | 模式遵循指令和呼叫主机工具 | 环境运行存储的行为或代码文物 |
| Portability | 包件合同可以交叉兼容主机 | 往往与一个环境和行动空间联系在一起 |
| Evaluation | 运行、工艺品、安全和主机兼容性 | 奖励、成功率、转让和图书馆增长 |

这两种想法都可重复使用,不应仅仅因为拥有共同的名称而分享执行要求。

<a id="the-portable-core"></a>

### 便携式核心

该 Agent Skills 规格要求两个前置事项字段:

```yaml
---
name: release-readiness
description: Inspect a release candidate when the user asks whether a version is ready to publish.
---
```

`name` 是一个稳定的标识符。它必须满足规格的命名规则,并与父目录匹配。 `description` 既包括文档,也包括路径元数据。它应该说明技能的用途和应用时间。

可移动字段为:

| Field | 目的 | 便携说明 |
|---|---|---|
| `license` | 说明一揽子条件 | 核心规格 |
| `compatibility` | 国家环境要求 | 核心规格 |
| `metadata` | 包含字符串值扩展数据 | 核心规格 |
| `allowed-tools` | 建议预先批准的工具 | 实验; 主机支持不同 |

该 Markdown 机构持有操作指令。 它应该定义工作流程、决定点、失败行为以及直接获取支持资源的途径 。

```markdown
# Release readiness

Use this workflow for a release candidate, not for ordinary development builds.

1. Read `references/release-policy.md`.
2. Run `python3 scripts/inspect_release.py --format json`.
3. Stop if the report contains a blocking failure.
4. Produce the checklist from `assets/release-checklist.md`.
5. Ask for approval before any publish or tag action.
```

<a id="runtime-extensions-are-a-second-layer"></a>

### 运行时间扩展为第二层

有些主机接受额外的前置事项或伴侣配置。 这些字段可能有用, 但并不是自动可移植的 。

| 行为 | 示例主机扩展名 | 便携式核心? |
|---|---|:---:|
| 从模型路径中隐藏技能, 保持用户直接引用 | `disable-model-invocation` | 否 |
| 从用户命令菜单中隐藏一项技能, 允许模式路径 | `user-invocable` | 否 |
| 在命令菜单中显示参数帮助 | `argument-hint` | 否 |
| 在授权背景下运行技能 | `context`, `agent` | 否 |
| 平面模型或推理设置 | `model`, `effort` | 否 |
| 登记生命周期自动化 | `hooks` | 否 |
| 禁用代码x 中的隐含引用 | `agents/openai.yaml` policy | 否 |

将每个扩展作为适配器。 保持核心工作流程不发生作用, 记录备份并测试使用该扩展的东道主。 运行时间可能会忽略未知字段, 拒绝它, 或者保存它而不执行行为 。

<a id="frontmatter-is-executable-metadata"></a>

### 前事项是可执行的元数据

元数据在阅读技能体之前会改变系统行为。

- 错误的 `name` 可能会让发现失败
- 模糊 `description` 可能会错误地处理请求
- 单人旗可以从模型目录中去除技能。
- 工具允许可以更改主机是否请求允许 。
- 上下文设置可以将执行移动为单独 agent session.

重审前事项, 如配置代码。 验证它, 版本它, 并且将它的行为包含在 evals 中 。

<a id="the-skill-lifecycle"></a>

### 技能生命周期

```figure
skill-runtime-lifecycle
```

每支箭都是有其自身失败模式的边界。

1. **Discovery** 在配置的位置中找到可能的软件包 。
2. **Validation** 在目录发布前拒绝错误的或不安全的软件包 。
3. **Cataloging** 暴露了契约 `name` 和 `description`,不是完整的包。
4. **Selection** 确定技能是否相关。
5. **Activation** 将身体装入可显示的模型环境。
6. **Disclosure** 仅在下列情况下才读取参考文献或资产: branch 需要他们。
7. **Execution** 使用主机工具,并按主机的许可和隔离规则。
8. **Verification** 与模型的索赔无关,检查所生产的文物。

串联这些阶段会导致不良的心理模式。 发现的技能不活跃。 一项积极的技能无权做它描述的所有事情。 允许的是一种允许的技巧。 tool call 并不是结果正确的证据。

<a id="skills-and-tools-are-orthogonal"></a>

### 技能和工具正对齐

MCP 答案是,“这个应用程序能调用哪些能力,他们的计划是什么?” agent 使用此任务类别吗?"

```figure
skill-tool-orthogonality
```

技能可以命名工具, 但东道方拥有实际的能力登记册。 如果该工具不存在, 则该技能应该明确说明其退缩或失败。 它绝不意味着命名能力会创建它 。

<a id="skills-and-repository-instructions-are-different-scopes"></a>

### 技能及 repository instructions 不同范围

Repository instructions 描述您已经处于的环境: 命令、 常规、 生成的文件和边界。 一种技能可以为许多仓库中的任务提供可重复使用的程序 。

当这两种应用时,主动用户请求和存储器规则会限制技能。通用的重新设定技能不能推翻禁止编辑生成文件的存储器规则。

<a id="skills-do-not-import-one-another"></a>

### 技能不相互输入

一种技能可以指导 agent 来引用另一个, 但这不是一个语言级的导入。 第二个技能仍然要经历运行时间发现、 资格、 激活、 许可和上下文处理 。

将跨技能依赖写为可观测的工作流程边角 :

```markdown
After producing the candidate changelog, invoke the `release-risk-review` skill.
Pass the candidate path and require a blocking or non-blocking verdict.
If that skill is unavailable, stop and report the missing dependency.
```

这使依赖性可以测试,并使东道方有机会执行政策。

<a id="build-it"></a>

## 动手实现

`code/main.py` 执行一个小型的标准导向验证器和一个人工制品选择器。 它只保持标准级, 所以每个规则都可见 。

验证人披露:

- `parse_frontmatter(text)` 将元数据与身体分离。
- `validate_skill_text(text, directory_name, allowed_runtime_extensions=())` 以检查所需的字段、命名、未知扩展、体身存在和可移动的限值。
- `ValidationIssue` 和 `SkillReport` 而不是一个不透明的布尔恩
- `FrontmatterSyntaxError` 用于无法安全解释的输入。

选择者暴露 `TaskShape` 和 `select_primitives(task)`。它绘制了任务对普通代码的需求, repository instructions技术 钩子 鱼钩 subagent,或 MCP tool.

运行实验室:

```bash
cd "$(git rev-parse --show-toplevel)"
cd phases/13-tools-and-protocols/22-skills-and-agent-sdks
python3 code/main.py
python3 -m unittest discover -s code/tests -v
```

此命令块需要一个本地克隆, 必须从内部任何地方开始
克隆人是这样 `git rev-parse --show-toplevel` 能够解析仓库根 。

演示指纹 JSON 对于一种有效的便携式技能, 一种主机扩展技能, 一个无效的软件包, 以及几项任务形状决定。 请检查发行代码。 软件包验证器应该解释如何在不代表作者的情况下修复文物 。

<a id="validation-order-matters"></a>

### 审定令的重要性

在更深的内容规则之前验证廉价的结构事实:

```figure
skill-validation-order
```

这一命令防止了第二错误蒙蔽第一个破碎的变数。

<a id="use-it"></a>

## 实际应用

在写作前,请填写决定卡:

| 问题 | 如果是,请说明 | 可能很原始 |
|---|---|---|
| 这是否需要通过几个步骤重新作出可使用的模型判断? | 程序稳定,但决定不尽相同 | Skill |
| 一定要每次发生火灾时都发生这种事吗? | 一次处决是无法接受的 | 钩或应用代码 |
| 该模型是否需要有输入输入的外部能力? | 行动不局限于模型背景 | 工具或 MCP server |
| 这项工作需要孤立的环境、状态或所有权吗? | 独立工人返回一个约束的结果 | Subagent |
| 是否针对一个存储处提供这一指导? | 说明地方指挥和制约因素 | Repository instructions |
| 一种互动就够了吗? | 不需要包件生命周期 | Prompt |

许多生产流程使用不止一行。卡片防止一个文物假冒提供每一个属性。

<a id="ship-it"></a>

## 交付成果

这个课产生 `skill-contract-reviewer` 捆绑在 `outputs/`. 其中载有:

- 便携式 `SKILL.md` 审查拟议的一揽子技能;
- 便携式合同和原始选择的参考清单;
- 确定性验证脚本;
- 任务形状装置覆盖 prompts技能、工具、钩子、普通代码 subagents.

安装完整包, 不仅其条目文件 :

```bash
cd "$(git rev-parse --show-toplevel)"
python3 scripts/install_skills.py /tmp/aiefs-skills --phase 13 --type skill
```

课程安装员报告每个版本的13阶段技能并写作
`/tmp/aiefs-skills/manifest.json`。这种干净的目的地检查包形状;
上方第一个成功循环检查发现和在真正的主机中引用。

以下经验教训深化了生命周期的各个阶段。 progressive disclosure25课建立职业政策和路线。26课将许可与沙箱分开。27课将整个包件变成评估的释放工艺品。

<a id="exercises"></a>

## 练习

1. 使用您的团队对五个工作流程进行分类 `TaskShape`。在每一个情况下,只要选择一个以上的原始案件,就都得保护它。
2. 添加边界测试, 证明有500个字符 `compatibility` 值通过,501字符值作为规格错误失败。
3. 向允许列表添加一个运行时间扩展名。 写入一个测试, 证明同一文件仍然可以与只可移动的技能区分 。
4. 分割一个400行 prompt 进入 `SKILL.md`,一个参考文件,一个脚本合同和一个输出模板。让每个文件负责一种信息。
5. 设计一个匹配无法使用的技能的失败响应 MCP 工具。不要以更广泛的权限静默地替换工具。
6. 审查现有的技能,并将每句标为路线、程序、政策、参考指针或输出合同。移动不属于它的任何内容。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|---|---|---|
| Agent skill | "一个被拯救的 prompt" | 可发现的程序性指示和可选资源目录 |
| 便携式核心 | "每个运行时间的股份都投入到田里" | 合同由 Agent Skills specification |
| 运行时间扩展 | "超前事项" | 其行为需要兼容的适配器的主机配置 |
| 激活 | 技术运行 | 技术体进入了可视模型环境;执行可能稍后进行 |
| 技能依赖 | "再输入一个技能" | 运行时间中介的调试边缘 availability 和政策检查 |
| Tool contract | "功能图" | 投入、产出、许可、副作用、错误和能力证据 |

<a id="further-reading"></a>

## 进一步阅读

- [Agent Skills specification](https://agentskills.io/specification) 用于便携式目录和前事项合同。
- [Agent Skills 最佳实践](https://agentskills.io/skill-creation/best-practices) 范围、指示和资源组织。
- [OpenAI:培养技能](https://learn.chatgpt.com/docs/build-skills) 以当前代码识别和调试行为
- [Claude 代码技能](https://code.claude.com/docs/en/skills) 用于一次运行时的引用、争论、工具和授权的文本扩展。
