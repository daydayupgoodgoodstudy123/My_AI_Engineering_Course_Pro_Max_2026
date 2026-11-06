# 参考答案讲解：TaskFrame（14/43）

计时结束后再看。参考实现在同目录的 `taskframe/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修任务框架的校验

**现象**：解锁后第一个失败是讲义的 example frame 不是 ready，`validate` 说 `Only AccountStore.save raises DUPLICATE_EMAIL` 这条事实没有收据，而 `validate` 本身没有错。

**顺着往下找**：`receipt_problem` 对这条收据说的是“`$ git grep -c 'raise DUPLICATE_EMAIL' -> app/accounts.py` 不在仓库里”。原因在 `parse_receipt`：它先试 `路径:行号`，用 `rpartition(":")` 切最后一个冒号，而 `git grep -c` 的输出正好是 `路径:次数`，整条命令收据就被读成了某个文件的第 1 行。同一个 example 里的 curl 收据中间也有冒号（`localhost:8000`），只是最后一个冒号后面不是数字，才碰巧没出事。命令的结果是自由文本，什么都可能出现，所以要先认 `$ ` 开头的命令形式，再按行号形式解析。这一关想练的是：报错的地方是 `validate`，出错的是两层以下的解析顺序。

**依次修三处**：

1. `parse_receipt` 先判断 `$ ` 开头的命令形式。
2. 行号从 1 开始：`app/accounts.py:0` 不是收据。grep -n 和编辑器都从 1 数，第 0 行多半是从 0 起数的工具（比如 LSP）抄来的，这样的收据每一条都差一行。
3. 命令收据的命令和结果都不能为空。讲义说命令结果比行号更好，前提是真的记下了结果；只有命令的收据只说明“可以去跑”，不是证据。

**性能**：`Repo.lines` 每次都把整个文件切一遍，每条收据都要问一次行数。1,500 条收据指向两个 20,000 行的文件，三个独立进程各测一次为 0.689、0.706、0.692 秒。快照的 docstring 写着它不会变，所以每个文件在每个快照上只切一次，存在实例上，之后为 2.139、2.144、2.533 毫秒。0.05 秒的限值在两侧都至少留 8 倍余量。

**护栏**：

- 缓存要跟着快照走。放在模块级、按路径做键，第二个快照里的同名文件会拿到第一个快照的行。
- 行号要和 grep -n、编辑器一致，只按 `\n` 切：结尾换行后面的空串不是一行（`app/accounts.py:34` 不存在），没有结尾换行的最后一行仍然是一行（`app/settings.py:2` 存在）。`splitlines()` 还会在换页符、U+2028 这些字符处切开；测试文件的两个测试类之间有一个换页符，这样切会多出一行。
- 每次用 `str.count` 数换行，不切文件了，但每条收据仍然把整个文件扫一遍，约 0.22 秒，过不了 0.05 秒的限值。

## Part 2 收据钉住

一个 frame 的收据今天能解析，不代表下周还指向同一句话。`pin` 把每条行收据指向的那一行原样存进内容寻址的仓库，再把这个 frame 的 pin 列表也存成一个对象，返回列表的摘要：

```python
pins = [Pin(fact.claim, r.path, r.line, self.put(repo.line(r.path, r.line).encode("utf-8")))
        for fact, r in receipts]
return self.put(json.dumps(listing, ensure_ascii=False, sort_keys=True).encode("utf-8"))
```

- 存的是那一行原样的 UTF-8 字节，不带换行，空白和非 ASCII 字符都不动。Makefile 里那一行以制表符开头、以两个空格结尾，法语提示语里有 é、à 和破折号。
- 对象名就是内容的 sha256，放在 `objects/<前 2 位>/<后 62 位>`。相同的内容只存一份；先写临时文件再 `os.replace`，对象要么不存在，要么是完整的。
- 命令收据没有行可钉，跳过。解析不了的收据在存任何东西之前就报 ValueError。

`recheck` 拿出存下的那一行，和新快照比较：

- 原来那一行还是这些字节：fresh。要先查原位置，后面再出现一次不影响。
- 不在原处，但同一个文件里恰好有一行是这些字节：moved，收据指向新的行号。新提交在 class 上面加了两行 import，`class AccountStore:` 从第 18 行挪到第 20 行，这条事实并没有失效。
- 其余都是 stale：字节没了（`email.strip()` 改成了 `canonical(email)`）、出现了两次（`return account`，选一个就是猜）、文件没了（signup.py 被 routes.py 取代）。不去别的文件里找：一模一样的 import 在测试文件里也有，但那不是原来那条事实说的地方。
- 空白也算变化：Makefile 只是去掉了行尾空格，收据照样是 stale，要重新确认。

## Part 3 决定覆盖

讲义的停止规则是：每个计划中的决定都有证据、被明确授权，或者被列为 unknown。`assess` 对每个决定按 docstring 的顺序取第一个成立的：

```python
asks = [u for u in mine if u.kind == "human" or (u.kind == "decidable" and key not in delegated)]
looks = [u for u in mine if u.kind == "discoverable" and u.look_at.strip()]
if asks:            -> "ask"
elif 证据能解析:     -> "evidence"
elif key in delegated -> "delegated"
elif looks:         -> "investigate"
elif 写进了 non_goals 的 deferred -> "deferred"
else:               -> "open"
```

- human 排在证据前面。“今天返回 409”是证据，“以后要不要改成 422”是会改变公开兼容性的选择，证据回答不了，要在写进代码之前问人。
- decidable 只有在任务契约授权了这个决定时才归 agent。契约没授权，agent 就不能给自己授权，这一条也要去问。
- 证据要经过 Part 1 的 `receipt_problem`：指向不存在的测试文件的“事实”只是假设，proof 这个决定于是落到 discoverable 那一条，去读 Makefile。
- deferred 必须出现在 non_goals 里，否则只是被搁下的决定；discoverable 必须写明去哪里查，否则和 open 没有区别。
- 状态：有 ask 就是 ASK；否则有 investigate 或 open 就是 INVESTIGATE；都没有才是 READY。要问的问题和要读的地方按计划顺序排，同一项只列一次。同一个决定可以有多个 human 问题，不能只留第一条；授权已经解决的决定，不再因为存在 discoverable 线索而要求调查。

## Part 4 侦察流

搜索结果一行一行到达，格式是 grep -n 的 `路径:行号:文本`。每来一行：

```python
path, sep, rest = line.partition(":")
number, sep2, text = rest.partition(":")
if not (sep and sep2 and path and number.isdigit()):
    continue                      # "--"、"Binary file ... matches"
surface = surface_of(path)
settled = [key for key, checks in pending.items()
           if any(surface in probe.surfaces and rx.search(text) for probe, rx in checks)]
...
yield f"{path}:{number}:{text}\n"
if not pending:
    return
```

- 只在前两个冒号处切，文本里的冒号原样保留。
- 正则只搜文本，表面由路径决定：路径里带 409 的测试文件、ADR 里写的 409，都不是 error_shape 的约束。
- 一条结果可以同时定下几个决定，只发一次；已经定下的决定不再响应。
- 最后一个决定定下，发完这一行就 return，不再拉下一条。讲义说过了停止点还在读，多半是在回避。没有探针时一条都不拉。
- 一定下就发出去，不先读完整个搜索。

生成器 return 并不会关掉上游的搜索。真实的 grep 是子进程，要用 `contextlib.aclosing` 或者显式 `aclose()`，让上游在 finally 里结束子进程；测试没有检查这一点。

## Part 5 收窄允许路径

先把计划里还不存在的文件加进树里，再递归：每个目录返回“下面的文件是不是都要改”和它贡献的条目。一个目录只有同时满足三条才收成 `dir/**`：下面的文件全都在计划里，没有任何禁止项落在它下面，而且这一项能替掉至少两项。

- 收起来的 `dir/**` 也允许以后在里面新建文件。所以只有一个文件的目录不收（条目没变少，范围却变宽了），根目录也永远不收。
- 禁止项不必存在：`app/.env` 还没有，`app/**` 却会允许创建它，所以 app 不能收。
- 深层的禁止项挡住它上面的每一层；空目录什么都不加，也不挡父目录。兄弟目录的完整性要累积：一个目录有不在计划里的文件，后面另一个目录全部在计划里也不能把父目录改判成完整。
- 要改的文件本身被禁止，说明 frame 自相矛盾，报 ValueError。

## 这套题证明了什么，没证明什么

通过了说明你能顺着调用链找到报错之外的根因，能把收据做成可以复核的内容寻址记录，能把讲义的停止规则和 unknown 分类写成确定的判定，能写出按条件停下的流式读取，能在目录树上做最小覆盖。它不涉及真实仓库的搜索和 git 历史，不涉及把 frame 渲染成 `outputs/task-frame.md`，也不涉及下一课的执行计划；验收证据有没有点名权威测试，这里只通过 proof 这个决定间接检查。讲义里的练习 1 和 5（给真实的 bug 写 frame、给验收证据加一条范围收据）需要在自己的仓库里另外做。
