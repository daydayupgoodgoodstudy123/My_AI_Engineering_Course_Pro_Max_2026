# 测验 · 在 Agent 编写代码前界定任务（Frame the Task Before the Agent Writes Code）

> **阶段 14 · Agent 工程 · 第 43 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 昂贵的失败 | 讲义："The speed is the same. The cost is not." 清楚和不清楚的任务 agent 都能很快实现，危险在于实现得干净、有测试，却与系统不兼容 |
| 2 | Task frame（任务框架）| coding agent 的第一个工作单元不是编辑，而是"有仓库证据支撑的 task frame" |
| 3 | 六个字段 | Goal（可观察行为）、Repository facts（已验证事实）、Allowed paths、Forbidden paths、Acceptance evidence、Unknowns |
| 4 | 事实要有收据 | "API 用 409 表示重复"在指出现有测试或 handler 之前不是事实；`文件:行号` 即可，涉及行为时命令结果更好 |
| 5 | 侦察 = 寻找约束 | 不要通读仓库，只找六类约束：当前行为及调用方、最近的测试、公开契约/序列化形状、管该路径的项目规则、构建与验证命令、类似的已完成变更 |
| 6 | 停止条件 | 每个计划中的决定都有证据、被明确授权，或被列为 unknown 时就停止；讲义："More reading after that point is often avoidance" |
| 7 | Unknown 的四种分类 | Discoverable（仓库能回答）、Decidable（契约授权 agent 自己选）、Human（改变产品行为、成本、风险或公开兼容性）、Deferred（不属于本切片，放进 non-goals） |
| 8 | Unknown ≠ 假设 | unknown 是受控的缺口，assumption 是对缺口的不受控回答；遇到 human unknown 要在决定被埋进代码前暂停 |
| 9 | 先写验收再写补丁 | 证明可以是聚焦的测试命令、浏览器旅程、请求/响应契约、性能阈值、scope 检查；"Tests pass" 不是证明计划 |
| 10 | 本节代码的边界 | `validate()` 只做非空检查和**字符串完全相同**的路径重叠检查；不识别 glob、不检查证据格式、不对 unknown 分类，因此"零事实""tests pass""存在 human unknown"都仍是 READY |

### 核心技能（能动手做到）

- [ ] 把一句模糊的需求（如 "Add duplicate email protection"）拆成六字段 task frame，并列出至少三个需要证据或人类决定的问题
- [ ] 区分 repository fact 与 assumption，并为每个事实写出 `文件:行号` 或命令结果形式的收据
- [ ] 给每个 unknown 归类（discoverable / decidable / human / deferred），说出 agent 遇到每类时该继续还是暂停
- [ ] 读懂 `validate()` 与 `render()`，按讲义"四种破坏方式"逐一跑出不同的拒绝原因
- [ ] 改造验证器：支持 glob 重叠检测、证据格式检查、拒绝泛泛的验收描述、human unknown 阻塞
- [ ] 解释 `tests/test_main.py` 中每个测试验证的性质，并补上缺失的测试

---

## 二、基础自测（选择题）

**Q1.** 讲义认为，可靠的 coding-agent 工作的**第一个单元**应当是：

- A. 一个有仓库证据支撑的 task frame
- B. 一个能跑起来的最小原型
- C. 通读整个仓库，建立完整理解
- D. 先写好实现代码，再补测试

**Q2.** 下列哪一条可以算作 task frame 中的 **repository fact**？

- A. "API 应该对重复邮件返回 409"
- B. "大多数 REST 项目都用 409 表示冲突"
- C. "重复响应的测试在 `tests/test_accounts.py:44` 期望 409"
- D. "我记得上个迭代里用的是 409"

**Q3.** 仓库中目前**没有**任何关于"重复邮件"的错误响应，你需要决定公开 API 返回 409 还是 422。按讲义的分类，这个 unknown 属于：

- A. Discoverable：在仓库里再搜一搜就能找到答案
- B. Decidable：agent 有权自己选一个
- C. Deferred：放进 non-goals 以后再说
- D. Human：它改变公开兼容性，应在写进代码前交给人决定

**Q4.** 关于侦察（reconnaissance）何时可以停止，讲义的说法是：

- A. 读完仓库中所有与任务相关的目录之后
- B. 每个计划中的决定都已有证据支撑、被明确授权，或被列为 unknown 时
- C. 找到第一个相关测试之后
- D. 花满预定的时间预算之后

**Q5.** 对 `example()` 返回的 frame 执行 `frame.allowed_paths.append("migrations/0007_unique_email.py")`（`forbidden_paths` 中有 `"migrations/**"`），再调用 `validate(frame)`，实际返回：

- A. `['paths are both allowed and forbidden: migrations/0007_unique_email.py']`
- B. 抛出 `ValueError`
- C. `[]`
- D. `['forbidden paths are empty']`

**Q6.** 按讲义"Acceptance Before Implementation"，下列哪一条是**最强**的验收证据？

- A. `python3 -m unittest tests.test_accounts.SignupTests.test_duplicate_email_returns_409`，并注明它证明"重复邮件返回 409 且不新增账户"
- B. "tests pass"
- C. "代码审查看起来没问题"
- D. "CI 流水线是绿的"

**Q7.** 关于本节 `validate()` 的行为，下列说法正确的是：

- A. `facts` 为空列表时返回 `"facts are empty"`
- B. `unknowns` 非空时 frame 状态变为 `BLOCKED`
- C. acceptance 写成 `"tests pass"` 时会被拒绝
- D. 以上都不对：零个事实、`"tests pass"`、存在 unknown，`validate()` 都返回 `[]`，状态为 `READY`

**Q8.** 讲义说 task frame "should fit on one screen"。如果你写出的 frame 一屏放不下，讲义的建议是：

- A. 缩小字号或改用更紧凑的格式
- B. 这个任务可能包含多个可独立验证的变更，考虑拆分
- C. 删掉 unknowns 一节以节省篇幅
- D. 放弃 frame，直接让 agent 开始实现

---

## 三、动手 / 代码题

**Q9.** 讲义 Build It："Break the example in four ways: remove the goal, remove a fact receipt, overlap an allowed and forbidden path, and remove the acceptance command. The validator should refuse each frame for a different reason."

1. 写出四种破坏方式分别得到的 `validate()` 输出。
2. `tests/test_main.py` 覆盖了其中哪几种？缺了哪一种？请补一个测试。
3. 同时破坏 goal、acceptance 和路径重叠时，`render()` 的输出有什么特点？

**Q10.** `validate()` 中的重叠检查：

```python
    overlap = sorted(set(frame.allowed_paths) & set(frame.forbidden_paths))
    if overlap:
        issues.append(f"paths are both allowed and forbidden: {', '.join(overlap)}")
```

1. 为什么 `migrations/0007_unique_email.py` 与 `migrations/**` 不会被判为冲突？
2. 写一个支持 glob 的 `path_conflicts(allowed, forbidden)`，要求能发现"允许的文件落在禁止的模式里"和"允许的模式覆盖了禁止的文件"两种情况。
3. 使用 `fnmatch` 时要注意什么？

**Q11.** 讲义把 unknown 分成四类，并要求 agent "pause at human unknowns before the choice is buried in code"，但代码里 `unknowns: list[str]` 只是字符串列表，从不影响状态。请：

1. 设计一个带分类的 `Unknown` 数据结构；
2. 修改验证逻辑，使存在 human unknown 时 frame 不能是 READY；
3. 说明 `example()` 中的 "Whether email comparison is case-insensitive" 应该归入哪一类，理由是什么。

**Q12.** 讲义说 "Facts need receipts"、"'Tests pass' is not a proof plan"、"Record two or three facts with exact evidence"。而当前代码：

```python
    for fact in frame.facts:
        if not fact.evidence.strip():
            issues.append(f"unsupported fact: {fact.claim}")
```

实测 `RepositoryFact("409 is used", "trust me")` 和 acceptance `["tests pass"]` 都能通过。请增强验证：证据必须是 `路径:行号` 或命令收据；acceptance 不能是泛泛描述；至少有一个事实。写出代码并给出对上述反例的输出。

---

## 四、面试高频题

**Q13.**（基础必考）什么是 task frame？它包含哪几个字段？为什么要在 agent 动手写代码之前先写它？

**Q14.**（原理深挖）讲义说"能力强的 agent 用看似合理的选择填补空白，这才是危险的情况"。为什么能力越强反而越危险？unknown 与 assumption 的区别是什么？

**Q15.**（工程实践）给你一个陌生的中型仓库和一个需求，你如何在 15 分钟内完成"足够"的侦察？用什么工具、看哪些地方、什么时候停？

**Q16.**（场景设计）产品经理提了一句需求："注册时防止重复邮件。" 请现场写出 task frame，并指出哪些问题必须交给人决定。

**Q17.**（追问型）agent 按 frame 开始实现后，发现了一个与 frame 中事实矛盾的新证据（例如 409 其实只用于另一个端点）。应该怎么处理？task frame 与第 36 节的 scope contract 是什么关系？

---

## 五、参考答案与解析

### Q1 — 答案：A

讲义："The first unit of coding-agent work is therefore not an edit. It is a task frame backed by repository evidence." B、D 都是"先动手"，正是讲义要避免的；C 错，讲义明确说 "Do not read the entire repository"，侦察是有针对性地寻找约束。

### Q2 — 答案：C

讲义："'The API uses 409 for duplicates' is not a fact until you can point to the existing test or handler. A file path and line is enough." C 有 `文件:行号` 收据。A 是需求或主张（"应该"）；B 是行业惯例，不是本仓库的事实；D 是记忆，没有收据，属于 assumption。

### Q3 — 答案：D

讲义对 Human 的定义："the choice changes product behavior, cost, risk, or public compatibility." 公开 API 的错误码一旦发布，客户端就会依赖它。题目前提是仓库里没有现成的重复错误形状，所以 A 不成立（搜不到答案）；B 错，除非 task contract 明确授权，否则 agent 不能替产品决定公开契约；C 错，这个决定就在本切片内，无法推迟。注意：若仓库里已有 `tests/test_accounts.py:44` 期望 409，它就变成了 discoverable，答案由仓库给出。

### Q4 — 答案：B

讲义："Stop when every planned decision is either supported by evidence, explicitly delegated, or listed as an unknown. More reading after that point is often avoidance." A 是"通读"的变体；C 只覆盖六类约束中的一类；D 用时间而不是信息完备性作为标准。

### Q5 — 答案：C

实测返回 `[]`。重叠检查是 `set(allowed) & set(forbidden)`——**字符串完全相等**才算重叠，`"migrations/0007_unique_email.py"` 与 `"migrations/**"` 是两个不同的字符串，交集为空。这正是讲义中"Is a migration allowed?"想防的情况：frame 说禁止迁移，但允许列表里偷偷放了一个迁移文件，验证器看不出来。A 是我们**期望**的行为（见 Q10）；B、D 都不会发生。

### Q6 — 答案：A

讲义："Name the authoritative test and the claim it supports." A 同时给出了精确命令和它证明的主张。B 讲义原话否定："'Tests pass' is not a proof plan."；C 不是可复现的观察；D 只说明"某些测试通过了"，不说明是哪个测试、证明了什么。

### Q7 — 答案：D

实测：`facts=[]` → `[]`；`acceptance=["tests pass"]` → `[]`；`example()` 本身就带一个 unknown，状态仍是 `READY`。`validate()` 只检查 goal、allowed、forbidden、acceptance 非空，每个已有 fact 的 evidence 非空，以及路径字符串交集。A、B、C 描述的都是讲义期望、但代码没有实现的检查（见 Q11、Q12）。

### Q8 — 答案：B

讲义 Use It："The frame should fit on one screen. If it cannot, the task may contain multiple independently verifiable changes." A 只是掩盖问题；C 删掉的恰恰是最需要暴露的部分；D 背离本节主旨。

### Q9 — 参考答案

1. 实测输出（在 `example()` 基础上每次只改一处）：

| 破坏方式 | `validate()` 输出 |
|---------|------------------|
| goal 置空 | `['goal is empty']` |
| 去掉事实收据（evidence 置空） | `['unsupported fact: Duplicate errors use status 409']` |
| 允许与禁止重叠（把 `app/accounts.py` 加入 forbidden） | `['paths are both allowed and forbidden: app/accounts.py']` |
| acceptance 置空 | `['acceptance evidence is empty']` |

四种破坏各得到一个不同的拒绝原因，符合讲义要求。

2. 测试覆盖了 goal（`test_empty_goal_blocks_work`）、事实收据（`test_unsupported_fact_is_reported`）、路径重叠（`test_path_overlap_is_reported`），**缺少"去掉 acceptance"**；另外 "allowed/forbidden 为空" 两条规则也没有测试。补充：

```python
    def test_missing_acceptance_blocks_work(self):
        frame = module.example()
        frame.acceptance = []
        self.assertEqual(module.validate(frame), ["acceptance evidence is empty"])

    def test_empty_forbidden_paths_blocks_work(self):
        frame = module.example()
        frame.forbidden_paths = []
        self.assertIn("forbidden paths are empty", module.validate(frame))
```

用 `assertEqual(..., [...])` 而非 `assertIn` 还能顺带证明"只产生这一个原因"，满足"each frame for a different reason"。

3. 实测：标题变成 `# Task Frame: `（goal 为空，标题后面什么都没有）；`Status: BLOCKED`；"Acceptance evidence" 小节标题下没有任何条目；末尾新增 "## Blocking issues"，按 `validate()` 的检查顺序列出三条：`goal is empty`、`acceptance evidence is empty`、`paths are both allowed and forbidden: app/accounts.py`。`render()` 不会拒绝渲染 BLOCKED 的 frame，而是把阻塞原因写进文档——frame 本身就成了"为什么还不能开工"的说明。

### Q10 — 参考答案

1. 集合交集只比较字符串是否相等，不展开 glob；`**` 在这里只是两个普通字符。
2. 参考实现（已实际运行验证）：

```python
from fnmatch import fnmatchcase

def path_conflicts(allowed: list[str], forbidden: list[str]) -> list[str]:
    hits = []
    for a in allowed:
        for f in forbidden:
            if a == f or fnmatchcase(a, f) or fnmatchcase(f, a):
                hits.append(f"{a} ~ {f}")
    return sorted(set(hits))
```

实测：`path_conflicts([..., "migrations/0007_unique_email.py"], ["migrations/**", "deploy/**"])` → `['migrations/0007_unique_email.py ~ migrations/**']`；`path_conflicts(["app/*.py"], ["app/accounts.py"])` → `['app/*.py ~ app/accounts.py']`（允许模式覆盖了禁止文件）。在 `validate()` 中用它替换原来的集合交集即可。

3. 注意事项：
   - `fnmatch` 不是路径感知的，`*` 也能匹配 `/`：`fnmatch("migrations/a/b.py", "migrations/*")` 为 `True`。若要严格的"`*` 不跨目录、`**` 跨目录"语义，可用 Python 3.13 的 `PurePosixPath(p).full_match(pattern)`（实测 `PurePosixPath("migrations/a/b.py").full_match("migrations/**")` 为 `True`），或 `pathspec` 这类 gitignore 风格的库；而 `PurePath.match("migrations/**")` 在 3.13 中对多层路径返回 `False`，不能直接用。
   - `fnmatch.fnmatch` 在 Windows 上大小写不敏感，用 `fnmatchcase` 保持行为一致。
   - "两个模式之间是否有交集"（如 `app/**` 与 `app/*/secret.py`）无法用简单匹配判定，实践中通常把 allowed 尽量写成具体文件（讲义："Name the smallest allowed path set"），把 glob 留给 forbidden。

### Q11 — 参考答案

1. 数据结构：

```python
from dataclasses import dataclass
from typing import Literal

@dataclass(frozen=True)
class Unknown:
    question: str
    kind: Literal["discoverable", "decidable", "human", "deferred"]
```

2. 验证逻辑（已实际运行验证）：

```python
    for u in frame.unknowns:
        if u.kind == "human":
            issues.append(f"human decision required: {u.question}")
```

实测：把 "Whether email comparison is case-insensitive" 标为 `human` 时，输出 `['human decision required: Whether email comparison is case-insensitive']`；标为 `discoverable` 的 unknown（如 "Which test runner is used"）不产生问题。更细的做法是引入第三种状态，例如 `NEEDS_HUMAN`，与"结构不完整"的 `BLOCKED` 区分开；discoverable 的 unknown 可以产生 warn，提醒 agent 去查而不是去猜。

3. "邮件比较是否大小写不敏感"通常应先当作 **discoverable**：查一下现有的登录、查重或规范化代码（是否在存储前 `lower()`），仓库很可能已经给出答案。如果仓库没有任何先例，它就变成 **human**：大小写敏感与否会改变产品行为（`A@x.com` 和 `a@x.com` 是否算同一用户），甚至影响已有数据（可能已存在只差大小写的重复账户，需要迁移，而 frame 禁止了 `migrations/**`）。这正是讲义所说的"必须在决定被埋进代码前暂停"的情形。

### Q12 — 参考答案

```python
import re

EVIDENCE = re.compile(r"^[\w./-]+:\d+(-\d+)?$|^\$ .+ -> .+$")   # path:line[-line] 或 "$ cmd -> 结果"
GENERIC = {"tests pass", "all tests pass", "it works", "ci green"}

def validate_strict(frame) -> list[str]:
    issues = validate(frame)
    if not frame.facts:
        issues.append("no repository facts recorded")
    for fact in frame.facts:
        ev = fact.evidence.strip()
        if ev and not EVIDENCE.match(ev):
            issues.append(f"evidence is not a path:line or command receipt: {fact.evidence}")
    for a in frame.acceptance:
        if a.strip().lower() in GENERIC:
            issues.append(f"acceptance is not a proof plan: {a}")
    return issues
```

实测输出：

- `facts=[RepositoryFact("409 is used", "trust me")]`、`acceptance=["tests pass"]` → `['evidence is not a path:line or command receipt: trust me', 'acceptance is not a proof plan: tests pass']`
- 证据写成 `"$ python3 -m unittest tests.test_accounts -> OK"` → `[]`（命令收据被接受）
- `example()` 原样 → `[]`

说明：格式检查只能挡住"明显没有收据"的情况，挡不住"收据是编的"。更进一步可以让验证器真正打开 `app/accounts.py` 检查第 18 行是否存在、内容是否包含 `AccountStore`，或者重跑命令收据——这就从"格式正确"升级到"证据可核实"，下一节的 evidence plan 会继续沿着这个方向走。黑名单式的 `GENERIC` 也只能挡住常见措辞，更稳的规则是"acceptance 必须是可执行命令或带明确预期的观察"。

### Q13 — 参考回答要点

- **定义**：在编辑代码前写下的一份有界任务描述，每个判断都尽量有仓库证据支撑。
- **六个字段**：Goal（要改变的可观察行为）、Repository facts（带收据的已验证事实）、Allowed paths、Forbidden paths（变更的"负空间"）、Acceptance evidence（证明目标的命令或观察）、Unknowns（尚需证据或人类判断的决定）。
- **为什么先写**：agent 实现清晰和不清晰任务的速度一样快，代价却不一样；frame 把"猜测"暴露成显式的 unknown，把"完成"定义成可执行的证据，把改动范围限定在最小路径集合中。
- 加分点：frame 应能放在一屏内；放不下说明任务可以拆分。它是下一节 evidence-backed plan 的输入（讲义："It is the input to the next lesson"）。

### Q14 — 参考回答要点

- **为什么越强越危险**：能力弱的 agent 在模糊任务上会明显失败，容易被发现；能力强的 agent 会给出"干净、有测试、看起来合理"的实现，但其中隐含的选择（错误码、大小写规则、放在哪一层、要不要迁移）可能与系统现有契约不兼容。讲义："the implementation can be clean, tested, and still incompatible with the system."
- **unknown vs assumption**：讲义："An unknown is a controlled gap. An assumption is an uncontrolled answer to that gap." unknown 是写下来、可追踪、可分配给人或调查的问题；assumption 是被悄悄写进代码的答案，没有人审查过它。
- **处理方式**：discoverable 去查、decidable 自己定并记录理由、human 暂停询问、deferred 写入 non-goals。
- 加分点：引用 SWE-agent 论文的结论——agent 周围的接口（agent-computer interface）会改变其效果；task frame 就是接口的一部分。

### Q15 — 参考回答要点

- **按讲义六类约束有针对性地找**：
  1. 当前行为及调用方：`rg "def signup|signup\(" -n`，看入口和调用链；
  2. 最近的测试：`rg "duplicate|409" tests/ -n`；
  3. 公开契约/序列化形状：OpenAPI 文件、错误响应的 schema、对外的 DTO；
  4. 管这个路径的项目规则：`AGENTS.md`、`CONTRIBUTING`、目录下的 README；
  5. 构建与验证命令：`Makefile`、`pyproject.toml`、CI 配置；
  6. 类似的已完成变更：`git log -S "409" --oneline`、`git log -- app/accounts.py`，看本地惯例。
- **记录方式**：每发现一条约束就写成"主张 + `文件:行号`"，验证行为的就附命令结果。
- **停止条件**：每个计划中的决定都有证据、被授权或列为 unknown；继续读下去往往是在拖延（"often avoidance"）。
- 常见误区：从 README 开始逐目录通读；或者只看实现不看测试和公开契约。

### Q16 — 参考回答要点

- **Goal**：注册时，若邮箱已存在，请求被拒绝且不创建新账户（写行为，不写"改 accounts.py"）。
- **Facts（示例，需要真实收据）**：账户写入经过 `AccountStore`（`app/accounts.py:18`）；已有重复错误测试期望 409（`tests/test_accounts.py:44`）；存储层是否已有唯一约束（看 schema/迁移文件）。
- **Allowed**：`app/accounts.py`、`tests/test_accounts.py`；**Forbidden**：`migrations/**`、`deploy/**`。
- **Acceptance**：`python3 -m unittest tests.test_accounts`，并指明其中的 `test_duplicate_email_returns_409` 证明"重复邮件返回 409 且账户数不变"；附加 scope 收据：`git diff --name-only` 只包含允许路径（讲义练习 5）。
- **必须交给人的问题**：
  - 大小写/空白/Unicode 规范化规则（改变产品行为，可能影响已有数据）；
  - 唯一性放在应用层还是数据库层（数据库唯一约束需要迁移，而迁移在 forbidden 中）；
  - 公开错误码与错误体格式（若仓库没有先例，改变公开兼容性）；
  - 已存在的重复账户如何处理（属于 deferred 还是本切片）。
- **加分点**：并发注册的竞态——只在应用层检查无法防止两个请求同时通过，彻底解决需要数据库约束，这正说明"放在哪一层"是 human 决定。

### Q17 — 参考回答要点

- **处理新证据**：
  1. 立刻停下，不要"顺着已经写的代码继续"；
  2. 更新 frame：把错误的事实标记为已推翻，写入新事实和收据；
  3. 重新评估受影响的决定：原本 discoverable 的问题可能变成 human；
  4. 如果新证据改变了 goal、allowed paths 或 acceptance，需要重新获得批准，而不是 agent 自行扩展范围；
  5. 在 state/handoff 中记录这次修订，避免下一个会话又按旧 frame 行事。
- **与 scope contract 的关系**：task frame 是"开工前的思考产物"，包括事实与 unknowns；第 36 节的 scope contract 是"执行期的机器可检查契约"（allowed/forbidden files、acceptance criteria、rollback plan），由 gate 强制执行。frame 中的 allowed/forbidden/acceptance 经过确认后落入 scope contract；facts 与 unknowns 则进入下一节的执行计划。
- 加分点：把"推翻 frame 中的事实"本身当作一个值得记录的信号——它说明侦察阶段漏掉了某类约束，可以反馈到侦察清单中（第 46 节"把纠正转化为系统改进"）。

---

## 六、关联知识点

### 前置知识
- [阶段 14 · 31 Agent 工作台工程：能力强的模型为什么仍会失败](../../31-agent-workbench-why-models-fail/docs/zh.md)：讲义列出的先修课，模型失败多源于 workbench 缺失。
- [阶段 14 · 36 Scope Contracts 与任务边界](../../36-scope-contracts/docs/zh.md)：讲义列出的先修课，allowed/forbidden/acceptance 的机器可检查形式。
- [阶段 14 · 33 将 Agent 指令作为可执行约束](../../33-instructions-as-executable-constraints/docs/zh.md)：侦察时要找的"管这个路径的项目规则"。
- [阶段 14 · 42 综合项目：交付可复用的 Agent 工作台包](../../42-agent-workbench-capstone/docs/zh.md)：task frame 是在装好 workbench 后、动手前的第一步。

### 本节被哪些后续内容用到
- [阶段 14 · 44 制定有证据支撑的执行计划](../../44-plan-from-evidence/docs/zh.md)：讲义明确说 `outputs/task-frame.md` 是下一节的输入。
- [阶段 14 · 45 通过隔离与合并契约委派 Agent 任务](../../45-delegate-with-isolation/docs/zh.md)：子任务的 owned paths 与 forbidden paths 来自 frame 的路径边界。
- [阶段 14 · 49 梳理假设，优先验证风险最高的一项](../../49-map-assumptions-and-risk/docs/zh.md)：把 unknown / assumption 的思路扩展到产品层面。
- [阶段 14 · 51 编写保留判断空间的规格说明](../../51-write-specifications-that-preserve-judgment/docs/zh.md)：哪些决定该写死、哪些该留给执行者判断。

### 延伸关键词
`task frame` · `repository evidence` · `receipt` · `negative space` · `reconnaissance` · `discoverable / decidable / human / deferred` · `assumption vs unknown` · `acceptance before implementation` · `fnmatch / glob` · `requirements engineering` · `SWE-agent` · `agent-computer interface`
