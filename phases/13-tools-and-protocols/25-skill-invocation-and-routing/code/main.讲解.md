# 代码讲解 · main.py

> **所属小节**：阶段 13 · 工具与协议 · 第 25 节 Skill Invocation 与路由 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 code/main.py`（在小节目录下）；测试 `python3 -m unittest discover -s code/tests -v` ｜ **依赖**：仅标准库（`json`、`math`、`re`、`dataclasses`、`enum`、`typing`），无需模型 API

---

## 1. 这份代码在考察什么

这份代码把"一个技能能不能被启动、被谁启动、启动哪一个"拆成两个相互独立的部分：

1. **策略（policy / eligibility）**：`InvocationPolicy` 描述宿主允许哪些 actor、哪些白名单、多深的组合；`CorePolicyAdapter` 只用应用提供的策略，`ExtensionPolicyAdapter` 在此基础上额外识别两个宿主字段（`user-invocable`、`disable-model-invocation`）。
2. **路由（routing / relevance）**：`route_request` 对显式通道（人类、应用、技能、harness）按精确名字选择；对隐式通道（模型、自主 agent）**先过滤资格、再按描述相关性排序**，低于阈值则弃权。

对应讲义的核心主张：

- "Invocation is an authority decision followed by a relevance decision"；
- 人类与模型的调用资格是两个独立维度（2×2 矩阵）；
- "Eligibility must precede ranking"；
- 宿主扩展字段只能由显式的适配器解释，不能被当作标准；
- 决策要可追踪：每个决策都带 `mode`、`score`、`reason`。

> 一句话：**用一个确定性的词汇路由器，把"谁可以调用"和"该调用哪个"两件事分开并逐条记录原因。** 词汇打分只是为了让策略边界可检查，讲义明确说它不代表生产中的模型路由质量——demo 里就有一个被误路由的例子值得仔细看。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Actor` | `str` 枚举 | human、model、agent、application、skill、harness 六种调用者 | 五个启动通道（模型与自主 agent 分开） |
| `_actor_label` | 私有函数 | 把任意对象转成可序列化的 actor 标签 | 未知 actor 的安全处理 |
| `SkillMetadata` | 冻结 dataclass | name、description、`runtime_extensions` | 目录中的路由身份 |
| `InvocationPolicy` | 冻结 dataclass + `__post_init__` | 各通道开关、阈值、三个白名单、最大组合深度；构造时严格校验类型 | 宿主策略 |
| `InvocationRequest` | 冻结 dataclass | actor、query、explicit_name、caller_name、depth | 调用请求 |
| `InvocationDecision` | 冻结 dataclass | activated、actor、skill_name、mode、score、reason；`to_dict()` | 可追踪的决策 |
| `_tokens` / `relevance_score` | 函数 | 小写字母数字 token 集合的 Jaccard 相似度 | 词汇路由 |
| `CorePolicyAdapter` | 类 | 只按策略判断各 actor 的资格 | 便携策略 |
| `_extension_false` / `_extension_true` | 私有函数 | 解释宿主字段的真假值 | 宿主字段解析 |
| `ExtensionPolicyAdapter` | 子类 | 在 core 允许后，再按两个宿主字段收紧 | 宿主适配器 |
| `build_invocation_matrix` | 函数 | 生成 2×2 矩阵并标出当前策略所在格 | 人类 × 模型矩阵 |
| `route_request` | 函数 | 显式通道按名选择；隐式通道资格过滤 → 打分 → 阈值 | 路由主流程 |
| `demo` | 函数 | 三个技能 × 七个请求 × 两种适配器 | 演示 |

数据流：`demo` 构造技能与策略 → 对每个 `InvocationRequest` 调 `route_request(skills, request, adapter)` → 显式分支：按名找技能 → `adapter.allows` → 决策；隐式分支：对所有技能 `adapter.allows` 过滤 → `relevance_score` 打分 → `max` 选出 → 与阈值比较 → 决策 → `to_dict()` → `json.dumps`。

---

## 3. 逐段精讲

### 3.1 `Actor` 与 `_actor_label`

```python
class Actor(str, Enum):
    HUMAN = "human"
    MODEL = "model"
    AGENT = "agent"
    APPLICATION = "application"
    SKILL = "skill"
    HARNESS = "harness"


def _actor_label(actor: object) -> str:
    value = getattr(actor, "value", actor)
    if isinstance(value, str) and value:
        return value
    if value is None:
        return "unknown"
    return type(value).__name__
```

- `Actor` 同时继承 `str` 和 `Enum`：成员既是枚举（可以用 `is` 比较），又是字符串（`Actor.HUMAN == "human"` 为真、可直接 JSON 序列化）。
- 讲义的五通道中"模型或自主 agent"被拆成 `MODEL` 与 `AGENT` 两个值，便于分别配置（`allow_model` / `allow_agent`）。
- `_actor_label` 处理"不是 `Actor` 的东西"：有 `.value` 就取（如 `SimpleNamespace(value="future")`）、是非空字符串就用、`None` 记为 `"unknown"`、其余记类型名（`object()` → `"object"`）。目的是让未知 actor 也能得到一个可序列化的拒绝决策，测试 `test_unknown_actor_routes_to_a_serializable_deny_decision` 验证了四种情况。

### 3.2 `InvocationPolicy`：严格校验的策略对象

```python
@dataclass(frozen=True)
class InvocationPolicy:
    allow_human: bool = True
    allow_model: bool = True
    allow_agent: bool = True
    allow_programmatic: bool = True
    allow_application: bool = True
    allow_skill: bool = False
    model_threshold: float = 0.2
    harness_allowlist: tuple[str, ...] = ()
    application_allowlist: tuple[str, ...] = ()
    skill_caller_allowlist: tuple[str, ...] = ()
    max_skill_depth: int = 1

    def __post_init__(self) -> None:
        for field_name in ("allow_human", ...):
            if type(getattr(self, field_name)) is not bool:
                raise TypeError(f"{field_name} must be a boolean")
        if (
            isinstance(self.model_threshold, bool)
            or not isinstance(self.model_threshold, (int, float))
            or not math.isfinite(self.model_threshold)
            or not 0.0 <= self.model_threshold <= 1.0
        ):
            raise ValueError("model_threshold must be a finite number from 0 to 1")
        ...
        if type(self.max_skill_depth) is not int or self.max_skill_depth < 1:
            raise ValueError("max_skill_depth must be a positive integer")
```

- 默认值的含义：人类、模型、agent、应用、harness 的**开关**都开着，技能组合默认关闭；但三个白名单默认为空——所以默认策略下应用与 harness **实际上都被拒绝**（开关只是必要条件）。
- `allow_programmatic` 这个名字只用于 **harness**；应用有自己的 `allow_application`。命名容易让人以为它控制所有"程序化"通道。
- `__post_init__` 是 dataclass 在自动生成的 `__init__` 之后调用的钩子，这里用来做类型校验：
  - `type(x) is not bool` 而不是 `isinstance(x, bool)`：拒绝字符串 `"false"`（真值为 True 的陷阱）；
  - 阈值先排除 `bool`（因为 `True` 是 `int` 的子类，`isinstance(True, int)` 为真），再要求有限且在 [0, 1]；
  - 白名单必须是**元组**且元素为非空字符串——列表会被拒绝（测试 `test_policy_rejects_invalid_threshold_and_boolean_types`），这保证了冻结对象真正不可变。
- ⚠️ 阈值允许 `0.0`：此时 `score < threshold` 永远不成立，零分的技能也会被激活（实测 "translate a poem" 激活了 `release-readiness`，score 0.0）。

### 3.3 请求与决策

```python
@dataclass(frozen=True)
class InvocationRequest:
    actor: Actor
    query: str
    explicit_name: str | None = None
    caller_name: str | None = None
    depth: int = 0


@dataclass(frozen=True)
class InvocationDecision:
    activated: bool
    actor: Actor | str
    skill_name: str | None
    mode: str
    score: float
    reason: str

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["actor"] = self.actor.value if isinstance(self.actor, Actor) else self.actor
        return data
```

- 决策同时记录 **mode**（哪个通道）、**score**（相关性，显式通道固定 1.0）和 **reason**（哪条策略生效）。讲义："A trace that records only `skill_used=true` hides the boundary where a failure happened."
- `actor` 字段类型为 `Actor | str`：未知 actor 用 `_actor_label` 转成字符串存放。
- ⚠️ `caller_name` 与 `depth` 由**请求方自报**，适配器直接信任它们（见 3.5）。

### 3.4 `relevance_score`：Jaccard 相似度

```python
def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", value.lower()))


def relevance_score(query: str, skill: SkillMetadata) -> float:
    query_tokens = _tokens(query)
    skill_tokens = _tokens(f"{skill.name} {skill.description}")
    if not query_tokens or not skill_tokens:
        return 0.0
    return len(query_tokens & skill_tokens) / len(query_tokens | skill_tokens)
```

- 小写后取连续字母数字串为 token；技能名中的连字符会把名字拆开（`incident-triage` → `incident`、`triage`），所以名字也参与匹配。
- 分数 = 交集 / 并集，范围 [0, 1]。例：`"triage this incident timeline evidence"` 对 `incident-triage` 得 4/10 = 0.4。
- 局限（实测）：
  - 没有词形还原：`requests` ≠ `request`、`ready` ≠ `readiness`。讲义自己的正例 "Is version 2.4.0 ready to publish?" 对 `release-readiness` 得 0 分。
  - 没有停用词：`from`、`and`、`an` 都计入，描述越长并集越大、分数越低——长描述天然吃亏。
  - 讲义："The deterministic router exists to make policy boundaries inspectable, not to claim that lexical matching reproduces production model routing."

### 3.5 `CorePolicyAdapter`：按 actor 分派的资格判断

```python
    def allows(self, skill, actor, request=None) -> tuple[bool, str]:
        if actor is Actor.HUMAN:
            return self.policy.allow_human, "human activation policy"
        if actor is Actor.MODEL:
            return self.policy.allow_model, "model activation policy"
        if actor is Actor.AGENT:
            return self.policy.allow_agent, "agent activation policy"
        if actor is Actor.APPLICATION:
            allowed = (self.policy.allow_application
                       and skill.name in self.policy.application_allowlist)
            return allowed, "application activation policy and target allowlist"
        if actor is Actor.SKILL:
            if not self.policy.allow_skill:
                return False, "skill composition policy"
            if request is None or not request.caller_name:
                return False, "skill composition requires a caller identity"
            if request.caller_name == skill.name:
                return False, "direct skill self-cycle"
            if request.caller_name not in self.policy.skill_caller_allowlist:
                return False, "skill caller allowlist"
            if request.depth < 1 or request.depth > self.policy.max_skill_depth:
                return False, "skill composition depth limit"
            return True, "skill caller allowlist and depth policy"
        if actor is Actor.HARNESS:
            allowed = (self.policy.allow_programmatic
                       and skill.name in self.policy.harness_allowlist)
            return allowed, "programmatic activation policy and allowlist"
        return False, f"unknown actor {_actor_label(actor)!r} has no activation policy"
```

- 返回 `(是否允许, 原因)` 二元组，原因字符串直接进入决策的 `reason`。
- 用 `is` 比较枚举成员：枚举成员是单例，`is` 精确且快。
- 应用与 harness 是"开关 **且** 目标在白名单"，对应讲义"exact configured name and target allowlist"。
- 技能组合依次检查：总开关 → 必须有 caller → 不能直接自调 → caller 在白名单 → `1 ≤ depth ≤ max_skill_depth`。
- 末尾兜底：任何未知 actor 都拒绝，**不会**继承 harness 等通道的权限（测试 `test_unknown_actor_does_not_inherit_harness_authority`）——默认拒绝（fail-closed）。
- ⚠️ 只检测"直接自环"：A→B→A 这种两技能环不被发现（实测 `caller_name="security-change-review"` 调 `release-readiness`、depth=2 被允许）。而 caller 与 depth 都是自报的，构造请求的代码可以随意声称。生产中应由宿主维护调用栈（测验 Q12）。
- **core 不解释宿主字段**：即使技能带 `{"user-invocable": False}`，core 适配器仍允许人类调用（测试 `test_core_adapter_does_not_invent_extension_semantics`）——讲义："If one parser assigns meaning to every observed frontmatter field, it silently promotes runtime conventions into a fake standard."

### 3.6 `ExtensionPolicyAdapter`：只收紧、不放宽

```python
def _extension_false(value: object) -> bool:
    return value is False or (isinstance(value, str) and value.lower() == "false")


def _extension_true(value: object) -> bool:
    return value is True or (isinstance(value, str) and value.lower() == "true")


class ExtensionPolicyAdapter(CorePolicyAdapter):
    def allows(self, skill, actor, request=None):
        allowed, reason = super().allows(skill, actor, request)
        if not allowed:
            return allowed, reason
        fields = skill.runtime_extensions
        if actor is Actor.HUMAN and _extension_false(fields.get("user-invocable")):
            return False, "host extension user-invocable=false"
        if actor in {Actor.MODEL, Actor.AGENT} and _extension_true(
            fields.get("disable-model-invocation")
        ):
            return False, "host extension disable-model-invocation=true"
        return True, reason
```

- **先调父类**：core 拒绝就直接返回；core 允许后才看宿主字段——扩展只能**收紧**资格，不能放宽。这是安全的组合方式。
- 识别的字段只有两个，语义与讲义一致：`user-invocable=false` 只拦人类；`disable-model-invocation=true` 拦模型与自主 agent，**不拦**人类、应用、技能、harness。
- 真假值解析接受布尔与大小写不敏感的 `"true"/"false"`（因为第 22 节的解析器把 frontmatter 标量都存成字符串）。
- ⚠️ **fail-open**：其他取值（`"yes"`、`"1"`、`"on"`）一律当作"没有设置"。实测 `{"disable-model-invocation": "yes"}` 的技能仍被模型激活。对于"禁用"类字段，更安全的做法是遇到无法识别的取值时拒绝或报错。
- 讲义说扩展适配器会"record which field changed the decision"——体现在 reason 字符串里（`host extension ...`），没有结构化字段。

### 3.7 `build_invocation_matrix`

```python
    active = None if policy is None else (policy.allow_human, policy.allow_model)
    for human, model, meaning in (
        (False, False, "programmatic-only or unavailable"),
        (True, False, "explicit human activation only"),
        (False, True, "implicit model activation only"),
        (True, True, "human and model activation"),
    ):
        rows.append({"human": human, "model": model, "meaning": meaning,
                     "active_policy": active == (human, model)})
```

- 固定输出四行，用元组比较 `active == (human, model)` 标出当前策略所在的格；不传策略时 `active` 为 `None`，没有任何一行被标记。
- 只看 `allow_human` 与 `allow_model` 两个开关，不考虑 agent、应用、技能等其他通道，也不考虑宿主扩展字段——它展示的是**策略级**的矩阵，不是某个技能的有效资格。

### 3.8 `route_request`：显式分支

```python
    if not isinstance(request.actor, Actor):
        actor = _actor_label(request.actor)
        return InvocationDecision(False, actor, None, "unsupported-actor", 0.0, ...)
    candidates = sorted(skills, key=lambda item: item.name)
    explicit_modes = {
        Actor.HUMAN: "explicit-human",
        Actor.APPLICATION: "programmatic-application",
        Actor.SKILL: "composed-skill",
        Actor.HARNESS: "programmatic-harness",
    }
    if request.actor in explicit_modes:
        mode = explicit_modes[request.actor]
        if not request.explicit_name:
            return InvocationDecision(False, request.actor, None, mode, 0.0, "an exact skill name is required")
        selected = next((skill for skill in candidates if skill.name == request.explicit_name), None)
        if selected is None:
            return InvocationDecision(False, request.actor, None, mode, 0.0, "named skill was not discovered")
        allowed, reason = adapter.allows(selected, request.actor, request)
        return InvocationDecision(allowed, request.actor, selected.name, mode, 1.0,
                                  reason if allowed else f"blocked by {reason}")
```

- 未知 actor 最先处理，返回 `unsupported-actor` 模式。
- 候选按名字排序，保证确定性。
- 四个显式通道都要求**精确名字**；名字缺失或未被发现分别给出不同的 reason（"identity-first"）。
- 找到后仍要过 `adapter.allows`——"An explicit request still passes policy"。
- 显式通道的 score 固定为 1.0，表示"身份匹配"，不是相关性。

### 3.9 `route_request`：隐式分支（资格 → 打分 → 阈值）

```python
    mode = "implicit-model" if request.actor is Actor.MODEL else "implicit-agent"
    if request.explicit_name:
        return InvocationDecision(False, request.actor, None, mode, 0.0,
            "implicit model or agent routing uses task relevance rather than an exact-name channel")
    if not candidates:
        return InvocationDecision(False, request.actor, None, mode, 0.0, "catalog is empty")

    eligible = []
    blocked_reasons = []
    for skill in candidates:
        allowed, reason = adapter.allows(skill, request.actor, request)
        if allowed:
            eligible.append((skill, reason))
        else:
            blocked_reasons.append(reason)
    if not eligible:
        reason = "no discovered skill is eligible for implicit routing"
        if blocked_reasons:
            reason = f"{reason}: {'; '.join(sorted(set(blocked_reasons)))}"
        return InvocationDecision(False, request.actor, None, mode, 0.0, reason)

    scored = [(relevance_score(request.query, skill), skill, reason) for skill, reason in eligible]
    score, selected, eligibility_reason = max(scored, key=lambda item: (item[0], item[1].name))
    if score < adapter.policy.model_threshold:
        return InvocationDecision(False, request.actor, selected.name, mode, round(score, 4),
                                  "best match did not meet the host threshold")
    return InvocationDecision(True, request.actor, selected.name, mode, round(score, 4), eligibility_reason)
```

- **模型不能"点名"**：带 `explicit_name` 的模型/agent 请求直接拒绝，名字通道只属于显式 actor。
- **资格先于排序**：先对全部候选 `adapter.allows`，只把合格者送去打分。被拒的原因去重排序后拼进 reason，便于看出"为什么没有任何候选"。
- **选择**：`max` 的键是 `(score, name)`，分数相同时选名字**更大**的（实测两个同描述技能中 `zulu-skill` 胜出）——确定但没有歧义处理（讲义练习 4）。
- **阈值与弃权**：低于阈值时 `activated=False`，但仍报告最佳候选名和分数，方便调参；全部 0 分时这个"最佳"只是名字最大的那个。
- 激活时 reason 是**资格原因**（如 "model activation policy"），而不是相关性说明——决策同时携带"为什么允许"和"分数多少"两类信息。
- 分数 `round(score, 4)` 只用于展示，阈值比较用的是未舍入的值。

### 3.10 `demo`

- 三个技能：`incident-triage`；`release-notes`（带 `{"user-invocable": True, "disable-model-invocation": True}`，即"仅人类"）；`release-readiness`。
- 策略：阈值 0.15，harness 白名单 `incident-triage`，应用白名单 `release-notes`，允许技能组合、caller 白名单 `release-readiness`、最大深度 2。
- 七个请求：人类点名 `release-notes`；模型问 incident；harness 点名 `incident-triage`；模型说"draft release notes…"；agent 问 incident；应用点名 `release-notes`；技能 `release-readiness` 以深度 1 调用 `incident-triage`。
- 每个请求分别经过 core 与 extension 两个适配器，对比哪一条因宿主字段而改变。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 策略与路由分离（adapter + `route_request`） | "authority decision followed by relevance decision" | 无 |
| core 与 extension 两个适配器 | 不把宿主约定冒充标准；调用方必须声明启用哪种语义 | 需要为每个宿主写并测试适配器 |
| 扩展只收紧不放宽（先调父类） | 宿主字段不能扩大 core 策略允许的范围 | 无 |
| 未知 actor 默认拒绝 | fail-closed，新通道不会意外继承权限 | 无 |
| 策略对象严格类型校验 | 防止 `"false"` 字符串、列表白名单等配置错误 | 阈值 0 仍被接受，导致零分激活 |
| 宿主字段只认 `true/false` | 简单 | 其他取值 fail-open；"禁用"类字段应 fail-closed |
| 显式通道必须精确名字 | identity-first，不做模糊匹配 | 用户拼写错误直接失败（可加"你是不是想找…"提示） |
| 模型通道拒绝点名 | 名字通道只属于显式 actor | 无 |
| 资格先于排序 | 被禁的高分候选不阻断合格候选 | 次优候选可能并不相关（demo 中的误路由），需要歧义边际或"被过滤最佳候选"提示 |
| Jaccard 词汇打分 | 确定、可手算、无需模型 | 不能代表真实路由质量；没有词形还原和停用词 |
| 平局按名字逆序 | 结果确定 | 应视为歧义并询问 |
| caller、depth 由请求自报 | 实现简单 | 可伪造；只能检测直接自环；应由宿主维护调用栈 |
| 决策带 mode/score/reason | 可追踪、可审计 | reason 是自由文本，统计时不便；可加结构化 code |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `str` + `Enum` 多重继承 | `class Actor(str, Enum)` | 成员既是枚举也是字符串，可直接序列化 |
| 枚举身份比较 | `actor is Actor.HUMAN` | 枚举成员是单例，用 `is` 比较 |
| `getattr` 默认值 | `getattr(actor, "value", actor)` | 没有该属性时返回默认值 |
| `field(default_factory=dict)` | `runtime_extensions: dict[str, object] = field(default_factory=dict)` | 可变默认值必须用工厂函数，否则所有实例共享同一个字典 |
| `__post_init__` | `InvocationPolicy.__post_init__` | dataclass 构造后自动调用，用于校验 |
| `type(x) is bool` | `type(getattr(self, field_name)) is not bool` | 精确类型判断，排除子类和真值字符串 |
| `bool` 是 `int` 子类 | `isinstance(self.model_threshold, bool) or not isinstance(..., (int, float))` | 必须先排除 `True/False`，否则会被当作 1/0 |
| `math.isfinite` | `math.isfinite(self.model_threshold)` | 排除 `nan` 与 `inf` |
| 链式比较 | `0.0 <= self.model_threshold <= 1.0` | 等价于两个比较用 `and` 连接 |
| 元组解包返回 | `allowed, reason = super().allows(...)` | 多返回值 |
| `super()` | `super().allows(skill, actor, request)` | 调用父类实现，再在其上叠加逻辑 |
| 集合成员 | `actor in {Actor.MODEL, Actor.AGENT}` | 集合字面量做成员判断 |
| `re.findall` + `set` | `set(re.findall(r"[a-z0-9]+", value.lower()))` | 提取所有匹配并去重 |
| 集合运算 | `query_tokens & skill_tokens`、`query_tokens \| skill_tokens` | 交集、并集 |
| 字典作分派表 | `explicit_modes = {Actor.HUMAN: "explicit-human", ...}` | 用映射代替一串 if |
| `next` 带默认值 | `next((skill for skill in candidates if ...), None)` | 取第一个匹配项 |
| `max(key=...)` 元组键 | `max(scored, key=lambda item: (item[0], item[1].name))` | 先比分数再比名字 |
| 三元组解包 | `score, selected, eligibility_reason = max(...)` | 一次取出三个值 |
| 条件表达式 | `reason if allowed else f"blocked by {reason}"` | 一行 if/else |
| `str.join` + `sorted(set(...))` | `'; '.join(sorted(set(blocked_reasons)))` | 去重、排序、拼接 |
| `round` | `round(score, 4)` | 仅用于展示 |
| `!r` 格式 | `f"unknown actor {_actor_label(actor)!r} ..."` | 带引号显示字符串 |
| 生成器表达式 + 列表推导 | `[route_request(skills, request, core).to_dict() for request in requests]` | 批量生成决策 |
| `json.dumps(sort_keys=True)` | `print(json.dumps(result, indent=2, sort_keys=True))` | 输出键按字母序排列（所以 `human_model_matrix` 出现在最后） |

---

## 6. 运行结果解读

实际运行（Python 3.13，`python3 code/main.py`，退出码 0）。为便于阅读整理成表（原始输出为 `sort_keys=True` 的 JSON）：

| # | 请求 | core 决策 | extension 决策 |
|---|---|---|---|
| 1 | 人类点名 `release-notes` | 激活，explicit-human，1.0，"human activation policy" | 同左（`user-invocable` 为 True，不拦） |
| 2 | 模型："triage this incident timeline evidence" | 激活 `incident-triage`，0.4 | 同左 |
| 3 | harness 点名 `incident-triage` | 激活，programmatic-harness，1.0 | 同左 |
| 4 | 模型："draft release notes from merged pull requests" | 激活 **`release-notes`**，0.6667 | 激活 **`release-readiness`**，0.2308 |
| 5 | agent："triage this incident timeline evidence" | 激活 `incident-triage`，implicit-agent，0.4 | 同左 |
| 6 | 应用点名 `release-notes` | 激活，programmatic-application，1.0 | 同左（扩展字段不拦应用） |
| 7 | 技能 `release-readiness` 以深度 1 调 `incident-triage` | 激活，composed-skill，"skill caller allowlist and depth policy" | 同左 |

`human_model_matrix` 四行中只有 `(human=true, model=true)` 的 `active_policy` 为 true——因为策略的两个开关都开着。

逐项解读：

- **第 1、6 行**：`release-notes` 是"仅人类"技能（`disable-model-invocation: true`），但人类与应用都能显式启动它——`disable-model-invocation` 只拦模型/agent。
- **第 2、5 行**：手算 Jaccard = 4/10 = 0.4 ≥ 0.15。agent 与模型共享同一套打分逻辑，只是 mode 不同。
- **第 4 行是全输出中最值得讨论的一行**：
  - core 适配器不认识宿主字段，`release-notes` 合格，得分 6/9 = 0.6667，选中——这是"正确的技能、错误的策略"（宿主本想禁止模型调用它）。
  - extension 适配器把 `release-notes` 过滤掉，剩下 `release-readiness` 得 3/13 = 0.2308，仍高于 0.15，于是激活——这是"正确的策略、错误的技能"：用户想写发布说明，却被路由到发布就绪审查。
  - 讲义把它描述为"a blocked top lexical match being removed before an eligible alternative is ranked"，这在**策略顺序**上是对的，但结果说明：仅靠"资格先于排序"还不够，还需要更高的阈值、歧义边际，或在"被过滤的候选明显更相关"时弃权并提示用户显式调用（测验 Q9）。
- **第 7 行**：caller 在白名单、深度 1 在 [1, 2] 内、caller ≠ target，允许。注意这些值都是请求自报的。

---

## 7. 动手改一改

1. **（讲义练习 1）** 构造四种 `InvocationPolicy`（两个开关的四种组合），分别调用 `build_invocation_matrix`，确认 `active_policy` 标在正确的格，并为每格写一个合理的用例。
2. **（讲义练习 2）** 实现"仅应用"策略：`allow_human=False, allow_model=False, allow_agent=False`，应用白名单含目标技能，写测试证明人类与模型都被拒绝、应用被允许。
3. **（讲义练习 4）** 加入歧义边际：合格候选前两名分差小于 `margin` 时返回 `mode="ask"`（测验 Q11）；再加一条"若被资格过滤掉的最佳候选分数明显更高，则弃权并在 reason 里提示可显式调用该技能"，让 demo 第 4 行不再误路由。
4. **（讲义练习 5）** 用宿主维护的调用栈替代自报的 `caller_name`/`depth`，检测任意长度的环（测验 Q12）。
5. **fail-closed 的扩展解析**：对已识别字段的未知取值（如 `"yes"`）返回拒绝并给出 `invalid host extension value` 的 reason；为 `user-invocable` 与 `disable-model-invocation` 各写一组取值表测试。
6. **（讲义练习 3、6）** 为一个部署技能写 10 条 near miss，加上 5 条正例、5 条明显负例，分别用 core 与 extension 适配器跑一遍，输出混淆矩阵并解释每一条变化。

---

## 8. 常见坑

- **把 `user-invocable: false` 当成"禁用"**：它只去掉用户直接调用，模型仍可选择。
- **把 `disable-model-invocation: true` 当成"隐藏"**：用户、应用、技能、harness 仍能显式启动。
- **默认策略下应用/harness 被拒**：`allow_application=True` 只是开关，白名单为空就全部拒绝。
- **`allow_programmatic` 只管 harness**：名字容易误导。
- **阈值设为 0**：零分技能也会被激活。
- **以为"资格先于排序"就能保证选对**：过滤后的最高分可能与请求无关（demo 第 4 行）。
- **平局时的"确定"选择**：名字逆序胜出，看起来稳定，其实是歧义。
- **宿主字段写成 `"yes"`/`"1"`**：本适配器当作没写（fail-open）。
- **信任请求自报的 caller 与 depth**：可以伪造，且只检测直接自环。
- **用词汇分数评估路由质量**：讲义的正例在这里得 0 分；词汇路由只用于检查策略边界。
- **把激活当成授权**：激活只加载指令，不批准任何工具、脚本、网络或密钥访问。

---

## 9. 测试在验证什么

运行方式（在小节目录下）：`python3 -m unittest discover -s code/tests -v`。测试设置 `sys.dont_write_bytecode = True`。实际结果：**Ran 23 tests … OK**。

测试共用 `SKILLS = (incident-triage "Triage incident timeline evidence.", release-notes "Draft release notes from merged changes.")`，`load_bundled_router` 用 `importlib.util.spec_from_file_location` 动态加载随包脚本 `outputs/skill-invocation-router/scripts/simulate_invocation.py`。

| 用例 | 验证的性质 |
|---|---|
| `test_matrix_contains_all_human_model_quadrants` | 矩阵恰好包含四种 `(human, model)` 组合 |
| `test_human_activation_requires_exact_name` | 人类请求没有名字 → 拒绝，reason 含 "exact skill name" |
| `test_human_explicit_activation_succeeds` | 人类点名 → 激活，mode 为 `explicit-human` |
| `test_model_routes_by_description_relevance` | 模型按描述选中 `incident-triage` |
| `test_agent_routes_by_description_relevance` | agent 同样能路由，mode 为 `implicit-agent` |
| `test_near_miss_below_threshold_does_not_activate` | "translate a poem" 得 0 分、低于 0.1，不激活 |
| `test_programmatic_activation_obeys_allowlist` | harness 白名单内允许、白名单外拒绝 |
| `test_application_activation_requires_exact_target_allowlist` | 应用白名单内允许（mode `programmatic-application`），白名单外拒绝 |
| `test_skill_composition_requires_caller_and_depth_policy` | 深度 1 允许、深度 3（超过 2）拒绝且 reason 含 "depth" |
| `test_skill_composition_rejects_direct_cycle` | caller 与 target 相同 → "self-cycle" |
| `test_empty_harness_allowlist_denies_programmatic_activation` | 默认空白名单 → harness 被拒 |
| `test_unknown_actor_does_not_inherit_harness_authority` | 四种非 `Actor` 值调用 `allows` 都被拒，reason 含 "unknown actor" |
| `test_unknown_actor_routes_to_a_serializable_deny_decision` | 四种未知 actor 经 `route_request` 得到 `unsupported-actor` 决策，`to_dict()` 可 JSON 往返，actor 标签分别为 `future`、`future`、`unknown`、`object` |
| `test_policy_rejects_invalid_threshold_and_boolean_types` | 负阈值、字符串布尔、列表白名单、深度 0 都在构造时报错 |
| `test_core_adapter_does_not_invent_extension_semantics` | core 适配器忽略 `user-invocable: False`，人类照常激活 |
| `test_extension_adapter_can_disable_human_activation` | extension 适配器据此拒绝人类 |
| `test_extension_adapter_can_disable_model_activation` | 字符串 `"true"` 的 `disable-model-invocation` 拒绝模型 |
| `test_implicit_routing_ranks_only_eligible_candidates` | 先断言被禁技能分数更高，再断言路由选中合格的 `incident-review`——"资格先于排序"的核心测试 |
| `test_implicit_routing_reports_when_no_candidate_is_eligible` | `allow_model=False` → 无合格候选，skill_name 为 None、score 为 0 |
| `test_relevance_score_is_deterministic` | 同输入同输出 |
| `test_bundled_router_enforces_recognized_invocation_extension` | 随包脚本：`recognizedExtensions` 含 `user-invocable` 时，`--user-invocable false` 拒绝人类，adapter 为 `host-extension-policy` |
| `test_bundled_router_rejects_invalid_policy_types` | 随包脚本：`allowModel: "false"`、`modelThreshold: -1` 抛 `ValueError` |
| `test_bundled_router_checks_eligibility_before_relevance` | 随包脚本：被扩展禁止时 score 为 0.0，即**不打分**直接拒绝 |

测试没有覆盖、值得补的地方：

- 两技能环（A→B→A）与自报深度的伪造（当前会被允许）；
- 宿主字段的非标准取值（`"yes"` 当前 fail-open）；
- 阈值为 0 时零分激活；
- 平局的处理；
- demo 第 4 行这类"过滤后误路由到邻居技能"的 near miss；
- 随包脚本与 `main.py` 的默认值差异：脚本中 `modelThreshold` 缺省为 1.0、各 `allow*` 缺省为 False（缺什么就拒绝什么），而 `main.py` 的 `InvocationPolicy` 缺省阈值 0.2、开关多为 True——两者对"空策略"的结论相反，值得用同一组 fixture 对拍。
