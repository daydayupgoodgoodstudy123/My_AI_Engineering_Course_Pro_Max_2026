# 面试官手册：RealRepo（14/41）

候选人计时期间不要看。候选人手里只有 README、`realrepo/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 同一个测试跑过两次，按哪一次算？ | "The last finished run. That's what latest_results is for." |
| 1 | 被 skip 的测试算跑过吗？ | "No. A skipped test didn't run, whatever the exit code says." |
| 2 | 同一次运行、同一条流水线记了两遍怎么办？ | "Refuse it with a ValueError. The tests don't check it." |
| 2 | 文件列表要排序吗？ | "No. Give back exactly what you were given." |
| 2 | run id 有格式吗？ | "No. Any string the caller picks. Don't parse it and don't sort by it." |
| 2 | 被拒绝的结果能留下几行吗？ | "No. A rejected outcome stores nothing." |
| 3 | 只有一条流水线的运行算不算？ | "No. List it under unpaired and keep it out of every count." |
| 3 | 越界文件是比列表还是比数量？ | "The count. Which files they are doesn't matter for the comparison." |
| 3 | 配对数是偶数时中位数怎么取？ | "The usual way: the mean of the two middle values." |
| 4 | 改 docstring 算有效修改吗？ | "Yes. Only comments, blank lines and whitespace don't count." |
| 4 | 改完的文件语法错误、解析不了呢？ | "Your call. Say what you chose. The tests don't cover it." |
| 4 | 时间用墙钟还是事件里的 t_ms？ | "The event's t_ms. Each run has its own clock." |
| 4 | 两个运行的记录之间按什么顺序输出？ | "The order they become known. Don't hold any back to sort them." |
| 5 | 函数里面的 import 算吗？ | "Yes. It runs when the function does." |
| 5 | 标准库和第三方库的 import？ | "Ignore anything that isn't a file in the repo." |
| 5 | conftest.py 要考虑吗？ | "Not for this exercise. Tell me afterwards what it would change." |
| 5 | 改动里有被删除的模块吗？ | "No. Every changed file is still in the repo." |

## 每关：要看什么、提示、追问

### Part 1 修五项结果的测量（目标 10 分钟）

一个测试里叠了 4 个缺陷和一处性能问题：

1. 解锁后第一个错误是 `latest_results` 里的 `AttributeError: 'NoneType' object has no attribute 'items'`，这个函数本身没有错。traceback 是 `measure → tests_actually_run → latest_results`；None 来自更早的 `sample.run_workbench → artifacts.load_feedback`：init 脚本和验证闸门不跑测试，JSONL 里没有 results，`raw.get("results")` 就是 None，和 `FeedbackRecord` 的 docstring 不一致。
2. `tests_actually_run` 在没有反馈记录时退回去看 agent 的声明。课里的 prompt-only 从没跑过测试，却声称 tests_passed。
3. `latest_results` 没有去掉 "skipped" 的结果，和它的 docstring 不一致。prompt-only 跑了验收测试，可这个测试被 skip 了：pytest 全部 skip 时退出码是 0，看起来是绿的，其实一个测试都没跑，tests_actually_run 却成了 True。课里说证明目标的测试必须是真正跑过的那个。
4. `handoff_quality` 把缺 `next_action` 的包评为 partial。第 40 课：只缺 next_action 的是状态报告，不是交接，应该是 missing。只查键在不在不够：空白的 next_action 也是没填，下一条断言抓住，要用现成的 `_filled`。
5. 性能：`acceptance_met` 对每个选择器把所有结果扫一遍，每次都调 `covers()`，而 `covers()` 每次用 `PurePosixPath(...).parents` 重算祖先。200 个选择器乘 2,000 个结果是 40 万次，本机约 1.9 秒，限值 0.15 秒。每个结果的祖先只算一次、建成索引后约 10 毫秒。
6. 护栏：按完整节点 id 精确查找（函数选择器覆盖不到参数化用例）、`startswith` 不看边界（`test_signup` 覆盖了 `test_signup_happy_path`）、只按模块建索引（`pytest -k happy` 也满足验收）、索引里每个选择器只记最后一个结果（`sample_app` 下有失败的测试）、把非零退出码全跳过（退出码 1 的 pytest 也跑了测试）、重写 `latest_results` 时丢了 None 退出码那一条（被 runner 杀掉的 pytest 打印过两个 passed，第 37 课：No exit, no progress）、`all()` 对空集为真（被 skip 的验收测试算满足）、空列表当成没填（`failed_attempts: []`）、任一字段没填就评 missing（空白的 verdict_pointer 应该是 partial），这些写法都会挂。
7. 可以接受：按 `record.error` 跳过记录。`FeedbackRecord` 的 docstring 写的是 exit_code 为 None 时才有 error，两种写法在这里等价；问一句候选人哪个字段才是约定。

看什么：是不是顺着 traceback 往上找 None 的来源，而不是在 `latest_results` 里补一个 `or {}` 就走；是不是先 `print(repr(record))` 看实际数据；提速时有没有先说清楚选择器的语义再动手。

提示：
- H1："Which value is None here, and which function created it?"
- H2："What does FeedbackRecord's docstring say results is for a command that runs no tests?"
- H3：直接指出 `load_feedback` 里 results 那一行。

追问：
- "Why not trust the agent when it says the tests passed?"（课里说大多数“测试过了”的说法无法核实；只有 feedback 记录是证据）
- "`pytest -k happy` ran a test. Why is acceptance not met?"（证明目标的测试必须是真正跑过的那个；跑过的是 happy path）
- "CI is green, but the acceptance test was skipped. How do you stop that from shipping?"（退出码 0 不等于跑过；按节点 id 看结果，验收选择器下必须有 passed，只有 skipped 就当没跑，闸门 fail closed）
- "Your index grows with tests times depth. Fine for 2,000 results; what about two million?"（前缀树，或者排序后二分查找加边界检查；按模块分片）

### Part 2 结果库（目标 12 分钟）

坑：
- SQLite 没有布尔类型。`True` 存进去是整数 1，读回来是 `int`；`1 == True`，普通的 `==` 看不出来，测试的 `exact()` 会逐层比类型。
- 文件列表拆成每个文件一行的话，`[]` 一行都没有，读回来拼不出这个结果。整份列表存成一个 JSON 值最省事。
- 用 `;` 或 `,` 把路径连起来存，遇到 `docs/notes, v2.md`、`docs/a;b.md` 就拆错了。
- 文件列表按给的顺序原样存取，不排序。
- `runs()` 按第一次写入的顺序：`ORDER BY run_id` 会把 `r10` 排在 `r2` 前面，不带 ORDER BY 的 `SELECT DISTINCT` 不保证顺序：表上有 `UNIQUE (run_id, ...)` 时 SQLite 走这个索引，返回 r1、r10、r2，测试会挂；没有索引时碰巧按插入顺序，测试抓不到，要追问。`outcomes()` 按写入顺序，不按运行和流水线排序。
- 每次重复都保留：r2 和 r10 都有 prompt-only，结果不能互相覆盖。
- 未知流水线、不存在的交接等级、超过 10 的总分都是 ValueError。

追问：
- "Why one row per outcome instead of one row per run?"（加第六项结果，比如练习 1 的时间，不用改表；代价是读的时候要按名字解码）
- "Two benchmark workers record at the same time?"（SQLite 的写锁；每次 record 一个事务；或者经一个队列写）
- "A run crashed after prompt-only finished. What does the store show, and what should the report do with it?"（只有一条流水线的运行；Part 3 把它列为 unpaired，不计入比较）

### Part 3 配对比较（目标 12 分钟）

坑：
- 按 run_id 配对。把两条流水线各排成一列再 zip，r3 只有 prompt-only，从它开始后面全部错位。先去掉没配对的运行再 zip 也不行：记录的顺序是乱的，r4 的 workbench 记录排在最后，r7 的排在 r4 的 prompt-only 后面，两次运行的 workbench 结果会对调。只有一条流水线的运行列进 unpaired，不进任何计数。
- handoff_quality 是有序等级。直接比字符串，"partial" > "full packet" > "missing"，有一半是反的。
- 越界文件比个数，越少越好。Python 的列表按字典序比较，`["docs/a.md"] < ["app/zz.py"]` 是 False，一个文件对一个文件本该打平。
- median_delta 是每个配对差值的中位数。两边各取中位数再相减（acceptance_met 会算成 1 而不是 0.5），或者用平均数，都不对。配对数是偶数，所以有 0.5、1.5。
- no_gain 是 workbench 一项都没赢的配对，包括全部打平的 r6。只列“prompt-only 赢过一项”的运行，会漏掉 r6、多出 r2。
- 没有配对就抛 ValueError：只有一条流水线的基准没有可比的东西。
- 最后一段是端到端检查：课里的两次脚本运行经过 Part 1 量出结果，在 Part 2 的库里记三遍，再从 `store.outcomes()` 比较。

追问：
- "Three runs, the workbench wins all three. Is that enough?"（不够；配对的胜负可以做符号检验；报告里每个比例都要写成 n / m，这是课里 skill 文件的硬性要求）
- "Why the median of the differences rather than the difference of the medians?"（配对去掉了运行之间的波动；各取中位数就丢了“哪两次是同一轮”的信息）
- "What would no_gain look like for a one-line lint task?"（课里说的 false negative：prompt-only 更快，workbench 的开销是真成本，要如实列出来）

### Part 4 里程碑流（目标 14 分钟）

坑：
- 要同时读两个运行：每个运行一个 task，把事件放进同一个队列。一个接一个读，或者轮流 `anext`，都会卡住：测试里 workbench 的事件流在等一个信号，测试要先收到 prompt-only 的最后一条记录才发出这个信号。卡住时测试 2 秒后报 “the stream stalled”。
- 一个运行结束时，马上输出它没达到的里程碑（t_ms 为空）。等全部运行结束再输出，同样会卡住。
- 有效修改只算合同允许的 .py 文件，而且要改到注释、空行和空白以外的东西。逐字比较会把 2100 的调空格算进去；去掉所有空白再比会把 2600 的加注释算进去；只删以 `#` 开头的整行，2600 那次在 `USERS` 那一行末尾加的注释还在，同样算成 2600；用正则删掉 `#` 之后的内容，会连字符串里的 `README.md#signup` 一起删掉，于是漏掉 3300 那次只改了字符串的修改，答案变成 3900。用 `tokenize` 去掉 COMMENT 和 NL 再比，或者比 `ast.dump`，都能得到 3300；`tokenize` 留着 NL、`ast.dump` 带上 `include_attributes=True`，都会把 2100 那次多出的空行算进去。1800 那次改的是真代码，但 `settings.py` 不在合同里。
- 时间用事件里的 t_ms，每个运行有自己的时钟，不用墙钟。
- tests_run 和 acceptance_met 直接用 Part 1 的规则：agent 的 claim 事件不算跑了测试；30000 那条被杀掉的记录不满足验收，要等到 38000。
- 一个事件可以同时达到两个里程碑：最后一小段只有一个运行，第一次 pytest 就通过了验收，tests_run 和 acceptance_met 都在 900，要按 MILESTONES 的顺序输出。用集合收集“这次新达到的里程碑”再遍历，顺序随哈希种子变化。
- 起始代码是普通的 `async def` 加 `raise`，调用它得到的是 coroutine，测试报 `'async for' requires an object with __aiter__ method, got coroutine`，要会看出来这里需要 async generator。

追问：
- "How do you measure time-to-first-meaningful-edit cleanly?"（练习 1：用运行自己的时钟，只算范围内的文件，按 token 比较；workbench 的准备步骤算进去，这是它真实的开销）
- "The reader stops after the first record. What is still running?"（每个运行的 task；要在 finally 里 cancel 并等它们结束）
- "Should a long init script count against the workbench?"（算；这正是 false negative 那一面，报告里要能看到）

### Part 5 测试影响（目标 12 分钟）

坑：
- `from sample_app import validators` 导入的是子模块。只把 import 后面的名字当属性，会漏掉 `test_validators.py`，`from . import errors`、`from .. import app` 也会断。
- `sample_app/api/__init__.py` 里的 `from .routes import router`：`__init__.py` 的包是它自己（`sample_app.api`）。按“模块名去掉最后一段”来算，会去找 `sample_app/routes.py`，`test_routes.py` 就断了。按文件所在目录算，两种情况都对。
- `from .. import app` 从 `sample_app/api/routes.py` 出发是 `sample_app/app.py`。
- `errors.py` 为了避开和 `validators.py` 的循环导入，把 import 写在函数里。只看 `tree.body` 会漏掉 `test_errors.py`。
- `import lib.util` 会执行 `lib/__init__.py`，它又导入了 `config`。只记 `lib/util.py`，改 `config.py` 时 `tests/test_util.py` 就漏了。
- 影响是传递的：要沿“被谁导入”的反向边一路走下去，不只看直接导入者。validators 和 errors 互相导入，要记已访问。
- 改动的测试文件自己受影响；README 这类非 Python 文件不影响任何测试。
- 测试文件按文件名认：名字以 `test_` 开头。`sample_app/testing.py` 是测试辅助模块，它导入了 validators，BFS 会走到它，但它不是测试；按 `startswith("test")` 判断会把它列进结果。
- `proves_change` 拿选择器 `::` 前面的部分去和受影响的测试文件比，目录选择器覆盖它下面的测试。目录要按路径边界比：`sample_app/api` 不覆盖 `sample_app/api_v2/` 下的测试。测试里没有这种相邻目录，看到不带边界的 `startswith` 时追问一句，复用 Part 1 的 `covers()` 最省事。

追问：
- "What does an import graph miss?"（conftest.py 和插件、运行时读的数据文件、importlib 的动态导入、子进程；所以还要有兜底，比如定期跑全量）
- "The change only touches README.md. What should the acceptance command be?"（没有测试能证明文档改动；照实说，课里 skill 文件的规则是没有验收命令就不出这个基准）
- "A monorepo with 50,000 files?"（按提交缓存 import 图，从 diff 增量更新；只解析变化的文件）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、找 None 的来源、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出声明与证据、噪声与样本量、并发写、import 图的盲区 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
