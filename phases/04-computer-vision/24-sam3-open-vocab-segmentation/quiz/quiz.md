# 测验 · SAM 3 与开放词表分割（SAM 3 & Open-Vocabulary Segmentation）

> **阶段 04 · 计算机视觉 · 第 24 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 三代演进 | SAM（2023，只接受点/框等视觉提示）→ Grounded SAM 2（2024，Grounding DINO 出框 + SAM 2 分割/跟踪的级联）→ SAM 3（2025，原生接受文本/示例图提示，一次前向输出全部实例） |
| 2 | PCS（Promptable Concept Segmentation，可提示概念分割） | 输入一个短名词短语或一张示例图（image exemplar），输出图中**所有**匹配实例的 mask + 唯一 instance ID |
| 3 | 概念提示（concept prompt） | 是"短名词短语"而不是整句话；SAM 3 一次前向只处理一个概念，多概念要循环或批处理 |
| 4 | 共享 backbone + 解耦的检测器/跟踪器 | 一个 ViT 编码图像，图像级检测头与基于记忆的视频跟踪器都读它，但两者头部分离、互不干扰 |
| 5 | Presence head（存在性头） | 先判断"这个概念在图里吗"，再回答"在哪里"；把两个决策解耦，减少对不存在概念的误检 |
| 6 | Memory bank 与 SAM 3.1 Object Multiplex | 视频跟踪靠逐帧存储实例特征的记忆库；Multiplex 把"N 个实例 N 个记忆库"合并成"一个共享记忆 + 每实例查询"，多目标跟踪显著提速 |
| 7 | 数据规模 | 数据引擎（AI + 人工迭代标注纠错）产出 400 万个唯一概念；SA-CO 基准含 27 万概念，比以往大 50 倍；SAM 3 达到人类水平的 75–80% |
| 8 | 选型 | 只要框、要实时 → YOLO-World；要 mask/跟踪 → SAM 3；要换检测器/许可证受限/要细控阈值 → Grounded SAM 2；关注解码器效率 → SAM-MI（约 1.6× 于 Grounded-SAM） |
| 9 | 统一接口与 RLE | 用抽象基类把不同后端包成同一个 `detect(image, concept)`；mask 用游程编码（RLE）压缩，下游不必关心后端是谁 |

### 核心技能（能动手做到）

- [ ] 能写出 `split_concepts`，把 `"cats, dogs and balloons"` 拆成 `['cats', 'dogs', 'balloons']`，并能举出这种启发式会拆错的例子（如 `"black and white cat"`）
- [ ] 能从零实现 `rle_encode` / `rle_decode`，用"往返差异为 0"验证正确性，并能手算一个小 mask 的 RLE 字符串
- [ ] 能用 `abc.ABC` + `@abstractmethod` 定义后端无关的 `OpenVocabSeg` 接口，并写一个确定性的 Stub 实现来测试整条流水线
- [ ] 能解释 Presence head 为什么能减少"对不存在概念的幻觉检测"
- [ ] 给定延迟、是否需要 mask/跟踪、许可证、检测器可替换性四个约束，能在 SAM 3 / Grounded SAM 2 / YOLO-World / SAM-MI 之间做出并论证选型
- [ ] 能处理多概念结果合并中的工程细节：实例 ID 跨概念冲突、按分数过滤、保留概念标签

---

## 二、基础自测（选择题）

**Q1.** 关于 SAM 3 提出的 PCS（Promptable Concept Segmentation），下列描述正确的是：

- A. 先用检测器出框，再对每个框调用一次 SAM 分割
- B. 给一个短名词短语或示例图，单次前向返回所有匹配实例的 mask 和唯一实例 ID
- C. 和经典 SAM 一样，每次点击一个点只返回一个 mask
- D. 只能做视频跟踪，不能处理单张图像

**Q2.** SAM 3 的 presence head 主要解决什么问题？

- A. 给每个实例生成更精细的 mask 边界
- B. 存储跨帧的实例特征以实现跟踪
- C. 把"概念是否出现在图中"与"它在哪里"解耦，让模型能干净地返回"没有"，减少对不存在概念的误检
- D. 把文本提示翻译成视觉 token

**Q3.** SAM 3.1 的 Object Multiplex 替换掉了什么？

- A. ViT backbone
- B. 每个被跟踪实例各自独立的记忆库，改为一个共享记忆 + 每实例查询
- C. Presence head
- D. 文本编码器

**Q4.** 你需要在边缘设备上做**实时**开放词表检测，只需要框、不需要 mask。最合适的是：

- A. SAM 3
- B. Grounded SAM 2
- C. YOLO-World
- D. SAM 3.1 Object Multiplex

**Q5.** 以下哪个场景**最不**构成"2026 年仍然选 Grounded SAM 2 而不是 SAM 3"的理由？

- A. 需要把检测器换成 DINO-X 或 Florence-2 这类特定的开放词表检测器
- B. SAM 3 在 HF 上是 gated 许可，团队法务暂时无法接受
- C. 需要比 SAM 3 暴露的更精细的检测阈值控制
- D. 需要在常见的单词概念（如 "car"）上拿到明显更高的精度

**Q6.** 下面哪个最符合 SAM 3 偏好的概念提示写法？

- A. `"please find every umbrella in this picture that has red stripes"`
- B. `"striped red umbrella"`
- C. `"thing to keep the rain off"`
- D. `"umbrella from yesterday"`

**Q7.** 讲义中关于"用 SAM 3 替换 Grounded SAM 2"的诚实对比，哪项正确？

- A. SAM 3 少了一个独立检测器的前向，但模型本身更重，延迟通常持平或略快
- B. SAM 3 在所有概念上精度都大幅领先
- C. SAM 3 比 Grounded SAM 2 更容易替换检测器组件
- D. SAM 3 延迟一定是 Grounded SAM 2 的一半

**Q8.** SAM-MI 提速的关键思路**不包括**：

- A. 稀疏点提示（sparse point prompting），解码器调用减少约 96%
- B. 浅层 mask 聚合（shallow mask aggregation），把粗 mask 融成一个更锐利的 mask
- C. 解耦的 mask 注入（decoupled mask injection），解码器直接接收预计算的 mask 特征
- D. 用共享记忆库替代逐实例记忆库

---

## 三、动手 / 代码题

**Q9.**（找 bug）讲义 Build It · Step 1 给出的 `split_concepts` 如下。请写出它对三个输入的输出，指出问题，并说明 `code/main.py` 里的版本是怎样修好的。

```python
def split_concepts(sentence):
    """
    Heuristic splitter for multi-concept prompts.
    Returns list of short noun phrases.
    """
    for sep in [",", ";", "and", "or", "&"]:
        if sep in sentence:
            parts = [p.strip() for p in sentence.replace("and ", ",").split(",")]
            return [p for p in parts if p]
    return [sentence.strip()]
```

输入：`"hand holding a mug"`、`"striped red umbrella; green hat"`、`"one large boat or small boat"`。

**Q10.**（预测输出 + 解释）`main.py` 的 RLE 编码如下：

```python
def rle_encode(binary_mask):
    flat = binary_mask.flatten().astype("uint8")
    if flat.size == 0:
        return ""
    runs = []
    prev = int(flat[0])
    count = 0
    for v in flat:
        iv = int(v)
        if iv == prev:
            count += 1
        else:
            runs.append((prev, count))
            prev, count = iv, 1
    runs.append((prev, count))
    return ";".join(f"{v}x{c}" for v, c in runs)
```

1. `rle_encode(np.array([[0, 0, 1], [1, 1, 0]]))` 返回什么？
2. 运行 `main.py` 时，Stub 在 240×320 图上生成的矩形 mask，`mask_len`（按 `;` 切分后的段数）是 241。请推导这个数。
3. 同一次运行中，16×16 随机 mask 的 RLE 字符串长度是 575 个字符，比像素数 256 还大。这说明了什么？

**Q11.**（扩展函数）`run_multi_concept` 对每个概念调用一次 `detect`，而 Stub 对每个概念都从 `instance_id=0` 开始编号。如果下游用 `instance_id` 做字典键（比如存 mask），会出什么问题？请写一个 `run_multi_concept_global(model, image, user_utterance, min_score=0.0)`：分配全局唯一的实例 ID，并丢弃分数低于 `min_score` 的检测，且**不修改**原来的 `ConceptDetection` 对象。

---

## 四、面试高频题

**Q12.**（基础必考）请对比 SAM、SAM 2、Grounded SAM 2、SAM 3：输入是什么、输出是什么、能不能做视频、各自的局限。

**Q13.**（原理深挖）SAM 3 为什么要单独加一个 presence head？如果没有它，模型在"图里根本没有这个概念"时会怎样？它对区分相近提示（如"穿白衣的球员" vs "穿红衣的球员"）有什么帮助？

**Q14.**（工程实践）你们线上有一条 Grounded SAM 2 流水线，老板问"要不要换 SAM 3"。你会怎么评估、看哪些指标、怎么降低迁移风险？

**Q15.**（场景设计）设计一个"零售门店视频分析"系统：运营人员输入自然语言（如"红色购物篮和婴儿推车"），系统统计每个时段画面中这些物体的数量并跟踪它们的轨迹。请给出模型选型、数据流和关键工程点。

**Q16.**（追问型）SAM 3 一次前向只处理一个概念。用户一次问 10 个概念时，延迟会怎么变化？有哪些优化手段？多概念结果合并时还要注意什么？

---

## 五、参考答案与解析

### Q1 — 答案：B

PCS 是 SAM 3 的核心任务：给一个概念（短名词短语或示例图），一次前向返回**所有**匹配实例的 mask 和各自的 ID。A 描述的是 Grounded SAM 这类级联流水线；C 是经典 SAM 的视觉提示模式（一次提示一个 mask）；D 错在 SAM 3 同时支持图像和视频（检测器负责图像，记忆跟踪器负责视频）。

### Q2 — 答案：C

Presence head 预测"概念是否存在于图中"，与定位解耦。一个"被要求必须给出框"的模型，面对不存在的概念时往往会硬凑出匹配（幻觉检测）；有了 presence head，模型可以干净地返回零个检测。A 是 mask 解码器的工作，B 是 memory bank，D 不是 SAM 3 的模块描述。

### Q3 — 答案：B

此前跟踪 N 个实例要维护 N 个记忆库，开销随目标数线性增长。Object Multiplex 改为一个共享记忆 + 每实例查询（per-instance queries），多实例联合跟踪显著提速，同时不牺牲精度。它不涉及 backbone、presence head 或文本编码器。

### Q4 — 答案：C

YOLO-World 是开放词表**检测器**，只出框、不出 mask，专为高帧率设计，适合机器人导航、快速看板这类场景。SAM 3 / 3.1 输出更丰富（mask + 跟踪），但更重；Grounded SAM 2 是两个模型的级联，更慢。原则：工具的"重量"要匹配任务，只需要框就别背 mask 的开销。

### Q5 — 答案：D

讲义的结论是：SAM 3 在**罕见或组合型概念**（如"striped red umbrella"）上明显更好，在**常见单词概念上两者相近**。所以"想在常见单词概念上大幅提精度"恰恰不是选 Grounded SAM 2 的理由。A、B、C 正是讲义列出的 Grounded SAM 2 仍有价值的场景：检测器可替换、许可证约束、阈值可控（另外还有对检测器组件做研究/消融）。

### Q6 — 答案：B

概念提示应该是**短名词短语**，修饰词紧贴名词前。A 是整句话，不是概念提示；C 太抽象（"可以挡雨的东西"）；D 的 "from yesterday" 不是图像中可见的属性。本节 `outputs/skill-concept-prompt-designer.md` 也总结了这些规则：短名词短语、具体名词、修饰语前置、去掉不可见的修饰。

### Q7 — 答案：A

讲义原话的要点：延迟上 SAM 3 省掉一个独立检测器的前向，但模型本身更重，**通常持平或略快**；精度上在罕见/组合概念上明显更好、常见单词概念上相近（所以 B 错）；灵活性上 Grounded SAM 2 可以换检测器，SAM 3 是整体式（monolithic）的（所以 C 正好说反）。D 是编造的数字。

### Q8 — 答案：D

A、B、C 是讲义列出的 SAM-MI 三个关键点，整体效果约为 Grounded-SAM 的 1.6 倍速度。D 是 SAM 3.1 Object Multiplex 的思路，属于视频跟踪的记忆机制，与 SAM-MI 的解码器瓶颈优化无关。

### Q9 — 参考答案

实际输出（已在 Python 3.13 上验证）：

```text
'hand holding a mug'              -> ['h', 'holding a mug']
'striped red umbrella; green hat' -> ['striped red umbrella; green hat']
'one large boat or small boat'    -> ['one large boat or small boat']
```

问题有三个：

1. **子串误匹配**：`"and" in sentence` 是子串判断，`"hand"` 里就含 `"and"`；随后 `replace("and ", ",")` 把 `"hand "` 变成 `"h,"`，于是被拆成 `'h'` 和 `'holding a mug'`。讲义自己举的概念例子 `"hand holding a mug"` 就会被拆坏。
2. **检测到的分隔符和实际用来切分的不一致**：循环检测的是 `;`、`or`、`&`，但真正执行的只有"把 `and ` 换成逗号、再按逗号切"。所以 `;` 和 `or` 被检测到了却没有被切开，原样返回整句。
3. 同理 `"or"` 也是子串判断，`"door"`、`"color"` 都会命中（虽然这里只是提前 return 整句，不会拆坏，但逻辑是错的）。

`main.py` 的修法：

```python
def split_concepts(sentence):
    normalised = sentence
    for sep in [" and ", " or ", "&", ";"]:
        normalised = normalised.replace(sep, ",")
    if "," in normalised:
        parts = [p.strip() for p in normalised.split(",")]
        return [p for p in parts if p]
    return [sentence.strip()]
```

- 先把**所有**分隔符统一替换成逗号，再只按逗号切——检测与切分用的是同一套规则。
- `" and "`、`" or "` 两侧带空格，只匹配独立的单词，不会误伤 `hand`、`door`。

仍然存在的局限（启发式的本质）：`"black and white cat"` 会被拆成 `['black', 'white cat']`；`"Cats AND dogs"` 因大小写不匹配不会被拆。生产中应结合规则 + 小模型/LLM 做概念抽取，并允许用户用引号保护整体短语（本节 skill 文件也提到了这条规则）。

### Q10 — 参考答案

1. `'0x2;1x3;0x1'`。`flatten()` 默认按行优先（C order）展平为 `[0,0,1,1,1,0]`：两个 0、三个 1、一个 0。注意第 0 行末尾的 1 与第 1 行开头的两个 1 **跨行合并**成了一段 `1x3`——RLE 作用在展平后的一维序列上，不关心行边界。

2. Stub 的第一个 mask 覆盖第 72–191 行（120 行）、第 64–159 列（96 列）。按行优先展平后：
   - 开头一段 0（从左上角一直到第 72 行第 64 列之前）：1 段；
   - 之后每一行都是"一段 1（96 个）+ 一段 0（本行右侧 224 个 + 下一行左侧 64 个，合并成一段）"：120 × 2 = 240 段；最后一行的那段 0 一直延伸到图像末尾。
   - 合计 1 + 240 = **241** 段。第二个 mask 同样是 120 行 × 96 列，所以也是 241。可以验证 `rle_decode` 后 `mask.sum() == 120 × 96 == 11520`。

3. 随机 mask 中 0/1 频繁交替，每段平均只有 2 个像素左右，而每段要写成 `"1x2;"` 这样 3–4 个字符，于是字符串比原始像素还长。**RLE 只对"大块连续区域"有效**：分割 mask 通常是大块连通区域，所以压缩率很好；对噪声状的 mask 反而膨胀。这也提醒我们：字符串形式的 RLE（`"1x96"`）是教学简化，COCO 等生产格式会只存计数（隐含 0/1 交替）并进一步压缩。

### Q11 — 参考答案

问题：`oranges` 和 `apples` 的检测都有 `instance_id=0` 和 `1`，以 `instance_id` 为键时后一个概念会**覆盖**前一个概念的结果，导致静默丢数据。要么用 `(concept, instance_id)` 作复合键，要么分配全局唯一 ID。

```python
from dataclasses import replace

def run_multi_concept_global(model, image, user_utterance, min_score=0.0):
    out = []
    next_id = 0
    for c in split_concepts(user_utterance):
        for d in model.detect(image, c):
            if d.score < min_score:
                continue
            out.append(replace(d, instance_id=next_id))   # 生成新对象，不改原对象
            next_id += 1
    return out
```

用 Stub 验证（`"oranges, apples"`）：不过滤时得到 `oranges 0/1, apples 2/3`；`min_score=0.8` 时只剩 `oranges 0 (0.89)`、`apples 1 (0.89)`。

要点：`dataclasses.replace` 返回一个修改了指定字段的**新实例**，避免就地修改后端返回的对象（后端可能有缓存）；先过滤再编号，ID 才是连续的。

### Q12 — 参考回答要点

| 模型 | 输入 | 输出 | 视频 | 局限 |
|------|------|------|------|------|
| SAM（2023） | 图像 + 点/框等视觉提示 | 该提示对应的一个 mask | 否 | 不懂文本；"所有橘子"需要外部检测器先给框 |
| SAM 2 | 同上，扩展到视频 | mask + 跨帧跟踪（记忆机制） | 是 | 仍然是视觉提示 |
| Grounded SAM 2（2024） | 文本 + 图像 | Grounding DINO 出框 → SAM 2 分割、跟踪 | 是 | 两个冻结模型级联，**误差累积**（检测漏了，分割就救不回来） |
| SAM 3（2025） | 短名词短语或示例图 + 图像/视频 | 所有匹配实例的 mask + 实例 ID | 是（记忆跟踪器；3.1 加 Multiplex） | 整体式，不能换检测器；HF 上需申请许可；模型更重 |

- 结构上的关键变化：检测、分割、图文 grounding **合并进同一个模型**。生产问题从"串哪几个模型"变成"哪个可提示模型能端到端覆盖我的场景"。
- 加分点：说出 SAM 3 的组成（共享 backbone、检测器、记忆跟踪器、presence head、检测/跟踪解耦）和 SA-CO 基准（27 万概念）。

### Q13 — 参考回答要点

- **没有 presence head 时**：每个候选只有一个分数，它要同时表达"这里有一个该概念的实例"和"这个实例就在这里"。模型被训练成"有提示就要给出匹配"，面对不存在的概念时倾向于挑一个最像的东西硬凑（幻觉检测）。
- **有 presence head 时**：先在图像级别回答"这个概念在图里吗"，再让定位部分只负责"在哪里"。当存在概率低时，可以干净地返回零检测——对开放词表尤其关键，因为用户输入的概念往往根本不在图里。
- **对相近提示的帮助**：存在性判断要求模型对整个概念（"穿白衣的球员"）做全局判别，而不是只匹配"球员"这个类别，有助于区分只差一个属性的提示。
- 工程含义：presence 分数可以作为一个独立的门控阈值；在评测里应专门统计"对不存在概念的误报率"。
- 常见误区：把 presence head 当成一个 mask 质量分数；或以为它是检测后的 NMS 后处理——它是模型内的一个预测头。

### Q14 — 参考回答要点

- **先建自己的评测集**：从线上流量采样，覆盖常见单词概念、罕见/组合概念（"striped red umbrella"）、**图中不存在的概念**（负样本），以及视频片段。
- **对比维度**（对应讲义 Step 5）：
  - 延迟：端到端 P50/P95。SAM 3 省一个检测器前向但模型更重，预期持平或略快，要实测；
  - 精度：mask IoU、按概念类型分桶的召回率（预期罕见/组合概念提升明显、常见概念相近）、负样本误报率；
  - 灵活性：是否依赖换检测器（领域专用检测器、DINO-X、Florence-2）；
  - 许可：SAM 3 在 HF 上是 gated 的，需要法务确认。
- **降低风险**：用统一接口（本节的 `OpenVocabSeg` 抽象）包住两个后端，先 shadow 流量双跑对比、再灰度切换；输出格式统一（框 + 标签 + 分数 + mask RLE + ID），下游不需要改。
- 加分点：指出"常见单词概念上两者相近"，如果业务概念都很常见，迁移收益可能主要是架构简化，而不是精度。

### Q15 — 参考回答要点

- **输入处理**：运营输入 → 概念提示设计（拆分、去掉"帮我找"这类填充词、保留可见修饰语、限制最大概念数）→ `["red shopping basket", "stroller"]`。
- **模型选型**：要计数 + 轨迹 → 需要跟踪，选 SAM 3.1（Object Multiplex 对同一概念的多个实例做联合跟踪，适合人多物多的门店）。如果某些看板只要"大致数量"、对延迟敏感，可用 YOLO-World 出框做快速通道。
- **数据流**：视频解码抽帧 → 每个概念送入 SAM 3（图像检测 + 记忆跟踪器给出跨帧一致的实例 ID）→ 按时段聚合"每个概念的唯一 ID 数"作为计数 → mask 用 RLE 存储、轨迹用框中心序列存储。
- **关键工程点**：
  - 多概念的实例 ID 要全局唯一或使用 `(concept, id)` 复合键；
  - 统一输出契约，后端可替换（必要时回退到 Grounded SAM 2）；
  - 负样本监控：presence 分数过低时不报数，避免"空货架也报出 3 个篮子"；
  - 记录原始输入与派生的概念，方便排查"是提示写坏了还是模型错了"。

### Q16 — 参考回答要点

- **延迟**：一次前向一个概念，10 个概念大约就是 10 次前向，延迟近似线性增长。
- **优化手段**：
  - 讲义给的办法：对多个概念**批处理**（batch），把串行变成并行，提高 GPU 利用率；
  - 限制每次请求的最大概念数（skill 文件里的 `max_concepts`，多出的放进 `dropped` 并说明原因）；
  - 合并同义/重复概念，去掉抽象概念（"thing"）以减少无效调用；
  - 只需要框的概念走 YOLO-World 这类轻量检测器。
- **合并时的注意事项**：
  - 每条检测保留概念标签（`concept` 字段），否则下游无法区分；
  - 实例 ID 跨概念冲突（见 Q11）；
  - 不同概念可能命中同一物体（"cup" 和 "mug"），是否跨概念去重要按业务决定；
  - 各概念的分数阈值可能需要分别校准。
- 常见误区：直接把 `"cats and dogs"` 整句丢给模型，期待它理解为两个概念——概念提示应当是单个短名词短语。

---

## 六、关联知识点

### 前置知识
- [阶段 04 · 07 语义分割——U-Net](../../07-semantic-segmentation-unet/docs/zh.md)：像素级 mask 的基本概念。
- [阶段 04 · 08 实例分割——Mask R-CNN](../../08-instance-segmentation-mask-rcnn/docs/zh.md)：先检测再分割的两阶段范式，理解"级联"与"实例 ID"。
- [阶段 04 · 18 开放词表视觉——CLIP](../../18-open-vocab-clip/docs/zh.md)：文本与图像对齐，开放词表能力的来源。

### 本节被哪些后续内容用到
- [阶段 04 · 14 Vision Transformers (ViT)](../../14-vision-transformers/docs/zh.md)：SAM 3 的共享 backbone 是 ViT。
- [阶段 04 · 06 物体检测——YOLO](../../06-object-detection-yolo/docs/zh.md)：理解 YOLO-World 作为实时开放词表检测器的定位。
- [阶段 04 · 16 视觉流程 Capstone](../../16-vision-pipeline-capstone/docs/zh.md)：本节的 `ConceptDetection` 输出契约就是对接那条流水线的。
- [阶段 04 · 27 多目标跟踪与视频记忆](../../27-multi-object-tracking/docs/zh.md)：SAM 2/3 的记忆库与 Object Multiplex 的完整展开。
- [阶段 12 · 02 CLIP 对比预训练](../../../12-multimodal-ai/02-clip-contrastive-pretraining/docs/zh.md)：图文对齐的预训练原理。
- [阶段 12 · 21 具身 VLA](../../../12-multimodal-ai/21-embodied-vlas-openvla-pi0-groot/docs/zh.md)：机器人"拿起红杯子"这类开放词表操作。
- [阶段 19 · 12 视频理解流水线](../../../19-capstone-projects/12-video-understanding-pipeline/docs/zh.md)：把分割 + 跟踪接进完整视频系统。

### 延伸关键词
`Grounding DINO` · `DINO-X` · `Florence-2` · `YOLO-World` · `SA-CO` · `Object Multiplex` · `COCO RLE` · `mask IoU` · `CVAT 预标注` · `SAM3-I（指令感知 SAM）`
