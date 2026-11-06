# 测验 · Structured Outputs & 约束解码（Structured Outputs & Constrained Decoding）

> **阶段 05 · NLP 从基础到进阶 · 第 20 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过 `main.py` 后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 三层方案 | Prompting（约 80% 可靠）→ 厂商原生 structured output API（可靠但绑定厂商）→ 约束解码（构造上 100% 合法，可用于任何本地模型） |
| 2 | 约束解码原理 | 每一步生成前，logit processor 根据语法当前状态，把所有非法 token 的 logit 设为 `-inf`，softmax 后概率只落在合法续写上 |
| 3 | FSM 方案（Outlines） | 把 JSON Schema / 正则编译成有限状态机，每步 O(1) 查合法 token；递归 schema 需要展平到固定深度 |
| 4 | CFG 方案（XGrammar / llguidance） | 上下文无关文法引擎，能处理递归 JSON Schema，解码开销接近于零 |
| 5 | Instructor | 基于 Pydantic，不改 logits：把 schema 写进 prompt → 解析 → 校验失败就重试；跨厂商但增加延迟与成本 |
| 6 | 反直觉：约束解码常常更快 | 合法 token 搜索空间更小；`{"name": "` 这类被完全确定的脚手架 token 可以直接输出、跳过生成 |
| 7 | 字段顺序就是逻辑 | `answer` 放在 `reasoning` 前面，模型会先定答案再"编理由"；JSON 合法，答案却错，校验抓不到 |
| 8 | 语法过严 | 强制 `YYYY-MM-DD` 时模型无法表达"未知"，只好编一个日期；要允许 `null` 或哨兵值 |
| 9 | JSON mode ≠ schema | 纯 JSON mode 只保证语法合法，不保证字段符合你的 schema；必须提供完整 schema |

### 核心技能（能动手做到）

- [ ] 用纯 Python 实现"FSM + logit 掩码 + softmax + 采样"的约束解码循环，并在 20 个样本上验证 100% 合法
- [ ] 能计算"随机 logits 无约束生成"命中目标格式的期望概率，解释为什么无约束版本几乎全部失败
- [ ] 能找出采样函数中"浮点误差回退到非法 token"这类边界 bug 并修复
- [ ] 能把单一电话号码 FSM 推广为"多模板 FSM"（例如允许 `unknown` 哨兵值）
- [ ] 能把字符级 FSM 提升到 token 级：给定词表，算出当前状态下哪些多字符 token 合法
- [ ] 能根据"厂商 / 是否本地模型 / schema 是否递归 / 能否容忍重试"选择 vendor API、Instructor、Outlines、XGrammar/llguidance 或 vLLM guided decoding
- [ ] 能设计一个 schema：reasoning 在前、answer 在后，未知字段可为 `null`，并给出合规率、语义正确率、p50/p99 延迟的验证计划

---

## 二、基础自测（选择题）

**Q1.** 约束解码在每一步生成时修改的是：

- A. 模型权重
- B. tokenizer 的词表
- C. 下一个 token 的 logit 向量：把非法 token 设为 `-inf`
- D. KV cache 中已经生成的内容

**Q2.** 关于 Instructor 的工作方式，正确的是：

- A. 它在本地模型的 logits 上做 FSM 掩码
- B. 它把 schema 写进 prompt，解析输出，校验失败则重试；不修改 logits
- C. 它只能配合 OpenAI 使用
- D. 它通过微调让模型学会输出 JSON

**Q3.** 你需要让本地模型输出一棵深度不固定的评论树（评论里嵌套回复，回复里还能再嵌套）。讲义推荐：

- A. Outlines（FSM）
- B. 纯 JSON mode
- C. XGrammar 或 llguidance（CFG）
- D. 只靠 prompt 约束

**Q4.** 下面哪种 schema 字段顺序更好，原因是什么？

```json
// 方案 1
{"answer": "yes", "reasoning": "because ..."}
// 方案 2
{"reasoning": "... therefore ...", "answer": "yes"}
```

- A. 方案 1，答案在前便于下游快速读取
- B. 方案 2，模型按顺序生成，先写推理再给答案，避免"先下结论再找理由"
- C. 两者等价，JSON 对象的字段本来就是无序的
- D. 方案 1，因为约束解码只校验第一个字段

**Q5.** 讲义说约束解码"常常比无约束生成更快"，原因是：

- A. 约束解码会自动换用更小的模型
- B. 合法 token 的搜索空间更小，而且被完全确定的脚手架 token 可以跳过生成
- C. 约束解码跳过了 softmax
- D. 约束解码不需要 tokenizer

**Q6.** 给日期字段加了严格正则 `\d{4}-\d{2}-\d{2}`，上线后发现一些发票的"到期日"是模型编造的。最合理的修改是：

- A. 换一个更大的模型
- B. 允许该字段为 `null` 或一个哨兵值（如 `"unknown"`）
- C. 去掉所有约束，回到纯 prompt
- D. 把正则改成 `\d{8}`

**Q7.** 你的 schema 里有一个 10,000 个选项的 enum（商品 SKU），编译非常慢甚至超时。讲义建议：

- A. 把 enum 改成任意字符串，事后再校验
- B. 先用检索器预测 top-k 候选，再把约束限制在这 k 个候选上
- C. 换用 JSON mode
- D. 把 10,000 个选项写进 system prompt

---

## 三、动手 / 代码题

**Q8.** `main.py` 的无约束生成中，每一步的 logits 是 11 个独立的 `gauss(0, 1.5)`（字母表为 10 个数字加 `-`），输出长度固定 12。

```python
def fake_llm_logits(alphabet, rng):
    return [rng.gauss(0.0, 1.5) for _ in alphabet]
```

1. 估算无约束生成恰好匹配 `^\d{3}-\d{3}-\d{4}$` 的期望概率。
2. 运行结果是 `valid: 0 / 20`，这与你的估算一致吗？

**Q9.** 找 bug：下面是 `main.py` 中的 `sample`。在约束解码里，某个数字位置上 `-` 的概率被掩码为 0。请说明这个函数在什么极端情况下仍会返回 `-`，后果是什么，并给出修复。

```python
def sample(probs, rng):
    r = rng.random()
    acc = 0.0
    for i, p in enumerate(probs):
        acc += p
        if r <= acc:
            return i
    return len(probs) - 1
```

**Q10.** 讲义的坑之一是"语法过严，模型无法表达未知"。请仿照 `PhoneFSM` 的接口（`valid_next / transition / is_accept`），写一个 `TemplateFSM(templates)`：模板中 `d` 表示任意数字、其余字符必须原样匹配；状态用"已生成的前缀字符串"表示。用它约束 `["dddd-dd-dd", "unknown"]`，在字母表 `list("0123456789-unkow")` 上生成 200 个样本，验证全部匹配 `\d{4}-\d{2}-\d{2}|unknown`。生成结果里出现 `9873-26-10` 这样的输出，说明了什么？

**Q11.** `main.py` 是**字符级**的：每一步只产生一个字符。真实 LLM 的 token 可能是 `"12"`、`"45-"`、`"-5678"` 这样的多字符片段。请写 `valid_token_ids(fsm, state, vocab)`，返回从 `state` 出发、能让 `PhoneFSM` **整段走通**的 token 下标。用 `vocab = ["0", "12", "123", "-", "-4", "45-", "1234", "a", "-5678"]` 分别求 state = 0、1、3、7 时的合法 token。

---

## 四、面试高频题

**Q12.**（基础必考）让 LLM 稳定输出结构化数据，有哪几种方案？各自的可靠性、适用场景和代价是什么？

**Q13.**（原理深挖）约束解码的 logit processor 是怎么工作的？FSM 和 CFG 两种实现有什么区别？为什么"token 和语法符号不对齐"是工程实现的难点？

**Q14.**（工程实践）一个结构化抽取服务"JSON 合规率 100%"，但业务方反馈结果经常是错的。你会从 schema 设计角度排查哪些问题？

**Q15.**（场景设计）设计一个发票抽取服务：既要支持调用 Claude/GPT 等托管模型，也要支持私有化部署的开源模型；要求 100% 可解析、能区分"缺失"和"真实值"、延迟可控。请给出方案。

**Q16.**（追问型）既然约束解码能保证 100% 合法，为什么不在所有场景都开最严格的约束？约束会带来什么副作用？

---

## 五、参考答案与解析

### Q1 — 答案：C

约束解码是**推理时**的技术：logit processor 位于模型与采样器之间，按语法状态把非法 token 的 logit 设为 `-inf`，softmax 后这些 token 概率为 0。它不改权重（A）、不改词表（B），也不改已生成的内容（D）。

### Q2 — 答案：B

讲义明确指出 Instructor "不碰 logits"：把 schema 格式化进 prompt，解析输出，验证失败就重试。好处是跨厂商可移植，代价是重试带来的额外延迟和费用。A 描述的是 Outlines；C 错，它支持多家厂商；D 与微调无关。

### Q3 — 答案：C

FSM 无法表示无界递归，Outlines 只能把递归展平到固定深度。树形结构（嵌套评论、AST）需要 CFG 引擎，讲义推荐 XGrammar 或 llguidance。B、D 都无法保证结构合法。

### Q4 — 答案：B

自回归模型**按顺序**生成：`answer` 在前，模型在还没"思考"时就必须做出决定，后面的 `reasoning` 只能为既定答案辩护。C 的错误在于：JSON 语义上字段无序，但**生成过程**是有序的。讲义总结："Schema field order is logic, not formatting."

### Q5 — 答案：B

两个原因：①下一 token 的候选集合变小；②像 `{"name": "` 这样每个字节都被语法确定的脚手架，聪明的实现可以直接写入、跳过前向计算。A、C、D 都不是事实——softmax 仍然要算。

### Q6 — 答案：B

过严的语法剥夺了模型表达"不知道"的出口，它只能在合法空间里挑一个看起来合理的日期——也就是编造。正确做法是让字段可为 `null` 或提供哨兵值。A 解决不了约束本身的问题；C 放弃了可靠性；D 只是换了一个同样严格的格式。

### Q7 — 答案：B

讲义原话：超大 enum 编译慢或超时，应改为先用检索器预测 top-k 候选，再约束到这些候选上。A 放弃了约束；C 只保证 JSON 语法；D 让 prompt 爆炸且不保证合法。

### Q8 — 参考答案

1. 每一步的 11 个 logits 独立同分布，由对称性，任一字符被选中的期望概率都是 1/11；各步之间独立，所以整串合法的期望概率是：

```
P = (10/11)^10 × (1/11)^2 ≈ 0.385 × 0.00826 ≈ 0.0032（约 0.32%）
```

即 10 个数字位都要选中数字，2 个连字符位都要恰好选中 `-`。

2. 一致。20 个样本的期望合法数约为 `20 × 0.0032 ≈ 0.06`，几乎不可能出现合法样本。这说明约束解码的价值不在于"模型更聪明"，而在于把概率 0.32% 的事件变成**构造上必然**：同样的随机 logits，加了掩码后 20/20 合法。

### Q9 — 参考答案

问题出在最后一行的回退。`softmax` 归一化后，`acc` 的最终值可能因浮点舍入略小于 1（例如 `0.9999999999999999`）。如果 `rng.random()` 恰好落在 `(acc, 1)` 区间，循环结束仍未返回，函数回退到 `len(probs) - 1`，也就是字母表最后一个字符 `-`——而它在数字位置上的概率是 0。

后果：`fsm.transition(state, "-")` 返回 `None`，`generate_constrained` 执行 `break`，输出一个不完整、不合法的字符串。这破坏了"构造上 100% 合法"的承诺。概率极低，但正是这种 bug 在生产中最难复现。

修复：回退到**最后一个概率大于 0 的下标**，或者直接用标准库按权重采样。

```python
def sample(probs, rng):
    r = rng.random() * sum(probs)          # 按实际总和缩放
    acc = 0.0
    last_valid = None
    for i, p in enumerate(probs):
        if p <= 0:
            continue
        last_valid = i
        acc += p
        if r < acc:
            return i
    return last_valid                       # 只会回退到合法 token
```

或者：`return rng.choices(range(len(probs)), weights=probs, k=1)[0]`，权重为 0 的下标不会被选中。

### Q10 — 参考答案

```python
class TemplateFSM:
    """state = 已生成的前缀；模板中 'd' 表示任意数字，其余字符必须原样匹配。"""
    def __init__(self, templates):
        self.templates = templates

    def _ok(self, t, prefix):
        if len(prefix) > len(t):
            return False
        return all((tc == "d" and pc.isdigit()) or tc == pc
                   for tc, pc in zip(t, prefix))

    def valid_next(self, state):
        nxt = set()
        for t in self.templates:
            if len(t) > len(state) and self._ok(t, state):
                tc = t[len(state)]
                nxt.update("0123456789" if tc == "d" else tc)
        return sorted(nxt)

    def transition(self, state, ch):
        return state + ch if ch in self.valid_next(state) else None

    def is_accept(self, state):
        return any(len(t) == len(state) and self._ok(t, state)
                   for t in self.templates)
```

`main.py` 的 `generate_constrained` 写死了 `state = 0`，需要把初始状态改成 `""`（或加一个 `initial` 参数），其余逻辑不变。实测 200 个样本全部匹配 `\d{4}-\d{2}-\d{2}|unknown`，其中 22 个是 `unknown`——第一步有 11 个合法字符（10 个数字 + `u`），随机 logits 下选中 `u` 的期望概率是 1/11，约 18 个，实测 22 个在合理范围内。

`9873-26-10` 说明：**语法合法 ≠ 语义合法**。正则只约束字符形状，月份 26 依然能通过。这对应讲义 Ship It 里把"schema 合规率"和"语义正确率（LLM-judge）"分开验证的要求；生产中要么写更精细的文法（月份只能 01–12），要么在解码后做业务校验。

### Q11 — 参考答案

```python
def valid_token_ids(fsm, state, vocab):
    ok = []
    for tid, tok in enumerate(vocab):
        s = state
        for ch in tok:
            s = fsm.transition(s, ch)
            if s is None:
                break
        if s is not None:
            ok.append(tid)
    return ok
```

结果：

| state | 含义 | 合法 token |
|---|---|---|
| 0 | 还没开始 | `0`、`12`、`123` |
| 1 | 已有 1 位数字 | `0`、`12`、`45-` |
| 3 | 需要第一个 `-` | `-`、`-4` |
| 7 | 需要第二个 `-` | `-`、`-4`、`-5678` |

要点：
- `123` 在 state 1 不合法（会在需要 `-` 的位置放数字），`45-` 却合法——一个 token 可以**跨越语法边界**。
- `-5678` 只在 state 7 合法，因为它正好走到接受状态 12。
- 这就是讲义 `valid_tokens(state, tokenizer)` 要做的事。逐 token 模拟的代价是 O(|V| × token 长度)，10 万词表每步都这么算太慢，所以 Outlines 会在编译期为每个 FSM 状态**预计算**合法 token 集合，生成时 O(1) 查表。

### Q12 — 参考回答要点

| 方案 | 可靠性 | 适用 | 代价 |
|---|---|---|---|
| Prompting | 讲义：前沿模型约 80%，小模型更低 | 原型、非关键路径 | 需要容错解析 |
| 厂商原生 API（OpenAI `response_format`、Anthropic tool use、Gemini JSON mode） | 对支持的 schema 很可靠，服务端约束解码 | 托管模型、schema 简单 | 绑定厂商；schema 能力受限 |
| Instructor（Pydantic + 重试） | 依赖重试，最终通过率高但非构造保证 | 跨厂商、可容忍重试、批处理 | 重试增加延迟和费用 |
| 约束解码（Outlines / XGrammar / llguidance / vLLM guided decoding） | 构造上 100% 合法 | 本地/自部署模型 | 需要控制推理栈；递归 schema 要选 CFG 引擎 |

- 加分点：说出"JSON mode 只保证语法，不保证 schema"；能按讲义的选型表给出决策。
- 常见误区：认为结构化输出只是 prompt 技巧。

### Q13 — 参考回答要点

- **工作流程**：模型输出全词表 logits → processor 根据语法当前状态求合法 token 集合 → 非法位置设 `-inf` → softmax、采样 → 用采样到的 token 推进语法状态 → 循环直到接受状态。
- **FSM（Outlines）**：把正则/JSON Schema 编译成有限状态机，可以预先为每个状态算好合法 token 集合，生成时 O(1) 查表；但 FSM 无法表达无界嵌套，递归 schema 只能展平到固定深度。
- **CFG（XGrammar、llguidance）**：用上下文无关文法（需要栈）表达递归结构，如任意深度的 JSON；讲义称其解码开销接近于零，OpenAI 在 2025 年的 structured output 实现中致谢了 llguidance。
- **token 与语法不对齐**：BPE token 可能是 `"},"`、`"45-"` 这样跨越多个语法符号的片段，也可能只是一个字符串字面量的一半。合法性判断必须"把 token 的每个字符喂给状态机看能否走通"（见 Q11），而词表有 10 万级别，所以需要预计算和缓存。
- 加分点：把它和第 19 节的子词切分联系起来；提到 vLLM 的 `guided_json`、`guided_regex`、`guided_choice`、`guided_grammar`。

### Q14 — 参考回答要点

1. **字段顺序**：`answer`/`decision` 是否放在 `reasoning` 前面？是的话模型在思考前就锁定了答案（讲义：premature commitment）。
2. **缺少"未知"出口**：必填字段 + 严格格式会迫使模型编造。检查是否允许 `null`/哨兵值。
3. **只用 JSON mode 没给 schema**：语法合法但字段名、类型、枚举值不受控。
4. **约束过粗**：正则只管形状不管语义（如月份 26），需要更细的文法或后置业务校验。
5. **超大 enum 被换成了自由字符串**：导致模型输出不在集合中的值。
- 验证：按讲义 Ship It 的计划，分别统计 schema 合规率（目标 100%）、语义正确率（LLM-judge 或人工标注）、字段覆盖率、p50/p99 延迟。合规率高只说明"格式对"。

### Q15 — 参考回答要点

- **统一的 schema 层**：用 Pydantic 定义 `Invoice`，一份定义同时生成 JSON Schema 供各后端使用。字段顺序：先放证据/推理类字段（如 `evidence_span`），再放结论字段；`due_date: str | None`，允许缺失。
- **托管模型**：走厂商原生 structured output（服务端约束解码），并提供完整 schema，不用裸 JSON mode。
- **私有化模型**：自部署推理服务用 vLLM guided decoding；schema 有递归时选 XGrammar/llguidance 后端。
- **兜底**：跨厂商需要统一行为时用 Instructor，设最大重试次数与降级模型；仍失败就返回显式的失败状态，而不是猜一个值。
- **后置业务校验**：金额 `>= 0`（讲义例子 `Field(ge=0)`）、明细金额之和与总额一致、日期合法。
- **监控**：合规率、语义正确率、字段覆盖率、重试率、p50/p99 延迟；按模型/版本分桶。
- 加分点：主动提出 schema 中的字段顺序与 `null` 设计，并说明"约束解码保证格式、业务校验保证语义"。

### Q16 — 参考回答要点

- **保证的只是格式**：约束解码让非法输出不可达，但不让答案变正确。
- **副作用 1：过早承诺**——字段顺序设计不当时，约束会强迫模型在推理前给出答案。
- **副作用 2：语法过严导致编造**——没有出口时模型只能在合法空间里挑一个，例如编日期。
- **副作用 3：分布被扭曲**——掩码后在剩余 token 上重新归一化，如果模型本来"想"走的路径被禁止，剩下的高概率路径未必合理；过窄的约束也可能压制模型的推理过程（可以把自由文本推理放进 `reasoning` 字段来缓解）。
- **工程代价**：超大 enum 编译慢；FSM 库处理不了递归 schema；需要掌控推理栈。
- 结论：约束要"刚好够用"——允许 `null`/哨兵、推理在前、超大枚举先检索再约束，并用语义正确率而非合规率来验收。

---

## 六、关联知识点

### 前置知识
- [阶段 05 · 17 聊天机器人](../../17-chatbots-rule-to-neural/docs/zh.md)：LLM 作为对话/工具组件的基本用法。
- [阶段 05 · 19 子词 Tokenization](../../19-subword-tokenization/docs/zh.md)：约束是在 token 级别施加的，必须理解 BPE token 如何跨越字符边界。
- [阶段 05 · 16 Transformers 之前的文本生成](../../16-text-generation-pre-transformer/docs/zh.md)：逐 token 生成、softmax 与采样的基本流程。

### 本节被哪些后续内容用到
- [阶段 11 · 03 Structured Outputs](../../../11-llm-engineering/03-structured-outputs/docs/zh.md)：在 LLM 应用工程中系统使用结构化输出。
- [阶段 11 · 09 Function Calling](../../../11-llm-engineering/09-function-calling/docs/zh.md)：工具调用参数本质上是受 schema 约束的 JSON。
- [阶段 13 · 04 Structured Output](../../../13-tools-and-protocols/04-structured-output/docs/zh.md) 与 [阶段 13 · 05 工具 Schema 设计](../../../13-tools-and-protocols/05-tool-schema-design/docs/zh.md)：在工具协议层设计 schema。
- [阶段 17 · 04 vLLM 服务内部机制](../../../17-infrastructure-and-production/04-vllm-serving-internals/docs/zh.md)：guided decoding 在推理服务中的集成位置。
- [阶段 19 · 21 工具注册表与 Schema 校验](../../../19-capstone-projects/21-tool-registry-schema-validation/docs/zh.md)：项目中落地 schema 校验。

### 延伸关键词
`logit processor` · `Outlines` · `XGrammar` · `llguidance` · `lm-format-enforcer` · `vLLM guided_json / guided_regex / guided_choice / guided_grammar` · `Instructor` · `Pydantic` · `JSONSchemaBench` · `JSON mode vs json_schema` · `premature commitment`
