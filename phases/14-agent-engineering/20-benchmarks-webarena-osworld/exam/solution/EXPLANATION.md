# 参考答案讲解：WebGym（14/20）

计时结束后再看。参考实现在同目录的 `webgym/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修套件运行器

**现象**：解锁后第一个失败在最前面的三个回合上：一个先加错一件、删掉以后再加对，一个不调 `list_items` 直接下单，一个把两件商品倒过来加。三个回合最后都恰好下了想要的那笔订单，却都被判失败。

**依次修五处**：

1. `episode_result`：原代码不调用 `judge`，而是拿 agent 的动作序列和 gold 比，一模一样才算成功。这是比对轨迹，不是课里 WebArena 的基于执行的评估：同一个任务有很多条合法路径，gold 只是已知最短的一条，绕路的、抄近路的、换了顺序的都该算成功。反过来，照着 gold 一步不差地做也不等于成功：测试把 gold 原样重放到一个购物车里本来就有键盘的快照上，结账会连键盘一起买下。改成 `judge(app, task.want)`，gold 只用来给出 `gold_steps`。只把比较放宽成“gold 是动作序列的子序列”“gold 的每个动作都做过”，或者先抵消加了又删掉的动作，绕路的回合能过，直接下单的回合过不了；调了 `judge` 还要求 gold 里改购物车的动作按原顺序出现，过不了倒过来加的回合；保留“和 gold 一样就直接算成功”的捷径，过不了那次重放；只看最后一步有没有返回订单号，会放过先买错再买对的回合。
2. `judge`：原代码是课里 `main.py` 那种写法，`any(...)` 扫所有订单，只检查想要的 sku 在订单里。于是快照里原有的那笔键盘订单让“什么都没做”的回合成功；先买错再买对的回合也成功；多买了鼠标的回合还是成功。按 docstring 改成：只看本回合新下的订单（`app.orders[app.pinned_orders:]`），恰好一笔，内容和 want 完全相等。这就是课里说的基于执行的评估：看终态，而且要看得足够严，多余的副作用也算失败。第一处修好之前 `judge` 根本没被调用，所以它的问题要等到这时才露出来。
3. `count_steps`：`len(trace)` 把 Note 也算了进去。课里 `revised_order` 打印 7 步，其中一行是 `"revised_choice: remove keyboard"`，不是对应用的操作。只数 `Step`。返回了 error 的动作照样算，拼错 sku 也花掉了一步。
4. `add_to_cart`：用 `app.py` 里给 `set_price` 用的 `_whole(qty, 1)` 检查，0、负数和 1.5 都返回 `error:` 字符串，购物车不变。只写 `qty < 1` 会放过 1.5，先 `int(qty)` 会把 1.5 当成 1。`_whole` 也拦住 bool（`True` 是 int 的子类），测试没有专门考这一点。
5. 计时：`add_to_cart` 为了检查 sku 是否存在，每次都调 `list_items()` 复制整份 catalog。5000 个商品、2500 次加购，要复制一千多万行，本机 0.73–2.5 秒。改成 `sku not in self.items`，整个回合约 3 ms，机器很忙时最多 9 ms 左右。

**护栏**：为了提速让 `list_items` 返回内部的行，调用方一改价格就改到了应用里；测试先检查了这一点。qty 不合法时抛异常也不行，应用的所有错误都是给 agent 读的字符串。`reset` 起始代码就是对的：每一行都复制一份（`dict(row)`；行里只有字符串和整数，复制一层就够了）。课里说 WebArena 的应用固定版本、可复现，`reset` 就是这个承诺在代码里的样子。测试留着三条断言守着它：markdown 回合的改价不能带到下一个回合，不能改到调用方传进来的快照，对一个应用直接 `set_price` 再 `reset` 要回到固定状态。让 `reset` 共享行、只在 `run_suite` 里给每个回合 `deepcopy` 一份快照，前两条能过，最后一条过不了。

## Part 2 内容寻址快照库

参考实现很短：

```python
data = json.dumps(state, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
digest = hashlib.sha256(data).hexdigest()
```

文件 `<root>/<digest>.json` 里存的就是这些字节，已存在就不再写。`get` 读原始字节，重新哈希，不一致就报 `SnapshotError`，文件不存在报 `KeyError`。

容易错的地方：

- **规范形式要一字不差**：测试钉死了 digest。`json.dumps` 的默认分隔符带空格，`ensure_ascii` 默认把 `ö` 写成 `\u00f6`，不排序时键顺序取决于构造顺序，三者都会得到另一个哈希。
- **只排键，不排列表**：catalog 的顺序就是 agent 在页面上看到的顺序，属于状态。把它按 sku 排序看起来更“规范”，实际上把两个不同的应用版本当成了同一个。
- **整数分是这个领域的精度陷阱**：`59.0 == 59`，可它们的规范 JSON 不同，哈希也不同。一个任务钉的是 `5900`，另一份“相等”的快照写成 `5900.0`，就会被当成另一个版本。所以 `put` 直接拒绝非整数，`True` 也拒绝，不做 `int()` 转换。规则对整个快照都成立：购物车和订单里的数量至少是 1，订单总价也是整数分，测试三处都放了坏值。校验要在写文件之前，被拒绝的快照不能留在目录里。
- **校验字节，而不是校验含义**：内容寻址的地址指的是字节。把文件解析后重新规范化再校验，能抓到改价格，也能抓到 `5900.0`，但会放过只改了排版的文件，那已经不是同一个对象。

## Part 3 轨迹对齐和效率

先规范化：sku 转小写，`add_to_cart` 补上默认的 `qty=1`，参数排序后成为可比较的元组。

对齐用后缀 DP：`rest[i][j]` 是 `agent[i:]` 和 `gold[j:]` 的最小代价。配对只在动作名相同时允许，参数相同记 match（0），不同记 substitute（1）；跳过一边各记 1。然后从 `(0, 0)` 往前走，每一步按“配对、跳过 agent、跳过 gold”的顺序，选第一个仍能达到最小代价的走法。这样两次一模一样的加购里，第一次和 gold 配上，重复的那次是 extra。前缀 DP 再从末尾回溯的写法正好相反。

`efficiency` 只看成功的任务。micro 是总步数除以总 gold 步数，这组数据是 18/10 = 1.8；macro 是每个任务比值的平均，(1.5 + 1 + 3) / 3 ≈ 1.83。课里 `main.py` 的汇总把失败任务也算了进去，会得到 28/13 ≈ 2.15：一个失败任务的步数说明不了效率。没有成功任务时 micro 和 macro 都是 None。

## Part 4 隔离的并行回合

每个回合放在自己的 task 里，用 `Semaphore(limit)` 限制并发，结束时把一行 CSV 放进队列；生成器先输出表头，再从队列里取够 `len(tasks)` 条：

```python
async def episode(task):
    async with slots:
        env = Env(ShoppingApp(snapshot))
        try:
            await task.agent(env)
        except Exception:
            ok = False
        else:
            ok = judge(env.app, task.want)
        await finished.put(_record((task.tid, int(ok), count_steps(env.trace), len(task.gold))))
```

- 每个回合 `ShoppingApp(snapshot)` 一份；`reset` 逐行复制快照，所以它们互不影响。
- 记录按结束顺序输出，一结束就输出。测试里 hold 回合要等 crash 回合的记录出来才继续，先 `gather` 或按批次跑都会卡住。
- 抛了异常就判失败，不再看终态。crash 回合在抛异常前已经下了一笔正好符合 want 的订单，`except` 里只记一下、最后照样调 `judge` 的写法会把它判成成功；`else` 分支只在 agent 正常返回时才判定。
- `except Exception` 不会吞掉 `CancelledError`（它是 BaseException），所以取消照常生效。
- CSV 用 `csv.writer` 写，任务名里的逗号和引号自动转义。success 写 `int(ok)`。测试用 `csv.reader` 解析每一行，换成 `QUOTE_ALL` 或 `\n` 行尾也一样能过。
- `finally` 里取消所有还没结束的 task 并等它们收尾，消费者提前 `aclose()` 时不会留下还在跑的回合。

## Part 5 嵌套成功条件

先递归校验整棵树：每个节点是只有一个键的 dict，`all`/`any` 带列表，`not` 带一个节点，叶子的参数不缺也不多，其他名字一律报 ValueError。参数多一个也要拒绝：`{"sku": ..., "quantity": 1}` 里拼错的参数如果被忽略，这个条件就悄悄变成了“任意数量”。然后求值：`orders` 的 count 和 `ordered` 的 qty 都按恰好相等比较，`ordered` 没写 qty 时匹配任意数量。

解释用一个带极性的递归 `_blame(node, wanted)`，意思是“为什么这个节点不等于 wanted”：

- `not`：翻转极性，进入子节点。
- `all` 想要成立却失败：进入第一个失败的子节点。
- `any` 想要不成立却成立：进入第一个成立的子节点。
- 其他情况（失败的 `any`、不该成立却成立的 `all`、叶子）：就是节点自己。

这是德摩根律在解释上的对应。`not(not(X))` 失败时一路翻转两次，落在 X 上；`not(any[...])` 失败时落在第一个成立的分支上，正好是“禁止的事情里哪一件发生了”。

## 这套题证明了什么，没证明什么

通过了说明你能在这个规模的代码里调试一个评测套件，分清看终态和比轨迹，把基于执行的判定写严，按内容固定和校验应用版本，用编辑距离量化轨迹效率，写隔离的并发回合，并且解释嵌套成功条件为什么失败。它不涉及真实浏览器和桌面环境，不涉及截图、GUI grounding 或真实模型，也没有复现 WebArena 和 OSWorld 的任何数字。课里 Exercises 4 和 5 要读的论文和应用仓库需要另外去看。
