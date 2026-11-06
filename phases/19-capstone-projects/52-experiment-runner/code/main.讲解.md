# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 52 节 实验执行器 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（在 `code/` 目录下；测试：`python3 -m pytest -q` 或 `python3 -m unittest discover tests`） ｜ **依赖**：`main.py` 本身只用标准库（`subprocess`、`threading`、`tempfile`、`json` 等）；它启动的示例实验脚本 `experiments/sparsity_experiment.py` 需要 `numpy`

---

## 1. 这份代码在考察什么

这是自动研究循环（50 生成假设 → 51 查文献 → **52 跑实验** → 53 评估）里负责"执行"的一环。它要回答一个问题：**怎样运行一段不可信的实验代码，并拿回一份评估器可以信任的结果记录？**

具体考察：

1. **子进程隔离**：`subprocess.Popen` 启动独立解释器，父进程握有 kill 句柄。
2. **两种资源限制**：墙钟硬超时（`communicate(timeout=)`）与基于 RSS 轮询的软内存上限（后台线程）。
3. **结果协议**：脚本在 stdout 打印 JSON 行，runner 取"最后一个覆盖全部 `metric_keys` 的行"为最终指标，其余覆盖行作为学习曲线。
4. **失败分类**：`ok / timeout / oom / crash` 四种 terminal，runner 自己**从不抛异常**。
5. **消融（ablation）**：固定 base spec，一次只改一个 knob。
6. **确定性**：seed 写进 config 转发给脚本，同 seed 结果完全一致。

> 一句话：**把"跑一个实验"包装成一个永远会返回、而且返回值语义明确的函数调用**。讲义也坦白它"不是完整沙箱"——看清它缺什么，和看懂它做了什么同样重要。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `ExperimentSpec` | dataclass | 描述一次实验：脚本路径、config、seed、超时、内存上限、指标键 | 实验契约 |
| `ExperimentResult` | dataclass | 一次运行的全部结果：退出码、terminal、耗时、峰值 RSS、指标、输出 | 结果契约 |
| `_rss_mb` | 函数 | 读 `/proc/<pid>/status` 的 `VmRSS`，否则用 `ps`，都不行返回 `None` | RSS 采样 |
| `_MemoryPoller` | `threading.Thread` 子类 | 每 0.05 s 采样一次 RSS，记录峰值，超限 kill | 软内存上限 |
| `_scan_intermediates` | 函数 | 扫描 stdout，返回 `(最终指标, 中间指标列表)` | 指标协议 |
| `ExperimentRunner` | 类 | 写临时 config → 启动子进程 → 超时 / OOM 处理 → 组装结果 | 执行器主体 |
| `_terminal_label` | 静态方法 | 按 `oom → timeout → ok/crash` 给出标签 | 失败分类 |
| `ablate` | 函数 | 由 base spec 派生每个 knob 值的 spec | 单 knob 消融 |
| `AblationTable` / `AblationRunner` | dataclass / 类 | 依次运行派生 spec，收集 `(value, result)` | 消融表 |
| `_demo` | 函数 | 跑一次 base，再对 `k ∈ {4, 8, 16, 32}` 做消融，打印 JSON | 演示 |

数据流：`ExperimentSpec` → `run()` 合并 `__seed` 写入临时 `config.json` → `Popen([python, script, config_path])` → 主线程 `communicate(timeout)` ‖ 轮询线程采样 RSS → `_scan_intermediates(stdout)` → `_terminal_label(...)` → `ExperimentResult` →（消融时）`AblationTable` → `json.dumps` 打印。

---

## 3. 逐段精讲

### 3.1 两个 dataclass：实验契约与结果契约

```python
@dataclass
class ExperimentSpec:
    spec_id: str
    hypothesis_id: int
    script_path: str
    config: dict
    seed: int = 0
    wall_timeout_s: float = 30.0
    memory_cap_mb: int = 512
    metric_keys: list[str] = field(default_factory=list)
```

- 字段与讲义"ExperimentSpec shape"一一对应。`hypothesis_id` 把结果链接回 50 节的假设队列。
- `metric_keys` 用 `field(default_factory=list)`：dataclass 不允许可变对象作默认值，否则所有实例会共享同一个列表。
- `to_dict()` 里写 `dict(self.config)`、`list(self.metric_keys)` 是**浅拷贝**，防止调用方修改返回的字典时改坏 spec 本身。

```python
    def to_dict(self) -> dict:
        return {
            ...
            "wall_time_s": round(self.wall_time_s, 4),
            "peak_rss_mb": None if self.peak_rss_mb is None else round(self.peak_rss_mb, 2),
            ...
            "stdout_tail": self.stdout_tail[-400:],
            "stderr_tail": self.stderr_tail[-400:],
        }
```

- `ExperimentResult.to_dict` 负责"展示层"处理：耗时保留 4 位、RSS 保留 2 位，stdout/stderr 只保留**最后 400 个字符**。
- 注意：字段名叫 `stdout_tail`，但对象里实际存的是**完整** stdout（见 3.6），截断只发生在 `to_dict` 里。输出很大时这会占用 runner 进程的内存。
- 讲义中 `ExperimentSpec` 的注释写 config "passed to the script as one json arg"，实际上传的是**临时文件路径**（讲义后文也是这么说的），以代码为准。

### 3.2 `_rss_mb`：尽力而为地读取常驻内存

```python
def _rss_mb(pid: int) -> float | None:
    proc_status = f"/proc/{pid}/status"
    if os.path.exists(proc_status):
        try:
            with open(proc_status, "rt", encoding="utf-8") as fh:
                for line in fh:
                    if line.startswith("VmRSS:"):
                        parts = line.split()
                        if len(parts) >= 2:
                            return float(parts[1]) / 1024.0
        except OSError:
            return None
        return 0.0
    if shutil.which("ps"):
        ...  # ps -o rss= -p <pid>
    return None
```

- Linux 的 `/proc/<pid>/status` 有一行形如 `VmRSS:   32432 kB`，`split()` 后取第 2 项，除以 1024 得到 MB。
- 没有 `/proc` 的平台（macOS）退而用 `ps -o rss= -p <pid>`（`rss=` 表示不要表头），单位也是 KB。讲义只提到 `/proc`，代码多了 `ps` 这一层兜底。
- `/proc` 存在但没有 `VmRSS` 行（例如僵尸进程）时返回 `0.0`。
- ⚠️ 返回 `None` 同时表示"平台不支持""`ps` 出错"和"进程已经不存在"三种情况（实测 `_rss_mb(999999)` 返回 `None`）。轮询器把 `None` 一律解读成"平台不支持"，存在误报的竞态窗口，详见测验 Q9。

### 3.3 `_MemoryPoller`：可停止的后台轮询线程

```python
class _MemoryPoller(threading.Thread):
    def __init__(self, proc, cap_mb, interval_s=0.05):
        super().__init__(daemon=True)
        ...
        self._stop_event = threading.Event()
        self.peak_rss_mb: float | None = None
        self.killed_for_oom = False
        self.unsupported = False

    def run(self) -> None:
        global _MEMORY_POLLER_UNSUPPORTED_WARNED
        while not self._stop_event.is_set() and self._proc.poll() is None:
            rss = _rss_mb(self._proc.pid)
            if rss is None:
                self.unsupported = True
                if not _MEMORY_POLLER_UNSUPPORTED_WARNED:
                    _MEMORY_POLLER_UNSUPPORTED_WARNED = True
                    _LOGGER.warning("memory poller disabled: ...")
                return
            self.peak_rss_mb = rss if self.peak_rss_mb is None else max(self.peak_rss_mb, rss)
            if rss > self._cap:
                self.killed_for_oom = True
                try:
                    self._proc.kill()
                except OSError:
                    pass
                return
            self._stop_event.wait(self._interval)
```

- **`daemon=True`**：守护线程不会阻止解释器退出，即使忘了 `join` 也不会让程序挂住。
- **循环条件**：主线程没有叫停（`_stop_event`）且子进程仍在运行（`poll() is None`）。
- **`self._stop_event.wait(self._interval)`** 而不是 `time.sleep`：主线程调用 `stop()` 后能立刻唤醒退出，而不必等满一个间隔。
- **峰值记录**：讲义："The runner records the maximum observed RSS so the evaluator can see how close the run came to the limit."
- **超限即 kill**：`killed_for_oom` 标志由主线程在之后读取。这里"跨线程读写一个布尔"在 CPython 中是安全的（GIL 保证赋值原子），且主线程在 `join` 之后才读。
- **"一次性警告"**：用模块级全局变量 `_MEMORY_POLLER_UNSUPPORTED_WARNED`，整个进程只警告一次；墙钟超时不受影响。
- 为什么是"软"上限：间隔 0.05 s 内的尖峰看不到，而且 kill 发生在"已经超过"之后。实测 `allocate_mb=400, memory_cap_mb=256` 时记录到的峰值为 309–349 MB。

### 3.4 `_scan_intermediates`：从 stdout 里挑出指标

```python
    intermediates: list[dict] = []
    final: dict = {}
    required = set(metric_keys)
    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if not line.startswith("{"):
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(parsed, dict):
            continue
        if required and not required.issubset(parsed.keys()):
            continue
        if final:
            intermediates.append(final)
        final = parsed
    return final, intermediates
```

- 四道过滤：不以 `{` 开头 → 解析失败 → 不是 dict → 不包含全部必需键，任何一道不过都 `continue`，**绝不抛异常**。
- "滚动替换"技巧：每遇到一个合格行，就把上一个 `final` 推进 `intermediates`，自己成为新的 `final`。扫描结束时，`final` 自然是最后一个合格行。
- `required` 为空集时（`metric_keys=[]`），任何 JSON 对象都合格（测试 `test_no_required_keys_takes_last_json`）。
- ⚠️ 讲义说"Earlier json lines are kept in the result as `intermediate_metrics`"，代码只保留**覆盖了 `metric_keys` 的**较早行；缺键的 JSON 行被直接丢弃（测试 `test_ignores_lines_missing_keys` 明确断言了这一行为）。
- ⚠️ 协议不区分"中间行"和"最终行"。`sparsity_experiment.py` 的中间行也带有 `perplexity`、`final_loss`，于是 demo 中 4 个中间行全部进入 `intermediate_metrics`；而超时运行里，最后一条中间行会被当成"最终指标"（测验 Q8、Q10）。

### 3.5 `ExperimentRunner.run`：临时目录与 seed 注入

```python
    def run(self, spec: ExperimentSpec) -> ExperimentResult:
        with tempfile.TemporaryDirectory(prefix="exp_") as workdir:
            config_path = os.path.join(workdir, "config.json")
            merged_config = dict(spec.config)
            merged_config["__seed"] = spec.seed
            with open(config_path, "w", encoding="utf-8") as fh:
                json.dump(merged_config, fh)
            return self._run_subprocess(spec, config_path)
```

- `TemporaryDirectory` 作为上下文管理器：`with` 块结束（包括 `return` 和异常）时目录被递归删除，不留垃圾。
- `dict(spec.config)` 先复制再写 `__seed`，**不修改调用方的 spec**——这对消融很重要，因为多个 spec 可能共享 base 的数据。
- `__seed` 用双下划线前缀，避免与用户的 knob 名冲突。讲义："The runner forwards the seed to the script via the config dict (`config["__seed"] = spec.seed`)."
- 注意：子进程的工作目录（cwd）仍是父进程的 cwd，不是 `workdir`；脚本若写相对路径文件，会写到父进程目录里。生产中通常加 `cwd=workdir`。

### 3.6 `_run_subprocess`：启动、超时、收尾

```python
        start = time.perf_counter()
        try:
            proc = subprocess.Popen(
                [self._python, spec.script_path, config_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except OSError as exc:
            ...
            return ExperimentResult(..., exit_code=-1, terminal="crash", ..., stderr_tail=str(exc))
```

- 用**列表形式**的 argv（不经过 shell），不存在 shell 注入问题。`self._python` 默认是 `sys.executable`，即当前解释器。
- `Popen` 本身失败（解释器路径不存在等）也不抛异常，而是包装成一条 `crash` 结果。脚本路径不存在则不会走这里——解释器能启动，只是自己以退出码 2 结束（实测 `terminal='crash', exit_code=2`，stderr 为 `can't open file ...`）。
- `time.perf_counter()` 是单调高精度计时器，适合测耗时（不受系统时间调整影响）。

```python
        poller = _MemoryPoller(proc, spec.memory_cap_mb, self._poll_interval)
        poller.start()
        killed_for_timeout = False
        try:
            stdout, stderr = proc.communicate(timeout=spec.wall_timeout_s)
        except subprocess.TimeoutExpired:
            killed_for_timeout = True
            try:
                proc.kill()
            except OSError:
                pass
            try:
                stdout, stderr = proc.communicate(timeout=2.0)
            except subprocess.TimeoutExpired:
                stdout, stderr = "", ""
        finally:
            poller.stop()
            poller.join(timeout=1.0)
```

- **为什么用 `communicate` 而不是 `wait`**：`communicate` 同时读 stdout 和 stderr 直到 EOF。如果只 `wait()`，子进程输出超过管道缓冲区（Linux 默认 64 KB）就会阻塞在写管道上，父子互相等待——经典死锁。
- **超时流程**：这正是 Python 官方文档推荐的写法——`TimeoutExpired` 后 `kill()`，再 `communicate()` 收集剩余输出并回收进程（避免僵尸进程）。
- **第二次 `communicate(timeout=2.0)`**：kill 之后正常情况下管道立即关闭，能拿回已经 flush 的部分输出（这就是超时运行仍有 `metrics` 的原因）。
- `finally` 保证无论哪条路径都停止并回收轮询线程。
- ⚠️ `proc.kill()` 只杀直接子进程。如果脚本又起了子进程，孙进程持有管道写端，第二次 `communicate` 也会超时，代码把 stdout 置为空串——**已经打印的输出全部丢失**，孙进程继续存活。实测 `wall_timeout_s=1.0` 时耗时 3.01 s、`metrics={}`、`stdout_tail=''`，结束后孙进程仍在运行。修法是 `start_new_session=True` + `os.killpg`（测验 Q12）。

```python
        wall = time.perf_counter() - start
        metrics, intermediates = _scan_intermediates(stdout, spec.metric_keys)
        terminal = self._terminal_label(proc.returncode, killed_for_timeout, poller.killed_for_oom, bool(metrics))
        return ExperimentResult(
            ...
            exit_code=proc.returncode if proc.returncode is not None else -1,
            ...
            stdout_tail=stdout,
            stderr_tail=stderr,
        )
```

- 被 SIGKILL 杀死的进程在 POSIX 上 `returncode` 为 **−9**（负数表示"被信号 N 终止"）。
- `returncode` 可能仍为 `None`（两次 `communicate` 都超时、进程尚未被回收），此时记为 −1。

### 3.7 `_terminal_label`：失败分类

```python
    @staticmethod
    def _terminal_label(exit_code, timed_out, oomed, have_metrics) -> str:
        if oomed:
            return "oom"
        if timed_out:
            return "timeout"
        if exit_code == 0 and have_metrics:
            return "ok"
        if exit_code == 0 and not have_metrics:
            return "crash"
        return "crash"
```

实测真值表：

| exit_code | timed_out | oomed | have_metrics | 结果 |
|-----------|-----------|-------|--------------|------|
| 0 | F | F | T | `ok` |
| 0 | F | F | F | `crash` |
| 1 | F | F | T | `crash`（讲义："Any non zero exit is labelled crash even when the script printed metrics"） |
| −9 | T | F | T | `timeout` |
| −9 | F | T | F | `oom` |
| −9 | T | T | F | `oom`（OOM 优先） |
| None | F | F | F | `crash` |

- `@staticmethod`：方法不需要 `self`，可以直接 `ExperimentRunner._terminal_label(...)` 调用，便于单独测试。
- 第 4 个 `if` 与最后的 `return` 结果相同，是"为可读性写出的冗余分支"。
- 设计含义：只有"干净退出 + 交出指标"才算成功；评估器看到非 `ok` 就自动判失败，不会把半截运行的数字拿去做显著性检验。

### 3.8 `ablate`、`AblationTable`、`AblationRunner`

```python
def ablate(base: ExperimentSpec, knob: str, values: Iterable[Any]) -> list[ExperimentSpec]:
    specs: list[ExperimentSpec] = []
    for value in values:
        derived_config = dict(base.config)
        derived_config[knob] = value
        specs.append(ExperimentSpec(
            spec_id=f"{base.spec_id}_{knob}_{value}",
            ...
            seed=base.seed,
            ...
            metric_keys=list(base.metric_keys),
        ))
    return specs
```

- 每个值复制一份 config 再覆盖 knob，**其它字段（包括 seed）全部继承**——这就是"一次只动一个变量"。
- `spec_id` 用 `str(value)` 拼接：`1e-4` 会变成 `0.0001`，字符串值里的空格会原样保留。
- 讲义中 `ablate` 签名是 `values: list[Any]`，代码放宽为 `Iterable[Any]`。

```python
    def sweep(self, base, knob, values) -> AblationTable:
        value_list = list(values)
        rows = []
        for value, spec in zip(value_list, ablate(base, knob, value_list)):
            result = self._runner.run(spec)
            rows.append((value, result))
        return AblationTable(knob=knob, rows=rows)
```

- 先 `list(values)` 物化：`values` 可能是生成器，只能遍历一次，而这里要遍历两次（传给 `ablate`、再与结果 `zip`）。这是一个很实用的细节。
- 串行执行，每行一个 `(value, ExperimentResult)`。讲义说"keyed by knob value"，实际是**有序的元组列表**而不是 dict（值可能不可哈希，比如列表）。
- `AblationTable.to_dict` 把每行转成 `{"value": v, "result": r.to_dict()}`，便于 JSON 输出。

### 3.9 `_demo` 与入口

```python
    base = ExperimentSpec(
        spec_id="demo_base", hypothesis_id=1, script_path=script,
        config={"k": 16, "steps": 4, "sleep_s": 0.0},
        seed=7, wall_timeout_s=15.0, memory_cap_mb=256,
        metric_keys=["perplexity", "final_loss"],
    )
    runner = ExperimentRunner()
    base_result = runner.run(base)
    sweep = AblationRunner(runner).sweep(base, "k", [4, 8, 16, 32])
```

- 脚本路径用 `os.path.dirname(os.path.abspath(__file__))` 拼出，与当前工作目录无关——在任何目录下运行 `python3 path/to/main.py` 都能找到 `experiments/`。
- base 的 `k=16` 与消融行 `k=16` 配置、seed 完全相同，可以直接用来观察确定性。
- 文件 docstring 说 "Stdlib only. Run: python3 code/main.py"——`main.py` 确实只用标准库，但 demo 依赖的实验脚本需要 NumPy。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 子进程而非进程内 import | 独立地址空间 + kill 句柄，崩溃不波及编排器 | 每次启动解释器 + import 约 0.2 s；生产用容器 / 微虚拟机加强隔离 |
| `communicate(timeout)` 实现硬超时 | 标准库原生、跨平台、避免管道死锁 | 只 kill 直接子进程；应用进程组或 cgroup 整体终止 |
| RSS 轮询的软内存上限 | 可移植，无需 POSIX 专有 API | 间隔内尖峰漏检；生产用 `setrlimit` / cgroup `memory.max` |
| 平台不支持时禁用轮询并只警告一次 | 不让监控失败阻塞实验 | `None` 语义混杂可能误报（测验 Q9） |
| stdout 最后一行 JSON 作为指标 | 脚本只需 `print`，几乎零接入成本 | 无法区分中间 / 最终行；生产用指标文件或上报 API |
| 非零退出一律 `crash` | 半截运行默认算失败，评估器不必猜 | 丢失"跑完但退出码异常"的细节，需看 stderr |
| runner 从不抛异常 | 编排器只需处理一种返回类型 | 调用方必须检查 `terminal`，不能只看 `metrics` |
| 单 knob 消融、串行执行 | 结果可解释、可画图，代码简单 | 看不到交互作用；无并行，需交给 56 节调度器 |
| 消融各行共用 seed | 公共随机数，差异只来自 knob | 只有一次抽样，结论需多 seed 验证 |
| `stdout_tail` 存完整输出、只在 `to_dict` 截断 | 实现简单，调试时信息完整 | 大输出时 runner 内存膨胀；应流式写日志文件 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 注解延迟求值，让 `float \| None`、`list[str]` 等写法在旧版本也能用 |
| `@dataclass` | `class ExperimentSpec:` | 自动生成 `__init__`、`__repr__`、`__eq__` |
| `field(default_factory=list)` | `metric_keys: list[str] = field(default_factory=list)` | 可变默认值必须用工厂函数，每个实例一份新列表 |
| 类型注解与 `X \| None` | `peak_rss_mb: float \| None` | 联合类型（Python 3.10+ 语法） |
| `typing.Iterable / Any` | `values: Iterable[Any]` | 接受任意可迭代对象 |
| 模块级 logger | `_LOGGER = logging.getLogger(__name__)` | 按模块名区分日志来源 |
| `global` 声明 | `global _MEMORY_POLLER_UNSUPPORTED_WARNED` | 在函数内给模块级变量赋值 |
| 继承 `threading.Thread` | `class _MemoryPoller(threading.Thread)` + `run()` | 重写 `run`，`start()` 后在新线程执行 |
| `super().__init__(daemon=True)` | `_MemoryPoller.__init__` | 调用父类构造函数，设置为守护线程 |
| `threading.Event` | `self._stop_event.wait(self._interval)` | 可被其它线程立即唤醒的"可中断 sleep" |
| `with` 上下文管理器 | `with tempfile.TemporaryDirectory(...) as workdir:`、`with open(...) as fh:` | 退出块时自动清理目录 / 关闭文件 |
| `try / except / finally` | `_run_subprocess` | `finally` 无论成功失败都执行 |
| 多个异常类型 | `except (OSError, subprocess.SubprocessError, ValueError):` | 元组捕获多种异常 |
| `subprocess.Popen` | `Popen([...], stdout=PIPE, stderr=PIPE, text=True)` | 非阻塞启动子进程；`text=True` 自动解码为 `str` |
| `subprocess.run` | `_rss_mb` 中调用 `ps` | 一次性运行并等待结束，`capture_output=True` 收集输出 |
| `@staticmethod` | `_terminal_label` | 不依赖实例状态的方法 |
| 条件表达式 | `rss if self.peak_rss_mb is None else max(...)` | 一行 if/else |
| 集合运算 | `required.issubset(parsed.keys())` | 判断"全部必需键都在" |
| `isinstance` | `isinstance(parsed, dict)` | 运行时类型检查 |
| f-string | `f"/proc/{pid}/status"`、`f"{base.spec_id}_{knob}_{value}"` | 字符串插值 |
| 切片取尾部 | `self.stdout_tail[-400:]` | 负索引从末尾计数 |
| 列表推导式 | `[dict(m) for m in self.intermediate_metrics]` | 逐个浅拷贝 |
| `zip` | `zip(value_list, ablate(...))` | 并行遍历两个序列 |
| `json.dump / dumps / loads` | `json.dumps({...}, indent=2)` | 序列化 / 反序列化；`indent` 美化输出 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 demo，被测试 import 时不执行 |

---

## 6. 运行结果解读

实际运行（Python 3.13，`cd code && python3 main.py`，总耗时约 1.5 s），输出是一个大 JSON，摘录如下：

```text
"base": {
  "spec_id": "demo_base", "exit_code": 0, "terminal": "ok",
  "wall_time_s": 0.2311,          ← 主要是解释器启动 + import numpy
  "peak_rss_mb": 32.43,           ← 轮询观测到的峰值，远低于 256 MB 上限
  "metrics": {"perplexity": 36.678399, "final_loss": 3.602188,
              "steps_completed": 4, "k": 16, "seed": 7},
  "intermediate_metrics": [ step 0: loss 4.975025 / ppl 144.75,
                            step 1: 4.480975 / 88.32,
                            step 2: 4.019517 / 55.67,
                            step 3: 3.602188 / 36.68 ],   ← 4 条，学习曲线
  "stdout_tail": "0, \"loss\": 4.975025, ..."            ← 只保留最后 400 字符，开头被截断
  "stderr_tail": ""
}
"ablation": {"knob": "k", "rows": [
  k=4 : perplexity 37.372607, final_loss 3.620938, wall 0.2179, rss 32.07
  k=8 : perplexity 37.139757, final_loss 3.614688, wall 0.2651, rss 25.43
  k=16: perplexity 36.678399, final_loss 3.602188, wall 0.2713, rss 30.05   ← 与 base 完全相同
  k=32: perplexity 35.772806, final_loss 3.577188, wall 0.2930, rss 32.50
]}
```

逐项解读：

- **全部 `terminal: "ok"`**：退出码 0 且最后一行同时含 `perplexity`、`final_loss`。
- **`intermediate_metrics` 有 4 条**：脚本每步打印的中间行也覆盖了 `metric_keys`，于是都被收为中间指标；最后一行（含 `steps_completed`）成为最终指标。第 3 步的中间行与最终行数值相同。
- **确定性**：base 与消融中 k=16 这一行的指标逐位相同——seed 7 下 `rng.normal` 产生同样的噪声。
- **消融趋势**：k 越大 loss 越低，相邻差值 0.00625、0.0125、0.025，正是 `0.05 × Δk/32`；共用 seed 让噪声在各行间抵消。
- **不确定的部分**：`wall_time_s`（0.22–0.29 s）和 `peak_rss_mb`（25–33 MB）每次运行都不同，因为它们取决于系统负载和采样时刻。评估器应只把 `metrics` 当作确定性数据。
- **`stdout_tail` 被截断**：`to_dict` 只保留最后 400 个字符，所以开头是半行 `0, "loss": ...`。

补充探针（自写脚本，运行于 `tmp/` 目录）的结果：

| 场景 | 结果 |
|------|------|
| `allocate_mb=400, memory_cap_mb=256` | `terminal=oom, exit_code=-9, peak_rss_mb≈310–349, metrics={}` |
| `steps=20, sleep_s=0.4, wall_timeout_s=0.5` | `terminal=timeout, exit_code=-9, wall≈0.504 s, metrics=` 第 0 步中间行 |
| `crashing_experiment.py`，`metric_keys=["perplexity"]` | `terminal=crash, exit_code=3, metrics={}`，stderr 含 `simulated failure` |
| 同上但 `metric_keys=[]` | `terminal=crash, exit_code=3, metrics={"step":0,"note":"about to fail"}` |
| `script_path` 不存在 | `terminal=crash, exit_code=2` |
| `metric_keys=["accuracy"]`（脚本不输出） | `terminal=crash, exit_code=0, metrics={}` |
| 脚本派生孙进程、`wall_timeout_s=1.0` | `terminal=timeout, wall≈3.01 s, metrics={}, stdout=''`，孙进程仍存活 |

---

## 7. 动手改一改

1. **（入门）** 把 `_demo` 的消融 knob 换成 `steps`，取值 `[1, 2, 4, 8]`，观察 `intermediate_metrics` 的条数与 `final_loss` 的变化；再把 k 扫到 `[32, 64, 128]`，验证 `min(k, 32)` 的截断。
2. **（入门）** 给 `ExperimentRunner` 加一个 `cwd=workdir` 参数，让脚本在临时目录里运行；写一个脚本往相对路径写文件，确认运行结束后文件随目录一起被删除。
3. **（进阶）** 实现测验 Q10 的修复：非 `ok` 运行把 `metrics` 降级为中间行；补一个测试断言"超时运行 `metrics == {}` 且 `intermediate_metrics` 非空"。
4. **（进阶）** 补齐讲义声称但测试未覆盖的路径：写一个 OOM 测试（`allocate_mb=400, memory_cap_mb=128` → `terminal == "oom"`），再用 `unittest.mock.patch("main._rss_mb", return_value=None)` 写一个"轮询器不支持"测试，断言仍能正常完成且 `peak_rss_mb is None`。
5. **（进阶）** 实现进程组 kill（`start_new_session=True` + `os.killpg`），用测验 Q12 的孙进程脚本验证：耗时回到约 1 s、孙进程被杀死；并在第二次 `communicate` 超时时从 `TimeoutExpired.stdout` 取回部分输出。
6. **（挑战）** 让 `AblationRunner.sweep` 支持 `seeds=[0, 1, 2]`：每个 knob 值跑多个 seed，表格中给出均值与标准差；再用 `concurrent.futures.ThreadPoolExecutor` 并行运行（每个线程只负责等待子进程，GIL 不是瓶颈）。

---

## 8. 常见坑

- **用 `wait()` 代替 `communicate()`**：子进程输出超过管道缓冲区时会互相等待，表现为"实验永远不结束"。
- **只 `kill()` 直接子进程**：多进程脚本的孙进程继续运行、占着管道和 GPU，runner 也会多等 2 s 并丢失全部输出。
- **以为软上限能防住 OOM**：轮询间隔内的尖峰可能直接触发系统 OOM killer，杀掉的未必是实验进程。需要硬限制时用 `setrlimit` 或 cgroup，并注意 `RLIMIT_AS` 限的是虚拟内存，取值要留足余量。
- **只看 `metrics` 不看 `terminal`**：超时 / 崩溃的运行也可能带着一条中间行作为 `metrics`。
- **脚本忘了 `flush=True`**：stdout 接到管道时是块缓冲，进程被 kill 前没刷出的行就丢了；本节示例脚本每次 `print` 都 `flush=True`，这不是多余的。
- **把 `stdout_tail` 当作"尾部"**：对象里存的是完整输出，只有 `to_dict()` 才截断到 400 字符。
- **以为固定 seed 就完全可复现**：`wall_time_s`、`peak_rss_mb` 本身就不确定；真实训练还受 GPU 非确定性算子、多线程等影响。
- **消融时修改了 base 的 config**：`ablate` 用 `dict(base.config)` 复制后再改；如果 config 里有嵌套字典，浅拷贝仍会共享内层对象，修改内层值要用 `copy.deepcopy`。

---

## 9. 测试在验证什么

测试文件：`code/tests/test_runner.py`（`unittest` 风格，pytest 也能收集）。它把 `code/` 加入 `sys.path` 后 `from main import ...`，并通过 `make_spec(**overrides)` 工厂函数生成默认 spec（`k=8, steps=3, seed=7, metric_keys=["perplexity","final_loss"]`），每个测试只覆盖自己关心的字段。

| 测试类 / 方法 | 验证的性质 |
|--------------|-----------|
| `TestScanIntermediates.test_picks_last_covering_line` | 最后一个覆盖行成为最终指标，较早的覆盖行进入中间列表；非 JSON 的 `noise` 行被忽略 |
| `TestScanIntermediates.test_ignores_lines_missing_keys` | 缺少必需键的 JSON 行既不是最终指标，也**不进入**中间列表 |
| `TestScanIntermediates.test_no_required_keys_takes_last_json` | `metric_keys` 为空时，任意 JSON 对象都合格，取最后一个 |
| `TestRunnerOk.test_success_returns_metrics` | 正常运行：`terminal="ok"`、`exit_code=0`，指标存在且 perplexity > 0 |
| `TestRunnerOk.test_intermediate_metrics_captured` | `steps=4` 时恰好 4 条中间指标，`step` 依次为 0–3 |
| `TestRunnerOk.test_seed_forwarded` | `seed=42` 经 `__seed` 转发后出现在脚本输出的 `metrics["seed"]` 中 |
| `TestRunnerTimeout.test_timeout_terminal` | `steps=20, sleep_s=0.4, wall_timeout_s=0.5` → `terminal="timeout"` |
| `TestRunnerCrash.test_non_zero_exit_is_crash` | `crashing_experiment.py` 退出码 3 → `crash`，stderr 中含 `simulated failure` |
| `TestAblate.test_ablate_creates_one_spec_per_value` | 每个值一个 spec，`spec_id` 为 `test_k_4/8/16`，config 中 k 被正确覆盖 |
| `TestAblate.test_ablation_sweep_returns_table` | `sweep` 返回的表 knob 正确、行数正确、每行 `ok` 且 `metrics["k"]` 等于该行的值 |
| `TestDeterminism.test_two_runs_same_seed_match` | 同 seed 两次运行 perplexity 与 final_loss 完全相等 |

运行方式与实际结果：

```text
$ cd code && python3 -m pytest -q
...........                                                              [100%]
11 passed in 2.23s
```

（`python3 -m unittest discover tests` 同样可以运行。）

测试**没有覆盖**的地方（也是讲义说法与实际不符之处）：

- 讲义说 "The lesson tests cover both paths"（轮询器支持 / 不支持），但测试里既没有 OOM 场景，也没有"平台不支持 RSS"场景；
- `Popen` 抛 `OSError` 的分支；
- 超时运行中 `metrics` 的内容（实际是第 0 步的中间行，见测验 Q8）；
- 孙进程场景下的超时行为。

练习 4 给出了补齐前两项的思路。
