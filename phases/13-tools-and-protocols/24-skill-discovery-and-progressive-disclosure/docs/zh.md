<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="skill-discovery-and-progressive-disclosure"></a>

# Skill Discovery（技能发现）与 Progressive Disclosure（渐进披露）

> 一种技能在它的身体被装入之前变得有用。 它的名称和描述在目录中占据一个位置; 其深层的文件只有在任务到达时才能获得上下文 。

**类型：** 构建
**语言:** Python (stdlib)
**先修要求:** 阶段13 · 22 (Agent Skills:便携式合同和运行时间边界)
**时间:** ~105分钟

<a id="learning-objectives"></a>

## 学习目标

- 建立一个文件系统发现管道, 将范围、验证、碰撞政策和目录发布分开。
- 解释三个披露级别:目录元数据、主动指示和具体任务资源。
- 设计参考 agent 可在不装入整个软件包的情况下直接达到所需的细节。
- 预算目录空间独立于主动技能环境。
- 拒绝路径的穿行和交汇当技能读取自己的资源时就逃跑。

<a id="the-problem"></a>

## 问题

你的 agent 具备200种安装技能。 `SKILL.md`,引用文件、脚本和模板会将当前任务隐藏在不相关的程序中。装入任何内容都不会迫使用户记住准确的文件系统路径。

通常的折中方案是目录:给模型显示每个合格技能的紧凑身份和路径描述,然后在选择后再加载整个身体。这造成了两个新的工程问题。

首先,发现不仅仅是递归文件搜索。 技能可以在工程、 用户、 管理员、 插件或内置范围中存在。 两个软件包可以共享一个名称。 一个符号链接可以在信任的根部之外指向。 一个错误的软件包可以消耗目录空间或者无法引用 。

Second, progressive disclosure 可能会逐渐变得混乱。如果 `SKILL.md` 表示“ 读取相关指南” , 而包包含十二个指南, 模型必须猜想。 如果每条指南指向另外三个文件, 装入会变成一个未绑定的图形行进 。

良好的运行时间使得发现具有决定性和故意披露。

<a id="the-concept"></a>

## 概念

<a id="discovery-is-a-compiler-pipeline"></a>

### 发现是一个编译管道

将文件系统作为源输入。 不要直接发布到模型的原始路径 。

```figure
skill-discovery-pipeline
```

每个阶段应产生结构化数据和结构化故障。

- Which roots 被搜过身?
- 找到哪些候选人了?
- 哪些候选人被拒绝,为什么?
- 哪个包裹赢得了碰撞?
- 哪些目录因预算而缩短或省略?

没有证据,"模型没有使用我的技能" 几乎无法诊断。

<a id="scope-is-runtime-policy"></a>

### 范围是运行时政策

便携式规格定义了技能软件包,而不是一个通用安装路径或优先顺序。主机决定它在哪里搜索。

通用运行时间可使用这些范围:

| Scope | 示例根 | 预期所有权 |
|---|---|---|
| Workspace | `<repo>/.agents/skills/` | 项目维护者 |
| User | `<user-data>/skills/` | 一个开发者 |
| Administrator | `<system>/skills/` | 机器或组织政策 |
| Plugin | 签名的插件包 | 插件发布器和安装器 |
| Built-in | 运行时间套件 | 运行时间供应商 |

2026年8月,代码系统记录了 `$CWD/.agents/skills` 通过仓库根端的祖先目录, 加上用户、 管理员和内建位置。 它支持有交错关联的技能目录。 重复的名称可能同时出现而不是合并。 这些是代码行为, 而不是对代码 `SKILL.md`; 验证当前 [代码技能文件](https://learn.chatgpt.com/docs/build-skills) 写一个适配器时。

从未从目录名称中创建优先级。 声明它为策略并测试它。 课程实验室对每个目录使用明确的整数排序 `Scope` 所以同一个候选人总是 以同样的方式解决。

<a id="collisions-need-identity-beyond-name"></a>

### 碰撞需要超越身份 `name`

两个包命名 `release-readiness` 可以是合法的。 一种可能是工作空间的超文本操作,另一种可能是用户默认。 因此目录条目至少需要 :

```json
{
  "name": "release-readiness",
  "description": "Inspect a release candidate for this repository.",
  "scope": "workspace",
  "source": "/repo/.agents/skills/release-readiness",
  "selected": true
}
```

共同碰撞政策包括:

| 政策 | Benefit | 风险 |
|---|---|---|
| 保持每个候选人 | 没有什么是隐藏的 | 模型看到模糊的名称 |
| 最高频度范围获胜 | 简单引用 | 本地软件包可以隐藏信任的软件包 |
| 拒绝重复 | 不许无声的影子 | 合法超标停止工作 |
| 按来源对名称进行资格认证 | 明确身份 | 用户定位名称变长 |

为主机选择一个策略。 即使在模型目录中找不到被拒绝或影子的候选人, 也保留他们的诊断能力 。

<a id="three-disclosure-levels"></a>

### 三个披露级别

该 Agent Skills 规格描述分阶段装入。 密钥是每个级别都有不同的目的 。

```figure
skill-disclosure-levels
```

<a id="level-1-catalog-metadata"></a>

#### 第1级:目录元数据

模型需要足够的信息来区分技能与邻居。 tokens 每个目录条目,但实际序列化和 tokenization 属于宿主

有用的说明有两个条款:

```yaml
description: Validate a release candidate and produce a readiness report. Use when the user asks whether a version, tag, or package is ready to publish.
```

第一条说明能力,第二条说明触发边界。 prompts.

<a id="level-2-active-instructions"></a>

#### 二级:主动指令

激活后, 身体应作为地图和程序运行。 规格建议保留 `SKILL.md` 低于500行,这是设计信号,不是要填充的目标

机构应包含:

- 任务边界;
- 默认工作流程;
- branch conditions;
- 直接引用更深的文件;
- 工具和脚本合同;
- 失败和停止行为;
- 和核查的预期产出。

不要将中心工作流程移动为引用, 仅让条目文件短短。 激活必须给模型足够的背景来正确启动 。

<a id="level-3-supporting-resources"></a>

#### 第3级:支助资源

参考文献提供说明或数据。脚本提供决定性的计算。资产被复制、填充或转换成可交付品,而不是作为指示处理。

| Directory | 模特儿读过吗? | 模特会执行吗? | 典型内容 |
|---|:---:|:---:|---|
| `references/` | 是的,必要时 | 否 | 计划、政策、域指南 |
| `scripts/` | 可能检查它 | 通过允许的工具 | 验证器、转换器、收集器 |
| `assets/` | 只有在有用的情况下 | 否 | 模板、 固定装置、 图像、 启动文件 |

这些名称是常规,而不是魔法能力。主机仍然需要文件访问和操作工具。

<a id="branch-specific-references-beat-topic-dumps"></a>

### Branch- 特定参考比对主题倾弃

将条目文件写入决定映射图 :

```markdown
## Choose the path

- For a Python package, read `references/python-release.md`.
- For a container image, read `references/container-release.md`.
- For a documentation-only release, read `references/docs-release.md`.
- If the release combines artifact types, read only the guides for those artifacts.
```

这给每个引用提供了可观测的负载条件。 "Read `references/` 更远的"没有。

将参考图保持浅色。 官方指导建议直接链接来自 `SKILL.md` 并且避免了深层的链条。一跳就能测试到可接触性,并减少一个必要的限制永远无法进入环境的可能性。

```figure
skill-reference-map
```

<a id="catalog-budget-and-active-context-are-different-budgets"></a>

### 预算表和现行背景不同

Let `c_i` 成为连续技术目录的成本 `i`, `B_c` 目录预算, `b_j` 活体成本, `r_k` 资源实际上已装入。

```text
catalog_cost = sum(c_i for every published skill)
active_cost = sum(b_j for every activated skill) + sum(r_k for every disclosed resource)
```

压缩一个预算不会自动减少另一个预算。 简短的描述可以节省目录空间, 而一个被激活的900行体仍然在任务上压倒。 将身体分成参考文件只有在运行时间和指令实际避免装载不相关的时段才能降低活动成本 branches.

代码目前将初始技能列表的预算为上下文的2%
窗口。8 000 字符值是一个
只有在未知大小时才会后退;它不是第二个上限,而是一个
2%的规则。当目录超过适用预算时,
描述可以缩短或略去。
代码政策, 不是 Agent Skills standard.

<a id="resource-paths-are-a-trust-boundary"></a>

### 资源路径是 trust boundary

一项技能只应读取软件包中的文件。 字串前缀检查不够 :

```text
references/../../../../.ssh/config
references/external-link -> /private/company-secrets
```

以文件系统语义解析软件包根和候选文件, 拒绝绝对输入, 并验证已解决的候选人是否仍然在已解决的根根下。 决定是否允许在发现之前使用符号链接 。 如果允许, 每次检查已解决的目标 。

```figure
skill-resource-containment
```

路径控制不能建立内容信任。 有效的内包引用仍然可以包含恶意指令。 26课处理这种威胁 。

<a id="loading-must-be-observable"></a>

### 装入必须是可观测的

记录披露事件, 不记录机密 :

```json
{
  "event": "skill.resource.loaded",
  "skill": "release-readiness",
  "resource": "references/python-release.md",
  "reason": "candidate contains pyproject.toml",
  "bytes": 2840
}
```

原因将上下文选择转化为可审查的证据。 agent 以装入每个文件"以防万一"

<a id="build-it"></a>

## 动手实现

`code/main.py` 建立决定性的发现和披露引擎。

发现表面包括:

- `Scope` 来源和优先元数据;
- `SkillCandidate` 用于未验证的文件系统候选人;
- `discover_scope(scope)` 列举直接技能目录;
- `resolve_collisions(candidates, precedence)` 实施一项宣布的政策;
- `CatalogEntry` 和 `build_catalog(...)` 公布封闭的元数据;
- `CatalogBudget` 用于解析没有假字符的序列条目 tokens.

披露面包括:

- `load_skill_body(entry, ...)` 用于二级激活;
- `validate_reference(skill_dir, reference)` 用于控制道路;
- `load_reference(...)` 3级的界限读作。

运行实验室:

```bash
cd "$(git rev-parse --show-toplevel)"
cd phases/13-tools-and-protocols/24-skill-discovery-and-progressive-disclosure
python3 code/main.py
python3 -m unittest discover -s code/tests -v
```

此块需要一个本地克隆, 并从任何
克隆人内部的工作目录。

演示创建了临时工程和用户范围,插入了碰撞,在精心设计的小额预算下构建了目录,激活了一种技能,并尝试了一种有效的参考读取和跨行逃跑。没有安装永久文件 。

<a id="why-discovery-is-shallow"></a>

### 为什么发现是浅的

`discover_scope` 检查当前子目录 `SKILL.md`。它不会反复处理每一个嵌入的 `SKILL.md` 是一个单独的软件包。它保存软件包的边界,避免意外地在安装的技能中公布示例或固定装置。

<a id="why-the-lab-does-not-parse-arbitrary-yaml"></a>

### 为什么实验室不任意分析 YAML

实验室支持其目录所需的天线前事项。 生产运行时间应该使用安全 YAML 具有明确方案、尺寸限制和禁用自定义对象构造的解析器。 “ 仅使用标准字” 是教学限制, 而不是允许生成部分 YAML 默默地说

<a id="use-it"></a>

## 实际应用

将此核对表应用到任何发现适配器 :

1. 列出所有配置的根和可以写入它的人。
2. 显示是否允许有交错的包 。
3. 验证软件包名称、 目录名称、 所需的元数据以及条目体大小 。
4. 保留内部身份的来源和范围。
5. 宣布并测试重复姓名行为。
6. 测量发送到模型的准确序列目录 。
7. 记录为什么装入一个身体或资源。
8. 将资源保留在解析软件包根中 。
9. 当引用文件丢失时明显失败 。
10. 当安装或政策改变时重建目录 。

<a id="ship-it"></a>

## 交付成果

这个课产生 `skill-catalog-builder` 捆绑。 它扫描明确订购 roots,拒绝连接的条目文件和名称-目录不匹配,解决交叉碰撞,拒绝同等位置重复,并将选定的元数据纳入申报的条目、描述和序列字符预算。

它的 JSON 报表包含选定的条目、 阴影候选人、 省略条目、 校验错误、 优先级和预算使用。 机体和引用装入仍然是单独的运行时间操作, 所以目录构建器不执行脚本或将整个软件包输入上下文 。

<a id="exercises"></a>

## 练习

1. 添加插件范围并将其置于用户和内置位次之间。 用测试来证明碰撞结果 。
2. 将碰撞策略从最高优先改为合格名称。 保存这两个条目在目录中 。
3. 添加字节大小限制到 `load_reference`。在极限处测试文件,并在文件上方测试一个字节。
4. 创建两个声音几乎相同的描述。 重写它们, 这样触发边界就不会重叠 。
5. 添加包含所有引用和脚本的散列表。 在装入前检测修改过的资源 。
6. 将演示报告为1级,2级和3级,分别计算。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|---|---|---|
| Skill discovery | "找到每一个SKILL.MD" | 搜索已配置的范围、 验证软件包、 附加来源和应用程序策略 |
| Skill catalog | "已安装技能清单" | 符合资格的软件包压缩模型可见路径元数据 |
| 碰撞政策 | "哪个重复赢" | 不同来源的同名候选人的公开规则 |
| Progressive disclosure | "懒惰的装货" | 分阶段从体到体的上下文 branch- 具体资源 |
| 参考图 | 由技能连接的文件 | 可达资源结构及其负荷条件 |
| 路径控制 | "留在文件夹里" | 验证已解决资源目标仍留在已解决软件包根中 |

<a id="further-reading"></a>

## 进一步阅读

- [Agent Skills specification](https://agentskills.io/specification) 组合形状和 progressive disclosure levels.
- [优化技能描述](https://agentskills.io/skill-creation/optimizing-descriptions) 用于目录路径元数据。
- [Agent Skills 最佳实践](https://agentskills.io/skill-creation/best-practices) 用于直接引用和条目文件大小。
- [OpenAI:培养技能](https://learn.chatgpt.com/docs/build-skills) 用于当前代码识别范围和目录限制。
