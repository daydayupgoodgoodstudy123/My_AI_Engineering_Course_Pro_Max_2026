# 代码讲解 · main.py

> **所属小节**：阶段 15 · 自主系统 · 第 15 节 Human-in-the-Loop：先提出方案，再 Commit ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`hashlib`、`json`、`os`、`tempfile`、`dataclasses`）；运行时会在系统临时目录下创建 `proposals.json`，且不会自动删除

---

## 1. 这份代码在考察什么

这是一个**propose-then-commit（先提出、再提交）人工审批状态机**，用 JSON 文件当持久化存储，复刻讲义所说的 2026 年 HITL 共识形状（LangGraph `interrupt()`、Microsoft Agent Framework `RequestInfoEvent`、Cloudflare `waitForApproval()` 名字不同、形状相同）：

1. **propose**：agent 把拟执行的动作连同元数据（意图 intent、数据来源 lineage、爆炸半径 blast radius、回滚方案 rollback）持久化，键是由内容派生的**幂等键（idempotency key）**；
2. **surface**：把这些元数据展示给审阅人；
3. **commit**：只有得到**肯定的批准**才执行；重复提交不会重复执行；
4. **verify**：执行后回读目标资源，确认副作用真的发生了。

三个演示分别对应讲义的三个论点：完整的 challenge-and-response（质询-应答清单）审批流程；批准后重试不会重复执行；"橡皮图章（rubber-stamp）"式一键批准与清单式审批的对比。

同时，这份玩具实现也暴露了几个值得深究的缺口（第 3 节详述，均已实测）：

- 幂等只靠存储里的 `status` 字段，**执行与写回状态之间崩溃**时重试会重复执行，执行端并不认幂等键；
- 两个审批函数**不检查当前状态**，对已经 `committed` 的提案再批准一次，`commit` 就会再执行一次；
- 提案缺少讲义要求的 **permissions touched（触及的权限）** 字段；
- `verify` 的结果只打印、不处理，验证失败时既不告警也不回滚。

> 一句话：**把"agent 问、用户点同意"升级为"持久化提案 + 结构化审阅 + 肯定提交 + 执行后验证"；同时要明白，幂等和状态机的正确性必须端到端成立，光在一处加检查是不够的。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Proposal` | dataclass | 7 个字段 + `key()`：对 `(thread_id, action, payload)` 做 SHA-256，取前 16 位十六进制 | 提案 + 幂等键 |
| `Store` | dataclass | JSON 文件存 `{key: record}`；`all()` 读全部、`save()` 写一条 | 持久化存储 |
| `SIDE_EFFECTS` | 模块级列表 | 假装是后端，记录真正发生的副作用 | 被操作的外部系统 |
| `execute(p)` | 函数 | 往 `SIDE_EFFECTS` 追加一条 | 执行副作用 |
| `verify(p)` | 函数 | 检查该副作用是否在 `SIDE_EFFECTS` 中 | 执行后验证 |
| `propose(store, p)` | 函数 | 键已存在则直接返回（幂等）；否则写入 `status="waiting"` 的记录 | Propose |
| `surface(store, k)` | 函数 | 打印 intent / lineage / blast_radius / rollback | Surface |
| `rubber_stamp_approve` | 函数 | 无条件把状态改为 `approved`，标记 `ack_mode="rubber_stamp"` | 橡皮图章审批 |
| `checklist_approve` | 函数 | 三个布尔回答全为真才批准，标记 `ack_mode="challenge_response"` | 质询-应答清单 |
| `commit(store, k)` | 函数 | 已提交 → 不重复执行；非 `approved` → 拒绝；否则执行、写回 `committed`、打印验证结果 | Commit + Verify |
| `main()` | 函数 | 三个演示 | 演示驱动 |

数据流：`Proposal` → `propose`（计算键、写 `waiting`）→ `surface`（展示）→ `*_approve`（改为 `approved`）→ `commit`（读记录 → 重建 `Proposal` → `execute` → 写 `committed` → `verify`）。

---

## 3. 逐段精讲

### 3.1 `Proposal` 与幂等键

```python
@dataclass
class Proposal:
    thread_id: str
    action: str
    payload: dict
    intent: str
    lineage: str
    blast_radius: str
    rollback: str

    def key(self) -> str:
        sig = json.dumps({"t": self.thread_id, "a": self.action,
                          "p": self.payload}, sort_keys=True)
        return hashlib.sha256(sig.encode()).hexdigest()[:16]
```

- 讲义要求提案包含：intent、data lineage、permissions touched、blast radius、rollback plan、idempotency key。代码有其中 5 项，**缺少 permissions touched**（这个提案会用到哪些权限范围、文件、端点）。skill 文件要求"all five required"，缺字段是 blocker。讲义练习 3 也是让你找出并补上一个缺失的元数据字段。
- **幂等键只由 `(thread_id, action, payload)` 派生**（讲义 Use It："hash of (thread_id, action_signature)"）。`json.dumps(..., sort_keys=True)` 保证字典键顺序不同时序列化结果相同——同样内容的提案永远得到同一个键。
- `hexdigest()[:16]`：取 SHA-256 的前 16 个十六进制字符（64 位）。演示规模下足够，碰撞概率可忽略。
- 设计含义（已实测）：
  - 键**不包含** intent、lineage 等元数据。同一动作换一个理由再提一次，会得到**同一个键**、命中旧记录；
  - 键**不包含时间**。这正是讲义与 skill 文件强调的："Keys that include wall-clock time are not idempotency keys; they are logging timestamps." 但代价是：同一会话里**合法地**再做一次完全相同的动作（比如下周再发同一封提醒邮件），会被当成重复提案，返回 `status=committed` 的旧记录，**这次合法的执行永远不会发生**。真实系统常在键里加入业务层面的区分量（如"第几周的提醒"），而不是时间戳。

### 3.2 `Store`：JSON 文件当持久化存储

```python
@dataclass
class Store:
    path: str

    def __post_init__(self) -> None:
        if not os.path.exists(self.path):
            with open(self.path, "w") as f:
                json.dump({}, f)

    def all(self) -> dict:
        with open(self.path) as f:
            return json.load(f)

    def save(self, key: str, record: dict) -> None:
        data = self.all()
        data[key] = record
        with open(self.path, "w") as f:
            json.dump(data, f)
```

- 与第 12 节的 `EventLog` 同一套路：每次读写都走文件，进程重启后状态还在——讲义 "approvals outlast processes"。
- 存储结构是 `{幂等键: 记录}` 的字典，按键覆盖写入。
- ⚠️ 同样的局限：整文件重写、非原子、无并发控制。两个审阅人同时批准、或 agent 与审阅人同时写，可能互相覆盖。生产中用 PostgreSQL 的行级锁或"比较并交换（compare-and-swap）"式条件更新，例如 `UPDATE ... SET status='committed' WHERE key=? AND status='approved'`。

### 3.3 `execute` 与 `verify`：假后端

```python
SIDE_EFFECTS: list[str] = []

def execute(proposal: Proposal) -> bool:
    SIDE_EFFECTS.append(f"{proposal.action}:{json.dumps(proposal.payload)}")
    return True

def verify(proposal: Proposal) -> bool:
    needle = f"{proposal.action}:{json.dumps(proposal.payload)}"
    return needle in SIDE_EFFECTS
```

- `SIDE_EFFECTS` 模拟外部系统（邮件服务、数据库）。每次 `execute` 都追加一条，**不看幂等键**——也就是说，后端本身不去重。
- `verify` 回读"后端"，检查副作用是否存在。讲义："'The commit ran' is not the same as 'the side effect happened.'" 类比数据库的 `RETURNING`、AWS 的 `PutObject` 后 `GetObject`。
- ⚠️ 在本代码中 `execute` 永远成功、永远追加，所以 `verify` 永远为 `True`，演示不出验证失败的情形；而且 `verify` 只检查"某处存在同样的字符串"，如果另一个线程之前做过同样的动作，也会误判为成功。真实的验证应读回**本次操作**的结果（如带幂等键或返回的资源 ID 去查）。

### 3.4 `propose` 与 `surface`

```python
def propose(store: Store, p: Proposal) -> str:
    k = p.key()
    existing = store.all().get(k)
    if existing:
        print(f"  [propose] idempotent: record {k} already exists "
              f"(status={existing['status']})")
        return k
    record = {"status": "waiting", **vars(p)}
    store.save(k, record)
    ...
```

- `store.all().get(k)`：键不存在时返回 `None`，不会抛 `KeyError`。
- **重复提交返回同一条记录**：这是讲义 "resubmission returns the same record" 的实现。agent 因超时重发提案，不会产生两条待审记录。
- `{"status": "waiting", **vars(p)}`：`vars(p)` 返回 dataclass 实例的属性字典，`**` 把它展开合并进新字典。结果记录包含 `status` + 7 个提案字段。
- `surface` 依次打印四个元数据字段。代码注释提到用 `name` 而不是 `field` 作循环变量，是为了不遮蔽从 `dataclasses` 导入的 `field`（Ruff 规则 F402）。
- 讲义要求审阅人是"a person (not the agent reviewing itself)"。代码没有记录审阅人身份——这在审计和 EU AI Act 第 14 条的"有效人类监督"语境下是一个缺口。

### 3.5 两种审批

```python
def rubber_stamp_approve(store: Store, k: str) -> bool:
    r = store.all()
    rec = r[k]
    rec["status"] = "approved"
    rec["ack_mode"] = "rubber_stamp"
    store.save(k, rec)
    ...

def checklist_approve(store: Store, k: str,
                      understood: bool, verified: bool,
                      rollback_ready: bool) -> bool:
    if not (understood and verified and rollback_ready):
        print("  [approve:checklist] REJECTED (incomplete answers)")
        return False
    ...
    rec["status"] = "approved"
    rec["ack_mode"] = "challenge_response"
```

- 清单的三个问题对应讲义："Do you understand what resource this touches?""Have you verified the blast radius is acceptable?""Do you have a rollback plan if this fails?" 任何一项为假就不批准——讲义称之为 forcing function（强制函数）："The reviewer who cannot tick the boxes either asks for clarification (escalation) or declines (safe default)."
- `ack_mode` 记录批准方式，事后审计可以区分"一键通过"和"走过清单"的批准。
- ⚠️ **清单被拒绝时状态不变**：仍是 `waiting`，没有写成 `rejected`，也没有记录拒绝理由。所以 Demo 3 里 `commit` 打印的是 `status=waiting`。被清单拒绝的提案之后仍然可以被 `rubber_stamp_approve` 一键通过。
- ⚠️ **两个审批函数都不检查当前状态**。实测：一个已经 `committed` 的提案，再调用一次 `rubber_stamp_approve`，状态被改回 `approved`，再调用 `commit` 就**又执行了一次**（副作用变成 2 条）。正确的状态机只允许 `waiting → approved / rejected`，`committed` 是终态。
- ⚠️ 清单的回答只是调用方传入的三个布尔值，代码无法区分"人认真回答了"和"程序自动填了 True"。讲义的强制函数要在 **UI 层**生效（未勾选时 Approve 按钮不可点），并且问题要针对具体动作类别定制（skill 文件："Confirm the checklist is tailored to the specific action class, not generic"）。

### 3.6 `commit`：状态检查 + 执行 + 验证

```python
def commit(store: Store, k: str) -> bool:
    data = store.all()
    rec = data[k]
    if rec["status"] == "committed":
        print(f"  [commit] idempotent: {k} already committed, no re-execute")
        return True
    if rec["status"] != "approved":
        print(f"  [commit] refusing: {k} status={rec['status']}")
        return False
    p = Proposal(thread_id=rec["thread_id"], ...)
    execute(p)
    rec["status"] = "committed"
    store.save(k, rec)
    print(f"  [commit] executed; verify={verify(p)}")
    return True
```

- 三分支：已提交 → 返回 True 但不执行（这就是 Demo 2 的"幂等"）；未批准 → 拒绝；已批准 → 执行。
- 执行时**从存储里重建** `Proposal`，而不是用调用方手里的对象——保证执行的是被审阅过的那份内容。
- ⚠️ **幂等的漏洞在 `execute(p)` 与 `store.save(k, rec)` 之间**：如果进程在执行副作用之后、把状态写回 `committed` 之前崩溃，存储里状态仍是 `approved`，重试时会再执行一次（实测：副作用 2 条）。这正是讲义举的转账例子——"Network blips. Workflow retries. The user has approved once but the transfer executes twice."——而本代码并没有防住它。讲义说"The idempotency key ties the approval to a single, unique side effect; the second execution is a no-op"，要做到这一点，**幂等键必须传给执行端**，由后端（或与副作用同一事务的去重表）判断"这个键已处理过"，就像 Stripe、AWS API 的做法。
- ⚠️ `verify(p)` 的结果只出现在 print 里。讲义："If the verify step fails, the system is in a known bad state and alerting engages." 代码既不告警、不回滚，也不把状态标成 `verify_failed`。讲义练习 2 要求补上自动回滚。

### 3.7 `main`：三个演示

- **Demo 1**：`propose → surface → checklist_approve(全部 True) → commit`，执行并验证成功。
- **Demo 2**：对同一个键再 `commit` 两次，都走"already committed"分支，副作用数保持 1。注意：这只演示了"**提交完全成功之后**的重试"，并没有演示讲义所说的"transient failure（瞬时故障）之后的重试"——后者才是幂等键真正要防的场景（见 3.6）。
- **Demo 3**：
  - `db.update`（单行、1 小时内可从备份恢复）被橡皮图章批准并执行；
  - `db.drop_table`（42 万行、24 小时内不可恢复）走清单，审阅人无法勾选"回滚就绪"，被拒绝；随后故意调用 `commit`，演示它因 `status=waiting` 而拒绝执行（代码注释说明这是有意为之）。
  - 这两个提案不是同一个动作，所以严格说不是"橡皮图章 vs 清单"的对照实验，而是"低风险动作走快速审批、高风险动作走清单"的示例——这恰好与讲义 "What counts as consequential" 的分级思想一致。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 键 = hash(thread_id, action, payload) | 由内容派生，重提返回同一记录；不含时间 | 同会话合法重复动作被吞掉；需要加入业务区分量 |
| 幂等靠存储里的 `status` | 实现简单 | 执行与写回之间崩溃会重复执行；应把键传给后端去重，或用 outbox / 同事务去重表 |
| JSON 文件存储 | 零依赖、可查看 | 非原子、无并发控制；生产用 PostgreSQL 等，状态转换用条件更新 |
| 审批函数不校验状态 | 代码短 | 已提交的提案可被再次批准并重复执行；应实现严格状态机，`committed`/`rejected` 为终态 |
| 清单拒绝不写 `rejected` | 演示 commit 拒绝 `waiting` | 被拒提案仍可被一键批准；应记录拒绝与理由 |
| 清单 = 三个布尔参数 | 表达"强制函数"的概念 | 无法证明是人回答的；UI 层强制 + 记录审阅人身份 + 按动作类别定制问题 |
| 无 permissions 字段 | 省略 | 审阅人看不到"这个动作动用了哪些权限"；讲义与 skill 文件要求必填 |
| verify 只打印 | 演示概念 | 失败时无告警、无回滚；应标记坏状态、告警，并按 rollback 方案处理 |
| `execute` 不接收幂等键 | 假后端 | 后端无法去重；真实 API（如支付）通过请求头接收幂等键 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass` 多字段 | `class Proposal: thread_id: str ...` | 自动生成按字段顺序的 `__init__` |
| dataclass 中定义方法 | `def key(self) -> str:` | 数据类也可以有普通方法 |
| `json.dumps(..., sort_keys=True)` | `key()` 中 | 字典键排序后序列化，保证同内容得到同字符串 |
| `hashlib.sha256(...).hexdigest()` | `hashlib.sha256(sig.encode()).hexdigest()[:16]` | 先把字符串编码成字节，再求哈希，取十六进制字符串前 16 位 |
| `__post_init__` | `Store` 中 | dataclass 构造后自动调用，用于初始化文件 |
| `with open(...)` | `Store.all` / `save` | 自动关闭文件 |
| 模块级变量注解 | `SIDE_EFFECTS: list[str] = []` | 给全局变量标注类型 |
| `dict.get` | `store.all().get(k)` | 键不存在返回 `None` |
| 字典解包合并 | `{"status": "waiting", **vars(p)}` | `vars()` 取对象属性字典，`**` 展开进新字典 |
| 遍历元组常量 | `for name in ("intent", "lineage", ...)` | 按固定顺序访问字段 |
| f-string 对齐 | `{name:<14}` | 左对齐、宽 14 |
| 布尔组合 | `if not (understood and verified and rollback_ready):` | 三者全真才通过 |
| 关键字参数调用 | `checklist_approve(store, k, understood=True, verified=True, rollback_ready=False)` | 布尔参数用关键字写更易读 |
| 多行函数签名 | `def checklist_approve(store, k,\n understood, ...)` | 括号内可以自由换行 |
| 多行构造对象 | `Proposal(thread_id=rec["thread_id"], action=rec["action"], ...)` | 从字典重建对象 |
| 相邻 f-string 拼接 | `print(f"..." f"...")` | 括号内自动拼接 |
| `tempfile.mkdtemp()` | `main` 中 | 创建临时目录（需自行清理） |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()` |

---

## 6. 运行结果解读

实际运行（`cd code && python3 main.py`，输出确定，键值由内容哈希决定，每次相同）：

```text
Demo 1: clean approval flow (challenge-and-response)
  [propose] record 9a9006579378a746 stored, waiting for review
  [surface] proposal 9a9006579378a746
    intent         Announce the v1.2 release to the team list
    lineage        Release notes page /releases/1.2
    blast_radius   37 recipients; wrong send = external embarrassment
    rollback       no in-band rollback; follow up with correction email
  [approve:checklist] APPROVED (all three checks)
  [commit] executed; verify=True

Demo 2: retry after approval; idempotency catches re-exec
  [commit] idempotent: 9a9006579378a746 already committed, no re-execute
  [commit] idempotent: 9a9006579378a746 already committed, no re-execute
  total side effects after 2 retries: 1 (was 1) -> idempotent

Demo 3: rubber-stamp UI vs challenge-and-response
  [propose] record ba777e7c9197a6c2 stored, waiting for review
  [approve:rubber-stamp] clicked Approve (no checklist)
  [commit] executed; verify=True
  [propose] record 7c4870bc65bafbe9 stored, waiting for review
  [approve:checklist] REJECTED (incomplete answers)
  [commit] refusing: 7c4870bc65bafbe9 status=waiting
```

逐项解读：

- **Demo 1**：四个阶段完整走过一遍。注意 surface 只展示了 4 个元数据字段，没有 permissions。邮件的 rollback 写的是"no in-band rollback"——发出去的邮件收不回，这类动作讲义归为"Consequential actions (always HITL)"中的"outbound communication"。
- **Demo 2**：两次重试都命中 `committed` 分支，副作用数保持 1。成立的前提是第一次 `commit` 已经完整写回了 `committed`。
- **Demo 3**：第一个提案没有经过任何清单就被执行了；第二个提案因回滚不就绪被拒绝，`commit` 也拒绝执行，状态停留在 `waiting`。
- **补充实验**（已实际运行，见测验 Q9–Q11）：

  | 场景 | 结果 |
  |------|------|
  | 已 `committed` 的提案再 `rubber_stamp_approve` 后 `commit` | 再执行一次，副作用 2 条 |
  | 在 `execute` 之后、写回 `committed` 之前模拟崩溃，然后重试 `commit` | 再执行一次，副作用 2 条 |
  | 同一会话中合法地再提一次完全相同的动作 | 返回旧键（`status=committed`），新动作不执行，副作用 0 条 |
  | 把幂等键改为"内容哈希 + 时间戳"，按 Demo 2 的方式用同一个 `k` 重试 `commit` | 仍然不会重复执行（副作用 1 条），因为重试没有重新计算键 |
  | 时间戳键 + 重试路径是"重新 propose → 批准 → commit" | 得到新键、再执行一次，副作用 2 条 |

  最后两行说明：讲义练习 1 的"把时间戳加进键就会重复执行"，只有在**重试会重新走 propose**（例如 agent 崩溃后从头重新生成提案）时才会发生；在本代码 Demo 2 的写法下复现不出来。

---

## 7. 动手改一改

1. **（讲义练习 1，修正版）**：把 `key()` 改为在哈希后拼接 `time.time_ns()`，并把 Demo 2 改成"agent 重启后重新 `propose` 同一个动作，再批准、再提交"，观察副作用变为 2 条；再恢复原来的键，确认重新 propose 时命中旧记录。
2. **（讲义练习 2）自动回滚**：给 `execute` 加一个参数让它"假装成功但没写入"，使 `verify` 返回 False；在 `commit` 中检测到验证失败时把状态写成 `verify_failed`、打印告警，并执行记录中的 rollback（例如从 `SIDE_EFFECTS` 中移除或追加一条补偿动作）。
3. **（讲义练习 3）补全元数据**：给 `Proposal` 加 `permissions: list[str]`（如 `["smtp:send", "list:team@example.com"]`），在 `surface` 中展示；思考它防的是什么——审阅人能看到"这个动作动用了超出任务所需的权限"。
4. **严格状态机**：定义允许的转换 `waiting → approved | rejected`、`approved → committed | verify_failed`，其他转换一律抛异常；清单拒绝时写 `rejected` 和理由。验证"已提交后再批准"会被拒绝。
5. **端到端幂等**：让 `execute(p, idem_key)` 维护一个"已处理键"集合，重复的键直接返回第一次的结果；再用"执行后、写回前崩溃"的场景验证副作用只有 1 条。
6. **（讲义练习 4）定制清单**：为"发布到公开 Twitter 账号"设计三个问题，并让 `checklist_approve` 根据 `action` 选择不同的问题集合。

---

## 8. 常见坑

- **以为状态字段就是幂等**：只在自己的存储里标记 `committed` 不够，执行与标记之间的崩溃会导致重复副作用；幂等键要一直传到执行端。
- **幂等键里放时间戳或随机数**：每次重试键都不同，等于没有幂等（skill 文件 hard reject）。
- **幂等键粒度过粗**：只用 `(thread, action, payload)` 会吞掉合法的重复动作；要按业务语义加区分量。
- **审批不校验当前状态**：已提交、已拒绝的提案被再次批准，导致重复执行或绕过拒绝。
- **"工具返回 200"就当成功**：skill 文件："'The tool returned 200' is not verify." 要回读目标资源。
- **验证失败不处理**：只打印 `verify=False` 等于没验证；必须告警并进入已知的处理流程。
- **审阅人是 agent 自己**：讲义与 skill 文件都明确要求审阅人是人。
- **通用清单**：对所有动作问同样三个问题，很快又会变成橡皮图章；问题要针对动作类别。
- **所有动作都走 HITL**：讲义分级——读操作从不需要 HITL，可逆动作视情况，不可逆/金融/对外通信/生产数据库/破坏性文件操作总是需要。全部都审批只会制造审批疲劳，反过来加剧橡皮图章。
- **把预算当成 HITL**：skill 文件："Budgets cap cost, not correctness."
