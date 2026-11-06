# 测验 · Few-Shot, Chain-of-Thought, Tree-of-Thought（Few-Shot, Chain-of-Thought, Tree-of-Thought）

> **阶段 11 · LLM 工程 · 第 02 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/advanced_prompting.py](../code/advanced_prompting.py) ｜ 代码讲解：[code/advanced_prompting.讲解.md](../code/advanced_prompting.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 说明：本节中文讲义机翻质量较差（如"GPT- 4个""托特很贵"），有疑义处以英文版为准。本节代码需要 OpenAI API key 与网络，测验中的运行结果来自用**模拟 client** 离线调用代码中各函数得到的结果（详见代码讲解第 6 节）。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Zero-shot vs few-shot | 示例是"压缩过的指令"：格式敏感、分类、抽取、领域术语类任务 few-shot 更好；简单事实问答、创意任务 zero-shot 即可 |
| 2 | 示例选择 | 语义相似、标签多样、难度匹配；讲义：多数任务 3–5 个示例最佳，相似示例比随机示例在分类上高 5–15%（Liu 等, 2022） |
| 3 | Chain-of-Thought | 让模型先写出中间推理再给答案；每个推理 token 都成为后续 token 的上下文，相当于延长了有效计算深度 |
| 4 | 两种 CoT | zero-shot CoT（加一句 "Let's think step by step"，Kojima 等 2022）与 few-shot CoT（示例中带推理过程，通常更好） |
| 5 | CoT 何时有害 | 简单事实回忆、单步分类、高吞吐低复杂度任务；讲义：每次查询多 50–200 个推理 token；推理模型（o 系列、R1）已内置 CoT，再加提示是冗余的 |
| 6 | Self-consistency | 温度 > 0 采样 N 条推理路径，对最终答案多数投票（Wang 等, 2023）；讲义：PaLM 540B 上 GSM8K 从 56.5% 提到 74.4%（N=40）；N=5 拿到大部分收益 |
| 7 | Tree-of-Thought | 生成候选思路 → 评估打分 → BFS/DFS 搜索并剪枝；讲义：Game of 24 上标准提示 7.3%、CoT 4.0%、ToT 74%；代价是大量 LLM 调用 |
| 8 | ReAct | Thought–Action–Observation 循环，把推理与工具调用交替进行，观察结果可以纠正推理错误；是现代 agent 的基础 |
| 9 | 结构化提示与 prompt chaining | 用 XML 标签/Markdown 标题/分隔符分区；把复杂任务拆成"抽取 → 分析 → 生成/验证"的多步链，中间结果可检查、可换模型 |
| 10 | 升级（escalation）策略 | 先用便宜的方法，置信度不足再上更贵的方法；答案抽取格式（"The answer is N"）是投票与评测的前提 |

### 核心技能（能动手做到）

- [ ] 写出 few-shot CoT、zero-shot CoT、zero-shot 三种 prompt 构建函数，并统一答案输出格式
- [ ] 写一个健壮的 `extract_answer`，正确处理句末句号、千分位、负数、小数与 `$` 符号，并在比较前做归一化
- [ ] 实现 self-consistency 投票并计算置信度，知道无法抽取答案的样本如何影响置信度
- [ ] 实现束宽（beam）受限的 ToT，并能算出给定 breadth/depth 下的 LLM 调用次数
- [ ] 实现一个带安全计算器工具的 ReAct 循环，处理"只有 Thought 没有 Action"等异常
- [ ] 根据准确率要求、延迟预算、成本上限为任务选择推理策略，并设计升级逻辑

---

## 二、基础自测（选择题）

**Q1.** 讲义从"机制"上解释 CoT 为什么有效，最贴切的是：

- A. CoT 让模型调用了更大的参数子集
- B. CoT 会自动触发模型内部的检索模块
- C. 每个生成的 token 都成为后续 token 的上下文，把中间计算"外化"为 token，相当于延长了有效计算深度
- D. CoT 降低了 temperature，使输出更确定

**Q2.** 为什么 `self_consistency_solve` 中采样温度设为 0.7，而不是 0.0？

- A. 温度为 0 时 N 次采样几乎完全相同，投票失去意义；需要足够的随机性产生多样的推理路径，但又不能多到胡言乱语
- B. 温度 0.7 时模型不会犯算术错误
- C. OpenAI API 不允许 temperature = 0
- D. 温度越高，答案抽取越容易

**Q3.** 在 `solve_with_escalation` 中，单次贪心 CoT 的答案为 `"72"`；5 次采样抽取到的答案为 `["72", "72", "72", None, "70"]`（其中一条无法抽取）。那么：

- A. confidence = 0.6，不升级
- B. confidence = 0.6，升级到 ToT
- C. confidence = 0.75，不升级
- D. confidence = 0.75，升级到 ToT

**Q4.** 代码中 `tree_of_thought_solve(question, client, model, breadth=3, depth=2)`（升级流程里用的参数）一共会调用 LLM 多少次（含生成与评估）？

- A. 9
- B. 18
- C. 30
- D. 39

**Q5.** 下列哪种任务**最不适合**加 CoT？

- A. 多步算术应用题
- B. "法国的首都是哪里？"这类简单事实回忆，且系统对吞吐量要求很高
- C. 需要符号推理的逻辑题
- D. 需要先解释再下结论的代码审查

**Q6.** 关于推理模型（如 OpenAI o 系列、DeepSeek-R1），讲义的观点是：

- A. 必须配合 few-shot CoT 才能发挥作用
- B. 对推理模型使用 self-consistency 的收益最大
- C. 推理模型不支持 system message
- D. 它们在输出前已在内部进行 CoT，再加 "Let's think step by step" 是冗余的，有时甚至适得其反

**Q7.** 讲义推荐的 few-shot 示例选择原则是：

- A. 语义相似、覆盖所有标签、难度与目标问题匹配；一般 3–5 个
- B. 随机挑选，越多越好，至少 10 个
- C. 只选最简单的示例，降低模型理解成本
- D. 只选与目标问题标签相同的示例

**Q8.** 关于 ReAct，下列说法正确的是：

- A. ReAct 只做推理，不调用外部工具
- B. ReAct 是 ToT 的一种特例
- C. ReAct 交替进行 Thought、Action、Observation，观察结果可以在执行中纠正推理错误
- D. ReAct 必须使用树搜索才能工作

---

## 三、动手 / 代码题

**Q9.** 阅读 `extract_answer`：

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

1. 写出以下输入的返回值：`"The answer is 72."`、`"The answer is 70,000."`、`"The answer is -5"`、`"Hello, world"`。
2. few-shot 示例都以 `"The answer is 70000."`（带句号）结尾。结合 `run_comparison` 中的 `is_correct = str(answer) == str(expected)`，如果模型照着示例格式输出，评测结果会怎样？对 self-consistency 的投票又有什么影响？
3. 第二个正则有什么问题？
4. 写出修正版，并说明比较答案时应该怎么做。

**Q10.** 审查 `GSM8K_EXAMPLES`：

1. 第 5 个示例（Wendi 喂鸡）的推理文本有什么问题？题目本身呢？
2. 第 4 个示例（James 写信）与 `TEST_QUESTIONS` 有什么关系？
3. 默认 `num_examples=3` 时，上面两个问题会不会影响结果？如果有人把 `num_examples` 改成 5 呢？
4. 由此总结：few-shot 示例库应该满足哪些"卫生"要求？

**Q11.** 计算 LLM 调用次数（每次生成或评估各算 1 次调用）：

```python
def tree_of_thought_solve(question, client, model, breadth=3, depth=3):
    thoughts = generate_initial_thoughts(question, client, model, breadth)
    scored = [(t, evaluate_thought(t, question, client, model)) for t in thoughts]
    ...
    for current_depth in range(1, depth):
        top_k = min(2, len(scored))
        for thought, score in scored[:top_k]:
            extensions = extend_thought(thought, question, client, model, breadth)
            for ext in extensions:
                ext_score = evaluate_thought(ext, question, client, model)
```

1. `breadth=3, depth=3` 时共多少次调用？`depth=2` 时呢？
2. `solve_with_escalation` 最好情况和最坏情况分别调用多少次？
3. 讲义说"branching factor 3、depth 3 的树最多需要 39 次 LLM 调用"，与代码对不上，差异来自哪里？
4. 讲义描述升级逻辑为"try cheap (single CoT) first"，代码是否真的先便宜后昂贵？请提出一个更省的升级方案。

**Q12.** 阅读 `react_solve` 的工具执行部分：

```python
        calc_match = re.search(r"Action:\s*calculate\s+(.+)", text)
        if calc_match:
            expression = calc_match.group(1).strip()
            try:
                result = eval(expression, {"__builtins__": {}}, {})
                observation = f"Observation: {result}"
            except Exception as e:
                observation = f"Observation: Error - {e}"
            messages.append({"role": "user", "content": observation})
```

1. `eval(..., {"__builtins__": {}}, {})` 是安全的沙箱吗？为什么？
2. 对题目 "Weng 每小时 $12，照看了 50 分钟"，模型调用 `calculate 12*50/60` 后回答 `Answer: 10.0`，`react_solve` 返回什么？与期望 `"10"` 比较会怎样？
3. 如果模型某一步只输出了 `Thought: ...`（既没有 Action 也没有 Answer），循环会发生什么？
4. 用 `ast` 写一个只支持四则运算的安全计算器。

---

## 四、面试高频题

**Q13.**（基础必考）zero-shot、few-shot、zero-shot CoT、few-shot CoT、self-consistency 分别是什么？各自适合什么场景、代价是什么？

**Q14.**（原理深挖）CoT 为什么能提升多步推理？为什么在 Game of 24 上 CoT 反而比标准提示差？模型写出的推理过程一定反映它"真实的思考"吗？

**Q15.**（工程实践）你要上线一个数学辅导应用，要求准确率高、平均延迟低、成本可控。请设计推理策略与升级逻辑，并说明如何评测。

**Q16.**（追问型）self-consistency 的多数投票为什么有效？在什么情况下会失效？N 怎么选？

**Q17.**（场景设计）为一个"需要查资料的多跳问答"场景设计 ReAct 系统：有哪些工具、如何防止死循环和工具滥用、如何评估它是否比纯 CoT 更好？

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义："Each token a transformer generates becomes context for the next token. Without CoT, the model must compress all reasoning into the hidden state of a single forward pass. With CoT, the model externalizes intermediate computations as tokens. Each reasoning token extends the effective computation depth." A 错：每个 token 用的参数相同（对稠密模型而言）；B 错：CoT 不涉及检索（那是 ReAct/RAG）；D 错：CoT 与温度无关，self-consistency 反而需要较高温度。

### Q2 — 答案：A

讲义："At temperature 0.0, all N samples would be identical, defeating the purpose. You need enough randomness for diverse reasoning paths but not so much that the model produces gibberish." 投票的前提是各路径的错误相互独立、彼此不同。B 错：温度与算术正确性无直接关系；C 错：API 允许 0（本节其他函数就用 0.0）；D 无依据。

### Q3 — 答案：D

`answers` 只收集非 None 的结果：`["72", "72", "72", "70"]`，共 4 个。`Counter` 多数为 `"72"`（3 票），`confidence = 3 / 4 = 0.75 < 0.8`，因此即使与贪心答案一致也会升级到 ToT。A、B 把分母当成 5（若按 5 计为 0.6）；C 判断条件弄反了。注意：无法抽取的样本被**静默丢弃**，分母变小会让置信度偏高或偏低，生产中应把"抽取失败率"单独监控。

### Q4 — 答案：B

初始：生成 3 次 + 评估 3 次 = 6；之后循环 `range(1, 2)` 只执行 1 层：保留前 2 个（`top_k = 2`），每个扩展 3 个，每个扩展 1 次生成 + 1 次评估 → `2 × 3 × 2 = 12`。合计 **18**（我们用计数的模拟 client 实测为 18）。C 是 `depth=3` 的次数（6 + 12 + 12 = 30）；D 是讲义中"分支 3、深度 3、不剪枝、只算生成"的上限 3 + 9 + 27 = 39；A 只算了第一层。

### Q5 — 答案：B

讲义 "When CoT hurts"：简单事实回忆、单步分类、速度比准确率更重要的任务；CoT 每次会多 50–200 个 token，高吞吐低复杂度场景是纯浪费。A、C 是 CoT 的主战场；D 需要解释过程，CoT 式的"先分析后结论"是合适的。

### Q6 — 答案：D

讲义 "Note on reasoning models"：o 系列与 DeepSeek-R1 "run chain-of-thought internally before emitting their answer. Adding 'Let's think step by step' to a reasoning model is redundant and sometimes counterproductive"；并且"For reasoning models self-consistency is subsumed by the built-in internal sampling"。所以 B 恰好相反；A、C 无依据。

### Q7 — 答案：A

讲义 "Example Selection: Similar Beats Random" 的三原则：semantic similarity、label diversity、difficulty matching；"The optimal number of examples for most tasks is 3-5"，多标签分类每个标签一个示例。B 违背"超过 5 个收益递减且浪费上下文"；C 违背难度匹配；D 违背标签多样性（只给同一标签的示例会让模型偏向该标签）。

### Q8 — 答案：C

ReAct 的核心是 Thought–Action–Observation 循环，讲义："reasoning errors get corrected by observations -- the model can update its plan mid-execution"。A、D 错；B 错：ReAct 是线性的交替循环，不是树搜索。

补充一个讲义数字的核对：讲义称 "On HotpotQA, ReAct with GPT-4 achieves 35.1% exact match vs 29.4% for CoT alone"。据 ReAct 原论文的表格，该实验使用的是 PaLM-540B 而非 GPT-4；29.4% 是 CoT，单独的 ReAct 约 27.4%（略低于 CoT），35.1% 是"ReAct 与 CoT-SC 结合"的方法。也就是说，"ReAct 单独就胜过 CoT"在 HotpotQA 上并不成立，ReAct 的优势主要体现在可解释性、事实依据（更少幻觉）以及与 CoT-SC 的互补上。引用论文数字时务必核对实验设置。

### Q9 — 参考答案

1. 实测返回值：

| 输入 | 返回 | 问题 |
|------|------|------|
| `"The answer is 72."` | `'72.'` | `\.?` 贪婪地吞掉了句末句号 |
| `"The answer is 70,000."` | `'70000.'` | 同上 |
| `"The answer is -5"` | `'5'` | 不支持负号 |
| `"Hello, world"` | `''` | 兜底的 `[\d,]+` 能匹配单独的逗号，返回空字符串而不是 None |

2. 示例教模型以 `The answer is 70000.` 结尾，模型极可能输出 `The answer is 72.`，被抽取成 `'72.'`，与期望 `'72'` 做字符串比较 → **全部判错**。我们用一个总是回答 `"... The answer is 72."` 的模拟 client 跑 `run_comparison`，四种方法的准确率都是 **0.0%**（`WRONG (got 72., expected 72)`）。self-consistency 中 `'72'` 与 `'72.'` 会被当成两个不同答案，**分散选票**，置信度被低估，导致不必要的升级。
3. 第二个正则 `[Tt]he answer is[:\s]*([\d,]+\.?\d*)` 是第一个的子集（第一个只是多了可选的 `\$?`），永远不会被用到，属于冗余代码。另外第四个正则末尾的 `$` 在未开启 `re.MULTILINE` 时只匹配整段文本的末尾。
4. 修正版（已验证上述用例全部正确）：

```python
NUM = r"\$?\s*(-?\d[\d,]*(?:\.\d+)?)"          # 小数点后必须有数字，句末句号不会被吞掉

def extract_answer(text):
    if not text:
        return None
    m = re.search(r"[Tt]he answer is[:\s]*" + NUM, text) or re.search(r"####\s*" + NUM, text)
    if m:
        s = m.group(1)
    else:
        nums = re.findall(r"-?\d[\d,]*(?:\.\d+)?", text)
        if not nums:
            return None
        s = nums[-1]
    return normalize(s)

def normalize(s):
    v = float(s.replace(",", ""))
    return str(int(v)) if v.is_integer() else f"{v:g}"     # '72.0' -> '72'，'10.50' -> '10.5'
```

   比较答案时应先**归一化为数值**再比较（或比较 `normalize` 后的字符串），而不是直接比较原始字符串；投票前也要先归一化。

### Q10 — 参考答案

1. **Wendi 示例的问题**：
   - 推理文本反复自我否定（"Wait, let me re-read" "Hmm" "needs to give negative? No."），先后得出 5、40、10 等多个答案，最后凭"每餐等量"的假设（15 只鸡）给出 5——而题目中早餐 15 杯、午餐 25 杯，三餐显然不等量，这个假设自相矛盾。
   - 题目最后一句被改成 "if the carry-over from prior feedings was 35 cups"，没有给出鸡的数量，题意不完整，无法唯一求解。
   - 这样的示例如果进入 prompt，会教模型"啰嗦、反复、靠不成立的假设凑答案"，对 few-shot CoT 是有害示范。
2. 第 4 个示例 James 写信与 `TEST_QUESTIONS[4]` **完全相同**（题干与答案 624）。
3. 默认 `num_examples=3` 只取前 3 个示例（Janet、robe、Josh），两个问题都不会进入 prompt（实测 prompt 中恰好 3 个示例）。若改为 5：
   - James 题会以"示例 + 标准答案"的形式出现在测试它自己的 prompt 里（实测该题干在 prompt 中出现 2 次），这是**测试集泄漏**，few-shot CoT 和 self-consistency 的准确率会被虚高；
   - Wendi 的混乱推理成为示范。
4. 示例库卫生要求：每个示例的推理清晰、单线、可验证且答案正确；题目条件完整；与评测集**去重**（精确匹配 + 近似匹配）；输出格式与抽取器一致（Q9）；按任务类型、难度、标签分布有意识地挑选。

### Q11 — 参考答案

1. `depth=3`：初始 3 生成 + 3 评估 = 6；第 1、2 层各 `2 × 3 × (1 + 1) = 12`；合计 **30**。`depth=2`：6 + 12 = **18**。（用计数的模拟 client 实测：30 与 18。）
2. `solve_with_escalation`：
   - 最好情况：1 次贪心 CoT + 5 次采样 = **6** 次，然后直接返回；
   - 最坏情况：6 + ToT(depth=2) 18 = **24** 次。
3. 讲义的 39 是"分支 3、深度 3、**不剪枝**、只计生成"的上限：3 + 9 + 27。代码与之不同的地方：每层只保留得分最高的 2 个节点继续扩展（束宽 2 的 beam search），所以生成数是 3 + 6 + 6 = 15；但每个节点还要一次评估调用，总数变为 30。如果按讲义的完全展开再加评估，会是 78 次。
4. 代码**并没有**"先便宜后昂贵"：它无条件地先跑贪心 CoT，再无条件地跑 5 次采样，然后才决定是否升级，即使贪心答案非常可靠，每题至少也要 6 次调用。更省的方案：
   - 先采样 3 次，若 3 次一致且与贪心一致就直接返回（4 次调用）；否则再追加 2 次凑满 5 次，再按 0.8 阈值判断；
   - 或者使用"自适应一致性"：逐次采样，一旦某答案的票数在剩余样本中不可能被超过就提前停止；
   - 升级到 ToT 时把 self-consistency 的多数答案作为候选之一，避免 ToT 结果比投票更差时无回退。

### Q12 — 参考答案

1. **不是安全沙箱**。清空 `__builtins__` 只能挡住直接调用 `open`、`__import__` 等名字，但表达式仍能通过对象属性层层访问到内部类，例如 `().__class__.__base__.__subclasses__()` 可以拿到解释器中所有已加载的类（我们实测该表达式在这个"沙箱"中可以正常执行），由此可以构造出危险操作；此外 `9**9**9` 这类表达式会让进程长时间卡住。讲义练习 4 说"在沙箱中 eval"，但这行代码不构成沙箱。
2. `12*50/60` 在 Python 中得到浮点数 `10.0`，Observation 为 `10.0`，模型回答 `Answer: 10.0`，`react_solve` 返回字符串 `'10.0'`（实测）；与期望 `'10'` 做字符串比较会**判错**。同样需要数值归一化（Q9）。
3. 只有 Thought 时既不匹配 Answer 也不匹配 Action，不会追加任何 Observation，下一轮请求的 messages 末尾仍是 assistant 消息；在 temperature 0 下模型很可能重复同样的内容，白白耗尽 `max_steps`（实测 5 次都只输出 Thought 时返回 `None`）。应在这种情况下追加一条提示（如 "Continue. Use Action: calculate or give Answer:"），并记录"无动作"次数。
4. 安全计算器（只允许数字与四则运算、乘方限制大小）：

```python
import ast, operator as op

OPS = {ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv,
       ast.USub: op.neg, ast.UAdd: op.pos, ast.Mod: op.mod}

def safe_calc(expr):
    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in OPS:
            return OPS[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in OPS:
            return OPS[type(node.op)](ev(node.operand))
        raise ValueError(f"unsupported expression: {ast.dump(node)[:40]}")
    return ev(ast.parse(expr.replace(",", ""), mode="eval"))
```

   `safe_calc("12*50/60")` 返回 `10.0`，`safe_calc("80,000*1.5")` 返回 `120000.0`；`().__class__`、`__import__('os')` 等属性访问、函数调用、名字引用都会抛 `ValueError`（已实测）。乘方未加入白名单，如需支持应限制指数大小。

### Q13 — 参考回答要点

| 方法 | 做法 | 适合 | 代价（讲义） |
|------|------|------|-------------|
| Zero-shot | 只给任务 | 简单任务、事实问答 | 1 次调用，无额外 token |
| Few-shot | 先给 3–5 个输入输出示例 | 格式匹配、分类、抽取 | +200–500 token |
| Zero-shot CoT | 加 "Let's think step by step" | 快速提升推理 | +50–200 token |
| Few-shot CoT | 示例中带推理过程 | 单次调用的最高准确率 | +300–600 token |
| Self-consistency | 温度 > 0 采样 N 次再投票 | 高风险推理 | N 倍成本与延迟 |

- 讲义建议："For most production systems, few-shot CoT with a 3-sample self-consistency fallback covers 90% of use cases."
- 加分点：说明推理模型已内置 CoT，策略要随模型类型调整；答案格式统一是投票与自动评测的前提。

### Q14 — 参考回答要点

- **为什么有效**：Transformer 每个 token 的计算深度固定，多步推理若必须在"一次前向"内完成会超出其能力；CoT 把中间结果写成 token，后续步骤可以"读到"它们，相当于用更多的序列步换计算深度（讲义 Q1 的解释）。
- **为什么在 Game of 24 上更差**：这类任务的难点是**搜索**（4 个数字的组合与运算顺序空间很大），线性 CoT 只走一条路，一旦早期选择错误就无法回头；讲义："CoT actually hurts here because the search space is wide"。ToT 通过生成多个候选、评估、剪枝和回溯解决这个问题（7.3% → 74%）。
- **忠实性（faithfulness）**：模型写出的推理不一定是它得出答案的真实原因，可能是"事后合理化"；推理过程正确也不保证答案正确，反之亦然。因此评测应以最终答案为准，对推理过程做抽检；过程级监督可参考讲义延伸阅读中的 "Let's Verify Step by Step"（过程奖励模型）。
- 常见误区：认为"加 CoT 总是更好"。

### Q15 — 参考回答要点

- **分层策略**：
  1. 简单题直接 few-shot CoT（temperature 0）；
  2. 自适应 self-consistency：先采 3 次，一致则返回，不一致再补到 5 次；
  3. 仍不确定（置信度 < 0.8 或与贪心不一致）时，用计算器工具（ReAct）或推理模型兜底，ToT 只用于少数难题；
  4. 对算术密集题，直接让模型写表达式交给安全计算器（Q12），消除算术错误。
- **工程要点**：统一答案格式与归一化（Q9）；对同题做缓存；设置每题最大调用次数与超时；记录每层的命中率、成本与延迟。
- **评测**：留出带标准答案的题库（与 few-shot 示例去重，Q10），按难度分层统计准确率、平均/P95 延迟、平均 token 成本；画"准确率–成本"曲线找拐点（讲义练习 3）。
- 加分点：对教学场景，推理过程本身也要可读、正确，可以用第二个模型校验关键步骤（prompt chaining 中的 verify 步骤，见 `prompt_chain_solve`）。

### Q16 — 参考回答要点

- **为什么有效**：若每条路径独立地以概率 p > 0.5 得到正确答案、错误答案又分散在不同数值上，多数投票的正确率随 N 增加而提高；正确的推理路径往往"殊途同归"，而错误五花八门。
- **失效情况**：
  - 系统性错误：模型对某类题有一致的误解，所有路径犯同样的错，投票只会加固错误（讲义："the sweet spot where single-path errors are frequent but not systematic"）；
  - 答案空间不可比：开放式文本无法直接计票，需要先归一化或聚类；
  - 抽取失败或格式不统一会分散选票（Q9 中 `'72'` 与 `'72.'`）；
  - 基础准确率很高（讲义：GPT-5 上 97% → 98%）时收益很小；对推理模型基本被内部采样取代。
- **N 的选择**：讲义——N = 3 是有意义投票的最小值，N = 5 拿到大部分收益，N > 10 多数任务收益递减；最好画准确率–成本曲线确定。
- 加分点：可以按路径的置信度/对数概率加权投票，或使用自适应早停节省成本。

### Q17 — 参考回答要点

- **工具**：搜索/检索（返回截断后的片段）、查表/数据库查询、安全计算器；工具接口要有清晰的名称、参数与错误信息。
- **循环控制**：最大步数、最大 token 数、重复动作检测（同样的查询连续出现就终止或提示换策略）、"只有 Thought 没有 Action"时的纠正提示（Q12）。
- **安全**：工具白名单与参数校验，绝不 `eval` 任意代码；检索结果视为数据而非指令（防间接 prompt injection）；对外部副作用操作要求确认。
- **观察处理**：长结果截断或摘要后再放入上下文，避免上下文膨胀。
- **评估**：多跳 QA 数据集上比较 ReAct、CoT、CoT-SC 以及组合方案的 EM/F1、调用次数、成本与幻觉率；注意 Q8 中提到的原论文结论——ReAct 单独不一定在 EM 上胜过 CoT，组合方案往往最好。
- 加分点：说明 ReAct 是第 14 阶段 agent loop 的雏形；现代 API 的 function calling 用结构化的工具调用取代了正则解析 "Action:" 文本。

---

## 六、关联知识点

### 前置知识
- [阶段 11 · 01 Prompt Engineering：技术与模式](../../01-prompt-engineering/docs/zh.md)：本节的 Few-Shot、CoT、Decomposition 模式都在上一节首次出现。
- [阶段 10 · 04 预训练 Mini GPT](../../../10-llms-from-scratch/04-pre-training-mini-gpt/docs/zh.md)：自回归生成与 temperature 采样，理解"推理 token 成为上下文"与 self-consistency 的采样多样性。
- [阶段 01 · 16 Sampling 方法](../../../01-math-foundations/16-sampling-methods/docs/zh.md)：多次采样与多数投票背后的概率直觉。

### 本节被哪些后续内容用到
- [阶段 11 · 03 Structured Outputs](../../03-structured-outputs/docs/zh.md)：用结构化输出代替正则抽取答案。
- [阶段 11 · 09 Function Calling 与工具使用](../../09-function-calling/docs/zh.md)：用结构化工具调用替代文本版 ReAct。
- [阶段 11 · 10 Evaluation 与 LLM 应用测试](../../10-evaluation/docs/zh.md)：本节准确率对比的系统化版本。
- [阶段 14 · 01 Agent Loop：观察、思考、行动](../../../14-agent-engineering/01-the-agent-loop/docs/zh.md)：ReAct 发展成完整的 agent 循环。
- [阶段 14 · 04 Tree of Thoughts 与 LATS](../../../14-agent-engineering/04-tree-of-thoughts-lats/docs/zh.md)：ToT 的深入与蒙特卡洛树搜索扩展。
- [阶段 14 · 05 Self-Refine 与 CRITIC](../../../14-agent-engineering/05-self-refine-and-critic/docs/zh.md)：生成—评估—改进的迭代模式。
- [阶段 15 · 02 STaR、V-STaR、Quiet-STaR](../../../15-autonomous-systems/02-star-family-reasoning/docs/zh.md)：用模型自己生成的推理链来训练推理能力。

### 延伸关键词
`zero-shot CoT` · `few-shot CoT` · `self-consistency` · `adaptive consistency` · `Tree-of-Thought` · `beam search` · `ReAct` · `prompt chaining` · `DSPy` · `answer normalization` · `test-set contamination` · `CoT faithfulness` · `process reward model` · `test-time compute`
