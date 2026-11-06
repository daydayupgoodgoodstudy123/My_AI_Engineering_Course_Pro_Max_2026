# 测验 · 托管 LLM 平台：Bedrock、Vertex AI、Azure OpenAI（Managed LLM Platforms — Bedrock, Vertex AI, Azure OpenAI）

> **阶段 17 · 基础设施与生产 · 第 01 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 说明：讲义与代码中的价格、延迟都是讲义作者给出的 2026 年近似值，本测验照讲义转述，未与各厂商价目表核对；做决策前请以官方定价页为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 三种平台战略 | AWS Bedrock = 模型市场（Claude、Llama、Titan、Mistral、Cohere 等一个 API）；Azure OpenAI = 与 OpenAI 的独家合作 + PTU；Vertex AI = Gemini 优先（长上下文、多模态），第三方模型放在 Model Garden |
| 2 | 选型规则 | 讲义："not 'which is fastest' but 'which model catalog and FinOps surface match my product'" |
| 3 | 延迟差距的来源 | 讲义：Azure OpenAI 中位 TTFT 约 50 ms、Bedrock 约 75 ms；差距来自容量模型（专用 vs 共享按需），不是"AWS 不行" |
| 4 | PTU / Provisioned Throughput | 按小时付费的预留推理容量，闲置也要付钱；讲义：可预测负载下最多省约 70%，盈亏平衡约在 40–60% 持续利用率；Bedrock PT 约 $21–50/小时/单位，需月度承诺 |
| 5 | 盈亏平衡公式 | 利用率 u 下按需日成本 = u × 每小时容量 × 24 × 单价；PTU 日成本 = 每小时价格 × 24；平衡点 u* = PTU 每小时价格 /（每小时容量 × 单价）——单价用输出价还是混合价，结论天差地别 |
| 6 | FinOps 归因面 | Bedrock Application Inference Profiles 原生最干净；Vertex 用"每团队一个项目 + 标签 + BigQuery 账单导出"最灵活；Azure 依赖订阅/资源组范围 + 标签，按请求归因需要 App Insights 或网关打 header |
| 7 | Two-provider minimum | 每条产品关键 LLM 调用至少跨两个云；常见组合是 Bedrock（Claude）+ Azure OpenAI（GPT），同一网关做故障切换 |
| 8 | 合规 | 三家都提供 BAA 等基础合规；差异在数据保留、日志处理和 abuse monitoring 是否读取流量（企业版通常可选择退出） |
| 9 | SLA 与容量 | 讲义：TTFT P99 < 100 ms 的 SLA 通常要么买 PTU/PT，要么接受共享容量的波动 |
| 10 | 本节代码的局限 | `simulate` 只按成本取最小、不看 SLA；盈亏平衡扫描只按输出单价计费；所有价格与延迟都是示意参数 |

### 核心技能（能动手做到）

- [ ] 根据"需要哪些模型 + 合规 + 已有云 + FinOps 要求"为一个产品选出主平台与备用平台，并写出理由
- [ ] 手算 PTU 的盈亏平衡利用率，并说明输入/输出 token 比例如何改变结论
- [ ] 读懂 `simulate`，指出它在"SLA 要求 PTU"的场景里为什么仍选按需，并把它改成"满足 SLA 的最便宜方案"
- [ ] 设计一个按团队/产品/功能的 LLM 成本归因方案（Bedrock Inference Profiles / Vertex 项目 + 标签 / Azure 网关打标）
- [ ] 量化 two-provider minimum 的额外成本，并与一次区域性故障的损失对比
- [ ] 发现讲义中的内部不一致（例如"Azure OpenAI 上的 Llama 3.1 405B"）

---

## 二、基础自测（选择题）

**Q1.** 一个产品需要在**同一个 API** 后面同时使用 Claude、Llama 和 Cohere。按讲义，最匹配的平台是：

- A. Azure OpenAI Service
- B. Vertex AI 的 Gemini 端点
- C. AWS Bedrock
- D. 直接调用 Anthropic API

**Q2.** 讲义解释"Azure OpenAI 中位 TTFT 约 50 ms、Bedrock 约 75 ms"时，给出的主要原因是：

- A. 容量模型不同：PTU 为租户预留 GPU 容量，而大多数 Bedrock 客户使用与他人共享的按需容量
- B. Azure 的数据中心离用户更近
- C. Bedrock 的 API 协议效率更低
- D. Bedrock 不支持流式输出

**Q3.** 运行本节代码的 `break_even_demo`（Azure：$10/小时、200 万 token/小时、按 $10/M 计费），PTU **第一次**比按需便宜是在哪个利用率档位？

- A. 40%
- B. 50%
- C. 永远不会
- D. 60%

**Q4.** 讲义认为三家云中**原生**成本归因最干净、无需后处理的是：

- A. Azure 的订阅 + 资源组标签
- B. Bedrock 的 Application Inference Profiles
- C. Vertex 的 BigQuery Billing Export
- D. 三家完全相同

**Q5.** 代码第二次调用 `simulate(30M 输入, 15M 输出, SLA=100 ms, use_ptu=True)` 的结果是：

- A. 三个平台都走按需（`[on-demand]`），SLA 全部 FAIL
- B. Azure 走 PTU 并 PASS，其余 FAIL
- C. 三个平台都走 PTU 并 PASS
- D. Bedrock 走 PTU 并 PASS，其余 FAIL

**Q6.** 讲义推荐的 two-provider minimum 中，"常见组合"是：

- A. Vertex + Vertex 的两个不同区域
- B. 直接 OpenAI API + Azure OpenAI
- C. Bedrock（取 Claude）+ Azure OpenAI（取 GPT），同一网关前置、相互故障切换
- D. 两个自托管 vLLM 集群

**Q7.** 关于 PTU / Provisioned Throughput 的成本特性，正确的是：

- A. 按实际处理的 token 计费，与按需相同，只是更快
- B. 只有在利用率低于 20% 时才划算
- C. 免费附带在企业合同中
- D. 每小时费用固定，与流量无关——空闲时也要为预留付费，所以要看持续利用率

**Q8.** 在 Azure 上想做"按请求"的成本归因（例如按功能、按租户），讲义指出的难点和做法是：

- A. Azure 不允许打标签，只能按订阅看总账
- B. 标签继承自资源组而不是请求，因此需要 Application Insights 自定义指标，或用网关给每个请求打 header
- C. 只要购买 PTU 就会自动按请求归因
- D. 必须把数据导出到 BigQuery

---

## 三、动手 / 代码题

**Q9.** 阅读 `simulate` 中 PTU 路径的选择逻辑：

```python
        if use_ptu and p.ptu_hourly is not None:
            total_tokens = tokens_in_per_day + tokens_out_per_day
            daily_capacity_per_ptu = p.ptu_tokens_per_hour * 24
            ptu_count = max(1, (total_tokens + daily_capacity_per_ptu - 1) // daily_capacity_per_ptu)
            cost_ptu = ptu_count * p.ptu_hourly * 24
            cost = min(cost_ondemand, cost_ptu)
            ttft_p50 = p.ttft_median_ptu_ms if cost == cost_ptu else p.ttft_median_ms
            ttft_p99 = ttft_p50 * 1.5 if cost == cost_ptu else p.ttft_p99_ms
            path = "PTU" if cost == cost_ptu else "on-demand"
```

1. 第二个工作负载（30M 输入 + 15M 输出/天，SLA P99 < 100 ms）下，算出 Bedrock 与 Azure 各需要几个 PTU、PTU 日成本、按需日成本、PTU 路径的 P99。
2. 为什么输出里三个平台都是 `[on-demand]` 且全部 FAIL？这与讲义"If your product SLA is TTFT < 100 ms at P99, you either buy PTUs…"的建议有什么冲突？
3. 把选择逻辑改成"在满足 SLA 的方案中选最便宜；都不满足再选最便宜并标 FAIL"，写出代码并给出新结果。
4. `(a + b - 1) // b` 是什么惯用法？还有什么等价写法？

**Q10.** `break_even_demo` 只按**输出**单价给所有 token 计费：

```python
        tokens_per_day = int(p.ptu_tokens_per_hour * 24 * (util_pct / 100.0))
        ondemand = (tokens_per_day / 1e6) * p.per_mtok_output
        ptu = 24 * p.ptu_hourly
```

1. 写出盈亏平衡利用率 u* 的公式，代入 Azure 参数验证 50%。为什么 50% 这一行的 Winner 显示 `on-demand`？
2. 而 `simulate` 中 PTU 容量是按"输入 + 输出"总 token 计算的。若改用混合单价，输入:输出 = 3:1 与 2:1 时 Azure 的 u* 分别是多少？说明了什么？
3. 对 Bedrock（$21/小时、120 万 token/小时、输出 $15/M）做同样计算，结论是什么？
4. 讲义说 PTU "up to ~70% savings"。在代码的 Azure 参数下，100% 利用率时最多省多少？

**Q11.** 阅读 `lock_in_cost`：

```python
    tokens_per_day = 5_000_000
    primary_cost = (tokens_per_day / 1e6) * 10.00
    gateway_overhead_pct = 3.0
    failover_headroom_pct = 10.0
    uplift = primary_cost * (gateway_overhead_pct + failover_headroom_pct) / 100
```

1. 写出全部打印数字，并算出冗余带来的成本增幅占主成本的百分比。讲义说"Cost uplift is negligible"，你怎么看？
2. 假设该 LLM 功能直接支撑每小时 $2,000 的收入，一年中累计多少小时的停机损失就能覆盖全年冗余成本（按每月 30 天、每年 12 个月）？
3. 这个模型漏掉了哪些成本或收益？

**Q12.** 找出讲义（英文原文）与代码中关于延迟和节省比例的**不一致**之处，至少三处：

- 讲义 Concept："On equivalent Llama 3.1 405B deployments (shared on-demand), Azure OpenAI median first-token latency is around 50 ms; Bedrock is around 75 ms."
- 讲义 Concept："No non-OpenAI models in the 'Azure OpenAI Service' catalog — those go to Azure AI Foundry."
- 讲义 Numbers："Azure OpenAI median TTFT on Llama 3.1 405B equivalents: ~50 ms (with PTUs)."
- 代码：`Platform("Azure OpenAI (PTU)", 2.50, 10.00, 10.0, 2_000_000, 50, 140, 38, ...)`，字段依次为按需输入价、输出价、PTU 每小时价格、PTU 每小时 token、**共享**中位 TTFT、共享 P99、**PTU** 中位 TTFT。

---

## 四、面试高频题

**Q13.**（基础必考）Bedrock、Azure OpenAI、Vertex AI 三家托管 LLM 平台的定位有什么不同？你会怎么为一个新产品选？

**Q14.**（原理深挖）什么时候应该买 PTU / Provisioned Throughput？请写出盈亏平衡的计算方法，并说明哪些因素会让"纸面上划算"在实际中不划算。

**Q15.**（工程实践）公司 Bedrock 账单本月涨了 4 倍，但流量没变（讲义练习 4）。没有 Application Inference Profiles 时你怎么查？有的话呢？以后如何预防？

**Q16.**（场景设计）一个受监管的医疗客户要求 BAA、美国东部数据驻留、TTFT P99 < 100 ms，同时产品需要 Claude 和 GPT 两个模型。请给出平台、容量、网关与故障切换方案。

**Q17.**（追问型）"two-provider minimum 会让成本上升、复杂度上升，为什么还要做？"如果面试官进一步追问"两个云上的模型不一样，切换后输出质量也不一样，怎么办？"你怎么回答？

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义："AWS Bedrock — the marketplace. Claude (Anthropic), Llama (Meta), Titan (AWS first-party), Stability (image), Cohere (embeddings), Mistral… One API, one IAM surface, one CloudWatch export." A 只提供 OpenAI 模型（非 OpenAI 模型在 Azure AI Foundry）；B 以 Gemini 为主，第三方模型在 Model Garden，不是同一个端点；D 只有 Claude。（这道题与本节自带的 `quiz.json` 第 1 题同源。）

### Q2 — 答案：A

讲义："The gap is not an AWS failure — it is a capacity model difference. Azure sells PTUs… which reserve GPU capacity for your tenant… most customers stay on shared on-demand." 共享容量要与其他客户的流量竞争。B、C、D 讲义均未提及。注意讲义在这里的叙述本身有矛盾（见 Q12）：同一句话里说是"shared on-demand"的测量，又用 PTU 解释差距。

### Q3 — 答案：D

实际输出：

```text
     50%  $          240.00  $    240.00  on-demand
     60%  $          288.00  $    240.00  PTU
```

50% 时两者恰好相等（240 = 240），而判断是 `winner = "PTU" if ptu < ondemand else "on-demand"`，严格小于，所以平局算按需；60% 才第一次是 PTU。A 是讲义平衡带的下限；B 是理论平衡点但不是"第一次更便宜"的档位；C 在只按输出价计费时不成立（但换成混合单价时确实可能成立，见 Q10）。

### Q4 — 答案：B

讲义："Bedrock Application Inference Profiles are the cleanest attribution in the marketplace… CloudWatch breaks out cost per profile without post-processing." C 是"最灵活"（任意 SQL）但需要建项目、打标签、导出；A 是"最不透明"，按请求归因需要额外埋点。总结句："Bedrock is cleanest native, Vertex is most flexible via BigQuery, Azure is most opaque unless you instrument."

### Q5 — 答案：A

实际输出：

```text
Bedrock on-demand          $  315.00       75 ms      180 ms    FAIL  ...  [on-demand]
Azure OpenAI (PTU)         $  225.00       50 ms      140 ms    FAIL  ...  [on-demand]
Vertex AI Gemini           $  112.50       60 ms      160 ms    FAIL  ...  [on-demand]
```

虽然 `use_ptu=True`，但代码用 `min(cost_ondemand, cost_ptu)` 只挑便宜的：Azure PTU $240 > 按需 $225，Bedrock 2 个 PTU $1,008 > 按需 $315，于是都走按需；共享容量的 P99（140–180 ms）全部超过 100 ms。Vertex 没有 PTU 选项。B 是**本应**出现的结果（见 Q9）。

### Q6 — 答案：C

讲义："Bedrock plus Azure OpenAI is the common pair — Claude from one, GPT from the other, failover between them, same gateway." A 只是同一云的多区域，不能防"单一云商"风险；B 都是 OpenAI 模型，模型层仍是单一供应商；D 与托管平台主题无关。

### Q7 — 答案：D

讲义："Costs fixed per hour regardless of traffic — you pay for the reservation even when idle. The break-even is usually around 40-60% sustained utilization." A 描述的是按需；B 说反了，利用率越**高**越划算；C 无依据。

### Q8 — 答案：B

讲义："Tags are inherited from resource groups, not requests, so per-request attribution requires Application Insights custom metrics or a gateway that stamps headers." A 错，Azure 支持标签，只是粒度在资源层；C 错，PTU 是"一等成本对象"，但它是预留本身的成本，不会自动拆到请求；D 是 Vertex 的做法。

### Q9 — 参考答案

1. 已用代码参数计算：
   - **Bedrock**：每 PTU 每天 1.2M × 24 = 28.8M token；45M 需要向上取整 **2 个**；PTU 日成本 2 × 21 × 24 = **$1,008**；按需 30 × 3 + 15 × 15 = **$315**；PTU 路径 P50 = 55 ms、P99 = 55 × 1.5 = **82.5 ms**。
   - **Azure**：每 PTU 每天 2M × 24 = 48M，**1 个**足够（利用率 45/48 ≈ 93.8%）；PTU 日成本 10 × 24 = **$240**；按需 30 × 2.5 + 15 × 10 = **$225**；PTU 路径 P50 = 38 ms、P99 = **57 ms**。
2. `min()` 只比较成本，完全不看 SLA。Azure 的 PTU 只比按需贵 $15/天（约 6.7%），却能把 P99 从 140 ms 降到 57 ms、满足 100 ms 的 SLA；代码却选了更便宜但必然 FAIL 的按需。讲义与 skill 文件都说"SLA 比按需能提供的更紧时，必须用 PTU"（skill："If the SLA is tighter than on-demand can deliver, require PTU"），代码的决策逻辑与之相反，导致整个演示里 PTU 路径从未被选中过。
3. 参考实现（已运行）：

```python
def options(p, tin, tout):
    od = tin / 1e6 * p.per_mtok_input + tout / 1e6 * p.per_mtok_output
    yield ("on-demand", od, p.ttft_median_ms, p.ttft_p99_ms)
    if p.ptu_hourly is not None:
        cap = p.ptu_tokens_per_hour * 24
        n = max(1, -(-(tin + tout) // cap))           # 向上取整
        yield (f"PTU x{n}", n * p.ptu_hourly * 24,
               p.ttft_median_ptu_ms, p.ttft_median_ptu_ms * 1.5)

def pick(p, tin, tout, sla):
    opts = list(options(p, tin, tout))
    ok = [o for o in opts if o[3] < sla]               # o[3] 是 P99
    if ok:
        return min(ok, key=lambda o: o[1]), "PASS"
    return min(opts, key=lambda o: o[1]), "FAIL"
```

   新结果：

```text
Bedrock on-demand         PTU x2     $ 1008.00 p50=55 p99=82.5 PASS
Azure OpenAI (PTU)        PTU x1     $  240.00 p50=38 p99=57.0 PASS
Vertex AI Gemini          on-demand  $  112.50 p50=60 p99=160.0 FAIL
```

   结论变成：满足 SLA 的最便宜方案是 Azure PTU（$240/天）；Vertex 在本模型里无 PTU 选项，只能 FAIL（讲义说 Vertex 也有按 SKU 出售的预留容量，只是代码没有建模）。
4. `(a + b - 1) // b` 是正整数的**向上取整除法**：45M 与 28.8M 得到 2。等价写法：`-(-a // b)`、`math.ceil(a / b)`（大数时浮点可能有误差）。外层 `max(1, ...)` 保证至少买 1 个。

### Q10 — 参考答案

1. 设利用率 u、每小时容量 C、单价 r（$/M），则按需日成本 = u × C × 24 × r / 10⁶，PTU 日成本 = H × 24。令二者相等：**u\* = H /（C/10⁶ × r）**。Azure：10 / (2 × 10) = **0.5**。50% 行两者都是 $240，`ptu < ondemand` 为假，平局判给按需。
2. 混合单价 = (输入份数 × 2.5 + 输出份数 × 10) / 总份数（已计算）：
   - 3:1 → $4.375/M → u\* = 10 / (2 × 4.375) ≈ **1.14**，超过 100%——**PTU 永远不划算**；
   - 2:1 → $5.0/M → u\* = **1.0**，只有满载才持平。
   说明：用输出单价给所有 token 计费会严重高估按需成本、低估 PTU 的门槛。现实中输入 token 往往比输出多（RAG、长 prompt），讲义"40–60% 平衡带"能否成立取决于真实的 PTU 定价与 token 构成，必须用自己的流量数据算。本节 `simulate` 的第二个工作负载（2:1）恰好对应 u\* = 100%，这也是 Azure PTU 在其中贵于按需的根本原因。
3. Bedrock：仅按输出价 u\* = 21 / (1.2 × 15) ≈ **1.17**；3:1 混合 $6/M → **2.92**；2:1 混合 $7/M → **2.5**。在代码参数下 Bedrock Provisioned Throughput **在任何利用率下都不比按需便宜**，它只能用来买延迟/容量保障。讲义说"Similar math — break-even is around half peak utilization"，与代码参数不符。
4. 100% 利用率时按需 $480/天、PTU $240/天，最多省 **50%**，达不到讲义所说的 70%。要省 70%，按需单价需要是 PTU 等效单价的 1/(1−0.7) ≈ 3.3 倍，而代码参数只有 2 倍。

### Q11 — 参考答案

1. 打印：主成本 $50.00/天；网关开销 3% = $1.50/天；备用余量 10% = $5.00/天；合计增幅 $6.50/天；月增幅 $195.00。增幅占主成本 **13%**。讲义"Cost uplift is negligible because gateway routes optimal"说的是"可以忽略"，而代码自己的假设给出 13%——不算可忽略，但相对于一次多小时故障的损失通常很小。更准确的说法是"增幅有限、可量化，并且是一种保险"。
2. 全年冗余成本 = 195 × 12 = **$2,340**；每小时收入 $2,000 → 一年累计约 **1.17 小时**停机即可覆盖。这还没算 SLA 赔付、客户流失和战情室人力（代码最后一行列出的定性成本）。
3. 漏掉的因素：
   - 成本侧：两套模型的 prompt/eval 适配与回归测试工作量；两边的合规审查与合同；跨云的数据出口费；备用侧若用 PTU 则是固定成本而非 10% 余量；
   - 收益侧：可以按价格/延迟动态路由节省成本（讲义"gateway routes optimal"）、获得两家的新模型、谈判筹码；
   - 风险侧：切换后的质量差异与输出格式差异（见 Q17）。

### Q12 — 参考答案

1. **"Azure OpenAI 上的 Llama 3.1 405B"自相矛盾**：讲义自己说 Azure OpenAI Service 目录里没有非 OpenAI 模型（它们在 Azure AI Foundry），却用"Azure OpenAI 在 Llama 3.1 405B 等价部署上的 TTFT"作对比。应理解为"Azure 平台上的同级部署"，不能说成 Azure OpenAI Service。
2. **"shared on-demand" vs "(with PTUs)"**：Concept 一节说 50 ms 是在"shared on-demand"条件下测的，Numbers 一节又说 50 ms 是"with PTUs"，同时用 PTU 解释差距——测量条件说不清。
3. **代码把 50 ms 当成 Azure 的共享延迟**：`ttft_median_ms=50` 是共享容量的中位数，PTU 中位数另设为 38 ms。代码的口径与讲义"~50 ms (with PTUs)"不一致。
4. **"up to 70% savings"**：代码参数下 PTU 最多省 50%（Q10.4）。
5. **"break-even around half peak"（Bedrock）**：代码参数下 Bedrock PT 永不划算（Q10.3）。
6. 代码 Azure 平台名叫 `"Azure OpenAI (PTU)"`，但两次 `simulate` 实际都走按需，名字有误导性。

启示：读平台对比材料时，要追问每个数字的测量条件（共享还是专用、哪个模型、哪个区域、哪一天），否则"50 ms vs 75 ms"这类数字无法复现，也不能作为选型依据。

### Q13 — 参考回答要点

- **定位**：
  - Bedrock：模型市场，一套 IAM / VPC / CloudWatch 下用 Claude、Llama、Titan、Mistral、Cohere 等；优势是选择权与 Application Inference Profiles 的成本归因；
  - Azure OpenAI：OpenAI 模型的企业版（GPT-4o / 5 / o 系列、Whisper、fine-tuning），PTU 提供专用容量，企业合规与 EU 数据驻留成熟；
  - Vertex AI：Gemini 优先，长上下文（讲义：1M token）与多模态是差异点，第三方模型在 Model Garden；BigQuery 账单导出最灵活。
- **选型流程**：
  1. 需要哪些模型？（模型目录决定一半答案；Claude + GPT + Gemini 都是 P0 时只能三家并用，skill 文件明确要求承认这一点）
  2. 已有云足迹、合规（BAA、数据驻留）；
  3. 延迟 SLA 与流量是否可预测（决定按需还是 PTU）；
  4. FinOps 归因要求；
  5. 至少再选一个备用平台。
- 讲义原则："not 'which is fastest' but 'which model catalog and FinOps surface match my product'"。
- 常见误区：只看排行榜上的延迟；"选最便宜的"——skill 文件把它列为拒绝理由："price is multi-dimensional"。

### Q14 — 参考回答要点

- **何时买**：流量可预测且持续利用率高；或 SLA（尤其 P99 TTFT）比共享容量能稳定提供的更紧；或需要容量保障（大促、上线）。
- **计算**：`u* = 每小时 PTU 价格 / (每小时容量 × 按需混合单价)`；混合单价按真实输入/输出比例加权（Q10 显示单价口径能让 u\* 从 50% 变成 >100%）；再与预测的利用率曲线（含峰谷）比较，而不是只看日均。
- **纸面划算、实际不划算的因素**：
  - 峰谷明显：容量按峰值买，夜间闲置；
  - 承诺期（讲义：Bedrock PT 需月度承诺）与模型换代——一个月后想换新模型，旧预留还在计费；
  - 容量单位的实际吞吐依赖 prompt 长度、输出长度与并发，标称 token/小时不一定达到；
  - 按需单价持续下降，长期预留可能被价格战反超；
  - 仍需按需或第二供应商兜底溢出流量。
- 加分点：混合策略——基线流量放 PTU，峰值溢出走按需；用"PTU 浪费率"（未用容量占比）作为持续监控指标（skill 文件："End with the single metric that will catch drift… sustained utilization, PTU waste…"）。

### Q15 — 参考回答要点

- **没有 Inference Profiles 时**：
  - 用 Cost Explorer 按服务 / 用量类型 / 区域 / 模型拆分，看是哪一个模型、输入还是输出 token、哪一个区域涨了；
  - 打开 CloudWatch 的调用指标（调用次数、输入/输出 token）与应用日志对照，找出 token/请求异常增长的调用方（例如 prompt 里塞进了整个历史、RAG 召回过多、重试风暴、某个 agent 循环）；
  - 若各团队共用账号与角色，只能靠应用侧日志或网关日志关联，往往要几天。
- **有 Inference Profiles 时**：每个 profile 带 `team / product / feature` 标签，CloudWatch 直接按 profile 拆成本，通常几分钟就能定位到具体功能——讲义："CloudWatch breaks out cost per profile without post-processing."
- **预防**：所有调用强制走 profile 或网关打标；按 profile 设预算告警与异常检测；对单请求 token 上限、重试预算做硬限制；在 CI 中做 prompt 长度回归。
- 加分点：说明"流量没变而成本涨 4 倍"最常见的原因是 token/请求变多或模型被换成更贵的版本，而不是请求数。

### Q16 — 参考回答要点

- **模型分配**：Claude 走 Bedrock、GPT 走 Azure OpenAI（讲义的常见组合）；两家都在美国东部区域部署，签 BAA。
- **合规**：确认 BAA 覆盖所用模型与区域；关闭或申请豁免 abuse monitoring 对内容的留存（企业版可选择退出）；日志脱敏、PHI 不进普通日志；VPC endpoint / Private Link 走私网。
- **延迟**：P99 < 100 ms 在共享按需上难以保证（讲义与 skill："If the SLA is TTFT P99 < 100 ms and the expected budget cannot support PTU, refuse to promise the SLA"）；关键路径购买 Azure PTU / Bedrock Provisioned Throughput，先按 Q14 的方法算利用率。
- **网关与故障切换**：自建或使用 AI 网关统一鉴权、限流、打标与路由；健康检查 + circuit breaker；按"功能"定义主备映射（如某功能主用 Claude、备用 GPT）；切换后启用该模型专属的 prompt 模板；故障演练。
- **FinOps**：Bedrock Inference Profiles + Azure 网关 header 打标，统一汇总到一个成本看板。
- 常见误区：只选一个云承诺 SLA；以为"三家都合规"就无需逐项核对数据保留政策。

### Q17 — 参考回答要点

- **为什么做**：讲义的两个理由——（1）前沿模型每季度轮换，单一平台会把你锁在大部分前沿模型之外；（2）区域性故障时可用性提升是决定性的。成本侧可以量化（本节代码约 13% 增幅），通常远小于一次故障的损失（Q11.2：约 1 小时停机即可覆盖全年成本）。
- **质量不一致怎么办**：
  - 每个模型维护自己的 prompt 模板与输出解析器，而不是共用一个 prompt；
  - 用 structured output / JSON schema 统一输出契约，网关层做校验；
  - 用同一套内部 eval 集对主备两条路径做回归，设定备用路径可接受的质量下限；
  - 分级降级：关键功能切到备用模型，非关键功能可以暂时关闭或排队；
  - 定期做故障演练与 shadow traffic，确保备用路径真的可用（阶段 17 后续小节会讲）。
- 加分点：区分"可用性冗余"（同一模型的多区域/多供应商，例如 Claude 同时在 Anthropic API 与 Bedrock）与"模型冗余"（Claude ↔ GPT），前者质量一致、后者覆盖更广，可以组合使用。

---

## 六、关联知识点

### 前置知识
- [阶段 11 · 11 缓存、请求速率限制与成本优化](../../../11-llm-engineering/11-caching-cost/docs/zh.md)：token 计费与成本控制的基础。
- [阶段 11 · 13 构建生产环境中的 LLM 应用](../../../11-llm-engineering/13-production-app/docs/zh.md)：从原型到生产需要补哪些能力。
- [阶段 13 · 21 LLM 路由层：LiteLLM、OpenRouter、Portkey](../../../13-tools-and-protocols/21-llm-routing-layer/docs/zh.md)：two-provider minimum 依赖的网关/路由层。

### 本节被哪些后续内容用到
- [阶段 17 · 02 Inference 平台经济性](../../02-inference-platform-economics/docs/zh.md)：超大云之外的推理平台对比。
- [阶段 17 · 08 Inference 指标：TTFT、TPOT、ITL、Goodput、P99](../../08-inference-metrics-goodput/docs/zh.md)：本节 SLA 中 TTFT、P99 的精确定义与测量。
- [阶段 17 · 16 将模型路由作为降低成本的基本手段](../../16-model-routing/docs/zh.md)：在多个平台/模型之间按成本与质量路由。
- [阶段 17 · 19 AI 网关：LiteLLM、Portkey、Kong AI Gateway、Bifrost](../../19-ai-gateways/docs/zh.md)：故障切换、统一计费与请求打标。
- [阶段 17 · 26 合规：SOC 2、HIPAA、GDPR、PCI-DSS、EU AI Act、ISO 42001](../../26-compliance-frameworks/docs/zh.md)：BAA、数据驻留等合规细节。
- [阶段 17 · 27 LLMs 的 FinOps：单位经济性与多租户成本归因](../../27-finops-llms/docs/zh.md)：本节 FinOps 归因面的深入展开。

### 延伸关键词
`AWS Bedrock` · `Azure OpenAI` · `Vertex AI` · `Model Garden` · `Azure AI Foundry` · `PTU / Provisioned Throughput` · `break-even utilization` · `Application Inference Profiles` · `BigQuery Billing Export` · `two-provider minimum` · `BAA` · `data residency` · `abuse monitoring opt-out` · `TTFT P99`
