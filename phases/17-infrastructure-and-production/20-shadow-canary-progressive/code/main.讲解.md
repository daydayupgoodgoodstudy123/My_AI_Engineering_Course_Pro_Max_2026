# 代码讲解 · main.py

> **所属小节**：阶段 17 · 基础设施与生产 · 第 20 节 面向 LLMs 的 Shadow Traffic、金丝雀 Rollout 与渐进式部署 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`dataclasses`、`random`）。同目录另有 TypeScript 版 `main.ts`，本讲解只覆盖 Python 版。

---

## 1. 这份代码在考察什么

代码模拟一次 canary 发布：候选模型的流量按 `1% → 10% → 25% → 50% → 75% → 100%` 六级推进，每一级"测量"五个指标并与基线比较，任何一个越过门禁就回滚，否则晋升。通过注入不同的回归（成本、时延、负反馈等），观察发布会在哪一级被拦下。

对应讲义：

1. **canary 阶梯**与**五个门禁指标**（时延 P99、每请求成本、错误率、输出长度 P99、负反馈率）；
2. **门禁倍数**：P99 > 1.5×、成本 > 1.2×、错误 > 2×、负反馈 > 1.5×（代码另给输出长度 1.4×）；
3. **非确定性**：每次测量带 ±8% 噪声；
4. **秒级回滚**：越线后打印 "ROLLBACK (policy flip, pinned model reverted)"。

> 一句话：**用"乘性回归 × 随机噪声 vs 固定倍数门禁"的循环，演示 canary 如何逐级放量并在越线时停下**。要注意它的噪声与流量比例无关、基线是静态常数，因此"小流量阶段样本少、噪声大"这一讲义重点没有被体现。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `STAGES` | 列表常数 | `[0.01, 0.10, 0.25, 0.50, 0.75, 1.00]` | canary 阶梯 |
| `BASELINE` | 字典常数 | 五个指标的基线值：P99 900 ms、$0.02、2%、450 token、3% | 生产基线 |
| `GATES` | 字典常数 | 每个指标允许的最大倍数 | 门禁 |
| `Regression` | `@dataclass` | 五个乘数，默认全为 1.0 | 注入的回归 |
| `measure_stage(stage, reg, seed)` | 函数 | 基线 × 回归 × 噪声（±8%） | 一级的测量 |
| `check_gates(metrics)` | 函数 | 返回越线指标名列表 | 门禁判断 |
| `rollout(name, reg)` | 函数 | 逐级测量、打印、越线即回滚 | 发布流程 |
| `stage_seed(i)` | 函数 | `11 + 3i`，每级固定种子 | 可复现噪声 |
| `main()` | 函数 | 依次运行 6 个场景 | 入口 |

数据流：`main()` → `rollout(场景名, Regression(...))` → 对每一级 `measure_stage(...)` → `check_gates(...)` → 打印 `PASS` 或 `HALT` → 越线即 `return`，全部通过则打印 `PROMOTED`。

---

## 3. 逐段精讲

### 3.1 阶梯、基线与门禁

```python
STAGES = [0.01, 0.10, 0.25, 0.50, 0.75, 1.00]

BASELINE = {
    "latency_p99_ms": 900,
    "cost_per_req": 0.02,
    "error_rate": 0.02,
    "output_len_p99": 450,
    "thumbs_down_rate": 0.03,
}

GATES = {
    "latency_p99_ms": 1.5,
    "cost_per_req": 1.2,
    "error_rate": 2.0,
    "output_len_p99": 1.4,
    "thumbs_down_rate": 1.5,
}
```

- `STAGES` 与讲义正文一致（讲义开头摘要写的是 "10% → 25% → 50% → 75% → 100%"，少了 1%，前后不一致）。
- 两个字典用**相同的键**，`check_gates` 遍历 `GATES` 时用同一个键去取 `BASELINE` 和测量值。
- 门禁换算成绝对阈值：P99 1350 ms、成本 $0.024、错误率 4%、输出长度 630 token、负反馈率 4.5%。
- 讲义对输出长度的门禁是"distributional shift"（分布漂移，看均值 + P99），代码简化为"P99 > 1.4×"；讲义的"error / refusal rate"在代码里只有 `error_rate`，没有拒答率。

### 3.2 回归描述：dataclass 默认值

```python
@dataclass
class Regression:
    latency_mult: float = 1.0
    cost_mult: float = 1.0
    error_mult: float = 1.0
    output_len_mult: float = 1.0
    thumbs_down_mult: float = 1.0
```

- 所有字段都有默认值 1.0（无回归），所以可以只写想注入的那一项：`Regression(cost_mult=1.25)`。
- 乘性模型：候选的指标 = 基线 × 乘数。真实回归往往不是简单倍数（例如时延只在长 prompt 上变差），但作为教学足够。

### 3.3 测量：基线 × 回归 × 噪声

```python
def measure_stage(stage: float, reg: Regression, seed: int) -> dict:
    rng = random.Random(seed)
    noise = lambda v: v * rng.uniform(0.92, 1.08)
    return {
        "latency_p99_ms": noise(BASELINE["latency_p99_ms"] * reg.latency_mult),
        "cost_per_req": noise(BASELINE["cost_per_req"] * reg.cost_mult),
        ...
    }
```

- `noise` 是一个 lambda：把值乘以 `[0.92, 1.08]` 内的均匀随机数，即 ±8% 的乘性噪声，用来模拟讲义的"非确定性"。
- 五个指标按字典书写顺序依次调用 `noise`，每次从同一个 `rng` 抽一个数；因此每个指标对应固定位置的随机数。
- ⚠️ **`stage` 参数没有被使用**：1% 与 100% 的噪声幅度一样。现实中 1% 流量的样本只有 1/100，测量噪声应大约是 √100 = 10 倍；讲义 "Metrics cadence" 一节正是强调小流量阶段噪声大、需要停留更久。
- ⚠️ 种子只由级别决定（`stage_seed(i)`），所以**所有场景在同一级抽到同样的噪声**。这让场景之间可以直接比较（差异只来自回归乘数），也意味着结果完全确定，不能体现"同一回归有时拦下、有时放过"的随机性，除非你自己换种子。

### 3.4 门禁判断

```python
def check_gates(metrics: dict) -> list[str]:
    breaches = []
    for k, mult in GATES.items():
        if metrics[k] > BASELINE[k] * mult:
            breaches.append(k)
    return breaches
```

- `dict.items()` 同时取出键和值；越线的指标名放进列表返回。空列表在布尔上下文里为假，`rollout` 用 `if not breaches` 判断是否通过。
- 只检查"变大"的方向——这五个指标都是越小越好，所以合理；若加入"任务成功率"这类越大越好的指标，就需要反向比较。
- ⚠️ 对比对象是静态的 `BASELINE`，而不是同一时间窗口的生产组；真实 canary 分析（Argo Rollouts / Flagger）会同期比较两个版本，以抵消时段与流量组成的变化。
- ⚠️ 单次测量越线就回滚，没有"连续 N 个窗口"或置信区间——在噪声下容易误报（见第 6 节）。

### 3.5 发布流程

```python
def rollout(name: str, reg: Regression) -> None:
    print(f"\n{name}")
    ...
    for i, stage in enumerate(STAGES):
        metrics = measure_stage(stage, reg, seed=stage_seed(i))
        breaches = check_gates(metrics)
        status = "PASS" if not breaches else f"HALT ({','.join(breaches)})"
        pct = int(stage * 100)
        print(f"  stage {pct:3}%  "
              f"lat_p99={metrics['latency_p99_ms']:5.0f}  "
              f"cost=${metrics['cost_per_req']:.4f}  "
              f"err={metrics['error_rate']*100:4.1f}%  "
              f"thumbs_dn={metrics['thumbs_down_rate']*100:4.1f}%  "
              f"{status}")
        if breaches:
            print(f"  → ROLLBACK (policy flip, pinned model reverted)")
            return
    print("  → PROMOTED to 100%")
```

- `','.join(breaches)` 把多个越线指标拼成一个字符串，如 `cost_per_req,thumbs_down_rate`。
- `int(stage * 100)`：0.01 × 100 = 1.0 → 1。这里浮点误差不会造成问题，但如果阶梯是 0.29 这类值，`int(0.29 * 100)` 会得到 28（`0.29 * 100 = 28.999999999999996`），用 `round` 更稳妥。
- ⚠️ 打印时**没有输出 `output_len_p99`**，只有当它越线时才会在 HALT 标签中出现。
- "ROLLBACK" 只是一行打印，没有建模回滚耗时，也没有建模"每级停留多久"——讲义的"秒级回滚 vs 小时级重新部署"在代码中只是文字。
- `return` 直接结束函数，后面的 `PROMOTED` 不会打印；所有级别都通过时 `for` 循环正常结束才会打印——也可以用 `for ... else` 表达。

### 3.6 六个场景

```python
    rollout("Clean promotion", Regression())
    rollout("Small cost regression (10%) — within gate", Regression(cost_mult=1.10))
    rollout("Cost regression 25%", Regression(cost_mult=1.25))
    rollout("Latency regression 80%", Regression(latency_mult=1.80))
    rollout("Thumbs-down regression 60%", Regression(thumbs_down_mult=1.60))
    rollout("Quality silent + cost creep", Regression(cost_mult=1.15, thumbs_down_mult=1.45))
```

- 前五个场景的回归要么明显低于门禁（10%）、要么明显高于门禁（25%、80%、60%），结果没有悬念。
- 第六个场景两项都**低于**门禁（1.15 < 1.2、1.45 < 1.5），名字暗示"静默的质量下降 + 成本缓慢爬升"，用来说明多个"差一点越线"的回归叠加时会发生什么——在本代码中，它是被噪声推过线的。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 乘性回归 + ±8% 均匀噪声 | 直观、参数少 | 噪声与样本量无关；生产中噪声 ∝ 1/√样本数，比例指标按 `√(p(1−p)/n)` |
| 每级固定种子 | 结果可复现、场景可对比 | 掩盖了"同一回归时拦时放"的随机性；可以多种子重复，统计拦截概率 |
| 与静态 BASELINE 比较 | 实现简单 | 生产应与同期 baseline 组比较，或用 A/A 校准 |
| 单次越线即回滚 | 保守 | 误报多；生产常要求连续多个窗口越线、或基于置信区间判定 |
| 门禁为固定倍数 | 与讲义一致 | 阈值需高于噪声地板（讲义练习 4）；不同指标的噪声不同，阈值应分别设计 |
| 输出长度只看 P99、不打印 | 代码短 | 讲义要求看分布漂移；生产中可用均值 + P99 + 分布距离（如 KS 检验） |
| 回滚只是打印 | 演示流程 | 真正的价值在于回滚基础设施（flag + pinned digest），代码不涉及 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass` + 字段默认值 | `latency_mult: float = 1.0` | 构造时可只传部分字段：`Regression(cost_mult=1.25)` |
| dataclass 自动 `__repr__` | 本文件手动拼了 "Regression: latency=..." | 也可以直接 `print(reg)` 得到 `Regression(latency_mult=1.0, ...)` |
| `lambda` | `noise = lambda v: v * rng.uniform(0.92, 1.08)` | 匿名单表达式函数；它"捕获"了外层的 `rng` |
| 闭包与共享状态 | 每次调用 `noise` 都推进同一个 `rng` | 调用顺序决定每个指标拿到哪个随机数 |
| 字典字面量 | `BASELINE = {...}`、`return {...}` | 用字符串键组织多个指标 |
| `dict.items()` | `for k, mult in GATES.items():` | 同时遍历键和值 |
| 返回列表、空列表为假 | `if not breaches` | `[]` 在条件判断中为 False |
| 条件表达式 | `"PASS" if not breaches else f"HALT (...)"` | 一行内选择两个值之一 |
| `str.join` | `','.join(breaches)` | 用逗号连接字符串列表 |
| `enumerate` | `for i, stage in enumerate(STAGES):` | 同时拿到下标（用于算种子）和元素 |
| 提前 `return` | 越线后 `return` | 结束整个函数，跳过后续级别 |
| f-string 格式符 | `{pct:3}`、`{metrics['latency_p99_ms']:5.0f}`、`{...:.4f}`、`{metrics['error_rate']*100:4.1f}%` | 宽度、小数位；花括号内可写表达式；`$` 和 `%` 是普通字符 |
| 多行 f-string 拼接 | `print(f"..." f"..." f"...")` | 相邻字符串字面量会自动拼接 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行 `main()` |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，不到 0.1 秒，结果完全可复现）：

```text
Clean promotion
  stage   1%  lat_p99=  893  cost=$0.0202  err= 2.1%  thumbs_dn= 3.0%  PASS
  stage  10%  lat_p99=  843  cost=$0.0206  err= 2.0%  thumbs_dn= 2.9%  PASS
  stage  25%  lat_p99=  903  cost=$0.0210  err= 2.1%  thumbs_dn= 3.1%  PASS
  stage  50%  lat_p99=  958  cost=$0.0206  err= 2.1%  thumbs_dn= 2.9%  PASS
  stage  75%  lat_p99=  961  cost=$0.0214  err= 2.1%  thumbs_dn= 3.0%  PASS
  stage 100%  lat_p99=  936  cost=$0.0190  err= 1.9%  thumbs_dn= 2.8%  PASS
  → PROMOTED to 100%

Small cost regression (10%) — within gate
  ...（六级全部 PASS，成本在 $0.0210–0.0236 之间）
  → PROMOTED to 100%

Cost regression 25%
  stage   1%  lat_p99=  893  cost=$0.0252  err= 2.1%  thumbs_dn= 3.0%  HALT (cost_per_req)
  → ROLLBACK (policy flip, pinned model reverted)

Latency regression 80%
  stage   1%  lat_p99= 1608  cost=$0.0202  err= 2.1%  thumbs_dn= 3.0%  HALT (latency_p99_ms)
  → ROLLBACK (policy flip, pinned model reverted)

Thumbs-down regression 60%
  stage   1%  lat_p99=  893  cost=$0.0202  err= 2.1%  thumbs_dn= 4.8%  HALT (thumbs_down_rate)
  → ROLLBACK (policy flip, pinned model reverted)

Quality silent + cost creep
  stage   1%  lat_p99=  893  cost=$0.0232  err= 2.1%  thumbs_dn= 4.4%  PASS
  stage  10%  lat_p99=  843  cost=$0.0237  err= 2.0%  thumbs_dn= 4.2%  PASS
  stage  25%  lat_p99=  903  cost=$0.0241  err= 2.1%  thumbs_dn= 4.5%  HALT (cost_per_req,thumbs_down_rate)
  → ROLLBACK (policy flip, pinned model reverted)
```

逐项解读：

- **各级噪声乘数是固定的**：我们按 `stage_seed(i)` 复现了每级抽到的数（顺序为 latency、cost、error、output_len、thumbs），例如 1% 级为 `0.9924, 1.0096, 1.0679, 0.9945, 1.0013`，25% 级为 `1.0035, 1.0491, 1.0737, 0.9663, 1.0426`，75% 级的 cost 为 1.0718。所有场景共用这组数，所以"Clean promotion"与"Small cost regression"每一级的时延、错误率完全相同，成本恰好差 10%。
- **明显回归在第一级就被拦下**：25% 成本（`0.02 × 1.25 × 1.0096 = 0.0252 > 0.024`）、80% 时延（`900 × 1.8 × 0.9924 = 1608 > 1350`）、60% 负反馈（`0.03 × 1.6 × 1.0013 = 4.8% > 4.5%`）。这也是讲义练习 1 的答案：25% 成本回归在 1% 就停止。
- **"Quality silent + cost creep" 在 25% 被拦下**：成本 `0.02 × 1.15 × 1.0491 = 0.02413 > 0.024`，负反馈 `0.03 × 1.45 × 1.0426 = 4.535% > 4.5%`。两项各自都低于门禁，是噪声把它们推过了线；在 1%、10% 两级（噪声较小）则通过了。
- **门禁的"灰色地带"**：我们扫描了只注入成本回归的情况——`r = 1.11` 全程通过；`r = 1.12`～`1.14` 在 **75%** 级被拦（该级 cost 乘数 1.0718）；`1.15`～`1.16` 在 25% 被拦；`1.18` 在 10% 被拦；`r ≥ 1.19` 在 1% 被拦。也就是说，一个 12% 的回归（低于 20% 门禁）会在已经暴露 75% 用户之后被"误报"回滚。输出长度同理：1.35 倍的长度回归会在 10% 级被拦（该级乘数 1.0705）。
- **输出长度不可见**：表中没有 `output_len_p99` 列；例如 10% 级的测量值其实是 `450 × 1.0705 ≈ 481.7`。

---

## 7. 动手改一改

1. **讲义练习 1**：在 `main()` 末尾加入 `rollout("Cost 25% (exercise)", Regression(cost_mult=1.25))`，确认在 1% 停下；再扫描 `cost_mult` 从 1.10 到 1.25，打印每个值的停止级别（复现第 6 节的灰色地带）。
2. **让噪声随流量变化**：使用 `stage` 参数，令相对噪声 ∝ `1/√(stage × 总请求数)`（参考测验 Q10），观察小流量阶段的误报/漏报如何变化。
3. **多种子统计**：对同一回归用 200 个不同的种子运行，统计"在第几级被拦下"的分布，以及"最终被晋升"的概率——这才是门禁的真实"检测功效"。
4. **同期对照组**：每一级同时测量 baseline 组（无回归、独立噪声），用 `canary / control` 的比值判断越线，并要求连续 2 次越线才回滚。
5. **打印输出长度并加入拒答率**：给 `BASELINE`、`GATES`、`Regression` 增加 `refusal_rate`，补齐讲义的"error / refusal"。
6. **讲义练习 4**：把噪声改为 ±7%，计算并设置不会误报的门禁倍数（提示：两组各 ±7% 时最坏比值约 1.15），再验证一个 20% 的回归能否被稳定拦下。

---

## 8. 常见坑

- **小流量阶段相信"全部 PASS"**：1% 流量的样本量很小，PASS 往往只是"还看不出来"；要按最小样本量而不是固定时间推进。
- **门禁设在噪声地板之内**：会频繁误报，团队很快就会习惯性忽略或关闭门禁。
- **和静态基线比**：白天/夜间、工作日/周末的指标差异可能超过门禁，应与同期对照组比较。
- **只看均值或只看 P99**：输出长度、时延这类分布型指标要同时看中心和尾部。
- **把成本当常量**：讲义强调成本是变量，"更好"的模型可能贵 3 倍；成本必须是门禁之一。
- **回滚依赖重新部署**：代码里一行打印就"回滚"了，现实中只有 flag + pinned digest 的架构才能做到秒级。
- **`int(x * 100)` 截断**：浮点乘法可能得到 28.999…，转换百分比时用 `round`。
