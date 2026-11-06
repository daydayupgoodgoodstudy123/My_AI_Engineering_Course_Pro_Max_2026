# 参考答案讲解：Statefile（14/34）

计时结束后再看。参考实现在同目录的 `statefile/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修状态管理器

**现象**：解锁后第一个错误是 `update` 里抛出的 `SchemaError: $.last_human_touch: expected ['number', 'null'], got float`。测试先写了一个人手改过的状态文件，带浮点时间戳，所以很容易怀疑是文件坏了。

**顺着往下找**：`update` 先 `load`，`load` 调 `validate`，`validate` 问 `_check_type` 这个值是不是 number，而 `_check_type` 根本不认识 number，对任何值都返回 False。报错的地方在 `validate`，根因在下面一层。讲义的代码讲解提过：schema 里写了 number 或 boolean，这个函数永远返回 False，是一个静默的子集。

**依次修四处**：

1. `_check_type` 补上 number 和 boolean。number 是 int 或有限的 float，但不是 bool（`isinstance(True, int)` 为真）；JSON 里没有 NaN 和 Infinity，所以用 `math.isfinite`，只用 `math.isnan` 会放过 Infinity。boolean 只认 True 和 False，`value in (True, False)` 会把 1 也算进去。integer 照 docstring 不收 1.0，这一点和 JSON Schema 规范不同，是这个代码库自己的约定。
2. pattern 改成 `re.fullmatch`。`re.match` 只锚定开头，而 Python 的 `$` 能匹配结尾换行之前的位置，所以 `"T-001\n"` 能过 `^T-\d{3,}$`（测验 Q8）。不带 `^ $` 的 pattern 用 `re.match` 时连 `"T-001-old"` 都能过。拼一个 `\Z` 看起来也行，可 `T-\d{3,}|EPIC-\d{2,}\Z` 里的 `\Z` 只管第二个分支。
3. 多余字段只在 `additionalProperties` 为 false 时拒绝。本课的验证器对所有对象都拒绝多余字段，和标准 JSON Schema 的默认行为相反（测验 Q5）。状态 schema 显式写了 false，任务没写，团队可以给任务加自己的字段。要改的是 validate，不是把 `estimate_h` 补进 BOARD_SCHEMA：任何没写 additionalProperties 的 schema 都允许多出来的键，测试另用一个小 schema 查了这一点。
4. 一次 changes 是一次状态转换。`update` 先 load 验证现有文件，在内存里合并全部字段，最后只 commit 一次；commit 验证完整新状态后调用已有 atomic_write。逐字段提交会在后续字段非法时留下合法前缀，也会反复编码、fsync 和替换整份文件。空 changes 只 load 并返回，不 commit。

**护栏**：多字段请求最后一个字段非法时，文件字节必须完整保留；成功请求只发生一次真正的 os.replace。先验证所有字段、再把同一最终状态写多次虽然不会留下非法文件，仍然违反一次提交合同。空更新要验证现有文件，但不重写。测试的 replace 记录器调用真实 os.replace；计时段没有替身 IO。

批量计时使用 256 个有 status / proof schema 的组件检查点和既有 2000 条 touched_files，文件 80,369 字节。真实逐字段提交三次为 0.255894 / 0.471284 / 0.256397 秒，整批为 0.002064 / 0.003418 / 0.001899 秒；0.03 秒限值在实测最差值上两侧分别有 8.53 和 8.78 倍余量。

类型化 enum 的 `_key` 和每顶层调用缓存已经正确给定，不是候选人要优化的缺陷。给定 enum helper 的护栏包括语义、大仓库 0.15 秒性能和动态 schema：True 与 1 不同，1 与 1.0 相等，嵌套数组保序、对象键序无关；跨调用缓存不能藏住同一列表内的重命名。

## Part 2 崩溃安全的快照

`save` 的顺序是：先编码，编码失败（set、NaN）直接抛错，什么都没碰；读出现在的文件，字节完全一样就返回 False；记下原来的权限位（新文件用 0o644）；在同一目录用 `mkstemp(prefix=<文件名>., suffix=.tmp)` 建临时文件，写入、flush、chmod、fsync；`os.replace` 换过去；最后打开目录再 fsync 一次。中途任何异常都删掉临时文件再抛出。

每一步防的是什么：

- 同一目录：rename 只在同一个文件系统里是原子的。名字有固定的形状，下次打开才认得出哪些是自己的残留。
- fsync 文件在 rename 之前：否则断电后名字已经指向新文件，内容却还在页缓存里，得到的是空文件。fsync 之前还要 flush：`fh.write` 只把字节放进 Python 的缓冲区，不 flush 就 fsync，落盘的是一个空文件。测试记下 fsync 那一刻文件的大小。
- fsync 目录在 rename 之后：fsync 文件只保证内容落盘，“这个名字现在指向新 inode”是目录的修改（测验 Q12）。
- chmod：`mkstemp` 出于安全总是 0600，换过去以后，以别的用户身份跑的 CI 和 reviewer 读不了状态文件。权限设在临时文件上、在 rename 之前：rename 以后再改，进程死在中间就留下一个 0600 的状态文件。
- 打开时清理：`kill -9` 和断电时 except 块根本不会执行，残留的临时文件只能由下一次打开来删。只删 `<文件名>.<随机>.tmp`，人的备份、别的文件正在写的临时文件都不能碰。

“没变就不写”比的是字节。`==` 会把 1 和 True、-0.0 和 0.0、键顺序不同的两个 dict 都当成一样；在内存里记住上次写了什么也不行，测试在两次保存之间让“人”改写了文件。格式固定为 `json.dumps(doc, indent=2, ensure_ascii=False, allow_nan=False) + "\n"` 的 UTF-8：键保持原来的顺序，非 ASCII 原样写，diff 才读得懂。Python 的 json 本来就能原样往返 2**63+1、-0.0、5e-324、U+2028 这些值，这一关的精度陷阱都来自“为了好看或省事”加上的选项：`sort_keys`、默认的 `ensure_ascii`、默认的 `allow_nan`、用 `==` 判断没变。

`load` 只做一件事：严格地读。字节先按 UTF-8 解码，再交给 `json.loads`，并用 `parse_constant` 拒绝 `NaN` 和 `Infinity`。截断的 JSON、空文件、非法 UTF-8、NaN、-Infinity 都包成 CorruptSnapshot，坏文件原样留着给人看。讲义里 Hive 的 bug 就是相反的做法：异常被吞掉，会话在坏状态上继续跑，没有任何信号。

## Part 3 迁移链

```python
validate(doc, schemas[version])          # 先确认输入在它自己的版本上是合法的
out = copy.deepcopy(doc)
for v in range(version, target):
    out = migrations[v](out)             # 迁移脚本可以随便改它拿到的对象
    validate(out, schemas[v + 1])        # 每一步都在下一个版本上检查，schema_version 也在内
```

在这之前先挡掉所有读不懂的版本：不是 int（缺失、字符串、bool）、没有对应的 schema、比 target 新（包括降级），以及缺了某一步，统统是 VersionError。讲义说的是 refuses to load a file from a version it cannot migrate，skill 文件把“没有 schema_version 的 schema”列为硬拒绝，所以缺失的版本不能当成 1。

为什么每一步都要验证：测试里的 lossy 在 v2 丢了 next_action，下一步又顺手补了一个默认值，只在最后验证就看不出 v2 那一步是坏的；jumps 自称产出了 v3，如果 migrate 自己去改 schema_version，这个错误就被掩盖了。验证用的是 `schemas[v + 1]`，不是步骤自报的版本：跟着自报的版本走、按自报的版本验证（测验 Q10 的 while 循环就是这样），leaps 一步做完两次升级也会被放过，v2→v3 那一步再也不跑。已经在 target 的文档也走同一条路，先验证再交回拷贝。为什么要 deepcopy：迁移脚本的写法通常是原地修改，annotate 还往嵌套的列表里追加，浅拷贝挡不住。

`upgrade_file` 把整个链在内存里跑完，最后只用 `atomic_write` 写一次；版本没变就不写；任何一步失败，异常往外抛，文件一个字节都没动。

## Part 4 多会话 CAS 提交

`RevisionFile.commit(expected, state)` 每次都重新读盘上的修订号，不等于 expected 就抛 Conflict，什么也不写；相等就用 `atomic_write` 写入 expected + 1。修订号不能记在实例里：每个会话有自己的 RevisionFile，就像不同的进程。

`run_sessions` 给每个会话开一个 task，所有 task 往同一个队列里放结果行，async generator 从队列里取，取到一行就 yield 一行：

```python
for attempt in range(1, max_attempts + 1):
    base, state = store.read()               # 每次尝试都重读
    new_state = await turn(state)            # 在新状态上重跑 turn
    try:
        revision, result = store.commit(base, new_state), "committed"
    except Conflict as lost:
        revision = lost.found
        result = "conflict" if attempt < max_attempts else "gave_up"
    queue.put_nowait(json.dumps({...}) + "\n")
```

丢失更新有两种写法：不比较修订号直接写（后写的覆盖先写的），以及冲突后把旧的结果用新修订号再提交一次（修订号对了，内容还是旧的）。只有重读再重跑 turn，reviewer 加的文件和 builder 加的文件才会同时留下。在一个事件循环里，commit 是同步的，读、比较、写之间不会被别的 task 插进来；换成真的多进程，这三步要用锁文件或 flock 包住，或者换成自带事务的存储。

“一有结果就输出”由测试的探针检查：builder 第一次 turn 要等测试拿到第一行才放行，第二次要等测试拿到第二行，也就是它自己的冲突行。等所有会话结束再输出、一个会话跑完再跑下一个、每个会话结束时才交出自己的几行，都会卡住。冲突行里的 revision 取 `Conflict.found`：第二段测试里人在 planner 思考时存了两遍，磁盘上的修订号比 base 大 2，写 base + 1 就错了。

## Part 5 迁移图寻路

`path` 是带确定性平票规则的 BFS：邻居按版本号排序后展开，每个版本的父节点取第一次发现它的那个。按层处理时，同一层的节点按它们最小路径的字典序出队，所以第一次发现 target 时拿到的就是最短路径里版本序列最小的那条。起点等于终点返回 []；找不到就是 VersionError。

`upgrade` 沿 `path` 跑，和 Part 3 一样先验证输入、每步验证、在拷贝上做。测试给了一个 touched_files 为 null 的 v1 文档，要求一步都不跑就拒绝。

`disagreements` 对每一条从当前版本到 target 的路径各跑一遍，和计划路径的结果比较：

- 每条路径从自己的 deepcopy 开始。迁移脚本会 pop 键、会原地 sort 列表，共用一份或浅拷贝都会让一条路径的副作用串到另一条上。
- 不按版本缓存中间结果。“从不同路径到达同一个版本，内容是否一样”正是要验证的事；按版本缓存，lossy_merge 在 3→4 上的错误就被 2→4 的结果盖住了。路径数是指数级的，这里的历史很小，可以全跑；历史大了，就只比较每条捷径和它跳过的那段链。
- 排除计划路径本身，结果按版本序列排序，用 DFS 加排好序的邻居就能自然得到这个顺序。版本只会往上走，所以超过 target 的版本可以剪掉，但 target 本身要保留。

## 这套题证明了什么，没证明什么

通过了说明你能在一个小的状态管理代码库里调试类型和正则的边界、按 JSON 的语义做 O(1) 查找、写出真正崩溃安全的原子写、设计“要么全部成功要么什么都不变”的迁移、用修订号做乐观并发并按要求输出流，以及在迁移 DAG 上做带平票规则的最短路径和全路径一致性检查。

它没有证明：真实断电下的持久性（进程内只能模拟“死在这一行”）、跨进程或跨机器的并发控制（这里的会话是同一个事件循环里的 task）、Windows 上的行为、讲义里的幂等键与 `pending_calls.jsonl`、事件日志加快照的恢复方式，以及 LangGraph checkpointer 这类真实框架的接口。这些需要另外动手做。
