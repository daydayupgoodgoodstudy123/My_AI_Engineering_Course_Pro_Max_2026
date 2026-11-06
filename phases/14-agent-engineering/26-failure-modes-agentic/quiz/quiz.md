# 测验 · 失效模式：Agents 为什么会失败（Failure Modes: Why Agents Break）

> **阶段 14 · Agent 工程 · 第 26 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | MASFT | Berkeley 2025（arXiv:2503.13657）的多 Agent 失效分类：14 种失效模式、3 大类，标注者间 Cohen's Kappa 0.88，说明类别可被可靠区分 |
| 2 | MASFT 的核心论断 | 多 Agent 失效是**系统设计缺陷**，不是靠换更强的基座模型就能消除的 LLM 局限 |
| 3 | Microsoft 失效分类 | 已有的 AI 失效（bias、hallucination、数据泄露）在 agentic 场景被**放大**；自主性还带来新失效：规模化的意外行动、工具滥用、任务漂移（mission drift） |
| 4 | Agent 幻觉的两种表现 | Instruction-following Deviation（不遵守 system prompt）与 Long-range Contextual Misuse（遗忘/误用早期上下文）；sub-intention 错误分 Omission（漏步）、Redundancy（重复步）、Disorder（乱序） |
| 5 | 五种行业高发模式 | hallucinated actions（调用不存在的工具/编造参数）、scope creep（越权多做）、cascading errors（一错连锁）、context loss（忘了早期约束）、tool misuse（对的工具错的参数或错的工具） |
| 6 | 级联错误为何最致命 | Agent 分不清"我失败了"和"任务做不到"，常在 400 错误后**幻觉出成功消息**来结束循环；讲义例子：一个幻影 SKU 触发 4 次下游 API 调用，演变成多系统事故 |
| 7 | 缓解：每一步都设 gate | 逐步安全分类器、工具参数校验、对照已知事实交叉核验（CRITIC）、重新探测环境状态以识破 success hallucination |
| 8 | 监控的三个误区 | 只标记崩溃（多数失效输出"看起来正常"）、没有基线（无法判断漂移）、过度告警（应聚类与限流） |
| 9 | 基于签名的检测器 | 本节代码对 trace 做纯规则匹配：未知工具名、无写意图却写文件、错误后仍有 ≥2 个调用、违反 "do not" 约束、缺必填参数、声称成功但状态未变 |
| 10 | 检测器本身也会出错 | 本节 `detect_context_loss` 取 "do not" 后的**动词**去匹配参数，导致 t005 漏报；关键词子串匹配还有误报与两套词表不一致的问题 |

### 核心技能（能动手做到）

- [ ] 说出五种行业高发失效模式，并为每种给出一个可落地的缓解手段
- [ ] 读懂 `Trace` / `TraceStep` 数据结构，手推任意一条 trace 会被打上哪些标签
- [ ] 找出 `detect_context_loss` 的漏报原因并改写成按路径/对象匹配的版本
- [ ] 实现"cascade radius"（级联半径）指标和"错误后仍声称成功"的检测器
- [ ] 设计一个生产级的失效监控流水线：规则检测器 + 抽样 LLM 评审 + 基线漂移 + 聚类告警 + PII 脱敏
- [ ] 把检测器接进 CI：某模式的标记率 ≥ 5% 时让构建失败（讲义练习 5）

---

## 二、基础自测（选择题）

**Q1.** 关于 MASFT（Multi-Agent System Failure Taxonomy），下列说法与讲义一致的是：

- A. 它把失效分成 5 大类、共 30 种模式
- B. 它的结论是：只要基座模型足够强，多 Agent 失效会自然消失
- C. 标注者间一致性很低（Kappa ≈ 0.3），所以类别只能作参考
- D. 14 种失效模式归为 3 大类，Kappa 0.88；失效是系统设计缺陷，而非靠更好基座模型就能修复的 LLM 局限

**Q2.** 运行本节代码，trace `t006`（请求 "read some file"，唯一一步 `read_file` 的参数是 `{"file": "/tmp/foo"}`）被打上的标签是：

- A. `['tool_misuse']`
- B. `['hallucinated_action']`
- C. `['tool_misuse', 'hallucinated_action']`
- D. `[clean]`

**Q3.** 讲义说"Cascading is the killer"。它给出的根本原因是：

- A. 级联错误只出现在多 Agent 系统里，单 Agent 不会发生
- B. 级联错误会让 API 费用翻倍
- C. Agent 分不清"我失败了"与"任务不可能完成"，常在 400 错误后幻觉出一条成功消息来结束循环，错误因此被掩盖并继续向下游传播
- D. 级联错误一定会导致进程崩溃，从而丢失全部 trace

**Q4.** 一个 Agent 的计划里"运行测试"这一步被执行了两遍，按 LLM Agent Hallucinations Survey 的划分，这属于哪类 sub-intention 错误？

- A. Omission（遗漏）
- B. Redundancy（冗余）
- C. Disorder（乱序）
- D. Long-range Contextual Misuse

**Q5.** 为什么"只对崩溃（crash）打标签"的监控远远不够？

- A. 绝大多数 Agent 失效产生的是**看起来合法**的输出，不会崩溃，必须做内容层面与状态层面的检查
- B. 崩溃日志会泄露 PII，所以不能存
- C. 崩溃太少见，统计上没有意义
- D. 崩溃只能由人工发现，无法自动化

**Q6.** 讲义指出漂移（drift）检测需要什么前提？

- A. 每条 trace 都调用一次 LLM-judge
- B. 把全部 trace 永久保存
- C. 告警必须发到所有人
- D. 一个"最后已知良好"（last-known-good）的基线，否则无法说"情况在变糟"

**Q7.** trace `t005`：请求 "update readme with release notes"，约束 `["do not modify src/"]`，步骤里写了 `README.md` 和 `src/foo.py`。本节代码的**实际**输出标签是：

- A. `['context_loss']`
- B. `[clean]`
- C. `['scope_creep']`
- D. `['scope_creep', 'context_loss']`

**Q8.** 关于 `detect_cascading_errors`，下列哪条 trace **不会**被标为 `cascading_errors`？

- A. 第 1 步 `search` 报错，之后又有 `read_file`、`write_file` 两个调用
- B. 第 1 步 `search` 报错，之后重试 `search` 成功，再 `read_file`
- C. 第 1 步 `search` 报错，之后只有 1 个 `read_file` 调用
- D. 第 2 步 `read_file` 报错，之后又有 3 个调用

---

## 三、动手 / 代码题

**Q9.** 阅读 `detect_context_loss`：

```python
def detect_context_loss(trace: Trace) -> str | None:
    for constraint in trace.constraints:
        con_l = constraint.lower()
        if "do not" in con_l:
            forbidden_token = con_l.split("do not")[-1].strip().split()[0]
            for step in trace.steps:
                if step.kind == "tool_call" and forbidden_token in str(step.args).lower():
                    return "context_loss"
    return None
```

1. 对约束 `"do not modify src/"`，`forbidden_token` 是什么？为什么 t005 明明写了 `src/foo.py` 却没被标记？
2. 构造一个**误报**的例子。
3. 构造一个让它**抛异常**的约束字符串。
4. 改写这个检测器，使 t002、t005 都能被标为 `context_loss`，并说明生产中约束应该怎样表达。

**Q10.** 本节有两处"写意图"关键词表：

```python
# detect_scope_creep
explicit_write_words = ("write", "create", "save", "update", "edit")
# detect_success_hallucination
("write", "create", "save", "update", "edit", "make")
```

用户请求 `"make a backup copy"`。分别回答：Agent 调用了 `write_file` 时会被打什么标签？Agent 没写任何文件、`final_success_claim=True`、`target_state_changed=False` 时又会被打什么标签？这说明了什么问题？还有什么子串匹配带来的隐患？

**Q11.** 实现讲义练习 3 的 "cascade radius"：给定一条 trace，返回第一个报错的工具调用**之后**还有多少个工具调用受到影响（没有报错则为 0）。写出函数，并给出它在 t004 上的结果。再说明它和 `detect_cascading_errors` 的 `downstream_ops >= 2` 是什么关系。

**Q12.** t004（"look up invoice 4711"）中 `search` 返回错误后，Agent 读写了 `/tmp/foo`（写入内容是 `"fabricated"`），最后 `final_success_claim=True`。代码给它打的是 `['scope_creep', 'cascading_errors']`，却**没有** `success_hallucination`。为什么？请写一个能识破"在错误后声称成功"的检测器，并说明讲义推荐的更根本的做法。

---

## 四、面试高频题

**Q13.**（基础必考）列举 Agent 在生产中最常见的五类失效模式，每类给一个例子和一种缓解手段。

**Q14.**（原理深挖）为什么说 agentic 场景会"放大"已有的 AI 失效？MASFT 为什么认为多 Agent 失效是设计缺陷而不是模型能力问题？

**Q15.**（工程实践）请设计一套 Agent 失效监控系统：从 trace 采集到告警，需要哪些组件？哪些地方用规则、哪些地方用 LLM？

**Q16.**（场景设计）一个电商客服 Agent 幻觉出了一个不存在的 SKU，随后连续调用库存、价格、下单、通知四个 API，造成多系统事故。请复盘并给出从"单步防护"到"系统兜底"的改进方案。

**Q17.**（追问型）"Agent 说做完了，但其实没做"——你如何在系统层面可靠地发现并阻止 success hallucination？如果目标状态不可直接探测怎么办？

---

## 五、参考答案与解析

### Q1 — 答案：D

讲义："14 failure modes clustered into 3 categories. Inter-annotator Cohen's Kappa 0.88"；核心论断是"failures are fundamental design flaws in multi-agent systems, not LLM limitations to be fixed with better base models"。A 的数字是编造的；B 与核心论断正好相反；C 把 Kappa 说成很低，实际 0.88 属于高度一致。

### Q2 — 答案：A

实际运行输出：`t006 ... labels: ['tool_misuse']`。`read_file` 在 `KNOWN_TOOLS` 里，所以 `detect_hallucinated_action` 不触发（排除 B、C）；`tool_args_schema["read_file"] == {"path"}`，而实际参数键是 `{"file"}`，`{"path"}.issubset({"file"})` 为 False，于是返回 `tool_misuse`。"工具对、参数错"正是讲义对 tool misuse 的定义："Valid call, wrong invocation"。

### Q3 — 答案：C

讲义原话："Agents cannot distinguish 'I failed' from 'the task is impossible' and often hallucinate a success message on 400 errors to close the loop." 失败被"成功消息"掩盖后，下游步骤会基于错误前提继续执行，一个错误变成多系统事故。A 错，单 Agent 的工具链同样会级联；B 只是附带后果；D 恰恰相反——级联错误通常**不崩溃**，所以才危险。

### Q4 — 答案：B

讲义："Sub-intention errors: Omission (missed step), Redundancy (repeated step), Disorder (out-of-order steps)." 重复执行同一步是 Redundancy。A 是漏步，C 是顺序错，D 是幻觉的一种"表现"（遗忘/误用早期上下文），不属于 sub-intention 的三分法。

### Q5 — 答案：A

讲义："Tagging only crashes. Most agent failures produce valid-looking output. Need content-level checks." 本节 7 条 trace 没有一条崩溃，却有 5 条带标签。B 是 PII 脱敏的问题（outputs 的 skill 要求存储前脱敏），不是不监控的理由；C、D 都不成立。

### Q6 — 答案：D

讲义："No baseline. Drift detection needs a last-known-good; without it you cannot say 'this is getting worse.'" outputs 中的 skill 也规定：没有 known-good 基线时拒绝做漂移告警。A 被 skill 明确列为 hard reject（生产中逐条调用 LLM 太贵，应只对抽样复核用 LLM-judge）；B 被列为拒绝规则（成本与合规）；C 是过度告警。

### Q7 — 答案：B

实际输出 `t005 ... labels: [clean]`——这是代码的**漏报 bug**。
- `detect_scope_creep`：请求含 "update"，有写意图，不触发（排除 C、D）。
- `detect_context_loss`：`"do not modify src/".split("do not")[-1].strip().split()[0]` 得到 `"modify"`，再检查 `"modify"` 是否出现在 `str(step.args)` 中——参数里只有路径和内容，没有 "modify"，所以不触发（排除 A）。
从语义上看，t005 正是讲义定义的 context loss（"Long-horizon turn drops early-turn facts"），正确标签应为 `['context_loss']`。详见 Q9。

### Q8 — 答案：C

检测逻辑：遇到第一个报错的 tool_call 后，统计其后的 tool_call 数，`>= 2` 才标记。C 只有 1 个下游调用，不触发。A：2 个下游，触发；B：重试 + read 共 2 个，**也触发**——这是一个误报，合理的重试-恢复被当成了级联；D：3 个下游，触发（检测器不要求错误出现在第 1 步）。B 说明这个计数规则无法区分"恢复"与"级联"。

### Q9 — 参考答案

1. `forbidden_token` = `"modify"`（取 "do not" 之后的**第一个词**，即动词）。检测器随后检查 `"modify"` 是否出现在参数字符串 `"{'path': 'src/foo.py', 'content': 'also notes'}"` 中——当然没有。真正应该匹配的是**对象** `src/`，而不是动词。同理，t002 的约束 `"do not modify any files"` 也只会去找 "modify"，所以 t002 只被 `scope_creep` 抓到。全部 7 条 trace 中 `context_loss` 一次都没有触发，聚合分布里也就没有这一项。
2. 误报：约束 `"do not touch src/"`，某步 `read_file` 的参数是 `{"path": "README.md", "content": "touch me"}`——实测被标为 `['context_loss']`，因为 "touch" 作为子串出现在了参数里，而实际并没有碰 `src/`。
3. 抛异常：约束以 "do not" 结尾，例如 `"you must do not"`。`split("do not")[-1].strip()` 为空串，`.split()[0]` 抛 `IndexError: list index out of range`（已实测）。整个 `tag()` 会因为一个检测器异常而崩溃——监控代码本身应当对单个检测器做异常隔离。
4. 参考改写（已实测：t002、t005 均被标为 `context_loss`，其余标签不变）：

```python
WRITE_TOOLS = {"write_file"}

def detect_context_loss(trace):
    for c in trace.constraints:
        c = c.lower()
        if "do not" not in c:
            continue
        words = c.split("do not", 1)[1].split()
        if len(words) < 2:                      # 防止 IndexError
            continue
        verb, objs = words[0], words[1:]
        if verb not in ("modify", "touch", "edit", "write"):
            continue
        writes = [s for s in trace.steps
                  if s.kind == "tool_call" and s.name in WRITE_TOOLS]
        if objs == ["any", "files"] and writes:
            return "context_loss"
        for s in writes:
            path = str(s.args.get("path", "")).lower()
            if any(path.startswith(o) for o in objs):
                return "context_loss"
    return None
```

生产中不应从自然语言里"猜"约束：约束应在任务创建时就结构化，例如 `{"deny_write": ["src/"]}` 或 `{"read_only": true}`，检测器（以及更前置的工具参数校验 gate）直接按路径前缀判断。更好的是把它做成**执行前拦截**（Lesson 06 的参数校验），而不仅是事后打标签。

### Q10 — 参考答案

- 调用了 `write_file`：`detect_scope_creep` 的词表里**没有** "make"，`wanted_write=False`，于是标为 `['scope_creep']`（实测）。
- 没写文件且声称成功、状态未变：`detect_success_hallucination` 的词表**有** "make"，于是标为 `['success_hallucination']`（实测）。
- 结论：对同一个请求，Agent 写也被标、不写也被标——两套词表不一致制造了一个"无论如何都失败"的陷阱，会污染失效分布统计。修复：抽成一个共享常量 `WRITE_INTENT_WORDS`，两处共用。
- 子串匹配的隐患：`any(w in request for w in ...)` 是子串匹配。`"read the editor config"` 含 "edit"，会被认为有写意图，此时 Agent 若越权写文件反而**漏报** scope creep（实测输出为空）；`"recreate"` 含 "create" 同理。至少应按词边界匹配（如 `re.search(r"\b(write|create|...)\b", request)`），更稳妥的是在任务入口用分类器或结构化字段（`intent: read_only / write`）确定意图。

### Q11 — 参考答案

```python
def cascade_radius(trace):
    calls = [s for s in trace.steps if s.kind == "tool_call"]
    for i, s in enumerate(calls):
        if s.status == "error":
            return len(calls) - i - 1      # 第一个错误之后的调用数
    return 0
```

t004：第 0 个调用 `search` 报错，后面还有 `read_file`、`write_file`、`list_dir`，结果为 **3**（已实测）。

关系：`detect_cascading_errors` 实际上就是 `cascade_radius(trace) >= 2` 的布尔版本。半径是一个连续指标，更适合做分布与趋势（比如按日统计 P50/P90 半径），也能用来设置"错误后最多允许 N 步就熔断"的 gate。进一步可以只统计"依赖了出错步骤输出"的下游步骤（需要在 trace 中记录数据依赖），从而把合理的重试/恢复排除在外（Q8 的选项 B）。

### Q12 — 参考答案

**为什么没触发**：`detect_success_hallucination` 要求请求含写意图（"write/create/save/update/edit/make"），"look up invoice 4711" 是只读请求，第一条件就不满足；何况 `target_state_changed=True`（因为 Agent 越权写了 `/tmp/foo`），第三条件也不满足。讲义定义的 success hallucination 是"Agent claims success on a 400; state unchanged"，而本代码只覆盖了"写任务没写成"这一种形态，对"读任务出错后编造结果并宣称成功"无能为力。

**补充检测器**（已在 t004 上实测触发）：

```python
def detect_claim_after_unrecovered_error(trace):
    calls = [s for s in trace.steps if s.kind == "tool_call"]
    for i, s in enumerate(calls):
        if s.status == "error":
            recovered = any(c.name == s.name and c.status == "ok"
                            for c in calls[i + 1:])
            if not recovered and trace.final_success_claim:
                return "success_after_error"
    return None
```

**更根本的做法**（讲义 "Mitigation: gates at every step"）：
- 不信任 Agent 的自述，**重新探测环境状态**（"was the file actually created?"）：文件是否存在、数据库行是否写入、PR 是否真的打开；
- 工具返回 4xx/5xx 时由 harness 强制把错误结构化地塞回上下文，并禁止在同一轮里输出"成功"总结；
- 对最终答案做 grounding 校验（CRITIC，Lesson 05）：回答里的发票号、金额必须能在工具返回中找到出处。

### Q13 — 参考回答要点

| 模式 | 例子 | 缓解 |
|------|------|------|
| Hallucinated actions | 调用不存在的 `magic_scanner`；编造订单号作参数 | 工具白名单 + JSON Schema 校验，未知工具直接拒绝 |
| Scope creep | 只让查配置却改了配置；多发邮件、多开 PR | 最小权限、只读模式、写操作需确认（propose-then-commit） |
| Cascading errors | 幻影 SKU 触发 4 个下游 API | 每步 gate、错误后熔断、限制错误后的步数 |
| Context loss | 长任务后期忘了"不要动 src/" | 约束结构化并由 harness 强制执行，而不是只写在早期 prompt 里；定期把约束重新注入上下文 |
| Tool misuse | `read_file` 传了 `file` 而不是 `path` | 参数 schema 校验，错误信息回传给模型让其自我修正 |

- 加分点：补充第六种 success hallucination，以及"监控要做内容级检查、要有基线、要聚类限流"。
- 常见误区：把所有失效都归因于"模型不够聪明"，期待换模型解决。

### Q14 — 参考回答要点

- **放大机制**：聊天场景里一次 hallucination 只是错一句话，由人读后判断；agentic 场景里幻觉会变成**行动**（调用 API、写文件、发邮件），而且行动的输出又成为下一步输入——错误被自动执行、被复制、被级联，规模越大损失越大。Microsoft 分类也指出自主性带来新失效：规模化的意外行动、工具滥用、任务漂移。
- **设计缺陷而非模型问题**：MASFT 的失效来源于 Agent 间的规范、协作、验证与终止机制（讲义："failures arise from orchestration, internal state evolution, and environment interaction"），这些是系统层面的问题——角色定义含糊、缺少验证步骤、没有终止条件——换更强的模型不会自动补上这些缺口。
- **Kappa 0.88** 说明这些类别是可以被稳定识别的，因此可以写成检测器做监控。
- 加分点：能说出 MASFT 原论文的三大类大意（规范/系统设计类、Agent 间错位类、任务验证与终止类；讲义本身没有列出类别名，回答时可说明出处是原论文）；能联系 Anthropic "Building Effective Agents"：很多失效可以通过选用更简单的 workflow 直接避免。

### Q15 — 参考回答要点

- **采集**：OpenTelemetry GenAI 约定记录每个 LLM 调用、工具调用、参数、状态码、耗时，以及任务级的约束与"目标状态快照"。
- **规则检测器（在线、全量）**：未知工具、schema 不符、错误后继续执行、违反结构化约束、声称成功但状态未变。讲义与 skill 强调：生产中不要对每条 trace 调用 LLM。
- **LLM-judge（离线、抽样）**：对被标记的 trace 和随机样本做语义复核，例如判断"是否超出用户意图"。
- **基线与漂移**：保存 last-known-good 版本的标签分布，按版本/日期对比。
- **告警**：按模式聚类、限流；阈值触发（如某模式 ≥ 5% 的 trace）才开工单，避免 over-alerting。
- **样本保留**：被标记 trace 保留输入、输出、状态快照供复盘，存储前做 PII 脱敏；不要"永久保存全部 trace"。
- **检测器版本化**：检测器改动会悄悄改变信号，需要版本号和回归测试（本节 Q9 就是检测器自身的 bug）。
- 加分点：把检测器接进 CI，对离线回放的 trace 计算标记率，超阈值让构建失败。

### Q16 — 参考回答要点

- **复盘链路**：SKU 不存在（hallucinated argument）→ 库存 API 返回 404/400 → Agent 未识别失败、甚至编造"有货" → 价格、下单、通知继续执行 → 多系统产生脏数据并通知了客户。
- **单步防护**：
  - SKU 参数先经过存在性校验（查商品目录），不存在就拒绝调用；
  - 每个工具调用后检查状态码，4xx/5xx 时由 harness 强制进入"失败处理"分支；
- **流程兜底**：
  - 错误后熔断：一旦出现未恢复的错误，禁止继续调用**有副作用**的工具；
  - 下单、发通知等不可逆动作采用 propose-then-commit，需要人工或二次校验确认；
  - 幂等键与补偿事务（saga），出错时可以回滚已执行的步骤；
- **监控**：cascade radius 指标、success-after-error 检测器、按 SKU/工具聚类告警。
- 常见误区：只在最后一步加审核——此时前三个 API 已经执行完毕。

### Q17 — 参考回答要点

- **原则**：不信任自述，验证外部状态。讲义："Detect success hallucination by re-probing state (was the file actually created?)"。
- **做法**：
  1. 每个任务定义可检查的完成条件（文件存在且内容哈希变化、PR URL 可访问、数据库行数增加）；
  2. Agent 宣告完成后，由 harness（不是 Agent 自己）执行探测；
  3. 工具错误结构化回传，并在 trace 中记录"最后一次错误是否被恢复"；
  4. 对答案做 grounding 检查：关键事实必须能在工具返回中找到。
- **状态不可直接探测时**：用间接证据（回执、日志、外部系统的事件）；让 Agent 输出可核验的"证据清单"并由独立的 verifier 检查；对高风险任务要求人工确认；对低风险任务抽样复核。
- 加分点：说明这本质是"实现者与评分者分离"——后续 Verification Gates 与 Reviewer Agent 两节就是这一思想的系统化。

---

## 六、关联知识点

### 前置知识
- [阶段 14 · 05 Self-Refine 与 CRITIC：迭代改进输出](../../05-self-refine-and-critic/docs/zh.md)：讲义缓解手段之一"对照已知事实交叉核验"来自 CRITIC。
- [阶段 14 · 06 工具使用与 Function Calling](../../06-tool-use-and-function-calling/docs/zh.md)：工具参数校验是防 tool misuse 与 hallucinated actions 的第一道 gate。
- [阶段 14 · 21 计算机操作：Claude、OpenAI CUA、Gemini](../../21-computer-use-agents/docs/zh.md)：讲义提到的逐步安全分类器。
- [阶段 14 · 24 Agent 可观测性（Observability）：Langfuse、Phoenix、Opik](../../24-agent-observability-platforms/docs/zh.md)：trace 存储与 Phoenix 的漂移聚类。
- [阶段 14 · 23 OpenTelemetry GenAI 语义约定](../../23-otel-genai-conventions/docs/zh.md)：检测器所依赖的 trace 结构。

### 本节被哪些后续内容用到
- [阶段 14 · 27 Prompt Injection 与 PVE 防御](../../27-prompt-injection-defense/docs/zh.md)：对抗性的失效模式。
- [阶段 14 · 30 评估驱动的 Agent 开发](../../30-eval-driven-agent-development/docs/zh.md)：把失效 trace 变成回归评测用例。
- [阶段 14 · 38 Verification Gates](../../38-verification-gates/docs/zh.md)：把"每一步都设 gate"工程化。
- [阶段 14 · 39 Reviewer Agent：将实现者与评分者分开](../../39-reviewer-agent/docs/zh.md)：独立验证以识破 success hallucination。
- [阶段 16 · 23 失效模式：MAST、群体思维、同质化与级联错误](../../../16-multi-agent-and-swarms/23-failure-modes-mast-groupthink/docs/zh.md)：多 Agent 场景下的失效分类深入。
- [阶段 15 · 14 紧急停止开关、Circuit Breakers 与金丝雀 Tokens](../../../15-autonomous-systems/14-kill-switches-canaries/docs/zh.md)：级联错误发生后的熔断。
- [阶段 17 · 23 AI 的 SRE：多 Agent Incident Response、操作手册与预测性检测](../../../17-infrastructure-and-production/23-sre-for-ai/docs/zh.md)：失效告警之后的事故响应。

### 延伸关键词
`MASFT / MAST` · `cascading errors` · `success hallucination` · `scope creep` · `context loss` · `tool misuse` · `sub-intention errors` · `verification gate` · `state re-probe` · `drift detection` · `alert clustering` · `cascade radius`
