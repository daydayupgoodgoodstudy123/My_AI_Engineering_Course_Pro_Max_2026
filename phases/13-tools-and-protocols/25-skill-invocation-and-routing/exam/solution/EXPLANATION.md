# 参考答案讲解：SkillRoute（13/25）

计时结束后再看。参考实现在同目录的 `skillroute/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修路由器

**现象**：解锁后的第一个失败是 `(False, 'incident-triage', 'implicit-model', 0.8)`，测试要的是 `(True, 'incident-review', 'implicit-model', 0.5)`。路由器选中了得分最高的 incident-triage，发现它不许模型调用，于是整个请求都弃权了。

**依次修四处**：

1. 隐式分支改成先过资格、再排序：对每个 skill 问 `adapter.allows`，只给允许的打分，一个都不允许时弃权。原来的写法是课里 Eligibility must precede ranking 点名批评的那种：被挡住的最高分把排在后面、本来可以用的 skill 也挡掉了。
2. `ExtensionPolicyAdapter.allows` 里两个宿主字段各管各的 actor：`user-invocable: false` 只去掉人类的直接调用，`disable-model-invocation: true` 只去掉模型和自主 agent 的选择。原来的代码正好是课里那两种误读：前者被当成“模型不能用”，后者被当成“整个禁用”。症状出现在上一层：人类按名字调 incident-triage 被拒，`eligible(HUMAN)` 和 `eligible(MODEL)` 都不对。对照 2×2 矩阵就能写出四个 skill 各自应该在哪边。
3. 补上歧义规则。阈值检查之后，找出分数和最高分相差不超过 `ambiguity_margin` 的可调用 skill，超过一个就不激活，按名字排好放进 `candidates`：

   ```python
   close = sorted(skill.name for other, skill, _ in scored if score - other <= policy.ambiguity_margin)
   if len(close) > 1:
       return InvocationDecision(False, actor, None, mode, round(score, 4), f"ambiguous between {', '.join(close)}", tuple(close))
   ```

   用 `<=`，所以默认边际 0 时完全并列也算歧义。歧义只在可调用的 skill 之间判断；阈值先于歧义，因为两个都不相关的 skill 打成平手，没有必要去问用户。课里代码的 `max(key=(score, name))` 让字典序决定并列，这在 quiz Q10(a) 里已经被指出来了。
4. 目录在构造时解析一次，并建一张名字到 skill 的表。原来 `_catalog()` 在每次 `route` 和 `eligible` 里都把所有 frontmatter 重新解析一遍，3000 个 skill、50 次显式调用要 0.3 秒左右；按名字查表以后约 0.07 毫秒。只解析一次、显式调用时仍在列表里线性查找，大约 0.7 毫秒，也能过。显式调用是 identity-first 的，本来就该按身份直接查。

**护栏**：给出的解析器只把不带引号的小写 true/false 变成布尔值，`"false"`、`False`、`TRUE` 都是文本。课里的 `_extension_false` / `_extension_true` 已经按“布尔值，或任意大小写的 true/false 文本”处理了，提速时不要改写成 `bool(value)`：`bool("false")` 是 True。另外，core 适配器不认宿主字段，应用通道不受这两个字段影响，按名字调用也要过策略。

## Part 2 可重入状态

一个 JSON 文件，布局在模块 docstring 里，因为 skill 的指令也读写这个文件。参考实现每次改动都把整个状态写进同目录的临时文件，fsync 后 `os.replace`：

```python
self.path.parent.mkdir(parents=True, exist_ok=True)
fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=f".{self.path.name}.", suffix=".tmp")
...
os.replace(tmp, self.path)
```

`resume` 就是课里写给 skill 正文的三句话：

- 文件不存在，就是新的运行。
- 同一个 skill、同一个候选、同一个 commit、同样的参数，就接着干：已完成的步骤和已记录的写入都保留。
- 其中任何一项不同，就是另一次运行：已完成的步骤作废，外部写入的记录保留。步骤是针对旧 commit 得出的结论，不能沿用；写入是外部世界已经发生的事，扔掉记录就会再发一次。
- 文件属于另一个 skill，报 ValueError。

重新校验 commit 用完整的 40 位 id 精确比较。测试里 tag 移到的新 commit 和旧的前 12 位相同，按前缀比较就会把旧结论当成有效的；短 SHA 直接拒绝，因为它本身就不能用来校验。

`write_once` 按幂等键查记录，查到就返回记下的结果，不看结果是什么。204 No Content 那次写入的结果是 `None`，用真值判断就会重复。没查到才调用 `action(key)`，返回以后才记录、保存：action 抛异常时什么都不记，下次用同一个键再执行。先记一个占位再调用，失败的写入就永远补不上了。

`complete` 拒绝两种输入：已经完成的步骤，以及 JSON 存不准的输出。`json.dumps({200: 14})` 不会报错，只是悄悄把键变成了 `"200"`，所以检查的办法是走一遍 `json.loads(json.dumps(value)) == value`，不相等就报 ValueError，而且在追加之前检查，什么都不记。

读回来要完全一样：`Step` 和 `Write` 对象、发生的顺序、0 和 `[]` 和 `None` 这些假值。这一章别的题已经考过写到一半崩溃的情况，这里测试没有模拟，参考答案照样整文件替换。

## Part 3 参数绑定

三种表示，三个函数。

`split_command` 去掉开头的 `/`，剩下的交给 `shlex.split`。docstring 写的规则就是 POSIX shell 的分词规则（不做任何展开，`#` 也不当注释），shlex 的 ValueError 转成 `ArgumentError`。`""` 会留下一个空参数，单引号里的反斜杠原样保留。

`bind` 从左到右扫一遍参数向量：

```python
if arg == "--":
    given_positional.extend(argv[i:])
    break
if not arg.startswith("--"):
    given_positional.append(arg)
    continue
option, has_value, inline = arg.partition("=")
param = options.get(option)     # 整个名字精确匹配，不认缩写
```

只有 `--` 开头的才是选项，`-1`、`-rc` 都是值。之后依次处理：未知选项、固定参数、重复、开关带值、选项缺值（下一个参数以 `--` 开头也算缺值）都报 `ArgumentError`；位置参数按声明顺序填，多了报错；没给的参数取默认值；必填参数没给就放进 `missing`，不报错，也不猜，宿主据此去问用户。`publish` 是课里 Use It 那份调用契约的 `publish: fixed_false`：调用方不能设置，结果里永远是 False。

`tool_arguments` 按 schema 再检查一次：string 原样保留，`"2.10"`、`"007"` 都还是字符串；integer 只接受可选负号加 ASCII 数字，`"-1"` 变成 -1；boolean 只接受真正的布尔值，文本一律不转，`"false"` 直接报错；string 也不接受布尔值；不在 properties 里的名字、缺少的必填属性都报错。默认值 `"1"` 也走这一步，变成 1。

端到端那段经过 `SkillHost.prepare`：先由 Part 1 的路由器决定能不能调用，再绑定，再类型化。`"v2.4.0; rm -rf ~"` 和 `"$(whoami) | tee"` 从头到尾只是一个字符串值；脚本拿到的应该是参数向量，不是拼出来的命令行。

## Part 4 多轮生命周期

一个 async generator，状态只有三样：当前回合号、本回合批准的工具、激活的 skill 及其正文（压缩后记为 None）。

```python
async for event in events:
    if isinstance(event, UserTurn):
        turn += 1
        allowed = set()
        ...                                  # /name 显式；没有激活的 skill 时才隐式路由
    elif isinstance(event, Approve):
        allowed.update(event.tools)
    elif isinstance(event, Compaction):
        for name in bodies:
            bodies[name] = None              # 只丢正文，skill 仍然激活
    elif isinstance(event, ToolCall):
        ...                                  # 没激活 -> denied；正文为 None -> 先 load_body，输出 reloaded
                                             # 再看本回合有没有批准：executing 或 denied
    elif isinstance(event, Check):
        ...                                  # 通过才 completed，并移出激活集合
```

- 批准跟着回合走，不跟着压缩走：压缩丢的是正文，不是授权。课里那句 Tool allowances may last one turn while instructions persist longer。
- 正文跟着 skill 走：每个 skill 各自记着自己的正文在不在，压缩后在自己的下一次工具调用之前重新加载。不能凭内存里的旧正文继续，测试里的 SKILL.md 在会话中途改成了 r2。
- 已激活的 skill 在后续回合保留：普通文本的回合只是接着干，不重新路由；再次调用已激活的 skill 什么都不输出。
- 每个阶段一发生就 `yield`，所以探针在第一个回合之后最多只多拉一个事件。

trace 里分开的 eligible、selected、activated、executing、completed，正是课里五个阶段；reloaded 和 denied 让压缩和拒绝在 trace 里也看得见。

## Part 5 skill 调用链

宿主用一个不可变的元组记录调用链，链上每一项是 (skill 名, 启动它的请求)，根的请求是 None。每次 `ctx.call(request)`：

```python
names = [name for name, _ in chain]
if req.target_skill in names:                          # 1. 环：目标在链上的任何位置
    refused("cycle: " + " -> ".join([*names, req.target_skill]))
depth = len(chain)                                     # 2. 深度：根发出的调用是 1
limit = min([r.max_depth for _, r in chain if r is not None] + [req.max_depth])
if depth > limit:
    refused(f"depth {depth} exceeds max_depth {limit}")
spec = self._skills.get(req.target_skill)              # 3. 存在
```

- 链是宿主自己的记录，请求里没有调用者和深度，伪造不了。环检测看整条链，所以回到根的环、经过第三个 skill 的环、不经过根的环都能查出来。
- 深度上限取链上所有请求和这次请求里最小的 max_depth，下面的请求不能把上面定下的上限调大。
- 目标运行时，fork 的看到空上下文，shared 的看到调用方看到的东西；请求总在 `ctx.request` 里。
- 回复的契约和 expected 不一致就算失败。
- 没完成的调用：有 fallback 就把 fallback 交给调用方继续，节点标 `used_fallback`；没有就在调用方里抛 `Stopped`。判断用 `is not None`，空串也是 fallback。宿主只接住 `Stopped`，skill 自己抛的其他异常原样传出去。调用方不处理它，宿主在调用方那一层接住，把调用方记为 failed "stopped"，再交给上一层的请求去决定。用不可变的链，异常路径上不需要手动弹栈；用可变栈就要放在 finally 里。

调用树记录每一次调用，包括被拒绝的，按发生顺序，完成的节点带上结果。

## 这套题证明了什么，没证明什么

通过了说明你能在策略和路由分开的代码里顺着调用链调试，能把可重入的运行状态存进一个和 skill 指令共用的 JSON 文件，能把调用文本一路转成类型化的工具参数而不碰 shell，能写出按回合管理授权、压缩后重新加载正文的事件流，能在宿主自己记录的调用链上处理环、深度、fallback 和上下文隔离。它不涉及真实的模型路由：词汇打分只是为了让策略边界可检查，课里说得很清楚，它不代表生产中的路由质量。它也不涉及路由评测（正例、负例和 near miss 的混淆矩阵在第 27 课），不涉及权限和沙箱（第 26 课），也没有接真实宿主的命令菜单、参数展开和子 agent。
