# 面试官手册：Voyager（14/10）

候选人计时期间不要看。候选人手里只有 README、`voyager/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。
- 测试里的技能代码、`ScriptedWriter`（代替写代码的模型）和 `has_iron_pickaxe`（代替自我验证）都是固定的替身，告诉候选人不要改它们。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 标签字符串里有空格，要拆成几个标签吗？ | "No. A string is one tag, spaces and all." |
| 1 | 精炼时去掉了一个标签，按这个标签还能搜到这个技能吗？ | "No. Search only sees each skill's latest version, tags included." |
| 1 | 一次检索能按几个标签过滤？ | "One tag. Tell me how you would add more." |
| 1 | 父技能钉住了一个依赖，它别的依赖也要冻结吗？ | "No. Only a reference written name@v is pinned. A bare name always means the latest version." |
| 1 | 同一次执行里需要同一个技能的两个版本，跑哪个？ | "Both. Each version is its own step, and each runs once. Locking a closure to one version is Part 5." |
| 1 | 失败的那个技能要不要在 log 里留一行？ | "No. The log lists what finished. The failure goes in failed and error." |
| 1 | 回滚只回滚世界，还是连 log 也清掉？ | "Only the world. The log is the report, and the refinement loop needs it." |
| 1 | 要做环检测吗？ | "register only accepts dependencies that already exist. The tests don't cover cycles; tell me where you would catch one." |
| 2 | 换行要统一成 LF 吗？ | "No. Code comes back byte for byte, CRLF and trailing spaces included." |
| 2 | 哈希算的是什么？ | "SHA-256 of the code's UTF-8 bytes, as hex. Nothing else goes into it." |
| 2 | 两个不同技能的代码一样呢？ | "Still one object. The manifest points both at it." |
| 2 | 再保存一次时，清单要和旧的合并吗？ | "No. save gets the whole library every time, so the manifest is replaced. Objects stay." |
| 2 | 没人引用的对象要清理吗？ | "Not in save. Objects stay, even when no version uses them. Cleaning up is a separate job." |
| 2 | 要做原子写吗？ | "The tests can't see it. Tell me what it would protect." |
| 3 | 任务自己算不算缺的技能？ | "Yes. Missing is everything the library would have to learn, the task included." |
| 3 | 前置技能连配方都没有呢？ | "It's still missing. We just don't know what it needs." |
| 3 | 缺的材料要把缺失前置的配方也算上吗？ | "No. Only the task's own recipe." |
| 3 | 材料不够的任务要不要直接排除？ | "No. They stay in the ranking, after the ones you can start now." |
| 3 | 已完成的任务怎么处理？ | "Voyager adds a skill when it completes a task, so a task that is already a skill is done. The library is all you need." |
| 4 | 编译不过的草稿算一轮吗？ | "Yes. It's an error round, with the stack trace in detail." |
| 4 | 草稿没有定义 run，或者依赖了库里没有的技能呢？ | "Also an error round, with the stack trace. The writer gets to fix it next round. The tests only use a syntax error." |
| 4 | 写手看到的是堆栈还是只有报错信息？ | "The whole event of the previous round, the same dict that went out on the stream." |
| 4 | 上一轮对世界的修改要带到下一轮吗？ | "No. Every round starts from the world as it was when refine was called." |
| 4 | 所有轮都失败时世界应该是什么样？ | "As it started. Same if the caller stops reading early." |
| 4 | 失败的草稿要不要存起来？ | "Not in the library. The stream is the record." |
| 4 | 成功那一轮的 detail 写什么？ | "The verifier's reason." |
| 5 | 不带版本的引用只跟随自己路径上的钉，还是树里任何地方的钉？ | "Anywhere in the tree." |
| 5 | 钉到最新版本和不带版本的引用算冲突吗？ | "No. They agree." |
| 5 | 一个技能有好几条路径时报哪一条？ | "The first one a depth-first walk in written order finds. The tests only use pins with one path." |
| 5 | 如果一个钉只出现在最后没被选中的版本下面呢？ | "It still counts. Pins are read from the tree as written, where a bare name means the latest version." |
| 5 | 引用写错了版本号呢？ | "KeyError, naming the reference, like craft_sticks@3." |

## 每关：要看什么、提示、追问

### Part 1 修技能库（目标 13 分钟）

一个测试里叠了 4 个缺陷和几个护栏：

1. `register` 用 `tuple(tags)` 规范化标签，调用方传单个字符串 `"gather"` 时被拆成一个个字母。错误不在 `register` 报出来，而是在 `search` 里：按 `tag_filter="gather"` 过滤时 gather_sticks 不见了，`tag_filter="g"` 反而能命中。这是课里 retrieval quality 那一条：标签过滤是硬约束，规范化错了，过滤就失效。
2. `register` 遇到同名时原地改写旧对象，`_history` 只留旧代码字符串；`get(name, 1)` 用 `dataclasses.replace` 拼出一个“v1”：代码是 v1 的，`fn`、依赖、描述却是最新版的。钉在 `mine_ore@1` 的 starter_kit 一执行就失败，`failed='mine_ore@1'`，堆栈却指向 `<skill mine_ore v2>` 那一行源码。这正是课里的 composed-skill drift：父技能钉在 v1，跑的却是 v2。docstring 写明每个版本都原样保留、可以执行。
3. `execute` 中途失败不回滚：place_table 和 gather_sticks 改过的世界留着，下一次重试从脏状态开始。docstring 写的是全有或全无。
4. `search` 带 `tag_filter` 时先给库里每个技能算 Jaccard，最后才按标签筛。类的 docstring 写的是 register 维护一份“标签→技能名”的索引，按标签检索只给索引里列出的技能打分；起始代码的 register 只存了描述的分词，没有这份索引。测试建了 5 万个技能的库，每个标签只挂 50 个，计时 30 次按标签检索：起始代码在 pytest 里约 1.3–1.5 秒（单独跑，Python 3.10–3.14 上 0.64–1.64 秒），限值 0.03 秒；参考答案约 1–1.5 毫秒。这是课里 retrieval quality 那一条：技能过了几百个，检索就要靠标签和硬约束先把范围缩小，再排序。只把标签判断挪到打分前面（课里代码的顺序），或者先扫一遍所有技能的标签再打分，仍然要碰全库，约 0.10–0.20 秒，也过不了。
5. 护栏：钉住版本的父技能，没钉的依赖仍然取最新版（把依赖全冻结在 v1，或者注册时把裸名字替换成当时的版本，都会挂）；已经注册的版本对象不能被改；`search` 每个技能只出现一次、取最新版（遍历所有版本会出重复）；回滚只回滚世界，log 照样报告失败前跑了什么；error 是完整堆栈；用浅拷贝做快照、在函数里给 `world` 重新赋值、只 `update` 不先 `clear`，都还原不了世界。
6. 索引的护栏：索引跟着最新版本走，精炼时去掉的标签要从索引里删掉（测试把 mine_iron_tools_7007 从 kit007 挪到 kit999，只加不删会挂），新加的标签要补上；索引存技能名、检索时取最新版本，存 Skill 对象的话，标签没变的技能精炼以后还会返回 v1，用列表每次注册都追加会出重复（测试在精炼之后按 gather 检索）；没有技能带的标签返回空列表，用 `self._tagged[tag]` 取会在 `tag_filter="g"` 上报 KeyError；集合的遍历顺序不固定，并列按名字排只能靠排序键（kit007 里有两个 0.6 分和 11 个 1/3 分的并列，删掉排序键里的名字会挂）；描述的分词在 register 时做，起始代码已经做对了，精炼时要换成新描述的分词（测试搜 "two at a time"）。
7. `_plan` 没有预埋缺陷，它是课里 `topo_order` 那种带已访问集合的遍历，写成递归以保持兄弟顺序。它的护栏都还在：18 层的梯子（每个技能依赖下一层的两个技能）要在 0.05 秒内跑完，参考答案约 0.02 毫秒，改成每条依赖都重算整棵闭包、不记忆化的递归约 0.8 秒；记忆化按名字而不是按（名字，版本）去重，会把同一次执行里的 gather_sticks v2 吞掉；把计划缓存在库上、跨调用复用，精炼以后父技能还在跑旧计划（测试在精炼前先跑一次 starter_kit），到 Part 4 还会让版本号都是 0 的草稿共用一份计划；改成课里那种栈式后序遍历，兄弟依赖的顺序会反过来。

测试抓不到的：把字符串标签写成 `tuple(tags.split())` 能过，因为测试里的标签都没有空格；但 docstring 说一个字符串就是一个标签，带空格也一样（见澄清问题）。先更新索引、再编译代码的话，代码编译不过时索引里会留下一个库里没有的名字，之后的检索会报 KeyError；测试没有覆盖 register 失败的情况。看到这两种写法就问一句。

看什么：是不是先读 traceback，注意到 `failed='mine_ore@1'` 和 `<skill mine_ore v2>` 对不上；是不是 `print(lib.get("mine_ore", 1))` 看实际数据；计时挂了以后，是不是先数一数一次检索打了多少个分，再动手；每改一处就重跑。Part 1 要建一个 5 万个技能的库，跑一次要一两秒，属于正常。

提示：
- 标签那一层：H1 "Print the tags gather_sticks was stored with." H2 "What does tuple() do to a string?"
- 版本那一层：H1 "The run says mine_ore@1 failed. Which code does the traceback point at?" H2 "Compare get('mine_ore', 1) with what you registered, field by field." H3 直接指出 `register` 原地改写、`get` 用 `replace` 只换了代码。
- 回滚那一层：H1 "Which skills ran before the failure, and what did they change?" H2 "What does a copy of world taken before the loop need, so nested dicts are not shared?"
- 计时那一层：H1 "How many skills does one search with tag_filter='kit007' score, and how many carry that tag?" H2 "The class docstring lists what register prepares for search. Which of those exists?" H3 直接指出 register 没有维护标签索引，`search` 扫完全库才过滤。

追问：
- "The lesson says add deduplication on write. What would you dedupe on, and what should the caller get back?"（描述相似度或代码哈希；命中时提示改成 refine 已有技能，而不是再加一个名字）
- "A search needs skills tagged both category=tooling and biome=nether. How does the index handle that?"（取两个集合的交集，从小的那个开始；条件再多就是倒排索引上的布尔查询）
- "The lesson says vector retrieval degrades past a few hundred skills. Besides tags, what hard constraints would you filter on?"（前置条件和环境状态，比如需要工作台；技能的状态，比如只要验证过的版本；先过滤再排序，排序还可以参考历史成功率）
- "A refinement can create a cycle: v2 depends on a skill that depends on the bare name. Where should that be caught?"（在 register 时做三色 DFS，拒绝写入，并把环路径当作反馈给改写循环）
- "The rollback deep-copies the whole world on every run. When does that get expensive, and what else could you do?"（世界大时；改成撤销日志或写时复制；真实环境像 Minecraft 根本回滚不了，只能靠验证和补偿动作）
- "Why not freeze every dependency when a parent is pinned?"（课里说的是被钉住的那条边；全冻结的话子技能的修复永远到不了父技能。要整棵树固定，用 Part 5 的锁）

### Part 2 内容寻址存储（目标 12 分钟）

坑：
- 用文本模式读对象：`read_text()` 或默认的 `open(path)` 开着通用换行，`\r\n` 被读成 `\n`。不校验哈希的话读回来的代码对不上；校验的话（按读出来的文本重新编码）会把完好的对象报成损坏。写入时同理，先把换行统一了，对象的字节就和名字对不上。要用 `read_bytes` / `write_bytes`，或者 `newline=""`。
- 哈希只算代码的 UTF-8 字节。先 `strip()`、统一换行，或者把名字、版本号、描述一起哈希，对象名都和测试算的不一样。
- 相同代码只存一个对象：mine_ore v1 和 v3（回退）代码相同。但清单里两个版本都要在。把“代码已经存过”的版本从清单里去掉，是把对象去重做过了头。
- 依赖要保留版本钉，`"mine_ore@1"` 原样写进清单。
- tags 和 depends_on 读回来要转回 tuple，JSON 给的是 list。
- 读回来的技能要能执行：从代码重新 `compile_skill`。
- 再保存一次：已经有的对象不重写（测试看 mtime）；`open(path, "xb")` 不先判断会报 FileExistsError。第二次保存的库里 craft_pickaxe 已经没了：清单要整份替换，追加到旧清单会出重复版本，按名字或按版本合并会把 craft_pickaxe 留下。它的代码对象却要留着，save 不删对象（测试数对象个数）。
- 对象缺失或者内容被改过（测试把一个 5 换成 7，长度不变）都要报 StoreError，消息里点名用到它的版本 `mine_ore@2`。直接漏出 FileNotFoundError、不校验哈希、消息里只有哈希，都过不了。

测试抓不到的：用 `path.write_text(code, encoding="utf-8")` 写对象，在 macOS 和 Linux 上不转换换行，能过；在 Windows 上每个 `\n` 都会写成 `\r\n`，对象的字节就和名字对不上了。可以顺着问为什么对象要按字节读写。

追问：
- "Why content-address the code instead of naming files name@version?"（相同代码自然去重；名字就是完整性校验；对象不可变，可以放心共享和缓存；多个技能库之间也能共用）
- "Two agents save into the same store at once. What can go wrong?"（对象没问题：同名必同内容，临时文件加 rename；清单是后写者胜，需要锁或者比较后交换）
- "How would you garbage-collect objects?"（从清单出发标记，清掉没被引用的；和并发保存一起做时要小心）
- "Why check the hash on load at all?"（磁盘损坏、写了一半的文件、被人改过；技能是要执行的代码，读到被篡改的代码就是安全问题）
- "The manifest names files by hash. What stops it from pointing at ../../etc/passwd?"（读之前检查是 64 位十六进制；参考答案就这样做）

### Part 3 课程提议（目标 10 分钟）

坑：
- 库里已有的技能不再往下找：craft_planks 已经会了，它的前置 chop_wood 就不算缺。往已知技能下面接着找，所有候选都会多出 chop_wood。
- 任务自己的技能也算缺：mine_iron 缺的是 mine_iron 和 craft_stone_pickaxe 两个。
- 要传递地找：smelt_iron 经 mine_iron 缺 craft_stone_pickaxe；没有配方的 collect_coal 也算缺，直接 `recipes[p]` 会报 KeyError。
- 菱形去重：craft_bucket 直接要 craft_furnace，经 smelt_iron 又要一次，只算一次。用 list 不查重会出重复；只在排序时递归计数，会把 bucket 数成 7 个、排到 shield 后面。
- 材料按数量：要 3 个圆石、手里 2 个，缺 1；刚好够的不算缺（smelt_iron 的 1 块铁矿）；背包里根本没有的按全数缺（coal）。`short` 只算任务自己的配方，不把缺失前置的材料加进来，也不列出缺 0 个的材料。
- 排序：缺的技能最少优先（只缺自己，就是课里说的“略高于当前能力”），然后是材料齐的，然后价值高的，最后按名字。数据是按错法配的：craft_stone_pickaxe 和 craft_furnace 这一组里，价值顺序和名字顺序、缺的种类数顺序都相反；craft_bucket 和 craft_shield 这一组里，价值顺序和缺的件数顺序相反，递归重复计数也会让两者对调。按配方顺序打平会在 bowl 和 ladder 上露馅。
- 没有候选时 `propose` 返回 None，不是 IndexError。

追问：
- "Why prefer the task that is one skill away over the most valuable one?"（课里的探索甜区：太难的任务会把改进轮次耗光，学不到东西；能做成的任务才会留下技能）
- "How would you use failed tasks?"（Voyager 的课程会记住太难的任务，推迟再提；可以按失败次数降权）
- "Voyager asks an LLM for the next task. What does a deterministic proposer buy you, and what does it miss?"（可测、便宜、能解释；但提不出配方表里没有的新任务，缺好奇心那一面）
- "Missing materials can be made by other skills. How would you plan that?"（变成规划问题：材料由技能产出，需要搜索或 HTN 分解，见下一课）

### Part 4 迭代改进流（目标 13 分钟）

坑：
- 三种信号要分清：编译不过也是 error，detail 是 `traceback.format_exc()` 的完整堆栈；技能抛异常时用 `run.error`；跑完但验证没过是 self_verification_failure，detail 是验证函数给的理由，不是 error。失败的运行不能再去跑验证。
- 每轮从调用时的世界开始。第 3 轮验证失败时世界里已经有 3 个矿石、2 根木棍、工作台，还有草稿自己写下的 `waiting_for`；不重置的话，第 4 轮那份漏了 gather_sticks 的草稿会“成功”，注册进库的技能拿到新世界就跑不起来。这就是伪成功：环境里的残留让一份有缺陷的草稿过了验证。重置时要深拷贝快照：`world.update(start)` 会让下一轮直接改到快照里的嵌套 dict。还要先 `clear`：只 `update` 的话，`waiting_for` 会一直留到成功那一轮之后，最后比对世界时会挂。
- 失败的草稿绝不入库。先注册再执行的话，失败以后删不掉，版本号也被占了（成功那一轮变成 v5）。成功时用库分配的版本号，这里是 2，因为库里已经有一个 v1。
- 轮数上限，成功后马上停。测试给了 6 轮上限、5 份草稿，成功以后再问写手会被替身拦下。
- 写手每轮拿到的是上一轮那个完整的事件 dict，不是只有 detail。
- 每轮一结束就输出。探针在读到第一行时检查写手只被调用了一次：先收集再统一输出，或者先要下一份草稿再输出，都会挂。
- 提前关闭：消费方读到第一行（验证失败）就 `aclose()`，世界也要回到开始时的样子。生成器在 yield 处收到 GeneratorExit，循环后面的重置代码不会执行，要放进 `try/finally`。成功以后不能再重置，消费方读到成功那一行就关闭时也一样：GeneratorExit 同样在那个 yield 处抛出，所以“已经学会”要在 yield 之前记下。只在 `except GeneratorExit` 里重置，或者 yield 之后才记成功，都会在最后一个探针上挂。失败的那一轮在 yield 之前就复原、不用 finally，也满足要求。
- NDJSON：一行一个对象。堆栈里的换行由 `json.dumps` 转义；`indent=2` 会报 Expecting property name，漏了 `\n` 会报 Extra data。
- 骨架是 `async def` 里只有 raise，测试报 `'async for' requires an object with __aiter__ method, got coroutine`，要看出这里需要 async generator。

追问：
- "Voyager's verifier is another LLM call. What changes when it can be wrong?"（会有假成功和假失败；可以多次投票、验证环境状态而不是看日志、成功的技能入库前再跑一次回归）
- "The writer keeps sending the same draft. What would you do?"（按代码哈希去重，重复的直接复用上一轮的结果或提前停；Part 2 的哈希正好用得上）
- "Minecraft can't be reset between attempts. What does that do to this loop?"（每次尝试都从不同的状态开始，残留状态会制造伪成功；所以验证要查任务本身的结果，技能入库前最好在干净环境里重放）
- "The client disconnects in the middle of a round. What runs, what is left behind?"（`aclose()` 在 yield 处抛 GeneratorExit；任务在等写手时被取消，CancelledError 在 await 处抛出；两种情况 finally 都会执行，把世界复原。写手如果是网络请求，取消要能传下去）

### Part 5 版本锁定（目标 12 分钟）

坑：
- 两遍走：第一遍按字面走整棵树（`name@v` 是 v，裸名字是最新版），收集所有的钉和第一次出现的路径；第二遍按锁定的版本走，输出依赖在前的顺序。只走一遍、遇到谁先用谁，在 craft_tools 和 craft_stone_pickaxe@1 上都会挂：裸名字的 craft_sticks 先出现，钉 `craft_sticks@1` 后出现。
- 第一遍要按（名字，版本）记已访问，不能按名字：craft_rails 先经 mine_iron 走到裸名字的 craft_stone_pickaxe（v2），后面才是 `craft_stone_pickaxe@1`，v1 里面的 `mine_stone@1`、`craft_sticks@1` 也要算。
- 锁定以后要按锁定版本的依赖往下走：craft_sticks 锁在 v1 时没有 strip_bark。
- 冲突要点名两条路径，从根开始，每个节点带版本：`craft_kit@1 -> craft_stone_pickaxe@1 -> craft_sticks@1` 和 `craft_kit@1 -> fletch_arrows@1 -> craft_sticks@2`。
- 同一个钉出现两次不算冲突；钉到最新版和裸名字也不冲突。把每个引用都当成钉，会在裸名字遇到旧版本钉时误报。
- 版本不存在、技能不存在都报 KeyError，消息里带引用本身；退回到最新版、跳过不认识的技能都不对。
- 根上的钉也要算：`craft_stone_pickaxe@1` 锁的是 v1。

追问：
- "Run resolve on stock_up from Part 1. What does the lock change compared with execute?"（execute 按引用逐条取版本，跑 gather_sticks v1 和 v2 两个；锁定以后裸名字跟随钉，只剩 v1）
- "How would you move a pinned parent to a newer child safely?"（先在干净环境里跑子技能新版本的验证和父技能的回归，再改钉；锁文件的 diff 就是升级清单）
- "Why is general version resolution hard?"（版本会带来不同的依赖，钉可能只出现在最后不用的版本下面；版本范围一多就是约束求解，npm、pip 各有取舍）
- "Should execute use the lock?"（共享或部署前应该用，保证每个技能只有一个版本；开发时逐条解析更灵活）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出版本不可变、检索规模、完整性校验、伪成功、提前断开、锁定与升级 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
