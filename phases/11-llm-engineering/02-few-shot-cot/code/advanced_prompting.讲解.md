# 代码讲解 · advanced_prompting.py

> **所属小节**：阶段 11 · LLM 工程 · 第 02 节 Few-Shot, Chain-of-Thought, Tree-of-Thought ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`OPENAI_API_KEY=sk-... LLM_MODEL=gpt-4o python advanced_prompting.py` ｜ **依赖**：第三方 `openai`（OpenAI Python SDK）+ 标准库 `json`、`re`、`os`、`collections.Counter`；**需要有效的 OpenAI API key 和网络**

---

## 1. 这份代码在考察什么

这是一个 GSM8K 风格数学应用题求解器，把讲义中的推理策略逐一实现并放进同一条流水线：

1. **Prompt 构建**：zero-shot、zero-shot CoT（"Let's think step by step"）、few-shot CoT（示例带推理过程）、XML 结构化提示。
2. **答案抽取**：`extract_answer` 用正则从自由文本中取出最终数字，是投票与评测的基础。
3. **Self-consistency**：温度 0.7 采样 5 次，多数投票并计算置信度。
4. **Tree-of-Thought**：生成多个初始思路 → LLM 自评分 → 保留前 2 个扩展 → 再评分。
5. **ReAct**：Thought / Action: calculate / Observation / Answer 循环，配一个 `eval` 计算器。
6. **Prompt chaining**：抽取事实 → 求解 → 验证三步链。
7. **升级策略**与**方法对比**：`solve_with_escalation`、`run_comparison`。

> 一句话：**同一个模型、同一道题，换一种"让模型思考的方式"，准确率和成本就不同——这份代码把每种方式都写成了可调用的函数**。但要注意：答案抽取器会把句末句号吞进数字，导致评测把正确答案判错；ReAct 的 `eval` 也不是沙箱。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `GSM8K_EXAMPLES` | 列表（5 个字典） | few-shot 示例：`question / reasoning / answer` | few-shot CoT 示例库 |
| `extract_answer` | 函数 | 正则抽取最终数字 | 答案格式化 |
| `build_cot_prompt` / `build_zero_shot_cot_prompt` / `build_zero_shot_prompt` | 函数 | 构造三种 (system, user) | few-shot CoT / zero-shot CoT / zero-shot |
| `call_llm` | 函数 | 封装一次 OpenAI Chat Completions 调用 | API 调用 |
| `zero_shot_solve` / `zero_shot_cot_solve` / `few_shot_cot_solve` | 函数 | 温度 0 单次求解 | 三种基线 |
| `self_consistency_solve` | 函数 | 温度 0.7 采样 N 次 + `Counter` 投票 | Self-consistency |
| `generate_initial_thoughts` / `evaluate_thought` / `extend_thought` / `tree_of_thought_solve` | 函数 | 生成、评分、扩展、束搜索 | Tree-of-Thought |
| `react_solve` | 函数 | 多轮 messages + 正则解析 Action/Answer + `eval` | ReAct |
| `solve_with_escalation` | 函数 | 贪心 CoT + SC，不达标则 ToT | 升级策略 |
| `run_comparison` | 函数 | 四种方法逐题比较并汇总准确率 | 方法对比 |
| `build_structured_prompt` | 函数 | XML 标签组织的 system + user（未被调用） | 结构化提示 |
| `prompt_chain_solve` | 函数 | 抽取 → 求解 → 验证 | Prompt chaining |
| `TEST_QUESTIONS` | 列表（5 题） | 测试题与标准答案 | 评测集 |

数据流：`__main__` 读取环境变量建 `OpenAI` client → `run_comparison`（5 题 × 4 种方法）→ 前 2 题跑 `solve_with_escalation` → 前 2 题跑 `prompt_chain_solve` → 前 2 题跑 `react_solve`。

---

## 3. 逐段精讲

### 3.1 few-shot 示例库

```python
GSM8K_EXAMPLES = [
    {
        "question": ("Janet's ducks lay 16 eggs per day. ... She sells every remaining egg ..."),
        "reasoning": ("Janet's ducks lay 16 eggs per day. She eats 3 and bakes with 4, "
                      "using 3 + 4 = 7 eggs. So she has 16 - 7 = 9 eggs left. "
                      "She sells each for $2, so she makes 9 * 2 = $18 per day."),
        "answer": "18",
    },
    ...
```

- 每个示例三段：题目、推理链、答案。讲义："The reasoning chain is what transforms a regular few-shot example into a CoT few-shot example."
- 代码题干写的是 "every remaining egg"，比讲义节选的 "every egg" 更严谨（"every egg" 会让 16 个蛋全部出售，题意矛盾）。
- 前三个示例（Janet 18、robe 3、Josh 70000）推理清晰且答案正确。
- ⚠️ 第 4 个示例（James 写信，624）与 `TEST_QUESTIONS[4]` **完全相同**；第 5 个示例（Wendi 喂鸡）题目被改成 "carry-over 35 cups"，缺少鸡的数量，推理文本反复自我否定，最后基于"三餐等量"的错误假设得出 5。默认 `num_examples=3` 时这两个示例不会进入 prompt；一旦改成 5，就会出现测试集泄漏和"坏示范"（测验 Q10）。

### 3.2 答案抽取

```python
def extract_answer(text):
    if not text:
        return None
    patterns = [
        r"[Tt]he answer is[:\s]*\$?([\d,]+\.?\d*)",
        r"[Tt]he answer is[:\s]*([\d,]+\.?\d*)",
        r"#### ([\d,]+\.?\d*)",
        r"= \$?([\d,]+\.?\d*)\s*$",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).replace(",", "")
    numbers = re.findall(r"[\d,]+\.?\d*", text)
    if numbers:
        return numbers[-1].replace(",", "")
    return None
```

- 按优先级尝试：`The answer is N`（可带 `$`、冒号）→ GSM8K 标准答案标记 `#### N` → 文本末尾的 `= N` → 兜底取最后一个数字。`.replace(",", "")` 去掉千分位。
- `[\d,]+\.?\d*`：一串数字/逗号，可选小数点，可选小数部分。
- ⚠️ **最严重的 bug**：`\.?` 会贪婪地匹配句末句号。`"The answer is 72."` → `'72.'`，`"The answer is 70,000."` → `'70000.'`（已实测）。而 few-shot 示例恰好以 `The answer is 70000.` 结尾，模型照格式输出时，`run_comparison` 的字符串比较会把正确答案判错；self-consistency 中 `'72'` 与 `'72.'` 会被计为不同答案。
- 其他问题：不支持负数（`-5` → `'5'`）；兜底正则能匹配单独的逗号（`"Hello, world"` → `''`）；第二个正则是第一个的子集，永远用不到；第四个正则的 `$` 只匹配全文末尾。
- 修正：数字正则改为 `-?\d[\d,]*(?:\.\d+)?`（小数点后必须有数字），并把结果归一化为数值再比较（测验 Q9 给出了完整实现）。

### 3.3 三种 prompt 构建

```python
def build_cot_prompt(question, examples, num_examples=3):
    system = (
        "You are a precise math problem solver. "
        "For each problem, show your step-by-step reasoning clearly. "
        "After your reasoning, state your final answer on the last line "
        "in exactly this format: 'The answer is [number]'."
    )
    example_text = ""
    for ex in examples[:num_examples]:
        example_text += f"Q: {ex['question']}\n"
        example_text += f"A: {ex['reasoning']} The answer is {ex['answer']}.\n\n"
    user = f"{example_text}Q: {question}\nA:"
    return system, user
```

- system 规定输出格式；user 是 "Q:/A:" 交替的示例，最后以 `Q: 目标题\nA:` 结尾，让模型"接着写答案"。
- 讲义强调格式约束的关键作用："Without it, self-consistency cannot extract and compare answers across samples."
- 注意示例末尾 `The answer is {ex['answer']}.` 带句号——这正是 3.2 中 bug 被触发的来源。
- `examples[:num_examples]` 只取前 n 个，**按列表顺序**而不是按与目标题的相似度选择；讲义推荐的语义相似选择（如 LangChain 的 `SemanticSimilarityExampleSelector`）没有实现。

```python
def build_zero_shot_cot_prompt(question):
    ...
    user = f"Q: {question}\nA: Let's think step by step."

def build_zero_shot_prompt(question):
    system = (... "Give only the final numerical answer. " "End with: 'The answer is [number]'.")
```

- zero-shot CoT 把触发语放在 `A:` 之后，相当于"替模型说出第一句"，这是 Kojima 等论文的原始用法。
- zero-shot 要求"只给最终答案"，作为没有推理过程的对照组。

### 3.4 API 调用与三个基线

```python
def call_llm(client, model, system, user, temperature=0.0):
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=temperature,
        max_tokens=1024,
    )
    return response.choices[0].message.content
```

- 所有函数都通过它调用模型（`react_solve` 除外，它需要多轮 messages）。`max_tokens=1024` 给推理留足空间。
- 没有重试、超时、限流处理；网络失败会直接抛异常中断整个程序（我们在无网络环境下运行即是如此）。
- 三个 `*_solve` 都是温度 0 的单次调用，返回 `(答案, 原文)` 元组。

### 3.5 Self-consistency

```python
def self_consistency_solve(question, examples, client, model, n_samples=5):
    system, user = build_cot_prompt(question, examples)
    answers = []
    reasonings = []
    for _ in range(n_samples):
        text = call_llm(client, model, system, user, temperature=0.7)
        reasonings.append(text)
        answer = extract_answer(text)
        if answer is not None:
            answers.append(answer)
    if not answers:
        return None, 0.0, reasonings, Counter()
    vote_counts = Counter(answers)
    best_answer = vote_counts.most_common(1)[0][0]
    confidence = vote_counts[best_answer] / len(answers)
    return best_answer, confidence, reasonings, vote_counts
```

- 同一个 prompt 采样 5 次（温度 0.7），抽取答案后用 `Counter.most_common(1)` 取票数最多者。
- 置信度 = 最高票数 / **成功抽取的答案数**。无法抽取的样本被静默丢弃，例如 `["72","72","72",None,"70"]` 的置信度是 3/4 = 0.75（测验 Q3）。
- 平票时 `most_common` 返回先出现的那个答案（`Counter` 保持插入顺序），相当于"先到先得"。
- 比讲义版本多了 `if not answers` 的保护，避免对空 `Counter` 取 `[0][0]` 时报 `IndexError`。
- 5 次调用是**串行**的；生产中应并发发送，或使用支持 `n` 参数一次返回多个候选的接口以节省 prompt 的重复计费。

### 3.6 Tree-of-Thought

```python
def generate_initial_thoughts(question, client, model, breadth=3):
    ...
    for i in range(breadth):
        user = (f"Problem: {question}\n\n"
                f"Generate approach #{i + 1} (use a different strategy than previous approaches). ...")
        text = call_llm(client, model, system, user, temperature=0.9)
```

- 用高温度（0.9）独立生成 3 个"部分推理"。
- ⚠️ 提示说"与之前的方法不同"，但之前生成的思路**并没有**放进 prompt，模型看不到它们，多样性只能靠温度。

```python
def evaluate_thought(thought, question, client, model):
    ...
    text = call_llm(client, model, system, user, temperature=0.0)
    try:
        score = float(re.search(r"([\d.]+)", text).group(1))
        return min(max(score, 0.0), 1.0)
    except (AttributeError, ValueError):
        return 0.5
```

- 让同一个模型给部分推理打 0–1 分——讲义说这是 ToT 的关键洞见："the model evaluates its own partial solutions"。
- 解析取回复中第一个"数字或点"串并截断到 [0, 1]；`re.search` 无匹配时 `.group` 会抛 `AttributeError`，`float(".")` 抛 `ValueError`，都回退到 0.5。实测："Score: 0.85" → 0.85；"8/10" → 8 被截断为 1.0（误判为满分）；"about 0.9 or 0.95" → 0.9。

```python
def tree_of_thought_solve(question, client, model, breadth=3, depth=3):
    thoughts = generate_initial_thoughts(question, client, model, breadth)
    scored = [(t, evaluate_thought(t, question, client, model)) for t in thoughts]
    scored.sort(key=lambda x: x[1], reverse=True)
    for current_depth in range(1, depth):
        next_thoughts = []
        top_k = min(2, len(scored))
        for thought, score in scored[:top_k]:
            extensions = extend_thought(thought, question, client, model, breadth)
            for ext in extensions:
                ext_score = evaluate_thought(ext, question, client, model)
                next_thoughts.append((ext, ext_score))
        if next_thoughts:
            scored = sorted(next_thoughts, key=lambda x: x[1], reverse=True)
    best_thought = scored[0][0] if scored else ""
    return extract_answer(best_thought), best_thought
```

- 这是**束宽为 2 的 beam search**（BFS 的剪枝版本）：每层只保留得分最高的 2 个节点，各扩展 `breadth` 个子节点并评分。
- `extend_thought` 返回的是"父思路 + 新续写"的拼接文本，所以节点保存了从根到自己的完整路径。
- 调用次数（实测）：`depth=3` 为 30 次，`depth=2`（升级流程里用的）为 18 次。讲义说"分支 3、深度 3 最多 39 次"，那是不剪枝、只算生成的上限（测验 Q11）。
- 最终答案用 `extract_answer` 从最佳路径中取；如果该路径还没写到 "The answer is"，就会退回"最后一个数字"，可能是中间结果。
- 与讲义版本相比，增加了 `top_k = min(2, len(scored))` 和 `if next_thoughts` 两处保护。

### 3.7 ReAct

```python
def react_solve(question, client, model, max_steps=5):
    system = ("... For each step, output exactly one of:\n"
              "Thought: [your reasoning]\n" "Action: calculate [expression]\n" "Answer: [final number]\n\n" ...)
    messages = [{"role": "system", "content": system}, {"role": "user", "content": f"Q: {question}\n"}]
    for step in range(max_steps):
        response = client.chat.completions.create(model=model, messages=messages, temperature=0.0, max_tokens=512)
        text = response.choices[0].message.content.strip()
        messages.append({"role": "assistant", "content": text})
        answer_match = re.search(r"Answer:\s*\$?([\d,]+\.?\d*)", text)
        if answer_match:
            return answer_match.group(1).replace(",", ""), text
        calc_match = re.search(r"Action:\s*calculate\s+(.+)", text)
        if calc_match:
            expression = calc_match.group(1).strip()
            try:
                result = eval(expression, {"__builtins__": {}}, {})
                observation = f"Observation: {result}"
            except Exception as e:
                observation = f"Observation: Error - {e}"
            messages.append({"role": "user", "content": observation})
    ...
```

- 多轮对话：模型的每一步追加为 assistant 消息，工具结果以 `Observation:` 作为 user 消息追加，形成 Thought–Action–Observation 循环。
- 先检查 Answer 再检查 Action：同一条回复里两者都有时以 Answer 为准。
- `(.+)` 不跨行，只取 `calculate` 后同一行的内容。
- ⚠️ `eval` 清空 `__builtins__` **不是沙箱**：`().__class__.__base__.__subclasses__()` 这类属性链仍可执行（已实测），`9**9**9` 可让进程卡死。应改用基于 `ast` 的白名单计算器（测验 Q12）。
- ⚠️ `12*50/60` 得到 `10.0`，模型照抄后返回 `'10.0'`，与期望 `'10'` 字符串比较判错；Answer 正则同样会吞掉句末句号。
- ⚠️ 只有 Thought 时不追加任何消息，下一轮请求与上一轮几乎相同，温度 0 下容易原地打转直到 `max_steps`（实测返回 `None`）。
- 讲义说这一节只讲"提示模式"层面的 ReAct，完整 agent 在第 14 阶段。

### 3.8 升级策略

```python
def solve_with_escalation(question, examples, client, model):
    single_answer, _ = few_shot_cot_solve(question, examples, client, model)
    sc_answer, confidence, reasonings, votes = self_consistency_solve(question, examples, client, model, n_samples=5)
    if confidence >= 0.8 and single_answer == sc_answer:
        return {"answer": sc_answer, "method": "self_consistency", "confidence": confidence, ...}
    tot_answer, tot_reasoning = tree_of_thought_solve(question, client, model, breadth=3, depth=2)
    return {"answer": tot_answer, "method": "tree_of_thought", "confidence": None, ...}
```

- 通过条件：5 次采样中至少 80%（≥4 个有效答案中的多数）一致，**并且**与温度 0 的贪心答案一致。讲义解释：单条贪心路径没有票数，所以用"与多数一致"来检验它。
- ⚠️ 讲义说"try cheap (single CoT) first"，但代码无条件地先跑 1 + 5 = 6 次调用，没有"贪心就够了"的早退分支；最坏情况 24 次调用。
- ⚠️ 升级后完全丢弃 self-consistency 的结果，ToT 答案即使更不可靠也会被采用；返回的 `votes` 只是附带信息。

### 3.9 方法对比

```python
def run_comparison(questions, expected_answers, examples, client, model):
    methods = {
        "zero_shot": lambda q: zero_shot_solve(q, client, model),
        ...
        "self_consistency": lambda q: (self_consistency_solve(q, examples, client, model, n_samples=5)[:2]),
    }
    results = {name: {"correct": 0, "total": 0} for name in methods}
    for i, (question, expected) in enumerate(zip(questions, expected_answers)):
        for name, solver in methods.items():
            answer, *_ = solver(question)
            is_correct = str(answer) == str(expected)
```

- 用字典把方法名映射到 `lambda`，`lambda` **闭包**捕获了 `client`、`model`、`examples`。
- `self_consistency_solve(...)[:2]` 只取前两个返回值，与其他方法的 `(answer, text)` 形状对齐；`answer, *_ = ...` 用星号解包丢弃其余部分。
- ⚠️ `str(answer) == str(expected)` 是字符串严格比较，配合 3.2 的抽取 bug，`'72.' != '72'`。我们用一个总回答 "... The answer is 72." 的模拟 client 实测：四种方法全部判错，准确率 0.0%。
- 每题共 1 + 1 + 1 + 5 = 8 次调用，5 题共 40 次。

### 3.10 结构化提示与 prompt chaining

```python
def build_structured_prompt(question, context=None):
    system = """<role>
You are a precise mathematical problem solver with expertise in word problems.
</role>
<rules>
...
</rules>
<output_format>
...
</output_format>"""
    user_parts = []
    if context:
        user_parts.append(f"<context>\n{context}\n</context>")
    user_parts.append(f"<problem>\n{question}\n</problem>")
    return system, "\n\n".join(user_parts)
```

- 用 XML 标签把角色、规则、输出格式、上下文、题目分开，对应讲义 "Structured Prompting"。三引号字符串保留换行。该函数在 `__main__` 中没有被调用。

```python
def prompt_chain_solve(question, client, model):
    facts = call_llm(client, model, extract_system, question, temperature=0.0)
    solution = call_llm(client, model, solve_system, f"Facts:\n{facts}\n\nOriginal problem: {question}", temperature=0.0)
    verified = call_llm(client, model, verify_system, f"Problem: {question}\n\nProposed solution:\n{solution}", temperature=0.0)
    return extract_answer(verified), {"facts": facts, "solution": solution, "verification": verified}
```

- 三步链：抽取数值与关系 → 基于事实求解 → 把答案代回原题验证。中间结果都保存在返回的字典里，便于检查——这正是讲义说的 chaining 优点 "Intermediate outputs are inspectable"。
- 求解步骤同时给了"抽取的事实"和"原题"，防止抽取遗漏导致信息丢失。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 统一要求 "The answer is N" | 让投票与评测可以自动抽取答案 | 正则脆弱（句号、负数）；生产中用结构化输出（JSON 字段）或更严格的解析 + 数值归一化 |
| 示例按列表顺序取前 3 个 | 简单、可复现 | 没有按相似度选择；示例库需与测试集去重 |
| SC 温度 0.7、N=5 | 讲义经验值 | 成本 5 倍；可用自适应早停 |
| ToT 束宽固定为 2、LLM 自评分 | 控制调用次数 | 自评分有偏、解析脆弱；评估可换成更强模型或可验证的规则 |
| ReAct 用文本正则解析 + `eval` | 不依赖 function calling 也能演示循环 | 不安全、易解析失败；生产用结构化 tool calling + 白名单工具 |
| 升级：贪心 + SC 都跑完再判断 | 逻辑直观 | 每题至少 6 次调用；应先便宜后昂贵并早退 |
| 字符串比较判对错 | 简单 | 必须数值归一化 |
| 串行调用、无重试 | 代码短 | 生产需并发、超时、重试、限流与缓存 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 相邻字符串自动拼接 | `("You are a precise math problem solver. " "For each problem, ...")` | 括号内多个字面量在编译期拼接 |
| 三引号多行字符串 | `system = """<role>\n...\n</output_format>"""` | 保留换行，适合写大段 prompt |
| f-string 取字典值 | `f"Q: {ex['question']}\n"` | 花括号内用与外层不同的引号 |
| f-string 格式符 | `{name:20s}`、`{acc:.1f}%` | 字符串占 20 宽；保留 1 位小数 |
| 正则 `re.search` / `re.findall` / `.group(1)` | `re.search(pattern, text).group(1)` | 取第一个捕获组；`findall` 返回所有匹配 |
| 原始字符串 | `r"[Tt]he answer is[:\s]*\$?([\d,]+\.?\d*)"` | 反斜杠不被 Python 转义 |
| `collections.Counter` | `Counter(answers).most_common(1)[0][0]` | 计数并取出现最多的元素 |
| `try / except` 多异常 | `except (AttributeError, ValueError): return 0.5` | 解析失败时给默认值 |
| `min(max(x, 0.0), 1.0)` | `evaluate_thought` | 把数值截断到区间 |
| 列表推导式 | `[(t, evaluate_thought(t, ...)) for t in thoughts]` | 生成 (思路, 分数) 列表 |
| `sort` 与 `sorted` + `lambda` | `scored.sort(key=lambda x: x[1], reverse=True)` | 原地排序 / 返回新列表 |
| 切片 | `examples[:num_examples]`、`scored[:top_k]`、`(...)[:2]` | 取前若干个 |
| 字典推导式 | `{name: {"correct": 0, "total": 0} for name in methods}` | 为每个方法初始化计数器 |
| `lambda` 闭包 | `"zero_shot": lambda q: zero_shot_solve(q, client, model)` | 捕获外层变量，统一成单参数函数 |
| 星号解包 | `answer, *_ = solver(question)` | 取第一个，其余丢进 `_` |
| `zip` + `enumerate` | `for i, (question, expected) in enumerate(zip(questions, expected_answers)):` | 同时遍历两个列表并计数 |
| `eval` 带受限命名空间 | `eval(expression, {"__builtins__": {}}, {})` | 第二、三个参数是全局/局部命名空间；**不等于安全沙箱** |
| 生成器表达式 + `join` | `"\n".join(m["content"] for m in messages if m["role"] == "assistant")` | 拼接所有 assistant 消息 |
| `os.environ.get` | `os.environ.get("OPENAI_API_KEY", "your-api-key")` | 读环境变量，带默认值 |
| `if __name__ == "__main__":` | 文件末尾 | 被 import 时不会发起任何 API 调用（本讲解正是 import 后用模拟 client 做实验） |

---

## 6. 运行结果解读

**未能完整运行，原因：需要 `OPENAI_API_KEY` 和访问 OpenAI API 的网络。** 我们安装了 `openai` SDK 后直接运行，程序打印标题和第一题后，在第一次 API 调用处抛出 `openai.APIConnectionError: Connection error.` 退出：

```text
============================================================
ADVANCED PROMPTING PIPELINE
Few-Shot + CoT + Self-Consistency + Tree-of-Thought
============================================================

--- Technique Comparison ---

Problem 1: Natalia sold clips to 48 of her friends in April, and then s...
Traceback (most recent call last):
  ...
openai.APIConnectionError: Connection error.
```

真实模型的准确率无法给出，以下**不是**真实模型输出，而是我们 `import` 本文件后，用一个只实现了 `client.chat.completions.create` 的**模拟 client** 离线调用各函数得到的结果，用来验证代码逻辑：

**① 答案抽取（直接调用 `extract_answer`）**

```text
'The answer is 18.'        -> '18.'      ← 句号被吞进数字
'The answer is $18'        -> '18'
'The answer is 70,000.'    -> '70000.'
'The answer is: 10.50'     -> '10.50'
'The answer is -5'         -> '5'        ← 丢了负号
'Hello, world'             -> ''         ← 匹配到单独的逗号
'#### 72'                  -> '72'
```

**② 评测（模拟 client 总是回答 "48/2 = 24. 48 + 24 = 72. The answer is 72."）**

```text
Problem 1: Natalia sold clips to 48 of her friends in April, and then s...
  zero_shot           : WRONG (got 72., expected 72)
  zero_shot_cot       : WRONG (got 72., expected 72)
  few_shot_cot        : WRONG (got 72., expected 72)
  self_consistency    : WRONG (got 72., expected 72)
ACCURACY SUMMARY
  zero_shot           : 0.0% (0/1)
  ...
```

答案明明正确，却因 `'72.' != '72'` 被全部判错，一题共调用了 8 次模型（1+1+1+5）。

**③ 调用次数（计数模拟 client）**：`tree_of_thought_solve(depth=3)` 30 次；`depth=2` 18 次；`solve_with_escalation` 在所有样本一致时 6 次，需要升级时 24 次。

**④ 其他函数**：`build_cot_prompt` 默认只放入 3 个示例；`num_examples=5` 时测试题 "James writes a 3-page letter…" 在 prompt 中出现 2 次（泄漏）；`evaluate_thought` 对 "8/10" 返回 1.0；`react_solve` 在模型回答 `Answer: 10.0` 时返回 `'10.0'`，5 步都只有 Thought 时返回 `None`。

**测试题的标准答案核对**（手算）：Natalia `48 + 24 = 72`；Weng `12 × 50/60 = 10`；Betty `100 − 50 − 15 − 30 = 5`；Julie `(120 − 12 − 24)/2 = 42`；James `3 × 2 × 2 × 52 = 624`——`TEST_QUESTIONS` 中的答案都正确。

如果你有 API key，可以运行 `OPENAI_API_KEY=... python advanced_prompting.py` 观察真实结果，但请先修复答案抽取（第 7 节练习 1），否则准确率会被严重低估。

---

## 7. 动手改一改

1. **修复答案抽取**：按测验 Q9 的修正版重写 `extract_answer`，并把 `run_comparison` 与 `react_solve` 的比较改为数值归一化后比较；用 ① 中的用例写单元测试。
2. **离线可运行**：写一个 `MockClient`（实现 `chat.completions.create`，按 system 内容返回不同文本），让 `__main__` 在没有 API key 时自动使用它，并打印每种方法的调用次数。
3. **相似度选示例（讲义练习 2）**：用简单的词袋余弦相似度（或 embedding）从示例库中为每道题选最相似的 3 个示例，同时确保示例与测试集去重；比较随机选择与相似选择的准确率。
4. **自适应 self-consistency（讲义练习 3）**：逐次采样，一旦领先答案的票数不可能被超越就停止；统计平均调用次数与准确率，画出 N = 1、3、5、7、10 的准确率–成本曲线。
5. **安全的 ReAct（讲义练习 4）**：用 `ast` 白名单计算器替换 `eval`（测验 Q12），并在"只有 Thought"时追加提示消息；再加一个 "lookup" 工具（查一个小字典），观察多工具时的循环行为。
6. **真正的先便宜后昂贵**：改写 `solve_with_escalation`——先 3 次采样，全一致直接返回；否则补到 5 次；仍不达标再 ToT，并在 ToT 与 SC 多数答案不一致时，用 `prompt_chain_solve` 的验证步骤做裁决。

---

## 8. 常见坑

- **答案抽取吞句号**：`\.?\d*` 会把 "72." 中的句号当小数点；数字正则应要求小数点后有数字。
- **字符串比较数值答案**：`'10.0'`、`'72.'`、`'72'` 都应视为同一答案。
- **示例与测试集重复**：few-shot 示例库必须与评测集去重，否则准确率虚高。
- **示例本身质量差**：推理混乱或答案错误的示例会被模型模仿。
- **温度 0 做 self-consistency**：所有样本相同，投票无意义。
- **静默丢弃无法抽取的样本**：置信度的分母变小，阈值判断随之失真；要单独统计抽取失败率。
- **"生成不同方法"但不给模型看之前的方法**：多样性只能靠温度。
- **LLM 自评分的解析**：`8/10`、百分数等格式会被误读；应要求严格格式并校验范围。
- **把 `eval` 当沙箱**：清空 `__builtins__` 挡不住属性链访问。
- **ReAct 没有"无动作"处理**：温度 0 下可能原地打转耗尽步数。
- **以为升级策略"先便宜"**：本代码每题至少 6 次调用，最坏 24 次。
- **在推理模型上叠加 CoT/SC**：讲义指出这通常是冗余的。
