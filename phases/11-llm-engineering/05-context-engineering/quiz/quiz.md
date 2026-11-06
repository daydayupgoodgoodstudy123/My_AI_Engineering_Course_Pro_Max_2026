# 测验 · Context Engineering：窗口、预算、记忆和检索（Context Engineering: Windows, Budgets, Memory, and Retrieval）

> **阶段 11 · LLM 工程 · 第 05 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Context vs prompt | 讲义："Prompt engineering is a subset. Context engineering is the whole game." 上下文 = system prompt + 工具定义 + 检索内容 + 对话历史 + few-shot + 当前问题 + 生成预留 |
| 2 | 上下文是稀缺资源 | 把窗口当 RAM 而不是磁盘；每个无关 token 都挤占有用 token，讲义："A carefully curated 10K token context often outperforms a dumped 100K token context." |
| 3 | Token 预算 | 显式给每个组件分配上限，并为生成预留 2,000–4,000 token；窗口上限同时包含输入和输出 |
| 4 | Lost-in-the-middle | Liu et al. (2023)：信息放在开头或结尾时准确率高，放在中间（约 40–70% 位置）明显下降；重要内容放两端，中间放最不重要的 |
| 5 | 压缩策略 | 历史摘要、相关性过滤、工具裁剪（tool pruning，讲义称可省 60–80%）、递归摘要 |
| 6 | 三种记忆 | 短期（当前对话，在窗口内）、长期（事实与偏好，存数据库、会话开始时取回，如 CLAUDE.md）、情景（过去的具体交互，存为 embedding、按相似度取回） |
| 7 | 动态组装 | 每个查询：分类意图 → 选工具 → 检索文档 → 选历史 → 选 few-shot → 按重要性排序 |
| 8 | RAG 即上下文工程 | 讲义："The entire RAG pipeline ... exists to solve one problem: putting the right information in the context window." |
| 9 | 长上下文的代价 | 注意力计算随长度增长（原始 Transformer 为 O(n²)），KV cache 随长度线性增长，prefill 变慢；更重要的是检索准确率下降 |
| 10 | 本节代码的简化 | 用"词数 × 1.3"估 token；按分配顺序截断导致优先级倒置；历史"摘要"其实是截断，且演示中从未触发；工具预算记的是工具名的 token 数 |

### 核心技能（能动手做到）

- [ ] 给定一个应用的各组件大小，算出总 token 与窗口占用率，并指出最该压缩的部分
- [ ] 实现一个 `ContextBudget`：按组件记账、单组件上限、全局上限、生成预留，并能按**优先级**而不是按调用顺序分配
- [ ] 实现 lost-in-the-middle 重排：按分数排序后交替放到首尾，最不相关的落在中间
- [ ] 实现"最近 N 轮原文 + 更早内容滚动摘要"的对话历史管理，并保证总量有界
- [ ] 用意图分类做动态工具选择，并说出关键词子串匹配的误判风险
- [ ] 为检索内容加相关性阈值、停用词处理和去重，避免"因为都有 the 而被召回"
- [ ] 说出把哪些信息放进长期记忆、哪些放进情景记忆，以及何时取回

---

## 二、基础自测（选择题）

**Q1.** 讲义中编程助手的上下文：system prompt 500、50 个工具定义 8,000、检索文档 4,000、10 轮历史 6,000、当前问题 200、生成预留 4,000。总量及其在 128K 窗口中的占比约为：

- A. 18,700 token，约 15%
- B. 22,700 token，约 18%
- C. 22,700 token，约 23%
- D. 26,700 token，约 21%

**Q2.** 执行 `reorder_lost_in_middle(["A", "B", "C", "D", "E"], [0.95, 0.60, 0.20, 0.80, 0.50])`，返回：

- A. `["A", "D", "B", "E", "C"]`
- B. `["A", "B", "C", "D", "E"]`
- C. `["C", "E", "B", "D", "A"]`
- D. `["A", "B", "C", "E", "D"]`

**Q3.** 关于 lost-in-the-middle，下列做法与讲义建议**一致**的是：

- A. 关键指令放在最前面，当前问题和最相关的上下文放在最后，必要时在末尾重复中间的关键信息
- B. 按检索分数从高到低依次排列即可，模型会平均关注所有位置
- C. 把最重要的文档放在正中间，因为两端会被 system prompt 和问题占据
- D. 只要窗口足够大，位置就不重要

**Q4.** 本节 STEP 3 用 `ConversationManager(max_history_tokens=200)` 记录 5 轮问答（10 条消息）。运行结束时摘要（summaries）的数量是：

- A. 3
- B. 1
- C. 0
- D. 5

**Q5.** STEP 5 中，代码查询（"Fix the bug in the authentication module..."）选中了 5 个工具，`select_tools` 返回的 `tool_tokens` 为 710，但预算报告中 `tools` 一行只有 6 token。原因是：

- A. `ContextBudget` 对工具做了压缩
- B. 生成预留占用了工具的预算
- C. 128K 窗口太大，工具占比被四舍五入
- D. `assemble` 把 `json.dumps(工具名列表)` 交给 `allocate` 计数，`tool_tokens` 被丢弃，只统计了 5 个工具名字符串的 token

**Q6.** 执行 `classify_intent("Show me the latest sales numbers")`，返回：

- A. `["code"]`
- B. `["data"]`
- C. `["research"]`
- D. `["code"]`，因为没有匹配到任何关键词时默认返回 code

**Q7.** 用户说"上周二我们在 auth 模块里调过一个类似的问题"，Agent 需要找回那次对话的细节。按讲义的三种记忆划分，这属于：

- A. 短期记忆（short-term memory）
- B. 长期记忆（long-term memory）
- C. 情景记忆（episodic memory）
- D. 工作记忆（generation budget）

**Q8.** 关于生成预留（generation budget），正确的是：

- A. 生成预留只影响费用，不影响模型能否完整回答
- B. 上下文窗口包含输入和输出；把输入塞满窗口，模型就没有空间回答，讲义建议至少预留 2,000–4,000 token
- C. 生成预留越大越好，最好占窗口的一半
- D. 生成预留只在流式输出时需要

---

## 三、动手 / 代码题

**Q9.** `ContextEngine.assemble` 按如下顺序调用 `allocate`，而 `allocate` 在超出剩余预算时从**开头**保留内容：

```python
        budget.allocate("system_prompt", self.system_prompt, max_tokens=1000)
        ...
        budget.allocate("tools", tool_text, max_tokens=2000)
        ...
            budget.allocate("retrieved_context", doc_text, max_tokens=3000)
        ...
            budget.allocate("conversation_history", history_text, max_tokens=5000)
        budget.allocate("user_query", query, max_tokens=500)
```

```python
        if used + tokens > self.available:
            allowed = self.available - used
            ...
            words = content.split()
            target_words = int(allowed / 1.3)
            content = " ".join(words[:target_words])
```

1. 把窗口设为 `ContextEngine(max_tokens=4150, generation_reserve=4000)`（可用 150 token），对代码查询调用 `chat`，`user_query` 会被分到多少 token？这说明了什么问题？
2. 对话历史超过上限被截断时，保留的是最早的还是最近的对话？为什么这对聊天是错误的？
3. `assemble` 返回的是什么？截断后的内容去哪儿了？
4. 写出改进思路或代码：分配顺序与拼接顺序如何解耦？

**Q10.** `ConversationManager` 的压缩逻辑：

```python
    def _compress_if_needed(self):
        total = sum(count_tokens(t["content"]) for t in self.turns)
        if total <= self.max_history_tokens:
            return
        while total > self.max_history_tokens and len(self.turns) > 4:
            old_turns = self.turns[:2]
            summary = self._summarize_turns(old_turns)
            self.summaries.append(summary)
            self.turns = self.turns[2:]
            total = sum(count_tokens(t["content"]) for t in self.turns)
```

1. 本节运行中（STEP 3 和 STEP 5）压缩被触发过吗？依据是什么输出？
2. 用 `max_history_tokens=50`、30 条每条约 15 token 的消息测试，`stats()` 给出 `live_turns=4, summaries=13, tokens=546`。为什么远超 50？100 条时会怎样？
3. `_summarize_turns` 真的是"摘要"吗？
4. 改写成"最近若干条原文 + 一份滚动摘要"且总量有界。

**Q11.** 相关性打分与阈值：

```python
def score_relevance(query, documents):
    query_words = set(query.lower().split())
    ...
        overlap = len(query_words & doc_words) / len(query_words)
```

`assemble` 使用 `threshold = 0.05`。实测查询"Schedule a team standup meeting for tomorrow morning"从知识库中召回了 4 条：Python 3.12 类型参数、PostgreSQL + pgvector、测试覆盖率 80%、repository pattern。

1. 这 4 条是因为哪个词被召回的？STEP 6 中被纳入的 4 条里，有几条只靠虚词入选？
2. 结合讲义"Bad retrieval is worse than no retrieval"，说明它的危害。
3. 改进打分函数，并验证上面的查询不再召回无关文档。

**Q12.** 工具选择：

```python
        "code": ["code", "function", "bug", "error", "file", "implement", "refactor", "debug", "test", "fix", "class", "module"],
        "calendar": ["meeting", "schedule", "calendar", "appointment", "event", "tuesday", "tomorrow"],
        "email": ["email", "mail", "send", "inbox", "message", "reply"],
    ...
        score = sum(1 for kw in keywords if kw in query_lower)
```

1. 预测 `"How do I prevent duplicate charges?"`、`"Who is the sender of this?"`、`"Explain the prefix tree"` 的意图，并说明原因。
2. `select_tools` 的 `token_budget=2000` 在本节数据下是否曾经起作用？
3. 讲义练习 4 要求"priority-based tool selector"。写出思路：如何给每个工具打分、如何在预算内选取？

---

## 四、面试高频题

**Q13.**（基础必考）什么是 context engineering？它和 prompt engineering 是什么关系？一次 LLM 调用的上下文由哪些部分组成？

**Q14.**（原理深挖）既然模型支持 200K 甚至更长的上下文，为什么"能放"不等于"该放"？请从计算成本、延迟和模型表现三个角度说明。

**Q15.**（工程实践）你负责一个长期运行的编程 Agent，会话经常超过 100 轮，还有大量工具输出。你如何管理对话历史与工具结果？

**Q16.**（场景设计）一个企业 Agent 接入了 200 个工具，工具定义总计约 30K token。如何设计工具选择？还需要考虑哪些副作用？

**Q17.**（追问型）"现在都有 1M token 的上下文了，直接把整个知识库塞进去不就行了，还要 RAG 和上下文工程干什么？"

---

## 五、参考答案与解析

### Q1 — 答案：B

`500 + 8,000 + 4,000 + 6,000 + 200 + 4,000 = 22,700`，`22,700 / 128,000 ≈ 17.7%`。讲义："That is only 18% of a 128K window."
- A 漏加了生成预留（4,000）。
- C 占比算错（22,700/100,000）。
- D 多加了一份 4,000。
- 讲义接着强调：占比低不代表没问题，注意力成本和检索准确率才是关键。

### Q2 — 答案：D

按分数降序：A(0.95)、D(0.80)、B(0.60)、E(0.50)、C(0.20)。偶数位 `[::2]` = A、B、C 放前半；奇数位 `[1::2]` = D、E，反转后为 E、D 放后半。结果 `["A", "B", "C", "E", "D"]`（已实际运行验证）：第 1 名在最前，第 2 名在最后，最不相关的 C 在正中间。
- A 是简单的降序排列。
- B 是原顺序。
- C 是升序排列。

### Q3 — 答案：A

讲义的四条建议："Put the most important information first... Put the current query and most relevant context last... Treat the middle of the context as the lowest-priority zone... If you must include information in the middle, duplicate the key point at the end."
- B 忽略了位置效应；讲义引用 Liu et al. (2023)：相关文档放首尾时准确率 85–90%，放在 20 篇中的第 10 篇时降到 60–70%。
- C 正好相反。
- D 错：讲义说这种效应"affects all current architectures"，窗口大小不能消除它。

### Q4 — 答案：C

运行输出：5 轮结束时 `Live turns: 10, Summaries: 0, Tokens: 139`。总 token 139 < 200，压缩条件从未满足，`get_context()` 只有 `[Recent Conversation]` 部分。这个演示名为"History Compression"，实际**没有展示任何压缩**——要看到压缩，需把上限调到 100 以下（见 Q10）。
- A、B、D 都假设压缩已触发。

### Q5 — 答案：D

```python
        tools, tool_tokens = select_tools(query, token_budget=2000)
        tool_text = json.dumps(list(tools.keys()))
        budget.allocate("tools", tool_text, max_tokens=2000)
```

`tool_text` 是 `'["read_file", "write_file", "search_code", "run_command", "query_database"]'`，按空格切是 5 个"词"，`int(5 × 1.3) = 6`。注册表里写明的真实 token 数（120 + 150 + 130 + 140 + 170 = 710）存在 `tool_tokens` 里却从未使用。日程查询只选中 1 个工具时，报告里 `tools` 只有 1 token。结果是预算报告严重低估工具开销——这恰恰是讲义说的最大浪费来源之一。
- A、B、C 都不符合代码。

### Q6 — 答案：A

`"test" in "show me the latest sales numbers"` 为 True——`latest` 里含有子串 `test`。没有其它意图命中，于是返回 `["code"]`，选中 5 个代码工具（已实际运行验证）。
- B 是"应该"的结果，但 `data` 的关键词（data、query、stats…）一个也没命中。
- C 不对：research 关键词都不在句中。
- D 的结果碰巧对，但原因错：这里不是走默认分支，而是子串误匹配。

### Q7 — 答案：C

讲义："Episodic memory: specific past interactions that might be relevant. 'Last Tuesday, we debugged a similar issue in the auth module.' Stored as embeddings, retrieved when the current conversation matches a past episode." 题干几乎就是讲义原例。
- A 是当前会话本身。
- B 是跨会话的事实与偏好（如"项目使用 PostgreSQL"），在会话开始时取回。
- D 不是记忆类型。

### Q8 — 答案：B

讲义 Key Terms："Context window: The maximum number of tokens (input + output)..."；"Generation budget: ... if the context fills the window completely, the model has no room to respond"；"Reserve at least 2,000-4,000 tokens for generation." 本节 `ContextBudget` 就是 `available = max_tokens - generation_reserve`。
- A 错：没有预留会导致输出被截断。
- C 过度：预留应按预期输出长度设置，过大会挤占输入。
- D 与流式无关。

### Q9 — 参考答案

1. 可用 150 token：`system_prompt` 41 + `tools` 6 + `retrieved_context` 79 + `conversation_history` 20 = 146，`user_query` 只剩 4 个 token 的额度，被截成 **3 token**（已实际运行验证，`allocations` 中 `'user_query': 3`）。用户的问题——最不能丢的部分——被截得只剩开头三个词。这是**优先级倒置**：分配顺序（先到先得）被当成了优先级，而讲义说"User query: Fixed, highest"（`outputs/skill-context-engineering.md`）。
2. `" ".join(words[:target_words])` 保留**开头**。历史文本按时间顺序排列（摘要在前、最早的轮次在前），所以截断后保留的是最早的对话、丢掉的是最近的对话。实测：10 轮历史截到 60 token 后只剩第 0 轮和第 1 轮的一部分。聊天中最近几轮最重要（skill 文件："Keep the last 3-4 turns verbatim"），应从**尾部**保留。
3. `assemble` 只返回 `ContextBudget` 对象（一个记账本），`allocate` 返回的截断后内容全部被丢弃（返回值没被接收），代码从未真正拼出一个可发送给模型的 prompt。它演示的是"记账"，不是"组装"。
4. 思路：**按优先级分配，按注意力友好的顺序拼接**，两者解耦。

```python
def truncate_tail(content, max_tokens):          # 历史：保留最近的内容
    words = content.split()
    keep = int(max_tokens / 1.3)
    return " ".join(words[-keep:]) if keep > 0 else ""

def assemble_by_priority(engine, query):
    budget = ContextBudget(engine.max_tokens, engine.generation_reserve)
    parts = {}
    # 1) 按优先级占预算：system → query → tools → 检索 → 历史
    parts["system_prompt"], _ = budget.allocate("system_prompt", engine.system_prompt, max_tokens=1000)
    parts["user_query"], _ = budget.allocate("user_query", query, max_tokens=500)
    tools, tool_tokens = select_tools(query, token_budget=2000)
    if tool_tokens <= budget.remaining():
        budget.allocations["tools"] = tool_tokens     # 记真实的工具定义 token 数
        parts["tools"] = json.dumps(list(tools))
    # ……检索内容同理；历史用 truncate_tail 截到 min(5000, budget.remaining())
    # 2) 按注意力友好的顺序拼接
    order = ["system_prompt", "tools", "retrieved_context", "conversation_history", "user_query"]
    return budget, "\n\n".join(parts[k] for k in order if parts.get(k))
```

在同样 150 token 的窗口下（已运行验证），`user_query` 完整保留 16 token；710 token 的工具定义放不下就整体跳过（真实系统中应换成更少的工具，而不是截断半个工具定义）；拼接出的 prompt 以完整的用户问题结尾。

### Q10 — 参考答案

1. **从未触发**。STEP 3 结束时 `Summaries: 0, Tokens: 139`（上限 200）；STEP 5 结束时 `Conversation state: 20 live turns, 0 summaries, 302 tokens`（上限 5000）。两个演示都没有展示压缩。
2. 原因有两个：
   - `total` 只统计 `self.turns`，**不统计 `self.summaries`**。每压缩一次就追加一条摘要，摘要列表无限增长，`get_context()` 的总量不受控。
   - `len(self.turns) > 4` 的条件让最后 4 条无论多长都保留；4 条 × 15 token = 60 > 50，上限本身就无法满足。
   - 已实测：30 条时 13 条摘要、546 token；100 条时 48 条摘要、1,820 token——随对话长度**线性增长**，与"压缩"的初衷相反。
3. 不是。它把每条消息截到前 100 个字符再拼起来，是"截断"不是"摘要"；讲义描述的是"We discussed X, decided Y, and the user wants Z"式的语义摘要（真实系统通常调用 LLM 生成）。
4. 改写（已运行验证：30 条与 100 条时都是 `live_turns=4, summaries=1, tokens=84`，不再增长；84 > 50 是因为保留的 4 条原文本身就有 60 token）：

```python
class RollingConversation(ConversationManager):
    def __init__(self, max_history_tokens=5000, keep_recent=4, summarize=None):
        super().__init__(max_history_tokens)
        self.keep_recent = keep_recent
        # 真实系统中这里调用 LLM；演示用"截取前若干词"代替
        self.summarize = summarize or (lambda text, budget: " ".join(text.split()[: int(budget / 1.3)]))

    def _compress_if_needed(self):
        while self.token_count() > self.max_history_tokens and len(self.turns) > self.keep_recent:
            old, self.turns = self.turns[:2], self.turns[2:]
            merged = " ".join(self.summaries + [self._summarize_turns(old)])
            self.summaries = [self.summarize(merged, self.max_history_tokens // 4)]
```

要点：用 `token_count()`（含摘要）判断；把旧摘要与新移出的轮次**合并后重新摘要**（即讲义的 recursive summarization），摘要只保留一份且有固定预算；`keep_recent` 与上限要相容。

### Q11 — 参考答案

1. 4 条都是因为 **`for`**（查询 8 个词，命中 1 个，1/8 = 0.125 ≥ 0.05）：`"...for generic classes"`、`"...for embedding storage"`、`"...for all new modules"`、`"...for data access"`。STEP 6 中纳入的 4 条里，有 **3 条**（PostgreSQL、Next.js、GitHub Actions）只因为共有 `the` 而得到 0.100；唯一真正相关的是 Supabase Auth + JWT（0.200）。另外 `split()` 不去标点，`tokens.` 与 `token` 不匹配，相关文档的分数也被低估。STEP 5 的向量检索查询甚至召回了 10 条中的 9 条，过滤几乎失效。
2. 讲义："Bad retrieval is worse than no retrieval -- it fills the window with noise and actively misleads the model." 日程查询被塞进 4 条技术事实，既浪费 token，又可能诱导模型答非所问；对相关查询，真正有用的文档被淹没在噪声中，还可能被重排到"中间"。配套的 skill 文件建议的阈值是 0.3（cosine），代码用的是 0.05（词重叠率），几乎等于"有任一共同词就收"。
3. 改进：正则分词去标点、去停用词、做简单的词形归一（去复数 s），再算重叠率：

```python
import re
STOP = {"the", "a", "an", "is", "are", "for", "with", "to", "of", "in", "on", "and", "or",
        "how", "do", "i", "what", "where", "by", "be", "too", "using", "all", "per", "must",
        "above", "now", "we", "me"}

def norm(text):
    return {w.rstrip("s") if len(w) > 3 else w
            for w in re.findall(r"[a-z0-9]+", text.lower())} - STOP

def score_relevance_v2(query, documents):
    q = norm(query)
    return [round(len(q & norm(d)) / len(q), 3) if q else 0.0 for d in documents]
```

已运行验证：日程查询召回 **0 条**；STEP 6 的 JWT 查询只召回 Supabase Auth 一条（分数 0.5）；向量检索查询只召回 HNSW 索引（0.333）与 PostgreSQL + pgvector（0.167）两条。生产中更好的做法是用上一节的 embedding 相似度 + 重排序，并做讲义练习 2 的语义去重。

### Q12 — 参考答案

1. 全部是子串误匹配（已实际运行验证）：
   - "How do I prevent duplicate charges?" → `["calendar"]`：`prevent` 含 `event`，选中 `create_calendar_event`；
   - "Who is the sender of this?" → `["email"]`：`sender` 含 `send`；
   - "Explain the prefix tree" → `["code", "research"]`：`prefix` 含 `fix`，`explain` 命中 research；
   - 同理 `latest` 含 `test`（Q6）。应按词边界匹配（`re.search(r"\bevent\b", q)`），更好的是用 embedding 或小模型做意图分类。
2. **没有**。整个注册表只有 1,580 token，小于 2,000，预算永远不会成为约束；`ContextEngine` 又没有把真实工具 token 计入总预算（Q5）。
3. 思路（讲义练习 4）：
   - 给每个工具一个与查询的相关性分数：工具名 + description 的 embedding 与查询 embedding 的 cosine，或意图分类器输出的类别概率；
   - 按分数降序贪心加入，直到工具预算用完（类似背包问题的贪心解）；
   - 设最低分阈值，并始终保留少量"兜底工具"（skill 文件："Always include a 'general' tool (like web search) as fallback"）；
   - 评估：在一组带"正确工具"标注的任务上，比较包含 5/10/20/50 个工具时的工具选择准确率与 token 成本。

### Q13 — 参考回答要点

- **定义**：决定"什么进入上下文窗口、以什么顺序、占多少预算"的工程学科；讲义："They decide what goes in, what stays out, and in what order."
- **关系**：prompt engineering 关注"怎么写指令"，是 context engineering 的子集；后者还包括检索、记忆、工具选择、历史压缩、预算与排序。
- **组成**（讲义 Context Components）：system prompt（每次调用都重复发送，要精简）、工具定义（每个 50–200 token）、检索内容、对话历史（随轮数线性增长）、few-shot 示例、当前问题、生成预留。
- **核心目标**：最大化信噪比。讲义："Context engineering is the discipline of maximizing signal-to-noise ratio within the context window."
- 加分点：举出 Claude Code 的做法——CLAUDE.md 作为长期记忆、按需读取文件而非一次性灌入代码库、旧对话摘要（讲义 Use It 一节）。

### Q14 — 参考回答要点

- **计算成本**：原始注意力对序列长度是 O(n²)（讲义："though most production models use efficient attention variants"）；按 token 计费的 API，输入越长每次调用越贵，system prompt 和工具定义每轮都会重复计费。
- **延迟与显存**：prefill 阶段要处理整个输入，长 prompt 直接拉高首 token 延迟（TTFT）；KV cache 随上下文长度线性增长，挤占并发（讲义延伸阅读中的 Pope et al.、SARATHI、GQA 论文讨论的正是这些）。
- **模型表现**：lost-in-the-middle——中间位置的信息更容易被忽略；无关内容会干扰甚至误导模型（"Bad retrieval is worse than no retrieval"）；skill 文件给出的经验红线是"Context utilization over 60%"。
- **结论**：讲义："having 200K tokens available does not mean using 200K tokens is effective."
- 加分点：提到可以用 NIAH、RULER 等长上下文评测来度量所选模型在不同位置/长度下的真实表现（讲义 Related 指向阶段 05 · 28）。

### Q15 — 参考回答要点

- **分层保留**：最近 3–4 轮原文保留；更早的轮次滚动摘要成一份"决策与状态"摘要（我们讨论了 X、决定了 Y、阻塞在 Z）；触发阈值按预算比例设（skill 文件："Trigger compression when history exceeds 30% of the available budget"）。
- **工具输出单独处理**：大块输出（日志、文件内容、搜索结果）在被使用后替换为简短摘要或引用（文件路径 + 行号），需要时再重新读取；去掉没有信息量的系统轮次。
- **长期记忆抽取**：把会话中出现的稳定事实（项目约定、用户偏好）写入长期记忆（如 CLAUDE.md 或数据库），下次会话开始时取回，而不是一直留在历史里。
- **情景记忆**：把已完成的子任务归档为 embedding，遇到相似问题时检索。
- **保证有界**：摘要本身也要有预算，并递归合并（Q10 的教训）；对历史做截断时从尾部保留（Q9 的教训）。
- **可观测**：每轮记录各组件 token 数（讲义练习 3 的"context replay"），找到开始压缩的轮次。
- 常见误区：只截断不摘要，导致早期的关键决策丢失；或只追加摘要不合并，导致"摘要也爆炸"。

### Q16 — 参考回答要点

- **两阶段选择**：先用轻量方法（意图分类、工具描述的 embedding 检索、分层的"工具目录"）选出候选 10–20 个，再把完整定义放进上下文；讲义称工具裁剪能减少 60–80% 的工具 token。
- **按词边界或语义匹配**，避免本节 `prevent → event` 式的子串误判；为高风险工具（发邮件、写库）设更高的选择门槛。
- **兜底与回退**：保留通用工具（如搜索）；模型发现缺工具时可以调用一个"查找工具"的元工具，按需加载（渐进披露）。
- **副作用 1：缓存失效**。前缀缓存（prompt caching）要求上下文开头保持稳定；每次请求换一组工具定义会让缓存命中率下降。可以把常用工具固定在前缀，动态部分放在后面（讲义 Related：Phase 11 · 15 Prompt Caching）。
- **副作用 2：选错工具**。被裁掉的工具模型就无法调用；需要离线评测"正确工具召回率"。
- **副作用 3：描述质量**。工具 description 本身就是上下文，写得冗长会抵消裁剪收益。

### Q17 — 参考回答要点

- **放得下 ≠ 用得好**：lost-in-the-middle 与噪声干扰使得把整个知识库塞进去后，关键事实的召回反而可能变差；讲义："A carefully curated 10K token context often outperforms a dumped 100K token context."
- **成本与延迟**：每次请求都为 1M token 付费、承担长 prefill 的延迟；而 RAG 每次只放入少量相关片段。
- **规模**：企业知识库通常远大于任何窗口；知识也在不断更新，检索可以即时反映新文档。
- **可控性与可追溯**：检索结果可以记录来源、做权限过滤（不同用户能看的文档不同），整库灌入很难做到。
- **两者结合**：长上下文适合"一个大文档内的深度阅读"，RAG 适合"从大量文档中找相关部分"；实践中常把检索到的较大片段放进较长的上下文。
- 加分点：引用讲义 Use It："embed everything, retrieve on demand, include only what matters."

---

## 六、关联知识点

### 前置知识
- [阶段 10 · 04 预训练 Mini GPT](../../../10-llms-from-scratch/04-pre-training-mini-gpt/docs/zh.md)：上下文窗口、KV cache 与 prefill/decode 的来源。
- [阶段 07 · 12 KV Cache、Flash Attention 与 Inference 优化](../../../07-transformers-deep-dive/12-kv-cache-flash-attention/docs/zh.md)：长上下文的显存与计算代价。
- [阶段 11 · 01 Prompt Engineering：技术与模式](../../01-prompt-engineering/docs/zh.md)、[阶段 11 · 02 Few-Shot, Chain-of-Thought, Tree-of-Thought](../../02-few-shot-cot/docs/zh.md)：讲义列出的先修课，few-shot 示例是上下文的组成部分。
- [阶段 11 · 04 Embeddings 与向量表示](../../04-embeddings/docs/zh.md)：相关性打分、情景记忆的向量检索。
- [阶段 05 · 28 长上下文 Evaluation](../../../05-nlp-foundations-to-advanced/28-long-context-evaluation/docs/zh.md)：讲义推荐用 NIAH/RULER 度量 lost-in-the-middle。

### 本节被哪些后续内容用到
- [阶段 11 · 06 RAG（检索增强生成）](../../06-rag/docs/zh.md)：讲义称 RAG 是"context engineering formalized"。
- [阶段 11 · 07 Advanced RAG](../../07-advanced-rag/docs/zh.md)：重排序、混合检索提升放入上下文的内容质量。
- [阶段 11 · 09 Function Calling 与工具使用](../../09-function-calling/docs/zh.md)：工具定义的 token 成本与选择。
- [阶段 11 · 15 Prompt 缓存与上下文缓存](../../15-prompt-caching/docs/zh.md)：讲义称缓存友好的布局是上下文工程的延伸。
- [阶段 14 · 07 Agent Memory：虚拟上下文与记忆分页](../../../14-agent-engineering/07-memory-virtual-context-memgpt/docs/zh.md)、[阶段 14 · 09 混合记忆：向量、图与 KV](../../../14-agent-engineering/09-hybrid-memory-mem0/docs/zh.md)：短期/长期/情景记忆的系统化实现。
- [阶段 13 · 24 Skill Discovery 与 Progressive Disclosure](../../../13-tools-and-protocols/24-skill-discovery-and-progressive-disclosure/docs/zh.md)：按需加载工具与技能，是动态工具选择的延伸。

### 延伸关键词
`context window` · `token budget` · `generation reserve` · `lost-in-the-middle` · `NIAH / RULER` · `tool pruning` · `intent classification` · `history summarization / recursive summarization` · `short-term / long-term / episodic memory` · `dynamic context assembly` · `prompt caching` · `TTFT` · `KV cache`
