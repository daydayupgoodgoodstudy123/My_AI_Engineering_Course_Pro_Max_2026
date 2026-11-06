# 面试官手册：WebGym（14/20）

候选人计时期间不要看。候选人手里只有 README、`webgym/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。
- 题目里没有模型。agent 是测试里的脚本函数，候选人不需要也不应该去接 API。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | agent 走的路和 gold 不一样，终态对了，算成功吗？ | "Yes. Only the final state decides. Gold is what we count the steps against." |
| 1 | 照着 gold 一步不差地做，是不是就一定成功？ | "No. The same actions can end somewhere else if the app started in another state. Only the final state counts." |
| 1 | 快照里本来就有的订单算不算 agent 的成果？ | "No. Only orders placed during the episode count." |
| 1 | 返回了 error 的动作算不算一步？ | "Yes. The agent spent a step on it." |
| 1 | qty 不合法时要不要抛异常？ | "No. The app answers with an error string, like every other error." |
| 1 | qty 可以是 1.5 吗？ | "No. Whole units only, and at least 1." |
| 2 | 文件被重新排版、内容没变，还算有效吗？ | "No. The digest names the bytes. Different bytes are a different object." |
| 2 | 价格可以是 59.0 吗？ | "No. Integer cents only. Reject anything else with a ValueError." |
| 2 | 为了规范化，put 要不要把 catalog 排个序？ | "No. Agents see the catalog in that order. It's part of the state." |
| 2 | 订单里的总价和数量也要校验吗？ | "Yes. Every price, total and quantity in the snapshot follows the same rules." |
| 3 | 不写 qty 的 add_to_cart 和写了 qty=1 的算同一个动作吗？ | "Yes. 1 is the default." |
| 3 | 动作对了、商品选错了，算一个错还是两个？ | "One. That's a substitution." |
| 3 | 失败的任务算进效率吗？ | "No. The success rate covers failures. Efficiency is for the tasks that succeeded." |
| 4 | agent 自己抛了异常怎么办？ | "That episode fails, even if the app state looks right, with the steps it took so far. The others keep going." |
| 4 | 行尾用 `\n` 还是 `\r\n`？字段要不要加引号？ | "Whatever csv.writer writes is fine, as long as csv.reader reads it back." |
| 4 | 记录按什么顺序输出？ | "Finish order. Each record as soon as its episode ends." |
| 5 | ordered 不写 qty 是什么意思？ | "Any quantity." |
| 5 | 永远不会被求值的分支里有未知谓词，要报错吗？ | "Yes. Check the whole goal before evaluating it." |
| 5 | 叶子谓词多了一个不认识的参数（比如 quantity）怎么办？ | "Malformed. Raise a ValueError. A typo must not widen the check." |
| 5 | orders 的 count 是至少 n 笔还是恰好 n 笔？ | "Exactly n. A qty is exact too." |

## 每关：要看什么、提示、追问

### Part 1 修套件运行器（目标 12 分钟）

一个测试里叠了 5 个缺陷，加 8 个护栏：

1. `episode_result` 不调用 `judge`，而是看 agent 的动作序列和 gold 是否一模一样。docstring 写的是：成功只看终态，不管 agent 走的是哪条路；gold 只用来给出 gold_steps，算 steps over gold。测试最先跑三个回合：一个先加错一件、`remove_from_cart` 以后再加对，一个不调 `list_items` 直接下单，一个把 gold 里的两件商品倒过来加。三个回合最后都恰好下了想要的那笔订单，却都被判失败。报错出现在 `run_suite` 的结果里，根因在 `episode_result`。这正是课里 WebArena 用基于执行的评估的原因：同一个任务有很多条合法路径。
2. `judge` 用 `any(...)` 扫所有订单，只看想要的 sku 在不在。快照里原有的订单也算进来；先下错单再下对单也算成功；多买了东西也算成功。docstring 写的是：本回合恰好新下了一笔订单，内容和 want 完全一致。`episode_result` 改成调用 `judge` 以后，这个问题才露出来。
3. `count_steps` 是 `len(trace)`，把 agent 的 Note（课里 `"revised_choice: ..."` 那种思考记录）也算成一步。
4. `add_to_cart` 接受 0、负数和 1.5，docstring 要求正整数，错误要以 `error:` 字符串返回。`app.py` 里给 `set_price` 用的 `_whole` 正好能用；只写 `qty < 1` 或先 `int(qty)` 会放过 1.5。
5. `add_to_cart` 每次都调 `list_items()` 复制整份 catalog 来检查 sku 是否存在。5000 个商品、2500 次加购，本机实测 0.73–2.5 秒（负载越高越慢）；直接查 `self.items` 后整个回合 2.8–9.2 ms，中位数约 3 ms。限值 0.08 秒，慢的一侧至少 9 倍，修好的一侧至少 8.7 倍。只去掉复制、每次仍从 `self.items.values()` 建一个集合，0.33–0.5 秒，照样超时。

护栏：
- 只把比较放宽也不行：gold 是动作序列的子序列、gold 的每个动作都做过（另外再调不调 `judge` 都一样），或者先把“加了又删掉”的动作抵消再和 gold 比。绕路的回合能过，直接下单的回合过不了：gold 里的 `list_items` 对终态没有影响。调了 `judge` 还要求 gold 里改购物车的动作按原顺序出现，倒过来加的回合过不了。
- 保留“和 gold 一模一样就算成功”的捷径，后面再补一个 `judge`。测试把 gold 原样重放到一个购物车里本来就有键盘的快照上，结账会连键盘一起买下，要求判失败。
- 只看最后一步有没有返回订单号也不行：mouse 回合先买错再买对，最后一步也是订单号。
- 一个拼错 sku 的动作返回了 error，仍然算一步。为了“只数有效动作”去过滤 error，会在步数断言上挂掉。
- `list_items` 交出去的必须是副本。为了提速直接返回内部的行，调用方一改就改到了应用状态。
- qty 不合法时抛 ValueError 也不对：应用的错误都是字符串，agent 要能读到。
- `reset` 起始代码就是对的，每一行都复制一份。测试保留三条断言守着它：markdown 回合的改价不能带到下一个回合，不能改到调用方传进来的快照，对一个应用直接 `set_price` 再 `reset` 要回到固定状态。改成共享快照里的行，第二个回合的总价和调用方的快照都会被改；只在 `__init__` 里复制一次快照、`reset` 共享这份副本的行，第二个回合照样拿到改过的价格；在 `run_suite` 里每个回合 `deepcopy` 一份快照、`reset` 仍然共享行，前两条能过，挂在直接 `set_price` 再 `reset` 那一条上。
- 每个动作前都 `reset` 也不对：一个回合里的状态要累积，markdown 回合先改价再下单。这种写法所有回合都下不了单，最先在开头那三个回合上挂掉。

看什么：是不是先读断言给出的列表，对着任务逐个算一遍期望值；是不是先查清 `Result.success` 是从哪里来的、`judge` 有没有被调用；计时失败时是不是先测量再动手。

提示：
- H1："Which of these episodes should succeed, which should fail, and what does each final state look like?"
- H2："Where does Result.success come from? Is judge ever called?"
- H3：直接指出 `episode_result` 拿动作序列和 gold 比，或者 `judge` 里的 `any(...)`，或者 `add_to_cart` 里对 `list_items()` 的调用。

追问：
- "Why judge the final state instead of comparing the trajectory with gold?"（WebArena 是基于执行的评估：同一个结果有很多条路径，gold 只是已知最短的一条；照着 gold 做也不一定成功，起始状态不同，同样的动作会落到别的终态。但终态检查要写严，不然会放过多余的副作用）
- "What can a final-state check still miss?"（课里测验 Q14 的盲点：检查没读到的副作用，做了又撤回的改动，比如改了价又改回去；绕了大弯的成功和一步到位的成功同分，所以 Result 里还要报 steps 和 gold_steps）
- "The lesson says WebArena pins its apps. What breaks if you upgrade one?"（任务和金标准轨迹是按旧版本整理的，结果失去可比性；课里说 update without re-curation breaks comparability）

### Part 2 内容寻址快照库（目标 10 分钟）

坑：
- 规范形式：键排序、紧凑分隔符、非 ASCII 直接写 UTF-8。测试钉死了 digest，`json.dumps` 默认的 `", "`、`": "`，`ensure_ascii=True`，不排序，都会得到另一个哈希。
- 列表顺序不能动。为了“更规范”把 catalog 按 sku 排序，digest 会变，读回来的顺序也错了。
- 价格是整数分。`59.0 == 59` 在 Python 里成立，但规范 JSON 一个写成 `59.0`、一个写成 `59`，哈希不同；`True` 是 int 的子类，`isinstance` 拦不住。用 `int()` 悄悄转换也不行，要报 ValueError。规则对整个快照都成立：测试还放了购物车里数量为 0、订单总价 `32800.0`、订单里数量为 0 的快照，只校验 catalog 的价格不够。
- `get` 要重新哈希文件的原始字节。不校验，改过价格的文件照样读出来；把 JSON 解析后再规范化去校验，会放过只改了排版的文件。
- 未知 digest 报 KeyError，不能漏出 FileNotFoundError。
- 先校验再写。先写文件再校验，被拒绝的快照会留在目录里，知道 digest 就能读出来；测试在几次 ValueError 之后又数了一遍文件。
- 测试没有覆盖、但可以聊的：`put` 每次都覆盖已有文件，测试看不出来。

追问：
- "Two machines write the same snapshot at once. Is that a problem?"（内容相同，字节相同；写临时文件再 `os.replace` 就不会读到半个文件）
- "How would a task declare which app version it needs?"（任务里存 digest，运行前用 `get` 校验；不符就拒绝运行，而不是在新版本上跑出不可比的分数）

### Part 3 轨迹对齐和效率（目标 14 分钟）

坑：
- 先规范化再比较：sku 不区分大小写，`add_to_cart` 的 qty 默认是 1。
- 动作名不同的两步不能配对。照抄通用编辑距离，把 remove 和 add 当成一次替换，会少算一次错误。
- 并列最优路径的选法在 docstring 里：从头往后走，优先配对，再跳过 agent 的动作，最后跳过 gold 的动作。教科书写法是前缀 DP 再从末尾回溯，重复的两次加购会把前一次标成 extra。
- 效率只算成功的任务。课里 `main.py` 的汇总把失败任务也算进去，这组数据会得到 2.15 而不是 1.8。
- micro 是总步数比总 gold，macro 是每个任务比值的平均，两者在这组数据上是 1.8 和 1.83。一个成功任务都没有时两者都是 None，不能除零。

追问：
- "OSWorld-G splits grounding from planning. How would you use these ops for that?"（substitute 是动作对了、目标错了，接近 grounding 失败；extra 和 missing 更像 planning 或操作知识的问题）
- "OSWorld-Human reports 1.4-2.7x. Which average would you publish?"（两个都报：micro 被长任务主导，macro 每个任务权重相同）

### Part 4 隔离的并行回合（目标 12 分钟）

坑：
- 每个回合有自己的应用实例。共用一个应用，mouse 回合会把 hold 回合放进购物车的耳机一起结账，两个回合都判失败。
- 记录要一个回合结束就输出。先 `gather` 再输出、按批次跑（一批跑完才开始下一批），都会卡住，测试 1 秒后报 stalled。
- agent 抛异常只让自己那个回合失败，步数记到异常前为止。测试里的 crash 回合抛异常前已经下了一笔正好符合 want 的订单，照终态判会判成成功，所以抛了异常就直接判失败（`try/except/else`）。异常漏出去，这个回合永远不出记录，流也会卡住。
- 输出格式由测试的 `csv.reader` 决定：要有表头，success 写 1/0，任务名里的逗号和引号要按 CSV 规则转义，每个字符串恰好一条记录并带行尾。手工拼逗号会把 `hold, "headphones"` 拆成两列。引号和行尾交给 `csv.writer`：`QUOTE_ALL`、`\n` 行尾也都能被读回来，测试都接受。
- 同时运行的回合数不超过 limit，空出一个位置就马上补上。
- 消费者提前关闭流时，还在跑的回合要取消。
- 测试没有覆盖、但可以聊的：`except BaseException` 会把取消也吞成一条失败记录；关闭时只 `cancel()` 不等它们结束也能通过，因为 docstring 只要求取消，但真实的回合是一台虚拟机，要等它收尾。

追问：
- "Each episode here is a dict. In OSWorld it's a VM. What changes?"（启动和回收很贵：预热池、快照恢复、超时回收；关闭时不回收就是泄漏一台虚拟机）
- "Why write steps and gold_steps instead of the ratio?"（比值丢掉了分母，后面没法再算 micro；整数也不会有浮点格式问题）

### Part 5 嵌套成功条件（目标 12 分钟）

坑：
- `ordered` 不写 qty 表示任意数量。照搬 Part 3 的“qty 默认 1”，`not ordered sku-002` 会放过买了两个键盘的订单。
- 解释要跟着极性走：`not` 失败，说明它禁止的东西成立了，要继续往里找“为什么成立”。两层 `not` 抵消后，该怪的是最里面那个失败的谓词。
- `any` 全部不成立时怪它自己，不怪第一个子谓词；`all` 失败时怪第一个失败的子谓词。反过来，`not` 下面的 `all` 全部成立时，也怪 `all` 自己。
- 空 `all` 成立，空 `any` 不成立。
- count 和 qty 都是恰好相等。写成 `>=`，测试里“0 笔订单”和“1 个键盘”这两个检查就成立了。
- 先校验整棵树：短路求值不会走到的分支里，未知谓词、格式错误、缺参数、多出不认识的参数（`quantity`）都要报 ValueError。拼错的参数名不能悄悄变成“任意数量”。

追问：
- "Why return a path instead of a message?"（路径是结构化的：可以按路径聚合失败原因，找出最常挂的子条件）
- "The lesson warns about stale apps. Where would a pinned version show up in a goal?"（谓词依赖 catalog 的 sku 和价格；应用升级改了 sku，谓词就悄悄变成永远不成立）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读断言里的实际值、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出可复现、版本固定、隔离、资源回收 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
