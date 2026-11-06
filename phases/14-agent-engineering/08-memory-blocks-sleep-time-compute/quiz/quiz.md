# 测验 · 记忆块与休眠时计算（Memory Blocks and Sleep-Time Compute）

> **阶段 14 · Agent 工程 · 第 08 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

> 说明：本节中文讲义为机器翻译，"Human block / Persona block"被译成"人类街区 / 人际关系区块"等，读不通时请以 [English](../docs/en.md) 为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | MemGPT 之后的三个生产问题 | Latency（记忆操作挡在关键路径上）、Memory rot（矛盾和陈旧事实堆积）、Structure loss（扁平存储表达不了"哪些段落总在 prompt 里"） |
| 2 | Letta 三层 | Core（始终可见，在 prompt 内，由 agent 工具调用 + sleep-time 改写）、Recall（对话历史，自动逐轮记录）、Archival（任意事实，向量 + KV + 图，由工具调用 + sleep-time 摄入） |
| 3 | Memory block | core 层中有类型、持久、可由 LLM 编辑的段落；字段 `id`、`label`、`value`、`limit`（字符上限）、`description`（告诉模型何时编辑它） |
| 4 | Human / Persona / 自定义块 | MemGPT 原论文定义 Human（用户事实）与 Persona（agent 自我设定）两个块；Letta 推广到 Task、Project、Safety 等任意块 |
| 5 | Block 工具 | `block_append`、`block_replace`、`block_read`、`block_summarize`（块接近上限时压缩） |
| 6 | Sleep-time compute | 第二个 agent 在后台、关键路径之外整理记忆：处理对话记录、写 `learned_context`、合并或作废 archival 记录 |
| 7 | Sleep-time 的三个性质 | 无延迟成本；可以用更强、更慢、更贵的模型；在用户不等待时自然地去重、摘要、作废矛盾事实 |
| 8 | Native reasoning | 讲义：Letta V1（`letta_v1_agent`，2026）弃用 `send_message`/heartbeat 和行内 `Thought:`，改用 provider 的独立推理通道；控制循环仍是 ReAct |
| 9 | 三种故障 | Block bloat（无限 append 撞上限）、Silent drift（sleep-time 改了块而主 agent 不知道 → 版本化 + 在 trace 中展示 diff）、Poisoned consolidation（把攻击者可达的内容整理进 core） |
| 10 | 本节代码的落差 | 演示中 sleep pass **没有**压缩任何块（都没到 80% 阈值）；`_summarize` 会把无句号的长块压成 `"."`；human 块中的 `city=Berlin` 矛盾没被处理；没有 Recall 层 |

### 核心技能（能动手做到）

- [ ] 说出 core / recall / archival 三层分别"存什么、谁来写、何时可见"
- [ ] 实现带 `limit`、`version`、`history` 的 `Block`，并算出任意上限下 `near_limit` 的触发长度
- [ ] 把"摘要 / 去重 / 作废矛盾"从主 agent 的关键路径移到 sleep-time pass
- [ ] 读出本节 `_summarize` 的三个缺陷（空选择返回 `"."`、保留旧句丢新句、按 `.` 切分误伤版本号）并修复
- [ ] 用版本号做乐观并发控制，避免 sleep-time 改写覆盖主 agent 的新写入（lost update）
- [ ] 为 Persona / Safety 块设计"二次审核后再提交"的写入门

---

## 二、基础自测（选择题）

**Q1.** 在 Letta 的三层记忆中，Recall 层由谁写入？

- A. 只能由 sleep-time agent 写入
- B. 自动的逐轮对话记录（automatic turn logging）
- C. 只能由用户手动写入
- D. 由向量数据库的定时任务写入

**Q2.** 讲义说 sleep-time agent 可以使用比主 agent 更强、更慢、更贵的模型。根本原因是：

- A. sleep-time agent 处理的数据量更小
- B. 更强的模型更不容易被注入攻击
- C. Letta 平台强制要求
- D. 它运行在关键路径之外，用户不等待它的结果，没有延迟约束

**Q3.** 运行 `code/main.py`，sleep-time pass 对三个块（human `limit=180`、persona `limit=160`、task `limit=220`）做了什么？

- A. 什么也没压缩：human 72/180、task 119/220 都没达到 80% 阈值（144、176），persona 为空；"consolidated" 前后的块内容完全一样
- B. 把 human 块压缩成一半长度
- C. 把 task 块压缩成 `limit // 2 = 110` 字符以内
- D. 删除了空的 persona 块

**Q4.** `Block.near_limit(threshold=0.8)` 的实现是 `len(self.value) >= int(self.limit * threshold)`。对 `limit=220` 的 task 块，`value` 至少多长时返回 `True`？

- A. 110
- B. 200
- C. 176
- D. 220

**Q5.** 讲义中的 silent drift 指什么？推荐的修复是？

- A. 模型权重随时间漂移；定期重新微调
- B. 向量 embedding 随模型升级而漂移；重建索引
- C. 用户偏好随时间变化；定期询问用户
- D. sleep-time agent 改写了某个块，主 agent 却从未察觉；给块加版本号并在 trace 中展示 diff

**Q6.** 按讲义，Letta V1 用什么取代了 `send_message`/heartbeat 模式和行内 `Thought:` token？

- A. Provider 层的 native reasoning：推理输出走独立通道并在轮次间传递，控制循环仍是 ReAct
- B. 一个专门的 planner 模型
- C. 把思考过程写进 Persona 块
- D. 完全取消推理，只输出工具调用

**Q7.** human 块的 value 为一串没有句号的 `key=value`，长度 183（limit 180，已超过 144 的阈值）。sleep-time pass 调用 `_summarize(value, 90)` 后，该块的新值是：

- A. 前 90 个字符
- B. 只有一个字符 `"."`
- C. 原值不变
- D. 抛出 `IndexError`

**Q8.** 配套 skill 文件要求遇到矛盾时"Invalidate rather than delete"。主要原因是：

- A. 删除操作在向量数据库中更慢
- B. 作废后的记录仍会参与检索，召回率更高
- C. 保留历史以便审计和排查（"为什么 agent 以为 X"），在合规、医疗、法律等需要历史主张的领域尤其重要
- D. 删除会导致记录 ID 重复

---

## 三、动手 / 代码题

**Q9.** 阅读 `_summarize`：

```python
def _summarize(text: str, target_len: int) -> str:
    sentences = [s.strip() for s in text.split(".") if s.strip()]
    if not sentences:
        return text[:target_len]
    picked: list[str] = []
    total = 0
    for sentence in sentences:
        if total + len(sentence) + 1 > target_len:
            break
        picked.append(sentence)
        total += len(sentence) + 2
    return ". ".join(picked) + "."
```

1. 对下面三个输入，分别写出返回值：
   - `("Ava ships agents. She lives in Berlin. She moved to Lisbon in May. She prefers concise writing with citations.", 60)`
   - `("uses v1.2 of the SDK. e.g. letta", 100)`
   - 一个 183 字符、不含句号的 `key=value` 串，`target_len=90`
2. 指出这个函数的三个缺陷。
3. 对 human 块这种 `key=value` 结构，写一个"后写覆盖先写"的合并函数，让 `"name=ava role=ships_agents city=Berlin city=Lisbon (updated from Berlin)"` 变成 `"name=ava role=ships_agents city=Lisbon"`。

**Q10.** 讲义的 "Block bloat" 建议"Wire a block summarizer before the write that pushes over the cap"，而配套 skill 文件的 hard reject 是"Any memory op that runs synchronously during a user-facing turn except a direct lookup. Summarization ... belong to the sleep-time pass."

1. 本节 `Block.append` 是否检查 `limit`？给一个 `limit=20` 的块 append 50 个字符会怎样？
2. 这两条建议看起来矛盾，你如何设计 append 的行为，同时满足"不超限"和"不在关键路径上做摘要"？

**Q11.** `SleepTimeAgent.run` 的作废逻辑：

```python
        for claim, reason in contradictions:
            for record in self.archival.all_records():
                if record.valid and claim.lower() in record.text.lower():
                    self.archival.invalidate(record.rid)
```

1. 对 claim `"ava lives in Berlin"`，下面四条记录哪些会被作废？`"ava lives in Berlin - old address"`、`"Java lives in Berlin servers"`、`"nova lives in berlin"`、`"ava lives in Berlingen"`。
2. 这段逻辑还有什么结构性问题（提示：`contradictions` 从哪里来）？
3. 讲义练习 2：在 sleep pass 中实现 archival 去重——两条记录 token 重叠 > 90% 时合并为一条。写出实现。

**Q12.** 真实的 sleep-time agent 与主 agent **并发**运行。考虑以下时序（用本节 `Block` 实现）：

```python
h.append("name=ava city=Berlin")                    # v1
snapshot = h.value                                   # sleep agent 读取 v1，开始慢慢整理
h.append("pet=cat")                                  # 主 agent 在此期间写入 v2
h.rewrite(snapshot.replace("city=Berlin", "city=Lisbon"))   # sleep agent 提交 v3
```

1. 最终 `h.value` 是什么？丢了什么？
2. 用 `version` 字段实现乐观并发控制（compare-and-swap），并在每次提交时记录 diff（讲义练习 3）。
3. 讲义练习 4：sleep-time agent 改 Persona / Safety 块时要求第二个 agent 审核。说明这道门应放在哪里、审核什么。

---

## 四、面试高频题

**Q13.**（基础必考）Letta（MemGPT 的后继）把记忆分成哪三层？各自存什么、谁写、什么时候对模型可见？为什么要从 MemGPT 的两层拆成三层？

**Q14.**（原理深挖）什么是 sleep-time compute？它解决了什么问题，又引入了什么新问题？

**Q15.**（工程实践）你要上线一个带 memory block 的助手。块的 `limit` 怎么定？接近上限时怎么办？如何让运维能回答"agent 为什么忘了 X"？

**Q16.**（场景设计）用户在第 3 轮说"我搬到里斯本了"。请描述从主 agent 写入，到 sleep-time 整理，再到下一次会话回答"我住哪"的完整数据流，并指出本节代码在这条链路上哪里做得不够。

**Q17.**（追问型）你说 sleep-time agent 可以用更强的模型去整理记忆，那如果它整理的对话里包含用户粘贴的恶意网页内容，会发生什么？怎么防？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义三层表格中 Recall 的 "Written by" 一列是 "Automatic turn logging"：每一轮对话自动记录，尾部被淘汰后仍可检索。A 不对，sleep-time agent 写的是 core（rewrites）与 archival（ingest）；C、D 都不是讲义描述。注意：本节代码**没有实现 Recall 层**，`PrimaryAgent.trace` 只是打印用的列表。

### Q2 — 答案：D

讲义："Stronger model allowed. The sleep-time agent can be a more expensive, slower model because it is not latency-constrained." 主 agent 的每一毫秒都计入用户等待时间，sleep-time agent 的不计入。A 不一定成立（它往往处理整段对话记录，数据量更大）；B 恰好相反，讲义专门提醒 "Poisoned consolidation"；C 不是讲义说法。

### Q3 — 答案：A

实际运行：sleep-time trace 只有一行 `invalidate a002 ...`，没有任何 `consolidate`；"blocks after sleep-time (consolidated)" 与压缩前完全相同。阈值为 `int(180 × 0.8) = 144`、`int(220 × 0.8) = 176`，而 human 只有 72、task 只有 119。讲义 Build It 说 trace 会展示"a sleep-time pass that summarizes a block and invalidates a stale fact"，实际只演示了后半句。B、C 是"如果到了阈值"会发生的事；D 代码中没有删除块的逻辑。

### Q4 — 答案：C

`int(220 × 0.8) = int(176.0) = 176`，`len(value) >= 176` 时触发。A 是 `limit // 2`，即 `_summarize` 的目标长度；B 无依据；D 是硬上限本身，而 near_limit 的意义正是在撞上限**之前**提醒。

### Q5 — 答案：D

讲义："Silent drift. Sleep-time agent rewrites a block and the primary agent never notices. Version blocks and surface diffs in the trace." 本节 `Block` 已经有 `version` 和 `history`（保存旧值），但 trace 里只打印版本号，没有展示 diff。A、B、C 都与 sleep-time 改写无关。

### Q6 — 答案：A

讲义："Letta V1 (`letta_v1_agent`, 2026) deprecates `send_message`/heartbeat and inline `Thought:` tokens in favor of native reasoning ... The control loop is still ReAct. The thought trace is structural, not prompt-shaped." OpenAI Responses API、Anthropic 带 extended thinking 的 Messages API 都在独立通道输出推理。B、C、D 都不是讲义描述。

### Q7 — 答案：B

已实际运行验证：块值被改写为 `"."`，trace 显示 `consolidate human: human v5 rewritten (1/180)`。原因：`text.split(".")` 在没有句号时得到只含一个元素的列表（整个 183 字符的串）；第一次循环 `0 + 183 + 1 > 90` 立即 `break`，`picked` 为空；`". ".join([]) + "."` 得到 `"."`。用户的全部事实从 core 中消失（只能从 `history` 里找回）。A 是 `if not sentences` 分支的行为，但这里 `sentences` 非空所以走不到；C、D 不会发生。

### Q8 — 答案：C

skill 文件："Deleting archival records on contradiction. Invalidate so history remains auditable."（hard reject）以及"If the user asks for 'no invalidation, always trust latest write,' refuse for any domain where historical claims matter (compliance, medical, legal)." B 恰好相反——作废的记录应**不再**参与检索（本节用 `valid_records()` 过滤）。A、D 都不是理由。

### Q9 — 参考答案

1. 实际运行结果：
   - 第一个输入 → `'Ava ships agents. She lives in Berlin.'`（"She moved to Lisbon in May" 被丢掉）
   - 第二个输入 → `'uses v1. 2 of the SDK. e. g. letta.'`（版本号和缩写被拆坏）
   - 第三个输入 → `'.'`
2. 三个缺陷：
   - **空选择返回 `"."`**：第一个句子就超过 `target_len` 时 `picked` 为空，函数返回一个句号，整块信息被抹掉。对 human 块这种 `key=value`、没有句号的格式，这是必然触发的。
   - **保留最旧、丢弃最新**：从前往后取句子直到超长，而块是 append 式增长的，最新的更新在末尾。结果是"住在柏林"保留，"搬到里斯本"丢失——"摘要"反而**制造**了陈旧事实，与 sleep-time 消除 memory rot 的目标背道而驰。
   - **按 `.` 切分**：`v1.2`、`e.g.`、小数、URL 都会被拆开，重组时插入多余空格。
   - 另外，它其实不是摘要而是截断；讲义设想的是用（更强的）模型生成摘要。
3. key=value 合并（已运行验证）：

```python
import re
KV = re.compile(r"(\w+)=([^\s(]+)")

def consolidate_kv(text: str) -> str:
    facts = {}
    for k, v in KV.findall(text):
        facts.pop(k, None)          # 先删再插，保证新值排在后面
        facts[k] = v                # 后写覆盖先写
    return " ".join(f"{k}={v}" for k, v in facts.items())

consolidate_kv("name=ava role=ships_agents city=Berlin city=Lisbon (updated from Berlin)")
# -> 'name=ava role=ships_agents city=Lisbon'
```

   对自由文本块，若只能做规则截断，至少要**从最新的句子往回取**，并在一句都放不下时退化为保留末尾 `target_len` 个字符，而不是返回 `"."`；更好的做法是调用 LLM 摘要，并把旧值保存在 `history` 中以便回滚。

### Q10 — 参考答案

1. 不检查。实测 `Block("t", limit=20).append("x" * 50)` 返回 `t v1 (50/20)`，值长度 50，超出上限 2.5 倍。`limit` 只在 `near_limit` 和 `render` 的显示中被用到，是"软"的。
2. 设计思路（两层阈值）：
   - **软阈值（如 80%）**：`near_limit` 为真时，append 照常写入，但把该块放进"待整理队列"，由 sleep-time pass 异步摘要——不阻塞用户。
   - **硬上限**：如果这次写入会让块超过 `limit`，在关键路径上**不做摘要**，而是选择一种廉价、确定性的动作：
     - 拒绝写入并返回结构化错误 observation（如 `error: human block full (178/180); write to archival instead or replace an existing fact`），让模型改用 `block_replace` 或 `archival_insert`；
     - 或把这条内容"溢出"写入 archival，并在块中留一个指针。
   - 这样讲义"在越过上限的写入之前接上摘要器"可以理解为：**摘要器要在块被撑爆之前就已经被（异步）触发**，所以软阈值要低于硬上限、并留出足够余量覆盖两次 sleep pass 之间的写入量——这也是讲义练习 1 问"哪个阈值能同时最小化摘要调用次数与溢出次数"的含义。
   - 实现示意：

```python
def append(self, text: str) -> str:
    new_value = (self.value + " " + text).strip() if self.value else text
    if len(new_value) > self.limit:
        return (f"error: {self.label} would be {len(new_value)}/{self.limit}; "
                f"use block_replace or archival_insert")
    ...  # 正常写入、version += 1、history 记录
    if self.near_limit():
        PENDING_CONSOLIDATION.add(self.label)    # 交给 sleep-time
```

### Q11 — 参考答案

1. 实际运行：第 1、2、4 条被作废，第 3 条保留。
   - `"ava lives in Berlin - old address"`：正确命中；
   - `"Java lives in Berlin servers"`：**误伤**——小写后 `"java lives in berlin"` 包含子串 `"ava lives in berlin"`（`ava` 是 `Java` 的后缀）；
   - `"nova lives in berlin"`：`nova` 以 `ova` 结尾，不含连续的 `ava lives`，不命中；
   - `"ava lives in Berlingen"`：**误伤**——`berlin` 是 `berlingen` 的前缀。

   结论：**子串匹配没有词边界**，会误作废那些"恰好包含目标串"的无关记录；而且由于是精确字面匹配，换一种说法（"ava is based in Berlin"）又完全匹配不到。
2. 结构性问题：`contradictions` 是 `main` 里**手写传入**的——"哪条事实被推翻了"这一最难的判断由调用者完成，sleep-time agent 只是执行字符串匹配。真实系统中应由 sleep-time agent 自己比较新旧事实（例如 human 块中 `city=Lisbon` 与 archival 中"lives in Berlin"）来发现矛盾。此外，`invalidate(rid)` 内部又遍历一遍所有记录，整体是 O(n²)；human 块里 `city=Berlin city=Lisbon` 的矛盾也完全没被处理。
3. 去重 + 带词边界的作废（已运行验证）：

```python
import re

def toks(s):
    return set(re.findall(r"[a-z0-9]+", s.lower()))

def jaccard(a, b):
    A, B = toks(a), toks(b)
    return len(A & B) / len(A | B) if A | B else 1.0

class DedupSleepAgent(SleepTimeAgent):
    def dedup(self, threshold=0.9):
        valid = self.archival.valid_records()
        for i, keep in enumerate(valid):
            if not keep.valid:
                continue
            for dup in valid[i + 1:]:
                if dup.valid and jaccard(keep.text, dup.text) > threshold:
                    self.archival.invalidate(dup.rid)        # 作废而非删除
                    self.trace.append(f"  dedup {dup.rid} -> duplicate of {keep.rid}")

    def invalidate_claim(self, claim, reason):
        pat = re.compile(r"(?<!\w)" + re.escape(claim) + r"(?!\w)", re.I)
        for r in self.archival.valid_records():
            if pat.search(r.text):
                self.archival.invalidate(r.rid)
                self.trace.append(f"  invalidate {r.rid} ({reason})")
```

   实测：`"ava prefers concise, citation-heavy writing over tutorial-style"` 与 `"Ava prefers concise citation-heavy writing over tutorial style."` 去标点后 Jaccard 为 1.0，后者被标记为重复；与 `"ava prefers concise writing"` 的 Jaccard 只有 0.44，不合并。带词边界后，`"Java lives in Berlin servers"`、`"nova lives in berlin"` 都不再被误作废，只有真正的 `"ava lives in Berlin - old address"` 被作废。讲义强调去重"Do it only in the sleep pass, never on the critical path"——O(n²) 的两两比较正是不该放在用户等待路径上的操作。

### Q12 — 参考答案

1. 实测最终 `h.value == "name=ava city=Lisbon"`，`version == 3`。主 agent 在 v2 写入的 `pet=cat` **丢失**了——经典的 lost update。`history` 里还有旧值，但没有人会注意到，这就是讲义说的 silent drift 的一种具体形态。
2. 乐观并发 + diff（已运行验证）：

```python
import difflib

class VBlock(Block):
    def rewrite_if(self, new, expected_version, writer="sleep"):
        if self.version != expected_version:
            return (f"conflict: {self.label} is v{self.version}, "
                    f"expected v{expected_version}; re-read and retry")
        diff = "\n".join(difflib.unified_diff(
            self.value.split(), new.split(), lineterm="", n=0))
        result = self.rewrite(new)
        self.diffs = getattr(self, "diffs", []) + [(self.version, writer, diff)]
        return result
```

   重放上面的时序：sleep agent 拿 v1 提交时得到 `conflict: human is v2, expected v1; re-read and retry`；重读 v2 后提交 `name=ava city=Lisbon pet=cat` 成功，diff 为 `-city=Berlin / +city=Lisbon`，可以直接出现在 trace 中。
3. 审核门：
   - **位置**：在 sleep-time agent 的"提交"步骤，而不是生成步骤——它可以生成任意候选改写，但对 Persona / Safety 块只能提交到"待审"区。
   - **审核内容**：diff 本身（而非全文）；改写是否引入了新的指令或约束放宽（如删除"不得执行转账"）；改写的依据是否来自可信来源（用户直接陈述 vs 网页/工具输出）；是否与 Safety 块的硬约束冲突。
   - **审核者**：第二个 agent（不同 prompt，最好不同模型）或人工；未通过则保持旧版本并记录原因。skill 文件也把"Writing to the Persona or Safety block without a review step"列为 hard reject。

### Q13 — 参考回答要点

- **Core**：始终在 prompt 内，由若干 memory block 组成（Human、Persona、Task……）；agent 通过工具编辑，sleep-time agent 也可改写。
- **Recall**：完整对话历史，每轮自动记录；超出窗口的尾部被淘汰出 prompt，但可以检索。
- **Archival**：任意长期事实，存在向量 / KV / 图存储中；agent 工具写入，sleep-time 摄入、合并、作废。
- **为什么拆三层**：讲义："The split cleans up MemGPT's two-tier overloading." MemGPT 的 external context 同时承担"历史对话"和"长期事实"两种职责，二者的写入方式（自动 vs 有意）、检索方式（按时间 vs 按语义）、生命周期都不同；拆开后各自可以独立优化。
- 加分点：block 有 `limit` 和 `description`，把"prompt 里每段放什么、最多多长、什么时候改"变成显式的结构，解决了讲义说的 Structure loss。

### Q14 — 参考回答要点

- **定义**：在主 agent 空闲时（或与之并行），由第二个 agent 在关键路径外处理记忆：读对话记录和代码库上下文，写 `learned_context` 到共享块，合并或作废 archival 记录。
- **解决的问题**：
  - Latency：摘要、去重、对账不再让用户等待；
  - Memory rot：有一个固定的"整理窗口"处理矛盾与重复；
  - 质量：可以用更强的模型做更细致的整理。
- **新问题**：
  - Silent drift：后台改写了块，主 agent 和运维都不知道（版本化 + diff）；
  - 并发冲突：主 agent 与 sleep agent 同时写同一块导致 lost update（版本号做 CAS，见 Q12）；
  - Poisoned consolidation：把恶意内容整理进 core，影响此后每一轮；
  - 新鲜度：整理是异步的，刚说的事实在下一次 sleep pass 前可能还没反映到块里；
  - 成本：更强的模型、对整段历史的处理都要花钱，需要控制频率（例如按空闲时间或累计写入量触发）。
- 类比：讲义"you do the task, you sleep on it, the long-term memory settles overnight."

### Q15 — 参考回答要点

- **定 limit**：按块的职责定，例如 Human 块放稳定的用户画像（几百字符）、Task 块放当前目标；所有块之和要在上下文预算中留出余量。块越大，每轮 token 成本越高，注意力也越分散。
- **接近上限**：软阈值（如 80%）触发异步整理；硬上限在写入时拒绝并引导模型改用 `replace` 或写 archival（见 Q10）；摘要要"保新弃旧"，避免本节 `_summarize` 的问题。
- **可追溯**：每次写入 `version += 1` 并记录旧值和 diff、写入者（主 agent / sleep agent / 人工）、依据（哪一轮对话或哪条 archival 记录）；暴露 `block_history(label)`（讲义练习 3）；sleep pass 必须有 trace（skill 文件："If the sleep-time agent has no trace output, refuse"）。
- **可观测性**：把每次块操作打成 span（讲义的后续指向 [阶段 14 · 23](../../23-otel-genai-conventions/docs/zh.md)）。
- 常见误区：把 `history` 只存旧值而不存 diff 和写入原因——能回滚但很难回答"为什么"。

### Q16 — 参考回答要点

- **理想链路**：
  1. 第 3 轮，主 agent 快速写入：`block_replace("human", "city=Berlin", "city=Lisbon")`（而非 append），或至少 append 一条带时间的更新；对话本身进入 Recall。
  2. 下一次 sleep pass：比对 Human 块与 archival，发现"lives in Berlin"与新事实冲突，作废旧记录（不删除），合并 Human 块中重复的 `city` 键，记录 diff 与依据（第 3 轮）。
  3. 新会话：Human 块随 core 注入 prompt，模型直接回答"里斯本"，必要时引用依据。
- **本节代码的不足**：
  - 主 agent 用的是 `block_append`，human 块变成 `city=Berlin city=Lisbon (updated from Berlin)`，自相矛盾；
  - sleep pass 只作废了 archival 中的旧记录，**没有修正 human 块**；
  - 矛盾由 `main` 手工传入，而不是 sleep agent 自己发现；
  - 若块到达阈值，`_summarize` 会保留最早的 `city=Berlin` 而丢掉 `city=Lisbon`，或者把整块压成 `"."`；
  - 主 agent 自己还写入了一条"ava lives in Berlin - old address, outdated"到 archival，再由 sleep pass 作废——演示了作废机制，但生产中不该写入已知过时的事实。
  - 没有 Recall 层，无法追溯是哪一轮说的。

### Q17 — 参考回答要点

- **后果**：sleep-time agent 处理的对话记录可能包含用户粘贴的网页、工具返回的外部内容。如果它把其中的"指令"当成事实整理进 core 块（尤其是 Persona / Safety），这些内容将出现在此后**每一轮**的 prompt 中——比单次 prompt injection 影响更大、更持久。讲义："Poisoned consolidation. Sleep-time agent processes attacker-reachable content into core. Lesson 27 applies to the sleep-time surface too."
- **防御**：
  - 把 sleep-time agent 当作**不可信写入者**（讲义练习 4）：对 Persona / Safety 块的改写必须经过审核（见 Q12）；
  - 来源分级：只允许"用户直接陈述"的内容进入 Human 块，工具输出/网页内容只能进 archival 且标记来源；
  - 内容过滤：检测指令形状的文本（"ignore previous instructions"、"you must now"）并拒绝整理进 core；
  - 版本化与回滚：任何块改写都可以一键回到前一版本；
  - "更强的模型"并不等于"更安全"——它同样可能被注入，反而因为权限更大（能改 core）而更危险。
- 加分点：结合 [阶段 14 · 27 Prompt Injection 与 PVE 防御](../../27-prompt-injection-defense/docs/zh.md) 讨论权限分离——sleep agent 默认只能写 archival 和"候选块"，提交到 core 需要单独的、受限的步骤。

---

## 六、关联知识点

### 前置知识
- [阶段 14 · 07 Agent Memory：虚拟上下文与记忆分页](../../07-memory-virtual-context-memgpt/docs/zh.md)：本节的直接前置——MemGPT 的两层结构与 core memory。
- [阶段 14 · 01 Agent Loop：观察、思考、行动](../../01-the-agent-loop/docs/zh.md)：主 agent 与 sleep-time agent 都运行 ReAct 循环。
- [阶段 11 · 05 Context Engineering: 窗口、 预算、 记忆和检索](../../../11-llm-engineering/05-context-engineering/docs/zh.md)：把 core 块当作上下文预算的一部分。

### 本节被哪些后续内容用到
- [阶段 14 · 09 混合记忆：向量、图与 KV](../../09-hybrid-memory-mem0/docs/zh.md)：archival 层的多存储实现与冲突检测（Mem0 的 conflict detector）。
- [阶段 14 · 10 技能库与终身学习（Voyager）](../../10-skill-libraries-voyager/docs/zh.md)：讲义 Use It 把 Agent SDK skills 类比为"block 形状的知识"。
- [阶段 14 · 17 将 Harness 封装为库：Subagents 与会话存储](../../17-claude-agent-sdk/docs/zh.md)：会话存储与 skill 按需加载。
- [阶段 14 · 23 OpenTelemetry GenAI 语义约定](../../23-otel-genai-conventions/docs/zh.md)：为块操作和 sleep pass 打 span。
- [阶段 14 · 27 Prompt Injection 与 PVE 防御](../../27-prompt-injection-defense/docs/zh.md)：poisoned consolidation 的防御。
- [阶段 14 · 29 生产运行时：队列、事件与定时任务](../../29-production-runtimes/docs/zh.md)：sleep-time 任务的调度（队列、定时触发）。

### 延伸关键词
`Letta` · `memory block` · `core / recall / archival` · `sleep-time compute` · `learned_context` · `block limit` · `consolidation` · `invalidation` · `optimistic concurrency` · `lost update` · `silent drift` · `native reasoning` · `letta_v1_agent`
