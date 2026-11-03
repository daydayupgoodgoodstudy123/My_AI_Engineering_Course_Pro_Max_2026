# 测验 · Skill Discovery（技能发现）与 Progressive Disclosure（渐进披露）（Skill Discovery and Progressive Disclosure）

> **阶段 13 · 工具与协议 · 第 24 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 发现是一条"编译器流水线" | 把文件系统当源输入：搜索根 → 候选 → 校验 → 冲突策略 → 预算 → 发布目录；每一阶段都要产出结构化数据和结构化失败 |
| 2 | 发现日志要回答的五个问题 | 搜了哪些根、找到哪些候选、拒了哪些及原因、冲突谁赢了、哪些条目因预算被截断或省略 |
| 3 | Scope 是运行时策略 | 便携规范只定义包，不定义安装路径和优先级；workspace / user / administrator / plugin / built-in 的顺序由宿主声明并测试，不要从目录名"猜" |
| 4 | 冲突需要超越 `name` 的身份 | 目录条目至少带 name、description、scope、source、selected；四种策略：全保留、最高优先级胜出、拒绝重复、按来源限定名 |
| 5 | 三级披露 | Level 1 目录元数据（规范估计每条约 100 token）；Level 2 激活后的 `SKILL.md` body（建议 < 500 行）；Level 3 按分支需要读取的 references / scripts / assets |
| 6 | 好的 description | 两个分句：能力 + 触发边界 |
| 7 | 分支化引用胜过主题堆砌 | body 写成决策地图，每个引用都有可观察的加载条件；引用图保持浅层（一跳） |
| 8 | 两种预算相互独立 | `catalog_cost = Σ c_i`，`active_cost = Σ b_j + Σ r_k`；缩短描述不会减少激活后的 body 开销 |
| 9 | 路径是信任边界 | 拒绝绝对路径和 `..`，按文件系统语义解析后确认仍在包根之内；是否允许 symlink 要在发现前决定；路径合法 ≠ 内容可信 |
| 10 | 加载要可观测 | 记录 `skill.resource.loaded` 事件：技能、资源、原因、字节数，不记录秘密 |

### 核心技能（能动手做到）

- [ ] 用 `discover_scope` + `resolve_collisions` + `build_catalog` 在两个 scope 上构建目录，并解释 `collisions`、`omitted`、`catalog_chars`、`report_chars`
- [ ] 手算一个目录在给定 `max_catalog_chars` 下会淘汰哪些条目
- [ ] 判断任意引用路径能否通过 `validate_reference`，并说出被拒的具体原因
- [ ] 指出本节实现与讲义"结构化失败"要求之间的差距，并把 fail-fast 改为收集拒绝原因
- [ ] 为 `load_reference` 增加字节上限与哈希清单校验
- [ ] 区分 Codex 的目录预算策略（讲义所述）与 Agent Skills 标准本身的要求

---

## 二、基础自测（选择题）

**Q1.** 按讲义的渐进披露模型，下列加载顺序正确的是：

- A. 启动时加载所有 `SKILL.md` body → 模型选中后再加载 frontmatter
- B. 目录元数据（name + description）→ 选中后加载 `SKILL.md` body → body 指向某个分支时再读对应 reference
- C. 先读全部 references 建索引 → 再生成目录 → 最后加载 body
- D. 只发布目录，body 和 references 永远不进入上下文

**Q2.** project 与 user 两个 scope 下都有 `evidence-report`，`precedence=("project", "user")`。`build_catalog` 的结果是：

- A. 两个条目都进入模型可见目录，由模型自行选择
- B. 抛出 `CollisionError`，因为出现了同名技能
- C. user 版本胜出，因为它在 `discover_scope` 中先被发现
- D. project 版本进入 `entries`；`collisions` 记录 `winner_scope="project"`、`shadowed_scopes=("user",)`，被遮蔽者不进入模型目录但保留在诊断报告里

**Q3.** 两个**都标记为 `project`** 的不同根目录下各有一个 `reporter`，调用 `resolve_collisions(candidates, ("project",))`：

- A. 抛出 `CollisionError`（equal precedence），整个目录构建失败
- B. 按目录路径字母序选第一个，静默覆盖
- C. 两个都保留，名字加上来源前缀
- D. 只保留最后发现的那个

**Q4.** 对一个包含 `references/format.md` 的技能目录，下列哪个引用能通过 `validate_reference`？

- A. `/etc/passwd`
- B. `references\format.md`
- C. `SKILL.md`
- D. `references/archive/format.md`

**Q5.** 关于讲义中 Codex 的目录预算，正确的说法是：

- A. 2% 上下文窗口与 8,000 字符两个上限同时生效，取较小者
- B. 这是 Agent Skills 标准规定的预算
- C. 超出预算时会报错并拒绝启动会话
- D. 已知上下文窗口大小时按其 2% 计算；8,000 字符只是窗口大小未知时的回退值；超出时描述可能被缩短或省略

**Q6.** 一个 scope 下有 `alpha`、`zeta` 两个合法技能和一个目录名为 `Bad`、frontmatter `name: bad` 的包。`discover_scope` 的行为是：

- A. 抛出 `DiscoveryError`，`alpha` 和 `zeta` 也都不会被返回
- B. 返回 `alpha`、`zeta`，并在返回值里附带 `Bad` 的拒绝原因
- C. 返回 `alpha`、`bad`、`zeta`
- D. 静默跳过 `Bad`，只返回 `alpha`、`zeta`

**Q7.** 讲义说 `discover_scope` 是"浅层"的，只检查直接子目录。主要原因是：

- A. 递归遍历太慢
- B. 便携规范禁止技能目录超过两层
- C. 保持包边界，避免把已安装技能内部的示例或夹具里的 `SKILL.md` 误发布为独立技能
- D. 为了让 symlink 能被正确跟随

**Q8.** `Catalog.catalog_chars` 衡量的是：

- A. 所有 `SKILL.md` 文件的总字符数
- B. `{"entries": [...]}`（每条含 name、description、scope、directory）用 `sort_keys=True` 与紧凑分隔符序列化后的 JSON 字符数
- C. 模型 tokenizer 计算出的 token 数
- D. 诊断报告（含 collisions、omitted）的字符数

---

## 三、动手 / 代码题

**Q9.** 手算预算淘汰。`build_catalog` 中：

```python
    def model_size(current_entries: list[CatalogEntry]) -> int:
        payload = {"entries": [asdict(entry) for entry in current_entries]}
        return len(json.dumps(payload, sort_keys=True, separators=(",", ":")))

    used = model_size(entries)
    while used > budget.max_catalog_chars and entries:
        removed = entries.pop()
        omitted.insert(0, removed.name)
        used = model_size(entries)
```

同一 scope 下有 `alpha`、`beta`、`gamma`、`delta` 四个技能（`max_entries=4`）。已知它们各自的条目 JSON 长度分别为 176、174、176、176（gamma 为 176），空目录 `{"entries":[]}` 为 14 字符，条目之间用一个逗号分隔。

1. `entries` 的初始顺序是什么？
2. `max_catalog_chars=700` 时，最终 `entries`、`omitted`、`catalog_chars` 各是多少？
3. 如果某个技能的 description 是 18 个汉字，它在 `model_size` 中贡献多少个字符？为什么？这对多语言技能意味着什么？

**Q10.** 讲义说"Each stage should produce structured data and structured failures"，并列出发现日志要回答"Which candidates were rejected, and why?"。阅读 `discover_scope`：

```python
    for directory in sorted(scope.root.iterdir(), key=lambda item: item.name):
        skill_path = directory / "SKILL.md"
        if not directory.is_dir() or directory.is_symlink():
            continue
        if skill_path.is_symlink():
            raise DiscoveryError(f"symlinked SKILL.md is not allowed: {skill_path}")
        if not skill_path.is_file():
            continue
        fields = _frontmatter(skill_path)
        ...
```

1. 指出两处与讲义要求不一致的行为。
2. 把它改造成返回 `(candidates, rejected)`，其中 `rejected` 记录 scope、路径和原因。

**Q11.** （讲义练习 3 与练习 5）现有 `load_reference` 先 `read_text` 读入整个文件再比较 `len(content) > max_chars`。

1. 这样做有什么问题？
2. 写一个 `load_reference_v2(entry, reference, max_bytes=12_000, manifest=None)`：只读取 `max_bytes + 1` 个字节判断超限；若提供 `manifest`（相对路径 → SHA-256），内容哈希不匹配时拒绝加载。说明"恰好等于上限"与"超出 1 字节"两个边界的结果。

**Q12.** 逐个判断下列引用传入 `validate_reference(skill_dir, ref)` 的结果（通过则写解析后的相对路径，失败则写错误信息），并回答：代码里 `any(part in {"", ".", ".."} ...)` 中的 `""` 和 `"."` 真的会被命中吗？`target == root` 这个条件防的是什么？

- (a) `"references/./format.md"`
- (b) `"."`
- (c) `"references"`
- (d) `"references/../SKILL.md"`
- (e) `"./SKILL.md"`

---

## 四、面试高频题

**Q13.**（基础必考）什么是 progressive disclosure？三个级别分别放什么、各自的预算怎么控制？为什么"把 body 拆成很多 references"不一定能降低开销？

**Q14.**（原理深挖）设计一个多 scope 的技能发现系统：同名技能怎么处理？优先级从哪来？被遮蔽的技能要不要让模型看到？各种冲突策略的风险是什么？

**Q15.**（工程实践）技能读取自己的资源时，有哪些路径类攻击？你会如何实现包内路径校验？路径校验通过后还剩哪些风险？

**Q16.**（场景设计）你的 agent 装了 200 个技能，用户反馈"它就是不用我写的那个技能"。你会如何排查？需要发现系统提供哪些证据？

**Q17.**（追问型）目录超出预算时，你会"按字母序截断"、"缩短所有描述"、还是"按相关性筛选"？各有什么取舍？本节代码选择了哪种？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义三级披露：Level 1 目录元数据；Level 2 激活后的指令；Level 3 任务需要时才读的资源。随包 `discovery-contract.md`："Catalog → Activation → Execution support: load a directly named file … only when needed." A 把顺序颠倒且一开始就加载全部 body，正是讲义开头批评的"bury the current task in unrelated procedure"；C 一开始就读全部 references；D 走向另一个极端，"Loading nothing would force the user to remember exact filesystem paths"。

### Q2 — 答案：D

`resolve_collisions` 按 `(rank, directory)` 排序，`project` 的 rank 为 0 胜出；`collisions` 记录 `Collision("evidence-report", "project", ("user",))`。实际 demo 输出中 `entries` 只有 project 版的 `evidence-report` 和 user 版的 `meeting-brief`，`collisions` 为 `[{"name": "evidence-report", "shadowed_scopes": ["user"], "winner_scope": "project"}]`。被遮蔽者不在 `model_dict()` 里，但保留在 `to_dict()` 诊断报告中——讲义："Preserve the rejected or shadowed candidates in diagnostics even when they are absent from the model catalog." A 是"全保留"策略，本节没有采用；B 只有同优先级才报错；C 发现顺序与优先级无关。

### Q3 — 答案：A

两个候选的 scope 都是 `project`，rank 相同，`tied` 长度为 2，抛 `CollisionError("ambiguous 'reporter' at equal precedence: ...")`。随包 `SKILL.md`："Never choose an equal-precedence duplicate by incidental filesystem order." B 正是被禁止的做法（虽然代码确实按路径排序，但只用于让报错信息稳定）；C 是"按来源限定名"策略（讲义练习 2）；D 依赖遍历顺序。注意代价：本节 `build_catalog` 会因此**整体失败**，而随包脚本 `build_catalog.py` 只把它记入 `errors`、继续构建其他条目。

### Q4 — 答案：C

实测：`SKILL.md` 通过（一级、无 `..`、是常规文件、在包根内）。A 是绝对路径 → "reference must be a clean relative path"；B 含反斜杠 → "references must use portable forward slashes"；D 有三段 → "reference may be at most one directory deep"。顺带说明：`SKILL.md` 本身能被当作 reference 读到，这不是安全问题，但意味着"reference"的定义比 `references/` 目录更宽。

### Q5 — 答案：D

讲义："Codex currently budgets the initial skill list at 2 percent of the context window when the context-window size is known. The 8,000-character value is a fallback only when that size is unknown; it is not a second cap combined with the 2 percent rule. When the catalog exceeds the applicable budget, descriptions may be shortened or omitted. Treat those figures as current Codex policy, not a property of the Agent Skills standard." A 恰好是讲义否定的理解；B 混淆了宿主策略与标准；C 与"缩短或省略"不符。本节 `CatalogBudget` 的默认 `max_catalog_chars=8_000` 就是对这个回退值的模仿。（注：中文讲义把 "Codex" 机翻成了"代码"，阅读时请对照英文。）

### Q6 — 答案：A

实测抛出 `DiscoveryError: frontmatter name 'bad' does not match directory 'Bad'`，函数没有返回任何候选——一个坏包让整个 scope 不可用。B 是讲义期望的"结构化失败"，也是 Q10 要你改成的样子；C 错在目录名校验会拒绝它；D 是 symlink 目录的处理方式（静默跳过），不是坏包的处理方式。

### Q7 — 答案：C

讲义 "Why discovery is shallow"："It does not recursively treat every nested `SKILL.md` as a separate package. This preserves the package boundary and avoids accidentally publishing examples or fixtures inside an installed skill." A 不是主要理由；B 不存在这样的规范规定（引用路径一级深是本节的 host 规则，不是目录发现规则）；D 相反，本实现直接跳过 symlink 目录。

### Q8 — 答案：B

见 Q9 中的 `model_size`。它测量的是**发给模型的那份**序列化目录，包括每条的绝对目录路径；`report_chars` 才是诊断报告的长度（D）。C 错：讲义对 `CatalogBudget` 的定位是 "account for serialized entries without pretending characters are universal tokens"——它数字符不数 token。A 错：body 根本不在目录里（测试 `test_body_load_is_separate_from_catalog_construction` 确认）。

### Q9 — 参考答案

1. `ordered = sorted(winners, key=lambda item: (rank[item.scope], item.name))`，同一 scope 按名字排序：`alpha, beta, delta, gamma`。
2. 四条全在时：`14 + (176 + 174 + 176 + 176) + 3 = 719 > 700`，弹出**最后一个** `gamma`；三条时：`14 + 176 + 174 + 176 + 2 = 542 ≤ 700`，停止。结果：`entries = [alpha, beta, delta]`，`omitted = ("gamma",)`，`catalog_chars = 542`。（本地实际运行这个配置——即测试 `test_catalog_budget_covers_exact_model_facing_entries`——得到的正是 `['alpha', 'beta', 'delta'] ('gamma',) 542`；条目长度包含临时目录路径，换一台机器数值会变。）
3. `json.dumps` 默认 `ensure_ascii=True`，每个非 ASCII 字符被转义成 `\uXXXX`（6 个字符）。18 个汉字的 description 贡献 `18 × 6 = 108` 个字符的内容，加上两侧引号共 110（实测 `len(json.dumps(desc)) == 110`，而 `ensure_ascii=False` 时只有 20）。意味着中文等非拉丁文字的技能在预算里被放大约 6 倍，更容易被淘汰——即使真实 tokenizer 对它们的开销远没有这么大。改进：序列化用 `ensure_ascii=False`，或者干脆按宿主实际发送给模型的格式与 tokenizer 计量。

### Q10 — 参考答案

1. 两处不一致：
   - **fail-fast**：任何一个包的 frontmatter、命名、长度、目录名问题，或 `SKILL.md` 是 symlink，都会 `raise DiscoveryError`，**整个 scope 的结果丢失**（Q6 实测）。讲义要求的是"拒绝哪些、为什么"的结构化日志。
   - **静默跳过**：symlink 目录 `directory.is_symlink()` 直接 `continue`，不留任何记录；没有 `SKILL.md` 的目录同样无记录（这一条可以接受，但 symlink 应当记录，因为讲义说"State whether symlinked packages are allowed"——拒绝也应可见）。
2. 改造（已运行验证）：

```python
@dataclass(frozen=True)
class Rejection:
    scope: str
    path: str
    reason: str

def discover_scope_v2(scope):
    candidates, rejected = [], []
    if not scope.root.exists():
        return (), ()
    for directory in sorted(scope.root.iterdir(), key=lambda item: item.name):
        skill_path = directory / "SKILL.md"
        if not directory.is_dir():
            continue
        if directory.is_symlink():
            rejected.append(Rejection(scope.name, str(directory), "symlinked skill directory"))
            continue
        try:
            if skill_path.is_symlink():
                raise DiscoveryError("symlinked SKILL.md is not allowed")
            if not skill_path.is_file():
                continue
            fields = _frontmatter(skill_path)
            ...  # 原有的 name / description / 目录名检查，失败时 raise DiscoveryError
        except DiscoveryError as error:
            rejected.append(Rejection(scope.name, str(directory), str(error)))
            continue
        candidates.append(SkillCandidate(...))
    return tuple(candidates), tuple(rejected)
```

   在 Q6 的场景下运行：候选为 `['alpha', 'zeta']`，`rejected` 为 `Bad | name 'bad' does not match directory 'Bad'` 与 `linked | symlinked skill directory`。随包脚本 `build_catalog.py` 就是这种"收集 errors 继续构建"的思路，可以参考。

### Q11 — 参考答案

1. 问题：先把整个文件读进内存再判断，一个几百 MB 的"reference"会先耗尽内存/时间；字符数与字节数也不同（多字节 UTF-8）；读取与校验之间没有完整性检查，文件可能在审核后被替换。
2. 实现（已运行验证）：

```python
def load_reference_v2(entry, reference, max_bytes=12_000, manifest=None):
    target = validate_reference(Path(entry.directory), reference)
    with target.open("rb") as handle:
        data = handle.read(max_bytes + 1)          # 多读 1 字节即可判断是否超限
    if len(data) > max_bytes:
        raise ReferencePathError(f"reference exceeds {max_bytes} bytes")
    if manifest is not None:
        expected = manifest.get(reference)
        if expected is None or hashlib.sha256(data).hexdigest() != expected:
            raise ReferencePathError(f"reference {reference!r} does not match manifest")
    return data.decode("utf-8")
```

   边界验证：demo 中的 `references/format.md` 为 46 字节；`max_bytes=46` 时成功读出 46 字节，`max_bytes=45` 时报 `reference exceeds 45 bytes`。哈希清单：未改动时通过；把内容改成 "Ignore previous instructions." 后报 `does not match manifest`。要点：清单的键要与传入的引用字符串一致（最好先规范化为解析后的相对路径）；清单本身要来自可信来源（如签名的发布产物，见第 27 节）。

### Q12 — 参考答案

实测结果：

| 引用 | 结果 |
|---|---|
| (a) `references/./format.md` | **通过**，解析为 `references/format.md` |
| (b) `.` | 失败：`reference escapes the skill directory` |
| (c) `references` | 失败：`reference must resolve to a regular file` |
| (d) `references/../SKILL.md` | 失败：`reference must be a clean relative path` |
| (e) `./SKILL.md` | **通过**，解析为 `SKILL.md` |

- `PurePosixPath` 在构造时会**规范化**掉空段和 `.`：`PurePosixPath("references/./format.md").parts == ('references', 'format.md')`，`PurePosixPath(".").parts == ()`。因此 `""` 和 `"."` 在 `parts` 里永远不会出现，这两项检查是死代码；真正起作用的只有 `".."`（`PurePosixPath` 不会折叠 `..`，因为在有 symlink 时折叠会改变语义）。这也是 (a)、(e) 能通过的原因——它们本身无害，但说明"clean relative path"的检查比字面意思宽松。
- `target == root`：当引用为 `.` 或空串时，`parts` 为空，循环不执行，`target` 就是包根本身。`root not in target.parents` 对 `target == root` 也为真，但单独写出这个条件让意图更清楚：引用必须指向包内的**某个文件**，不能是包根。不过此时报的错误信息 "escapes the skill directory" 有误导性，更准确的是 "reference must name a file"。

### Q13 — 参考回答要点

- **定义**：分阶段准入上下文——讲义 Key Terms："Staged context admission from catalog to body to branch-specific resources"。
- **Level 1**：每个合格技能一条 name + description（规范估计约 100 token/条，实际由宿主序列化决定）；预算是目录预算（条目数、描述长度、总字符数，本节 `CatalogBudget`）。
- **Level 2**：被选中技能的 `SKILL.md` body——任务边界、默认流程、分支条件、直接引用、工具/脚本契约、失败与停止行为、输出与验证；规范建议 < 500 行（"a design signal, not a target to fill"）；本节用 `max_chars=12_000` 限制。
- **Level 3**：references（读）、scripts（经许可的工具执行）、assets（复制/填充成交付物）；按分支加载，有字节上限。
- **为什么拆分不一定省**：讲义 "Reducing one budget does not automatically reduce the other… Splitting the body into references can reduce active cost only when the runtime and instructions actually avoid loading irrelevant branches." 如果 body 写"read `references/` for more"，模型很可能把它们全读一遍。
- 加分点：给出两种预算公式；说明不能把核心流程挪到 reference 里只为让入口文件变短——"Activation must give the model enough context to begin correctly."

### Q14 — 参考回答要点

- **身份**：内部身份至少是 (name, scope, source)；条目带 `selected` 标记。
- **优先级来源**：宿主显式声明并测试（本节 `precedence` 元组、随包 `scope-policy.json`），讲义："Never invent precedence from directory names."
- **四种策略与风险**（讲义表）：全保留 → 模型看到歧义名字；最高优先级胜出 → 本地包可能遮蔽可信包；拒绝重复 → 合法覆盖失效；按来源限定名 → 名字变长。
- **被遮蔽者**：不进入模型目录，但必须进入诊断报告（本节 `collisions`）。
- **同优先级重复**：报歧义，不按文件系统偶然顺序选择。
- 加分点：讲义提到截至 2026 年 8 月 Codex 文档中重名技能"may both appear rather than being merged"——不同宿主行为不同，适配器要按目标宿主测试；"可写入某个 scope 的人"决定了该 scope 的信任级别（Use It 清单第 1 条）。

### Q15 — 参考回答要点

- **攻击**：`../` 穿越（讲义例 `references/../../../../.ssh/config`）；绝对路径；指向包外的 symlink（`references/external-link -> /private/company-secrets`）；Windows 反斜杠与盘符；深层引用链导致不可控的加载图；TOCTOU（校验后、读取前替换文件）。
- **实现**：拒绝非字符串、反斜杠、绝对路径、`..`；限制深度；逐段检查 symlink（本节 `unresolved.is_symlink()`）；`resolve()` 后确认 `root in target.parents`；要求是常规文件；带字节上限读取。讲义强调"Literal string-prefix checks are not enough"——`startswith(root)` 会被 `/skills/reporter-evil` 这类兄弟目录绕过。
- **剩余风险**：讲义 "Path containment does not establish content trust"——包内的合法 reference 仍可能含恶意指令（prompt injection，第 26 节处理）；文件在审核后被替换（用哈希清单，Q11）；超大文件（字节上限）。
- 加分点：在打开文件时使用 `O_NOFOLLOW` 或打开后用 `fstat` 再确认，缩小 TOCTOU 窗口。

### Q16 — 参考回答要点

按流水线逐级排查，每一级都需要发现系统给出证据（讲义："Without that evidence, 'the model did not use my skill' is almost impossible to diagnose"）：

1. **根**：技能所在目录是否在配置的搜索根里？会话启动后是否重建了目录（Use It 第 10 条）？
2. **候选与校验**：是否因 name 与目录不匹配、frontmatter 语法、symlink、描述超长被拒？（本节实现中这些会直接抛异常，需要先做 Q10 的改造才能看到）
3. **冲突**：是否被更高优先级的同名技能遮蔽？
4. **预算**：是否因为排在后面被 `omitted`，或描述被截断到失去触发词？
5. **路由**：目录里在，但描述的触发边界与用户说法不匹配——进入第 25 节的路由评测（正例 + near miss）。
6. **激活后**：body 是否引用了缺失的文件？加载事件里有没有对应的 `skill.resource.loaded`？
- 加分点：要求发现日志输出完整的 `entries`、`collisions`、`omitted`、`rejected` 和精确的目录字节数，并能按会话回放。

### Q17 — 参考回答要点

- **按固定顺序截断**（本节做法）：排序键 `(scope rank, name)`，超预算时从末尾弹出——低优先级 scope、名字靠后的先被省略。确定、可复现、可审计；但与当前任务无关，`zeta-*` 技能天生吃亏。
- **统一缩短描述**：本节只用 `max_description_chars` 做**固定**截断（加 `…`），超预算时不会进一步缩短而是直接省略条目。缩短保留了"存在感"，但可能把第二个分句（触发边界）截掉，导致误路由；讲义说 Codex 超出预算时"descriptions may be shortened or omitted"。
- **按相关性筛选**：把目录变成检索问题，节省预算；但引入了另一个概率性环节，路由失败更难诊断，且需要稳定的检索评测。
- 随包 `catalog-builder` 的建议与讲义 quiz 的答案一致："Apply deterministic limits, report omitted entries, and allow narrower discovery"——即确定性截断 + 报告 + 允许用户/宿主缩小发现范围（如只加载当前项目 scope）。
- 加分点：被省略的技能仍可以通过显式调用（按名字）使用，这要求显式调用不依赖目录可见性——第 25 节的话题。

---

## 六、关联知识点

### 前置知识
- [阶段 13 · 22 Agent Skills：可移植契约与运行时边界](../../22-skills-and-agent-sdks/docs/zh.md)：`SKILL.md` 契约、命名规则与生命周期八阶段。
- [阶段 11 · 05 Context Engineering: 窗口、预算、记忆和检索](../../../11-llm-engineering/05-context-engineering/docs/zh.md)：上下文预算的一般方法。
- [阶段 13 · 10 MCP Resources 与 Prompts：无状态服务端的可寻址上下文](../../10-mcp-resources-and-prompts/docs/zh.md)：另一种"按需加载上下文"的机制。

### 本节被哪些后续内容用到
- [阶段 13 · 25 Skill Invocation 与路由](../../25-skill-invocation-and-routing/docs/zh.md)：在本节目录的基础上做资格过滤与相关性路由。
- [阶段 13 · 26 Skill 权限、Sandboxes 与信任](../../26-skill-permissions-sandboxes-and-trust/docs/zh.md)：路径合法之后的内容信任问题。
- [阶段 13 · 27 Skill 评估、打包与可移植性](../../27-skill-evals-packaging-and-portability/docs/zh.md)：资源哈希清单与发布门禁。
- [阶段 13 · 30 MCP 注册表供应链：准入、漂移与 Rollback](../../30-mcp-registry-supply-chain-and-drift/docs/zh.md)：多来源发布物的准入与漂移检测，与本节的冲突策略同类。
- [阶段 14 · 33 将 Agent 指令作为可执行约束](../../../14-agent-engineering/33-instructions-as-executable-constraints/docs/zh.md)、[阶段 14 · 34 代码仓库记忆与持久状态](../../../14-agent-engineering/34-repo-memory-and-state/docs/zh.md)：workspace scope 中的仓库级指令。
- [阶段 19 · 26 带拒绝列表与路径隔离的 Sandbox 执行器](../../../19-capstone-projects/26-sandbox-runner-denylist/docs/zh.md)：路径隔离的综合实现。

### 延伸关键词
`progressive disclosure` · `skill catalog` · `scope precedence` · `collision policy` · `shadowed candidate` · `catalog budget` · `ensure_ascii` · `path traversal` · `symlink escape` · `PurePosixPath` · `TOCTOU` · `resource manifest hash` · `discovery log`
