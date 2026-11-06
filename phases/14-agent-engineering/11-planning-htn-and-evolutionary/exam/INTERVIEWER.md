# 面试官手册：HTNPlan（14/11）

候选人计时期间不要看。候选人手里只有 README、`htnplan/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 方法的前置条件成立、但子任务失败了，要问 LLM 吗？ | "Yes, once every library method and the learned decomposition have failed for this task in this state." |
| 1 | 学到的分解失败了，LLM 新给的分解要替换它吗？ | "Yes. Keep the newest one that worked." |
| 1 | 失败记录要跨 plan() 调用保留吗？ | "No. Each call starts fresh. The LLM may answer differently next time." |
| 1 | LLM 的回答里有一个未知名字，是去掉它还是整条拒绝？ | "Reject the whole reply. Never plan a name that is outside the schema." |
| 1 | max_depth 从哪一层算起？ | "The requested task is depth 0. Nothing may sit deeper than max_depth." |
| 2 | 方法名能重复吗？不同任务之间呢？ | "No. Names are unique across the whole library. Raise a ValueError." |
| 2 | 名字里会有哪些字符？ | "Anything printable. The canary steps have percent signs, and some facts have spaces and commas." |
| 2 | 别的程序会读这个文件吗？ | "Yes. Another tool reads task and source straight from the INI." |
| 2 | 两个进程同时写怎么办？ | "Out of scope. Two objects in one process, adding one after the other, is in scope." |
| 3 | generations 包不包括第 0 代？ | "No. It counts the generations after the seed, so generations=2 reports generations 0, 1 and 2." |
| 3 | 父代和变异器，哪个在外层循环？ | "Parents. The best parent goes through every mutator, then the next parent." |
| 3 | 预算在一代中途用完，这一代还报告吗？ | "Yes. Close it with the children you have, report it, then stop." |
| 3 | 缓存命中算预算吗？ | "No. Only evaluator calls count." |
| 3 | target 是每个孩子之后检查，还是每代之后？ | "At the end of a generation, generation 0 included." |
| 3 | 同一代里两个孩子一模一样怎么算？ | "The second one is a cache hit." |
| 4 | 要表头吗？换行用 `\r\n` 还是 `\n`？ | "Yes, one header line first. Either line ending is fine." |
| 4 | 能按变异完成的先后来评估吗？ | "Only if the result cannot depend on it. With a budget it can, so no." |
| 4 | 有个模型一直不回答怎么办？ | "You only cancel when the budget runs out. No timeouts in this part." |
| 5 | 路径用什么表示？ | "Child indices from the root, as a tuple. The root itself is the empty tuple." |
| 5 | 学到的分解在树里标什么？ | "llm. Only library methods have names." |
| 5 | 一棵树里有好几处问题，报哪一个？ | "The first node in plan order that breaks. A task comes before its subtasks." |

## 每关：要看什么、提示、追问

### Part 1 修规划器（目标 12 分钟）

一个测试里叠了 4 个缺陷和几组护栏：

1. `_plan` 只试第一个前置条件成立的方法（`applicable[0]`），它的子任务失败了也不试下一个；而且只要有方法的前置条件成立，就不会走到 LLM。现象是 `plan("release", ...)` 返回 None，没有任何异常。根因在两层分解之下：`release` 的方法没问题，是 `deploy` 先选了 `deploy_canary`（前置条件成立），`watch_canary` 需要 `metrics_on` 失败，没有回溯到 `deploy_direct`。docstring 写的顺序是：前置条件成立的每个库方法（按库里的顺序）、学到的分解、新问一次 LLM，第一个能展开的胜出。
2. LLM 的回答先写进 `cached_methods`，再展开。`("open_pr",)` 的名字都合法，但在 `{"logged_in"}` 下展开失败，照样被学了进去。测试在这一步直接检查 `cached_methods == {}`；不查的话，这个错要到下一次请求才显出来：缺陷 3 让缓存里的坏分解失败后直接返回 None，从此不再问 LLM。
3. 走学到的分解失败时直接 `return`，不再回退去问 LLM。`hotfix` 学到的分解在已登录时能用，换到未登录的状态就失败，这时应该问 LLM。这一次 LLM 给的 `("open_pr",)` 也展开不了，学到的分解原样留着；下一次请求再问，拿到 `("ship_change",)`，才替换旧的。
4. 加上回溯以后，失败过的（任务, 状态）没有记下来。`rollout` 的第一个方法要发 18 波，每波有两种方法、结果状态相同，最后的 `cab_signoff` 永远做不成：2^18 条路径都在同一个死胡同里失败，约 0.7 秒，测试限 0.05 秒；每条路径还都问一次 LLM，一共 52 万次。在一次 `plan()` 调用里按 `(task, frozenset(state))` 记下失败，同一状态不再重试，约 50 微秒，LLM 只问 19 次。
5. 护栏：
   - 失败记录的键要包含状态。`redeploy` 先试 `redeploy_existing`，这时还没构建，`deploy` 失败；再试 `redeploy_from_main`，构建以后 `deploy` 必须成功。只按任务名记，会把它跳过。
   - 失败记录只在一次调用里有效。`hotfix` 的第二、三次请求都要重新问 LLM。把记录挂在实例上不清，或者把 LLM 的回答按（任务, 状态）缓存，第三次请求拿不到能用的分解。
   - 回答里有 schema 外的名字（`push_to_main`），整条回答在展开前拒绝。去掉名字检查，规划器会去“规划” `push_to_main`，又问一次 LLM 怎么分解它；只删掉那个名字、留下其余的，会把 `("open_editor",)` 学进去，第一次请求就返回了计划。
   - LLM 的新回答展开失败时，已经学到的分解不能动。修缺陷 2 时先写缓存、展开失败再 `del`，`cached_methods == {}` 那条能过；可 `hotfix` 从未登录状态请求时，先写进去的 `("open_pr",)` 盖掉了学到的 SHIP，失败后一删，SHIP 也没了。
   - 方法按库里的顺序试：有 `metrics_on` 时要走金丝雀。按子任务个数排序、先试短的，会选成直接发布。
   - 库方法在学到的分解之前，学到的分解在新问 LLM 之前（省一次调用）。
   - 用展开次数上限代替失败记录：死胡同确实停下来了，但 LLM 被问了 4999 次。
   - 调用方传进来的 `state` 不能被改。

看什么：是不是从 `release` 往下逐层打印每个任务试了哪些方法；有没有分清“前置条件成立”和“能展开”是两回事；修缓存时有没有区分“学到了”和“试过”；失败记录的键和作用域是不是想清楚了再写。

提示：
- H1："Which task is the first to give up, and which methods did it try?"
- H2："deploy has two methods whose preconditions hold. How many does the code try?"
- H3：直接指出 `applicable[0]` 和 `if not applicable:` 两处。
- 计时那一步卡住时："How many times is wave17 planned, and from how many different states?"

追问：
- "Your failure record ignores depth. Is that safe with max_depth?"（在深处因为深度上限失败的任务，换到浅处可能成功。可以把剩余深度放进键，或记下失败时的最浅深度；本题按 docstring 不重试，不过键里带上深度测试也能过，可以接受。）
- "The learned decomposition has no preconditions. How would you generalize it?"（课里的 online method learning：用回归把计划实际依赖的初始事实算成前置条件，按状态模式缓存。讲义说这样最多减少 75% 的 LLM 查询。）
- "The hotfix plan is sound. Does it do what a hotfix means?"（sound 只说明每一步都能执行，不说明达成目标；需要目标条件，比如结束状态里必须有某个事实。）
- "An operator fails at run time. What then?"（讲义练习 1：执行期回溯需要补偿动作。规划期的回溯不用撤销，因为每一步都产生新的状态。）

### Part 2 方法库（目标 10 分钟）

坑：
- configparser 默认的 BasicInterpolation 不认单独的 `%`。值里有 `shift_10%`、`error_rate < 1%`、备注里的 `100%`，写的时候报 `ValueError: invalid interpolation syntax`；只在读的一侧用默认解析器，取值时报 `InterpolationSyntaxError`。用 `interpolation=None` 或 RawConfigParser。
- configparser 会去掉值首尾的空白，续行的行首空白也去掉，续行里以 `#` 开头的行当注释丢掉，结尾的换行也留不住。备注要原样读回，就得编码，比如 `json.dumps` 成一行带引号的字符串。手工把换行换成 `\n` 两个字符，开头的两个空格照样丢。
- 空列表：`"".split(",")` 是 `[""]`，`fresh_login` 的前置条件和 `reuse_session` 的子任务会读回成 `("",)`。按空白切又会把 `error_rate < 1%` 切成三个名字。补上空列表的判断也不够：`approved_by(release-eng, sre)` 本身带逗号。
- 每个名字一行写成多行值、读回时 `splitlines()`，测试能过：名字都是可打印字符，没有换行。可以接受；追问时可以指出，configparser 会去掉名字开头的空格，以 `#` 或 `;` 开头的名字会被当成注释丢掉。
- 读回来要是 tuple。list 和 tuple 比较不相等。
- 每个任务的方法顺序就是规划器尝试的顺序，`methods()` 不能排序：按名字排，`fresh_login` 会跑到 `reuse_session` 前面。
- 同一个文件有两个对象：每次 add 都要以磁盘上的文件为准。每个对象只记得自己加过的方法、每次整体重写，或者用 `"w"` 只写自己这一节，都会冲掉别人写的。先把磁盘上的整个文件读进来、加上新的一节、再用 `"w"` 整体写回，测试能过：同一进程里先后添加不会丢，两个进程同时写才会丢，放进追问。重名检查也要读文件，只查自己内存里的，会漏掉另一个对象加的 `fresh_login`。
- 重名要报 ValueError，名字在整个库里唯一：只在同一个任务里查重，`log_back_in` 下的 `fresh_login` 就混进去了。不检查就追加出第二个同名节；交给 `add_section` 报的是 `DuplicateSectionError`，不是 ValueError；用 `parser[name] = ...` 赋值会悄悄覆盖。
- 非法的 source（`gpt`）要在写文件之前拒绝，被拒的方法不能留在文件里。
- 文件还不存在时，`entries()` 返回空列表。
- task 和 source 写成普通值，别的工具（测试里是另一个 ConfigParser）可以直接读；把它们也 JSON 编码就挂。

追问：
- "Two processes add a method at the same moment?"（追加写不保证原子；用文件锁，或写临时文件再 rename，或换 SQLite。）
- "Why keep learned methods in a file people can read?"（LLM 学来的东西要能审查、能 diff、能回滚；符号层负责正确性，人也得看得懂它依据的是什么。）
- "A learned method turns out to be wrong in production?"（按 source 整批停用；记下学到时的状态和失败次数，到阈值自动退役。）

### Part 3 进化搜索（目标 13 分钟）

坑：
- 第 0 代就是种子本身，它的那次评估也要计数。
- 每个变异拿到的是父代的副本。测试里的 `b_up` 和 `nudge` 会原地改传进来的列表，就像一个直接改文件的工具。把调用方的种子列表直接交出去，种子会被改；一个父代只复制一份、整个集成共用，第二个变异器拿到的是第一个改过的。
- 排名键是 (fitness, genome)。只按 fitness 排，并列时沿用候选的先后顺序，第 1 代就会留下 [5, 6] 而不是 [4, 5]。
- 父代在外层：最好的父代依次交给每个变异器，再轮到下一个父代。`budget=5` 那条断言里，预算在第 2 代的第二个孩子用完，按这个顺序评到的是 [4, 6] 和 [3, 5]；变异器放在外层会评到 [4, 6] 和 [5, 7]，这一代最好的就成了 [4, 6]。这里错了不抓住，到 Part 4 会变成第 7 代对不上，很难往回查。
- `generations` 是种子之后的代数：`generations=2` 返回第 0、1、2 代。`range(1, generations)` 少跑一代。
- 父代互不相同：[3, 6] 被两个父代各变出来一次，只算一个。保留重复，下一代的评估和命中次数都会变。
- 缓存跨代有效，同一代里的重复也算命中。
- 预算只算真正的评估，命中不算。评估次数一到预算就停：这一代剩下的变异不再做，命中也不再算（`budget=6` 那条断言）。只在代与代之间看预算，会多评估；比较写成 `>`，多一次。被截断的那一代照样要报告。
- target 在一代结束时检查，第 0 代也算；在每个孩子之后检查，会少评估。写成 `if target and ...` 会把 0.0 当成没有 target，而测试里的 target 正好是 0.0。
- 随机数：每个变异用 `random.Random(f"{seed}/{g}/{p}/{m}")`，p 是父代名次（0 是最好的），g 从 1 开始。整次运行共用一个生成器、每代一个生成器、编号错一位，种子跑出来的历史都会不同。先 `random.seed(...)` 再把 `random` 模块当生成器传进去，结果一模一样，但改了全局随机状态，测试会比较 `random.getstate()`。
- 精英保留：下一代父代从父代和孩子里一起挑。只从孩子里挑，最好的会变差，种子跑出来的历史也不对。从所有评估过的基因组里挑前 `survivors` 个，结果和从父代加孩子里挑完全一样（排名是全序，落选的基因组前面总有 `survivors` 个更好的还在），可以接受。

追问：
- "Why one generator per mutation instead of one for the run?"（结果只取决于参数，不取决于调度顺序；Part 4 并发时靠的就是这一点，和 numpy 的 SeedSequence.spawn 是一个思路。）
- "The lesson says the evaluator must be deterministic and fast. What breaks with an LLM judge?"（选择会留下运气好的候选，缓存也失去意义，候选还会学会讨好评委；讲义和 skill 文件都把 LLM judge 列为硬拒绝。）
- "The evaluator is a test suite. How do you keep the search from gaming it?"（留出集、多组数据、对结果语义设正确性门槛，防 reward hacking。）
- "An evaluator returns NaN?"（NaN 和谁比都是 False，排序会乱；当成最差，或者直接报错。）

### Part 4 异步变异集成（目标 12 分钟）

坑：
- 格式由测试的解析代码决定：第一行是表头，之后每代一行，每行以换行结尾。`best_genome` 是 JSON 列表，里面有逗号，要按 CSV 规则加引号；手工用逗号拼接，`json.loads` 会报 JSONDecodeError。fitness 不能四舍五入，`9.727272727272727` 要原样写出。
- 一代的变异要同时开始，测试数到同时在跑的最多 6 个；一个个 await 只有 1 个。
- 评估器一次只评一个。把一代的新孩子用 gather 一起评，结果是对的，但评估重叠了 28 次。
- 评估顺序是 evolve() 的顺序（父代名次、变异器），不是完成顺序。as_completed 加一把锁看上去也是一个一个评，但预算在一代中途用完时，评到哪些孩子取决于哪个模型先回答，两种延迟下结果不同。这一关的预算故意在第 7 代中途用完。
- 预算用完时还在跑的变异要取消，并等它们结束。测试里有一个永远不回答的模型：不取消就一直等到超时；取消了不等，任务还挂在事件循环里；完全不管也一样。这个模型被取消后还要花一轮事件循环收尾（先关连接），所以 cancel 之后只 `sleep(0)` 一次也不够，要 await 它们，比如 `gather(*tasks, return_exceptions=True)`。
- 先 gather 等一代的变异全部回来再按顺序评，或者先 await 下一个变异再看预算，都会去等那个永远不回答的模型，2 秒后超时。
- 每代的行要在下一代开始之前交出去。探针：第 0 代的行出来时一个变异都还没开始，第 1 代的行出来时正好开始了 2 个。把行攒到最后，或先发出下一代的变异再交上一代的行，都会被发现。
- 被预算截断的最后一代也要输出。
- 并发的变异共用一个生成器，结果取决于谁先用到它。Part 3 规定每个变异一个生成器，在这里成了必须。
- 写成普通的 `async def` 而没有 `yield`，测试报的是 `'async for' requires an object with __aiter__`，要看出这里需要 async generator。

追问：
- "The evaluator is the bottleneck. How would you use four of them?"（四个评估工作者并行，但仍按槽位顺序提交结果、扣预算，结果不变。）
- "A model never answers. What should happen without a budget?"（给每个变异设超时，超时算没有孩子；本题只在预算用完时取消。）
- "The dashboard disconnects mid-run?"（`aclose()` 让 GeneratorExit 在 yield 处抛出；这里 yield 时没有挂着的任务，不会泄漏。）
- "Why CSV and not JSON lines?"（表格工具直接能开，每代一行、字段固定；数据一旦嵌套就不合适了。）

### Part 5 分解树与独立检查（目标 13 分钟）

坑：
- 树里记的是真正成功的方法。`deploy` 先试了 `deploy_canary` 并失败，树里应该是 `deploy_direct`，不是第一个前置条件成立的方法；失败的尝试也不能留在树里。叶子从左到右必须等于 `plan()`。
- 同一个任务在树里出现两次，用的方法不同：`ensure_login` 第一次是 `fresh_login`（还没登录），第二次是 `reuse_session`。按任务名记“选了哪个方法”，两处会显示成同一个。
- LLM 来的分解标 `"llm"`，下次从缓存里再用也标 `"llm"`，不能是 None 或别的标签。
- 检查器是独立的：只拿树、operators、methods 和初始状态，自己重放；不能改调用方的 `state`。
- 按计划顺序检查（先任务后子任务，从左到右），返回第一个出问题的节点：
  - 方法节点的孩子必须正好是方法的子任务。调换两步，要报在 `ship_change` 上 `(0,)`，而不是等到 `write_tests` 再报 `(0, 1)`。
  - 方法自己的前置条件也要查：未登录时把 `ensure_login` 标成 `reuse_session`，报 `(0, 0)`。
  - 方法只能分解自己的任务。在所有任务里按方法名查找，`deploy` 就能借用 `merge_reviewed`。
  - llm 节点的孩子只能是操作符或库里的任务。嵌套的 `revert_db` 也标着 llm，不能因此放过。
  - 复合任务当叶子（`deploy` 没有分解）要报出来。
  - 操作符节点没有方法，也没有孩子。`Node("login", "llm", (Node("push_prod"),))` 要在根上报 `()`：只查 `login` 的前置条件就放行，检查器认可了这棵树，可它的叶子读出来是 `push_prod`，一个谁也没检查过的计划。
- 路径用孩子下标。两个一模一样的 `merge_pr` 兄弟，失败的是第二个，路径是 `(2,)`；用 `children.index(child)` 会找到第一个，得到 `(1,)`。根节点的路径是 `()`，写成 `return path or None` 会把它变成 None。
- `next()` 不给默认值，找不到方法时抛 StopIteration。

追问：
- "Why check a tree the planner has already checked?"（纵深防御：树可能来自缓存文件、别的进程或 LLM；检查器比规划器简单，容易审查。这就是“符号层负责正确性”落到代码里。）
- "Will the checker accept a tree the planner would never build?"（会：已登录时走 `fresh_login` 也能重放成功。它查的是 sound，不是“是不是规划器的选择”。）
- "How would you report a violation to the person on call?"（把路径换成任务名链，再带上缺少的事实。）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读断言消息、逐层打印、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出成本（LLM 调用次数）、并发、可复现、失败处理 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
