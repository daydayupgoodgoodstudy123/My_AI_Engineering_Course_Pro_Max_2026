# 测验 · 基准评测：WebArena 与 OSWorld（Benchmarks: WebArena and OSWorld）

> **阶段 14 · Agent 工程 · 第 20 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | WebArena 构成 | Zhou et al.（ICLR 2024）：812 个长程任务，四个自托管 web 应用（购物站、论坛、类 GitLab 开发工具、企业 CMS），外加地图、计算器、草稿板等工具 |
| 2 | 基于执行的评估 | 通过 gym API 检查最终状态：订单是否下了、issue 是否关了、CMS 页面是否更新——看结果，不看过程是否和参考一致 |
| 3 | 自托管的意义 | 目标应用版本固定、可复现，评测不会因为线上网站变化而"抖动" |
| 4 | WebArena 发布时差距 | 最好的 GPT-4 agent 14.41%，人类 78.24% |
| 5 | 扩展 | VisualWebArena（截图作为一等观测、需要理解图像）；TheAgentCompany（2024 年 12 月，加入终端与编码，更像远程办公环境） |
| 6 | OSWorld | Xie et al.（NeurIPS 2024）：Ubuntu / Windows / macOS 上 369 个真实任务，自由键鼠控制，观测是 1920×1080 截图；发布时最好模型 12.24%，人类 72.36% |
| 7 | 两大失败模式 | GUI grounding（像素 → 界面元素的定位）与 operational knowledge（哪个菜单、哪个快捷键、哪个偏好设置面板） |
| 8 | OSWorld-G | 564 个样本的 grounding 测试集 + Jedi 训练集，把 grounding 与 planning 拆开分别测量 |
| 9 | OSWorld-Human | 人工整理的 gold 动作轨迹；顶级 agent 的步数是必要步数的 1.4–2.7 倍（trajectory-efficiency gap） |
| 10 | 三种误用 | 用 DOM / 无障碍 API 的 agent 跑截图基准（绕过 grounding）、只看成功率不看轨迹长度、升级自托管应用却不重新整理任务 |

### 核心技能（能动手做到）

- [ ] 说清 WebArena 与 OSWorld 各自测什么、怎么评估、发布时人机差距多大
- [ ] 解释"基于执行的状态检查"相对"轨迹比对"的优点，以及它在副作用检查上的盲点
- [ ] 读懂 `main.py` 的购物应用、任务定义与评估循环，手算每个任务与总体的 trajectory efficiency
- [ ] 指出用 `len(trace)` 计步、宽松成功谓词带来的度量偏差，并修复
- [ ] 区分 grounding 失败与 planning 失败，设计一个最小的失败分类器
- [ ] 为自己的产品流程设计 gold 轨迹、状态重置、版本固定与沙箱策略

---

## 二、基础自测（选择题）

**Q1.** 关于 WebArena 的构成，正确的是：

- A. 369 个任务，覆盖 Ubuntu、Windows、macOS
- B. 2,294 个 GitHub issue，用单元测试判定
- C. 812 个长程任务，运行在四个自托管 web 应用上：购物站、论坛、类 GitLab 开发工具、企业 CMS
- D. 466 个问题，人类 92%、GPT-4 15%

**Q2.** WebArena 为什么要自托管目标应用？

- A. 固定应用版本、保证可复现，使基于执行的评估稳定、不抖动，不同时间的结果可比
- B. 为了避免使用 TLS
- C. 为了让 agent 可以用 GPU 加速浏览器
- D. 为了让 agent 能访问真实用户数据

**Q3.** 讲义引用的 OSWorld 发布时结果是：

- A. 最好的 agent 50%，人类 50%
- B. 最好的 GPT-4 agent 14.41%，人类 78.24%
- C. 最好的 agent 99%，人类 100%
- D. 最好的模型 12.24%，人类 72.36%

**Q4.** OSWorld 揭示的两大主要失败模式是：

- A. 延迟与带宽
- B. GUI grounding（像素到界面元素的映射）与 operational knowledge（菜单、快捷键、偏好面板等操作知识）
- C. 幻觉与拒答
- D. embedding 漂移与 token 泄露

**Q5.** OSWorld-G 相比基础 OSWorld 增加了什么？

- A. 564 个样本的 grounding 测试集与 Jedi 训练集，把 grounding 与 planning 拆开分别测量
- B. 人工整理的 gold 动作轨迹，用于衡量步数效率
- C. 更高的截图分辨率
- D. 新增 Android 系统

**Q6.** 运行 `code/main.py`，`revised_order` 任务打印 `steps: 7 (gold 5, efficiency 1.40x)`。这个 7 是怎么来的？

- A. 应用内部真实调用了 7 次方法
- B. 5 个 gold 步骤加上 2 次重试
- C. `len(trace)`：trace 有 7 行，其中包括一行并不是应用操作的 `"revised_choice: remove keyboard"`
- D. 购物车里最终有 7 件商品

**Q7.** `main.py` 最后打印 `step efficiency: 1.17x over gold`。它是怎么算的？

- A. 三个任务效率的平均值 `(1.00 + 1.00 + 1.40) / 3`
- B. 只统计成功任务的中位数
- C. 最大的单任务效率减去 0.23
- D. 总步数 / 总 gold 步数 = `(3 + 4 + 7) / (3 + 4 + 5) = 14 / 12`

**Q8.** 讲义提醒的 "screenshot-only evals" 问题是指：

- A. 截图太大，评估成本过高
- B. OSWorld 以截图为驱动；用一个使用 DOM 或无障碍 API 的 agent 去跑 OSWorld，会绕过它想测量的 grounding 挑战
- C. 截图无法保存，无法复现
- D. 截图会泄露用户隐私，因此禁止使用

---

## 三、动手 / 代码题

**Q9.** `buy_headphones` 的成功谓词是：

```python
            success=lambda app: any(
                o["items"].get("sku-001") == 1 for o in app.orders
            ),
```

1. 以下三种 agent 行为，谓词分别判成功还是失败？哪些是错误判定？
   - (a) 把耳机和鼠标放在同一单里一起买了；
   - (b) 先误下了一单键盘，再下一单耳机；
   - (c) 一次买了 2 副耳机。
2. `ShoppingApp.add_to_cart("sku-001", -3)` 之后 `checkout()` 会发生什么？这说明玩具应用缺了什么？
3. 写一个更严格的成功谓词工厂 `strict_success(expected_items)`，要求"恰好一单、商品与数量完全一致、购物车已清空"。这样做又会带来什么新问题？

**Q10.** 评估循环用 `steps = len(trace)` 计步：

```python
def _agent_task_3(app: ShoppingApp) -> list[str]:
    trace: list[str] = []
    trace.append(f"list_items")
    app.list_items()
    trace.append(f"add_to_cart sku-001 -> {app.add_to_cart('sku-001')}")
    trace.append(f"add_to_cart sku-002 -> {app.add_to_cart('sku-002')}")
    trace.append("revised_choice: remove keyboard")
    trace.append(f"remove_from_cart sku-002 -> {app.remove_from_cart('sku-002')}")
    trace.append(f"add_to_cart sku-003 -> {app.add_to_cart('sku-003')}")
    trace.append(f"checkout -> {app.checkout()}")
    return trace
```

1. 为什么"由 agent 自己写的 trace 行数"不是可靠的步数？
2. 写一个 `RecordingApp(ShoppingApp)` 子类，在应用层记录每一次真实操作；用它重新计算三个任务的效率和总体效率。
3. `revised_order` 的 gold 是 5 步。最短的成功轨迹需要几步？gold 步数应当如何确定？

**Q11.**（对应讲义练习 4 与 `outputs` 第 5 条）`outputs/skill-web-desktop-harness.md` 要求"for each failure, tag whether it's a grounding miss (wrong element) or a planning miss (wrong action)"。

1. 设 gold 与 agent 轨迹都表示为 `(action, target)` 列表。写一个最简单的分类函数：动作序列一致但目标不同 → grounding；动作序列本身不同 → planning。
2. 用它分类：gold 为 `[("list_items", None), ("add_to_cart", "sku-001"), ("checkout", None)]`，agent 分别为
   - (a) `[("list_items", None), ("add_to_cart", "sku-002"), ("checkout", None)]`
   - (b) `[("list_items", None), ("checkout", None), ("add_to_cart", "sku-001")]`
3. 这种规则在真实 OSWorld 场景下有什么局限？OSWorld-G 的做法给了什么启发？

**Q12.**（计算题）

1. 分别计算 WebArena 与 OSWorld 发布时"最好 agent / 人类"的比值和百分点差距。
2. 某桌面任务的人类 gold 轨迹是 10 步，每步（截图 + 模型推理 + 执行）平均 3 秒。按 OSWorld-Human 报告的 1.4–2.7 倍，agent 需要多少步、多少秒？
3. 如果把 OSWorld 的 369 个任务都按"gold 10 步、2.7 倍、每步 3 秒"估算，跑一遍需要多少小时（单并发）？这对评测基础设施意味着什么？

---

## 四、面试高频题

**Q13.**（基础必考）WebArena 和 OSWorld 分别测什么？它们是怎么判定任务成功的？

**Q14.**（原理深挖）为什么 web/desktop agent 基准偏好"基于执行的状态检查"，而不是比对 agent 的动作轨迹？状态检查有什么盲点？

**Q15.**（原理深挖）GUI grounding 与 operational knowledge 分别是什么？如果你的 computer-use agent 在 OSWorld 上表现差，你如何判断是哪一种问题、怎么改进？

**Q16.**（场景设计）你们的 SaaS 产品要上线一个能操作网页后台的 agent。请设计内部评测：任务来源、gold 轨迹、评估器、状态重置、版本固定、安全措施与报告指标。

**Q17.**（追问型）有人说"我们的桌面 agent 在 OSWorld 上成功率很高"。你会追问哪些问题来判断这个数字的含金量？

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义："812 long-horizon tasks across four self-hosted web apps: a shopping site, a forum, a GitLab-like dev tool, a business CMS." A 是 OSWorld；B 是 SWE-bench（第 19 节）；D 是 GAIA（第 19 节）。

### Q2 — 答案：A

讲义："The self-hosted framing matters — the benchmark is not flaky because the target apps are pinned and reproducible." 线上网站的内容、布局、反爬策略随时在变，同一个 agent 今天和明天的分数会不同；自托管并固定版本，才能让基于执行的评估可复现、跨时间可比。B、C、D 都与讲义无关，D 甚至违背了评测隔离的原则。

### Q3 — 答案：D

讲义："At release: best model 12.24% vs human 72.36%." B 是 WebArena 的数字（14.41% vs 78.24%），是最常见的混淆项；A、C 是编造的。

### Q4 — 答案：B

讲义："GUI grounding. Pixel → element mapping ... Operational knowledge. Which menu has the setting, which keyboard shortcut, which preference pane." A、C、D 是 LLM 系统的其他常见问题，不是 OSWorld 的结论。

### Q5 — 答案：A

讲义："OSWorld-G — 564-sample grounding suite + Jedi training set. Decomposes grounding from planning so you can measure them separately." B 是 OSWorld-Human 的贡献；C、D 无依据。

### Q6 — 答案：C

trace 共 7 行：`list_items`、`add_to_cart sku-001`、`add_to_cart sku-002`、`revised_choice: remove keyboard`、`remove_from_cart sku-002`、`add_to_cart sku-003`、`checkout`。其中第 4 行只是一句"思考"，没有调用任何应用方法。`7 / 5 = 1.40`。如果只数真实操作是 6 步，效率为 1.20x（见 Q10）。A 错在应用方法实际只调用了 6 次；B、D 无依据（购物车最终是 2 件商品，结账后清空）。

### Q7 — 答案：D

代码累加 `total_steps += steps`、`total_gold += task.gold_steps`，最后打印 `total_steps / total_gold`，即"总和之比"：`14 / 12 ≈ 1.17`。A 是"比值的平均"，结果是 `(1 + 1 + 1.4) / 3 ≈ 1.13`——两种聚合口径不同：总和之比会让 gold 步数多的长任务权重更大，平均比值则每个任务权重相同。报告时应注明口径。

### Q8 — 答案：B

讲义："OSWorld is screenshot-driven; evaluating an agent that uses DOM or accessibility APIs on OSWorld misses the grounding challenge." 用结构化接口拿到元素坐标，就跳过了"从 1920×1080 像素中找到按钮"这一最难的环节，分数会偏高且不可比。

注意 `outputs` 的硬规则 "Screenshots-only harness without DOM parity" 看似相反：那是在**为自己的产品搭 harness** 时，建议同时提供截图和 DOM，以免限制了 agent 可用的观测面；而讲义说的是**在 OSWorld 上报告分数**时要遵守它的截图设定。两者目的不同，并不矛盾。

### Q9 — 参考答案

1. 已实际运行验证：
   - (a) **成功**——谓词只检查是否存在一个订单里有 1 副耳机，多买的鼠标不影响。这是**错误判定**：多余的商品是副作用（多扣了用户的钱）。
   - (b) **成功**——`any(...)` 只要有一单满足即可，误下的键盘订单被忽略。**错误判定**：真实电商里这是一笔需要退款的错误订单。
   - (c) **失败**——`== 1` 要求数量恰好为 1。这个判定是合理的（任务说"买耳机"，默认 1 副）。
2. 已验证：`add_to_cart` 不检查数量，购物车变成 `{'sku-001': -3}`，`checkout()` 生成一个 `total = -597` 的订单。玩具应用缺少输入校验（数量必须为正整数）。真实应用的约束往往更多，基准任务恰恰会暴露 agent 在这些边界上的行为。
3. 参考实现（已验证：(a) 判为失败，原 `_agent_task_1` 仍判为成功）：

```python
def strict_success(expected_items: dict[str, int]):
    def check(app: ShoppingApp) -> bool:
        return (len(app.orders) == 1
                and app.orders[0]["items"] == expected_items
                and not app.cart)
    return check

# 用法：success=strict_success({"sku-001": 1})
```

   新问题：谓词越严格，越可能把"合理但不同"的完成方式判为失败（例如用户本来就有一张历史订单，或者任务允许"顺便"保留购物车）。基于执行的评估需要明确定义"允许的副作用"，WebArena 也是按任务逐个编写检查逻辑的。

### Q10 — 参考答案

1. trace 是 agent 自己写的叙述：可以包含不对应任何操作的"思考"行（`revised_choice: ...`），也可能漏写真实操作（`_agent_task_2` 中先 `append("list_items")` 再单独调用 `app.list_items()`，二者只是碰巧一致）。步数应该由**环境**记录，而不是由被测对象自报——这和"测试由 harness 运行、不由 agent 报告是否通过"是同一个原则。
2. 参考实现（已验证）：

```python
class RecordingApp(ShoppingApp):
    def __init__(self) -> None:
        super().__init__()
        self.actions: list[tuple] = []

    def list_items(self):
        self.actions.append(("list_items",))
        return super().list_items()

    def add_to_cart(self, sku, qty=1):
        self.actions.append(("add_to_cart", sku, qty))
        return super().add_to_cart(sku, qty)

    def remove_from_cart(self, sku):
        self.actions.append(("remove_from_cart", sku))
        return super().remove_from_cart(sku)

    def checkout(self):
        self.actions.append(("checkout",))
        return super().checkout()

# 评估循环中：app = RecordingApp(); task.agent(app); steps = len(app.actions)
```

   结果：`buy_headphones` 3 步 1.00x；`buy_bundle` 4 步 1.00x；`revised_order` **6 步 1.20x**（原输出 1.40x）；总体 `13 / 12 ≈ 1.08x`（原输出 1.17x）。
3. 最短成功轨迹：`add_to_cart sku-001 → add_to_cart sku-003 → checkout` 共 3 步（已验证能满足谓词）；若像其他任务一样把 `list_items` 计入，则为 4 步。gold 写成 5 步，大概是把"加入键盘再换掉"的过程也算了进去，但这正是 agent 走的弯路。gold 应当是**人类专家完成任务的最少必要步骤**，由人工录制并复核（OSWorld-Human 的做法）；gold 设得偏大，会让 agent 的效率看起来比实际更好。按 3 步 gold 计，`revised_order` 的真实效率是 `6 / 3 = 2.0x`。

### Q11 — 参考答案

1. 参考实现：

```python
def classify_failure(gold, agent):
    gold_ops = [a for a, _ in gold]
    agent_ops = [a for a, _ in agent]
    if agent_ops == gold_ops:
        return "match" if agent == gold else "grounding"   # 动作对、目标错
    return "planning"                                       # 动作序列本身不对
```

2. 已运行验证：(a) → `grounding`（动作序列一致，但把 `sku-001` 点成了 `sku-002`，相当于在页面上点错了元素）；(b) → `planning`（先结账再加购物车，动作顺序错了）；与 gold 完全相同 → `match`。
3. 局限：
   - 真实任务有多条合法路径，agent 的动作序列不同不一定是 planning 错误；
   - 截图场景下的 grounding 失败表现为"点击坐标落在错误元素上"，需要知道每次点击实际命中了哪个元素（需要 DOM/无障碍树或人工标注来对照），仅靠动作名无法判断；
   - 一次失败往往同时包含两类问题，前面的 grounding 错误会导致后面的 planning 混乱。
   - OSWorld-G 的启发：**单独构造 grounding 测试**（给定截图和"点击某元素"的指令，只看定位是否正确），把 grounding 能力与规划能力分开测量；在自己的评测中也可以为关键步骤准备"只测定位"的样本，并在完整任务中记录每步的目标元素。

### Q12 — 参考答案

（已用 Python 计算）

1. 发布时：
   - WebArena：`14.41 / 78.24 ≈ 18.4%`，差距 `78.24 − 14.41 = 63.83` 个百分点；
   - OSWorld：`12.24 / 72.36 ≈ 16.9%`，差距 `72.36 − 12.24 = 60.12` 个百分点。
   两者都只有人类水平的六分之一左右。讲义："The gap is narrowing; the failure modes haven't changed."
2. agent 需要 `10 × 1.4 = 14` 到 `10 × 2.7 = 27` 步，即 `42` 到 `81` 秒（人类 gold 路径对应 30 秒）。多出来的步数直接转化为延迟、token 成本和出错机会（每多一步就多一次可能点错）。
3. `369 × 10 × 2.7 × 3 s ≈ 29,889 s ≈ 8.3 小时`（单并发）。这还没算虚拟机启动、状态重置与失败重试。因此讲义建议在 VM 集群上运行 OSWorld（"OSWorld in a VM fleet"），并行化与快速重置是评测基础设施的核心需求；同时这也说明只看成功率会掩盖巨大的运行成本差异。

### Q13 — 参考回答要点

- **WebArena**：812 个长程 web 任务，四个自托管应用（购物、论坛、类 GitLab、CMS）+ 地图/计算器/草稿板；评估是基于执行的——通过 gym API 检查订单是否创建、issue 是否关闭、页面是否更新。
- **OSWorld**：369 个真实桌面任务，跨 Ubuntu/Windows/macOS，自由键鼠操作，观测是 1920×1080 截图；同样检查任务完成后的系统/应用状态。
- **发布时差距**：WebArena 14.41% vs 78.24%；OSWorld 12.24% vs 72.36%。
- **扩展**：VisualWebArena（视觉 grounding）、TheAgentCompany（终端 + 编码）、OSWorld-G（grounding 拆分）、OSWorld-Human（gold 轨迹与效率）。
- 加分点：讲义指出 Claude computer use、OpenAI CUA、Gemini 2.5 Computer Use 都在这类工作负载上训练（"The benchmarks are the target; the production models are the shipped answer."），所以理解这些基准有助于理解第 21 节的产品。

### Q14 — 参考回答要点

- **为什么用状态检查**：
  - 同一个任务有很多合法路径（先搜索再点、直接从分类进入……），比对动作轨迹会惩罚正确但不同的做法；
  - 用户关心的是结果——订单是否下了、设置是否生效；
  - 状态检查可自动化、可复现，不依赖 LLM 评委。
- **盲点**：
  - 副作用：只检查目标状态，不检查有没有做多余或破坏性的事（见 Q9：多买商品、多下订单都能通过）；
  - 过程质量：绕了大弯的成功与一步到位的成功同分——所以需要 trajectory efficiency；
  - 谓词编写质量：太松会误判成功，太严会误判失败；
  - 状态污染：任务之间不重置状态会让后面的任务基于脏数据（`outputs` 硬拒绝 "No state reset between tasks"）。
- 加分点：理想的评估是"目标状态检查 + 不变量检查（不该变的没变）+ 轨迹效率"，类似第 19 节 FAIL_TO_PASS + PASS_TO_PASS 的组合。

### Q15 — 参考回答要点

- **GUI grounding**：从截图像素中定位目标元素（按钮、输入框、菜单项）并给出正确坐标。高分辨率、小图标、相似元素、动态布局都会让定位出错。
- **Operational knowledge**：知道"做这件事该去哪里"——设置在哪个菜单、哪个快捷键、哪个偏好面板。讲义称之为"人类花多年积累的长尾知识"。
- **诊断**：
  - 记录每一步的截图、意图（agent 想点什么）和实际命中元素；
  - 意图正确但坐标落错 → grounding；意图本身错（去错菜单、不知道入口）→ operational knowledge / planning；
  - 用 OSWorld-G 风格的"只测定位"样本单独评估 grounding。
- **改进**：
  - grounding：更高质量的视觉模型或专门的 grounding 模型、截图裁剪放大、提供 DOM/无障碍树辅助（在不受截图限制的产品场景中）；
  - operational knowledge：检索应用文档或操作手册、为常见应用提供技能库（第 10 节）、记录成功轨迹以复用。
- 加分点：同时关注 trajectory efficiency——即使成功，1.4–2.7 倍的多余步骤也代表 grounding 或知识上的犹豫。

### Q16 — 参考回答要点

- **任务来源**：从产品日志中选出用户最常做的 20 个流程（讲义："capture gold trajectories for your top 20 tasks; run agents against them weekly"），覆盖简单、中等、长程三档。
- **gold 轨迹**：由熟练员工录制最短路径并复核；每任务记录 gold 步数（`outputs`："If the tasks have no gold trajectories, refuse."）。
- **评估器**：基于执行的状态检查 + 不变量检查（不该改的数据没被改）；为每个任务写明允许的副作用。
- **状态重置**：每个任务从同一个快照开始（数据库快照或容器镜像），任务间绝不共享脏状态。
- **版本固定**：被测后台的版本与测试数据钉死；升级后重新整理任务（讲义："Stale self-hosted apps"）。
- **安全**：删除、发布、付款等破坏性操作只能在沙箱副本中执行（`outputs` 拒绝规则）。
- **观测面**：同时提供截图与 DOM（`outputs`："DOM parity"），并分别报告。
- **报告**：每任务成功与否、步数与 gold 之比、耗时、token 成本；失败按 grounding / planning 分类；周度趋势与回归告警。

### Q17 — 参考回答要点

- 是在哪个 OSWorld 版本与设置下测的？观测是纯截图，还是用了无障碍树/DOM（讲义：这会绕过 grounding 挑战）？
- 跑了哪些操作系统、哪些任务子集？有没有排除某些类别？
- 步数与 gold 相比如何？有没有 trajectory efficiency、耗时、成本数据？
- 失败案例中 grounding 与 operational knowledge 各占多少？
- 每个任务跑了几次，方差多大？环境是否每次重置？
- 是否有针对这些任务的专门调优或训练，是否在其他应用、其他分辨率上验证过泛化？
- 与人类基线（72.36%）和发布时最好结果（12.24%）相比处在什么位置？
- 加分点：能说出讲义的三种误用（截图评估却用结构化接口、忽略轨迹长度、应用版本漂移）并解释每一种会如何抬高或扭曲分数。

---

## 六、关联知识点

### 前置知识
- [阶段 14 · 19 基准评测：SWE-bench、GAIA、AgentBench](../../19-benchmarks-swebench-gaia/docs/zh.md)：讲义的先修；FAIL_TO_PASS / PASS_TO_PASS 与本节"状态检查 + 不变量"的思路一致。
- [阶段 14 · 06 工具使用与 Function Calling](../../06-tool-use-and-function-calling/docs/zh.md)：玩具应用的四个方法就是 agent 可调用的工具。
- [阶段 04 · 25 Vision-Language Models — ViT-MLP-LLM 模式](../../../04-computer-vision/25-vision-language-models/docs/zh.md)：截图驱动的 agent 依赖视觉语言模型做 grounding。
- [阶段 12 · 25 多模态 Agents 与计算机操作（综合项目）](../../../12-multimodal-ai/25-multimodal-agents-computer-use/docs/zh.md)：多模态 agent 操作计算机的整体架构。

### 本节被哪些后续内容用到
- [阶段 14 · 21 计算机操作：Claude、OpenAI CUA、Gemini](../../21-computer-use-agents/docs/zh.md)：在这些基准上训练与评测的产品化模型。
- [阶段 14 · 26 失效模式：Agents 为什么会失败](../../26-failure-modes-agentic/docs/zh.md)：grounding、规划等失败的系统化分类。
- [阶段 14 · 30 评估驱动的 Agent 开发](../../30-eval-driven-agent-development/docs/zh.md)：把 gold 轨迹与周度评测纳入开发流程。
- [阶段 15 · 11 浏览器 Agents 与长程网页任务](../../../15-autonomous-systems/11-browser-agents/docs/zh.md)：长程网页任务的工程实践。
- [阶段 16 · 24 Evaluation 与协调基准评测](../../../16-multi-agent-and-swarms/24-evaluation-coordination-benchmarks/docs/zh.md)：多 agent 场景下的评测。

### 延伸关键词
`WebArena` · `VisualWebArena` · `TheAgentCompany` · `OSWorld` · `OSWorld-G` · `OSWorld-Human` · `Jedi` · `execution-based evaluation` · `GUI grounding` · `operational knowledge` · `trajectory efficiency` · `gold trajectory` · `accessibility tree / DOM` · `state reset` · `computer use`
