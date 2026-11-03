<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="skill-invocation-and-routing"></a>

# Skill Invocation 与路由

> 援引是一种权威决定,随后作出相关决定。 良好的描述有助于模式的选择;良好的政策决定是否允许选择。

**类型：** 构建
**语言:** Python (stdlib)
**先修要求:** 阶段13 · 24 (Skill Discovery 和 Progressive Disclosure)
**时间:** ~105分钟

<a id="learning-objectives"></a>

## 学习目标

- 区分明确用户的援引、隐含的模式援引、应用的援引以及技能与-skill invocation.
- 模拟人的能见度和作为独立政策层面的资格。
- 写出路径描述, 带有正触发器和接近缺失的边界 。
- 单独资格、选择、激活、辩论约束和执行 traces 和测试。
- 调整运行时特定的工作权限,不显示为可移动的前事项。

<a id="the-problem"></a>

## 问题

你安装 `database-migration` 技能。 用户可以用名称运行它, 但模型也可以看到它的描述, 当有人询问一般数据库问题时选择它。 技能然后为只需要解释的任务提出一个方案修改 。

您添加 `user-invocable: false`,期待阻止人们手动运行。在另一个运行时间,该字段被忽略。您添加 `disable-model-invocation: true`,期待技能完全消失。在运行时,用户仍然可以明确引用它。

字段名称没有问题。 模型是错误的 。 “ 用户可以看到它 ” , “ 模型可以选择它 ” , “ 应用程序可以预加载它 ” , “ 工具在里面可以执行” 是不同的事实。 一个叫做“ 布尔” 的单词是单独的事实 。 `invocable` 无法表达这些。

运行有第二个失败模式。 如果描述模糊, 几种技能就变得合理。 如果描述中含有关键词, 则不相关的任务触发它们。 目录是一个概率界面: 足够精密, 足够具体到路由 。

<a id="the-concept"></a>

## 概念

<a id="five-channels-can-start-the-lifecycle"></a>

### 五个频道可以启动生命周期

| Actor | 调用形状 | 典型用途 | 主要风险 |
|---|---|---|---|
| 人类用户 | 使用用户界面中显示一个技能或 prompt | 故意选择工作流程 | 用户期待 availability 或授权东道方不给予 |
| 型号或自主 agent | 从任务上下文中选择目录条目 | 自动专家程序 | 假阳性路线 |
| Application | 通过运行时间代码激活或预加载一项技能 | 固定产品工作流程 | 隐藏连接到一个主机 |
| 另一种技能或 subagent | 要求具备作为工作流程依赖性的确切技能 | 成分 | 周期、缺乏依赖性或上下文流血 |
| Evaluation harness | 在固定的情景下激活精确的技能 | 可重复测量 | 无意中绕过研究中的生产政策,测试技能 |

便携式 Agent Skills 指定软件包定义。它不统一一个通用的斜线命令 UI、隐性路径标志、应用程序 API, 或 subagent lifecycle.

<a id="the-five-invocation-stages"></a>

### 五个援引阶段

```figure
skill-invocation-stages
```

准确使用这些词:

- **Eligible** 意味着政策允许这样做 actor 要求获得技能。
- **Selected** 表示用户命名它或一个路由器判断它是否相关。
- **Activated** 是指其指示进入工作环境。
- **Executing** 表示 agent 根据这些指示开始模型或工具工作。
- **Completed** 表示输出成功独立检查。

一个 trace 仅记录 `skill_used=true` 隐藏失败的边界。

<a id="human-and-model-invocation-form-a-2x2-matrix"></a>

### 人和型号引用组成 2x2 矩阵

| 人类可以援引 | 模式可以援引 | 模式 | 适当实例 |
|:---:|:---:|---|---|
| 是的 | 是的 | Shared | 代码解释,测试 planning,文件审查 |
| 是的 | 否 | Human-only | 出版准备、出帐、破坏性清理计划 |
| 否 | 是的 | Model-only | 内部样式指南、域名参考、自动支持程序 |
| 否 | 否 | 禁用或只使用应用程序 | Staged rollout,折旧包,方案预载 |

矩阵是一个政策模式,而不是标准 YAML.

当前主机使用 `disable-model-invocation: true` 用于单人行和 `user-invocable: false` 用于只使用模型的行。默认是两者。另一个主机使用 `agents/openai.yaml` 与 `allow_implicit_invocation: false` 以保持明确的引用,同时禁用隐含的选择。这些是运行时间调整器。未知的主机可能忽略它们 。

混乱的细节很重要: `user-invocable: false` 并不表示“ 模型不能使用此功能 。 它会删除主机中直接用户的引用 。 `disable-model-invocation: true` 并不表示“ 技能已被禁用 。 ” 它删除了模式启动的选择, 同时保留明确的用户访问 。

<a id="explicit-invocation-is-identity-first"></a>

### 明确援引即身份第一

明确援引直接提供身份:

```text
/release-readiness v2.4.0
```

或：

```text
release-readiness check v2.4.0 without publishing
```

当前代码界面文档 `/skills` 要求明确援引时,可选用和普通技能名称。 Claude 代码文件 `/skill-name` 和主机特定的参数扩展。 精确的语法、 菜单可见度、 引用规则以及变量扩展属于主机 。

明确的请求仍然通过政策。 命名技能时不能绕过缺少的许可、 工作空间限制, approval gates或运行时间隔离。

<a id="implicit-invocation-is-description-first"></a>

### 隐含的引用是描述第一

对于隐含路径,模型最初看到的是目录元数据而不是整个体。因此,描述是技术的路径界面。

Weak:

```yaml
description: Helps with releases.
```

Over-broad:

```yaml
description: Use for release, version, package, build, deploy, publish, tag, changelog, GitHub, CI, or software tasks.
```

Bounded:

```yaml
description: Inspect an already prepared release candidate and produce a readiness report. Use when the user asks whether a version, tag, package, or image is ready to publish; do not use for ordinary build failures or feature development.
```

封装版本包括:

1. **Capability:** 检查一个准备就绪的候选人。
2. **输出:** 准备报告
3. **正边界 :** 问解禁物品是否已准备好
4. **负边界 :** 普通建筑和发展超出了范围。

负边界在附近两个技能共享时有用 vocabulary。它们不是近乎缺失的 Evals 的替代物。

<a id="routing-is-classification-with-an-abstain-option"></a>

### 运行是包含弃权选项的分类

做一个技艺 `s` 和要求 `x`,想象一个路由器得分:

```text
score(s, x) = capability_match + trigger_match + context_match - exclusion_match - ambiguity_penalty
```

确切的评分可能是 LLM 工程原理仍然坚持:选择应该超越一个门槛和一种竞争的技能。当证据薄弱时,就弃权。

```figure
skill-routing-abstention
```

对于高影响力技能,隐性路线即使描述有力也可能不合适。 当假正数成本超过自动选择的方便度时,使用只为人的政策。

<a id="eligibility-must-precede-ranking"></a>

### 资格必须先于排名

选择最强的匹配,然后检查其中一项策略。 被阻断的顶级匹配会错误地阻止合格低分候选人被考虑。

使用此顺序进行隐性路径 :

1. 请求者过滤所发现的技能 actor 以及活动的主机适配器。
2. 只评分合格候选人。
3. 如果选择最符合条件的匹配值, 则该匹配值将清除阈值和模糊性规则 。
4. 拒绝任何候选人或没有合格分数就足够了。

Suppose `incident-triage` scores `0.80` 但主机扩展功能会禁用模式引用 。 `incident-review` scores `0.55` 并允许模型引用。 路由器应该对 `incident-review` 不应选择 `incident-triage`否认,停止。

此顺序还防止政策变化改变关联度评分的含义。 资格定义了选择集。 相关性排序是设定的 。

<a id="routing-evals-need-near-misses"></a>

### 运行的反省需要近乎失手

事实证明,有积极的情况:

```json
{"prompt":"Is version 2.4.0 ready to publish?","expected":"release-readiness"}
```

清除的负数证明基本精确度 :

```json
{"prompt":"Explain rotary position embeddings.","expected":null}
```

几乎漏掉曝光边界质量 :

```json
{"prompt":"Why did today's package build fail?","expected":"build-diagnostics"}
```

差一点就分红了 `package` 和 `build` 使用释放技巧,但属于别处。 由明显的正数和非相干负数组成的路径组合将会夸大质量。

<a id="arguments-have-three-representations"></a>

### 论点有三项陈述

援引论点跨越若干界限:

```figure
skill-argument-boundaries
```

在每个边界上,保留意图而不将文字视为代码。

- 主机分析器决定命令语法和引用 。
- 技能根据主机规则接收约束文本或变量。
- 说明验证了所需的数值和默认值。
- 一个 tool call 将值转换成已输入的公式并重新验证。

不将原始参数插入 shell 命令。 最好使用参数矢量或输入的脚本 MCP tool.

<a id="application-invocation-is-explicit-orchestration"></a>

### 适用性明确 orchestration

产品可以激活一项技能, 因为它的工作流程已经知道任务类型。 例如, 一次拉动请求审查服务可以预加载 `pull-request-risk-review` 用户按下“ Review” 后。

这会消除路线不确定性, 但会给运行时间造成依赖 API。将适配器保存在便携式体之外:

```figure
skill-host-adapter
```

由另一个遵守规定的客户开业时,技能应保持易懂。

<a id="skill-to-skill-invocation-is-a-tool-like-edge"></a>

### Skill-to-skill invocation 类似工具的边缘

Suppose `release-readiness` 要求 `security-change-review` 当依赖文件更改时。

打电话者应提供:

- 目标技能特性;
- 一条捆绑的任务和人工道路;
- 预期的反应合同;
- 援引的理由;
- 如果无法备份;
- 最大深度或周期规则。

```json
{
  "target_skill": "security-change-review",
  "task": "Review dependency changes in the candidate diff",
  "inputs": ["artifacts/release.diff"],
  "expected": "risk-report.json",
  "max_depth": 2
}
```

第二种技能不是盲目粘贴到第一个技能。 东道方决定如何激活它, 以及它是否共享上下文、 以叉子运行, 或者通过工具结果返回 。

<a id="context-lifecycle-is-host-specific"></a>

### 背景生命周期是主机专用的

激活后, 技能机构可以保留在对话中, 压缩时可以总结, 或者在授权环境下运行。 工具允许时间可以持续一个回合, 而指令则持续更长的时间 。 subagent 可能获得技能 没有父母的整个历史。

不要写出取决于隐形寿命假设的技能。 在文件或输入状态中设置耐久输出, 使重返安全, 并声明中断后必须重新装入的内容 。

```markdown
On resume, read `artifacts/release-readiness.json` if it exists.
Revalidate the candidate commit before continuing.
Do not repeat an external write whose idempotency key is already recorded.
```

<a id="build-it"></a>

## 动手实现

`code/main.py` 执行政策和作为单独的适应器进行路线调整。

该模式包括:

- `Actor` 人类,模特,自主 agent、应用、技能和 harness callers;
- `SkillMetadata` 用于确定身份;
- `InvocationPolicy` 用于人类/模型矩阵;
- `InvocationRequest` 和 `InvocationDecision` 用于可追踪的投入和结果;
- `CorePolicyAdapter` 用于没有主机扩展的便携式行为;
- `ExtensionPolicyAdapter` 用于公认的运行时字段;
- `build_invocation_matrix(policy)` 2. 用于 2x2 视图;
- `route_request(skills, request, adapter)` 以在相关等级、选择和拒绝之前筛选资格。

运行：

```bash
cd phases/13-tools-and-protocols/25-skill-invocation-and-routing
python3 code/main.py
python3 -m unittest discover -s code/tests -v
```

演示打印了一个矩阵和决定 以明确的人,隐含模型,自主agent、应用、技能构成以及 harness 频道。它的扩展适应结果显示,在符合条件的选项排行之前,将删除一个封存的顶部词汇匹配。它还包括精确的名称允许列表。没有模式 API 确定性路由器的存在是为了使政策界限可以检查,而不是声称与词汇匹配的路径模型复制。

<a id="why-core-and-extension-adapters-are-separate"></a>

### 为什么核心适应器和扩展适应器是分开的

如果一个分析器给每个观察到的前题字段指定了含义, 它会悄悄地将运行时间的常规化为假标准。 单独的调整器迫使调用者命名主机语义活跃的域 。

该 `CorePolicyAdapter` 仅使用应用程序供应的策略。 `ExtensionPolicyAdapter` 承认一组明确的主机字段和记录,这些字段改变了决定。

<a id="use-it"></a>

## 实际应用

发布技能前写下劳动合同:

```yaml
actors:
  human: allow
  model: deny
  application: allow
  skill: deny
explicit_name: release-readiness
arguments:
  candidate: required
  publish: fixed_false
ambiguity: ask_user
missing_dependency: stop
context:
  durable_state: artifacts/release-readiness.json
  max_composition_depth: 2
```

这项合同是适应器和测试的设计文件。 `SKILL.md` 前置事项,除非有标准明确采用。

<a id="ship-it"></a>

## 交付成果

这个课产生 `skill-invocation-router` 捆绑。 它包括一个引用模型参考, 一个示例主机政策, 和一个无法执行的 CLI, 评估一个人, 模型, 自主 -agent、应用、技能构成或 harness 请求并返回 a JSON 以频道、适配器、分数和理性来决定

单项请求的CLI是政策调查,不是完全触发 evaluation。使用27课中贴有肯定和接近缺失的标签设计来计算混乱的计数、精确度、回溯和重复运行的稳定性。

<a id="exercises"></a>

## 练习

1. 创建全部四行的人类/模型矩阵,并写出每个矩阵的合法使用选项。
2. 添加只允许应用程序激活到 `CorePolicyAdapter`证明人类和模特儿的呼唤者仍然被拒之门外
3. 写十个差近的部署技能 prompt 必须共享 vocabulary 拥有技能,同时属于不同的工作流程。
4. 在前两个路由分数之间添加模糊差。 返回 `ask` 当边际太小的时候,
5. 将最大成分深度添加到技能到技能的要求中,并检测出双技能周期。
6. 通过核心和扩展适配器运行相同的标签集。 解释每个更改的决定 。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|---|---|---|
| 明确援引 | "斜线命令" | 一个 actor 直接提供技能身份,但须遵守政策 |
| 默示援引 | 模特儿选 | 路由器根据任务背景从符合条件的目录元数据中选择 |
| User-invocable | 人类可以使用它 | 特定主机菜单或直接调用属性, 不是核心字段 |
| Model-invocable | "该 agent 可以用它来表达 | 根据东道方政策隐含选择模型的资格 |
| 调试器 | "反物质分析器" | 用于绘制主机字段的代码 APIs 成为已宣布的政策模式 |
| 近乎错过 | 阴性 | 类似技能预期投入的不触发请求 |
| Abstention | "没有选择技能" | 缺乏证据或证据模糊时故意的路线结果 |

<a id="further-reading"></a>

## 进一步阅读

- [优化技能描述](https://agentskills.io/skill-creation/optimizing-descriptions) 积极触发器、特性和 evaluation.
- [评估技能](https://agentskills.io/skill-creation/evaluating-skills) 用于触发和输出反射设计。
- [OpenAI:培养技能](https://learn.chatgpt.com/docs/build-skills) 用于当前代码编码的明示和默示引用控制。
- [Claude 代码技能](https://code.claude.com/docs/en/skills) 给一个主人 `user-invocable`, `disable-model-invocation`、辩论和授权的背景。
