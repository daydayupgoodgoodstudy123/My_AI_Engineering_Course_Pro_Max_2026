# 测验 · Agent 工作台工程：能力强的模型为什么仍会失败（Agent Workbench Engineering: Why Capable Models Still Fail）

> **阶段 14 · Agent 工程 · 第 31 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 说明：本节中文讲义是机器翻译，质量较差（例如把 "frontier model" 译成"边境模型"、"repo" 译成"回购"），遇到读不通的地方请以英文版为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 能力 ≠ 可靠性 | 模型"会写 Python"不等于"会完成这份工作"；讲义："The model was not wrong about Python. It was wrong about the work." |
| 2 | Workbench（工作台）的定义 | 任务执行期间包裹在模型外面的运行环境；它独立于模型——换模型可以保留工作台，拆掉工作台就保不住可靠性 |
| 3 | 七个 surface（工作台表面） | Instructions、State、Scope、Feedback、Verification、Review、Handoff，每个都对应一种"缺了就会出现"的典型症状 |
| 4 | 系统记录（system of record） | 循环闭合在状态文件上而不是聊天记录上；讲义："Chat is volatile. The repo is the system of record." |
| 5 | 工作台 vs prompt engineering vs 框架 | prompt 只管"这一轮要什么"；工作台管"跨轮次、跨会话如何干活"；框架（LangGraph、Agents SDK）给运行时，工作台给 agent 在运行时里的"工位" |
| 6 | 八个分布式系统原语 | Function、Worker、Trigger、Runtime、HTTP/RPC、Queue、Session persistence、Authorization policy——七个 surface 都能落到这八个原语上 |
| 7 | surface → 原语映射 | Scope = 授权策略（ACL）；State = 会话持久化；Feedback = 写入队列的调用日志；Verification = 确定性、fail closed 的函数；Review = 权限受限的独立 worker；Handoff = 会话结束 trigger 发出的持久记录 |
| 8 | 把厂商术语翻译成原语 | Ralph Loop = 用干净上下文重新入队的 trigger；Hooks = 包在调用路径上的 trigger + function；MCP server = 通过 RPC 暴露函数的 worker；Sandbox = 计算平面 |
| 9 | "harness 胜过模型"的证据 | 讲义列举：Terminal Bench 2.0 同模型换 harness 从 30 名开外升到第 5；Vercel 删掉 80% 工具后成功率 80% → 100%；Harvey 准确率翻倍以上 |
| 10 | 本节代码的定位 | `stub_agent` 是规则桩（不是 LLM），只用来演示"哪个 surface 缺失 → 产生哪种症状"，并导出 `failure_modes.json` |

### 核心技能（能动手做到）

- [ ] 不看讲义写出七个 surface 的名称、各自承载的内容、缺失时的症状
- [ ] 把任意一个"harness 新名词"（Ralph Loop、Hooks、Skills、Sandbox agent…）翻译成八个原语之一，并说明理由
- [ ] 读懂 `main.py` 中 `stub_agent` 的分支逻辑，预测给定 surface 组合下的 `failure_report` 输出
- [ ] 指出本节代码中"verification 不依赖 feedback 也能判通过""白名单写死在 `failure_report` 里"等简化，并能修正
- [ ] 按 `outputs/skill-workbench-audit.md` 的 0/1/2 评分法给一个真实仓库做工作台审计，排出前三个优先修补项
- [ ] 面对"等更强的模型就好了"的说法，能用讲义中的数据点和"模型会吸收 harness 技巧"两面作答

---

## 二、基础自测（选择题）

**Q1.** 讲义开头的场景：frontier 模型在真实仓库里"加输入校验"，改了四个文件、宣布成功；结果两个测试失败、还碰了一个无关文件、没留下任何记录。讲义把根因归为：

- A. 模型的 Python 能力不足，换更大的模型即可解决
- B. 工作台缺失：模型不知道什么算完成、能写哪里、哪些测试是权威的、下个会话如何接手
- C. 上下文窗口太短，看不全仓库
- D. 采样温度太高，导致输出不稳定

**Q2.** 在七个 surface 的表格中，"Agent declares success on a 400"（拿到 400 错误还宣布成功）是哪个 surface 缺失的症状？

- A. Instructions
- B. Scope
- C. Review
- D. Feedback

**Q3.** 讲义的流程图（Task → Scope → State → Agent → Feedback → Verify → Review → Handoff → State）最终闭合在哪里？

- A. 状态文件（仓库是系统记录），而不是聊天历史
- B. 聊天历史，因为它记录了全部推理
- C. 模型权重，因为每次任务都会微调模型
- D. CI 日志，因为它最权威

**Q4.** 按讲义的原语映射，Scope（允许/禁止的文件、需要审批的边界）对应哪个原语？

- A. Queue
- B. Session persistence
- C. Authorization policy
- D. Worker

**Q5.** 讲义把社区流行的 "Ralph Loop"（agent 试图提前停止时，把原始意图重新注入一个全新的上下文窗口）翻译成了什么？

- A. 一种授权策略，由执行前的 worker 校验
- B. 一个计算平面，带隔离的文件系统与网络
- C. 一个函数注册表，函数元数据按需加载进上下文
- D. 一个用干净上下文把任务重新入队的 trigger，目标靠会话持久化传递下去

**Q6.** 用本节代码执行 `stub_agent(task, surfaces=["verification"])`，`failure_report` 中 `tests_run` 和 `actually_passing` 分别是：

- A. `tests_run=False`，`actually_passing=True`
- B. `tests_run=False`，`actually_passing=False`
- C. `tests_run=True`，`actually_passing=True`
- D. `tests_run=True`，`actually_passing=False`

**Q7.** 运行 `python3 code/main.py`，prompt-only 那一轮 7 个 surface 全部缺失。其中哪些缺失的 surface **在 `notes` 里没有产生任何对应症状**？

- A. scope、feedback
- B. state、verification
- C. instructions、review、handoff
- D. 没有，七个 surface 各有一条 note

**Q8.** 讲义"What the receipts actually say"里关于 Vercel 的数据点是：

- A. 换成更大的模型后，成功率从 50% 提到 80%
- B. 删掉 agent 80% 的工具后，成功率从 80% 跳到 100%
- C. 加入 RAG 后，准确率翻倍
- D. 增加工具数量后，从 Terminal Bench 30 名开外升到第 5 名

---

## 三、动手 / 代码题

**Q9.** 阅读 `stub_agent` 与 `failure_report` 的片段：

```python
    if has_verification:
        result.actually_passing = True
        result.declared_success = True
        result.notes.append("verification gate proved acceptance criteria met")
    else:
        result.declared_success = True
        result.actually_passing = False
        result.notes.append("declared success without running acceptance checks")
```

```python
def failure_report(result: RunResult) -> dict[str, object]:
    return {
        "label": result.label,
        "missing_surfaces": result.missing_surfaces(),
        "off_scope_writes": [
            f for f in result.files_touched if f not in {"app.py", "test_app.py"}
        ],
        ...
```

1. 指出至少三处逻辑简化或缺陷（提示：verification 与 feedback 的关系；`RepoTask` 的哪些字段从未被使用；`label` 怎么定）。
2. 若把任务改成 `allowed_files=["app.py", "test_app.py", "validators.py"]`，workbench 那一轮的 `off_scope_writes` 会是什么？为什么？
3. 给出修正思路（可写代码）。

**Q10.** `mission.md` 的验收标准写着："`failure_modes.json` lists each missing surface with matching symptom"。但实际生成的 JSON 只有一个 `missing_surfaces` 列表和一个 `notes` 列表，两者之间没有对应关系。请写一个函数 `surface_symptoms(result)`，返回 `{缺失的 surface: 症状}` 字典（症状文字取讲义表格第三列），并说明怎样把它接入 `main()`。

**Q11.** 讲义练习 4："Re-run the script with a different stub agent that hallucinates an extra file write. Which surface catches it first?" 请：

1. 写一个 `hallucinating_agent(task, surfaces)`：在 workbench 模式下也会多写一个 `app_backup.py`。
2. 说明在本节代码里，这个越界写入是由谁"发现"的；在一个真实工作台里，Scope 与 Verification 哪个应当**先**拦住它，二者的区别是什么。

**Q12.** 按 `outputs/skill-workbench-audit.md` 的评分法（0 缺失 / 1 部分 / 2 健康）给下面这个仓库打分，并排出前三个优先修补项：

- 根目录有一份 600 行的 `AGENTS.md`，所有规则都写在里面；
- 没有任何记录当前任务/阻塞/下一步的文件；
- 任务通过 issue 描述下发，没有允许/禁止文件列表；
- agent 能跑 shell，但命令输出只出现在聊天里，不落盘；
- 有 `pytest`，但只在合并到 main 后由 CI 跑；
- 同一个 agent 既写代码又批准自己的 PR；
- 有 PR 模板，包含"改了什么/为什么"，但没有"还剩什么/下一步"。

---

## 四、面试高频题

**Q13.**（基础必考）为什么一个在基准上很强的模型，放进真实代码仓库后仍然经常"交付不了"？什么是 agent 工作台？它由哪些部分组成？

**Q14.**（原理深挖）讲义主张"从原语推理，而不是从厂商分类推理"。请把七个 surface 映射到分布式系统原语，并说明这种视角在工程上带来什么好处。

**Q15.**（工程实践）请设计一个 verification gate：它应该检查什么、由谁触发、失败时如何处理？怎样避免"builder 给自己的作业打分"？

**Q16.**（场景设计）你们团队的 coding agent 最近的 PR 经常出现两类问题：顺手改了无关文件；PR 描述写"所有测试通过"，CI 却是红的。请用工作台思路诊断并给出改造方案。

**Q17.**（追问型）"模型每半年就变强一大截，现在花力气做 harness/工作台是不是浪费？" 你怎么回答？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义原话："It had no idea what counted as done, where it was allowed to write, what tests were authoritative, or how the next session was supposed to pick up. This is not a model bug. It is a workbench bug." 这四个"不知道"分别对应 Instructions/Verification（完成定义）、Scope（写权限）、Feedback/Verification（权威测试）、State/Handoff（会话接续）。

- A 正是讲义要反驳的观点："The model was not wrong about Python."
- C、D 都是"模型侧"的参数，换了也解决不了"碰无关文件、无记录"这类问题。

### Q2 — 答案：D

Feedback surface 承载的是"Real command output captured into the loop"。没有它，agent 看不到真实的 stdout/stderr/退出码，只能"猜"结果，于是在 400 上宣布成功。

- A Instructions 缺失的症状是"Agent guesses what shipping means"；
- B Scope 缺失的症状是"Edits leak into unrelated code"；
- C Review 缺失的症状是"Builder marks own homework"。

### Q3 — 答案：A

讲义："The loop closes on the state file, not on chat history. Chat is volatile. The repo is the system of record." 聊天记录会被截断、压缩或在新会话中消失；只有写进仓库的状态文件能跨会话、跨模型存活。B 恰好相反；C 与本节无关（工作台不改模型权重）；D 的 CI 日志只是 Feedback/Verification 的一部分，不是"闭环的落点"。

### Q4 — 答案：C

讲义："Scope — authorization policy per task. Allowed/forbidden globs are an ACL. Approvals required are a permission lattice." Queue 对应 Feedback（调用日志写入队列）；Session persistence 对应 State；Worker 对应 Review（独立的 worker）。

### Q5 — 答案：D

讲义翻译表："A trigger that re-enqueues a task with a clean context; session persistence carries the goal forward." A 是 Open Agent Passport（OAP）的翻译；B 是 Sandbox agents；C 是 "Skills as Markdown with progressive disclosure"。

### Q6 — 答案：A

`stub_agent` 中 `tests_run` 只由 `has_feedback` 决定，`actually_passing` 只由 `has_verification` 决定，两者互不依赖。实际运行结果：

```text
['verification'] -> tests_run: False, actually_passing: True
```

这暴露了一个逻辑漏洞：**连测试都没跑，verification gate 却"证明"了验收标准已满足**。真实系统里 verification 必须基于真实的命令输出（也就是依赖 Feedback），否则就是讲义批评的"Looks good reaches main"。B、C、D 都与代码不符。

### Q7 — 答案：C

`stub_agent` 只检查了 `scope`、`state`、`verification`、`feedback` 四个 surface，`instructions`、`review`、`handoff` 在代码里完全没有分支，所以缺失时不产生任何 note。实际输出的 4 条 notes：

```text
'touched unrelated files because scope was missing'
'never ran the test command, guessed at output'
'declared success without running acceptance checks'
'no state file written, next session restarts from zero'
```

这也意味着把 `instructions`、`review`、`handoff` 从 workbench 列表里删掉，结果除 `missing_surfaces` 外完全不变——stub 无法演示这三个 surface 的价值（见 Q10）。

### Q8 — 答案：B

讲义："Vercel — deleted 80% of its agent's tools; success rate jumped from 80% to 100% (MongoDB)." 它的启示是：工具越多不一定越好，收窄动作空间本身就是 harness 优化。D 是 Terminal Bench 2.0 的数据点，而且那里是"换 harness"，不是"加工具"；C 混淆了 Harvey 的"准确率翻倍以上"（讲义说是 harness 优化，不是 RAG）。

### Q9 — 参考答案

1. **缺陷与简化**（均已实际运行验证）：
   - `actually_passing` 只看 `has_verification`，与 `tests_run` 无关：只开 verification 时 `tests_run=False` 却 `actually_passing=True`（见 Q6）。
   - `declared_success` 在两个分支里**都是 True**——stub 永远宣称成功，只是 workbench 版"恰好"真的通过。这其实正是讲义练习 2 想要的"假成功"，代码已经自带了。
   - `failure_report` 把白名单**写死**为 `{"app.py", "test_app.py"}`，而不是用 `task.allowed_files`；`RepoTask.forbidden_files` 和 `RepoTask.acceptance` 两个字段从未被读取，`description` 也只是摆设。
   - `label = "prompt-only" if not surfaces else "workbench"`：只要有一个 surface 就叫 "workbench"，部分配置的运行无法区分。
   - `instructions`、`review`、`handoff` 没有任何行为分支（见 Q7）。
   - 讲义说输出是"a side-by-side log of the two runs ... and a one-line verdict for the workbench run"，实际是**先后打印**两份完整报告，没有并排、也没有一行结论。
2. `off_scope_writes` 会是 `['validators.py']`（已实际运行）。因为 workbench 模式下 agent 只写 `task.allowed_files` 中的文件，而 `failure_report` 用的是写死的二元白名单，`validators.py` 虽然被允许，仍被判为越界——误报。
3. 修正思路：

```python
def stub_agent(task, surfaces):
    ...
    if has_verification and result.tests_run:          # 验证必须基于真实输出
        result.actually_passing = True
        result.notes.append("verification gate proved acceptance criteria met")
    elif has_verification:
        result.actually_passing = False
        result.notes.append("verification refused: no captured test output (fail closed)")
    result.declared_success = True                     # 保留"总是宣称成功"的设定

def failure_report(result, task):
    allowed = set(task.allowed_files)
    forbidden = set(task.forbidden_files)
    return {
        ...,
        "off_scope_writes": [f for f in result.files_touched if f not in allowed],
        "forbidden_writes": [f for f in result.files_touched if f in forbidden],
        "acceptance": task.acceptance,
    }
```

`label` 可以改为 `"workbench" if set(surfaces) == set(WORKBENCH_SURFACES) else f"partial({len(surfaces)}/7)"`。

### Q10 — 参考答案

```python
SYMPTOMS = {
    "instructions": "agent guesses what shipping means",
    "state": "each session restarts from zero",
    "scope": "edits leak into unrelated code",
    "feedback": "agent declares success on a 400",
    "verification": "'looks good' reaches main",
    "review": "builder marks own homework",
    "handoff": "next session re-discovers everything",
}

def surface_symptoms(result):
    return {s: SYMPTOMS[s] for s in result.missing_surfaces()}
```

接入方式：在 `failure_report` 返回的字典里加一项 `"symptoms": surface_symptoms(result)`；`main()` 已经把 `failure_report(prompt_only)` 写入 `failure_modes.json`，无需再改。prompt-only 那轮会得到 7 个键值对，workbench 那轮为空字典。

更进一步：症状不应只是静态文字，而应由**观测到的证据**生成，例如 `scope` 的症状附上 `off_scope_writes` 列表、`feedback` 的症状附上"tests_run=False"。这样报告才是"证据驱动"的，符合 audit skill 中"Healthy scores without a file path or process reference" 属于硬拒绝的精神。

### Q11 — 参考答案

1. 实现：

```python
def hallucinating_agent(task, surfaces):
    result = stub_agent(task, surfaces)
    result.files_touched.append("app_backup.py")       # 幻觉出来的额外写入
    result.notes.append("wrote app_backup.py that nobody asked for")
    return result
```

2. 在本节代码里，`stub_agent` 的 Scope 只影响"agent 打算写哪些文件"，并没有在写入发生前拦截任何东西；越界写入是事后由 `failure_report` 的 `off_scope_writes` 发现的（相当于 Verification 中的 scope check）。workbench 那一轮的 `off_scope_writes` 会变成 `['app_backup.py']`，但 `actually_passing` 仍然是 `True`——说明本节的 verification 并不检查 scope。
   - 在真实工作台中，**Scope 应该先拦住它**：Scope 是授权策略（ACL），在写操作执行前（pre-action）拒绝 `app_backup.py`，属于讲义 "Guides and Sensors" 里的 guide（feedforward）。
   - **Verification 是第二道防线**：讲义把 "scope check" 列为 Verification 的组成部分，它在任务关闭时对 diff 做检查，属于 sensor（feedback）。它能发现问题，但写入已经发生过了。
   - 两道都要：前者便宜、即时；后者兜底，防止 ACL 配置遗漏或 agent 绕过工具直接用 shell 写文件。

### Q12 — 参考答案

| Surface | 分数 | 证据 / 理由 |
|---------|------|-------------|
| Instructions | 1 | 有根文件，但 600 行全塞在一起，不是"short, that routes to deeper rules"（audit skill 第 1 条） |
| State | 0 | 没有任何持久化的任务/阻塞/下一步文件 |
| Scope | 0 | 只有自然语言 issue，没有允许/禁止文件和验收标准 |
| Feedback | 1 | 能跑命令，但输出只在聊天里，不可回放、不进循环之外的记录 |
| Verification | 1 | 有测试命令，但只在合并后跑——"Looks good" 已经到了 main |
| Review | 0 | builder 批准自己的 PR，正是"Builder marks own homework" |
| Handoff | 1 | PR 模板有"改了什么/为什么"，缺"还剩什么/下一步" |

总分 4 / 14。按"补上后消除的失败模式最多"排序的一种合理答案：

1. **Verification 前移**：把 pytest + scope check 设为任务关闭前必须通过的 gate（fail closed）。它同时兜住 Feedback 和 Scope 的缺口，杠杆最大。
2. **Scope 合约**：每个任务一份允许/禁止文件 + 验收标准，verification 才有据可查。
3. **Review 分离**：引入只读权限的 reviewer 角色，禁止 builder 自批。

State 也是 0 分，若任务经常跨会话，State 应排进前三（替换 3）。关键是每个分数都要有证据（audit skill："Healthy scores without a file path or process reference" 属于硬拒绝）。

### Q13 — 参考回答要点

- **核心论点**：能力与可靠性是两回事。模型会写代码，但不知道"这份工作"的边界：什么算完成、能动哪些文件、哪个测试权威、下个会话怎么接。讲义："Most agent failure stories are workbench failures wearing prompt-engineering clothes."
- **工作台定义**：任务期间包裹模型的运行环境，独立于模型（"You can swap the model and keep the surfaces. You cannot swap the surfaces and keep reliability."）。
- **七个 surface**：Instructions（启动规则、禁止动作、完成定义）、State（当前任务、改动文件、阻塞、下一步）、Scope（允许/禁止文件、验收标准）、Feedback（真实命令输出回灌）、Verification（测试/lint/冒烟/范围检查）、Review（不同角色的第二遍）、Handoff（改了什么、为什么、还剩什么）。
- **加分点**：能说出每个 surface 缺失时的症状；指出闭环落在状态文件而不是聊天历史；区分工作台与框架（框架给 runtime，工作台给工位）。
- **常见误区**：把一切归因于 prompt 写得不好，继续堆 prompt；或者以为"选个 agent 框架"就自带工作台。

### Q14 — 参考回答要点

- 八个原语：Function、Worker、Trigger、Runtime、HTTP/RPC、Queue、Session persistence、Authorization policy。
- 映射（讲义原文要点）：
  - Instructions → policy + function metadata（规则是检查函数，`AGENTS.md` 是挂在 runtime 启动上的策略）；
  - State → session persistence（存储后端不重要，持久化语义才重要）；
  - Scope → authorization policy（globs 是 ACL，审批是权限格）；
  - Feedback → 写入 queue 的调用日志（持久、可回放）；
  - Verification → 确定性 function，任务关闭时触发，fail closed；
  - Review → 独立 worker，对 builder 产物只读、对评审报告只写；
  - Handoff → 会话结束 trigger 发出的持久记录，下次启动 trigger 读取。
- agent loop 本身就是一个 worker：消费事件、调用函数、写记录、发出 trigger，"the same shape as a job processor"。
- **好处**：术语稳定（厂商换说法时不必重学）；可以直接复用成熟的工程实践（幂等、重试、背压、ACL、审计日志）；能看出厂商叙述的缺口（讲义指出 LangChain 的 11 组件里没有 queue、部署单元、trigger 语义、授权策略）。
- **加分点**：举例翻译 Hooks（trigger + function）、MCP server（通过 RPC 暴露函数的 worker，能力列表即授权）、"harness-compute separation"（控制面/数据面分离）。

### Q15 — 参考回答要点

- **检查什么**：测试（以验收标准中点名的用例为准）、lint/type-check、冒烟运行、scope check（diff 中的文件是否都在允许列表、是否触碰禁止文件）、验收标准逐条核对。
- **触发**：任务关闭时由 trigger 自动调用，而不是由 builder 自己决定"要不要跑"。
- **输入必须是真实证据**：基于 Feedback 记录的命令、stdout/stderr、退出码，而不是 agent 的自述（对照本节代码 Q6 的漏洞）。
- **fail closed**：缺证据、命令超时、无法解析结果都按失败处理；讲义："Verification — a function. Deterministic over inputs. Triggered on task close. Fails closed."
- **防止自评**：verification 是确定性函数，builder 无法"说服"它；之后再由独立的 reviewer worker 复核（只读 builder 产物、只写评审报告），builder 没有批准权限。
- **加分点**：gate 的结果写回 State/Handoff，下次会话可见；gate 本身要版本化，避免 agent 修改测试来"通过"。

### Q16 — 参考回答要点

- **诊断**：
  - 改无关文件 → Scope 缺失（无 ACL），且 Verification 没有 scope check；
  - 描述说通过、CI 红 → Feedback 缺失（没有把真实测试输出回灌）+ Verification 缺失或后置 + Review 缺失（没人核对自述与证据）。
- **改造**：
  1. 每个任务生成 scope 合约（allowed/forbidden globs + 验收标准），在写文件的工具层强制执行（pre-action 授权）；
  2. 所有 shell 调用经过一个 runner，记录 command/stdout/stderr/exit code 并持久化；
  3. 任务关闭前跑 verification gate（测试 + scope check），PR 描述中的"测试通过"由 gate 自动生成，不允许 agent 手写；
  4. 引入 reviewer 角色，读 diff 与 gate 结果后再放行；
  5. 每次会话结束写 handoff（改了什么、为什么、还剩什么）。
- **验证改造效果**：统计改造前后"越界写入率""自述与 CI 不一致率"。
- **常见误区**：只在 prompt 里加一句"不要修改无关文件""务必跑测试"——这是把工作台问题当成 prompt 问题。

### Q17 — 参考回答要点

- **证据**：讲义列出的数据点——Terminal Bench 2.0 同一模型仅改 harness 从 30 名开外到第 5；Vercel 删 80% 工具成功率 80% → 100%；Harvey 仅靠 harness 优化准确率翻倍以上；讲义引用的预印本称 88% 的企业 agent 项目到不了生产，失败集中在运行时而非推理。
- **承认另一面**：讲义也说 "Models do absorb harness tricks over time"——某些技巧（如强制分步、特定提示格式）会被下一代模型内化，不必永远保留。
- **但原语不会过时**：授权（谁能写哪里）、持久化（跨会话状态）、验证（客观的完成定义）、审计记录——这些是任何生产系统都需要的，与模型多聪明无关。再聪明的模型也不应该拥有不受约束的写权限。
- **工作台与模型解耦**：换模型时保留工作台，可以直接做 A/B 对比，工作台反而让"升级模型"变得更安全。
- **加分点**：提到讲义中的 ratchet（棘轮）思路——每次失败都转化为一条机器可检查的规则，让系统只进不退（课程索引中第 46 节"把每一次对 Agent 的纠正转化为系统改进"与此相关）。

---

## 六、关联知识点

### 前置知识
- [阶段 14 · 01 Agent Loop：观察、思考、行动](../../01-the-agent-loop/docs/zh.md)：工作台包裹的就是这个循环，讲义说 agent loop 本身是一个 worker。
- [阶段 14 · 26 失效模式：Agents 为什么会失败](../../26-failure-modes-agentic/docs/zh.md)：七个 surface 是为吸收这些失败模式而设计的（讲义练习 5）。
- [阶段 14 · 12 Anthropic 的工作流模式：优先采用简单方案](../../12-anthropic-workflow-patterns/docs/zh.md)：理解 workflow 与 agent 的区分，以及"先简单"的原则。
- [阶段 14 · 13 有状态图 Orchestration：Durable Execution 与 Checkpoints](../../13-langgraph-stateful-graphs/docs/zh.md)：checkpoint 就是 State surface 在框架里的形态。

### 本节被哪些后续内容用到
- [阶段 14 · 32 最小 Agent 工作台](../../32-minimal-agent-workbench/docs/zh.md)：把七个 surface 落成一个最小仓库布局。
- [阶段 14 · 33 将 Agent 指令作为可执行约束](../../33-instructions-as-executable-constraints/docs/zh.md)：深入 Instructions surface。
- [阶段 14 · 34 代码仓库记忆与持久状态](../../34-repo-memory-and-state/docs/zh.md)：深入 State surface。
- [阶段 14 · 36 Scope Contracts 与任务边界](../../36-scope-contracts/docs/zh.md)：深入 Scope surface。
- [阶段 14 · 37 运行时反馈循环](../../37-runtime-feedback-loops/docs/zh.md)、[阶段 14 · 38 Verification Gates](../../38-verification-gates/docs/zh.md)：Feedback 与 Verification。
- [阶段 14 · 39 Reviewer Agent：将实现者与评分者分开](../../39-reviewer-agent/docs/zh.md)、[阶段 14 · 40 跨会话 Handoff](../../40-multi-session-handoff/docs/zh.md)：Review 与 Handoff。
- [阶段 14 · 29 生产运行时：队列、事件与定时任务](../../29-production-runtimes/docs/zh.md)：本节原语（queue、trigger、cron）在部署中的位置。
- [阶段 14 · 27 Prompt Injection 与 PVE 防御](../../27-prompt-injection-defense/docs/zh.md)：授权策略原语上的安全防线。

### 延伸关键词
`harness engineering` · `Agent = Model + Harness` · `system of record` · `definition of done` · `fail closed` · `control plane / data plane` · `guides and sensors` · `Ralph Loop` · `AGENTS.md / CLAUDE.md` · `ACL` · `workbench audit`
