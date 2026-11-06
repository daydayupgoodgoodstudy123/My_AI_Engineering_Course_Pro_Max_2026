# 参考答案讲解：swebench（14/19）

计时结束后再看。参考实现在同目录的 `swebench/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修测试闸门

**现象**：解锁后的第一个失败是 “a patch that breaks a PASS_TO_PASS test is unresolved”。这个补丁修好了 reset_to，同时把 step 从 1 改成了 2，test_step 应该挂；可结果里补丁后的 test_step 还是 True，任务被判成了 resolved。

**依次修四处**：

1. `run_task`：打完补丁只重跑了 FAIL_TO_PASS，PASS_TO_PASS 照抄补丁前的结果。PASS_TO_PASS 修复前本来就通过，这样写看上去省掉了一半测试，可它检查的就只剩“补丁前通过”，不再是“补丁后仍然通过”，打坏 PASS_TO_PASS 的补丁一律被判成 resolved。课里 t003 那个顺手改坏 flag 的补丁就是这种情况，skill 的硬拒绝里也有一条“没有 PASS_TO_PASS 闸门的 harness”。docstring 写的是打完补丁后整套测试重跑：`after = _gate(run_tests(task.tests, patched), ids)`。
2. `passed`：报告行用 `line.split()` 切开、取第二段当 test id。pytest -rA 的每一行是 `<STATUS> <test id>`，参数化的 id 带方括号，里面可以有空格：`test_strip[two words]` 被切成 `test_strip[two`，永远对不上，被当成没通过。报错不在 `passed` 里，而在两层之外 `run_task` 给出的结果里：修好 strip 的补丁，ftp_passed 是 0。要先 `print(log)`，才看得出报告里明明写着 PASSED。只在第一个空格处切开（`partition(" ")`），再拿后半段整串比较。
3. `run_task`：先判任务是否有效。没有 FAIL_TO_PASS 测试、某个 FAIL_TO_PASS 测试修复前就通过、某个 PASS_TO_PASS 测试修复前就失败，这三种任务都区分不了修复和什么都不做，记成 invalid，不打补丁，也不进分母。课里 Verified 去掉不可靠测试，以及 quiz Q9 里那个空补丁被判成 resolved 的例子，说的都是这件事。一个测试不成立就够了，所以条件是 `any(before[:nf])` 和 `not all(before[nf:])`。这一步要放在打补丁之前：无效任务的补丁根本不执行，就算它会报错，状态也是 invalid。
4. 速度：原来每找一个测试 id 都把整份报告从头扫一遍，3500 个测试就是 O(T²)，本机要 1 秒多。把报告解析一次成 `{id: status}`，判定就是线性的了。只把拆行提到循环外、再对每个 id 做列表的 `in`，结果是对的，但仍然是 O(T²)，只是比较在 C 里做，本机 50–90 ms，这个测试拦不住。

**起始代码里已经对的**：`run_tests` 把抛异常的测试记成一行 `ERROR <id>`，接着跑下一个。修复前的 FAIL_TO_PASS 测试访问还不存在的 reset_to 键，会抛 KeyError；`demo__half-5` 里有个测试修复前抛 ZeroDivisionError。测试直接核对 `run_tests` 的输出，所以这里要接的是 `Exception`，报错的测试记 ERROR，不记 FAILED，也不能让它中断整轮。

**护栏**：
- 修第 1 处时不要只改状态。只看 FAIL_TO_PASS 判 resolved，或者另跑一遍整套测试来定状态、计数和 outcomes 还用旧的，都过不了比对整个 TaskResult 的那条断言。
- 不要为了保住提速，只在 FAIL_TO_PASS 全部通过时才重跑 PASS_TO_PASS。一个没修好、又把 step 改坏的补丁，ptp_passed 应该是 0，docstring 说计数取补丁之后的结果。
- 报告行用 `partition(" ")` 切成状态和 id。改成在整行里找 id，或者用 `startswith`，`test_split` 会匹配到排在前面、已经通过的 `test_split_lines`；按空白切开再用一个空格拼回去，`test_strip[word  ]` 里的两个空格会变成一个；取最后一段（`split()[-1]`）也一样截断。
- 不要在 `run_task` 外面整个包一层 try/except，然后把任务记成 error。那样修复前报错的 FAIL_TO_PASS 测试会让每个任务都变成 error。
- 不要为了提速只跑修复后的测试、直接相信两张列表。有效性要靠修复前的那一轮来判断。

**课里的净值计数**：`code/main.py` 用 `ptp_pre - ptp_post` 判断有没有打坏 PASS_TO_PASS，一个测试被打坏、另一个原本失败的测试被修好时，净值是 0，会误判成 resolved。这套题的判定是逐个测试看修复后的结果，再加上有效性检查要求 PASS_TO_PASS 修复前全部通过，这个误判就不会出现。

## Part 2 结果 CSV

两个文件：`runs.csv` 每个任务一行（状态、成本、补丁原文），`tests.csv` 每个测试结果一行。先校验，再写；先写 `tests.csv`，最后写 `runs.csv`。读的时候以 `runs.csv` 为准，按 instance id 把测试行挂回去。

容易漏的几点：

- **读写都用 `newline=""`**：csv 模块自己处理引号里的换行。读的时候不加，通用换行模式会把补丁里的 `\r\n` 变成 `\n`。
- **类型**：CSV 里全是字符串。成本用 `int()` 读回，passed 按 `== "1"` 读回。`bool("0")` 是 True；`float()` 读回的成本能通过 `==`，过不了类型检查。
- **表头只写一次**：文件不存在时才写。
- **重复 id**：打开时从 `runs.csv` 读出已有的 id，不能只记在内存里。
- **先校验再写**：status、成本、phase、重复 id 全部查完再动文件。被拒的记录都带着测试结果，任何一项检查放到写 tests.csv 之后，同一个 id 之后重写时，读回来就会多出旧的测试行。
- **读以文件为准**：`get()` 和 `records()` 都从文件读，重开之后照样拿得到；按写入顺序返回，不按 id 排序。
- 成本必须是非负的 int。`900.0` 写得进去，读的时候 `int("900.0")` 会报错，所以在写之前拒绝。

## Part 3 三种口径和分位数

**泄漏检查**（课里练习 3、skill 的 30% 规则、quiz Q11）：只看 diff 的新增行，去掉 `+++` 文件头和空行；每行把连续空白压成一个空格、去掉首尾，和 issue 里同样规范化过的某一整行相等就算泄漏；新增行里至少 30% 泄漏，补丁就算泄漏。比较时用整数 `100 * hits >= 30 * len(added)`，不碰浮点。整行比较是为了不把 issue 正文里的 “pass”、“)” 这种短片段当成泄漏。规范化是 `" ".join(line.split())`：连续空白压成一个空格，不是删掉，否则 `return x` 和 `returnx` 会相等。

**最近秩**：第 ceil(p·n/100) 小的值，用整数写成 `-(-p * n // 100)`。quiz Q12 的步数 `[3, 5, 4, 12, 7, 6, 25, 4, 5, 8]` 给出 P50 = 5、P75 = 8、P95 = 25。插值会得到 5.5，把秩当成 0 基下标会得到 6。p=0 时 ceil 得 0，docstring 要求至少取第 1 个，所以写 `max(1, ...)`；漏掉的话 `xs[-1]` 返回的是最大值。

**三种口径**：

- 先去掉 invalid，剩下的都计分；error 计分，算未解决。
- `all` 是全部计分任务，`verified` 是其中 id 在 Verified 集合里的。
- `plus` 和 `all` 是同一批任务，但修复内容泄漏的 resolved 按未解决算，任务数不变。这和 quiz Q12 里 50% × (1 − 0.3267) 的算法一致，也是课里“50% 可能变成 35%”的意思。
- 没有任务的视图，rate 和三种成本都是 None。

最后一段把 Part 1–3 串起来：课里的 t001、t002 被修好，t003 越界打坏了 `flag`，全部口径的解决率是 2/3，和课里 `code/main.py` 打印的 resolution rate 一样；Verified（只有 t001）是 1.0。

## Part 4 并发评测流

用一个 `Semaphore(concurrency)` 限流，每个任务一个 worker，做完把结果行放进队列；生成器从队列里取一行就 yield 一行，取满任务数之后再输出 summary：

```python
workers = [asyncio.create_task(work(task)) for task in tasks]
try:
    for _ in tasks:
        status, line = await done.get()
        counts[status] += 1
        yield line
    yield json.dumps({"summary": counts}) + "\n"
finally:
    for worker in workers:
        worker.cancel()
    await asyncio.gather(*workers, return_exceptions=True)
```

- worker 里只接 `Exception`：agent 的报错变成一行 error，`CancelledError` 不在其中，取消能照常生效。写成 `except BaseException` 测试也能过，但 worker 会把取消当成 agent 报错，写一行再正常结束，取消就传不出去了。
- 只接一部分异常的话，worker 静默死掉，读的一方永远等不到最后一行。
- `finally` 先取消再等待，`aclose()` 返回时不会留下还在跑的 agent。
- `counts` 一开始就有四个键，空运行也输出完整的 summary。
- 测试里的 agent 按事件循环轮数“思考”，不用真实时间，所以完成顺序是确定的：b、c、d、e 先后完成，50 轮的 a 最后。

## Part 5 GAIA 分级

对每个节点算一张表：模态集合 → 读这些模态的路径上最多几次工具调用。

- 工具调用：`{ {input}: 1 }`；think：`{ {}: 0 }`。
- seq：从 `{ {}: 0 }` 开始，逐个子步骤做组合，集合取并、次数相加，同一集合保留最大值。
- par：各分支的表合并，同一集合保留最大值。一条路径只走一个分支，所以不相加。

整棵树的表算出来以后，chain 是表里最大的次数，modalities 是所有集合的并集；某个集合至少 2 种模态而且次数至少 5，就是 level 3。level 2 的两个条件各自成立就行：连着两次网页调用，链长 2、只有一种模态，也是 level 2。

只看最长路径会错：`hidden` 里最长的是 6 次纯网页搜索，真正跨模态的那条只有 5 次。用全计划的模态数配最长链也会错：`split` 里 5 次调用的那条路径只有网页，带图片的那条只有 4 次。直接枚举所有路径也能通过测试，但路径数随串联的并行选择指数增长；按模态集合合并以后，表的大小只和模态种类数有关。

## 这套题证明了什么，没证明什么

通过了说明你能在 SWE-bench 式的 harness 里调试测试判定、把评测结果原样存进 CSV、按课里的要求报告 Verified、SWE-bench+ 和分位数，写出带并发上限和取消的评测流，以及在分解树上做路径分析。它没有在真实仓库上跑测试，也没有沙箱、Docker 或真实模型；泄漏规则和 GAIA 分级规则都是这套题自己的简化，不是 SWE-bench+ 论文或 GAIA 数据集的官方方法。AgentBench 的八个环境这里没有涉及，课里的练习 1、4、5 需要另外动手做。
