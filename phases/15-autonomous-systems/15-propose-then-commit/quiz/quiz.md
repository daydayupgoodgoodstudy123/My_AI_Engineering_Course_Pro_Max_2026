# 测验 · Human-in-the-Loop：先提出方案，再 Commit（Human-in-the-Loop: Propose-Then-Commit）

> **阶段 15 · 自主系统 · 第 15 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 2023 式 HITL 的问题 | 同步弹窗"Agent 想发邮件给 X，同意吗？"会被大量橡皮图章式通过：批准很快、几乎不能预测问题，出事后审计记录里是一长串用户记不起来的批准 |
| 2 | Propose-then-commit 四阶段 | Propose（持久化提案）→ Surface（带元数据展示给人）→ Commit（肯定批准后才执行）→ Verify（执行后回读确认） |
| 3 | 提案必须携带的元数据 | intent（为什么做）、data lineage（哪个来源导致了提案）、permissions touched（动用哪些权限/文件/端点）、blast radius（最坏情况）、rollback plan（如何撤销）、idempotency key |
| 4 | 幂等键 | 每个提案唯一，重提返回同一记录；把一次批准绑定到唯一一次副作用，重试时第二次执行是 no-op；与 Stripe、AWS API 的幂等模式相同；不能含挂钟时间 |
| 5 | 审批要比进程活得久 | 等待审批的状态不属于 agent，workflow 暂停（第 12 节），批准到达后从原处继续；所以 LangGraph 把 `interrupt()` 与 PostgreSQL checkpoint 搭配 |
| 6 | 橡皮图章与质询-应答清单 | 默认 Approve/Reject 按钮导致无实质审阅；对策是必须对具体问题给出肯定回答后 Approve 才可用——是强制函数，不是官僚主义 |
| 7 | 动作分级 | 不可逆写、金融交易、对外通信、生产数据库变更、破坏性文件操作总是 HITL；可逆动作有时 HITL；读与检查从不 HITL |
| 8 | 执行后验证 | "commit 跑了"不等于"副作用发生了"；网络分区和竞态可能让 workflow 以为成功而后端没有落盘；回读目标资源确认 |
| 9 | EU AI Act 第 14 条 | 要求高风险 AI 系统有"有效"的人类监督；讲义：监管语言明确排除橡皮图章模式 |
| 10 | 代码揭示的缺口 | 幂等只靠存储 `status`，执行与写回之间崩溃会重复执行；审批不校验状态；缺 permissions 字段；verify 失败不处理 |

### 核心技能（能动手做到）

- [ ] 跑通 `code/main.py`，逐行解释三个演示的输出，并说出 Demo 2 演示的"重试"与讲义所说"瞬时故障后的重试"有何不同
- [ ] 构造"执行后、写回前崩溃"的场景复现重复执行，并把幂等键传到执行端修复它
- [ ] 把审批流程改成严格状态机（`waiting → approved/rejected → committed/verify_failed`），拒绝非法转换
- [ ] 正确设计幂等键：由内容与业务语义派生、不含时间，同时不误吞合法的重复动作
- [ ] 为一个具体动作类别设计 3 个质询-应答问题，并说明为什么是这三个
- [ ] 判断一个动作属于"总是 / 有时 / 从不 HITL"中的哪一级

---

## 二、基础自测（选择题）

**Q1.** 按讲义，一个 propose-then-commit 提案在持久化时**应当**携带哪一组信息？

- A. 只需要动作名称和参数，其余信息审阅人可以自己查
- B. intent、data lineage、permissions touched、blast radius、rollback plan、idempotency key
- C. 动作名称、执行时间戳、agent 的置信度分数
- D. agent 的完整思维链，以便审阅人逐字检查

**Q2.** 下列哪种做法会让"幂等键"失去意义？

- A. 用 `(thread_id, action, payload)` 的哈希作为键
- B. 对 payload 先 `json.dumps(..., sort_keys=True)` 再哈希
- C. 把业务订单号作为键的一部分
- D. 把当前挂钟时间戳拼进键里

**Q3.** 讲义给出的应对"橡皮图章式批准"的有据可查的方法是：

- A. 质询-应答清单：审阅人必须对具体问题给出肯定回答，Approve 按钮才可用
- B. 把 Approve 按钮做得更大更醒目
- C. 让 agent 自己再审阅一遍自己的提案
- D. 取消人工审批，改为完全自动执行

**Q4.** 讲义中"post-action verification（执行后验证）"的含义是：

- A. 执行前再问用户一次是否确定
- B. 检查工具调用返回了 HTTP 200
- C. 执行后回读目标资源，确认副作用确实发生；失败则系统处于已知的坏状态并触发告警
- D. 由另一个 LLM 判断执行结果是否合理

**Q5.** 按讲义的动作分级，下列哪个动作属于"总是需要 HITL（always HITL）"？

- A. 读取工作区中的一个配置文件
- B. 列出云账号中的存储桶
- C. 修改本地分支上的一个源文件（有 git 可以回退）
- D. 向外部客户的邮件列表发送一封公告邮件

**Q6.** 运行 `code/main.py`，Demo 3 中 `db.drop_table` 提案被清单拒绝后，代码故意调用了 `commit`。输出是：

- A. `[commit] refusing: 7c4870bc65bafbe9 status=waiting`
- B. `[commit] refusing: 7c4870bc65bafbe9 status=rejected`
- C. `[commit] executed; verify=True`
- D. `[commit] idempotent: 7c4870bc65bafbe9 already committed, no re-execute`

**Q7.** 讲义说 LangGraph 把 `interrupt()` 与 PostgreSQL checkpoint 搭配，而不只是用内存状态。主要原因是：

- A. PostgreSQL 的查询速度比内存快
- B. 内存状态无法存储字符串
- C. 审批可能在很久之后才到达（例如两天后），workflow 状态必须跨进程、跨重启、跨部署保存
- D. `interrupt()` 只能在 PostgreSQL 上编译

**Q8.** 在本节代码中，同一个会话里先完整执行了一次 `email.send` 到 `{"to": "a"}`；一周后 agent 合法地需要再发一次完全相同的邮件，于是再次 `propose` 同样的 `Proposal`。会发生什么？

- A. 生成一个新的记录，等待审批
- B. 命中同一个幂等键，返回已是 `committed` 的旧记录；之后 `commit` 走"already committed"分支，这封邮件不会再发出
- C. 抛出 `KeyError`
- D. 自动执行，无需审批

---

## 三、动手 / 代码题

**Q9.** 阅读 `commit`：

```python
def commit(store: Store, k: str) -> bool:
    data = store.all()
    rec = data[k]
    if rec["status"] == "committed":
        print(f"  [commit] idempotent: {k} already committed, no re-execute")
        return True
    if rec["status"] != "approved":
        ...
        return False
    p = Proposal(...)
    execute(p)
    rec["status"] = "committed"
    store.save(k, rec)
    print(f"  [commit] executed; verify={verify(p)}")
    return True
```

1. 讲义的转账例子："user approves 'transfer $100 from A to B.' Network blips. Workflow retries." 如果进程在 `execute(p)` 之后、`store.save` 之前崩溃，重试 `commit` 会怎样？Demo 2 为什么没有暴露这个问题？
2. 修改代码，使这种情况下副作用也只发生一次。

**Q10.** 下面的调用序列会产生几条副作用？指出根本原因并给出修复。

```python
k = propose(store, p)
checklist_approve(store, k, understood=True, verified=True, rollback_ready=True)
commit(store, k)
rubber_stamp_approve(store, k)     # 有人又点了一次 Approve
commit(store, k)
```

**Q11.** 讲义练习 1："Confirm that a retry of an approved proposal uses the durable record and does not re-execute. Now change the idempotency key to include a timestamp and show the retry double-executes."

1. 只把 `Proposal.key()` 改为"原哈希 + `time.time_ns()`"，再运行 Demo 2（用同一个 `k` 两次调用 `commit`），副作用是几条？为什么？
2. 在什么样的重试路径下，"带时间戳的键"才会导致重复执行？
3. 结合 Q8，说明幂等键设计中"太粗"与"太细"各自的代价。

**Q12.** 讲义练习 2 与练习 3：

1. 给提案加上 `permissions` 字段并在 `surface` 中展示。它保护的是什么？
2. 让 `verify` 可能失败，并在失败时自动执行回滚、标记状态、告警。给出关键代码。

---

## 四、面试高频题

**Q13.**（基础必考）什么是 propose-then-commit？它和"弹窗问用户是否同意"有什么本质区别？

**Q14.**（原理深挖）HITL 场景下的幂等键应该怎么设计？为什么只在自己的数据库里把状态标成 `committed` 不足以保证"恰好一次"？

**Q15.**（工程实践）"橡皮图章式批准"为什么会发生？除了清单，你还会用哪些手段让审阅真正有效？

**Q16.**（场景设计）讲义练习 4：为"agent 代表公司在公开 Twitter/X 账号发帖"设计 propose-then-commit 流程，包括提案元数据、三个质询问题、验证与回滚。

**Q17.**（追问型）讲义练习 5：什么时候一个同步的"Approve?"弹窗就够了、不需要持久化存储？你在接受什么风险？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义 "The propose-then-commit state machine" 第 1 步列出：intent、data lineage、permissions touched、blast radius、rollback plan、idempotency key。A 正是 skill 文件批评的"'the agent wants to X' is not a proposal"；C 中的时间戳与置信度都不是讲义要求的字段，且时间戳不能用于幂等键；D 不可行也不必要——审阅人需要的是结构化的风险信息，而不是冗长的推理过程。

### Q2 — 答案：D

skill 文件："Keys that include wall-clock time are not idempotency keys; they are logging timestamps." 每次重试时间不同，键就不同，重复的提交会被当成新的提案。A 是本节代码的做法（讲义："hash of (thread_id, action_signature)"）；B 保证同内容得到同一个键；C 用业务主键是常见的正确做法，还能区分"合法的重复动作"（见 Q11）。

### Q3 — 答案：A

讲义："Documented mitigation: a challenge-and-response checklist that requires positive answers to specific questions before the Approve button is enabled." B 只会让人点得更快；C 违反讲义"The reviewer is a person (not the agent reviewing itself)"，skill 文件也把它列为 hard reject；D 放弃了监督，在 EU AI Act 第 14 条的高风险场景下不可接受。

### Q4 — 答案：C

讲义："The verify step re-reads the target resource after commit to confirm." 以及 "If the verify step fails, the system is in a known bad state and alerting engages." B 是 skill 文件明确否定的："'The tool returned 200' is not verify."；A 是二次确认而非验证；D 不是回读资源。

### Q5 — 答案：D

讲义："Consequential actions (always HITL): irreversible writes, financial transactions, outbound communication, production database changes, destructive file-system operations." 发给外部客户的邮件属于对外通信且不可撤回。A、B 是"Reads and inspections (never HITL)"；C 是"Reversible actions (sometimes HITL): edits to local files"。

### Q6 — 答案：A

`checklist_approve` 拒绝时直接 `return False`，**不修改状态**，记录仍是 `waiting`，所以 `commit` 走 `status != "approved"` 分支，打印 `refusing: ... status=waiting`。B 是很多人以为的结果，但代码并没有写 `rejected` 状态（这本身是个缺口：被拒的提案之后仍可被一键批准）；C、D 都不会发生。

### Q7 — 答案：C

讲义："an approval two days later still finds the workflow intact." 审批的等待时间不由 agent 控制，期间进程可能重启、主机可能更换、服务可能部署新版本，内存状态都会丢失。A 错，持久化存储一般比内存慢，选择它是为了耐久而非速度；B、D 无依据。

### Q8 — 答案：B

已实测：第二次 `propose` 打印 `idempotent: record e21b... already exists (status=committed)`，返回同一个键；`commit` 打印 `already committed, no re-execute`，新增副作用 0 条。幂等键只由 `(thread_id, action, payload)` 派生，两次合法的相同动作无法区分。A 是期望的行为但代码做不到；C 不会发生，`propose` 用的是 `.get(k)`；D 错，命中旧记录也不会绕过审批去执行。

### Q9 — 参考答案

1. **会重复执行**。崩溃时副作用已经发生，但存储里的状态仍是 `approved`；重试时 `commit` 看到 `approved`，就会再执行一次。已实测：在写回 `committed` 时抛异常模拟崩溃，再次 `commit`，`SIDE_EFFECTS` 中出现 2 条 `email.send:{"to": "a"}`——正是讲义"The user has approved once but the transfer executes twice"的情形。Demo 2 没暴露它，是因为 Demo 2 的重试发生在第一次 `commit` **完全成功之后**（状态已经是 `committed`），演示的是"成功后的重复调用"，不是"故障后的重试"。

2. 修复的核心：**把幂等键传给执行端，由执行端（或与副作用同一事务的去重表）判断是否已处理**，而不是只依赖自己存储里的状态：

   ```python
   PROCESSED: dict[str, bool] = {}          # 模拟后端的"已处理键"表

   def execute(proposal: Proposal, idem_key: str) -> bool:
       if idem_key in PROCESSED:            # 后端去重：同一键只执行一次
           return PROCESSED[idem_key]
       SIDE_EFFECTS.append(f"{proposal.action}:{json.dumps(proposal.payload)}")
       PROCESSED[idem_key] = True
       return True

   def commit(store, k):
       ...
       execute(p, idem_key=k)               # 把提案的幂等键一路传下去
       rec["status"] = "committed"
       store.save(k, rec)
   ```

   这样即使在 `execute` 与 `save` 之间崩溃，重试时后端识别出同一键，返回第一次的结果而不再执行。真实系统中对应支付/邮件 API 的 `Idempotency-Key` 请求头（讲义："the same idempotency pattern Stripe and AWS APIs use"），或者在自己的数据库里用"同一事务中写业务结果 + 写去重记录"的 outbox 模式。

### Q10 — 参考答案

**2 条**（已实测）。第一次 `commit` 执行并写回 `committed`；`rubber_stamp_approve` 不检查当前状态，直接把 `status` 改回 `approved`；第二次 `commit` 看到 `approved`，于是又执行了一次。

根本原因：审批函数**不是状态机的合法转换**，它们无条件地写 `approved`，覆盖了终态 `committed`。同理，被清单拒绝的提案（状态仍是 `waiting`）也可以被随后的一键批准放行。

修复：显式定义合法转换并在每次写状态前检查：

```python
ALLOWED = {
    "waiting":  {"approved", "rejected"},
    "approved": {"committed"},
    "committed": {"verified", "verify_failed"},
}

def transition(store, k, new_status, **extra):
    rec = store.all()[k]
    if new_status not in ALLOWED.get(rec["status"], set()):
        raise ValueError(f"illegal transition {rec['status']} -> {new_status}")
    rec.update(status=new_status, **extra)
    store.save(k, rec)
```

`rubber_stamp_approve` / `checklist_approve` 改为调用 `transition(store, k, "approved", ack_mode=..., reviewer=...)`；清单拒绝时调用 `transition(store, k, "rejected", reason=...)`。生产中还要用数据库的条件更新（`UPDATE ... WHERE key=? AND status='waiting'`）防止并发审批互相覆盖。

### Q11 — 参考答案

1. **1 条**（已实测）。Demo 2 的重试是 `commit(store, k)`，用的是**已经算好的同一个 `k`**，`key()` 不会被重新调用，所以键里有没有时间戳都无所谓——第二次 `commit` 照样命中 `committed` 分支。讲义练习 1 的后半句在这份代码的 Demo 2 写法下复现不出来。
2. 当重试路径会**重新生成提案**时：例如 agent 进程崩溃后从头重跑，重新调用 `propose(store, p)`。此时带时间戳的 `key()` 得到一个新键，存储里查不到旧记录，于是新建一条 `waiting` 记录，审阅人再批准一次（审阅人很可能不知道这是同一件事），`commit` 就再执行一次。实测：这条路径下副作用为 2 条。这也说明幂等键必须**由内容决定**，才能把"同一件事的第 N 次尝试"映射到同一条记录。
3. 粒度权衡：
   - **太细**（含时间戳、随机数）：同一件事的重试被当成新事件 → 重复执行（转账两次）。
   - **太粗**（只有 `thread_id + action + payload`）：不同时间的两件合法同样的事被当成同一件 → 第二件被静默吞掉（Q8：下周的提醒邮件没发出）。
   - 正确做法：键 = 内容 + **业务语义上的区分量**（如"2026 第 42 周提醒"、订单号、工单号），既能让重试命中同一记录，又能区分真正不同的业务事件；绝不使用挂钟时间。

### Q12 — 参考答案

1. 加字段：

   ```python
   @dataclass
   class Proposal:
       ...
       permissions: list[str] = field(default_factory=list)   # 如 ["smtp:send", "list:team@example.com"]
   ```

   并在 `surface` 的字段元组中加上 `"permissions"`。它保护的是**权限越界**：审阅人能直接看到"这个动作动用了哪些作用域/端点/文件"，如果一个"关闭陈旧 issue"的提案要求 `db:drop`，或者一个"给团队发公告"的提案动用了"外部客户列表"，审阅人就能识别出提案与意图不符（可能来自注入或 agent 推理错误）。讲义把它列为提案必备元数据，skill 文件要求五项元数据缺一不可。（讲义练习 3 让你对照 Microsoft Agent Framework 的 `RequestInfoEvent` 找缺失字段；permissions 是代码相对讲义自身清单就缺的一项。）

2. 验证失败 → 回滚 → 告警：

   ```python
   def execute(proposal, fail_silently=False) -> bool:
       if fail_silently:            # 模拟"返回成功但后端没落盘"
           return True
       SIDE_EFFECTS.append(...)
       return True

   def commit(store, k, fail_silently=False):
       ...
       execute(p, fail_silently)
       rec["status"] = "committed"
       store.save(k, rec)
       if verify(p):
           rec["status"] = "verified"
       else:
           rec["status"] = "verify_failed"
           print(f"  [ALERT] verify failed for {k}; running rollback: {rec['rollback']}")
           run_rollback(rec)          # 按记录中的回滚方案执行补偿动作
       store.save(k, rec)
   ```

   要点：验证失败是一个**显式状态**，触发告警和预先写好的回滚方案；回滚本身也应走幂等与验证。注意有些动作没有真正的回滚（Demo 1 的邮件："no in-band rollback; follow up with correction email"），这类动作的 HITL 要更严格。

### Q13 — 参考回答要点

- **定义**：把 agent 的有后果动作拆成四步——**Propose**（带元数据和幂等键持久化）、**Surface**（结构化展示给人）、**Commit**（得到肯定批准后才执行）、**Verify**（执行后回读确认）。
- **与弹窗的本质区别**：
  1. **持久化**：提案存在耐久存储里，审批可以两天后到达，进程重启、部署都不影响（弹窗随进程消失）；
  2. **结构化元数据**：审阅人看到意图、来源、权限、爆炸半径、回滚方案，而不只是"同意吗？"；
  3. **幂等**：一次批准只对应一次副作用，重试不会重复执行；
  4. **肯定提交 + 强制清单**：对抗橡皮图章；
  5. **执行后验证**：确认副作用真的发生。
- **框架对应**：LangGraph `interrupt()` + PostgreSQL checkpoint、Microsoft Agent Framework `RequestInfoEvent`、Cloudflare `waitForApproval()`——讲义："The API names differ; the shape does not."
- 加分点：提到 EU AI Act 第 14 条对"有效人类监督"的要求排除了橡皮图章模式。

### Q14 — 参考回答要点

- **设计原则**：
  - 由提案**内容**确定性派生（规范化后哈希，如 `sort_keys=True`），重提/重试得到同一个键；
  - 包含会话/租户作用域（`thread_id`），避免跨会话碰撞；
  - 包含**业务区分量**，让合法的重复动作不被吞掉（Q8、Q11）；
  - **绝不**包含挂钟时间或随机数。
- **为什么只标 `committed` 不够**：副作用发生在外部系统，状态记录在自己的存储里，两者之间没有原子性——在"执行完成"与"写回状态"之间崩溃，重试会重复执行（Q9）。分布式系统里这就是"至少一次投递"。
- **怎么做到效果上的恰好一次**：
  1. 幂等键一路传到执行端，由下游 API 去重（Stripe/AWS 风格的 `Idempotency-Key`）；
  2. 下游不支持时，自己维护"已处理键"表，并与业务写入放在**同一事务**中；
  3. 不可去重的外部动作，执行前先查询"是否已经做过"；
  4. 配合执行后验证，发现不一致时告警。
- 常见误区："我们有幂等键"但键只存在自己的数据库里，从未传给执行端。

### Q15 — 参考回答要点

- **为什么发生**：审批频率高、绝大多数提案都没问题，审阅人形成"点同意"的习惯；界面上 Approve 是阻力最小的路径；提案信息不结构化，审阅成本高；出了问题责任模糊。讲义："approvals predict little, and when the agent goes wrong, the audit trail shows a long history of approvals the user cannot recall."
- **清单之外的手段**：
  - **分级**：只对真正有后果的动作要求 HITL（讲义的三级），减少审批疲劳；
  - **按动作类别定制问题**（skill 文件），而不是每次都问同样的三个问题；
  - **结构化展示风险**：突出爆炸半径、权限、不可逆性、数据来源是否不可信（与第 11 节读写边界结合）；
  - **记录审阅人身份与 `ack_mode`**，事后可以审计批准质量；
  - **抽查与反馈**：定期复盘被批准后出问题的案例；
  - **高风险动作双人审批**或冷静期；
  - 对来自不可信内容的提案加醒目标识。
- 讲义原话："Not bureaucracy for its own sake — a forcing function." 目标是"make a structured review the path of least resistance"。

### Q16 — 参考回答要点

- **提案元数据**：
  - intent：为什么发这条（关联的产品发布/活动）；
  - lineage：文案来源（哪份发布说明、哪个网页、是否含有从外部抓取的内容）；
  - permissions：使用哪个账号、哪个 API 作用域（发帖、上传媒体）；
  - blast radius：公开账号、粉丝数量级、可能的品牌/法律风险，转发后不可收回；
  - rollback：可以删帖，但截图和转发无法撤回——等同"无真正回滚"；
  - 幂等键：`hash(账号, 规范化文案, 媒体哈希, 活动 ID)`。
- **三个质询问题**（以及为什么）：
  1. "我已逐字阅读最终文案和所有链接/图片，确认没有未经核实的事实、内部信息或不当内容"——公开内容最大的风险是**内容本身**错误或泄密；
  2. "我已确认文案来源可信，没有来自外部页面或用户输入的未审核文字"——防止第 11 节的注入通过 agent 发到公司账号上；
  3. "我知道这条帖子发出后无法真正撤回，并确认发帖时机与账号无误"——对抗"可以删帖"的错觉，强调不可逆性。
- **验证与回滚**：发帖后通过 API 回读该帖子，比对文案、媒体、账号；不一致立即告警并删帖，同时通知社媒负责人准备更正声明。
- 加分点：在 EU 高风险场景外也建议双人审批；保留审批记录以备合规审查。

### Q17 — 参考回答要点

- **可以只用同步弹窗的情况**：动作**可逆且影响范围小**，审批在用户当前会话中立即完成，进程中断后重新发起也无害。例如：编码 agent 在用户正盯着的本地开发分支上修改一个文件（有 git 可回退），或在个人沙箱环境里运行一个只影响沙箱的命令。讲义分级中属于"Reversible actions (sometimes HITL)"。
- **为什么不需要持久化**：审批不需要跨越进程生命周期；如果进程崩溃、弹窗消失，最坏结果只是动作没执行，用户重新发起即可；没有"批准后重复执行造成损失"的风险。
- **你在接受的风险**：
  - 橡皮图章风险：同步弹窗最容易被习惯性点同意；
  - 审计弱：没有持久化记录，事后难以追溯谁批准了什么；
  - 重复执行风险：没有幂等键，重试时可能重复（对可逆的本地编辑影响小）；
  - 归类错误风险：如果把一个其实不可逆的动作（如 `git push --force` 到共享分支）误归为"可逆"，这些风险就会变成真实损失。
- 常见误区：为了省事把对外通信、生产变更也放进同步弹窗——这正是讲义批评的 2023 式 HITL。

---

## 六、关联知识点

### 前置知识
- [阶段 15 · 12 长时间运行的后台 Agents：Durable Execution](../../12-durable-execution/docs/zh.md)：持久化的"等待人工"状态与幂等键的基础。
- [阶段 15 · 14 紧急停止开关、Circuit Breakers 与金丝雀 Tokens](../../14-kill-switches-canaries/docs/zh.md)：检测器触发后"上报给人"的落地方式。
- [阶段 15 · 11 浏览器 Agents 与长程网页任务](../../11-browser-agents/docs/zh.md)：读写边界要求由不可信内容引发的写走人工批准。
- [阶段 15 · 10 自主 Agents 的权限模式](../../10-claude-code-permission-modes/docs/zh.md)：哪些动作需要询问用户，取决于权限模式。
- [阶段 14 · 13 有状态图 Orchestration：Durable Execution 与 Checkpoints](../../../14-agent-engineering/13-langgraph-stateful-graphs/docs/zh.md)：LangGraph `interrupt()` 与 checkpointer 的实际用法。

### 本节被哪些后续内容用到
- [阶段 15 · 16 Checkpoints（检查点）与 Rollback（回滚）](../../16-checkpoints-rollback/docs/zh.md)：提案中的 rollback 方案如何落地。
- [阶段 15 · 17 Constitutional AI 与规则覆盖](../../17-constitutional-ai/docs/zh.md)：人工监督之外的硬性规则层。
- [阶段 17 · 26 合规：SOC 2、HIPAA、GDPR、PCI-DSS、EU AI Act、ISO 42001](../../../17-infrastructure-and-production/26-compliance-frameworks/docs/zh.md)：EU AI Act 第 14 条等合规要求。
- [阶段 17 · 25 安全：密钥、API 密钥轮换、Audit Logs 与 Guardrails](../../../17-infrastructure-and-production/25-security-secrets-audit/docs/zh.md)：审批记录作为审计日志的一部分。
- [阶段 18 · 11 可扩展监督与弱到强泛化](../../../18-ethics-safety-alignment/11-scalable-oversight-weak-to-strong/docs/zh.md)：当人难以审阅 agent 的提案时如何监督。

### 延伸关键词
`propose-then-commit` · `two-phase approval` · `idempotency key` · `Idempotency-Key header` · `outbox pattern` · `state machine` · `interrupt()` · `RequestInfoEvent` · `waitForApproval()` · `rubber-stamp` · `challenge-and-response` · `blast radius` · `data lineage` · `post-commit verify` · `EU AI Act Article 14`
