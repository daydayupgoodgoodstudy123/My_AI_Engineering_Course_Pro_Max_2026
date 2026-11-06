# 参考答案讲解：RealRepo（14/41）

计时结束后再看。参考实现在同目录的 `realrepo/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修五项结果的测量

**现象**：解锁后的第一个错误是 `latest_results` 里的 `AttributeError: 'NoneType' object has no attribute 'items'`，而这个函数本身没有错。

**顺着往上找**：traceback 是 `measure → tests_actually_run → latest_results`。`record.results` 是 None，说明记录在创建时就已经坏了。记录来自 `sample.run_workbench`，由 `artifacts.load_feedback` 解析 JSONL。init 脚本和验证闸门这两条命令不跑测试，JSONL 里没有 `results` 字段，`raw.get("results")` 就是 None；而 `FeedbackRecord` 的 docstring 写的是“不跑测试的命令，results 为空”。根因在加载器，报错在两层调用之后。在加载器里改成 `dict(raw.get("results") or {})`。在 `latest_results` 里写 `record.results or {}` 也能过，但别处读记录的代码还会碰到同一个 None。

**依次修四处**：

1. `load_feedback`：没有 results 的记录给空 dict。
2. `tests_actually_run`：去掉“没有反馈记录就看 agent 怎么说”这条退路。课里说大多数“测试过了”的说法无法核实，能当证据的只有 feedback 记录。样例里的 prompt-only 从没跑过测试，却声称 `tests_passed`。
3. `latest_results`：去掉 "skipped" 的结果，docstring 写的就是这一条。pytest 把选中的测试全部 skip 时退出码是 0，可一个测试都没跑。prompt-only 跑了验收测试，结果是 skipped，不能算 tests_actually_run。
4. `handoff_quality`：`next_action` 没填的包评为 missing。第 40 课：七个字段只缺 next_action 的，是状态报告，不是交接。“没填”沿用 docstring 里的定义，用现成的 `_filled`：只查键在不在，空白的 next_action 会被评成 partial。

**提速**：`acceptance_met` 对每个选择器都把所有结果扫一遍，每次调用 `covers()`，而 `covers()` 每次都用 `PurePosixPath(...).parents` 重算一遍祖先。200 个选择器乘 2,000 个结果，就是 40 万次，本机约 1.9 秒。改法是每个结果只算一次祖先，建一张“选择器 → 它覆盖的结果是否全部通过”的表，再逐个查选择器，约 10 毫秒：

```python
passing: dict[str, bool] = {}
for nodeid, result in latest_results(records).items():
    for selector in ancestors(nodeid):
        passing[selector] = passing.get(selector, True) and result == "passed"
return all(passing.get(selector, False) for selector in acceptance)
```

`passing.get(selector, False)` 的默认值是 False：一个选择器覆盖不到任何跑过的测试，就不算满足。

**护栏**：常见的提速写法会改坏语义，后面的断言专门抓这些：

- 按完整节点 id 精确查找：函数选择器 `…::test_too_short` 覆盖不到参数化的 `[1234567]` 和 `[]`，模块选择器也覆盖不到它里面的测试。
- `str.startswith` 不看边界：`test_signup` 会覆盖 `test_signup_happy_path`。
- 只按模块建表：一个测试选择器替整个模块回答，跑一下 `pytest -k happy` 验收就成立了。
- 表里每个选择器只记最后一个结果：`sample_app` 下面有失败的测试，它不能算通过。
- 把非零退出码都跳过：退出码 1 的 pytest 也跑了测试，失败的结果正是要看的东西。
- 丢了 None 退出码那一条：起始代码里 `latest_results` 已经跳过 `exit_code` 为 None 的记录，重写时别丢。第 37 课：runner 没拿到退出码时，记录里是 `exit_code: null`，No exit, no progress。被杀掉的 pytest 在超时前打印了两个 passed，也不算数。
- 空列表当成没填：workbench 的交接包里 `failed_attempts: []` 是填了，内容是“没有失败的尝试”。

## Part 2 结果库

参考实现只有一张表：自增的 `seq` 记录写入顺序，每行是（run_id、pipeline、outcome、value），value 是 `json.dumps` 之后的文本。JSON 能分清 true 和 1、`[]` 和空串，读回来类型不变。

容易错的地方：

- **布尔值**：SQLite 没有布尔类型，`True` 存进去是整数 1，读回来是 `int`。Python 里 `1 == True`，普通的 `==` 看不出来，测试的 `exact()` 会逐层比类型。
- **空列表**：把文件列表拆成每个文件一行，`[]` 就一行也没有，读回来拼不出这个结果。整份列表存成一个 JSON 值。
- **拼接**：用 `;` 或 `,` 把路径连成一串，遇到 `docs/notes, v2.md`、`docs/a;b.md` 就拆错了。
- **顺序**：文件列表按给的顺序原样存取，不排序。`runs()` 按第一次写入的顺序，不能 `ORDER BY run_id`（`r10` 会排在 `r2` 前面），也不能靠不带 ORDER BY 的 `SELECT DISTINCT`。`outcomes()` 也按写入顺序。
- **每次重复都保留**：r2 和 r10 都有 prompt-only，各自的结果互不覆盖。
- **校验**：未知的流水线、不存在的交接等级、超过 10 的总分，都抛 ValueError。参考实现先校验，再在一个事务里写入五行，被拒的结果一行都不留。

一行一项结果，而不是一行一次运行，好处是加第六项结果（比如练习 1 的时间）不用改表。

## Part 3 配对比较

`compare` 先按 run_id 把记录归到一起，两条流水线都有的才算配对，其余按出现顺序列进 `unpaired`。然后对每一项结果，把两边换成可比的数：两个布尔值记成 1 和 0，越界文件记成个数，交接等级记成 0、1、2，评审总分原样。每个配对算一个差值（workbench 减 prompt-only），并按这一项的方向记胜负平：越界文件越少越好，其余越大越好。`median_delta` 是这些差值的中位数。

- **按 id 配对**：把两条流水线各排成一列再 zip，r3 只有 prompt-only，从它开始后面全部错位。先去掉没配对的运行再 zip 也不对：记录是乱序到达的，r4 的 workbench 记录在最后，r7 的在 r4 的 prompt-only 后面，r4 和 r7 的 workbench 结果会对调，评审分的胜负跟着变。
- **有序等级**：直接比字符串，"partial" > "full packet" > "missing"，有一半是反的。
- **越界文件比个数**：Python 的列表按字典序比较，`["docs/a.md"] < ["app/zz.py"]` 是 False，可一个文件对一个文件本该打平。
- **差值的中位数**：配对设计要先算每一对的差，再取中位数。两边各取中位数再相减，这组数据里 acceptance_met 会算成 1，而不是 0.5；用平均数也不对。配对数是偶数，中位数取中间两个的平均，所以会出现 0.5、1.5。
- **no_gain**：workbench 一项都没赢的配对，包括全部打平的 r6。只列“prompt-only 赢过一项”的运行，会漏掉 r6、多出 r2。课里的 skill 文件要求把 prompt-only 更划算的任务如实列出来，不能藏。
- **没有配对**：只有一条流水线的基准没有可比的东西，抛 ValueError。

最后一段把 Part 1–3 串起来：课里的两次脚本运行经过 Part 1 量出结果，在 Part 2 的库里记三遍，再从 `store.outcomes()` 拿出来比较，五项都是 workbench 3 比 0。

## Part 4 里程碑流

参考实现给每个运行开一个 task，把事件放进同一个队列，读者从队列里取，谁先到先处理：

```python
async def pump(pipeline, events):
    async for event in events:
        await queue.put((pipeline, event))
    await queue.put((pipeline, end))
```

读者先输出表头；每取到一个事件，就交给这个运行自己的进度对象，第一次达到的里程碑马上输出一行；取到某个运行的 `end`，就补上它没达到的里程碑，t_ms 为空。`finally` 里取消还在跑的 task。

- **同时读**：一个接一个读，或者轮流 `anext`，都会卡住。测试里 workbench 的事件流在等一个信号，测试要先收到 prompt-only 的最后一条记录才发出这个信号。
- **运行一结束就补空行**：等全部运行结束再补，同样会卡住。
- **有效修改**：只算合同允许的 .py 文件，而且要改到注释、空行和空白以外的东西。逐字比较，会把 2100 那次调空格算进去；去掉全部空白再比，会把 2600 那次加注释算进去；只删整行注释也一样，2600 那次还在 `USERS` 那行末尾加了注释；用正则删掉 `#` 之后的内容，会把字符串里的 `README.md#signup` 一起删掉，于是漏掉 3300 那次只改了字符串的修改，答案变成 3900。用 `tokenize` 去掉 COMMENT 和 NL 再比，或者比 `ast.dump`，都得到 3300。1800 那次改的是真代码，但 `settings.py` 不在合同里。
- **时间**：用事件里的 t_ms，每个运行有自己的时钟。
- **沿用 Part 1 的规则**：agent 声称测试通过的 claim 事件不算跑了测试；30000 那条被杀掉的记录不满足验收，要等到 38000。
- **同一个事件达到两个里程碑**：最后一小段的运行第一次跑 pytest 就通过了验收，tests_run 和 acceptance_met 都是 900。参考实现按 MILESTONES 的顺序检查，返回列表；用集合收集再遍历的话，顺序不固定。

这就是练习 1 问的“怎么量才干净”：用运行自己的时钟，只看范围内的代码，按 token 而不是按字符比较。workbench 在 9000 才第一次有效修改，比 prompt-only 的 3300 晚，因为前面有 init、读合同和状态这些步骤；这段开销是真的，报告里应该看得到。

起始代码是普通的 `async def` 加 `raise`，调用它得到的是 coroutine，测试报 `'async for' requires an object with __aiter__ method, got coroutine`，要会看出来这里需要 async generator。

## Part 5 测试影响

先用 `ast` 找出每个 .py 文件直接导入了仓库里的哪些文件，再从变化的文件出发，沿“被谁导入”的反向边做 BFS，走到的测试文件就是受影响的测试。

解析 import 的规则：

- `import a.b.c` 会执行 `a/__init__.py`、`a/b/__init__.py`，再加上 `a/b/c.py`。只记最后一个文件的话，`import lib.util` 看不到 `lib/__init__.py`，也就看不到它导入的 `config`。
- `from a.b import c`：仓库里有 `a/b/c.py` 时，c 是子模块，也要算进去。`from sample_app import validators`、`from . import errors`、`from .. import app` 都是这种情况。
- 相对导入相对于导入者所在的包。`sample_app/api/routes.py` 的包是 `sample_app.api`；`sample_app/api/__init__.py` 的包是它自己，也是 `sample_app.api`。按“模块名去掉最后一段”来算，`__init__.py` 会被算到上一层的 `sample_app`，`from .routes import router` 就找不到 `sample_app/api/routes.py`。按文件所在的目录来算，两种情况都对。
- 函数里的 import 也是 import。`errors.py` 为了避开和 `validators.py` 的循环导入，把 import 写在函数里；只看顶层语句会漏掉 `test_errors.py`。
- validators 和 errors 互相导入，BFS 要记已经访问过的文件。
- 变化的测试文件自己受影响；README 这类不是 Python 的文件不影响任何测试。
- 测试文件按名字认，以 `test_` 开头。`sample_app/testing.py` 是 test_app 用的辅助模块，改 validators 时 BFS 会经过它，但它不是测试。

`proves_change` 把这一关和 Part 1 接起来：取验收选择器 `::` 前面的部分，用 `covers()` 看它是不是某个受影响的测试文件，或者在它上面的目录。只改了 `lib/config.py` 时，SIGNUP 的验收测试没有导入它，跑了也证明不了这次改动。

## 这套题证明了什么，没证明什么

通过了说明你能从运行留下的产物里量出课里的五项结果，在别人的代码里顺着调用链找到根因，把结果存下来并保住类型，做按运行配对的前后对比，同时读多个异步流并按事件自己的时钟输出，以及按 Python 的规则解析 import 图。它不涉及真的跑一个 agent、调用 pytest 或 git，也没有测量真实模型带来的噪声（练习 4）：样例应用和两条流水线都是脚本。课里 skill 文件要求的 CI 工作流和 `docs/benchmark.md` 需要另外动手做。
