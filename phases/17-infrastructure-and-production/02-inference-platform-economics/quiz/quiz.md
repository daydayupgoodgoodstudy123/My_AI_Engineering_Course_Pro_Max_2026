# 测验 · Inference 平台经济性：Fireworks、Together、Baseten、Modal、Replicate、Anyscale（Inference Platform Economics — Fireworks, Together, Baseten, Modal, Replicate, Anyscale）

> **阶段 17 · 基础设施与生产 · 第 02 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 说明：本节中文讲义是机器翻译，大量厂商名被误译（如 Fireworks →"烟花"、Baseten →"基地/基调"、Together →"共同"、Anyscale →"任何规模"），学习时请以英文版为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 市场三分法 | custom silicon（Groq LPU、Cerebras WSE、SambaNova RDU）/ GPU 平台（Baseten、Together、Fireworks、Modal、Anyscale）/ API-first 市场（Replicate、DeepInfra、OpenRouter、Fal） |
| 2 | 三种计价函数 | per-token（按消耗的 token，空闲不付钱）、per-minute / per-second（按墙钟 GPU 时间，独占）、per-prediction（按调用次数，多见于图像/视频） |
| 3 | 必须先归一化再比较 | 不同计价单位不能直接比，要结合工作量模型折算成 **有效 $/M tokens** 或 $/day |
| 4 | per-token vs per-minute 的盈亏平衡 | 盈亏平衡利用率 `u* = 每分钟价格 / (满载每分钟 token 数 × per-token 单价)`；讲义经验值约 30%，本节代码参数下算出约 68% |
| 5 | 预留下限（reserved floor） | per-minute 的真实成本由 `max(满载分钟数, 预留分钟数)` 决定；24h 预留时，低流量下有效单价会被放大数百倍 |
| 6 | 各家定位 | Fireworks 拼延迟（FireAttention）、Together 拼目录广度、Baseten 拼企业合规（Truss、SOC 2 Type II、HIPAA-ready）、Modal 拼 Python 原生 DX、Replicate 拼多模态、Anyscale 拼 Ray 分布式 |
| 7 | 差异化在哪 | 讲义：vLLM + SGLang 约占生产开源 inference 的 80%，平台层真正的差异化是 DX、成本归因（attribution）和 SLA，"自研引擎"带营销成分 |
| 8 | 批处理档（batch tier） | 非交互流量走 batch tier，约为 serverless 价格的 50%；混合成本 = 加权平均 |
| 9 | 冷启动（cold start） | serverless 平台的隐性成本：首请求延迟；需要预热 / `min_workers=1` 等缓解，代价是又回到了"为空闲付费" |
| 10 | 需要记住的数字（讲义） | Fireworks 2026-05-01 起 GPU 租用 +$1/hr、估值 $4B、日处理 10T+ token；Baseten $5B（2026 年 1 月 E 轮 $300M）；Modal $1.1B（2025 年 B 轮） |

### 核心技能（能动手做到）

- [ ] 把 per-token、per-minute、per-prediction 三种报价用同一个工作量模型折算为 $/day 与有效 $/M tokens
- [ ] 手算任意一对 per-token / per-minute 厂商的盈亏平衡利用率，并解释它为什么与讲义的"30% 经验值"可能不同
- [ ] 看懂 `cost_per_day` 中"预留分钟下限"对低流量场景的放大效应
- [ ] 计算 batch tier 分流后的混合单价（如 40% 流量走 5 折）
- [ ] 根据工作负载画像（突发/稳定、延迟 SLA、合规、模态）选出主平台与备选平台，并说出切换条件
- [ ] 指出玩具模型漏掉的成本项（冷启动、网关、可观测性、利用率波动）

---

## 二、基础自测（选择题）

**Q1.** 讲义把 2026 年的 inference 市场分成三段。下列归类**全部正确**的是：

- A. custom silicon：Groq、Cerebras、SambaNova；GPU 平台：Baseten、Fireworks、Modal；API-first：Replicate、DeepInfra
- B. custom silicon：Groq、Fireworks；GPU 平台：Baseten、Replicate；API-first：Modal、OpenRouter
- C. custom silicon：Cerebras、Together；GPU 平台：RunPod、Lambda；API-first：Bedrock、Fal
- D. custom silicon：SambaNova、Anyscale；GPU 平台：Groq、Modal；API-first：Replicate、Baseten

**Q2.** 按本节 `code/main.py` 的参数（Fireworks $0.90/M、Baseten $0.55/min、满载 900k tok/min、Baseten 每天预留 1440 分钟），Baseten 开始比 Fireworks 便宜的持续利用率约为：

- A. 5%
- B. 30%
- C. 50%
- D. 68%

**Q3.** 在 Scenario A（每天 2M 输出 token）里，Baseten 的有效单价是 **$396/M tokens**，比 Fireworks 贵了 440 倍。最直接的原因是：

- A. Baseten 的 `tokens_per_minute` 比 Fireworks 低
- B. Baseten 按 1440 分钟/天的预留下限计费，实际只需要约 2.2 分钟满载时间，其余全在为空闲付费
- C. Baseten 的冷启动是 5 秒，代码把冷启动时间折算进了成本
- D. Baseten 按 prediction 计费，10,000 次请求导致成本很高

**Q4.** 讲义对 Fireworks 的 LoRA 定价有一个"真正的差异化"描述，它是：

- A. LoRA 模型必须单独购买专用 GPU
- B. LoRA 请求比基础模型贵 50%
- C. 微调（LoRA）模型按基础模型相同的单价提供服务
- D. Fireworks 不支持 LoRA

**Q5.** 一家医疗客户要求 SOC 2 Type II、HIPAA-ready、专用 GPU。根据讲义与 `outputs/` 中的 skill，最合适的默认选择是：

- A. Replicate
- B. Modal
- C. Together serverless
- D. Baseten

**Q6.** 关于"自研引擎是真正的护城河"这一小节，讲义的真实观点是：

- A. vLLM + SGLang 约占生产开源 inference 的 80%，"自研引擎"说法带营销色彩，平台层真正的差异化在 DX、成本归因与 SLA
- B. 自研引擎永远比 vLLM 快 4 倍，所以是唯一的护城河
- C. 所有自研引擎都是 TensorRT-LLM 的分支
- D. 只有 per-token 价格才是差异化因素

**Q7.** 你的主模型在 Fireworks 上 $0.90/M 输出 token。把 40% 的流量迁到 batch tier（5 折）后，混合单价约为：

- A. $0.45/M
- B. $0.54/M
- C. $0.72/M
- D. $0.81/M

**Q8.** 关于本节代码的 `cold_start_penalty()`，说法正确的是：

- A. 它把冷启动秒数乘以 GPU 单价，计入每日成本
- B. 它只是把 `cold_start_sec × 100` 作为"每天额外延迟秒数"打印出来，**不进入任何成本计算**
- C. 它计算的是 P99 TTFT
- D. 它只对 per-minute 厂商生效

---

## 三、动手 / 代码题

**Q9.** 阅读 `cost_per_day` 与厂商参数：

```python
    Vendor("Baseten",  "Custom Llama 70B", None, 0.55, None, 900_000, 5.0, "...", 1440),
    Vendor("Modal",    "Custom Llama 70B", None, 0.48, None, 800_000, 2.5, "...", 60),
    Vendor("Anyscale", "Llama 70B RayTurbo", None, 0.60, None, 850_000, 3.0, "...", 1440),

    if v.per_minute is not None:
        saturated_minutes = tokens_per_day / v.tokens_per_minute
        minutes = max(saturated_minutes, v.min_reserved_minutes_per_day)
        return minutes * v.per_minute
```

1. 写出 per-minute 厂商在"超过预留下限"之后的**饱和有效单价**（$/M tokens）公式，并分别算出 Baseten、Modal、Anyscale 的值。
2. 为什么 Scenario B（100M token/天）里 Modal 只要 $60/天、比 Fireworks 还便宜？这个结论在现实中靠得住吗？
3. Modal 从多少 token/天开始比 Fireworks 便宜？

**Q10.** 讲义说"超过约 30% 持续利用率，per-minute 开始击败 per-token"，代码末尾却打印"~60-70%"。

1. 推导一般化的盈亏平衡公式 `u*`，用代码参数验证约 68%。
2. 保持 Fireworks 价格和吞吐不变，Baseten 每分钟价格要降到多少，盈亏平衡点才会落在讲义说的 30%？
3. 由此说明"30% 经验值"在什么条件下成立。

**Q11.** Replicate 的成本 `predictions_per_day × 0.006` 与 token 数无关。

1. 每个 prediction 平均产生多少输出 token 时，Replicate 与 Fireworks 成本相同？
2. 代码在 Scenario A/B 里都隐含了每个 prediction 200 个 token，此时 Replicate 的有效单价是多少？与讲义"Together 比 Replicate 便宜 50–70%"一致吗？
3. `Vendor` 里 Replicate 的 `tokens_per_minute=750_000` 起什么作用？

**Q12.**（讲义练习 5）假设每个 prediction 平均 200 个输出 token，用本节代码计算 Fireworks、Together、Baseten、Modal、Replicate、Anyscale 在 **10 次/天** 和 **10,000 次/天** 下每 1,000 次 prediction 的成本，并指出最便宜者与最贵者。

---

## 四、面试高频题

**Q13.**（基础必考）per-token、per-minute、per-prediction 三种计价方式分别适合什么工作负载？怎样把它们放到同一张表里比较？

**Q14.**（原理深挖）讲义说 per-token API 的价格"向 serving 引擎的成本曲线压缩，而不是硬件的成本曲线"，这句话是什么意思？为什么同样一张 H100，不同平台能给出差别很大的 per-token 价格？

**Q15.**（场景设计）你的产品同时提供图片生成、聊天和语音转文字。请为每种模态选平台，并说明你会如何用网关（gateway）把它们统一起来。

**Q16.**（工程实践）一家初创公司每天 2M 输出 token、流量突发、TTFT SLA < 500ms，CTO 想"直接包一张卡跑自己的 70B 更省钱"。你如何用数据说服或支持他？

**Q17.**（追问型）既然 batch tier 能打 5 折、per-minute 在高利用率下更便宜，为什么很多团队仍然坚持 serverless per-token？玩具成本模型漏掉了哪些真实成本？

---

## 五、参考答案与解析

### Q1 — 答案：A

讲义原文：custom silicon 是 Groq（LPU）、Cerebras（WSE）、SambaNova（RDU）；GPU 平台是 Baseten、Together、Fireworks、Modal、Anyscale；API-first 市场是 Replicate、DeepInfra、OpenRouter、Fal。B 把 Fireworks（GPU 平台）放进了 custom silicon，又把 Modal 当成 marketplace；C 中 RunPod、Lambda 在讲义里是"原始 GPU 租赁"，Bedrock 是超大规模云托管服务，都不属于这三类中的对应项；D 把 Anyscale、Groq、Baseten 全部放错。

### Q2 — 答案：D

Baseten 每天固定 `1440 × 0.55 = $792`。Fireworks 达到 $792 需要 `792 / 0.9 × 1e6 = 880M` token；满载容量 `900k × 1440 = 1,296M` token/天，所以 `u* = 880 / 1296 ≈ 67.9%`。代码表格里 50% 时 Fireworks $583.20 仍更便宜、75% 时 $874.80 才输给 Baseten；逐点扫描得 67% → $781.49（Fireworks 胜）、68% → $793.15（Baseten 胜）。B（30%）是讲义的经验值，与代码参数不一致（见 Q10）。

### Q3 — 答案：B

2M token / 900k tok/min ≈ 2.2 分钟满载，但 `max(2.2, 1440) = 1440` 分钟，成本 `1440 × 0.55 = $792`，折算 `792 / 2 = $396/M`。A 错：Baseten 的 `tokens_per_minute`（900k）与 Fireworks 相同，且 Fireworks 的吞吐字段根本不参与计费；C 错：冷启动只用于打印，不进成本；D 错：Baseten 的 `per_prediction` 是 `None`。

### Q4 — 答案：C

讲义："Fine-tuned model served at the same rate as the base model — a real differentiator versus providers that charge a premium for your LoRA." Key Terms 中也有"Fine-tuned at base rate"。A、B 描述的正是讲义所说"其他厂商收溢价"的做法；D 与事实相反。

### Q5 — 答案：D

讲义：Baseten "SOC 2 Type II, HIPAA-ready. Common fintech and healthcare pick"，并提供专用 GPU（T4 到 B200、per-minute）。skill 的拒绝规则也写明：受监管客户若选 Modal 或 Replicate 要拒绝并建议 Baseten。C 是共享 serverless，不满足"专用 GPU"。

### Q6 — 答案：A

讲义："the honest framing is that vLLM + SGLang represent about 80% of production open-source inference, and the differentiators at the platform layer are DX, attribution, and SLAs." B 把 Fireworks "4x lower latency than vLLM" 的营销说法当成了普遍事实；C 是捏造；D 与"多维成本函数"的观点相反。

### Q7 — 答案：C

`0.6 × 0.90 + 0.4 × 0.45 = 0.72`，即降低 20%。A 是 100% 走 batch；B 是把 40% 当成"打 4 折"之类的误算（`0.9 × 0.6`）；D 是只省了 10%。讲义练习 3 还叠加了"GPU 租用 +$1/hr"，那部分只影响按 GPU 时长租用的用户，per-token serverless 价格不会直接改变——计算前先确认自己用的是哪种计价。

### Q8 — 答案：B

```python
        impact_sec = v.cold_start_sec * 100
        print(f"{v.name:12}  {v.cold_start_sec:>8.1f} s   +{impact_sec:.0f} seconds/day of extra latency")
```

只是乘以 100 后打印；`cost_per_day` 完全没有用到 `cold_start_sec`。C 错：P99 需要分布，这里只有一个常数；D 错：它遍历全部 6 家，包括 per-token 厂商。另外"每天累计额外延迟秒数"是个不太有意义的指标——用户感知的是单次首包延迟和 P99，而不是总和。

### Q9 — 参考答案

1. 超过预留下限后 `minutes = tokens / tokens_per_minute`，所以有效单价恒为 `per_minute / tokens_per_minute × 1e6`：
   - Baseten：`0.55 / 900,000 × 1e6 ≈ $0.611/M`
   - Modal：`0.48 / 800,000 × 1e6 = $0.600/M`
   - Anyscale：`0.60 / 850,000 × 1e6 ≈ $0.706/M`
   三者满载单价都低于 Fireworks $0.90/M 和 Together $0.88/M——这正是"高利用率时 per-minute 更便宜"的来源。
2. Modal 的预留下限只有 60 分钟，100M / 800k = 125 分钟 > 60，于是按 `125 × 0.48 = $60` 计费，等价于 $0.60/M。但这隐含了一个很强的假设：**流量被完美压缩成"满载的 125 分钟"，其余时间完美缩容到零**。真实流量是分散在 24 小时里的，GPU 在两次请求之间不会处于 100% 饱和；而且 Baseten/Anyscale 被假设成 24h 预留、Modal 却只有 60 分钟预留，三者口径并不对称，结论偏向 Modal。代码 docstring 自己也说这个下限是为了让两个函数"口径一致"，但厂商之间的口径仍不一致。
3. Modal 下限成本 `60 × 0.48 = $28.80/天`，Fireworks 达到 $28.80 需要 `28.8 / 0.9 = 32M` token/天；此时 Modal 仍处于下限内（下限可覆盖 `60 × 800k = 48M` token）。所以 **32M token/天以上 Modal 更便宜**——换算成 24h 满载利用率只有约 2.8%（`32M / 1,152M`），这就是"预留下限决定盈亏平衡点"的直观体现。

### Q10 — 参考答案

1. 设 per-minute 价格 `p_m`（$/min）、满载吞吐 `r`（tok/min）、per-token 价格 `p_t`（$/M）。24h 预留下 per-minute 每天 `1440 × p_m`；利用率 u 时 token 数 `u × r × 1440`，per-token 成本 `u × r × 1440 × p_t / 1e6`。令两者相等：

   `u* = p_m / (r × p_t / 1e6)`

   代入 `0.55 / (900,000 × 0.9 / 1e6) = 0.55 / 0.81 ≈ 0.679`，即约 68%，与代码打印的"~60-70%"一致。Anyscale 同理：`0.60 / (850,000 × 0.9 / 1e6) ≈ 78.4%`。
2. 令 `u* = 0.3`：`p_m = 0.3 × 0.81 = $0.243/min`（约 $14.6/小时）。即 Baseten 价格要降到现在的约 44%，盈亏平衡点才落在 30%。
3. "30%"不是物理常数，而是 `p_m / (r × p_t)` 这个比值的一个取值。per-minute 越便宜、引擎吞吐 `r` 越高（例如更好的 batching、量化）、per-token 越贵，盈亏平衡点越低。讲义与代码不一致本身就说明：**必须用自己的价格和实测吞吐重新算**，不能照搬经验值。skill 文件里也仍写"~30%"，与代码结论冲突。

### Q11 — 参考答案

1. `0.006 / (0.9 / 1e6) ≈ 6,667` token/prediction。平均输出少于约 6.7k token 时 Replicate 更贵，多于时反而更便宜（per-prediction 不随长度涨价）。
2. Scenario A：2M token / 10,000 次 = 200 token/次，Scenario B：100M / 500,000 = 200 token/次。Replicate 有效单价 `0.006 / 200 × 1e6 = $30/M`，Together $0.88/M 比它便宜约 97%，远超讲义说的 50–70%。原因是"per-prediction 的 LLM 价格"在代码里是随手设的参数，且结果高度依赖每次输出长度；讲义的 50–70% 是厂商间真实 per-token 报价的比较。用玩具参数去"验证"市场结论要谨慎。
3. 不起任何作用。`tokens_per_minute` 只在 per-minute 分支里使用；Fireworks、Together、Replicate 的这个字段都是装饰性的。

### Q12 — 参考答案

（已用本节代码实际计算，`tokens = 次数 × 200`）

| 厂商 | 10 次/天：每 1,000 次 | 10,000 次/天：每 1,000 次 |
|------|---------------------|-------------------------|
| Fireworks | $0.18 | $0.18 |
| Together | $0.176 | $0.176 |
| Baseten | $79,200 | $79.20 |
| Modal | $2,880 | $2.88 |
| Replicate | $6.00 | $6.00 |
| Anyscale | $86,400 | $86.40 |

- 两种流量下最便宜的都是 Together（略低于 Fireworks），最贵的都是 Anyscale。
- per-token 与 per-prediction 的"每千次成本"与流量无关；per-minute 厂商的每千次成本与流量成反比——10 次/天时 Baseten 一天 $792 被摊到 10 次请求上。这就是 skill 中"低于 100k token/天拒绝推荐 per-minute"的原因。
- 注意讲义练习 5 提到的 Llama 3.1 70B 实际报价需要查各家价格页；这里只用代码的近似参数。

### Q13 — 参考回答要点

- **per-token**：按实际消耗计费，空闲不付钱。适合突发、低到中等流量、对延迟不极端敏感的场景（Fireworks、Together serverless）。
- **per-minute / per-second**：按墙钟 GPU 时间计费，独占资源。适合高且稳定的利用率、需要专用环境/合规/自定义模型（Baseten、Modal、Anyscale 的专用部署）。
- **per-prediction**：按调用次数计费，适合单次成本较稳定的图像/视频/音频模型（Replicate）。
- **统一比较**：先建立工作量模型（token/天、请求数/天、平均输出长度、峰谷比），再折算成 $/day 和有效 $/M tokens；per-minute 要明确是否有预留下限、能否缩容到零；per-prediction 要按平均输出长度折算。
- 加分点：给出盈亏平衡公式 `u* = p_m / (r × p_t)`，并强调 r 是"实测满载吞吐"，而不是厂商宣传值。
- 常见误区：直接拿 $/min 与 $/M tokens 比较（skill 的 hard reject 第一条）。

### Q14 — 参考回答要点

- per-token 价格的底层是 `GPU 小时成本 / 每 GPU 小时能产出的 token 数`。分母由 serving 引擎决定：continuous batching、PagedAttention、前缀缓存、speculative decoding、量化都会成倍提升单卡吞吐。
- 因此在硬件相同的情况下，引擎更好、利用率更高（多租户共享、流量聚合）的平台单 token 成本更低，市场价格向"最好引擎的成本曲线"收敛。
- 同一张 H100，平台 A 满载 + 高并发 batching，平台 B 低利用率，单 token 成本可以差几倍；这也是讲义说 Fireworks 的 per-token 价格"反映的是它们的利用率曲线"。
- 但讲义也提醒：vLLM + SGLang 约占生产开源 inference 的 80%，引擎差距在缩小，平台差异化更多来自 DX、归因、SLA。
- 加分点：联系阶段 17 · 04（PagedAttention、continuous batching）与 · 06（RadixAttention）说明这些技术如何改变 r。

### Q15 — 参考回答要点

- **图片生成**：Replicate（多模态默认平台、per-prediction、生态集成）。
- **聊天 LLM**：交互式低延迟用 Fireworks（延迟优化）或 Together（目录广、价格低）；若有严格合规或微调模型的专用需求，用 Baseten。
- **语音转文字**：讲义没有给出具体厂商，可选 Replicate 等多模态市场；若是实时语音 agent 且对延迟极敏感，讲义提到 Groq 是"voice agents 和实时翻译"的生产之选（主要用于 LLM 部分）。
- **网关模式**：前面放一个 AI gateway（LiteLLM、Portkey、Kong AI Gateway），统一认证、路由、重试/fallback、配额与成本归因，让产品代码与供应商变更隔离。skill 默认推荐加网关（除非规模低于 500 RPS）。
- 加分点：网关里按模态和 SLA 打标签，按调用记录每个功能的单位成本，为后续 FinOps 做准备。

### Q16 — 参考回答要点

- 先算账：2M token/天在 Fireworks 约 $1.80/天；按代码参数包一张卡全天预留（Baseten）约 $792/天，有效 $396/M，是 per-token 的 440 倍；即使按讲义 30% 经验值，这个流量也远低于阈值（满载容量约 1,296M token/天，利用率约 0.15%）。
- 突发流量 + TTFT < 500ms：serverless per-token 平台有共享热池，冷启动更少；自建专用卡反而要为预热付费。
- 什么时候支持他：流量增长到持续高利用率（按自己的实测吞吐算 `u*`）、有合规/数据驻留要求、需要定制模型且平台不支持、或需要稳定可预测的延迟时。
- 给出决策指标：每周看一次实际 token/天 与 `u* × 满载容量` 的比值；超过阈值并持续一段时间后再迁移。
- 常见误区：用"单价"而不是"有效单价"比较；只算 GPU 钱不算运维人力。

### Q17 — 参考回答要点

- **batch tier 的限制**：只适合非交互任务（离线评估、批量摘要、数据标注），完成时间以小时计，不能服务在线用户。
- **per-minute 的限制**：需要持续高利用率；流量有峰谷时要么为峰值预留（低谷空转），要么承受扩容延迟和冷启动；还要自己管理版本、扩缩容、监控。
- **玩具模型漏掉的成本**：
  - 冷启动的用户体验成本与预热成本（`min_workers=1` 本身就是预留）；
  - 输入 token 的价格（代码只算输出 token）；
  - 利用率随时间波动，"满载吞吐"在小 batch 下达不到；
  - 网关、可观测性、重试与 fallback 带来的额外调用；
  - 工程人力与运维（DX 差异）；
  - 合规认证与审计成本；
  - 供应商涨价风险（例如讲义提到的 Fireworks 2026-05-01 GPU 租用 +$1/hr）。
- skill 的观点：拒绝"只要最便宜"，要说明多维成本函数（token 单价 + 冷启动 + 归因 + 网关 + DX）。

---

## 六、关联知识点

### 前置知识
- [阶段 17 · 01 托管 LLM 平台：Bedrock、Vertex AI、Azure OpenAI](../../01-managed-llm-platforms/docs/zh.md)：超大规模云托管平台是本节的对照组。
- [阶段 17 · 04 服务引擎内部机制：PagedAttention、Continuous Batching 与 Chunked Prefill](../../04-vllm-serving-internals/docs/zh.md)：引擎吞吐决定 per-token 成本曲线。
- [阶段 11 · 11 缓存、请求速率限制与成本优化](../../../11-llm-engineering/11-caching-cost/docs/zh.md)：按 token 计费的基本成本意识。

### 本节被哪些后续内容用到
- [阶段 17 · 10 缓解无服务器 LLMs 的冷启动](../../10-cold-start-mitigation/docs/zh.md)：本节只打印了冷启动秒数，那里专门处理它。
- [阶段 17 · 15 批处理 APIs：作为行业标准的五折优惠](../../15-batch-apis/docs/zh.md)：batch tier 的深入讨论。
- [阶段 17 · 16 将模型路由作为降低成本的基本手段](../../16-model-routing/docs/zh.md)、[阶段 17 · 19 AI 网关：LiteLLM、Portkey、Kong AI Gateway、Bifrost](../../19-ai-gateways/docs/zh.md)：多平台统一入口与路由。
- [阶段 17 · 27 LLMs 的 FinOps：单位经济性与多租户成本归因](../../27-finops-llms/docs/zh.md)：把有效单价进一步落到每个租户、每个功能。
- [阶段 17 · 28 自托管服务选型：让引擎匹配硬件与规模](../../28-self-hosted-serving-selection/docs/zh.md)：决定"自己跑"之后如何选引擎。
- [阶段 13 · 21 LLM 路由层：LiteLLM、OpenRouter、Portkey](../../../13-tools-and-protocols/21-llm-routing-layer/docs/zh.md)：网关层的协议视角。

### 延伸关键词
`per-token / per-minute / per-prediction` · `effective $/M tokens` · `break-even utilization` · `reserved capacity` · `scale-to-zero` · `batch tier` · `FireAttention` · `Truss` · `RayTurbo` · `custom silicon (LPU / WSE / RDU)` · `AI gateway` · `FinOps`
