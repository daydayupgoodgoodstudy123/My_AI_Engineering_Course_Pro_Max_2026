# 测验 · 综合项目 86：宪法式规则引擎（Capstone 86 — Constitutional Rules Engine）

> **阶段 19 · 综合项目 · 第 86 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py)、[code/yaml_subset.py](../code/yaml_subset.py)、[code/tests.py](../code/tests.py)、[code/rules.yml](../code/rules.yml) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)（含 tests.py、rules.yml）、[code/yaml_subset.讲解.md](../code/yaml_subset.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 规则引擎 vs 分类器 | 讲义："Classifiers cover the recognizable failures. Rules engines cover the contractual ones."——"拒答必须给出下一步""代码回复必须以可运行块或假设结尾"这类约束不是分类目标，而是对回复的谓词 |
| 2 | 宪法 = 声明式 YAML | 规则写在 YAML 文件里，进版本控制、走独立评审，非工程师也能读；讲义："A rule is a name, a predicate, and an explanation." |
| 3 | 规则的字段 | `name`、`severity`（low/medium/high）、`applies_when`（适用条件）、`must`（必须满足的谓词）、`explanation`，可选 `fix` |
| 4 | 原子谓词 | `contains_regex`、`not_contains_regex`、`starts_with_regex`、`ends_with_regex`、`max_words`、`min_words` |
| 5 | 组合谓词 | `all_of`、`any_of`、`not_` 递归嵌套；`all_of` 遇到第一个失败就返回，`any_of` 遇到第一个成功就返回（都短路） |
| 6 | 三种状态 | `applies_when` 为假 → `not_applicable`（`must` 不评估）；否则 `must` 为真 → `pass`，为假 → `violation` |
| 7 | Fixer | 每条规则一个确定性的局部修复：`append_if_missing`、`prepend_if_missing`、`replace_regex`；修复后**再跑一遍引擎**确认 |
| 8 | 结构化 diff | 用 `difflib.SequenceMatcher` 按行比较草稿与修订稿，输出 `add / remove / edit-removed / edit-added` 的 `Change` 列表，供审计 |
| 9 | 与第 85、87 节的关系 | severity 与第 85 节对齐；第 87 节把 high 规则违规与 high 分类判决一样处理：block |
| 10 | YAML 加载 | 有 PyYAML 时用 `yaml.safe_load`，否则用手写的 `yaml_subset._parse`；两条路径在 `rules.yml` 上结果一致，但在其他 YAML 写法上有明显差异 |

### 核心技能（能动手做到）

- [ ] 读懂 `rules.yml` 中任意一条规则，手算它在一段文本上的状态（not_applicable / pass / violation）和 `matched_span`
- [ ] 用 `all_of / any_of / not_` 写出新的组合规则，并为它写 `fix`
- [ ] 跑通"草稿 → 引擎 → fixer → 引擎第二遍 → diff"的完整闭环，并解释每条 `Change`
- [ ] 找出 fixer 修好一条规则却触发另一条规则的情况，设计"迭代到不动点 + 升级"的处理
- [ ] 指出 `yaml_subset` 不支持或解析错误的 YAML 写法，并能在没有 PyYAML 的环境下测试它
- [ ] 实现讲义练习 3：在一组草稿上统计每条规则的违规率，找出"过度触发"的规则
- [ ] 用 `unittest` 运行 `tests.py`，并说出测试覆盖不到的地方

---

## 二、基础自测（选择题）

**Q1.** 讲义主张把约束写成声明式的 YAML "宪法"，而不是在代码里写一堆 if。最主要的理由是：

- A. YAML 的解析速度比 Python 代码更快
- B. YAML 支持锚点和别名，可以复用规则
- C. 规则文件可以被非工程师阅读、放进版本控制、走独立的评审流程，修改规则不必改代码
- D. Python 标准库内置了 YAML 解析器

**Q2.** 一条规则的 `applies_when` 在某段文本上求值为假时，`Engine.evaluate` 会：

- A. 记录状态 `not_applicable`，不评估 `must`，也不产生 violation
- B. 记录状态 `pass`，因为没有违反任何东西
- C. 仍然评估 `must`，若不满足就记为 `violation`
- D. 抛出 `ValueError`，因为规则无法应用

**Q3.** 模型回复 `"I can't help with that."`（一句没有任何下一步建议的拒答）经过默认宪法评估，结果是：

- A. `no-empty-refusal` 违规，severity medium
- B. `no-empty-refusal` 违规，severity high
- C. 所有规则都是 `not_applicable`，因为文本少于 800 词
- D. 没有任何违规：`applies_when` 的正则只认 `i cannot / i will not / i refuse / unable to help`，`can't` 不匹配，规则不适用——这是一次漏报

**Q4.** 调用 `_eval_predicate({"contains_regex": "a", "max_words": 1}, "a b c d")` 的返回值是：

- A. `(False, 'word count 4')`，因为超过 1 个词
- B. `(True, 'a')`：一个节点里写了两个谓词时，只有 if 链中**先被检查到**的 `contains_regex` 生效，`max_words` 被静默忽略
- C. 抛出 `ValueError: unknown predicate`
- D. `(False, None)`，两个谓词按 all_of 合并

**Q5.** 下面两句回复分别经过 `no-pii-in-examples`（`applies_when: contains_regex '\b(example|sample)\b'`）评估：
① `Contact me at lee@example.com for details.` ② `Contact me at lee@corp.com for details.`

- A. ① 违规（high）、② 不适用：①中邮箱域名里的 `example` 本身就满足了 `applies_when`
- B. ① ② 都违规，因为都含邮箱
- C. ① ② 都不适用，因为句子里没有"example"这个独立单词
- D. ① 不适用、② 违规

**Q6.** Fixer 对拒答草稿 `"I cannot help with that question."` 追加了 `"\n\nIf this is something I cannot help with, consider rephrasing ..."`。`diff(draft, revised)` 的结果和 demo 打印的信息是：

- A. 一条 `edit-added`，demo 打印 `fixer applied 1 change(s)`
- B. 一条 `add`，内容为整段追加文本
- C. 一条 `edit-removed` 加一条 `edit-added`
- D. 两条 `add`：一条是空行 `""`，一条是追加的句子；demo 打印 `fixer applied 2 change(s)`——这里的"2"是 diff 行数，不是修复次数

**Q7.** 关于 `all_of` 与 `any_of` 的求值方式，正确的是：

- A. 两者都会完整评估所有子谓词，再合并结果
- B. 两者都短路：`all_of` 遇到第一个假就返回，`any_of` 遇到第一个真就返回；因此写错名字的谓词若排在短路点之后，加载和评估时都不会报错
- C. 只有 `any_of` 短路，`all_of` 会评估全部子谓词
- D. `not_` 会把子谓词的 `matched_span` 清空

**Q8.** 本机已安装 PyYAML 6.0.3。`tests.py` 中 `TestYamlSubset` 的 5 个测试实际上验证的是：

- A. 手写的 `_parse` 函数，因为测试文件导入了 `yaml_subset`
- B. 同时验证 PyYAML 和 `_parse` 两条路径
- C. 只验证了 PyYAML：`load_yaml` 优先用 `yaml.safe_load`，手写解析器根本没被执行；讲义说"tests parse by both code paths"并不成立
- D. 什么都没验证，因为测试被跳过了

---

## 三、动手 / 代码题

**Q9.** 下面这段草稿经过"引擎 → fixer → 引擎第二遍"后，第二遍出现了一条**新的 high 违规**。实际运行结果：

```text
draft:  "Here is the code:\n```python\nPHONE = '555-123-4567'\nprint(PHONE)\n```\nDone."
draft violations:   [('end-with-runnable-or-assumption', 'medium', None)]
revised ends with:  "...```\nDone.\n\nAssumption: the example inputs are valid and the module is on the import path."
revised violations: [('no-pii-in-examples', 'high', '555-123-4567')]
```

1. 为什么修复一条 medium 规则会制造出一条 high 违规？
2. demo 的 `demo()` 对这种情况做了什么？讲义流程图里的 "accepted or escalated" 在代码中体现了吗？
3. 设计一个更稳健的修复闭环（给出伪代码或代码）。

**Q10.** 下面是同一份 YAML，PyYAML 与 `yaml_subset._parse` 的实际解析结果：

```yaml
items:
- id: 1
  label: a
- id: 2
```

```text
yaml_subset._parse : {'items': None}
yaml.safe_load     : {'items': [{'id': 1, 'label': 'a'}, {'id': 2}]}
```

1. 结合下面的源码，解释 `_parse` 为什么得到 `None`，以及后面三行去了哪里。
2. 这种"静默丢数据"对规则引擎意味着什么？给出修复思路。

```python
def _parse_mapping(lines, start, indent):
    ...
        if stripped.startswith("- "):
            break
        m = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", stripped)
        ...
        if rest.strip() == "":
            if i + 1 < len(lines) and _indent_of(lines[i + 1]) > indent:
                value, i = _parse_block(lines, i + 1, _indent_of(lines[i + 1]))
                out[key] = value
                continue
            out[key] = None
            i += 1
```

**Q11.**（手算）不运行代码，写出下面草稿经过默认宪法的：① 违规规则与 severity；② fixer 修订后的文本；③ `diff` 结果；④ 你认为这个修复在语义上是否合格。

```text
According to the 2020 census, the population grew.
That is all.
```

**Q12.** 讲义练习 3：给定一组草稿，返回**每条规则的违规率**，帮助团队发现"过度触发"的规则。请实现 `violation_rates(engine, corpus)`，同时给出两种口径（违规数 / 草稿总数、违规数 / 适用数），并在 demo 的 5 条草稿上报告结果。再说明：为什么只看"违规数 / 草稿总数"会误判？

---

## 四、面试高频题

**Q13.**（基础必考）同样是输出侧的安全控制，内容分类器（第 85 节）和规则引擎（本节）分别适合处理什么问题？各举两个例子。

**Q14.**（原理深挖）本节的"宪法式规则引擎"和 Anthropic 提出的 Constitutional AI（RLAIF）有什么本质区别？二者能否配合使用？

**Q15.**（工程实践）规则文件由安全、法务、产品多个团队共同维护。你会如何保证"改一条规则不会把线上搞坏"？

**Q16.**（场景设计）设计一个"草稿 → 检查 → 修复 → 复检"的闭环：哪些违规适合确定性修复，哪些应该交给 LLM 重写，哪些必须直接拒绝？如何审计 fixer 的行为？

**Q17.**（追问型）面试官问："为什么不直接用 Python 写规则？YAML DSL 会带来哪些新风险？"你怎么回答？

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义："The honest representation is a declarative file. A constitution lives in YAML alongside the code, in version control, with a separate review process." 并强调约束"need to be readable by a non-engineer"。

- A 错：速度不是动机，本节规则只有 6 条。
- B 错：`yaml_subset` 明确**不支持**锚点和别名，本节也没用到。
- D 错：Python 标准库没有 YAML 解析器，所以才需要 PyYAML 或手写的 `yaml_subset`。

### Q2 — 答案：A

```python
            applies, _ = _eval_predicate(rule.get("applies_when"), text)
            if not applies:
                report.results.append(
                    RuleResult(rule_name=name, severity=sev, status="not_applicable", explanation=expl)
                )
                continue
```

`continue` 直接跳到下一条规则，`must` 不会被评估。讲义说这样"the team sees the engine evaluated it explicitly"。B 混淆了 `pass` 与 `not_applicable`；C 把 `applies_when` 当成了摆设；D 不对，只有未知谓词才会抛 `ValueError`。注意：缺省 `applies_when` 或写成 `{}` 时恒为真（`no-internal-library-leak`、`bounded-length` 就是这样）。

### Q3 — 答案：D

`applies_when` 是 `'\b(i cannot|i will not|i refuse|unable to help)\b'`，`I can't` 不在其中，规则判为 `not_applicable`。实测该句所有规则都是 `not_applicable` 或 `pass`，没有任何违规。反过来，`"I cannot recommend this library highly enough."`（并非拒答）会被判为 `no-empty-refusal` 违规，fixer 还会给它追加一句"If this is something I cannot help with ..."（已实测）。基于关键词的 `applies_when` 同时存在漏报与误报。

A、B 都假设规则适用了；C 的理由错误，`bounded-length` 对任何文本都适用（`applies_when: {}`），在这里是 `pass` 而非 `not_applicable`。

### Q4 — 答案：B

`_eval_predicate` 是一串 `if "xxx" in node:` 判断，**命中第一个就 return**。`contains_regex` 排在 `max_words` 前面，所以只评估了它，`max_words` 被静默忽略。实测返回 `(True, 'a')`。规则作者很容易在一个映射里写两个谓词并以为是"且"的关系，正确写法是放进 `all_of` 列表。引擎加载时也不会对此报错。C 只在节点里**没有任何**已知谓词时才会发生。

### Q5 — 答案：A

`\b(example|sample)\b` 会在 `lee@example.com` 里匹配到 `example`（`@` 与 `.` 都是词边界）。于是①规则适用，`must` 中的邮箱正则命中，违规，`matched_span = 'lee@example.com'`，fixer 替换为 `[example-contact]`。②的域名不含 example，规则不适用，**真实**的邮箱反而放行了。实测完全如此。这说明 `no-pii-in-examples` 的 `applies_when` 设计有问题：它想表达"在举例时"，实际匹配的是"文本中任意位置出现 example"。

### Q6 — 答案：D

`diff` 按 `splitlines()` 逐行比较。草稿 1 行，修订稿 3 行（原句、空行、新句），`SequenceMatcher` 给出一个 `insert` 操作，代码为插入的每一行生成一条 `add`，所以是 `add ""` 和 `add "If this is ..."` 两条，`outputs/rules_report.json` 中也是这样。demo 用 `len(change_list)` 打印 `fixer applied 2 change(s)`，实际只执行了 1 次修复。同理，`replace_regex` 修改一行会生成 `edit-removed` + `edit-added` 两条记录，也打印"2 change(s)"。

### Q7 — 答案：B

```python
    if "all_of" in node:
        for child in node["all_of"]:
            ok, span = _eval_predicate(child, text)
            if not ok:
                return False, span       # 第一个失败就返回
    if "any_of" in node:
        for child in node["any_of"]:
            ok, span = _eval_predicate(child, text)
            if ok:
                return True, span        # 第一个成功就返回
```

讲义只说"short-circuiting on any_of"，其实 `all_of` 也短路。实测：`{"any_of": [{"contains_regex": "a"}, {"contains_regx": "b"}]}` 在文本 `"a"` 上返回 `(True, 'a')`，拼写错误的 `contains_regx` 不报错；换成文本里没有 `a` 时才会抛 `ValueError: unknown predicate: ['contains_regx']`。`Engine.__init__` 只校验 `severity` 和必填字段，不校验谓词结构。D 错：`not_` 原样返回子谓词的 span。

### Q8 — 答案：C

```python
def load_yaml(text: str) -> Any:
    try:
        import yaml
        return yaml.safe_load(text)
    except ModuleNotFoundError:
        return _parse(text)
```

有 PyYAML 时 `_parse` 一行都不会执行。我们用 import 钩子屏蔽 PyYAML 后重跑，18 个测试仍全部通过，demo 输出与仓库报告逐字节一致——说明 `_parse` 在这些用例上是对的，但默认环境下它没有被测试覆盖。讲义的说法（"tests parse by both code paths"）以及"loader accepts ... a JSON file (built-in)"都与代码不符：代码里没有 JSON 分支，`_parse` 遇到 `{"rules": []}` 会抛 `malformed line`。

### Q9 — 参考答案

1. **修复引入了新的适用条件**。`end-with-runnable-or-assumption` 的 fix 文本是 `"Assumption: the example inputs are valid ..."`，里面有单词 `example`。草稿原本不含 example/sample，`no-pii-in-examples` 不适用；追加之后规则变得适用，而代码里的 `555-123-4567` 正好是电话形状，于是第二遍出现 high 违规。fixer 只在"违规规则"自身范围内做局部编辑，不考虑对其他规则的影响。
2. demo 只是在第二遍有违规时打印 `revised still has N violation(s)`，并把 `revised_violations` 写进报告；**没有任何升级或拒绝逻辑**，也不会再修一轮。流程图里的 "accepted or escalated" 只存在于讲义中。（第 87 节的安全关卡在 redact 分支中会再调用一次 fixer，但同样不做第二次复检。）
3. 稳健闭环：迭代到不动点，设置上限，最后按 severity 决定接受或升级。

```python
def revise(engine, fixer, draft, max_rounds=3):
    text = draft
    history = []
    for _ in range(max_rounds):
        violations = engine.evaluate(text).violations()
        if not violations:
            return "accepted", text, history
        new_text = fixer.apply(text, violations)
        history.append(diff(text, new_text))
        if new_text == text:          # 没有可用的修复，不再空转
            break
        text = new_text
    report = engine.evaluate(text)
    if report.max_severity() == "high":
        return "escalated", REFUSAL_TEXT, history       # high 仍在：拒答或转人工
    return "accepted_with_warnings", text, history
```

再配合两个规则层面的修正：fix 文本避免出现会触发其他规则的词（例如把 "example inputs" 改成 "the inputs"）；`no-pii-in-examples` 的 `applies_when` 应排除邮箱内部的匹配（如 `(?<![@.\w])\b(example|sample)\b(?!\.\w)`（实测：`lee@example.com`、`sample.org` 不再触发，`Example user:`、句末的 `for example.` 仍触发）），或者干脆不加适用条件、对所有输出检查 PII。

### Q10 — 参考答案

1. 处理第 1 行 `items:` 时 `rest` 为空，于是检查下一行缩进：`- id: 1` 的缩进是 0，**不大于**当前映射缩进 0，代码认为 `items` 没有子块，写入 `None`。接着处理第 2 行，它以 `- ` 开头，`_parse_mapping` 直接 `break`；回到 `_parse` 后只返回第一个块的结果，剩下的行**被静默丢弃**，没有任何报错。YAML 规范允许序列与父键同缩进（很多格式化工具默认这样输出），PyYAML 因此能正确解析。
2. 对规则引擎而言，如果有人把 `rules:` 下面的列表写成这种风格，在**没有 PyYAML 的环境**里 `data["rules"]` 会是 `None`，`Engine.__init__` 遍历 `None` 时会报 `TypeError`；更隐蔽的情况是只丢了某条规则内部的 `any_of` 列表（实测：`must` 变成 `{'any_of': None}`，同一条规则的其他字段照常解析），加载时一切正常，直到 `evaluate` 时才抛 `TypeError: 'NoneType' object is not iterable`。修复思路：
   - 在 `rest` 为空、下一行是同缩进的 `- ` 时，也调用 `_parse_sequence`（`_indent_of(next) >= indent and next.lstrip().startswith("- ")`）；
   - 解析结束时检查是否还有未消费的行，有则抛错，而不是静默返回；
   - 加载后用 JSON Schema 或手写校验检查每条规则的结构；
   - 生产中直接依赖 PyYAML（`safe_load`），把手写解析器只当作教学示例。

其他已实测的差异：双引号字符串 `"café"` 被 `unicode_escape` 解码成 `cafÃ©`；单引号里的 `''` 不会还原成 `'`；`don't leak # secret` 中的撇号让注释没被去掉；`yes/no` 在 PyYAML（YAML 1.1）里是布尔值，在 `_parse` 里是字符串；缩进多出来的行会被 `_parse_mapping` 悄悄跳过。

### Q11 — 参考答案

1. `cite-when-asserting-fact`（low）：`applies_when` 的 `(?im)^(according to|...)\b` 在**行首**匹配到 `According to`（`m` 标志让 `^` 匹配每一行的开头）；`must` 要求文本中有 `\([\w .,-]+\)` 形式的括号，没有 → 违规，`matched_span = None`。其余规则：`bounded-length`、`no-internal-library-leak` 为 pass，另外 3 条 not_applicable。
2. fix 是 `append_if_missing: " (citation pending)"`：

```text
According to the 2020 census, the population grew.
That is all. (citation pending)
```

3. `diff` 结果：`[edit-removed 'That is all.', edit-added 'That is all. (citation pending)']`（已实测）。
4. 语义上**不合格**：括号被追加到**全文末尾**，挂在了 `That is all.` 后面，而不是 `According to` 那一行；而且 `(citation pending)` 只是满足了正则，并不是真正的引用。`must` 的正则也很宽松，任意位置的任意括号（如 `(see below)`）都能让规则通过。更合理的做法是对 `According to` 所在行做 `replace_regex`，或者在无法给出真实来源时删除这一断言、交给人工复核。这也说明 fixer 只能做"局部、机械"的编辑，讲义："structural rewrites belong in a separate refusal-and-help layer"。

### Q12 — 参考答案

```python
from collections import Counter

def violation_rates(engine, corpus):
    applicable, violated = Counter(), Counter()
    for text in corpus:
        for r in engine.evaluate(text).results:
            if r.status != "not_applicable":
                applicable[r.rule_name] += 1
            if r.status == "violation":
                violated[r.rule_name] += 1
    n = len(corpus)
    out = {}
    for rule in engine.rules():
        name = rule["name"]
        out[name] = {
            "violations": violated[name],
            "applicable": applicable[name],
            "rate_over_corpus": violated[name] / n,
            "rate_over_applicable": violated[name] / applicable[name] if applicable[name] else 0.0,
        }
    return out
```

在 demo 的 5 条草稿上（已实际运行）：

| 规则 | 违规 | 适用 | 违规/总数 | 违规/适用 |
|---|---|---|---|---|
| no-empty-refusal | 1 | 1 | 0.2 | 1.0 |
| end-with-runnable-or-assumption | 1 | 1 | 0.2 | 1.0 |
| no-pii-in-examples | 1 | 1 | 0.2 | 1.0 |
| cite-when-asserting-fact | 0 | 0 | 0.0 | 0.0 |
| no-internal-library-leak | 1 | 5 | 0.2 | 0.2 |
| bounded-length | 0 | 5 | 0.0 | 0.0 |

只看"违规/总数"，4 条规则都是 0.2，看不出差别；看"违规/适用"，前三条只要适用就 100% 违规——在 demo 语料上这是刻意构造的结果，但在真实语料上如果某条规则的"违规/适用"长期接近 1，往往说明 `applies_when` 太宽（比如 `I cannot recommend ...` 被当成拒答）或 `must` 太严。这两个比率要一起看，还要配合人工抽样判断违规是否为真阳性，并且 demo 的 5 条草稿本来就是为每条规则各造了一个反例，不能代表真实分布。

### Q13 — 参考回答要点

- **分类器**（第 85 节）回答"这段内容**是不是**某类坏东西"：骚扰辱骂、PII 泄漏、system prompt 回显、仇恨言论等"可识别的失败"。输出 severity + score，适合统计/模型方法。
- **规则引擎**（本节）回答"这段回复**有没有遵守约定**"：讲义例子是"包含代码的回复必须以可运行块或声明的假设结尾"、"每次拒答都必须给出下一步"；本节还包括内部库名不得出现、长度上限、断言要附引用。它们是对回复（以及对话和系统策略）的谓词，需要非工程师可读。
- 二者都输出 low/medium/high，第 87 节按最大 severity 统一处置。
- 加分点：规则引擎还能**修复**（fixer + 复检 + diff），分类器通常只能打码或拦截；规则引擎的问题是覆盖面窄、需要人维护，分类器的问题是难解释、有误报。

### Q14 — 参考回答要点

- **Constitutional AI**（参见阶段 18 · 05）：在**训练阶段**用一组自然语言原则，让模型自我批评、修订回复，并用 AI 反馈（RLAIF）训练偏好模型，把原则"内化"进权重。
- **本节的宪法式规则引擎**：在**推理阶段**对输出做确定性检查，规则是可执行的谓词，结果可复现、可审计、可单测；不改变模型本身。
- 相同点：都是"先写成文的原则，再据此批评和修订"——本节的 fixer + 第二遍检查与 CAI 的 critique → revision 在结构上相似。
- 配合方式：CAI 降低违规的**基础概率**；运行时规则引擎作为**硬约束**兜底，处理必须 100% 遵守的契约（如内部名称不得泄漏）；规则引擎的违规日志还可以反过来变成训练数据。
- 常见误区：把二者等同，认为有了 CAI 就不需要运行时检查，或者认为规则引擎能理解自然语言原则。

### Q15 — 参考回答要点

- **加载即校验**：用 schema 校验每条规则（字段、severity、谓词名、正则能否编译），未知谓词在加载时就报错，而不是等到某次评估走到那个分支（本节代码做不到这点，见 Q7）。
- **每条规则配测试**：至少一个应违规、一个应通过、一个不适用的样例，作为规则文件的单元测试；CI 中两条 YAML 加载路径都要跑。
- **回放语料**：改规则前后在历史输出语料上跑 `violation_rates`，对比每条规则的违规率变化；突增的规则需要人工抽检。
- **灰度发布**：新规则先以 shadow 模式运行（只记录、不处置），观察误报率后再切换到正式动作；severity 先给 low，确认后再升级。
- **评审与版本**：规则文件走 code review，需要安全/法务签字；`version` 字段写入 trace，出事时能追溯是哪一版宪法做的决定。
- **性能与安全**：限制正则复杂度，防止灾难性回溯（ReDoS）；限制规则数量和嵌套深度。

### Q16 — 参考回答要点

- **确定性修复**（适合 fixer）：局部、可机械完成、修复后语义不变——替换内部库名、把示例中的邮箱换成占位符、追加固定的免责或"下一步"语句。
- **交给 LLM 重写**：需要理解上下文的修复——补真实引用、把空洞拒答改写成带替代方案的回复、缩短超长回复（本节 `bounded-length` 没有 fix，fixer 也做不到）。重写后必须再跑一遍引擎和分类器。
- **直接拒绝 / 转人工**：high severity 且修复后仍违规；修复引入新违规（Q9）；多轮修复不收敛。
- **闭环**：迭代上限（如 3 轮）+ 不动点检测 + 最终按最大 severity 升级（见 Q9 代码）。
- **审计**：保存每轮的结构化 diff、触发的规则名、规则文件版本；定期抽样人工复核 fixer 的修改，统计"修复后仍违规率""修复引入新违规率"，后者高说明 fix 文本或规则之间有冲突。
- 加分点：diff 里可能含有被替换掉的敏感原文（`edit-removed` 行），审计日志要按敏感数据处理。

### Q17 — 参考回答要点

- **为什么用 DSL**：规则可被非工程师阅读和评审；规则与执行引擎分离，修改规则不需要发布代码；可以静态分析（统计规则、检查冲突）；执行受限，不会在规则里写出任意副作用。
- **新风险**：
  - **解析差异**：不同 YAML 解析器结果不同（本节 `yaml_subset` 与 PyYAML 在同缩进序列、Unicode、`yes/no`、`''` 转义上都不同），同一份宪法在不同环境下语义不同；
  - **静默错误**：同一映射中写两个谓词只生效一个（Q4）、谓词拼写错误被短路掩盖（Q7）、缩进错误导致数据丢失（Q10）；
  - **正则风险**：规则作者写出灾难性回溯的正则，一段恶意输出就能拖垮服务；`IGNORECASE | DOTALL` 是全局强加的，作者可能不知道；
  - **反序列化安全**：必须用 `yaml.safe_load` 而不是 `yaml.load`，否则 YAML 标签可以构造任意 Python 对象（本节代码用的是 `safe_load`，正确）。
- **缓解**：schema 校验、规则单元测试、正则超时或使用线性时间的正则引擎、固定解析器版本。

---

## 六、关联知识点

### 前置知识
- [阶段 19 · 85 内容分类器集成](../../85-content-classifier-integration/docs/zh.md)：severity 体系与"block / redact / warn / log"处置方式，本节规则引擎与之对齐。
- [阶段 18 · 05 Constitutional AI 与 RLAIF](../../../18-ethics-safety-alignment/05-constitutional-ai-rlaif/docs/zh.md)："宪法"概念的来源：训练阶段用成文原则做自我批评与修订。
- [阶段 15 · 17 Constitutional AI 与规则覆盖](../../../15-autonomous-systems/17-constitutional-ai/docs/zh.md)：自主系统中用规则覆盖约束 agent 行为。
- [阶段 19 · 25 Verification Gates 与观察预算](../../25-verification-gates-observation-budget/docs/zh.md)：讲义列出的前置课程，"检查—放行"关卡的设计思路。
- [阶段 19 · 15 宪法式安全 Harness 与红队演练场](../../15-constitutional-safety-harness/docs/en.md)：较早的综合项目中对"宪法式"安全检查的另一种实现（该节暂无中文讲义）。

### 本节被哪些后续内容用到
- [阶段 19 · 87 端到端安全关卡](../../87-end-to-end-safety-gate/docs/zh.md)：导入本节的 `Engine` 与 `Fixer`，在生成后阶段与第 85 节的分类路由器一起评估，high 规则违规直接 block，redact 时调用 fixer。
- [阶段 18 · 29 内容审核系统：OpenAI、Perspective、Llama Guard](../../../18-ethics-safety-alignment/29-moderation-systems-openai-perspective-llamaguard/docs/zh.md)：审核系统中"策略文档 → 可执行规则"的生产实践。
- [阶段 10 · 09 Constitutional AI 与自我改进](../../../10-llms-from-scratch/09-constitutional-ai-self-improvement/docs/zh.md)：从模型训练角度看 critique → revision 闭环。

### 延伸关键词
`policy as code` · `declarative rules` · `predicate composition` · `short-circuit evaluation` · `not_applicable` · `deterministic fixer` · `fixed-point iteration` · `difflib.SequenceMatcher` · `yaml.safe_load` · `JSON Schema validation` · `ReDoS` · `shadow mode` · `Constitutional AI`
