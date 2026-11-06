# 代码讲解 · main.py

> **所属小节**：阶段 11 · LLM 工程 · 第 05 节 Context Engineering：窗口、预算、记忆和检索 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py` ｜ **依赖**：标准库 `json`、`collections.OrderedDict`；文件开头 `import numpy as np` 但从未使用（需要安装 numpy 才能导入成功）。无需 API key、无需网络。同目录 `main.ts` 是 TypeScript 移植版，本讲解只覆盖 Python 版。

---

## 1. 这份代码在考察什么

这份代码把讲义"动态上下文组装"的六个步骤做成可运行的小部件，不调用任何模型：

1. **Token 计数**（`count_tokens`）：用"空格词数 × 1.3"估算 token——"You cannot budget what you cannot measure"。
2. **预算管理**（`ContextBudget`）：按组件记账，单组件上限 + 全局上限 + 生成预留，超出就截断。
3. **Lost-in-the-middle 重排**（`reorder_lost_in_middle`）：最相关的放首尾，最不相关的放中间。
4. **对话历史压缩**（`ConversationManager`）：超过上限时把最早的两条替换为"摘要"。
5. **动态工具选择**（`classify_intent` + `select_tools`）：关键词意图分类，只保留相关类别的工具。
6. **完整组装**（`ContextEngine`）：系统提示 → 工具 → 检索 → 历史 → 查询，逐项记账。

> 一句话：**把"窗口是稀缺资源，要按预算、按优先级、按位置去分配"这一思想落成六个可替换的部件**。这些部件的接口是对的，但几乎每个都有值得指出的简化或 bug——优先级倒置、从错误的一端截断历史、压缩从未触发、工具 token 记错、虚词驱动的"检索"——它们恰恰是生产实现中最容易犯的错误。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `count_tokens` / `count_tokens_json` | 函数 | 词数 × 1.3 取整；后者先 `json.dumps`（未被使用） | Token 计量 |
| `ContextBudget` | 类 | `allocate` 记账并截断；`remaining`、`utilization`、`report` | Token 预算 |
| `reorder_lost_in_middle` | 函数 | 按分数排序后交替放到首、尾 | Lost-in-the-middle |
| `score_relevance` | 函数 | 查询词集合与文档词集合的重叠率 | 相关性过滤 |
| `ConversationManager` | 类 | 记录轮次；超限时把前两条压成一条"摘要"；`get_context` 拼接 | 短期记忆 / 历史摘要 |
| `TOOL_REGISTRY` | 常量字典 | 10 个工具：描述、token 数、类别，合计 1,580 token | 工具定义 |
| `classify_intent` | 函数 | 5 类意图的关键词**子串**计数，取 ≥ 最高分一半的类别 | 意图分类 |
| `select_tools` | 函数 | 选出类别命中的工具，受工具预算约束 | Tool pruning |
| `ContextEngine` | 类 | 持有对话管理器、系统提示、10 条知识；`assemble` 组装、`chat` 一轮对话 | 动态上下文组装 |
| `run_*_demo` × 6 | 函数 | STEP 1–6 演示 | — |

数据流（`ContextEngine.chat`）：用户查询 → `conversation.add_turn("user")` → `assemble`：新建 `ContextBudget` → 系统提示记账 → `select_tools` → 工具名列表记账 → `score_relevance` + 阈值 0.05 → `reorder_lost_in_middle` → 检索内容记账 → 历史记账 → 查询记账 → 返回 `budget` → 生成模拟回复并 `add_turn("assistant")`。

---

## 3. 逐段精讲

### 3.1 Token 计数：词数 × 1.3

```python
def count_tokens(text):
    if not text:
        return 0
    return int(len(text.split()) * 1.3)
```

- 英文 BPE tokenizer 平均每个词约 1.3 个 token，这是讲义采用的经验系数；`int()` 向下取整。
- `if not text` 同时处理 `None` 和空字符串。
- ⚠️ **对中文完全失效**：中文没有空格，`count_tokens("你好世界今天天气很好")` 返回 1（已实测），实际 token 数远不止 1。对中文学习者尤其要注意：生产中必须用模型对应的 tokenizer（如 tiktoken、Hugging Face tokenizer 或供应商的 token 计数接口）。
- ⚠️ JSON、代码、URL 等内容的空格很少，也会被严重低估（见 3.7 的工具计数）。

### 3.2 `ContextBudget.allocate`：记账 + 两级截断

```python
    def allocate(self, component, content, max_tokens=None):
        tokens = count_tokens(content)
        if max_tokens and tokens > max_tokens:
            words = content.split()
            target_words = int(max_tokens / 1.3)
            content = " ".join(words[:target_words])
            tokens = count_tokens(content)

        used = sum(self.allocations.values())
        if used + tokens > self.available:
            allowed = self.available - used
            if allowed <= 0:
                return None, 0
            words = content.split()
            target_words = int(allowed / 1.3)
            content = " ".join(words[:target_words])
            tokens = count_tokens(content)

        self.allocations[component] = tokens
        return content, tokens
```

- **第一级：组件上限**。超过 `max_tokens` 就按"token ÷ 1.3 = 词数"反推保留多少词。
- **第二级：全局上限**。`available = max_tokens − generation_reserve`，已用 + 本次超出时只给剩余额度；完全没额度返回 `(None, 0)` 且不记账。
- `OrderedDict` 保持插入顺序，报告按分配顺序列出组件（Python 3.7+ 的普通 dict 也保持插入顺序）。
- `if max_tokens and ...`：`max_tokens=0` 会被当成"无上限"——用 `is not None` 更严谨。
- 同名组件重复 `allocate` 会**覆盖**旧值，而不是累加。
- ⚠️ **先到先得 = 优先级倒置**：全局截断只发生在"后来者"身上。`ContextEngine.assemble` 最后才分配 `user_query`，窗口紧张时被截断的是用户的问题本身。实测：`ContextEngine(max_tokens=4150, generation_reserve=4000)`（可用 150）下，`user_query` 只分到 3 token（测验 Q9）。
- ⚠️ **只从开头保留**：`words[:target_words]` 对检索文档尚可（排在前面的是更相关的），对对话历史则是错的——会保留最早的对话、丢掉最近的对话。
- ⚠️ **截断粒度粗**：按空格词截断可能把 JSON、代码切成半截。
- `report` 中 `bar = "#" * int(pct * 2) if pct >= 0.5 else ""`：每 0.5% 一个 `#`。本节所有组件都低于 0.5%，所以运行输出里没有任何条形图。讲义正文写的是 `int(pct / 2)`（每 2% 一个 `#`），与代码不同。

### 3.3 Lost-in-the-middle 重排

```python
def reorder_lost_in_middle(items, scores):
    paired = sorted(zip(scores, items), reverse=True)
    sorted_items = [item for _, item in paired]

    if len(sorted_items) <= 2:
        return sorted_items

    first_half = sorted_items[::2]
    second_half = sorted_items[1::2]
    second_half.reverse()

    return first_half + second_half
```

- 先按分数降序：第 1、3、5…名进前半段（正序），第 2、4、6…名进后半段（倒序）。结果是"两头高、中间低"的 U 形：第 1 名在最前，第 2 名在最后，最低分落在中间。
- STEP 2 的 7 篇文档：排序后 A(.95) D(.80) F(.75) B(.60) E(.30) G(.10) C(.05) → 前半 A、F、E、C，后半 D、B、G 反转为 G、B、D → `A F E C G B D`。最不相关的 C、G 在正中间。
- `zip(scores, items)` 把分数放在元组第一位，`sorted` 按元组比较；分数相同时会接着比较 `items` 本身——字符串可以比，但若 items 是字典就会抛 `TypeError`。更稳妥的是 `sorted(zip(scores, items), key=lambda p: p[0], reverse=True)`。
- 讲义建议"Put the current query and most relevant context last"：本函数把第 1 名放在**最前**，第 2 名放在最后；而在 `assemble` 中检索内容之后还有历史和查询，所以"末尾"实际是查询，不是检索文档。这只是对 lost-in-the-middle 的一种近似。

### 3.4 相关性打分

```python
def score_relevance(query, documents):
    query_words = set(query.lower().split())
    scores = []
    for doc in documents:
        doc_words = set(doc.lower().split())
        if not query_words:
            scores.append(0.0)
            continue
        overlap = len(query_words & doc_words) / len(query_words)
        scores.append(round(overlap, 3))
    return scores
```

- 分数 = 查询词中有多少比例出现在文档里（类似"查询覆盖率"）。
- `set & set` 求交集，`len(...)` 计数。
- ⚠️ **虚词驱动**：不去停用词，`the`、`for` 都算匹配；不去标点，`tokens.` 与 `token` 不匹配。配合 `assemble` 中 `threshold = 0.05`，几乎任何共享一个虚词的文档都会入选。实测日程查询"Schedule a team standup meeting for tomorrow morning"因为 `for` 召回了 4 条毫不相关的技术事实；向量检索查询召回了 10 条中的 9 条。这正是讲义警告的"Bad retrieval is worse than no retrieval"。改进见测验 Q11。

### 3.5 `ConversationManager`：短期记忆

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

    def _summarize_turns(self, turns):
        parts = []
        for t in turns:
            content = t["content"]
            if len(content) > 100:
                content = content[:100] + "..."
            parts.append(f"{t['role']}: {content}")
        return "Previous: " + " | ".join(parts)
```

- 每次 `add_turn` 后检查：超限就把最早的两条（通常是一问一答）移出并"摘要"，直到不超限或只剩 4 条。
- `get_context` 输出 `[Conversation Summary]` 段 + `[Recent Conversation]` 段，`stats` 返回活跃轮数、摘要数、token 数。
- ⚠️ **"摘要"其实是截断**：每条消息截到 100 字符。讲义描述的是"We discussed X, decided Y"式的语义摘要（通常由 LLM 生成）。
- ⚠️ **摘要不计入总量、也不合并**：`total` 只算 `self.turns`。实测 `max_history_tokens=50` 时，30 条消息后有 13 条摘要、546 token，100 条后 48 条摘要、1,820 token——历史仍然线性增长。正确做法是用 `token_count()`（含摘要）判断，并把旧摘要与新移出的轮次合并后重新摘要（讲义的 recursive summarization），见测验 Q10。
- ⚠️ **演示从未触发压缩**：STEP 3 上限 200，五轮只有 139 token；STEP 5 上限 5000，20 条只有 302 token。两处输出都是 `Summaries: 0`。
- `len(self.turns) > 4` 保证至少保留最近 4 条原文（与 skill 文件"Keep the last 3-4 turns verbatim"一致），但若 4 条本身就超限，上限无法满足。

### 3.6 工具注册表与意图分类

```python
def classify_intent(query):
    query_lower = query.lower()
    intent_keywords = {
        "code": ["code", "function", "bug", "error", "file", "implement", "refactor", "debug", "test", "fix", "class", "module"],
        "calendar": ["meeting", "schedule", "calendar", "appointment", "event", "tuesday", "tomorrow"],
        ...
    }
    scores = {}
    for intent, keywords in intent_keywords.items():
        score = sum(1 for kw in keywords if kw in query_lower)
        if score > 0:
            scores[intent] = score
    if not scores:
        return ["code"]
    max_score = max(scores.values())
    return [intent for intent, score in scores.items() if score >= max_score * 0.5]
```

- 每类意图数命中的关键词个数；保留得分 ≥ 最高分一半的所有类别（允许多意图）；一个都没命中时默认 `["code"]`。
- `"what is"`、`"look up"` 这类多词短语也能用 `in` 匹配，这是子串匹配的好处。
- ⚠️ **子串误匹配**（均已实测）：`latest` ⊃ `test` → code；`prevent` ⊃ `event` → calendar；`sender` ⊃ `send` → email；`prefix` ⊃ `fix` → code。STEP 4 中"Search for best practices on error handling in Python"被判为 `['code', 'research']`（`error` 命中 code），选了 6 个工具。
- 默认返回 `code` 意味着闲聊或未知问题也会带上 5 个代码工具。

```python
def select_tools(query, token_budget=2000):
    intents = classify_intent(query)
    relevant = {}
    total_tokens = 0
    for name, tool in TOOL_REGISTRY.items():
        if any(cat in intents for cat in tool["categories"]):
            if total_tokens + tool["tokens"] <= token_budget:
                relevant[name] = tool
                total_tokens += tool["tokens"]
    return relevant, total_tokens
```

- 工具只要有一个类别命中就入选；按注册表顺序贪心加入，超出预算的跳过（不是停止，后面更小的工具仍可能加入）。
- ⚠️ 注册表合计 1,580 token < 2,000，预算**永远不起作用**；也没有按相关度排序（讲义练习 4）。

### 3.7 `ContextEngine.assemble`：把所有部件串起来

```python
    def assemble(self, query):
        budget = ContextBudget(self.max_tokens, self.generation_reserve)
        budget.allocate("system_prompt", self.system_prompt, max_tokens=1000)

        tools, tool_tokens = select_tools(query, token_budget=2000)
        tool_text = json.dumps(list(tools.keys()))
        budget.allocate("tools", tool_text, max_tokens=2000)

        relevance = score_relevance(query, self.knowledge_base)
        threshold = 0.05
        relevant_docs = [doc for doc, score in zip(self.knowledge_base, relevance) if score >= threshold]
        if relevant_docs:
            doc_scores = [s for s in relevance if s >= threshold]
            reordered = reorder_lost_in_middle(relevant_docs, doc_scores)
            doc_text = "\n".join(reordered)
            budget.allocate("retrieved_context", doc_text, max_tokens=3000)

        history_text = self.conversation.get_context()
        if history_text.strip():
            budget.allocate("conversation_history", history_text, max_tokens=5000)

        budget.allocate("user_query", query, max_tokens=500)
        return budget
```

- **每次查询新建预算**：上下文按查询动态组装，不复用上一次的分配——这符合讲义"Dynamic beats static"。
- `relevant_docs` 与 `doc_scores` 用两个独立的列表推导式生成，但过滤条件相同、遍历顺序相同，所以一一对应。
- ⚠️ **工具 token 记错**：`tool_tokens`（真实定义的 token 数，如 710）被丢弃，记账的是工具**名字列表**的 JSON（如 `'["read_file", "write_file", ...]'` → 6 token）。日程查询只有 `'["create_calendar_event"]'`，记为 1 token。
- ⚠️ **只记账、不组装**：`allocate` 返回的截断后内容一律没有接收，`assemble` 返回的只是 `ContextBudget`。代码从未拼出真正要发送的 prompt。
- ⚠️ **优先级倒置**：分配顺序就是截断优先级，用户问题排在最后（3.2）。正确做法是"按优先级分配、按注意力友好的顺序拼接"，见测验 Q9 参考实现。
- ⚠️ **查询重复**：`chat` 先 `add_turn("user", query)` 再 `assemble`，所以当前问题既出现在 `conversation_history` 里，又作为 `user_query` 出现一次。STEP 5 第一问的 `conversation_history 20 tokens` 就是 `[Recent Conversation]\nuser: <当前问题>`。
- 讲义的组件图还包括 few-shot 示例，代码没有实现。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 词数 × 1.3 估 token | 无需 tokenizer 依赖 | 中文、代码、JSON 误差极大；用模型对应的 tokenizer |
| 组件上限 + 全局上限 + 生成预留 | 体现"预算"思想 | 先到先得造成优先级倒置；按优先级分配 |
| 统一从开头截断 | 实现简单 | 历史应从尾部保留；结构化内容应整块取舍 |
| U 形重排 | 对应 lost-in-the-middle | 只是近似；末尾实际是查询 |
| 词重叠率 + 阈值 0.05 | 不需要 embedding | 虚词驱动、噪声多；用 embedding + 重排 + 合理阈值 |
| 截断代替摘要、摘要不合并 | 不调用 LLM | 历史无界增长；用 LLM 滚动摘要并限制摘要预算 |
| 关键词子串意图分类 | 零依赖、可解释 | 误匹配多；用词边界、embedding 或分类模型 |
| 工具名代替工具定义计数 | 偷懒的写法 | 严重低估工具开销；记录真实定义的 token 数 |
| `assemble` 只返回预算 | 聚焦记账演示 | 不能直接对接模型；应返回拼接好的 messages |
| 模拟回复 | 无需 API | 无法观察压缩后模型的真实表现 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `collections.OrderedDict` | `self.allocations = OrderedDict()` | 记住插入顺序的字典（3.7+ 普通 dict 也有序） |
| 真值判断 | `if not text:`、`if max_tokens and tokens > max_tokens:` | 空串/None/0 都为假；注意 0 会被当作"没设置" |
| 元组返回与解包 | `return content, tokens`、`tools, tool_tokens = select_tools(...)` | 一次返回多个值 |
| `sum` + 生成器表达式 | `sum(count_tokens(t["content"]) for t in self.turns)` | 不建中间列表直接求和 |
| `dict.values()` | `sum(self.allocations.values())` | 对字典的所有值求和 |
| 切片步长 | `sorted_items[::2]`、`sorted_items[1::2]` | 取偶数位 / 奇数位元素 |
| `list.reverse()` | `second_half.reverse()` | 原地反转，返回 `None` |
| `sorted(zip(...), reverse=True)` | `sorted(zip(scores, items), reverse=True)` | 按元组第一项（分数）降序 |
| 推导式取元组元素 | `[item for _, item in paired]` | `_` 表示忽略的变量 |
| 集合运算 | `query_words & doc_words` | 交集 |
| `round` | `round(overlap, 3)` | 保留 3 位小数 |
| 列表切片重新赋值 | `self.turns = self.turns[2:]` | 去掉前两个元素 |
| 字典字面量嵌套 | `TOOL_REGISTRY = {"read_file": {"description": ..., "tokens": 120, ...}}` | 用字典存配置 |
| `any` + 生成器 | `any(cat in intents for cat in tool["categories"])` | 只要一个为真就为真 |
| `max(dict.values())` | `max_score = max(scores.values())` | 取最高分 |
| 子串判断 `in` | `kw in query_lower` | 字符串包含（不区分词边界） |
| `json.dumps` | `json.dumps(list(tools.keys()))` | 把列表序列化成 JSON 字符串 |
| 字符串乘法 | `"You are a helpful assistant. " * 20`、`"-" * 55` | 重复字符串 |
| 相邻字符串字面量拼接 | `self.system_prompt = ("You are ... " "code editing, ...")` | 括号内相邻字符串自动拼接 |
| 链式条件表达式 | `"START" if i < 2 else "END" if i >= len(reordered) - 2 else "middle"` | 一行写多分支 |
| f-string 格式符 | `{self.max_tokens:,}`、`{component:<25}`、`{tokens:>6}`、`{pct:>5.1f}`、`{position:>6}` | 千分位、左/右对齐、宽度与小数位 |
| f-string 中的单引号 | `f"{t['role']}: {content}"` | 外层双引号时内部用单引号取键 |
| `sorted(..., key=lambda x: -x[1])` | STEP 6 按分数降序打印 | 用取负实现降序 |
| `if __name__ == "__main__":` | 文件末尾依次调用 6 个演示 | 直接运行时执行，被 import 时不执行 |

---

## 6. 运行结果解读

实际运行（Python 3.13，瞬间完成）。

**STEP 1 预算管理器**：

```text
    system_prompt                130 tokens (  0.1%)    ← "You are a helpful assistant. " × 20 = 100 词 × 1.3
    tools                         13 tokens (  0.0%)    ← 10 个工具名的 JSON，真实定义是 1,580 token
    retrieved_docs               260 tokens (  0.2%)    ← 200 词 × 1.3
    history                      118 tokens (  0.1%)
    query                         11 tokens (  0.0%)
    Used                         532 tokens (0.4%)
    Remaining                 123468 tokens             ← 128,000 − 4,000 − 532
```

各组件都远低于上限，没有任何截断发生；百分比都低于 0.5%，所以条形图为空。

**STEP 2 重排**：输出顺序 A、F、E、C、G、B、D（标注 START ×2、middle ×3、END ×2），最不相关的 C(0.05)、G(0.10) 在中间。

**STEP 3 历史压缩**：

```text
  After turn 5:
    Live turns: 10, Summaries: 0, Tokens: 139
  Final context:
    [Recent Conversation]
    ...
```

上限 200，未触发压缩；最终上下文就是 10 条原文。

**STEP 4 工具选择**（全部工具 1,580 token）：

| 查询（截取） | 意图 | 选中工具数 | token | 备注 |
|------------|------|----------|-------|------|
| Fix the bug in auth.py... | code | 5 | 710 | `query_database` 也属于 code 类 |
| Schedule a meeting... | calendar | 1 | 180 | |
| Show me the database query performance stats... | data | 2 | 360 | |
| Search for best practices on error handling... | code, research | 6 | 850 | `error` 把它拉进了 code |
| Send an email... | email | 2 | 360 | |
| Read the config file and check for database... | code, data | 6 | 900 | |

节省比例为 43%–89%（例如日程查询 1,400/1,580 ≈ 89%），讲义说的 60–80% 是一个典型范围。

**STEP 5 完整组装**：

```text
  Query: Fix the bug in the authentication module where JWT tokens expire too early
    system_prompt                 41 tokens
    tools                          6 tokens      ← 实际选中 5 个工具，710 token
    retrieved_context             79 tokens      ← 6 条知识入选，其中 5 条只因共享 "the"
    conversation_history          20 tokens      ← 就是当前问题本身（chat 先写入历史）
    user_query                    16 tokens
  Query: What is the best approach for implementing vector search with PostgreSQL?
    retrieved_context            119 tokens      ← 10 条知识中入选 9 条
  Query: Schedule a team standup meeting for tomorrow morning
    tools                          1 tokens      ← '["create_calendar_event"]'
    retrieved_context             53 tokens      ← 4 条无关技术事实，全因 "for" 入选
  --- After building up conversation history ---
    conversation_history         284 tokens
  Conversation state: 20 live turns, 0 summaries, 302 tokens
```

`conversation_history` 在报告中是 284，而 `stats()` 给出 302：报告是在 `chat` 加入助手回复**之前**算的，`stats()` 是在之后算的。20 条、0 条摘要再次说明压缩没有被触发。

**STEP 6 相关性打分**：

```text
    * 0.200  Authentication is handled by Supabase Auth with JWT tokens....
    * 0.100  The project uses PostgreSQL 16 with pgvector ...       ← 只因 "the"
    * 0.100  The frontend is built with Next.js 15 ...              ← 只因 "the"
    * 0.100  The deployment pipeline uses GitHub Actions ...        ← 只因 "the"
  Threshold 0.05: 4 included, 4 excluded
  Token savings: ~80 tokens from excluded docs                     ← 硬编码每条 20 token
```

查询有 10 个词，命中 1 个就是 0.100。唯一真正相关的文档得分 0.200（命中 `jwt`、`authentication`；`token` 与 `tokens.` 因标点不匹配）。

---

## 7. 动手改一改

1. **让压缩真正发生**：把 STEP 3 的上限改为 80，观察 `Summaries` 何时从 0 变为非 0；再按测验 Q10 改成"滚动摘要 + 计入总量"，比较 30 条和 100 条消息时的 token 数。
2. **修复工具记账**：在 `assemble` 中用 `tool_tokens` 记账（可以直接写 `budget.allocations["tools"] = tool_tokens` 或给 `allocate` 增加 `tokens=` 参数），重跑 STEP 5，看各组件占比的变化。
3. **按优先级分配、按位置拼接**：实现测验 Q9 的 `assemble_by_priority`，返回拼接好的 prompt；在 `max_tokens=4150` 下确认用户问题完整保留、历史从尾部截断。
4. **讲义练习 1（token 浪费检测）**：给 `ContextBudget` 加 `waste_report()`，对占可用预算 30% 以上的组件给出针对性建议（历史→摘要、工具→裁剪、检索→重排）。
5. **讲义练习 2（语义去重）**：在检索内容入选后，两两计算词重叠率（或用上一节的 embedding cosine），> 0.8 只保留分数高的，统计回收的 token。
6. **讲义练习 4（按优先级选工具）**：给每个工具按"查询与描述的相关度"打分，降序加入直到预算用完；改用词边界匹配修掉 `prevent → event` 之类的误判。

---

## 8. 常见坑

- **用空格数估算中文 token**：结果接近 0，预算形同虚设。
- **按调用顺序分配预算**：最后分配的组件（往往是用户问题）最先被截断。
- **从开头截断对话历史**：留下最早的、丢掉最近的。
- **摘要只追加不合并**：摘要本身无限增长；判断是否超限时也要把摘要算进去。
- **把"截断前 100 字符"当摘要**：关键信息可能恰好在后面。
- **相关性打分不去停用词和标点**：`the`、`for` 主导结果，阈值又过低时，几乎所有文档都会被"检索"进来。
- **关键词子串匹配做意图分类**：`latest`→test、`prevent`→event、`sender`→send。
- **只记录工具名而非工具定义的 token 数**：严重低估工具开销。
- **当前问题既进历史又单独出现**：重复占用 token。
- **只算记账不拼 prompt**：预算报告看起来合理，但真正发给模型的内容从未被构造和检查过。
- **忘了生成预留**：窗口被输入塞满时模型无法完整回答。
