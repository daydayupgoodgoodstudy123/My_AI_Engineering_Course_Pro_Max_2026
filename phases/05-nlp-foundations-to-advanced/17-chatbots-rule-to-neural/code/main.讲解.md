# 代码讲解 · main.py

> **所属小节**：阶段 05 · NLP 从基础到进阶 · 第 17 节 聊天机器人——从规则系统到神经网络，再到 LLM Agents ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数） ｜ **依赖**：仅 Python 标准库（`re`；`collections.Counter` 被导入但未使用）；讲义中的 sentence-transformers、FLAN-T5 和 LLM agent 本文件都没有用到

---

## 1. 这份代码在考察什么

讲义讲了四代聊天机器人；这份代码把其中**不需要模型**的两代真的写出来，再用它们拼出 2026 年生产系统的"骨架"——混合路由：

1. **规则式（ELIZA 风格）**：正则模式 + 回复模板，理解"模式顺序 = 优先级"和"兜底规则"。
2. **检索式（FAQ）**：用 Jaccard 词集合相似度代替讲义中的 embedding，核心设计是**低于阈值就返回 `None`**，让上层升级处理。
3. **破坏性操作检测**：关键词闸门，把退款、取消、转账等请求交给确定性的结构化流程。
4. **混合路由**：破坏性 → 规则；能匹配 FAQ → 检索；其余 → LLM agent（这里只打印一句占位文字）。

> 一句话：**生产中的聊天机器人不是"一个模型"，而是一个路由器**——把每个请求交给最可控、最便宜、又能胜任的那条路径。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `RulePattern` | 类 | 保存编译好的正则（忽略大小写）和回复模板 | 规则 = 模式 + 模板 |
| `PATTERNS` | 常量列表 | 5 条规则：报名字、需要 / 想要、感觉、问候、兜底 | ELIZA 分解 / 重组规则 |
| `rule_based_respond(user_input)` | 函数 | 按顺序匹配，第一个命中的规则生成回复 | 规则式聊天机器人 |
| `FAQ` | 常量列表 | 4 组 (问法, 标准回答) | 检索式知识库 |
| `token_set(text)` | 函数 | 小写后抽取纯字母词，转成集合 | 词集合表示 |
| `faq_respond(user_input, threshold)` | 函数 | 求 Jaccard 最高的 FAQ，低于阈值返回 `None` | 检索 + 阈值拒答 |
| `is_destructive(text)` | 函数 | 子串匹配 5 个危险词 | 破坏性意图闸门 |
| `hybrid_respond(user_input)` | 函数 | 按"规则 → FAQ → agent"顺序路由，返回 (回复, 路由名) | 混合路由 |
| `main()` | 函数 | 两组演示：5 句 ELIZA 对话、4 句路由 | — |

调用关系：`hybrid_respond` 依次调用 `is_destructive` 和 `faq_respond`（后者用 `token_set`）；`rule_based_respond` 只在第一段演示中独立使用，**并不在混合路由里**。

---

## 3. 逐段精讲

### 3.1 `RulePattern` 与规则表

```python
class RulePattern:
    def __init__(self, pattern, template):
        self.regex = re.compile(pattern, re.IGNORECASE)
        self.template = template


PATTERNS = [
    RulePattern(r"my name is (\w+)", "Nice to meet you, {0}."),
    RulePattern(r"i (need|want) (.+)", "Why do you {0} {1}?"),
    RulePattern(r"i feel (.+)", "Why do you feel {0}?"),
    RulePattern(r"(hi|hello|hey)\b.*", "Hello. How can I help?"),
    RulePattern(r".*", "Tell me more about that."),
]
```

- `re.compile` 在构造时**预编译**正则，之后每次匹配不必重新解析；`re.IGNORECASE` 让 "My name is" 和 "my name is" 都能命中。
- 正则里的**捕获组** `( ... )` 就是 ELIZA 的"分解规则"：把用户话里的片段拆出来。模板里的 `{0}`、`{1}` 是"重组规则"：把片段按位置填回去。`"I feel tired"` → 捕获 `tired` → `"Why do you feel tired?"`，这就是讲义说的"反射技巧"。
- `(need|want)` 捕获了动词本身，所以模板能写 `Why do you {0} {1}?`，同一条规则覆盖两种说法。
- `(hi|hello|hey)\b.*`：`\b` 保证 `hi` 后面是单词边界，`"history"` 不会被当成问候。
- `.*` 是**兜底规则**，匹配任何输入，所以永远放最后。
- ⚠️ **顺序就是优先级**：问候规则的 `.*` 会吞掉后面的内容，`"Hey, I want coffee"` 只会得到 "Hello. How can I help?"。
- ⚠️ `(\w+)` 只捕获一个词：`"My name is Mary Jane"` → `Mary`。
- ⚠️ 没有代词反射：`"I need my password reset"` → `"Why do you need my password reset?"`（应为 your）。真正的 ELIZA 有一张 `my → your`、`I → you` 的替换表（见测验 Q9）。
- 与讲义 Step 1 相比，这里多了一条问候规则，且兜底规则从 `(.*)` 改成了不带捕获组的 `.*`。

### 3.2 `rule_based_respond`：第一个命中的规则胜出

```python
def rule_based_respond(user_input):
    for p in PATTERNS:
        m = p.regex.match(user_input.strip())
        if m:
            return p.template.format(*m.groups())
    return "I don't understand."
```

- `re.match` 只从**字符串开头**匹配（不要求匹配到结尾）。所以 `"I feel tired"` 会命中 `i feel (.+)`，但 `"Today I feel tired"` 不会，只能落到兜底。若想在句中任意位置找，用 `search`。
- `m.groups()` 返回所有捕获组组成的元组，`*m.groups()` 把它**展开**成 `format` 的位置参数。兜底规则没有捕获组，`groups()` 为空元组，模板里也没有占位符，正好对得上。
- `.strip()` 去掉首尾空白，避免 `"  hi"` 匹配失败。
- ⚠️ 因为 `.*` 兜底永远命中，最后一行 `return "I don't understand."` 实际上**不可达**，只是防御性写法。

### 3.3 FAQ 检索：Jaccard + 阈值

```python
def token_set(text):
    return set(re.findall(r"[a-z]+", text.lower()))


def faq_respond(user_input, threshold=0.3):
    user_tokens = token_set(user_input)
    best_score = 0.0
    best_answer = None
    for question, answer in FAQ:
        q_tokens = token_set(question)
        if not q_tokens or not user_tokens:
            continue
        jaccard = len(user_tokens & q_tokens) / len(user_tokens | q_tokens)
        if jaccard > best_score:
            best_score = jaccard
            best_answer = answer
    if best_score < threshold:
        return None, best_score
    return best_answer, best_score
```

- `token_set` 只保留字母（`[a-z]+`），数字和标点都被丢掉；`what's` 会变成 `what` 和 `s`。用 `set` 表示"出现了哪些词"，不关心次数和顺序。
- **Jaccard** = `|交集| / |并集|`，范围 [0, 1]。`"how do i reset my password"` 与 FAQ 完全相同 → 1.00。
- 空集保护：任一方没有词就跳过，避免除零。
- 用"打擂台"方式找最大值：`jaccard > best_score` 才更新，所以并列时保留先出现的那条。
- **阈值拒答**：讲义说这是"关键设计选择"——最佳匹配不够近就返回 `None`，让上层升级（这里是交给 agent）。函数总是返回 `(answer, score)` 二元组，即使拒答也把分数带出去，方便日志和调参。
- ⚠️ **虚词同权**：`"how do i track my order"` 与 `"how do i cancel my order"` 的 Jaccard 高达 5/7 ≈ 0.71，会把"查物流"的用户引导去"取消订单"。关键动词只占一票，`how / do / i / my` 占四票。讲义 Step 2 用 embedding 正是为了缓解这个问题；即使用 embedding，也要在验证集上调阈值（讲义示例 0.5，混合路由里用 0.6）。

### 3.4 `is_destructive`：关键词闸门

```python
def is_destructive(text):
    danger_words = ["delete", "cancel", "charge", "refund", "transfer"]
    return any(w in text.lower() for w in danger_words)
```

- `any(... for ...)`：只要有一个危险词出现就返回 `True`，并且找到后立即停止（短路求值）。
- ⚠️ `w in text.lower()` 是**子串**判断：`"discharge summary"` 含 `charge` → 误判为破坏性。应改用词边界正则 `\bcharge\b`（见测验 Q10）。
- ⚠️ 关键词列表注定漏报：`"close my account"`、`"wire money"`、拼写错误、其他语言都检测不到。讲义说路由层"通常是一个小的意图分类器"，关键词只适合做高精度的第一道闸门。
- 设计倾向：对破坏性意图**宁可误报**（多走一次确认流程）也不要漏报（让 LLM 直接执行退款）。

### 3.5 `hybrid_respond`：路由顺序就是安全策略

```python
def hybrid_respond(user_input):
    if is_destructive(user_input):
        return "Destructive action detected. Routing to structured confirmation flow.", "rule"

    answer, score = faq_respond(user_input)
    if answer:
        return f"{answer}  (faq match={score:.2f})", "faq"

    return f"(would call LLM agent for: {user_input!r})", "agent"
```

- **顺序是刻意的**：最危险的先判（确定性规则），最便宜可靠的其次（FAQ），最灵活也最难控制的放最后（agent）。与讲义 Step 5 的 `hybrid_chat` 一致。
- 返回 `(回复, 路由名)` 二元组，路由名用于日志和评估——生产中你需要知道每个请求走了哪条路。
- `if answer:`：`faq_respond` 拒答时返回 `None`，`None` 为假值，于是落到 agent。
- ⚠️ 副作用：FAQ 里的 `"how do i cancel my order"` **永远到达不了**，因为含 `cancel` 的输入都先被 `is_destructive` 截走。这可能是有意的（取消本就应走确认），但配置里保留一条不可达的 FAQ 会误导维护者。
- agent 路径只是占位：`{user_input!r}` 用 `repr` 打印，字符串会带引号，便于在日志里看清首尾空格等细节。真实实现见讲义 Step 4 的 `agent_loop`。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 正则规则 + 模板 | 完全可控、可解释、零幻觉 | 覆盖面有限、规则互相"截胡"；生产中只用于认证、支付等窄流程 |
| 兜底规则 `.*` | 保证总有回复 | 回复空洞；生产中应转人工或交给 agent |
| Jaccard 代替 embedding | 零依赖、能跑通流程 | 虚词同权、不懂语义；生产用 sentence-transformers + 在验证集上调的阈值 |
| FAQ 低于阈值返回 `None` | 不确定就不答，交给上层 | 阈值需要调；还应检查 top-1 与 top-2 的分差 |
| 子串关键词判破坏性 | 简单、高召回 | 误报（discharge）和漏报（close account）；生产用意图分类器 + 词边界规则 |
| 路由顺序：规则 → FAQ → agent | 风险从高到低、成本从低到高 | 规则层会"吃掉"部分 FAQ；需要显式维护路由表 |
| 返回 `(回复, 路由名)` | 便于日志、评估和调试 | — |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 类与 `__init__` | `class RulePattern: def __init__(self, pattern, template)` | 用类把"正则 + 模板"打包成一个对象 |
| `re.compile` + 标志 | `re.compile(pattern, re.IGNORECASE)` | 预编译正则；忽略大小写 |
| 正则捕获组与或 | `r"i (need\|want) (.+)"` | `( )` 捕获片段，`\|` 表示或 |
| 单词边界 `\b` | `r"(hi\|hello\|hey)\b.*"` | 匹配单词边界，防止 `history` 被当成 `hi` |
| `regex.match` vs `search` | `p.regex.match(user_input.strip())` | `match` 只从开头匹配；`search` 在任意位置找 |
| `m.groups()` + 星号展开 | `template.format(*m.groups())` | 把元组展开成位置参数 |
| `str.format` 位置占位符 | `"Why do you {0} {1}?"` | `{0}` 对应第一个参数 |
| `re.findall` | `re.findall(r"[a-z]+", text.lower())` | 返回所有匹配子串 |
| 集合运算 | `user_tokens & q_tokens`、`user_tokens \| q_tokens` | 交集、并集 |
| 元组解包遍历 | `for question, answer in FAQ` | 每个元素是二元组 |
| 多返回值 | `return None, best_score` / `answer, score = faq_respond(...)` | 返回元组并解包 |
| `any` + 生成器 | `any(w in text.lower() for w in danger_words)` | 有一个为真即为真，短路求值 |
| 子串判断 `in` | `w in text.lower()` | 字符串包含关系（注意不是"整词"） |
| `None` 的真值 | `if answer:` | `None` 和空字符串都为假 |
| f-string 格式符 | `f"{score:.2f}"`、`f"{user_input!r}"`、`f"[{route:5s}]"` | 两位小数；`repr`；宽度 5 左对齐 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行演示 |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，Python 3.13）输出：

```text
=== rule-based ELIZA-style ===
  user : Hi there
  bot  : Hello. How can I help?
  user : My name is Alex
  bot  : Nice to meet you, Alex.
  user : I want coffee
  bot  : Why do you want coffee?
  user : I feel tired
  bot  : Why do you feel tired?
  user : The sky is blue
  bot  : Tell me more about that.

=== hybrid routing ===
  [faq  ] how do i reset my password
           -> Go to Settings > Security > Reset Password.  (faq match=1.00)
  [rule ] cancel my order
           -> Destructive action detected. Routing to structured confirmation flow.
  [agent] what's the weather like
           -> (would call LLM agent for: "what's the weather like")
  [rule ] I want a refund
           -> Destructive action detected. Routing to structured confirmation flow.
```

**规则部分**：五句话恰好各命中一条规则——问候、报名字、want、feel、兜底。演示输入是精心挑选的"舒适区"；换成 `"Hey, I want coffee"`、`"My name is Mary Jane"`、`"I need my password reset"`，就会分别暴露规则截胡、捕获不全、缺少代词反射三个问题（已实测）。

**路由部分**：

- `how do i reset my password`：与 FAQ 完全一致，Jaccard = 1.00 → faq。
- `cancel my order`：含 `cancel` → rule。注意 FAQ 里明明有"如何取消订单"的答案，但路由根本没走到 FAQ。
- `what's the weather like`：词集合 `{what, s, the, weather, like}` 与所有 FAQ 都没有交集，分数 0 < 0.3 → agent。`f"{user_input!r}"` 因为字符串里有单引号，`repr` 自动改用双引号包裹。
- `I want a refund`：含 `refund` → rule。

额外探测（已实测）：`"discharge summary please"` 被误判为 rule；`"how do i track my order"` 以 0.71 的分数匹配到"取消订单"的答案；`"where is my order"` 与 `"when will my order arrive"` 的 Jaccard 只有 0.29，低于阈值，反而交给了 agent——词面相似度在"该匹配的没匹配、不该匹配的匹配上"两头都会出错。

---

## 7. 动手改一改

1. **代词反射**：加一张 `{"i": "you", "my": "your", "am": "are", ...}` 替换表，对捕获组逐词替换后再填模板。
2. **规则顺序**：把问候规则改成 `(hi|hello|hey)\b[\s,!.]*$`（只匹配纯问候），让 `"Hey, I want coffee"` 落到 want 规则（提示：还要处理开头的 "Hey,"）。
3. **修 `is_destructive`**：用 `\b...\b` 词边界正则，测试 `discharge`、`cancelled`、`Refund`。
4. **FAQ 去停用词**：在 `token_set` 中去掉 `how / do / i / my / the`，重新计算 `"how do i track my order"` 的分数，看看是否还会误匹配。
5. **加状态**：仿照 PARRY，给机器人加一个 `frustration` 计数器，用户连续 2 次落到兜底规则就回复"要不要我帮你转人工？"。
6. **接 agent**：用讲义 Step 4 的 `agent_loop` 替换占位文字（需要一个能做 tool call 的 LLM），并给破坏性工具加确认步骤。

---

## 8. 常见坑

- **规则顺序写反**：宽泛的规则（`.*`、问候 + `.*`）放在前面，会吞掉所有更具体的规则。
- **`match` 和 `search` 混用**：`match` 只看开头，句中出现的模式匹配不到。
- **子串关键词**：`"charge" in "discharge"` 为真；整词匹配要用 `\b`。
- **词面相似度把关键动词淹没**：`track` vs `cancel` 只差一个词，Jaccard 却很高；FAQ 检索至少要去停用词或换 embedding。
- **路由层"吃掉"下游配置**：FAQ 中含 `cancel` 的条目永远不可达，配置与行为不一致。
- **把占位的 agent 当真**：这里只是打印一句话；真实的 agent 需要步数预算、工具校验、异常处理、破坏性操作确认和注入防御。
