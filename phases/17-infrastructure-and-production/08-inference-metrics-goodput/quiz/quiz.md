# 测验 · Inference 指标：TTFT、TPOT、ITL、Goodput、P99（Inference Metrics — TTFT, TPOT, ITL, Goodput, P99）

> **阶段 17 · 基础设施与生产 · 第 08 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | TTFT | `TTFT = queue_time + network_request + prefill_time`；长 prompt 时 prefill 主导（讲义：Llama-3.3-70B FP8 / H100 上 32k prompt 纯 prefill 约 800 ms） |
| 2 | TPOT = ITL | time per output token、inter-token latency、decode latency per token 是同一个量：首 token 之后相邻两个流式 token 的间隔，反映 memory-bound 的 decode 成本 |
| 3 | E2E | `E2E = TTFT + TPOT × output_tokens + network_response`；长输出（>500 token）由 TPOT 主导，短输出长 prompt 由 TTFT 主导，应按输出长度分桶报告 |
| 4 | Throughput | `total_output_tokens / elapsed_time`，反映集群效率，不反映单个请求是否健康 |
| 5 | Goodput | 同时满足 `TTFT ≤ a AND TPOT ≤ b AND E2E ≤ c` 的请求占比；任何一项违约该请求就不算"好" |
| 6 | 均值是错误的统计量 | LLM 延迟右偏；讲义例子：均值 TPOT 9 ms、P99 TPOT 65 ms。始终报 P50 / P90 / P99，优化 P99 |
| 7 | 测量陷阱 | GenAI-Perf 计算 ITL 时排除 TTFT（从第 2 个 token 开始），LLMPerf 包含 TTFT；同一请求两者可差 7.07 ms vs 12.00 ms |
| 8 | 参考数字 | 讲义：Llama-3.1-8B-Instruct / TRT-LLM，mean TTFT 162 ms、mean TPOT 7.33 ms、mean E2E 1,093 ms，P99 TPOT 10–25 ms（取决于 chunked prefill 配置） |
| 9 | 典型 SLO | 70B 消费级聊天：TTFT P99 ≤ 800 ms、TPOT P99 ≤ 25 ms、E2E P99 ≤ 3 s（<300 token 输出）、goodput ≥ 99% |
| 10 | 测量方法 | 真实或拟真流量（输入/输出长度带标准差）、2 倍峰值并发、30–50 次迭代合并取分位数，发布时写明工具、版本、模型、硬件、并发与 prompt 分布 |

### 核心技能（能动手做到）

- [ ] 给定一条请求的时间戳，手算 TTFT、E2E，以及 GenAI-Perf 与 LLMPerf 两种口径的 TPOT
- [ ] 写出 goodput 的多约束计算，并能指出某次结果里是哪一个约束在"卡脖子"
- [ ] 区分"每请求平均 TPOT 的 P99"与"逐 token ITL 的 P99"，解释为什么前者会把尾部抹平
- [ ] 为不同交互形态（流式聊天、语音、Agent）写出有依据的 SLO
- [ ] 按 skill 文件设计一个以 goodput 为闸门的 CI/CD 压测方案（并发扫描、工具声明、样本量）
- [ ] 读懂并修正本节代码中 TPOT 分母与 decode 样本数不一致的问题

---

## 二、基础自测（选择题）

**Q1.** 按讲义的定义，TTFT 由哪几部分组成？

- A. prefill 时间 + 第一个 decode step 的时间
- B. 模型加载时间 + prefill 时间
- C. 排队时间 + 请求网络时间 + prefill 时间
- D. TPOT × 输出长度

**Q2.** 一个请求 TTFT = 500 ms，共输出 100 个 token，首 token 之后的 decode 共耗时 700 ms。GenAI-Perf 与 LLMPerf 报告的 ITL 分别是：

- A. 7.07 ms 与 12.00 ms
- B. 7.00 ms 与 12.00 ms
- C. 12.00 ms 与 7.07 ms
- D. 两者都是 7.07 ms，只是名称不同

**Q3.** 关于 goodput，下列说法正确的是：

- A. goodput = 总输出 token / 总耗时，与 throughput 同义
- B. goodput = 满足 P99 TTFT 的请求占比
- C. goodput 越高，throughput 一定越高
- D. goodput = 同时满足 TTFT、TPOT、E2E 全部 SLO 约束的请求占比，任一约束违约即不计入

**Q4.** 讲义说"mean is the wrong statistic"，最根本的原因是：

- A. 流式输出无法计算均值
- B. LLM 延迟分布右偏，少量尾部请求（用户会经常碰到）被均值掩盖
- C. 均值只适用于 prefill，不适用于 decode
- D. GenAI-Perf 不支持输出均值

**Q5.** 讲义练习 3 问"为什么 chunked prefill 保护的是 P99 TPOT 而不是 mean TPOT"。最合适的解释是：

- A. 长 prefill 偶尔会和正在 decode 的序列挤在同一步里，让少数 token 的间隔飙到 50 ms；把 prefill 切块后这种尖刺被削平，而尖刺本来就很少，对均值影响很小
- B. chunked prefill 会让每个 decode step 都变快，所以均值也大幅下降
- C. chunked prefill 只影响 TTFT，与 TPOT 无关
- D. chunked prefill 把 KV cache 量化成 FP8，降低了尾延迟

**Q6.** 本节代码在 "target TTFT<500 TPOT<15 E2E<2000" 下的 goodput 为 75.95%。逐约束统计 2000 个请求，违约最多的是哪一项？

- A. TTFT（排队时间指数分布的长尾）
- B. TPOT（2% 的 token 有 3–8 倍尖刺）
- C. E2E（输出最多 300 token × 约 7.6 ms，长输出天然超过 2 s）
- D. 三者违约次数大致相同

**Q7.** 本节代码打印 P99 TPOT = 8.99 ms，而 KEY FINDING 写的是"P99 TPOT ~25–40 ms"。造成差异的原因是：

- A. 代码用的是 LLMPerf 口径
- B. 代码的 `percentiles` 函数实现错误
- C. 随机种子不同
- D. 代码先对每个请求的所有 token 求平均 TPOT，再在请求之间取 P99；逐 token 的尖刺被 50–300 个 token 平均掉了（逐 token ITL 的 P99 实际约 37.5 ms）

**Q8.** 某请求 prompt 很短、输出 800 个 token。它的 E2E 主要由什么决定？

- A. TTFT
- B. TPOT × 输出长度
- C. 网络回包时间
- D. 排队时间

---

## 三、动手 / 代码题

**Q9.** 阅读 `RequestTrace` 与 `synth_workload` 的关键片段：

```python
    @property
    def ttft_ms(self) -> float:
        return self.queue_ms + self.prefill_ms

    @property
    def e2e_ms(self) -> float:
        return self.ttft_ms + sum(self.decode_ms_per_token)

    def tpot_genaiperf(self) -> float:
        """GenAI-Perf: ITL starts from token 2."""
        if self.output_tokens <= 1:
            return 0.0
        return sum(self.decode_ms_per_token) / (self.output_tokens - 1)
# ...
        decodes = []
        for _ in range(output_tokens):
            ...
            decodes.append(t)
```

1. 一个输出 `n` 个 token 的请求，首 token 在 TTFT 时刻到达，之后应有几个 token 间隔？代码生成了几个 decode 样本？
2. 这会让 `tpot_genaiperf()` 系统性地偏高还是偏低？偏多少？用本次运行的数据说明（提示：所有 token 间隔的真实均值约 7.63 ms）。
3. 给出一种修正方式。
4. 另外，`output_tokens <= 1` 时返回 0.0 会对 goodput 产生什么影响？

**Q10.** 讲义练习 1：用 1% 尾部尖刺生成负载，把 TPOT 约束从 30 ms 收紧到 15 ms，goodput 如何变化？

1. 实际运行 `synth_workload(n=2000, tail_spike_rate=0.01)`，在 TTFT<500、E2E<2000 不变的情况下，TPOT 取 30、15、10、8 ms 时 goodput 分别是多少？
2. 为什么 30 → 15 → 10 完全没有变化？
3. 如果希望 TPOT 约束真正反映"用户感受到的卡顿"，应如何修改 `goodput`？写出代码。

**Q11.** 手算一条短输出、长 prompt 的请求：排队 40 ms，prompt 8192 token（代码按每 token 0.05 ms 估 prefill），输出 3 个 token，首 token 之后两次间隔为 `[7, 49]` ms（按"n − 1 个间隔"的正确建模）。

1. 计算 TTFT、E2E、GenAI-Perf TPOT、LLMPerf TPOT（LLMPerf 按代码口径 `E2E / output_tokens`）。
2. 在 target SLO（TTFT<500、TPOT<15、E2E<2000）下，这个请求按两种口径分别是否算 good？
3. 由此说明：两种工具的差异在什么类型的请求上会被放大？

**Q12.** 按 `outputs/skill-slo-goodput-gate.md` 的 gating logic，写一个函数：

```python
def slo_gate(goodput_by_conc: dict[int, float], target_conc: int, target: float = 0.99) -> tuple[bool, list[str]]:
    ...
```

输入是并发扫描（25%、50%、100%、150% 目标并发）的 goodput 结果。要求：目标并发下 goodput ≥ target 才通过；若 150% 并发相比 100% 下降超过 5 个百分点，给出"压测余量不足"的告警；若缺少扫描点则拒绝。用 `{25: 1.0, 50: 0.998, 100: 0.991, 150: 0.92}`（目标并发 100）测试。

---

## 四、面试高频题

**Q13.**（基础必考）解释 TTFT、TPOT/ITL、E2E、throughput、goodput 的定义，以及它们分别主要受系统哪个部分影响。

**Q14.**（原理深挖）为什么 prefill 是 compute-bound、decode 是 memory-bound？chunked prefill 在 TTFT 与 TPOT 之间做了什么取舍？

**Q15.**（工程实践）供应商宣称"Llama 3.3 70B 在 H100 上 15,000 tok/s"。在相信这个数之前，你会问哪些问题？

**Q16.**（场景设计）为一个语音助手（首个 token 是"听到"而不是"看到"的）设计 SLO 与压测方案。哪个指标对用户最可见？

**Q17.**（追问型）同事报告"我们 P99 TPOT 只有 9 ms，非常健康"。你会追问什么？

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义：`TTFT = queue_time + network_request + prefill_time`。A 漏掉了排队和网络，并错误加入了 decode；B 中模型加载属于冷启动（第 10 节），不在稳态 TTFT 里；D 是 E2E 中 decode 的部分。注意本节代码的 `ttft_ms` 只建模了 `queue + prefill`，没有网络项。

### Q2 — 答案：A

GenAI-Perf：ITL 从第 2 个 token 开始，`700 / 99 = 7.07 ms`；LLMPerf：把 TTFT 也算进去，`(500 + 700) / 100 = 12.00 ms`。B 的分母用了 100（应为 99 个间隔）；C 把两个工具弄反；D 忽视了讲义的"tool trap"。

### Q3 — 答案：D

讲义：`goodput = fraction of requests meeting (TTFT <= a) AND (TPOT <= b) AND (E2E <= c)`。A 是 throughput 的定义；B 只看了一个约束；C 错，讲义强调"High throughput at 60% goodput is failure"，二者常常此消彼长（加大 batch 提高吞吐，但拉长 TPOT 和排队）。

### Q4 — 答案：B

讲义："LLM latency distributions are right-skewed... Users hit the P99 regularly — that is why they leave." 一个用户一次会话会发很多请求、每个请求有几百个 token 间隔，P99 级别的卡顿几乎人人都会遇到。A、C、D 都不是事实。

### Q5 — 答案：A

讲义："Without chunked prefill, during a long prefill on a neighboring sequence, TPOT can spike to 50 ms." 尖刺只出现在"恰好有长 prefill 插进来"的少数 step 上，对均值影响很小，但决定了 P99。chunked prefill 把长 prefill 切成小块与 decode 交替执行，削平尖刺。B 错，均值几乎不变；C 错，它影响的恰恰是邻居的 TPOT（自身 TTFT 还可能略变长）；D 与量化无关。

### Q6 — 答案：C

实际逐约束统计（n = 2000，seed = 7）：TTFT 违约 46、TPOT 违约 **0**、E2E 违约 **455**，goodput = 75.95%。输出长度 `randint(50, 300)`，按 ~7.6 ms/token，300 token 就要约 2.3 s，加上 TTFT 必然超过 2 s。所以这里 goodput "崩塌"的主因是**对所有输出长度用同一个 E2E 上限**，而不是尾延迟。讲义的 SLO 写的是"E2E P99 ≤ 3 s for <300-token outputs"，并建议"Report output-length-conditioned E2E"——代码没有按输出长度分桶。

### Q7 — 答案：D

`tpot_genaiperf()` 返回的是"该请求所有间隔的平均值"，`report_latency` 再在 2000 个请求的平均值之间取分位数。2% 的尖刺在每个请求的 50–300 个 token 中被平均掉，所以请求级 P99 只有 8.99 ms；把 35 万多个 token 间隔摊平直接取分位数，P99 约 **37.5 ms**、P99.9 约 59 ms（已实际计算）。KEY FINDING 的"25–40 ms"对应的是逐 token 的 ITL，而代码并没有打印它。A 错，打印的是 GenAI-Perf 口径；B 错，`percentiles` 的结果与 `statistics.quantiles` 一致（TTFT P99 均为 524.4）；C 错，种子固定为 7。

### Q8 — 答案：B

讲义："For long outputs (>500 tokens), E2E is TPOT-dominated." 800 × 7 ms ≈ 5.6 s，远大于几百毫秒的 TTFT。A 适用于"短输出 + 长 prompt"；C、D 通常是几十毫秒量级。

### Q9 — 参考答案

1. 首 token 在 TTFT 时刻到达，之后只有 **n − 1** 个间隔；代码却为每个请求生成了 **n** 个 decode 样本（`for _ in range(output_tokens)`）。等价于这个请求其实输出了 n + 1 个 token。
2. `tpot_genaiperf` 用 n 个样本之和除以 n − 1，**系统性偏高**，比例为 `n / (n − 1)`：n = 50 时偏高约 2%，n = 300 时约 0.3%。本次运行中所有间隔的真实均值约 7.63 ms（按"样本和 / n"计算每请求均值再平均也约 7.63），而报告的 GenAI-Perf 均值为 7.69 ms，多出的 0.06 ms 就来自这个分母错位。同时 `e2e_ms` 也多算了一个间隔。
3. 修正方式（任选其一）：
   - 生成 `output_tokens - 1` 个间隔：`for _ in range(output_tokens - 1):`，其余公式不变；
   - 或者保持 n 个样本，但把语义改为"第 1 个样本属于 TTFT 之后的首 token 生成"，GenAI-Perf 口径改为 `sum(decodes[1:]) / (n - 1)`。
4. 输出只有 1 个 token 时没有间隔，TPOT 无定义；返回 0.0 会让该请求的 TPOT 约束**自动通过**，可能高估 goodput。更稳妥的做法是返回 `None` 并在 goodput 中跳过 TPOT 判断（明确写进 SLO 定义），或单独统计。本代码 `randint(50, 300)` 不会触发该分支。

### Q10 — 参考答案

1. 实际运行结果（n = 2000，seed = 7，tail_spike_rate = 0.01，TTFT<500、E2E<2000）：

| TPOT 上限 | goodput | 仅看 TPOT 约束时 |
|-----------|---------|-----------------|
| 30 ms | 80.10% | 100% |
| 15 ms | 80.10% | 100% |
| 10 ms | 80.10% | 100% |
| 8 ms | 76.95% | 96.55% |

2. 因为 TPOT 约束作用在"每请求平均 TPOT"上，它的 P99 只有 8 ms 多一点（1% 尖刺被平均掉），30、15、10 ms 都远高于它，约束根本不生效；goodput 被 E2E 约束（长输出）卡在 80.1%。这说明：**要回答练习 1，必须先把 TPOT 约束改成能反映尾部的形式**。
3. 改为对每个请求的 token 间隔取高分位或最大值：

```python
def goodput_tail(traces, slo_ttft, slo_itl_p99, slo_e2e):
    good = 0
    for t in traces:
        itl = sorted(t.decode_ms_per_token)
        itl_p99 = itl[min(len(itl) - 1, int(0.99 * len(itl)))]   # 该请求内部的 P99 间隔
        if t.ttft_ms <= slo_ttft and itl_p99 <= slo_itl_p99 and t.e2e_ms <= slo_e2e:
            good += 1
    return good / len(traces)
```

用同一份 1% 尖刺负载实际运行：TTFT<500、E2E<2000 不变时，`slo_itl_p99 = 30` 的 goodput 为 56.1%，收紧到 15 ms 降为 45.1%（只看 ITL 约束时分别为 68.7% 与 53.5%）——此时收紧 TPOT 才真正产生影响，这才是练习 1 想让你看到的现象。也可以用"单个间隔超过 X ms 的次数 ≤ k"（stall 计数）。另一种做法是同时报告"请求级平均 TPOT 的 P99"和"token 级 ITL 的 P99"，并在 SLO 文档中写明用哪一个。

### Q11 — 参考答案

1. prefill = `8192 × 0.05 = 409.6 ms`；TTFT = `40 + 409.6 = 449.6 ms`；E2E = `449.6 + 7 + 49 = 505.6 ms`；GenAI-Perf TPOT = `(7 + 49) / 2 = 28.0 ms`；LLMPerf TPOT = `505.6 / 3 ≈ 168.5 ms`。
2. TTFT 449.6 < 500 ✓，E2E 505.6 < 2000 ✓；TPOT：GenAI-Perf 28.0 > 15 ✗，LLMPerf 168.5 > 15 ✗。两种口径下都**不算 good**，但如果间隔是 `[7, 7]`，GenAI-Perf 为 7 ms（good），LLMPerf 为 `463.6 / 3 ≈ 154.5 ms`（bad）——同一个请求，工具不同，结论相反。
3. 输出越短、TTFT 越大，LLMPerf 口径被 TTFT"污染"得越严重；输出很长时，TTFT 被摊薄，两种口径接近。本节代码输出 50–300 token，所以均值只差约 1 ms（7.69 vs 8.71）；在 Agent 工具调用、分类类短输出负载上，差距会大得多。所以讲义说"Always state which tool. Always publish the definition."

### Q12 — 参考答案

```python
def slo_gate(goodput_by_conc, target_conc, target=0.99):
    msgs = []
    needed = [int(target_conc * f) for f in (0.25, 0.5, 1.0, 1.5)]
    missing = [c for c in needed if c not in goodput_by_conc]
    if missing:
        return False, [f"REJECT: concurrency sweep missing points {missing}"]
    g100 = goodput_by_conc[target_conc]
    g150 = goodput_by_conc[int(target_conc * 1.5)]
    passed = g100 >= target
    msgs.append(f"goodput@{target_conc}={g100:.2%} -> {'PASS' if passed else 'FAIL'} (target {target:.0%})")
    if g100 - g150 > 0.05:
        msgs.append(f"WARN: goodput drops {g100 - g150:.1%} from 100% to 150% concurrency; load-test headroom missing")
    return passed, msgs

print(slo_gate({25: 1.0, 50: 0.998, 100: 0.991, 150: 0.92}, 100))
```

实际运行输出：

```text
(True, ['goodput@100=99.10% -> PASS (target 99%)', 'WARN: goodput drops 7.1% from 100% to 150% concurrency; load-test headroom missing'])
```

要点：通过/失败只看目标并发（skill："CI passes if goodput >= target AT target concurrency"），但 150% 处下降 7.1 个百分点触发告警——流量一旦超过预期，SLO 会迅速失守。完整的闸门还应校验工具名/版本、样本量（skill 要求 ≥ 30 次运行、每次 ≥ 100 个请求）以及 prompt 分布不是"同一 prompt 循环"。

### Q13 — 参考回答要点

- **TTFT**：排队 + 网络 + prefill；受调度器负载、prompt 长度（prefill 算力）影响。
- **TPOT / ITL**：首 token 后相邻 token 的间隔；受 decode 的显存带宽、batch 大小、是否有长 prefill 插队影响。
- **E2E**：`TTFT + TPOT × 输出长度 + 网络回包`；长输出看 TPOT，短输出看 TTFT。
- **Throughput**：总输出 token / 时间；衡量集群效率，与单请求体验无直接关系。
- **Goodput**：同时满足所有 SLO 的请求占比；产品真正关心的指标，讲义称 MLPerf Inference v6.0 与平台内部 SLA 都用它。
- 加分点：说明"每个指标都要报 P50/P90/P99，并声明使用的工具及其 ITL 定义"。

### Q14 — 参考回答要点

- **prefill**：prompt 的所有 token 已知，可以一次大矩阵乘并行算完，算术强度高，瓶颈在算力；耗时随 prompt 长度增长（attention 部分超线性）。
- **decode**：每步每序列只算 1 个 token，是矩阵-向量乘，必须把权重和 KV cache 从 HBM 读一遍，瓶颈在带宽；增大 batch 可以摊薄读权重的成本，但每步变慢、TPOT 上升。
- **chunked prefill 的取舍**：把长 prefill 切成固定大小的块，与 decode 请求混合在同一步执行。好处是 decode 步不会被整段长 prefill 阻塞，P99 TPOT 被削平（讲义：无 chunked prefill 时可尖到 50 ms）；代价是长 prompt 本身的 prefill 被拆成多步完成，它自己的 TTFT 可能变长，且块大小需要调优。
- 加分点：再往前一步就是 prefill/decode 分离（disaggregation，第 17 节），把两类负载放到不同 GPU 池，彻底消除互相干扰。

### Q15 — 参考回答要点

- **在什么延迟下？** 给出 TTFT/TPOT/E2E 的 P50/P90/P99，以及在该吞吐下的 goodput（针对哪个 SLO）。
- **什么负载？** 输入/输出长度分布、并发数、是否同一个 prompt 循环（skill 文件称之为 prompt-uniformity trap，会因前缀缓存而虚高）。
- **什么配置？** 精度（FP8？FP4？）、几张卡、TP/PP 配置、是否开 speculative decoding、引擎与版本。
- **什么工具、什么定义？** LLMPerf 还是 GenAI-Perf，版本号；tok/s 是输出 token 还是输入 + 输出 token。
- **测了多久、多少次？** 讲义建议 30–50 次迭代、2 倍峰值并发。
- 常见误区：只比较峰值吞吐，不问延迟分位数——"15,000 tok/s"在 batch 极大、TPOT 很差时也能达到。

### Q16 — 参考回答要点

- **最可见指标**：TTFT——第一个音节什么时候被听到。语音还要加上 TTS 首包时间，因此 LLM 的 TTFT 预算更紧（skill 文件：语音 TTFT 300 ms，比聊天的 500 ms 更严）。
- **TPOT 要求**：只要 token 生成速度快于 TTS 播放/合成的消耗速度即可，不需要像文字流式那样追求极低 TPOT；但不能有长卡顿，否则语音会中断——因此要约束**逐 token 的最大间隔或 P99 ITL**，而不是平均 TPOT（见 Q10）。
- **E2E**：语音回答通常较短，E2E 约束可以按输出长度设定。
- **SLO 示例**（需按产品验证）：TTFT P99 ≤ 300 ms；单请求内 ITL P99 ≤ 某个阈值（保证 TTS 缓冲不被耗尽）；goodput ≥ 99%。
- **压测**：拟真的语音对话 prompt 分布（短问题、多轮上下文）、并发扫描、把网络与 TTS 首包也纳入端到端测量。
- 加分点：可以用"先说一个短确认语"等产品手段掩盖 TTFT，但 SLO 仍应量化真实延迟。

### Q17 — 参考回答要点

- **口径**：是 GenAI-Perf 还是 LLMPerf？是"每请求平均 TPOT 的 P99"还是"所有 token 间隔的 P99"？本节代码就是一个例子：前者 8.99 ms、后者约 37.5 ms，差 4 倍。
- **负载**：在什么并发下测的？是否覆盖了 2 倍峰值？prompt 是否有长短混合（有没有长 prefill 插队的机会）？是否开了 chunked prefill？
- **样本量**：多少次运行、多少请求？P99 至少需要几千个样本才稳定。
- **其它维度**：TTFT 和 E2E 的 P99 如何？goodput 多少？只看一个指标健康不代表 SLO 达标（本节代码 TPOT 违约为 0，但 goodput 只有 76%）。
- 加分点：建议同时报告 P99.9 和"卡顿次数"，并按输出长度分桶报告 E2E。

---

## 六、关联知识点

### 前置知识
- [阶段 17 · 04 服务引擎内部机制：PagedAttention、Continuous Batching 与 Chunked Prefill](../../04-vllm-serving-internals/docs/zh.md)：continuous batching 与 chunked prefill 决定了 TTFT/TPOT 的形状。
- [阶段 10 · 12 Inference Optimization](../../../10-llms-from-scratch/12-inference-optimization/docs/zh.md)：prefill 与 decode 的计算特性。
- [阶段 17 · 07 针对硬件的 Inference 编译：Blackwell 上的 FP8 与 NVFP4](../../07-tensorrt-llm-blackwell/docs/zh.md)：吞吐与成本的数字需要用 goodput 来校验。

### 本节被哪些后续内容用到
- [阶段 17 · 17 Prefill 与 Decode 分离：NVIDIA Dynamo 与 llm-d](../../17-disaggregated-prefill-decode/docs/zh.md)：为了同时守住 TTFT 与 TPOT 而分离两个阶段。
- [阶段 17 · 22 对 LLM APIs 进行负载测试](../../22-load-testing-llm-apis/docs/zh.md)：如何正确地压测并采集这些指标。
- [阶段 17 · 13 LLM Observability 技术栈选型](../../13-llm-observability/docs/zh.md)：生产中持续采集 TTFT/TPOT/goodput。
- [阶段 17 · 20 面向 LLMs 的 Shadow Traffic、金丝雀 Rollout 与渐进式部署](../../20-shadow-canary-progressive/docs/zh.md)：用 goodput 作为金丝雀的放量闸门。
- [阶段 17 · 23 AI 的 SRE](../../23-sre-for-ai/docs/zh.md)：SLO、错误预算与告警。
- [阶段 17 · 11 多区域 LLM 服务与 KV Cache 局部性](../../11-multi-region-kv-locality/docs/zh.md)：跨区域路由对 TTFT 的影响。

### 延伸关键词
`TTFT` · `TPOT / ITL` · `E2E latency` · `goodput` · `SLO / SLA` · `P50 / P90 / P99` · `tail latency` · `chunked prefill` · `continuous batching` · `GenAI-Perf` · `LLMPerf` · `concurrency sweep` · `output-length bucketing` · `MLPerf Inference`
