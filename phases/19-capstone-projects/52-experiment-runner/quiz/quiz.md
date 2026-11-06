# 测验 · 实验执行器（Experiment Runner）

> **阶段 19 · 综合项目 · 第 52 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py)、[code/experiments/sparsity_experiment.py](../code/experiments/sparsity_experiment.py)、[code/experiments/crashing_experiment.py](../code/experiments/crashing_experiment.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)、[code/experiments/sparsity_experiment.讲解.md](../code/experiments/sparsity_experiment.讲解.md)、[code/experiments/crashing_experiment.讲解.md](../code/experiments/crashing_experiment.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 为什么用子进程 | 研究循环跑的是"不可信代码"（假设与脚本都来自采样器）；子进程给出独立地址空间和父进程侧的 kill 句柄，实验崩溃不会拖垮编排器（orchestrator） |
| 2 | `ExperimentSpec` 契约 | `spec_id / hypothesis_id / script_path / config / seed / wall_timeout_s / memory_cap_mb / metric_keys`；config 写进临时文件，路径作为唯一 argv 传给脚本 |
| 3 | 硬超时（wall clock） | `proc.communicate(timeout=...)` 超时抛 `TimeoutExpired` → `proc.kill()` → 再 `communicate(timeout=2.0)` 收尾，标记 `timeout` |
| 4 | 软内存上限 | 后台线程每 0.05 s 读一次 `/proc/<pid>/status` 的 `VmRSS`（退而求其次用 `ps`），超过上限就 kill，标记 `oom`；轮询有间隔，所以是"软"的 |
| 5 | 指标协议 | 脚本在 stdout 打印 JSON 行；**最后一个**覆盖全部 `metric_keys` 的 JSON 行是最终指标，之前的覆盖行进入 `intermediate_metrics`（学习曲线） |
| 6 | terminal 标签 | 优先级 `oom > timeout > ok/crash`；只有"退出码 0 且解析到指标"才是 `ok`，非零退出即使打印了指标也是 `crash` |
| 7 | 从不抛异常 | 退出码、stderr 都记录进 `ExperimentResult`；连 `Popen` 本身失败（`OSError`）也包装成 `exit_code=-1, terminal="crash"` |
| 8 | 单 knob 消融 | `ablate(base, knob, values)` 每个值生成一个 spec，`spec_id = f"{base}_{knob}_{value}"`；一次只动一个旋钮，得到评估器能画的干净坐标轴 |
| 9 | 确定性 | `config["__seed"] = spec.seed` 转发给脚本；同 seed 两次运行指标完全一致，53 节才能区分"真回退"与"随机初始化不同" |
| 10 | 这不是真沙箱 | 没有 cgroup、seccomp、namespace；只实现了"超时 + 内存轮询 + kill"这个所有沙箱都要扩展的最小运行时契约 |

### 核心技能（能动手做到）

- [ ] 用 `subprocess.Popen` + `communicate(timeout=)` 写出"超时即 kill、仍能拿回部分输出"的子进程执行器
- [ ] 用一个 daemon 线程 + `threading.Event` 实现可停止的周期性轮询器，并解释它为什么只能做"软"上限
- [ ] 给定一段 stdout 和 `metric_keys`，手推 `_scan_intermediates` 返回的 `(final, intermediates)`
- [ ] 给定退出码、是否超时、是否 OOM、是否有指标，判断 terminal 标签
- [ ] 用 `ablate` / `AblationRunner.sweep` 构造一次单 knob 消融，并说清为什么所有行共用同一个 seed
- [ ] 说出本节 runner 与生产级沙箱（进程组 kill、`setrlimit`、cgroup、容器）之间的差距，并能补上其中一两项

---

## 二、基础自测（选择题）

**Q1.** 讲义说研究循环应当在子进程里运行实验脚本，而不是在编排器进程里 `import` 它。最核心的理由是：

- A. 子进程启动比 `import` 更快
- B. Python 不允许在运行时 `import` 磁盘上的任意脚本
- C. 实验代码来自采样器、不可信；独立进程有独立地址空间，父进程保留 kill 句柄，脚本崩溃、死循环或吃光内存都不会拖垮编排器
- D. 只有子进程才能打印 JSON

**Q2.** 某次运行退出码为 0，但 stdout 中没有任何一行 JSON 同时包含 `perplexity` 和 `final_loss`（`metric_keys`）。`_terminal_label` 返回：

- A. `"crash"`
- B. `"ok"`
- C. `"timeout"`
- D. `"oom"`

**Q3.** 内存轮询线程已把进程 kill（`killed_for_oom=True`），而主线程几乎同时也触发了 `TimeoutExpired`（`killed_for_timeout=True`）。最终标签是：

- A. `"timeout"`，因为墙钟超时是硬限制
- B. `"crash"`，因为退出码是 −9
- C. 取决于两个线程谁先执行
- D. `"oom"`，因为 `_terminal_label` 按 `oom → timeout → ok/crash` 的顺序判断

**Q4.** 讲义把内存上限称为"软上限（soft cap）"，原因是：

- A. 它只统计堆内存，不统计栈
- B. 它靠周期性轮询 RSS 实现，轮询间隔内进程可以短暂冲高再回落而不被发现；真正的硬上限需要内核层面的 `resource.setrlimit`/cgroup
- C. 超过上限时只记录警告，不会 kill 进程
- D. NumPy 分配的内存不计入 RSS

**Q5.** `metric_keys = ["a"]`，脚本的 stdout 如下。`_scan_intermediates` 返回的 `(final, intermediates)` 是：

```text
{"a": 1}
[1, 2]
 {"a": 2, "b": 3}
not json {
```

- A. `({"a": 2, "b": 3}, [{"a": 1}])`
- B. `({"a": 1}, [{"a": 2, "b": 3}])`
- C. `({}, [])`，因为第 2、4 行解析失败会让整个扫描放弃
- D. `({"a": 2, "b": 3}, [{"a": 1}, [1, 2]])`

**Q6.** `base.spec_id = "exp"`，调用 `ablate(base, "lr", [0.1, 1e-4])`，得到的两个 `spec_id` 是：

- A. `"exp_0"`、`"exp_1"`
- B. `"exp_lr_0.1"`、`"exp_lr_1e-4"`
- C. `"exp_lr_0.1"`、`"exp_lr_0.0001"`
- D. `"lr_exp_0.1"`、`"lr_exp_0.0001"`

**Q7.** `ablate` 生成的所有 spec 都沿用 `base.seed`，而不是每个值换一个 seed。这样做的主要好处是：

- A. 节省子进程启动时间
- B. 让每个 spec 的 `spec_id` 唯一
- C. 让内存轮询更准确
- D. 控制变量：各行的随机噪声完全相同，指标差异只能来自被扫描的 knob（实际运行中 k=4 与 k=32 的 `final_loss` 差恰好等于公式项之差 0.04375）

**Q8.** 测试 `test_timeout_terminal` 用 `steps=20, sleep_s=0.4, wall_timeout_s=0.5`。实际运行时结果为 `terminal="timeout"`，那么 `result.metrics` 是什么？

- A. 空字典 `{}`，因为超时的运行不解析 stdout
- B. 第 0 步的中间指标行 `{"step": 0, "loss": ..., "perplexity": ..., "final_loss": ...}`，因为中间行也覆盖了 `metric_keys`，被当成了"最终指标"
- C. 脚本最后一行 `{"perplexity": ..., "steps_completed": 20, ...}`
- D. `{"error": "timeout"}`

---

## 三、动手 / 代码题

**Q9.** 阅读 `_rss_mb` 和 `_MemoryPoller.run`（节选）：

```python
def _rss_mb(pid: int) -> float | None:
    proc_status = f"/proc/{pid}/status"
    if os.path.exists(proc_status):
        ...  # 读 VmRSS，没有这一行就 return 0.0
    if shutil.which("ps"):
        ...  # ps -o rss= -p pid，输出为空则落到最后
    return None

    # _MemoryPoller.run 中
            rss = _rss_mb(self._proc.pid)
            if rss is None:
                self.unsupported = True
                ...  # 记一次 "platform does not expose RSS" 警告
                return
```

1. `_rss_mb` 的返回值 `None` 实际上混合了哪几种含义？在 Linux 上什么情况下会出现"平台明明支持，却被判成 unsupported"？
2. 讲义说"Hard memory caps need `resource.setrlimit`"。请给 `ExperimentRunner` 加一个可选的硬上限，并说明用 `RLIMIT_AS` 时上限应该怎么取值（提示：实测 `allocate_mb=400` 在 `RLIMIT_AS=512MB` 下以 `MemoryError` 退出，在 1024MB 下正常）。

**Q10.** 承接 Q8：超时、崩溃的运行里，`metrics` 可能被填上一条"中间行"。虽然评估器"先看 terminal"，但这仍是一个容易误用的接口。请给出两种修复思路，并写出其中一种的代码。

**Q11.** 手算题。`sparsity_experiment.py` 的损失公式为：

```python
loss_step = base_loss * (0.9 ** step) - 0.05 * min(k, 32) / 32.0 + noise   # base_loss = 5.0
```

demo 配置 `steps=4, seed=7`。已知实际运行 k=16 时 `final_loss = 3.602188`。

1. 求最后一步（step=3）的噪声值。
2. 不再运行代码，写出 k = 4、8、32、64 时的 `final_loss`，并估算 k=4 与 k=32 的 perplexity。
3. 消融表中 k 从 4 到 32，perplexity 只变化了约 1.6。如果把 seed 换成"每个 k 一个不同 seed"，这张表还能说明问题吗？

**Q12.** 实验脚本自己又 `Popen` 了一个子进程（例如 DataLoader worker），代码如下。我们实测：`wall_timeout_s=1.0` 时 runner 的 `wall_time_s` 为 **3.02 s**，`metrics={}`，`stdout_tail=''`——脚本第一行明明已经打印并 flush 了指标。

```python
print(json.dumps({"perplexity": 1.0, "final_loss": 0.1}), flush=True)
subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
time.sleep(30)
```

1. 解释为什么耗时是 3 s 而不是 1 s，为什么已打印的输出丢了。
2. 运行结束后孙进程还活着吗？如何修改 `_run_subprocess` 让 kill 覆盖整个进程树？

---

## 四、面试高频题

**Q13.**（基础必考）为什么自动化研究 / Agent 系统要在子进程中执行生成的代码？本节的 runner 提供了什么、缺少什么？一个"真正的沙箱"还需要哪些层？

**Q14.**（原理深挖）本节靠"转发 seed"保证确定性。在真实的深度学习实验里，固定 seed 之后还有哪些因素会破坏可复现性？评估器应该如何应对"无法完全确定"的情况？

**Q15.**（工程实践）runner 与实验脚本之间用"stdout 上的最后一行 JSON"作为指标协议。这个协议有哪些脆弱点？如果让你设计生产版本，你会怎么改？

**Q16.**（场景设计）研究循环每天要跑上千个实验，部分需要 GPU。请在本节 `ExperimentRunner` 的基础上设计一个可扩展的执行系统。

**Q17.**（追问型）一次只扫一个 knob 的消融有什么局限？什么时候必须做多因素（factorial）或随机搜索？

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义原话："A research loop runs untrusted code... Subprocesses are the simplest isolation the language ships: a separate process, an independent address space, a signal handle on the parent side." 进程内 `import` 时，脚本的 `sys.exit`、段错误、无限循环、内存泄漏都会直接作用在编排器上，而且无法从外部安全地"杀掉一个函数调用"。

- A 错：子进程要重新启动解释器、重新 import numpy，每次约 0.2 s（实测 `wall_time_s` 0.22–0.29 s），比 `import` 慢。
- B 错：`importlib` 完全可以加载任意路径的模块，问题不是"做不到"，而是"不安全"。
- D 错：打印 JSON 和是否用子进程无关。

### Q2 — 答案：A

```python
        if exit_code == 0 and have_metrics:
            return "ok"
        if exit_code == 0 and not have_metrics:
            return "crash"
        return "crash"
```

"退出码 0 但没给出约定的指标"被视为失败：评估器拿不到可比较的数字，只能把它当成失败运行。实测把 `metric_keys` 改成 `["accuracy"]`（脚本不输出该键）后，结果为 `terminal="crash", exit_code=0, metrics={}`。注意第 2 个 `if` 与最后的 `return "crash"` 结果相同，是冗余分支，只起"把情况写明白"的作用。

B 错在忽略了 `have_metrics`；C、D 需要超时或 OOM 标志。

### Q3 — 答案：D

```python
        if oomed:
            return "oom"
        if timed_out:
            return "timeout"
```

判断顺序固定，与线程调度无关（C 错）。我们直接调用 `_terminal_label(-9, True, True, False)` 得到 `"oom"`。退出码 −9（SIGKILL）不会被标成 crash（B 错），因为 oom/timeout 的判断在退出码之前。这样排序的含义是：内存超限是更"具体"的失败原因，对评估器和调参更有信息量。

### Q4 — 答案：B

讲义："The cap is soft because the poller has a non zero interval; a process can spike above the cap between polls and then drop back." 轮询间隔默认 0.05 s，两次采样之间的瞬时峰值看不到；而且 kill 发生在"发现超限"之后，进程实际占用会短暂超过上限（实测 `allocate_mb=400, memory_cap_mb=256` 时记录到的 `peak_rss_mb` 为 309–349 MB，随后被 kill，标签 `oom`、退出码 −9）。

- A 错：RSS 是常驻内存总量，不区分堆栈。
- C 错：超限会 `self._proc.kill()`。
- D 错：`bytearray`/NumPy 分配并写入的页都计入 RSS，这正是 `allocate_mb` 能触发 OOM 的原因。

### Q5 — 答案：A

逐行看：

1. `{"a": 1}`：dict 且含 `a` → `final = {"a": 1}`。
2. `[1, 2]`：以 `[` 开头，`startswith("{")` 不成立直接跳过（即使能解析也会被 `isinstance(parsed, dict)` 挡掉）。
3. ` {"a": 2, "b": 3}`：先 `strip()` 去掉前导空格，再解析；此时 `final` 非空，旧的 `{"a": 1}` 被追加到 `intermediates`，`final` 更新。
4. `not json {`：不以 `{` 开头，跳过。

实测输出 `({'a': 2, 'b': 3}, [{'a': 1}])`。C 错：解析失败只 `continue`，不会中断；D 错：列表永远不会进入结果。B 把顺序弄反了——"最后一个覆盖行"才是最终指标。

### Q6 — 答案：C

`spec_id=f"{base.spec_id}_{knob}_{value}"`，`value` 用的是 Python 的 `str(1e-4)`，结果是 `'0.0001'`（实测输出 `['p_lr_0.1', 'p_lr_0.0001', ...]`）。B 想当然地以为会保留源码里的写法；A、D 格式不对。附带一点：值里如果有空格或 `/`（例如 `"a b"` 会得到 `"p_lr_a b"`），这个 id 再拿去当文件名就会出问题，生产中常对 value 做规范化或哈希。

### Q7 — 答案：D

同 seed 意味着同一条随机数序列：`rng.normal` 产生的噪声在每个 k 下完全相同，于是 `final_loss` 的差只来自 `0.05 * min(k,32)/32` 这一项。实测 k=4 为 3.620938、k=32 为 3.577188，差 0.04375 = `0.05 × (32−4)/32`，分毫不差。这在统计上叫 common random numbers（公共随机数），能显著降低比较的方差。A、B、C 与 seed 无关。

注意它的另一面：同一个 seed 只是一次抽样，结论可能依赖这个 seed；严谨的做法是"每个 knob 值 × 多个 seed"，再交给 53 节做显著性检验。

### Q8 — 答案：B

`sparsity_experiment.py` 每一步打印的中间行同时带有 `perplexity` 和 `final_loss` 键，正好覆盖 `metric_keys`。超时 kill 后，`communicate(timeout=2.0)` 仍能拿回已经 flush 的输出，`_scan_intermediates` 把"最后一个覆盖行"当成最终指标。我们实测：`terminal='timeout', exit_code=-9, wall_time_s=0.504`，`metrics={'step': 0, 'loss': 4.987525, 'perplexity': 146.573206, 'final_loss': 4.987525}`，`intermediate_metrics=[]`（因为解释器启动 + import numpy 约 0.2 s，0.5 s 内只来得及打印第 0 步）。

A 错：代码对所有情况都扫描 stdout；C 错：脚本根本没跑完；D：代码里没有这种结构。这也是 Q10 要修的问题。

### Q9 — 参考答案

1. **`None` 的三种含义**：
   - 平台既没有 `/proc` 也没有 `ps`（真正的 unsupported）；
   - `ps` 调用失败或超时（`OSError / SubprocessError / ValueError`）；
   - **进程已经不存在**：`/proc/<pid>/status` 不存在，`ps -p <pid>` 输出为空，于是落到最后的 `return None`。实测 `_rss_mb(999999)` 返回 `None`。

   竞态场景：轮询线程刚检查完 `self._proc.poll() is None`，主线程的 `communicate()` 就回收了子进程（`/proc/<pid>` 消失），此时 `_rss_mb` 返回 `None`，轮询器把自己标记为 `unsupported` 并打印"platform does not expose RSS"——而且因为用的是**全局**标志 `_MEMORY_POLLER_UNSUPPORTED_WARNED`，这个误报还会让之后真正的 unsupported 警告不再出现。我们连续跑 60 次快速退出的脚本没有复现，说明窗口很小，但逻辑上存在。另一个边界：`/proc` 存在但没有 `VmRSS` 行（僵尸进程）时返回 `0.0`，会被当成合法采样。

   修法：把"读不到"和"平台不支持"分开——启动时用 `_rss_mb(os.getpid())` 探测一次平台能力；运行中读不到就当作"进程已退出"，`continue`/`return` 但不置 `unsupported`。

2. **硬上限**：在 `Popen` 中加 `preexec_fn`（仅 POSIX，在 fork 后、exec 前于子进程内执行）：

```python
import resource

def _make_limiter(hard_mb: int | None):
    if hard_mb is None:
        return None
    def _limit() -> None:
        nbytes = hard_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (nbytes, nbytes))
    return _limit

proc = subprocess.Popen(
    [self._python, spec.script_path, config_path],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    preexec_fn=_make_limiter(getattr(spec, "hard_memory_mb", None)),
)
```

   `RLIMIT_AS` 限制的是**虚拟地址空间**，不是 RSS：解释器、NumPy 的共享库、线程栈预留都算在内，比 RSS 大得多。实测 `allocate_mb=400` 时，`RLIMIT_AS=512MB` 下脚本以 `MemoryError` 退出（退出码 1，标签会是 `crash`），1024MB 下正常完成。所以硬上限要取"预期 RSS + 明显余量"，并保留软上限做精细监控；超出硬上限时进程收到的是 `MemoryError`（或 malloc 失败），runner 最好解析 stderr 把它也标成 `oom`。生产中更常用 cgroup v2 的 `memory.max`（容器的 `--memory`）——它限制真实内存，并由内核 OOM killer 执行。

### Q10 — 参考答案

问题本质：协议没有区分"中间行"和"最终行"，而 sparsity 脚本的中间行恰好带齐了 `metric_keys`。

思路一：**非 ok 时不暴露最终指标**。保留中间行用于诊断，但 `metrics` 只在 `terminal == "ok"` 时才有值：

```python
        metrics, intermediates = _scan_intermediates(stdout, spec.metric_keys)
        terminal = self._terminal_label(proc.returncode, killed_for_timeout,
                                        poller.killed_for_oom, bool(metrics))
        if terminal != "ok":
            if metrics:
                intermediates.append(metrics)   # 不丢数据，降级为中间行
            metrics = {}
```

思路二：**在协议里显式标记最终行**，例如要求最终行带 `"__final": true`，或把指标写入一个约定好的文件（`<workdir>/metrics.json`），只有脚本正常结束前才写入。runner 只认这个标记 / 文件，`intermediate_metrics` 另走一条通道。

两者可以结合：思路二解决"语义不清"，思路一保证即使脚本不守约，失败运行也不会带出看似合法的数字。还要同步更新测试：例如新增"超时运行的 `metrics` 为空、`intermediate_metrics` 非空"的断言。

### Q11 — 参考答案

1. step=3 时 `5 × 0.9³ = 3.645`，k=16 的公式项 `0.05 × 16/32 = 0.025`，无噪声值 `3.620`。噪声 = `3.602188 − 3.620 = −0.017812`。
2. 同 seed → 同噪声，所以（已用 Python 计算并与运行结果核对）：

| k | 无噪声值 | final_loss | perplexity = e^loss |
|---|---------|-----------|--------------------|
| 4 | 3.63875 | 3.620938 | ≈ 37.37（实测 37.372607） |
| 8 | 3.6325 | 3.614688 | ≈ 37.14（实测 37.139757） |
| 32 | 3.595 | 3.577188 | ≈ 35.77（实测 35.772806） |
| 64 | 3.595 | 3.577188 | 与 k=32 相同，因为 `min(k, 32)` 截断 |

3. 噪声标准差是 0.02，而 k=4 与 k=32 的真实差距只有 0.044（约 2 个标准差）。若每个 k 用不同 seed，各行噪声独立，差值的标准差变为 `0.02·√2 ≈ 0.028`，单次运行的排序就可能被噪声打乱（k=8 与 k=4 之间真实差仅 0.00625，远小于噪声）。共用 seed 让比较更"干净"，但只代表一次抽样；要下结论，应每个 k 跑多个 seed，再做配对检验——这正是 53 节评估器的工作。

### Q12 — 参考答案

1. **3 s 的来历**：1.0 s 时 `communicate` 抛 `TimeoutExpired`，runner `proc.kill()` 只杀死了**直接子进程**；孙进程继承了 stdout/stderr 管道的写端，管道一直不关闭，于是第二次 `communicate(timeout=2.0)` 读不到 EOF，再等 2 s 后又超时，走到 `stdout, stderr = "", ""`。总计约 1 + 2 = 3 s。**输出丢失**：第一次 `communicate` 超时时已经读到的数据只缓存在 `Popen` 内部，第二次又超时后代码直接把 stdout 置为空串，已经 flush 的指标行就这样被丢掉了。
2. 孙进程**还活着**（实测运行结束后仍能找到它，要手动清理），这就是"孤儿实验进程"——它可能继续占 GPU 显存、写文件。修法：让子进程成为新会话 / 进程组的组长，kill 时对整个组发信号：

```python
import os, signal

proc = subprocess.Popen(
    [self._python, spec.script_path, config_path],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    start_new_session=True,                 # 子进程 pgid == pid
)
...
except subprocess.TimeoutExpired:
    killed_for_timeout = True
    try:
        os.killpg(proc.pid, signal.SIGKILL)  # 整个进程组
    except (OSError, ProcessLookupError):
        pass
```

   轮询器里的 `self._proc.kill()` 也要同样改成 `os.killpg`。更稳妥的做法是先发 `SIGTERM` 给脚本一个保存/清理的机会，宽限期后再 `SIGKILL`；容器 / cgroup 方案则可以"一次性冻结并杀死整个 cgroup"。另外，如果仍要"尽量保住部分输出"，第二次 `communicate` 超时时应读取 `TimeoutExpired` 异常上的 `exc.stdout`，而不是直接置空。

### Q13 — 参考回答要点

- **为什么**：生成的代码不可信——可能死循环、内存爆炸、崩溃、调用 `sys.exit`，甚至有害操作。子进程提供独立地址空间和外部 kill 句柄，故障被隔离在实验内部，编排器只收到一条结构化的失败记录。
- **本节提供**：墙钟硬超时；RSS 轮询的软内存上限与峰值记录；stdout/stderr 完整捕获；从不抛异常的结果记录（`ok/timeout/oom/crash`）；临时工作目录（`TemporaryDirectory`，结束即删除）。
- **本节缺少**（讲义："There is no cgroup, no seccomp filter, no namespace remapping"）：
  - 资源：cgroup 限 CPU/内存/GPU、`setrlimit`、磁盘配额；
  - 系统调用：seccomp 过滤危险 syscall；
  - 隔离：mount/PID/network namespace（容器）、只读文件系统、禁网或网络白名单；
  - 进程树管理：进程组 kill（见 Q12）；
  - 更强隔离：gVisor、Firecracker 微虚拟机。
- 加分点：能联系 [阶段 19 · 26](../../26-sandbox-runner-denylist/docs/zh.md) 的拒绝列表 + 路径隔离，说明"拒绝执行"和"限制执行"是两层防线。
- 常见误区：把 `subprocess` 等同于"沙箱"——它只隔离了内存地址空间，文件系统和网络权限与父进程完全相同。

### Q14 — 参考回答要点

- **固定 seed 之后仍可能不确定的来源**：
  - GPU 非确定性算子（atomicAdd 规约、cuDNN 自动选择算法），需要 `torch.use_deterministic_algorithms(True)`、关闭 `cudnn.benchmark`；
  - 多线程 / 多进程 DataLoader 的 worker seed 与读取顺序；
  - 浮点规约顺序随 batch 大小、并行度、硬件变化；
  - 库版本、驱动、CUDA 版本不同；
  - 依赖时间、哈希随机化（`PYTHONHASHSEED`）、文件系统遍历顺序的代码；
  - 分布式训练中的通信顺序。
- **本节的约定**：seed 作为 spec 的一部分，由 runner 统一注入 `config["__seed"]`，脚本负责使用它；实测同 seed 两次运行 `perplexity`、`final_loss` 完全相等（`test_two_runs_same_seed_match`）。
- **评估器如何应对**：
  - 记录完整环境（代码版本、依赖锁文件、硬件）作为结果的一部分；
  - 每个配置跑多个 seed，比较分布而不是单点；
  - 用显著性检验 / 置信区间判断差异（53 节）；
  - 对基线做"重跑一致性"检查：同配置重跑的波动即噪声下限。
- 常见误区：以为"固定 seed = 结果可信"。固定 seed 只保证"可复现"，不保证"有代表性"。

### Q15 — 参考回答要点

- **脆弱点**：
  - 中间行与最终行无法区分（Q8/Q10）；
  - 脚本里任何库打印到 stdout 的 JSON（或以 `{` 开头的日志）都可能被误认为指标；
  - stdout 全部缓存在内存中（`communicate`），输出巨大时 runner 自身内存会膨胀；`stdout_tail` 字段其实保存的是**完整** stdout，只在 `to_dict` 时截取最后 400 字符；
  - 没有 schema：指标类型、单位、方向（越大越好还是越小越好）都不在协议里；
  - 进程被 kill 时最后一行可能只写了一半。
- **生产设计**：
  - 指标写入约定文件（如 `metrics.json`，写临时文件再原子 rename）或通过专门的 fd / socket / 指标服务上报；
  - 带 schema 与版本号（JSON Schema / pydantic），runner 校验后再落库；
  - 中间指标走流式通道（逐步上报到实验追踪系统，如 MLflow / W&B 一类工具），最终指标单独确认；
  - stdout/stderr 流式写入日志文件，内存里只保留尾部；
  - 结果中记录 config 哈希、代码版本、环境信息。
- 加分点：强调"runner 从不抛异常、所有失败都结构化记录"这一原则要保留。

### Q16 — 参考回答要点

- **调度层**：spec 进入队列（优先级来自 56 节的调度器），按资源需求（CPU/GPU/内存）匹配 worker；每个 spec 有 `spec_id`，结果按 id 幂等写入，便于重试。
- **执行层**：每个实验一个容器或 cgroup，限制 GPU（设备可见性）、内存、CPU、磁盘、网络；进程组 / cgroup 级别 kill；超时分为"排队超时"和"运行超时"。
- **数据层**：结果、日志、产物（checkpoint、曲线）写入对象存储；`ExperimentResult` 写数据库，供 53 节评估器读取。
- **可靠性**：失败分类（`oom` 可自动加内存重试一次，`crash` 不重试，`timeout` 视预算决定）；worker 心跳与租约，worker 挂掉时任务重新入队；同一 spec 去重（缓存命中直接返回）。
- **可复现**：镜像版本固定、seed 由 spec 统一给定、环境指纹写入结果。
- **成本控制**：每个假设设预算上限；先用小 `steps` 的廉价筛选，再对有希望的配置做完整运行（successive halving 思路）。
- 常见误区：直接在一台机器上起几千个 `subprocess` 而不做资源隔离，一个 OOM 实验就能拖垮整台机器上的其它实验。

### Q17 — 参考回答要点

- **单 knob 的优点**（讲义）：全因子扫描随 knob 数指数增长，结果难以解读；单 knob 给出一条"干净的坐标轴"，评估器可以直接画图。
- **局限**：
  - 看不到**交互作用**：例如学习率的最优值依赖 batch size，单独扫学习率得到的"最优"只在当前 batch size 下成立；
  - 依赖基准点：在一个糟糕的 base 上做消融，结论可能不能迁移；
  - 逐个 knob 贪心调优可能陷入局部最优。
- **何时需要多因素**：怀疑存在强交互（学习率 × batch size、正则 × 数据量）时，做小规模的 2×2 或 3×3 factorial；knob 多、预算有限时用随机搜索、拉丁超立方或贝叶斯优化，而不是网格。
- **本节的立场**：只支持单 knob，多 knob 由调用方"重复单 knob 消融"组合实现，保持 runner 简单；更复杂的搜索策略属于调度器（56 节）。
- 加分点：消融的本意是"移除/改变一个组件看贡献"，与超参搜索目标不同；消融结论最好配多 seed 与显著性检验。

---

## 六、关联知识点

### 前置知识
- [阶段 19 · 20 Agent Harness 的循环契约](../../20-agent-harness-loop-contract/docs/zh.md)：讲义把 Track A（20–29 节）列为先修，本节的"从不抛异常、结构化结果"延续了 harness 的契约思想。
- [阶段 19 · 26 带拒绝列表与路径隔离的 Sandbox 执行器](../../26-sandbox-runner-denylist/docs/zh.md)：同样是 `subprocess` + 超时 + 输出截断，并多了拒绝列表与路径隔离，可与本节对照。
- [阶段 19 · 50 研究假设生成器](../../50-hypothesis-generator/docs/zh.md)：`hypothesis_id` 的来源。
- [阶段 19 · 51 文献检索](../../51-literature-retrieval/docs/zh.md)：先过滤掉文献已解决的假设，剩下的才交给本节执行。
- [阶段 13 · 26 Skill 权限、Sandboxes 与信任](../../../13-tools-and-protocols/26-skill-permissions-sandboxes-and-trust/docs/zh.md)：沙箱与信任边界的协议层视角。

### 本节被哪些后续内容用到
- [阶段 19 · 53 结果评估器](../../53-result-evaluator/docs/zh.md)：读取 `terminal` 与 `metrics`，对非 ok 运行自动判失败，对 ok 运行做显著性检验。
- [阶段 19 · 54 论文写作器](../../54-paper-writer/docs/zh.md)：消融表、实验结果被写进论文的实验章节。
- [阶段 19 · 56 迭代调度器](../../56-iteration-scheduler/docs/zh.md)：把多个 spec 并行投入实验槽位，消费本节的结果。
- [阶段 19 · 57 端到端研究演示](../../57-end-to-end-research-demo/docs/zh.md)：把 runner 与其它组件串成完整的自动研究循环。

### 延伸关键词
`subprocess.Popen` · `communicate(timeout=)` · `TimeoutExpired` · `RSS / VmRSS` · `resource.setrlimit / RLIMIT_AS` · `cgroup v2 memory.max` · `seccomp` · `namespace` · `start_new_session / os.killpg` · `common random numbers` · `ablation study` · `factorial design` · `reproducibility`
