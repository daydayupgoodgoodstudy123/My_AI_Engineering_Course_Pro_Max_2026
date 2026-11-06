# 测验 · 运行时反馈循环（Runtime Feedback Loops）

> **阶段 14 · Agent 工程 · 第 37 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 问题：agent 会"想象"输出 | agent 说"正在跑测试"，下一句说"全部通过"，实际上没跑、跑了没看、或看了但把失败行截掉了 |
| 2 | Feedback runner | 每条命令都经过 runner，把 stdout、stderr、退出码、耗时结构化落盘；agent 下一轮读记录，verification gate 在任务结束时读记录 |
| 3 | 记录字段 | `command`（精确 argv）、`stdout_tail`、`stderr_tail`、`exit_code`、`duration_ms`、`started_at`、`agent_note`；代码还加了 `command_id`、`parent_command_id`、`error`、`truncations`、`redactions` |
| 4 | 确定性截断 | 保留头 N 行 + 尾 M 行，中间换成 `...truncated N lines...`；同样的输入永远得到同样的记录；不采样，因为最终错误和总结在尾部 |
| 5 | Feedback 与 telemetry 分离 | feedback 给**本次运行的下一轮**用，telemetry（OTel GenAI）给运维跨时间回看；字段可共享，但文件和保留策略不同 |
| 6 | Refuse-on-null | runner 在拿到退出码之前出错时，记录 `exit_code: null` + `error`；没有退出码就不能宣称成功——"No exit, no progress" |
| 7 | 写入时脱敏 | 在追加 JSONL **之前**剥离 `Bearer`、`password=`、`api_key=`、`AKIA…`、`xox[baprs]-` 等；读取时脱敏是"自伤"，因为攻击者拿到的是磁盘文件 |
| 8 | 轮转而非单文件 | 当前文件上限 1 MB，溢出时轮转为 `.1`…`.5`，丢弃最老的；热循环的成本有上界 |
| 9 | 重试链 | 每条记录有 `command_id`，重试带 `parent_command_id` 指向上一次尝试；否则重试看起来像独立的成功，审计会隐藏失败历史 |
| 10 | argv-only | 只用参数列表、禁止 `shell=True`，避免 shell 展开带来的意外与注入 |

### 核心技能（能动手做到）

- [ ] 用 `subprocess.run(argv, capture_output=True, text=True, timeout=...)` 写出一个带超时、捕获三类异常路径（正常、超时、启动失败）的 runner
- [ ] 手算 `deterministic_tail` 在任意行数输入下的截断行数与输出行数
- [ ] 区分 `loop_can_advance`（有没有反馈）与"命令是否成功"（退出码是否为 0）
- [ ] 为脱敏正则写回归用例，找出漏报（如 `OPENAI_API_KEY=`）和误报（如 `token: 4096`）
- [ ] 说清"先截断再脱敏"与"先脱敏再截断"的安全差异，并能给出修复
- [ ] 用 `parent_command_id` 重建重试链，并说明轮转后链条可能断裂

---

## 二、基础自测（选择题）

**Q1.** 讲义开头描述的问题是"agent 说在跑测试，然后说全部通过，但实际上没有任何测试运行"。feedback runner 解决这个问题的方式是：

- A. 换一个更强的模型，让它不再幻觉
- B. 每条命令都经过 runner，把 stdout/stderr/退出码/耗时写成结构化记录，agent 下一轮和 verification gate 都读这份记录，而不是相信 agent 的叙述
- C. 在 system prompt 里要求 agent "如实汇报"
- D. 让 agent 每次运行命令前先预测结果，预测即结果

**Q2.** 关于 feedback 与 telemetry，讲义的观点是：

- A. 两者是同一件事，用一个文件就行
- B. telemetry 给下一轮 agent 读，feedback 给运维看
- C. feedback 必须走 OpenTelemetry 协议
- D. feedback 服务于本次运行的下一轮，telemetry 服务于跨时间回看的运维人员；字段可以共享，但存放在不同文件、有不同的保留策略

**Q3.** 本节代码中 `loop_can_advance(record)` 对一条 `exit_code=2` 的记录返回什么？

- A. `True`——它只在 `exit_code is None`（没有拿到反馈）时拒绝推进；非零退出码是 agent 需要读取并做出反应的事实
- B. `False`——非零退出码代表失败，循环不能推进
- C. 抛出异常
- D. `None`

**Q4.** `deterministic_tail` 使用 `HEAD_LINES=5`、`TAIL_LINES=30`。输入是 100 行文本（`line0` … `line99`），输出的标记和总行数是：

- A. `...truncated 70 lines...`，共 31 行
- B. `...truncated 65 lines...`，共 35 行
- C. `...truncated 65 lines...`，共 36 行
- D. 随机抽样 35 行，没有标记

**Q5.** 讲义强调"redact at write, not at read"，理由是：

- A. 磁盘上的文件才是攻击者能拿到的东西；只在读取时脱敏，秘密依然完整地躺在 JSONL 里
- B. 读取时脱敏会破坏 JSON 格式
- C. 写入时脱敏速度更快
- D. 写入时脱敏可以压缩文件

**Q6.** 运行 `python3 code/main.py`，`missing`（执行不存在的程序 `does-not-exist`）那条记录的情况是：

- A. `exit_code=127`，与 shell 中"命令未找到"一致
- B. runner 抛出 `FileNotFoundError`，整个脚本退出
- C. `exit_code=1`，`error=None`
- D. `exit_code=None`，`error` 为 `[Errno 2] No such file or directory: 'does-not-exist'`，`truncations` 和 `redactions` 都是空字典，`loop_can_advance` 返回 `False`

**Q7.** `parent_command_id` 的作用是：

- A. 让 JSONL 文件更小
- B. 让重试指向上一次尝试，reviewer 与 verification gate 能沿链条看到失败历史；没有它，重试看起来像一次独立的成功
- C. 保证命令按顺序执行
- D. 用作 subprocess 的进程号

**Q8.** 把 `ROTATE_BYTES` 临时改成 600 字节（每个文件约容纳 2 条短记录）、`MAX_ROTATIONS=5`，连续运行 16 条短命令后调用 `load_all()`，返回多少条记录？

- A. 16
- B. 2
- C. 12
- D. 10

---

## 三、动手 / 代码题

**Q9.** 运行 demo 后查看 `feedback_record.jsonl` 的第二行（`leak` 那条）：

```text
{"command_id": "...", "parent_command_id": null,
 "command": ["python3", "-c", "print('Authorization: Bearer ya29.AbCdEf'); print('password=hunter2'); print('AKIAIOSFODNN7EXAMPLE')"],
 "stdout_tail": "Authorization: Bearer [REDACTED]\npassword=[REDACTED]\nAKIA[REDACTED]\n", ...}
```

1. 脱敏是否成功？秘密还在磁盘上吗？指出代码中的原因。
2. 给出至少两种修复思路，并说明各自的局限。

**Q10.** 脱敏规则之一：

```python
    (re.compile(r"(?i)\b(password|passwd|secret|api[_-]?key|access[_-]?key|token)\s*[:=]\s*\S+"),
     r"\1=[REDACTED]"),
```

对下面四行分别调用 `redact()`，写出结果，并解释漏报/误报的原因：

```text
export OPENAI_API_KEY=sk-abc123
password: hunter2
max tokens: 512 ; token: 4096 used
he was the bearer of bad news
```

然后给出一个改进后的正则，至少修复 `OPENAI_API_KEY=` 这类环境变量写法，并说明讲义为什么建议"每季度审计"这些模式、以及应如何把它们变成回归测试。

**Q11.** `_process_capture` 的顺序是"先截断，再脱敏"：

```python
def _process_capture(text: str) -> tuple[str, int, int]:
    """Truncate first, then redact. Returns (text, cut_lines, redaction_hits)."""
    tailed, cut = deterministic_tail(text)
    redacted, hits = redact(tailed)
    return redacted, cut, hits
```

构造输入：10 行普通日志，后面跟一个 52 行的 PEM 私钥块（`-----BEGIN RSA PRIVATE KEY-----`、50 行密钥内容、`-----END RSA PRIVATE KEY-----`）。

1. 截断后保留了哪些行？私钥规则命中几次？泄漏了多少行密钥内容？
2. 如何修复？顺带指出 `deterministic_tail` 对"一行 5 MB"的输出会怎样，并一起修掉。

**Q12.** 讲义说"If the runner errors before capturing exit, the record carries `exit_code: null` and `error: <reason>`"。

1. 本节代码只捕获了 `TimeoutExpired` 和 `FileNotFoundError`。执行一个没有可执行权限的脚本会怎样？
2. 改写 runner 的异常处理，使任何启动失败都能落一条 `exit_code=None` 的记录；同时完成讲义练习 1（增加 `cwd` 字段），并把 `duration_ms` 改用单调时钟。

---

## 四、面试高频题

**Q13.**（基础必考）为什么 agent 需要一个 feedback runner？一条 feedback record 至少应包含哪些字段，每个字段解决什么问题？

**Q14.**（原理深挖）为什么讲义要求截断是"确定性的 head + tail"，而不是采样或只保留开头？确定性对 agent 循环、回放和缓存分别有什么意义？

**Q15.**（工程实践）agent 运行的命令输出里可能有密钥。请设计 runner 的脱敏方案：在哪一层做、覆盖哪些字段、模式如何维护、如何测试，以及有哪些脱敏之外的补充手段。

**Q16.**（场景设计）10 个并行 agent worker 共享一个仓库和一个 `feedback_record.jsonl`。请设计记录的写入、轮转、读取与重试链方案，并说明会遇到哪些并发问题。

**Q17.**（追问型）agent 最后汇报"所有测试已通过"。你作为 harness 设计者，怎样**机械地**验证这句话？如果 agent 先跑了测试通过、之后又改了代码，怎么办？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义："Every command goes through the runner... The agent reads the record at the next turn. The verification gate reads the records at the end of the task."核心思想是让 agent"对事实做反应，而不是对自己预测的事实做反应"。A 换模型不能保证命令真的被执行；C 仍然是"相信叙述"；D 把讲义里的 `agent_note`（执行前写下的预期）误解成了结果——`agent_note` 的价值恰恰在于可以和真实结果对比。

### Q2 — 答案：D

讲义："Telemetry ... is for human operators reviewing runs across time. Feedback is for the next turn of this run. They share fields but they live in different files with different retention."A 忽略了用途与保留期的差别；B 说反了；C 错，feedback 是一个 JSONL 文件，OTel 是 telemetry 那一侧（第 23 节）。

### Q3 — 答案：A

```python
def loop_can_advance(record: FeedbackRecord) -> bool:
    return record.exit_code is not None
```

实际验证：`exit_code=2` 的记录返回 `True`；超时记录（`exit_code=None`）返回 `False`。这个函数回答的是"有没有反馈"，不是"命令是否成功"——"No exit, no progress"。失败本身是一条有效反馈，agent 应读取 stderr 后修复并重试（这时用 `parent_command_id` 串起来）。B 是常见误解，把"能否推进"和"是否成功"混为一谈；判断成功要另外检查 `exit_code == 0`，这正是第 38 节 verification gate 做的事。

### Q4 — 答案：C

`cut = 100 − 5 − 30 = 65`，输出 = 前 5 行 + 1 行标记 + 后 30 行 = 36 行。实际运行：

```text
cut 65 ['line0', 'line1', 'line2', 'line3', 'line4', '...truncated 65 lines...', 'line70'] 36
```

注意阈值是 `len(lines) <= head + tail` 不截断：35 行不截，36 行截掉 1 行（实际验证）。A 算错了 cut；B 漏数了标记行；D 违反了讲义"No sampling"。

### Q5 — 答案：A

讲义："Redaction at read time is a foot-gun; the file on disk is what an attacker reaches."秘密一旦落盘，就会进入备份、CI artifact、日志收集系统，读取时再遮掩已经晚了。B、C、D 都不是讲义给出的理由。

### Q6 — 答案：D

实际输出：

```text
missing: cid=bcd74d24c2cc parent=- exit=None duration_ms=0 redactions=-
  error: [Errno 2] No such file or directory: 'does-not-exist'
```

`subprocess.run` 以 argv 方式直接 `exec`，找不到程序时在 Python 层抛 `FileNotFoundError`，代码捕获后写 `exit_code=None`。这条分支没有传 `truncations`/`redactions`，所以是 dataclass 默认的空字典，打印时 `rec.redactions or '-'` 显示为 `-`。A 中的 127 是 **shell** 的约定，只有 `shell=True` 时才会出现，本节禁止 `shell=True`；B 错，异常被捕获了；C 错。

### Q7 — 答案：B

讲义："Without this link, retries look like independent successes and the audit hides the failure history."demo 中 `retry` 的 `parent_command_id` 指向 `fail`，`retry_chain(retry.command_id)` 输出 `['840ce3baaa5c', '791070e774e2'] (oldest -> newest)`（id 每次运行不同）。A、C、D 都与它无关。

### Q8 — 答案：C

实际运行（16 条记录，每个文件约 2 条）：当前文件 + `.1`…`.5` 共 6 个文件、每个 2 条，`load_all()` 返回 12。最早的 4 条已随 `.5` 被覆盖而丢弃。几点细节：

- `maybe_rotate()` 在**追加之前**检查大小，只有当前文件已经 ≥ 阈值才轮转，所以单个文件会超过阈值一条记录的大小（实测 660 字节 > 600）；
- 磁盘上最多 1 + 5 个文件，生产配置下总量约 6 MB；
- `load_all()` 会读取全部轮转文件，这与讲义"agent 的循环只读当前文件"的说法不一致；被丢弃文件中的父记录会让 `retry_chain` 静默地截断。

A 忽略了丢弃；B 只算了当前文件；D 算错了文件数。

### Q9 — 参考答案

1. **stdout 脱敏成功，但秘密仍在磁盘上**：`command` 字段原样写入了 `Bearer ya29.AbCdEf`、`password=hunter2`、`AKIAIOSFODNN7EXAMPLE`。原因是 `redact()` 只作用于 stdout/stderr（`_process_capture`），`command`、`agent_note`、`error` 都没有经过脱敏就进了 `asdict(record)`。demo 输出里的 "stdout after redaction" 给人一种"已经安全"的错觉。
2. 修复思路：
   - **对所有字符串字段脱敏**：写入前对 `command` 的每个元素、`agent_note`、`error` 都调用 `redact`。局限：贪婪的 `\S+` 会吞掉引号和分号，实测 `password=hunter2');` 被整个替换成 `password=[REDACTED]`，记录下来的 argv 已经不是可重放的原命令；而且正则永远有漏网之鱼。
   - **不要让秘密出现在 argv 里**：密钥通过环境变量或文件传给子进程（`subprocess.run(..., env=...)`），runner 只记录环境变量**名**，不记录值。这是更根本的做法——argv 在 `ps` 中对同机其他用户可见。
   - **已知秘密值精确替换**：runner 启动时从环境中收集已知的密钥值，写入前做字面量替换，弥补正则的漏报。
   - 再加上文件权限（如 0600）和保留期，缩小泄漏面。

### Q10 — 参考答案

实际运行结果：

```text
export OPENAI_API_KEY=sk-abc123         → 未变（0 次命中）            漏报
password: hunter2                        → password=[REDACTED]        正确
max tokens: 512 ; token: 4096 used       → max tokens: 512 ; token=[REDACTED] used   误报
he was the bearer of bad news            → he was the Bearer [REDACTED] bad news     误报
```

- **漏报**：`\b` 是"单词边界"，而 `_` 属于单词字符，`OPENAI_API_KEY` 中 `API` 前面是 `_`，不存在 `\b`，于是整条规则不匹配。`GITHUB_TOKEN=...`、`DB_PASSWORD=...` 同理——恰恰是最常见的环境变量写法。
- **误报**：`token: 4096` 在 LLM 日志里很常见（token 计数）；`bearer\s+\S+` 匹配普通英文。误报的代价是 agent 看不到有用信息（例如 token 用量）。
- 改进（实际验证可以修复前三种中的漏报，并且不误伤 `max tokens: 512`）：

  ```python
  API_KEY = re.compile(
      r"(?i)([A-Za-z0-9_]*(?:password|passwd|secret|api[_-]?key|access[_-]?key|token))\s*[:=]\s*\S+")
  # export OPENAI_API_KEY=sk-abc123 → export OPENAI_API_KEY=[REDACTED]
  # GITHUB_TOKEN=ghp_x              → GITHUB_TOKEN=[REDACTED]
  ```

  `token: 4096` 仍会被替换——可以要求值看起来像密钥（如长度 ≥ 16 且含字母数字混合），或为纯数字值放行。
- **为什么要审计**：讲义："Audit the redaction patterns quarterly against the production runtime's observed secret formats."新的云服务、新的 token 前缀（如 `sk-`、`ghp_`）会不断出现。把每一种格式写成 fixture（应被脱敏的正例 + 不应被脱敏的反例），作为 CI 回归测试；讲义延伸阅读也提到把脱敏模式当作回归测试来维护。

### Q11 — 参考答案

1. 输入共 62 行，`cut = 62 − 35 = 27`。保留：前 5 行普通日志（`log0`–`log4`）+ 标记 + 最后 30 行（密钥内容的第 22–50 行共 29 行 + `END` 行）。`BEGIN` 行落在被截掉的中间部分，私钥规则要求 `BEGIN ... END` 成对出现，因此**命中 0 次**，**29 行密钥内容原样泄漏**（实际运行：`key hits 0 leaked keylines: 29`）。
2. 修复：**先脱敏，再截断**——在完整文本上运行多行模式，然后再截断。实测 `redact` 先行时命中 1 次、泄漏 0 行。代价是要对完整输出跑一遍正则（50 MB 日志会更慢），可以先做一个很大的字节上限（例如只保留前后各若干 MB）再脱敏、再按行截断。
   同时，`deterministic_tail` 只按**行**截断：实测一行 5,000,000 字符的输出 `cut=0`，原样进入记录，讲义说的"50 MB log destroys the loop"并没有被挡住。补一个按字符/字节的上限：

   ```python
   def process_capture_v2(text, max_bytes=64_000):
       red, hits = redact(text)                      # 1) 先在全文上脱敏
       tailed, cut = deterministic_tail(red)         # 2) 再按行截断
       if len(tailed) > max_bytes:                   # 3) 最后按字符兜底，同样是确定性的头+尾
           half = max_bytes // 2
           tailed = tailed[:half] + f"...truncated {len(tailed) - max_bytes} chars..." + tailed[-half:]
       return tailed, cut, hits
   ```

   实测：私钥用例泄漏 0 行；5 MB 单行被压到 64,029 个字符。

### Q12 — 参考答案

1. 没有执行权限的脚本会让 `subprocess.run` 抛出 `PermissionError`，它不在任何 `except` 分支里，**异常直接冒出 runner，不写任何记录**（实测：`PermissionError [Errno 13] Permission denied`）。`cwd` 指向不存在的目录、argv 中含 `\0` 等也会类似。这违背了讲义"出错也要落一条 `exit_code: null` 的记录"。
2. 参考实现（已实际运行）：

   ```python
   def safe_run(command, cwd=None, timeout_s=30.0):
       t0 = time.monotonic()
       base = {"cwd": cwd or os.getcwd()}
       try:
           cp = subprocess.run(command, capture_output=True, text=True, timeout=timeout_s, cwd=cwd)
           return {**base, "exit_code": cp.returncode, "error": None,
                   "duration_ms": int((time.monotonic() - t0) * 1000)}
       except subprocess.TimeoutExpired:
           return {**base, "exit_code": None, "error": f"timeout after {timeout_s}s",
                   "duration_ms": int((time.monotonic() - t0) * 1000)}
       except OSError as exc:   # FileNotFoundError、PermissionError、NotADirectoryError 都是 OSError 子类
           return {**base, "exit_code": None, "error": f"{type(exc).__name__}: {exc}",
                   "duration_ms": int((time.monotonic() - t0) * 1000)}
   ```

   实测：不可执行脚本 → `exit_code=None, error="PermissionError: ..."`；`cwd="/nonexistent-dir"` → `FileNotFoundError`；`cwd="/tmp"` 运行 `pwd` → `exit_code=0`。`time.monotonic()` 不受系统时间调整影响，适合测耗时；`started_at` 仍用 `time.time()` 作为可读的时间戳。真正落盘时还要把 stdout/stderr 的处理和 JSONL 追加保留下来。

### Q13 — 参考回答要点

- **为什么**：LLM 会"预测"命令输出而不是读取它；即便读了，也可能忽略或截掉失败行。runner 让每条命令都留下客观、结构化的事实，agent 下一轮读、gate 在结束时读。
- **字段**：
  - `command`：精确 argv，避免 shell 展开的歧义，可重放；
  - `stdout_tail` / `stderr_tail`：分开保存，错误通常在 stderr 尾部；
  - `exit_code`：最明确的成功信号，`null` 表示没拿到反馈；
  - `duration_ms`：发现慢探针、卡死进程（skill 把缺失 `duration_ms` 列为 hard reject）；
  - `started_at`：回放与排序；
  - `agent_note`：执行前写下的预期，事后可对比"预期 vs 实际"；
  - 生产补充：`command_id` / `parent_command_id`（重试链）、`error`、`truncations`、`redactions`、`cwd`。
- 加分点：提到 Claude Code 的 Bash 工具已经捕获 stdout、stderr、退出码和耗时，本节 runner 是与框架无关的等价物。

### Q14 — 参考回答要点

- **为什么要截断**：上下文窗口与 token 预算有限，讲义："A 50 MB log destroys the loop."
- **为什么 head + tail**：头部有命令启动信息、配置、早期警告；尾部有最终错误、堆栈、测试总结（"the parts the agent needs to see ... live at the tail"）。只保留开头会丢掉最关键的失败行。
- **为什么确定性、不采样**：
  - 同样的输出 → 同样的记录，agent 的行为可复现，便于调试和回归；
  - 回放时（CI artifact、reviewer）看到的就是 agent 当时看到的；
  - 稳定的文本有利于 prompt caching 和差异对比；采样会让同一次失败每次呈现不同片段。
- 加分点：显式标记 `...truncated N lines...`，让 agent 知道"有东西被省略"，必要时可以用 `grep` 等命令精准取回；指出按行截断对超长单行无效，需要再加字节上限。

### Q15 — 参考回答要点

- **在哪一层**：写入时、在 runner 内部、在任何持久化之前（讲义）。读取时脱敏无效。
- **覆盖哪些字段**：stdout、stderr，还有 `command`（argv）、`agent_note`、`error`——本节代码只覆盖了前两个（见 Q9）。
- **模式维护**：Bearer、`password=`、`api_key=`、AWS `AKIA…`、Slack `xox[baprs]-`、PEM 私钥等；注意 `\b` 与下划线的问题（Q10）；按季度对照生产中观察到的密钥格式审计；每种格式都有正反例 fixture 作为回归测试。
- **顺序**：先在全文上脱敏再截断，避免多行秘密被截断"切开"后漏网（Q11）。
- **补充手段**：秘密不进 argv，改用环境变量或文件；对已知秘密值做字面量替换；JSONL 文件权限、保留期、CI artifact 访问控制；`redactions` 计数作为告警信号（某条命令突然出现大量命中，说明可能在打印凭据）。
- 常见误区：认为"日志只给 agent 看所以无所谓"——记录会进入 CI artifact、reviewer、handoff 文件。

### Q16 — 参考回答要点

- **写入**：多进程同时 `open("a")` + `write` 一行：追加模式（O_APPEND）保证每次底层 write 都定位到文件末尾，但 Python 的缓冲写入可能把一条大记录拆成多次 write，不同进程的记录就可能交错、撕裂 JSON 行；skill 明确要求"refuse to skip a file lock around the JSONL append"。可用 `fcntl.flock`、每个 worker 一个文件、或写入队列由单一写者落盘。
- **轮转**：轮转（重命名）与写入之间存在竞争：A 判断需要轮转并重命名后，B 可能仍持有旧文件句柄继续写入。需要把"检查 + 轮转 + 追加"放在同一把锁里。
- **读取**：agent 热循环只读当前文件最近 N 条（skill："A loader that returns an unbounded list" 是 hard reject）；CI 与 reviewer 读全部轮转文件。按 `task_id` / worker id 过滤。
- **重试链**：`command_id` 用 UUID 避免冲突；`parent_command_id` 指向的记录可能已被轮转丢弃，读取时要区分"链的起点"与"父记录已丢失"；关键链条应在 handoff 或 gate 报告里固化。
- 加分点：把 runner 的 JSONL 同时以 OTel 的格式导出到 telemetry，但两条管道保留期不同。

### Q17 — 参考回答要点

- **机械验证**：verification gate 不接受自由文本声明，而是读取 feedback 记录：
  - 合同（第 36 节）中的每条 acceptance 命令，都要有一条匹配的记录，且 `exit_code == 0`；
  - `exit_code is None` 的记录一律视为"没有反馈"；
  - agent 的完成声明必须引用具体 `command_id`，gate 去查这条记录。
- **先通过后修改**：记录要带时间戳或序号，并与"最后一次文件写入"比较——测试记录必须晚于最后一次代码改动，否则视为过期证据，需要重跑。也可以记录运行时的 git tree hash，gate 只认与最终 diff 一致的那次运行。
- **失败历史**：通过 `parent_command_id` 能看到"失败 → 修改 → 重试成功"的链，reviewer（第 39 节）可以判断修复是否合理，而不是只看到一个绿色结果。
- 常见误区：只检查"最近一条记录是 0"——它可能根本不是测试命令。

---

## 六、关联知识点

### 前置知识
- [阶段 14 · 32 最小 Agent 工作台](../../32-minimal-agent-workbench/docs/zh.md)：feedback runner 是工作台的组件之一。
- [阶段 14 · 35 面向 Agents 的初始化脚本](../../35-initialization-scripts/docs/zh.md)：初始化脚本确定环境与命令，runner 负责执行并记录。
- [阶段 14 · 01 Agent Loop：观察、思考、行动](../../01-the-agent-loop/docs/zh.md)：feedback record 就是"观察"这一步的结构化版本。
- [阶段 14 · 06 工具使用与 Function Calling](../../06-tool-use-and-function-calling/docs/zh.md)：shell 命令也是一种工具调用，其结果要回填给模型。

### 本节被哪些后续内容用到
- [阶段 14 · 38 Verification Gates](../../38-verification-gates/docs/zh.md)：gate 读取 JSONL，确认验收命令真的跑过且退出码为 0。
- [阶段 14 · 39 Reviewer Agent：将实现者与评分者分开](../../39-reviewer-agent/docs/zh.md)：reviewer 打分时读取 feedback 记录。
- [阶段 14 · 40 跨会话 Handoff](../../40-multi-session-handoff/docs/zh.md)：handoff 的"失败尝试"列表沿重试链整理。
- [阶段 14 · 23 OpenTelemetry GenAI 语义约定](../../23-otel-genai-conventions/docs/zh.md)、[阶段 14 · 24 Agent 可观测性](../../24-agent-observability-platforms/docs/zh.md)：telemetry 一侧的规范与平台。
- [阶段 17 · 25 安全：密钥、API 密钥轮换、Audit Logs 与 Guardrails](../../../17-infrastructure-and-production/25-security-secrets-audit/docs/zh.md)：日志脱敏与审计日志的生产实践。

### 延伸关键词
`subprocess.run` · `argv vs shell=True` · `TimeoutExpired` · `exit code` · `head/tail truncation` · `secret redaction` · `log rotation` · `JSONL` · `file locking` · `retry lineage` · `time.monotonic` · `feedback vs telemetry`
