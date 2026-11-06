# 测验 · Checkpoints（检查点）与 Rollback（回滚）（Checkpoints and Rollback）

> **阶段 15 · 自主系统 · 第 16 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 每次状态转移都持久化 | 生产实现把每一次 graph-state transition 写入持久存储（如 LangGraph → PostgreSQL），而不是只在少数 commit 点写；多几次写入换来"可以从任意位置 replay" |
| 2 | Lease（租约）恢复 | lease 是"某 worker 正在执行这个 run"的短期声明；worker 崩溃后 lease 过期，另一个 worker 从最新 checkpoint 接手，滚动发布时不丢在途工作 |
| 3 | 四件套缺一不可 | idempotency key（防重复执行）+ precondition check（状态仍与批准时一致）+ post-action verify（副作用真的发生了）+ verify 失败时 rollback |
| 4 | Idempotency 不等于 precondition | 讲义转账例子：崩溃与恢复之间余额被别的流程降到 $500，idempotency 检查照样通过，只有 commit 时重查 precondition 才能避免透支 |
| 5 | 真正的 verify | "工具返回 200"不是验证；要重新读取目标状态：`UPDATE ... RETURNING *`、查已发送邮件夹、回读文件算哈希、对资源再发一次 `GET` |
| 6 | 三类 rollback | in-band（直接逆操作，如 INSERT 后 DELETE）、compensating transaction（新动作抵消原动作，SAGA 模式）、out-of-band（告警给人、暂停流程、保留现场）；"无法撤销"必须在提案中写明并要求更强的 HITL |
| 7 | 双重执行（double-execute） | 最常见事故：执行成功返回 200 → 写"已提交"之前崩溃 → 恢复后看到"已批准未提交"→ 再执行一次 |
| 8 | 写状态的顺序 | 执行前先持久化"in-flight 意图"，带 idempotency key 执行，post-action verify 通过后才标记 committed；恢复路径上先 verify 再决定是否补发 |
| 9 | EU AI Act 第 14 条的工程解读 | checkpoint 可被审计员查询、rollback 至少端到端演练过一次、审计轨迹能挺过一次部署、verify 失败要告警而不是静默记日志 |
| 10 | 代码中的简化 | 意图状态叫 `committed`、成功叫 `verified`；崩溃后重试直接 `idempotent-skip` 而不做 verify，留下"副作用从未发生却被当成已完成"的缺口 |

### 核心技能（能动手做到）

- [ ] 说清 idempotency、precondition、verify、rollback 各自覆盖哪一类故障，并为每类举一个反例
- [ ] 手动追踪 `run_transfer` 在给定调用序列下的返回值、checkpoint 状态和余额
- [ ] 复现"先执行再写状态"导致的 double-execute，并解释"先写意图再执行"为什么能避免它
- [ ] 指出本节代码"崩溃发生在写意图之后、执行之前"时的丢失副作用缺口，并写出带恢复期 verify 的修复版本
- [ ] 为一个具体动作（发 Slack 消息、发邮件、转账）设计 rollback 计划并归类为 in-band / compensating / out-of-band
- [ ] 设计一个 rollback 演练测试（rehearsal test），写出它的断言

---

## 二、基础自测（选择题）

**Q1.** 讲义认为，在 LangGraph、Cloudflare Durable Objects、Microsoft Agent Framework 等不同系统中，"真正有效"的组合是：

- A. idempotency key + precondition check + post-action verify + verify 失败时 rollback
- B. 只要 checkpoint 足够频繁，就不需要 idempotency key
- C. 重试 3 次 + 指数退避，失败后人工处理
- D. 每一步都要求人类审批，就不需要 rollback

**Q2.** 一个工作流被批准"当 A 余额 > $1000 时从 A 转 $100 给 B"。执行中途崩溃；在崩溃与恢复之间，另一个工作流把 A 的余额降到了 $500。恢复后，能阻止这次转账造成透支的机制是：

- A. idempotency key——它保证转账只执行一次
- B. post-action verify——转账后回读余额
- C. lease 过期机制——让另一个 worker 接手
- D. commit 时重新执行的 precondition check

**Q3.** 下面哪一项属于讲义所说的"真正的 post-action verification"？

- A. 工具调用返回了 HTTP 200
- B. 执行 `UPDATE ... RETURNING *`，并断言返回行与预期状态一致
- C. 在日志里写一行 "transfer succeeded"
- D. 同一请求重试 3 次都没有报错

**Q4.** 运行 `code/main.py`，场景 2（commit 中途崩溃后重试）结束时 `balance_A` 是多少？（场景 1 已把 A 从 1500 转出 100。）

- A. 1400：崩溃导致转账丢失
- B. 1200：重试又执行了一次，出现 double-execute
- C. 1300：转账恰好执行一次，重试返回 `idempotent-skip`
- D. 1500：崩溃触发了自动 rollback

**Q5.** 关于 lease（租约），说法正确的是：

- A. lease 是永久锁，worker 崩溃后需要人工释放
- B. lease 记录的是工作流的业务状态，用来做 rollback
- C. lease 只在 commit 点创建，普通状态转移不需要
- D. lease 是"某 worker 正在执行这个 run"的短期声明；worker 崩溃后它会过期，另一个 worker 从最新 checkpoint 恢复

**Q6.** 下列哪项描述的是 **out-of-band rollback**？

- A. 告警通知人类、暂停工作流，把错误状态保留下来供调查
- B. INSERT 之后执行 DELETE，直接撤销副作用
- C. 发起一个新动作抵消原动作，即标准 SAGA 模式
- D. 在提案里写明"此操作无法撤销"，然后照常自动执行

**Q7.** 讲义对 EU AI Act 第 14 条（human oversight）的工程化解读中，**没有**包括下面哪一项？

- A. checkpoint 可以被审计员查询
- B. rollback 至少端到端演练过一次
- C. 每一个工具调用都必须由人类实时逐条批准
- D. 审计轨迹能挺过一次部署（checkpoint 后端不能是临时存储）

**Q8.** 在本节代码中，idempotency key 由 `hashlib.sha256(txid.encode()).hexdigest()[:12]` 生成。若先用 `txid="tx-020", amount=100` 成功执行，再用**同一个** `txid` 但 `amount=900` 调用 `run_transfer`，会发生什么？

- A. 抛出异常，提示金额与原记录不一致
- B. 直接返回 `"ok"`，900 的转账既没执行也没报警
- C. 执行 900 的转账，因为参数不同
- D. 触发 rollback，撤销原先 100 的转账

---

## 三、动手 / 代码题

**Q9.** `run_transfer` 中写意图与执行副作用的顺序如下：

```python
    cp.save(k, {"status": "committed", "txid": txid,
                "from_acct": from_acct, "to_acct": to_acct,
                "amount": amount,
                "prior_last_transfer_id": prior_last_transfer_id})
    persist_transfer(txid, from_acct, to_acct, amount)
    if inject_crash_after_execute:
        raise RuntimeError("simulated crash after execute")
```

1. 假设进程在 `cp.save(...)` 之后、`persist_transfer(...)` 之前崩溃（例如把 `persist_transfer` 临时替换成一个直接 `raise` 的函数）。从 `DB = {A:1500, B:200}` 出发重试同一个 `txid`，返回值和余额分别是什么？
2. 场景 2（崩溃发生在执行之后）重试返回 `idempotent-skip`。此时 checkpoint 中该 key 的状态是什么？它被 verify 过吗？
3. 按讲义"恢复路径上先 verify，再决定是否补发"的思路，改写重试分支。

**Q10.**（讲义练习 2）把"先写状态再执行"改成"先执行再写状态"：

```python
def run_after(cp, txid, amount, crash=False):
    k = m.key(txid); rec = cp.load().get(k, {"status": "new"})
    if rec["status"] in ("committed", "verified"):
        return "skip"
    m.persist_transfer(txid, "A", "B", amount)
    if crash:
        raise RuntimeError("crash")
    cp.save(k, {"status": "committed"})
    return "ok"
```

从 `A=1500, B=200` 出发，先 `run_after(cp, "tx-040", 100, crash=True)`（捕获异常），再 `run_after(cp, "tx-040", 100)`。写出最终余额，说明转账实际执行了几次、为什么。

**Q11.** 阅读 rollback 与 verify 的实现：

```python
def rollback_transfer(txid, from_acct, to_acct, amount, prior_last_transfer_id):
    # Compensating transaction: restore balances and the prior transfer id.
    DB[f"balance_{from_acct}"] += amount
    DB[f"balance_{to_acct}"] -= amount
    DB["last_transfer_id"] = prior_last_transfer_id
...
    if inject_verify_fail or DB["last_transfer_id"] != txid:
        rollback_transfer(txid, from_acct, to_acct, amount, prior_last_transfer_id)
```

1. 注释说这是 compensating transaction。按讲义的三类定义，它更接近哪一类？为什么？
2. 列出至少三个在真实并发环境下会出问题的地方（提示：如果 `rollback_transfer` 在没有对应转账时被调用会怎样？`last_transfer_id` 被直接覆盖会怎样？verify 只比较一个字段够吗？rollback 之后有没有验证？）。
3. 给出一个更稳妥的 SAGA 式补偿方案的要点。

**Q12.** 手动追踪：`DB = {"balance_A": 1500, "balance_B": 200, "last_transfer_id": None}`，使用同一个 checkpoint 文件依次执行：

```python
r1 = run_transfer(cp, "tx-a", "A", "B", 1300, min_balance=200)
r2 = run_transfer(cp, "tx-b", "A", "B", 1,    min_balance=200)
DB["balance_A"] += 500                       # 外部入账
r3 = run_transfer(cp, "tx-b", "A", "B", 1,    min_balance=200)
r4 = run_transfer(cp, "tx-c", "A", "B", 300,  min_balance=200, inject_verify_fail=True)
```

写出 `r1`–`r4`、最终 `DB`，并讨论：`r3` 的结果是不是你想要的？"aborted-precondition 也算终态"这个设计的利弊是什么？

---

## 四、面试高频题

**Q13.**（基础必考）Agent 执行"有后果的动作"时，idempotency key、precondition check、post-action verify、rollback 各解决什么问题？只做其中一两个会漏掉什么？

**Q14.**（原理深挖）为什么说对外部副作用"恰好一次（exactly-once）"在一般情况下做不到？工程上如何做到"等效一次"？请结合 double-execute 事故的五个步骤说明写状态的顺序。

**Q15.**（工程实践）你要给一个运行数小时的后台 coding / ops agent 设计 checkpoint 后端。你会持久化什么、怎么设计 lease、怎么保证审计轨迹在部署后仍然可查？

**Q16.**（场景设计）（讲义练习 3）为"往团队 Slack 频道发一条消息"和"给客户发一封退款确认邮件"分别设计 rollback 计划，并归类为 in-band / compensating / out-of-band。

**Q17.**（追问型）面试官问："你们怎么证明自己满足 EU AI Act 第 14 条的有效人类监督？" 请给出一个可执行的 rollback 演练（rehearsal）测试，并说明它断言什么。

---

## 五、参考答案与解析

### Q1 — 答案：A

讲义原文："the combination that actually works is: idempotency key (prevents double-execute) + precondition check (state is still what we approved against) + post-action verify (the side effect actually happened) + rollback on verify-fail"。代码结尾的 HEADLINE 也强调 "Four pieces, not one"。

- B 错：checkpoint 只解决"从哪里恢复"，恢复后重放仍可能重复执行副作用，需要 idempotency。
- C 错：盲目重试恰恰是 double-execute 的来源。
- D 错：讲义说的是"没有 rollback 的动作需要更强的 HITL"，人类审批不能替代 rollback；而且审批发生在执行之前，挡不住执行中的崩溃与状态漂移。

### Q2 — 答案：D

讲义用这个例子说明 "Idempotency alone is not enough"：idempotency 只判断"这个动作做没做过"，不判断"现在还该不该做"。崩溃和恢复之间状态漂移了，只有在 **commit 时**重新检查 precondition 才能发现。代码中 precondition 也是在 `run_transfer` 执行前即时计算的：`DB[f"balance_{from_acct}"] - amount < min_balance`。

- A 错：idempotency 检查照样通过，正是讲义要指出的陷阱。
- B 错：verify 在副作用之后，透支已经发生，只能靠 rollback 补救。
- C 错：lease 只决定由谁接手执行。

### Q3 — 答案：B

讲义："'The tool returned 200' is not verification. Real verification re-reads the target state"，并列出 `UPDATE ... RETURNING *`、查已发送邮件夹、回读文件算哈希、追加 `GET`。A、C、D 都只是"调用方自己的说法"，没有去目标系统确认。

### Q4 — 答案：C

实际输出：`retry result=idempotent-skip  DB={'balance_A': 1300, 'balance_B': 400, 'last_transfer_id': 'tx-002'}`。第一次调用在 `persist_transfer` 之后才抛出模拟崩溃，钱已经转出（1400 → 1300）；状态 `committed` 已在执行前写入，重试直接短路，没有再扣一次。A 对应"崩溃在执行之前"的另一种情况（见 Q9）；B 对应练习 2 的错误顺序（见 Q10）；D 错，代码里崩溃不会触发 rollback，rollback 只在 verify 失败时调用。

### Q5 — 答案：D

讲义 Key Terms："Short-lived claim that a worker is executing a run; expires on crash"。A 错在"永久"，正是因为短期、会过期，才能在崩溃后自动转移；B 混淆了 lease 和 checkpoint；C 错，lease 覆盖整个 run 的执行期。

### Q6 — 答案：A

讲义："Out-of-band rollback: alert a human, pause the workflow, leave the bad state for investigation."。B 是 in-band；C 是 compensating transaction；D 是错误做法——"无法撤销"必须写进提案，但这类动作需要在 commit 时施加更强的 HITL（第 15 节的 challenge-and-response），而不是照常自动执行。

### Q7 — 答案：C

讲义列出的四条是：checkpoint 可查询、rollback 已演练、审计轨迹挺过部署、verify 失败要告警而不是静默记日志。C 不在其中——"有效人类监督"并不等于逐条实时审批，后者在长程 agent 上既不现实也会造成审批疲劳。

### Q8 — 答案：B

已实际运行：`run_transfer(cp, "tx-020", ..., 100, ...)` 返回 `ok`，再用相同 txid、`amount=900` 调用仍返回 `ok`，余额停在 A=1400、B=300。原因是 key 只由 `txid` 决定，代码读到 `status == "verified"` 就直接返回缓存结果，**不比对参数**。本节 `outputs/skill-rollback-rehearsal.md` 要求 "the idempotency key is derived from proposal content"；生产实践通常还会在命中 key 时比对请求指纹（参数哈希），不一致就报 409 冲突，而不是静默返回旧结果。A 是理想做法但代码没做；C、D 都与代码行为不符。

### Q9 — 参考答案

1. 已实际运行（用 monkeypatch 让 `persist_transfer` 抛异常）：重试返回 `idempotent-skip`，余额仍为 `A=1500, B=200, last_transfer_id=None`。也就是说，**转账从未发生，系统却报告"已处理"**。代码注释自己也承认了这个 "Subtle durability gap"。
2. 状态仍是 `committed`（意图记录），从未被提升为 `verified`。场景 2 能"碰巧正确"，只是因为崩溃恰好发生在执行之后。代码里的 `committed` 其实是讲义说的 "in-flight intent"，命名容易误导：讲义要求"verify 成功后才标记 committed"，代码用的是 `verified`。
3. 改写思路：命中意图状态时不要直接跳过，而是先去目标系统做 verify：

```python
    if record["status"] == "committed":            # 实为 in-flight 意图
        if DB["last_transfer_id"] == txid:          # 副作用已落地（更好的做法：查带 txid 的流水）
            cp.save(k, {"status": "verified", "txid": txid})
            return "recovered-verified"
        # 副作用没落地：重新检查 precondition 后补发（目标端必须按 txid 去重）
        if DB[f"balance_{from_acct}"] - amount < min_balance:
            cp.save(k, {"status": "aborted-precondition", "txid": txid})
            return "aborted-precondition"
        persist_transfer(txid, from_acct, to_acct, amount)
        # ...再走一次正常的 post-action verify
```

要点：恢复路径上"先 verify 再决定"，而判断依据必须来自目标系统；`last_transfer_id` 只记最后一笔，若中间有其他转账就判断不准，生产里应查一张以 txid 为主键的流水表，并让目标端自己按 idempotency key 去重（代码注释中的方案 (a)）。

### Q10 — 参考答案

已实际运行：最终 `A=1300, B=400, last_transfer_id='tx-040'`。只想转 100，实际转了 **两次**。

过程：第一次调用执行了 `persist_transfer`（A 变 1400），在写状态前崩溃，checkpoint 里没有任何记录；重试时读到 `status == "new"`，于是再执行一次（A 变 1300），这才写入 `committed`。这正是讲义 double-execute 的第 3–5 步："Workflow crashes before persisting the 'committed' status... sees 'approved but not committed'; re-executes."

对比：原代码先写意图再执行，崩溃后重试能看到意图记录，不会盲目重放；代价是 Q9 中"意图写了但没执行"的缺口，需要恢复期 verify 来补。两种顺序各有一个缺口，**只有"先写意图 + 恢复时去目标系统核对"才能把两个缺口都堵上**。

### Q11 — 参考答案

1. 更接近 **in-band rollback**（直接逆操作）：它把余额加回、减回，并把 `last_transfer_id` 直接写回旧值，是对原状态的"还原"。SAGA 意义上的 compensating transaction 是一个**新的、可审计的业务动作**（例如一笔 B→A 的冲正转账，带自己的 txid 和流水记录），而不是悄悄改回字段。
2. 问题（第一条已实际验证）：
   - **没有守卫、不幂等**：在没有对应转账的情况下调用 `rollback_transfer("tx-x", "A", "B", 100, "tx-prev")`，A 从 1500 变成 1600、B 从 200 变成 100——凭空把钱"转回来"。rollback 本身被重试两次也会多冲一次。
   - **覆盖并发写**：`DB["last_transfer_id"] = prior_last_transfer_id` 会抹掉 verify 与 rollback 之间其他工作流写入的转账 id。
   - **verify 太弱**：只比较 `last_transfer_id`，不检查余额是否正确变化；若别的转账恰好在之后写入，verify 会误判为失败并错误回滚。
   - **rollback 后不 verify**：没有确认余额真的恢复；失败也只是返回字符串，没有告警（讲义要求 "Failed verifications are alerted on, not silently logged"）。
   - **B 账户可能已经花掉这笔钱**：直接 `-= amount` 可能让 B 变负，真实世界要走 out-of-band。
3. SAGA 式补偿要点：为补偿动作生成独立 txid（如 `tx-004-comp`），同样带 idempotency key；先写补偿意图，再执行冲正转账，再回读流水 verify；补偿失败则升级为 out-of-band（告警 + 暂停 + 保留现场）；所有步骤写入 append-only 的审计日志。

### Q12 — 参考答案

已实际运行：`r1='ok'`、`r2='aborted-precondition'`、`r3='aborted-precondition'`、`r4='verify-fail-rolled-back'`，最终 `DB={'balance_A': 700, 'balance_B': 1500, 'last_transfer_id': 'tx-a'}`；checkpoint 中三个 key 的状态分别是 `verified`、`aborted-precondition`、`rolled-back`。

逐步：

- `r1`：`1500 − 1300 = 200`，条件是 `< min_balance` 才拒绝，等于 200 允许 → 执行，A=200、B=1500。
- `r2`：`200 − 1 = 199 < 200` → 写 `aborted-precondition`。
- 入账后 A=700。`r3`：同一 txid 命中终态 `aborted-precondition`，**直接返回旧结论**，即便现在余额足够。
- `r4`：`700 − 300 = 400 ≥ 200` 通过 precondition，执行后 A=400；注入 verify 失败 → rollback，A 回到 700，`last_transfer_id` 还原为 `tx-a`。

讨论：把 `aborted-precondition` 当终态的好处是结果确定、可审计——同一个已批准提案不会因为反复重试而"碰运气"通过；坏处是业务上合理的"稍后重试"被永久拒绝。更清晰的做法是：precondition 失败意味着"批准时的前提已不成立"，应该回到 propose 阶段重新生成提案（新 txid）、重新审批，而不是复用旧 key。

### Q13 — 参考回答要点

- **Idempotency key**：解决"重试导致重复执行"。只有它时，状态漂移（Q2）和"返回成功但没生效"都发现不了。
- **Precondition check（commit 时）**：解决"批准与执行之间状态变了"（time-of-check vs time-of-use）。本节 skill 文件强调必须在 commit 时而不是 propose 时检查。
- **Post-action verify**：解决"以为发生了其实没发生 / 发生得不对"。只有返回码检查等于没有 verify。
- **Rollback**：解决"已知坏状态怎么办"——恢复或告警。没有 rollback，verify 失败也只能干看着。
- 加分点：能用代码的四个场景一一对应（干净运行、崩溃重试、precondition 失败、verify 失败）；指出本节代码在恢复路径上缺 verify。
- 常见误区：认为"有了 checkpoint 就能安全重放"——checkpoint 只保存工作流状态，不保证外部副作用的次数。

### Q14 — 参考回答要点

- **为什么做不到严格的 exactly-once**：执行副作用和写本地状态是两个系统上的两次写，中间总可能崩溃（经典的两将军问题）。先写状态后执行 → 可能"记了没做"；先执行后写状态 → 可能"做了没记"。
- **double-execute 五步**：批准（key k）→ 执行成功返回 200 → 写 committed 前崩溃 → 恢复后看到"已批准未提交"→ 再执行一次。
- **等效一次（effectively-once）= at-least-once 投递 + 幂等接收 + 核对**：
  1. 执行前持久化 in-flight 意图（带 key）；
  2. 把 idempotency key 传给目标系统，让目标端去重（支付 API 的 `Idempotency-Key` 头、数据库唯一约束）；
  3. post-action verify 成功后才标记 committed；
  4. 恢复时看到 in-flight，先去目标系统核对，再决定补发或标记完成。
- 加分点：outbox 模式（业务写和"待发事件"写在同一个本地事务中）；说明本节代码的 `committed` 实为 in-flight。
- 常见误区："加个重试就好"；"状态写在执行之后更安全"（练习 2 已证伪）。

### Q15 — 参考回答要点

- **持久化什么**：每一次状态转移（节点输入/输出、工具调用的意图与结果、审批记录、idempotency key、precondition 快照、verify 结果、rollback 记录），带时间戳、run id、worker id、提案哈希。
- **存储**：持久化数据库（如 PostgreSQL，LangGraph 的 checkpointer 即如此），不能是内存或容器本地盘；本节 skill 文件把 "in-memory checkpoint" 列为直接拒绝项。写入要原子（代码用"临时文件 + fsync + `os.replace`"演示了这一点）。
- **Lease 设计**：带 TTL 的租约 + 心跳续期；worker 崩溃后租约过期，其他 worker 从最新 checkpoint 接手；用 fencing token（单调递增版本号）防止"假死后复活"的旧 worker 继续写。
- **审计可查**：有文档化的 schema（skill 文件要求无 schema 不上生产），append-only，保留期满足合规要求；部署不清库，迁移有版本。
- **告警**：verify 失败、rollback 失败、lease 频繁过期都要进告警通道。
- 加分点：提到 Cloudflare Durable Objects 让计算与状态同址；Microsoft Agent Framework 的 `Checkpoint` 原语靠 replay + idempotency 覆盖重试。

### Q16 — 参考回答要点

- **发 Slack 消息**：
  - 可以 `chat.delete` 删除（若 bot 有权限）→ 形式上是 in-band；但消息可能已被人看到、被转发或触发了下游 webhook，删除并不能真正"撤销"。
  - 更稳妥：发更正/撤回消息（compensating），并在 thread 里说明；若内容涉及敏感信息，升级为 out-of-band（通知安全团队）。
  - verify：发送后用返回的 `ts` 读取消息，确认频道和内容正确。
- **退款确认邮件**：
  - 邮件无法撤回 → 在提案中明确标注"不可撤销"（no-op rollback），commit 时要更强的 HITL（第 15 节 challenge-and-response）。
  - 发错时的补救是发更正邮件（讲义把 "Send-correction-email after send" 列在 in-band 例子里，但从语义上看它更像 compensating：原邮件仍在客户收件箱里）。
  - verify：提交后在已发送文件夹查 message ID。
- 分类判断标准：能否把目标系统恢复到**等价于没发生过**的状态 → in-band；只能用新动作抵消影响 → compensating；需要人判断 → out-of-band。
- 加分点：指出讲义对"更正邮件"的归类值得商榷；对"不可撤销"动作，最好的 rollback 是 commit 前的 dry-run 与审批。

### Q17 — 参考回答要点

- 第 14 条的工程化解读（讲义）：checkpoint 可查询、rollback 已演练、审计轨迹挺过部署、verify 失败要告警。
- **演练测试脚本**（对应 skill 文件 a–f 步）：
  1. 在 staging 启动真实工作流；
  2. 在执行副作用之后、写完成状态之前注入崩溃（kill 进程，而不是抛 Python 异常）；
  3. 让另一个 worker 在 lease 过期后接手；
  4. **断言**：副作用恰好发生一次（查目标系统流水，按 txid 计数 == 1）；
  5. 注入 verify 失败；
  6. **断言**：rollback 执行、目标状态恢复到快照、产生告警事件、审计日志里有完整的 intent → executed → verify-failed → rolled-back 链路；
  7. 重新部署服务后，**断言**审计记录仍可按 run id 查到。
- 额外断言：precondition 漂移场景下动作不执行；同一 key 不同参数被拒绝。
- 加分点：演练要定期跑（如每次发版的 CI 或每月 game day），而不是"上线前跑过一次"；结果本身也存档，作为监管证据。
- 常见误区：用单元测试里的 `raise` 代替真实崩溃——真实崩溃会丢失内存状态，`raise` 不会（本节代码的全局 `DB` 在崩溃后仍保留在内存中）。

---

## 六、关联知识点

### 前置知识
- [阶段 15 · 12 长时间运行的后台 Agents：Durable Execution](../../12-durable-execution/docs/zh.md)：让崩溃的 agent 可恢复，是本节 checkpoint 与 lease 的基础。
- [阶段 15 · 15 Human-in-the-Loop：先提出方案，再 Commit](../../15-propose-then-commit/docs/zh.md)：每个已批准动作携带的 rollback 计划与 idempotency key 来自这里。
- [阶段 15 · 14 紧急停止开关、Circuit Breakers 与金丝雀 Tokens](../../14-kill-switches-canaries/docs/zh.md)：out-of-band 停止与告警机制。
- [阶段 11 · 16 Agent State Machines——图、节点与 Checkpoints](../../../11-llm-engineering/16-langgraph-state-machines/docs/zh.md)：图状态与 checkpointer 的基本用法。
- [阶段 14 · 13 有状态图 Orchestration：Durable Execution 与 Checkpoints](../../../14-agent-engineering/13-langgraph-stateful-graphs/docs/zh.md)：LangGraph 持久化执行的工程细节。

### 本节被哪些后续内容用到
- [阶段 16 · 22 生产扩展：队列、Checkpoints 与持久性](../../../16-multi-agent-and-swarms/22-production-scaling-queues-checkpoints/docs/zh.md)：多 agent 场景下的 checkpoint 与持久化。
- [阶段 17 · 26 合规：SOC 2、HIPAA、GDPR、PCI-DSS、EU AI Act、ISO 42001](../../../17-infrastructure-and-production/26-compliance-frameworks/docs/zh.md)：EU AI Act 等合规框架的完整视角。
- [阶段 17 · 25 安全：密钥、API 密钥轮换、Audit Logs 与 Guardrails](../../../17-infrastructure-and-production/25-security-secrets-audit/docs/zh.md)：审计日志的生产实践。
- [阶段 18 · 24 监管框架：欧盟、美国、英国、韩国](../../../18-ethics-safety-alignment/24-regulatory-frameworks-eu-us-uk-korea/docs/zh.md)：EU AI Act 的监管背景。
- [阶段 19 · 47 Checkpoint 保存与恢复](../../../19-capstone-projects/47-checkpoint-save-resume/docs/zh.md)、[阶段 19 · 80 分片 Checkpoint 与原子恢复](../../../19-capstone-projects/80-checkpoint-sharded-resume/docs/zh.md)：原子写与恢复的另一类应用（训练 checkpoint）。

### 延伸关键词
`idempotency key` · `precondition / TOCTOU` · `post-action verification` · `SAGA` · `compensating transaction` · `outbox pattern` · `lease / fencing token` · `at-least-once + idempotent` · `atomic rename (os.replace)` · `LangGraph checkpointer` · `Durable Objects` · `EU AI Act Article 14`
