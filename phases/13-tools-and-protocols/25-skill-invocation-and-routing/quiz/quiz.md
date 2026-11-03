# 测验 · Skill Invocation 与路由（Skill Invocation and Routing）

> **阶段 13 · 工具与协议 · 第 25 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 调用 = 授权决策 + 相关性决策 | "A good description helps the model choose; a good policy decides whether that choice is allowed." |
| 2 | 五个启动通道 | 人类用户（显式点名）、模型/自主 agent（从目录选择）、应用（运行时预加载）、另一个技能或 subagent（组合）、评测 harness（固定场景下按名激活）；各有主要风险 |
| 3 | 五个调用阶段 | Eligible（策略允许该 actor 请求）→ Selected（被点名或被判定相关）→ Activated（指令进入上下文）→ Executing（开始工作）→ Completed（输出通过独立检查）；只记 `skill_used=true` 会掩盖失败位置 |
| 4 | 人类 × 模型 2×2 矩阵 | 共享 / 仅人类 / 仅模型 / 禁用或仅应用；这是策略模型，不是标准 YAML |
| 5 | 宿主字段的反直觉语义 | 某宿主中 `user-invocable: false` 只去掉用户直接调用，模型仍可选；`disable-model-invocation: true` 只去掉模型选择，用户仍可显式调用；另一宿主用 `agents/openai.yaml` 的 `allow_implicit_invocation: false` |
| 6 | 显式调用是"身份优先" | 直接给出技能名，但仍要经过策略——点名不能绕过权限、工作区约束、审批与隔离 |
| 7 | 隐式调用是"描述优先" | description 就是路由接口；好的描述含能力、输出、正向边界、负向边界 |
| 8 | 路由是带弃权的分类 | 选择要越过阈值并胜过竞争者，证据弱就弃权；高影响技能宜用仅人类策略 |
| 9 | 资格先于排序 | 先按 actor 与宿主适配器过滤，再只对合格候选打分；被禁止的最高分候选不能"选中后再拒绝" |
| 10 | 评测要有 near miss；参数有三种表示 | 正例测召回、明显负例测基本精度、near miss 测边界；参数经过宿主解析 → 技能绑定 → 工具 schema 三道边界，不能把原始参数插进 shell |

### 核心技能（能动手做到）

- [ ] 用 `InvocationPolicy` + `CorePolicyAdapter` / `ExtensionPolicyAdapter` 为六种 actor 写出允许/拒绝决策，并解释每个 `reason`
- [ ] 手算 `relevance_score` 的 Jaccard 相似度，预测隐式路由的选择与是否越过阈值
- [ ] 解释 demo 中扩展适配器为什么把"draft release notes"路由到了 `release-readiness`，并判断这是否是期望行为
- [ ] 给路由器加入"前两名差距过小则询问用户"的歧义处理
- [ ] 用宿主维护的调用链检测技能组合的环与深度，而不是信任请求自报的 `caller_name` / `depth`
- [ ] 设计一组包含正例、负例、near miss 的路由评测，并说出 core 与 extension 适配器结果差异的含义

---

## 二、基础自测（选择题）

**Q1.** 在定义了该字段的宿主中，给技能加上 `user-invocable: false` 的效果是：

- A. 技能被完全禁用，任何人都无法使用
- B. 模型不能再隐式选择这个技能
- C. 技能变成可移植的"私有技能"，所有宿主都会隐藏它
- D. 去掉用户直接调用（如命令菜单），但模型仍可以根据描述选择它

**Q2.** 2×2 矩阵中 "human = Yes, model = No" 这一格，讲义给出的合适例子是：

- A. 代码解释、测试计划、文档审阅
- B. 发布准备、计费导出、破坏性清理计划
- C. 内部风格指南、领域参考、自动支持流程
- D. 灰度发布中的技能、已弃用的包

**Q3.** 讲义例子：`incident-triage` 得分 0.80 但宿主扩展禁止了模型调用；`incident-review` 得分 0.55 且允许。正确的路由行为是：

- A. 把 `incident-triage` 移出候选集，在剩余合格候选中评估 `incident-review`，若其越过阈值则选中
- B. 选中 `incident-triage`，发现被禁止后拒绝并停止
- C. 两者都激活，让模型自行决定
- D. 因为最高分被禁止，整个请求弃权

**Q4.** 已知 `_tokens` 用正则 `[a-z0-9]+` 取小写 token 集合，`relevance_score` 为 Jaccard 相似度（交集大小 / 并集大小，技能侧 token 来自 `name + description`）。查询 `"triage this incident timeline evidence"` 对技能 `incident-triage`（描述 `"Triage an incident timeline and separate evidence from hypotheses."`）的得分是：

- A. 0.8
- B. 0.4444
- C. 0.4
- D. 0.5

**Q5.** `InvocationRequest(Actor.MODEL, "x", explicit_name="release-readiness")` 交给 `route_request`，结果是：

- A. 按名字直接激活，score 为 1.0
- B. 拒绝，原因是隐式的模型/agent 路由使用任务相关性，而不是精确名字通道
- C. 忽略名字，照常按相关性路由
- D. 抛出 `TypeError`

**Q6.** 使用**默认** `InvocationPolicy()` 的 `CorePolicyAdapter`，应用（`Actor.APPLICATION`）按名请求 `release-notes`：

- A. 激活，因为 `allow_application` 默认为 True
- B. 激活，但 mode 为 `explicit-human`
- C. 拒绝，原因是缺少 caller 身份
- D. 拒绝，原因是 `application_allowlist` 默认为空元组，目标不在白名单里

**Q7.** 技能的 `runtime_extensions` 为 `{"disable-model-invocation": "yes"}`，用 `ExtensionPolicyAdapter` 做模型隐式路由（查询与描述高度相关）。结果是：

- A. 激活——适配器只识别布尔 `True` 或不区分大小写的字符串 `"true"`，`"yes"` 不被识别，等于没写
- B. 拒绝——任何非空值都视为禁用
- C. 抛出 `ValueError`，提示取值非法
- D. 拒绝——`"yes"` 被解析为 True

**Q8.** 讲义强调路由评测要包含 near miss（近似负例）。它的作用是：

- A. 证明技能在明显相关的请求上能被选中（召回）
- B. 证明完全无关的请求不会触发（基本精度）
- C. 暴露边界质量：与技能共享词汇、实际属于另一工作流的请求是否被误路由
- D. 测量模型调用的延迟

---

## 三、动手 / 代码题

**Q9.** demo 中有三个技能（`incident-triage`；`release-notes`，带 `{"user-invocable": True, "disable-model-invocation": True}`；`release-readiness`，描述为 "Review merged pull request summaries and report release readiness."），策略 `model_threshold=0.15`。对模型请求 `"draft release notes from merged pull requests"`，实际输出为：

```text
core_decisions:      activated=true  skill_name=release-notes      score=0.6667
extension_decisions: activated=true  skill_name=release-readiness  score=0.2308
```

1. 手算两个分数（列出 token 集合）。
2. 讲义把扩展适配器的这条结果描述为"a blocked top lexical match being removed before an eligible alternative is ranked"。从产品角度看，这个结果对吗？
3. 给出至少两种改进，使这类请求不会被误路由到"邻居"技能。

**Q10.** 下列四个探测都是实际运行结果。指出每个暴露的问题，并给出修复建议。

```python
# (a) 两个描述相同的技能
route_request((SkillMetadata("alpha-skill", "Summarize logs."),
               SkillMetadata("zulu-skill",  "Summarize logs.")),
              InvocationRequest(Actor.MODEL, "summarize logs"),
              CorePolicyAdapter(InvocationPolicy(model_threshold=0.1)))
# -> activated=True, skill_name='zulu-skill', score=0.5

# (b) 阈值为 0
route_request((release_readiness,), InvocationRequest(Actor.MODEL, "translate a poem"),
              CorePolicyAdapter(InvocationPolicy(model_threshold=0.0)))
# -> activated=True, skill_name='release-readiness', score=0.0

# (c) 讲义自己的正例
relevance_score("Is version 2.4.0 ready to publish?", release_readiness)
# -> 0.0

# (d) 两个技能互相调用
# policy: allow_skill=True, skill_caller_allowlist=("release-readiness", "security-change-review"), max_skill_depth=2
InvocationRequest(Actor.SKILL, "", explicit_name="release-readiness",
                  caller_name="security-change-review", depth=2)
# -> activated=True
```

**Q11.** （讲义练习 4）给隐式路由加入歧义处理：写 `route_with_margin(skills, request, adapter, margin=0.1)`，当**合格**候选的前两名得分差小于 `margin` 时，返回 `activated=False`、`mode="ask"`。说明在 Q10(a) 和"triage this incident timeline evidence"两种请求上的结果。

**Q12.** （讲义练习 5）现有实现只检测"直接自环"（caller 等于 target），且 `caller_name`、`depth` 都由请求方自报。请写 `route_composed(skills, target, chain, adapter)`，其中 `chain` 是**宿主记录**的调用栈（如 `("release-readiness",)`），要求：检测任意长度的环；深度由 `len(chain)` 推出。给出 A→B、A→B→A 两种情况的结果。

---

## 四、面试高频题

**Q13.**（基础必考）显式调用和隐式调用有什么区别？除了这两种，还有哪些通道会启动一个技能？各自的主要风险是什么？

**Q14.**（原理深挖）为什么必须"先资格过滤、后相关性排序"？如果反过来会出什么问题？阈值和弃权在路由里扮演什么角色？

**Q15.**（工程实践）请为一个 `release-readiness` 技能设计路由评测集与指标。你会如何利用 core 与 extension 两种适配器的差异？

**Q16.**（场景设计）讲义开头的事故：`database-migration` 技能在用户只问一般数据库问题时被模型选中，并提出了 schema 变更。你会如何从描述、调用策略、执行权限三个层面修复？

**Q17.**（追问型）"技能被激活了，所以它描述里提到的脚本和工具就可以执行了。"这句话哪里不对？用户传入的参数又该怎么处理？

---

## 五、参考答案与解析

### Q1 — 答案：D

讲义："`user-invocable: false` does not mean 'the model cannot use this.' It removes direct user invocation in the host that defines it." 对应 2×2 矩阵中的"仅模型"一格。A 混淆了"隐藏"与"禁用"；B 是 `disable-model-invocation: true` 的效果；C 错在宿主字段不可移植——"Unknown hosts may ignore them"。代码中 `ExtensionPolicyAdapter` 对 `Actor.HUMAN` 检查 `user-invocable` 是否为假，对模型则不检查它。

### Q2 — 答案：B

讲义矩阵："Yes / No — Human-only — Publish preparation, billing export, destructive cleanup plan"。A 是 Shared（双 Yes）；C 是 Model-only；D 是 Disabled or application-only。高影响、误触发代价大的技能适合仅人类：讲义"Use human-only policy when the cost of a false positive exceeds the convenience of automatic selection."

### Q3 — 答案：A

讲义："The router should evaluate `incident-review` as the best eligible candidate. It should not choose `incident-triage`, deny it, and stop." B 正是被批评的"先排序再检查"；C 违反只选一个的路由语义；D 混淆了"最高分不合格"与"无合格候选"。测试 `test_implicit_routing_ranks_only_eligible_candidates` 固定了这一行为。

### Q4 — 答案：C

查询 token：`{triage, this, incident, timeline, evidence}`（5 个）。技能 token：`incident-triage` 拆成 `incident`、`triage`，描述贡献 `triage, an, incident, timeline, and, separate, evidence, from, hypotheses`，去重后为 `{incident, triage, an, timeline, and, separate, evidence, from, hypotheses}`（9 个）。交集 `{triage, incident, timeline, evidence}` = 4，并集 = 5 + 9 − 4 = 10，得分 0.4。实际 demo 输出这一条的 `score` 正是 `0.4`。A 是讲义例子里的假想分数；B 是 4/9（只用技能侧做分母）；D 是 5/10 之类的误算。

### Q5 — 答案：B

`route_request` 中，MODEL 与 AGENT 不在 `explicit_modes` 里，走隐式分支；分支开头 `if request.explicit_name:` 直接返回拒绝，reason 为 "implicit model or agent routing uses task relevance rather than an exact-name channel"（实测）。这让"按名调用"只属于人类、应用、技能、harness 四个通道，避免模型借名字绕过相关性与阈值。

### Q6 — 答案：D

`CorePolicyAdapter.allows` 对 APPLICATION 要求 `allow_application and skill.name in application_allowlist`；默认 `application_allowlist=()`，所以实测 reason 为 "blocked by application activation policy and target allowlist"。A 只看到了布尔开关；B 的 mode 应为 `programmatic-application`；C 是技能组合通道的条件。harness 通道同理：默认空白名单即拒绝（测试 `test_empty_harness_allowlist_denies_programmatic_activation`）。

### Q7 — 答案：A

`_extension_true(value)` 只在 `value is True` 或字符串小写后等于 `"true"` 时为真。实测 `"yes"` → 激活（score 0.6667），而 `"TRUE"` → 拒绝。这是一个 **fail-open（失败即放行）** 的设计：拼写不规范的禁用标记会被当作"没有禁用"。更安全的适配器应对已识别字段的**未知取值**报错或按拒绝处理。C 是更安全的做法但不是本实现；B、D 与代码不符。

### Q8 — 答案：C

讲义："Positive cases prove recall… Clear negatives prove basic precision… Near misses expose boundary quality… A routing set made only of obvious positives and unrelated negatives will overstate quality." A 是正例的作用，B 是明显负例的作用，D 与路由质量无关。讲义例子："Why did today's package build fail?" 共享 package、build 词汇但属于 `build-diagnostics`。

### Q9 — 参考答案

1. 查询 token：`{draft, release, notes, from, merged, pull, requests}`（7 个；注意是复数 `requests`）。
   - `release-notes`：`{release, notes, draft, from, merged, pull, request, summaries}`（8 个）。交集 `{draft, release, notes, from, merged, pull}` = 6；并集 = 7 + 8 − 6 = 9；得分 6/9 = **0.6667**。`requests` 与 `request` 因为没有词形还原而不匹配。
   - `release-readiness`：`{release, readiness, review, merged, pull, request, summaries, and, report}`（9 个）。交集 `{release, merged, pull}` = 3；并集 = 7 + 9 − 3 = 13；得分 3/13 = **0.2308**。
2. 不对。用户要的是"起草 release notes"，而 `release-notes` 被宿主扩展设为不允许模型调用（仅人类）。"资格先于排序"这条原则只保证被禁止的技能不会被选中，并**不保证**剩下的最高分就是合适的技能；0.2308 只是因为共享了 `release`、`merged`、`pull` 三个词，而阈值 0.15 又很低。结果是一个"发布就绪审查"技能被用来回答"写发布说明"的请求——这正是讲义开头 `database-migration` 事故的同类问题（误路由到邻近技能）。讲义自己也说明 lexical 路由器"exists to make policy boundaries inspectable, not to claim that lexical matching reproduces production model routing"。
3. 改进：
   - **提高阈值或加歧义边际**：0.2308 与理想匹配差距很大，但在"被过滤后"没有可比较的对象；可以记录**被过滤掉的最佳候选分数**，若被过滤者明显更相关（如 0.67 对 0.23），则弃权并提示"该技能需要显式调用：`/release-notes`"。
   - **负向边界**：在 `release-readiness` 的描述里写"do not use for drafting release notes"，并在路由器中对负向边界计分（讲义 score 公式中的 `exclusion_match`）。
   - **near-miss 评测**：把这条请求作为 `release-readiness` 的 near miss 固定进评测集，期望结果为"弃权"或"ask"。
   - **词形归一**：至少做简单的复数还原，避免 `requests`/`request` 这种无关差异影响分数（只是让玩具路由器更合理，不能替代真实评测）。

### Q10 — 参考答案

- **(a) 平局按名字逆序**：`max(scored, key=lambda item: (item[0], item[1].name))` 在分数相同时选名字**最大**的，所以 `zulu-skill` 胜出。这是确定的，但与讲义"ambiguity penalty / abstain"的思想相反：完全相同的分数正说明存在歧义。修复：加入歧义边际，平局或差距过小时返回 `ask`（Q11）。
- **(b) 阈值 0 允许零分激活**：`InvocationPolicy` 接受 `0.0 <= threshold <= 1.0`，`score < threshold` 对 0 不成立，于是与请求毫无关系的技能也被激活。修复：要求 `score > 0`（或阈值下限大于 0），并对"所有分数为 0"直接弃权。顺带：在未激活的决策里，`skill_name` 是"最佳"候选——全为 0 分时它只是名字最大的那个，日志中容易被误读。
- **(c) 词汇路由对正例失灵**：讲义的正例 "Is version 2.4.0 ready to publish?" 与 `release-readiness` 没有任何共同 token（`ready` ≠ `readiness`，`publish` 不在描述里），得分 0。这说明 Jaccard 只能用来演示策略边界，不能当作路由质量的证据；真实评测要用宿主实际的模型路由。改进描述：加入 "Use when the user asks whether a version… is ready to publish"（讲义推荐的 bounded description 正是这样写的）。
- **(d) 两技能环未被检测**：`CorePolicyAdapter` 只检查 `caller_name == skill.name`（直接自环）。A 调 B、B 再调 A 时，caller 是 B、target 是 A，二者不同，caller 在白名单里，depth=2 不超过上限，于是被允许（实测 depth=1 也同样被允许）。更根本的问题是 `caller_name` 与 `depth` 都是**请求方自报**的：任何构造请求的代码都可以声称自己是 `release-readiness`、深度为 1。修复：由宿主维护调用栈，从栈推导 caller 与深度，并检测栈中是否已出现目标（Q12）。

### Q11 — 参考答案

```python
def route_with_margin(skills, request, adapter, margin=0.1):
    decision = route_request(skills, request, adapter)
    if request.actor not in {Actor.MODEL, Actor.AGENT} or not decision.activated:
        return decision
    eligible = [s for s in skills if adapter.allows(s, request.actor, request)[0]]
    scores = sorted((relevance_score(request.query, s) for s in eligible), reverse=True)
    if len(scores) > 1 and scores[0] - scores[1] < margin:
        return InvocationDecision(False, request.actor, decision.skill_name, "ask",
                                  decision.score,
                                  f"top two eligible scores within {margin}: ask the user")
    return decision
```

实测：

- Q10(a)：原实现选 `zulu-skill`；新实现返回 `activated=False, mode="ask"`，reason 为 "top two eligible scores within 0.1: ask the user"。
- "triage this incident timeline evidence"（候选 `incident-triage` 0.4、`release-notes` 0）：差距 0.4 ≥ 0.1，照常激活 `incident-triage`。

要点：边际只在**合格候选**之间比较（与"资格先于排序"一致）；只对隐式通道生效，显式通道不需要；`ask` 是一种独立的结果，不是激活也不是简单的弃权，日志里要能区分。生产中还可以把边际设计成相对值（如 `scores[1] / scores[0] > 0.8`）。

### Q12 — 参考答案

```python
def route_composed(skills, target, chain, adapter):
    """chain 是宿主记录的调用栈，不信任请求自报的 caller/depth。"""
    if target in chain:
        return InvocationDecision(False, Actor.SKILL, target, "composed-skill", 0.0,
                                  f"composition cycle: {' -> '.join(chain + (target,))}")
    request = InvocationRequest(Actor.SKILL, "", explicit_name=target,
                                caller_name=chain[-1], depth=len(chain))
    return route_request(skills, request, adapter)
```

在策略 `allow_skill=True, skill_caller_allowlist=("release-readiness", "security-change-review"), max_skill_depth=2` 下实测：

- A→B：`route_composed(..., "security-change-review", ("release-readiness",), ad)` → `activated=True`，reason "skill caller allowlist and depth policy"。
- A→B→A：`route_composed(..., "release-readiness", ("release-readiness", "security-change-review"), ad)` → `activated=False`，reason "composition cycle: release-readiness -> security-change-review -> release-readiness"。
- 栈长度为 3 时（超过 `max_skill_depth=2`）→ "blocked by skill composition depth limit"。

要点：环检测用"目标是否已在栈中"，对任意长度都有效；深度由栈长度推出，不可伪造；caller 取栈顶。讲义要求组合请求还应带"bounded task、expected response contract、reason、fallback"，可以把这些字段加进请求并在拒绝时返回给调用方的技能，让它执行"不可用时停止并报告"。

### Q13 — 参考回答要点

- **显式（identity-first）**：调用者直接给出技能身份，如 `/release-readiness v2.4.0` 或在请求中写技能名；语法、菜单可见性、参数展开由宿主决定。仍要过策略。
- **隐式（description-first）**：模型只看到目录元数据，按描述判断相关性；描述就是路由接口。
- **五个通道及风险**（讲义表）：
  - 人类用户——期望宿主并未授予的可用性或权限；
  - 模型 / 自主 agent——假阳性路由；
  - 应用——与某个宿主的隐性耦合；
  - 另一个技能或 subagent——环、缺失依赖、上下文渗漏；
  - 评测 harness——测试时意外绕过了被研究的生产策略。
- 加分点：本节代码把它们映射为 `explicit-human`、`implicit-model`、`implicit-agent`、`programmatic-application`、`composed-skill`、`programmatic-harness` 六种 mode，并说明为什么 harness 按名激活（隔离路由方差，使重复运行可比，课程 quiz.json 也这样解释）。

### Q14 — 参考回答要点

- **原因**：讲义——"A blocked top match would incorrectly prevent an eligible lower-scored candidate from being considered." 先排序再检查，会出现"最高分被拒 → 整体失败"；而且策略变化会改变相关性分数的含义。"Eligibility defines the selection set. Relevance ranks that set."
- **顺序**：按 actor 与宿主适配器过滤 → 只给合格候选打分 → 超过阈值且满足歧义规则才选中 → 否则弃权。
- **阈值与弃权**：路由是"带弃权选项的分类"；证据弱时弃权比硬选一个更安全。
- **但要警惕**（加分点）：资格过滤后的"次优"候选不一定相关——见 Q9，demo 中被禁止的 `release-notes` 被换成了不相关的 `release-readiness`。成熟的做法是同时记录"被过滤的最佳候选"，必要时弃权并提示显式调用。
- 常见误区：用一个布尔 `invocable` 表达全部语义——讲义："'User can see it,' 'model can select it,' 'application can preload it,' and 'tools inside it can execute' are separate facts."

### Q15 — 参考回答要点

- **数据集**：
  - 正例（召回）："Is version 2.4.0 ready to publish?"、"Can we tag v3.1 today?"……
  - 明显负例（基本精度）："Explain rotary position embeddings."
  - near miss（边界）："Why did today's package build fail?"（属于 build-diagnostics）、"Draft release notes for 2.4.0"（属于 release-notes，见 Q9）、"Bump the version in pyproject"……讲义练习 3 要求为部署技能写十条 near miss。
  - 每条标注期望技能或 `null`（弃权），歧义样本可标注 `ask`。
- **指标**：混淆矩阵、每个技能的 precision / recall、弃权率；重复运行的稳定性（同一 prompt 多次路由结果是否一致）——讲义 Ship It："Use the labeled positive and near-miss design in Lesson 27 to compute confusion counts, precision, recall, and repeated-run stability."
- **core vs extension**（讲义练习 6）：用同一标注集分别跑两种适配器，**逐条解释每个变化**；变化应只来自被识别的宿主字段（如 `disable-model-invocation`），并检查"被禁止技能的请求是否被转给了不相关的邻居"。
- **harness 注意**：评测路由时不要用 harness 按名激活——那会绕过被测的路由策略（讲义五通道表中 harness 的风险）。
- 加分点：把评测接入 CI，描述的每次修改都要重跑；单条 CLI 只是"policy probe"，不是完整评测。

### Q16 — 参考回答要点

- **描述**：从"Helps with databases"类的弱描述改为有边界的描述：能力（为已确定的 schema 变更生成迁移计划）+ 正向边界（用户明确要求修改 schema / 生成迁移）+ 负向边界（"do not use for explaining database concepts or query tuning"）。用 near miss（"为什么这个索引慢？"）验证。
- **调用策略**：高影响技能设为仅人类（某宿主用 `disable-model-invocation: true`，Codex 用 `allow_implicit_invocation: false`），通过适配器实现并测试；在不识别该字段的宿主中，要有可移植的退路（例如在 body 第一步要求用户确认意图）。
- **执行权限**：即使被激活，生成迁移、执行 DDL 都要经过宿主权限与审批；迁移脚本以参数向量调用而不是拼 shell；写操作带幂等键，恢复时不重复执行（讲义 "Context lifecycle" 示例）。
- **可观测**：trace 中分别记录 eligible、selected、activated、executing、completed，才能看出事故发生在"误选"还是"误执行"。
- 加分点：讲义提醒，`user-invocable: false` 不会阻止模型选择该技能，`disable-model-invocation: true` 也不会让技能彻底消失（用户仍可显式调用）——字段语义要逐个核对，想"既不让模型选、也不让人随手点"需要两个字段配合或宿主的其他机制。

### Q17 — 参考回答要点

- **激活 ≠ 授权**：随包 SKILL.md："Activation loads instructions. It does not approve tools, filesystem changes, network access, secret use, or bundled scripts." 讲义："Naming a skill should not bypass missing permissions, workspace constraints, approval gates, or runtime isolation." 课程 quiz.json 的结论："Route activation through host policy, then review each requested action under the permission model."
- **阶段区分**：Activated（指令进入上下文）与 Executing（开始工具/模型工作）是两个阶段，执行要在权限模型下逐动作审查；Completed 还需独立检查。
- **参数**：跨越"宿主解析 → 技能绑定 → 指令校验 → 工具 schema 再校验"多道边界；"Do not interpolate raw arguments into shell commands. Prefer a script invoked with an argument vector or a typed MCP tool." 例如 `v2.4.0; rm -rf ~` 不能进入 `bash -c`。
- **上下文生命周期**：工具许可可能只持续一轮，而指令留得更久；不要依赖不可见的生命周期假设，把持久结果写入文件或类型化状态，恢复时重新校验。
- 加分点：引出第 26 节——权限（permission）、沙箱（sandbox）、信任（trust）三者的区别。

---

## 六、关联知识点

### 前置知识
- [阶段 13 · 22 Agent Skills：可移植契约与运行时边界](../../22-skills-and-agent-sdks/docs/zh.md)：宿主扩展字段为何不属于便携核心。
- [阶段 13 · 24 Skill Discovery 与 Progressive Disclosure](../../24-skill-discovery-and-progressive-disclosure/docs/zh.md)：路由的输入——目录元数据从哪里来、怎样受预算约束。
- [阶段 13 · 05 工具 Schema 设计：命名、描述与 Parameter 约束](../../05-tool-schema-design/docs/zh.md)：描述即路由接口，与工具描述的写法相通。
- [阶段 13 · 21 LLM 路由层：LiteLLM、OpenRouter、Portkey](../../21-llm-routing-layer/docs/zh.md)：另一种"路由"——在模型提供商之间选择，可对比两者的策略与相关性分离。

### 本节被哪些后续内容用到
- [阶段 13 · 26 Skill 权限、Sandboxes 与信任](../../26-skill-permissions-sandboxes-and-trust/docs/zh.md)：激活之后的执行权限与隔离。
- [阶段 13 · 27 Skill 评估、打包与可移植性](../../27-skill-evals-packaging-and-portability/docs/zh.md)：用标注的正例与 near miss 计算混淆矩阵、precision、recall 与稳定性。
- [阶段 14 · 16 OpenAI Agents SDK：Handoffs、Guardrails 与追踪](../../../14-agent-engineering/16-openai-agents-sdk/docs/zh.md)、[阶段 14 · 17 将 Harness 封装为库：Subagents 与会话存储](../../../14-agent-engineering/17-claude-agent-sdk/docs/zh.md)：handoff 与 subagent 作为"技能组合"在 SDK 中的对应物。
- [阶段 14 · 30 评估驱动的 Agent 开发](../../../14-agent-engineering/30-eval-driven-agent-development/docs/zh.md)：把路由评测纳入开发循环。
- [阶段 14 · 27 Prompt Injection 与 PVE 防御](../../../14-agent-engineering/27-prompt-injection-defense/docs/zh.md)：参数与上下文作为攻击面。
- [阶段 17 · 16 将模型路由作为降低成本的基本手段](../../../17-infrastructure-and-production/16-model-routing/docs/zh.md)：生产中的路由与阈值设计。

### 延伸关键词
`explicit invocation` · `implicit invocation` · `user-invocable` · `disable-model-invocation` · `allow_implicit_invocation` · `eligibility before ranking` · `abstention` · `ambiguity margin` · `near miss / hard negative` · `Jaccard similarity` · `skill composition depth` · `cycle detection` · `fail-open vs fail-closed` · `argument vector`
