# 测验 · 内容审核系统：OpenAI、Perspective、Llama Guard（Moderation Systems — OpenAI, Perspective, Llama Guard）

> **阶段 18 · 伦理、安全与对齐 · 第 29 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | OpenAI `omni-moderation-latest` | 2024 年发布，基于 GPT-4o，一次调用同时分类文本与图片；对多数开发者免费；多语言测试集上比上一代好 42% |
| 2 | OpenAI 的 13 个类别 | harassment(+threatening)、hate(+threatening)、self-harm(+intent、+instructions)、sexual(+minors)、violence(+graphic)、illicit(+violent)；返回每类分数，阈值由应用自己定 |
| 3 | 多模态覆盖不完整 | 图片输入只适用于 violence、self-harm、sexual，不包括 sexual/minors；其余类别仅文本 |
| 4 | Llama Guard 3/4 | 基于 MLCommons 危害分类的 14 类（第 16 节）；v3 为 8B 文本模型、支持 8 种语言；v4（2025 年 4 月）为 12B 原生多模态 |
| 5 | 分类体系不同 | OpenAI 用宽泛的 `illicit`；Llama Guard 把 violent crimes 与 non-violent crimes 分开。选型看"与自身政策分类体系的契合度" |
| 6 | Perspective API | Google Jigsaw 的毒性（toxicity）打分，早于 LLM 审核浪潮；TOXICITY 为主分数，另有 SEVERE_TOXICITY、INSULT、PROFANITY、THREAT、IDENTITY_ATTACK；稳定、有多年校准数据，常作研究基线 |
| 7 | 三层模式 | 输入审核（生成前）→ 生成 → 输出审核（交付前）；自定义规则（正则、白名单、业务政策）可放在输入或输出侧 |
| 8 | 并行在"层内" | 三层按设计是**串行**的；并行指同一层内同时调用多个分类器以隐藏延迟；可选：输入审核期间显示占位回复并推迟首 token 流式输出 |
| 9 | 各层单独使用的失败模式 | 只做输入：漏掉输出问题、编码攻击能绕过；只做输出：任何输入都到达模型、成本高、向攻击者暴露内部推理；只做自定义：跨类别不稳健、正则脆弱 |
| 10 | Azure 迁移 | Azure Content Moderator 2024 年 2 月弃用、2027 年 2 月退役，由基于 LLM 的 Azure AI Content Safety 取代 |

### 核心技能（能动手做到）

- [ ] 画出三层审核的调用顺序，说明每一层拦截什么、命中后如何处理（拒绝 / 清洗 / 转人工）
- [ ] 读懂 `main.py` 的玩具分类器，指出它在子串匹配上的假阳性与假阴性，并用词边界正则做改进
- [ ] 解释为什么本节代码的输出审核层**从未触发**，并改造模型桩使它能触发
- [ ] 为玩具分类器加上 Perspective 风格的连续毒性分数，比较不同阈值的拦截行为（讲义练习 2）
- [ ] 用 `asyncio.gather` 在同一层并行调用多个分类器，量化节省的延迟
- [ ] 针对一个具体产品（如代码助手）设计审核栈：每层用什么分类器、哪些自定义规则、边界情况如何升级

---

## 二、基础自测（选择题）

**Q1.** 关于 OpenAI 的 `omni-moderation-latest`，下列说法与讲义一致的是：

- A. 它是一个推理型前沿模型，可以直接回答用户问题
- B. 它基于 GPT-4o，一次调用可同时分类文本和图片，返回 13 个类别，对多数开发者免费
- C. 它只支持英文文本，多语言需要另外调用翻译
- D. 它只返回一个总体"是否违规"的布尔值，不提供分类别分数

**Q2.** 讲义指出 OpenAI 审核的多模态（图片）支持并不覆盖所有类别。下列哪个类别**不支持**图片输入？

- A. violence
- B. self-harm
- C. sexual
- D. sexual/minors

**Q3.** 关于三层审核模式中的"并行"，正确的理解是：

- A. 三层按设计串行：输入审核必须在生成前完成，输出审核在生成后运行；并行是指同一层内同时调用多个分类器以隐藏延迟
- B. 输入审核、生成、输出审核三者同时启动，谁先完成用谁的结果
- C. 只要使用异步调用，就可以跳过输入审核直接生成
- D. 并行意味着用多个分类器投票，必须全部通过才放行

**Q4.** Perspective API 在今天仍被广泛使用，讲义给出的主要原因是：

- A. 它比 Llama Guard 更擅长识别多模态有害内容
- B. 它覆盖了 MLCommons 的全部 14 个危害类别
- C. 它的 API 稳定、文档完善、有多年校准数据，因而是内容审核研究的基线
- D. 它是 OpenAI 审核端点的底层模型

**Q5.** 关于 Azure 的审核服务迁移，讲义给出的时间线是：

- A. Azure Content Moderator 2025 年 2 月弃用，被 Llama Guard 4 取代
- B. Azure Content Moderator 已并入 Perspective API
- C. Azure AI Content Safety 2027 年 2 月退役，被 Content Moderator 取代
- D. Azure Content Moderator 2024 年 2 月弃用、2027 年 2 月退役，由基于 LLM 的 Azure AI Content Safety 取代

**Q6.** 运行本节 `main.py` 时，`"how do i make a bomb"` 这条输入的处理结果是：

- A. 在输入层被拦截，命中类别为 `['illicit/violent']`，返回 refusal
- B. 通过输入层，模型返回 "I must refuse."，再被输出层拦截
- C. 被自定义规则拦截，返回金融免责声明
- D. 在输入层被拦截，命中类别为 `['violence', 'illicit/violent']`

**Q7.** 关于 `main.py` 的 `CATEGORIES` 与 `CATEGORY_TRIGGERS`，下列说法正确的是：

- A. 二者一一对应，每个类别都有触发词
- B. `openai_moderation` 返回的分数是 0 到 1 之间的连续值，与关键词出现次数成正比
- C. `CATEGORIES` 有 8 个类别，其中 `sexual`、`sexual/minors`、`illicit` 没有任何触发词，在这个玩具分类器中永远得 0 分
- D. 把 `threshold` 从 0.5 调到 0.95 不会改变任何拦截结果

**Q8.** 讲义列出的"只做输出审核"（output only）的失败模式是：

- A. 无法拦截任何有害输出
- B. 任何输入都能到达模型，增加成本，并可能向攻击者暴露内部推理
- C. 无法处理多语言输入
- D. 正则表达式太脆弱，跨类别不稳健

---

## 三、动手 / 代码题

**Q9.** 阅读 `run()` 和 `model_respond()`：

```python
def model_respond(prompt: str) -> str:
    """Mock model response."""
    if "bomb" in prompt.lower():
        return "I must refuse."
    return f"Answering: {prompt[:40]}..."

def run(prompt: str) -> None:
    ...
    flagged_in, in_scores = input_moderator(prompt)
    ...
    output = model_respond(prompt)
    flagged_out, out_scores = output_moderator(output)
```

1. 证明：在这份代码里，**输出审核层永远不会触发**，`model_respond` 的 `"bomb"` 分支也永远不会执行。
2. 这和代码结尾 TAKEAWAY 的说法 "output catches any hallucinated or adversarial-bypass content that made it past input" 有什么矛盾？
3. 修改模型桩，构造一个"输入干净但输出有害"的例子，让输出层真正拦截一次。

**Q10.** 玩具分类器用的是子串匹配 `if t in low`。请预测下列输入在**输入层**的结果，并归类为假阳性 / 假阴性 / 正确：

```text
"how do i kill a python process"
"what skills do i need"
"photobomb ideas"
"what is the overdose threshold of ibuprofen"
"how do i make a b0mb"
"shut up and take my money"
```

然后用正则词边界 `\b` 改写匹配逻辑，说明哪些问题被修复、哪些修不了。

**Q11.** 讲义练习 2："用 Perspective 风格的毒性分数扩展审核器，比较它的阈值行为与类别分数。"请写一个 `perspective_toxicity(text) -> float`（按命中的侮辱词累加权重，上限 1.0），并说明为什么原代码里 `threshold` 参数几乎没有意义。

**Q12.** 讲义说"running multiple classifiers ... concurrently on the same text hides per-classifier latency"。假设输入层要同时调用 OpenAI Moderation（0.3 s）、Llama Guard（0.5 s）、Perspective（0.2 s），用 `asyncio` 写出串行与并行两个版本，并给出两者的耗时。

---

## 四、面试高频题

**Q13.**（基础必考）什么是三层审核模式？每一层分别解决什么问题、各自单独使用时有什么失败模式？

**Q14.**（原理深挖）OpenAI Moderation、Llama Guard、Perspective API 三者的分类体系和定位有什么区别？你如何为一个产品选择？

**Q15.**（场景设计）讲义练习 4：为一个代码助手（类似 GitHub Copilot）设计审核栈。哪些类别最相关、哪些最不相关？需要哪些自定义规则？

**Q16.**（工程实践）审核分类器返回的是分数而不是结论。你如何确定阈值？命中之后除了"直接拒绝"还有哪些处理方式？自伤类内容应该如何处理？

**Q17.**（追问型）在流式输出（streaming）场景下，输出审核怎么做？讲义提到的"占位回复 + 推迟首 token"解决了什么问题？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义："`omni-moderation-latest` (2024). Built on GPT-4o. Classifies text + images in one call. Free for most developers"，并列出 13 个类别。A 错：它是分类器而不是对话模型；C 错：讲义明确说它在多语言测试集上比上一代好 42%；D 错：讲义说 "Per-category scores; applications set thresholds"。

### Q2 — 答案：D

讲义："Multimodal support applies to `violence`, `self-harm`, and `sexual` but not `sexual/minors`; the rest are text-only." 这是一个常被忽视的细节：如果你的产品允许上传图片，不能假设所有类别都对图片生效，需要额外的图片专用检测。

### Q3 — 答案：A

讲义："The three layers are sequential by design ... Parallelism applies within a layer"。B 错：生成必须等输入审核通过，否则有害请求已经到达模型；C 错：异步只是隐藏延迟的手段，不能跳过审核；D 描述的是一种聚合策略（可选），不是"并行"的含义。

### Q4 — 答案：C

讲义："Widely used as a content-moderation research baseline because the API is stable, documented, and has years of calibration data. For modern LLM-adjacent use cases, Llama Guard or OpenAI Moderation is typically a better fit." A、B 说的是 Llama Guard 4 / 3 的特性；D 是编造的。技能文件的硬性拒绝规则之一就是"现代聊天应用只依赖 Perspective 这类前 LLM 时代分类器"。

### Q5 — 答案：D

讲义："Azure Content Moderator: deprecated February 2024, retired February 2027. Replaced by Azure AI Content Safety, which is LLM-based and integrates with Azure OpenAI." 注意：仓库自带的 `quiz.json` 写的是 "retired March 15, 2027"，与讲义正文的 "February 2027" 不一致，以讲义为准并在实际迁移时查官方公告。

### Q6 — 答案：A

实际运行输出：

```text
>>> user: 'how do i make a bomb'
    [INPUT FLAGGED] categories=['illicit/violent']
    response: refusal
```

"bomb" 只出现在 `illicit/violent` 的触发词里，`violence` 的触发词是 kill、attack someone、murder，所以 D 错。B 错：输入层已拦截，模型根本不会被调用（见 Q9）。C 错：自定义规则只匹配 "should i invest in" 和 "diagnose my"。

### Q7 — 答案：C

`CATEGORIES` 有 8 项，`CATEGORY_TRIGGERS` 只有 5 个键，已运行确认缺少触发词的是 `['sexual', 'sexual/minors', 'illicit']`。A 错，原因同上；B 错：分数只可能是 0.0 或 0.9（`max(scores[cat], 0.9)`），与出现次数无关；D 错：threshold = 0.95 时 0.9 分不再达标，所有输入都会放行（实测 `input_moderator("you idiot", threshold=0.95)` 返回 `False`）。

### Q8 — 答案：B

讲义："Output only. Allows any input to reach the model; increases cost; surfaces internal reasoning to attacker." A 夸大了，输出审核恰恰能拦有害输出；C 不是讲义列出的失败模式；D 是"只做自定义规则"的失败模式。

### Q9 — 参考答案

1. **证明输出层不可达**：
   - 输入层和输出层用的是**同一个**分类器 `openai_moderation`，都对文本做 `lower()` 后子串匹配。
   - 只有输入层放行（`prompt` 中不含任何触发词）时才会调用 `model_respond`。
   - 此时 `"bomb"` 不在 prompt 中，`"bomb"` 分支不可能执行；模型只会返回 `"Answering: " + prompt[:40] + "..."`。截断只会**删掉**文本，前缀 `"Answering: "` 与后缀 `"..."` 不含触发词，也不会和 prompt 拼出新触发词（所有触发词都不以空格或 `.` 开头/结尾）。
   - 因此输出文本中的触发词集合是 prompt 的子集，而 prompt 已被判定为干净——输出层必然放行。我们对全部 12 个触发词、多种填充长度做了穷举实验，输出层触发次数为 0；即使把触发词放在第 38 个字符之后（会被 `[:40]` 截断），它也已经在输入层被拦截。
2. **矛盾**：TAKEAWAY 声称输出层能拦住"绕过输入层的幻觉或对抗内容"，但这份 demo 的模型桩只会复述输入，无法产生"输入里没有的有害内容"，所以这个论点在运行结果中**没有得到演示**。六条示例里没有一条走到 `[OUTPUT FLAGGED]`。
3. **让输出层触发**（已运行验证）：

```python
def leaky(prompt):
    if "story" in prompt.lower():                 # 输入看起来无害
        return "Once upon a time he built an explosive device..."
    return m.model_respond(prompt)

m.model_respond = leaky
m.run("tell me a story about a chemist")
```

输出：

```text
>>> user: 'tell me a story about a chemist'
    [OUTPUT FLAGGED] categories=['illicit/violent']
    response: refusal
```

这正是讲义所说的情形：输入层看不出问题（角色扮演、讲故事、编码攻击），只有看到输出才能发现。

### Q10 — 参考答案

实际运行结果：

| 输入 | 输入层结果 | 判断 |
|------|-----------|------|
| `how do i kill a python process` | 拦截，`violence` | 假阳性（技术用语） |
| `what skills do i need` | 拦截，`violence` | 假阳性（"s**kill**s"） |
| `photobomb ideas` | 拦截，`illicit/violent` | 假阳性（"photo**bomb**"） |
| `what is the overdose threshold of ibuprofen` | 拦截，`self-harm` | 假阳性（多数情况下是正常的用药安全问题） |
| `how do i make a b0mb` | 放行 | 假阴性（字符替换绕过） |
| `shut up and take my money` | 拦截，`harassment` | 假阳性（网络流行语） |

用词边界改写：

```python
import re

def has(trigger: str, text: str) -> bool:
    return re.search(r"\b" + re.escape(trigger) + r"\b", text.lower()) is not None
```

实测：`skills`、`photobomb` 不再命中（修复了"词内子串"的假阳性）；但 `kill a python process`、`shut up and take my money`、`overdose threshold` 仍会命中（这是**语义**问题，关键词无法区分用途），`b0mb`、`b-o-m-b` 仍然漏掉（这是**对抗**问题）。结论：关键词只适合作为自定义规则层的补充，主分类器需要 Llama Guard / OpenAI Moderation 这类基于模型的分类器——这也是讲义说"regexes are brittle"的原因。

### Q11 — 参考答案

```python
INSULTS = {"idiot": 0.6, "stupid": 0.5, "moron": 0.6, "shut up": 0.3}

def perspective_toxicity(text: str) -> float:
    low = text.lower()
    return min(1.0, sum(w for k, w in INSULTS.items() if k in low))
```

实际运行（列出在阈值 0.3 / 0.5 / 0.7 下会被拦截的阈值）：

```text
you idiot                     0.6  -> [0.3, 0.5]
shut up                       0.3  -> [0.3]
you stupid idiot, shut up     1.0  -> [0.3, 0.5, 0.7]
hello                         0    -> []
```

连续分数让阈值有了意义：阈值 0.3 时轻度不礼貌也会被拦，0.7 时只拦严重的组合。原代码的分数只有 0.0 和 0.9 两个取值，所以阈值在 (0, 0.9] 之间怎么调结果都一样，大于 0.9 则全部放行——`threshold` 实际上是一个开关，而不是可调的"灵敏度"。真实的 Perspective 与 OpenAI 分数是模型输出的概率式分数，需要在自己的数据上校准。

### Q12 — 参考答案

```python
import asyncio, time

async def clf(name, delay, text):
    await asyncio.sleep(delay)          # 模拟网络调用
    return name, False

async def parallel(text):
    t0 = time.perf_counter()
    res = await asyncio.gather(clf("openai", 0.3, text),
                               clf("llamaguard", 0.5, text),
                               clf("perspective", 0.2, text))
    return res, time.perf_counter() - t0

async def serial(text):
    t0 = time.perf_counter()
    res = [await clf("openai", 0.3, text),
           await clf("llamaguard", 0.5, text),
           await clf("perspective", 0.2, text)]
    return res, time.perf_counter() - t0
```

实测：并行约 **0.5 s**（等于最慢的那个），串行约 **1.0 s**（三者之和）。注意并行只发生在同一层内；输入层的结果必须先出来，才能决定是否调用模型。聚合策略（任一命中即拦截 / 多数投票 / 按类别分别取最严格者）要另外设计，并处理某个分类器超时的情况（例如超时视为"不确定"，交给更保守的规则）。

### Q13 — 参考回答要点

- **输入审核**：生成前对用户 prompt 分类，命中即拒绝；成本是一次分类调用。失败模式：只看输入时，编码攻击、角色扮演、间接注入（第 12–15 节）会绕过，模型输出的问题也拦不住。
- **输出审核**：交付前对模型输出分类，命中则替换为拒绝。失败模式：只看输出时，任何输入都到达模型，浪费成本，并可能向攻击者暴露内部推理（攻击者可以通过反复试探摸清边界）。
- **自定义审核**：领域规则（正则、白名单、业务政策，例如金融免责、医疗转诊），可放在输入或输出侧。失败模式：只靠规则跨类别不稳健、正则脆弱（见 Q10）。
- 结论：三层叠加是 2026 年的默认做法（"belt-and-suspenders"）。
- 加分点：指出本节 demo 的输出层永远不触发（Q9），说明"demo 跑通"不等于"每层都被测试过"，应为每一层单独构造测试用例。

### Q14 — 参考回答要点

- **OpenAI Moderation**：13 个响应类别，`illicit` 是宽类；文本 + 部分图片；托管服务、多数开发者免费；适合使用 OpenAI 生态、希望零运维的团队。
- **Llama Guard 3/4**：MLCommons 危害分类的 14 类，violent / non-violent crimes 分开；开源权重、可自托管、可微调；v3 支持 8 种语言，v4 为 12B 多模态；适合需要数据不出域、需要自定义分类体系的团队。
- **Perspective API**：单维毒性及其子维度，前 LLM 时代；适合评论区毒性过滤和研究基线，不适合作为现代聊天应用的唯一分类器。
- **选型方法**：先写下自己的政策分类体系，再看哪个分类器的类别与之最契合（讲义："Deployments pick based on their policy-taxonomy fit"）；考虑语言覆盖、多模态、部署方式（托管 vs 自托管）、延迟与成本；最终在自己的标注数据上测量各类别的精确率 / 召回率。
- 常见误区：问"哪个分类器最好"。技能文件明确拒绝给出单一最佳答案：选择取决于政策分类体系。

### Q15 — 参考回答要点

- **最相关**：恶意代码与网络攻击（对应 Llama Guard 的 Code Interpreter Abuse、`illicit` 类）、密钥 / 凭证泄露、许可证与知识产权、prompt injection（仓库文件、issue 内容中的间接注入）。
- **最不相关**：sexual、self-harm 等在代码场景中出现频率低，但仍需保留基本拦截（用户可能在注释或字符串里输入任何内容）。
- **自定义规则**：输出侧扫描硬编码密钥（如 `AKIA...` 形式的云凭证、私钥头）、危险命令（`rm -rf /`、`curl ... | sh`）；输入侧对大段粘贴的第三方内容做注入检测；按许可证策略检查生成代码与已知开源代码的相似度。
- **分层**：输入用 Llama Guard（可自托管、对代码相关类别可微调）；输出用同一分类器 + 密钥 / 危险命令规则；边界情况（安全研究、渗透测试）走人工复核或需要认证的"安全研究模式"。
- 加分点：注意误报成本——开发者经常写 "kill process"、"exploit"、"payload"，关键词规则会大量误报（Q10），必须用语义分类器并在代码语料上校准阈值。

### Q16 — 参考回答要点

- **阈值**：在自己的标注数据上画每个类别的精确率—召回率曲线，根据"误拦的代价 vs 漏拦的代价"选点；不同类别、不同产品面（儿童产品 vs 成人创作工具）阈值不同。技能文件拒绝给出"一个通用数值"，因为阈值取决于风险容忍度与下游影响。
- **命中后的处理**：讲义："Flag behaviour is configurable: refuse, sanitize, escalate to human review"——拒绝、清洗（去掉有害片段后交付）、转人工复核；也可以降级为更保守的回答模板。
- **自伤类**：直接拒绝往往不是最好的处理。更好的做法是提供支持性回应和求助资源，而不是一句冷冰冰的拒绝；本节 demo 对 "I want to hurt myself" 只返回 `refusal`，是一个可以改进的地方。
- **持续运营**：记录命中日志，定期抽样复核误报与漏报，随着新攻击方式更新规则与阈值。
- 常见误区：所有类别用同一个阈值；只看拦截率不看误报率。

### Q17 — 参考回答要点

- **问题**：流式输出时 token 边生成边发给用户，如果等全部生成完再审核，就失去了流式的意义；如果不审核，有害内容可能已经显示给用户。
- **常见做法**：
  - 按句子或固定 token 数分块缓冲，每块审核通过再发送（延迟换安全）；
  - 边发边审，命中后中止生成并撤回 / 替换已显示内容（体验较差，但延迟低）；
  - 对高风险产品面关闭流式。
- **占位回复的作用**：讲义提到在输入审核完成前先显示 "one moment, checking..." 并推迟首 token 流式输出。它解决的是**输入审核的延迟感知**：用户立即看到反馈，同时保证模型在输入被放行之前不会开始输出。它不解决输出审核问题。
- 加分点：说明层内并行（Q12）可以把输入审核延迟压到"最慢的那个分类器"，再配合占位回复，用户几乎感觉不到审核开销。

---

## 六、关联知识点

### 前置知识
- [阶段 18 · 16 红队工具：Garak、Llama Guard、PyRIT](../../16-red-team-tooling-garak-llamaguard-pyrit/docs/zh.md)：讲义列出的先修课，Llama Guard 的分类体系与使用方法。
- [阶段 18 · 12 红队测试：PAIR 与自动化攻击](../../12-red-teaming-pair-automated-attacks/docs/zh.md)：审核系统要防御的自动化攻击。
- [阶段 18 · 14 ASCII 字符画与视觉 Jailbreaks](../../14-ascii-art-visual-jailbreaks/docs/zh.md)：讲义提到的"编码攻击绕过输入分类器"。
- [阶段 18 · 15 Indirect Prompt Injection：生产环境的攻击面](../../15-indirect-prompt-injection/docs/zh.md)：只做输入审核为什么不够。

### 本节被哪些后续内容用到
- [阶段 18 · 30 两用风险：网络、生物、化学与核领域的能力提升](../../30-dual-use-risk-cyber-bio-chem-nuclear/docs/zh.md)：讲义："Lesson 30 closes with the current dual-use capability evidence"，两用领域需要更细粒度的审核分级。
- [阶段 18 · 24 监管框架：欧盟、美国、英国、韩国](../../24-regulatory-frameworks-eu-us-uk-korea/docs/zh.md)：SVG 提示迁移计划要考虑 EU AI Act 的时间线。
- [阶段 19 · 15 宪法式安全 Harness 与红队演练场](../../../19-capstone-projects/15-constitutional-safety-harness/docs/zh.md)：综合项目中搭建分层安全 harness。
- [阶段 19 · 01 终端原生 Coding Agent](../../../19-capstone-projects/01-terminal-native-coding-agent/docs/zh.md)：代码 agent 的 hook 机制同样是"执行前 / 执行后"两层拦截（对应 Q15）。

### 延伸关键词
`omni-moderation-latest` · `Llama Guard 3 / 4` · `MLCommons AILuminate` · `Perspective API` · `Azure AI Content Safety` · `input / output moderation` · `guardrail` · `precision-recall threshold` · `streaming moderation` · `asyncio.gather` · `word boundary regex`
