# 参考答案讲解：Workbench（14/32）

计时结束后再看。参考实现在同目录的 `workbench/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修回合循环

**现象**：解锁后的第一个错误是 `load_state` 里的 `TypeError: AgentState.__init__() got an unexpected keyword argument 'last_run'`。

**依次修四处，再处理计时**：

1. `load_state`：按 `STATE_KEYS` 取课里的五个键，其余的放进 `extra`，`save_state` 本来就会把 `extra` 原样写回。这就是课后测验 Q11 说的报错：状态文件和 dataclass 绑得太紧，新工具多写一个键，旧工具就起不来。只把未知键过滤掉也能让报错消失，但下一次写文件时 `last_run` 就没了，测试的第一条断言查的就是这个。照测验 Q11 的参考答案把 `last_run` 加成字段也不行：状态文件里还有一个 `lease`，同样的 TypeError 换个键名又出来了。
2. 接回进行中的任务。修完第一处，报错变成 `ValueError: the builder has 2 tasks in progress: T-007, T-006`，位置在 `take_turn -> save_board -> check_board`，而 `check_board` 没有错。往回找：测试模拟的是上一个会话写完看板、还没写状态就死了，所以 T-006 在看板上是 in_progress，状态里没有活动任务；`run_one_turn` 只找 todo，又领了 T-007。按 docstring，没有活动任务时先找 owner 是 builder、状态是 in_progress 的任务，再找 todo。`take_turn` 先写看板后写状态，就是为了让崩溃留下的是看板上的 in_progress，下一回合能接回来。这一关想练的是：报错的位置往往不是出 bug 的位置。
3. 退出码。`all(exits.values())` 把 0 当成假：T-007 的命令全部退出 0，却走进 blocked 分支，blockers 是空列表，`state.blockers[0]` 报 IndexError。改成判断 `code == 0`，失败就是 `code != 0`。T-006 的登录测试被信号杀掉，退出码是 -9，写成 `code > 0` 会把它当成通过。
4. 没有验收命令。`all()` 对空序列返回 True，T-008 一条命令都没跑就成了 done。AGENTS.md 的完成定义要求验收里的命令退出 0，没有命令就不可能满足，所以 T-008 要 blocked，blocker 写 `T-008 has no acceptance command`。配套 skill 说没有 acceptance 的任务会变成“looks good”的橡皮图章，说的就是这种情况。
5. 按需文档读取。`load_context` 先遍历并读取全部Markdown，最后才按requested取内容；输出看起来正确，实际每回合读了许多无关文件。正文的tiny root router要求只在相关时加载深文档。使用给定context_paths得到AGENTS.md加本次请求的稳定去重路径，再直接读取这些文件；每次调用重新读选中文档，不保留跨回合catalog。20个回合、600份无关文档，慢0.644–0.663秒，快1.192–1.315毫秒，限0.03秒。

**护栏**：未知键仍须保留，接回任务仍只属于builder，退出码按0判断且验收不能为空。`check_board` 从起始就是正确的线性校验器；重复id点名与8000正常任务计时验证它保持健康。上下文输出精确保留首次请求顺序，不把AGENTS.md或重复路径发两次；改过的选中文档下一次读取立即可见，未请求的非法UTF-8文件完全不读。路径规范化和原文读取helper已给对。

## Part 2 JSON Lines 看板

参考实现保存的是“文件里的行”，不只是任务：

- `save` 写规范行：每个任务一行 `json.dumps(task_to_doc(task)) + "\n"`。课里的键在前，`extra` 在后，所以 R-001 的 `depends_on`、`priority`、`notes` 排在 `checks` 后面。
- `load` 按 `"\n"` 切开，跳过空行，逐行 `json.loads` 再 `task_from_doc`，最后跑 `check_board`。文件以换行结束时，切出来的最后一项是空串，不跳过就会报 `Expecting value`。
- `update` 读出所有行，逐行解析、比较 `id`，只替换这一行，其余行（包括空行）原样用 `"\n"` 拼回去。替换之前先对替换后的整个看板跑 `check_board`，不合法就什么都不写。

容易漏的几点：

- **手写的行**：测试手工追加的 T-003 前面空了一行，本身是紧凑格式、键的顺序不同，也没有 `checks`。整个文件重写一遍，它就变成了规范格式，空行也没了。测试用 `difflib.unified_diff(..., n=0)` 比较，只允许一块 `@@ -3 +3 @@`，也就是第 3 行原地被替换；删掉旧行、把新行追加到末尾也过不了。练习 3 要 JSON Lines，图的就是 diff 干净。
- **空行**：读的时候跳过，改的时候留着。用 `splitlines()` 不跳过会报 `Expecting value`；按任务在 `load()` 结果里的下标去改第几行，会被空行错开一位。
- **找对行**：不能用子串，R-001 的 goal 和 depends_on 里都有 T-002；也不能拿 `'"id": "T-003"'` 这种规范写法去匹配，手写的那行是 `"id":"T-003"`。
- **整板检查**：只检查传进来的任务不够。T-003 已经在做，这时把 T-002 改成 in_progress，单看 T-002 没问题，整个看板上 builder 却有两个任务在做。
- **不缓存**：别人会在两次调用之间改文件，每次都要重新读。
- **合并之后**：两个分支各加了一个 T-004，git 把两行都留了下来，`load` 要报错，而不是挑一个。

## Part 3 取任务

先看时间，再看看板：

1. `last_run` 用 `datetime.fromisoformat` 解析。没有时区偏移就报 ValueError；有偏移就直接和 `now` 相减，两个带时区的 datetime 相减会自动换算。年龄严格大于 24 小时才算过期，正好 24 小时还能跑。
2. 过期时只有 `confirm == last_run` 才放行。确认点名的是操作员看过的那个状态；这次运行结束会写入新的 `last_run`，旧确认自然就失效了，所以它只管一次运行。这一步在看板之前，看板上没事可做时，过期的状态也是 refuse。
3. 整板检查一遍 `depends_on`，不在看板上的 id 报 ValueError，并写出这个 id。
4. 遍历 builder 的 todo：有没完成的依赖就记进 `waiting`；否则和当前最好的比优先级，严格大于才替换，这样平局时留下看板上靠前的那个。没有可开始的任务时返回 idle 和 `waiting`。先看 owner 再算依赖，human 的 H-020 也在等 T-021，但不进 `waiting`。

几个错法和后果：不看 owner 会拿 H-001；不排除 blocked 会拿 T-002；把 in_progress 的依赖当成满足会拿 T-003；平局用 `>=` 会拿 T-006，按 id 打破平局也会拿 T-006，因为看板上 T-010 排在它前面。`.replace(tzinfo=timezone.utc)` 只改标签不换算，把 10:30+02:00 当成 10:30 UTC，年龄就从 24.5 小时变成了 22.5 小时。

## Part 4 回合 JSON Patch

`diff` 递归比较，分三种情况：

```python
# dict：按 before 的键顺序，after 没有的 remove，两边都有的递归；再按 after 的顺序 add 新键
# list：共同的下标逐个递归；after 多出来的按下标 add；before 多出来的从最后一个往前 remove
# 其他：类型不同或值不同就 replace，null 也是值
```

路径片段先把 `~` 换成 `~0`，再把 `/` 换成 `~1`。RFC 6901 规定解码时先把 `~1` 还原成 `/`、再把 `~0` 还原成 `~`，编码就得反过来。验收命令做了 `checks` 的键，所以 `tests/test_login.py` 和 `HEAD~1` 都会出现在路径里。

`turn_patches` 记住上一次发出去的文档：

```python
sent = workbench_document(root)
for _ in range(turns):
    take_turn(root, run)
    current = workbench_document(root)
    yield json.dumps(diff(sent, current)) + "\n"
    sent = current
```

- 对着 `sent` 比，回合之间人改的内容（第 4 行之后把 T-006 改回 todo，又加了 H-003）会随下一行一起发出去。每回合开始时重新读文件当 before，这些修改就漏了。
- 生成器在每个回合结束时 yield，第一行到达时只跑了一个回合。
- 没有变化的回合也发 `[]`，watcher 收到的行数和回合数一致。回合数是调用方给的，没事可做了也照样跑完。
- 格式由测试决定：每个补丁恰好一行、以换行结束，测试逐行 `json.loads`，再交给自己写的严格应用器，应用后的结果要和磁盘上的文件一致。

## Part 5 Epic 汇总

先按看板顺序建 `children` 和 `roots`，parent 不在看板上就报错。然后从每个根做后序遍历：叶子保留自己的状态；epic 看子节点汇总后的状态，全部 done 为 done，否则有 blocked 为 blocked，否则有 in_progress 或 done 为 in_progress，否则 todo。遍历完还没有状态的任务，一定挂在 parent 环上，报 ValueError，并写出看板上第一个这样的任务。

`conflicts` 最后按看板顺序生成，只看有子任务的节点。

`next_leaf` 是另一次深度优先：兄弟按优先级稳定排序（`sorted` 是稳定的，平局保持看板顺序），遇到 epic 就进去找，遇到 builder 的 todo 叶子就返回。E-1 在根这一层优先级最高，所以它下面优先级 0 的 T-113 先于根上优先级 4 的 T-9。E-1 汇总后是 blocked，但 T-113 本身是 todo，照样可以做。S-11 下面 T-113 和 T-110 优先级相同，T-113 在看板上靠前；按 id 打破平局，或者改成显式栈却按优先级升序压栈，都会拿到 T-110。

## 这套题证明了什么，没证明什么

通过了说明你能在这三个文件上调试一个一次推进一步的回合（崩溃后接回、完成定义、新旧版本的键共存），只读取本回合相关的深文档，把看板换成一行一个任务而保持 diff 干净，实现带依赖和过期确认的取任务规则，写出符合 RFC 6902 和 RFC 6901 的逐回合补丁流，以及在 parent 指针上做树汇总。

它不涉及真正的模型和真正执行验收命令（runner 是测试给的假服务），也不涉及多个 agent 并发写同一个文件和原子写（第 34 课），`AGENTS.md` 的行数和链接检查（练习 4 和第 33 课），以及嵌套 `AGENTS.md` 的逐级拼接和跨工具软链接。这些需要另外动手。
