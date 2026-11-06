# 代码讲解 · main.py

> **所属小节**：阶段 14 · Agent 工程 · 第 33 节 将 Agent 指令作为可执行约束 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 code/main.py` ｜ **依赖**：仅标准库（`json`、`re`、`dataclasses`、`pathlib`）
>
> **相关文件**：同目录的 `agent-rules.md` 是规则文件（内容与代码中的 `SEED_RULES` 完全相同，已用 diff 核对）；`agent-rules.zh.md` 是机器翻译的中文版，连字段名都被翻译了（如 `- 类别:启动`），**不能**被本解析器读取，只供阅读。
>
> **副作用**：若 `code/agent-rules.md` 不存在会先写入种子规则；每次运行都会写（覆盖）`code/rule_report.json`。

---

## 1. 这份代码在考察什么

讲义的核心主张是："Instructions written as prose are wishes. Instructions written as constraints are tests." 这份代码演示把规则变成"测试"的完整链路：

1. **规则文件机器可读**：每条规则一个 `##` 标题（slug），下面是 `- category:`、`- check:` 两个字段和一行描述。
2. **解析器**：`parse_rules` 把 Markdown 解析成 `Rule` dataclass 列表。
3. **检查器**：`RuleChecker` 的每个方法对应一个 `check` 名字，输入是一轮运行的 `TurnTrace`，输出布尔值——确定性、便宜、不调用 LLM。
4. **打分**：`score` 用 `getattr` 按名字把规则分派到检查函数，得到每条规则的 pass/fail。
5. **报告**：写出 `rule_report.json`，供 verification gate（第 38 节）和 reviewer（第 39 节）消费。

五条种子规则正好覆盖讲义的五个类别：startup、forbidden、definition_of_done、uncertainty、approval。

> 一句话：**规则 = Markdown 里的一个名字 + 检查器里的一个函数；"加一条规则"就是"加一个 check"。** 同时要注意解析器的若干静默失败，以及 demo 与讲义描述不一致之处。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `HERE` / `RULES_PATH` / `REPORT_PATH` | 模块常量 | 规则文件与报告都放在 `code/` 下 | 文件位置 |
| `SEED_RULES` | 多行字符串 | 五条种子规则，各属一个类别 | 五类规则 |
| `Rule` | dataclass | slug、category、check、description | 机器可读的规则 |
| `TurnTrace` | dataclass | 一轮运行的观测：读没读状态、改了哪些文件、置信度、是否求助、测试退出码、新增依赖、已批准项 | 检查的输入（运行轨迹） |
| `write_seed_rules` | 函数 | 规则文件不存在时写入种子 | 幂等初始化 |
| `parse_rules` | 函数 | 正则切分 Markdown → `list[Rule]` | 规则解析器 |
| `RuleChecker` | 类 | 五个检查方法，一条规则一个 | 检查器（讲义中的 `rule_checker.py`） |
| `score` | 函数 | 按名字分派、汇总 pass/fail | 规则打分 |
| `main` | 函数 | 构造坏/好两个 trace，打分、打印、写 JSON | 演示 |

数据流：`write_seed_rules` → `parse_rules`（`agent-rules.md` → `Rule[]`）→ 构造 `bad_trace` / `good_trace` → `score(rules, RuleChecker(), trace)` → 打印 PASS/FAIL → 写 `rule_report.json`。

---

## 3. 逐段精讲

### 3.1 规则文件格式

```text
## forbidden/no-release-script-edits
- category: forbidden
- check: no_release_script_edits
Never edit scripts/release.sh outside an approved release task.
```

- slug 采用 `类别/短名` 形式，标题即 ID，改名在 diff 里一目了然（讲义："Renames are visible in diffs"）。
- `check` 的值必须是 `RuleChecker` 上的方法名——这是 Markdown 与 Python 之间唯一的"接口"。
- 注意文件位置：讲义说规则在 `docs/agent-rules.md`，代码用的是 `code/agent-rules.md`（`HERE / "agent-rules.md"`）；讲义说检查器在 `rule_checker.py`，代码把它放在 `main.py` 里。概念一致，路径不同。

### 3.2 两个数据类

```python
@dataclass
class Rule:
    slug: str
    category: str
    check: str
    description: str


@dataclass
class TurnTrace:
    read_state_file: bool
    edited_files: list[str]
    confidence: float
    asked_for_help: bool
    tests_exit_code: int | None
    added_dependencies: list[str]
    approvals: list[str] = field(default_factory=list)
```

- `TurnTrace` 是"一轮运行留下的证据"。配套 skill 规定：agent 产品至少要记录 `read_state_file`、`edited_files`、`tests_exit_code` 才能接入检查器——**没有观测就没有检查**。
- `tests_exit_code: int | None`：`None` 表示"没跑测试"，与"跑了但失败"（非零）区分开。`tests_pass` 用 `== 0` 判断，`None == 0` 为 `False`，所以"没跑"也算失败（已实测）——正确的 fail closed。
- `approvals` 唯一带默认值，必须放在最后（dataclass 字段顺序规则）。

### 3.3 解析器 `parse_rules`

```python
    for block in re.split(r"\n## ", text)[1:]:
        head, *rest = block.split("\n", 1)
        slug = head.strip()
        body = rest[0] if rest else ""
        cat_match = re.search(r"-\s*category:\s*(\S+)", body)
        check_match = re.search(r"-\s*check:\s*(\S+)", body)
        non_empty = [ln.strip() for ln in body.splitlines() if ln.strip()]
        desc = non_empty[-1] if non_empty else ""
        if not cat_match or not check_match:
            continue
```

逐行理解：

- `re.split(r"\n## ", text)`：以"换行 + `## `"为分隔符切块；`[1:]` 丢掉第一块（`# Agent Rules` 标题部分）。
- `head, *rest = block.split("\n", 1)`：最多切一刀，第一行是 slug，剩余部分是 body；`*rest` 让"没有 body"时 `rest == []` 而不报错。
- `(\S+)`：取冒号后的第一个非空白"词"作为值。
- 描述 = body 中**最后一个**非空行。

种子文件上完全正确，但实测几种"手写时很常见"的输入会出问题：

| 输入 | 实际结果 | 问题 |
|------|---------|------|
| 文件直接以 `## a/b` 开头 | 第一条规则消失 | 分隔符要求前面有 `\n`，且 `[1:]` 丢了第一块 |
| 规则缺 `- check:` | 被 `continue` 跳过 | 愿望式规则**静默消失**，而不是报错 |
| 描述写在字段前 | `description='- check: x'` | "最后一个非空行"的假设不成立 |
| 描述跨两行 | 只保留最后一行 | 同上 |
| 规则下有 `### note` 子标题 | 描述变成子标题下的文字 | 同上 |
| `category: style` | 照常接受 | 不校验五个类别 |

改进方法见测验 Q9：用 `re.M` 的 `^## ` 切分、把字段解析成字典、缺 check 或类别非法时抛异常、描述排除字段行后拼接。

### 3.4 检查器 `RuleChecker`

```python
class RuleChecker:
    def state_file_fresh(self, trace):
        return trace.read_state_file

    def no_release_script_edits(self, trace):
        return "scripts/release.sh" not in trace.edited_files

    def tests_pass(self, trace):
        return trace.tests_exit_code == 0

    def opened_question_when_unsure(self, trace):
        return trace.confidence >= 0.7 or trace.asked_for_help

    def new_dependency_approved(self, trace):
        if not trace.added_dependencies:
            return True
        return all(dep in trace.approvals for dep in trace.added_dependencies)
```

| check | 判定逻辑 | 简化 / 隐患 |
|-------|---------|------------|
| `state_file_fresh` | 读了状态文件即通过 | 名字叫"fresh"却不检查新鲜度；规则描述要求"在任何 tool call **之前**读取"，但 trace 里没有顺序信息 |
| `no_release_script_edits` | 精确字符串不在列表中 | `./scripts/release.sh` 可绕过（已实测返回 `True`）；规则描述中的"outside an approved release task"例外没有实现 |
| `tests_pass` | 退出码等于 0 | `None`（没跑）也判失败，正确 |
| `opened_question_when_unsure` | 置信度 ≥ 0.7 或求助过 | 阈值 0.7 写死在代码里，规则文件里看不到；规则描述说"写 question note"，检查的却是 `asked_for_help` |
| `new_dependency_approved` | 每个新依赖都在 approvals 中 | 用 `all(...)`；没有新依赖时直接通过 |

- 所有检查都是纯函数：只读 trace，不访问网络、不调用模型，满足 skill "Checks that require LLM calls" 的硬拒绝条款。
- `opened_question_when_unsure` 在边界上：`confidence=0.7` 通过；`0.69` 且 `asked_for_help=True` 也通过（已实测）。

### 3.5 打分 `score`：按名字分派

```python
def score(rules, checker, trace):
    results = []
    for rule in rules:
        check_fn = getattr(checker, rule.check, None)
        passed = bool(check_fn(trace)) if check_fn else False
        results.append({"slug": rule.slug, "category": rule.category, "passed": passed})
    return results
```

- `getattr(obj, name, default)`：用**字符串**取对象的属性/方法，这是"Markdown 里写函数名、Python 里找到函数"的关键。它比 `eval` 安全，因为只能访问 `RuleChecker` 上已有的属性。
- 找不到方法时记为 `False`（fail closed），但结果里**没有错误原因**——拼错 check 名与真实违规看起来一模一样（测验 Q4）。
- `bool(...)` 把检查函数的返回值统一成布尔，防止某个 check 返回 `None` 或列表。
- 结果中没有 `severity`、没有 `description`、没有失败证据；mission 要求的"aggregate severity"未实现。

### 3.6 `main`：两个 trace 与报告

```python
    bad_trace = TurnTrace(
        read_state_file=False,
        edited_files=["app.py", "scripts/release.sh"],
        confidence=0.4,
        asked_for_help=False,
        tests_exit_code=1,
        added_dependencies=["fastapi"],
    )
```

- `bad_trace` 的**每个字段**都是违规值，所以五条规则全部失败；讲义和 mission 都说 demo "violates two rules"，与代码不符（测验 Q11 给出了恰好违反两条的 trace）。
- `good_trace` 全部通过。
- 打印用 `f"{r['slug']:42}"` 左对齐到 42 列，形成整齐的表格。
- 报告 JSON 包含 `bad`、`good` 两组结果和两份 trace 的 `asdict`。讲义说输出会打印"run trace"，实际 trace 只写进了 JSON，没有打印。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| Markdown 作为规则源 | 人可读、diff 友好、可在 PR 中审查 | 解析脆弱；生产中用 pre-commit hook 生成 `agent-rules.lock.json`，热路径只读 JSON（讲义） |
| `check` 字段写函数名，`getattr` 分派 | 规则文件与代码解耦，加规则只需加方法 | 名字写错只会静默失败；启动时应校验所有 check 都存在 |
| 检查函数输入是 `TurnTrace` | 检查与 agent 实现解耦，任何产品只要产出 trace 就能复用 | 依赖 trace 的完整性；trace 漏记字段，检查就失明 |
| 纯函数、确定性检查 | 每轮可跑、结果可复现、不受 prompt injection 影响 | 无法表达语义判断；那部分交给 reviewer |
| 找不到 check 记为失败 | fail closed | 应附带错误原因，区分"违规"与"配置错误" |
| 缺字段的规则被跳过 | 容错 | 违背"愿望式规则要么升级要么删除"；应抛错 |
| 没有 severity / expiry | 保持演示简单 | 讲义的生产模式（block/warn/info、90 天过期）需要自己补（练习 2、4） |
| 阈值 0.7 写死在检查器 | 代码短 | 规则参数应写在规则文件里，便于审查和调整 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 续行的三引号字符串 | `SEED_RULES = """\` | 开头的 `\` 吞掉第一个换行，让字符串从 `# Agent Rules` 开始 |
| `re.split` | `re.split(r"\n## ", text)[1:]` | 按正则切分字符串；`r"..."` 是原始字符串，反斜杠不转义 |
| `re.search` + `group` | `re.search(r"-\s*check:\s*(\S+)", body).group(1)` | 找第一个匹配；`(\S+)` 是捕获组，`group(1)` 取出 |
| 正则元字符 | `\s*`、`\S+` | 任意个空白 / 至少一个非空白字符 |
| 星号解包 | `head, *rest = block.split("\n", 1)` | 第一个元素给 `head`，剩下的打包成列表 `rest` |
| `str.split(sep, maxsplit)` | `block.split("\n", 1)` | 最多切一刀 |
| 条件表达式 | `rest[0] if rest else ""` | 空列表为假 |
| 带条件的列表推导式 | `[ln.strip() for ln in body.splitlines() if ln.strip()]` | 去空白并过滤空行 |
| 负索引 | `non_empty[-1]` | 取最后一个元素 |
| `getattr(obj, name, default)` | `getattr(checker, rule.check, None)` | 用字符串名字动态取方法，找不到返回默认值 |
| 方法作为一等对象 | `check_fn(trace)` | 取到的绑定方法可以像普通函数一样调用 |
| `all()` + 生成器 | `all(dep in trace.approvals for dep in ...)` | 全部为真才为真；空序列返回 `True` |
| `or` 短路 | `trace.confidence >= 0.7 or trace.asked_for_help` | 前者为真就不再计算后者 |
| 联合类型注解 | `tests_exit_code: int \| None` | 整数或 None |
| 类型注解的局部变量 | `rules: list[Rule] = []` | 给变量标注类型，便于阅读和静态检查 |
| f-string 宽度 | `f"{r['slug']:42}"` | 字符串默认左对齐，占 42 个字符宽 |
| f-string 内条件表达式 | `{'PASS' if r['passed'] else 'FAIL'}` | 花括号里可以写任意表达式 |
| `asdict` + `json.dumps` | `asdict(bad_trace)` | dataclass → dict → JSON |
| `Path.name` | `REPORT_PATH.name` | 只取文件名部分 |

---

## 6. 运行结果解读

实际运行（Python 3.13，退出码 0；在临时目录副本中运行以免覆盖仓库中的文件）：

```text
rules parsed: ['startup/state-file-fresh', 'forbidden/no-release-script-edits', 'done/tests-pass', 'uncertainty/open-question-note', 'approval/new-dependency']

bad trace:
  startup/state-file-fresh                   FAIL
  forbidden/no-release-script-edits          FAIL
  done/tests-pass                            FAIL
  uncertainty/open-question-note             FAIL
  approval/new-dependency                    FAIL

good trace:
  startup/state-file-fresh                   PASS
  forbidden/no-release-script-edits          PASS
  done/tests-pass                            PASS
  uncertainty/open-question-note             PASS
  approval/new-dependency                    PASS

wrote rule_report.json
```

逐项解读：

- **rules parsed**：五条规则都被解析出来，顺序与文件一致，每个类别一条。
- **bad trace 五条全挂**：`read_state_file=False` → startup 挂；改了 `scripts/release.sh` → forbidden 挂；`tests_exit_code=1` → done 挂；置信度 0.4 且没求助 → uncertainty 挂；新增 `fastapi` 未批准 → approval 挂。讲义"violates two rules"的说法与此不符。
- **good trace 全过**：读了状态、只改 `app.py` 与 `test_app.py`、测试退出 0、置信度 0.9、没有新依赖。
- **rule_report.json**：结构为 `{"bad": [...], "good": [...], "trace_bad": {...}, "trace_good": {...}}`，每条结果只有 `slug`、`category`、`passed` 三个键，没有 severity 和聚合结论。
- **额外实验**（import 后调用）：恰好违反两条的 trace（改 release.sh + 未批准依赖）得到 forbidden 与 approval 两个 False；`edited_files=["./scripts/release.sh"]` 时 forbidden 检查返回 `True`（绕过）。

---

## 7. 动手改一改

1. **严格解析**：按测验 Q9 重写 `parse_rules`——缺 check 或类别非法时抛异常；再在启动时断言每个 `rule.check` 都是 `RuleChecker` 的方法。
2. **讲义练习 2：severity**：解析 `- severity:` 字段（默认 `block`），`score` 结果带上 severity，报告增加 `aggregate`；聚合为 `block` 时 `raise SystemExit(1)`（练习 3 接 CI，参考测验 Q10）。
3. **修路径绕过**：`no_release_script_edits` 先用 `posixpath.normpath` 规范化再比较；进一步把禁止列表移到规则文件里（例如 `- paths: scripts/release.sh`），让检查器读取参数而不是写死。
4. **把阈值移进规则**：`opened_question_when_unsure` 的 0.7 改为从规则字段 `- threshold: 0.7` 读取，体会"规则参数可审查"的好处。
5. **讲义练习 4：过期**：给规则加 `expires_at`，维护一个 `rule_history.jsonl`，实现测验 Q12 的 `expiry_findings`。
6. **进阶：lock 文件**：写一个 `build_lock.py`，把 Markdown 解析成 `agent-rules.lock.json`；`main.py` 只读 lock，并在 lock 比 Markdown 旧时拒绝运行（模拟 pre-commit hook 没跑的情况）。

---

## 8. 常见坑

- **愿望式规则被静默丢弃**：缺 check 的规则不会报错，只是从报告里消失，读者以为它"通过了"。
- **check 名拼错**：报告显示 FAIL，但原因是配置错误而不是 agent 违规。
- **字符串精确匹配做安全检查**：路径要规范化；最好在写文件的工具层就按 ACL 拦截，规则检查作为兜底。
- **把阈值、路径写死在检查器里**：规则文件看起来很清楚，真实行为却藏在代码里，审查者看不到。
- **只记录"结果"不记录"顺序"**：像"在任何 tool call 之前读状态"这样的规则，trace 里必须有时间顺序才能检查。
- **在 CI 里跑 demo trace**：`bad_trace` 永远失败；CI 应检查最近一次真实运行的 trace。
- **误用中文规则文件**：`agent-rules.zh.md` 的字段名被翻译成了中文，喂给解析器会得到空列表。
