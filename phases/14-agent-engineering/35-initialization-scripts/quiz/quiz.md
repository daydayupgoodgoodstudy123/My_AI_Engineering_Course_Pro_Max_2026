# 测验 · 面向 Agents 的初始化脚本（Initialization Scripts for Agents）

> **阶段 14 · Agent 工程 · 第 35 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Setup tax（启动税） | 冷启动的会话会反复猜 Python 版本、猜测试命令、反复列目录、试导入缺失的包；讲义："ten thousand tokens have gone to setup work that should have been a single script" |
| 2 | Init script 的定位 | 在 agent 做任何事之前运行，把探测结果写进 `init_report.json`，agent 启动时读报告而不是重新探测 |
| 3 | 探测什么 | 运行时版本、依赖可用性、测试命令、仓库路径、环境变量、状态与任务板新鲜度、last-known-good（LKG）提交 |
| 4 | Probe 的形状 | 确定性函数，返回 `(name, status, detail)`；status 为 pass / warn / fail |
| 5 | Fail loud / fast / in one place | 任一阻断级探测失败就停下、交给人处理，不允许"让 agent 自己想办法"；init 的意义就是工作台坏了时拒绝启动 |
| 6 | 幂等 | 连续运行两次，除时间戳外报告完全相同；这样才能接进 CI、hooks、pre-task 斜杠命令 |
| 7 | Init vs 启动规则 | 规则（第 33 节）描述"行动前什么必须为真"；init 确保这些规则可被检查。讲义："Rules without init become 'be careful.' Init without rules becomes a polished failure." |
| 8 | LKG 锚定 | 当前提交与 LKG 的差异超过预算（默认 50 个文件）就拒绝启动，需人工确认新基线，防止漂移跨会话累积 |
| 9 | 带 TTL 的锁文件 | 首次全部通过后写 `prereqs.lock`，TTL（默认 24h）内且清单哈希不变时跳过昂贵探测——与 Docker 层缓存同构 |
| 10 | 热路径不碰网络与 LLM | 探测是确定性的管道；调用 LLM 或外部服务的不是探测而是工作流；干跑超过 3 秒是工作台异味 |

### 核心技能（能动手做到）

- [ ] 为一个仓库列出 init 需要的探测，并给每个探测定 severity（阻断 / 警告）
- [ ] 读懂 `_timed` 装饰器、`lock_is_fresh` 缓存判断和 `probe_lkg_diff` 的每个分支
- [ ] 预测 `main.py` 在"首次运行 / 立即再次运行 / `--no-cache` / 缺环境变量 / LKG 超预算"等情形下的输出与退出码
- [ ] 找出锁文件缓存的失效漏洞（失败后旧锁仍有效、指纹不含实际环境），并修复
- [ ] 用 `git diff --name-only <LKG> HEAD` 实现漂移预算检查，并处理"不是 git 仓库""LKG 文件格式错误"等边界
- [ ] 把 init 脚本接入 Claude Code hook、GitHub Actions 或 Docker entrypoint，确保非零退出码不会被吞掉

---

## 二、基础自测（选择题）

**Q1.** 讲义认为 init script 要解决的核心问题是：

- A. 让模型推理更快
- B. 替代单元测试
- C. 冷启动会话反复做的"启动税"（猜版本、找测试命令、列目录、试导入），用一个脚本付一次并把答案写进报告
- D. 自动修复所有环境问题，让 agent 无需人工介入

**Q2.** 讲义对 init 失败时的处理要求是：

- A. Fail loud、fail fast、fail in one place：停下并交给人，绝不"让 agent 自己想办法"
- B. 记录警告后继续启动 agent，由 agent 在执行中修复
- C. 自动重试直到成功
- D. 静默降级，跳过失败的探测

**Q3.** 在一个全新的 `workdir/`（没有状态文件、没有 LKG 文件、不是 git 仓库）上第一次运行 `python3 code/main.py`，结果是：

- A. 退出码 1，因为 `state_freshness` 和 `lkg_diff` 不是 pass
- B. 退出码 0，但不写 `prereqs.lock`
- C. 抛出 `FileNotFoundError`
- D. 退出码 0；`state_freshness` 与 `lkg_diff` 为 warn，其余 pass；写入 `init_report.json` 和 `prereqs.lock`

**Q4.** 紧接着第二次运行 `python3 code/main.py`（不带参数），会：

- A. 再跑一遍全部探测，只有时间戳不同
- B. 打印 `prereqs.lock fresh (TTL 86400s); skipping probes` 并以 0 退出，`init_report.json` 不会被重写
- C. 因为锁文件已存在而报错
- D. 删除锁文件后重新探测

**Q5.** 设 `REQUIRED_ENV_VARS = ["DEMO_KEY"]`。第一次运行时环境中有 `DEMO_KEY`，init 通过并写了锁；随后 `unset DEMO_KEY`，**不带** `--no-cache` 再运行一次。结果是：

- A. 退出码 0——锁文件仍"新鲜"，探测被整体跳过，缺失的环境变量没有被发现
- B. 退出码 1，env 探测失败
- C. 锁文件被自动删除，然后退出码 1
- D. 抛出 `KeyError`

**Q6.** `_timed` 装饰器包住一个耗时 50 ms 的探测，`PROBE_BUDGET_SECONDS` 设为 0.01。若该探测返回 `status="fail"`，最终状态是：

- A. `warn`，因为超时一律降级为警告
- B. `pass`，超时与状态无关
- C. 仍是 `fail`——装饰器只会把超时的 `pass` 改成 `warn`
- D. 装饰器抛出 `TimeoutError`

**Q7.** 按讲义，以下哪项**不应**出现在 init 的热路径中？

- A. 用 `importlib.util.find_spec` 检查依赖
- B. 用 `shutil.which` 解析测试命令
- C. 读取状态文件的修改时间
- D. 调用 LLM 对失败原因做分类，或访问外部服务检查许可证

**Q8.** 讲义所说的 init "幂等"是指：

- A. 每次运行都必须重新安装依赖
- B. 连续运行两次，报告除时间戳外完全相同，因此可以安全地接入 CI、hooks 和 pre-task 命令
- C. 只能运行一次，第二次会拒绝
- D. 运行结果与机器无关

---

## 三、动手 / 代码题

**Q9.** 锁文件缓存的相关代码：

```python
def _deps_fingerprint() -> str:
    h = hashlib.sha256()
    h.update(str(sorted(REQUIRED_DEPS)).encode())
    h.update(REQUIRED_TEST_COMMAND.encode())
    h.update(str(sorted(REQUIRED_ENV_VARS)).encode())
    h.update(str(REQUIRED_PYTHON).encode())
    return h.hexdigest()[:16]
```

```python
    if not args.no_cache and lock_is_fresh():
        print(f"prereqs.lock fresh (TTL {LOCK_TTL_SECONDS}s); skipping probes")
        return 0

    probes = run_probes()
    ...
    if not report["ok"]:
        print("\ninit failed; refuse to launch agent", file=sys.stderr)
        return 1
    write_lock()
```

1. 依次执行：①有 `DEMO_KEY` 时运行（通过、写锁）→ ②删掉 `DEMO_KEY`，带 `--no-cache` 运行 → ③不带参数再运行。②和③的退出码各是多少？③说明了什么漏洞？
2. 指纹哈希的是什么？讲义说跳过的条件是"the dependency manifest hash matches"，二者有何差别？
3. 给出修复方案（至少三点）。

**Q10.** 讲义和 mission 都说"exits non-zero if any **block-severity** probe fails"，但 `Probe` 没有 severity 字段，`main` 用的是 `all(p.status != "fail" ...)`。

1. 给 `Probe` 加 `severity`（`block` / `warn`），改写退出逻辑：只有 `block` 级探测 fail 才非零退出，`warn` 级 fail 只记录。
2. 讲义说"Stale state from a crashed session is a footgun"，代码中状态过期只是 `warn`。你会如何为 `state_freshness` 定级？说明理由。

**Q11.** 讲义练习 1（LKG 差异预算）在代码中已实现为 `probe_lkg_diff`。我们在一个临时 git 仓库里做了实验：先提交 5 个文件并 `--write-lkg`，再新增 51 个文件后 `git add -A && git commit`，然后运行 `--no-cache`，得到：

```text
  lkg_diff         fail     3ms  52 files changed since 85fbd61 (budget 50)
```

1. 明明只新增了 51 个文件，为什么报告 52 个？这对工程实践有什么提示？
2. 若 `last_known_good.json` 的内容是 `[]`（合法 JSON，但不是对象），会发生什么？
3. `git diff --name-only <LKG> HEAD` 会漏掉哪类改动？
4. `--write-lkg` 分支有哪些不严谨之处？

**Q12.** 讲义练习 3：加一个 `--fix` 参数，自动安装缺失的**开发**依赖，但"never modifies runtime dependencies without approval"。请给出设计与关键代码，说明如何保持 init 的幂等性与"fail loud"原则（mission 把"自动安装依赖"列为本节 out of scope，所以它必须是显式开启的）。

---

## 四、面试高频题

**Q13.**（基础必考）什么是 agent 的初始化脚本？它应该探测哪些内容？为什么不让 agent 自己在会话中摸索这些信息？

**Q14.**（原理深挖）init 脚本为什么必须是确定性、幂等、不调用网络和 LLM 的？"init" 与第 33 节的"startup 规则"是什么关系？

**Q15.**（工程实践）为了让 init 足够快，你引入了"锁文件 + TTL"缓存。缓存失效应该怎么设计才不会让 init 失去意义？

**Q16.**（场景设计）请把 init 脚本分别接入 Claude Code hooks、GitHub Actions 和 Docker 容器。有哪些常见的"失败被吞掉"的陷阱？报告里如何处理 secrets？

**Q17.**（追问型）LKG 锚定为什么能防止"漂移跨会话累积"？如果团队正好做了一次合理的大重构（改了 300 个文件），init 拒绝启动，你怎么办？

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义开篇："Every session that starts cold pays a tax. The agent reads the same files, retries the same probes, and rediscovers the same paths. An init script pays the tax once and writes the answers into state." A 与 init 无关；B 错：init 只确认"能验证"（例如测试命令存在），不替代验证本身；D 与"fail loud、交给人"的原则相反，mission 也把自动安装依赖列为 out of scope。

### Q2 — 答案：A

讲义："A probe failure means halt and surface to the human. No 'the agent will figure it out.' The whole point of init is to refuse to start when the workbench is broken." B、D 都是"静默兜底"；C 的无限重试会掩盖配置错误，而且对非确定性问题毫无帮助。

### Q3 — 答案：D

实际运行：

```text
  runtime          pass     0ms  python 3.13
  dependencies     pass     0ms  all of ['json', 'dataclasses'] importable
  test_command     pass     0ms  python3 resolvable on PATH
  env              pass     0ms  all of [] present
  state_freshness  warn     0ms  no state file yet; first run
  lkg_diff         warn     0ms  no last_known_good.json; pin one after first successful merge

init ok (lock refreshed)
```

退出码 0。`ok` 的判断是 `all(p.status != "fail" ...)`，warn 不影响结果；通过后 `write_lock()` 写入 `prereqs.lock`。A 错在把 warn 当成了 fail。

### Q4 — 答案：B

实际运行第二次：

```text
prereqs.lock fresh (TTL 86400s); skipping probes
```

退出码 0。`lock_is_fresh()` 为真时 `main` 直接 `return 0`，既不跑探测，也不重写 `init_report.json`（报告停留在上一次）。这与 mission 的验收标准"Running it twice in a row is a no-op except for the timestamp"并不完全一样：第二次连时间戳都没更新，报告本身也不是"本次"的结果。A 描述的是带 `--no-cache` 时的行为。

### Q5 — 答案：A

已实测：第二次（不带参数）输出 `prereqs.lock fresh ...; skipping probes`，退出码 0。锁的指纹只哈希了**配置常量**（`REQUIRED_ENV_VARS` 这个列表本身），而不是"环境变量当前是否存在"。列表没变 → 指纹没变 → 锁仍新鲜 → 所有探测被跳过。mission 的验收标准"A simulated missing env var probe surfaces in the report and flips the exit code"只有在带 `--no-cache` 时才成立。详见 Q9。

### Q6 — 答案：C

```python
        if result.duration_ms > PROBE_BUDGET_SECONDS * 1000 and result.status == "pass":
            result.status = "warn"
```

条件里有 `result.status == "pass"`，只降级 pass。实测：慢的 pass 探测变为 `warn`，detail 追加 `(slow: 50ms > 10ms)`；慢的 fail 探测保持 `fail`、detail 不变。D 错：装饰器只是事后计时，并不会中断一个运行过久的探测——真正的超时需要像 `probe_lkg_diff` 那样给子进程传 `timeout=`。

### Q7 — 答案：D

讲义："No network, no LLM, no surprises in the hot path ... A probe that calls an LLM to classify a failure or that hits an external service to check a license is not a probe; it is a workflow." A、B、C 都是本地、确定、毫秒级的检查，正是代码里实际使用的手段。

### Q8 — 答案：B

讲义："Run it twice in a row. The second run should be a no-op except for a fresh timestamp. Idempotency is what lets you wire the script into CI, hooks, or a pre-task slash command." 配套 skill 的硬拒绝也包括 "Probes that touch state without idempotency"。注意：代码报告中的 `duration_ms` 每次可能不同，严格来说也属于"非时间戳的差异"，比较报告时应忽略它。

### Q9 — 参考答案

1. 实测：② 退出码 **1**（env 探测 fail，`init failed; refuse to launch agent`）；③ 退出码 **0**（`prereqs.lock fresh ...; skipping probes`）。
   漏洞：失败的运行**不会让旧锁失效**。① 留下的锁仍在 TTL 内、指纹也没变，③ 直接短路通过——一次明确的失败被下一次普通运行"洗白"了。在 CI 或 hook 里，只要有人重跑一次，agent 就会在缺少密钥的环境中启动。
2. 指纹哈希的是**脚本中的配置常量**：依赖名列表、测试命令名、环境变量名列表、Python 版本要求。讲义说的是"dependency manifest hash"（例如 `requirements.txt`、`package-lock.json` 的内容哈希）。差别：
   - 修改 `requirements.txt` 新增依赖，指纹不变，锁照样生效；
   - 实际环境变化（卸载了包、删了环境变量、换了 Python 解释器）都不会反映到指纹里。
3. 修复（任选三点以上）：
   - **失败即删锁**：`if not report["ok"]: LOCK_PATH.unlink(missing_ok=True); return 1`；
   - **指纹包含真实输入**：依赖清单文件内容的哈希、`sys.executable` 与完整版本号、各必需环境变量"是否存在"（只哈希存在性，不哈希值，避免把 secret 写进锁）；
   - **只缓存昂贵探测**：env、state 新鲜度这类毫秒级探测每次都跑，锁只用于跳过真正慢的探测（讲义："skip the expensive probes"）；
   - **命中缓存也写报告**：写一份带 `"cached": true` 和本次时间戳的报告，agent 读到的永远是"这次启动"的结论；
   - 锁文件同样用原子写入（第 34 节）。

### Q10 — 参考答案

1. 实现：

```python
@dataclass
class Probe:
    name: str
    status: str                    # pass / warn / fail
    detail: str
    duration_ms: int = 0
    severity: str = "block"        # 默认最严格，漏标不会放水

def probe_state_freshness() -> Probe:
    ...
        return Probe("state_freshness", "fail", f"state is {hours}h old", severity="warn")

# main 中
blocking = [p for p in probes if p.status == "fail" and p.severity == "block"]
report["ok"] = not blocking
report["blocking"] = [p.name for p in blocking]
if blocking:
    print(f"init failed: {report['blocking']}", file=sys.stderr)
    return 1
```

   这样 status 表示"探测到了什么"，severity 表示"失败时该不该拦"，两个维度分开；与第 33 节规则的 block / warn / info 保持一致。`_timed` 中超时降级也应改为：对 `block` 级探测，超时只记录 warn，不改变其 pass/fail 结论。

2. 定级建议（开放题，给出理由即可）：
   - 状态文件**不存在**（首次运行）→ warn：正常情况，init 可以顺便 seed 一个空状态；
   - 状态**过期**且上次会话**异常结束**（例如 `active_task_id` 非空、没有 handoff）→ **block**：这正是讲义说的"footgun"，需要人确认后再继续（呼应第 32 节练习 1"超过 24 小时需操作员确认"）；
   - 状态过期但上次会话正常收尾 → warn。
   另外，用文件 mtime 判断新鲜度不可靠（`git checkout` 会改 mtime），更好的是读取状态内部的 `last_run` 时间戳字段。

### Q11 — 参考答案

1. 第 52 个文件是 `code/workdir/last_known_good.json`：`--write-lkg` 把 LKG 文件写在仓库里，随后 `git add -A` 把它也提交了。提示：init 自己产生的文件（`workdir/`、`init_report.json`、`prereqs.lock`、LKG 文件）要么放在仓库外，要么加入 `.gitignore`，否则 init 会被自己的产物计入漂移预算，甚至每次运行都让工作区变"脏"。
2. 实测抛出未捕获的 `AttributeError: 'list' object has no attribute 'get'`，脚本以 traceback 崩溃——`try` 只捕获了 `json.JSONDecodeError`，没有检查顶层类型。虽然崩溃也是非零退出，但它不是"fail in one place"的结构化失败：报告没有写出，人看到的是一段堆栈。应在 `json.loads` 之后加 `if not isinstance(lkg, dict): return Probe("lkg_diff", "fail", "lkg file malformed")`。
3. 只比较两个**提交**之间的差异，工作区中未提交的修改、未跟踪的新文件都不计入。如果预算要覆盖"当前工作区相对基线的全部漂移"，应改用 `git diff --name-only <LKG>`（与工作区比较）并加上 `git ls-files --others --exclude-standard`。
4. `--write-lkg` 的问题：
   - 不运行探测就把当前 HEAD 钉为"last-known-**good**"——讲义说 LKG 应在"last successful merge"时写入，至少应要求探测全部通过；
   - 只捕获 `FileNotFoundError` 和 `CalledProcessError`，`git rev-parse` 超时会抛未捕获的 `subprocess.TimeoutExpired`；
   - 用 `write_text` 非原子写入；
   - 实测在非 git 目录下输出 `lkg pin failed: ... returned non-zero exit status 128`，退出码 1，这一点处理正确。

### Q12 — 参考答案

设计要点：

```python
DEV_DEPS = {"pytest": "pytest>=8", "ruff": "ruff"}         # 允许自动安装的白名单
RUNTIME_DEPS = {"fastapi"}                                  # 永不自动安装

def fix_missing(missing: list[str]) -> list[str]:
    """返回仍未解决的依赖；只安装白名单中的开发依赖。"""
    unresolved = []
    for dep in missing:
        if dep in DEV_DEPS:
            r = subprocess.run(
                [sys.executable, "-m", "pip", "install", DEV_DEPS[dep]],
                capture_output=True, text=True, timeout=120,
            )
            if r.returncode != 0:
                unresolved.append(f"{dep}: pip failed: {r.stderr.strip()[-200:]}")
        else:
            unresolved.append(f"{dep}: runtime dependency, needs human approval")
    return unresolved
```

- **显式开启**：只有带 `--fix` 时才执行，默认行为仍是"探测 → 失败就停"。
- **白名单**：只装预先登记的开发依赖；运行时依赖一律交给人，并在报告里写明原因。
- **用 `sys.executable -m pip`**：保证装进运行 init 的同一个解释器环境，而不是 PATH 上另一个 `pip`。
- **修完再探测**：`--fix` 之后重新跑全部探测，以第二次探测结果决定退出码；任何仍未解决的项都要非零退出（fail loud）。
- **幂等**：已安装的依赖 `find_spec` 能找到，第二次运行不会再装；`--fix` 运行后锁文件应失效（环境变了）。
- **记录**：报告里加 `"fixed": [...]`，让人知道 init 改动了环境。
- 注意：这会让 init 访问网络（下载包），违背"热路径不碰网络"；因此 `--fix` 不应出现在 hook 或 CI 的默认调用里，只用于人工准备环境。

### Q13 — 参考回答要点

- **定义**：在 agent 会话开始前运行的确定性脚本，把"环境是否可工作"的答案一次性算出来，写进 `init_report.json`；不健康就拒绝启动。
- **探测项**（讲义表格）：运行时版本（错版本 = 静默的版本 bug）、依赖可用性（现在发现比以后发现便宜十倍）、测试命令（agent 必须知道怎么验证）、仓库路径（解析一次并固定）、环境变量（缺 `OPENAI_API_KEY` 是失败面，不是运行时谜题）、状态与任务板新鲜度、LKG 提交（会话结束 handoff diff 的锚点）。
- **为什么不让 agent 摸索**：浪费 token（讲义：上万 token 的启动税）；摸索不确定、不可复现；agent 可能"猜"出一个错误的答案并继续工作；失败点分散在会话各处，难以定位。
- **加分点**：每个探测返回 `(name, status, detail)` 统一形状；报告是结构化的，可以被 verification gate 和 handoff 复用。

### Q14 — 参考回答要点

- **确定性**：同样的环境必须得到同样的结论，否则"今天能启动、明天不能"无法排查；也才能缓存。
- **幂等**：可以被 CI、hook、斜杠命令反复调用而没有副作用。
- **不碰网络/LLM**：快（讲义：超过 3 秒就是异味）、离线可用、不受外部服务抖动影响；LLM 判断不确定、可能被注入；skill 硬拒绝"Probes that call out to the network without a timeout"和"Probes that require LLM calls"。
- **与 startup 规则的关系**：规则说"行动前状态文件必须新鲜"，init 是让这条规则**能被检查**的那段代码——它读状态文件、算年龄、写进报告；规则检查器再读报告。讲义："Rules without init become 'be careful.' Init without rules becomes a polished failure."
- **加分点**：init 产出的报告本身就是 `TurnTrace` 的一部分输入（第 33 节 skill 要求至少记录 `read_state_file` 等字段）。

### Q15 — 参考回答要点

- **缓存键必须覆盖所有会改变结论的输入**：依赖清单文件内容哈希、解释器路径与版本、必需环境变量的存在性（不含值）、探测代码本身的版本；讲义的类比是 Docker 层缓存——"idempotent probe + content hash = skip"。
- **TTL 只是兜底**：防止外部变化（系统包被卸载）长期不被发现；讲义默认 24h，练习 2 的"超过 7 天拒绝启动"是另一层保护。
- **失败即失效**：任何一次探测失败都删除锁（本节代码缺这一步，见 Q9）。
- **只缓存昂贵的**：毫秒级探测每次都跑；缓存命中也要写本次报告并标记 `cached: true`。
- **可强制绕过**：保留 `--no-cache`，CI 的定时任务用它做全量检查。
- **常见误区**：只哈希配置常量（本节代码的做法），导致"环境变了缓存还在"。

### Q16 — 参考回答要点

- **Claude Code hooks**：在会话/任务开始的 hook 中调用 init，hook 返回非零即阻止 agent 运行；讲义："`pre-task` hook calls the init script and refuses to launch the agent if it fails."
- **GitHub Actions**：单独的 `setup-agent` job 运行 init，agent job 用 `needs:` 依赖它；把 `init_report.json` 作为 artifact 上传便于排查。
- **Docker**：entrypoint 先运行 init，成功后 `exec` agent 运行时；失败时日志直接输出到容器日志。
- **吞掉失败的陷阱**：shell 中 `init.py || true`、管道 `init.py | tee log`（没有 `set -o pipefail` 时退出码来自 `tee`）、Makefile 中目标前的 `-`、包装脚本没有 `set -e`、hook 框架把非零当作警告。skill 的硬拒绝之一："A non-zero exit code that the wrapper swallows."
- **secrets**：env 探测只报告变量**名**和"是否存在"，绝不打印值（本节代码正是如此）；skill："If the env var list contains secrets the script will print, refuse and force redaction." 锁文件指纹也只能哈希存在性。
- **加分点**：所有接入方式共享同一个脚本——讲义："The init script is portable because it makes no calls to a specific framework."

### Q17 — 参考回答要点

- **原理**：每个会话都相对同一个已知良好的基线比较，而不是相对"上一个会话结束时的状态"。如果每次只和上一次比，每次的小漂移都看起来"在预算内"，累积起来却可能面目全非；锚定 LKG 后，累积漂移超过预算（默认 50 个文件）就会被拦下。讲义："every review session anchors against the same last-known-good and never compounds drift across sessions"（Cloudflare AI Code Review 的做法）。
- **合理的大重构**：讲义的处理是 "refuse to start and require a human to ratify the new baseline"。流程：人审查重构 → 合并 → 确认测试通过 → 运行 `--write-lkg`（理想情况下要求探测全部通过才能写）把新提交钉为基线 → agent 恢复工作。这是"人作为基线的批准者"，不是 init 的缺陷。
- **不要**：为了让 agent 跑起来而把预算调到 1000，或者直接删掉 LKG 文件——那等于关闭了这道防线。
- **加分点**：预算可以按目录分级（核心模块更严格）；LKG 也是会话结束 handoff diff 的锚点（第 40 节）；注意 init 自己的产物不能计入差异（见 Q11）。

---

## 六、关联知识点

### 前置知识
- [阶段 14 · 32 最小 Agent 工作台](../../32-minimal-agent-workbench/docs/zh.md)：init 检查的就是这三个文件是否健康。
- [阶段 14 · 34 代码仓库记忆与持久状态](../../34-repo-memory-and-state/docs/zh.md)：init 读取（并可 seed）的状态文件；锁文件、报告也应原子写入。
- [阶段 14 · 33 将 Agent 指令作为可执行约束](../../33-instructions-as-executable-constraints/docs/zh.md)：startup 类规则依赖 init 的结果；severity 分级的同一套思路。
- [阶段 00 · 01 开发环境](../../../00-setup-and-tooling/01-dev-environment/docs/zh.md)：运行时版本、依赖与环境变量的基础。

### 本节被哪些后续内容用到
- [阶段 14 · 36 Scope Contracts 与任务边界](../../36-scope-contracts/docs/zh.md)：使用 init 报告中解析好的仓库路径。
- [阶段 14 · 37 运行时反馈循环](../../37-runtime-feedback-loops/docs/zh.md)：使用 init 确认过的测试命令。
- [阶段 14 · 38 Verification Gates](../../38-verification-gates/docs/zh.md)：验证门依赖 init 探测通过。
- [阶段 14 · 40 跨会话 Handoff](../../40-multi-session-handoff/docs/zh.md)：handoff diff 以 init 记录的 LKG 为锚点。
- [阶段 14 · 29 生产运行时：队列、事件与定时任务](../../29-production-runtimes/docs/zh.md)：在生产运行时中接入启动前检查。

### 延伸关键词
`setup tax` · `probe` · `fail loud` · `idempotent` · `pre-task hook` · `last-known-good` · `drift budget` · `cache invalidation` · `content hash` · `TTL` · `set -o pipefail` · `secret redaction`
