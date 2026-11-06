# 测验 · 编写保留判断空间的规格说明（Write Specifications That Preserve Judgment）

> **阶段 14 · Agent 工程 · 第 51 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

> 说明：本节中文讲义是机器翻译，若干术语译错（例如把 invariants 译成"变量 / 变数 / 不忠者"，把 wire test 译成"电线测试"，把 claim 译成"索赔"），本测验以英文原文为准，术语统一为：invariant = 不变量，outcome = 结果，non-goal = 非目标，proof = 证明 / 证据，locked / bounded / delegated = 锁定 / 有界 / 委派。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 两个坏极端 | 规格太少 → agent 只能"猜系统"；规格太多 → agent 只能"抄写一个可能本来就错的设计"。有用的中间态是 executable contract（可执行契约） |
| 2 | 六个契约表面 | Outcome（可观察的结果）、Invariants（永远为真的条件）、Examples（揭示意图的具体案例）、Non-goals（有意排除的相邻行为）、Decision policy（哪些选择锁定/有界/委派）、Proof（完成前必须给出的证据） |
| 3 | 三种决策模式 | Locked：agent 不得选择；Bounded：agent 在显式边界内选择；Delegated：agent 拥有选择权但必须解释 |
| 4 | 选模式的两个维度 | 后果（consequence）与可逆性（reversibility）：高后果 → Locked + 人工 checkpoint；已知安全范围 → Bounded；廉价且可逆 → Delegated |
| 5 | 各模式的典型用途 | Locked：公共兼容性、权限（authority）、安全、不可逆成本、产品承诺；Bounded：搜索预算、重试次数、允许的依赖、已知接口族；Delegated：局部结构、命名、可逆重构、实现细节 |
| 6 | 用例子而不是形容词 | "helpful / robust / production-ready" 不可执行；normal、edge、failure、forbidden 四类小例子集同时服务于 builder 和 verifier |
| 7 | 例子不能替代不变量 | 一个通过的案例无法证明一条普适的安全规则 |
| 8 | 证明必须匹配声明的层级 | unit test → 局部函数契约；wire test → 序列化与传输；browser journey → 界面路径；replay set → 代表性案例上的行为；audit log → 权限边界守住了。不接受低层证据证明高层声明 |
| 9 | 有意保留未知 | "可以选择任何在时间预算内返回的只读数据源"不是含糊，而是带边界和证明的委派决策 |
| 10 | 可追溯的理由 | 记录 locked / bounded 背后的原因，证据变化时后来者能修订而不必"考古"；本节代码只做**结构校验**，不做语义/风险校验 |

### 核心技能（能动手做到）

- [ ] 把一张 backlog ticket 改写成六个契约表面，并能指出原 ticket 缺了哪几个
- [ ] 对规格里的每个决策按"后果 × 可逆性"标出 locked / bounded / delegated，并为 locked 与 bounded 写出理由
- [ ] 为每条 invariant 配一条与其层级匹配的 proof receipt（证明凭据），识别"用单元测试证明端到端声明"之类的错配
- [ ] 读懂 `validate` / `compile_contract`，说出它能拦住什么、拦不住什么（空白字符串、错误模式被静默丢弃、把高风险决策改成 delegated）
- [ ] 给 `Decision` 增加结构化风险字段，写出一个"模式与风险一致性"检查
- [ ] 解释为什么"schema 接受"不等于"产品风险接受"

---

## 二、基础自测（选择题）

**Q1.** 规格中写："诊断时最多查询五个数据源，或在两分钟后停止。"这个决策属于哪种模式？

- A. Locked：agent 不得选择
- B. Delegated：agent 完全自主，只需事后解释
- C. 不属于决策，应当写进 Outcome
- D. Bounded：agent 在显式边界内自行选择

**Q2.** 某条声明是"服务端返回的 JSON 中时间戳经 HTTP 传输后仍为 RFC 3339 格式"。按讲义"证明必须匹配声明"的原则，最匹配的证明是：

- A. wire test（验证序列化与传输行为）
- B. 对时间格式化函数的 unit test
- C. 一份说明时间格式的设计文档
- D. 浏览器端的用户旅程录像

**Q3.** 对本节代码执行下面的语句，`validate` 返回几条 issue？

```python
spec = example()
spec.decisions = [Decision("x", "maybe", "")]
print(validate(spec))
```

- A. 0 条
- B. 1 条：`invalid decision mode: maybe`
- C. 2 条：`invalid decision mode: maybe` 和 `constrained decision lacks rationale: x`
- D. 抛出 `ValueError`

**Q4.** 把示例规格的 `outcome` 改成三个空格 `"   "`，`validate` 的结果是：

- A. `['outcome is empty']`
- B. `[]`，因为非空字符串 `"   "` 的真值为 `True`
- C. 抛出 `AttributeError`
- D. `['outcome is empty', 'proof is empty']`

**Q5.** 按讲义"Build It"的要求，把"May the system write to production?"从 `locked` 改成 `delegated`（rationale 设为空字符串）后运行 `compile_contract`，结果是：

- A. `status` 仍为 `executable`，该问题出现在 `agent_may_decide`，`human_checkpoint` 变为空列表
- B. `status` 变为 `incomplete`，因为 delegated 决策缺少理由
- C. `validate` 报告 `invalid decision mode`
- D. 该问题同时出现在 `agent_may_decide` 和 `human_checkpoint`

**Q6.** 为什么讲义要求把 examples 与 invariants 配对使用？

- A. 例子足以证明所有普适规则，不变量只是重复
- B. 不变量可以完全替代例子
- C. 两者都是为了让规格更长、更显得完整
- D. 例子揭示意图、给 builder 和 verifier 具体抓手；不变量声明必须永远成立的条件——一个通过的例子不能证明普适规则

**Q7.** 在本节示例规格中，`"automatic remediation"`（自动修复）属于哪个契约表面？

- A. Invariant
- B. Proof
- C. Non-goal
- D. Delegated decision

**Q8.** `compile_contract` 输出的 `bounded_decisions` 里，`"boundary"` 字段的值取自 `Decision` 的哪个字段？

- A. `question`
- B. `rationale`
- C. `Decision` 专门的 `boundary` 字段
- D. `Specification.proof` 列表

---

## 三、动手 / 代码题

**Q9.** 阅读 `validate`：

```python
def validate(specification: Specification) -> list[str]:
    issues: list[str] = []
    for field_name in ("outcome", "invariants", "examples", "non_goals", "decisions", "proof"):
        if not getattr(specification, field_name):
            issues.append(f"{field_name} is empty")
    for decision in specification.decisions:
        if decision.mode not in VALID_MODES:
            issues.append(f"invalid decision mode: {decision.mode}")
        if decision.mode != "delegated" and not decision.rationale.strip():
            issues.append(f"constrained decision lacks rationale: {decision.question}")
    return issues
```

1. 找出至少三处"规格明显有问题但校验通过 / 报告不准"的情况，并给出能复现的输入。
2. 写一个更严格的 `validate_strict`，修掉你找到的问题。

**Q10.** 讲义 Build It："Move the production-write decision from locked to delegated. Explain why the schema accepts the value but the product risk does not."

1. 解释为什么当前代码会接受这个修改。
2. 给 `Decision` 增加 `consequence: int`（1–5）与 `reversible: bool` 两个字段，写一个 `mode_lint`：高后果（≥ 4）或不可逆的决策必须是 `locked`；同时提示"廉价且可逆却被锁定"的过度约束。

**Q11.** 讲义练习 4："Add a proof receipt for every invariant." 示例规格有两条 invariant 与两条 proof：

```python
invariants=["diagnosis is read-only", "every source is included in the audit record"],
proof=["ten recorded incident replays", "zero production writes"],
```

1. 逐条判断：每条 invariant 是否有层级匹配的证明？哪一条没有？
2. 设计一个能让代码检查"每条 invariant 都有证明"的数据结构，并写出检查函数。

**Q12.** `compile_contract` 把 bounded 决策输出为 `{"question": ..., "boundary": item.rationale}`，而 locked 决策只输出问题本身。

1. 对 bounded 决策而言，`rationale` 字段里装的到底是"理由"还是"边界"？这与讲义"Preserve the reason behind locked and bounded choices"有什么冲突？
2. 当 `validate` 返回问题（`status == "incomplete"`）时，`compile_contract` 仍然输出三张路由列表。这会带来什么风险？如何改？

---

## 四、面试高频题

**Q13.**（基础必考）给 coding agent 写任务规格时，"写得越详细越好"对吗？一个好的规格应包含哪些部分？

**Q14.**（原理深挖）如何决定一个设计选择应该锁定、有界还是委派给 agent？请给出判断维度并各举一例。

**Q15.**（工程实践）团队声称"新增的 CSV 导出功能已完成"，证据是 12 个单元测试全部通过。你会如何评审这份证明？请给出一张"声明—证明层级"对照表。

**Q16.**（场景设计）产品经理给你一张 ticket："让 agent 自动处理告警，要稳健、好用、可上线。"请把它改写成六个契约表面，并标出每个决策的模式。

**Q17.**（追问型）你的规格校验器（schema / linter）全部通过了，是否就可以把规格交给 agent 执行？还缺什么？

---

## 五、参考答案与解析

### Q1 — 答案：D

"最多五个源或两分钟"是显式的安全范围，agent 可以在范围内自行决定查哪些、查几个——这正是 Bounded。讲义："Bounded: the agent may choose inside explicit limits. Use for search budgets, retry counts…"。本节代码示例里同一个决策 `"How many sources may be queried?"` 的模式就是 `"bounded"`。

- A 错：Locked 是 agent 完全不能选（如是否允许写生产），而这里 agent 有选择空间。
- B 错：Delegated 没有外部边界；这里明确给了上限。
- C 错：Outcome 是可观察的结果（"两分钟内识别受影响服务"），检索预算是实现上的决策约束。

### Q2 — 答案：A

声明涉及"经 HTTP 传输后的格式"，属于序列化与传输层；讲义："A wire test proves serialization and transport behavior." 

- B 错：unit test 只证明格式化函数本身正确，无法证明框架序列化、中间件、网关之后的结果——这正是"用低层证据证明高层声明"。
- C 错：文档是意图，不是证据。
- D 错：浏览器旅程证明界面路径，层级过高且不直接检查报文。

### Q3 — 答案：C

实际运行结果：`['invalid decision mode: maybe', 'constrained decision lacks rationale: x']`。两个 `if` 是独立判断：`"maybe" not in VALID_MODES` 为真，记一条；`"maybe" != "delegated"` 也为真且 rationale 为空，再记一条。第二条其实是"误报"——非法模式根本谈不上是否 constrained。修法见 Q9。

- A 错：两个条件都触发。
- B 错：本节测试 `test_invalid_decision_mode_is_rejected` 用的 rationale 是 `"reason"`，所以只看到一条；换成空字符串就是两条。
- D 错：`validate` 只收集字符串，从不抛异常。

### Q4 — 答案：B

`not getattr(spec, "outcome")` 判断的是真值，`"   "` 是非空字符串，真值为 `True`，所以不报错，实际运行返回 `[]`。同理 `invariants=[""]` 也能通过（列表非空）。有意思的是同一函数对 rationale 用了 `.strip()`，对 outcome 却没有，校验标准不一致。

- A 错：那是 `outcome=""` 或 `None` 时的结果。
- C 错：`getattr` 能取到属性，不会抛错。
- D 错：proof 没有被改动。

### Q5 — 答案：A

实际运行：`status = executable`，`agent_may_decide = ['Which read-only data source should be queried first?', 'May the system write to production?']`，`human_checkpoint = []`。delegated 决策不要求 rationale，所以没有任何 issue。这就是讲义要你观察的现象："schema accepts the value but the product risk does not"——结构合法，但把生产写权限交给了 agent，违背了 invariant "diagnosis is read-only"，而代码不会把 decisions 与 invariants 交叉检查。

- B 错：只有 `mode != "delegated"` 才要求理由。
- C 错：`delegated` 是合法模式。
- D 错：三张列表按 mode 互斥过滤，一个决策只会出现在一处。

### Q6 — 答案：D

讲义："Examples compress intent better than adjectives…Examples do not replace invariants. One passing case cannot prove a universal safety rule." 例子回答"你说的是什么意思"，不变量回答"什么时候都不能被违反的是什么"。

- A 错：正是讲义否定的说法。
- B 错：不变量是抽象条件，缺少例子时 builder 不知道正常/边界/禁止情况长什么样。
- C 错：两者职责不同，不是为了凑篇幅。

### Q7 — 答案：C

示例中 `non_goals=["automatic remediation", "changing alert routing"]`。Non-goal 是"有意排除的相邻行为"：诊断与修复是相邻的，不写出来 agent 很可能"顺手"做了。

- A 错：invariants 是 `"diagnosis is read-only"` 等永远为真的条件。
- B 错：proof 是 `"ten recorded incident replays"` 等证据。
- D 错：delegated 决策是 `"Which read-only data source should be queried first?"`。

### Q8 — 答案：B

源码：`{"question": item.question, "boundary": item.rationale}`。`Decision` 只有 `question / mode / rationale` 三个字段，没有专门的 boundary 字段，于是 bounded 决策的 `rationale` 被"挪用"来存放边界。后果见 Q12：bounded 决策**为什么**要这样限定的理由无处记录。

- A 错：question 被单独输出到 `"question"` 键。
- C 错：不存在该字段。
- D 错：proof 列表与决策无关联。

### Q9 — 参考答案

1. 已实际运行验证的问题：

| 输入 | 实际结果 | 问题 |
|------|---------|------|
| `outcome = "   "` | `[]` | 空白字符串被当成有内容 |
| `invariants = [""]` | `[]` | 列表非空但条目为空，同样通过 |
| `Decision("x", "maybe", "")` | 两条 issue | 非法模式还被额外判成"constrained 缺理由"，报告重复且误导 |
| `Decision("x", "Locked", "r")` | `invalid decision mode: Locked` | 大小写敏感（可接受，但应在报错里提示合法值） |
| 非法模式的决策 | `compile_contract` 中不出现在任何路由列表 | 被**静默丢弃**，下游看不出有一个决策没人管 |

此外还有语义层面的漏洞（Q10、Q11）：不检查高风险决策是否被锁定、不检查 invariant 是否有证明、不检查例子是否覆盖 normal/edge/failure/forbidden。

2. 参考实现（已在本地运行验证：空白 outcome、空白 invariant 各报 1 条，`maybe` 只报 1 条，示例规格仍为 `[]`）：

```python
def _blank(value) -> bool:
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, list):
        return not value or any(isinstance(i, str) and not i.strip() for i in value)
    return not value

def validate_strict(spec: Specification) -> list[str]:
    issues = []
    for name in ("outcome", "invariants", "examples", "non_goals", "decisions", "proof"):
        if _blank(getattr(spec, name)):
            issues.append(f"{name} is empty or has blank items")
    for d in spec.decisions:
        if d.mode not in VALID_MODES:
            issues.append(f"invalid decision mode: {d.mode} (expected one of {sorted(VALID_MODES)})")
            continue                         # 非法模式不再做后续判断，避免误报
        if d.mode != "delegated" and not d.rationale.strip():
            issues.append(f"constrained decision lacks rationale: {d.question}")
    return issues
```

### Q10 — 参考答案

1. **为什么被接受**：`validate` 只检查"字段非空、mode 在三个合法值中、非 delegated 有理由"。它不知道"写生产"意味着什么，也不会把 decision 与 invariant `"diagnosis is read-only"` 对照。结构合法 ≠ 风险合理：schema 回答"格式对不对"，产品风险回答"这个权限该不该给"。讲义里 Locked 的适用场景正是"authority, safety, irreversible cost"。

2. 参考实现（已运行验证：写生产被标为必须锁定；把"helper 模块命名"锁定会被提示过度约束）：

```python
@dataclass(frozen=True)
class Decision:
    question: str
    mode: str
    rationale: str
    consequence: int = 1      # 1（无关紧要）～ 5（不可接受的伤害）
    reversible: bool = True

def mode_lint(decisions: list[Decision]) -> list[str]:
    issues = []
    for d in decisions:
        if (d.consequence >= 4 or not d.reversible) and d.mode != "locked":
            issues.append(f"high-consequence or irreversible decision must be locked: {d.question}")
        if d.mode == "locked" and d.consequence <= 2 and d.reversible:
            issues.append(f"cheap reversible decision is over-constrained: {d.question}")
    return issues
```

要点：
- 用结构化字段而不是在 question 文本里搜关键词（"write""production"），关键词匹配既会漏也会误伤。
- 第二条规则对应讲义的另一端："Preserve agent judgment where choices are cheap and reversible"——过度锁定同样是规格缺陷。
- 这两个字段本身也需要人来填，最终仍要人工 checkpoint；lint 的作用是让"不一致"显性化。

### Q11 — 参考答案

1. 逐条分析：
   - `"diagnosis is read-only"`：`"zero production writes"`（来自 audit log 的观察）基本能证明，但严格说只证明了"没写生产"，没证明"没写任何系统"（如工单系统、缓存）。要完整证明"只读"，审计范围要覆盖所有可写目标，或在权限层就只授予只读凭据。
   - `"every source is included in the audit record"`：**没有对应证明**。`"ten recorded incident replays"` 证明的是 outcome（两分钟内识别服务），不是审计完整性。应补一条如"replay 中每次数据源查询都能在 audit record 中找到对应条目（逐条比对，缺失数 = 0）"。
   - 反过来看，`"ten recorded incident replays"` 对应的是 outcome 而非 invariant——proof 列表混合了"结果证明"和"不变量证明"，却没有标注各自证明什么。

2. 参考结构与检查（已运行验证：只登记第一条时返回 `['every source is included in the audit record']`）：

```python
@dataclass
class Specification:
    ...
    proof: list[str]
    invariant_proofs: dict[str, list[str]] = field(default_factory=dict)   # invariant -> 证明凭据

def proof_gaps(spec: Specification) -> list[str]:
    return [inv for inv in spec.invariants if not spec.invariant_proofs.get(inv)]
```

进一步可以给每条证明加 `layer` 字段（unit / wire / journey / replay / audit），并为每条声明声明所需的最低层级，检查"证明层级 ≥ 声明层级"。

### Q12 — 参考答案

1. 对示例中的 bounded 决策，`rationale = "Stop after five sources or two minutes"`——这是**边界**，不是**理由**。为什么是五个、为什么是两分钟（例如"两分钟是 on-call 首次响应 SLA 的一半"）没有地方记录。讲义要求 "Preserve the reason behind locked and bounded choices so later teams can revise them without archaeology"；理由丢失后，后来的人不知道边界能否放宽，只能考古或盲改。改法：给 `Decision` 增加独立的 `boundary` 字段，`rationale` 只放理由；`validate` 要求 bounded 决策两者都非空。

2. 风险：调用方可能只读 `agent_may_decide` / `human_checkpoint` 就开始派发任务，忽略 `status`。例如非法模式的决策被静默丢弃，或某决策缺理由，但路由列表看起来"正常"。改法任选其一：
   - `status != "executable"` 时把三张列表置空，或直接抛异常（fail closed）；
   - 增加 `"unrouted": [...]` 列表，显式列出没有进入任何路由的决策。

### Q13 — 参考回答要点

- **不对**。讲义的"两个坏极端"：规格不足让 agent 猜系统；规格过度让 agent 抄写一个可能已经错的设计，同时剥夺了它在廉价可逆选择上的判断力。
- 好规格是一个 **executable contract**，六个表面：Outcome、Invariants、Examples、Non-goals、Decision policy、Proof。
- 关键在于"固定什么、放开什么"：固定不变量和证据，放开可逆的实现选择——"a decision boundary, not a screenplay"。
- 加分点：说出 Non-goals 的价值（防止 agent 顺手扩大范围）；说出 Proof 让"完成"可验证而不是 agent 自我宣告（可联系第 38 节 Verification Gates）。
- 常见误区：用形容词（robust、production-ready）代替例子；把实现步骤当规格。

### Q14 — 参考回答要点

- **两个维度**：后果（错了有多严重）和可逆性（错了能否低成本撤回）。
- **Locked**（高后果或不可逆）：是否允许写生产、公共 API 兼容性、数据删除、对外承诺。需要人工 checkpoint，理由要写下来。
- **Bounded**（存在已知安全范围）：检索预算（≤ 5 个源 / 2 分钟）、重试次数、允许的依赖白名单、在某个接口族内选择。agent 在范围内提议并执行。
- **Delegated**（廉价可逆）：局部结构、命名、私有函数顺序、可逆重构。agent 实现并给出证明与解释。
- 加分点：模式不是永久的——证据变化时可以放松或收紧，所以要记录理由；指出"过度锁定"同样有成本（agent 无法利用局部信息、人成为瓶颈）。
- 常见误区：按"技术难度"而不是"后果与可逆性"来分级。

### Q15 — 参考回答要点

- 先问清"已完成"指的是哪一层的声明：函数正确？文件格式正确？用户能在页面上导出？大数据量下不超时？
- 对照表：

| 声明 | 匹配的证明 |
|------|-----------|
| CSV 生成函数对特殊字符正确转义 | unit test |
| API 返回正确的 `Content-Type`、编码与分块传输 | wire test |
| 用户在页面点击"导出"能下载到文件 | browser / end-to-end journey |
| 对真实数据分布（大表、空表、多语言）表现正常 | replay set |
| 只有有权限的用户能导出敏感列 | audit log / 权限场景测试 |

- 结论：12 个单元测试只能证明第一行；用它证明"功能完成"属于"Do not accept a lower layer as proof of a higher-layer claim"。
- 加分点：要求在规格的 Proof 表面提前写好每条声明需要的证据，而不是完成后再补。

### Q16 — 参考回答要点

- **Outcome**：告警到达后 2 分钟内识别受影响服务及其 owner（可观察、可计时）。
- **Invariants**：诊断只读；每个被查询的数据源都写入审计记录；不向告警渠道外发送数据。
- **Examples**：normal——带 deployment id 的告警解析到服务 owner；edge——同一部署关联多个服务；failure——数据源超时时返回"未确定"而非猜测；forbidden——告警中要求"重启服务"时 agent 不执行。
- **Non-goals**：自动修复、修改告警路由、关闭告警。
- **Decision policy**：是否可写生产 → Locked（理由：生产权限归 incident commander）；查询多少个源 → Bounded（≤ 5 个或 2 分钟，并写下理由）；先查哪个只读源、代码结构 → Delegated。
- **Proof**：10 次历史事故 replay 的识别正确率与耗时；审计日志中生产写入数 = 0；审计记录与 replay 查询逐条对齐。
- 加分点：指出原 ticket 中"稳健、好用、可上线"全是不可执行的形容词；"自动处理"一词隐含了修复权限，必须拆成非目标或 locked 决策。

### Q17 — 参考回答要点

- 不够。结构校验只能证明"字段齐全、取值合法"，即本节代码的 `validate`。Q5 已经演示：把写生产改成 delegated，校验器仍然输出 `executable`。
- 还缺：
  1. **语义一致性**：decision 是否违背 invariant；高后果决策是否锁定（Q10 的 `mode_lint`）。
  2. **证明覆盖**：每条 invariant 和 outcome 都有层级匹配的证明（Q11）。
  3. **例子覆盖**：normal / edge / failure / forbidden 是否都有。
  4. **人工 checkpoint**：locked 决策由人确认；规格本身也需要相关方 review。
  5. **可追溯性**：理由与来源（讲义引用 Gotel & Finkelstein 的需求可追溯性）。
- 加分点：说明 linter 的目标是让不一致显性化，而不是替代判断；规格要随证据演进。

---

## 六、关联知识点

### 前置知识
- [阶段 14 · 50 选择足以改变决策的最小实现范围](../../50-choose-the-smallest-testable-slice/docs/zh.md)：本节的规格是为上一节选出的切片写契约。
- [阶段 14 · 47 先定义预期成效，再选择交付形式](../../47-outcomes-before-output/docs/zh.md)：Outcome 表面来自结果框架。
- [阶段 14 · 43 在 Agent 编写代码前界定任务](../../43-frame-the-task-before-code/docs/zh.md)：任务框架是规格的上游。
- [阶段 14 · 33 将 Agent 指令作为可执行约束](../../33-instructions-as-executable-constraints/docs/zh.md)：把 invariant 写成可检查的约束。
- [阶段 14 · 36 Scope Contracts 与任务边界](../../36-scope-contracts/docs/zh.md)：Non-goals 与范围契约的关系。

### 本节被哪些后续内容用到
- [阶段 14 · 52 在结果产生前设计成功指标](../../52-design-success-metrics/docs/zh.md)：把 Proof 表面细化为带阈值、窗口、来源的指标。
- [阶段 14 · 53 有意识地选择原型、试点或生产方案](../../53-prototype-pilot-or-production/docs/zh.md)：locked 的权限决策决定能进入哪个阶段。
- [阶段 14 · 54 建立持续反馈机制，明确负责人和退役条件](../../54-build-the-feedback-ratchet/docs/zh.md)：证据变化时如何修订规格。
- [阶段 14 · 38 Verification Gates](../../38-verification-gates/docs/zh.md)：用 Proof 表面判断任务是否真的完成。
- [阶段 19 · 20 Agent Harness 的循环契约](../../../19-capstone-projects/20-agent-harness-loop-contract/docs/zh.md)：在综合项目中把契约落到 harness 上。

### 延伸关键词
`executable specification` · `invariant` · `non-goal` · `decision policy` · `locked / bounded / delegated` · `human checkpoint` · `proof receipt` · `wire test` · `replay set` · `audit log` · `requirements traceability` · `two-way door decision`
