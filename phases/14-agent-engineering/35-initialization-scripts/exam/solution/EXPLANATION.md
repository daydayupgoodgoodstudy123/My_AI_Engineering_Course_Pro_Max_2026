# 参考答案讲解：InitProbe（14/35）

计时结束后再看。参考实现在同目录的 `initprobe/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修探针运行器

**现象**：解锁后第一个失败的断言在 dependencies 探针上：它是 fail，detail 是 `FileNotFoundError: [Errno 2] No such file or directory: '…/repo/src/app/requirements.txt'`。这个探针没有 bug，它只是去读钉好的 manifest 路径。

**顺着往上找**：路径里多了 `src/app`，正是测试 chdir 进去、模拟 pre-task hook 启动 init 的目录。路径是测试一开始用 `pin_paths(repo, LAYOUT)` 钉的，而 `pin_paths` 用 `Path(rel).resolve()` 按进程的当前目录解析相对路径，`root` 根本没用上。在仓库根目录跑 init 时碰巧是对的；从子目录启动时，`pin_paths` 不报错，错误要等到下游读文件的探针才露出来。课里的探针表说 Repo paths："Hard-coded paths drift; resolve them once and pin."

**依次修五处**：

1. `pin_paths` 相对仓库根解析一次：`(Path(root) / rel).resolve()`。root 可以是相对路径（`git rev-parse --show-cdup` 打印的就是 `../../`），所以要 resolve 成绝对、规范化的路径再钉住：只拼起来不 resolve，钉住的还是相对路径；`absolute()` 留着 `..`，和从别处钉住的同一个文件比较不相等。也不要 `os.chdir(root)`：init 和 agent 共用一个进程，工作目录是整个进程的状态。
2. `_timed` 只把慢的 pass 变成 warn，条件里要有 `status == "pass"`。起始代码把所有超过预算的结果都改成 warn，于是又慢又失败的 test_command 回来是 warn，detail 后面还多了 slow 说明。block 探针的 warn 不阻止启动，这等于把一个 fail 吞掉了，违反 Fail loud。课里说超过三秒的探针是 workbench smell，是提醒，不改变探针的结论；测验 Q6 和代码讲解 3.2 也都说慢的 fail 原样保留。写成 `status != "fail"` 也不对：慢的 warn 会被加上 slow 说明，而 docstring 说其他状态原样。
3. 计时换成 `time.monotonic()`。测试在探针运行时把墙钟往前拨 1 小时、再往回拨 2 小时，`time.time()` 会算出 3600000ms（于是一个瞬间完成的 pass 被降成 warn）和负数。`time.time_ns()` 一样是墙钟；`process_time()` 只算 CPU 时间，sleep 不算，慢探针就判不出来了。
4. `lock_is_fresh` 最后改成 `0 <= age < LOCK_TTL_S`。时钟被拨回过、或者有人手改了锁文件，时间戳就在未来，年龄没法相信。`abs(age)`、“容忍一分钟偏差”、按整秒算 age（`int()` 或 `round()` 会把半秒之后的时间戳算成 0）都会放过它。
5. `fingerprint` 把 manifest 和排好序的名字各哈希一次。起始代码每处理一个名字，就把 manifest 和到目前为止的全部名字重新序列化、哈希一遍，是 O(n²)：5000 个探针写一次锁再查一次要 0.76–0.81 秒，改完不到 1ms。最后一轮哈希的输入和一次哈希的输入完全一样，所以指纹的值不变，已经写下的锁照样有效。init 每次启动都要查锁，锁本来是为了让热路径变便宜，查锁本身不能比它省下的探针还慢。给慢版本加缓存没用：每次启动都是新进程，第一次算照样慢。

```python
def pin_paths(root: str | Path, layout: dict[str, str]) -> dict[str, Path]:
    return {name: (Path(root) / rel).resolve() for name, rel in layout.items()}


async def _timed(probe: Probe) -> Result:
    started = time.monotonic()
    try:
        status, detail = await probe.check()
    except Exception as exc:
        status, detail = "fail", f"{type(exc).__name__}: {exc}"
    duration_ms = int((time.monotonic() - started) * 1000)
    if status == "pass" and duration_ms > probe.budget_s * 1000:
        status = "warn"
        detail = f"{detail} (slow: {duration_ms}ms > {int(probe.budget_s * 1000)}ms)"
    return Result(probe.name, status, detail, duration_ms)


def fingerprint(manifest: str, probes: list[Probe]) -> str:
    h = hashlib.sha256()
    h.update(manifest.encode())
    h.update(b"\0" + json.dumps(sorted(probe.name for probe in probes)).encode())
    return h.hexdigest()[:16]
```

**起始代码已经做对的三件事**，测试照样检查，修别处时不能改坏：

- 探针抛异常变成它自己的 fail。测试里的 env 探针有自己的 bug（`env["OPENAI_API_KEY"]` 抛 KeyError），`_timed` 接住它，detail 是 `KeyError: 'OPENAI_API_KEY'`，照常计时，其他探针照跑。课里的 fail in one place 指的就是这个：一个探针坏了，报告里只有它一行是 fail。接的是 `Exception`，不是 `BaseException`：Ctrl-C 和任务取消（`asyncio.CancelledError` 从 3.8 起继承 BaseException）必须还能停下 init。
- `run_probes` 用 `asyncio.gather`。200 个各 10ms 的探针一起跑约 13ms，一个接一个约 2.3 秒；`gather` 按传入顺序返回结果，报告仍按探针列出的顺序。计时在 `_timed` 里、每个探针各算各的：把整批的耗时发给每个探针，瞬间完成的探针也会显示 50ms。
- 指纹覆盖排好序的探针名。只哈希 manifest 时，新加的探针在锁有效的 24 小时里一次都不会跑。要排序，因为列出顺序不影响结论；只用名字，不用 repr，因为 repr 里有函数地址，下一个进程永远对不上；也不能用 Python 的 `hash()`，它在每个进程里的随机种子不同，测试会另起一个进程算指纹来比。

## Part 2 运行历史

一次运行一行 JSON，文件只追加、不重写。每次 append 都用 `"a"` 打开、写一行、关闭，写完就在磁盘上，另一个读者马上能读到：

```python
def append(self, report: InitReport) -> None:
    _check(report)
    line = json.dumps(_encode(report)) + "\n"
    with self.path.open("a", encoding="utf-8") as f:
        f.write(line)
```

精度和格式上要注意的几点：

- **一行一次运行**：`to_json()` 里的 `indent=2` 是给 init_report.json 用的，历史文件里一次运行只能占一行。
- **时间戳**：Python 的 float 经过 `json.dumps` 和 `json.loads` 能逐位还原。写成 ISO 8601 或者四舍五入到微秒，`1761955200.1234567` 就回不来了。
- **耗时**：整数毫秒原样存。存成秒再乘回来是 float，`int()` 截断时 1003ms 会变成 1002ms。
- **顺序和类型**：results 存成列表，保持探针列出的顺序；读回来的是 `Result` 和 list，不是 dict 或 tuple。
- **先检查再写**：负的耗时（Part 1 时钟 bug 的产物）、不是整数的耗时、未知状态都拒绝，而且被拒绝的运行一个字节也不写。
- **坏行要喊出来**：`runs()` 逐行解析，哪一行不是一次运行就报 ValueError，带上文件里的行号。跳过坏行的历史恰好会藏起人要找的那一次。

`last_ready()` 从后往前找第一个 `exit_code == 0` 的运行。按时间戳取最大值不对：测试最后追加的那次运行发生在时钟被拨回之后，时间戳反而更早，可它才是最近一次。

## Part 3 探针编排

先校验，再运行。`check_probes` 检查名字不重复、severity 只能是 block/warn/info、needs 里的名字都存在、needs 不成环（深度优先，路径上再遇到自己就是环）。任何一条不满足都抛 ProbeConfigError，一个探针都不跑。拖到运行时才发现的话，未知依赖报 KeyError，成环的会互相等待到超时。

运行时每个探针一个任务，先等它 needs 里的探针的结果，再决定跑还是跳过：

```python
async def one(index: int, probe: Probe) -> None:
    behind: set[str] = set()  # the failed probes that keep this one from running
    for need in probe.needs:
        result, causes = await settled[need]
        if result.status == "fail":
            behind.add(need)
        elif result.status == "skip":
            behind |= causes
    if behind:
        names = sorted(behind, key=position.__getitem__)
        result = Result(probe.name, "skip", "needs " + ", ".join(names))
    else:
        result = await _timed(probe)
    settled[probe.name].set_result((result, frozenset(behind)))
    queue.put_nowait((index, result))
```

- **跳过沿链传递，原因指向根上的失败**：被跳过的探针把“挡住它的失败探针”这个集合传下去。smoke 需要的三个探针都被跳过了，没有一个是 fail，可它的原因是 `needs git, dependencies`。一个失败经两条路径传过来，集合保证只写一次。
- **名字按列表顺序**：字母序、needs 的顺序都会写成 `dependencies, git`；按失败的先后排，两次运行会不一样。
- **warn 算完成**：只有 fail 和 skip 挡住依赖它的探针。依赖失败了就跳过，不管失败的探针是什么级别。
- **不按层跑**：每个任务只等自己的 needs，所以 test_command 在 dependencies 一结束就开始，不等同层还没完的 env。
- **结论**：`verdict` 按列表顺序走一遍。block 级别的 fail 和 skip 进 blocking；其余不是 pass 的进 warnings，info 级别除外。exit_code 有 blocking 就是 1。被跳过的 block 探针也阻断：git 只是 warn 级别，它失败了，lkg_diff 没法跑，init 就没法为漂移预算担保。课里的代码在 git 不可用时只给 warn，那样在没有 git 的机器上，漂移预算形同虚设。

结果放回列表里各自的位置，blocking 和 warnings 也按列表顺序，所以不管探针按什么顺序完成，两次运行的 `to_json()` 只差时间戳。耗时不进 init_report.json，否则这条也不成立（测验 Q8 提过这一点），耗时放在 Part 2 的历史里。

最后一段把 Part 1 的锁、Part 2 的历史和 `run_init` 接到 `InitService` 上：被拒绝的运行要删掉锁，下一次普通运行才会重新探测，这正是课里测验 Q9 指出的那个漏洞。

## Part 4 TAP 流

和 `run_init` 共用同一套校验 `check_probes()` 和同一个调度器 `settle()`。先校验，配置坏了只发一行 Bail out!；否则 `settle()` 按完成顺序产出 `(位置, 结果)`，这里一拿到就格式化成一行：

```python
try:
    check_probes(probes)
except ProbeConfigError as exc:
    yield f"Bail out! {_escape(str(exc))}\n"
    return
results: list[Result | None] = [None] * len(probes)
async for index, result in settle(probes):
    results[index] = result
    yield _test_line(index + 1, result)
yield f"1..{len(probes)}\n"


def _test_line(number: int, result: Result) -> str:
    if result.status == "skip":
        return f"ok {number} - {result.name} # SKIP {_escape(result.detail)}\n"
    ok = "not ok" if result.status == "fail" else "ok"
    return (
        f"{ok} {number} - {result.name} # {result.status} {result.duration_ms}ms "
        f"{_escape(result.detail)}\n"
    )
```

- **编号**：用探针在列表里的位置，开跑前就定了。行按完成顺序出来，编号照样能对上探针。
- **ok 和 not ok 只看状态**：`_test_line` 只拿到结果，拿不到 severity，这是故意的。只有 fail 是 not ok，pass 和 warn 是 ok：warn 级别的 git、info 级别的 coverage 失败了也是 not ok，慢了的 block 探针 test_command 是 warn，也是 ok。它们挡不挡启动，由最后的结论行说。测验 Q10 讲的就是这两个维度：status 是探针看到了什么，severity 是失败了该不该拦。把 severity 混进 ok/not ok，按 not ok 计数的 CI 就看不见 info 级别的失败。跳过用 SKIP 指令，写成 `ok N - name # SKIP 原因`，被跳过的 block 探针也一样；SKIP 照 docstring 大写，后面直接是原因，没有冒号和耗时。skip 不是和 pass、warn、fail 并列的第四种状态，不能写成 `# skip 0ms …`。
- **Bail out!**：探针配置坏了时，整个流只有一行 `Bail out! 原因`，以换行结尾，什么都不跑，ProbeConfigError 也不往外抛。TAP 的解析器读到 Bail out! 就停下，后面的文字就是停下的原因，这是 TAP 里的 fail fast、fail in one place。让异常抛出去，CI 日志里是半截流加一段堆栈。yield 之后要 `return`，否则生成器会接着去跑这套坏配置。
- **一结束就发**：跳过的探针在它的 needs 都结束时就发，所以 env 和 coverage 被卡住时，前 8 行已经到了。也不能更早：原因要列出背后所有失败的探针，smoke 要等 git 和 dependencies 都有了结果。
- **收尾**：计划行和结论放在最后，结论的 blocking 和 `run_init` 一样按列表顺序。
- **转义**：照 docstring 写明的顺序，先把反斜杠写成 `\\`，再把换行写成 `\n`、回车写成 `\r`，别的字符不动。顺序反了会转义两次；只转义换行时，git 那条 detail 里的回车会把一行拆开；不转义反斜杠时，`C:\new` 读回来是 `C:`、换行、`ew`。

## Part 5 LKG 差异

对象和 git 一样按内容寻址：blob 和 tree 的 oid 是它们 git 编码的 SHA-1，所以 oid 相同的子树里文件完全一样。比较时从两个根同时往下走：

```python
def _walk(store, old, new, prefix, out):
    if old == new:
        return
    before = store.tree(old) if old is not None else {}
    after = store.tree(new) if new is not None else {}
    for name in before.keys() | after.keys():
        path = prefix + name
        a, b = before.get(name), after.get(name)
        a_dir = a is not None and a.mode == TREE
        b_dir = b is not None and b.mode == TREE
        if a_dir or b_dir:
            _walk(store, a.oid if a_dir else None, b.oid if b_dir else None, path + "/", out)
        a_file = a is not None and not a_dir
        b_file = b is not None and not b_dir
        if a_file and b_file:
            if a != b:
                out.append(("M", path))
        elif a_file:
            out.append(("D", path))
        elif b_file:
            out.append(("A", path))
```

- **跳过相同子树**：开头的 `old == new` 连根也算在内，两棵相同的树一棵都不读。只有通往改动的那条路上的树会被读，blob 从来不读：Entry 里有 oid 和 mode，比较它们就够了。
- **目录和文件互换**：一个名字一边是目录、一边是文件时，目录那一侧递归下去（另一侧当作空），文件那一侧单独记一次增或删。
- **只列文件**：目录从不出现在结果里，空目录走下去什么也产生不了。
- **mode 也是内容**：`a != b` 比较的是整个 Entry，可执行位变了就是 M。
- **移动**：不做改名检测，一删一加。
- **排序**：最后按完整路径排序。按目录里的名字递归、最后不排序的话，`a/x.py` 会排在 `a-b.txt` 前面。git 自己在树里把目录当成名字后面带 `/` 来排，按这个顺序遍历，多数时候出来的就是路径顺序；但一个名字一边是文件、一边是目录时，文件 `notes` 和目录 `notes/` 在路径顺序里不挨着，中间夹着 `notes.md`，所以最后统一排一次序最稳。

`lkg_drift` 是 lkg_diff 探针的检查：没有 LKG 是 warn；LKG 提交找不到是 fail，要人重新指定基线；否则数出改动的文件，排除 init 自己写在 `.init/` 下的文件（测验 Q11 里，LKG 文件被自己提交进去，51 个文件报成了 52 个），超过预算（默认 50）就 fail。要用带斜杠的 `.init/` 匹配，否则 `.initrc` 也会被排除。

## 这套题证明了什么，没证明什么

通过了说明你能顺着下游探针的报错找到钉错的仓库路径，能在 async 代码里调试时钟和超时降级的问题，能找出缓存失效的边界和查锁本身的开销，能写只追加的 JSONL 并做到精确往返，能做带依赖、带级别的并发调度并保证结果幂等，能边跑边输出格式严格的 TAP（每一行只报探针自己的状态，配置坏了一行 Bail out! 就停下），能在内容寻址的树上做递归比较并跳过相同子树。它不涉及真实的环境探测（`find_spec`、`shutil.which`、读环境变量）和自己往上找仓库根（`.git`、`git rev-parse --show-toplevel`），不涉及调用 git、Claude Code hook、GitHub Actions 或 Docker entrypoint 的接入，也不涉及课里的 `--fix` 自动安装依赖和 YAML 探针注册表（练习 3、4）。这些需要另外动手跑。
