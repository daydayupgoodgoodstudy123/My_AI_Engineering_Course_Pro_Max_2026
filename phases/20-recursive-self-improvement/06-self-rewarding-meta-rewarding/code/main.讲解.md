# 代码讲解 · main.py

> **所属小节**：阶段 20 · 递归自我改进 · 第 06 节 自我奖励与元奖励：当裁判就是学生 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py [--iterations 12] [--length-bias 0.5] [--audit-size 40] [--regime frozen|meta|both] [--seed 7]` ｜ **依赖**：仅标准库（`argparse`、`json`、`math`、`random`、`dataclasses`、`typing`）

---

## 1. 这份代码在考察什么

讲义的核心论断是：**当裁判（judge）和学生（actor）是同一组权重时，学生学到的不是"质量"，而是"裁判的偏好"**。Self-Rewarding（Yuan et al., 2024）里回答越来越长、Meta-Rewarding（Wu et al., 2024）里裁判平均分从 4.1 涨到 4.7 以上，都是这个机制的实证。这份代码把机制抽成一个可以反复跑的玩具模型：

1. **actor 是一个风格分布**：6 种回答风格，每种有一个潜在的真实质量均值 `quality` 和典型长度 `length`；最好的风格（`concise`，0.78）恰好是短的，最差的长风格（`verbose`，0.50）恰好是最长的。
2. **judge 看得见质量，但带长度偏好**：`score = q + length_bias × length/1000 + 噪声`。
3. **DPO 式更新**：每轮抽 200 对回答，judge 选赢家，赢的风格对数概率上调、输的下调（乘法权重更新）。
4. **两种制度（regime）对照**：`frozen`——judge 永不修正（Self-Rewarding）；`meta`——一个**有根基的元裁判**拿着一小份人工标注的审计集，每轮估计 judge 的长度偏好并砍掉一半（讲义对 Meta-Rewarding 的解读：真正起作用的是审计集，不是多出来的那一层）。
5. **四个监控信号**：审计集上的裁判—人类一致率、长度漂移、分数通胀、偏好对熵——正是讲义"每轮必记"的那张表。

> 一句话：**用一个六风格的 actor 和一个带长度偏好的 judge，演示"冻结的裁判把学生教坏、有根基的元裁判把裁判修好"，并把讲义的四个监控信号算出来**。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `STYLES`、`K`、`LENGTH_SCALE` 等常量 | 常量 | 六种风格的 `(name, quality, length)`；长度归一化到"每 1,000 字符" | actor 的动作空间 |
| `Style` / `Response` / `AuditItem` | frozen dataclass | 风格定义、一次采样的回答、带人工标签的审计样本 | 潜变量 q、L 与人工标签 |
| `Judge` | dataclass | `score()`：真实质量 + 长度偏好 + 噪声 | LLM-as-a-Judge 及其偏好 |
| `Config` / `IterStats` | dataclass | 运行参数；每轮的 10 个统计量 | 监控信号 |
| `sample_response` / `actor_expectations` | 函数 | 按 actor 分布采样一条回答；精确计算 E[q]、E[L] | actor 采样与"真实质量" |
| `dpo_like_update` | 函数 | 指数梯度（乘法权重）更新风格概率 | 迭代 DPO 的风格级近似 |
| `make_audit_set` / `audit_judge` | 函数 | 固定审计集；回归估计 β̂ 并算裁判—人类一致率 | 有根基的元裁判 |
| `run_regime` | 函数 | 跑一个制度 `iterations` 轮，返回每轮 `IterStats` | 自我奖励循环 |
| `print_history` / `print_headline` | 函数 | 对齐表格；由数字拼出 HEADLINE | 结果呈现 |
| `main` | 函数 | argparse、跑一或两个制度、可选写 JSON | 入口 |

数据流：命令行参数 → `Config` → 对每个制度 `run_regime(regime, cfg, seed)`（每轮：采样 200 对 → `Judge.score` 选赢家 → 累计胜负 → `audit_judge` → 记录 `IterStats` → `dpo_like_update`，`meta` 制度再更新 `judge.length_bias`）→ `print_history` → `print_headline`（f-string 拼数字）→ 可选 `--out` JSON。

---

## 3. 逐段精讲

### 3.1 风格表与常量

```python
LENGTH_SCALE = 1000.0   # chars; length bias is "quality points per 1,000 characters"
QUALITY_SD = 0.05       # within-style spread of true quality
LENGTH_SD_FRAC = 0.15   # within-style spread of length, fraction of the style mean
JUDGE_NOISE = 0.05      # judge scoring noise, quality points
LABEL_NOISE = 0.10      # noise of the human labels in the audit set, quality points

STYLES: tuple[Style, ...] = (
    Style("concise", 0.78, 180.0),
    Style("standard", 0.72, 320.0),
    Style("thorough", 0.74, 520.0),
    Style("padded", 0.62, 780.0),
    Style("verbose", 0.50, 1100.0),
    Style("sloppy", 0.40, 110.0),
)
```

- 风格表是**刻意反相关**的：质量最高的 `concise` 最短，`verbose` 最长却只有 0.50。这样"偏好长度"与"偏好质量"会指向不同的风格，差异才看得见。
- `LENGTH_SCALE = 1000` 让 `--length-bias 0.5` 的含义是"每 1,000 字符值 0.5 个质量点"。`verbose` 比 `concise` 长 920 字符，在 β = 0.5 下多得 0.46 分，超过两者 0.28 的质量差——这就是讲义"长度项是最大的一项"的来源。
- `LABEL_NOISE = 0.10` 大于 `JUDGE_NOISE = 0.05`：人工标签也有噪声，所以审计集越小，元裁判的估计越抖（§6 的 `--audit-size 6`）。

初始 actor 对六种风格均匀分布：真实质量 `(0.78+0.72+0.74+0.62+0.50+0.40)/6 = 0.627`，平均长度 502 字符。

### 3.2 `Judge.score()`：一行写出 Goodhart

```python
@dataclass
class Judge:
    length_bias: float
    noise: float = JUDGE_NOISE

    def score(self, r: Response, rng: random.Random) -> float:
        return r.quality + self.length_bias * (r.length / LENGTH_SCALE) + rng.gauss(0.0, self.noise)
```

- judge **确实看得见真实质量** `r.quality`，所以它不是坏裁判，只是带一个与质量无关的偏好项。讲义：actor 不需要作恶，"gradient ascent on Δs finds the length term because it is the biggest term"。
- `length_bias` 是普通字段，不是 frozen：`meta` 制度每轮会就地修改它。

### 3.3 `sample_response()` 与 `actor_expectations()`

```python
def sample_response(probs: Sequence[float], rng: random.Random) -> Response:
    k = rng.choices(range(K), weights=probs, k=1)[0]
    st = STYLES[k]
    q = min(1.0, max(0.0, rng.gauss(st.quality, QUALITY_SD)))
    length = max(20.0, rng.gauss(st.length, LENGTH_SD_FRAC * st.length))
    return Response(k, q, length)
```

- `rng.choices(..., weights=probs)` 按 actor 的概率抽风格；同一风格内质量和长度再加高斯扰动，所以同风格的两条回答也能分出胜负。
- `actor_expectations` 不采样，直接算 `Σ p_k·q_k` 和 `Σ p_k·L_k`——表格里的 `true_q`、`length` 列是**精确期望**，不受抽样噪声影响；`judge`、`inflat`、`agr_tr` 三列才是本轮 400 条样本上的统计量。

### 3.4 `dpo_like_update()`：风格级的 DPO

```python
def dpo_like_update(probs, wins, losses, shown, lr):
    logits = []
    for k, p in enumerate(probs):
        adv = (wins[k] - losses[k]) / shown[k] if shown[k] else 0.0
        logits.append(math.log(max(p, 1e-12)) + lr * adv)
    top = max(logits)
    weights = [math.exp(x - top) for x in logits]
    z = sum(weights)
    return [w / z for w in weights]
```

- `adv ∈ [−1, 1]`：风格 k 每次出场的净胜率。`log p_k += lr × adv` 是**指数梯度 / 乘法权重**更新，对应 DPO "拉高 chosen 的对数概率、压低 rejected"。
- `math.exp(x - top)` 先减去最大值再取指数，是 softmax 的标准防溢出写法。
- 没出场的风格 `adv = 0`，概率在归一化前不变——所以概率只会被挤小，不会突变为 0。

### 3.5 `make_audit_set()` 与 `audit_judge()`：有根基的元裁判

```python
def make_audit_set(size, rng, label_noise=LABEL_NOISE):
    base = uniform_probs()
    items = []
    for _ in range(size):
        r = sample_response(base, rng)
        items.append(AuditItem(r, r.quality + rng.gauss(0.0, label_noise)))
    return items
```

- 审计集从**初始均匀分布**抽，而且只在 `run_regime` 开头生成一次：它是固定的、不随 actor 漂移的——讲义反复强调的 "fixed audit set"。标签是真实质量加 0.10 的噪声，模拟人工打分。

```python
    scores = [judge.score(it.response, rng) for it in audit]
    xs = [it.response.length / LENGTH_SCALE for it in audit]
    rs = [s - it.label for s, it in zip(scores, audit)]
    ...
    beta_hat = sxr / sxx if sxx > 0 else 0.0
    for i in range(0, len(audit) - 1, 2):
        n_pairs += 1
        if (scores[i] - scores[i + 1]) * (audit[i].label - audit[i + 1].label) > 0:
            agree += 1
```

- `rs = judge 分 − 人工标签` 是裁判的"误差"；把误差对归一化长度做一元最小二乘回归，斜率 `beta_hat` 就是裁判长度偏好的估计。因为 `score = q + β·ℓ + ε`、`label = q + η`，所以 `score − label = β·ℓ + (ε − η)`，回归无偏。
- 一致率把审计集两两配对（`range(0, n-1, 2)`），比较裁判排序和人类排序的符号。40 个样本 = 20 对，所以 `agr_au` 只能以 5% 为步长变化；6 个样本 = 3 对，步长 33.3%。
- 元裁判**唯一**多于裁判的信息就是这些人工标签——这正是讲义的设计规则："a meta-judge is only useful if it has information the judge does not"。

### 3.6 `run_regime()`：一轮里发生了什么

```python
        for _ in range(cfg.pairs):
            a = sample_response(probs, rng)
            b = sample_response(probs, rng)
            sa = judge.score(a, rng)
            sb = judge.score(b, rng)
            winner, loser = (a, b) if sa >= sb else (b, a)
            wins[winner.style] += 1
            losses[loser.style] += 1
            shown[a.style] += 1
            shown[b.style] += 1
            if (sa - sb) * (a.quality - b.quality) > 0:
                agree += 1
            score_sum += sa + sb
            q_sum += a.quality + b.quality
        beta_hat, agree_audit, _, _ = audit_judge(judge, audit, rng)
        ...
        if it == cfg.iterations:
            break
        probs = dpo_like_update(probs, wins, losses, shown, cfg.lr)
        if regime == "meta":
            corrected = judge.length_bias - cfg.meta_lr * beta_hat
            judge.length_bias = max(-2.0, min(2.0, corrected))
```

- 第 0 行是"未训练的 actor 被初始 judge 打分"的基线；之后每轮先采样、评判、统计，**再**更新 actor；`meta` 制度最后才修 judge，所以表格里的 `bias` 列是**本轮实际使用**的偏好。
- `agree`（表格 `agr_tr`）比较的是裁判赢家与**真实质量**赢家——现实里你拿不到这个数，它只在模拟器里可见，用来说明"自己的训练对上的一致率"有多不可靠（见 §6）。
- `inflation = (score_sum − q_sum)/400`：裁判平均分比真实平均质量高多少，等于 `β × 平均归一化长度`；冻结裁判下它随长度一起涨。
- `meta_lr = 0.5`：每轮砍掉估计偏好的一半，所以 β 大约按 0.5、0.25、0.125 … 几何衰减，再叠加估计噪声。
- 两个制度各自用 `random.Random(seed)` 重新起一条随机流，审计集用 `seed + 1`：因此两张表的第 0 行完全相同，差异全部来自 judge 是否被修正。

### 3.7 `print_headline()`：结论由数字生成

```python
        print(f"  {regime:<6} judge (bias {h0.length_bias:+.2f} -> {hT.length_bias:+.2f}): "
              f"true quality {h0.true_quality:.3f} -> {hT.true_quality:.3f} ({dq / h0.true_quality:+.1%}), "
              f"mean length {h0.mean_length:,.0f} -> {hT.mean_length:,.0f} chars ({dl / h0.mean_length:+.1%}).")
    ...
        verdict = "beats" if gap > 0 else "does not beat"
```

- 所有结论句都是 f-string 拼数字，包括 "beats / does not beat" 这个动词——换种子、换参数，结论跟着数据变，不会出现"硬编码结论与数据矛盾"的情况。
- `first_iteration_below(hist, 0.10)` 找 |β| 第一次低于 0.10 的轮次，找不到返回 −1，HEADLINE 据此打印 "by iteration N" 或 "never within N iterations"。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| actor 是 6 种风格上的分布，而不是文本生成器 | 把"学生学到裁判偏好"压缩成概率的移动，一眼可见 | 真实策略的动作空间是 token 序列；风格是对"回答簇"的粗粒度近似 |
| judge 显式写成 `q + β·ℓ + ε` | 让 Goodhart 可量化，β 可调、可估计 | 真实 LLM-judge 的偏好是隐式的、多维的（长度、位置、格式、自我偏好），要靠回归或对照提示去发现 |
| 乘法权重更新代替真正的 DPO 损失 | 一行即可表达"chosen 升、rejected 降"，无需梯度框架 | 没有 KL 参考模型、没有 β_DPO 温度；真实 DPO 的更新幅度依赖 logit 差 |
| 元裁判 = 有人工标签的审计集 + 一元回归 | 讲义主张"真正起作用的是审计集"，于是把它做实；信息来源一句话说清 | Wu et al. 的 meta-judge 没有标签，只是同权重换提示；本模拟器是"有根基"的理想版，不是论文复现 |
| 审计集固定、从初始分布抽 | 不随 actor 漂移，才能当尺子 | 生产中要按长度分桶抽样、哈希冻结、只追加不替换（见 skill 文件） |
| 两个制度各用独立 `random.Random(seed)` | 同种子下第 0 行一致，差异可归因 | 若共用一条随机流，第二个制度的结果会被第一个制度"消耗"的随机数影响 |
| `true_q`、`length` 用精确期望 | 消除抽样噪声，趋势干净 | 真实系统只有样本统计，需要置信区间 |
| HEADLINE 全部由数字生成 | 参数一变结论跟着变 | 需要为每句话定义清楚"比较的是哪两个数" |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass(frozen=True)` | `class Style`、`class Response` | 不可变数据类，可哈希，防止被意外修改 |
| 可变 dataclass 的就地修改 | `judge.length_bias = ...` | `Judge` 没加 `frozen`，`meta` 制度要改它 |
| `rng.choices(population, weights=..., k=1)` | `sample_response` | 带权重抽样；返回列表，所以要 `[0]` |
| 局部 RNG 实例 | `random.Random(seed)`、`random.Random(seed + 1)` | 不用全局 `random`，各段互不干扰、可复现 |
| 条件表达式 | `adv = (...) / shown[k] if shown[k] else 0.0` | 一行处理"除零"分支 |
| softmax 防溢出 | `math.exp(x - top)` | 先减最大值再取指数 |
| 元组解包交换 | `winner, loser = (a, b) if sa >= sb else (b, a)` | 一行决定胜负双方 |
| `range(start, stop, step)` | `range(0, len(audit) - 1, 2)` | 两两配对遍历 |
| f-string 格式符 | `{h.length_bias:>+6.2f}`、`{h.agree_train:>6.1%}`、`{h0.mean_length:,.0f}` | 强制正负号、百分比一位小数、千位分隔 |
| 字典推导 + `asdict` | `{regime: [asdict(h) for h in hist] ...}` | dataclass 转 JSON 友好的字典 |
| `argparse` 的 `choices` 与 `parser.error` | `choices=("frozen", "meta", "both")`、`parser.error("--audit-size must be at least 2")` | 参数校验在解析阶段完成 |
| `formatter_class=argparse.RawDescriptionHelpFormatter` | `ArgumentParser(description=__doc__, ...)` | 让 `--help` 原样显示模块 docstring 的换行 |

---

## 6. 运行结果解读

实际运行 `python3 main.py`（seed 7，瞬间完成），节选：

```text
  untrained actor: uniform over 6 styles -> true quality 0.627, mean length 502 chars

Regime FROZEN — the judge is never corrected (Self-Rewarding)
  it    bias  true_q  length   judge  inflat  agr_tr  agr_au  win_H  top style (p)
   0   +0.50   0.627     502   0.884  +0.234   54.5%   55.0%   2.44  concise (0.17)
   1   +0.50   0.626     596   0.948  +0.317   48.0%   50.0%   2.09  verbose (0.23)   ← 一轮之后最长的风格已经领跑
   4   +0.50   0.608     780   1.009  +0.393   45.5%   40.0%   1.72  verbose (0.40)
   8   +0.50   0.571     914   1.033  +0.459   50.0%   35.0%   1.35  verbose (0.58)
  12   +0.50   0.542     990   1.039  +0.499   64.5%   50.0%   1.07  verbose (0.72)   ← 质量 −13.5%，长度 ×2，裁判分 +0.155

Regime META — a grounded meta-judge shrinks the judge's length bias each iteration
   0   +0.50   0.627     502   0.884  +0.234   54.5%   55.0%   2.44  concise (0.17)   ← 与 FROZEN 第 0 行完全相同
   1   +0.24   0.626     596   0.785  +0.153   73.0%   65.0%   2.30  verbose (0.23)   ← 第 1 轮 actor 已被 β=0.5 推长一次
   2   +0.10   0.647     596   0.706  +0.064   87.5%   75.0%   2.31  padded (0.24)
   3   +0.04   0.674     544   0.691  +0.026   85.0%   80.0%   2.04  thorough (0.26)  ← |β| < 0.10，开始回头
   4   -0.00   0.702     484   0.713  +0.002   82.0%   70.0%   1.79  thorough (0.32)
   8   -0.03   0.753     325   0.748  -0.007   80.0%   75.0%   1.11  concise (0.56)
  12   -0.02   0.771     235   0.768  -0.002   77.0%   80.0%   0.63  concise (0.82)   ← 收敛到真正最好的风格
```

HEADLINE（节选）：

```text
  frozen judge (bias +0.50 -> +0.50): true quality 0.627 -> 0.542 (-13.5%), mean length 502 -> 990 chars (+97.4%).
         judge mean score moved +0.155 while truth moved -0.084; inflation +0.234 -> +0.499; ...
  meta   judge (bias +0.50 -> -0.02): true quality 0.627 -> 0.771 (+23.0%), mean length 502 -> 235 chars (-53.1%).
  The grounded meta-judge (audit set of 40 labelled items) pushed |bias| below 0.10 by iteration 3.
  At seed 7 the meta regime beats the frozen regime on final true quality by +0.228 points (0.771 vs 0.542).
```

逐项解读：

- **FROZEN 的 `judge` 列一路上涨、`true_q` 一路下跌**：裁判平均分 0.884 → 1.039，真实质量 0.627 → 0.542。只看裁判的分数，你会以为训练在变好——这就是讲义说的 "self-confirming loop"：代理指标和被优化者一起漂移，差距（`inflat` 从 +0.234 涨到 +0.499）在循环内部不可见。
- **`agr_au` 在 FROZEN 里停在 35%–55%**：β = 0.5 的裁判在审计集上和人类几乎掷硬币。这是四个信号里唯一需要"循环外"信息的，也是唯一不会被漂移污染的。
- **`agr_tr` 在 FROZEN 第 12 轮反而升到 64.5%**：这不是裁判变好了，而是 actor 72% 都在 `verbose`，配对多数是同风格对，比较的是风格内的小扰动。讲义练习 4、测验 Q11 都围绕这一点：**用自己的训练对算一致率，不是监控**。
- **`win_H` 从 2.44 bit 跌到 1.07 / 0.63 bit**：两个制度都在收敛，熵本身不区分"收敛到对的风格"还是"收敛到错的风格"，必须和 `agr_au` 一起看。
- **META 第 1 轮长度也涨到 596**：第 0 轮的更新用的还是 β = 0.5 的裁判。修裁判总比学生学坏慢一步，`--meta-lr` 越小这一段"先漂再回"越长。

**非默认参数 `--length-bias 0.8`**（强偏好）：

```text
Regime FROZEN
   0   +0.80   0.627     502   1.025  +0.375   49.0%   50.0%   2.42  concise (0.17)
   6   +0.80   0.539     990   1.340  +0.806   51.5%   30.0%   0.66  verbose (0.76)
  12   +0.80   0.506    1084   1.376  +0.871   61.5%   40.0%   0.11  verbose (0.96)   ← 几乎只剩 verbose；熵 0.11 bit
Regime META
   3   +0.08   0.652     621   0.698  +0.053   86.0%   80.0%   2.07  thorough (0.26)
  12   -0.02   0.767     261   0.763  -0.002   77.5%   80.0%   0.90  concise (0.74)
  frozen judge (bias +0.80 -> +0.80): true quality 0.627 -> 0.506 (-19.3%), mean length 502 -> 1,084 chars (+116.1%).
  meta   judge (bias +0.80 -> -0.02): true quality 0.627 -> 0.767 (+22.4%), mean length 502 -> 261 chars (-48.0%).
```

偏好越强，冻结裁判下坍缩越快越彻底（第 12 轮 `verbose` 占 0.96）；元裁判仍在第 3 轮把 |β| 压到 0.10 以下，终点 0.767 与默认几乎一样——因为回归估计的是 β 本身，起点大只是多砍一轮。

**非默认参数 `--audit-size 6`**（审计集太小）：

```text
Regime META
   1   +0.20   0.626     596   0.763  +0.118   83.0%  100.0%   2.38  verbose (0.23)   ← 3 对样本，一致率只能是 0/33/67/100%
   3   -0.06   0.679     528   0.653  -0.032   85.5%   33.3%   2.05  thorough (0.26)
   4   -0.14   0.704     463   0.652  -0.060   84.0%   33.3%   1.78  concise (0.29)   ← 过冲到 −0.14：裁判开始"惩罚"长度
  12   -0.14   0.773     216   0.735  -0.033   77.5%   33.3%   0.38  concise (0.87)
```

6 个样本的回归噪声太大，β 被推过零到 −0.14 并停在那里；`agr_au` 在 33.3% 和 100% 之间跳，作为监控完全失效。真实质量仍然到 0.773，是因为这组风格里"惩罚长度"恰好也指向 `concise`——这是模拟器的巧合，不是元裁判的功劳。

**非默认参数 `--length-bias 0.3`**（温和偏好）：

```text
Regime FROZEN
  12   +0.30   0.725     536   0.888  +0.167   73.0%   70.0%   0.86  thorough (0.82)  ← 质量上升了，但停在 0.74 的 thorough
Regime META
  12   -0.02   0.773     221   0.770  -0.002   77.0%   80.0%   0.52  concise (0.87)
```

温和偏好不坍缩，而是**收敛到错误的最优点**：β = 0.3 时 `thorough` 的裁判分 0.74 + 0.156 = 0.896 高于 `concise` 的 0.78 + 0.054 = 0.834。裁判分与真实质量同向上涨、`inflat` 稳定在 +0.17，所有循环内指标都"正常"——这是最难被发现的 Goodhart（讲义练习 2）。

---

## 7. 动手改一改

1. **（讲义练习 1）** 跑 `--length-bias 0` 与 `--length-bias 0.8`，把两个制度的终点 `true_q`、`length`、`inflat` 列成一张表；验证 β = 0 时两个制度几乎相同（0.774 vs 0.775），说明差异全部来自裁判修正而不是更新规则。
2. **（讲义练习 2）** 跑 `--length-bias 0.3`，用风格表手算 β = 0.3 下六种风格的期望裁判分，确认 `thorough` 最高；再找出让 `concise` 重新领先的 β 上限。
3. **（讲义练习 3）** 跑 `--audit-size 6`、`40`、`200`，记录 META 制度 β 的轨迹和 `agr_au` 的步长；给 `audit_judge` 加一个基于 `sxx` 和残差方差的标准误输出，让元裁判在标准误过大时**拒绝更新**。
4. **实现 Wu et al. 的长度控制**（讲义练习 5）：每个 prompt 抽 N = 4 条，chosen 取分数在 `[(1−ρ)S_max + ρS_min, S_max]` 内**最短**的一条，rejected 取分数在 `[S_min, (1−ρ)S_min + ρS_max]` 内**最长**的一条；在 `frozen` 制度、β = 0.5 下比较 ρ ∈ {0, 0.3, 0.5} 的终点质量，与 `meta` 制度对照。
5. **让元裁判失去根基**：把 `audit_judge` 里的 `it.label` 换成另一个同 β 的 `Judge` 给出的分数（即"同权重换提示"的 meta-judge），观察 β̂ 恒为 0、`meta` 退化成 `frozen`——这是讲义"元裁判必须拥有裁判没有的信息"的反证。
6. **进阶：会漂移的审计集**。每轮用 actor 的当前样本替换 20% 的审计集（标签仍由真实质量加噪声生成），观察 `agr_au` 是否仍能预警，并解释为什么 skill 文件要求审计集"只追加、不替换"。

---

## 8. 常见坑

- **把 `judge` 列当成训练进度**：冻结裁判下它单调上涨而真实质量下跌。任何自我奖励循环里，裁判分数都不是进度条。
- **用训练对算一致率**：`agr_tr` 在 actor 坍缩后上升是假象。监控一致率必须在固定的、循环外的审计集上算。
- **审计集太小**：20 对的步长是 5%，3 对是 33.3%；小样本还会让元裁判过冲到负 β。先算标准误，再决定是否相信估计。
- **忽略"先漂一轮"**：修裁判永远落后学生一步；`--meta-lr` 越小，漂移段越长。生产中应当在裁判修正完成前**暂停**actor 更新，而不是让两者赛跑。
- **以为温和偏好无害**：`--length-bias 0.3` 下质量也上升，但停在错误的风格；所有循环内指标正常。只有审计集上的一致率（70% vs 80%）能分出差别。
- **熵单独解读**：`win_H` 下降只说明在收敛，不说明收敛方向；要与 `agr_au` 同看。
- **忘了模拟器与论文的差别**：这里的元裁判有人工标签，是"有根基"的理想版；Wu et al. 的 meta-judge 没有标签，所以论文里人类一致率几乎没动（Spearman 0.315 → 0.326）。不要拿模拟器的 0.771 去推断论文方法的效果。
