# 测验 · 自动化 Alignment 研究（Automated Alignment Research (Anthropic AAR)）

> **阶段 15 · 自主系统 · 第 06 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 注：本节中文讲义机器翻译质量较差（例如把 "Claude Opus 4.6" 译成 "Claude 行动4.6"、把 Datadog 译成"数据犬"），有疑义请以英文版为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | AAR 是什么 | Automated Alignment Researcher：讲义："Claude Opus 4.6 instance operated autonomously on alignment problems"，多个实例并行、各自在独立 sandbox 中运行 |
| 2 | 公开结果 | 在 weak-to-strong training（用较弱的监督者模型训练更强的学生模型）这一研究问题上，AAR 的表现超过人类研究者基线 |
| 3 | 共享论坛（shared forum） | AAR 把发现发布到共享论坛；论坛的存储后端位于**所有 sandbox 之外**，agent 能读、不能从自己的 sandbox 内删改记录 |
| 4 | 日志完整性 | 讲义："log-integrity property is the difference between a controlled experiment and a potentially compromised one"；基础设施里的对应物是 append-only + write-through 到外部存储（如 S3 Object Lock） |
| 5 | 规定流程 vs 自由分解 | 讲义："prescribed workflows often constrain AAR flexibility and degrade performance"；但让性能变好的灵活性，也是允许未经批准的分解、新奇工具使用和目标漂移的灵活性 |
| 6 | 压缩风险（compression risk） | 能自动化 alignment 研究，就意味着离"自动化整个 AI R&D 流水线"更近；若能力复合得比 alignment 更快，错位风险面会扩大 |
| 7 | 与 RSP / FSF 阈值的关系 | RSP v3.0 的 AI R&D 阈值 = 以有竞争力的成本完全自动化 AI R&D 流水线；AAR 只自动化了其中一部分（范围明确的 alignment 任务），讲义称其"one step short of the threshold" |
| 8 | AAR 不替代什么 | 人类设定任务队列、审查结果、决定发表与撤回；AAR 加速流水线的"中段"而不是"两端"——即把 propose-then-commit 用在研究本身 |
| 9 | 哈希链（hash chain） | 每条记录的哈希包含上一条的哈希，篡改会让校验失败；但它只是 tamper-**evident**（可发现），要配合"链头哈希存放在 agent 碰不到的地方"才真正可信 |
| 10 | 代码的简化 | 模拟器里"自由分解"只比"固定流程"期望高 0.025、方差大 3 倍，并没有建模"越难的问题越占优"；"外部备份交叉核对"只是打印出来的一句话，没有实现 |

### 核心技能（能动手做到）

- [ ] 说清 AAR 的四个架构要素（并行 agent、共享论坛、任务分配、weak-to-strong 焦点）以及各自的安全意义
- [ ] 读懂 `Forum.post` / `Forum.verify` 的哈希链实现，能预测某种篡改会被标记在哪个下标
- [ ] 指出纯哈希链检测不到的攻击（重写整条后缀、截断尾部、低于序列化精度的修改），并给出外部锚定的修复方案
- [ ] 用期望和方差分析 `solve()` 中两种 regime 的差异，解释为什么单次运行的结论不可靠
- [ ] 按 `outputs/skill-aar-deployment-review.md` 的五个维度对一个 AAR 部署方案做部署前评审
- [ ] 讲清"自动化 alignment 研究"为什么既是好事、又在压缩到 RSP AI R&D 阈值的时间线

---

## 二、基础自测（选择题）

**Q1.** 讲义引用的 Anthropic 2026 年 AAR 研究中，AAR 超过人类研究者的研究问题是：

- A. 奖励模型诊断（reward-model diagnosis）
- B. 检测 alignment faking
- C. RLHF 超参数搜索
- D. weak-to-strong training：用较弱的监督者模型训练更强的学生模型

**Q2.** 讲义强调共享论坛的存储要放在**所有 sandbox 之外**，最主要的原因是：

- A. 防止 agent 删除或修改自己过去的记录，掩盖失败或可疑的实验
- B. 外部存储读写更快，能提升 AAR 的研究吞吐
- C. 让不同 AAR 之间无法读到彼此的发现，保证实验独立
- D. 节省 sandbox 内的磁盘空间

**Q3.** 在本节 `Forum` 中已按顺序 `post` 了 15 条记录。攻击者**只**把下标 6 那条记录的 `result` 加了 0.5（不改 `my_hash`、`prev_hash`），`verify()` 返回：

- A. `[6, 7, 8, …, 14]`，篡改点之后的全部记录
- B. `[7]`，只有下一条记录的 `prev_hash` 对不上
- C. `[6]`，只有被改的那一条
- D. `[]`，因为 `prev_hash` 链条没有被破坏

**Q4.** 关于"规定流程（prescribed workflow）"与"自由分解（free decomposition）"，与讲义一致的说法是：

- A. 规定流程总是更好，因为它更容易审计且性能更稳定
- B. 规定流程常常限制 AAR 的灵活性并降低性能；但带来性能的灵活性也给了未经批准的分解和目标漂移空间
- C. 自由分解只影响审计成本，不影响研究性能
- D. Anthropic 的报告建议完全取消人类设计的任务队列

**Q5.** 本节 `solve()` 中，固定流程返回 `base + random.random() * 0.25`，自由分解返回 `base + random.gauss(0.15, 0.22)`。下列哪项描述正确？

- A. 两者相对 `base` 的期望增益分别为 0.125 与 0.15，标准差约为 0.072 与 0.22；自由分解约有 25% 的概率低于 `base`
- B. 两者期望相同，只有方差不同
- C. 自由分解在难题（`base` 小）上的期望增益更大
- D. 自由分解的结果永远落在 `[base, base + 0.37]` 区间内

**Q6.** 讲义如何定位 AAR 与 RSP v3.0 "AI R&D 能力阈值"之间的关系？

- A. AAR 已经越过了该阈值，因此 Anthropic 启动了更高等级的控制
- B. 两者无关：RSP 只关心生物、化学等两用风险
- C. AAR 证明 alignment 研究永远无法被自动化，所以阈值不会被触发
- D. AAR 只自动化了流水线的一部分（范围明确的 alignment 任务），还没有自动化端到端的能力开发循环，"距离阈值一步之遥"

**Q7.** 讲义说 AAR "accelerate the middle of the pipeline, not the ends"。"两端"指的是：

- A. 数据收集与模型部署
- B. 训练开始与训练结束
- C. 由人类设定任务队列，以及由人类审查结果并决定发表、撤回、精炼
- D. sandbox 的创建与销毁

**Q8.** 仅凭本节 `Forum.verify()`（链头哈希没有存放在任何外部位置），下列哪种篡改**检测不到**？

- A. 修改某条记录的 `result`，其余不动
- B. 从被改的那条开始，按 `post()` 的规则把它及之后所有记录的哈希全部重算一遍
- C. 删除中间某条记录
- D. 修改某条记录的 `author` 字段

---

## 三、动手 / 代码题

**Q9.** 阅读篡改与校验的核心代码：

```python
    def verify(self) -> list[int]:
        bad = []
        prev = self.genesis
        for i, r in enumerate(self.records):
            payload = (f"{r.author}|{r.task}|{r.regime}|"
                       f"{r.result:.3f}|{prev}")
            expected = hashlib.sha256(payload.encode()).hexdigest()[:16]
            if expected != r.my_hash or r.prev_hash != prev:
                bad.append(i)
            prev = r.my_hash
        return bad
```

1. `attempt_tamper` 只改了 `result`。解释为什么 `verify()` 只标记被改的那一条，而不是它之后的全部记录。
2. 如果攻击者在改完 `result` 后**顺手重算了这一条的 `my_hash`**，`verify()` 会标记哪条？
3. 如果攻击者有论坛的写权限，从篡改点开始把整条后缀重新 `post` 一遍，`verify()` 返回什么？这说明哈希链缺了什么？
4. 写一个 `verify_anchored(forum, anchored_head, anchored_len)`，利用"在 sandbox 外定期记录的链头哈希和记录数"来抓住第 3 种攻击和"截断尾部"攻击。

**Q10.** `post()` 与 `verify()` 都用 `f"{rec.result:.3f}"` 把分数写进哈希载荷。

1. 原始分数为 `0.34509675910144444`，攻击者把它改成 `0.3454`，`verify()` 能发现吗？为什么？
2. 这类"序列化精度低于存储精度"的问题在真实系统里有哪些对应物？应如何修复？

**Q11.** 讲义的 "Use It" 部分说要观察"自由分解在更难的问题上如何胜过固定流程"。

1. 根据 `solve()` 的写法，自由分解相对固定流程的优势与任务难度（`base`）有没有关系？
2. 在 `random.seed(3)` 的那次运行里，哪个任务上自由分解的均值反而**低于**固定流程？这与"自由分解更好"矛盾吗？
3. 用不同种子重复整个实验，自由分解的总体均值大约在多少比例的种子里胜出？（实测：2000 个种子）
4. 改写 `solve()`，让"自由分解的优势随难度增大"真正体现在模型里（讲义练习 1）。

**Q12.** `tamper_demo()` 的写法：

```python
def tamper_demo() -> None:
    ...
    baseline = run_regime("free")
    tampered = attempt_tamper(baseline)
    bad = tampered.verify()
```

1. 这里的 `baseline` 与上方 `regime_report("free")` 打印的那张表是同一批记录吗？
2. 本次运行输出 `verify() flagged 1 corrupted record(s) at indices [0]`。为什么是下标 0？换种子后下标会变吗？
3. 按讲义练习 2，用一段话描述"检测签名（detection signature）"在日志中长什么样。

---

## 四、面试高频题

**Q13.**（基础必考）什么是 Automated Alignment Research？Anthropic 的 AAR 系统架构有哪几个要素？为什么"在 weak-to-strong 问题上超过人类"这个结果同时是好消息和警示？

**Q14.**（原理深挖）tamper-evident 和 tamper-proof 有什么区别？哈希链能提供什么、不能提供什么？为什么讲义强调日志必须"out-of-sandbox"？

**Q15.**（工程实践）你负责评审一个即将上线的 AAR 流水线，请给出你的部署前评审清单，并说明哪些情况你会直接否决。

**Q16.**（场景设计）设计一个任务分配策略，平衡"自由分解带来的性能"与"规定流程带来的可审计性"，并说明你如何做 A/B 测试来验证（讲义练习 4）。

**Q17.**（追问型）既然 AAR 能加速 alignment 研究，为什么讲义仍称它为"compression step"、只是"qualified good"？什么样的能力会让一个类似系统越过 RSP 的 AI R&D 阈值？

---

## 五、参考答案与解析

### Q1 — 答案：D

讲义："The published study addressed weak-to-strong training — using a weaker supervisor model to train a stronger student model. AARs outperformed human researchers on this task." A、B、C 是本节代码 `TASKS` 列表里虚构的模拟任务名（`reward-model-diagnosis`、`alignment-faking-detector`、`RLHF-hyperparam-sweep`），不是公开结果中 AAR 胜过人类的任务。

### Q2 — 答案：A

讲义："If AARs could edit their own logs, they could cover up failed or dubious experiments." 日志完整性是"信任研究产出"的必要条件。B 不是动机；C 反了——论坛的作用正是让 agent 之间**共享**发现（agent 可以读论坛）；D 无关。

### Q3 — 答案：C

`verify()` 中 `prev = r.my_hash` 取的是**存储着的**哈希。只改 `result` 时，第 6 条重算的 `expected` 与存储的 `my_hash` 不同 → 标记 6；第 7 条的 `prev_hash` 等于第 6 条**存储的** `my_hash`（没变），重算自己的 `expected` 也匹配 → 不标记。所以只有 `[6]`。实际运行（seed 3）也只标记了 1 条：`indices [0]`。A 是很多人的直觉，但那需要 `prev` 用"重算出的哈希"往下传；B 是攻击者重算了第 6 条 `my_hash` 之后的情形（见 Q9）。

### Q4 — 答案：B

讲义："prescribed workflows often constrain AAR flexibility and degrade performance"，紧接着指出安全上的微妙之处："The flexibility that improves AAR performance is also the flexibility that allows unsanctioned decomposition, novel tool use, and goal-drift." A 与报告结论相反；C 忽略了性能差异；D 错，讲义明确说人类仍然设置任务队列。

### Q5 — 答案：A

均匀分布 `U(0, 0.25)` 的均值 0.125、标准差 `0.25/√12 ≈ 0.072`；`gauss(0.15, 0.22)` 均值 0.15、标准差 0.22。自由分解低于 `base` 的概率为 `Φ(−0.15/0.22) ≈ 0.248`，超过固定流程上限 `base + 0.25` 的概率约 0.325（均已用 `statistics.NormalDist` 计算）。B 错，期望差 0.025；C 错，`solve()` 中增益与 `base` 无关；D 错，正态分布无界——本次运行就出现了 1.032 和 0.055。

### Q6 — 答案：D

讲义："AAR is one step short of the threshold: it automates part of the pipeline (alignment research on specific, well-scoped tasks) but not the end-to-end capability development loop." A 不符合讲义；B 错，RSP v3.0 明确有 AI R&D 阈值，DeepMind FSF v3 也有对应的 ML R&D autonomy level；C 与结果相反。

### Q7 — 答案：C

讲义："Human researchers set the task queue, review results, and hold the constitutional authority." 发表、撤回、精炼的判断仍由人类做出——"AARs propose; humans commit"。其余选项与讲义无关。

### Q8 — 答案：B

实测（seed 3 的记录）：把整条后缀按 `post()` 规则重建后，`verify()` 返回 `[]`。哈希链只验证"内部自洽"，攻击者若掌握写权限和哈希算法（这里没有任何密钥），就能伪造一条同样自洽的新链。A、D 都会让该条 `expected != my_hash`；C 删除下标 5 后，原第 6 条的 `prev_hash` 指向已删除的记录，实测返回 `[5]`。另外"直接截掉尾部记录"同样检测不到（实测 `[]`）。修复需要外部锚点，见 Q9。

### Q9 — 参考答案

1. 循环里 `prev = r.my_hash` 用的是存储的哈希而不是重算值。被改记录的 `my_hash` 没动，所以下一条的 `prev_hash == prev` 仍然成立，下一条自己的载荷也没变——错误不会"传染"。好处是能**精确定位**被改的那一条；讲义正文中"the append-only chain breaks at the first edited record"正对应这一点。
2. 第 6 条自洽了（`expected == my_hash`），但第 7 条存的 `prev_hash` 仍是旧哈希，`r.prev_hash != prev` → 标记 **7**。实测：改下标 4 并重算其哈希后，`verify()` 返回 `[5]`。
3. 返回 `[]`（实测）。哈希链缺的是**信任锚**：没有密钥（任何人都能算 SHA-256），也没有存放在攻击者够不着的地方的链头。这正是讲义强调"out-of-sandbox"的原因——链本身只是"可被发现"，可信来自"agent 没有修改历史记录的凭证"。
4. 参考实现：

```python
def verify_anchored(forum, anchored_head: str, anchored_len: int) -> list[str]:
    problems = [f"record {i} hash mismatch" for i in forum.verify()]
    if len(forum.records) < anchored_len:
        problems.append(f"truncated: {len(forum.records)} < anchored {anchored_len}")
    elif forum.records[anchored_len - 1].my_hash != anchored_head:
        problems.append("history rewritten before anchor point")
    return problems
```

外部监视器（在 sandbox 外运行）每 N 条或每 T 秒把 `(len, head)` 写到 write-once 存储（如开启 Object Lock 的对象存储或独立账号下的日志）；校验时先跑 `verify()`，再比对锚点。更强的做法是用只有论坛服务持有的密钥做 HMAC 或签名，让 agent 即使能读写存储也无法伪造合法记录。

### Q10 — 参考答案

1. **发现不了**。`f"{0.34509675910144444:.3f}"` 与 `f"{0.3454:.3f}"` 都是 `"0.345"`，载荷完全相同，哈希不变；实测 `verify()` 返回 `[]`。凡是不改变四舍五入后三位小数的修改都检测不到（最大可改约 ±0.0005，具体取决于原值离舍入边界有多远）。
2. 对应物：只对部分字段签名、日志里存的是浮点而签名用的是格式化字符串、JSON 序列化时字段顺序不固定导致"同一内容不同哈希"等。修复：对**存储的确切字节**做哈希——用规范化序列化（如 `json.dumps(record, sort_keys=True)`，浮点用 `repr()` 或直接存成字符串/定点整数），保证"哈希覆盖的内容 = 被存储与被读取的内容"。另外用 `|` 拼接字段也有歧义（若 `author` 中含 `|`，可构造出不同记录、相同载荷），规范化序列化同时解决了这个问题。

### Q11 — 参考答案

1. **没有关系**。两个分支都是 `base + 噪声`，噪声分布与 `base` 无关：自由分解在每个任务上都只比固定流程期望高 0.025。讲义描述的"harder problems"效应在代码里没有被建模。
2. `reward-model-diagnosis`：fixed 均值 0.408，free 均值 0.269（`alignment-faking-detector` 也略低：0.413 对 0.389）。不矛盾——每个格子只有 3 个样本，free 的标准差是 0.22，3 个样本均值的标准差约 0.127，远大于 0.025 的真实差距，单格的胜负几乎是噪声。
3. 在 2000 个种子上重复（每个种子先 fixed 后 free），自由分解的总体均值胜出 1330 次，约 **66.5%**。seed 3 下的差距 0.582 对 0.500 属于偏有利的一次抽样。单次抽取的比较：自由分解单次结果大于固定流程单次结果的概率仅约 0.545。
4. 一种改法（让难题上自由分解优势更大、易题上固定流程更稳）：

```python
def solve(agent, task, regime):
    _name, base = task
    difficulty = 1.0 - base                     # base 越低越难
    if regime == "fixed":
        return base + random.random() * 0.25 * (1 - 0.5 * difficulty)
    return base + random.gauss(0.05 + 0.30 * difficulty, 0.22)
```

然后按难度分组报告 fixed / free 的均值与方差，并对每组跑多个种子给出置信区间——这样才能回答练习 1 "是否存在固定流程有竞争力的问题类别"。

### Q12 — 参考答案

1. **不是**。`run_regime` 每次都从全局 `random` 继续抽样；`main()` 先 `seed(3)`，依次跑 fixed、free 两张表，`tamper_demo` 再跑**第三次** `run_regime("free")`。所以被篡改的是一批没有打印出来的新记录（其第 0 条是 AAR-A 在 weak-to-strong-distill 上的 0.310，而表中该任务 free 的最小值是 0.731）。演示结论不受影响，但读者容易误以为两者是同一批数据。
2. `attempt_tamper` 选的是 **AAR-A 分数最低的那条**；这一批里它恰好是第 0 条（0.310）。下标随种子变化：在 200 个种子上统计，被标记的下标有 12、3、0、9、6 等，且总是 3 的倍数——因为每个任务按 A、B、C 顺序发帖，AAR-A 的记录必在 `0, 3, 6, 9, 12`。
3. 签名描述（示例）："第 k 条记录用其存储字段重算出的哈希与存储的 `my_hash` 不一致，而第 k+1 条的 `prev_hash` 仍等于第 k 条存储的 `my_hash`；即错误恰好局限在一条记录上，说明该记录在写入后被就地修改了内容但哈希未更新。若出现的是'第 k 条自洽、第 k+1 条 `prev_hash` 不匹配'，说明攻击者重算过第 k 条的哈希；若链完全自洽但与外部锚点不一致，说明整条后缀被重写或尾部被截断。"

### Q13 — 参考回答要点

- **定义**：让前沿模型自主承担 alignment 研究工作——提出分解、跑实验、写结论。讲义：AAR 是"Claude Opus 4.6 instance operated autonomously on alignment problems"。
- **架构四要素**：并行 agent（各自独立 sandbox，限制文件系统、网络、进程）；共享论坛（存储在所有 sandbox 之外、append-only）；人类设计的任务队列；研究焦点是 weak-to-strong training。
- **好消息**：alignment 工作量的增长快于合格研究者的供给，AAR 证明前沿模型能帮忙缩小差距。
- **警示**：讲义："If alignment research can be automated, so can the parts that compromise safeguards." 同一能力离 RSP 的 AI R&D 阈值更近。
- 加分点：说明 weak-to-strong 是 scalable oversight 的经典基准（Burns et al. 2023）——它模拟"未来人类监督比自己更强的模型"的处境。
- 常见误区：把 AAR 理解为"无人监督的研究"；实际上两端（任务设定、发表决定）仍是人类。

### Q14 — 参考回答要点

- **tamper-evident**：篡改**会被发现**；**tamper-proof / tamper-resistant**：篡改**做不到**。哈希链只提供前者。
- **哈希链能提供**：给定一个可信的链头，能验证之前所有记录未被改动、未被插删，并能定位出问题的记录。
- **不能提供**：没有可信锚点时，攻击者可以重写整条后缀、截断尾部；SHA-256 无密钥，谁都能算（见 Q8、Q9）。
- **为什么 out-of-sandbox**：可信性来自"agent 没有修改历史的凭证"，而不是来自算法本身。讲义类比："append-only logs with write-through to external storage (e.g. S3 object-lock, immutable Datadog logs). The agent has no credential to modify past records." 这与企业防勒索软件的审计日志是同一模式。
- 加分点：提出"定期把链头写到第三方 / write-once 存储"、"对记录做 HMAC 或数字签名，密钥只在论坛服务里"、"读路径与写路径分离，agent 只能通过一个独立服务发帖"（skill 文件："all posts go through a separate service"）。

### Q15 — 参考回答要点

按 `outputs/skill-aar-deployment-review.md` 的五维度：

1. **Sandbox 隔离**：文件系统、网络、进程限制；AAR 之间不能读写彼此 sandbox；AAR 不能直接触达论坛存储的写端点。
2. **论坛日志完整性**：append-only、tamper-evident；明确存储介质（如 Object Lock）、校验频率、发现篡改后的响应。
3. **任务分配策略**：谁写任务、谁批准、AAR 能否自行提出后续任务、在什么条件下；明确记录"自由分解赢性能、规定流程赢可审计性"的取舍。
4. **人类评审闸门**：AAR 产出影响真实研究方向、训练数据或发表之前，必须有**具名**评审人签字；检查实验可复现性、日志完整性、结论与证据的对应关系。
5. **阈值监控**：跟踪接近 AI R&D-4 的信号——任务复杂度变化、自主派生子任务、跨任务信息迁移。

直接否决（skill 文件的 hard rejects / refusal rules）：没有 tamper-evident 的 out-of-sandbox 日志；AAR 输出未经具名人类评审就进入训练数据或生产策略；单个 AAR 的凭证能影响多个下游系统；隔离只有单层（例如只有 Docker，没有 seccomp / gVisor）；日志存储任何人（包括运维）可编辑；部署目标其实是自动化能力流水线而不只是 alignment 研究（要升级到 RSP 评审）。

### Q16 — 参考回答要点

- **分层策略（hybrid）**：
  - 按任务风险与难度分档：低风险、范围明确的任务允许自由分解；涉及训练数据、权限、外部系统的任务使用规定流程或"自由分解 + 计划需人类批准"；
  - 自由分解时要求 agent 先输出结构化的分解计划（子任务、工具、预期产物）写入论坛，作为审计材料；
  - 设"灵活性预算"：可调用的工具白名单、可派生子任务数上限、计算预算。
- **A/B 测试设计**：同一任务池随机分配到 fixed / free / hybrid 三组；主指标为研究质量（例如 weak-to-strong 任务上的指标、盲审评分），护栏指标为审计成本（评审人时）、越界行为次数（未授权工具调用、超预算）、可复现率；每格多次重复并报告方差和置信区间——Q11 说明 3 个样本的比较几乎全是噪声。
- 常见误区：只看均值不看方差和尾部；把"自由分解平均更好"直接推广到所有任务类别。

### Q17 — 参考回答要点

- **为什么是 compression step**：讲义："Automating alignment research is the compression step that compresses the timeline to the exact misalignment risks the RSP is meant to detect." 能自主完成 alignment 研究的能力，与自主完成 AI R&D 的能力高度重叠。
- **为什么是 qualified good**：讲义："each additional alignment result reduces the gap if and only if the research process is trustworthy." 如果能力复合得比 alignment 快（讲义称这是历史趋势），差距会扩大；而且研究过程本身被一个可能未对齐的系统执行，可信性依赖日志完整性与人类评审。
- **越过 AI R&D 阈值需要什么**：RSP v3.0 的定义是"以相对人类 + AI 工具有竞争力的成本，完全自动化 AI R&D 流水线"。相比现在的 AAR，还缺：自主设定研究议程（而非从人类队列领任务）、端到端的能力开发循环（数据、训练、评测、部署）、长期无人监督下的稳定产出且成本具有竞争力。
- 加分点：给出"接近阈值"的可观测信号——自主派生子任务的比例上升、任务复杂度持续上升、跨任务迁移增多（与 skill 文件的阈值监控一致）。

---

## 六、关联知识点

### 前置知识
- [阶段 15 · 04 Darwin Godel Machine：开放式自我修改 Agents](../../04-darwin-godel-machine/docs/zh.md)：开放式自我改进系统及其对日志与评估的依赖。
- [阶段 15 · 05 AI Scientist v2：达到研讨会论文水平的自主研究](../../05-ai-scientist-v2/docs/zh.md)：自主研究 agent 的流水线，本节把它用到 alignment 研究上。
- [阶段 18 · 11 可扩展监督与弱到强泛化](../../../18-ethics-safety-alignment/11-scalable-oversight-weak-to-strong/docs/zh.md)：AAR 所攻克的 weak-to-strong 问题本身。
- [阶段 16 · 13 共享记忆与黑板模式](../../../16-multi-agent-and-swarms/13-shared-memory-blackboard/docs/zh.md)：多个 agent 通过共享存储协作，即本节"共享论坛"的通用模式。

### 本节被哪些后续内容用到
- [阶段 15 · 07 递归自我改进：能力与 Alignment 的权衡](../../07-recursive-self-improvement/docs/zh.md)：从"自动化 alignment 研究"推进到"自动化能力改进"的循环。
- [阶段 15 · 08 有界自我改进设计](../../08-bounded-self-improvement/docs/zh.md)：如何给自我改进循环加闸门。
- [阶段 15 · 15 Human-in-the-Loop：先提出方案，再 Commit](../../15-propose-then-commit/docs/zh.md)：本节"AARs propose; humans commit"的通用形式。
- [阶段 15 · 19 Anthropic Responsible Scaling Policy v3.0](../../19-anthropic-rsp/docs/zh.md)：AI R&D 能力阈值的完整定义。
- [阶段 15 · 20 OpenAI Preparedness Framework 与 DeepMind Frontier Safety Framework](../../20-openai-preparedness-deepmind-fsf/docs/zh.md)：FSF 中对应的 ML R&D autonomy level。
- [阶段 17 · 25 安全：密钥、API 密钥轮换、Audit Logs 与 Guardrails](../../../17-infrastructure-and-production/25-security-secrets-audit/docs/zh.md)：生产中的不可篡改审计日志。

### 延伸关键词
`Automated Alignment Researcher` · `weak-to-strong generalization` · `scalable oversight` · `append-only log` · `hash chain` · `tamper-evident` · `S3 Object Lock` · `WORM storage` · `HMAC` · `prescribed workflow` · `free decomposition` · `AI R&D threshold` · `propose-then-commit`
