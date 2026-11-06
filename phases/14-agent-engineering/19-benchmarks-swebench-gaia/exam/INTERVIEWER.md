# 面试官手册：swebench（14/19）

候选人计时期间不要看。候选人手里只有 README、`swebench/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 测试函数抛异常，算失败还是让整个评测报错？ | "It's a failing test. The report says ERROR for it and the run goes on." |
| 1 | PASS_TO_PASS 在修复前已经通过了，打完补丁还要再跑吗？ | "Yes, every one of them. A patch can break a test that used to pass. That's what PASS_TO_PASS is there to catch." |
| 1 | test id 里会有空格吗？ | "Yes. A parametrized id is printed the way pytest prints it, brackets and spaces included." |
| 1 | FAIL_TO_PASS 的测试在打补丁前就通过了怎么办？ | "Then the task can't tell a fix from a no-op. It's invalid, and it doesn't count." |
| 1 | 两个 FAIL_TO_PASS 里只有一个修复前就通过呢？ | "One is enough. The task is invalid. Same for one PASS_TO_PASS test that fails or errors before the patch." |
| 1 | 列表里有、报告里没有的测试？ | "It didn't pass." |
| 2 | 补丁里可能有 CRLF、引号、逗号吗？ | "Yes. It's whatever the agent wrote, and it has to come back byte for byte." |
| 2 | 同一个 instance id 再写一次？ | "Reject it with a ValueError, also after a reopen. One record per task per run." |
| 2 | passed 写成 True/False 行不行？ | "No. 1 or 0, as the docstring says. Other tools read this file." |
| 3 | plus 视图要不要把泄漏的任务去掉？ | "No. Keep them in the denominator and count them as not resolved." |
| 3 | error 状态的任务进不进分母？ | "Yes. An agent that crashes failed the task. Only invalid tasks are left out." |
| 3 | 分位数用哪种算法？ | "Nearest rank, as in the docstring. No interpolation." |
| 4 | 输出按输入顺序还是完成顺序？ | "Completion order. A slow task must not hold back the others." |
| 4 | invalid 的任务还要不要调 agent？ | "Yes, for now. run_task decides it's invalid." |
| 5 | 并行分支的调用次数要不要相加？ | "No. They can run at the same time, so a path takes one branch." |
| 5 | 同一个模态出现多次？ | "It counts once." |

## 每关：要看什么、提示、追问

### Part 1 修测试闸门（目标 12 分钟）

一个测试里叠了 4 个缺陷：

1. `run_task` 打完补丁只重跑 FAIL_TO_PASS，PASS_TO_PASS 直接沿用补丁前的结果。PASS_TO_PASS 修复前本来就通过，看上去省掉了一半测试，可这样一来补丁打坏哪个 PASS_TO_PASS 都发现不了：修好 reset_to、顺手把 step 改成 2 的补丁被判成 resolved，补丁后的 test_step 还是 True。这就是课里 t003 那种越界的补丁，课里的 skill 也把“没有 PASS_TO_PASS 闸门的 harness”列为硬拒绝。docstring 写的是打完补丁后整套测试重跑。
2. `passed` 用 `line.split()` 切开报告行，取第二段当 test id。pytest -rA 的每一行是 `<STATUS> <test id>`，参数化的 id 带方括号，里面可以有空格：`test_strip[two words]` 被切成 `test_strip[two`，永远对不上，被当成没通过。错误不在 `passed` 里报出来，而是在两层之外 `run_task` 给出的结果里：修好 strip 的补丁，ftp_passed 是 0。修法是只在第一个空格处切开，再整串比较。
3. 没有任务有效性检查。修复前就通过的 FAIL_TO_PASS、修复前就失败的 PASS_TO_PASS、没有 FAIL_TO_PASS 的任务，都应该是 invalid（课里 Verified 去掉的就是这类任务）。原代码把一个什么都不做的补丁判成 resolved。有一个测试不成立就够了：写成 `all(before[:nf])` 或 `not any(before[nf:])`，`demo__half-5` 的两种情形会挂。有效性要在打补丁之前判，无效任务上补丁报错，状态也还是 invalid，不是 error。
4. 每个测试 id 都把整份报告从头扫一遍，3500 个测试的套件是 O(T²)，本机 1.0 到 1.9 秒，负载高时到 3.5 秒。报告解析一次成字典或集合就是线性的，本机中位数 3 ms。

起始代码里已经正确、测试也在守的：`run_tests` 把抛异常的测试记成 ERROR，接着跑下一个。修复前的 FAIL_TO_PASS 测试访问还不存在的 reset_to 键，会抛 KeyError；`demo__half-5` 的一个测试修复前抛 ZeroDivisionError。测试直接核对 `run_tests` 的输出：改成只接 KeyError、记成 FAILED 或 PASSED、遇到异常就停，都会挂。

防过度修复：
- 修第 1 条只改状态：只看 FAIL_TO_PASS 判 resolved，或者另跑一遍整套测试来定状态、计数和 after 的 outcomes 还照抄补丁前，都会挂在比对整个 TaskResult 的那条断言上。
- 为了保住提速，只在 FAIL_TO_PASS 全部通过时才重跑 PASS_TO_PASS：一个没修好、又把 step 改坏的补丁，ptp_passed 会是 1，“the pass counts are taken after the patch”会挂。
- 修第 2 条时改成在整行里找 id（`test_id in line`）或用 `startswith`：`test_split` 是 `test_split_lines` 的前缀，后者排在前面而且通过了，越界的补丁又被判成 resolved。按空白切开再用一个空格拼回去：`test_strip[word  ]` 里的两个空格变成一个，还是对不上；取最后一段（`split()[-1]`）也一样截断。
- 在 `run_task` 外面整个包一层 try/except，把任务记成 error：第一段断言要的是 resolved，会挂。
- 为了提速不跑修复前的测试、直接相信两张列表：有效性检查失效，会挂。
- 补丁作用在浅拷贝上：嵌套字典被原地改掉，“the task's own state never changes”会挂。

计时的灰色地带：报告只拆一次行，再对每个 id 查 `f"PASSED {id}" in lines`，结果是对的，但仍是 O(T²)，只是列表比较在 C 里做。本机 50–90 ms，基本能过 0.1 s（负载 60 时 400 次里有 2 次超过）。`f"PASSED {id}\n" in log` 本机 140–600 ms，过不了。看到前一种写法不要因为测试绿了就放过，追问复杂度，让候选人说出为什么该用字典或集合。

看什么：是不是先对照断言里 outcomes 的差异，看出补丁后 test_step 的结果和补丁前一模一样，再回到 `run_task` 看补丁后跑了哪些测试；是不是 `print(log)` 看报告长什么样；每改一处就重跑。

提示：
- H1："The patch sets step to 2. Which tests did the harness run on the patched copy?"
- H2："Print the report for the text task. What does passed() read as the id on the test_strip[two words] line?"
- H3：直接指出 `run_task` 补丁后只跑了 FAIL_TO_PASS、PASS_TO_PASS 照抄补丁前的结果，`passed` 用 `split()` 切行，以及 `run_task` 里 before 的结果没有用来判定任务是否有效。

追问：
- "Re-running every test after every patch is slow. How would you cut the cost without weakening the PASS_TO_PASS gate?"（并行跑、复用装好依赖的环境镜像，或者按补丁改到的文件先挑出受影响的测试做快速初筛；但最终判定用的 PASS_TO_PASS 是数据集给定的列表，补丁之后必须真跑一遍，不能沿用补丁前的结果）
- "Why gate on unit tests at all, instead of comparing the patch with the reference fix?"（同一个 bug 有很多种正确修法；测试判定的是行为。课里的定义就是 FAIL_TO_PASS 翻转、PASS_TO_PASS 不破）
- "The agent's patch is code you didn't write. Where does it run?"（沙箱。课里的 skill 明确拒绝不带沙箱的 harness，测试还要钉在固定 commit 上）
- "A test is flaky. What does it do to these gates?"（修复前后的结果都不可信，属于 Verified 要去掉的“不可靠测试”；可以重跑多次再判定）

### Part 2 结果 CSV（目标 12 分钟）

坑：
- `bool("0")` 是 True。passed 要按 `"1"` 比较读回来。
- 读 CSV 必须 `newline=""`。不写的话，通用换行模式会把补丁里的 `\r\n` 改成 `\n`，往返就不一致了。写的时候在 macOS/Linux 上不加也不会出错，所以这个坑只在读的一侧出现。
- 读回来的成本是字符串；用 `float()` 转的话，`18234.0 == 18234` 能过相等比较，类型检查会挂。
- 每次打开都写表头：重开之后表头被当成数据读，`int("tokens")` 报错。
- 重复 id 只记在内存里：重开后同一个 id 能再写一次。
- 一边写一边校验 phase：坏记录的前两行已经写进 tests.csv，之后同 id 的正确记录读回来会多出两条 outcome。必须先校验，再写。
- 被拒绝的记录都带着测试结果：重复 id、900.0、-1、未知 status 这几条，只要有一项检查放在写 tests.csv 之后，读回来就会多出孤立的测试行。status 和负数成本也要拒绝。
- `get()` 要读文件。只记在内存里的话，重开之后 get 报 KeyError；文件句柄一直开着又不 flush 的话，写完马上 get 也是 KeyError（docstring 说 add() 返回时就要落盘）。
- 按写入顺序返回。按 instance id 排序的话，sphinx 会排到 django 后面。
- error 记录没有任何测试行，也要能读回来，outcomes 是空列表。
- 900.0 这样的浮点成本要拒绝，否则写进去容易，读回来 `int("900.0")` 就炸了。

追问：
- "Why two files instead of one wide row per task?"（每个测试一行便于按测试统计 flaky 和回归；任务级的成本不应该在每个测试行重复）
- "The process dies between the two writes. What do you see on reopen?"（参考实现先写 tests.csv 再写 runs.csv，runs.csv 相当于提交标记，只有测试行的任务不会出现在 records() 里；但同一个 id 重写时，这些孤立行会被并进来。更严格的做法是给每行带上写入批次号，或者写临时文件再原子改名）
- "Ten workers write the same run at once?"（CSV 追加写没有锁；按 worker 分文件再合并，或者换 SQLite）

### Part 3 三种口径和分位数（目标 12 分钟）

坑：
- 泄漏检查只看新增行：`+++` 文件头和空的新增行都不算，否则分母变大，1/3 变成 1/4，低于 30%。
- 空白要规范化后整行比较。只 `strip()` 的话，issue 里 `return  count +\t1` 匹配不上；用子串比较的话，issue 正文里的 “pass”、“return None”、“)” 会被当成泄漏。
- 阈值是“至少 30%”，3/10 必须算泄漏。
- 最近秩：第 ceil(p·n/100) 小的值。插值（例如 `statistics.median`）会给出 5.5；把秩当 0 基下标会给出 6。
- invalid 不进分母，error 进分母，按未解决算。
- plus 视图里泄漏的 resolved 按未解决算，任务数不变。从分母里去掉的话，rate 是 2/4 而不是 2/5。
- 空视图（这里是 verified 集合为空）的 rate 和成本都是 None，不是 0。
- `added_lines` 是把连续空白压成一个空格，不是删掉空白：`x  =\t1` 要变成 `x = 1`。`"".join(line.split())` 能过泄漏的几条断言，过不了这一条。
- 最近秩至少取第 1 个：p=0 时 ceil 得 0，不加 `max(1, ...)` 的话 `xs[-1]` 返回的是最大值。
- 阈值写成 `100 * hits >= 30 * n`、`hits / n >= 0.3` 或 `hits >= 0.3 * n` 都行，n 在 40 以内结果完全一样。
- 最后一段把 Part 1 的判定、Part 2 的存储和本关的报告串起来，跑课里的 t001、t002、t003：全部口径是 2/3，和课里的 resolution rate 一样。rate 不要四舍五入，0.67 会挂。

追问：
- "Your agent gets 50% on SWE-bench. What do you report?"（Verified 的分数、SWE-bench+ 式过滤后的分数，以及成本和步数的分布。课里说 50% 可能变成 35%）
- "What does this line-equality leak check miss, and what does it flag wrongly?"（漏掉换了变量名、拆成多行、用自然语言描述的修法；误报很短、很通用的行。课里 SWE-bench+ 的数字来自人工审计，自动规则只能初筛）
- "n is 10. How much do you trust P95?"（n=10 时 P95 就是最大值，样本太少时分位数很不稳定）

### Part 4 并发评测流（目标 12 分钟）

坑：
- 输出格式由测试决定：逐行 `json.loads`，每行恰好一个 `\n`，第一行的原文要和 json.dumps 默认格式、文档里的键顺序一致。
- 并发上限：同时最多 `concurrency` 个 agent，而且要用满。不限流、按批次跑、一次一个，事件顺序都会变。
- 完成一个就输出一行。先 gather 全部再输出，探针会看到慢任务 a 已经结束。
- agent 抛异常时这一个任务记成 error，其他任务照常进行。只接一部分异常的话，worker 静默死掉，读的一方永远等不到第 5 行，测试的 3 秒超时变成 TimeoutError。
- 读到一半调用 `aclose()`，要取消还在跑的 agent 并等它们结束。只取消不等待，测试会看到残留的 task。
- summary 四个计数都要有，空运行也一样。
- concurrency 小于 1 要报 ValueError，否则 `Semaphore(0)` 永远等下去。
- 关闭时 gather 不带 `return_exceptions=True`，被取消的 worker 的 CancelledError 会从 `aclose()` 里冒出来。
- worker 里写成 `except BaseException` 也能过测试：关闭时 agent 照样被取消，只是 worker 把 CancelledError 吞成一行 error 再正常结束。这算能接受，但要追问为什么只该接 Exception（取消要能传出去，外层的 `wait_for` 和 TaskGroup 才能正确收尾）。
- 写成普通的 async 函数时，测试报的是 `'async for' requires an object with __aiter__`，要看出这里需要 async generator。

追问：
- "The lesson says these benchmarks don't measure wall-clock or cost. Where would you add them here?"（每行带上开始和结束时间；summary 里给成本分位数；和 Part 3 共用计算）
- "One agent call hangs forever."（每个任务加超时，`asyncio.wait_for`，超时记成 error；整个运行也要有总的截止时间）
- "Should invalid tasks even reach the agent?"（不该花 token：有效性是数据集的属性，应该在评测前用修复前的状态和参考补丁算好，跑的时候直接跳过）

### Part 5 GAIA 分级（目标 12 分钟）

坑：
- par 的分支可以同时跑，一条路径只走其中一个分支；把分支的调用次数相加，三个并行搜索会变成 chain 3、level 2。
- 模态按去重后计数。
- think 不是工具调用。
- level 3 要求同一条路径上既有至少 5 次调用、又有至少 2 种模态。只看最长路径的话，`hidden` 里 6 次纯网页的路径会盖住 5 次网页加图片的那条；用全计划的模态数配最长链的话，`split` 会被误判成 level 3。
- level 2 有两个条件，链长至少 2，或者全计划至少 2 种模态。只写模态那一半，连着两次网页调用会被判成 level 1。边界都是“至少”：`react` 正好 5 次调用、2 种模态，必须是 level 3。
- 裸列表是 seq 的简写，会出现在 par 里面。
- 空的 seq/par、缺 input 的工具、未知形状都报 ValueError。

参考做法是对每个节点算“每种模态集合 → 这类路径上最多几次调用”，seq 做笛卡尔组合，par 取并集里的最大值。直接枚举所有路径也能通过测试，追问时问它的复杂度。

追问：
- "Enumerating paths: how many are there for 30 two-way choices in a row?"（2³⁰；按模态集合合并以后只和模态种类数有关）
- "Real GAIA levels are assigned by the question authors. What is this classifier good for?"（课里的 `gaia_level` 只是演示“深度 + 模态 + 工具 → 难度”的直觉；可以用来给自己的评测集分层抽样，不能代替人工标注）
- "GAIA vs SWE-bench: which one do you run for a research assistant that browses and reads PDFs?"（GAIA；课里说不要把通用能力基准和代码基准混为一谈）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出沙箱、污染、分布、超时、取消 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
