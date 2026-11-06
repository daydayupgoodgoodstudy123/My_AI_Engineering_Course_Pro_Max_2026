# 代码讲解 · main.py

> **所属小节**：阶段 18 · 伦理、安全与对齐 · 第 20 节 LLMs 中的偏见与表征性伤害 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py` ｜ **依赖**：仅标准库（`math`），无第三方包

---

## 1. 这份代码在考察什么

这是一个 WEAT 形状的玩具偏见探针，对应 Gallegos 等人 2024 三类指标中的第一类：**embedding-based**。它做三件事：

1. **度量**：在一个手工构造的 4 维 embedding 中，计算身份词（he/his/man vs she/her/woman）与属性词（engineer/programmer/scientist vs nurse/teacher/caregiver）之间的 WEAT 式关联差。
2. **去偏**：把属性词在"性别方向"上的分量投影掉（Bolukbasi 2016 hard debiasing 中"中立化"那一步的简化版）。
3. **观察**：去偏后指标下降，但没有归零。

讲义练习 1 要求解释"为什么没有归零"。代码 TAKEAWAY 给出的理由（"because the toy is 4-d"）**并不正确**。本讲解第 3.4 和第 6 节会用实验说明：真正的原因是偏见同时编码在身份词的 tech/care 分量里，而投影只处理了属性词的性别方向。

> 一句话：**用 12 个 4 维向量把"测量偏见 → 投影去偏 → 残留偏见"演示完整，并留下一个典型教训：指标变小不等于偏见消失。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `EMB` | 全局字典 | 12 个词 → 4 维向量；轴 0 masculine、1 feminine、2 tech、3 care | 词向量空间 |
| `cos(u, v)` | 函数 | 余弦相似度（分母加 `1e-9` 防止除零） | 向量关联度 |
| `weat_score(A, B, X, Y)` | 函数 | 内部函数 `s(w)` = 与 X 的平均余弦 − 与 Y 的平均余弦；返回 A 组均值 − B 组均值 | WEAT 检验统计量（未标准化） |
| `debias(emb)` | 函数 | 复制 embedding，只对 6 个属性词减去在 `[1,−1,0,0]` 上的投影 | 投影去偏 / 中立化 |
| `main()` | 函数 | 打印去偏前分数 → 替换全局 `EMB` → 打印去偏后分数 → TAKEAWAY | 实验流程 |

数据流：`EMB` → `weat_score` → 打印 pre → `EMB = debias(EMB)`（`global` 重绑定）→ `weat_score` → 打印 post。

---

## 3. 逐段精讲

### 3.1 手工 embedding：偏见是"写进去的"

```python
# 4-d embedding. Axis 0 = "masculine", 1 = "feminine", 2 = "tech", 3 = "care".
EMB = {
    # identity A
    "he":        [ 1.0, 0.0, 0.2,  0.0],
    "his":       [ 0.9, 0.0, 0.1,  0.0],
    "man":       [ 1.0, 0.0, 0.1,  0.1],
    # identity B
    "she":       [ 0.0, 1.0, 0.0,  0.2],
    ...
    # attribute X: tech / career
    "engineer":  [ 0.4, 0.0, 1.0,  0.0],
    ...
    # attribute Y: care / family
    "nurse":     [ 0.0, 0.4, 0.0,  1.0],
    ...
}
```

偏见被写进了**两个地方**，这一点是理解后面所有结果的关键：

| 偏见位置 | 例子 | 去偏能否处理 |
|---------|------|-------------|
| 属性词带性别分量 | engineer 的 masculine = 0.4；nurse 的 feminine = 0.4 | 能，`debias` 就是处理它 |
| 身份词带职业分量 | he 的 tech = 0.2；she 的 care = 0.2 | **不能**，`debias` 不碰身份词，而且这部分不在性别方向上 |

- 每个轴都有明确语义，这在真实 embedding 中不存在。真实的 300 维向量没有"tech 轴"，性别信息分散在许多方向上。
- ⚠️ 讲义 Use It 说代码"in a simple co-occurrence embedding"，并且"You can inject a bias and observe the metric fire"。实际上，向量是手工指定的，不是从共现统计得来；代码也没有"注入偏见"的函数，偏见是硬编码的。Key Terms 把 WEAT 定义为 "co-occurrence-based bias probe" 也不准确：WEAT 基于向量的余弦关联，适用于任何 embedding，与它们是否来自共现统计无关。

### 3.2 `cos`：余弦相似度

```python
def cos(u: list[float], v: list[float]) -> float:
    nu = math.sqrt(sum(x * x for x in u)) + 1e-9
    nv = math.sqrt(sum(x * x for x in v)) + 1e-9
    return sum(a * b for a, b in zip(u, v)) / (nu * nv)
```

- `cos(u, v) = u·v / (|u||v|)`，只看方向、不看长度，取值 [−1, 1]。本例中所有分量非负，所以余弦在 [0, 1] 之间。
- `+ 1e-9` 防止零向量导致除零；对正常向量的影响约为 1e-9，可以忽略。
- 典型数值（已实际计算）：`cos(he, engineer) = 0.5463`，`cos(he, nurse) = 0.0`（完全正交），`cos(she, nurse) = 0.5463`。身份词与属性词的关联是**对称构造**的。

### 3.3 `weat_score`：两层平均

```python
def weat_score(identity_a, identity_b, attr_x, attr_y) -> float:
    def s(w):
        mx = sum(cos(EMB[w], EMB[a]) for a in attr_x) / len(attr_x)
        my = sum(cos(EMB[w], EMB[a]) for a in attr_y) / len(attr_y)
        return mx - my
    mean_a = sum(s(w) for w in identity_a) / len(identity_a)
    mean_b = sum(s(w) for w in identity_b) / len(identity_b)
    return mean_a - mean_b
```

- 第一层：`s(w)` 衡量**单个身份词** w 更靠近 X 还是 Y。
- 第二层：两组身份词的 s 均值之差。
- `s` 是定义在函数内部的**嵌套函数**，它读取的是全局 `EMB`，所以 `main()` 替换 `EMB` 后，同一个 `weat_score` 自动使用新的 embedding。
- ⚠️ **与原版 WEAT 的差异**：Caliskan 等人 2017 的 effect size 是 `(mean_a − mean_b) / std(全部身份词的 s)`，并用置换检验求 p 值。代码打印的 "WEAT effect size" 实际上是**未标准化的均值差**。两者的差别在本例中影响很大：去偏后均值差降了 75%（0.8906 → 0.2212），标准化 effect size 只从 1.81 降到 1.60（测验 Q10）。
- 6 个身份词的 s 值（实际运行）：

| 词 | s（去偏前） | s（去偏后） |
|----|-----------|-----------|
| he | +0.5138 | +0.1831 |
| his | +0.4408 | +0.1031 |
| man | +0.3396 | 0.0000 |
| she | −0.5138 | −0.1831 |
| her | −0.4408 | −0.1031 |
| woman | −0.4230 | −0.0911 |

### 3.4 `debias`：只中立化属性词

```python
def debias(emb: dict) -> dict:
    """Crude debias: project out the gender direction (axis 1 minus axis 0)."""
    new = {k: list(v) for k, v in emb.items()}
    gender_dir = [1.0, -1.0, 0.0, 0.0]
    norm_sq = sum(x * x for x in gender_dir)
    for w in ["engineer", "programmer", "scientist",
              "nurse", "teacher", "caregiver"]:
        proj = sum(a * b for a, b in zip(new[w], gender_dir)) / norm_sq
        new[w] = [a - proj * b for a, b in zip(new[w], gender_dir)]
    return new
```

- `{k: list(v) for ...}`：字典推导式加 `list(v)`，复制出新的字典和新的列表，避免修改原 embedding（浅拷贝外层字典的同时复制了内层列表）。
- 投影公式：`w' = w − (w·g / |g|²) g`。以 engineer 为例：`w·g = 0.4`，`|g|² = 2`，`proj = 0.2`，`w' = [0.2, 0.2, 1.0, 0.0]`。masculine 与 feminine 分量相等，即在性别方向上中立。
- ⚠️ docstring 写 "axis 1 minus axis 0"（feminine − masculine），但代码中 `gender_dir = [1, −1, 0, 0]` 是 axis 0 − axis 1。方向差一个符号，对投影结果没有影响（`g` 和 `−g` 张成同一条直线），但注释与代码不一致。
- 真实的 Bolukbasi 2016 方法：用多个性别词对的差向量做 PCA 估计 g；对中立词做中立化（neutralize）；再对性别词对做均衡化（equalize）。这里的 g 是手工指定的"正确答案"，真实场景里拿不到。
- **为什么不归零**：投影后所有属性词在性别方向上中立，但身份词仍带着 tech/care 分量（he 有 0.2 tech，she 有 0.2 care），它们与属性词的 tech/care 分量相乘，仍然产生关联差。实验验证（测验 Q11）：再把身份词的 tech/care 清零，WEAT 精确地变为 0；而如果对**所有词**投影，WEAT 反而升到 0.3080。所以残留来自"偏见编码在性别方向之外"，与维度高低无关。这正是 Gonen & Goldberg 2019 所说的投影去偏"掩盖而非消除"。

### 3.5 `main` 与 `global EMB`

```python
def main() -> None:
    global EMB
    ...
    pre = weat_score(A, B, X, Y)
    print(f"\npre-debias WEAT effect size : {pre:+.4f}")
    ...
    EMB = debias(EMB)
    post = weat_score(A, B, X, Y)
    print(f"post-debias WEAT effect size: {post:+.4f}")
```

- `global EMB` 声明后，函数内的 `EMB = ...` 会**重新绑定模块级变量**，否则 Python 会把 `EMB` 当作局部变量，导致 `debias(EMB)` 在赋值前被读取而报 `UnboundLocalError`。
- ⚠️ 这是一种"隐式状态"设计：`weat_score` 依赖全局变量，调用顺序决定结果；如果在别处 import 这个模块并调用 `main()` 两次，第二次的 "pre" 实际上已是去偏后的值。更好的写法是让 `weat_score` 接收 embedding 参数（第 7 节练习 1）。
- `{pre:+.4f}`：带正负号、保留 4 位小数。

### 3.6 TAKEAWAY 的对与错

- 对："embedding-based bias is measurable and partially reducible"；"probability- and generated-text-based metrics are required to capture the behavioural bias residual"，这与讲义的三类指标框架一致。
- ⚠️ 错："the metric does not drop to zero because the toy is 4-d"。见 3.4，残留与维度无关。
- 补充："real debiasing (Bolukbasi 2016) operates on 300-d embeddings"，原论文使用的是 300 维 word2vec 向量，这一点没问题。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 手工 4 维、轴有语义 | 每个数字都能手算，偏见在哪里一目了然 | 真实 embedding 没有可解释的轴；生产中要用预训练向量（如 GloVe、word2vec）或上下文化 embedding（SEAT） |
| 每组只有 3 个词 | 简洁 | 置换检验的 p 值最小只能是 1/20 = 0.05，统计上无法得到更强结论；真实 WEAT 每组 8 个词以上 |
| 打印未标准化的均值差 | 直观 | 与原版 effect size 不可比，会夸大去偏效果（均值差降 75%，标准化值只降约 11%） |
| 手工指定性别方向 `[1,−1,0,0]` | 避免 PCA 等额外步骤 | 真实场景中性别方向需要估计，而且不止一个；只投影一个方向会遗留偏见 |
| 只中立化属性词 | 对应 Bolukbasi 的 neutralize 步骤 | 身份词中的职业关联没被处理；也没有 equalize 步骤 |
| `global EMB` 原地替换 | 少传一个参数 | 隐式状态、不可重入；应把 embedding 作为参数传递 |
| 只测二元性别 | 讲义的玩具示例 | 恰好落入元批评所说的"过度集中于二元性别"；练习 2 和练习 5 要求扩展 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 嵌套列表作为向量 | `"he": [1.0, 0.0, 0.2, 0.0]` | 用 Python 列表表示向量，不依赖 NumPy |
| 生成器表达式 + `sum` | `sum(x * x for x in u)` | 不建中间列表，直接逐个求和，相当于 `Σ x²` |
| `zip` 并行遍历 | `sum(a * b for a, b in zip(u, v))` | 把两个向量的对应分量配对，实现点积 |
| `math.sqrt` | `math.sqrt(sum(...))` | 平方根，用于求向量范数 |
| 类型注解 `list[float]` | `def cos(u: list[float], v: list[float]) -> float` | Python 3.9+ 可直接写内置泛型 |
| 嵌套函数（闭包） | `weat_score` 里的 `def s(w):` | 内部函数可以读取外层函数的参数 `attr_x`、`attr_y` |
| 字典推导式 | `{k: list(v) for k, v in emb.items()}` | 复制字典并复制每个列表值 |
| 列表推导式 | `[a - proj * b for a, b in zip(new[w], gender_dir)]` | 逐分量计算新向量 |
| `global` 声明 | `global EMB` | 在函数内重新绑定模块级变量；不声明会被当作局部变量 |
| 多行字符串 docstring | `"""Crude debias: ..."""` | 函数说明 |
| f-string 正号格式 | `{pre:+.4f}` | 显示符号，保留 4 位小数 |
| 列表字面量换行 | `for w in ["engineer", ..., \n "nurse", ...]:` | 括号内可直接换行 |
| `if __name__ == "__main__"` | 文件末尾 | 直接运行时才执行 `main()` |

---

## 6. 运行结果解读

实际运行（Python 3，标准库，瞬间完成，退出码 0）：

```text
======================================================================
TOY WEAT BIAS PROBE (Phase 18, Lesson 20)
======================================================================

pre-debias WEAT effect size : +0.8906
(positive means identity A associates more with X than B does.)
post-debias WEAT effect size: +0.2212

======================================================================
TAKEAWAY: embedding-based bias is measurable and partially reducible
by projecting out gender-correlated directions. the metric does not
drop to zero because the toy is 4-d; real debiasing (Bolukbasi 2016)
operates on 300-d embeddings and reduces but does not eliminate
the effect. probability- and generated-text-based metrics are
required to capture the behavioural bias residual.
======================================================================
```

逐项解读（讲义练习 1）：

- **+0.8906**：男性词的 s 均值为 +0.4314，女性词为 −0.4592，差值为 0.8906。手算过程见测验 Q9。不对称来自 `man`（带 0.1 care）与 `woman`（带 0.1 tech）的细节差异。
- **+0.2212**：投影后属性词在性别方向上中立，剩余的关联完全来自身份词的 tech/care 分量。
- **为什么不归零**（附加实验，已实际运行）：

| 方案 | 均值差 | 标准化 effect size |
|------|-------|-------------------|
| 去偏前 | 0.8906 | 1.811 |
| 原代码去偏（只投影属性词） | 0.2212 | 1.603 |
| 对所有词投影 | 0.3080 | 1.604 |
| 原代码去偏 + 身份词 tech/care 清零 | 0.0000 | 无定义（所有 s = 0） |

结论：残留与"4 维"无关，完全由"身份词携带职业维度"造成；而且以标准化 effect size 衡量，去偏前后两组的分离程度几乎不变。

- **统计显著性**：两种情况下置换检验的 p 值都是 1/20 = 0.05，这是"每组 3 个词"时能达到的最小值。

---

## 7. 动手改一改

1. **去掉全局状态**：把 `weat_score` 改为 `weat_score(emb, A, B, X, Y)`，`main()` 中显式传入 `EMB` 和 `debias(EMB)`，确认结果不变，并且连续调用 `main()` 两次也不会出错。
2. **标准化与显著性**：实现 Caliskan 的 effect size 与置换检验（测验 Q10），确认 1.811 → 1.603 和 p = 0.05。再给每组加到 5 个词（自行构造向量），观察 p 值下限变为 `1/C(10,5) = 1/252`。
3. **找到残留偏见**：依次尝试测验 Q11 的三种去偏方案，然后写一个函数，把残留的 WEAT 按维度分解（只保留某一维时 WEAT 还剩多少），自动定位偏见所在的轴。
4. **估计而非指定性别方向**：用 he−she、his−her、man−woman 三个差向量的平均（或 PCA 第一主成分）作为 g，看它与手工的 `[1,−1,0,0]` 有多接近，以及去偏效果有何不同。
5. **交叉性扩展**（讲义练习 2）：扩展到 6 维（加两个种族轴），构造 4 个交叉组，计算交互项 `s(f,r2) − s(f,r1) − s(m,r2) + s(m,r1)`（参考测验 Q12，示例结果为 −0.119）。
6. **进阶：从 embedding 到行为**：用一个小型开源模型（如通过 transformers 加载），对 "The engineer said that [he/she] ..." 这类模板计算两个代词的对数似然差，实现一个 probability-based 指标，比较它与 WEAT 的结论是否一致。

---

## 8. 常见坑

- **把均值差当成 effect size**：不标准化会夸大去偏效果；报告时要写清楚是哪一种。
- **只看指标下降就宣称"已去偏"**：本例中均值差降了 75%，组间分离却几乎没变。`skill-bias-eval.md` 的 Hard rejects："Any 'debiased' claim based on a single metric category."
- **以为偏见只在一个方向上**：投影一个方向，偏见会转移或残留在其他方向（本例中的 tech/care 轴）。
- **小样本 WEAT 的显著性**：每组 3 个词时 p 值不可能低于 0.05，不要过度解读。
- **混淆 debias 函数里的方向注释**：docstring 写 "axis 1 minus axis 0"，代码是 axis 0 − axis 1；对投影结果没有影响，但读代码时容易困惑。
- **把 embedding 结论推到 LLM 行为**：讲义明确说 embedding-based 指标 "measures the representation, not the behaviour"。
- **轻信讲义对外部论文的概括**：例如讲义说 UniBias 是"attention-head manipulation"并针对身份类偏见，但其 arXiv 摘要描述的是同时识别并消除有偏的 **FFN 向量和 attention head**，针对的是 in-context learning 中的标签偏置与提示脆弱性，而不是社会群体偏见。
