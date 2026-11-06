# 参考答案讲解：HTNPlan（14/11）

计时结束后再看。参考实现在同目录的 `htnplan/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修规划器

**现象**：解锁后第一个失败是 `plan("release", ...)` 返回 None，没有异常。`release` 只有一个方法，它本身没错。

**顺着往下找**：逐层看每个任务试了什么。`ship_change`、`merge`、`build` 都成功了，最后的 `deploy` 有两个前置条件都成立的方法：`deploy_canary` 排在前面，走到 `watch_canary` 时缺 `metrics_on` 失败。代码只试 `applicable[0]`，失败就整个返回 None，`deploy_direct` 根本没被试过。报错的地方（`release` 的结果）和出错的地方（`deploy` 的方法选择）隔了两层分解。

**依次修四处**：

1. 回溯。按库里的顺序试每个前置条件成立的方法，第一个能展开的胜出；全都失败（或者一个都不适用）时，再试学到的分解，最后才问 LLM。课里的代码只在“没有方法的前置条件成立”时才问 LLM，测试里 `merge` 的 `merge_reviewed` 前置条件成立却因为审阅人不在而失败，这时也要问 LLM（课后测验 Q10 的写法）。
2. 先验证、后学习。LLM 的回答先过 schema 检查（每个名字都是操作符或库里的任务，否则整条拒绝，不去展开），展开成功才写进 `cached_methods`。课里的代码先写缓存再展开，`("open_pr",)` 这种名字合法、前置条件不满足的回答会被永久记住。
3. 学到的分解失败时回退到 LLM。它在一个状态下能用，不代表在别的状态下能用；失败了就问 LLM，新回答展开成功后替换旧的。
4. 记住失败。回溯带来了一个新问题：同一个（任务, 状态）会从很多条路径上被反复尝试。`rollout` 前面那 18 波，每波两种做法、结果状态一样，最后都卡在做不成的 `cab_signoff`，2^18 条路径要 0.7 秒左右，而且每条路径都问一次 LLM。在一次 `plan()` 调用里记下失败过的 `(task, frozenset(state))`，再遇到就直接返回，时间降到几十微秒，LLM 只问 19 次。

参考实现把状态一路当 frozenset 传，`_plan` 返回（节点, 结束状态），失败记录作为参数传下去：

```python
def plan_tree(self, task, state):
    found = self._plan(task, frozenset(state), 0, set())
    return None if found is None else found[0]

# _plan 里，复合任务的部分
if (task, state) in failed:
    return None
for method in self.methods.get(task, []):            # 1. 库方法，按顺序
    if method.applicable(state):
        found = self._expand(task, method.name, method.subtasks, state, depth, failed)
        if found is not None:
            return found
learned = self.cached_methods.get(task)              # 2. 学到的分解
...
suggested = self.llm.decompose(task, set(state))     # 3. LLM，过 schema 才展开
if suggested is not None and all(s in self.operators or s in self.methods for s in suggested):
    found = self._expand(task, LLM, tuple(suggested), state, depth, failed)
    if found is not None:
        self.cached_methods[task] = tuple(suggested) # 展开成功才学
        return found
failed.add((task, state))
return None
```

**护栏**：失败记录有两个常见的错法。一是只按任务名记：`redeploy` 先试 `redeploy_existing` 时还没构建，`deploy` 失败；换成 `redeploy_from_main` 构建之后，`deploy` 本该成功，却被记录跳过了。二是记录跨调用保留：LLM 下一次可能给出不同的回答，`hotfix` 的第三次请求正是靠重新问才拿到能用的分解。用展开次数上限代替失败记录，时间是快了，可 LLM 被问了几千次，测试数的就是这个。

修缺陷 2 时还有一个顺手的写法：先写缓存，展开失败再删掉。它能过 `cached_methods == {}`，可这个任务要是已经学到过一个分解，先写就把它盖掉了。测试里 `hotfix` 从未登录状态请求时，学到的 SHIP 失败，LLM 这次给的 `("open_pr",)` 也失败，这时 SHIP 必须还在。

## Part 2 方法库

参考实现每个方法一节，节名是方法名；`task` 和 `source` 写普通值，`preconditions`、`subtasks` 和 `note` 都用 `json.dumps` 写成一行；读写都用 `ConfigParser(interpolation=None)`；`add` 先校验、再读一遍文件查重，然后以追加方式写入这一节。

容易漏的几点：

- **`%`**：默认的 BasicInterpolation 把 `%` 当插值语法，`shift_10%` 写不进去，读也读不出来。关掉插值，或者用 RawConfigParser。
- **空白和注释**：configparser 会去掉值首尾的空白、续行的行首空白，续行里以 `#` 开头的行当注释丢掉，结尾的换行也留不住。备注这种自由文本必须编码，JSON 字符串最省事。
- **空列表和逗号**：`"".split(",")` 得到 `[""]`，没有前置条件的 `fresh_login` 会读回成一个空名字的前置条件，永远不适用；补上空列表的判断，又会把 `approved_by(release-eng, sre)` 切成两半。JSON 列表没有这些问题，名字里的空格和逗号都不怕。
- **以文件为准**：同一个文件可能有两个对象在用（测试里规划服务也开着它）。每次 add 都读磁盘上的文件查重，再追加；只记自己内存里的东西再整体重写，会冲掉别人写的。
- **错误类型**：重名和非法 source 都在写文件之前报 ValueError。configparser 自己的 `DuplicateSectionError` 不是 ValueError，`parser[name] = ...` 赋值又会悄悄覆盖。
- **顺序**：`methods()` 按任务分组，组内保持添加顺序，这就是规划器尝试方法的顺序。

## Part 3 进化搜索

参考实现把“一次搜索要记住的东西”放进 `Pool`：适应度缓存、当前父代、评估和命中计数、是否结束。`evolve` 只负责按顺序产生孩子：

```python
pool.record(first, evaluate(list(first)))            # 第 0 代：种子，计一次评估
history = [pool.close(0, [first])]
for g in range(1, generations + 1):
    if pool.finished:
        break
    children = []
    for p, parent in enumerate(pool.parents):        # 父代按名次
        for m, mutate in enumerate(mutators):        # 变异器按集成里的顺序
            if pool.spent():                         # 预算一用完立刻停
                break
            child = tuple(mutate(list(parent), mutation_rng(seed, g, p, m)))
            if not pool.scored(child):               # 命中缓存不计评估
                pool.record(child, evaluate(list(child)))
            children.append(child)
    history.append(pool.close(g, children))          # 被截断的一代也报告
```

`close` 把父代和孩子去重后按 `(fitness, genome)` 排序，留前 `survivors` 个；再看预算是否用完、最好的是否达到 target，决定要不要结束。

几个决定都写在 docstring 里，测试逐条核对：

- **每个变异一个生成器**：`random.Random(f"{seed}/{g}/{p}/{m}")`。结果只取决于参数，不取决于谁先算；Part 4 并发时靠的就是这一点。课里的代码用 `random.seed(0)` 改全局随机状态，测试会比较 `random.getstate()`。
- **副本**：测试里的 `b_up` 和 `nudge` 会原地改传进来的列表。每次都给 `list(parent)`，父代和缓存的键是 tuple，谁也改不了。
- **并列**：只按 fitness 排，并列时会沿用候选的先后，第 1 代就选错。
- **顺序**：父代在外层、变异器在内层。预算在一代中途用完时，评到的是哪几个孩子取决于这个顺序（`budget=5` 那条断言）；Part 4 也按这个顺序评估。
- **代数**：`generations` 不含第 0 代，`generations=2` 返回第 0、1、2 代。
- **预算**：只有评估器调用算数，命中不算；评估到第 `budget` 次立刻停，这一代剩下的变异不做，命中也不再算。这一代照样报告。
- **target**：在一代结束时检查，第 0 代也查。

最后一段用课里自己的评估器（平方误差，目标 3x + 7）和 `random_mutation`，种子 11 跑出的十一代历史逐项比对，第 10 代到达 [3, 7]。

## Part 4 异步变异集成

每一代先把所有变异作为任务同时发出去，然后按 evolve() 的顺序一个个等：

```python
tasks = [asyncio.ensure_future(mutate(list(parent), mutation_rng(seed, g, p, m)))
         for p, parent in enumerate(pool.parents) for m, mutate in enumerate(mutators)]
try:
    for task in tasks:                               # 槽位顺序，不是完成顺序
        if pool.spent():
            break
        child = tuple(await task)
        if not pool.scored(child):
            pool.record(child, await evaluate(list(child)))   # 一次只评一个
        children.append(child)
finally:
    for task in tasks:
        task.cancel()                                # 预算用完时还在跑的
    await asyncio.gather(*tasks, return_exceptions=True)
yield _row(pool.close(g, children))                  # 下一代开始之前交出这一行
```

- 变异是并发的：评估器在评第 k 个孩子时，后面的变异还在跑。
- 评估是串行的，而且按槽位顺序。按完成顺序评估（as_completed 加锁）在预算刚好在一代中途用完时会出问题：评到的是哪几个孩子，取决于哪个模型先回答。测试用两种延迟各跑一遍，结果都要和 evolve() 一样。
- 预算用完时取消剩下的变异，并且等它们真正结束。测试里有一个永远不回答的模型：不取消会一直等到超时，取消了不等，任务还挂在事件循环里。它被取消后还要一轮事件循环收尾，所以要 await；cancel 之后 `sleep(0)` 一次，等不到它结束。
- 一行一代，用 `csv.writer` 写：`best_genome` 是带逗号的 JSON 列表，需要 CSV 加引号；fitness 按 `str()` 原样写，`9.727272727272727` 不能被四舍五入。
- 行在下一代开始之前 yield 出去，消费者一拿到这一行就能显示；探针检查的正是这一点。

参考实现和 Part 3 共用 `Pool` 和 `mutation_rng`，两边的行为因此不会分叉。

## Part 5 分解树与独立检查

**树**：规划器的搜索本来就是一层层分解，`_plan` 直接返回节点：操作符是 `Node(task)`，复合任务是 `Node(task, 方法名或 "llm", 孩子们)`。`plan()` 读叶子，`plan_tree()` 返回整棵树，两者是同一次搜索，学到的东西也一样。只在分解成功时才造节点，所以失败的尝试（比如 `deploy_canary`）不会出现在树里；每个节点记的是自己这次用的方法，所以 `ensure_login` 两次出现、用了不同方法也不会混。LLM 来的分解，不管是这次问的还是缓存里的，都标 `"llm"`。

**检查器**：只拿树、operators、methods 和初始状态，自己从一份 frozenset 重放：

```python
def visit(node, path):
    if node.task in operators:                       # 操作符：没有方法、没有孩子、前置条件成立
        ...
    if node.method == LLM:                           # llm：孩子只能是操作符或库任务
        for i, child in enumerate(node.children):
            if child.task not in operators and child.task not in methods:
                return path + (i,)
            ...
    method = next((m for m in methods.get(node.task, []) if m.name == node.method), None)
    if method is None or not method.applicable(current) \
            or tuple(c.task for c in node.children) != method.subtasks:
        return path                                  # 方法节点：先查自己，再查孩子
    ...
```

- 顺序是计划顺序：任务在子任务之前，孩子从左到右。方法节点的结构问题（孩子和方法的子任务对不上、方法前置条件不成立、方法不属于这个任务）报在方法节点上，不等到某个操作符失败才报。
- 路径用 `enumerate` 的下标，不用 `children.index(child)`：两个一模一样的兄弟节点相等，`index` 只会找到第一个。
- 根节点的路径是空元组 `()`，它是假值，不能写 `return path or None`。
- 操作符节点必须是光秃秃的叶子。带了方法或孩子，`leaves()` 读出来的是孩子，检查器重放的却是这个操作符，认可的就不是同一个计划。
- 只查操作符前置条件是不够的：一串能执行的操作符不等于一个合法的 HTN 分解，把 `ship_change` 的两步调换、或者让 `deploy` 借用别的任务的方法，都得被拒绝。

## 这套题证明了什么，没证明什么

通过了说明你能在这个规模的代码里调试一个递归搜索（回溯、缓存什么时候写、失败记录的键和作用域），把带特殊字符的数据原样存进 INI，写出可复现、计数准确的进化搜索，用 asyncio 写出并发但结果确定的流水线并正确取消任务，以及把搜索过程变成一棵可以独立验证的树。

它没有证明这些：真正的 LLM 怎样提出分解、怎样把自然语言回答解析成子任务（这里的 LLM 是按脚本回答的）；在线方法学习里用回归泛化前置条件；执行期失败后的回滚（讲义练习 1 的那一半）；AlphaEvolve 真正演化的是程序文本和 diff，这里的个体只是课里那两个整数系数；评估器是现成的函数，没有涉及怎样为一个真实领域设计评估器（讲义练习 3、4）。
