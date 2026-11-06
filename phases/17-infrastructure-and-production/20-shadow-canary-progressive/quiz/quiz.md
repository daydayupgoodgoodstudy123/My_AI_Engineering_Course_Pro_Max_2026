# 测验 · 面向 LLMs 的 Shadow Traffic、金丝雀 Rollout 与渐进式部署（Shadow Traffic, Canary Rollout, and Progressive Deployment for LLMs）

> **阶段 17 · 基础设施与生产 · 第 20 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py)（另有 TypeScript 版 [code/main.ts](../code/main.ts)，本测验以 Python 版为准） ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | LLM 发布难在哪 | 没有单元测试、失败模式分散、信号滞后；离线 eval 提升 3% 不代表线上用户满意 |
| 2 | 三步顺序 | ① shadow（复制流量给候选、只记录不返回，零用户影响）→ ② canary（逐级放量 + 每级门禁）→ ③ 稳定后对"明显不同的方案"做 A/B |
| 3 | shadow 能抓什么 | 成本暴涨、输出长度回归、拒答变化、硬错误；抓不到用户可感知的质量差异——讲义："Shadow is a smoke test, not a quality test" |
| 4 | canary 阶梯 | 正文：1% → 10% → 25% → 50% → 75% → 100%（讲义摘要写的是从 10% 开始，前后不一致） |
| 5 | 五个门禁指标 | 时延百分位（P99 > 1.5× 基线）、每请求成本（> 1.2×）、错误/拒答率（> 2×）、输出长度分布（分布漂移）、用户负反馈率（> 1.5×） |
| 6 | 非确定性 | GPU 浮点非结合性 + batch 大小变化 + 采样，同样输入的准确率可相差多达 15%；"稳定"是指在预期方差内，门禁要设在噪声地板之上 |
| 7 | 成本是变量 | 讲义："A 20% better model can be 3x more expensive per call"；破坏单位经济性的"更好模型"同样要回滚 |
| 8 | 秒级回滚 | 策略放在 feature flag / 配置里，模型在 registry 中用固定 digest 引用；回滚 = 翻转开关 + 恢复旧 digest，几秒完成；需要重新部署就太慢了 |
| 9 | 工具 | Argo Rollouts / Flagger（K8s 渐进交付）、Istio 加权路由、KServe / Seldon（自带 canary）、LaunchDarkly / Flagsmith / Unleash（feature flag） |
| 10 | 样本量与节奏 | 门禁每 5–15 分钟检查一次；小流量阶段样本少、噪声大，每级停留时间要足够积累样本 |

### 核心技能（能动手做到）

- [ ] 区分 shadow、canary、A/B 三者的目的、用户影响和能发现的问题
- [ ] 为一次模型切换写出五个门禁的具体阈值，并说明阈值为何要高于噪声地板
- [ ] 读懂 `measure_stage` / `check_gates` / `rollout`，能预测某个注入回归会在哪一级被拦下
- [ ] 指出模拟器的噪声与流量比例无关、基线是静态常数等简化，并能改成"随样本量缩小的噪声 + 同期对照组"
- [ ] 设计一条 60 秒内完成的回滚路径，并列出所需基础设施
- [ ] 为 shadow 阶段写出成本/长度漂移的告警规则

---

## 二、基础自测（选择题）

**Q1.** 讲义推荐的 LLM 上线顺序是：

- A. 先 A/B 测试，再 shadow，最后 canary
- B. 直接 100% 切换，出问题再回滚
- C. 先 canary 到 50%，再 shadow
- D. shadow（零影响对比）→ canary（逐级放量 + 门禁）→ 对明显不同的方案做 A/B

**Q2.** 讲义列出的五个 canary 门禁指标是：

- A. GPU 利用率、显存、网络带宽、磁盘 IO、CPU
- B. 时延百分位、每请求成本、错误/拒答率、输出长度分布、用户反馈率
- C. BLEU、ROUGE、困惑度、准确率、F1
- D. QPS、并发数、连接数、Pod 数、节点数

**Q3.** 关于 shadow mode，说法正确的是：

- A. 候选模型的输出会返回给 1% 的用户
- B. shadow 可以证明新模型的质量更好
- C. 候选模型接收同样的请求、输出只记录不返回；能发现成本暴涨、长度回归、拒答变化和硬错误，但不是质量保证
- D. shadow 只需要记录时延，不需要记录 token 数

**Q4.** 讲义认为正确的回滚设计是：

- A. 翻转 feature flag 把流量切回，并把 registry 中的模型 digest 恢复为旧版本，几秒完成
- B. 重新构建镜像并走一遍 CI/CD，约 3 小时
- C. 让用户刷新页面
- D. 等下一次例行发布再修复

**Q5.** 运行 `code/main.py`，"Cost regression 25%" 场景在哪一级被拦下？

- A. 10%
- B. 1%（第一级），cost_per_req 门禁触发
- C. 50%
- D. 没有被拦下，直接晋升到 100%

**Q6.** "Quality silent + cost creep" 场景注入的是 `cost_mult=1.15, thumbs_down_mult=1.45`，都**低于**各自门禁（1.2 和 1.5），却在 25% 那一级被拦下。原因是：

- A. 25% 那一级的门禁阈值更严格
- B. 代码在 25% 时把两个回归相乘了
- C. 代码有 bug，门禁比较方向写反了
- D. 测量值带有 ±8% 的随机噪声，该级的噪声抽样让 `0.02 × 1.15 × 1.049 > 0.024`、`0.03 × 1.45 × 1.043 > 0.045`，两项同时越线

**Q7.** 讲义说同样输入的 LLM 准确率可能相差多达 15%，原因包括：

- A. GPU 浮点运算的非结合性（归约顺序随 batch 变化）、batch 大小变化、temperature > 0 的采样
- B. 模型权重每次加载都会随机初始化
- C. tokenizer 每次切分结果不同
- D. 网络丢包导致输出被截断

**Q8.** `measure_stage(stage, reg, seed)` 中的 `stage` 参数：

- A. 用来把噪声按流量比例缩放
- B. 决定该级使用哪组门禁阈值
- C. 根本没有被使用——1% 和 100% 两级的噪声幅度完全一样（都是 ±8%）
- D. 用来选择基线

---

## 三、动手 / 代码题

**Q9.** 每一级的噪声来自固定种子 `stage_seed(i) = 11 + 3i`，五个指标依次各抽一次 `rng.uniform(0.92, 1.08)`。实际抽到的乘数如下（顺序：latency、cost、error、output_len、thumbs_down）：

| 级别 | 种子 | latency | cost | error | output_len | thumbs |
|------|------|---------|------|-------|-----------|--------|
| 1% | 11 | 0.9924 | 1.0096 | 1.0679 | 0.9945 | 1.0013 |
| 10% | 14 | 0.9371 | 1.0324 | 1.0243 | 1.0705 | 0.9634 |
| 25% | 17 | 1.0035 | 1.0491 | 1.0737 | 0.9663 | 1.0426 |
| 50% | 20 | 1.0649 | 1.0298 | 1.0426 | 1.0647 | 0.9616 |
| 75% | 23 | 1.0680 | 1.0718 | 1.0628 | 0.9334 | 1.0147 |
| 100% | 26 | 1.0396 | 0.9524 | 0.9528 | 1.0161 | 0.9291 |

1. 只注入成本回归 `cost_mult = r`。r 至少多大时会在第一级（1%）就被拦下？
2. `r = 1.12`（低于 20% 门禁）会怎样？这说明了什么？
3. 讲义练习 1（注入 25% 成本回归）的答案是什么？

**Q10.** 当前代码里噪声与流量比例无关。请改写 `measure_stage`：假设总流量 `TOTAL_RPM = 600` 请求/分钟、每级观察窗口 `WINDOW_MIN = 15` 分钟，让每个指标的相对噪声标准差为 `0.3 / sqrt(样本数)`（样本数 = 流量比例 × TOTAL_RPM × WINDOW_MIN），并说明 1% 与 50% 两级的噪声差多少倍。

**Q11.** `check_gates` 的写法：

```python
def check_gates(metrics: dict) -> list[str]:
    breaches = []
    for k, mult in GATES.items():
        if metrics[k] > BASELINE[k] * mult:
            breaches.append(k)
    return breaches
```

1. 它和真实 canary 系统（如 Argo Rollouts 的 analysis）相比，最大的建模差异是什么？
2. 讲义对"输出长度分布"门禁的描述是什么？代码实现成了什么？输出里能看到这个指标吗？
3. 把它改成"与同一时间窗口内的 baseline 组对比"，写出新的函数签名与判断逻辑。

**Q12.** 讲义练习 4 与练习 5：

1. 你的 eval 显示 ±7% 的非确定性噪声，且 canary 组与 baseline 组各自都有这样的噪声。若不想因噪声误报，比值型门禁至少要设多大？
2. 写一条 shadow 阶段的告警规则：当候选模型每请求成本比生产高 40% 时触发（讲义的"40% cost spike"例子），给出指标、窗口、阈值和最小样本量条件。

---

## 四、面试高频题

**Q13.**（基础必考）shadow、canary、A/B 测试分别是什么？各自回答什么问题？

**Q14.**（原理深挖）LLM 的非确定性从哪里来？它如何影响 canary 门禁的设计？

**Q15.**（工程实践）设计一个 60 秒内完成的端到端回滚方案（讲义练习 3），需要哪些基础设施？

**Q16.**（场景设计）新模型离线 eval 准确率 +3%，但 shadow 显示每请求成本 +18%。你会怎么推进上线（讲义练习 2）？

**Q17.**（追问型）"你们的 canary 在 1% 流量跑了 10 分钟全部 PASS，就放到 10% 了"——这里有什么问题？

---

## 五、参考答案与解析

### Q1 — 答案：D

讲义摘要："(1) shadow mode ... (2) canary rollout ... (3) A/B testing for distinct alternatives after stability confirmed." A、C 的顺序都不对：A/B 需要先确认稳定；shadow 应该在任何用户暴露之前。B 正是讲义"The Problem"里那个毁掉周末的反例（成本 +40%、负反馈 +8%、回滚要 3 小时）。

### Q2 — 答案：B

讲义："Gate on 5 metrics at each step: Latency percentiles, Cost per request, Error / refusal rate, Output length distribution, User-feedback rate." A、D 是基础设施指标；C 是离线 NLP 指标，不能作为线上门禁。

### Q3 — 答案：C

讲义："Candidate receives the same requests as production; outputs are logged, not returned to users. Zero user impact." "Does NOT catch: quality delta users would perceive." A 描述的是 canary；B 错，shadow 只是冒烟测试；D 错，token 数（成本差异）是 shadow 必须记录的内容。

### Q4 — 答案：A

讲义："Rollback = revert flag + set pinned digest to previous. Seconds, not hours." "If your stack requires redeploy to rollback, fix that before rolling." B 正是讲义批评的做法（"Redeploy takes 3 hours"）；C、D 不是回滚。

### Q5 — 答案：B

实际运行：

```text
Cost regression 25%
  stage   1%  lat_p99=  893  cost=$0.0252  err= 2.1%  thumbs_dn= 3.0%  HALT (cost_per_req)
```

`0.02 × 1.25 × 1.0096 = 0.0252 > 0.02 × 1.2 = 0.024`，第一级就触发。这也是讲义练习 1 的答案。

### Q6 — 答案：D

25% 这一级（种子 17）的 cost 噪声乘数是 1.0491、thumbs 是 1.0426：

- 成本：`0.02 × 1.15 × 1.0491 ≈ 0.02413 > 0.024`；
- 负反馈：`0.03 × 1.45 × 1.0426 ≈ 0.04535 > 0.045`。

两项同时越线，输出 `HALT (cost_per_req,thumbs_down_rate)`。A 错：所有级别用同一组 `GATES`；B 错：每个指标独立计算；C 错：比较方向正确。这个场景说明：**接近阈值的回归会被噪声随机地拦下或放过**——在 1%、10% 两级它就通过了。

### Q7 — 答案：A

讲义："GPU FP non-associativity (floating-point reduction order varies by batch). Batch-size variance. Sampling (temperature > 0)." B 错：推理时权重是固定的；C 错：tokenizer 是确定性的；D 不是讲义所说的非确定性来源。

### Q8 — 答案：C

```python
def measure_stage(stage: float, reg: Regression, seed: int) -> dict:
    rng = random.Random(seed)
    noise = lambda v: v * rng.uniform(0.92, 1.08)
```

函数体里没有任何地方用到 `stage`。现实中 1% 流量的样本量只有 100% 的 1/100，测量噪声应大约是 10 倍（`√100`）；讲义也强调"1% traffic ... noisy for user feedback"。B、D 错：阈值和基线都是全局常数。

### Q9 — 参考答案

1. 第一级 cost 噪声乘数为 1.0096，触发条件 `r × 1.0096 > 1.2`，即 **r > 1.1886**。实际运行验证：`r = 1.19` 在 1% 被拦下，`r = 1.18` 在 10% 被拦下（该级乘数 1.0324，`1.18 × 1.0324 = 1.218 > 1.2`）。
2. `r = 1.12` 时，前 4 级都通过（最大乘数 1.0491，`1.12 × 1.0491 = 1.175`）；到 75% 一级乘数为 1.0718，`1.12 × 1.0718 = 1.2004 > 1.2`，**在 75% 被回滚**（已实际运行验证；`r = 1.11` 则全程通过）。一个低于门禁的 12% 成本回归，因为噪声被拦在了 75%——这是噪声导致的"误报"，而且发生在已经暴露了 75% 用户之后。它说明：
   - 门禁阈值与噪声幅度必须一起设计（阈值要高于噪声地板，讲义练习 4）；
   - 只做单次测量就决定"回滚"太脆弱，应要求连续 N 个窗口越线或用置信区间判断。
3. 练习 1：25% 成本回归在 **1%（第一级）** 就被拦下（见 Q5）。

### Q10 — 参考答案

```python
import math, random

TOTAL_RPM = 600
WINDOW_MIN = 15

def measure_stage(stage: float, reg: Regression, seed: int) -> dict:
    rng = random.Random(seed)
    n = max(1, int(stage * TOTAL_RPM * WINDOW_MIN))     # 本级样本数
    rel_sd = 0.3 / math.sqrt(n)                          # 相对噪声标准差
    noise = lambda v: v * max(0.0, rng.gauss(1.0, rel_sd))
    return {
        "latency_p99_ms": noise(BASELINE["latency_p99_ms"] * reg.latency_mult),
        "cost_per_req": noise(BASELINE["cost_per_req"] * reg.cost_mult),
        "error_rate": noise(BASELINE["error_rate"] * reg.error_mult),
        "output_len_p99": noise(BASELINE["output_len_p99"] * reg.output_len_mult),
        "thumbs_down_rate": noise(BASELINE["thumbs_down_rate"] * reg.thumbs_down_mult),
        "n_samples": n,
    }
```

- 1%：`n = 0.01 × 600 × 15 = 90`，`rel_sd ≈ 0.0316`；
- 50%：`n = 4500`，`rel_sd ≈ 0.00447`；
- 两者相差 `√(4500/90) = √50 ≈ 7.1` 倍。（已实际运行：100% 级 `n = 9000`、`rel_sd ≈ 0.0032`；注入 12% 成本回归时，各级测得的成本都稳定在 0.0225–0.0233 之间，不会再出现"75% 才被噪声推过线"的情况。）

注意：`0.3/√n` 只是演示用的简化模型。比例类指标（错误率、负反馈率）的标准误应按 `√(p(1−p)/n)` 计算，在 p = 3% 时相对噪声远大于此；P99 时延的估计在小样本下更不稳定（90 个样本里 P99 只由最大的一两个值决定）。这正是讲义"Progressions should pause long enough to accumulate enough samples at each step"的原因。

### Q11 — 参考答案

1. **对比对象是静态常数 `BASELINE`**，而不是同一时间窗口内的生产组。真实系统中，时段（白天/夜间）、流量组成、上游提供商状况都会让指标漂移；canary 与 baseline 同期对比才能抵消这些共同因素。Argo Rollouts / Flagger 的分析通常就是查询同一时间段内两个版本的指标。
2. 讲义："Output length distribution — mean + P99. Breach: distributional shift." 代码只实现为 `output_len_p99 > 1.4 × 450`，只看 P99、不看均值和分布形状；而且 `rollout()` 打印时**没有输出** `output_len_p99`，这个门禁触发时只能从 HALT 标签里看到。另外讲义的"error / refusal rate"在代码里只有一个 `error_rate`，没有单独的拒答率。
3. 改写示例：

```python
def check_gates_vs_control(canary: dict, control: dict, min_samples: int = 200) -> list[str]:
    if canary.get("n_samples", 0) < min_samples:
        return []                         # 样本不足：不判定，继续等待
    breaches = []
    for k, mult in GATES.items():
        if control[k] > 0 and canary[k] / control[k] > mult:
            breaches.append(k)
    return breaches
```

   `control` 由同一窗口、同样方式测量的生产组得到；更严格的做法是对比值计算置信区间，只有区间下界超过阈值才判定越线。

### Q12 — 参考答案

1. 若 canary 与 baseline 各自有 ±7% 的噪声，最坏情况下二者之比可达 `1.07 / 0.93 ≈ 1.15`。因此比值型门禁至少要高于 **1.15**，留些余量取 1.2 左右；"P99 > 1.5×"、"负反馈 > 1.5×"等门禁已远在噪声之上。skill 文件也写道 "Gates tighter than 15% variance. Refuse"。若想检测更小的回归（如 10%），只能靠增加样本量缩小噪声，而不是收紧阈值。
2. shadow 成本告警示例：

```text
指标：mean(cost_per_req{variant="candidate"}) / mean(cost_per_req{variant="prod"})
     （同一批被复制的请求，两边逐请求配对）
窗口：滚动 1 小时，每 5 分钟评估一次
条件：比值 > 1.4 且 配对样本数 ≥ 500，连续 2 个评估周期满足
动作：告警并阻止进入 canary；附带 token 输入/输出分解，定位是输出变长还是单价变高
```

   因为 shadow 是同一请求的配对比较，噪声远小于独立分组，可以更早、更准地发现成本差异。skill 文件的 shadow 告警线是"> 20% cost shift, > 30% output length shift"，比 40% 更敏感。

   另外注意讲义"Metrics cadence"一节的说法存在歧义："1% traffic with 10 req/min gives 50-150 data points per window"——若 10 req/min 是总流量，1% 只有 0.1 req/min，5–15 分钟窗口里只有 0.5–1.5 个样本；只有当 10 req/min 指的是 canary 本身的流量时，50–150 才成立。

### Q13 — 参考回答要点

- **Shadow**：复制生产请求给候选模型，输出只记录不返回；零用户影响。回答"候选在真实流量上会不会出明显问题"（成本、长度、拒答、错误、时延）。不能回答用户是否更喜欢。
- **Canary**：真实用户逐级放量（1% → 10% → 25% → 50% → 75% → 100%），每级检查门禁，越线即回滚。回答"在真实用户暴露下是否稳定、没有回归"。
- **A/B**：稳定之后，对明显不同的方案做随机对照实验（常在 50/50），回答"用户/业务指标是否真的更好"（下一节内容）。
- **何时可以跳过 A/B**：讲义——只是"改进版"且 canary 全部通过，可以直接到 100%；行为、成本曲线、语气明显不同时才需要 A/B。
- 加分点：三者不是互斥的，shadow 在离线 eval 之后、canary 之前；回滚能力是三者的共同前提。

### Q14 — 参考回答要点

- **来源**：GPU 浮点加法非结合，归约顺序随 batch 组成和 kernel 选择变化；同一 prompt 在不同 batch 大小下数值略有不同；temperature > 0 的采样；还有上游提供商的静默更新。讲义：同样输入准确率可相差多达 15%。
- **对门禁的影响**：
  - "稳定"不等于"与基线相同"，而是"在预期方差内"；
  - 阈值要高于噪声地板（否则误报会阻断正常发布）；
  - 小流量阶段样本少，噪声更大，需要更长的停留时间或更宽的阈值；
  - 用同期对照组和置信区间，而不是单点比较；要求连续多个窗口越线再回滚。
- **工程手段**：固定 temperature 与 seed 做离线回归；监控长度、拒答等分布指标而不只是均值；对质量类指标用更大的样本与更长窗口。
- 加分点：结合本节代码说明——12% 的成本回归在 ±8% 噪声下于 75% 被误拦，而 1% 级别的噪声本应更大。

### Q15 — 参考回答要点

- **策略与模型解耦**：模型版本通过 registry 的不可变 digest 引用（不是 `latest` 标签）；路由比例放在 feature flag 系统或网关配置里。
- **数据面支持即时切流**：服务网格（Istio 加权路由）或 AI 网关（阶段 17 · 19）读取 flag，秒级生效；旧版本实例在放量期间保持热备（不要缩容到 0）。
- **自动化**：Argo Rollouts / Flagger 的 analysis 越线时自动回滚；也提供一键人工回滚。
- **三个动作**（skill 文件）：翻转 flag → 恢复 pinned digest → 验证（指标回到基线）。目标 60 秒以内。
- **其他前提**：配置变更有审计与权限；回滚演练（skill："rehearse rollback once before first real deploy"）；回滚后保留候选的日志用于复盘；提示词模板、路由策略同样版本化。
- 常见误区：回滚依赖 CI/CD 重新构建镜像；旧版本已缩容导致冷启动（阶段 17 · 10）。

### Q16 — 参考回答要点

- **先判断政策**：成本门禁 1.2×，+18% 在门禁内但接近阈值；考虑噪声，可能随机越线（参考 Q9 的 1.12 例子）。
- **路径一（质量优先）**：+3% 准确率能带来足够的业务价值（例如解决率提升、工单减少），则：
  - 显式把成本门禁调整为 1.25× 并记录决策；
  - canary 后做 A/B，以"每个已解决任务的成本"等单位经济性指标判断；
  - 同时寻找降本手段（路由：简单请求仍走旧模型，阶段 17 · 16；缓存；批处理）。
- **路径二（成本优先）**：单位经济性不允许 +18%，则不全量；只对高价值请求类别启用，或先优化提示词/输出长度再上线。
- **无论哪条路**：shadow 中拆解成本来源（输入 token、输出 token、单价）；A/B 的主指标与护栏指标事先写清（下一节）。
- 加分点：引用讲义"A 20% better model can be 3x more expensive per call"，强调成本必须作为门禁而不是事后发现。

### Q17 — 参考回答要点

- **样本量不足**：1% 流量 10 分钟可能只有几十个甚至几个请求；P99 时延、负反馈率这类指标在这个样本量下几乎没有统计意义，"全部 PASS"不代表没有回归。
- **信号滞后**：用户负反馈、工单等信号需要时间才会出现；讲义说 LLM 发布的难点之一就是"delayed signals"。
- **噪声**：门禁的单次判断受噪声影响；本节代码中噪声与流量比例无关，掩盖了这个问题。
- **改进**：按"达到最小样本量"而不是"固定时间"推进；小流量阶段延长停留（skill："If traffic volume is <100 req/hour, require extended canary stages"）；对比同期对照组；关键指标要求置信区间；1% 阶段主要用于发现硬错误，质量判断要等更大流量。
- 加分点：给出估算——要以 80% 功效、α = 0.05 检测 3% → 4.5% 的负反馈率变化，每组约需 2,514 个样本（用下一节 `fixed_sample_size(0.03, 0.5)` 实际算得）；1% 流量 10 分钟远远达不到。

---

## 六、关联知识点

### 前置知识
- [阶段 17 · 13 LLM Observability 技术栈选型](../../13-llm-observability/docs/zh.md)：门禁指标从哪里来。
- [阶段 17 · 08 Inference 指标：TTFT、TPOT、ITL、Goodput、P99](../../08-inference-metrics-goodput/docs/zh.md)：时延百分位门禁的含义。
- [阶段 11 · 10 Evaluation 与 LLM 应用测试](../../../11-llm-engineering/10-evaluation/docs/zh.md)：离线 eval 是 shadow 之前的第一道关。
- [阶段 17 · 03 Kubernetes 上的 GPU Autoscaling](../../03-gpu-autoscaling-kubernetes/docs/zh.md)：Argo Rollouts / Flagger 所在的 K8s 环境。

### 本节被哪些后续内容用到
- [阶段 17 · 21 对 LLM Features 进行 A/B 测试](../../21-ab-testing-llm-features/docs/zh.md)：canary 通过后的 A/B 步骤。
- [阶段 17 · 19 AI 网关](../../19-ai-gateways/docs/zh.md)：在网关层做流量切分与灰度。
- [阶段 17 · 23 AI 的 SRE：多 Agent Incident Response、操作手册与预测性检测](../../23-sre-for-ai/docs/zh.md)：回滚演练与事故处理。
- [阶段 17 · 24 LLM 生产环境中的混沌工程](../../24-chaos-engineering-llm/docs/zh.md)：验证回滚路径在故障下是否可靠。
- [阶段 17 · 16 将模型路由作为降低成本的基本手段](../../16-model-routing/docs/zh.md)：成本门禁不过时的降本手段。

### 延伸关键词
`shadow traffic` · `canary analysis` · `progressive delivery` · `Argo Rollouts` · `Flagger` · `Istio weighted routing` · `KServe` · `feature flags` · `model registry digest` · `noise floor` · `GPU non-determinism` · `rollback drill` · `sample size per stage`
