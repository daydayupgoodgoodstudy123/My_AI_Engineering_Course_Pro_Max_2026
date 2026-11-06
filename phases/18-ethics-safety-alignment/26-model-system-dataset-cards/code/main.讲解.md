# 代码讲解 · main.py

> **所属小节**：阶段 18 · 伦理、安全与对齐 · 第 26 节 模型卡、系统卡与数据集卡 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无参数） ｜ **依赖**：仅标准库（实际没有 import 任何模块），无需网络

---

## 1. 这份代码在考察什么

这是一个约 130 行的"卡片生成器"。它为一个虚构的玩具部署（ToyClassifier-1.0，二分类逻辑回归）输出三份 Markdown 文档：

1. **Model Card**（Mitchell 等 2019）——记录模型；
2. **Datasheet**（Gebru 等）——记录数据；
3. **System Card**（讲义引 Sidhpurwala 2024 / "Blueprints of Trust"）——记录整个部署。

学习目标是**看清三种文档的标准节结构和各自的范围**。但更有价值的是把它当作一份"待审计的卡片"：它恰好展示了真实世界模型卡的典型问题——缺节、占位内容、没有证据的数字、卡片之间互相矛盾。讲义练习 1 要求的就是找出这些弱点。

> 一句话：**文档的格式容易模仿，证据才是难点**。这份代码给出了格式；读完后你应该能指出它在证据层面缺了什么。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `model_card()` | 函数，返回多行字符串 | 8 节的模型卡 | Mitchell 2019（缺 Evaluation Data） |
| `datasheet()` | 函数，返回多行字符串 | 7 节的 datasheet | Gebru Datasheets for Datasets |
| `system_card()` | 函数，返回多行字符串 | 6 节的系统卡 | System Card 的端到端范围 |
| `main()` | 函数 | 依次打印三张卡与 TAKEAWAY | 三种范围对比 |

数据流：`main()` → 调用三个函数取得**固定字符串** → `print`。没有任何输入参数，也没有生成数据、训练或评测——"生成器"实际上是模板常量。

---

## 3. 逐段精讲

### 3.1 `model_card()`：模型的"营养标签"

```python
def model_card() -> str:
    return """
# Model Card: ToyClassifier-1.0

## Model Details
- Developer: ai-engineering-from-scratch / Phase 18 / Lesson 26
- Version: 1.0.0
- Type: binary logistic classifier (toy)
...
## Quantitative Analysis
- accuracy: 0.97 overall
- demographic parity gap: +0.03 (group0 vs group1)
- equalized odds TPR gap: -0.01

## Ethical Considerations
- Toy classifier; not validated for real-world use.
- Bias metrics are placeholder; ship a full audit before any deployment.
...
"""
```

与 Mitchell 2019 的 9 个标准节对照：

| 标准节 | 代码中 | 评价 |
|---|---|---|
| Model Details | 有 | 开发者、版本、类型、许可证、联系方式齐全 |
| Intended Use | 有 | 明确"Out-of-scope: any production decision"，写得好 |
| Factors | 有 | 列出 gender（二元）与 age bucket——但 datasheet 中没有年龄（见 3.4） |
| Metrics | 有 | accuracy、demographic parity、equalized odds |
| **Evaluation Data** | **缺失** | 读者无法知道 0.97 等数字是在哪个数据上测的 |
| Training Data | 有 | 只有一句"见 datasheet"——这种"链接上游"的写法是对的 |
| Quantitative Analyses | 有（单数 "Analysis"） | 只有点估计，无样本量、无置信区间；只有差值，没有各组的原始值 |
| Ethical Considerations | 有 | 自己承认"placeholder" |
| Caveats and Recommendations | 有 | 指向第 22 节差分隐私 |

- ⚠️ **数字没有来源**：代码中不存在任何数据生成、训练或评测。我们按 datasheet 的描述真的生成数据并训练逻辑回归（测验 Q10），测试集准确率是 **1.000**（标签是线性规则，可完美拟合），TPR 差与 FPR 差都是 0，demographic parity 差为 −0.044——而每组约 250 个样本时它的 95% 置信区间半宽约 ±0.088，与 0 无法区分。卡片上的 0.97 / +0.03 / −0.01 是手写占位值。
- ⚠️ **"equalized odds TPR gap"** 的写法不严谨：equalized odds 要求 TPR 和 FPR 都相等；只报 TPR 差，检验的是 equal opportunity（第 21 节）。
- 正负号约定（"+0.03 (group0 vs group1)"）需要写清楚是 `group0 − group1` 还是反过来。
- `"""..."""` 三引号字符串以换行开头，所以打印时每张卡前面会多一个空行；Markdown 内容会**原样保留缩进**——这里的内容都顶格写，正好避免了 Markdown 把缩进内容渲染成代码块。

### 3.2 `datasheet()`：数据的"元件手册"

```python
def datasheet() -> str:
    return """
# Datasheet: ToyBinaryClassification-1.0

## Motivation
- Created for pedagogical demonstration in Phase 18, Lesson 26
- Funded by no one; not for production use

## Composition
- 1,500 synthetic examples
- Features: 2-d continuous, 1 binary sensitive attribute
- Labels: binary, derived from x[0] + x[1] > 0 rule
...
## Maintenance
- Static; regenerated on every run from fixed seed
"""
```

- 7 节与讲义列出的 Gebru 结构一一对应：Motivation、Composition、Collection Process、Labeling、Uses、Distribution、Maintenance（原论文中 Labeling 一节的全称是 Preprocessing/cleaning/labeling）。
- **写得好的地方**：Composition 给出了样本数、特征维度、标签规则；Collection Process 说明"No human subjects involved"；Uses 同时写了预期用途和禁止用途。
- ⚠️ **声明与代码不符**：Collection Process 说"Synthetically generated via Python random.gauss with fixed seed"，Maintenance 说"regenerated on every run from fixed seed"——但 `main.py` 里根本没有生成数据的代码，也没有 `import random`。这就是 skill 文件所说的"self-report"：没有任何东西能验证这些说法。
- ⚠️ "Labels programmatically derived; no annotation error"：对程序化标签成立，但应同时说明"标签规则与真实任务的距离"——合成数据上的公平性结论不能迁移到真实人群。
- 这张 datasheet 是模型卡的**上游**：讲义"the model card depends on the datasheet being accurate"。

### 3.3 `system_card()`：部署层文档

```python
def system_card() -> str:
    return """
# System Card: ToyClassifier Service

## Deployment
- Scope: localhost pedagogical service
- Stack: ToyClassifier-1.0 behind a single-threaded HTTP server

## Security Capabilities
- Prompt-injection: N/A (non-generative)
- Data-exfiltration detection: basic egress rate limit
- Rate limiting: 100 req/min per client
...
## Regulatory Alignment
- EU AI Act: N/A (toy; no EU deployment)
- GPAI Code of Practice: N/A (non-GPAI)
- Transparency Code: N/A (no AI-generated content output)
"""
```

- 覆盖了讲义列出的 System Card 节：Security capabilities（含 prompt injection 与外泄检测）、Alignment、Incident Response，并额外加了 Deployment 与 Regulatory Alignment（后者对应第 24 节）。
- "Prompt-injection: N/A (non-generative)"：对分类器是合理的，**N/A 加上理由**是好的写法——比留空强得多。
- ⚠️ "Data-exfiltration detection: basic egress rate limit"：速率限制只能减缓批量外传，不能**检测**外泄；应写明检测规则、测试方法与结果。
- ⚠️ "Incident Response: escalation goes nowhere"：坦诚，但在真实系统卡中等于没有事故响应。
- Regulatory Alignment 三行都是 N/A 且给出了理由，这正是第 24 节"逐法域映射"的最小形式。
- 缺少 skill 文件要求的 **sustainability**（碳、水、能耗）和 **verifiable attestation**——三张卡都没有。

### 3.4 三张卡之间的一致性

| 检查项 | 模型卡 | Datasheet | 系统卡 | 一致？ |
|---|---|---|---|---|
| 敏感属性 | gender（二元）、age bucket | 1 个二元敏感属性 | — | **否**：数据里没有年龄 |
| 样本 / 数据 | "见 Datasheet" | 1,500 条合成样本 | — | 是（但模型卡缺评测集说明） |
| 模型 | ToyClassifier-1.0，逻辑回归 | — | ToyClassifier-1.0 | 是 |
| 用途 | 仅教学 | 仅教学 | localhost 教学服务 | 是 |

skill 文件第 3 节"Datasheet alignment"要做的就是这种交叉核对。

### 3.5 `main()` 与 TAKEAWAY

```python
def main() -> None:
    print("=" * 74)
    print("CARDS GENERATOR (Phase 18, Lesson 26)")
    print("=" * 74)
    print(model_card())
    print(datasheet())
    print(system_card())
    ...
```

- 三个函数都返回字符串、由 `main` 统一打印——"生成"与"输出"分离，便于以后把字符串写入文件（`Path("MODEL_CARD.md").write_text(model_card())`）或交给审计函数（测验 Q9）。
- TAKEAWAY："in 2026, EU AI Act GPAI Code of Practice requires model cards as compliance artifacts. verifiable attestations (Laminator 2024) are the next phase." 与讲义"Regulatory cards"一节一致。
- 小出入：模块 docstring 写"System Card (Sidhpurwala 2024 / 'Blueprints of Trust' 2025)"，讲义正文把 Sidhpurwala 2024 与 "Blueprints of Trust" 当作两项工作，而讲义 Further Reading 又把 "Blueprints of Trust" 署名为 Sidhpurwala 等——出处表述前后不一。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 卡片是硬编码的 Markdown 字符串 | 一眼看清标准节结构 | 数字与真实模型脱节；生产中卡片应由评测流水线的结果**渲染**生成（docs-as-code） |
| 不生成数据、不训练模型 | 聚焦文档格式 | 卡片中的数字、datasheet 中"每次运行重新生成"的说法都无法验证 |
| 模型卡只有 8 节 | 代码简洁 | 缺 Evaluation Data，Quantitative Analysis 无法溯源 |
| 只报差值、不报各组值与样本量 | 简化 | 无法判断差值是否显著；应报各组 n、点估计与置信区间 |
| N/A 附理由 | 对不适用的节保持诚实 | 好做法，值得保留 |
| 无可持续性、无签名证明 | 超出玩具范围 | skill 要求两项都检查；生产中至少应报告训练能耗与关键评测的可验证证明 |
| 三张卡分开生成 | 对应三种范围 | 需要额外的交叉一致性检查（3.4） |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 模块 docstring | 文件开头三引号字符串 | 描述三种卡片及其出处 |
| `from __future__ import annotations` | 文件开头 | 延迟求值类型注解（本文件只有 `-> str` / `-> None`，可省略） |
| 返回类型注解 | `def model_card() -> str:` | 表明函数返回字符串 |
| 三引号多行字符串 | `return """\n# Model Card: ...\n"""` | 保留换行与缩进；开头紧跟换行会让字符串以 `\n` 开头 |
| 字符串内的 Markdown | `## Model Details`、`- Version: 1.0.0` | 字符串本身就是 Markdown 源文本 |
| 字符串乘法 | `"=" * 74` | 生成分隔线 |
| 函数组合 | `print(model_card())` | 先调用函数得到字符串，再打印 |
| 主入口 | `if __name__ == "__main__": main()` | 被 import 时不执行，便于在测验 Q9 中 `import main` 后复用三个函数 |
| （扩展）`re.match(r"^## (.+)$", line)` | 测验 Q9 的 `sections()` | 正则匹配二级标题并捕获节名 |
| （扩展）`textwrap.dedent` | 改造练习 | 当三引号字符串写在缩进的代码块里时，用它去掉公共缩进 |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，瞬间完成）输出三张 Markdown 卡片，节选：

```text
==========================================================================
CARDS GENERATOR (Phase 18, Lesson 26)
==========================================================================

# Model Card: ToyClassifier-1.0
...
## Quantitative Analysis
- accuracy: 0.97 overall                          ← 无评测集说明；按 datasheet 复现应为 ~1.0
- demographic parity gap: +0.03 (group0 vs group1) ← 每组 ~250 样本时 ±0.09 的区间，不显著
- equalized odds TPR gap: -0.01                   ← 缺 FPR 差

## Ethical Considerations
- Toy classifier; not validated for real-world use.
- Bias metrics are placeholder; ship a full audit before any deployment.
...
# Datasheet: ToyBinaryClassification-1.0
...
## Composition
- 1,500 synthetic examples
- Features: 2-d continuous, 1 binary sensitive attribute   ← 与模型卡的 age bucket 矛盾
...
# System Card: ToyClassifier Service
...
## Security Capabilities
- Prompt-injection: N/A (non-generative)
- Data-exfiltration detection: basic egress rate limit     ← 速率限制 ≠ 外泄检测
...
TAKEAWAY: three canonical cards cover three scopes. ...
```

用测验 Q9 的审计脚本对输出做自动检查，实际结果：

| 卡片 | 缺失节 | 关键字判"弱"的节 |
|---|---|---|
| Model Card | Evaluation Data | Ethical Considerations |
| Datasheet | — | Motivation（"Funded by no one"，其实是合理陈述，属假阳性） |
| System Card | — | Security Capabilities、Incident Response、Regulatory Alignment |

注意自动审计**没有**把 Quantitative Analysis 标为弱——没有证据的数字最难被关键字规则发现，这正是人工审计和可验证证明的价值所在。

---

## 7. 动手改一改

1. **（讲义练习 1）** 给每张卡逐节标注"有证据 / 只有声明 / 占位"，并为每个弱项写一句"需要什么证据"（参考测验 Q12）。
2. **补齐 Evaluation Data**：在模型卡中加入该节，写明评测集大小、划分方式、与训练集是否同分布。
3. **（讲义练习 2）让数字有来源**：新增 `make_dataset(seed)` 与 `train_and_eval()`，按 datasheet 生成 1,500 条数据并训练逻辑回归；把各组的 n、准确率、选择率、TPR、FPR 和置信区间用 f-string 填进 Quantitative Analysis，替换手写的 0.97 / +0.03 / −0.01。
4. **一致性检查**：写一个函数比较模型卡 Factors 与 datasheet Composition 中的敏感属性，不一致时报错；修正 age bucket 的矛盾。
5. **（讲义练习 4）可验证字段**：在模型卡中加入 `## Attestations` 节，内容是测验 Q11 生成的 `{"claim": ..., "sig": ...}`；再写一个 `verify_card()` 读回并校验。
6. **（讲义练习 5）** 把 `system_card()` 改造成一个真实 LLM 应用（例如第 25 节的企业 Copilot）的系统卡，补上 sustainability 字段，并在 Security Capabilities 中写出 retrieval / scope / output 三边界的控制与测试结果。

---

## 8. 常见坑

- **有格式没证据**：节都在、数字都写了，却说不出数字从哪个数据集、哪段代码来——这是最常见也最危险的问题。
- **只报差值、不报样本量**：小样本下 ±0.09 的区间足以让"+0.03"毫无意义。
- **把 equal opportunity 当成 equalized odds**：后者要求 TPR 与 FPR 都相等。
- **卡片之间互相矛盾**：模型卡的 Factors 与 datasheet 的 Composition 必须对齐。
- **留空不如写 N/A + 理由**：本节系统卡的 "N/A (non-generative)" 是好示范。
- **把速率限制当外泄检测**：控制措施的名字要和它实际能做的事一致。
- **自动生成后不复核**：skill 文件只接受"CardGen 类系统 + 人工复核"；LLM 可能编造从未评测过的数字。
