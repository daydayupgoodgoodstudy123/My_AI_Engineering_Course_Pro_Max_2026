# 代码讲解 · main.py

> **所属小节**：阶段 16 · 多智能体与集群 · 第 16 节 协商与议价 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无参数） ｜ **依赖**：仅标准库（`random`、`dataclasses`），无需 API key、无需网络

---

## 1. 这份代码在考察什么

讲义的核心工程规则是："Let the LLM narrate. Do not let the LLM compute the offer." 这份代码用两个部分来说明：

1. **议价模拟**：买方分别用"朴素 LLM"（高方差随机出价，经常越出 ZOPA）和"OG-Narrator"（确定性的固定比例让步）与同一个确定性卖方议价，在 1000 组随机保留价上统计**成交率**；
2. **Contract Net 任务市场**：一个 manager、三个 bidder，演示 `cfp → propose → accept / reject` 与按 `置信度 / 价格` 授标。

> 一句话：**把"出价"从语言模型手里拿走，交给算术——成交率立刻上升**。但要注意：代码里并没有任何"narrator"（没有生成任何自然语言），OG 买方的开局价用到了卖方的私有保留价，而且只统计成交率、不统计谁拿到了多少剩余——OG 买方在成交率上赢了，在收益上却输得很惨。这些是阅读本节代码的关键批判点。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `BargainState` | `@dataclass` | 双方保留价、当前报价、轮数、轮数上限 | 议价状态 |
| `naive_llm_bargain` | 函数 | 随机出价，范围常越过 ZOPA | 全 LLM 出价的策略错误 |
| `og_narrator_bargain` | 函数 | 开局 + 每轮向对方报价让步 35% | 确定性 offer generator |
| `seller_response` | 函数 | 卖方每轮向买方报价让步 30%，不低于 `seller_min` | 对手策略（两种买方共用） |
| `simulate_bargain` | 函数 | 交替出价直到交叉或 5 轮用完；检查成交价是否在双方保留价内 | 议价协议 + ZOPA 校验 |
| `bench_deal_rate` | 函数 | 1000 组随机保留价下统计成交率 | 评测 |
| `Bid` / `ContractNetTask` | `@dataclass` | 投标（价格、ETA、置信度）/ 任务（截止、预算） | Contract Net 消息内容 |
| `ContractNetManager` | 类 | `broadcast_cfp`、`receive_proposal`、`award` | Contract Net manager |
| `demo_contract_net` | 函数 | 1 个任务、3 个投标的演示 | 任务市场 |

数据流：`main()` → `bench_deal_rate(naive)` 与 `bench_deal_rate(og)`（各自 `random.Random(42)`，逐次采样 `seller_min ∈ [50, 80]`、`buyer_max ∈ [max(seller_min+5, 75), 115]` → `simulate_bargain`）→ `demo_contract_net()` → Takeaways。

讲义 Build It 说 OG-Narrator 是"deterministic **Zeuthen-style** concession toward the midpoint"，实际代码是"每轮让出与对方报价差距的固定 35%"——既不是 Zeuthen 策略（Zeuthen 按双方"冲突风险承受度"比较决定谁让步），也不是"向中点"让步。

---

## 3. 逐段精讲

### 3.1 `BargainState`

```python
@dataclass
class BargainState:
    buyer_max: int
    seller_min: int
    buyer_offer: int | None = None
    seller_offer: int | None = None
    rounds: int = 0
    max_rounds: int = 5
```

- `buyer_max`（买方最高愿付）与 `seller_min`（卖方最低接受）是**双方各自的私有信息**，ZOPA = `[seller_min, buyer_max]`。
- 关键设计问题：买卖双方的策略函数都拿到**同一个** `state` 对象，里面同时放着两边的保留价。这等于把"私有信息"放进了公共状态——skill 文件明确把"single agent hold both buyer and seller state"列为硬拒绝。下面会看到 OG 买方确实读了 `seller_min`。
- `max_rounds = 5` 是讲义 Ship It "3–5 rounds maximum" 的上限，也是 OG 失败的直接原因（见 3.5）。

### 3.2 朴素 LLM 买方

```python
def naive_llm_bargain(state, rng):
    r = rng.random()
    if state.seller_offer is None:
        candidate = rng.randint(state.buyer_max - 60, state.buyer_max + 30)
    elif r < 0.35:
        candidate = state.seller_offer + rng.randint(-8, 3)
    elif r < 0.65:
        candidate = rng.randint(state.seller_min - 30, state.buyer_max + 30)
    else:
        candidate = rng.randint(state.seller_min - 60, state.buyer_max + 60)
    return candidate
```

- 用随机数模拟讲义转述的 LLM 策略错误："offer at nonsensical prices, ignore the other side's ZOPA"。开局价可能比自己的上限还高 30；之后 35% 的概率"贴着对方报价"，30% 在宽区间乱报，35% 在更宽的区间乱报。
- `rng.randint(a, b)` 是**闭区间** `[a, b]`。
- 注意它也用到了 `state.seller_min`（对方私有信息）来决定随机区间——不过这里只是为了生成"有时越界"的分布，影响不大。

### 3.3 OG-Narrator 买方

```python
def og_narrator_bargain(state, rng, concession: float = 0.35):
    if state.seller_offer is None and state.buyer_offer is None:
        return state.buyer_max - max(1, int((state.buyer_max - state.seller_min) * 0.2))
    if state.seller_offer is None:
        return state.buyer_offer
    prior = state.buyer_offer if state.buyer_offer is not None else state.buyer_max
    move = max(1, int(concession * (state.seller_offer - prior)))
    candidate = prior + move
    candidate = min(candidate, state.buyer_max)
    return candidate
```

- **开局**：`buyer_max − 20% × ZOPA 宽度`。例如 `buyer_max = 100, seller_min = 60` 时开局 92。这里用到了 `seller_min`——卖方的私有保留价，现实中的买方根本不知道。实测 `seller_min` 从 60 改为 90，开局价从 92 变成 98。
- **让步**：每轮向卖方报价靠拢差距的 35%，至少 1；并用 `min(..., buyer_max)` 保证**永不越过本方保留价**——这正是确定性 offer generator 的核心价值：报价永远在本方可接受范围内。
- `max(1, ...)` 保证每轮至少让 1，防止僵持；但如果卖方报价低于买方上一口价，`move` 计算为负，会被强制成 1——即买方仍会"加价"，不过这种情况下双方已交叉、协议会先结束。
- `rng` 参数完全没有使用（为了与朴素版本保持同样的函数签名）。
- **没有任何 narration**：函数只返回一个整数，代码里没有生成任何自然语言消息。所谓 "Narrator" 只存在于名字里。

### 3.4 卖方策略与一段死代码

```python
def seller_response(state, rng, concession: float = 0.3):
    if state.buyer_offer is None and state.seller_offer is None:
        return state.seller_min + max(1, int((state.buyer_max - state.seller_min) * 0.4))
    if state.buyer_offer is None:
        return state.seller_offer
    prior = state.seller_offer if state.seller_offer is not None else state.seller_min + 20
    move = max(1, int(concession * (prior - state.buyer_offer)))
    candidate = prior - move
    candidate = max(candidate, state.seller_min)
    return candidate
```

- `simulate_bargain` 每轮都是**买方先出价**，卖方被调用时 `buyer_offer` 一定不是 None，因此第一个分支（卖方开局，且用到了 `buyer_max`）和第二个分支**都是死代码**。卖方真正的起点是第 3 行的回退值 `seller_min + 20`。
- 后果一：当 ZOPA 宽度 < 20 时，卖方从高于 `buyer_max` 的位置起步。
- 后果二：当买方开局价高于 `seller_min + 20` 时，`move = max(1, int(0.3 × 负数))` 被强制为 1，卖方报 `seller_min + 19`，立刻低于买方开局价，**以买方开局价成交**——卖方白捡了差价。
- `int()` 对负数是**向零取整**：`int(-3.6) = -3`，不是 `-4`。

### 3.5 `simulate_bargain`：交替出价与可行性检查

```python
    while state.rounds < state.max_rounds:
        state.buyer_offer = buyer_fn(state, rng)
        if state.seller_offer is not None and state.buyer_offer >= state.seller_offer:
            if state.seller_offer >= state.seller_min and state.seller_offer <= state.buyer_max:
                deal = True
            break
        state.seller_offer = seller_response(state, rng)
        if state.buyer_offer is not None and state.seller_offer <= state.buyer_offer:
            if state.buyer_offer <= state.buyer_max and state.buyer_offer >= state.seller_min:
                deal = True
            break
        state.rounds += 1
```

- 两个交叉点：买方出价 ≥ 卖方要价时按**卖方要价**成交；卖方要价 ≤ 买方出价时按**买方出价**成交。
- **可行性检查**就是讲义 Ship It 的 "Reject out-of-ZOPA offers at the protocol boundary"：成交价必须在 `[seller_min, buyer_max]` 内，否则这次议价记为失败并**立即结束**（`break`）。
- 对朴素买方而言，最常见的失败就是"出价高于自己的 `buyer_max`"（1000 次中 336 次）。现实中没有这道校验，卖方会接受，买方会亏本成交——模拟器里的"失败"在现实里是"更糟的成功"。
- 逐次追踪 1000 次试验的结局分布（实测）：

| 结局 | 朴素 LLM | OG-Narrator |
|------|---------|-------------|
| 按卖方要价成交 | 436 | 97 |
| 按买方出价成交 | 169 | 795 |
| 出价越过 `buyer_max` 被判不可行 | 336 | 0 |
| 接受了高于 `buyer_max` 的要价，判不可行 | 24 | 0 |
| 5 轮超时 | 35 | 108 |

- OG 的 108 次失败**全是超时**，对应 ZOPA 宽度 5–13：卖方从 `seller_min + 20`（高于 `buyer_max`）起步，每轮只让 30%，而买方已封顶在 `buyer_max`，5 轮追不上。把 `max_rounds` 改为 10，OG 成交率变为 **100%**（1000/1000）。代码 Takeaway "OG-Narrator ... converges on every trial" 与 89.2% 的输出不符，正确的说法是"给足轮数时每次都能收敛"。

### 3.6 成交率之外：剩余分配

代码只统计成交率。我们额外统计了"买方剩余占比 = (buyer_max − 成交价) / (buyer_max − seller_min)"（实测）：

| 买方策略 | 成交数 | 买方平均剩余占比 | 第 0 轮成交次数 |
|---------|-------|----------------|---------------|
| 朴素 LLM（5 轮） | 605 | 57.4% | 142 |
| OG-Narrator（5 轮） | 892 | 16.5% | 719 |
| OG-Narrator（10 轮） | 1000 | 14.7% | 719 |

- OG 买方 72% 的成交发生在第 0 轮，以自己的开局价（`buyer_max` 往下仅 20%）成交，所以平均只拿到约 1/6 的剩余。
- 这说明 OG-Narrator 的"结构优势"在本模拟里只体现在成交率上；收益取决于 offer generator 的参数（开局锚点、让步速度），需要单独设计与评估。讲义 Ship It 也要求"Measure deal rate **and payoff variance**"。

### 3.7 `bench_deal_rate`

```python
def bench_deal_rate(buyer_fn, label, trials=1000):
    rng = random.Random(42)
    for _ in range(trials):
        seller_min = rng.randint(50, 80)
        buyer_max = rng.randint(max(seller_min + 5, 75), 115)
```

- 每个策略都重新 `Random(42)`，但朴素买方在议价过程中会消耗随机数，OG 不会，所以两者从第 2 次试验起抽到的保留价序列就不同了。严格的对照实验应先生成 1000 组保留价，再让两种策略分别跑同一组。
- `buyer_max ≥ seller_min + 5` 保证每次都有 ZOPA；`max(..., 75)` 让 `buyer_max` 至少 75。

### 3.8 Contract Net 任务市场

```python
    def award(self, task):
        props = self.proposals.get(task.task_id, [])
        feasible = [b for b in props if b.price <= task.budget and b.eta_minutes <= task.deadline_minutes]
        if not feasible:
            print("    no feasible bid; awarding rejected")
            return None
        winner = max(feasible, key=lambda b: b.confidence / max(b.price, 1))
        ...
        for b in props:
            if b is not winner:
                print(f"  manager reject-proposal -> {b.bidder}")
        return winner
```

- 先按预算和截止时间过滤，再按 `confidence / price` 选最大值；`max(b.price, 1)` 防止价格为 0 时除零。
- 评分结果：worker-a 0.273，worker-b 0.385，worker-c 0.225 → worker-b 中标。价格在分母上，影响被放大；ETA 只做过滤不参与评分，于是最快、最有把握的 worker-c 排最后（见测验 Q12 的多目标改造）。
- `b is not winner` 用**身份比较**而不是 `!=`：dataclass 默认按字段值比较相等，两个字段完全相同的投标会被 `==` 视为相等，用 `is` 才能准确排除中标者本身。
- 与 Contract Net 规范的差距：`broadcast_cfp` 只是初始化列表并打印，`self.bidders` 从未使用，投标是在 demo 里直接调用 `receive_proposal` 注入的；没有 `refuse`、没有收标截止、"无可行投标"时没有给各 bidder 发 `reject-proposal`、也没有执行结果的回报环节。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用随机数模拟"朴素 LLM 出价" | 无需 API 即可复现"越界报价"现象 | 真实 LLM 的错误是锚定差、象征性还价等，分布不同；讲义数字（26.67% → 88.88%）来自真实 LLM 基准 |
| 固定比例让步作为 offer generator | 最简单的确定性策略，报价永不越过本方上限 | 名为 Zeuthen 实非 Zeuthen；开局与让步参数决定剩余分配，需要调优 |
| 双方策略共享同一个 `state` | 写起来方便 | 私有保留价进入公共状态，OG 买方开局读了 `seller_min`；生产中双方各有私有状态，只交换报价消息 |
| 买方永远先出价 | 简化回合逻辑 | 卖方开局分支成为死代码；卖方以写死的 `seller_min + 20` 起步 |
| 越界成交记为失败并结束 | 模拟协议边界校验 | 现实中没有校验时这是"亏本成交"；应在发送前和接收后都做校验 |
| 5 轮上限 | 遵循讲义 3–5 轮建议 | 窄 ZOPA 下 OG 超时；生产中僵局应升级到调解者，而不是直接判失败 |
| 只统计成交率 | 与论文指标一致 | 看不到剩余分配和收益方差，OG 买方收益很差的问题被掩盖 |
| 没有 narrator | 聚焦机制 | 讲义所说的"LLM 叙述"完全缺席；可加一个模板/LLM 生成公开消息并与私有 scratchpad 分离 |
| `conf / price` 授标 | 一行代码兼顾质量与价格 | 价格权重过大、ETA 不计分；应使用多目标加权 + 质量下限 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass` 可选字段 | `buyer_offer: int \| None = None` | 默认值为 None，表示"还没出过价" |
| 可变状态对象 | `state.buyer_offer = buyer_fn(state, rng)` | dataclass 实例默认可修改，多个函数共享同一个对象 |
| 函数作为参数 | `simulate_bargain(buyer_fn, rng, ...)`、`bench_deal_rate(naive_llm_bargain, "naive LLM")` | 函数是一等对象，可以像变量一样传递（策略模式） |
| 带默认值的关键字参数 | `concession: float = 0.35` | 调用时可覆盖，便于调参实验 |
| `random.Random(seed)` | `rng = random.Random(42)` | 独立、可复现的随机数生成器 |
| `rng.randint(a, b)` | `rng.randint(50, 80)` | 闭区间整数，两端都可能取到 |
| `int()` 截断 | `int(concession * (prior - state.buyer_offer))` | 向零取整：`int(-3.6) == -3` |
| `min` / `max` 截断 | `min(candidate, state.buyer_max)`、`max(candidate, state.seller_min)` | 把值限制在边界内（clamp） |
| 条件表达式 | `state.buyer_offer if state.buyer_offer is not None else state.buyer_max` | 判断 None 时用 `is not None`，避免把 0 误判为假 |
| 链式比较 | 可写成 `state.seller_min <= price <= state.buyer_max` | 代码中用 `and` 拆开写，两者等价 |
| `while` + `break` | `while state.rounds < state.max_rounds: ... break` | 达成交易时提前退出循环 |
| `lambda` | `max(feasible, key=lambda b: b.confidence / max(b.price, 1))` | 匿名函数作为排序/取最大的依据 |
| `is` 身份比较 | `if b is not winner:` | 判断是不是同一个对象，而非值相等 |
| 列表推导式过滤 | `[b for b in props if b.price <= task.budget and ...]` | 只保留满足条件的投标 |
| `dict.get` 默认值 | `self.proposals.get(task.task_id, [])` | 任务不存在时返回空列表 |
| 返回 `Optional` | `def award(...) -> Bid \| None` | 可能没有中标者 |
| f-string 百分比格式 | `{deals / trials:.2%}` | 自动乘 100 并加 `%`，保留两位小数 |
| f-string 宽度 | `{label:20s}`、`{bid.confidence:.2f}` | 左对齐 20 宽、两位小数 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 |

---

## 6. 运行结果解读

实际运行（Python 3.13，`cd code && python3 main.py`，不到 1 秒，结果确定）：

```text
========================================================================
DEAL RATE — naive LLM bargaining vs OG-Narrator
reservation prices sampled per trial: seller_min in [50,80], buyer_max in [75,115]
========================================================================
  naive LLM            deal rate: 60.50%  (605/1000)
  OG-Narrator          deal rate: 89.20%  (892/1000)

========================================================================
CONTRACT NET TASK MARKET — manager + 3 bidders
========================================================================
  manager CFP -> compress 10GB log bundle (deadline 30m, budget 10)
    propose from worker-a: price=3 eta=18m conf=0.82
    propose from worker-b: price=2 eta=25m conf=0.77
    propose from worker-c: price=4 eta=10m conf=0.90
  manager accept-proposal -> worker-b (score = conf/price)
  manager reject-proposal -> worker-a
  manager reject-proposal -> worker-c
```

逐项解读：

- **成交率 60.50% vs 89.20%**：差距 28.7 个百分点。讲义预期"naive ~65-75%、OG ~85-95%、差距 15-25 点"，朴素买方实际低于预期区间，差距也大于预期。
- **朴素买方为何失败**：主要是出价超过自己的 `buyer_max`（336 次），其次是接受了高于上限的要价（24 次）和超时（35 次）。
- **OG 为何失败**：全部是 5 轮超时，集中在 ZOPA 宽度 5–13 的窄区间（见 3.5）；轮数上限改为 10 即 100% 成交。
- **成交率不等于收益**：OG 买方平均只拿到 16.5% 的剩余，朴素买方成交时平均拿到 57.4%（见 3.6）。
- **Contract Net**：worker-b 因为最便宜而中标，最快、最有把握的 worker-c 落选，这是 `conf / price` 评分的直接后果。
- **Takeaways 的说法**："OG-Narrator ... converges on every trial" 与输出（892/1000）矛盾；"Our simulation shrinks the gap because the opposing seller is already using deterministic offers" 在本次运行中也不成立——模拟中的差距（28.7 点）并不比讲义预期区间小，反而更大。

---

## 7. 动手改一改

1. **公平对照**：先用 `Random(42)` 生成 1000 组 `(seller_min, buyer_max)`，再让两种买方在同一组保留价上议价；比较成交率与"买方剩余占比"两个指标。
2. **去掉信息泄露**：把 OG 开局改为只依赖本方信息，例如 `buyer_max × 0.75`，或基于卖方首个要价做锚定；观察成交率和买方剩余的变化。再把 `BargainState` 拆成 `BuyerPrivate`、`SellerPrivate` 和只含报价的 `PublicState`。
3. **轮数与调解**：把 `max_rounds` 从 3 扫到 10，画出成交率曲线；为超时情况加入"调解者"——取双方最后报价的中点，若在 ZOPA 内则成交，否则升级。
4. **真正的 narrator（讲义练习 2）**：给 OG 买方加一个叙述函数，按 persona（如 "desperate to buy this week"）从模板生成公开消息，报价数字只来自 offer generator；验证报价不变时成交率不变，再思考 persona 何时会影响一个"会读文本"的对手。
5. **CoT 隐藏（讲义练习 3）**：实现 `NegotiationTurn(private_scratchpad, public_message, offer)`，只把公开字段交给卖方；再模拟"通道接反"，让卖方读到 `buyer_max` 后每轮报 `buyer_max - 1`，比较买方剩余（测验 Q10：14.7% → 4.2%）。
6. **多目标授标（讲义练习 4）**：给 `award` 加入质量下限和价格/ETA/置信度加权评分，补上 `refuse` 消息与"无可行投标时逐个发送 reject-proposal"，并记录每个落选者的确定性理由。

---

## 8. 常见坑

- **只看成交率**：高成交率可能来自"开局就报接近上限的价格"，买方收益很差；必须同时统计剩余分配与收益方差。
- **把私有信息放进公共状态**：一旦策略函数能读到对方保留价，模拟出来的"好策略"在现实中无法实现。
- **以为有 Narrator**：本代码只有确定性出价，没有任何文本生成；不要把"OG-Narrator"误解为代码已演示了 LLM 叙述。
- **名不副实的 Zeuthen**：固定比例让步不是 Zeuthen 策略，面试时要能说清区别。
- **死代码掩盖了设计**：卖方的开局分支永远不会执行，真正起作用的是写死的 `seller_min + 20`。
- **`int()` 负数取整**：`int(-3.6)` 是 `-3`，再被 `max(1, ...)` 改成 1，让步方向可能与直觉相反。
- **越界报价的两种后果**：模拟器里记为失败，现实中没有校验会变成亏本成交；发送前、接收后都要校验。
- **授标公式的隐性偏好**：`conf / price` 对价格极度敏感，ETA 不计分；授标规则应显式、可解释，并告诉落选者原因。
