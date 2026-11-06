# 面试官手册：ReWOO（14/02）

候选人计时期间不要看。候选人手里只有 README、`rewoo/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 失败的那一步，Solver 看到的是错误文本还是 MISSING？ | "The error text. The solver gets to see what went wrong. Only the steps that needed it get MISSING." |
| 1 | 要不要在执行前检查工具都存在？ | "Not here. An unknown tool is just a failed step, like the 'serch' typo." |
| 1 | 互不依赖的步骤按什么顺序跑？要并行吗？ | "Any order that respects the dependencies. One at a time is fine. The tests don't look at the order." |
| 1 | 一步能引用列表里排在它后面的步骤吗？ | "Yes. The planner doesn't always write steps in dependency order." |
| 2 | args 里键的顺序不同，算不算重复？ | "Your call. The tests don't cover it." |
| 2 | 重复的那条分数更高，要不要替换旧的？ | "No. The first one stays. Return False." |
| 2 | 可以在两次 append 之间一直开着文件吗？ | "Yes, as long as each example is in the file when append returns." |
| 2 | 进程崩溃留下半行怎么办？ | "Out of scope. The tests don't cover it." |
| 2 | score 正好是 0 或 1 可以吗？整数呢？ | "Both ends are valid, ints included. A bool is not a score." |
| 2 | 只有空格的问题算空吗？ | "Your call. The tests only check an empty string." |
| 3 | replanner 和 Solver 能看到被丢弃的步骤吗？ | "No. They see the live steps and their evidence. The run record keeps everything." |
| 3 | 没被替换的失败步骤，要不要重跑？ | "No. Nothing runs twice. Only patch steps run." |
| 3 | 补丁能引用一个失败了但没被替换的步骤吗？ | "Yes, it's still live. Then Part 1's rule skips the patch step." |
| 3 | 补丁里的 id 总是 P1、P2……按顺序吗？ | "Yes." |
| 3 | replanner 返回一个空补丁？ | "Nothing new runs, and it still counts toward max_replans." |
| 3 | 次数用完了还有失败的步骤？ | "Stop and let the solver answer with the evidence there is." |
| 3 | replanner 返回 None 时次数还没用完，要不要再问它一次？ | "No. None means it accepts the plan. Go straight to the solver." |
| 4 | 工具要并发跑吗？ | "No. Run a step right there, as soon as it is ready." |
| 4 | 一行会被切在两块之间吗？`#E1` 本身呢？ | "Anywhere. A line is complete only at its newline, or at the end of the stream." |
| 4 | `=` 两边一定是一个空格吗？ | "The planner always writes ' = '. Being lenient is fine." |
| 4 | 跑完一步以后，接着往下找就绪的步骤，还是从头找？ | "Each time, run the ready step whose line came first. The step you just ran may have freed one higher up." |
| 4 | 一行看着像步骤但格式不对？ | "Treat it like any other line that is not a step. The tests don't cover it." |
| 5 | 子计划能直接引用外层的步骤吗？ | "No. Only through imports." |
| 5 | 新编号的顺序？嵌套子计划的步骤排在它后面的兄弟步骤之前还是之后？ | "Follow the docstring. The tests only use sub-plans where both readings give the same numbers." |
| 5 | import 能指向外层自己 import 进来的名字吗？ | "Yes. That's how evidence reaches a sub-plan two levels down." |
| 5 | 顶层 id 重复呢？ | "Also a ValueError. The tests check it inside a sub-plan." |

## 每关：要看什么、提示、追问

### Part 1 修 Workers（目标 12 分钟）

一个测试里叠了 4 个缺陷和几组护栏：

1. `resolve_references` 只替换顶层字符串，列表和字典里的 `#E1` 原样传给工具。`topological` 用 `str(step.args)` 找依赖，嵌套引用也找得到，所以顺序是对的，只是值没替换。错误不在这里报：`largest` 工具把 `"#E4"` 读成 4、`"#E5"` 读成 5，挑出了 `"#E2"`，最后 Solver 写出 `#E2 has more people: ...`。断言挂在答案上，离根因隔了两层调用，而且没有任何异常。
2. 失败步骤的 `error: ...` 被当成证据代入下游。docstring 规定：依赖失败（或被跳过）步骤的步骤标 skipped，不调用工具，证据文本是 `MISSING`。修好之前，E2 拿 `population of error: LookupError: ...` 去搜，又失败一次；E6 的依赖藏在嵌套的 `items` 里，也要跳过。跳过要传递：E3 依赖的 E2 是 skipped 而不是 failed，E3 也得跳过。
3. 引用不存在的 `#E9` 时报的是 `ValueError: cyclic plan`。docstring 要求 `KeyError` 并点名 E9。判断“不存在”要对照整个计划的 id，不能对照“目前已经排好的步骤”，否则真正的环（E1↔E2、E1 引用自己）也会被报成 KeyError；也不能对照“列表里排在它前面的步骤”，E3 引用的 E4、E5 就排在它后面。
4. `topological` 每一轮都对所有待定步骤重新 `str(args)` 加正则，一轮只放行一步。倒序给出的 3000 步链要 3000 轮，约 1.8 秒；测试要求 0.1 秒内。预先抽一次引用，用入度加队列（Kahn 算法），约 5 毫秒。
5. 护栏：
   - 计划本身不能被改写。递归替换时原地改列表和字典，第二次跑同一个计划就没有引用可替换了。
   - `#E1` 和 `#E10` 是两个步骤。逐个 `str.replace("#E1", ...)` 会把 `#E10` 改成 `Paris0`；正则写成 `#E\d` 也一样。E3 的 title 又提到了一次 `#E1` 和 `#E2`：入度按“步骤”只算一次、释放时却按“出现次数”减，E3 会在 E4、E5 之前就被放行（`KeyError: 'E4'`）。
   - 计划不能执行时一个工具都不调用：拓扑排序写成边排边执行的生成器，E1 会在报 KeyError 之前就跑掉。
   - 反过来，不要在执行前检查工具是否都注册了、没注册就让整份计划报错：`serch` 那一步应该是 failed，别的步骤照常执行（澄清问题里也这样答）。
   - 递归 DFS 排序在 3000 层上 RecursionError；只缓存引用、仍然一轮轮重扫的“半修”约 0.8 秒，还是超时。
   - Kahn 算法不建“谁依赖我”的表，每出队一步就把所有步骤扫一遍，也是平方级。3000 步在本机约 0.2 秒，测试能抓住，但离 0.1 秒的限值只有两倍左右，换一台快得多的机器可能会过。看到这种写法要追问复杂度。
   - 在 `json.dumps(args)` 的文本上做替换再 `json.loads` 回来，看起来一次解决了嵌套，但 Paris 的人口证据里有双引号（`("Paris proper")`），JSON 会坏掉。

看什么：是不是先问“`#E2` 是从哪来的”，而不是去改 `largest`；有没有打印工具实际收到的参数；改跳过逻辑时有没有想到传递；改排序时有没有顺手把报错类型分清楚。

提示：
- H1："The answer says '#E2 has more people'. Where did '#E2' come from?"
- H2："Print the arguments the largest tool actually receives."
- H3：直接指出 `resolve_references` 开头的 `if not isinstance(value, str): return value`。

追问：
- "The lesson says the solver sees the error and degrades gracefully. Why not pass the error text down to the next tool too?"（下游工具会把错误当数据：测验 Q11 里 `error: 404 not found` 被 `rounded_million` 读成 `404 million`，错误伪装成了答案）
- "Exercise 1: run independent steps in parallel. Is your order already the levels?"（不是。拓扑序只保证先后；要并行，得把入度同时归零的一批当作一层；测验 Q9 那个 6 节点 DAG 分成 4 层）
- "What would you validate before running anything?"（本课 skill：无环、每个引用都有生产者并指出是哪条边、工具都在目录里、参数和引用替换后的类型符合 schema）
- "Why not find dependencies with str(args)?"（每次都要重新扫描，慢；还会把字典键里的文本也当成引用）

### Part 2 蒸馏数据集（目标 10 分钟）

坑：
- 行格式由 docstring 和测试决定：每行一个 JSON 对象，键是 question、steps（id、tool、args）、answer、score，文件以换行结尾。用 `indent=2` 会报 JSONDecodeError；照搬 `dataclasses.asdict` 会多出一层 `plan`，测试取 `steps` 时 KeyError。
- `reader` 在任何 append 之前就创建了。它每次 `examples()` 都要读文件；构造时或第一次调用时读一次缓存起来，就看不到后来的记录。append 返回时记录必须已经在文件里：一直开着句柄又不 flush，读者什么也看不到。
- 问题里有 U+2028（行分隔符，网页抓来的文本里常见）。`ensure_ascii=False` 会把它原样写进文件，读的时候再用 `str.splitlines()` 切行，这一行就被切成两半，JSONDecodeError。默认的 `ensure_ascii=True`，或者按文件行迭代，都不会出事。
- 读回要完全一致：参数里 1、1.0、True、None，键的顺序（`sort_keys=True` 会改掉），Step 对象而不是字典，列表而不是元组，整数 score 不能变成 1.0。测试比较的是 `repr`，`==` 分不出 1 和 1.0。
- 去重：同一个问题加同一组步骤才算重复，answer 和 score 不参与；只看 steps 也不对（换个问法是新样本）。1、1.0、True 是三个不同的计划，可 Python 的 `==` 和 `hash` 认为它们相等，用 `example in existing` 去重会把 1.0 那条丢掉。用 JSON 文本当键就分得开。
- 重开：用 `"w"` 打开会清空文件；去重集合只放在内存里，重开后同一条又能写进去。
- 先校验再写：空问题、score 越界、NaN、布尔值、空计划、重复 id、引用了计划里没有的步骤（藏在嵌套参数里）。`score < 0 or score > 1` 会放过 NaN；`isinstance(True, int)` 是 True。0 和 1 都在范围内：写成 `0 < score` 会拒掉测试最后那条 0 分的样本；只认 float 会拒掉整数 1。
- `examples(min_score)` 包含等于的情况；文件还不存在时返回空列表，不要报 FileNotFoundError。

追问：
- "Exercise 4: what training data do you need, and how do you score plan quality?"（(question, plan) 对，Planner 看不到观察结果所以可以离线批量采；按执行后 Solver 是否答对打分，只拿高分计划训练学生模型）
- "Why does 1 versus 1.0 matter here?"（学生模型学的就是这段文本；工具 schema 写的是 integer 时 1.0 会被拒；本课 skill 要求检查引用替换后的类型）
- "Ten million examples later, how do you dedupe?"（只存规范化 JSON 的哈希；按问题哈希分片；或者交给有唯一索引的库）
- "Two teacher jobs append at once?"（每个进程各有一份去重集合，会写进重复；用单一写入方、文件锁，或者合并时再去重）

### Part 3 局部重规划（目标 14 分钟）

坑：
- 新编号接在计划里最大的步骤号后面，被丢弃的步骤也算。按字符串取最大值，`"E9" > "E10"`，补丁会从 E10 开始，撞上已有的 E10。按步骤个数 +1 也不行：paris 计划跳过了 E3，`len + 1` 是 E4，撞上已有的 E4。只看存活步骤的最大号，会和被丢弃的 E9、E10 撞号。每一轮都要用最新的计划，第二个补丁从 E7 开始。
- 补丁里的 `#P1` 要改写成新 id（嵌套的列表里也要改），`#E1` 这类对保留证据的引用原样不动。
- 下游要沿嵌套引用找（E9 的 `values` 列表里引用了 E4），要传递（E10 依赖 E9），还要跨轮次（第二个补丁替换 E1，第一个补丁里引用了 `#E1` 的 E5、E6 也要丢弃）。这里的触发不是异常：E4 的结果是 `no data`，状态是 ok，所以不能靠 failed/skipped 状态推出该丢哪些。
- 只跑补丁步骤，保留的证据不重跑。直接把补丁当计划交给 Part 1 的 `run_workers`，它会因为 `#E1` 不在这个小计划里报 KeyError，需要让它接受“计划外已有的证据”。整个存活计划重跑一遍，搜索会从 9 次变成 16 次。
- Solver 和 replanner 只看存活步骤；`run.evidence` 保留全部记录。交给它们的计划和证据要对得上：计划给全部步骤、证据只给存活的，测试里的替身会直接报 "each live step with its evidence"。失败和跳过的步骤也是存活的，replanner 要看到它们才知道该补哪里；只给成功的步骤，paris 那组里它两次都只看到 E1。max_replans 用完、还有失败时，Solver 照样作答，失败步骤给错误文本，跳过的给 MISSING。
- replanner 最多被问 max_replans 次。多问一次（`range(max_replans + 1)` 或者 `while True` 等它接受），脚本化的 replanner 会直接报 "asked for more patches than max_replans allows"。它返回 None 就是接受，之后不再问：第一组 max_replans=3，replanner 第二次就接受了，返回 None 后还接着循环，替身会报 "once the replanner accepts the plan, it is not asked again"。`max_replans=0` 就是纯 ReWOO；负数报 ValueError。
- 补丁先整体校验再执行：引用了被丢弃的步骤报 ValueError，引用不存在的步骤、`#P` 或替换不存在的步骤报 KeyError。边跑边校验的话，P1 已经搜过一次了，测试数到 11 次调用。

追问：
- "Exercise 2: what is the smallest change that turns ReWOO into Plan-and-Execute?"（加一个能看到观察结果的 replanner；讲义说这让它更接近 ReAct，但保住了 token 上的节省）
- "How do you keep the replanner from turning into ReAct?"（测验 Q17：只在失败或检查点触发；设次数和成本上限；只改受影响的子图；把失败原因写进 replan 的约束）
- "Why not just replan from scratch?"（保留的证据要重新花钱拿；有副作用的工具会再执行一次）
- "A dropped step had already charged a card. Is it undone?"（不会。丢弃证据不等于撤销副作用；需要补偿动作或幂等键）

### Part 4 流式计划（目标 12 分钟）

坑：
- 一行在换行处才算完整；流结束时没有换行的最后一行（这里正是 `#E2`）也要处理。逐块解析、或者看到 `]` 就当这一行写完，都会在切块的地方出错：grep 的输入是 `[0-9.]+ million`，写到 `[0-9.]` 时就以 `]` 结尾了。
- 输入取第一个 `[` 到最后一个 `]` 之间；非贪婪的 `\[(.*?)\]` 会截在第一个 `]`。
- 引用还没出现的步骤要等。一步完成后要反复检查等待中的步骤，直到没有能跑的：E2 到达后 E7、E4 能跑，E4 跑完 E5 才能跑。只扫一遍的写法会把 E5 留到流结束，报 "steps wait on each other"。同时就绪的按行的先后跑：E7 在 E4 前面，按编号排就错了。
- 每跑完一步都要从头找：cascade 那份计划里 E1 最后到达，E2、E4 就绪；E2 跑完，E3 也就绪了，它的行在 E4 前面，要先跑。一轮扫到底、跑完一步接着往下扫的写法会先跑 E4、E5，最后才跑 E3。
- 记录行里的输入是替换后的；证据里的换行改成一个空格（grep 返回两行），每条记录恰好一个换行。替换进输入的证据也会带换行：cascade 里 E5 的输入就是 grep 的两行结果，只处理证据的话，这条记录会断成两行。
- 失败步骤记录错误文本；依赖它的步骤记 `skipped`，输入保持原样，不调用工具。
- 同一个 id 写两次报 ValueError，第一次那行还在等待时也一样（只查已经跑完的步骤会漏掉）；流结束时还在等一个从没出现的 id，报 KeyError 并点名这个 id（不是点名在等的那一步）；互相等待报 ValueError。
- 第一条记录要在计划流结束前出来：先把整个流读完再执行，探针数到 50 块。
- 写成普通函数（没有 yield）时，测试报 `'async for' requires an object with __aiter__ method, got coroutine`，要会看出这里需要 async generator。

追问：
- "Why bother streaming the plan?"（ReWOO 里 Planner 那一次调用最大，边写边执行能把规划的延迟藏在工具调用后面）
- "The planner changes its mind about a step that already ran. Now what?"（跑过的收不回来；有副作用的步骤要等计划校验完，或者加人工确认）
- "The tools are slow network calls. What changes?"（就绪的步骤用 task 并发，记录按完成顺序输出；这是第 13 章 03 课 fan-out 的问题）
- "Why a line format instead of JSON?"（一行一步，模型逐 token 写也好解析；JSON 要增量解析器，见第 13 章 03 课 Part 5）

### Part 5 子计划展开（目标 12 分钟）

坑：
- 子计划里的 `#E1` 是它自己的 E1；外层证据只能经 imports 进来。population_of("E4", "E2") 里，`#E1` 是 import（外层 E2），`#E2` 是自己的第一步（新编号 E7）。
- 改写要一次完成。按映射逐个 `str.replace`：先把 `#E1` 改成 `#E2`，再把 `#E2` 改成 `#E7`，import 进来的引用被改了两次。用一次正则替换（回调里查映射）就没有这个问题。
- output 那一步拿子计划自己的 id，外层引用 `#E3` 得到的就是它的证据；output 本身也可以是一个子计划（wrapper），id 一层层传下去。
- imports 在直接外层的作用域里解析：density 里的嵌套子计划 import 的是 density 的 `E9`，顶层根本没有 E9。外层没有 import 的名字，内层也不能 import（`population_of("E2", "E1")` 放在一个没有 import E1 的子计划里要报错）。
- 不能“找不到就去外层找”：子计划里直接写 `#E1` 而没有 import，要报 KeyError。
- 新编号从顶层最大步骤号往上数：顶层是 E1、E2、E4，新编号从 E5 开始；用顶层个数会从 E4 开始，撞上 wrapper。子计划里的本地 id 不算：density 里有本地的 E8，把它也算进最大值会从 E9 开始编号。
- 校验：空子计划、output 不是自己的步骤（指向一个 import 也不算）、import 和步骤同名、id 重复，都报 ValueError。
- 不能改动输入的嵌套计划：原地改写参数，`repr(nested)` 就变了。

追问：
- "Exercise 5: Plan-and-Act's plan is a sequence, not a DAG. What changes?"（失去并行和按节点定位失败；换来更简单的规划格式，适合长程网页任务）
- "Why flatten instead of running each sub-plan with its own executor?"（一个执行器、一张证据表、全局的拓扑序，子计划之间也能并行；失败跳过的规则不用再写一遍）
- "The same sub-plan is used 20 times. Does the plan have to grow 20x?"（按“子计划 + 导入的证据”缓存结果；或者把调用保留成一个节点，单独执行）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看工具实际收到的参数、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出执行前校验、副作用、去重规模、重规划预算 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
