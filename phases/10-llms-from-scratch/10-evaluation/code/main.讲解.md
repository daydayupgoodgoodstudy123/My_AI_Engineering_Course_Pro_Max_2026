# 代码讲解 · main.py

> **所属小节**：阶段 10 · 从零构建 LLM · 第 10 节 Evaluation：基准、Evals 与 LM Harness ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：标准库 `hashlib`（`json`、`collections.Counter` 被导入但未使用）+ 第三方 `numpy`（无需模型、无需网络）

---

## 1. 这份代码在考察什么

这份代码从零搭了一个迷你版 eval harness，用三个"假模型"（查表函数）演示评测的完整链路：

1. **评测框架的最小抽象**：`EvalCase`（输入 + 期望输出）与 `EvalSuite`（用例 + 多个 scorer），`run(model_fn)` 对每条用例跑模型、跑所有打分函数。
2. **三种打分函数**：exact match、token F1、模拟的 LLM-as-judge，以及它们在同一批输出上给出的**相互矛盾**的结论。
3. **结果汇总**：mean / median / std / min / max / pass rate，体会"通过率比均值更能说明可靠性"。
4. **ELO 成对排名**：Chatbot Arena 式的相对评分。
5. **Perplexity**：由逐 token 的 log 概率计算 PPL（用模拟概率）。
6. **指标分歧分析**：同一个预测在 EM、F1、Judge 下的分数差异。

> 一句话：**评测的结论首先取决于"你怎么打分"。这份代码最有价值的地方，恰恰是它的打分函数本身就带着偏差——读懂这些偏差，比记住指标公式更重要。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `EvalCase` | 类 | 保存 `input_text`、`expected`、`metadata` | 测试用例 |
| `EvalSuite` | 类 | `run(model_fn)`：遍历用例 × scorer，返回结果列表 | eval harness |
| `exact_match` | 函数 | 去首尾空白、小写后全等 | Exact match |
| `token_f1` | 函数 | 按空格切词、用集合求交，算 P/R/F1 | Token F1 |
| `llm_judge_simulated` | 函数 | `0.7 × 召回 + 0.3 × 长度比` | LLM-as-judge（模拟） |
| `ELOTracker` | 类 | 期望胜率、更新分数、记录历史、排行 | ELO |
| `perplexity` | 函数 | `exp(−mean(log_probs))` | Perplexity |
| `token_log_probs_simulated` | 函数 | 按"模型质量"与词长生成模拟 log 概率 | 模拟 logits |
| `summarize_results` / `print_summary` | 函数 | 按指标聚合统计、打印 | 汇总 / pass rate |
| `demo_model_good / bad / random` | 函数 | 三个"模型"：精确查表、啰嗦改写、随机词 | 被测模型（模拟） |
| `run_eval_demo` 等 4 个 `run_*` | 函数 | 四个演示步骤 | 演示入口 |

数据流：`__main__` → STEP 1：8 条用例 × 3 个模型 × 3 个 scorer → 汇总打印；STEP 2：8 条用例 × 3 个配对 = 24 场，用 token F1 判胜负 → ELO 排行；STEP 3：3 段文本 × 3 种质量 → PPL；STEP 4：6 组 (预测, 参考) → EM/F1/Judge 对照表。

---

## 3. 逐段精讲

### 3.1 EvalCase 与 EvalSuite

```python
class EvalCase:
    def __init__(self, input_text, expected, metadata=None):
        self.input_text = input_text
        self.expected = expected
        self.metadata = metadata or {}

class EvalSuite:
    def run(self, model_fn):
        results = []
        for case in self.cases:
            prediction = model_fn(case.input_text)
            scores = {}
            for scorer_name, scorer_fn in self.scorers.items():
                scores[scorer_name] = scorer_fn(prediction, case.expected)
            results.append({...})
        return results
```

- `metadata=None` 再写 `metadata or {}`：这是避免"可变默认参数"陷阱的标准写法。如果直接写 `metadata={}`，所有实例会共享同一个字典。
- **模型只是一个函数** `model_fn(str) -> str`，scorer 是 `scorer_fn(prediction, expected) -> float`。这种"依赖注入"让同一个 suite 能评估任意模型、组合任意指标，lm-evaluation-harness、promptfoo 的核心抽象也是如此。
- scorer 放在字典里，结果按名字保存，后续汇总时可以按指标分组。
- 生产中还应记录：模型版本、prompt 版本、耗时、token 用量、原始输出，便于追踪和做 model diff（讲义练习 5）。

### 3.2 三个打分函数

```python
def exact_match(prediction, expected):
    return 1.0 if prediction.strip().lower() == expected.strip().lower() else 0.0
```

- 只做了去首尾空白和小写，因此 "paris" 与 "Paris" 判为一致（第 4 步表格中 Case mismatch 一行 EM = 1.00），但 "Paris." 会被判错。

```python
def token_f1(prediction, expected):
    pred_tokens = set(prediction.lower().split())
    exp_tokens = set(expected.lower().split())
    if not pred_tokens or not exp_tokens:
        return 0.0
    common = pred_tokens & exp_tokens
    precision = len(common) / len(pred_tokens)
    recall = len(common) / len(exp_tokens)
    ...
    return 2 * (precision * recall) / (precision + recall)
```

- precision = 预测中有多少词是对的；recall = 参考中有多少词被覆盖；F1 是二者的调和平均。
- ⚠️ **没有去标点**：`"Paris, France"` 切出 `"paris,"`，与 `"paris"` 不相等，F1 = 0（第 4 步 Extra info 一行）。
- ⚠️ **用 set 而不是多重集合**：`"paris paris paris"` 对 `"paris"` 得 1.0。SQuAD 官方 F1 用 `Counter` 求交集；本文件导入了 `Counter` 却没用，很可能就是这一步被简化掉了。
- ⚠️ **没去冠词**：`"The capital of France is Paris"` 的分母里多了 "the"。SQuAD 规范化会去掉 a / an / the。改进版见测验 Q9。

```python
def llm_judge_simulated(prediction, expected):
    pred_words = set(prediction.lower().split())
    exp_words = set(expected.lower().split())
    if not exp_words:
        return 0.0
    overlap = len(pred_words & exp_words) / len(exp_words)
    length_penalty = min(1.0, len(prediction) / max(len(expected), 1))
    return round(overlap * 0.7 + length_penalty * 0.3, 3)
```

- `overlap` 除以参考词数，是**召回率**：多说不扣分，所以 "The capital of France is Paris" 得满分 1.000。
- ⚠️ `length_penalty` 名为惩罚，实为**长度奖励**：字符数不短于参考答案就拿满 0.3。于是 "I don't know"、"France" 这类错误答案都白拿 0.300；随机模型 C 一题没对，judge 均值仍有 0.182。
- 这个"模拟评委"恰好复现了讲义警告的 **verbosity bias**（偏好长回答）。真实的 LLM-as-judge 是把题目、参考、回答和 rubric 发给强模型打分，而不是算词重叠。把它当成反面教材来读更有收获。
- `max(len(expected), 1)`：防止参考为空时除以 0。

### 3.3 ELOTracker

```python
    def expected_score(self, rating_a, rating_b):
        return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))

    def record_match(self, player_a, player_b, outcome):
        ...
        ea = self.expected_score(self.ratings[player_a], self.ratings[player_b])
        eb = 1 - ea
        if outcome == "a":
            sa, sb = 1.0, 0.0
        elif outcome == "b":
            sa, sb = 0.0, 1.0
        else:
            sa, sb = 0.5, 0.5
        self.ratings[player_a] += self.k * (sa - ea)
        self.ratings[player_b] += self.k * (sb - eb)
```

- **期望胜率**是 logistic 曲线：分差 400 分时强者期望胜率约 0.91；分差 200 分时约 0.76（实测 `expected_score(1700, 1500) = 0.760`）。
- **更新量** `K × (实际 − 期望)`：符合预期的胜利加分少，爆冷加分多；K = 32 是单场最大变化量。
- 平局记 0.5 分。
- **零和**：`sa + sb = 1` 且 `ea + eb = 1`，所以每场两人的变化量互为相反数，总分恒为 `1500 × 人数`。本次运行 `1666 + 1470 + 1364 = 4500`（精确值 4500.0）。
- `_ensure_player`：首次出现的选手自动以 1500 分加入。
- `leaderboard` 用 `sorted(..., key=lambda x: -x[1])` 按分数降序。
- ⚠️ 在线 ELO **依赖比赛顺序**：同样的 24 场结果反序处理，得到 1666.4 / 1468.6 / 1365.1（实测）。讲义称这是 "exactly the system Chatbot Arena uses"；用于静态评测时，更稳健的做法是对全部结果做 Bradley–Terry 最大似然拟合，并用 bootstrap 给置信区间。

### 3.4 Perplexity 与模拟 log 概率

```python
def perplexity(log_probs):
    if not log_probs:
        return float("inf")
    avg_neg_log_prob = -np.mean(log_probs)
    return float(np.exp(avg_neg_log_prob))
```

- 完全对应公式 `PPL = exp(−(1/N) Σ log p_i)`。等价地说，PPL 是"每个 token 概率的几何平均的倒数"：若每个 token 概率都是 0.25，PPL = 4。
- 空输入返回 `inf`，避免对空数组求均值得到 NaN 并报警告。

```python
def token_log_probs_simulated(text, model_quality=0.8):
    np.random.seed(int(hashlib.sha256(text.encode()).hexdigest()[:8], 16) % 2**31)
    tokens = text.split()
    for i, token in enumerate(tokens):
        base_prob = model_quality
        if len(token) > 8:
            base_prob *= 0.6
        if i == 0:
            base_prob *= 0.7
        prob = np.clip(base_prob + np.random.normal(0, 0.1), 0.01, 0.99)
        log_probs.append(float(np.log(prob)))
```

- 规则：基础概率 = 模型质量；长词（> 8 字符）× 0.6，模拟"罕见词更难猜"；第一个词 × 0.7，模拟"没有上下文时更难猜"；再加高斯噪声并截断到 `[0.01, 0.99]`。
- **种子来自文本的 sha256**：取前 8 个十六进制字符转整数。同一段文本、不同 quality 用的是同一串噪声，比较只反映 quality 的差异；而且每次运行结果一致。讲义版用的是 `hash(text)`，Python 的字符串哈希每个进程随机加盐，结果不可复现，代码改成 `hashlib` 是一处修正。
- 副作用：`np.random.seed` 改的是全局随机状态。更好的写法是 `rng = np.random.default_rng(seed)`，再用 `rng.normal(...)`。
- ⚠️ 这里的 "token" 是按空格切的词，不是 tokenizer 的 token；概率在 0.3–0.99 附近，因此 PPL 只有 1.1–4.5，远低于讲义给出的真实数值（GPT-2 在 WikiText-103 上约 30，Llama 3 8B 约 7）。只能用来看"质量越高 PPL 越低"的趋势。

### 3.5 汇总统计

```python
def summarize_results(results, threshold=0.8):
    all_scores = {}
    for r in results:
        for metric, score in r["scores"].items():
            all_scores.setdefault(metric, []).append(score)
    ...
            "pass_rate": round(float(np.mean(arr >= threshold)), 3),
```

- `dict.setdefault(key, [])`：键不存在时先放入空列表并返回它，适合"按键分组追加"。
- `arr >= threshold` 得到布尔数组，`np.mean` 把 True 当 1，直接得到通过率。
- `np.std` 默认是总体标准差（ddof = 0）。
- ⚠️ `print_summary` 中写死了 `"(threshold >= 0.8)"`，如果调用 `summarize_results(..., threshold=0.5)`，打印出来的阈值仍然是 0.8，会误导读者。应把阈值也放进 `summary` 里一起打印。
- 只有 8 条用例时，均值的波动很大；生产中应同时报告置信区间或标准误。

### 3.6 三个"模型"

- `demo_model_good`：一个**按测试题写死答案**的字典，回答与参考答案逐字相同，未见过的题返回 "I don't know"。它在本 eval 上拿满分，等价于"完全污染"：答案就是从测试集里抄来的。
- `demo_model_bad`：回答更啰嗦或换了说法，但大部分**事实正确**（"The answer is four"、"212 Fahrenheit"、"About 300 million m/s"、"World War 2 ended in 1945"）。它被叫作 "bad"，是因为 EM/F1 惩罚了表述差异，而不是因为它答错了。
- `demo_model_random`：用 prompt 的 sha256 做种子，从 7 个词里随机选一个，每题输出固定。

### 3.7 ELO 锦标赛

```python
    for case in cases:
        for i in range(len(model_names)):
            for j in range(i + 1, len(model_names)):
                ...
                score_a = token_f1(pred_a, case.expected)
                score_b = token_f1(pred_b, case.expected)
                if score_a > score_b + 0.01:
                    outcome = "a"
                elif score_b > score_a + 0.01:
                    outcome = "b"
                else:
                    outcome = "tie"
```

- 双重循环 `i < j` 枚举所有无序配对（3 个模型 → 3 对），8 条用例共 24 场。
- **裁判是 token F1**，不是人，也不是 LLM 评委。0.01 的容差用来把近似相等判为平局。
- concise 的 F1 恒为 1.0，所以 16 场全胜；verbose 对 random 有 5 胜 3 平。这个排名只是 STEP 1 的 F1 结论换了一种形式，并没有新信息。

### 3.8 指标分歧分析

- 6 组预测对同一个参考 "Paris"：完全一致、啰嗦但正确、错但相关、拒答、大小写不同、附加信息。
- 打印用了 f-string 对齐格式（`{pred:<35}`、`{em:>5.2f}`），形成对照表。
- 结论（见第 6 节）：三个指标在"啰嗦但正确""附加信息"两行上给出截然不同的分数，而 Judge 对拒答也给了 0.3。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 模型 = `str -> str` 函数 | 任意模型/API 都能接入 | 生产中还需批量、并发、重试、记录 token 与延迟 |
| scorer 用字典注册 | 方便组合多个指标 | 应同时记录每个 scorer 的版本 |
| EM 只做 strip + lower | 最简单 | "Paris." 判错；应有统一的规范化函数 |
| F1 用 set、不去标点 | 代码短 | 重复词与标点导致误判；用 SQuAD 规范化 + Counter |
| 用词重叠 + 长度比"模拟"评委 | 无需调用 API | 奖励冗长，与真实评委相差甚远；真实做法是 rubric + 强模型 + 人工校准 |
| 在线 ELO | 实现简单、与 Arena 概念一致 | 顺序相关；离线评测用 Bradley–Terry + bootstrap |
| 用 F1 当 ELO 裁判 | 无需人类 | 只复述了 F1 的偏好 |
| 模拟 log 概率 + sha256 种子 | 可复现、三种质量共享噪声 | 数值不真实；真实 PPL 需从模型 logits 取 |
| 只有 8 条用例 | 演示 | 讲义建议原型 ≥ 50、生产 ≥ 200，且含边界用例 |
| `pass_rate` 阈值 0.8 | 体现"可靠性"视角 | 打印处阈值写死；阈值应按任务标定 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 类与 `__init__` | `class EvalCase: def __init__(self, input_text, expected, metadata=None)` | 用实例属性保存数据 |
| `None` 默认值 + `or` | `self.metadata = metadata or {}` | 避免可变默认参数被所有实例共享 |
| 函数作为参数 | `suite.run(demo_model_good)`、`scorers={"exact_match": exact_match, ...}` | Python 函数是一等对象，可存入字典、作为参数传递 |
| `dict.items()` 解包 | `for scorer_name, scorer_fn in self.scorers.items()` | 同时取键和值 |
| `dict.get` 默认值 | `responses.get(prompt, "I don't know")` | 键不存在时返回默认值 |
| `dict.setdefault` | `all_scores.setdefault(metric, []).append(score)` | 不存在则插入空列表再追加 |
| 集合运算 | `pred_tokens & exp_tokens` | 交集 |
| 字符串方法链 | `prediction.strip().lower()`、`text.encode()` | 去空白、小写、转字节 |
| `hashlib` | `hashlib.sha256(text.encode()).hexdigest()[:8]` | 稳定的哈希；切片取前 8 个十六进制字符 |
| `int(s, 16)` | `int(..., 16) % 2**31` | 按十六进制解析；取模限制种子范围 |
| 幂运算 | `10 ** ((rating_b - rating_a) / 400)`、`2**31` | `**` 是乘方 |
| `lambda` + `sorted` | `sorted(self.ratings.items(), key=lambda x: -x[1])` | 按值降序 |
| `enumerate(..., 1)` | `for rank, (name, rating) in enumerate(elo.leaderboard(), 1)` | 下标从 1 开始；嵌套元组解包 |
| 链式条件表达式 | `m["a"] if ... == "a" else m["b"] if ... == "b" else "tie"` | 一行写多分支（可读性一般） |
| `float("inf")` | `return float("inf")` | 正无穷 |
| NumPy 布尔数组求均值 | `np.mean(arr >= threshold)` | True/False 当作 1/0 |
| `np.clip` | `np.clip(x, 0.01, 0.99)` | 截断到区间，避免 `log(0)` |
| `np.random.seed` / `normal` / `randint` | 模拟噪声与随机模型 | 全局随机状态；推荐 `default_rng` |
| f-string 格式符 | `{stats['pass_rate']:.1%}`、`{name:<15}`、`{rating:.0f}`、`{em:>5.2f}`、`{'=' * 60}` | 百分数、左对齐、取整、右对齐、表达式 |
| 切片 | `text[:60]`、`elo.history[:5]` | 取前 N 个 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行四个演示 |

---

## 6. 运行结果解读

实际运行（Python 3.13 + NumPy 2.5，耗时不到 1 秒），节选：

```text
  Model A (concise, exact) Summary
  exact_match / token_f1 / llm_judge: Mean 1.000, Pass rate 100.0%     ← 查表模型，答案与参考逐字相同

  Model B (verbose, paraphrase) Summary
  exact_match:  Mean 0.000  Pass rate 0.0%
  token_f1:     Mean 0.254  Median 0.268  Std 0.232  Range [0.000, 0.667]  Pass rate 0.0%
  llm_judge:    Mean 0.580  Median 0.443  Std 0.337  Range [0.221, 1.000]  Pass rate 37.5%

  Model C (random) Summary
  exact_match / token_f1: Mean 0.000
  llm_judge:    Mean 0.182  Range [0.033, 0.300]                         ← 全错也有分

  ELO Leaderboard (after pairwise comparisons):
    1. concise         1666
    2. verbose         1470
    3. random          1364
  Match history (24 matches): ...

  Text: The quick brown fox jumps over the lazy dog in the garden...
    Strong 1.13 / Medium 1.44 / Weak 2.52
  Text: Quantum entanglement demonstrates nonlocal correlations betw...
    Strong 1.66 / Medium 2.19 / Weak 4.51                                ← 长词多，PPL 更高
  Text: def fibonacci(n): return n if n < 2 else fibonacci(n-1) + fi...
    Strong 1.27 / Medium 1.62 / Weak 2.78

  Prediction                          Expected      EM    F1  Judge
  Paris                               Paris       1.00  1.00  1.000  (Exact match)
  The capital of France is Paris      Paris       0.00  0.29  1.000  (Verbose correct answer)
  France                              Paris       0.00  0.00  0.300  (Wrong but related)
  I don't know                        Paris       0.00  0.00  0.300  (Refusal)
  paris                               Paris       1.00  1.00  1.000  (Case mismatch)
  Paris, France                       Paris       0.00  0.00  0.300  (Extra info)
```

逐项解读：

- **Model B 的逐题分数**（实测）：F1 依次为 0.25、0、0.667、0.5、0、0、0.333、0.286；Judge 依次为 1.0、0.3、0.524、0.362、0.221、0.233、1.0、1.0。Judge 的 3 个满分正好对应"参考答案作为完整词出现在长回答里"的三题，所以 pass rate = 3/8 = 37.5%。按事实判断，B 约 7 题正确、1 题部分正确（"Python"），却被 EM 判为全错。
- **Model C 的 judge 0.182**：全部来自长度项。"unknown" 对 "Paris" 得 0.300，就是 `0.7 × 0 + 0.3 × min(1, 7/5)`。
- **ELO**：三者之和 4500，零和守恒。concise 16 战全胜；verbose 对 random 5 胜 3 平（"2 + 2"、"boiling point"、"speed of light" 三题两者 F1 都是 0）。
- **Perplexity**：第一段文本 strong 模型逐词概率实测为 `[0.521, 0.967, 0.973, 0.922, 0.99, ...]`，第一个词因 × 0.7 明显偏低；量子那段有 4 个超过 8 字符的词（entanglement、demonstrates、correlations、particles），所以 PPL 比其他两段高。三种 quality 的排序在每段文本上都一致，这是共享噪声的结果。
- **指标分歧表**：同一个正确答案 "Paris, France"，EM 和 F1 都给 0（F1 是标点问题），Judge 给 0.3，与 "I don't know" 一样；"The capital of France is Paris" 则在 F1 下只有 0.29、在 Judge 下满分。讲义："the same model looks great or terrible depending on how you score it."

---

## 7. 动手改一改

1. **修 F1**：实现 SQuAD 式规范化（小写、去标点、去冠词）+ `Counter` 交集（参考测验 Q9），重新运行 STEP 1 和 STEP 4，比较 Model B 的 F1 均值变化。
2. **修打印阈值**：让 `summarize_results` 把 `threshold` 写进返回值，`print_summary` 读取它；用 0.5 和 0.8 两个阈值对比 Model B 的 pass rate。
3. **讲义练习 1（一致性 scorer）**：给 `demo_model_random` 加一个不固定种子的版本，同一输入跑 5 次，统计输出一致的比例。
4. **讲义练习 2（多评委 ELO）**：裁判改为 `w1 × EM + w2 × F1 + w3 × Judge`，分别取"重 EM"与"重 F1"两组权重，观察排行榜变化；再实现 Bradley–Terry 拟合，与在线 ELO 比较，并验证打乱比赛顺序后的稳定性。
5. **讲义练习 4（污染检测）**：准备一份"训练语料"文本，对每条用例计算 8-gram 重叠率，标记重叠率超过阈值的题目；对比"去掉可疑题目"前后各模型的分数。
6. **讲义练习 5（model diff）**：给定两个模型的 `results`，输出每条用例在各指标上的"改进 / 退化 / 不变"，并按退化幅度排序。

---

## 8. 常见坑

- **把"与参考答案形式一致"当成"正确"**：EM/F1 会惩罚正确的改写、单位换算和数字的不同写法（"four" vs "4"）。
- **F1 不做规范化**：标点粘在词上（"paris,"）、冠词计入分母、重复词被集合吞掉。
- **评委奖励长度**：本文件的模拟评委对任何不短于参考的回答都给 0.3 分。真实 LLM 评委也有冗长偏差，需要在 rubric 中明确并抽样校准。
- **在线 ELO 的顺序依赖**：不同的比赛顺序会给出不同的分数；离线评测用 Bradley–Terry，并报告置信区间。
- **用 `hash()` 做随机种子**：Python 字符串哈希每个进程都不同，结果不可复现；用 `hashlib`。
- **全局随机状态**：在函数里调 `np.random.seed` 会影响其他代码；用局部的 `default_rng`。
- **跨 tokenizer 比较 perplexity**：词表不同，"每个 token"的含义不同；用 bits-per-byte。
- **用例太少就下结论**：8 条用例的均值波动很大，一题之差就是 12.5 个百分点。
- **查表式模型 = 污染**：在自己写的测试题上拿 100% 并不说明泛化能力，必须有模型从未见过的保留集。
- **中文讲义的机翻错误**：`docs/zh.md` 中 "EleutherAI" 被译成"优绝国际"，"RAGAS" 被译成"反种族主义组织"，阅读时以英文版为准。
