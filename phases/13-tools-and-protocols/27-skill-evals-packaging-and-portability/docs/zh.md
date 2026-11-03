<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="skill-evals-packaging-and-portability"></a>

# Skill 评估、打包与可移植性

> 当它的软件包在灵敏中存活下来, 遵循正确的要求, 改进一个有分量的任务, 留在政策内, 并诚实地降低对另一个主机的性能时, 技能就完成了。

**类型:** Build
**语言:** Python (stdlib)
**先修要求:** 阶段13 22、24、25和26
**时间:** ~150分钟

<a id="learning-objectives"></a>

## 学习目标

- 将专家工作流程转化为技能,将判断、确定性计算、参考和产出合同分开。
- 测试包结构,触发路径,任务行为,脚本正确性,安全和可移动性 分别作为一层。
- 测量触发精确度,并使用正数、清晰的负数和几乎失灵的回溯。
- 将业绩与重复运行中的技能进行比较,不进行这种技能比较。
- 建立和强制执行跨运行能力矩阵和完整放行门 skill bundles.

<a id="the-problem"></a>

## 问题

一种技能在一个演示中起作用。 用户询问其描述中使用的词句, 作者知道打开哪个引用, 脚本看到干净输入, 并且预期主机会识别每个自定义字段 。

然后真正的使用开始。

- 模型是用来做一个附近但又不同的任务
- 一项有效的请求使用不熟悉的措辞,因此模型忽略了它。
- 尸体告诉 agent 做什么,但没有什么 文物证明完成。
- 脚本在空格、重复执行或部分状态上失败 。
- 软件包安装器副本 `SKILL.md` 但却忘记了它的参考文献。
- 另一次运行时忽略了传教标志和工具津贴。
- 一次成功,三次相同跑进不同的 branches.

这些失败没有一个被 Markdown 技能是小型软件包,具有概率路径和操作层。它们需要与其他任何生产界面一样的分解关注。

<a id="the-concept"></a>

## 概念

<a id="start-from-a-real-workflow-not-a-topic"></a>

### 由真正的工作流程开始,而不是一个主题

创建 Kubernetes 技能"不是一个可用的范围。 Kubernetes 包含数百项任务, 工具、风险和产出不同。

分析为何一个部署没有达到可用状态,

- 触发边界;
- 证据收集步骤的稳定顺序;
- 需要判断的决定要点;
- 能够成为狭义脚本或工具的命令;
- 定义的文物;
- 安全界限:只读诊断。

使用此提取访问 :

1. 专家在什么具体事件下开始这个工作流程?
2. 什么样的类似请求不应启动?
3. 专家首先收集什么证据?
4. 哪些决定取决于证据?
5. 哪些步骤足以决定剧本的写法?
6. 哪些领域规则值得参考?
7. 哪些行动需要批准,或必须超出范围?
8. 什么工艺品证明工作流程已经完成?
9. 独立审查员如何检查?
10. 哪些步骤取决于一次运行?

答案变成了一揽子结构 eval set.

<a id="separate-judgment-from-deterministic-work"></a>

### 与决定性工作分开判决

```figure
skill-workflow-extraction
```

使用模型判断来进行分类、排序、合成和模糊。使用脚本或工具来分析、计算、验证、转换、查询键入 APIs和强制的变异。

包含80行手动模拟分析的技术体是易碎的。 试图做出主观建筑决定的脚本是不透明的。 将每种行为放入最能测试的地方。

<a id="author-the-package-in-dependency-order"></a>

### 按依赖顺序撰写软件包

不从擦亮简讯开始。 从可观测到的内装合同构建 。

1. **个体合同:** 定义所需的文件、字段或决定。
2. **Verification:** 定义如何检查每项要求。
3. **证据工具:** 执行确定性收集器和验证器。
4. **决定地图 :** 连接证据状态到 branches.
5. **References:** 提供域细节 branch 需要它。
6. **条目 :** 解释工作流程、边界、失败和输出。
7. **描述:** 状态能力和触发边界。
8. **运行时间适配器 :** 单独添加引用或上下文扩展。
9. **Evals:** 运行结构,路线,行为,安全和可移动层。
10. **Package:** 安装完整的目录并从目标测试它 。

这个命令使得这篇流言为一种可测试的系统服务,而不是在演示后发明成功标准。

<a id="six-eval-layers"></a>

### 6个电子算法层

```figure
skill-eval-layers
```

每一层都回答一个不同的问题,通过一个无法替代另一个。

<a id="layer-1-package-structure"></a>

## 图层1:软件包结构

静态刺刺应核实不需要模型的事实:

- `SKILL.md` 软件包根存在;
- 前置物质分析安全;
- `name` 和父目录匹配;
- 具备所需字段,且不超过限度;
- 发布策略的运行时间延长许可列表中显示的每个非核心前事项字段;
- 包件内的每一直接参考解决方案;
- 参考文献、脚本、资产和反响装置使用释放政策允许的后缀,并停留在字节限制之内或以下;
- 没有被禁止的符号链接或特殊文件;
- 机构不得超出释放政策的人员预算;
- 故意进行狭窄的秘密式扫描,没有发现明显的证书任务或私人钥匙头;
- non-empty `## Output contract` 和 `## Failure behavior` 另有章节。

在解析前先执行物理树前飞行 `SKILL.md`, evval 数据、 证据、 主机装置或 列表。 在读取任何内容之前拒绝一个有交错的根、 有交错的父或条目, 缺少普通文件, 以及特殊文件。 然后运行内容识别策略提示。 在前飞行前解析捆绑路径时, 将删除根相链接, 证明检查需要 。

教训 harness 使这些政策值具体化: 10,000字形体限制, 1 000 000字节的同伴文件限制, 目录特定的后缀允许列表, 以及软件包要求提供的明确的运行时间扩展名称。 这些是释放政策示例, 不是通用的 。 Agent Skills 秘密扫描 guardrail 而不是证明一个包没有敏感数据

报上应该使用稳定的发行代码。 `E_*` 允许复议时出错 `W_*` 设计警告。

静态光滑可以证明软件包形状。 它不能证明模型会选择或遵循此技能 。

<a id="layer-2-trigger-routing"></a>

## 第2层:触发运行

在反复编辑描述之前创建标签的大小写 。

| 案件类型 | 目的 | 释放准备情况实例 |
|---|---|---|
| 正 | 衡量预期覆盖范围 | "3.1.0号船能造吗?" |
| 引文为正 | 避免记忆 | "在我们公布之前先检查这个标签" |
| 清除负 | 抓毛路过 | 解释批次 normalization" |
| 近乎错过 | 定义相邻边界 | "为什么包裹会失败?" |
| 竞争技能 | 在可信的条目中选择测试 | "发布说明草稿" |
| 反义词 | 测试关键字填充和注入名称 | “ 不要使用释放准备状态; 解释此堆栈 trace" |

将案件分为发展和验证组。 描述开发组。 使用验证组来决定修改后的描述是否概括。 如果释放决定足够重要, 保留最后的搁置 。

二进制引用:

```text
precision = true_positives / (true_positives + false_positives)
recall = true_positives / (true_positives + false_negatives)
f1 = 2 * precision * recall / (precision + recall)
```

10100人中有10人都是100% 但提供的证据却不同

对于目录来说,也测量顶级技能精度、弃权质量和邻里技能之间的混淆。 只有在选择了三个错误的技能之后才使用正确的技能的路由器是不健康的。

<a id="routing-evals-must-use-the-target-runtime"></a>

### 运行的反估必须使用目标运行时间

词汇模拟器对于解释测量和获取明显重叠非常有用。 它无法证明模型驱动的生产路由器的行为方式。 在要求运行时间质量之前,先运行通过实际主机、模型、目录序列和政策配置设定的标签。

<a id="layer-3-instruction-and-artifact-behavior"></a>

## 第3层: 指令和人工行为

正确触发只是入口。 技能必须改进任务 。

创建固定任务, 使用 :

- 输入文件和环境假设;
- 允许的工具和界限;
- 需要的文物路径;
- 确定性检查;
- 需要判断的物品;
- 最长时间、通话或费用;
- 失败案例和预期停止行为。

运行配对条件 :

```text
baseline: same model + same tools + same task, no skill
treatment: same model + same tools + same task, skill available
```

保持模型, temperature 或 sampling 政策、工具集、任务固定装置和预算不变。否则您不能将差异归因于技能。

有用的成果层面包括:

| 尺寸 | 示例计量 |
|---|---|
| Correctness | 所需测试和不固定出入证 |
| Completeness | 每一个艺术品合同领域都存在 |
| Efficiency | Tool calls时间流逝 tokens,或费用 |
| 证据 | 索赔指向有效的档案或意见 |
| Scope | 被禁止的文件和行动未受影响 |
| Recovery | 中断运行的复文, 且不重复副作用 |
| 人类的努力 | 审校更正的次数和严重程度 |

不仅为更少的人优化 tokens更糟糕的是短跑错过了必要的安全检查

<a id="artifact-contracts-make-behavior-executable"></a>

### 个体合同使行为可执行

人工制品合同是一份独立检查的属性清单:

```json
{
  "artifact": "release-readiness.json",
  "required_fields": [
    "candidate",
    "source_revision",
    "checks",
    "blocking_findings",
    "recommendation"
  ],
  "allowed_recommendations": ["ready", "blocked", "needs-review"],
  "evidence_required_for_each_check": true,
  "publish_side_effect_allowed": false
}
```

域检查验证候选人审校和证据路径,由人或校准法官评估建议是否根据证据。

<a id="layer-4-script-correctness"></a>

## 图4:脚本正确性

测试技能脚本,像普通软件, 外型运行。

最低情况:

- 正常输入;
- 空输入;
- 输入格式错误;
- Unicode、空白和路径边缘大小写;
- 重复处决;
- 超时或依赖性失灵;
- 上一个运行的输出部分;
- 输出大小限制;
- 干线行为;
- 结构化退出和错误合同。

使用固定装置。 不需要实时网络进行单位测试。 在明确的标志后安装网络整合测试, 并记录它们所依赖的远程合同 。

如果脚本执行副作用,请将计划与 commit. 需要 idempotency 或重新审阅外部文件的补偿。

<a id="layer-5-safety-and-authority"></a>

## 第5层:安全和权威

安全评价询问包裹是否在授权范围内。

至少测试 :

- 用户在技能范围以外提出请求;
- 参考输入中的恶意指令;
- 摆脱包件的资源路径;
- 工作空间符号链接, 以避开允许的根;
- 申请未申报的网络目的地;
- 需要环境证书的命令;
- 未经批准而采取破坏性或外部行动;
- a. 输出过大或无穷无尽;
- 技能到技能周期;
- 复述可能会重复副作用

记录控件是否只为指令、工具策略、批准 sandbox或核查。只使用指令的防御不应报告为强制封闭。

<a id="layer-6-packaging-and-portability"></a>

## 第6层:包装和便携性

<a id="install-the-directory-as-one-unit"></a>

### 将目录安装为单元

释放测试应安装到干净的目的地,然后对安装的复制件进行验证。

```figure
skill-package-install
```

只测试源树时丢失安装器错误、 丢失可执行比特、 平坦引用、 重写名称以及旧版本的残废文件 。

清单可包括:

```json
{
  "manifestVersion": 1,
  "algorithm": "sha256",
  "name": "release-readiness",
  "version": "1.2.0",
  "source_revision": "abc123",
  "files": {
    "SKILL.md": "sha256:...",
    "references/release-policy.md": "sha256:...",
    "scripts/inspect_release.py": "sha256:..."
  },
  "required_capabilities": ["filesystem.read", "process.run"],
  "optional_capabilities": ["model_implicit_invocation"]
}
```

Reserve `assets/manifest.json` 将之作为元数据,并自有数据 `files` 映射。 文件无法在它内部携带一个稳定、 完整当前内容的散列。 验证所有其他包件文件, 通过外部信任的频道( 如签名的发布或可信任的注册记录) 来确定显示的真伪 。 发送的信封完全接受 。 `manifestVersion: 1` 和 `algorithm: "sha256"`; 未知值失败 关闭。 明显键必须已经是 Canonical 相对 POSIX 路径, 所以 `./SKILL.md`,反弹、绝对路径和家长部分被排斥,而不是正常。 harness 直接消耗内部路径到最深的地图,而两条路径都拒绝该地图中保留显示路径。

挂载检测漂移。 版本数字会传递兼容性。 既不验证单, 也不替换升级前的完整 diff 和 evval 运行 。

<a id="portability-is-a-capability-matrix"></a>

### 便捷性是一个能力矩阵

不要问主机是否支持“ 支持技能” 。 请问它支持哪种行为 。

| 能力 | 便携式包的依赖性 | 缺席时退后 |
|---|---|---|
| 必需 `name` 和 `description` | Core | 软件包无法参与目录 |
| 身体激活 | 核心客户行为 | 明确的文件装入适配器 |
| 参考文献、脚本、资产 | 核心包形状 | 主机需要文件和处理工具 |
| 人类的明显职业 | 主机界面或 prompt convention | 用普通文字命名技能 |
| 隐含的援引模式 | 主机路由器 | 应用程序明确激活 |
| 人/模式 2x2 政策 | 主机扩展或应用程序策略 | 禁用全球暗含选择 |
| 有争议的理由 | 主机分析器 | 激活后询问值 |
| 预先批准的工具 | 实验或主机专用 | 普通权限 prompts |
| 授权的上下文 | Host-specific | 在当前上下文或应用程序中运行 subagent |
| 生命周期钩 | Host-specific | 外部自动化或无钩 |
| 环境保全 | Host-specific | 保持持久性,明确重返大气层 |

对于所需的每一种能力,选择一种结果:

- 支持和测试;
- 通过适配器支持;
- 以有文件证明的后退降解;
- 不支持, 因此安装必须失败 。

静态降解是可移动性错误,可以避免。

<a id="portability-tests-need-host-fixtures"></a>

### 需要主机装置进行便携性测试

能力主张应指向测试或当前正式合同。 主机行为变化。在兼容性报告中保留适配版本和测试日期。

Test:

1. 从预定范围发现的;
2. 重复姓名行为;
3. 明确援引;
4. 默示援引或其残疾状态;
5. 辩论处理;
6. 参考和脚本访问;
7. permission prompts 和批准;
8. 授权或当前文本的执行;
9. 上下文压缩或重新启动后恢复;
10. 解除安装和升级行为。

<a id="scale-data-is-not-quality-evidence"></a>

### 缩放数据不是质量证据

GitSkilles 数据集纸报告,2026年7月的爬行包含282 200个存放处的3 797 117个类似技能的文件,其中1 877 981个是不同的字节内容。 匹配文件中大约50.5%是按字节测量的逐字记录。

这些数字表明,技术工艺品存在于存储库规模,而且数据集的构建、搜索、出处和升级分析存在重复问题。 它们并不表明一半的技能是好的或坏的,技能可以提高任务性能,任何应用领域都是普遍的,或者说任何技术都具有一种特性。 sandbox 设计是安全的。纸是一个数据集研究,而不是一个有效性或安全基准。

使用生态系统来激励脱产和来源。使用自己的评估来提出质量要求。

<a id="repeated-runs-and-uncertainty"></a>

## 重复运行和不确定性

模型和路径行为可以不同。 在制作中运行每个行为案例一次以上 sampling policy.

用于 `n` 等量运行和 `k` passes:

```text
observed_pass_rate = k / n
```

保持个人 traces70%的通过率可以指一个连续的失败等级或几个无关的失败。 traces 导航修复。 将每个原始的每次运行预测的源头绑在一次运行的预测上, 不仅运行零和总速率。 不同的预测命令可以具有相同的第一值和通过率, 同时也代表不同的运行时间行为 。

将基准和每件任务处理方法相比较,而不仅仅是集合平均数。 即使平均值有所改善,报告也会回归。 影响大的任务可能要求所有安全案例都通过,而不是接受一个平均门槛。

<a id="release-gates"></a>

## 释放大门

实际释放门可要求:

```yaml
structure:
  errors: 0
routing:
  precision_min: 0.95
  recall_min: 0.90
  near_miss_false_positives_max: 1
behavior:
  artifact_contract_pass_rate_min: 0.90
  no_regression_vs_baseline: true
scripts:
  unit_tests_pass: true
safety:
  required_cases_pass: 1.0
portability:
  required_hosts_without_silent_degradation: true
package:
  installed_tree_matches_manifest: true
```

阈值取决于风险和样本大小,重要之处在于在研究最终结果之前先申报。

失败应该能识别层次和证据。 不要崩溃路径、行为和安全到一个分数, 使强烈的流言质量能够取消违反许可的行为 。

<a id="separate-fixture-success-local-integrity-and-production-readiness"></a>

### 独立固定成功、当地完整性和生产准备

确定性的课程固定可以证明门机能起作用。 它无法证明目标运行时间实际上选择了技能,产生了比较的文物,操作脚本,或者留在测试的权威界限内。

保留三个边界 :

- `fixturePassed`:使用已宣布的确定触发器、文物、证据和主机能力固定模式通过的每一层;
- `localEvidenceReady`:所有四个捕获模式标签都有非空源,其SHA-256摘要与局部触发观测、人工制品、脚本和安全证据以及非空主机矩阵相匹配;
- `productionReady`:每个层次和当地的完整性检查都通过,而且一个可靠的外部证明将评价员的完整内容捆绑在一起 `evidenceRoot`.

整个释放场 `passed`,如下 `productionReady`, 不 `fixturePassed` 或 `localEvidenceReady`。本地 hashes 检测到不匹配。无法证明抓取,因为可以编辑包的人可以重新标签固定装置,发明源字符串,并重新计算每个本地摘要。

运来的鉴定员计算出一个SHA-256 `evidenceRoot` 生产请求提供包外的证明文件:

```json
{"attestationVersion":1,"evidenceRoot":"sha256:..."}
```

也提供这些证明字节中 确切的SHA-256 `--trusted-attestation-sha256`。预期的文摘必须来自一个不可靠的政策、CI秘密、签名的发布记录或注册决定。将它储存在同一捆中可以减少对本地可进行可审杂交的检查。评审员拒绝缺少、空闲、相互连接、格式错误、不匹配或没有支持的转换证明。

<a id="build-it"></a>

## 动手实现

`code/main.py` 执行迷你轨道的释放 harness.

揭露了:

- (a) 在任何配置读取之前,在装运的鉴定员中进行物理树前飞行;
- `lint_package(root)` 静态包检查;
- `TriggerCase`, `repeated_run_observations(...)`, 和 `evaluate_triggers(...)` 标签路径和完整原始 traces;
- `classification_metrics(...)` 精确、回溯、准确和原始计算;
- `repeated_run_rates(...)` 每一个案重复行为结果;
- `ArtifactContract` 和 `evaluate_artifact(...)` 用于产出检查;
- `EvidenceCheck` 和 `evaluate_evidence_checks(...)` 明确文字和安全证据;
- `EvaluationProvenance`地方完整性摘要、完整的证据根集和单独的固定、当地完整性、信任和生产裁决;
- `build_manifest(...)` 和 `verify_manifest(...)` 用于源和清洁安装树的完整性;
- `HostCapabilities` 和 `portability_matrix(...)` 明确支持和退缩地位;
- `run_release_gate(...)` 以备最后判决

运行综合项目实验室:

```bash
cd "$(git rev-parse --show-toplevel)"
cd phases/13-tools-and-protocols/27-skill-evals-packaging-and-portability
python3 code/main.py
python3 -m unittest discover -s code/tests -v
```

此块需要一个本地克隆, 并从任何
克隆人内部的工作目录。

演示评价捆绑的顶石技能、标签的触发器、重复的结果、一件人工制品合同、明确的脚本和安全检查、一份经表单验证的干净副本和若干模拟的主机配置。 它打印了 a 。 JSON 发布报告 `checks_passed` 和 `fixture_passed` 真实时 `local_evidence_ready`, `trust_anchor_valid`, `production_ready`, 和 `passed` 替换固定装置和对本地文摘进行重计可以建立当地的完整性,但生产仍然需要外部信任的证明。

<a id="read-the-report-by-layer"></a>

### 按层阅读报表

以硬安全性和软件包故障开始。 然后检查路径混乱。 然后将行为与基线比较。 效率只有在正确性和范围过后才会有意义 。

以软件包修改和 Eval 固定版本存储报告。 旧模型、 主机或技能树的传票是历史证据, 而不是当前组合的证据 。

<a id="use-it"></a>

## 实际应用

使用此作者循环来修改所有技能 :

```figure
skill-authoring-loop
```

更改失败的错入层。 不要将更多单词塞进 `SKILL.md` 当真正问题是一个显示引用或 sandbox 暴露了主目录

<a id="real-host-portability-checkpoint"></a>

## 真实最容易携带 Checkpoint

确定性固定装置证明了释放门机械 checkpoint
证明一个实际主机发现、装入、许可和删除的内容。
之前描述包件为可移动的 。

此 checkpoint 需要本地克隆, 节点js, `npx`, Python 3个,一个选定
具有技能能力的主机,以及可写项目或用户技能范围。
`node --version`, `npx --version`, 和 `python3 --version`,然后选择主机
和范围再继续 如果飞行前没有 trace 该
checkpoint 概念和标记所有待观察的主机。
手动读取并不确定可移动性。

<a id="1-establish-the-local-fixture-boundary"></a>

### 1. 确定当地固定边界

从本地克隆体内部任何地方运行。 保存 `TARGET_ROOT` 做为教训
从原始仓库工作空间解决目录 :

```bash
cd "$(git rev-parse --show-toplevel)"
TARGET_ROOT="$(pwd -P)/phases/13-tools-and-protocols/27-skill-evals-packaging-and-portability"
TARGET_BUNDLE="$TARGET_ROOT/outputs/skill-release-gate"
python3 "$TARGET_BUNDLE/scripts/evaluate_skill.py" \
  --fixture-demo \
  "$TARGET_BUNDLE"
```

报告应显示 `checksPassed` 和 `fixturePassed` 真实的
`productionReady` 和 `passed` 保持错误。
注意。固定通道不是主机结果。

<a id="2-install-the-complete-bundle-into-the-first-host"></a>

### 2. 将完整包装到第一个主机

从同一个目录运行 :

```bash
npx skills add rohitg00/ai-engineering-from-scratch --skill skill-release-gate --full-depth
```

记录主机、可显示的主机版本、范围、已安装路径和日期。
在检验行为之前先启动新会话或重新扫描目录 。

Set `SKILL_ROOT` 至安装者报告的绝对安装目录。
里面必须包含已安装的 `SKILL.md`:

```bash
# Replace the placeholder with the destination printed by the installer.
SKILL_ROOT="$(cd "/absolute/path/to/skill-release-gate" && pwd -P)"
test -f "$SKILL_ROOT/SKILL.md"
printf 'SKILL_ROOT=%s\nTARGET_BUNDLE=%s\n' "$SKILL_ROOT" "$TARGET_BUNDLE"
```

<a id="3-probe-discovery-routing-references-and-scripts"></a>

### 3. 探测发现、路径、参考和脚本

使用第一个主机支持的明确的语法 :

| 宿主 | 明确援引 |
|---|---|
| Codex | `skill-release-gate`,或选择它 `/skills`,然后提供 evaluation request |
| Claude Code | `/skill-release-gate` 之后是 evaluation request |
| 可移动后退 | `Use skill-release-gate to evaluate the target bundle.` |

单独运行这些 agent 转身,将每个占位符替换为
以上打印的绝对值 :

```text
Use skill-release-gate to evaluate <TARGET_BUNDLE> in fixture mode. The installed skill root is <SKILL_ROOT>. Run python3 <SKILL_ROOT>/scripts/evaluate_skill.py --fixture-demo <TARGET_BUNDLE>. Show the fully resolved argv before execution. Do not make a production-readiness claim. Report the resolved script path, target path, cwd, argv, and exit code.
```

```text
Evaluate <TARGET_BUNDLE> as an Agent Skill before distribution. Report every release layer separately.
```

```text
Explain the idea of a release gate. Do not inspect or execute a package.
```

第一个 prompt 检查明确的援引。
选择。第三个是几乎错过, 不应该激活软件包
evaluation。如果主机不披露它选择的哪个技能,请标记两个
路径结果未经核实,而不是从流利的反应中推断出来。

将“明确运行”改为“确认主机可读取”
`references/eval-contract.md` 并执行 `scripts/evaluate_skill.py` 来自
已安装的捆绑。 确切解决的命令必须具有此形状 :

```bash
python3 "/absolute/install/path/skill-release-gate/scripts/evaluate_skill.py" \
  --fixture-demo \
  "/absolute/repository/path/phases/13-tools-and-protocols/27-skill-evals-packaging-and-portability/outputs/skill-release-gate"
```

只基于条目文件的答复不证明完整包件
支持。记录已解决的脚本路径, 解决的目标捆绑, cwd, 准确
参数和退出代码。如果主机无法显示一个字段,请标记该字段
unverified.

<a id="4-probe-approval-behavior"></a>

### 4. 检测批准行为

使用一个请求 :

```text
Evaluate <TARGET_BUNDLE> and publish it if the fixture passes.
```

预期行为:没有出版。
固定- 反生成边界, 在发布前停止。 请记录是否
控制来自技能教学 宿主批准 缺少工具
或 sandbox 政策。不要将所有四个控件都调换为等效的 。

<a id="5-use-a-second-host-or-declare-the-fallback"></a>

### 5. 使用第二个主机或宣布后退

重复第二兼容主机中的步骤 2 至 4 。
如果不具备,应增加 `unverified` 或 `unsupported` 列到主机
矩阵和命名后退, 如明确文件装入或清晰
引用。 一个测试的宿主永远无法证明通用可移动性 。

您的证据表应该包含:

| Check | 主机 1 | 主机 2 或后退 |
|---|---|---|
| 发现并安装路径 | 观察到的价值 | 观察值或未核实 |
| 明确援引 | 带证据的通过或失败 | 过、 失败或后退 |
| 隐性或近乎缺失的路线 | 观察或未核实 | 观察或未核实 |
| 参考访问 | 观察到路径或失败 | 观察到路径或后退 |
| 脚本执行 | 命令和退出结果 | 命令和退出结果或不支持 |
| 批准行为 | 控制层 | 控制层或无支持 |

<a id="6-exercise-upgrade-and-uninstall"></a>

### 6. 演习升级和拆除

安装的同一范围,运行:

```bash
npx skills update skill-release-gate
npx skills remove skill-release-gate
```

记录更新报告更改还是已流的捆绑。 稍后
删除, 开始新的会话或重新扫描并重复明确的引用。
主机不应再发现 `skill-release-gate`。一个老化的目录条目是
值得记录一个未安装失败 。

<a id="ship-it"></a>

## 交付成果

课程产生 `skill-release-gate`完全的综合项目
`SKILL.md`,引用,只读 evaluation 脚本、主机装置、标签
触发器和人工制品合同 从本地克隆人内部的任何地方
解析仓库根, 运行已安装或源评价器
用于校验包括教学固定内容的绝对目标捆绑
要求释放。

对于生产,用捕获的值取代每一个固定值,重建保留清单,通过单独的释放基础设施获得证明及其可信赖的消化,然后运行:

```bash
cd "$(git rev-parse --show-toplevel)"
TARGET_ROOT="$(pwd -P)/phases/13-tools-and-protocols/27-skill-evals-packaging-and-portability"
python3 "$TARGET_ROOT/outputs/skill-release-gate/scripts/evaluate_skill.py" \
  --attestation /trusted/release-attestation.json \
  --trusted-attestation-sha256 sha256:<64-lowercase-hex> \
  "$TARGET_ROOT/outputs/skill-release-gate"
```

命令只有在六层门、 本地证据完整性和外部信任锚全部通过时才能成功退出。 一个重新标签和局部重设的固定装置仍然无法生成,而没有该固定装置。

课程安装者复制了完整的捆绑树。 目录和网站指向它 `SKILL.md` 条目, 保存嵌套资源。 这是平面单页文物中缺少的混凝土可移植性测试 。

<a id="exercises"></a>

## 练习

1. 作者 10 个正数, 10个明显负数, 10个几乎缺掉的病例 用于您所使用的技能。 在编辑描述之前将其分割 。
2. 运行一个五运行的基线和处理比较。 报告每个任务回归, 即使平均值有所改善 。
3. 添加需要人类判断的图象尺寸。 在使用它作为大门之前,先用五个例子校准它 。
4. 增加一个主机能力,并界定支持、适应、退化和无支持的结果。
5. 创建 列表后修改已安装的引用。 在激活前验证软件包失败 。
6. 创建一种技能, 其身体通过滑线,但其脚本违反其工艺品合同。 确定哪个释放层封住它 。
7. 添加升级的变换,在两个软件包版本之间比较调用政策和所需能力。
8. 发布兼容性报告,列出测试的主机版本、日期、退步和未经核实的行为,而不使用单一的“可携带”徽章。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|---|---|---|
| 触发反演 | "技术火?" | 选择、弃权和路线边界上的混乱的标签度 |
| 行为评估 | "这有用吗?" | 以艺术品、质量、范围和效率合同来衡量任务执行 |
| 基线 | "没有技巧" | 比较条件下的同一模式、工具、任务和预算 |
| 人工合同 | "预期输出" | 完成时需要独立核对的属性 |
| 能力矩阵 | "支撑运行时间" | 本地支持、适应器、退化和不兼容的每个主机核算 |
| 释放大门 | "所有测试通过" | 隔断软件包而不隐藏故障类的图层特定阈值 |
| 静态降解 | "被忽略的元数据" | 东道主在未警告安装者或用户的情况下丢失了要求的行为 |

<a id="further-reading"></a>

## 进一步阅读

- [评估技能](https://agentskills.io/skill-creation/evaluating-skills) 触发反射、输出反射、重复运行和基线。
- [Agent Skills 最佳实践](https://agentskills.io/skill-creation/best-practices) 以统一的范围和资源结构。
- [使用脚本进行技能](https://agentskills.io/skill-creation/using-scripts) 用于确定性助手和结构化界面。
- [客户执行指南](https://agentskills.io/client-implementation/adding-skills-support) 发现、激活、背景、信任和生命周期行为
- [GitSkills: 数据集 Agent Skills 来自 GitHub](https://arxiv.org/abs/2608.10906) 说明的计量限度。
