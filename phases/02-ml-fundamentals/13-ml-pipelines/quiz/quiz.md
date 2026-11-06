# 测验 · 机器学习管道（ML Pipelines）

> **阶段 02 · 机器学习基础 · 第 13 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/pipeline.py](../code/pipeline.py) ｜ 代码讲解：[code/pipeline.讲解.md](../code/pipeline.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Pipeline = 有序变换 + 模型 | 把填补、缩放、编码、模型串成一个对象，在训练数据上整体 `fit` 一次，推理时原样复用 |
| 2 | `fit` / `transform` / `fit_transform` | `fit` 从数据里学统计量（均值、中位数、类别表）；`transform` 只用已学到的统计量；训练集 `fit_transform`，测试集只 `transform` |
| 3 | 数据泄漏（data leakage） | 训练过程用到了预测时拿不到的信息（测试集统计量、未来数据、标签衍生特征），导致离线分数虚高 |
| 4 | 交叉验证要包住整个 pipeline | 每一折都在该折训练部分重新 fit 预处理器和模型，验证部分只 transform，才能得到无偏估计 |
| 5 | ColumnTransformer | 不同列走不同预处理：数值列"中位数填补 + 标准化"，类别列"众数填补 + 独热编码"，最后横向拼接 |
| 6 | `handle_unknown="ignore"` | 线上出现训练时没见过的类别时输出全零向量而不是崩溃 |
| 7 | 训练/服务偏差（training/serving skew） | 训练与推理的特征处理不一致；根治办法是训练和服务共用同一个序列化的 pipeline 对象 |
| 8 | 实验追踪与模型注册 | MLflow / wandb 记录每次运行的参数、指标、制品；Model Registry 管理模型版本、上线审批与回滚 |
| 9 | 数据版本化（DVC） | git 里只存记录数据哈希的 `.dvc` 小文件，真实数据放 S3/GCS 等远端，每个 commit 同时钉住代码和数据 |
| 10 | 可复现四要素 | 固定随机种子、锁定依赖版本、数据版本化、超参数写进配置文件 |

### 核心技能（能动手做到）

- [ ] 不用 sklearn，从零实现 `MedianImputer`、`StandardScaler`、`OneHotEncoder`，每个都有 `fit` / `transform` / `fit_transform`，并能说出每个类在 `fit` 时"记住"了什么状态
- [ ] 实现 `PipelineFromScratch`：`fit` 时前 n-1 步依次 `fit_transform`、最后一步 `fit`；`predict` 时前 n-1 步只 `transform`
- [ ] 手写 K 折交叉验证，传入 **pipeline 工厂函数**，保证每折都新建 pipeline 且只在训练折上 fit
- [ ] 故意写出"先在全量数据上 fit scaler 再切分"的泄漏版本，与干净版本对比测试分数
- [ ] 用 sklearn 搭出 `ColumnTransformer + Pipeline + cross_val_score` 完整流程，并说清 fit / predict 时每一步调用了什么方法
- [ ] 用 `joblib.dump` / `joblib.load` 序列化整个 pipeline，在另一个进程中加载并验证预测完全一致
- [ ] 为一次实验写出可复现清单：`set_seed`、锁版本的依赖文件、DVC 数据版本、配置文件

---

## 二、基础自测（选择题）

**Q1.** 下列哪种做法**不会**造成数据泄漏？

- A. 在全量数据上做 StandardScaler，然后再划分 train/test
- B. 在全量数据上用卡方检验挑出 top-20 特征，再对这 20 个特征做 5 折交叉验证
- C. 把 StandardScaler 和模型放进同一个 Pipeline，再对整个 Pipeline 调用 `cross_val_score`
- D. 把时间序列数据随机打乱后再划分训练集和测试集

**Q2.** 对 `pipe = Pipeline([("scaler", StandardScaler()), ("model", LogisticRegression())])` 调用 `pipe.predict(X_test)` 时，scaler 上实际调用的是：

- A. `fit_transform(X_test)`
- B. `transform(X_test)`
- C. 先 `fit(X_test)` 再 `transform(X_test)`
- D. 不经过 scaler，直接把 `X_test` 交给模型

**Q3.** 本节代码里的 `OneHotEncoder` 在训练时见过 `["new_york", "chicago", "la", "houston"]`，推理时遇到 `"seattle"`，编码结果是：

- A. 抛出 `KeyError`
- B. `[0, 0, 0, 0]`
- C. `[0.25, 0.25, 0.25, 0.25]`
- D. 自动新增第 5 列并置为 1

**Q4.** 关于在交叉验证中使用 pipeline，正确的是：

- A. 预处理器在全量数据上 fit 一次、各折复用，既省时间又不影响评估
- B. 每一折都在该折的训练部分上重新 fit 预处理器和模型，验证部分只做 transform
- C. 只有模型需要每折重训，预处理器只是"整理数据"，放在哪里都一样
- D. 交叉验证本身就能防止泄漏，所以预处理放在 CV 外面也可以

**Q5.** DVC 实现数据版本化的方式是：

- A. 把大文件直接提交进 git 仓库
- B. git 里保存记录数据哈希的 `.dvc` 小文件，真实数据存放在 S3/GCS/Azure 等远端存储
- C. 每次训练前自动下载最新数据，不保留历史版本
- D. 把数据压缩后嵌入模型文件一起发布

**Q6.** 线上模型效果明显差于离线评估。排查发现：训练代码和服务代码各自实现了一遍特征处理，几个月后两份代码已经不一致。这类问题叫什么？最根本的修复是？

- A. 过拟合；加大正则化
- B. 概念漂移；提高重训频率
- C. 训练/服务偏差；训练与推理共用同一个序列化的 pipeline 对象
- D. 类别不平衡；对少数类重采样

**Q7.** 本节 `FullPipeline` 的数值列是 `age / income / score`，类别列是 `city`（训练集中有 5 个取值）和 `plan`（3 个取值）。预处理后送入模型的特征矩阵有多少列？

- A. 5
- B. 8
- C. 11
- D. 13

---

## 三、动手 / 代码题

**Q8.** 使用本节代码中的 `OneHotEncoder`，写出下面三行 `print` 的输出，并解释为什么 `"new_york"` 的 1 出现在最后一位。

```python
train_cats = np.array([["new_york"], ["chicago"], ["la"], ["houston"]])
encoder = OneHotEncoder(handle_unknown="ignore")
encoder.fit(train_cats)
print(encoder.transform(train_cats)[0])
print(encoder.transform(np.array([["seattle"]]))[0])
print(encoder.transform(np.array([["la"], ["la"]])).shape)
```

**Q9.**（找 bug）有同学觉得 `PipelineFromScratch.predict` 里调用 `transform` 太麻烦，改成了下面这样：

```python
    def predict(self, X):
        X_current = X.copy() if isinstance(X, np.ndarray) else X
        for name, step in self.steps[:-1]:
            X_current = step.fit_transform(X_current)   # 原来是 step.transform
        name, model = self.steps[-1]
        return model.predict(X_current)
```

用 `demo_pipeline_from_scratch` 的数据（`StandardScaler` + `LogisticRegressionSimple`）测试：①一次性对 60 条测试样本 `predict`；②在线服务场景下每次只对 1 条样本 `predict`。两种情况分别会发生什么？为什么第 ① 种情况可能"看起来没问题"？

**Q10.**（解释写法）`demo_model_comparison` 里有这样一段：

```python
    for name, model_fn in models:
        def make_pipe(m=model_fn):
            return FullPipeline(
                model=m(),
                numeric_cols=["age", "income", "score"],
                categorical_cols=["city", "plan"],
            )

        scores = cross_validate_pipeline(make_pipe, data, n_folds=5)
```

(a) 为什么 `cross_validate_pipeline` 接收的是"工厂函数" `make_pipe`，而不是一个已经建好的 pipeline 对象？
(b) 如果把 `def make_pipe(m=model_fn):` 改成 `def make_pipe():` 并在函数体里直接用 `model_fn()`，在**这段代码里**结果会变吗？如果先把 4 个 `make_pipe` 收集到列表里、循环结束后再逐个调用呢？

**Q11.**（补全）本节 `OneHotEncoder` 的构造函数接收了 `handle_unknown` 参数，但 `transform` 从未使用它（总是"忽略"）。请写一个子类 `StrictOneHotEncoder`，在 `handle_unknown="error"` 时遇到未知类别抛出 `ValueError`（错误信息里要指出是哪一列、哪些值），`"ignore"` 时保持原行为。

---

## 四、面试高频题

**Q12.**（基础必考）什么是数据泄漏？请至少列举 4 种常见形式，并说明怎么发现、怎么预防。

**Q13.**（原理深挖）为什么交叉验证必须包住整个 pipeline，而不是只包住模型？如果还要做超参数搜索，评估流程应该怎么设计？

**Q14.**（工程实践）什么是 training/serving skew？在生产系统中有哪些系统性的手段避免它？

**Q15.**（场景设计）同事交给你一个能跑出好结果的 Jupyter notebook，要求把它变成"可复现、可上线、可回滚"的训练流水线。你会按什么步骤改造？每一步解决什么问题？

**Q16.**（追问型）你用 `joblib.dump` 把 sklearn pipeline 存成文件交给服务端加载。这样做有哪些坑？怎么规避？

---

## 五、参考答案与解析

### Q1 — 答案：C

Pipeline + `cross_val_score` 时，每一折只在训练部分上 fit scaler，验证部分用训练折的均值和标准差做 transform，不会看到验证数据。
- A：scaler 的均值和标准差包含了测试样本，是讲义里的"Leaky (wrong)"例子。
- B：特征选择同样是"从数据中学东西"，在全量数据上选特征时已经用到了验证折的标签信息，是比缩放更严重的泄漏（尤其当特征多、样本少时，可以从纯噪声里"选"出看似有用的特征）。
- D：时间序列打乱后，训练集里有"未来"的样本，属于时间泄漏（第 15 节会专门讲）。

### Q2 — 答案：B

`pipe.fit` 时 scaler 调 `fit_transform(X_train)`，模型调 `fit`；`pipe.predict` 时 scaler 只调 `transform(X_test)`，用的是训练集上学到的统计量，然后模型调 `predict`。这正是"scaler never sees test data during fitting"。C 会用测试数据重新估计统计量，相当于泄漏 + 训练/推理不一致。

### Q3 — 答案：B

`transform` 的实现是对每个**训练时见过的**类别 `cat` 生成一列 `(X[:, col] == cat)`。`"seattle"` 不等于任何已知类别，所以 4 列全为 0。这和 sklearn 中 `OneHotEncoder(handle_unknown="ignore")` 的行为一致：输出零向量，不崩溃。A 是 sklearn 默认 `handle_unknown="error"` 时会发生的事（抛 `ValueError`）；D 不可能——列数在 fit 时就固定了，模型的输入维度不能在推理时改变。

### Q4 — 答案：B

见 `cross_validate_pipeline`：每折调用 `pipeline_factory()` 新建 pipeline，`pipe.fit(train_data)` 只用训练折，`pipe.score(val_data)` 只做 transform + predict。A/D 都是泄漏：验证折的数据参与了统计量估计。C 错在"预处理也会从数据中学参数"，中位数、均值、类别表都是学出来的。

### Q5 — 答案：B

`dvc add data/training.csv` 生成 `training.csv.dvc`（含哈希），把它和 `.gitignore` 提交到 git；`dvc push` 把真实数据推到远端。切换 git commit 后 `dvc checkout` 就能恢复当时用的数据，做到"每个 commit 同时钉住代码和数据"。

### Q6 — 答案：C

这正是讲义 "Common Pipeline Mistakes" 表最后一行：Training/serving skew → One Pipeline object for both。把所有特征处理放进 pipeline，训练后整体序列化，服务端加载同一个制品，就不存在"两份代码"。A/B/D 都可能导致线上效果变差，但与题目描述的根因无关。

### Q7 — 答案：C

数值列经过 `MedianImputer + StandardScaler` 后仍是 3 列；`city` 独热成 5 列，`plan` 独热成 3 列，`np.hstack` 后共 `3 + 5 + 3 = 11` 列。实际运行验证：训练集上学到的类别表为 `['chicago','houston','la','new_york','phoenix']` 和 `['basic','free','premium']`。

### Q8 — 参考答案

输出：
```
[0. 0. 0. 1.]
[0. 0. 0. 0.]
(2, 4)
```

- `fit` 里用 `sorted(set(X[:, col]))` 构建类别表，**按字母序**排列为 `['chicago', 'houston', 'la', 'new_york']`，与输入顺序无关，所以 `new_york` 在第 4 位。排序保证了"同样的类别集合，每次 fit 得到同样的列顺序"，这是可复现的前提——如果用 `set` 的迭代顺序，字符串哈希随机化可能让每次运行的列顺序都不同。
- `seattle` 不在类别表中，4 个比较全为 False，得到零向量。
- 输出形状 = (样本数, 类别数) = (2, 4)。列数只取决于 fit 时的类别表，不取决于推理数据。

### Q9 — 参考答案

这是把"训练时学到的统计量"换成了"推理数据自己的统计量"，本质是训练/推理不一致：

- **情况 ①（60 条一起预测）**：scaler 用测试集自己的均值和标准差做标准化。由于测试集与训练集来自同一分布（都是标准正态），两组统计量很接近，所以准确率可能和正确版本差不多——实际运行中甚至从 0.967 变成了 1.000。这就是它"看起来没问题"的原因：**分数没变差不代表做法正确**，结果取决于这一批数据的组成，换一批分布不同的数据就会出问题。
- **情况 ②（每次 1 条）**：单个样本的均值就是它自己，标准差为 0，代码里 `self.stds[self.stds == 0] = 1.0` 把它改成 1，于是每个样本都被变成全 0 向量。模型的输出只剩 `sigmoid(bias)`，所有样本得到同一个预测。实际运行中 bias ≈ -0.10，60 条样本全部预测为 0，准确率掉到 0.533（≈ 测试集中 0 的比例）。

修复：`predict` 中必须调用 `transform`。这也是为什么 sklearn 的 `Pipeline.predict` 只会调用中间步骤的 `transform`。

### Q10 — 参考答案

(a) 每一折都需要一个**全新的、未 fit 过的** pipeline。如果传入同一个对象，第 2 折 `fit` 会覆盖第 1 折学到的状态，虽然在本代码里碰巧不会出错，但一旦 pipeline 有"增量"行为（如某些模型的 warm start），就会把上一折的信息带到下一折。工厂函数让"每折新建"成为强制约定。sklearn 的 `cross_val_score` 则是用 `clone(estimator)` 达到同样目的。

(b) 在**这段代码里**结果不会变：`make_pipe` 在同一轮循环内就被 `cross_validate_pipeline` 调用完了，此时 `model_fn` 指向的正是当前这轮的模型构造函数。

但如果先收集再调用，就会踩到 Python 闭包的**延迟绑定（late binding）**：闭包记住的是变量 `model_fn` 本身而不是它当时的值，循环结束后 `model_fn` 指向最后一个元素，所以 4 个工厂会全部构造 `max_depth=10` 的树。验证：

```python
fns = []
for d in [3, 5, 10]:
    fns.append(lambda: DecisionTreeSimple(max_depth=d))
print([f().max_depth for f in fns])        # [10, 10, 10]

fns = []
for d in [3, 5, 10]:
    fns.append(lambda d=d: DecisionTreeSimple(max_depth=d))
print([f().max_depth for f in fns])        # [3, 5, 10]
```

默认参数在**函数定义时**求值，所以 `m=model_fn` 把当时的值"冻结"进了函数。`demo_experiment_tracking` 里的 `lambda c=config:` 是同一个技巧。

### Q11 — 参考答案

```python
class StrictOneHotEncoder(OneHotEncoder):
    def transform(self, X):
        if self.handle_unknown not in ("ignore", "error"):
            raise ValueError(
                f"handle_unknown must be 'ignore' or 'error', got {self.handle_unknown!r}"
            )
        if self.handle_unknown == "error":
            for col in range(X.shape[1]):
                unknown = set(X[:, col]) - set(self.categories[col])
                if unknown:
                    raise ValueError(
                        f"column {col}: unknown categories {sorted(map(str, unknown))}"
                    )
        return super().transform(X)


enc = StrictOneHotEncoder(handle_unknown="error").fit(np.array([["a"], ["b"]]))
print(enc.transform(np.array([["b"], ["a"]])))   # [[0. 1.] [1. 0.]]
enc.transform(np.array([["c"]]))                 # ValueError: column 0: unknown categories ['c']
```

要点：
- 复用父类的 `fit` 与编码逻辑，只在前面加一道检查（开闭原则）。
- 用集合差 `set(...) - set(...)` 一次找出所有未知值，错误信息里带列号和取值，线上排查时一眼能定位。
- `sorted(map(str, ...))` 让错误信息稳定可读（NumPy 2.x 的字符串元素直接打印会显示成 `np.str_('c')`）。
- 两种模式的取舍：`error` 适合离线训练 / 数据校验阶段尽早暴露问题；`ignore` 适合线上服务保证可用性，但应同时**记录日志/监控未知类别比例**，否则新类别悄悄变多时你不会察觉。

### Q12 — 参考回答要点

- **定义**：模型在训练或评估过程中使用了**预测时刻拿不到的信息**，使离线指标虚高，上线后崩塌。
- **常见形式**：
  1. 预处理泄漏：scaler / imputer / encoder 在全量数据上 fit 后再切分；
  2. 特征选择泄漏：用全量数据（含验证集标签）选特征；
  3. 目标泄漏（target leakage）：特征由标签派生，或是事件发生之后才产生的信息，例如用"是否已办理退款"预测"是否流失"；
  4. 时间泄漏：时间序列随机切分、用未来窗口算特征；
  5. 分组泄漏：同一用户/同一病人的样本同时出现在训练和测试中（应使用按组切分）；
  6. target encoding 不做 out-of-fold、在切分前做过采样（SMOTE）等。
- **怎么发现**：分数好得不真实；某个特征重要性异常高；交叉验证分数远高于时间外 holdout 或线上表现；逐个审查特征"在预测时刻是否可得"。
- **怎么预防**：先切分再做一切；所有"从数据学参数"的步骤放进 pipeline 并让 CV 包住整个 pipeline；时间数据用按时间切分；分组数据用按组切分。
- **加分点**：能区分"预处理泄漏通常影响较小、目标泄漏往往是灾难性的"，并能举出自己项目里的真实例子。

### Q13 — 参考回答要点

- **原理**：交叉验证要模拟"模型从没见过验证数据"。预处理器也是在学参数（均值、中位数、类别表、被选中的特征），如果它在 CV 外用全量数据 fit，验证折的信息就已经进入了训练。把整个 pipeline 交给 CV，每折 `clone` 一份并只在训练折上 fit，才能得到无偏估计。本节 `cross_validate_pipeline` + 工厂函数正是在模拟这一点。
- **加入超参数搜索后**：如果用同一套 CV 既选超参又报告分数，报告的分数是在"被选中的那组"上的最大值，同样偏乐观。正确做法是**嵌套交叉验证**：内层 CV（如 `GridSearchCV(pipe, ...)`）选超参，外层 CV（`cross_val_score(grid_search, X, y)`）评估"整个选参流程"的泛化性能；或者留出一份从未参与选参的最终测试集。
- **sklearn 细节**：搜索 pipeline 中某一步的参数用双下划线命名，如 `model__max_depth`、`preprocess__num__impute__strategy`，预处理的选项也可以一起搜。
- **常见误区**：以为"我用了 CV 就不会泄漏"——CV 只是评估框架，泄不泄漏取决于 fit 发生在哪里。

### Q14 — 参考回答要点

- **定义**：同一个样本在训练时和在线上推理时被处理成了不同的特征，模型看到的输入分布不同，表现悄悄变差，通常不报错。
- **常见成因**：训练（Python/批处理）和服务（Java/实时）各写一套特征代码；统计量（均值、词表）没有随模型保存；服务端缺失值处理与训练不同；某些特征训练时可得、线上实时不可得或有延迟；依赖库版本不同导致行为变化。
- **系统性手段**：
  1. 单一制品：所有特征变换放进 pipeline，训练后整体序列化，服务端加载同一个对象；
  2. 共享特征定义：用 feature store 或共享特征库，离线和在线读同一份定义；
  3. 在线记录特征：把服务时实际算出的特征落日志，用于下一次训练（"log and train"）并与离线特征做比对；
  4. 数据校验：上线前和运行时检查 schema、取值范围、缺失率、未知类别比例；
  5. 监控：对比线上特征分布与训练分布（如 PSI、KS 检验），出现漂移时告警；
  6. 锁定依赖版本，训练与服务使用同一镜像。
- **加分点**：能区分 skew（处理逻辑不一致）和 drift（数据本身随时间变化），两者的应对手段不同。

### Q15 — 参考回答要点

对照讲义 "From Notebook to Production Pipeline" 的 8 步：
1. **提取函数**：把加载、预处理、特征工程、评估从 notebook 单元格抽成模块里的函数，去掉隐式的全局状态（notebook 单元格执行顺序本身就是不可复现的来源）。
2. **构建 Pipeline**：所有"从数据学参数"的变换放进 Pipeline / ColumnTransformer，解决泄漏和训练/服务偏差。
3. **配置文件**：超参数、列名列表、数据路径写进 YAML/JSON，代码里不硬编码。
4. **实验追踪**：接入 MLflow 或 wandb，记录参数、指标、代码版本（git commit）、数据版本、模型制品。
5. **数据校验**：训练前检查 schema、分布、缺失模式，坏数据早失败。
6. **测试**：transformer 的单元测试（如"fit 后 transform 训练集均值≈0"）、整条 pipeline 的集成测试、"加载后预测一致"的回归测试。
7. **可复现**：固定随机种子、锁定依赖、DVC 版本化数据。
8. **部署**：序列化整个 pipeline，包成 API（FastAPI/Flask）、容器化；通过 Model Registry 管理版本，需要审批才能上线，出问题能立即切回旧版本。
- **加分点**：提到上线后还需要监控（数据漂移、指标下降）和定期重训；提到 Sculley 等人的论文 *Hidden Technical Debt in Machine Learning Systems*——模型代码只是整个系统中很小的一部分。

### Q16 — 参考回答要点

- **安全**：pickle（joblib 底层也是 pickle）反序列化时可以执行任意代码，**绝不能加载来源不可信的模型文件**。可以考虑更安全的格式（如 sklearn 文档推荐的 skops，或转换成 ONNX）。
- **版本兼容**：sklearn 不保证跨版本反序列化兼容，不同版本加载可能报警告、报错，甚至静默得到不同结果。训练和服务要锁定同样的 Python、sklearn、NumPy 版本（最好同一个容器镜像）。
- **自定义类**：pipeline 里有自定义 transformer 时，pickle 只存"模块路径 + 类名 + 属性"，服务端必须能 `import` 到同名同路径的类，否则加载失败；改了类的实现，旧模型的行为也会跟着变。
- **只存模型不存预处理**：只保存模型权重而不保存 scaler 等统计量，是训练/服务偏差的经典来源——要序列化**整个 pipeline**。
- **元数据**：模型文件旁边要记录训练数据版本、特征 schema（列名、顺序、类型）、依赖版本、评估指标，最好交给 Model Registry 统一管理。
- **验证**：加载后用一批固定样本做"预测一致性"回归测试（讲义练习 3）。

---

## 六、关联知识点

### 前置知识
- [阶段 02 · 12 Hyperparameter 调整](../../12-hyperparameter-tuning/docs/zh.md)：本节的前置课；调参和交叉验证需要放在 pipeline 之上。
- [阶段 02 · 08 Feature 工程与选择](../../08-feature-engineering/docs/zh.md)：缩放、编码、缺失值填补等变换本身。
- [阶段 02 · 09 模型 Evaluation](../../09-model-evaluation/docs/zh.md)：K 折交叉验证、train/test 划分。
- [阶段 02 · 03 逻辑回归](../../03-logistic-regression/docs/zh.md)、[阶段 02 · 04 决策树和随机森林](../../04-decision-trees/docs/zh.md)：本节代码里手写的两个模型。
- [阶段 00 · 09 数据管理](../../../00-setup-and-tooling/09-data-management/docs/zh.md)：DVC 等数据版本工具。

### 本节被哪些后续内容用到
- [阶段 02 · 15 时间序列基础知识](../../15-time-series/docs/zh.md)：时间泄漏与 walk-forward 验证，是"切分方式决定泄漏"的典型。
- [阶段 02 · 17 处理不平衡数据](../../17-imbalanced-data/docs/zh.md)：SMOTE 等重采样必须放在 pipeline 内部，只作用于训练折。
- [阶段 02 · 18 Feature 选择](../../18-feature-selection/docs/zh.md)：把特征选择放进 pipeline，避免特征选择泄漏。
- [阶段 10 · 03 预训练数据管道](../../../10-llms-from-scratch/03-data-pipelines/docs/zh.md)、[阶段 10 · 13 构建完整 LLM 管道](../../../10-llms-from-scratch/13-building-complete-llm-pipeline/docs/zh.md)：同样的"可复现流水线"思想放大到 LLM 训练。
- [阶段 17 · 20 影子流量与金丝雀发布](../../../17-infrastructure-and-production/20-shadow-canary-progressive/docs/zh.md)：模型注册、版本钉住与快速回滚在生产中的落地。
- [阶段 19 · 07 端到端微调流水线](../../../19-capstone-projects/07-end-to-end-fine-tuning-pipeline/docs/zh.md)：综合项目中的完整训练—评估—服务流水线。

### 延伸关键词
`sklearn.base.clone` · `嵌套交叉验证` · `GroupKFold / TimeSeriesSplit` · `target leakage` · `feature store` · `MLflow Model Registry（2.9 起 stage 被标记为弃用，改用 alias / tag）` · `DVC pipelines` · `skops / ONNX` · `数据漂移 (PSI)` · `Hidden Technical Debt in ML Systems`
