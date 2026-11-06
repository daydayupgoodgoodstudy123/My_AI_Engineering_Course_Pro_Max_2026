# 代码讲解 · main.py

> **所属小节**：阶段 15 · 自主系统 · 第 16 节 Checkpoints（检查点）与 Rollback（回滚） ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`hashlib`、`json`、`os`、`tempfile`、`dataclasses`）

---

## 1. 这份代码在考察什么

这份代码用一个"从账户 A 向 B 转账"的小工作流，把讲义的"四件套"做成可运行的状态机：

1. **Checkpoint**：每次状态变化都写进一个 JSON 文件，并且用"临时文件 + fsync + 原子重命名"保证崩溃时文件不会写坏一半。
2. **Idempotency key**：由交易 id 哈希得到；同一个 key 一旦进入终态，重试直接返回原结果。
3. **Precondition check**：在执行副作用前（即 commit 时）检查转账后余额是否仍 ≥ `min_balance`。
4. **Post-action verify + rollback**：执行后回读数据库确认副作用落地，失败就回滚。

驱动程序跑四个场景：干净运行、执行后崩溃再重试、precondition 失败、verify 失败触发 rollback。

> 一句话：**用不到 200 行代码演示"一个已批准的动作在崩溃、重试、状态漂移、验证失败时如何保持正确"**——同时也暴露了恢复路径上缺 verify 的缺口，这正是讲义 double-execute 一节要讨论的地方。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `DB` | 全局 dict | 模拟目标系统（余额 + 最后一笔交易 id） | 外部副作用所在的系统 |
| `persist_transfer` | 函数 | 执行转账：扣 A、加 B、记录 txid | 有后果的动作（side effect） |
| `rollback_transfer` | 函数 | 加回、减回余额并还原 `last_transfer_id` | rollback（注释称 compensating） |
| `Checkpoint` | dataclass | JSON 文件存储；`load` 读、`save` 原子写 | 持久化 checkpoint |
| `key` | 函数 | `sha256(txid)` 取前 12 个十六进制字符 | idempotency key |
| `run_transfer` | 函数 | 终态短路 → precondition → 写意图 → 执行 → verify → rollback / 标记 verified | 完整的 commit 状态机 |
| `main` | 函数 | 依次跑 4 个场景并打印 | 演示驱动 |

数据流：`main` 建临时目录 → 每个场景新建一个 `Checkpoint` 文件 → `run_transfer` 读 checkpoint、读写全局 `DB` → 打印结果与 `DB`。

状态机（checkpoint 中 `status` 字段）：

```text
new ──precondition 失败──▶ aborted-precondition（终态）
 │
 └─写意图──▶ committed ──执行──▶ verify 通过 ──▶ verified（终态）
                         │        verify 失败 ──▶ rollback ──▶ rolled-back（终态）
                         └─ 崩溃：停留在 committed（重试时也按终态短路）
```

---

## 3. 逐段精讲

### 3.1 模拟数据库与两个副作用函数

```python
DB = {"balance_A": 1500, "balance_B": 200, "last_transfer_id": None}

def persist_transfer(txid: str, from_acct: str, to_acct: str, amount: int) -> None:
    DB[f"balance_{from_acct}"] -= amount
    DB[f"balance_{to_acct}"] += amount
    DB["last_transfer_id"] = txid
```

- `DB` 是模块级全局变量，四个场景**共享**它：场景 1 结束后 A=1400，场景 2 从 1400 开始。所以场景之间不是独立的，读输出时要累计着看。
- `f"balance_{from_acct}"` 用 f-string 拼出键名，`"A"` → `"balance_A"`。
- `last_transfer_id` 是后面 verify 唯一依赖的字段。

```python
def rollback_transfer(txid, from_acct, to_acct, amount, prior_last_transfer_id):
    # Compensating transaction: restore balances and the prior transfer id.
    DB[f"balance_{from_acct}"] += amount
    DB[f"balance_{to_acct}"] -= amount
    DB["last_transfer_id"] = prior_last_transfer_id
```

- 注释称之为 compensating transaction，但按讲义定义它更像 **in-band rollback**：直接把字段改回去，没有生成一笔新的、可审计的冲正交易。
- ⚠️ 没有任何守卫：我们实测在没有对应转账时调用它，A 从 1500 变 1600、B 从 200 变 100。真实系统中 rollback 本身也必须幂等、也要 verify。
- ⚠️ `last_transfer_id = prior` 是直接覆盖，如果中间有其他工作流写入了新的转账 id，会被抹掉。

### 3.2 `Checkpoint`：原子写的 JSON 存储

```python
@dataclass
class Checkpoint:
    path: str

    def __post_init__(self) -> None:
        if not os.path.exists(self.path):
            with open(self.path, "w") as f:
                json.dump({}, f)

    def save(self, k: str, v: dict) -> None:
        data = self.load()
        data[k] = v
        tmp_path = f"{self.path}.tmp"
        with open(tmp_path, "w") as f:
            json.dump(data, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, self.path)
```

- `@dataclass` 自动生成 `__init__(self, path)`；`__post_init__` 在其后执行，保证文件存在且是合法 JSON（`{}`）。
- `save` 是"读—改—写全量"：每次都重写整个文件。
- **原子写三步**：写到兄弟文件 `*.tmp` → `flush()` 把 Python 缓冲推给操作系统、`os.fsync()` 让操作系统落盘 → `os.replace()` 原子替换。崩溃发生在任何一步，原文件要么是旧版本、要么是新版本，不会是半截 JSON。这对 idempotency 至关重要：如果 checkpoint 写坏了，重试就读不到之前的记录。
- ⚠️ 简化之处：没有对目录做 fsync（严格的崩溃一致性还需要）；`.tmp` 文件名固定，多个进程同时写会冲突；读—改—写之间没有锁，并发写会丢更新。生产中用数据库事务（如 PostgreSQL）。
- ⚠️ 讲义说生产实现"persist every transition"，这里的 checkpoint 只记录**当前状态**（同一 key 被覆盖），不是 append-only 的转移历史，所以审计员看不到 `committed → verified` 的过程。

### 3.3 Idempotency key

```python
def key(txid: str) -> str:
    return hashlib.sha256(txid.encode()).hexdigest()[:12]
```

- `txid.encode()` 把字符串转成 bytes（哈希函数只接受 bytes），`hexdigest()` 得到 64 个十六进制字符，取前 12 个（48 bit）。例：`key("tx-001") == "cb23007c9881"`。
- ⚠️ key 只由 txid 决定，与金额、账户无关。实测：同一 txid 先转 100 成功，再用 900 调用，直接返回 `ok` 且什么都没做，也不报警（测验 Q8）。skill 文件要求 key 来自提案内容（第 15 节），生产里还会在命中 key 时比对请求指纹。

### 3.4 `run_transfer` 第一步：终态短路

```python
    k = key(txid)
    record = cp.load().get(k, {"status": "new"})

    terminal_results = {
        "committed": "idempotent-skip",
        "verified": "ok",
        "rolled-back": "verify-fail-rolled-back",
        "aborted-precondition": "aborted-precondition",
    }
    if record["status"] in terminal_results:
        return terminal_results[record["status"]]
```

- `dict.get(k, 默认值)`：没有记录时视为 `new`。
- 四种状态都"短路"：重试同一个 txid 不会重新执行，而是返回当初的结论。这就是 idempotency。
- ⚠️ 关键问题：`committed` 在本代码里是**执行前写的意图**，不是"已确认完成"。把它也当终态，意味着：
  - 崩溃发生在执行之后（场景 2）→ 碰巧正确，只执行一次；
  - 崩溃发生在写意图之后、执行之前 → 重试返回 `idempotent-skip`，但转账**从未发生**（我们用 monkeypatch 实测：余额保持 1500/200）。
  - 讲义的处理是："If the action fires and the status write fails, you know to verify and (if necessary) re-fire"——恢复路径要先 verify。代码注释把这称为 "Subtle durability gap"，但没有实现修复。
- ⚠️ 命名与讲义不一致：讲义的 in-flight 对应代码的 `committed`，讲义的 committed（verify 后）对应代码的 `verified`。

### 3.5 Precondition：在 commit 时检查

```python
    if DB[f"balance_{from_acct}"] - amount < min_balance:
        cp.save(k, {"status": "aborted-precondition", "txid": txid})
        return "aborted-precondition"
```

- 检查的是**此刻**的余额，而不是批准时的快照——这正是讲义"Idempotency plus preconditions"的要求，也是 skill 文件里"precondition 必须在 commit 时评估"的体现。
- 边界：用 `<` 判断，所以转账后余额**恰好等于** `min_balance` 是允许的（实测 1500 转 1300 → A=200，返回 `ok`）。
- `aborted-precondition` 也写进 checkpoint 成为终态：之后余额回升，重试同一个 txid 仍然被拒（测验 Q12）。合理的流程是重新提案、重新审批。

### 3.6 写意图 → 执行 → 模拟崩溃

```python
    prior_last_transfer_id = DB["last_transfer_id"]

    cp.save(k, {"status": "committed", "txid": txid,
                "from_acct": from_acct, "to_acct": to_acct,
                "amount": amount,
                "prior_last_transfer_id": prior_last_transfer_id})
    persist_transfer(txid, from_acct, to_acct, amount)
    if inject_crash_after_execute:
        raise RuntimeError("simulated crash after execute")
```

- 先保存执行前的 `last_transfer_id`，供 rollback 精确还原（"restore exactly (not just invert)"）。
- 意图记录里带上了完整参数，理论上恢复进程可以凭它做 verify 或 rollback——但本代码的重试分支并没有使用这些字段。
- **顺序是"先写状态、再执行"**，即讲义 Key Terms 里的 mark-as-done-first。讲义练习 2 让你把顺序反过来：实测会 double-execute（A 从 1500 变 1300，100 元转了两次，见测验 Q10）。
- `raise RuntimeError(...)` 模拟进程崩溃。注意它只是 Python 异常：全局 `DB` 和已写入的 checkpoint 都还在，比真实崩溃"温和"。

### 3.7 Post-action verify 与 rollback

```python
    if inject_verify_fail or DB["last_transfer_id"] != txid:
        rollback_transfer(txid, from_acct, to_acct, amount, prior_last_transfer_id)
        cp.save(k, {"status": "rolled-back", "txid": txid})
        return "verify-fail-rolled-back"

    cp.save(k, {"status": "verified", "txid": txid})
    return "ok"
```

- verify 的方式是**回读目标系统**（`DB["last_transfer_id"]`），而不是相信 `persist_transfer` 的返回值——方向正确。
- `inject_verify_fail=True` 时，转账其实已经成功，只是人为判定失败，用来演示 rollback 路径。
- ⚠️ verify 只看一个字段：既不检查余额变化量，也不能区分"别的转账覆盖了 last_transfer_id"与"本次没落地"。生产中应查以 txid 为键的流水记录，并核对金额。
- ⚠️ rollback 之后没有再 verify，也没有告警；讲义要求 "Failed verifications are alerted on, not silently logged"。
- ⚠️ 写 `rolled-back` 状态在 rollback 之后：若在两者之间崩溃，重试看到的是 `committed`，返回 `idempotent-skip`，而真实状态是"已回滚"——又一个状态与现实不符的窗口。

### 3.8 `main`：四个场景

```python
    tmp = tempfile.mkdtemp()
    cp = Checkpoint(os.path.join(tmp, "cp1.json"))
    out = run_transfer(cp, "tx-001", "A", "B", 100, min_balance=200)
    ...
    try:
        run_transfer(cp, "tx-002", "A", "B", 100, min_balance=200,
                     inject_crash_after_execute=True)
    except RuntimeError as e:
        print(f"  crash: {e}")
    out = run_transfer(cp, "tx-002", "A", "B", 100, min_balance=200)
    ...
    balances_before = dict(DB)
    out = run_transfer(cp, "tx-004", ..., inject_verify_fail=True)
    balances_after = dict(DB)
    print(f"... balances_before_after_equal={balances_before == balances_after}")
```

- `tempfile.mkdtemp()` 创建一个临时目录，每个场景一个独立 checkpoint 文件。⚠️ 运行结束后目录不会被删除（会在 `/tmp` 留下 `tmpXXXX/cp*.json`）；这也说明它只是演示——临时目录恰恰是 skill 文件里"部署后会丢失"的那类后端。
- `dict(DB)` 做浅拷贝快照，`==` 比较两个 dict 的全部键值，用来证明 rollback 完全恢复了状态（包括 `last_transfer_id`）。
- 场景 2 的"崩溃"与"重试"在同一进程中进行，没有真正的 lease、没有第二个 worker。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 全局 dict 当数据库 | 演示简单，副作用一目了然 | 场景之间互相影响；真实目标系统有自己的事务与并发 |
| JSON 文件 + 原子重命名 | 用标准库展示"崩溃不写坏 checkpoint" | 无锁、无目录 fsync、固定 `.tmp` 名；生产用 PostgreSQL 等事务存储 |
| 只存当前状态 | 代码短 | 不是 append-only 历史，审计看不到转移过程；讲义要求每次转移都持久化 |
| key = sha256(txid) 前 12 位 | 稳定、可复现 | 不含参数指纹，同 key 不同参数静默放过；生产应来自提案内容并比对 |
| 先写意图再执行 | 防止"做了没记"导致的 double-execute | 引入"记了没做"缺口；需要恢复路径 verify + 目标端按 key 去重 |
| `committed` 也作为终态短路 | 保证崩溃后不重复执行 | 恢复时不 verify，可能把未发生的副作用报告为完成 |
| precondition 用此刻余额 | 体现 commit 时检查 | `aborted-precondition` 永久终态，需重新提案 |
| verify 只比 `last_transfer_id` | 一行表达"回读目标状态" | 易误判；应查以 txid 为键的流水并核对金额 |
| rollback 直接改回字段 | 精确还原、易验证 | 不幂等、可能覆盖并发写、无告警；生产用 SAGA 冲正交易 + out-of-band 兜底 |
| 用 `raise` 模拟崩溃 | 单进程即可演示 | 内存状态不会丢，比真实崩溃温和；演练应 kill 进程 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 推迟注解求值，让 `str \| None` 这类写法在较老的 Python 上也不报错 |
| 类型注解 | `def key(txid: str) -> str`、`prior_last_transfer_id: str \| None` | 说明参数和返回值类型；`X \| None` 表示"可能为 None" |
| `@dataclass` | `class Checkpoint: path: str` | 自动生成 `__init__`、`__repr__`、`__eq__` |
| `__post_init__` | `Checkpoint.__post_init__` | dataclass 构造完成后自动调用的钩子，用于额外初始化 |
| `with open(...) as f` | `with open(tmp_path, "w") as f:` | 上下文管理器，离开代码块自动关闭文件 |
| `json.dump` / `json.load` | `json.dump(data, f)` | Python 对象与 JSON 文件互转 |
| `os.fsync` / `os.replace` | `os.fsync(f.fileno())`、`os.replace(tmp, path)` | 强制落盘；原子地用新文件替换旧文件 |
| `hashlib` | `hashlib.sha256(txid.encode()).hexdigest()[:12]` | 计算哈希；`.encode()` 转 bytes，切片取前 12 位 |
| f-string | `f"balance_{from_acct}"`、`f"{self.path}.tmp"` | 在字符串中嵌入表达式 |
| `dict.get(key, default)` | `cp.load().get(k, {"status": "new"})` | 键不存在时返回默认值而不报错 |
| `in` 判断字典键 | `record["status"] in terminal_results` | 检查键是否存在 |
| 关键字参数与默认值 | `inject_crash_after_execute: bool = False`、`min_balance=200` | 调用时按名字传参，可读性好 |
| 数字下划线 | `10_000` | 等于 10000，仅为可读性 |
| `try` / `except ... as e` | `except RuntimeError as e: print(...)` | 捕获指定异常并取得异常对象 |
| `raise` | `raise RuntimeError("simulated crash after execute")` | 主动抛出异常（这里用来模拟崩溃） |
| `dict(...)` 浅拷贝 | `balances_before = dict(DB)` | 复制一份快照，之后修改 `DB` 不影响它 |
| `tempfile.mkdtemp` | `tmp = tempfile.mkdtemp()` | 创建唯一的临时目录（不会自动删除） |
| `"=" * 80` | `print("=" * 80)` | 字符串重复，打印分隔线 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()`，被 import 时不执行（本讲解的实验正是 import 后调用函数） |

---

## 6. 运行结果解读

实际运行（Python 3，无参数，耗时 < 1 秒）：

```text
Scenario 1: clean run
  result=ok  DB={'balance_A': 1400, 'balance_B': 300, 'last_transfer_id': 'tx-001'}

Scenario 2: crash mid-commit, retry (idempotency catches)
  crash: simulated crash after execute
  retry result=idempotent-skip  DB={'balance_A': 1300, 'balance_B': 400, 'last_transfer_id': 'tx-002'}

Scenario 3: precondition fails (balance would go below min)
  result=aborted-precondition  DB={'balance_A': 1300, 'balance_B': 400, 'last_transfer_id': 'tx-002'}

Scenario 4: verify fails -> rollback
  result=verify-fail-rolled-back  balances_before_after_equal=True
```

逐项解读：

- **场景 1**：1500 − 100 = 1400 ≥ 200，precondition 通过；执行、verify 通过，状态 `verified`。
- **场景 2**：从 1400 开始。第一次调用写了 `committed` 意图并完成转账（A=1300）后抛出模拟崩溃；重试读到 `committed`，返回 `idempotent-skip`。A=1300 说明转账**恰好执行一次**（讲义练习 1 要确认的就是这一点）。但我们额外检查了 checkpoint：该 key 的状态仍是 `committed`，从未变成 `verified`——恢复路径没有做 verify。
- **场景 3**：1300 − 10,000 远小于 200，直接写 `aborted-precondition`，余额不变。
- **场景 4**：从 1300 开始，转账执行（A=1200），注入 verify 失败后 rollback，A 回到 1300、`last_transfer_id` 回到 `tx-002`，所以前后快照完全相等，输出 `True`。
- HEADLINE 部分是固定文本，总结四件套各自覆盖的故障类别和第 14 条的三条工程解读。

补充实验（导入模块后调用函数，脚本放在临时目录，已运行）：

| 实验 | 结果 | 说明 |
|------|------|------|
| 在写意图后、执行前崩溃，再重试 | `idempotent-skip`，余额 1500/200 不变 | 副作用丢失却报告已处理 |
| 同 txid，金额从 100 改为 900 | 第二次返回 `ok`，余额只变了 100 | key 不含参数指纹 |
| 练习 2：先执行后写状态，崩溃后重试 | A=1300、B=400 | 100 元被转了两次（double-execute） |
| 无对应转账时调用 `rollback_transfer` | A=1600、B=100 | rollback 没有守卫 |

---

## 7. 动手改一改

1. **（讲义练习 1）** 运行代码，确认四个场景的输出，并在场景 2 后打印 `cp.load()`，观察状态停留在 `committed`。
2. **（讲义练习 2）** 把 `cp.save(... "committed" ...)` 移到 `persist_transfer` 之后，重跑场景 2，统计转账执行次数（应为 2）。再改回来，体会两种顺序各自的缺口。
3. **修复恢复路径**：把意图状态改名为 `in-flight`；重试命中 `in-flight` 时先回读目标系统，副作用已落地则标记 `verified`，未落地则重查 precondition 后补发（参考测验 Q9）。用 monkeypatch 构造"执行前崩溃"验证修复有效。
4. **参数指纹**：在意图记录里存 `sha256(json.dumps(参数, sort_keys=True))`，命中 key 时比对，不一致就返回 `"conflict"`。
5. **SAGA 式补偿**：把 `rollback_transfer` 改为一笔带独立 txid（如 `txid + "-comp"`）的反向转账，加入一张流水表 `DB["ledger"]`，verify 改为"流水中存在该 txid 且金额正确"；rollback 后也做 verify，失败时打印 `ALERT` 并返回 `"out-of-band"`。
6. **（讲义练习 5）** 写一个演练脚本：用 `subprocess` 启动一个执行转账的子进程，在副作用后 `os._exit(1)` 真正退出，再在父进程中重试并断言"流水中该 txid 恰好一条"。

---

## 8. 常见坑

- **把"已写意图"当"已完成"**：本代码的 `committed` 是执行前写的；恢复时不 verify 就会把没发生的副作用当成完成。
- **先执行后写状态**：做了没记，恢复后重复执行（练习 2）。
- **只做 idempotency 不做 precondition**：批准与执行之间状态漂移时照样执行（讲义的透支例子）。
- **verify 只看返回码或单个字段**：讲义明确"返回 200 不是验证"；本代码只比较 `last_transfer_id` 也容易误判。
- **rollback 不幂等、不验证、不告警**：rollback 本身也是一个有后果的动作，同样需要四件套。
- **非原子地写 checkpoint**：直接 `open(path, "w")` 覆盖写，崩溃时会留下截断的 JSON，下次 `json.load` 失败，idempotency 记录全丢。
- **用临时目录或内存做 checkpoint 后端**：部署或重启就丢，过不了第 14 条"审计轨迹挺过部署"的要求。
- **用 `raise` 代替真实崩溃做演练**：内存状态还在，掩盖了真实崩溃会暴露的问题。
