# 参考答案讲解：RuleCheck（14/33）

计时结束后再看。参考实现在同目录的 `rulecheck/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修规则报告

**现象**：解锁后的第一个错误是 `Report.verdict` 里的 `KeyError: 'startup/state-file-fresh'`，而 `Report.verdict` 本身没有 bug。

**顺着往上找**：报告里没有这条规则，是因为 `score` 拿到的规则列表里就没有它。`parse_rules` 用 `re.split(r"\n## ", text)` 切规则，切点要求 `## ` 前面有一个换行，然后用 `[1:]` 把第一段当序言扔掉。课里的规则文件有 `# Agent Rules` 标题，第一段确实是序言；测试里的文件第一行就是规则标题，于是第一条规则连同标题一起进了第一段，被扔掉了（测验 Q9(a)）。这一关想练的是：报错的位置往往不是出 bug 的位置。

**依次修五处**：

1. 按行首切：`re.split(r"^## ", text, flags=re.MULTILINE)`。文件以规则开头时第一段是空串，扔掉它正好。
2. 描述是规则里所有描述行用空格连起来，在字段前面还是后面都一样。原来的代码每读到一行就覆盖一次，两行的描述只剩最后一行（测验 Q9(d)）。以反斜杠开头的行去掉一个反斜杠，这个处理原样保留。
3. `score` 先把每条规则的 check 都解析出来，有一个不是检查器的公开方法就报 `BrokenRule`，消息里带规则名和 check 名，然后才运行检查。课里的写法 `getattr(checker, rule.check, None)` 把它记成失败（测验 Q4），报告就会把一个写错的 check 名怪到 agent 头上。课里说：一个不再能解析的指针比缺一条规则更糟。
4. `normalize` 的字符类补上 `.`：`re.sub(r"[-_.]+", "-", name).lower()`，这才是 PEP 503。原来的 `[-_]+` 只认 `-` 和 `_`，`zope.interface`、`ruamel.yaml` 就和它们的另一种写法对不上；好的回合里没有带点的名字，所以要到 `mixed` 那条才挂。连续的分隔符合成一个 `-`，所以 `zope__interface` 和 `zope.interface` 是同一个包；分隔符不能删掉，`pythondateutil` 和 `python-dateutil` 是两个包。规范化只用在比较上，`unapproved_dependencies` 报的是 agent 写的原样名字。
5. `TurnTrace` 的摘要字段换成 `functools.cached_property`。原来的 `@property` 每读一次就扫一遍整个事件列表，2,000 条规则、5 万个事件要 1 到 2 秒（看 Python 版本）；缓存后每个字段只算一次，4 到 7 毫秒，限值是 0.1 秒。`TurnTrace` 是 frozen 的，事件存在 tuple 里，构造之后不会变，所以缓存是安全的。

**护栏**：常见的改坏写法各有一条断言接着。为了提速把摘要存在 `RuleChecker` 上，同一个检查器评第二个回合时拿到的是第一个回合的数据；`BrokenRule` 在循环走到那条规则时才抛，前面的检查已经跑过了；改写摘要时 `tests_exit_code` 要取最后一次验收运行，`confidence` 要取最低的那次决定。

## Part 2 规则文件

`write_rules` 按 `CATEGORIES` 的顺序给规则稳定排序（Python 的 `sorted` 是稳定的，同一类别里保持传入的顺序），每条规则写成固定的一块：

```python
def _block(rule: Rule) -> str:
    lines = [f"## {rule.slug}", f"- category: {rule.category}",
             f"- check: {rule.check}", f"- severity: {rule.severity}"]
    if rule.description:
        lines.append(_escape(rule.description))
    return "\n".join(lines) + "\n"
```

转义的规则直接照着解析器写：解析器会把以 `## ` 开头的行当成新规则、把整行匹配 `FIELD` 的行当成字段、把开头的反斜杠吃掉一个，所以只有这三种行前面加一个反斜杠。判断时直接用解析器的 `FIELD`，不另写一个"像字段"的正则：`-check:always_ok` 没有空格，也整行匹配 `FIELD`；`##__VA_ARGS__` 的 `##` 后面没有空格，不是标题。转义少了，`## approval/always-ok` 会变成一条没有 category 的新规则，`- check: always_ok` 会让 check 设了两次；转义多了，文件里会出现不必要的反斜杠，审查的人读着费劲。写不出来的规则提前报 `ValueError`：描述用 `text.splitlines() != [text]` 判断是不是一行，这样 `\u2028` 这种 `str.splitlines` 认的换行也会被拦下；首尾有空白的描述读回来会被 strip，也要拦；描述中间的空白原样保留，解析器不能把两个空格压成一个。`add_rule` 插入的块就是 `_block` 写出来的那一块，转义和 `write_rules` 一样。

`add_rule` 和 `remove_rule` 不重写文件，只在原文上插入或删除一段：

- 用和解析器同一个正则 `^## `（MULTILINE）找出每条规则标题的位置，和 `parse_rules` 的结果一一对应，所以比较 slug 时是整条比，`done/tests` 不会撞上 `done/tests-pass`。
- 新规则插在第一条"类别不早于它"的规则前面，块后面跟一个空行；找不到就加在文件末尾。这一条同时处理了"类别已有规则"（放在最前）和"类别还没有规则"（放在后面类别之前）。
- 删除时去掉从标题到下一条规则之前的所有内容；删最后一条时，再把它前面的空行去掉，文件仍然以一个换行结尾。

测试用 `change()` 比较前后两段文本，前后相同的行都剥掉，剩下的就是 diff 里的那一块：加规则时只能多出新的一块，删规则时只能少掉那一块。这就是课里说的"对 diff 友好"。

## Part 3 按事件判定

`TurnTrace` 的摘要没有顺序：`read_state_file` 只能说读过状态文件，说不出是不是在第一个 tool call 之前读的。`judge` 直接读事件。每条规则的 check 在 `Watch` 上是一个谓词，只回答"这条规则关心这个事件吗"；关心的事件要满足什么，由类别决定：

- startup：先算出开始干活的位置，也就是第一个没有任何 startup 规则关心的 tool call。每条 startup 规则在这之前要见到自己关心的事件，否则就在这个位置失败。几条 startup 规则一起划出启动阶段，所以按规则各算各的会出错。开工点只看 startup 规则：装依赖有 approval 规则在看，照样算开始干活。
- forbidden：第一个关心的事件。
- definition_of_done：最后一个关心的事件是证明。退出码不是 0 就在证明处失败；证明之后又有 write 或 install，证明就过期了，在第一次改动处失败；问题记录、决定、批准和读文件都不算改动。没有证明时失败，`at=None`。
- uncertainty：一个 `asked` 标记，见到 ask 置位，见到关心的事件（决定）清掉。低于阈值的决定见到的标记必须是置位的。不管那个决定有没有把握都要清，否则一个问题记录会盖住后面的决定。
- approval：按顺序收集 approve 事件的规范化名字，关心的事件（安装）必须已经在集合里。

`watchers()` 在判定之前把每条规则解析成谓词，类别不认识、check 解析不到都报 `BrokenRule`。Part 4 的运行时也用它。

## Part 4 运行时拦截

运行时对每个到达的事件做三件事：

1. 按已经放行的事件判断它违反了哪些规则。startup 的"开始干活"、uncertainty 的问题记录、approval 的批准集合、definition_of_done 的证明，全部只从 record 里来。
2. 还没出过行的违规规则各记一行 `not ok`，block 规则的行加 `refused`。只要违反了一条 block 规则，这个事件就被拒绝：不进 record，也不更新任何状态。
3. 放行的事件进 record，再更新状态：还没开始干活时，startup 规则见到自己的事件就记一行 `ok`。

这个事件记下的所有行按规则顺序输出，然后才去拉下一个事件：

```python
if not any(rules[k].severity == "block" for k in broken):
    self.record.append(event)
    working = working or starts
    ...                            # update startup, notes, proofs, approvals
for k, status, note in sorted(out):
    number += 1
    yield f"{status} {number} - {rules[k].slug}{note}\n"
```

被拒的事件不更新状态，带来两个效果：第 9 个事件（再写 release.sh）被拒，第 8 个事件的测试证明就不会过期；被拒的写操作不算开始干活，agent 读状态文件之前再写多少次都会被拒；被拒的验收运行也不算证明。过期的位置只记第一次改动，后面的改动不覆盖它。流结束时，还没出过行的规则按规则顺序补上，definition_of_done 在这时按最后的证明判定，最后输出计划行。编号是输出的先后，事件序号是收到的先后，被拒的也算，这样操作员能和 agent 的记录对上。

## Part 5 router 可达性

广度优先，从 router 出发，每个文件第一次被发现时的深度就是最少链接数。每条链接按这几步处理：

```python
path, _, anchor = target.partition("#")
resolved = posixpath.normpath(posixpath.join(posixpath.dirname(current), path)) if path else current
outside = path.startswith("/") or resolved == ".." or resolved.startswith("../")
if outside or not (root / resolved).is_file():
    broken.add((current, target))
    continue
if anchor and is_rule_file(resolved) and anchor not in rules_in(resolved):
    broken.add((current, target))
if resolved not in depth:
    depth[resolved] = depth[current] + 1
    queue.append(resolved)
```

- slug 里有 `/`，所以先在 `#` 处切开，再规范化路径。
- 路径断了，链接哪儿也到不了；只是锚点断了，agent 照样能打开那个文件，所以照常往下走。
- 只有锚点的链接指向本文件，锚点照样检查，不能跳过。

- 只读 `.md` 文件里的链接，每一行先去掉行内代码再找 `[text](target)`；带协议的链接跳过。
- 规则文件用 Part 1 的 `parse_rules` 读，得到每个文件里的 slug。规则的跳数就是它所在文件的深度；整个仓库里找到的规则文件，没被走到的，里面的规则都不可达。
- topic doc 是 `docs/` 下直接的、不是规则文件的 `.md`。router 直接链接的文件深度正好是 1，所以"router 没有链接它"就是深度不等于 1。
- router 自己的断链是 startup 违规。行数用 `splitlines()`，50 行及以上超预算。

这个仓库把课里的几种失效都放进去了：规则文件按类别拆开后，router 里指向索引的锚点失效了；approval 规则只能经 deploy 文档走到，3 跳太深；deploy 文档只在 router 里用一句话提到，没有链接；architecture 的链接拼错了；startup 规则文件里有一个本文件锚点，指向一条已经改名的规则；旧的规则文件留在仓库根下的 `legacy/` 里没删，只在 `docs/` 里找规则文件会漏掉它。

## 这套题证明了什么，没证明什么

通过了说明你能在这个规模的代码里调试一个规则解析器和检查器（静默丢规则、描述取错、断掉的 check、包名规范化、重复计算），把规则文件写成能原样读回、每次改动在 diff 里只占一块的 Markdown，按五个类别实现基于事件顺序的判定，写一个只拒绝 block 违规、边收事件边输出 TAP 的运行时，以及检查渐进披露的可达性。它不涉及真实的 agent 和模型：回合是写好的事件列表，题里的事件种类、"开始干活"的定义、证明过期的条件和锚点约定都是本题为了可检查而定的简化，不是哪个框架的规范。课里的规则过期（`expires_at`、60 天零违规）、`agent-rules.lock.json` 缓存、把检查接进 CI，以及 OpenAI Agents SDK guardrails、LangGraph interrupts 的真实接法，都需要另外动手做。
