# 测验 · Skill 评估、打包与可移植性（Skill Evals, Packaging, and Portability）

> **阶段 13 · 工具与协议 · 第 27 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 从真实工作流而不是话题出发 | "做一个 Kubernetes skill"不是可用范围；"诊断一个 deployment 为何不 Available、只读收集证据、产出排序的事故报告"才是：有触发边界、证据步骤、判断点、可脚本化命令、确定的产物和安全边界 |
| 2 | 判断与确定性工作分离 | 分类、排序、综合、消歧交给模型；解析、计数、校验、转换、查询类型化 API、强制不变量交给脚本/工具 |
| 3 | 按依赖顺序编写 | 产物契约 → 验证方式 → 证据工具 → 决策图 → references → 正文 → description → 运行时适配 → evals → 打包安装；先有可测系统，再写文字 |
| 4 | 六层评估 | 包结构、触发路由、指令与产物行为、脚本正确性、安全与权限、打包与可移植性；"Passing one cannot substitute for another" |
| 5 | 触发评估 | 正例、改写正例、明确负例、near miss、竞争 skill、对抗措辞；先分 dev/validation 再改 description；报告 precision/recall 时附原始计数 |
| 6 | 基线对比 | baseline 与 treatment 只差"有没有 skill"，模型、采样策略、工具、任务、预算全部固定；按任务比较，平均提升也要报告回退 |
| 7 | 产物契约 | 一组可独立检查的性质（必需字段、允许取值、证据要求、禁止副作用），让"完成"变成可执行的判断 |
| 8 | Manifest 与安装测试 | 对每个文件记 SHA-256，`assets/manifest.json` 自身排除在外；键必须是规范的相对 POSIX 路径；必须对**安装后的副本**做验证；哈希检测漂移但不认证 manifest |
| 9 | 可移植性是能力矩阵 | 不问"支不支持 skills"，而是逐项问能力：原生支持 / 适配器 / 有文档的降级 / 不支持则安装失败；静默降级是要避免的 bug |
| 10 | 三种"通过" | `fixturePassed`（教学夹具通过）≠ `localEvidenceReady`（本地摘要一致）≠ `productionReady`（还需带外可信的 attestation 绑定 `evidenceRoot`）；`passed` 跟随 `productionReady` |

### 核心技能（能动手做到）

- [ ] 为一个自己常用的 skill 设计 10 正例 + 10 负例 + 10 near miss，并先划分 dev/validation（讲义练习 1）
- [ ] 由混淆矩阵手算 precision、recall、F1，并解释"10/10 与 100/100 都是 100%，但证据强度不同"
- [ ] 写出一个产物契约，并用 `evaluate_artifact` 的"标题 + 词边界"规则判断某份产物是否通过
- [ ] 用 `build_manifest` / `verify_manifest` 证明"安装后改动 reference 会在激活前被发现"（讲义练习 5）
- [ ] 为两三个宿主填写能力矩阵，区分 native / adapter-required / unsupported，并指出哪些需求会被静默降级
- [ ] 说清 fixture → captured → attested 三个阶段的差别，以及为什么可信摘要必须"带外"提供

---

## 二、基础自测（选择题）

**Q1.** 某 skill 的触发评估中有 10 个应触发的用例和 12 个不应触发的用例。路由器在正例上触发了 9 次，在负例上误触发了 3 次。precision 和 recall 分别是：

- A. precision = 0.75，recall = 0.90
- B. precision = 0.90，recall = 0.75
- C. precision = 0.75，recall = 0.75
- D. precision = 0.82，recall = 0.90

**Q2.** 对一个 release-readiness skill，讲义所说的 **near miss** 用例最接近下面哪一个？

- A. "Can version 3.1.0 ship?"
- B. "Explain batch normalization"
- C. "Audit this tag before we publish it"
- D. "Why did the package build fail?"

**Q3.** 本节 demo 的 `KeywordRouter`（词表 `skill, package, bundle, trigger, portability, evaluate, release`，`threshold=2`）对提示 "Do not use the skill package; explain this stack trace" 的判定是：

- A. 不触发，因为提示里有否定词 "Do not"
- B. 触发，因为命中了 `skill` 和 `package` 两个词；这是一个对抗措辞造成的误触发
- C. 不触发，因为 "stack trace" 不在词表中
- D. 抛出异常，因为提示里有分号

**Q4.** 为什么 `assets/manifest.json` 要从它自己的 `files` 映射中排除？

- A. JSON 文件不需要校验
- B. 为了让 manifest 可以被任意修改而不影响校验
- C. 一个文件无法在自身内容里携带"自身完整当前内容"的稳定哈希；manifest 的真实性要靠外部可信渠道（签名发布、可信注册表）建立
- D. 因为 SHA-256 无法对 JSON 求值

**Q5.** 做 baseline 与 treatment 对比时，下列哪一项**不应该**在两组之间变化？

- A. 模型、温度/采样策略、工具集、任务夹具和预算——只有"skill 是否可用"这一项变化
- B. 只需要固定模型，工具集可以给 treatment 多开几个
- C. 只需要固定任务，模型可以换成更强的以便看出差异
- D. 什么都可以变，只要样本足够多

**Q6.** 在本课程仓库副本中实际运行 `python3 code/main.py`，下列哪项与真实输出一致？

- A. `checks_passed: true`、`fixture_passed: true`、`passed: false`，与讲义描述完全一致
- B. `checks_passed: true`、`passed: true`，因为 demo 自动生成了 attestation
- C. 程序抛出异常，因为缺少 attestation 文件
- D. `checks_passed: false`、`fixture_passed: false`：`structure` 检查失败，原因是 bundle 里多出的 `SKILL.zh.md` 和 `references/eval-contract.zh.md` 触发了 `package-depth` 与 `orphan-file`

**Q7.** 讲义说 local hashes "cannot prove capture"。原因是：

- A. SHA-256 已经被攻破
- B. 本地摘要只覆盖了部分文件
- C. 任何能编辑 bundle 的人都可以把夹具重新标成 captured、编造 source 字符串并重新计算所有本地摘要；只有绑定 `evidenceRoot` 且摘要来自带外可信渠道的 attestation 才能作为信任锚
- D. 本地摘要使用了 `ensure_ascii=False`，不可复现

**Q8.** 某宿主能加载 SKILL.md，但安装时只复制入口文件、丢掉 `references/` 和 `scripts/`，而且不给任何提示。按讲义，这属于：

- A. 原生支持（supported and tested）
- B. 静默降级（silent degradation）——可移植性要避免的 bug；应改为适配器、有文档的降级，或让安装失败
- C. 不需要处理，因为模型可以凭正文完成任务
- D. 只要 SKILL.md 能解析，就算可移植

---

## 三、动手 / 代码题

**Q9.** 讲义说 demo "prints a JSON release report with `checks_passed` and `fixture_passed` true"，但在本仓库副本中实际输出为 `false`，`lint.issues` 如下：

```text
package-depth : file is not one level deep: SKILL.zh.md
orphan-file   : SKILL.md does not directly reference 'SKILL.zh.md'
orphan-file   : SKILL.md does not directly reference 'references/eval-contract.zh.md'
```

而 `packaging.installed_tree.passed` 却是 `true`。

1. 结合 `lint_package` 的源码，解释两条规则为什么会命中。
2. 同样的 bundle，交付脚本 `outputs/skill-release-gate/scripts/evaluate_skill.py --fixture-demo` 报告 `installedTree.unexpected = ["SKILL.zh.md", "references/eval-contract.zh.md"]`，而 `main.py` 的 `installed_tree` 却通过了。为什么两者不同？`main.py` 的 `source_manifest` 检查在 demo 里有没有实际意义？
3. 给出至少两种修复方案，并说明各自的代价。

**Q10.** 观察 demo 的触发指标：

```json
"metrics": {"accuracy": 1.0, "false_negative": 0, "false_positive": 0,
            "precision": 1.0, "recall": 1.0, "true_negative": 15, "true_positive": 15}
```

demo 只有 6 个用例（3 正 3 负），`runs=5`。

1. 15 是怎么来的？这样报告原始计数有什么误导性？
2. `KeywordRouter.__call__` 中 `del run_index`，`repeated_run_rates` 的意义因此受到什么影响？
3. `classification_metrics` 先 `round(precision, 4)`，`run_release_gate` 再与阈值比较。真实召回率为 19999/25000 = 0.79996 时，在 `min_recall=0.8` 下这一项会通过吗？应如何改？

**Q11.** 阅读 `compare_artifacts`：

```python
    return {
        "baseline": baseline_result,
        "with_skill": skill_result,
        "skill_improves_pass_state": not baseline_result["passed"] and skill_result["passed"],
    }
```

`run_release_gate` 把 `artifact_improvement` 作为必过检查。

1. 如果 baseline 产物本来就满足契约（skill 只是让它更快、更省），这个 skill 能通过发布闸门吗？这与讲义 release gate 示例中的 `no_regression_vs_baseline: true` 是否一致？
2. 契约的 `forbidden_terms=("guaranteed portable",)`。产物 "Not guaranteed portable." 和 "It is Guaranteed  portable"（两个空格）分别会被判定为什么？说明了 `evaluate_artifact` 的什么局限？
3. 讲义要求"Run each behavioral case more than once"并"Compare baseline and treatment per task"。本节代码在行为层做到了吗？

**Q12.** 手推 attestation 流程。已知一次 captured 模式的评估得到 `evidence_root = "sha256:de3a…6329"`：

1. 写出 `build_external_attestation(evidence_root)` 产出的字节内容（格式）。
2. 发布基础设施要把哪两样东西交给 `run_release_gate`？其中哪一样**绝不能**和 bundle 放在一起？为什么？
3. 有人事后把某条 script check 的 evidence 文本改了，并重新计算了 `checks_digest`。`local_evidence_ready`、`trust_anchor_valid`、`passed` 分别会是什么？

---

## 四、面试高频题

**Q13.**（基础必考）一个 skill 怎样才算"做完了"？请说出六层评估分别回答什么问题，以及为什么不能把它们合成一个总分。

**Q14.**（原理深挖）如何为 skill 的触发路由设计评估集？用例类型、数据划分、指标、重复运行分别怎么做？为什么"词法模拟器"上的好成绩不能代表生产效果？

**Q15.**（工程实践）设计一个 skill 包的发布与安装校验流程：manifest 里放什么、路径如何规范化、manifest 本身如何被信任、为什么一定要在安装后的副本上验证？

**Q16.**（场景设计）你的 skill 需要随包脚本、生命周期 hook 和"委托子上下文"三项能力，要发布到三个宿主：A 全支持；B 能加载正文与 references 但不能执行脚本；C 只能把 SKILL.md 当提示词贴进去。请写出能力矩阵和每个宿主的处理方式。

**Q17.**（追问型）同事说："fixture 全绿了，可以发了吧？"你怎么回答？fixture、local integrity、production readiness 各证明了什么？

---

## 五、参考答案与解析

### Q1 — 答案：A

TP = 9，FN = 10 − 9 = 1，FP = 3，TN = 12 − 3 = 9。precision = 9 / (9 + 3) = 0.75；recall = 9 / (9 + 1) = 0.90（F1 = 2·0.75·0.9 / 1.65 ≈ 0.818，已用 Python 计算）。B 把两者弄反；D 的 0.82 是 F1，不是 precision。讲义要求"Report raw counts with the ratios"：应写成 "precision 0.75（9/12）、recall 0.90（9/10）"。

### Q2 — 答案：D

讲义表格中 "Why did the package build fail?" 是 near miss："Define the neighboring boundary"——同属发布/打包领域，但任务是排查构建失败而不是判断能否发布。A 是正例，C 是改写正例，B 是明确负例。

### Q3 — 答案：B

`KeywordRouter` 只做 `set(re.findall(r"[a-z0-9]+", prompt.lower())) & set(terms)`，命中 `skill`、`package` 两个词，达到 `threshold=2`，返回 `True`（已实际运行验证）。它完全不理解否定。这正是讲义"Adversarial wording: Do not use release-readiness; explain this stack trace"一行要测的内容，也说明"A lexical simulator ... cannot prove how a model-driven production router behaves"。D 错：分号只是分隔符，正则会忽略它。

### Q4 — 答案：C

讲义："A file cannot carry a stable hash of its complete current contents inside itself." 写入哈希会改变文件内容、进而改变哈希。代码里 `build_manifest` 跳过 `RESERVED_MANIFEST_PATH`，`verify_manifest` 遇到它出现在映射里直接报 "reserved manifest path must not be listed"。B 恰恰相反：manifest 的真实性需要外部渠道保证，而不是"随便改"。

### Q5 — 答案：A

讲义："Hold model, temperature or sampling policy, tool set, task fixtures, and budgets constant. Otherwise you cannot attribute a difference to the skill." B、C 都引入了第二个变量，无法把差异归因于 skill；D 的"样本多"解决不了混杂变量问题。

### Q6 — 答案：D

实际运行输出：`"checks_passed": false`、`"fixture_passed": false`、`"checks": {"structure": false, 其余 10 项 true}`。原因是本仓库副本的 bundle 中多了中文翻译文件：`SKILL.zh.md` 位于包根目录（深度 1，违反"恰好一层深"的 `package-depth` 规则），两个 `.zh.md` 都没有被 SKILL.md 用反引号直接引用（`orphan-file`）。我们把这两个文件从一份**副本**中删除后重跑，`checks_passed` 与 `fixture_passed` 都恢复为 `true`，51 个单元测试也全部通过（原副本中 2 个失败）。A 是讲义的描述，与本副本不符；B、C 错：demo 不提供 attestation，也不会因此报错，只是 `trust_anchor_valid` 为 `false`。

### Q7 — 答案：C

讲义："Local hashes detect mismatches. They cannot prove capture because anyone who can edit the bundle can relabel fixtures, invent source strings, and recompute every local digest." 测试 `test_relabelled_local_fixtures_need_external_trust_anchor` 演示的就是这个攻击：把 bundle 里四类数据全部改成 captured 并重算摘要，`localEvidenceReady` 变成 `true`，但没有外部 attestation 时 `productionReady` 仍是 `false`。A、D 与此无关；B 不对，`evidenceRoot` 覆盖了 triggers、artifacts、evidence、portability、manifest、thresholds、provenance 全部配置对象。

### Q8 — 答案：B

讲义："Silent degradation is the portability bug to avoid." 对每个必需能力只能选四种结果之一：supported and tested / supported through an adapter / degraded with a documented fallback / unsupported, so installation must fail。在代码里，这类宿主对应 `HostCapabilities(name, True, False, ...)`，`portability_matrix` 会标成 `adapter-required` 并列出 `companion-files` 缺失——至少把降级显式化了。

### Q9 — 参考答案

1. **两条规则**：
   - `package-depth`：`lint_package` 遍历 `root.rglob("*")`，对除 `SKILL.md` 外的每个文件要求 `len(path.relative_to(root).parts) == 2`，即必须位于 `references/`、`scripts/`、`assets/`、`evals/` 之一的**直接**子文件。`SKILL.zh.md` 在根目录，`parts` 长度为 1。
   - `orphan-file`：所有打包文件都必须出现在 `_bundle_paths(body)` 中——也就是 SKILL.md 正文的反引号代码片段里出现过的 `references/…` 等路径。`packaged_files - set(references)` 非空即报。`references/eval-contract.zh.md` 深度合法、后缀 `.md` 合法，但没被引用。
2. **差异原因**：`main.py` 的 demo 用 `manifest = build_manifest(package_root)` **在运行时现算** manifest，再 `shutil.copytree` 出安装副本，两边自然完全一致——所以 `source_manifest` 检查在 demo 里是同义反复（source 拿自己算出的 manifest 验证自己），`installed_tree` 也只验证了 `copytree` 没出错。交付脚本则读取包里**事先存好的** `assets/manifest.json`，其中没有这两个后来加入的翻译文件，于是报 `unexpected`。这也说明：只有"预先固定的 manifest + 安装后的副本"组合才真正检测漂移。
3. **修复方案**：
   - (a) 把翻译文件移出发布 bundle（例如放到 lesson 的 `docs/` 或单独的 locale 包），发布物保持单语。代价：中文用户看不到中文版 SKILL。
   - (b) 允许本地化变体：把 lint 策略扩展为允许根目录 `SKILL.<locale>.md`、在 SKILL.md 中引用 `references/eval-contract.zh.md`，并重新生成 `assets/manifest.json`。代价：改变发布策略，需要同步修改 `main.py` 与交付脚本两份 linter（测试强调两者行为要一致）。
   - (c) 在翻译流水线中跳过 `outputs/<skill>/` 目录。代价：需要改工具链，但最符合"发布物是独立软件包"的原则。

### Q10 — 参考答案

1. 指标是把**每一次运行的每一个预测**都当作一个样本：3 个正例 × 5 次 = 15 个 TP，3 个负例 × 5 次 = 15 个 TN。原始计数看起来像"30 个样本"，实际上只有 6 个不同的提示。讲义说 "Ten out of ten and one hundred out of one hundred are both 100 percent but provide different evidence"——把重复运行池化会让计数虚高，夸大证据强度。更好的报告：按用例数报告（3/3 正例、3/3 负例），重复运行单独报告每个用例的一致率。
2. `del run_index` 表示路由器不使用运行序号，结果完全确定，所以 `repeated_run_rates` 必然全部是 1.0（demo 输出 6 个用例全是 1.0）。重复运行检查只有在接入**真实的、带采样的**路由器时才有意义；在本 demo 中它只验证了"管道能跑通"。
3. 会通过：`classification_metrics` 返回 `round(0.79996, 4) = 0.8`（已实测输出 `'recall': 0.8`），`0.8 >= 0.8` 为真。应该用未取整的原始比值与阈值比较，取整只用于展示；或者直接比较整数：`tp * 10 >= 8 * (tp + fn)`。

### Q11 — 参考答案

1. **不能通过**。baseline 已通过时 `not baseline_result["passed"]` 为 `False`，`artifact_improvement` 为 `False`，`checks_passed` 为 `False`（已实测：两份都通过契约的产物得到 `skill_improves_pass_state: False`）。这与讲义 release gate 示例的 `no_regression_vs_baseline: true` 语义不同：讲义要求"不回退"，代码要求"从失败变成通过"。对于"让正确结果更高效"的 skill，代码会错误地阻止发布；更合理的检查是：with-skill 产物通过契约，并且在多个任务上逐任务满足"baseline 通过的任务，with-skill 也必须通过"（无回退），再结合讲义列出的效率维度（工具调用数、耗时、token、成本）判断是否有提升。
2. 实测：
   - "Not guaranteed portable." → `forbidden_hits: ['guaranteed portable']`，**失败**——否定句也被当成违规（假阳性）；
   - "It is Guaranteed  portable" → **通过**——多一个空格就绕过了（`re.escape` 后的模式要求恰好一个空格），这是假阴性。
   局限：契约检查是纯词法的（大小写不敏感 + 词边界），不理解语义、不做空白归一化。讲义也说 "A human or calibrated judge may assess whether the recommendation follows from the evidence"——词法检查只适合结构性要求。
3. **没有**。`compare_artifacts` 只比较**一对**产物（一个 baseline 字符串、一个 with-skill 字符串），没有多任务、没有重复运行。代码中的 `repeated_run_rates` 作用于**触发**观测，而讲义 Build It 把它描述为 "for per-case repeated behavioral outcomes"——这是讲义与代码不一致的地方。

### Q12 — 参考答案

1. 紧凑、键排序的 UTF-8 JSON：

```text
{"attestationVersion":1,"evidenceRoot":"sha256:de3a…6329"}
```

   （`separators=(",", ":")`、`sort_keys=True`、`ensure_ascii=False`，所以同一个 evidence root 永远得到同样的字节。）
2. 两样东西：`attestation_payload`（上面的字节）和 `trusted_attestation_digest`（这些字节的 SHA-256）。**可信摘要绝不能放在 bundle 里**：讲义 "Storing it in the same bundle would reduce the check to another locally recomputable hash"——攻击者既然能改 bundle，就能同时改 attestation 和它旁边的摘要。摘要应来自带外渠道：可信策略、CI secret、签名发布记录或注册表决策。交付脚本还会拒绝位于 bundle 内部、是 symlink、格式错误或版本不支持的 attestation 文件。
3. 实测：`local_evidence_ready = True`（因为攻击者重算了 `checks_digest`，本地摘要依然一致），`trust_anchor_valid = False`（issue："external attestation evidenceRoot does not match"——evidence 文本变了，`evidence_root` 随之改变，与旧 attestation 里记录的不同），`passed = False`。这正是三层分离的价值：本地一致性挡不住"改了再重算"，外部信任锚可以。

### Q13 — 参考回答要点

- **六层及其问题**：
  1. 包结构：包的形状对不对（SKILL.md、frontmatter、名称与目录、引用存在、后缀/大小、无 symlink/特殊文件、有输出契约与失败行为段落）；
  2. 触发路由：该触发时触发、不该触发时不触发、竞争 skill 之间选对；
  3. 指令与产物行为：触发后是否真的让任务变好（与 baseline 对比、满足产物契约）；
  4. 脚本正确性：脚本像普通软件一样在模型之外被单测（空输入、畸形输入、重复执行、部分状态、超时）；
  5. 安全与权限：是否待在被授予的权限内（越界路径、未声明网络、未批准的外部写、skill 循环、重复副作用）；
  6. 打包与可移植性：安装后的完整目录是否与 manifest 一致；各宿主是原生、适配还是不支持。
- **为什么不能合成总分**：讲义 "Do not collapse routing, behavior, and safety into one score that allows strong prose quality to cancel a permission violation." 安全层通常要求 100% 通过而不是平均阈值；失败报告必须指出层级和证据，才能"Change the layer responsible for the failure"。
- 加分点：代码中 `run_release_gate` 的 `checks` 是 11 个独立布尔值，`checks_passed = all(checks.values())`，体现了"逐层保留"。
- 常见误区："Markdown 看起来不错就是完成了"。

### Q14 — 参考回答要点

- **用例类型**：正例、改写正例（防止背短语）、明确负例（抓严重过触发）、near miss（定义相邻边界）、竞争 skill（目录内选择）、对抗措辞（关键词堆砌、注入 skill 名）。
- **划分**：在改 description **之前**先分好 dev / validation（重要发布再留 held-out）；只在 dev 上调 description，用 validation 判断是否泛化。
- **指标**：precision、recall、F1，并报告原始计数；对目录还要看 top-1 准确率、弃权质量、相邻 skill 之间的混淆。
- **重复运行**：生产采样策略下每个用例跑多次，保留每次 trace；按用例看通过率（`k/n`），不要只看池化后的平均；provenance 要绑定每一个原始预测（测试 `test_trigger_digest_binds_every_raw_prediction`：两组顺序不同但首值和通过率相同的预测，摘要不同）。
- **为什么词法模拟器不够**：它解释指标、发现明显重叠，但真实路由取决于宿主、模型、目录序列化方式和策略配置。讲义 "Run the labeled set through the actual host ... before claiming runtime quality." 本节 `KeywordRouter` 会把"Do not use the skill package…"判为触发（见 Q3）。
- 常见误区：先反复改 description，再"顺手"造用例——等于在测试集上调参。

### Q15 — 参考回答要点

- **manifest 内容**：`manifestVersion`、`algorithm: sha256`、name、version、source_revision、每个文件的 `sha256:<hex>`、required/optional capabilities。
- **路径规则**：键必须已经是规范的相对 POSIX 路径；`./SKILL.md`、反斜杠、绝对路径、`..` 一律**拒绝而非规范化**（代码：`raw_path != relative.as_posix()` 即拒绝）；保留路径 `assets/manifest.json` 不得出现在映射里；未知 version/algorithm fail closed。
- **构建时**：遇到 symlink 或特殊文件直接报错；空目录报错。
- **信任**：哈希只检测漂移，版本号只表达兼容性，"Neither authenticates the manifest"；真实性靠签名发布或可信注册表。
- **为什么验证安装副本**：讲义 "Testing only the source tree misses installer bugs, lost executable bits, flattened references, rewritten names, and stale files left from older versions." 代码还专门拒绝"安装目录与源目录是同一路径"的情况。
- **升级**：哈希一致不能替代"完整 diff + 重跑 evals"（讲义练习 7：比较两个版本的调用策略与所需能力）。
- 加分点：结合 Q9 说明"运行时现算 manifest"会让源校验变成同义反复。

### Q16 — 参考回答要点

| 能力 | 宿主 A | 宿主 B | 宿主 C |
|------|--------|--------|--------|
| 核心加载（name/description/正文） | 原生 | 原生 | 无加载器：用"显式文件加载"适配，或标 unsupported |
| references / assets | 原生 | 原生 | 由应用把文件内容显式拼进上下文（适配）|
| 随包脚本执行 | 原生 | 缺失 → 适配器（应用侧提供工具执行脚本）或有文档的降级（改为让用户手动运行并粘贴结果） | 同 B |
| 生命周期 hook | 原生 | 外部自动化代替或"无 hook"并在报告中声明 | 同 B |
| 委托子上下文 | 原生 | 在当前上下文执行或应用级 subagent | 同 B |

- 规则：每个**必需**能力都要落到四种结果之一；如果脚本执行是必需的且没有适配器，B、C 的安装应**失败**，而不是悄悄只装 SKILL.md。
- 代码映射：`PackageRequirements(companion_files=True, script_execution=True, runtime_extensions=("hooks", "delegated-context"))`；`portability_matrix` 会把 B 标为 `adapter-required`（缺 `script-execution`、`extension:…`），把 C 标为 `unsupported`（缺 `core-skill-loader`）。注意代码只有三种状态，没有讲义里的"degraded with documented fallback"，需要自己扩展。
- 兼容性报告要写明测试过的宿主版本、日期、适配器版本、未验证的行为，不要只贴一个 "portable" 徽章（练习 8）。

### Q17 — 参考回答要点

- **fixture 通过**：证明闸门的**机制**能工作——在声明的确定性触发、产物、证据、宿主夹具下各层都过了。它不证明真实运行时选中了 skill、产生了被比较的产物、执行了脚本、待在权限内。
- **local integrity（`localEvidenceReady`）**：四类数据都标为 captured、有非空 source，且 SHA-256 与本地内容一致。它只能发现"不一致"，不能证明"确实采集过"（能改 bundle 的人能重算）。
- **production readiness**：所有检查通过 + 本地完整性 + 外部 attestation 的 `evidenceRoot` 与本次评估一致，且 attestation 字节的摘要来自带外可信渠道。`passed` 只跟随这一项。
- 回答同事："不能发。fixture 绿只说明门禁本身没坏；要换成真实宿主采集的数据，重建 manifest，由发布基础设施出具 attestation 和可信摘要，再跑一次。"
- 加分点：讲义"Real-Host Portability Checkpoint"要求在真实宿主上记录安装路径、显式/隐式/near-miss 路由、reference 读取、脚本 argv 与退出码、审批行为、升级与卸载；拿不到的字段标 unverified，不要从流畅的回答中推断。
- 常见误区：把 `checks_passed` 当 `passed`；把本地摘要当签名。

---

## 六、关联知识点

### 前置知识
- [阶段 13 · 22 Agent Skills：可移植契约与运行时边界](../../22-skills-and-agent-sdks/docs/zh.md)：SKILL.md 结构、核心字段与运行时扩展字段的区别。
- [阶段 13 · 24 Skill Discovery 与 Progressive Disclosure](../../24-skill-discovery-and-progressive-disclosure/docs/zh.md)：references/scripts/assets 的按需加载，决定了"包必须整体安装"。
- [阶段 13 · 25 Skill Invocation 与路由](../../25-skill-invocation-and-routing/docs/zh.md)：触发评估所测的路由行为。
- [阶段 13 · 26 Skill 权限、Sandboxes 与信任](../../26-skill-permissions-sandboxes-and-trust/docs/zh.md)：安全层评估的内容来源。
- [阶段 11 · 10 Evaluation 与 LLM 应用测试](../../../11-llm-engineering/10-evaluation/docs/zh.md)：基线对比、重复运行与评估集划分的通用方法。
- [阶段 02 · 09 模型 Evaluation](../../../02-ml-fundamentals/09-model-evaluation/docs/zh.md)：precision、recall、F1 与混淆矩阵。

### 本节被哪些后续内容用到
- [阶段 13 · 28 MCP Tool Contracts 与内容](../../28-mcp-tool-contracts-and-content/docs/zh.md)：从 skill 的产物契约走向 MCP 工具的输入/输出契约。
- [阶段 13 · 30 MCP 注册表供应链：准入、漂移与 Rollback](../../30-mcp-registry-supply-chain-and-drift/docs/zh.md)：manifest、漂移检测与可信注册表。
- [阶段 13 · 31 MCP 一致性工程：版本管理、证据与运维](../../31-mcp-conformance-versioning-and-operations/docs/zh.md)：证据绑定与版本兼容。
- [阶段 14 · 30 评估驱动的 Agent 开发](../../../14-agent-engineering/30-eval-driven-agent-development/docs/zh.md)：把评估闸门放进 agent 的开发循环。
- [阶段 19 · 27 使用固定测试任务的评估 Harness](../../../19-capstone-projects/27-eval-harness-fixture-tasks/docs/zh.md)：fixture 任务驱动的评估 harness。

### 延伸关键词
`trigger eval` · `near miss` · `precision / recall / F1` · `dev / validation / held-out` · `paired baseline` · `artifact contract` · `SHA-256 manifest` · `SLSA provenance` · `in-toto attestation` · `capability matrix` · `silent degradation` · `release gate`
