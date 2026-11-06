# 测验 · Self-Refine 与 CRITIC：迭代改进输出（Self-Refine and CRITIC: Iterative Output Improvement）

> **阶段 14 · Agent 工程 · 第 05 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 提示：本节中文讲义为质量很差的机器翻译（如把 Self-Refine 译成"自译自审"、evaluator-optimizer 译成"蒸发器"），请以英文版为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 要解决的问题 | 输出"差一点就对"（语法错一行、总结太长、计划漏了边界情况）时，让 agent 先批评自己的输出再修正 |
| 2 | Self-Refine | Madaan 等（NeurIPS 2023）：同一个 LLM 扮演 generate、feedback、refine 三个角色循环；讲义："7 个任务平均绝对提升 20 个百分点"，无需训练、无需外部工具 |
| 3 | refine 要看历史 | refine 的输入包含**全部**之前的输出和批评，避免重复犯错；论文消融：去掉历史质量明显下降 |
| 4 | CRITIC 的核心洞见 | Gou 等（arXiv:2305.11738）：LLM 在没有外部 grounding 时自我验证不可靠（幻觉在生成它的模型看来很可信）；把 feedback 换成 `verify(task, output, tools)` |
| 5 | CRITIC 的工具 | 搜索引擎（事实）、代码解释器（代码正确性）、计算器（算术）、领域验证器（单测、类型检查、linter）；产出基于工具结果的结构化批评 |
| 6 | 何时退化 | 没有外部验证器的任务（创意写作、格式）CRITIC 就退化为 Self-Refine；不要为一个空壳验证器付延迟 |
| 7 | 停止条件 | 2026 默认组合："验证器通过，或（模型说没问题且迭代 ≥ 2），或迭代 ≥ 上限"——永远不只用单一条件 |
| 8 | Evaluator-Optimizer | Anthropic 2024 年 12 月提出的五种工作流模式之一：evaluator 打分并批评，optimizer 修改；两者的 prompt 要**结构上明显不同**，避免橡皮图章 |
| 9 | Output guardrails | OpenAI Agents SDK 中对 agent 最终输出运行的校验器；触发时抛 `OutputGuardrailTripwireTriggered`，输出被拒绝、可重试；可以调工具（CRITIC 式）或是纯函数 |
| 10 | 三大陷阱 | 橡皮图章循环（同模型同风格自评收敛到"看起来不错"）、过度精修（每轮都加延迟和 token，预算 1–3 轮后转人工）、在没有验证器的简单任务上硬套 CRITIC |

### 核心技能（能动手做到）

- [ ] 写出 generate → verify/feedback → refine 的循环，并正确记录每轮的输出、批评与是否通过
- [ ] 实现一个基于外部参考数据的验证器，输出结构化批评（pass/fail + violations 列表 + 修改建议）
- [ ] 实现讲义推荐的组合停止条件，并能对任意输入组合说出是否停止、为什么
- [ ] 识别"demo 中两种方法的差异其实来自脚本耦合而非 grounding"这类评测陷阱
- [ ] 量化有噪声验证器（例如 30% 误放行）对最终正确率的影响，并提出缓解办法
- [ ] 把模式映射到 Anthropic evaluator-optimizer 与 OpenAI Agents SDK output guardrails

---

## 二、基础自测（选择题）

**Q1.** Self-Refine 的三个角色是：

- A. Planner、Worker、Solver，由三个不同的模型担任
- B. Actor、Evaluator、Self-Reflector，跨多次试验运行
- C. Policy、Value、Reflector，嵌在 MCTS 中
- D. generate、feedback、refine，由同一个 LLM 在一个循环里担任

**Q2.** 为什么 Self-Refine 的 refine 步骤必须看到完整历史？

- A. 没有之前的输出和批评，refine 容易重复已经被指出过的错误；论文消融显示去掉历史后质量明显下降
- B. 历史越长 token 越多，模型越"努力"
- C. 为了让 refine 能调用外部工具
- D. 为了满足 API 的多轮对话格式要求，与质量无关

**Q3.** CRITIC 相对 Self-Refine 的关键改动是：

- A. 把 generate 换成更大的模型
- B. 去掉 refine，只保留 verify
- C. 把"模型自己给反馈"换成"借助外部工具（搜索、代码解释器、计算器、单测等）验证"，产生有工具结果依据的结构化批评
- D. 在多次试验之间保存反思

**Q4.** 讲义转述的 Self-Refine 论文主结果是：

- A. 在 HotpotQA 上 token 减少 5 倍
- B. 在 7 个任务上平均绝对提升约 20 个百分点，无需训练和外部工具
- C. 在 HumanEval 上 pass@1 达到 92.7%
- D. 只对 GPT-4 有效，对其他模型无提升

**Q5.** 运行本节代码，Self-Refine 4 轮都没修好，而 CRITIC 3 轮通过。仔细读代码后，Self-Refine 失败的真正原因是：

- A. 自我批评其实**已经**指出了问题（"first bullet reads wrong, double-check capital"），但脚本化的 `generate` 只在批评文本里出现 `"germany"` 或 `"everest"` 时才改写；措辞不匹配，所以输出原封不动
- B. 自我批评没有发现 "Paris is the capital of Germany" 这个幻觉
- C. `max_iters=4` 太小，再多几轮就会修好
- D. Self-Refine 没有把历史传给 refine

**Q6.** 讲义推荐的 2026 年 evaluator-optimizer 停止条件是：

- A. 只要模型说"没问题"就停止
- B. 固定迭代 3 轮
- C. 验证器通过，**或**（模型说没问题**且**迭代 ≥ 2），**或**迭代 ≥ 上限
- D. 验证器通过**且**模型说没问题**且**迭代 ≥ 上限

**Q7.** 把 `"- The sun orbits the earth\n- Water is wet\n- Ice is cold"` 交给本节的 `verify_external`，结果是：

- A. 返回 "the sun orbits the earth contradicts reference data"，因为它在 `KNOWN_WRONG_FACTS` 中
- B. 抛出异常，因为 `fact.split(" is ")` 找不到 " is "
- C. 返回 "expected 3 bullet lines"
- D. 返回 `verifier: ok`——循环虽然遍历了 `KNOWN_WRONG_FACTS`，但循环体里只有两条写死的检查，从未使用 `fact`

**Q8.** 关于"橡皮图章循环（rubber-stamp loop）"，正确的说法是：

- A. 指验证器太严格，任何输出都通不过
- B. 同一个模型用同样风格的 prompt 既生成又批评，很容易收敛到"看起来不错"；应使用结构上不同的 prompt，或用另一个（更小更便宜的）模型做批评
- C. 只要把 temperature 调到 0 就能避免
- D. 只出现在 CRITIC 中，Self-Refine 不会出现

---

## 三、动手 / 代码题

**Q9.** 阅读 `verify_external`：

```python
def verify_external(output: str) -> tuple[str, bool]:
    text = output.lower()
    for fact in KNOWN_WRONG_FACTS:
        key = fact.split(" is ")[0] if " is " in fact else fact
        if "paris" in text and "germany" in text:
            return f"verifier: 'paris is the capital of germany' contradicts reference data", False
        if "everest" in text and "europe" in text:
            return f"verifier: 'mt everest is in europe' contradicts reference data", False
    if len([l for l in output.splitlines() if l.startswith("-")]) != 3:
        return "verifier: expected 3 bullet lines", False
    if any(len(l) > 60 for l in output.splitlines()):
        return "verifier: bullet exceeds 60 chars", False
    return "verifier: ok", True
```

1. 找出至少 4 个问题（提示：未使用的变量、漏检、误报、边界条件、一次只报一个问题）。
2. 写一个返回 `{"pass": bool, "violations": [...]}` 的结构化版本（配套 skill 要求"Structured JSON only"）。

**Q10.** 完成讲义练习 1：用 `max_iters=1` 运行。

```python
def run_loop(topic, use_critic, max_iters=4):
    history = []
    output = generate(topic, history)
    verify = verify_external if use_critic else (lambda o: feedback_self(o))
    for i in range(1, max_iters + 1):
        critique, ok = verify(output)
        history.append(Attempt(i, output, critique, ok))
        if ok:
            break
        output = refine(topic, output, critique, history)
    return history
```

1. `max_iters=1` 时 CRITIC 还有帮助吗？`max_iters=2、3` 呢？
2. 实测 `max_iters=2` 时 `refine` 被调用了 2 次。哪一次调用是浪费的？在真实系统中这意味着什么？怎么改？

**Q11.** 完成讲义练习 2：把外部验证器换成有噪声的版本——它对**错误的**输出有 30% 的概率误判为通过（false pass）。demo 中初始输出有 2 处错误，需要 2 次修正后才正确。

1. 不跑代码，推算循环最终"声称通过、但实际仍有错误"的概率。
2. 实测 10,000 个随机种子的比例是 0.5139。讲义说这是"2026 年大多数 guardrail 栈的现实"，你会怎样缓解？

**Q12.** 按讲义与配套 skill 的停止策略写一个 `should_stop(i, verifier_ok, self_ok, max_iters=4)`，其中 `verifier_ok` 为 `True / False / None`（`None` 表示没有外部验证器）。对下列输入给出返回值：

| i | verifier_ok | self_ok |
|---|-------------|---------|
| 1 | True | False |
| 1 | None | True |
| 2 | None | True |
| 2 | False | True |
| 4 | False | False |

---

## 四、面试高频题

**Q13.**（基础必考）Self-Refine 和 CRITIC 分别是什么？它们的区别是什么？各适合什么任务？

**Q14.**（原理深挖）为什么 LLM 不擅长自我验证？CRITIC 的外部验证解决了什么、解决不了什么？

**Q15.**（工程实践）讲义说这个模式在 2026 年以 Anthropic 的 evaluator-optimizer 和 OpenAI Agents SDK 的 output guardrails 形式出现。在生产中实现一个 evaluator-optimizer 循环，你会怎么设计 prompt、验证器、停止条件和可观测性？

**Q16.**（场景设计）为一个"自然语言 → SQL"的 agent 设计 CRITIC 式的验证与精修循环：有哪些外部验证器可用？每一层能发现什么问题？

**Q17.**（追问型）Self-Refine、Reflexion、LATS 都有"批评/反思"环节，它们的区别是什么？如果精修了 3 轮还没通过，你会怎么办？

---

## 五、参考答案与解析

### Q1 — 答案：D

讲义："Self-Refine uses one LLM in three roles — generate, feedback, refine — in a loop." A 是 ReWOO（第 02 节），且 ReWOO 也不要求三个不同模型；B 是 Reflexion（第 03 节），它跨多次**完整试验**运行，而 Self-Refine 是对**同一个输出**反复修改；C 是 LATS（第 04 节）。

### Q2 — 答案：A

讲义："refine sees the full history — all prior outputs and critiques — so it does not repeat mistakes. The paper ablates this: drop history and quality drops sharply." 配套 skill 也把"refiner prompt 去掉历史"列为 hard reject。B 是错误的直觉；C 是 CRITIC 中 verify 的职责；D 错，历史直接影响质量。

### Q3 — 答案：C

讲义："CRITIC replaces `feedback(task, output)` with `verify(task, output, tools)`… The verifier produces a structured critique grounded in tool results." A 不是 CRITIC 的内容；B 错，refine 仍然保留；D 是 Reflexion。

### Q4 — 答案：B

讲义："+20 absolute improvement averaged across 7 tasks (math, code, acronym, dialog) including GPT-4. No training, no external tools, single model." A 是 ReWOO 的结果；C 是 LATS 的结果；D 与"including GPT-4"的表述不符，论文在多种模型上都有提升。

### Q5 — 答案：A

```python
def feedback_self(output: str) -> tuple[str, bool]:
    if "Germany" in output and "Paris" in output:
        return "first bullet reads wrong, double-check capital", False
```

```python
    last = history[-1]
    if "germany" in last.critique.lower():
        return ("- Paris is the capital of France\n" ...)
    if "everest" in last.critique.lower():
        ...
    return history[-1].output
```

自我批评明确指出了第一条有问题（`ok=False`），所以 B 是错的——讲义和程序最后打印的 "a self-critic can fail to flag its own confident-sounding hallucination" 在这个 demo 里**并不成立**。真正的原因是脚本化 `generate` 只认关键词 `germany` / `everest`，自我批评用的是 "capital"、"continent"，于是 `generate` 走到最后一行原样返回。实测把自我批评改写为 "Paris is not in Germany…"、"is Everest really in Europe?"，Self-Refine 同样 3 轮通过，与 CRITIC 完全一样。C 错：输出不变，轮数再多也一样；D 错：`refine` 收到了 `history`（只是脚本只看最后一条）。

教训：demo 中 CRITIC 胜出靠的是"批评文本的措辞与生成器脚本的耦合"，而不是 grounding。要展示 CRITIC 的真正优势，应该让自我批评**漏掉**某个错误（例如对"太阳绕地球转"说"no issues"），而外部验证器抓到它。

### Q6 — 答案：C

讲义："Stop if verifier passes OR model says fine AND iterations >= 2 OR iterations >= max_iterations."（按 skill 的写法加括号：`verifier passes OR (self-eval says fine AND iterations >= 2) OR iterations >= max_iterations`。）A 是单一条件，容易被橡皮图章骗；B 不考虑是否已经通过；D 要求三者同时满足，几乎永远跑满上限。本节代码只实现了"验证器（或自评）通过 / 达到上限"两种，自评第一轮说"没问题"就会直接停止。

### Q7 — 答案：D

循环变量 `fact` 和计算出的 `key` 从未被使用，循环体里只有 Paris/Germany、Everest/Europe 两条写死的检查，`KNOWN_WRONG_FACTS` 中第三条"太阳绕地球转"根本不会被检测；三条都是 "- " 开头、长度都不超过 60，于是返回 `verifier: ok`（已实测）。A 是代码"看起来"想做的事；B 错，`split` 只在 `" is " in fact` 时才执行，且结果没被用到；C 错，恰好 3 行。

### Q8 — 答案：B

讲义："Same model doing generation and critique with the same prompt style converges on 'looks good to me.' Use structurally different prompts, or a smaller cheap model for critique." Anthropic 的 evaluator-optimizer 也强调两个 prompt 要明显不同。A 说反了；C 错，temperature 不改变"模型倾向于认可自己"的偏差；D 错，橡皮图章恰恰是 Self-Refine 最突出的风险，CRITIC 用外部工具来缓解它。

### Q9 — 参考答案

1. 问题清单（均已实测）：

| 问题 | 现象 |
|------|------|
| 循环变量 `fact`、`key` 未被使用，循环体是两条写死的检查 | 对 3 个已知错误事实循环 3 次，做的却是同样两件事 |
| 漏检（false negative） | "The sun orbits the earth" 在列表里却从不检查，输出 `verifier: ok` |
| 误报（false positive） | 检查的是**整段文本**中关键词是否共现："- Paris is the capital of France / - Germany borders France / - Everest is in Asia" 被判为 "paris is the capital of germany" |
| 长度边界 | 讲义写"each under 60 chars"，代码用 `> 60`，恰好 60 个字符的行能通过；且长度把 "- " 前缀也算进去 |
| 一次只报一个问题 | 初始输出有两处错误，需要两轮才都暴露；每多一轮就多一次 refine 调用 |
| 自由文本批评 | 下游只能靠关键词匹配（这正是 Q5 中 Self-Refine 失败的根源） |

2. 结构化版本（已运行验证）：

```python
WRONG = {("paris", "germany"): "Paris is the capital of France, not Germany",
         ("everest", "europe"): "Mt Everest is in Asia, not Europe",
         ("sun", "orbits the earth"): "The Earth orbits the Sun"}

def verify_structured(output: str) -> dict:
    violations = []
    for line_no, line in enumerate(output.splitlines(), 1):
        l = line.lower()
        for keys, fix in WRONG.items():
            if all(k in l for k in keys):            # 逐行检查，避免跨行误报
                violations.append({"line": line_no, "type": "fact", "fix": fix})
        if len(line) >= 60:
            violations.append({"line": line_no, "type": "length", "fix": "shorten below 60 chars"})
    if len([l for l in output.splitlines() if l.startswith("- ")]) != 3:
        violations.append({"line": None, "type": "format", "fix": "exactly 3 bullets"})
    return {"pass": not violations, "violations": violations}
```

实测：初始输出一次返回两条 fact 违规（第 1、2 行）；"Germany borders France" 的例子返回 `pass: True`（误报消除）；太阳的例子返回第 1 行违规（漏检修复）。真正的 CRITIC 中，`WRONG` 这张表会被搜索引擎或知识库查询替代，但"逐条、结构化、带修改建议"的输出格式不变。

### Q10 — 参考答案

1. 实测：
   - `max_iters=1`：只验证一次初始输出（失败），之后 refine 生成的新输出**从未被验证**，`history` 只有 `[(1, False)]`。CRITIC 的验证结果没有机会转化为一次被确认的改进——讲义练习 1 的答案是"不再有帮助"。
   - `max_iters=2`：`[(1, False), (2, False)]`，第二次输出仍有 Everest 的错误；
   - `max_iters=3`：`[(1, False), (2, False), (3, True)]`，通过。原因是验证器一次只报一个问题（见 Q9），两处错误需要两次 refine。
2. 循环的最后一轮失败后仍然执行了 `output = refine(...)`，这个结果既没被验证也没被返回。`max_iters=2` 时第 2 次 refine 就是浪费的。真实系统中，这是一整次 LLM 调用的延迟和 token，而且调用方拿到的 `history[-1].output` 是**未修正的旧版本**。修复：只在还有下一轮时才 refine，例如

```python
    for i in range(1, max_iters + 1):
        critique, ok = verify(output)
        history.append(Attempt(i, output, critique, ok))
        if ok or i == max_iters:
            break
        output = refine(topic, output, critique, history)
```

或者让循环结构变为"refine 之后立即 verify"，保证最后返回的输出一定经过验证。

### Q11 — 参考答案

1. 只有当验证器对错误输出"放行"时才会带着错误结束。第 1 轮输出错误，误放行概率 0.3；若第 1 轮被正确拦下（0.7），第 2 轮输出仍有 Everest 错误，再次误放行概率 0.3；第 3 轮输出已正确。所以
   `P = 0.3 + 0.7 × 0.3 = 0.51`。
   而循环**每次都会报告"通过"**（实测"声称通过"比例 100%）——这正是危险所在：有噪声的验证器不会让循环跑满，而是让它带着错误自信地停下来。
2. 实测 0.5139，与理论值 0.51 吻合。缓解办法：
   - 降低单个验证器的误放行率：用更可靠的工具（真实测试优于 LLM 判断）；
   - 多个**相互独立**的验证器取"全部通过才算通过"：两个各 30% 误放行的独立验证器同时误放行的概率降为 9%；
   - 抽样复核：对"声称通过"的结果按比例做二次验证或人工抽检；
   - 记录与监控：统计验证器的误报/漏报率，作为 guardrail 栈的健康指标；
   - 高风险输出始终保留人工审核（讲义："budget 1–3 passes; after that, escalate to human review"）。

### Q12 — 参考答案

```python
def should_stop(i, verifier_ok, self_ok, max_iters=4):
    if verifier_ok is True:
        return True, "verifier passed"
    if verifier_ok is None and self_ok and i >= 2:
        return True, "self-eval fine after >=2 iters"
    if i >= max_iters:
        return True, "max iterations"
    return False, ""
```

| i | verifier_ok | self_ok | 结果 |
|---|-------------|---------|------|
| 1 | True | False | 停止：验证器通过（外部验证优先于自评） |
| 1 | None | True | **不停止**：没有外部验证器时，自评说"没问题"也至少要跑到第 2 轮，防止第一轮就被橡皮图章放行 |
| 2 | None | True | 停止：自评通过且迭代 ≥ 2 |
| 2 | False | True | 不停止：外部验证器明确失败时，自评的"没问题"不算数 |
| 4 | False | False | 停止：达到上限（应标记为"未通过"，并考虑转人工） |

（已运行验证。）设计要点：`verifier_ok` 用三值区分"失败"和"没有验证器"；自评只在没有外部验证器时才有权决定停止。讲义写的是不加括号的 "A OR B AND C OR D"，在 Python 中 `and` 优先于 `or`，含义与加括号的版本相同。

### Q13 — 参考回答要点

- **Self-Refine**：同一个 LLM 循环执行"生成 → 自我反馈 → 带历史的精修"，直到反馈说没问题或达到预算；无需训练和工具；讲义称 7 个任务平均 +20 个百分点。
- **CRITIC**：把反馈步骤换成借助外部工具的验证——搜索查事实、代码解释器跑代码、计算器验算、单测/类型检查/linter；批评有工具结果作依据。
- **区别**：信号来源不同——Self-Refine 是模型意见，CRITIC 是环境证据；因此 CRITIC 在事实类任务上更强，而在没有验证器的任务上退化为 Self-Refine。
- **适用**：Self-Refine → 风格、结构、可读性等主观改进（写作、摘要压缩）；CRITIC → 有客观对错的输出（事实问答、代码、数学、数据查询）。
- 加分点：说出 Anthropic 的 evaluator-optimizer 与 OpenAI Agents SDK 的 output guardrails 是这一模式的工程化版本。

### Q14 — 参考回答要点

- **自我验证为何不可靠**：
  - 生成与验证使用同一套参数知识，生成时的错误信念在验证时依然存在（讲义："a hallucination often looks convincing to the model that produced it"）；
  - 模型倾向于认可自己的输出、迎合已有上下文（橡皮图章）；
  - 对精确计算、最新事实、代码执行结果，模型本来就没有可靠的内部检查手段。
- **CRITIC 解决了什么**：把"判断对错"交给有 ground truth 的外部系统，批评具体、可定位（哪一行、哪个事实、哪个测试）。
- **解决不了什么**：
  - 验证器本身的覆盖面和噪声（本节代码的漏检与误报；Q11 的 30% 误放行）；
  - 工具结果也可能被注入或过时（搜索结果不可信，见第 01 节 trust boundary）；
  - 主观质量无法用工具验证，只能退化为 Self-Refine；
  - 测试通过不等于正确（测试覆盖不足、对可见测试过拟合）。
- 加分点：讲义练习 3——用不同模型做批评（大模型生成、小模型批评）是缓解自我认同偏差的低成本手段。

### Q15 — 参考回答要点

- **Prompt**（配套 skill）：
  - generator：明确任务、格式、约束；
  - evaluator：与 generator 风格明显不同，例如对抗式"至少找出一个缺陷"；输出**结构化 JSON**（pass/fail、violations、suggested_fixes），禁止自由文本；
  - optimizer：必须引用历史，明确"不要重复之前被指出的问题"。
- **验证器**：能用工具就用工具（测试、类型检查、schema 校验、搜索）；OpenAI Agents SDK 中写成 output guardrail，失败时抛 `OutputGuardrailTripwireTriggered`，由外层决定重试或拒绝。
- **停止条件**：验证器通过 OR（自评通过 AND 迭代 ≥ 2）OR 迭代 ≥ 上限（默认 4）；skill 建议上限 ≥ 10 时直接重新设计任务。
- **预算**：讲义建议 1–3 轮，超过后转人工；记录每轮 token 与延迟。
- **可观测性**：每轮记录为 OpenTelemetry GenAI span（evaluate、optimize，第 23 节），能回放完整的精修轨迹；统计各验证器的通过率、误报率。
- **安全**：验证器若调用破坏性工具（shell、git 写），必须放进沙箱。
- 常见误区：generator 和 evaluator 共用一个 prompt；把"模型说没问题"当成唯一的停止条件。

### Q16 — 参考回答要点

| 验证层 | 工具 | 能发现的问题 |
|-------|------|-------------|
| 语法 | SQL 解析器 / `EXPLAIN` | 语法错误、方言不兼容 |
| 模式 | 数据库 schema 查询 | 表名、列名不存在，类型不匹配，JOIN 键错误 |
| 安全 | 规则检查 / 只读账号 | 出现 `DROP`、`UPDATE`、无 `WHERE` 的 `DELETE`，越权访问的表 |
| 代价 | `EXPLAIN` 的代价估计 | 全表扫描、笛卡尔积、缺少 `LIMIT` |
| 结果 | 在只读副本或采样数据上执行 | 结果为空、行数异常、与问题中的约束不符（如"上个月"却查出全年数据） |
| 语义 | LLM 评估（与生成 prompt 不同风格） | SQL 是否真正回答了问题（工具无法完全判断，属于 Self-Refine 部分） |

- **循环**：生成 SQL → 逐层验证，汇总为结构化 violations → 带历史精修 → 直到全部硬性检查通过且语义评估通过，或达到 3 轮上限。
- **停止与兜底**：超过上限时返回最后一版并附带未通过的检查项，或请用户澄清问题。
- 加分点：执行验证必须在只读副本、带超时；把"用户确认过的问题 → SQL"沉淀为 few-shot 示例（呼应第 03 节 Reflexion 的记忆思想）。

### Q17 — 参考回答要点

| 维度 | Self-Refine / CRITIC | Reflexion | LATS |
|------|---------------------|-----------|------|
| 改进对象 | 同一个输出，逐轮修改 | 跨多次完整试验，每次从头开始 | 搜索树中的多条候选轨迹 |
| 反馈去向 | 直接进入下一次 refine 的 prompt | 存入 episodic memory，下一次试验读取 | 进入价值估计，并作为反思重新播种 rollout |
| 成本 | 低到中（1–3 轮） | 中（多次完整试验） | 高（CoT 的 100–1000 倍 token） |
| 适合 | 输出"差一点就对" | 同类任务会反复出现 | 单条轨迹明显不够、有可靠价值函数 |

- **3 轮还没通过时**：
  - 先判断是否是**生成 prompt 的问题**：skill 指出精修超过 3–4 轮通常意味着 generator prompt 设计有误；
  - 检查验证器是否有误报（本节代码的跨行误报会让循环永远通不过）；
  - 换策略：升级到更强的模型、搜索（第 04 节）或任务拆解；
  - 转人工审核，并附上历史与未通过的检查项；
  - 把这次失败的原因沉淀为反思或规则，防止下次重演。
- 常见误区：无限提高迭代上限，期待"多改几轮总会好"。

---

## 六、关联知识点

### 前置知识
- [阶段 14 · 01 Agent Loop：观察、思考、行动](../../01-the-agent-loop/docs/zh.md)：讲义练习 3 中"把错误作为 observation 反馈"就是 CRITIC 式纠错的雏形。
- [阶段 14 · 03 Reflexion：语言反馈驱动的 Reinforcement Learning](../../03-reflexion-verbal-rl/docs/zh.md)：跨试验的反思，与本节的单输出精修互为补充。
- [阶段 11 · 10 Evaluation 与 LLM 应用测试](../../../11-llm-engineering/10-evaluation/docs/zh.md)：LLM-as-judge 的偏差与验证器设计。
- [阶段 11 · 12 Guardrails,安全及内容过滤](../../../11-llm-engineering/12-guardrails/docs/zh.md)：output guardrail 的基础。
- [阶段 13 · 04 Structured Output：JSON Schema、Pydantic、Zod 与约束解码](../../../13-tools-and-protocols/04-structured-output/docs/zh.md)：结构化批评（pass/violations）的格式保障。

### 本节被哪些后续内容用到
- [阶段 14 · 04 Tree of Thoughts 与 LATS：审慎搜索](../../04-tree-of-thoughts-lats/docs/zh.md)：搜索中的价值函数同样依赖可靠的验证器。
- [阶段 14 · 12 Anthropic 的工作流模式：优先采用简单方案](../../12-anthropic-workflow-patterns/docs/zh.md)：evaluator-optimizer 是五种工作流模式之一。
- [阶段 14 · 16 OpenAI Agents SDK：Handoffs、Guardrails 与追踪](../../16-openai-agents-sdk/docs/zh.md)：output guardrails 的具体用法。
- [阶段 14 · 23 OpenTelemetry GenAI 语义约定](../../23-otel-genai-conventions/docs/zh.md)：为每轮 evaluate / optimize 记录 span。
- [阶段 14 · 38 Verification Gates](../../38-verification-gates/docs/zh.md)、[阶段 14 · 39 Reviewer Agent：将实现者与评分者分开](../../39-reviewer-agent/docs/zh.md)：把"生成者与评审者分离"做成工程制度。
- [阶段 14 · 30 评估驱动的 Agent 开发](../../30-eval-driven-agent-development/docs/zh.md)：用评测集衡量精修循环是否真的提升质量。

### 延伸关键词
`Self-Refine` · `CRITIC` · `evaluator-optimizer` · `output guardrail` · `OutputGuardrailTripwireTriggered` · `tool-grounded verification` · `refine history` · `rubber-stamp loop` · `stop condition` · `structured critique` · `false pass / false positive` · `LLM-as-judge`
