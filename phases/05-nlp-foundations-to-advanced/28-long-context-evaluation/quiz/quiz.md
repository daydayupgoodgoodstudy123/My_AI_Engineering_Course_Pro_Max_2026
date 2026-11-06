# 测验 · 长上下文 Evaluation — NIAH、RULER、LongBench、MRCR（Long-Context Evaluation — NIAH, RULER, LongBench, MRCR）

> **阶段 05 · NLP 基础到进阶 · 第 28 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 标称 ≠ 可用 | 规格表上的上下文窗口只是上限；真正可用的长度取决于任务，讲义的经验值是推理有效长度通常只有标称值的 25–50% |
| 2 | 能力随任务分层退化 | 单针检索在前沿模型上接近满分；多跳 / 聚合在约 128k 之后大多急剧下降；对分散事实的推理最先失败 |
| 3 | NIAH（2023） | 在长填充文本的可控深度处埋一个事实（"the magic word is pineapple"），扫描 深度 × 长度 网格得到热力图；前沿模型已饱和，是必要但不充分的基线 |
| 4 | RULER（NVIDIA，2024） | 4 大类 13 种任务：检索（单 key / 多 key / 多 value）、多跳追踪（变量追踪）、聚合（高频词统计）、QA；长度可配（4k 到 128k+）；2024 年 17 个号称 32k+ 的模型中只有一半在 32k 保持质量 |
| 5 | LongBench v2（2024） | 503 道多选题，上下文 8k–2M 词，6 类任务（单文档 QA、多文档 QA、长 ICL、长对话、代码仓库、长结构化数据）；衡量真实场景 |
| 6 | MRCR 与其他基准 | MRCR：多轮共指消解、多针变体，测"同时能记住多少事实"；NoLiMa：针与问题无字面重叠；HELMET：多文档中选择性注意；BABILong：在干扰文本中嵌入 bAbI 推理链 |
| 7 | Lost in the middle | 模型对长输入中间部分的关注不足；深度必须扫 0、0.25、0.5、0.75、1.0，只测 0.5 不够 |
| 8 | 该报告什么 | 标称窗口、有效检索长度（如 NIAH 90% 通过）、有效推理长度（如多跳 70% 通过）、按任务类型的退化曲线；外加首 token 延迟（TTFT）和单次成本 |
| 9 | 常见陷阱 | 只做 NIAH；只测一个深度；针与填充文本有词汇重叠导致检索过于简单；忽略预填充延迟（1M token 约 30–120 秒）；轻信厂商自报分数 |

### 核心技能（能动手做到）

- [ ] 能写出可控深度、可控长度的 NIAH 构造器，扫 5 个深度 × 多个长度，输出热力图表格
- [ ] 能从网格结果算出"有效检索长度"（每个长度跨深度的通过率 ≥ 阈值的最大长度）
- [ ] 能构造多针（multi-needle）变体，并对比同长度下单针与多针的通过率
- [ ] 能构造 RULER 风格的变量追踪任务（X1 → X2 → X3）嵌在长填充文本中
- [ ] 能在 haystack 中加入干扰针（distractor）和非字面针（NoLiMa 风格），解释它们为什么让测试更真实
- [ ] 能设计模型升级时的长上下文回归 harness：固定数据、固定网格、报告增量和 TTFT

---

## 二、基础自测（选择题）

**Q1.** 某模型在 1M token 长度、所有深度上的 NIAH 通过率都是 100%。下列结论中**有依据**的是：

- A. 该模型在 1M token 上能胜任任何长文档任务
- B. 该模型在 1M token 内能找回一个与问题字面匹配的单一事实；多跳和聚合能力仍然未知，需要 RULER 或自定义多跳测试
- C. 该模型的有效推理长度就是 1M
- D. 该模型在任何任务上都不存在 lost in the middle 问题

**Q2.** 某团队的长上下文测试只把针放在 depth = 0.5。这种做法的主要问题是：

- A. depth = 0.5 是最容易的位置，结果会偏乐观
- B. 准确率会随针的位置变化（lost in the middle），只测一个深度得不到完整的位置曲线；应该扫 0、0.25、0.5、0.75、1.0
- C. depth = 0.5 会导致 tokenizer 截断
- D. 没有问题，深度对结果没有影响

**Q3.** 下列哪一项**不是** RULER 的任务类别？

- A. 检索（单 key、多 key、多 value 的 NIAH 变体）
- B. 多跳追踪（变量追踪）
- C. 聚合（统计高频词）
- D. 长文档机器翻译

**Q4.** 在长文本中埋入针："Mia's apartment window looks straight out at the Eiffel Tower."，然后提问："Which character lives in Paris?"。这种设计主要测试的是：

- A. 模型的分词速度
- B. 针与问题没有字面重叠，模型必须做一步语义推理（埃菲尔铁塔 → 巴黎）才能定位，这是 NoLiMa 的思路
- C. 模型能否记住多轮对话
- D. 模型能否统计词频

**Q5.** 某模型标称上下文 1M。你的测试结果：NIAH 通过率 ≥ 90% 一直保持到 512k；多跳变量追踪通过率 ≥ 70% 只保持到 128k。按讲义建议，规格表应该写：

- A. 上下文 1M
- B. 有效检索长度 512k，有效推理长度 128k
- C. 有效长度 (512k + 128k) / 2 = 320k
- D. 有效长度 128k，不必区分任务类型

**Q6.** 一个产品要把 800k token 的代码仓库一次性塞进 prompt 再提问。除了准确率，讲义强调还必须测量：

- A. 模型参数量
- B. 首 token 延迟（TTFT）和单次请求成本，因为 1M 级 prompt 的预填充可能需要 30–120 秒
- C. 模型的 embedding 维度
- D. tokenizer 的词表大小

**Q7.** 关于 LongBench v2，下列说法正确的是：

- A. 它是纯合成的 NIAH 变体，只测检索
- B. 它由 503 道多选题组成，上下文从 8k 到 2M 词，覆盖单文档 QA、多文档 QA、长 ICL、长对话、代码仓库、长结构化数据 6 类任务，用来衡量真实场景下的长上下文能力
- C. 它只有 128k 以内的上下文
- D. 它只报告一个总分，不分任务类别

---

## 三、动手 / 代码题

**Q8.** 本节 `code/main.py` 中的 mock 模型如下：

```python
def mock_retrieval_model(context, question, effective_capacity):
    needle_pattern = re.compile(r"(?:the magic word is|the secret code is|the pass phrase is|x1\s*=|x2\s*=|x3\s*=) [A-Z0-9a-z_]+", re.IGNORECASE)
    matches = list(needle_pattern.finditer(context))
    if not matches:
        return "no answer"
    total_len = len(context.split())
    for m in matches:
        before = len(context[:m.start()].split())
        if before <= effective_capacity:
            return m.group(0).split()[-1].strip(",.")
    return "no answer"
```

`run_niah_grid` 用 `capacity = 20000`、长度 `[500, 2000, 8000, 20000, 40000]`、深度 `[0.1, 0.3, 0.5, 0.7, 0.9]`，针由 `insert_needle` 插入在 `int(len(words) * depth_ratio)` 的位置。

1. 长度为 40000 的那一列，5 个深度分别输出 1 还是 0？
2. 为什么 `depth=0.5, len=40000` 恰好能通过？如果把 `capacity` 改成 19999 会怎样？
3. 无论怎么调 `capacity`，这个 mock 的热力图都**不可能**出现 lost in the middle 的形状。为什么？

**Q9.** 有同学在 haystack 里额外放了一个干扰针：

```python
filler = make_filler(2000, seed=7)
words = filler.split()
words = words[:1200] + ["the magic word is pineapple"] + words[1200:]
words = words[:400] + ["the magic word is banana"] + words[400:]
hay = " ".join(words)
print(mock_retrieval_model(hay, "What is the magic word?", 20000))
print(score_single_needle(hay, "pineapple", 20000))
```

1. 两行分别输出什么？
2. 这暴露了 mock 模型的哪两个简化？与 RULER 的多 key 检索任务、讲义的"词汇重叠"陷阱有什么关系？

**Q10.** 讲义要求报告"有效检索长度"（如 90% 通过）。请实现：

1. `niah_grid(lengths, depths, capacity=20000, seed=0)`：复用本节的 `make_filler / insert_needle / score_single_needle`，返回字典 `{(depth, length): 0 或 1}`；
2. `effective_length(grid, lengths, depths, threshold=0.9)`：从短到长遍历长度，计算每个长度在所有深度上的通过率；返回**连续**满足"通过率 ≥ threshold"的最大长度（一旦某个长度不达标就停止）。

分别给出 `capacity=20000` 和 `capacity=5000` 时的有效检索长度，并写出 `capacity=5000` 时每个长度的通过率。

---

## 四、面试高频题

**Q11.**（基础必考）什么是 Needle-in-a-Haystack 测试？怎么构造？为什么讲义说它"必要但不充分"？

**Q12.**（原理深挖）为什么模型的有效上下文远小于标称窗口？lost in the middle 是什么现象？为什么多跳和聚合任务比单针检索退化得更早？

**Q13.**（工程实践）你要为"200 页合同审阅"产品选型一个长上下文模型。请设计评测方案：测什么、怎么构造数据、报告哪些数字、通过标准是什么。

**Q14.**（场景设计）公司每季度都会升级底座模型。请设计一套长上下文回归 harness，保证每次升级都能发现长上下文能力的退化。

**Q15.**（追问型）"既然模型都支持 1M 上下文了，还要 RAG 和 chunking 干什么？"——你怎么回答？

---

## 五、参考答案与解析

### Q1 — 答案：B

NIAH 测的是"在长文本中找回一个与问题有字面联系的单一事实"。讲义反复强调：前沿模型已经让 NIAH 饱和，它是**必要但不充分**的基线；"Passing NIAH at 1M tokens says nothing about multi-hop"。A、C 把检索能力外推成了推理能力；D 也不成立，lost in the middle 在更难的任务（多针、多跳）上依然可能出现。

### Q2 — 答案：B

Lost in the middle（Liu et al.）指模型对长输入中间部分关注不足，准确率随位置变化，常见形状是两端高、中间低。只测一个深度既可能高估也可能低估，更重要的是看不到位置曲线。讲义的做法是每个长度都扫 0、0.25、0.5、0.75、1.0 五个深度。A 说反了：中间位置往往更难，而不是更容易。

### Q3 — 答案：D

RULER 的 13 种任务分属 4 类：检索（单 key / 多 key / 多 value 等 NIAH 变体）、多跳追踪（变量追踪）、聚合（高频词统计）、QA。机器翻译不在其中。RULER 的价值在于揭示"NIAH 饱和但多跳失败"的模型。

### Q4 — 答案：B

针里没有出现 "Paris"、"lives" 这些问题中的词，模型不能靠关键词匹配找到它，必须知道"埃菲尔铁塔在巴黎"才能建立联系。这就是 NoLiMa（non-lexical needle）的设计：去掉字面重叠，逼模型做一步语义推理。讲义陷阱部分也提醒：针和填充文本、问题有词汇重叠时，检索会变得过于简单。

### Q5 — 答案：B

讲义：规格表上应该写**两个数字**：有效检索长度（如 NIAH 90% 通过）和有效推理长度（如多跳 70% 通过）。两者对应不同的工作负载，不能平均（C），也不能只留一个（D）。本例中推理有效长度只有标称值的 12.5%，比讲义"通常 25–50%"的经验值还低，这正说明必须在自己的任务上实测。

### Q6 — 答案：B

讲义陷阱 "Ignoring latency"：1M token 的 prompt 预填充需要 30–120 秒，准确率再高，用户也等不起。skill 文件要求的指标包括 retrieval pass rate、reasoning pass rate、time-to-first-token、cost-per-query。

### Q7 — 答案：B

LongBench v2：503 道多选题，8k–2M 词，6 类真实任务，讲义称它是"衡量真实长上下文行为的生产基准"。讲义还提醒：要报告**分类别**准确率，因为总分会掩盖任务间的巨大差异，所以 D 错。A 描述的是 NIAH / RULER 这类合成基准。

### Q8 — 参考答案

**1.** 实际运行结果，长度 40000 那一列：

```text
depth=0.1 → 1   (针前约 4000 词)
depth=0.3 → 1   (约 12000 词)
depth=0.5 → 1   (正好 20000 词)
depth=0.7 → 0   (约 28000 词 > 20000)
depth=0.9 → 0   (约 36000 词 > 20000)
```

所以输出里 depth=0.7 和 0.9 两行的结尾是 `4/5`，其余行是 `PASS`。

**2.** `insert_needle` 把针插在 `int(40000 * 0.5) = 20000` 的位置，针前面正好 20000 个词；判断条件是 `before <= effective_capacity`，**小于等于**，所以 20000 ≤ 20000 通过。改成 19999 后，这一格变成 0，depth=0.5 那一行也变成 `4/5`（已实际验证）。这类"恰好落在边界上"的格子对 `<=` 和 `<` 非常敏感，写评测代码时要特别注意边界条件。

**3.** mock 的判定只依赖**针之前的绝对词数**：只要 `before <= capacity` 就一定找到，否则一定找不到。所以对任意长度，通过与否随深度**单调**变化（浅的通过、深的失败），热力图只能是"左上全 1、右下出现 0"的阶梯形状，相当于"把超过容量的部分截断"。lost in the middle 是**两端好、中间差**的非单调曲线，而且是概率性的逐渐退化。这也是脚本 notes 里说的 "mock model has hard effective-capacity cutoff; real LLMs degrade gradually"。要模拟它，可以让命中概率依赖相对深度（例如中间段命中率更低）。

### Q9 — 参考答案

**1.** 输出（已实际运行）：

```text
banana
0
```

**2.** 两个简化：

- **mock 完全忽略了 `question` 参数**，只按正则找第一个"the magic word is X"。干扰针 banana 位于第 400 个词附近，比真针（约第 1200 个词）更靠前，又在容量之内，于是被返回，得分为 0。真实模型需要根据问题判断哪个针才是答案。RULER 的多 key 检索任务正是放入多个相似的 key-value 对，只问其中一个，测的就是这种"抗干扰的精确检索"。
- **mock 是纯字面匹配**：只要句式是 "the magic word is"，它就能找到；换成 NoLiMa 风格的非字面针，它会完全失效。讲义的陷阱 "Lexical overlap with filler" 说的就是：如果测试只需要关键词匹配，它测到的是"grep 能力"，而不是长上下文理解。

改进思路：让针带 key（如 "the magic word for vault A is X"），mock 先从问题中解析出 key 再匹配；评测集里同时放入多个 key 和干扰项。

### Q10 — 参考答案

```python
from main import make_filler, insert_needle, score_single_needle


def niah_grid(lengths, depths, capacity=20000, seed=0):
    needle, expected = "the magic word is pineapple", "pineapple"
    grid = {}
    for d in depths:
        for n in lengths:
            hay = insert_needle(make_filler(n, seed=seed + n), needle, d)
            grid[(d, n)] = score_single_needle(hay, expected, capacity)
    return grid


def effective_length(grid, lengths, depths, threshold=0.9):
    eff = 0
    for n in sorted(lengths):
        rate = sum(grid[(d, n)] for d in depths) / len(depths)
        if rate < threshold:
            break          # 要求"连续"达标：一旦某个长度不达标就停止
        eff = n
    return eff


lengths = [500, 2000, 8000, 20000, 40000]
depths = [0.1, 0.3, 0.5, 0.7, 0.9]
print(effective_length(niah_grid(lengths, depths), lengths, depths))                 # 20000
print(effective_length(niah_grid(lengths, depths, capacity=5000), lengths, depths))  # 2000
```

实际运行结果：

| capacity | 500 | 2000 | 8000 | 20000 | 40000 | 有效检索长度（90%） |
|----------|-----|------|------|-------|-------|-------------------|
| 20000 | 1.0 | 1.0 | 1.0 | 1.0 | 0.6 | **20000** |
| 5000 | 1.0 | 1.0 | 0.6 | 0.2 | 0.2 | **2000** |

要点：

- capacity = 5000 时，长度 8000 只有 depth 0.1、0.3、0.5（针前 800、2400、4000 词）能找到，通过率 3/5 = 0.6 < 0.9，所以有效长度停在 2000。注意它并不等于 capacity 本身：有效长度受**测试网格的粒度**限制，网格越密，估计越准。
- 用"连续达标"而不是"任意一个长度达标"，是为了避免短长度失败、长长度偶然通过这种噪声让结论虚高。
- 阈值是参数：讲义 skill 文件建议检索用 90%，推理用 70%。同样的函数换成多跳任务的网格，就能算出有效推理长度。

### Q11 — 参考回答要点

- **定义**：在一段很长的无关填充文本中，在受控深度埋入一个事实（针），再让模型回答与该事实有关的问题，判断是否找回。
- **构造**：
  1. 准备填充文本（讲义 `build_haystack`：重复填充文本直到达到目标长度）；
  2. 按 `depth_ratio` 计算插入位置；
  3. 扫描 深度 {0, 0.25, 0.5, 0.75, 1.0} × 长度（如 1k、4k、16k、64k……直到目标长度）；
  4. 判分用"答案中是否包含期望值"；
  5. 画热力图。
- **为什么必要但不充分**：
  - 必要：它是最便宜的"模型能不能看到这段内容"的检查，连 NIAH 都过不了，其他都不用谈；
  - 不充分：只测单一事实、字面匹配的检索，前沿模型已饱和；多跳、聚合、分散推理会更早崩溃（RULER 发现很多模型 NIAH 饱和却在多跳上失败）。
- **加分点**：提到多针、干扰针、非字面针（NoLiMa）等加难手段；指出填充文本的选择会影响结果（与针主题差异太大会让针过于显眼）。

### Q12 — 参考回答要点

- **现象**：讲义把能力分成三层：单针检索在前沿模型上接近标称上限；多跳 / 聚合在约 128k 后急剧下降；分散事实推理最先失败。推理有效长度通常只有标称值的 25–50%。
- **Lost in the middle**：信息在输入开头或结尾时准确率高，在中间时明显下降，常见形状是 U 形，说明模型对不同位置的利用并不均匀。
- **为什么多跳 / 聚合更早退化**（常见解释，讲义未展开机制，面试时可以这样组织）：
  - 单针检索只需要一次"定位"；多跳需要多次定位并串联，每一步的错误会**相乘**：每跳 90% 的成功率，三跳只剩约 73%；
  - 聚合需要关注**大量**位置并统计，而注意力权重分散在越来越多的 token 上；
  - 训练数据中真正需要长距离依赖的超长样本较少，位置编码在长距离上的外推也有限（可联系 RoPE 外推、位置插值相关内容）。
- **加分点**：MRCR 的多针变体正是测"同时能处理多少个事实"；工程上可以把关键信息放在 prompt 的开头或结尾，缓解中间位置的问题。

### Q13 — 参考回答要点

1. **测试集**：
   - **领域 NIAH**：用真实合同做 haystack，针是领域化的条款事实（如"终止通知期为 90 天"），放在 0、0.25、0.5、0.75、1.0 深度，长度覆盖实际合同长度分布（如 50k、120k、200k token）；
   - **多跳**：条款之间的交叉引用（"第 12 条所述违约情形下，按第 3 条附件 B 的费率赔偿"），需要串联 2–3 处；
   - **聚合**：如"列出所有涉及第三方责任的条款"；
   - **非字面针**：问题用业务语言，条款用法律措辞，没有字面重叠；
   - **真实问题集**：律师标注的 100+ 个问题，可以参考 LongBench v2 单文档 QA 的形式。
2. **报告**：有效检索长度（90%）、有效推理长度（70%）、按任务和深度的热力图、TTFT、单次成本。
3. **通过标准**：最长合同长度 ≤ 有效推理长度（并留余量），TTFT 在产品 SLA 内；否则改用 RAG / 分段处理。
4. **独立复测**：不采信厂商自报分数，在自己的数据上跑。
- **常见误区**：只用 "the magic word is pineapple" 这种与合同无关的针，结果过于乐观。

### Q14 — 参考回答要点

- **固定 harness**：固定的填充语料、针集合、随机种子、深度 × 长度网格、判分规则；评测代码和数据都做版本管理（讲义 Use It："Fixed in-house NIAH + RULER harness, run on every new model"）。
- **任务覆盖**：单针 NIAH + 多针 + 变量追踪（多跳）+ 聚合 + 1 个领域任务；每个任务都有自己的通过阈值。
- **输出**：
  - 每个任务的热力图和退化曲线；
  - 有效检索长度、有效推理长度；
  - 与上一代模型的**增量**（逐格对比，标出变差的格子）；
  - TTFT 与成本随长度的曲线。
- **门禁**：有效长度下降、任一关键格子从通过变为失败、TTFT 超出 SLA，都阻止升级或要求人工评审。
- **统计**：每格多次采样（不同种子、不同针），报告通过率而不是单次 0/1，避免偶然性。
- **加分点**：升级前后用完全相同的 prompt 模板，避免 prompt 变化混入；不同模型使用不同 tokenizer，长度要按"词数 / 字符数"或目标模型的 token 数统一换算。

### Q15 — 参考回答要点

- **长上下文的局限**：
  - **有效长度**：标称 1M 不等于可用 1M，多跳 / 聚合的有效长度可能只有几分之一；
  - **延迟与成本**：1M token 预填充需要 30–120 秒，每次请求都按全量 token 计费；
  - **位置偏差**：中间部分可能被忽视；
  - **规模上限**：企业知识库远超 1M token，总要先筛选。
- **RAG 的优势**：只把相关 chunk 放进上下文，成本低、延迟低、可引用、数据可随时更新；但依赖检索质量，跨文档推理时可能漏掉信息。
- **结论**：两者互补。语料小、需要通读全文、问题跨越全文多处时，用长上下文（前提是测过有效长度）；语料大、问题局部、对延迟和成本敏感时，用 RAG；常见做法是"RAG 粗筛 + 长上下文精读"。讲义的原则："never trust a context window until you have NIAH + 1 reasoning task at your intended length"。
- **加分点**：chunking 策略决定 RAG 的召回上限（第 23 节）；长上下文时可以用 prompt caching 降低重复前缀的成本。

---

## 六、关联知识点

### 前置知识
- [阶段 05 · 13 问答系统](../../13-question-answering/docs/zh.md)：长上下文评测的大部分任务都是 QA 形式。
- [阶段 05 · 23 面向 RAG 的 Chunking 策略](../../23-chunking-strategies-rag/docs/zh.md)：长上下文与 RAG 是同一个问题的两种解法。
- [阶段 05 · 24 共指消解](../../24-coreference-resolution/docs/zh.md)：MRCR 就是"多轮共指消解"。
- [阶段 05 · 27 LLM Evaluation — RAGAS、DeepEval、G-Eval](../../27-llm-evaluation-frameworks/docs/zh.md)：评测方法论、CI 闸门、回归思想。

### 本节被哪些后续内容用到
- [阶段 07 · 04 位置编码](../../../07-transformers-deep-dive/04-positional-encoding/docs/zh.md)：位置编码决定了模型在长距离上的外推能力。
- [阶段 07 · 12 KV Cache 与 Flash Attention](../../../07-transformers-deep-dive/12-kv-cache-flash-attention/docs/zh.md)：长上下文推理的显存与速度瓶颈。
- [阶段 10 · 17 原生稀疏注意力](../../../10-llms-from-scratch/17-native-sparse-attention/docs/zh.md)：为长上下文设计的注意力结构。
- [阶段 11 · 05 上下文工程](../../../11-llm-engineering/05-context-engineering/docs/zh.md)：决定把什么放进上下文、放在哪里。
- [阶段 14 · 07 记忆与虚拟上下文（MemGPT）](../../../14-agent-engineering/07-memory-virtual-context-memgpt/docs/zh.md)：用分层记忆绕开上下文窗口限制。
- [阶段 17 · 08 推理指标与 Goodput](../../../17-infrastructure-and-production/08-inference-metrics-goodput/docs/zh.md)：TTFT 等延迟指标的系统化测量。

### 延伸关键词
`Lost in the Middle` · `RULER` · `LongBench v2` · `NoLiMa` · `BABILong` · `HELMET` · `MRCR` · `RoPE 外推 / YaRN` · `prefill vs decode` · `prompt caching` · `effective context length`
