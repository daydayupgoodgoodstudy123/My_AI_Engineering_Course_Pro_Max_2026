# 测验 · 任务规范格式（Task Spec Format）

> **阶段 19 · 综合项目 · 第 70 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 为什么要"冻结" spec | eval 脚本会比测试增长得快；先定 JSONL schema + 校验器，"拒绝其他一切"，跨 run 的数字才可比 |
| 2 | 记录形状 | 一行一个 JSON 对象；必填 `task_id / category / prompt / targets / metric_name / post_process`，可选 `few_shot_examples / metadata`；未知顶层字段直接拒绝 |
| 3 | 三套封闭词表 | 5 个 category、6 个 metric（`exact_match f1 bleu_4 rouge_l accuracy code_exec`）、6 条 post-process 规则；加新词条 = 加新课 + 改校验器 |
| 4 | category–metric 合法组合 | `LEGAL_CATEGORY_METRIC` 表：如 `code_exec` 只能配 `code_exec`，`mcq` 只能配 `exact_match/accuracy` 且 target 必须是单个 `A–E` 字母 |
| 5 | 字段级规则 | `task_id` 只允许 `[A-Za-z0-9_-]`、文件内唯一；prompt 非空且不能有尾随空白；targets 非空字符串列表；few-shot 最多 8 条 |
| 6 | 校验器行为 | 坏行只废掉这一条记录、不终止整次 run；每条记录**只报第一个错误**；返回 `(validated, errors)` 两个列表 |
| 7 | few-shot 渲染归 runner | 作者只写一次 `{prompt, completion}`；`render_prompt` 用 `"\n\n"` 拼接，所有模型走同一代码路径，方差只来自模型 |
| 8 | post-process 确定且无状态 | 在生成之后、metric 之前执行；`extract_letter / extract_code_block / extract_first_line` 等每条规则只有一种行为，不允许组合 |
| 9 | 夹具（fixture） | 10 条合法任务（5 类各 2 条）全部通过；10 条坏任务每条触发一个错误，校验器正好返回 10 个错误 |
| 10 | 契约 vs 实现的差距 | 代码只按 category 约束 metric、不约束 post-process；`extract_letter` 并非"第一个 A–E 字符"；嵌入式 few-shot 检测是启发式 |

### 核心技能（能动手做到）

- [ ] 手写一条合法的 `mcq` / `code_exec` / `summary` 任务记录，并说出每个字段会被哪条规则检查
- [ ] 给定一条坏记录，按校验顺序（非对象 → 缺字段 → 未知字段 → 类型/取值 → 组合 → 嵌入式 few-shot → 重复 ID）预测校验器报出的**唯一**错误
- [ ] 手算 `render_prompt` 的输出字符串（含分隔符与长度）
- [ ] 预测 `extract_letter`、`extract_code_block` 在各种模型输出上的结果，并指出其误判场景
- [ ] 为 spec 增加一条新约束（如 category–post_process 合法表）并让夹具与测试保持通过
- [ ] 用 `python3 -m pytest -q` 运行 23 个测试，并说出每组测试锁定的契约

---

## 二、基础自测（选择题）

**Q1.** 按本节代码，下列哪个字段是**可选**的？

- A. `few_shot_examples`
- B. `post_process`
- C. `metric_name`
- D. `targets`

**Q2.** 对下面这条记录调用 `validate_task`，结果是：

```json
{"task_id": "m1", "category": "mcq", "prompt": "Pick one.\nA) x\nB) y\nAnswer:",
 "targets": ["B"], "metric_name": "accuracy", "post_process": "none"}
```

- A. `illegal_pair`：mcq 只能用 `exact_match`
- B. `bad_value`：mcq 必须用 `extract_letter`
- C. `embedded_few_shot`：prompt 里有选项列表
- D. 返回空列表，记录合法

**Q3.** `post_process("A good choice is C", "extract_letter")` 的返回值是：

- A. `"C"`
- B. `"A"`
- C. `""`
- D. `"G"`

**Q4.** 一条记录既缺少 `task_id`，又多了一个未知字段 `"rogue": true`。`validate_task` 返回：

- A. 两个错误：`missing_required` 和 `unknown_field`
- B. 一个错误：`unknown_field`
- C. 一个错误：`missing_required`（字段 `task_id`）
- D. 一个错误：`bad_json`

**Q5.** 夹具 `arith_001` 的 prompt 是 `"Compute the result.\nQuestion: 17 + 24\nAnswer:"`，few-shot 为 `{"prompt": "Question: 2 + 2\nAnswer:", "completion": "4"}`。`render_prompt` 的结果是：

- A. `"Question: 2 + 2\nAnswer: 4\n\nCompute the result.\nQuestion: 17 + 24\nAnswer:"`
- B. `"Question: 2 + 2\nAnswer:\n4\n\nCompute the result.\nQuestion: 17 + 24\nAnswer:"`
- C. `"Compute the result.\nQuestion: 17 + 24\nAnswer:\n\nQuestion: 2 + 2\nAnswer: 4"`
- D. `"Question: 2 + 2\nAnswer: 4\nCompute the result.\nQuestion: 17 + 24\nAnswer:"`

**Q6.** 一个 JSONL 文件里有两条**完全相同**且各自合法的记录（`task_id` 相同）。`validate_file` 的结果是：

- A. 两条都被拒绝
- B. 两条都通过
- C. `validate_task` 在第二条上报 `duplicate_task_id`
- D. 第一条通过；第二条由 `validate_file` 记一个 `duplicate_task_id` 错误

**Q7.** 以下 prompt（记录中都**没有** `few_shot_examples`，其他字段合法）哪一条会被判为 `embedded_few_shot`？

- A. `"Compute.\nQuestion: 1+1\nAnswer:"`
- B. `"Translate: hello"`
- C. `"Read the FAQ: shipping.\nQ: how long?\nA:"`
- D. `"Example: 2+2=4\nNow: 3+3="`

**Q8.** 讲义坚持把 few-shot 示例放进任务记录、由 runner 统一渲染，而不是让作者直接写进 prompt 或让每个模型适配器自己拼。主要目的是：

- A. 节省磁盘空间
- B. 让所有模型看到逐字相同的 prompt，分数差异只来自模型本身
- C. few-shot 只在微调时使用，评估时会被丢弃
- D. 让校验器可以跳过 prompt 字段的检查

---

## 三、动手 / 代码题

**Q9.** 讲义说："The category constrains which metric **and post-process pair** is legal." 但代码只有：

```python
LEGAL_CATEGORY_METRIC = {
    "arithmetic": {"exact_match", "f1"},
    "mcq": {"exact_match", "accuracy"},
    "code_exec": {"code_exec"},
    "classification": {"exact_match", "accuracy", "f1"},
    "summary": {"exact_match", "f1", "bleu_4", "rouge_l"},
}
```

1. 举出两条"按讲义应当非法、但当前代码判为合法"的记录。
2. 增加一张 `LEGAL_CATEGORY_POST_PROCESS` 表并接入 `_check_category_metric`，要求 10 条合法夹具仍全部通过。
3. 这个修改会不会让现有 23 个测试中的某个失败？

**Q10.** `extract_letter` 的实现是：

```python
LETTER_RE = re.compile(r"(?:^|[^A-Za-z])([A-E])(?:[^A-Za-z]|$)")
LETTER_FALLBACK_RE = re.compile(r"[A-E]")
...
    if rule == "extract_letter":
        m = LETTER_RE.search(text)
        if m:
            return m.group(1)
        m2 = LETTER_FALLBACK_RE.search(text)
        return m2.group(0) if m2 else ""
```

1. 预测以下输入的输出：`"Answer: C is correct"`、`"The answer is (b)."`、`"ABCD"`、`"I pick option e"`、`"Answer:D"`。
2. 讲义原文是"returns the first character that matches `[A-E]`"。按这句话字面实现，第一个输入会得到什么？代码为什么要多写一层？
3. 写一个更稳健的版本：优先识别 "answer/option/choice + 字母" 的显式表达，大小写不敏感；否则取**最后一个**独立大写字母。

**Q11.** 讲义说坏夹具 `tasks_bad.jsonl` "trips every rule"。

1. 列出校验器中**没有**被这 10 条坏记录触发的规则（至少 4 条）。
2. 往一个 JSONL 文件里依次写入：两条相同的合法记录（`task_id="dup"`）、一条 prompt 里有两个 `Question:` 的记录、一条 `targets=["b"]` 的 mcq 记录、一条 9 个 few-shot 的记录，最后一行写 `{not json`。预测 `validate_file` 返回的 `len(validated)` 以及每个错误的 `(行号, rule, field)`。

**Q12.** 阅读嵌入式 few-shot 检测：

```python
def _embedded_few_shot(prompt: str) -> bool:
    lowered = prompt.lower()
    markers = ("question:", "q:", "example:")
    hits = sum(lowered.count(m) for m in markers)
    return hits > 1
...
    if _embedded_few_shot(record["prompt"]) and not record.get("few_shot_examples"):
        errors.append(...)
```

1. 指出一个**误报**（正常 prompt 被拒）和一个**漏报**（明显内嵌了 few-shot 却通过）的例子。
2. 讲义说校验器"rejects records that already contain a few-shot block in the prompt body"。代码中 `and not record.get("few_shot_examples")` 这个条件和讲义是否一致？会造成什么后果？
3. 如果你要把它改得更可靠，会怎么做？

---

## 四、面试高频题

**Q13.**（基础必考）为什么一个评估 harness 要先"冻结"任务格式、写严格校验器，而不是直接开始写打分函数？如果不这么做，半年后会出现什么问题？

**Q14.**（原理深挖）post-process（答案抽取）为什么必须是任务定义的一部分、而且必须确定、无状态？举例说明抽取规则如何直接改变模型的分数。

**Q15.**（工程实践）团队想新增一个 `translation` 类别。按讲义"像数据库迁移一样对待 spec"的思路，你会怎么落地这次变更？

**Q16.**（场景设计）上百名标注者往一个 10 万行的 `tasks.jsonl` 里贡献任务。请设计从提交到进入 eval 的校验流程（fail-fast 还是收集全部错误？在 CI 的哪一步拦截？错误报告长什么样？）。

**Q17.**（追问型）"校验器全部通过"是否意味着这批任务就是好的评估数据？还有哪些问题是 schema 校验发现不了的？

---

## 五、参考答案与解析

### Q1 — 答案：A

`REQUIRED_FIELDS = ("task_id", "category", "prompt", "targets", "metric_name", "post_process")`，`OPTIONAL_FIELDS = ("few_shot_examples", "metadata")`。B/C/D 都是必填字段，缺任何一个都会得到 `missing_required`（测试 `test_missing_required_fields` 逐个删除这 6 个字段验证过）。

### Q2 — 答案：D

已实际运行验证：返回 `[]`。原因有二：

- `LEGAL_CATEGORY_METRIC["mcq"] = {"exact_match", "accuracy"}`，所以 `accuracy` 合法——A 错。讲义写的是 "a `mcq` task must use `metric_name = exact_match`"，代码比讲义宽松。
- 代码**完全没有** category 与 post_process 的约束，`mcq + none` 能通过——B 是讲义的意图，但不是代码的行为（见 Q9）。
- C 错：选项列表 `A) x` 不是 few-shot 标记（标记只有 `question:`、`q:`、`example:`）。

### Q3 — 答案：B

`LETTER_RE` 要求字母两侧都不是英文字母。开头的 `A` 前面是字符串开头、后面是空格，满足条件，于是被当成答案——尽管这里的 "A" 只是不定冠词。A 是我们"希望"的结果；C 错，有匹配；D 不在 `[A-E]` 范围内。这是 `extract_letter` 最典型的误判：模型用 "A ..." 开头的英文句子作答时，会被稳定地判成选 A。

### Q4 — 答案：C

`validate_task` 的检查顺序是：非对象 → `_check_required` → `_check_unknown_fields` → `_check_types` → `_check_category_metric` → 嵌入式 few-shot；**每一步一旦出错就 `return errors`**。缺字段检查在前，所以只报 `missing_required`，`field="task_id"`，且 `task_id` 显示为 `"?"`。这也解释了为什么 10 条坏夹具正好得到 10 个错误：每条记录最多一个错误。

### Q5 — 答案：A

```python
for ex in task.few_shot_examples:
    parts.append(f"{ex['prompt']} {ex['completion']}")
parts.append(task.prompt)
return "\n\n".join(parts)
```

示例 prompt 与 completion 之间是**一个空格**（B 错），示例在前、正题在后（C 错），块之间是**空行** `"\n\n"`（D 错）。实际运行 demo 打印 `sample render len=72`，正是 A 这个字符串的长度。

### Q6 — 答案：D

重复检查不在 `validate_task` 里（它只看单条记录，C 错），而在 `validate_file` 里：先 `validate_task` 通过，再查 `seen_ids`。第一条加入集合并通过，第二条记 `duplicate_task_id`。测试 `test_duplicate_task_id` 断言 `len(tasks) == 1` 且 `len(errors) == 1`。

### Q7 — 答案：C

实际运行结果：只有 C 返回 `['embedded_few_shot']`。小写后为 `"read the faq: shipping.\nq: how long?\na:"`，`count("q:")` 同时数到了 **`faq:` 末尾的 `q:`** 和真正的 `q:`，共 2 次，`hits > 1`。这是子串计数的**误报**：prompt 里根本没有 few-shot。A、D 各只有 1 个标记；B 没有标记。

### Q8 — 答案：B

讲义："The same code path runs for every model, so the only source of variance is the model itself. Authors write examples once, not once per provider." A、D 与目的无关；C 错，few-shot 正是评估 prompt 的一部分。

### Q9 — 参考答案

1. 例子（已运行验证均返回 `[]`）：
   - `{"category": "mcq", "metric_name": "accuracy", "post_process": "none", "targets": ["A"], ...}`：模型输出 "The answer is A." 原样进入 exact_match，永远判错。
   - `{"category": "code_exec", "metric_name": "code_exec", "post_process": "lower", ...}`：代码被整体小写，`True/False/None` 变成 `true/false/none`，执行必然报错。
2. 参考实现（已运行：10 条合法夹具错误数为 0；`mcq + none` 被拒）：

```python
LEGAL_CATEGORY_POST_PROCESS = {
    "arithmetic": {"strip_whitespace", "extract_first_line"},
    "mcq": {"extract_letter"},
    "code_exec": {"extract_code_block"},
    "classification": {"lower", "strip_whitespace", "extract_first_line"},
    "summary": {"extract_first_line", "strip_whitespace", "none"},
}

def _check_category_metric(record):
    cat, metric = record["category"], record["metric_name"]
    if metric not in LEGAL_CATEGORY_METRIC[cat]:
        return ("illegal_pair", "metric_name", f"{metric} not allowed for category {cat}")
    pp = record["post_process"]
    if pp not in LEGAL_CATEGORY_POST_PROCESS[cat]:
        return ("illegal_pair", "post_process", f"{pp} not allowed for category {cat}")
    if cat == "mcq":
        ...  # 原有的单字母 target 检查
    return None
```

3. 不会。我们在临时副本上打了这个补丁并实际运行：23 个测试全部通过，demo 仍是 `good 10/0、bad 0/10`。原因：测试里的 `good_record()` 是 `arithmetic + strip_whitespace`，mcq 用例都配 `extract_letter`，都在表内；10 条坏夹具在更早的检查（缺字段、未知字段、类型等）就已失败，错误数不变。要点是：**加约束前先跑一遍全部夹具和测试**，确认"收紧"不会误伤合法数据；再补一个 "`mcq + none` 必须失败" 的新测试把这条规则钉住。

### Q10 — 参考答案

1. 实际运行结果：

| 输入 | 输出 | 原因 |
|------|------|------|
| `"Answer: C is correct"` | `"C"` | `Answer` 的 `A` 后面紧跟字母 `n`，不算独立字母；`C` 两侧是空格 |
| `"The answer is (b)."` | `""` | 只认大写 `A–E`，小写 `b` 两个正则都匹配不到 |
| `"ABCD"` | `"A"` | 没有独立字母，走 fallback，取第一个 `[A-E]` |
| `"I pick option e"` | `""` | 同样是小写问题 |
| `"Answer:D"` | `"D"` | `:` 不是字母，`D` 在末尾 |

2. 按字面"第一个匹配 `[A-E]` 的字符"实现，`"Answer: C is correct"` 会返回 `"A"`（来自单词 Answer）。代码先要求"独立字母"，正是为了绕开单词里的大写字母；本节 `quiz.json` 和测试 `test_extract_letter` 期望的都是 `"C"`，说明代码行为才是真正的契约，讲义描述过于简化。
3. 参考实现（已运行验证）：

```python
EXPLICIT_RE = re.compile(r"(?i)\b(?:answer|option|choice)\s*(?:is|:)?\s*\(?([A-E])\)?(?![A-Za-z])")
STANDALONE_RE = re.compile(r"(?<![A-Za-z])([A-E])(?![A-Za-z])")

def extract_letter_v2(text: str) -> str:
    m = EXPLICIT_RE.search(text)
    if m:
        return m.group(1).upper()
    hits = STANDALONE_RE.findall(text)
    return hits[-1] if hits else ""
```

结果：`"A good choice is C"` → `C`（原版 `A`）；`"The answer is (b)."` → `B`；`"I pick option e"` → `E`；`"ABCD"` → `""`（原版 `A`，不再"猜"）。注意：改抽取规则等于改 benchmark，必须升级 spec 版本并重跑所有模型，不能新旧分数混比。

### Q11 — 参考答案

1. 10 条坏记录覆盖的是：缺必填、`task_id` 字符、未知 category、非法组合、空 targets、尾随空白、未知字段、未知 metric、mcq 多 target、未知 post_process。**未覆盖**：`bad_json`、`duplicate_task_id`、`embedded_few_shot`、few-shot 超过 8 条、few-shot 条目缺 `prompt/completion` 或类型错、mcq target 不是 `A–E` 字母、targets 元素非字符串、`metadata` 非对象、`task_id` 非字符串、记录本身不是对象。其中一部分被单元测试补上了（`bad_json`、重复 ID、few-shot 上限、mcq 字母），但讲义"trips every rule"的说法并不成立。
2. 实际运行结果：`len(validated) == 1`，错误为

```text
(2, 'duplicate_task_id', 'task_id')
(3, 'embedded_few_shot', 'prompt')
(4, 'bad_value', 'targets')            # mcq target must be a letter A-E
(5, 'bad_value', 'few_shot_examples')  # max 8 entries
(6, 'bad_json', '_line')
```

注意第 1 行通过；行号从 1 开始（`enumerate(fp, start=1)`），空行会被跳过但仍占行号。

### Q12 — 参考答案

1. 误报：`"Read the FAQ: shipping.\nQ: how long?\nA:"`（`faq:` 被当成 `q:`，见 Q7）；同理 `"Iraq: ..."` 也会命中 `q:`。漏报：`"Translate.\nen: cat\nfr: chat\nen: dog\nfr:"`、`"Input: 2+2\nOutput: 4\nInput: 3+3\nOutput:"` 这类不用 `question/q/example` 字样的内嵌示例完全检测不到。
2. 不一致。讲义说"拒绝 prompt 中已含 few-shot 块的记录"；代码只在**没有** `few_shot_examples` 时才拒绝。后果：作者只要随便填一条 `few_shot_examples`，prompt 里再内嵌多少示例都能通过，最终渲染出"双份 few-shot"，而且不同任务的示例数量不再受 8 条上限约束。
3. 改进方向：
   - 用**行首**正则代替子串计数，如 `re.findall(r"(?im)^(?:question|q|example)\s*:", prompt)`，避免 `faq:` 之类误报；
   - 无论有没有 `few_shot_examples`，只要命中都拒绝（与讲义一致），或至少把它降级为 warning 并输出到报告；
   - 把检测结果放进 CI 报告，由人复核，而不是假装启发式是精确的。

### Q13 — 参考回答要点

- **问题根源**：讲义："A research codebase will accumulate eval scripts faster than it accumulates tests." 每个 notebook 一种 JSON 形状、每个 metric 实现两遍，结果是同名 benchmark 的数字不可比。
- **冻结 spec 的收益**：
  - 每个字段只有一个"所有者"：runner 读任务，metric 读 targets，post-process 规范化生成——讲义："No field is mutable mid-pipeline."
  - 封闭词表让下游可以按 `metric_name` 分派（71–73 课），不需要猜。
  - 校验器在任务进入 runner 前拒绝坏数据，坏行只废一条，不拖垮整次 run。
- **不这么做的后果**：字段拼写不一（`target` / `targets`）、metric 名混乱、抽取规则因人而异、同一个任务在不同模型上 prompt 不同，最终排行榜上的差异分不清是模型差还是管线差。
- 加分点：类比"数据库 schema + migration"；schema 里拒绝未知字段是为了防止"悄悄扩展"让旧代码默默忽略新语义。

### Q14 — 参考回答要点

- 抽取规则决定"模型输出的哪一部分被拿去比较"。同一段输出，用 `none` 和 `extract_letter` 打分可以从 0 变成 1。
- **必须属于任务**：如果由 runner 或各个模型适配器自行决定，不同模型就是在不同规则下被评分，排名失去意义；讲义："Each rule has a single deterministic behaviour. The validator forbids combining rules."
- **必须确定、无状态**：同样的输入永远得到同样的输出，才能复现、才能缓存、才能把分数差异归因到模型。
- 例子（本节代码实测）：`extract_letter("A good choice is C") == "A"`、`extract_letter("The answer is (b).") == ""`——一个习惯用小写或用 "A ..." 开头作答的模型会被系统性低估；`extract_code_block` 在 ` ```py ` 后有空格时匹配失败、原样返回整段文字，代码执行就会报语法错误。
- 加分点：业界很多"同一模型在不同论文上分数不同"的争议，根源就是答案抽取规则不同；抽取规则的变更应当视为 benchmark 版本变更。

### Q15 — 参考回答要点

- 讲义原则："refuse to add a category without also adding a metric, a post-process rule, and at least one fixture task. Treat the spec like a database migration."
- 落地步骤：
  1. 写变更说明（RFC）：新 category 的用途、合法 metric（如 `bleu_4`/`f1`）、合法 post-process；
  2. 修改 `CATEGORIES`、`LEGAL_CATEGORY_METRIC`（以及建议新增的 category–post_process 表）；
  3. 如需新 metric（如 chrF），同步改 `METRICS` 和 71 课的 `score` 分派，否则校验通过但打分时抛 `ValueError`；
  4. 至少加 1–2 条合法夹具 + 若干坏夹具，补单元测试；
  5. 给 spec 打版本号（如在 `metadata` 或文件头记录 `spec_version`），报告里写明用的是哪个版本；
  6. 代码评审 + CI 通过后才合并；旧结果不与新版本结果直接混比。
- 常见误区：只在 `CATEGORIES` 加一个字符串就提交——校验器放行，但下游 metric 和抽取规则没有对应实现。

### Q16 — 参考回答要点

- **收集全部错误，而不是 fail-fast**：本节 `validate_file` 对 JSON 解析错误和规则违反都 `continue`，把所有错误收进列表，一次性反馈给作者；但**单条记录内**只报第一个错误（可改为收集全部，方便作者一次改完）。
- **拦截位置**：
  - pre-commit / PR CI：对改动的 JSONL 运行校验器，错误列表非空则 PR 失败；
  - runner 启动时再校验一次（讲义：错误列表非空时拒绝启动，除非显式 `--allow-bad-tasks`——注意本节代码并未实现这个参数）。
- **错误报告**：`line_number / task_id / rule / field / detail`（即 `ValidationError.to_dict()`），按 rule 聚合计数，便于发现系统性问题（比如某个标注者所有 prompt 都带尾随空格）。
- **跨文件约束**：`task_id` 全局唯一要跨分片检查；大文件用流式逐行读取（本节已逐行读）。
- 加分点：给每条错误配修复建议；对启发式规则（嵌入式 few-shot）只发 warning 并人工复核，避免误报阻塞合并。

### Q17 — 参考回答要点

- 不意味着。schema 校验只保证"形状对"，不保证"内容对"。发现不了的问题包括：
  - **答案错误**：`targets` 写错（如 144 / 12 写成 11）；
  - **答案不完整**：exact_match 只给了 `"41"`，模型回答 `"41."` 或 `"forty-one"` 都判错——需要多 target 或更合适的 metric；
  - **题目歧义**、多个正确选项；
  - **数据污染**：任务出现在模型训练数据中；
  - **难度/分布失衡**：所有任务都太简单，区分不出模型；
  - **抽取规则与 prompt 不匹配**：prompt 要求"只输出一个代码块"，模型却习惯加解释，抽取规则是否稳健；
  - **启发式规则的漏报**（Q12）。
- 对策：用参考模型/人工抽检跑一遍、对每个任务看多模型的答对率分布、对 0% 或 100% 的任务重点复查、为 targets 加多种等价写法。
- 加分点：把"任务质量"本身也当作需要评估的对象（item analysis），例如找出所有模型都答错的题，常常是标注错误。

---

## 六、关联知识点

### 前置知识
- [阶段 19 · 27 使用固定测试任务的评估 Harness](../../27-eval-harness-fixture-tasks/docs/zh.md)：用固定夹具任务驱动 harness 的思路，本节把它规范化为 JSONL 契约。
- [阶段 11 · 03 Structured Outputs：JSON、Schema 校验与约束解码](../../../11-llm-engineering/03-structured-outputs/docs/zh.md)：JSON schema 与校验的通用做法。
- [阶段 19 · 21 带 Schema 校验的工具注册表](../../21-tool-registry-schema-validation/docs/zh.md)：同样是"先定 schema、再严格拒绝"的设计。
- [阶段 11 · 02 Few-Shot, Chain-of-Thought, Tree-of-Thought](../../../11-llm-engineering/02-few-shot-cot/docs/zh.md)：few-shot prompt 的构造方式。
- [阶段 10 · 10 Evaluation：基准、Evals 与 LM Harness](../../../10-llms-from-scratch/10-evaluation/docs/zh.md)：lm-eval 风格 harness 的整体图景。

### 本节被哪些后续内容用到
- [阶段 19 · 71 经典评估指标](../../71-classical-metrics/docs/zh.md)：按 `metric_name` 分派 exact_match / F1 / BLEU-4 / ROUGE-L / accuracy。
- [阶段 19 · 72 代码执行评估指标](../../72-code-exec-metric/docs/zh.md)：`code_exec` 任务的 targets（断言字符串）与代码块抽取。
- [阶段 19 · 73 Perplexity 与 Calibration（困惑度与校准）](../../73-perplexity-calibration/docs/zh.md)：在同一套任务上汇总置信度与正确性。
- [阶段 19 · 74 排行榜汇总](../../74-leaderboard-aggregation/docs/zh.md)：消费每个 `(model, task)` 的分数。
- [阶段 19 · 75 端到端评估执行器](../../75-end-to-end-eval-runner/docs/zh.md)：直接导入本节的 `TaskSpec`、`render_prompt`、`post_process`。

### 延伸关键词
`JSONL` · `JSON Schema` · `closed vocabulary` · `answer extraction` · `few-shot rendering` · `BIG-bench` · `HELM` · `lm-evaluation-harness` · `schema migration` · `spec versioning` · `item analysis`
