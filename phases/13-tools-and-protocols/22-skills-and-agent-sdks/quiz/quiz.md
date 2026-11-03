# 测验 · Agent Skills：可移植契约与运行时边界（Agent Skills: Portable Contract and Runtime Boundary）

> **阶段 13 · 工具与协议 · 第 22 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Skill 的定义 | 一个以 `SKILL.md` 为入口的**目录**：YAML frontmatter + Markdown 指令体，可附带 `references/`、`scripts/`、`assets/`；目录才是部署单元，缺了引用文件的 `SKILL.md` 是坏包 |
| 2 | 相邻抽象的分工 | prompt 管一次交互；repository instructions（如 `AGENTS.md`）管一个仓库的常设规则；skill 管可复用流程；MCP tool 暴露带 schema 的外部能力；hook 在事件上跑确定性逻辑；subagent 提供隔离上下文；plugin 是更大的运行时扩展分发 |
| 3 | "skill" 一词的两种含义 | 本节的 Agent Skill 是**人写的、有文件系统契约的包**；研究里的 learned skill library（如 Voyager）是从经验中学到的程序/轨迹，二者不应互相借用实现结论 |
| 4 | 便携核心字段 | 必填 `name`、`description`；可选 `license`、`compatibility`、`metadata`，以及**实验性**的 `allowed-tools`（宿主支持不一） |
| 5 | `name` 规则 | ≤ 64 字符、小写字母/数字/单个连字符（正则 `^[a-z0-9]+(?:-[a-z0-9]+)*$`），且**必须等于父目录名** |
| 6 | `description` 双重身份 | 既是文档也是路由元数据，应写清"做什么 + 何时用"；≤ 1024 字符；`compatibility` 若出现须 1–500 字符 |
| 7 | Runtime extension 是第二层 | `disable-model-invocation`、`user-invocable`、`argument-hint`、`context`/`agent`、`model`/`effort`、`hooks`、`agents/openai.yaml` 都不是便携核心，要当作适配器（adapter）显式声明与测试 |
| 8 | Frontmatter 是可执行元数据 | 在 body 被读之前就改变系统行为：坏 `name` 让发现失败、模糊 `description` 误路由、某个开关把技能移出模型目录 |
| 9 | 生命周期 8 个阶段 | Discovery → Validation → Cataloging → Selection → Activation → Disclosure → Execution → Verification；"被发现 ≠ 被激活 ≠ 被授权 ≠ 结果正确" |
| 10 | 技能与工具正交、技能不互相 import | skill 回答"怎么做"，MCP 回答"能调用什么"；技能 A 调用技能 B 是**经运行时中介的工作流边**，要写明目标、输入、期望结论和不可用时的退路 |

### 核心技能（能动手做到）

- [ ] 手写一个合规的 `SKILL.md`（frontmatter + 指令体），并说出每个字段属于便携核心还是宿主扩展
- [ ] 读懂 `parse_frontmatter` 支持的"YAML 小子集"，能预测哪些写法会被拒（`>-`、`[...]`、下划线字段名）
- [ ] 用 `validate_skill_text` 对任意包给出结构化的 issue code，并解释 `elif` 链导致"只报第一个 name 问题"的行为
- [ ] 用 `allowed_runtime_extensions` 区分"便携包"和"带宿主扩展的包"
- [ ] 用 `TaskShape` / `select_primitives` 给真实工作流选原语（可以多选），并为每个选择说出一句理由
- [ ] 指出本节 `main.py` 与随包脚本 `check_skill.py` 两个校验器的行为差异，并说明"双实现漂移"的风险

---

## 二、基础自测（选择题）

**Q1.** 关于 Agent Skill 的"可部署单元"，下列说法最准确的是：

- A. 以 `SKILL.md` 为入口的整个目录，包括它引用的 references、scripts、assets
- B. 单独一个 `SKILL.md` 文件，其余文件只是可选的说明
- C. frontmatter 中的 `name` 字段，宿主按名字到网上拉取其余内容
- D. 宿主的 plugin 安装包，skill 只是 plugin 的一个别名

**Q2.** 目录名与 `name` 相同时，下列哪个 `name` 能通过本节 `validate_skill_text` 的命名检查？

- A. `Release-Check`
- B. `release_check`
- C. `release--check`
- D. `release-check-2`

**Q3.** 便携核心的可选字段中，讲义特别标注为"实验性、宿主支持不一"的是：

- A. `license`
- B. `compatibility`
- C. `allowed-tools`
- D. `metadata`

**Q4.** 一个 `SKILL.md` 的 frontmatter 多了一行 `user-invocable: true`，调用 `validate_skill_text(text, "incident-summary")`（**不传** `allowed_runtime_extensions`），返回结果是：

- A. `valid=True`，该字段被当作便携核心字段收入 `core_fields`
- B. `valid=False`，issue 为 `unsupported-runtime-field`，`runtime_extensions` 仍然列出 `("user-invocable",)`
- C. `valid=False`，issue 为 `frontmatter-syntax`，因为 `true` 不是字符串
- D. `valid=True`，未知字段被静默丢弃

**Q5.** 讲义把技能生命周期拆成 8 个阶段。关于 **Activation（激活）**，正确的是：

- A. 宿主在配置目录里找到了这个包
- B. 技能获得了执行其描述中所有动作的授权
- C. 技能产出的结果已通过独立检查
- D. 技能的 body 进入了模型可见的上下文，执行可能稍后才发生

**Q6.** `select_primitives(TaskShape(repeatable_method=True, lifecycle_event=True, repository_default=True))` 返回：

- A. `("Agent Skill", "AGENTS.md", "hook")`
- B. `("AGENTS.md", "Agent Skill", "hook")`
- C. `("hook",)`
- D. `("prompt",)`

**Q7.** frontmatter 中有一行 `description: Use when: deploying`。本节 `parse_frontmatter` 与标准 YAML 解析器（PyYAML `safe_load`）的表现分别是：

- A. 两者都报错
- B. 本节解析器报 `frontmatter-syntax`，PyYAML 正常解析
- C. 本节解析器接受，值为 `Use when: deploying`；PyYAML 抛出 `ScannerError`
- D. 两者都接受，值都是 `Use when: deploying`

**Q8.** 讲义说"Skills do not import one another"。下列写法最符合讲义建议的是：

- A. "产出 changelog 后调用 `release-risk-review` 技能，传入候选路径并要求给出 blocking / non-blocking 结论；若该技能不可用，停止并报告缺失依赖。"
- B. 在 `SKILL.md` 顶部写 `import release-risk-review`，让宿主把两个技能合并加载
- C. 把 `release-risk-review` 的全文复制进当前技能的 body，避免依赖
- D. 写"必要时参考其他相关技能"，由模型自行决定

---

## 三、动手 / 代码题

**Q9.** 阅读 `parse_frontmatter` 中处理块标量（block scalar）的片段：

```python
        value = raw_value.strip()
        if value in {">", "|"}:
            block: list[str] = []
            index += 1
            while index < end and (not lines[index] or lines[index][:1].isspace()):
                block.append(lines[index].lstrip())
                index += 1
            metadata[key] = (" " if value == ">" else "\n").join(block).strip()
            continue
```

1. 对下面两段 frontmatter，`validate_skill_text` 分别返回什么？为什么？
   - (a) `description: >-` 后跟两行缩进文本 `  folded` / `  text`
   - (b) `description: |` 后跟 `  line1` / `    indented` / 空行 / `  line3`
2. 这两处与标准 YAML 有何差异？给出最小修改思路。
3. 讲义在第 24 节说"Stdlib-only is a teaching constraint, not permission to invent a partial YAML dialect silently"。结合本题说明生产环境应该怎么做。

**Q10.** 本节有**两个**校验器：`code/main.py` 的 `validate_skill_text` 和随包分发的 `outputs/skill-contract-reviewer/scripts/check_skill.py` 的 `validate`。对下面四个输入（目录名都与 `name` 一致），分别写出两者的结论，并总结"双实现"带来的风险。

| 输入 frontmatter（关键行） | 说明 |
|---|---|
| `name: d` 出现两次 | 重复字段 |
| `description: 'abc"` | 单引号开头、双引号结尾 |
| 额外一行 `user-invocable: true` | 宿主扩展 |
| `name` 为 70 个 `a` | 超长 |

**Q11.** 随包 `SKILL.md` 要求输出"selected primitives, and one sentence explaining each selection"，但 `select_primitives` 只返回名字元组。请写一个 `explain_primitives(task: TaskShape) -> list[tuple[str, str]]`：返回 `(原语, 一句理由)` 列表，顺序与 `select_primitives` 一致，全为 False 时返回 prompt。

**Q12.** 手算：目录名均为 `incident-summary`，基础文本为

```markdown
---
name: incident-summary
description: Summarize incidents.
---

# B
Body
```

对以下改动，写出 `valid` 和全部 issue code：

- (a) description 改为 1025 个字符
- (b) `name: Incident_Summary`
- (c) 在 description 前插入 `metadata: owner`
- (d) 在 description 前插入 `allowed_tools: Read`（注意是下划线）
- (e) 删掉 description 行，并删掉 body（`---` 之后什么也没有）

---

## 四、面试高频题

**Q13.**（基础必考）Agent Skill、MCP tool、hook、subagent、`AGENTS.md`、prompt 分别解决什么问题？给一个需要组合使用其中至少三种的真实例子。

**Q14.**（原理深挖）为什么说 frontmatter 是"可执行元数据"？`name` 必须匹配目录名、`description` 要写触发边界，各自防止了什么故障？

**Q15.**（工程实践）你要为团队的技能仓库写一个 CI 校验器。请给出检查顺序、输出格式、YAML 解析策略、对宿主扩展字段的处理方式，以及如何避免"校验器有两份实现"。

**Q16.**（场景设计）把讲义里的发布流程（找出已合并变更 → 检查迁移说明 → 更新 changelog → 跑打包命令 → 产出审查清单 → 发布前必须人工批准）拆成合适的原语组合，并说明某个依赖的 MCP 工具不可用时技能应如何表现。

**Q17.**（追问型）"这个 skill 通过了校验，所以可以放心让 agent 运行它附带的脚本。"这句话错在哪里？一个合法技能到底授予了什么？

---

## 五、参考答案与解析

### Q1 — 答案：A

讲义："The directory, not the Markdown file alone, is the deployable unit. A copied `SKILL.md` with missing references is a broken package even if its frontmatter parses." B 把附属文件当可选说明，正是讲义批评的做法（第 2 步安装时需要 `--full-depth` 也是因为它是带 references/scripts/assets 的嵌套包）；C 把 `name` 误当成远程定位符，`name` 只是稳定标识；D 混淆了 plugin（分发更大的运行时扩展）与 skill 契约本身。

### Q2 — 答案：D

`NAME_PATTERN = ^[a-z0-9]+(?:-[a-z0-9]+)*$`：只允许小写字母、数字，用**单个**连字符连接。实测：`Release-Check` 含大写（False）、`release_check` 含下划线（False）、`release--check` 是连续连字符（False）、`release-check-2` 为 True。顺带一提，`2fa-helper` 这种数字开头也是合法的，但 `-release`（连字符开头）不合法。

### Q3 — 答案：C

讲义的便携可选字段表中，`license`、`compatibility`、`metadata` 都是 "Core specification"，只有 `allowed-tools` 标注为 "Experimental; host support varies"。代码中它只被检查为"非空字符串"（`allowed-tools-shape`），不校验工具名是否存在——工具注册表归宿主所有。

### Q4 — 答案：B

`validate_skill_text` 先计算 `extension_names = sorted(set(fields) - CORE_FIELDS)`，再对不在 `allowed_runtime_extensions` 里的每个字段追加 `unsupported-runtime-field`。实测输出：`valid=False`、`runtime_extensions=('user-invocable',)`、issues 为 `['unsupported-runtime-field']`。传入 `allowed_runtime_extensions={"user-invocable"}` 后同一文本 `valid=True`（demo 中的 `host_extended`）。A 错在它不属于 `CORE_FIELDS`；C 错在本节解析器把所有标量都存成字符串 `"true"`，不会因类型报语法错；D 错在校验器**不会静默丢弃**未知字段，这正是讲义"Runtime extensions are a second layer"的要求。

### Q5 — 答案：D

讲义 Key Terms："Activation — The skill body entered model-visible context; execution may come later"。A 是 Discovery；C 是 Verification；B 正是讲义警告的错误心智模型："An active skill is not authorized to do everything it describes."

### Q6 — 答案：B

`select_primitives` 按固定顺序检查：`repository_default → repeatable_method → external_capability → lifecycle_event → deterministic_logic → isolated_delegation`，只要有一个为 True 就不会返回 `prompt`。实测为 `('AGENTS.md', 'Agent Skill', 'hook')`。A 顺序错；C、D 忽略了"多个原语可以组合"——讲义："Many production workflows use more than one row."

### Q7 — 答案：C

本节解析器用 `line.split(":", 1)` 只按第一个冒号切分，因此值是 `Use when: deploying`，`valid=True`。标准 YAML 中未加引号的标量里出现 `": "` 是非法的，PyYAML 6.0.3 实测抛 `ScannerError`。这意味着**本节校验器会放行一个真实 YAML 宿主无法加载的包**——描述里写"Use when: …"恰恰是常见写法，应加引号：`description: "Use when: deploying"`。

### Q8 — 答案：A

A 是讲义原文给出的写法：目标技能明确、输入明确、要求可检验的结论、不可用时停止并报告——"This makes the dependency testable and gives the host a chance to enforce policy." B 不存在语言级 import，第二个技能仍要经历发现、资格、激活、权限与上下文处理；C 复制全文会让两份内容漂移，并绕过宿主对第二个技能的策略；D 没有可观测的触发条件，无法测试。

### Q9 — 参考答案

1. 实测结果：
   - (a) `valid=False`，issue `frontmatter-syntax`。`value` 为 `">-"`，不在 `{">", "|"}` 里，走到 `_decode_scalar(">-")` 被当成普通字符串 `">-"`；`index` 只加 1，下一行 `  folded` 以空格开头，触发 `malformed top-level line 4`。
   - (b) `valid=True`，description 为 `'line1\nindented\n\nline3'`——`lines[index].lstrip()` 把每行左侧空白全部去掉，`indented` 原本比 `line1` 多缩进 2 格，这个相对缩进丢失了。
2. 标准 YAML 中，`>-`、`|-`（strip，去掉末尾换行）与 `>+`、`|+`（keep）都是合法的块标量指示符，PyYAML 对 (a) 解析为 `'folded text'`；`|` 字面块应保留"超出基准缩进"的部分。最小修改：
   - 判断改为 `if value[:1] in {">", "|"} and value[1:] in {"", "-", "+"}`；
   - 收集原始行后用 `textwrap.dedent("\n".join(block))` 去掉公共缩进而不是逐行 `lstrip()`，再按 `>`/`|` 折叠或保留换行，按 `-`/`+` 处理末尾换行。
3. 生产中应使用**安全的 YAML 解析器**（如 `yaml.safe_load`，禁止自定义对象构造），配合显式 schema 校验字段类型与长度、限制 frontmatter 大小；教学用的"小子集"至少应在遇到不支持的语法时**明确报错并说明原因**，而不是像 Q7 那样静默接受一个真实 YAML 会拒绝的写法。

### Q10 — 参考答案

实测结果（`check_skill.py` 的 `validate` 读真实目录，`main.py` 的 `validate_skill_text` 读文本）：

| 输入 | `check_skill.py` | `main.py` |
|---|---|---|
| `name: d` 重复 | `valid=False`，code `duplicate`（并**继续解析**，后一次覆盖前一次） | `valid=False`，code `frontmatter-syntax`（立即停止，`name`/`description` 都为 None） |
| `description: 'abc"` | `valid=True`，description 被 `strip("\"'")` 成 `abc` | `valid=False`，`frontmatter-syntax`：unterminated single-quoted scalar |
| `user-invocable: true` | `valid=False`，code `unsupported-field`（**没有**宿主扩展白名单参数） | `valid=False`，code `unsupported-runtime-field`；可通过 `allowed_runtime_extensions` 放行 |
| `name` 70 个字符 | `valid=False`，code `name-format`（长度和格式合并为一个 code） | `valid=False`，code `name-too-long` |

其他差异：`description-length` vs `description-too-long`、`compatibility-length` vs `compatibility-empty`/`compatibility-too-long`；`check_skill.py` 还检查 `SKILL.md` 必须是常规文件且不是 symlink（`skill-file`），`main.py` 只看文本。

风险：同一个包在课程测试里"有效"、在随包脚本里"无效"（或反过来）；issue code 不一致导致下游 CI 规则、文档和告警无法复用；修了一个实现的 bug，另一个仍然有。建议抽出单一的校验库，两处入口都调用它，并用同一组 fixture 做**对拍测试**（同一输入两边结论必须一致）。

### Q11 — 参考答案

```python
from main import TaskShape

REASONS = (
    ("repository_default", "AGENTS.md", "规则只对当前仓库成立，进入该仓库就应生效"),
    ("repeatable_method", "Agent Skill", "跨仓库复用的多步骤方法，需要模型判断"),
    ("external_capability", "MCP tool", "操作发生在模型上下文之外，需要带 schema 的可调用能力"),
    ("lifecycle_event", "hook", "必须在宿主事件点确定性触发，漏一次都不行"),
    ("deterministic_logic", "ordinary code", "输入输出固定，不需要模型判断"),
    ("isolated_delegation", "subagent", "需要独立上下文/状态，返回有界结果"),
)

def explain_primitives(task: TaskShape) -> list[tuple[str, str]]:
    picked = [(name, why) for attr, name, why in REASONS if getattr(task, attr)]
    return picked or [("prompt", "一次性交互，不需要包的生命周期")]
```

已实际运行：`explain_primitives(TaskShape())` 返回 `[('prompt', ...)]`；`TaskShape(repeatable_method=True, external_capability=True)` 返回 Agent Skill 与 MCP tool 两项。要点：用**一张表**同时驱动"选择"和"理由"，顺序与 `select_primitives` 一致，避免两处逻辑分叉；理由文本直接对应讲义"Use It"决策卡的每一行。

### Q12 — 参考答案

全部实测：

| 改动 | valid | issue codes | 说明 |
|---|---|---|---|
| (a) description 1025 字符 | False | `description-too-long` | 上限 1024 |
| (b) `name: Incident_Summary` | False | `name-format` | `elif` 链：格式不合法就不再检查 `directory-mismatch`，只报第一个 name 问题 |
| (c) `metadata: owner` | False | `metadata-shape` | 有值时 `metadata` 被解析成字符串而不是映射 |
| (d) `allowed_tools: Read` | False | `frontmatter-syntax` | 字段名正则 `[A-Za-z][A-Za-z0-9-]*` 不允许下划线，**在解析阶段**就失败，后续检查全部不跑 |
| (e) 无 description、无 body | False | `description-required`、`body-required` | 两个独立检查都会追加 |

(d) 值得注意：拼错成下划线的字段不会被报告为"未知扩展字段"，而是语法错误，错误信息是 `invalid field name 'allowed_tools'`。这对作者是友好的（错误位置明确），但也说明本节的"YAML"比真实 YAML 更严格——真实 YAML 允许下划线键。

### Q13 — 参考回答要点

- **prompt**：塑造一次交互，无版本、无发现规则。
- **`AGENTS.md`（repository instructions）**：描述"你已身处的这个仓库"——构建命令、约定、不得修改的生成文件；进入该仓库作用域即生效。
- **Agent Skill**：可跨仓库复用的流程性知识（procedural knowledge），显式或隐式激活；**不是硬授权边界**。
- **MCP tool**：带 schema 的外部能力；"Which capabilities can this application call?"
- **hook**：在宿主声明的事件点运行确定性逻辑，"漏执行一次不可接受"时使用。
- **subagent**：独立上下文、状态与所有权，返回有界结果。
- **组合例子**（讲义原例）：发布技能讲"怎么检查发布"；MCP server 暴露发布注册表；hook 禁止直接 push；subagent 独立审计候选版本；仓库约定放 `AGENTS.md`。
- 加分点：说出判断标准——`select_primitives` 的 docstring："Select composable primitives by responsibility, not by product branding"；并能指出 learned skill library（第 14 阶段第 10 节）与 Agent Skill 包是两回事。
- 常见误区：把所有可复用指令都塞进 `SKILL.md`，结果"看起来可移植，实际依赖某个宿主未文档化的行为"。

### Q14 — 参考回答要点

- 讲义："Metadata changes system behavior before the skill body is read." 宿主在加载 body 之前就根据 frontmatter 决定：能否被发现、出现在目录里的文字、是否对模型可见、工具是否预批准、是否在独立上下文中执行。
- **`name` 匹配目录名**：发现工具常同时按文件夹和 frontmatter 索引；两者不一致会出现两个互相冲突的身份，造成目录条目歧义、安装路径错乱（课程 quiz.json 的解释）。
- **`description` 写触发边界**：它是路由接口；含糊会把无关请求路由进来（假阳性），过窄则该触发时不触发。第 25 节会用 near-miss 评测这个边界。
- 因此 frontmatter 应"像配置代码一样被评审"：校验、版本化、把它的行为纳入 evals。
- 加分点：举出宿主扩展的例子（如某宿主用 `disable-model-invocation` 把技能移出模型路由），并强调未知宿主可能"忽略、拒绝或保留但不实现"该字段。

### Q15 — 参考回答要点

- **检查顺序**（讲义"Validation order matters"：先廉价的结构事实，再更深的内容规则）：文件存在且为常规文件（拒绝 symlink）→ 分隔符 → YAML 语法 → 必填字段 → 命名规则与目录匹配 → 长度限制 → 可选字段形状 → 未知字段/宿主扩展 → body 非空 →（进一步）引用文件是否存在。
- **输出**：结构化报告（如本节 `SkillReport` + `ValidationIssue(code, message)`），code 稳定、message 告诉作者如何修复；"A package validator should explain how to fix an artifact without guessing on the author's behalf."
- **YAML 解析**：用安全解析器 + schema，限制大小；不支持的语法要明确报错（对照 Q7、Q9）。
- **宿主扩展**：默认拒绝，通过显式白名单（对应 `allowed_runtime_extensions`）按目标宿主放行，并在报告中单列 `runtime_extensions`，保证"便携包"和"带扩展的包"可区分（讲义练习 3）。
- **单一实现**：课程代码与随包脚本应共享同一个库，并用同一批 fixture 对拍（对照 Q10）。
- 常见误区：只返回一个布尔值；遇到第一个错误就抛异常，作者要反复提交才能看到全部问题。

### Q16 — 参考回答要点

- **Agent Skill（release-readiness）**：流程本身——读发布策略 reference → 运行检查脚本 → 遇到阻断项停止 → 用 asset 模板生成清单 → **发布或打 tag 前请求批准**（讲义示例 body 第 5 步）。
- **MCP tool**：查询合并记录、部署/发布注册表等外部能力。
- **ordinary code / script**：迁移说明格式检查、changelog 规范化这类确定性转换。
- **hook**：例如"每次生成文件后强制格式化""禁止直接 push"。
- **`AGENTS.md`**：本仓库的打包命令、不得编辑的生成文件。
- **subagent**（可选）：独立审计候选版本，返回有界结论。
- **工具不可用时**（讲义练习 5）：技能应明确写出退路或明确失败——停止并报告"缺少 X 工具"，**不得静默换成权限更大的工具**；讲义："It should never imply that naming a capability creates it."
- 加分点：发布是高影响动作，后续第 25 节会建议对这类技能采用 human-only 调用策略。

### Q17 — 参考回答要点

- 错在把"结构合法"当成"有授权"。随包 contract 清单最后一句："Passing this checklist makes the package structurally loadable. It does not grant filesystem, network, secret, subprocess, or tool authority."
- 合法技能授予的只是：**可被发现的流程性指令**，仍受宿主运行时策略约束（课程 quiz.json："Discoverable procedural instructions, subject to the host runtime's policies"）。
- 脚本执行要经过宿主的权限与隔离规则（Execution 阶段）；结果还要独立验证（Verification 阶段）——"A permitted tool call is not proof that the result is correct."
- 即便 `allowed-tools` 存在，它也只是"建议预批准"，且是实验性字段，行为要在目标宿主中验证。
- 加分点：引出第 26 节——权限（permission）与沙箱（sandbox）是两个不同的机制；路径合法不代表内容可信。

---

## 六、关联知识点

### 前置知识
- [阶段 13 · 01 工具接口：为什么 Agents 需要结构化输入输出](../../01-the-tool-interface/docs/zh.md)：理解"工具契约"，才能区分 skill（流程）与 tool（能力）。
- [阶段 13 · 05 工具 Schema 设计：命名、描述与 Parameter 约束](../../05-tool-schema-design/docs/zh.md)：`description` 作为路由元数据的写法与工具描述同源。
- [阶段 13 · 06 MCP 基础：无状态请求与 JSON-RPC](../../06-mcp-fundamentals/docs/zh.md)：本节反复对比的 MCP tool 来自这里。

### 本节被哪些后续内容用到
- [阶段 13 · 23 综合项目：无状态工具生态系统](../../23-capstone-tool-ecosystem/docs/zh.md)：把 skill、MCP、A2A、OTel 放进一个系统，强调"skill 是流程不是传输"。
- [阶段 13 · 24 Skill Discovery 与 Progressive Disclosure](../../24-skill-discovery-and-progressive-disclosure/docs/zh.md)：生命周期中的 Discovery / Cataloging / Disclosure 阶段。
- [阶段 13 · 25 Skill Invocation 与路由](../../25-skill-invocation-and-routing/docs/zh.md)：Selection / Activation 阶段与 `user-invocable` 等宿主扩展。
- [阶段 13 · 26 Skill 权限、Sandboxes 与信任](../../26-skill-permissions-sandboxes-and-trust/docs/zh.md)：Execution 阶段的权限与隔离。
- [阶段 13 · 27 Skill 评估、打包与可移植性](../../27-skill-evals-packaging-and-portability/docs/zh.md)：把整个包变成经过评估的发布产物。
- [阶段 14 · 10 技能库与终身学习（Voyager）](../../../14-agent-engineering/10-skill-libraries-voyager/docs/zh.md)："skill"的另一种含义——从经验中学到的技能库。
- [阶段 14 · 17 将 Harness 封装为库：Subagents 与会话存储](../../../14-agent-engineering/17-claude-agent-sdk/docs/zh.md)、[阶段 14 · 33 将 Agent 指令作为可执行约束](../../../14-agent-engineering/33-instructions-as-executable-constraints/docs/zh.md)：subagent 与仓库级指令的工程实践。

### 延伸关键词
`SKILL.md` · `YAML frontmatter` · `progressive disclosure` · `runtime extension / adapter` · `AGENTS.md` · `allowed-tools` · `disable-model-invocation` · `user-invocable` · `hook` · `subagent` · `learned skill library` · `yaml.safe_load` · `structured validation report`
