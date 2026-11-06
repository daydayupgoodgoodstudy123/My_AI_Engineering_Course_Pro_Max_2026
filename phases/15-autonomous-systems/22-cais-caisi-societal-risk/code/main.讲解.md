# 代码讲解 · main.py

> **所属小节**：阶段 15 · 自主系统 · 第 22 节 CAIS、CAISI 与社会规模风险 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`dataclasses`），无需网络、无需 API key

---

## 1. 这份代码在考察什么

这是一个约 150 行的"四风险清单"小工具：用 7 个特征描述一个部署，按 CAIS 四风险框架（malicious use、AI races、organizational risks、rogue AIs）打标签，再为每个标签打印一份缓解措施清单。

它考察的是：

1. **四风险框架的可操作化**：把讲义里的定性描述翻译成能运行的 if 规则——以及这种翻译会丢掉什么。
2. **组织风险是"任何一个子杠杆缺失就触发"**：对应讲义 Where organizational risk lives 一节。
3. **阶段 15 的知识地图**：`MITIGATIONS` 字典把第 10–21 节的控制措施挂到四类风险上，相当于整个阶段的索引。

讲义自己的定位："It's a reading aid for the framework, not a substitute for human judgment." 读这份代码的最大收获，恰恰是找出它的规则在哪里**漏标、误标**。

> 一句话：**把风险分类写成规则很容易，难的是规则覆盖了讲义说的全部维度、并区分"有风险"和"已缓解"。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Deployment` | dataclass | 部署的 7 个特征：是否面向公众、是否涉及有害能力、竞争压力、独立审计、多层防御、信息安全、自主运行时长 | 待审查对象 |
| `MITIGATIONS` | 模块级字典 | 风险类别 → 缓解措施列表（标注对应的阶段 15 课号） | 四风险 × 缓解 |
| `tag` | 函数 | 4 条 if 规则，返回风险标签列表 | 四风险打标签 |
| `report` | 函数 | 打印特征、标签和对应缓解清单 | 审查报告 |
| `main` | 函数 | 构造 low / mid / high 三个部署并逐个报告，最后打印 HEADLINE | 演示驱动 |

数据流：`main` 构造 3 个 `Deployment` → 对每个调用 `report(d)` → `tag(d)` 产生标签 → 按标签查 `MITIGATIONS` → 打印。

---

## 3. 逐段精讲

### 3.1 `Deployment`：用 dataclass 描述一个部署

```python
@dataclass
class Deployment:
    name: str
    public_facing: bool
    handles_harmful_capabilities: bool   # e.g. bio/cyber uplift possible?
    competitive_pressure: bool           # rushed to launch ahead of rivals?
    independent_audit: bool
    multi_layer_defense: bool
    information_security: bool           # weights / evals / keys hardened
    agent_autonomy_hours: float          # per Lesson 1 / 21
```

- `@dataclass` 根据类型注解自动生成 `__init__`、`__repr__`、`__eq__`。所有字段都没有默认值，所以构造时 8 个参数一个都不能少（少传会抛 `TypeError: ... missing 6 required positional arguments`）。
- 字段分三组：
  - **威胁面**：`public_facing`、`handles_harmful_capabilities`；
  - **结构压力**：`competitive_pressure`；
  - **组织子杠杆**：`independent_audit`、`multi_layer_defense`、`information_security`；
  - **自主程度**：`agent_autonomy_hours`。
- ⚠️ 讲义列出的组织风险子杠杆有**四个**：safety culture、rigorous audits、multi-layered defenses、information security。这里**没有 `safety_culture` 字段**——而讲义说它是 "a strong predictor of the other levers"。HEADLINE 也写着 "four levers every team controls"，代码只实现了三个。
- ⚠️ 注释 "per Lesson 1 / 21" 暗示自主时长与 METR time horizon 有关，但两者概念不同：horizon 是模型能力（专家完成任务所需时间），这里是部署允许 agent 无人监督运行多久。

### 3.2 `MITIGATIONS`：阶段 15 的索引

```python
MITIGATIONS = {
    "malicious_use": [
        "constitutional hardcoded prohibitions (Lesson 17)",
        "Llama Guard input/output classifier (Lesson 18)",
        "tool allowlist per task (Lessons 10, 11)",
    ],
    "ai_races": [...],
    "organizational_risks": [...],
    "rogue_ais": [
        "kill switches and canary tokens (Lesson 14)",
        "propose-then-commit HITL (Lesson 15)",
        "deceptive-alignment monitoring (Lesson 20 DeepMind FSF)",
        "durable checkpoints and rollback (Lesson 16)",
    ],
}
```

| 风险 | 缓解措施 | 对应阶段 15 课 |
|------|---------|--------------|
| malicious_use | 硬编码禁止、输入输出分类器、按任务的工具白名单 | 17、18、10/11 |
| ai_races | scaling policy + Risk Reports、公开 Frontier Safety Roadmap、外部能力评估 | 19/20、21 |
| organizational_risks | 安全文化与上报渠道、按固定节奏独立审计、多层防御、RAND SL-4 信息安全 | 10/13/14/17/18、19 |
| rogue_ais | kill switch 与 canary、propose-then-commit、欺骗性 alignment 监控、checkpoint 与 rollback | 14、15、20、16 |

- 字典的键是字符串常量，`tag()` 返回的标签必须与这些键完全一致，否则 `MITIGATIONS[t]` 会抛 `KeyError`。生产代码里通常用 `Enum` 避免拼写错误。
- ⚠️ ai_races 的缓解措施都是**实验室级**的（发布 scaling policy、公开路线图）。对一家用 API 做 SaaS 的创业公司（main 中的 mid 部署），这些措施基本不可执行，更现实的是"把竞争压力下的发布节奏和审计绑定"。

### 3.3 `tag`：四条规则

```python
def tag(d: Deployment) -> list[str]:
    tags = []
    if d.handles_harmful_capabilities and d.public_facing:
        tags.append("malicious_use")
    if d.competitive_pressure:
        tags.append("ai_races")
    org_missing = (
        (not d.independent_audit)
        or (not d.multi_layer_defense)
        or (not d.information_security)
    )
    if org_missing:
        tags.append("organizational_risks")
    if d.agent_autonomy_hours >= 4.0:
        tags.append("rogue_ais")
    return tags
```

逐条分析：

| 规则 | 逻辑 | 问题 |
|------|------|------|
| malicious_use | 有害能力 **且** 面向公众 | 内部部署永远不触发，漏掉内部滥用和权重泄漏后的滥用 |
| ai_races | 有竞争压力 | 只看压力，不看是否有独立审计来对冲 |
| organizational_risks | 三个子杠杆任一为 False | 缺 safety_culture；64 种布尔组合中 56 种会触发（87.5%），区分度低 |
| rogue_ais | 自主时长 ≥ 4.0 小时 | 硬阈值无出处；3.99 不触发、4.0 触发；不考虑有无工具、有无 HITL |

- `org_missing` 等价于 `not (a and b and c)`（德摩根定律）。也可以写成 `not all([...])`。
- 规则之间相互独立、顺序固定，所以标签列表总是按 malicious → races → org → rogue 的顺序出现。
- ⚠️ 讲义说四类"不互斥"，代码也允许多标签——这一点是对的。但代码**只判断暴露，不判断缓解是否到位**：一个已经有 Llama Guard 和硬编码禁止的公开生物问答服务，与一个什么都没有的服务，得到完全相同的 `malicious_use` 标签和相同的缓解清单。

### 3.4 `report`：打印审查结果

```python
def report(d: Deployment) -> None:
    tags = tag(d)
    print(f"\nDeployment: {d.name}")
    print("-" * 70)
    print(f"  public_facing            = {d.public_facing}")
    ...
    if tags:
        print(f"  tagged risks: {tags}")
        for t in tags:
            print(f"\n  mitigations for {t}:")
            for m in MITIGATIONS[t]:
                print(f"    - {m}")
    else:
        print("  no tagged risks (check sub-levers manually)")
```

- 先打印全部输入特征，再打印标签与清单——审查报告"可追溯"：读者能看到结论来自哪些输入。
- `if tags:` 利用空列表为假的特性。
- ⚠️ "no tagged risks" 容易被误读为"没有风险"。skill 文件要求对"不适用"的类别也给一句话理由，代码没有做到。

### 3.5 `main`：三个部署

| 部署 | 关键特征 | 标签 |
|------|---------|------|
| low：internal refactor helper | 内部、无有害能力、无压力、三杠杆全 True、1 小时 | `[]` |
| mid：public coding agent | 公开、无有害能力、有压力、infosec=False、4.0 小时 | `ai_races, organizational_risks, rogue_ais` |
| high：autonomous ML research agent | 全部风险特征为真、三杠杆全 False、48 小时 | 四类全中 |

- 三个部署都用**关键字参数**构造（`name=..., public_facing=...`），可读性好，也让后续给 dataclass 增加带默认值的字段时不影响这里。
- mid 的 `agent_autonomy_hours=4.0` 恰好等于阈值，是 rogue_ais 被触发的唯一原因。
- HEADLINE 的结论"organizational risk is the lever practitioners actually pull"对应讲义 "the most actionable for practitioners"。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 布尔特征 + if 规则 | 简单透明，便于对照讲义 | 风险不是二值的；生产会用分级评分（低/中/高）并记录证据 |
| 只有 3 个组织子杠杆 | 简化 | 漏掉讲义中最具预测力的 safety culture；应补字段 |
| malicious_use 需"公开 + 有害" | 把公开接口当主要滥用渠道 | 漏掉内部滥用与泄漏；应以"有害能力"为主条件、公开度调严重度 |
| rogue_ais 用 4 小时硬阈值 | 体现"风险随自主时长增长" | 边界突变、无出处；应结合工具权限、不可逆副作用、HITL 分级 |
| 每个标签打印固定缓解清单 | 当作学习索引很方便 | 不区分"已做/未做"；生产应输出缓解缺口与 hard reject |
| 没有就绪等级 | 讲义只要求"阅读辅助" | skill 文件要求输出 production / staging / research-only |
| 字符串作为类别键 | 直观 | 拼写错误会 `KeyError`；可改用 `Enum` |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 注解延迟求值，可在旧版本 Python 中写 `list[str]` |
| `@dataclass` 装饰器 | `@dataclass class Deployment:` | 由类型注解自动生成构造函数、`repr`、相等比较 |
| 类型注解 | `name: str`、`agent_autonomy_hours: float`、`def tag(d: Deployment) -> list[str]` | 说明字段与返回值类型，运行时不检查 |
| 行尾注释 | `# rushed to launch ahead of rivals?` | 解释字段含义 |
| 字典字面量 + 列表值 | `MITIGATIONS = {"malicious_use": [...], ...}` | 一对多映射 |
| 布尔运算 | `d.handles_harmful_capabilities and d.public_facing`、`(not a) or (not b)` | `and`/`or`/`not` 短路求值 |
| 括号续行 | `org_missing = ( ... or ... )` | 圆括号内可以自由换行 |
| 空列表的真值 | `if tags:` | 空列表为假，非空为真 |
| 嵌套 for 循环 | `for t in tags: for m in MITIGATIONS[t]:` | 先遍历标签，再遍历该标签的措施 |
| 关键字参数 | `Deployment(name="...", public_facing=False, ...)` | 按名字传参，顺序无关、可读性好 |
| 元组迭代 | `for d in (low, mid, high):` | 直接遍历元组 |
| f-string | `f"  public_facing            = {d.public_facing}"`、`f"  tagged risks: {tags}"` | 嵌入变量；列表会按 `repr` 打印成 `['a', 'b']` |
| 字符串乘法 | `"-" * 70` | 分隔线 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()` |

---

## 6. 运行结果解读

实际运行输出（节选）：

```text
Deployment: internal refactor helper (scoped project repo)
  ...
  agent_autonomy_hours     = 1.0

  no tagged risks (check sub-levers manually)

Deployment: public coding agent (SaaS, general user base)
  ...
  information_security     = False
  agent_autonomy_hours     = 4.0

  tagged risks: ['ai_races', 'organizational_risks', 'rogue_ais']

  mitigations for ai_races:
    - scaling policy with standing Risk Reports (Lessons 19, 20)
    ...

Deployment: autonomous ML research agent (frontier)
  ...
  tagged risks: ['malicious_use', 'ai_races', 'organizational_risks', 'rogue_ais']

HEADLINE: organizational risk is the lever practitioners actually pull
```

逐项解读：

- **low → 无标签**：所有规则都不触发。但它并不说明"无风险"：safety culture 没有被检查，内部工具也可能有权限过大等问题——所以括号里提示 "check sub-levers manually"。
- **mid → 三个标签**：
  - ai_races 因为 `competitive_pressure=True`；
  - organizational_risks 只因为 `information_security=False`（审计和多层防御都有）；
  - rogue_ais 因为 4.0 恰好等于阈值。把它改成 3.99 再跑，这个标签就消失了。
  - 打印的 ai_races 缓解措施（发布 scaling policy、公开路线图）对一家 SaaS 公司并不适用。
- **high → 四类全中**：对应讲义 "a rogue AI produced by an organization that traded audit for speed in a race is all four"。
- **补充实验**（我们额外运行的验证）：
  - "内部生物研究助手"（非公开、有害能力、其余安全、2 小时）→ `[]`，漏标 malicious_use；
  - "离线文档翻译批处理"（无工具、6 小时、其余安全）→ `['rogue_ais']`，误标；
  - 固定自主时长 1.0、枚举 6 个布尔字段的 64 种组合：organizational_risks 56 次、ai_races 32 次、malicious_use 16 次。

---

## 7. 动手改一改

1. **补上 safety culture**：给 `Deployment` 末尾加 `safety_culture: bool = True`，在 `tag()` 中改成 `if not all([...4 个杠杆...])`，并在 `report()` 中打印它。构造一个"其余全好、只有文化差"的部署验证会被打上 organizational_risks。
2. **修正 malicious_use 规则**（讲义练习 1）：只要 `handles_harmful_capabilities` 就打标签，`public_facing` 用来区分 "high / medium" 严重度；用"内部生物研究助手"验证。
3. **把 rogue_ais 改成分级**：`<1h` 低、`1–8h` 中、`>8h` 高，并且没有工具权限时降一级；比较 3.99 与 4.0 小时的结果是否还会突变。
4. **加 hard reject 与就绪等级**：增加 `hardcoded_prohibitions`、`external_eval` 字段，实现测验 Q11 的 `hard_rejects()` 与 `readiness()`，让输出与 `outputs/skill-societal-risk-review.md` 的格式一致。
5. **输出四行表**：每一类风险都输出"触发/未触发 + 依据字段 + 一句话理由"，未检查的维度输出 `UNKNOWN`。
6. **进阶**（讲义练习 4）：为你熟悉的一个真实部署填写所有字段，给四个组织子杠杆从 0–3 打分而不是布尔值，找出最弱的一项并估算补齐成本。

---

## 8. 常见坑

- **把"没有标签"当成"没有风险"**：规则只覆盖了 7 个字段，没检查的维度默认被当作安全。
- **漏掉 safety culture**：讲义说它对其它杠杆有预测作用，代码却没有这个字段；HEADLINE 说"四个杠杆"，实现只有三个。
- **只看暴露不看缓解**：同一个标签下，"已有 Llama Guard + 硬编码禁止"和"什么都没有"得到相同的输出。
- **硬阈值的边界效应**：`>= 4.0` 让 3.99 和 4.0 小时的结论完全不同；阈值应有依据并分级。
- **混淆自主时长与 time horizon**：前者是部署暴露面，后者是模型能力上界（第 21 节）。
- **混淆 CAIS 与 CAISI**：代码 `MITIGATIONS` 里的 "external capability evaluation by METR / CAISI" 指的是 NIST 的 CAISI，而四风险框架出自非营利的 CAIS。
- **给 dataclass 加字段时破坏构造**：无默认值字段不能放在有默认值字段之后；新字段加默认值并放在末尾，现有调用才不受影响。
