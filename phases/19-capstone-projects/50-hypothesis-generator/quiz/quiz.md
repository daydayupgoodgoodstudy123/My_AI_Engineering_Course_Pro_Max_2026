# 测验 · 研究假设生成器（Hypothesis Generator）

> **阶段 19 · 综合项目 · 第 50 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 先生成、再过滤 | 研究循环需要一个**有深度的有序队列**：第一个假设失败时，下一个已经准备好，不必再付一次完整采样的成本 |
| 2 | 结构化的假设记录 | `Hypothesis` 的 `variables`、`metric`、`baseline_ref` 不是自由文本，而是从带标签的回复中解析出来，供第 52 节 runner、第 53 节 evaluator 直接读取 |
| 3 | 带标签的输出 + 解析器 | 用 `<hypothesis><text>…<variables>…<metric>…[<baseline>…]` 约束模型输出；不符合 schema 的回复抛 `ParserError` 并记入日志，而不是让循环崩溃 |
| 4 | Temperature ramp | 从 `t_min` 到 `t_max` 等间距 `n_passes` 个温度，步长 `(t_max − t_min)/(n_passes − 1)`；越往后越"发散"，鼓励新方向 |
| 5 | Hashed embedding | 词 → md5 → 桶下标 + 正负号，累加后 L2 归一化；零依赖、跨进程确定，但会哈希碰撞，只认字面词 |
| 6 | 新颖性过滤 | 新草稿与**已接受**假设的最小余弦距离 `1 − dot(a, b)` 低于阈值（默认 0.25）就判为重复丢弃 |
| 7 | 排名分 | `0.4·novelty + 0.3·specificity + 0.3·testability`；specificity = `min(1, 变量数/3)`，testability = 有 metric 与 baseline 得 1、只有 metric 得 0.5 |
| 8 | 确定性 | 同样的 `(prompt, temperature, seed)` 总得到同样的队列：mock 按 `(prompt 签名, 温度桶)` 查脚本，`seed` 选脚本里的第几条 |
| 9 | 可替换部件 | `embedder` 通过构造函数注入，权重放在 `GeneratorConfig`；生产中换真 LLM、换句向量模型，接口不变 |
| 10 | 在研究循环中的位置 | 50 产出队列 → 51 文献检索确认/反驳 → 52 跑实验 → 53 写判决；队列空了就扩展种子 prompt 或报告预算耗尽 |

### 核心技能（能动手做到）

- [ ] 写出 `GeneratorConfig.schedule()` 的等间距温度表，并处理 `n_passes` 为 0、1 的边界
- [ ] 手算一个假设的 `rank_score`，解释每个子分数的来源
- [ ] 解释 hashed embedding 的原理，并说出为什么用 `hashlib.md5` 而不是内置 `hash()`
- [ ] 构造让新颖性过滤"误杀"和"漏放"的例子，并提出改进方案
- [ ] 写出不依赖生成顺序的对称新颖性重排序，并把分数截断到 `[0, 1]`
- [ ] 给 mock LLM 写脚本、覆盖"解析失败""重复""正常"三条路径的测试
- [ ] 把固定轮数的生成循环改成"凑够 K 个或预算耗尽即停"

---

## 二、基础自测（选择题）

**Q1.** 讲义认为研究 agent 应该"先生成一批、再过滤排序"，而不是"问一次模型拿一个假设"。主要理由是：

- A. 一次只生成一个假设会导致 JSON 解析失败
- B. 研究循环需要一个有深度的有序队列：当前假设被证伪时，下一个已经就绪，无需再付一次完整采样的成本
- C. 生成多个假设可以降低 temperature
- D. 只有这样才能使用 hashed embedding

**Q2.** `GeneratorConfig()` 的默认设置是 6 轮、温度 0.2 → 1.2。默认温度表及对应的 `temperature_bucket` 是：

- A. `[0.2, 0.4, 0.6, 0.8, 1.0, 1.2]`，桶 `[0, 1, 2, 3, 3, 3]`
- B. `[0.2, 0.37, 0.53, 0.7, 0.87, 1.03]`，桶 `[0, 1, 1, 2, 2, 3]`
- C. `[0.2, 0.4, 0.6, 0.8, 1.0, 1.2]`，桶 `[0, 0, 1, 2, 3, 3]`
- D. `[0.2, 0.4, 0.6, 0.8, 1.0, 1.2]`，桶 `[0, 1, 1, 2, 3, 3]`

**Q3.** demo 中 id = 2 的假设：`novelty_score = 0.8498`，3 个变量，有 metric 也有 baseline。按默认权重，它的 `rank_score` 是：

- A. 0.9399
- B. 0.8498
- C. 0.9000
- D. 1.0

**Q4.** `hashed_embed` 用 `hashlib.md5(tok)` 计算桶下标，而不是 Python 内置的 `hash(tok)`。最重要的原因是：

- A. md5 比 `hash()` 快
- B. `hash()` 只能用于整数
- C. 字符串的 `hash()` 默认每个进程随机加盐（`PYTHONHASHSEED`），不同进程结果不同；md5 跨进程、跨机器稳定，才能保证"同样的种子产生同样的队列"
- D. md5 能消除哈希碰撞

**Q5.** 讲义说 `novelty_score` 是"distance from prior survivors, 0..1"。对本节的 `hashed_embed`（带正负号的哈希）+ `cosine_distance`，实际取值范围是：

- A. 严格在 `[0, 1]`，因为向量做了 L2 归一化
- B. `[0, 0.5]`
- C. `[-1, 1]`
- D. `[0, 2]`：两个单位向量点积可以为负，距离最大到 2；此时 `rank_score` 也可能超过 1

**Q6.** 对于**成功通过** `parse_response` 的假设，`_testability_score` 可能的取值是：

- A. 只有 1.0 或 0.5——解析器会拒绝空 metric，所以 0.0 分支对解析出来的假设永远走不到
- B. 0.0、0.5、1.0 都可能
- C. 只有 1.0
- D. 0 到 1 之间的任意值

**Q7.** 用默认 `GeneratorConfig()`（6 轮，0.2 → 1.2）跑 demo 脚本 `build_demo_scripts()`，结果是：

- A. 6 个假设全部入队
- B. 0 个入队，全部解析失败
- C. 4 个入队，第 2、5 轮（温度 0.6 与 1.2）被判为 `duplicate`
- D. 4 个入队，第 2、5 轮被判为 `parse:` 失败

**Q8.** 关于 `_novelty` 与排名，下面说法正确的是：

- A. 每个假设的新颖性都是与**所有其他**假设比较得出的，与生成顺序无关
- B. 新颖性只与**之前已接受**的假设比较，第一个被接受的假设恒为 1.0；同样的四条假设换个生成顺序，排名会改变
- C. 被拒绝的草稿也会加入比较集合
- D. 新颖性越低，排名越靠前

---

## 三、动手 / 代码题

**Q9.** 新颖性过滤的"误杀"与"漏放"。已接受假设 B：`"Lowering attention head count from 8 to 4 raises validation loss by less than 2 percent on a 12M parameter model."`。分别判断下列草稿与 B 的距离大约多少、会不会被当作重复（阈值 0.25），并解释：

1. C：把 B 中 `less than 2 percent` 改成 `more than 20 percent`（结论相反）。
2. A：`"Reducing heads from eight to four barely changes validation loss for a 12M model."`（同义改写）。
3. 两条完全相同的中文假设 `"稀疏注意力降低损失"`。
4. 提出至少三条改进方案。

**Q10.** 顺序依赖与越界：

1. 把 demo 的 4 条假设按相反顺序生成（桶 0 放原来桶 3 的那条，依此类推），"Lowering attention head count…"这条的排名分会从 0.9 变成多少？为什么？
2. 写 `rerank_symmetric(gen, queue)`：生成结束后，把每个假设的新颖性重新定义为"与其他**所有**幸存者的最小距离"，并截断到 `[0, 1]`，再重算 `rank_score` 并排序。给出在 demo 上的结果。

**Q11.** `specificity_score` 只数变量个数：

```python
    def _specificity_score(self, h: Hypothesis) -> float:
        target = max(1, self._cfg.target_variable_count)
        return min(1.0, len(h.variables) / target)
```

1. 指出 demo 中假设 1（`variables = head_count, validation_loss`，`metric = validation_loss`）暴露的问题。
2. 模型可以怎样"刷"这一分？
3. 写一个 `specificity_v2(h)`：只数**不等于 metric** 的自变量（目标为 2 个），文本中没有任何数字时打五折。给出 demo 四条假设的新旧分数对比。

**Q12.** 固定 `n_passes` 的循环可能产出过少的假设，也可能浪费采样。

1. 解释为什么 demo 脚本里 `seed` 对输出没有任何影响，而讲义说"the same `(prompt, temperature)` pair with different seeds produces different drafts"。
2. 写 `run_until(gen, llm, prompt, k, max_samples, cfg)`：循环使用温度表，直到凑够 `k` 个幸存者或用完 `max_samples` 次采样。分别用 `k=3` 与 `k=6`（`max_samples=10`）在 demo 脚本上运行，各采样了几次、得到几个假设？
3. 对 `k=6` 的结果，你会加什么停止条件？

---

## 四、面试高频题

**Q13.**（基础必考）如何让 LLM 稳定地输出"结构化的研究假设"，并在输出不合规时不让整个 agent 崩溃？

**Q14.**（原理深挖）temperature ramp 与"同一温度多次采样"在多样性上有什么区别？只靠调高温度来追求新颖性有什么风险？

**Q15.**（原理深挖）用 embedding 余弦距离做去重的局限是什么？在"研究假设"这个场景下，什么样的两个假设应该算"重复"？

**Q16.**（工程实践）把这个生成器接到真实 LLM 和真实句向量模型上，需要改哪些地方？如何保持可复现与可测试？

**Q17.**（场景设计 / 追问型）排名分的三项权重（0.4 / 0.3 / 0.3）是拍脑袋定的。上线后你会怎么校准它们？如果发现排名靠前的假设经常在第 51 节文献检索里被"已经有人做过"否决，你会怎么改？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义："The loop wants a ranked queue with depth, so when the first hypothesis fails the runner has the next one ready without paying for another full sampling pass." A 与生成数量无关；C 说反了——本节是逐轮**升高**温度；D 无因果关系，embedding 只是用来去重。

### Q2 — 答案：D

步长 `(1.2 − 0.2)/(6 − 1) = 0.2`，温度为 0.2、0.4、0.6、0.8、1.0、1.2。桶边界是 `<0.35 → 0`、`<0.65 → 1`、`<0.95 → 2`、其余 → 3，因此桶为 `[0, 1, 1, 2, 3, 3]`（实际运行确认）。A、C 的桶算错了；B 的温度是按 `n_passes` 而不是 `n_passes − 1` 等分的错误结果。注意：6 个温度只落进 4 个桶，有两对温度会拿到相同的脚本（见 Q7）。

### Q3 — 答案：A

`specificity = min(1, 3/3) = 1`，`testability = 1`（metric + baseline），`rank = 0.4 × 0.8498 + 0.3 × 1 + 0.3 × 1 = 0.33992 + 0.6 = 0.9399`，与运行输出一致。B 只取了 novelty；C 是假设 1 的分数（`0.4×1.0 + 0.3×(2/3) + 0.3×1 = 0.9`）；D 假设了 novelty 为 1。

### Q4 — 答案：C

CPython 对 `str`/`bytes` 的 `hash()` 默认在每次启动解释器时随机化（防哈希洪水攻击）。我们在两个进程里各算一次 `hash("attention")`，得到 `-389588366348815844` 与 `-2291074063867271221`。若用 `hash()`，桶下标每次运行都会变，"同样的种子产生同样的队列"就不成立。A 错，md5 更慢；B 错；D 错，128 维照样碰撞（见 Q9 讲解中 `memory` 与 `w7` 的例子）。

### Q5 — 答案：D

每个词以 +1 或 −1 加到某个桶，两个向量的点积可以为负。实测：找到两个落在同一桶、符号相反的单词 `w0` 与 `w4`，各自作为一条假设文本时余弦距离为 **2.0**；用它们跑生成器，第二条的 `novelty_score = 2.0`，`rank_score = 0.4×2 + 0.3 + 0.3 = 1.4`。`cosine_distance` 里的 `max(-1, min(1, dot))` 只截断了点积，没有截断距离。讲义 "0..1" 的说法与实现不符；`test_specificity_weight_changes_rank` 断言 `rank_score ≤ 1` 时把 `w_novelty` 设成了 0，正好避开了这个问题。

### Q6 — 答案：A

`parse_response` 里 `if not metric: raise ParserError("empty metric")`，所以入队的假设 metric 一定非空，testability 只能是 1.0（有 baseline）或 0.5（无 baseline）。0.0 分支只有在绕过解析器直接构造 `Hypothesis` 时才会走到（我们手工构造验证过）。这是"防御性代码"，无害，但说明 testability 实际上只是"有没有 baseline"的二值信号。

### Q7 — 答案：C

实测日志：第 0 轮（0.2，桶 0）接受；第 1 轮（0.4，桶 1）接受；第 2 轮（0.6，桶 1）`duplicate`；第 3 轮（0.8，桶 2）接受；第 4 轮（1.0，桶 3）接受；第 5 轮（1.2，桶 3）`duplicate`。demo 每个桶只有 1 条脚本，`bank[seed % 1]` 永远取第 0 条，同一个桶第二次被访问时返回完全相同的文本，距离为 0。所以 demo 和 README 里都用了 `n_passes=4, t_max=1.1` 让 4 个温度恰好各占一个桶。D 错，文本是合法的，只是重复。

### Q8 — 答案：B

`_novelty` 只对 `survivor_vecs`（已接受的向量）取最小距离，空列表时直接返回 1.0。因此第一个被接受的假设"天生"满分新颖。实测把 demo 顺序倒过来，"Lowering attention head count…"从排名 3（0.9）跌到最后（0.8032），见 Q10。A 是 Q10 要实现的改进；C 错，被拒绝的不加入；D 说反了。

### Q9 — 参考答案

实测距离（hashed_embed + cosine_distance）：

1. **C vs B ≈ 0.095** → 低于 0.25，被判为重复丢弃。两句只差 `less/more`、`2/20` 几个词，词袋几乎一样；但它们是**相反的科学主张**，恰恰应该都保留（甚至应该成对测试）。词袋 embedding 看不到否定、比较方向和数值大小。
2. **A vs B ≈ 0.592** → 远高于阈值，被当作新颖假设接受。同义改写（`heads`/`head count`、`eight`/`8`）在字面上几乎不共享词，词袋认为它们很不一样——"漏放"。
3. `_tokenise` 只匹配 `[a-z0-9]+`，中文文本得到**零向量**，`hashed_embed` 遇到范数为 0 直接返回全零。零向量与任何向量的点积为 0，距离恒为 1.0，于是两条完全相同的中文假设**都被接受**（实测两条的 `novelty_score` 都是 1.0）。
4. 改进方案（任选三条以上）：
   - 换成句向量模型（讲义："A production deployment would swap in a small sentence model"），能处理同义改写与多语言；
   - 零向量单独处理：文本无法嵌入时直接拒绝或回退到字符 n-gram；
   - 结构化去重：在 `(variables 集合, metric, baseline)` 相同的前提下再比较文本，而不是只比较文本；
   - 对"方向相反"的主张做显式检测（例如用 NLI 模型判断蕴含/矛盾），矛盾对应该保留并关联；
   - 加大哈希维度（128 → 4096 等）或使用多个哈希函数减少碰撞——实测 128 维下 `memory` 与 `w7` 落在同一桶且同号，两个毫不相干的单词距离为 0。

### Q10 — 参考答案

1. 倒序后（实测）：Block sparse 1.0 → Routing 1.0（与 Block 的距离恰为 1.0）→ Top-k 0.8974 → Lowering **0.8032**。原因：正序时 Lowering 是第一个被接受的，novelty 白拿 1.0；倒序时它最后一个出现，novelty 变成与前三条的最小距离 0.7579，`0.4×0.7579 + 0.3×(2/3) + 0.3×1 = 0.8032`。同样的四条假设，排名完全取决于采样顺序——这不是"假设本身的质量"。
2. 参考实现（已在 demo 上运行验证）：

```python
def rerank_symmetric(gen, queue, embed=hashed_embed):
    vecs = {h.id: embed(h.text) for h in queue}
    for h in queue:
        others = [vecs[o.id] for o in queue if o.id != h.id]
        d = min((cosine_distance(vecs[h.id], v) for v in others), default=1.0)
        h.novelty_score = min(1.0, d)              # 截断到 [0, 1]
        h.rank_score = gen._score(h)
    queue.sort(key=lambda h: (-h.rank_score, h.id))
    return queue
```

   demo 结果（`id, novelty, rank`）：`3, 0.7579, 0.9032`；`2, 0.7435, 0.8974`；`4, 0.7435, 0.8974`；`1, 0.7579, 0.8032`。不论生成顺序如何，结果都相同。`min(..., default=1.0)` 处理只有一个幸存者的情况。另一种常见做法是 MMR（Maximal Marginal Relevance）：贪心地每次选"质量高且与已选集合最不相似"的一条。

### Q11 — 参考答案

1. 假设 1 的 `variables` 里包含了 `validation_loss`，而它就是 `metric`——因变量被当成了"变量"计数。demo 中假设 2 的 `perplexity`、假设 4 的 `training_seconds` 也一样。讲义把 variables 定义为 "what changes between conditions"（实验条件之间改变的东西，即自变量），把因变量算进去就混淆了"操纵什么"与"测量什么"。
2. 刷分方法：在 `<variables>` 里随便列 3 个以上名字即可拿满 specificity（实测 `a,b,c,d,e,f` 解析通过，得 1.0）；把 metric 也列进去；列与文本无关的变量。
3. 参考实现（已运行验证）：

```python
import re
NUM = re.compile(r"\d")

def specificity_v2(h, target=3):
    indep = [v for v in h.variables if v != h.metric]     # 去掉因变量
    score = min(1.0, len(indep) / max(1, target - 1))      # 目标 2 个自变量
    if not NUM.search(h.text):                              # 没有可检验的数值就打五折
        score *= 0.5
    return score
```

| id | variables | metric | 旧分 | 新分 |
|----|-----------|--------|------|------|
| 1 | head_count, validation_loss | validation_loss | 0.667 | 0.5 |
| 2 | k, perplexity, parameter_count | perplexity | 1.0 | 1.0 |
| 3 | gate_temperature, flops, accuracy | downstream_accuracy | 1.0 | 1.0 |
| 4 | block_size, training_seconds, hardware | training_seconds | 1.0 | 1.0 |

   注意假设 3 的变量 `accuracy` 与 metric `downstream_accuracy` 名字不完全相同，字符串比较认不出来——更彻底的做法是在 schema 里拆成 `<independent>` 与 `<dependent>` 两个标签，或者要求每个自变量给出取值范围（如 `head_count: 8 -> 4`）。

### Q12 — 参考答案

1. `MockLLM.sample` 返回 `bank[seed % len(bank)]`。demo 每个桶的 `bank` 只有 1 条，`seed % 1 == 0`，所以 seed 完全不起作用。讲义那句话只有在 bank 有多条脚本时才成立（实测给一个桶放两条脚本，`base_seed=0` 与 `1` 分别取到不同文本）。真实 LLM 的 seed 会影响采样，但同一温度下不同 seed 的输出也可能高度相似。
2. 参考实现（已运行验证）：

```python
def run_until(gen, llm, prompt, k, max_samples, cfg):
    survivors, vecs, logs = [], [], []
    temps = cfg.schedule()
    for i in range(max_samples):
        if len(survivors) >= k:
            break
        t = temps[i % len(temps)]                    # 温度表循环使用
        raw = llm.sample(prompt, t, cfg.base_seed + i)
        try:
            p = parse_response(raw)
        except ParserError:
            logs.append((i, "parse")); continue
        v = hashed_embed(p["text"])
        nov = gen._novelty(v, vecs)
        if nov < cfg.novelty_threshold:
            logs.append((i, "dup")); continue
        h = Hypothesis(len(survivors) + 1, p["text"], p["variables"], p["metric"],
                       p["baseline_ref"], i, t, nov)
        h.rank_score = gen._score(h)
        survivors.append(h); vecs.append(v); logs.append((i, "ok"))
    survivors.sort(key=lambda h: (-h.rank_score, h.id))
    return survivors, logs
```

   - `k=3`：采样 4 次（ok, ok, dup, ok）后凑够 3 个即停。
   - `k=6`：10 次全部用完，只得到 4 个，其余 6 次都是 `dup`（第 2 次，以及第 5–9 次：4 个桶的脚本都已用过，之后每次都重复）。
3. 加"连续 N 次重复/解析失败即停"的早停（例如连续 3 次），并在日志中报告"候选空间耗尽"，交给编排器去**扩展种子 prompt**（讲义 "Output queue" 一节：队列空了就 widen the seed prompt 或报告预算耗尽）。也可以在连续重复时把被拒绝的文本作为"不要重复这些"的负例加进 prompt。

### Q13 — 参考回答要点

- **约束格式**：在 prompt 中给出明确 schema 与示例（本节用 XML 风格标签；也可以用 JSON Schema / 结构化输出 / tool calling 让 API 强制返回结构）。
- **宽进严出的解析器**：正则或 JSON 解析 + 字段校验（非空、类型、取值范围），失败抛专用异常 `ParserError`。
- **失败不崩溃**：在循环里捕获，记录 `reject_reason` 与原文摘录（本节 `GenerationLog.raw_excerpt` 截前 80 字符），继续下一轮。
- **重试与修复**：把错误信息回传给模型让它修正一次；或换温度重采样。
- **可观测**：统计解析失败率，失败率升高通常意味着温度过高或 prompt 退化（讲义："Above 1.2 the responses tend to drift off topic and fail the parser"）。
- 加分点：本节正则要求标签**严格按顺序**出现（实测把 `<metric>` 放到 `<variables>` 前面就解析失败），真实模型输出顺序不稳定时应逐个标签独立匹配。

### Q14 — 参考回答要点

- **Temperature ramp**：不同轮使用递增的温度，前几轮保守、后几轮发散，覆盖"稳妥 → 大胆"的谱系；每轮一个样本，成本固定。
- **同温多采样**：在一个温度下取多个 seed，多样性来自采样随机性；温度适中时质量稳定，但多个样本可能扎堆在同一个模式附近。
- **只靠高温的风险**：高温提高的是 token 级随机性，不等于"科学上的新颖"；会带来格式错误、跑题、事实错误、不可检验的空话。讲义也说高于 1.2 时容易跑题并解析失败。
- **更好的多样性手段**：在 prompt 中显式要求"与以下已有假设不同"（把已接受的假设作为负例）、换角度的种子 prompt（机制/规模/效率/鲁棒性）、先生成研究方向再在方向内生成假设、生成后用 MMR 选多样子集。
- 加分点：讲义的 mock 用"温度桶"模拟温度效应；真实模型的温度与多样性关系是连续且模型相关的，需要实测解析成功率与去重率来选 `t_min/t_max`。

### Q15 — 参考回答要点

- **局限**：
  - 词袋/哈希 embedding 只看字面，同义改写判为不同、只差否定词或数字的相反主张判为相同（Q9 实测 0.592 与 0.095）；
  - 句向量模型更好，但同样对否定、数值、比较方向不敏感，"A 提升 B"与"A 降低 B"往往很近；
  - 阈值是全局常数，不同领域、不同长度的文本距离分布不同；
  - 只看文本，不看结构化字段。
- **研究假设的"重复"应该怎么定义**：操纵的自变量相同、测量的因变量相同、比较的基线相同、预测方向相同，才是同一个实验。只要其中之一不同（例如同样的自变量但预测相反），就是不同的可检验假设。
- **做法**：结构化字段先粗筛（变量集合 + metric + baseline），再用语义相似度细筛，再对高相似对用 NLI/LLM 判定"是否同一主张"。
- 加分点：去重还要跨运行（与历史队列、已完成实验比较），否则每次重启都会重复生成相同假设。

### Q16 — 参考回答要点

- **LLM**：写一个与 `MockLLM.sample(prompt, temperature, seed)` 同签名的适配器，把 temperature、seed（若 API 支持）传给模型；记录模型版本与原始回复。
- **Embedding**：`HypothesisGenerator(..., embedder=...)` 已支持注入，换成句向量模型函数即可；注意向量应 L2 归一化，或在 `cosine_distance` 中显式除以范数。
- **Prompt**：把"已接受假设"作为负例拼进 prompt（mock 里 prompt 固定，真实模型需要每轮更新）。
- **可复现**：缓存每次 `(prompt, temperature, seed, model_version) → 原始回复`，回放时不调 API；排行与过滤是纯函数，结果完全由缓存决定。
- **可测试**：单元测试继续用 `MockLLM` 脚本覆盖解析失败、重复、正常三条路径（本节测试就是这样做的）；集成测试用少量真实调用、只断言结构不断言内容。
- **成本控制**：限制轮数与 token；早停（Q12）。

### Q17 — 参考回答要点

- **校准权重**：以下游结果作为标签——第 51 节文献检索是否判为"已知/新颖"、第 52/53 节实验是否成功跑通、结果是否显著。收集一批 `(子分数, 下游结果)`，用逻辑回归或排序学习（learning to rank）拟合权重；或做 A/B：不同权重组合下"每单位预算产出的有效发现数"。
- **权重放在配置里**：讲义强调权重在 `GeneratorConfig` 中，下游课程可以调而不用 fork 代码。
- **"已经有人做过"问题**：说明 novelty 只衡量"与本批次其他假设的差异"，不衡量"与文献的差异"。改进：
  - 在生成阶段就做一次轻量文献检索（第 51 节），把"与已知论文的最大相似度"作为新的 `literature_novelty` 子分数加入排名；
  - 把检索到的相关工作摘要放进生成 prompt，要求模型提出"在此基础上的差异点"；
  - 把被否决的假设加入负例库，后续生成时去重。
- 常见误区：继续提高 temperature 来追求"新颖"——高温只增加随机性，不增加对文献的了解。

---

## 六、关联知识点

### 前置知识
- [阶段 19 · 20 Agent Harness 的循环契约](../../20-agent-harness-loop-contract/docs/zh.md)：本节是 Track A 循环原语在"研究"场景下的应用（讲义先修：Track A 第 20–29 课）。
- [阶段 19 · 25 Verification Gates 与观察预算](../../25-verification-gates-observation-budget/docs/zh.md)：解析失败、重复都属于"门控"，轮数就是预算。
- [阶段 10 · 04 预训练 Mini GPT](../../../10-llms-from-scratch/04-pre-training-mini-gpt/docs/zh.md)：temperature 如何改变采样分布。
- [阶段 11 · 04 Embeddings 与向量表示](../../../11-llm-engineering/04-embeddings/docs/zh.md)：余弦距离与句向量。
- [阶段 05 · 22 Embedding 模型 — 2026 年深度剖析](../../../05-nlp-foundations-to-advanced/22-embedding-models-deep-dive/docs/zh.md)：生产中替换 hashed embedding 的选择。

### 本节被哪些后续内容用到
- [阶段 19 · 51 文献检索](../../51-literature-retrieval/docs/zh.md)：取队首假设检索相关论文，确认或反驳。
- [阶段 19 · 52 实验执行器](../../52-experiment-runner/docs/zh.md)：读取 `variables` 与 `metric` 构造实验配置。
- [阶段 19 · 53 结果评估器](../../53-result-evaluator/docs/zh.md)：用 `baseline_ref` 做对比并写判决。
- [阶段 19 · 56 迭代调度器](../../56-iteration-scheduler/docs/zh.md)：决定何时弹出下一个假设、何时重新生成。
- [阶段 19 · 57 端到端研究演示](../../57-end-to-end-research-demo/docs/zh.md)：把 50–56 串成完整研究循环。
- [阶段 15 · 05 AI Scientist v2](../../../15-autonomous-systems/05-ai-scientist-v2/docs/zh.md)：自主研究系统中的想法生成与新颖性检查。
- [阶段 19 · 05 自主研究 Agent——AI-Scientist 级系统](../../05-autonomous-research-agent/docs/zh.md)：同类系统的完整项目版本。

### 延伸关键词
`structured output` · `XML tags / JSON schema` · `temperature schedule` · `feature hashing` · `signed hashing trick` · `cosine distance` · `semantic deduplication` · `MMR (Maximal Marginal Relevance)` · `NLI contradiction detection` · `learning to rank` · `PYTHONHASHSEED` · `dependency injection` · `deterministic mock LLM`
