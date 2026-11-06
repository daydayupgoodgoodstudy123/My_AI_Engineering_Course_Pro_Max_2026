# 参考答案讲解：ThoughTree（14/04）

计时结束后再看。参考实现在同目录的 `thoughtree/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修 ToT 搜索

**现象**：解锁后第一条断言就挂了，[4, 4, 10, 10] 只返回了一步 `10 * 10 = 100`。

**依次修四处**：

1. **停止条件**。tot_bfs 照搬了课里的 `if value(child) > 0.99: return`。课里的价值函数只有解出来的终局才得 1.0；这里的评判员按 sure / likely / impossible 打分，sure 的状态也是 1.0，于是还剩三个数的 (100, 4, 4) 被当成了解。改成 `if solved(child)`：只剩一个数、而且是 24，才是解。sure 只说明还有希望。
2. **精确算术**。修完第 1 处，[4, 4, 10, 10] 过了，[3, 3, 8, 8] 却返回 None，它明明有解 8 / (3 − 8 / 3)。顺着往下找：start() 把整数原样放进状态，`/` 得到 float；评判员穷举 (8, 3, 2.6666666666666665) 时，8 / (3 − 2.6666666666666665) 算出 23.99999999999999，不等于 24，这个状态被判成 impossible，beam 把它丢了。报错的地方离根因隔着 tot_bfs → value → solvable → children → combine 好几层。[4, 4, 10, 10] 能过，只是因为 96 / 4 = 24.0 恰好等于 24。修法是 start() 里把每个数换成 Fraction，之后的运算全都精确。在比较的地方加容差不行：步骤里还是 2.6666666666666665 这样的数，精确步骤的断言照样挂。
3. **非交换运算**。[1, 5, 5, 5] 返回 None。它的解 5 * (5 − 1 / 5) 需要 1 / 5，可是状态按降序排，a 总是不小于 b，课里的 expand 只生成 a op b，b − a 和 b / a 永远出不来。按 docstring 的顺序每对数生成 a + b、a − b、b − a、a * b、a / b、b / a。
4. **转置**。最后挂的是计时：五个 7、五个 9、五个 10 用 plain BFS 证明无解，原代码要 1.5 秒以上。同一个状态可以从很多条路径到达（两个相同的数、5 * 1 和 5 / 1、先合并哪一对），每层不去重，每条路径都要展开和打分一遍，每个 deal 生成 24.3 万个孩子。每层用一个 set 记下已经见过的状态，第一次见到才打分、才保留，一共 8 毫秒左右。

**护栏**：

- 只有 - 和 / 要两个顺序。四种运算都按两个顺序算，+ 和 * 每对数会多出一个完全一样的孩子，测试精确断言了 (5, 1) 的 6 个孩子和 (6, 4, 4, 1) 的 36 个。children() 自己去重、a == b 时跳过 b − a，个数也不对。去重是搜索的事。
- 去重要在截 beam 之前。截完再去重，beam 里就剩不到 5 个状态；按“走过的步骤”去重，5 * 1 和 5 / 1 这种不同步骤到达同一状态的情况合并不了。这两种写法计时都能过，[1, 5, 5, 5, 13] 会失败，因为第一层的几个相同状态占满了 beam。
- 一层只用一个 set，建在 frontier 的循环外面。建在循环里面就是每个父节点各去各的重，不同父节点到达的同一状态照样重复。第一层只有根一个父节点，看不出区别；[5, 6, 6, 6, 7, 10] 在第二层被这样的重复挤满，找不到 (10 + 7 + 5) + (6 + 6) / 6。
- 平分保持发现的顺序。`sort(key=lambda item: item[0], reverse=True)` 是稳定排序；按 (score, state) 元组排，平分时比的是状态大小，[1, 2, 3, 8] 会找到另一条解。
- [1, 2, 3, 4, 6, 11] 有解，ToT 却找不到：六个数时第一、二层评判员只能按离 24 多近来估计，每层 5 个状态不够。这一条钉死了 beam 是“每层留 5 个”，按父节点各留 5 个就会找到它。它也说明了课里那句话：价值函数不可靠时，搜索会稳稳地错过。

## Part 2 搜索检查点

检查点要装下 run() 依赖的一切：seed、c、已经跑了几次迭代、解（如果有），以及每个节点的状态、trace、visits、value_sum 和孩子的顺序。参考实现的布局：

```
HEADER   "<4sHqdqI"  MAGIC、VERSION、seed、c、iterations、节点数
COUNT    "<i"        解有几步，-1 表示还没有解
解的每一步：1 个字节的运算符，再是 a、b、result，各一个 NUMBER
每个节点，深度优先先序（节点本身，再按顺序是每个孩子的子树）：
  NODE   "<QdBI"     visits、value_sum、状态里有几个数、几个孩子
  NUMBER "<qq"       状态里每个数的分子和分母
  根以外的节点，再写导致它的那一步
```

trace 不用整条存：读回时每个节点的 trace 是 `parent.trace + [step]`，一定要建新列表。但最后这一步要存，不能从状态反推：4 * 1 和 4 / 1 到达同一个状态，测试里就有一个经 4 / 1 到达的节点。

容易错的地方：

- **数**：分子分母各一个有符号 64 位。经过 float，2/3 读回来就是 6004799503160661/9007199254740992；分子用无符号，负数存不进去；用 32 位，1000033 × 1000003 就溢出了。
- **ValueError**：放不下 64 位的数（2^80）、截断、多出来的字节、错误的 magic 或版本，都要报 ValueError。struct 自己抛的是 struct.error，不是 ValueError 的子类，所以 save 和 load 都要把它转换掉。测试把 blob 的每一个前缀都试了一遍。
- **浮点**：value_sum 和 c 用 'd'，0.1 + 0.2、1/3、次正规数 2.5e-310、√2 才能按位还原。
- **None 和 []**：已经是 24 的 deal，解是空列表；还没找到解是 None。参考实现用 -1 表示 None。
- **类型**：数读回来要是 Fraction，visits、seed 和 iterations 要是 int。整数读成 int 时 `==` 照样成立，可后面一做除法又成了 float，Part 3 的续跑就会悄悄出错；visits 存成 double 读回来是 1000003.0，`==` 也看不出来；seed 读成 9.0，f"{seed}:{i}" 拼出的种子就变了。

## Part 3 MCTS

`iterate()` 是课里 MCTS 的四步，加上让它可以续跑的随机数：

```python
rng = random.Random(f"{search.seed}:{search.iterations}")
node, path = search.root, [search.root]
while node.children:                                   # 1. select
    parent = node
    node = max(parent.children, key=lambda child: uct(parent, child, search.c))
    path.append(node)
if node.visits > 0 and len(node.state) > 1:           # 2. expand, on the second visit
    node.children = [Node(state, node.trace + [step]) for step, state in children(node.state)]
    node = node.children[0]
    path.append(node)
state, rollout = node.state, []
while len(state) > 1:                                  # 3. simulate
    step, state = rng.choice(children(state))
    rollout.append(step)
score = reward(state)
for visited in path:                                   # 4. backpropagate
    visited.visits += 1
    visited.value_sum += score
search.iterations += 1
return node.trace + rollout if solved(state) else None
```

- **UCT**：没访问过的孩子返回 +inf，先判断再算 ln N / n。`max()` 遇到平分返回第一个，正好是 docstring 要的。
- **延迟扩展**：和课里一样，叶子第二次被选中才展开。父节点有孩子时它的 visits 至少是 1，所以 ln N 不会遇到 0；前提是回传包括根。
- **什么时候加 visits**：在第 4 步回传时加。往下走的时候就加，UCT 里的 N(s) 把这一次也算了进去，[2, 3] 在 c = 0.1 下跑 70 次，访问次数就和规定的不一样。
- **终局**：只剩一个数的节点不展开，从它 rollout 就是零步，奖励就是它自己的。
- **随机数**：每次迭代用 seed 和累计迭代数新建一个生成器。续跑时只要检查点里有 seed 和 iterations，就能重放出同样的 rollout，所以存档、读回、接着跑，和一口气跑完逐字节相同。
- **解**：rollout 走到 24 就是解，trace 是 rollout 起点的 trace 加 rollout 的步骤。课里的 mcts 把这样的解丢了，最后还在所有叶子里按启发式挑了一个没做完的状态当答案（测验 Q7、Q11）。[4, 6, 4, 1] 用 seed 9，第 150 次迭代由 rollout 找到 (6 − 1) * 4 + 4；只认树里的节点，要到第 640 次。
- **c**：[1, 2, 7] 无解，跑 100 次。c = 0.1 时 2 + 1 = 3 这个孩子拿到 20 次（剩下的 7 和 3 能凑出 21，奖励 1/4，是这里最好的），c = 2.0 时每个孩子 5 到 6 次。这里大部分奖励都接近 0，Q 之间差得很少，c 稍大一点搜索就近似轮流访问。

## Part 4 流式评估

每一层：找出前沿状态的所有不同孩子，全部同时送去评判，回来一个输出一行。参考实现用 `asyncio.as_completed`，停下时在 finally 里取消并等待：

```python
tasks = [asyncio.create_task(judged(i)) for i in range(len(order))]
try:
    for next_back in asyncio.as_completed(tasks):
        i, value, tokens = await next_back
        used += tokens
        values[i] = value
        yield _line({"depth": depth, "state": [str(x) for x in order[i]], "value": value, "tokens_used": used})
        if solved(order[i]):
            yield _line({"stop": "solved", "tokens_used": used, "trace": [str(s) for s in found[order[i]]]})
            return
        if used >= budget:
            yield _line({"stop": "budget", "tokens_used": used})
            return
finally:
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
```

- **顺序**：测试里的评判员先回答最后一个问题，所以“回来的顺序”和“发出的顺序”正好相反。测试还记录了每一行到达时已经回来了几个评估，等整层都回来再输出就对不上。
- **预算**：只加已经回来的评估。达到预算的那一行照常输出，紧跟 stop 行；解和预算同时到时，解优先。stop 行写实际花掉的总数，可以超过预算（预算 50 时是 60）。
- **听评判员的**：下一层按评判员回来的分数选，不自己再调 game.value。测试里有一个把每个判断都说反的评判员，跟着它走就找不到解，这正是评判员不可靠时会发生的事。
- **已经是 24**：不调评判员，只输出一行 solved，trace 是空列表。
- **取消**：只 cancel 不 await，生成器结束时任务还在跑。测试里的评判员挂断要花几轮事件循环，所以必须真的等它们结束。
- **beam**：一层评完，按分数取前 beam 个，平分时按发现的顺序，不能按回来的顺序。
- **格式**：每行一个 JSON 对象加 `\n`，数写成字符串，`"1/5"` 才能精确表达。

## Part 5 表达式树

`build()` 维护一个池子：deal 的每个数是一个带位置的 Leaf，按 deal 的顺序；每一步先取 a，再从剩下的里取 b，都取池子里最早的那个，取到就删掉，然后把 `Op(op, a, b)` 追加到末尾。最后池子里必须只剩一个表达式。

- 两个相同的数（10 * 10、deal 里的两个 4）各是一片叶子：取 a 时删掉，取 b 时才会拿到另一个。
- 结果可能和 deal 里的数相等：[2, 3, 6, 6] 里 6 / 3 = 2，下一步的 2 * 6 用的是 deal 里原来的那个 2，因为它在池子里更早。
- 减法和除法保留步骤里的左右：`1 - 6 = -5` 就是 Op("-", 1, 6)，渲染出来是 4 − 4 * (1 − 6)。
- `render()`：子表达式的运算比父节点松才加括号；右边的子表达式在父节点是 − 或 / 且一样紧时也加。所以 10 − (3 − 1) 要括号，10 − 3 − 1 不要；10 + 3 − 1 是 10 + (3 − 1)，10 * 3 / 1 是 10 * (3 / 1)。
- `evaluate()` 用 Fraction，返回的也是 Fraction。用 float 或 `eval(render(...))`，8 / (3 − 8 / 3) 就成了 23.99999999999999。

## 这套题证明了什么，没证明什么

通过了说明你能在搜索代码里调试（停止条件和价值的含义、精确算术、非交换运算、转置），能设计一个可以续跑的二进制检查点，能实现可复现的 MCTS 四步，能写带预算和取消的并发流式评估，也能处理表达式树。它不涉及真实 LLM 的提示词、自评的质量和噪声、LATS 的反思（Reflexion）环节，也不涉及用单元测试做价值函数的代码任务。课里的练习 2（给价值函数加噪声）、练习 4 和 5（读 LATS 论文）需要另外做。
