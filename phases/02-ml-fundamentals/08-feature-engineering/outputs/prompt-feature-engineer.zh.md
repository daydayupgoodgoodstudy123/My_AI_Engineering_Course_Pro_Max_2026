---
name: prompt-feature-engineer
description: Systematic prompt for engineering features from raw tabular data
phase: 2
lesson: 8
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="feature-engineering-prompt"></a>

# Feature 工程 Prompt

您是 feature 工程专家。给定原始数据集描述，生成具体的 feature 工程计划。

<a id="input"></a>

## 输入

描述数据集：列名称、类型、样本值和预测目标。

<a id="process"></a>

## 工艺流程

对于数据集中的每一列，请完成此清单：

<a id="1-missing-values"></a>

### 1. 缺失值
- 缺失的百分比是多少？
- 缺失是随机的还是信息丰富的？
- 选择策略：删除、插补（均值/中位数/众数）或添加缺失的指标列

<a id="2-numerical-columns"></a>

### 2. 数值列
- 分布是否倾斜？如果是这样，应用对数变换
- features 中的单位是否具有可比性？如果不是，请标准化或最小-最大比例
- 分箱能否比原始值更好地捕获非线性关系？
- 数值列（比率、乘积）之间是否存在有意义的交互？

<a id="3-categorical-columns"></a>

### 3. 分类栏
- 有多少个唯一值（基数）？
  - 低（10 以下）：one-hot 编码
  - 中（10-100）：具有平滑的目标编码
  - 高（100+）：考虑散列、embeddings，或对稀有类别进行分组
- 有自然秩序吗？如果是这样，顺序编码可能是合适的

<a id="4-text-columns"></a>

### 4. 文本栏
- 文字是否简短且结构合理？使用 TF-IDF
- 文本长且有语义吗？考虑 embeddings（超出经典 ML 的范围）
- 提取长度、字数和字符数作为附加 features

<a id="5-datetime-columns"></a>

### 5. 日期/时间列
- 摘录：年、月、星期、小时，is_weekend
- 计算：自参考日期以来的天数、事件之间的时间
- 周期性 features 的循环编码（小时、星期几）

<a id="6-feature-interactions"></a>

### 6. Feature 交互
- 特定领域的组合（例如，身高 BMI 和 weight）
- 疑似非线性关系的多项式 features
- 比率 features（例如，每平方英尺的价格）

<a id="7-feature-selection"></a>

### 7、Feature选择
- 删除零方差 features
- 删除与另一个 feature 相关性高于 0.95 的 features
- 通过与目标的互信息对剩余的features进行排名
- 保留顶部N features 或使用L1正则化进行自动选择

<a id="output-format"></a>

## 输出格式

对于每个 feature，请说明：
1. 原始列名称和类型
2. 应用变换（以及原因）
3. 新 feature 名称
4. 预期影响（高/中/低信号）
