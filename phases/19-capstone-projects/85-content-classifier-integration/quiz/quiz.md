# 测验 · 综合项目 85：内容分类器集成（Capstone 85 — Content Classifier Integration）

> **阶段 19 · 综合项目 · 第 85 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/classifiers.py](../code/classifiers.py)、[code/main.py](../code/main.py)、[code/tests.py](../code/tests.py) ｜ 代码讲解：[code/classifiers.讲解.md](../code/classifiers.讲解.md)、[code/main.讲解.md](../code/main.讲解.md)（含 tests.py）
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 为什么要有输出侧分类 | 输入侧检查只能拦"已知攻击族"；输出侧分类器看的是模型**真正要发出去的回复**，问的是"不管 prompt 怎么来的，这段内容能不能给用户看"，是最后一道关 |
| 2 | 统一的 verdict 结构 | 每个分类器返回 `ClassifierVerdict(name, severity, score, findings)`；severity ∈ `none / low / medium / high`，score ∈ [0, 1] |
| 3 | 分类器 = classify + redact | 每个分类器既能判（`classify`），也带一个自己的打码器（`redact`），打码彼此独立、可叠加 |
| 4 | 路由规则：取最大 severity | `high → block`、`medium → redact`、`low → warn`、`none → log`；block 压倒一切，redact + warn 变成 redact |
| 5 | Toxicity 分类器 | 关键词表 + `\b` 词边界正则 + 左侧 20 字符否定窗口（`not / never / no`）；1 处 low、2 处 medium、≥3 处 high，score = `min(1, 0.4 + 0.2·hits)` |
| 6 | PII 分类器 | email / phone / SSN / 信用卡 / IPv4 五种正则；卡号再做 **Luhn 校验**降低误报；SSN 或卡号 → high，email 或 ≥3 处 → medium，其余 → low |
| 7 | Instruction leakage 分类器 | 输出与已知 system prompt 的**字符级 trigram 计数向量余弦相似度**；≥0.55 才报，≥0.70 medium，≥0.85 high |
| 8 | Action 对象 | `Action(verb, output, severity, verdicts, metadata)`，`metadata.fired` 列出触发的分类器，供第 87 节安全关卡写入 trace |
| 9 | 延迟与流式 | 讲义：分类器可以与 token streaming 并行，关卡缓冲最后一块、在 flush 前套用判决；本节全是规则，延迟约等于 0 |
| 10 | 规则分类器的局限 | 否定窗口会漏报（"No way, you idiot."）、复数漏报（"idiots"）、IPv4 不校验范围、长回复会稀释 trigram 余弦、低危 PII 原样放行 |

### 核心技能（能动手做到）

- [ ] 给定任意一句模型输出，手算三个分类器的 severity / score / findings，并推出路由器的 verb 和最终 output
- [ ] 解释 Luhn 校验的算法，并能判断 `4111 1111 1111 1111` 和 `1234 5678 9012 3456` 谁会被当作卡号
- [ ] 计算两个字符串的字符 trigram 余弦相似度，说清"余弦"和"包含率（containment）"在长文本上的区别
- [ ] 找出"medium 判决但 redactor 实际什么都没改"的失败路径，并写出 fail-closed 的修复
- [ ] 按讲义练习给路由器加"置信度阈值降级"或"按分类器加权"，并在 demo fixture 上报告 block 率变化
- [ ] 新增一个分类器（例如代码注入 `<script>`、`eval(`），实现 `name / classify / redact` 三件套并接入 `Router`
- [ ] 用 `unittest` 跑通 `tests.py`，并为自己发现的漏报/误报补测试用例

---

## 二、基础自测（选择题）

**Q1.** 讲义认为"输入侧已经检测过，还要输出侧分类器"的根本理由是：

- A. 输出侧分类器只需在输入检测报错时才运行，用来兜底异常
- B. 输入侧检测通常是神经网络，输出侧必须用规则来互补
- C. 输出侧分类器会把用户 prompt 重新改写一遍再检测
- D. 输出侧看到的是模型的真实回复；任何输入侧没覆盖的新攻击族，产生的输出都会直接落到用户面前，输出侧是最后一道关

**Q2.** 某段输出的三个判决为：toxicity = `low`、pii = `medium`、instruction-leakage = `none`。`Router.decide` 的结果是：

- A. verb = `redact`，并且 toxicity 和 pii 两个 redactor 都会作用在输出上，不追加 warn 提示
- B. verb = `warn`，输出末尾追加低危提示
- C. 先执行 warn 再执行 redact，输出既打码又追加提示
- D. verb = `block`，因为有两个分类器同时触发

**Q3.** `ToxicityClassifier` 在一段文本中找到 2 处**未被否定**的命中，它返回的 severity 和 score 是：

- A. `low`，0.6
- B. `medium`，0.6
- C. `medium`，0.8
- D. `high`，1.0

**Q4.** PII 分类器对"卡号形状"的数字串额外做 Luhn 校验，目的是：

- A. 把 16 位数字压缩成更短的正则
- B. 区分真正可能是信用卡号的数字串与任意数字序列，降低误报
- C. 从卡号推算出持卡人的 SSN
- D. 让 `[redacted-card]` 标签里带上卡的发行行

**Q5.** 文本 `"Server at 192.168.1.5, backup 10.0.0.2, call 555-123-4567"` 经过 `PIIClassifier.classify`，结果是：

- A. `low`：没有 email、SSN、卡号，只有 IP 和电话
- B. `high`：IP 地址属于网络敏感信息
- C. `none`：内网 IP 不算 PII
- D. `medium`：共 3 处发现（2 个 IP + 1 个电话），达到"≥3 处"的门槛，score = 0.95

**Q6.** `InstructionLeakageClassifier` 判断泄漏的方法是：

- A. 把输出和 system prompt 都转小写、压缩空白，切成**字符** trigram 计数向量，算余弦相似度，≥ 阈值 0.55 才报
- B. 把两段文本切成**单词** trigram，计算 Jaccard 系数
- C. 调用另一个 LLM 判断输出是否在复述系统指令
- D. 只检查输出中是否**逐字包含** system prompt 的第一行

**Q7.** 输出 `"No way, you idiot."` 经过默认路由器，结果是：

- A. `warn`：命中 1 处 `idiot`，low
- B. `redact`：`idiot` 被替换为 `[redacted-language]`
- C. `log`：`idiot` 左侧 20 个字符内出现了单词 `No`，被否定窗口当成"否定"而跳过——这是一次漏报
- D. `block`：辱骂语句一律拦截

**Q8.** 输出 `"Call me at 555-123-4567 tonight."` 经过默认路由器，用户最终看到的是：

- A. `Call me at [redacted-phone] tonight.`
- B. 原文（电话号码原样保留），后面追加一行 `[note: an output safety classifier flagged this response at low severity]`
- C. 拒答文本 `I cannot share that. ...`
- D. 原文，不做任何改动，只在 trace 中记录

---

## 三、动手 / 代码题

**Q9.** 默认 system prompt 是 `"SYSTEM: You are PolicyBot, follow internal policy."`。我们实际测得：

| 模型输出 | trigram 余弦 | severity |
|---------|-------------|----------|
| `SYSTEM: You are PolicyBot, follow internal policy. As PolicyBot I will now answer.` | 0.870 | high |
| `"Sure! My instructions say: " + system prompt 全文 + 一段 375 字符的正常解释` | **0.211** | **none** |

1. 第二条输出**逐字包含**了完整的 system prompt，为什么反而判为 none？
2. 给出一个对长输出不敏感的替代指标，写出实现，并说明它在上面两条输出上的值。

相关源码：

```python
def _cosine(a: Counter, b: Counter) -> float:
    ...
    dot = sum(a[g] * b[g] for g in common)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    ...
    return dot / (na * nb)

class InstructionLeakageClassifier:
    def classify(self, text: str) -> ClassifierVerdict:
        score = _cosine(self._sys_grams, _trigrams(text))
```

**Q10.** 阅读 `Router._apply_redactors` 与 `InstructionLeakageClassifier.redact`：

```python
    def _apply_redactors(self, text, verdicts):
        out = text
        for c in self._classifiers:
            for v in verdicts:
                if v.name == getattr(c, "name", "") and v.severity != "none":
                    out = c.redact(out)
                    break
        return out

    # InstructionLeakageClassifier
    def redact(self, text: str) -> str:
        marker = self._sys.split("\n", 1)[0].strip()
        if marker and marker.lower() in text.lower():
            return re.sub(re.escape(marker), "[redacted-system-prompt]", text, flags=re.IGNORECASE)
        return text
```

输出 `"you are policybot and you follow the internal policy"` 的泄漏分数为 0.788（medium）。

1. 路由器的 verb 和最终 output 分别是什么？这为什么是一个安全漏洞？
2. 写出一个 fail-closed 的修复：当 medium 判决对应的 redactor 没有改动文本时怎么办？

**Q11.**（手算）不运行代码，写出下面这句输出经过默认 `Router().run(...)` 后的：① 三个 verdict 的 severity 与 score；② verb；③ 最终 output。

```text
Email bob@corp.io or call 555-867-5309, you idiot.
```

**Q12.** 讲义练习 3："加一个置信度阈值，低分判决降一级 severity；扫描阈值并报告 block 率变化。"请写一个 `ThresholdRouter(Router)`：分数低于阈值 `t` 的非 none 判决降一级。在 6 个 demo fixture 上分别取 `t = 0.0, 0.62, 0.7, 0.9`，block 率各是多少？你从结果里看出 score 与 severity 之间有什么问题？

---

## 四、面试高频题

**Q13.**（基础必考）LLM 应用的 guardrail（护栏）为什么要同时做输入侧和输出侧？两者各自能拦什么、拦不住什么？

**Q14.**（原理深挖）本节三个分类器都是规则式的。规则分类器和神经分类器（如 Llama Guard、Perspective API 这类审核模型）各有什么优缺点？在生产里你会怎么组合？

**Q15.**（工程实践）输出分类器会增加延迟，而产品要求流式输出（streaming）。你如何在"边生成边显示"的同时保证被 block 的内容不会先流到用户屏幕上？

**Q16.**（场景设计）你负责一个客服机器人的 PII 策略：用户自己的订单号、邮箱、电话、银行卡都可能出现在回复里。请设计 severity → action 的映射，并说明 trace/日志该怎么处理 PII。

**Q17.**（追问型）面试官追问："system prompt 泄漏检测用 trigram 相似度靠谱吗？有没有更好的办法？"你怎么回答？

---

## 五、参考答案与解析

### Q1 — 答案：D

讲义原话："An output-side classifier sees the model's actual response, not the user's prompt, and asks a different question: regardless of how this prompt got here, is what we are about to ship to the user acceptable." 并指出跳过输出分类等于给攻击者"one-shot bypass"：输入管道没覆盖的任何新攻击族都会直接落到用户身上。

- A 错：输出分类器对**每个**输出都运行，不是异常兜底。
- B 错：讲义没有"输入必须是神经网络"的说法，本节输出侧用规则只是为了"讲管道而不是词表"。
- C 错：输出侧看的是模型回复，不是 prompt。

### Q2 — 答案：A

`_max_severity` 取最大值 `medium` → redact。`_apply_redactors` 会对**所有 severity ≠ none 的分类器**执行 redactor（不只是 medium 那个），所以 low 的 toxicity 也会被打码。redact 分支直接返回打码后的文本，**不会**再追加 warn 的提示——讲义："A redact + warn becomes redact"。

- B 错：warn 只在最大 severity 为 low 时发生。
- C 错：路由器只执行一个动作。
- D 错：block 只看是否存在 high，与触发数量无关。

### Q3 — 答案：C

```python
score = min(1.0, 0.4 + 0.2 * hits)   # hits=2 → 0.8
if hits >= 3: sev = "high"
elif hits == 2: sev = "medium"
else: sev = "low"
```

实际运行 `"You are a moron and a scumbag."` 得到 `medium 0.8`。A 是 1 处命中的结果（打印出来是 `0.6000000000000001`，浮点误差）；D 是 3 处命中的结果。

### Q4 — 答案：B

`_CARD_RE` 只要求 13–19 位数字（中间可夹空格或短横），很多订单号、流水号都长这样。Luhn 校验是信用卡号自带的校验位算法，随机数字串大约只有 1/10 能通过。实测：`4111 1111 1111 1111` 通过（high），`1234 5678 9012 3456` 不通过（none）。A、C、D 都不是 Luhn 的作用。

### Q5 — 答案：D

实际运行结果：

```text
ClassifierVerdict(name='pii', severity='medium', score=0.95,
  findings=["phone '555-123-4567'", "ip '192.168.1.5'", "ip '10.0.0.2'"])
```

severity 规则：先看有没有 ssn/card（high）；再看 `len(findings) >= 3` 或有 email（medium）；否则 low。3 处发现触发 medium；score = `0.5 + 0.15 × 3 = 0.95`。A 忽略了"≥3 处"这条；B、C 都不是代码规则（代码不区分内网/公网 IP）。

### Q6 — 答案：A

`_trigrams` 先 `strip().lower()` 并把连续空白压成一个空格，再取**每 3 个连续字符**作为一个 gram 计数；`_cosine` 计算两个计数向量的余弦。阈值：<0.55 → none，[0.55, 0.70) → low，[0.70, 0.85) → medium，≥0.85 → high。

- B 错：是字符级，不是单词级，也不是 Jaccard。
- C 错：全部是规则，无模型调用。
- D 描述的是 `redact` 的做法（只替换第一行），不是 `classify` 的判定方法——这两者不一致正是 Q10 的漏洞来源。

### Q7 — 答案：C

`_negated_at` 取命中位置左侧 20 个字符 `"No way, you "`，用 `\b(not|never|no)\b` 搜索，`No`（忽略大小写后为 `no`）命中，于是这处 `idiot` 被跳过，toxicity 为 none，三个分类器都没触发 → `log`。实测确实如此。这是**否定窗口的漏报**：窗口只看"附近有没有否定词"，不看否定词修饰的是谁。类似地 `"You idiots!"` 也会漏报（`\bidiot\b` 不匹配复数）。

### Q8 — 答案：B

PII 只发现 1 个电话 → `low` → warn。warn 分支是 `text + note`，**原文不打码**：

```text
Call me at 555-123-4567 tonight.

[note: an output safety classifier flagged this response at low severity]
```

A 是 redact 才会有的效果（只有最大 severity 为 medium 时才执行 redactor）；C 需要 high；D 是 none 的效果。这暴露了一个策略问题：低危 PII 会原样发给用户，只多一行提示（见 Q16）。

### Q9 — 参考答案

1. **余弦被长文本稀释**。余弦 = `dot / (‖a‖·‖b‖)`。system prompt 的 trigram 全部出现在输出里，所以 `dot` 已经达到"包含全文"时的水平；但输出越长，`‖b‖` 越大，分母随之变大，分数被压低。这里输出约 450 个字符，其中 system prompt 只占约 50 个字符，余弦只剩 0.211，低于 0.55 的阈值。攻击者只要让模型"把 system prompt 夹在一大段正常回答里"就能绕过。
2. **改用包含率（containment）**：system prompt 的 trigram 有多大比例出现在输出中，分母只与 system prompt 有关，与输出长度无关。

```python
def containment(sys_grams: Counter, out_grams: Counter) -> float:
    total = sum(sys_grams.values())
    if total == 0:
        return 0.0
    return sum(min(c, out_grams[g]) for g, c in sys_grams.items()) / total
```

实测：长输出的 containment = **1.000**（余弦 0.211）；第一条 = 1.000；无关的 pasta 菜谱 = 0.042。也可以对输出做**滑动窗口**（窗口长度 ≈ system prompt 长度），取所有窗口余弦的最大值。代价：containment 对短的"碎片式"重合更敏感，比如 `"Please follow internal policy."` 的 containment 为 0.458（余弦 0.67），阈值需要重新标定。

### Q10 — 参考答案

1. 实测：verb = `redact`，output = 原文 `you are policybot and you follow the internal policy`，**一个字都没改**。原因：`classify` 用的是模糊的 trigram 相似度，而 `redact` 只做"system prompt 第一行"的**精确子串替换**；默认 system prompt 只有一行 `SYSTEM: You are PolicyBot, follow internal policy.`，改写过的复述根本不包含这一行。于是"判定为 medium 泄漏"与"实际处理"脱节：路由器报告"已打码"，泄漏内容却原样发出，trace 里还记着 `verb=redact`，事后审计会误以为处理过。另外讲义说该 redactor 会"removes lines that look like the system prompt header"，代码实际只把匹配的子串替换成标签，并不删整行。
2. fail-closed 修复（判了 medium 但打码无效时升级为 block）：

```python
    def decide(self, text, verdicts):
        max_sev = self._max_severity(verdicts)
        ...
        if max_sev == "medium":
            redacted = self._apply_redactors(text, verdicts)
            if redacted == text:                     # 判定有问题，但没打掉任何东西
                return Action(verb="block", output=REFUSAL_TEXT, severity="high",
                              verdicts=serialized,
                              metadata={**metadata, "escalated": "redaction_no_op"})
            return Action(verb="redact", output=redacted, ...)
```

更细的做法是按分类器检查：对每个 medium 判决，确认它自己的 redactor 改动了文本；或者在打码后**重新跑一遍分类器**，若仍 ≥ medium 则升级为 block。

### Q11 — 参考答案

1. 三个 verdict（已实际运行核对）：
   - toxicity：`idiot` 左侧 20 个字符是 `"l 555-867-5309, you "`，里面没有 not/never/no → 1 处命中 → `low`，score `0.6`（打印为 `0.6000000000000001`）。
   - pii：email `bob@corp.io` + phone `555-867-5309`，2 处；有 email → `medium`；score = `0.5 + 0.15×2 = 0.8`。
   - instruction-leakage：与 system prompt 几乎无重合 → `none`，score `0.0`。
2. 最大 severity = medium → verb = `redact`。
3. 两个非 none 分类器的 redactor 都执行（toxicity 在前、pii 在后，顺序由 `self._classifiers` 决定）：

```text
Email [redacted-email] or call [redacted-phone], you [redacted-language].
```

注意没有 warn 提示，且电话虽然单独看只是 low，也被打码了——因为 PII 分类器的 redactor 会替换所有形状，不区分是哪一条发现把 severity 推高的。

### Q12 — 参考答案

```python
from classifiers import SEVERITY_ORDER
from main import Router, _DEMO_OUTPUTS

class ThresholdRouter(Router):
    def __init__(self, threshold: float, **kw):
        super().__init__(**kw)
        self.t = threshold

    def run(self, text):
        verdicts = [c.classify(text) for c in self._classifiers]
        for v in verdicts:
            if v.severity != "none" and v.score < self.t:
                v.severity = SEVERITY_ORDER[SEVERITY_ORDER.index(v.severity) - 1]
        return self.decide(text, verdicts)

for t in (0.0, 0.62, 0.7, 0.9):
    verbs = [ThresholdRouter(t).run(f["output"]).verb for f in _DEMO_OUTPUTS]
    print(t, verbs, sum(v == "block" for v in verbs) / len(verbs))
```

实测输出：

```text
0.0  ['log', 'warn', 'redact', 'block', 'block', 'log']   0.333
0.62 ['log', 'log', 'redact', 'block', 'block', 'log']    0.333
0.7  ['log', 'log', 'warn', 'redact', 'block', 'log']     0.167
0.9  ['log', 'log', 'warn', 'redact', 'redact', 'log']    0.0
```

观察：

- `t = 0.62` 时 low toxicity（score 0.6）降为 none，warn 变 log。
- `t = 0.7` 时**Luhn 校验通过的卡号**（severity high，但 score 只有 0.65）被降成 medium，block 变 redact——卡号这种"确定性很高"的发现，score 反而很低。
- 问题根源：PII 的 score 只由**发现数量**决定（`0.5 + 0.15·n`），与发现的类型无关；toxicity 的 score 也只看命中数。score 和 severity 是两套独立规则，score 不是"置信度"。要做阈值降级，得先让 score 真正表示置信度（例如卡号通过 Luhn 时置信度给 0.95）。
- 若阈值是用 `<=` 而不是 `<`，`0.6000000000000001` 这类浮点误差会让 t = 0.6 的结果出乎意料，阈值比较要留意浮点。

### Q13 — 参考回答要点

- **输入侧**（如第 83 节的 prompt injection 检测器）：在生成前拦截明显的攻击 prompt，省掉生成成本，能拦已知的 jailbreak / 注入模式。拦不住：新的攻击族、间接注入（恶意内容在检索文档或工具结果里）、模型自身"无辜"地产生的问题输出（复述训练数据中的辱骂、无意泄漏 PII）。
- **输出侧**（本节）：只看要发给用户的内容，与攻击路径无关；能拦 PII 泄漏、有害语言、system prompt 回显。拦不住：生成过程中已经流出去的内容（需要缓冲）、语义层面的危害（规则看不懂）、输出被编码/拆分后的变体。
- 二者是**纵深防御**：讲义说跳过输出分类等于给攻击者"one-shot bypass"。
- 加分点：第 86 节再加声明式规则（非分类器形状的约束），第 87 节把输入检测、流式中止、输出分类、规则引擎组合成完整安全关卡。
- 常见误区：认为"输入侧够严就行"；或把输出侧当作只记录日志、不采取动作的旁路。

### Q14 — 参考回答要点

- **规则分类器**（本节）：确定性、零延迟、可解释（findings 直接说明命中了什么）、单测稳定；但召回低、易被改写绕过（同义词、拼写变体、复数、否定窗口误判），维护词表成本高，无法理解上下文。
- **神经分类器**：能理解语义和上下文，召回高，可覆盖多类别分类体系；但有延迟和算力成本、存在误报且难解释、对抗样本仍可绕过、需要标注数据与阈值标定。
- **组合方式**：
  - 结构化、模式明确的问题（卡号、SSN、邮箱、API key）用正则 + 校验（Luhn），精确、便宜；
  - 语义类问题（骚扰、自残、仇恨）交给审核模型；
  - 规则先跑做快速路径，命中高危直接 block；不确定的再送模型；
  - 所有分类器统一成本节的 `verdict` 接口，路由器不关心背后是规则还是模型——讲义："for a real model with neural classifiers, the same plumbing applies"。
- 加分点：给每个分类器单独标定阈值并按类别报告 precision/recall；保留规则分类器作为模型故障时的降级方案。

### Q15 — 参考回答要点

- 讲义思路：分类器与 token streaming **并行运行**，关卡缓冲最后一块，在 flush 前套用分类判决。
- 具体做法：
  - **滞后缓冲（hold-back buffer）**：只把"已确认安全"的前缀发给用户，保留最近 N 个 chunk 或 N 个字符；规则类 PII（卡号最长 19 位 + 分隔符）需要的缓冲长度可以算出来。
  - **增量检测**：每来一个 chunk，对缓冲窗口跑轻量规则（第 87 节的 `_during_gen` 就是这样：命中终止模式就提前中止）；完整输出结束后再跑一次全量分类。
  - **可撤回的 UI**：如果最终判决为 block，前端把已显示内容替换为拒答文本；但对高危内容不能依赖撤回，必须靠缓冲。
  - **异步分级**：低成本规则同步跑，神经分类器异步跑，结果用于事后审计和告警。
- 代价：首 token 延迟增加缓冲长度；窗口太小会漏掉跨 chunk 的模式（卡号被切成两半）。
- 常见误区：先把 token 全部流给用户，生成结束后再分类——此时 block 已经没有意义。

### Q16 — 参考回答要点

- **按 PII 类型 + 上下文**设定动作，而不是只看数量：
  - 银行卡完整号码、SSN/身份证号、密码、API key：block 或强制打码（只保留后 4 位）；
  - 用户**本人**的邮箱/电话（来自已认证会话）：可以放行或部分打码；**他人**的 PII：redact；
  - IP、订单号：通常 log；
  - 本节代码的问题：单个电话号码只算 low → warn，**原样发出**（见 Q8）；"≥3 处才 medium"让数量而不是类型决定动作。
- **trace 与日志**：本节 `findings` 里直接写了原始值（如 `card '4111 1111 1111 1111'`），`classifier_report.json` 还保存了完整 `input`——生产中这会把 PII 写进日志系统。应只记录类型、位置、哈希或打码后的片段，原文按数据保留策略加密存储或不存。
- **误报处理**：订单号被当成电话（实测 `Order 1234567890 shipped` 被判为 phone）、版本号被当成 IP（`1.2.3.4`）；需要上下文规则或白名单。
- 加分点：把策略写成配置（第 86 节的声明式规则思路），让法务/合规可以审阅；按地区法规（如欧盟 GDPR）区分处理。

### Q17 — 参考回答要点

- **trigram 相似度的问题**：
  - 余弦被长输出稀释，夹在长回答里的完整 system prompt 判为 none（Q9 实测 0.211）；
  - 改写、翻译、逐条概括都能显著降低字符级重合；
  - 短输出与 system prompt 共用常见词也会误报（`Please follow internal policy.` 判 low）；
  - 打码只替换第一行的精确子串，与模糊判定不一致（Q10）。
- **更好的办法**：
  - **包含率 / 滑动窗口最大相似度**，消除长度稀释；
  - **canary token**：在 system prompt 里埋一个随机串，输出中出现即判定泄漏，几乎零误报；
  - **embedding 相似度**：对改写更鲁棒，但有成本和阈值标定问题；
  - **根本措施**：不要在 system prompt 里放真正的秘密（密钥、内部 URL），把它当作"迟早会泄漏"的内容来设计。
- 加分点：泄漏检测应结合输入侧（"repeat your instructions" 这类请求由第 83 节的检测器先拦）。

---

## 六、关联知识点

### 前置知识
- [阶段 18 · 29 内容审核系统：OpenAI、Perspective、Llama Guard](../../../18-ethics-safety-alignment/29-moderation-systems-openai-perspective-llamaguard/docs/zh.md)：生产级审核模型的类别体系与阈值，是本节规则分类器的"神经版"。
- [阶段 18 · 15 Indirect Prompt Injection：生产环境的攻击面](../../../18-ethics-safety-alignment/15-indirect-prompt-injection/docs/zh.md)：说明为什么输入侧拦不住所有攻击，输出侧必须兜底。
- [阶段 18 · 22 面向 LLMs 的差分隐私](../../../18-ethics-safety-alignment/22-differential-privacy-for-llms/docs/zh.md)：模型从训练数据中"复述" PII 的风险来源。
- [阶段 19 · 25 Verification Gates 与观察预算](../../25-verification-gates-observation-budget/docs/zh.md)：讲义列出的前置课程，"关卡"式设计的源头。
- [阶段 19 · 28 通过 OTel GenAI Spans 与 Prometheus Metrics 实现 Observability](../../28-observability-otel-traces/docs/zh.md)：`Action.metadata` 最终要写进 trace。
- [阶段 19 · 83 Prompt Injection 检测器](../../83-prompt-injection-detector/docs/zh.md)：输入侧检测器，与本节形成"输入—输出"两道关。

### 本节被哪些后续内容用到
- [阶段 19 · 86 宪法式规则引擎](../../86-constitutional-rules-engine/docs/zh.md)：处理"不是分类器形状"的约束（长度、引用、格式），同样输出 severity。
- [阶段 19 · 87 端到端安全关卡](../../87-end-to-end-safety-gate/docs/zh.md)：直接导入本节 `main.py` 的 `Router`，把它作为生成后（post-gen）阶段的分类器路由。
- [阶段 19 · 84 拒答 Evaluation](../../84-refusal-evaluation/docs/zh.md)：本节 block 产生的拒答文本，也需要纳入拒答率与过度拒答的评估。

### 延伸关键词
`output guardrail` · `defense in depth` · `PII redaction` · `Luhn checksum` · `character n-gram` · `cosine vs containment` · `canary token` · `fail-closed` · `streaming hold-back buffer` · `Llama Guard` · `Perspective API` · `severity routing`
