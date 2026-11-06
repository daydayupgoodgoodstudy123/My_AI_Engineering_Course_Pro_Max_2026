# 参考答案讲解：VerifyGate（14/38）

计时结束后再看。参考实现在同目录的 `verifygate/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修验收检查和覆盖

**现象**：解锁后第一个失败是三条验收命令全报 `acceptance.missing`，而 feedback 里明明三条都跑过、都是 0。

**顺着往下找**：`acceptance_findings` 对每条命令调 `latest_run`，`latest_run` 比较的是两边的 `command_text`。打印一条记录的 `command_text`，得到的是 `"['pytest', '-x', 'tests/...']"`：列表走了 `str()`。第 37 课的 runner 按讲义记录 exact argv，合同里却是一行 shell 字符串，两节课的产物在这里接不上（测验 Q9）。报错的位置在两层调用之上，这一层想练的是顺着调用链往下找根因。

**依次修五处**：

1. **argv 用 `shlex.join`**。字符串那一侧已经是先 `shlex.split` 再 `shlex.join`，所以多余的空格、单双引号的不同写法都会归一。用空格拼接不行：合同里 `pytest -k "card and not slow"` 的引号对不上；两边都用空格拼接，又会把 `-k card and not slow` 这样拆开的另一个命令当成同一个。
2. **最新一次运行说了算**。`latest_run` 找到第一条匹配就返回了，先失败、重试后成功的命令还报 `acceptance.failed`。课里的原始代码更糟：每一条失败记录都 block，正常的“失败、修复、重跑”永远过不了，逼着 agent 去删记录（测验 Q6、Q10）。反过来，先过后挂的也必须 block。
3. **`ts` 也要签进去**。`make_override` 先对五个字段签名，再把 `ts` 加进条目；`verify_signature` 按除签名以外的全部字段验证，于是刚签的覆盖验不过，被 `apply_overrides` 当成伪造的丢掉。改法是先把 `ts` 放进条目再签名。反过来让 `verify_signature` 也跳过 `ts`，两边是一致了，可时间戳就能随便改，测试里改过 ts 的条目会抓住这种写法。
4. **覆盖绑定 HEAD**。`apply_overrides` 只比较了 task_id 和签名。课里说每条覆盖都记下当时的 HEAD commit：代码变了，人签字时看的就不是这份代码了，旧覆盖要失效。
5. **日志只规范化一次**。每条验收命令都把整份日志 `shlex.join` 一遍，400 条命令、8400 条记录约 2 秒。参考实现先用 `latest_runs` 建一个“规范化文本 → 最新一次记录”的字典，后面的记录自然覆盖前面的，再逐条查表，约 8 毫秒。倒序扫描、找到就返回不够：这份日志里验收命令都在前面跑，倒着找照样要走完几千条。先把记录规范化成列表、再逐条命令扫描列表，比较次数还是命令数乘记录数，几十毫秒，离 0.1 秒的限值不远。

**护栏**：一条覆盖只清掉它自己那个 code，别的 block 照旧；`apply_overrides` 返回新列表，不改传进来的；别的任务的、改过字段的、别的密钥签的、没签名的条目一律不算；null exit 不能覆盖，没有退出码就没有结果可以签字，出路是重跑；warn 本来就不挡路，也不能覆盖；同一个 code 有两条有效覆盖时，报告里写最后一条的签名人和理由。“最后一条”只在算数的条目里取：所有任务共用一份日志，别的任务对同一个 code 的覆盖排在后面，也不能把这个任务的挤掉，所以要先验，再按 code 记下。

## Part 2 签名的覆盖日志

`OverrideLog` 只做两件事：

- `append` 先校验：字段正好是 `FIELDS` 加 `signature`，签名能用日志的密钥验过。校验通过才写，写的是 `json.dumps(entry)` 加一个换行。文件用 `"a+b"` 打开，写之前数一下文件里已有的换行，加一就是新条目的行号。行号按文件算，不按实例算，两个实例交替写也对。
- `entries` 读字节、按 `\n` 切开、丢掉最后的空串，逐行解析，再用和 append 同一个校验检查字段和签名，第一处坏行抛 `LogTampered(行号, 原因)`。只验签名不够：别的工具把 `ts` 改名成 `timestamp` 再签，签名验得过，字段却不对。

几个设计点：

- **签的是内容，不是行**。签名覆盖六个字段的规范 JSON（`sort_keys`、紧凑分隔符、默认的 ASCII 转义），和行怎么写无关。另一个工具把键倒过来写、分隔符带空格、德文原样写成 UTF-8，照样能验过。所以读的时候先解析，再交给 `signing.verify_signature`。
- **往返要逐字节一致的是签名输入**。ts 有 float（`1767225600.4815162`）也有 int（覆盖工具记整秒），reason 里有非 ASCII、引号、反斜杠和制表符。Python 的 json 原样还原它们，读回来的规范 JSON 和签名时一样。任何“顺手整理”都会让签名失效：把 int 的 ts 写成 float，`1767225660` 就变成了 `1767225660.0`。
- **重复字段是篡改**。`{"finding_code": "coverage.missing", ..., "finding_code": "rule.failed"}` 在 Python 里取最后一个值，签名验得过；但别的 JSON 读取方可能取第一个，同一行就被读成了两条不同的覆盖。参考实现用 `object_pairs_hook` 发现重复就拒绝。
- **坏行不能跳过**。这是审计日志，一行读不出来本身就是需要人看的问题：截断的行、空行、`null`、乱码签名都报出行号。`JSONDecodeError` 不能漏出去；签名里有非 ASCII 字符时 `hmac.compare_digest` 会抛 TypeError，`verify_signature` 先检查类型和 ASCII，直接返回 False。
- **只追加**。已经写下的字节永远不动。整份重写哪怕内容一样，也会把别的工具写的那一行重新序列化成另一个样子。

## Part 3 结论和唯一的报告

`verify` 按来源顺序收集 finding：验收（或 `gate.no_acceptance`、缺失的 feedback）、scope、规则、覆盖率。缺失的产物各自换成一条 `gate.missing_artifact`，占在它那个来源的位置上。然后 strict 把 warn 升成 block，再应用覆盖，最后没有 block 就算通过。

- **缺失和为空是两种状态**。`None` 表示文件不存在，要 block；`[]` 和 `{}` 表示文件在、里面没东西。课里的代码把两者都读成空，什么都没证明的任务也能通过（测验 Q7、Q11）。没有一条验收命令同样是 block，skill 的拒绝规则说得很直接：a gate that proves nothing is theater。
- **规则带着自己的 severity**。第 33 课在写规则时就标好 block、warn 或 info，闸门只照抄。拼写不对的（`"Warn"`、`"critical"`）和没写的都按 block：闸门不猜，猜错的方向必须是拦下。
- **先 strict，后覆盖**。strict 把 off-scope 这样的 warn 升成 block 之后，人还可以签字放行；顺序反过来，覆盖时它还是 warn 不能覆盖，升级后就成了谁也清不掉的 block。info 不受 strict 影响。
- **覆盖率边界**。`coverage_findings` 保留了课里的写法：比上次低一个百分点以上才 block，正好一个点是 warn。浮点里 0.85 − 0.84 是 0.010000000000000009，所以要用 `math.isclose(delta, 0.01, rel_tol=1e-9)` 把恰好一个点排除；和 0 比较时相对误差没有意义，要用 `abs_tol`。四舍五入到整点会放过 1.1 个点的下降，`int()` 截断会放过 0.8599→0.849。更稳的长期做法是用整数基点存覆盖率。
- **下限的单位**。`coverage_floor` 是比例，不在 (0, 1] 里就报错。传 80 进来会让每个任务都低于下限，这是代码讲解里点过的坑；传 0 会把下限检查悄悄关掉，也要拒绝；1.0 是“要求百分之百覆盖”，合法。
- **一个任务，一个路径**。`write_report` 写 `outputs/verification/<task_id>.json`，内容是 `json.dumps(to_dict(), indent=2, sort_keys=True)` 加换行，不带时间戳，同样的产物永远是同样的字节。先写临时文件再 `os.replace`，CI 不会读到半份报告。task id 必须是纯文件名，`../T-42` 直接拒绝；把它“清洗”成 `T-42` 会盖掉另一个任务的真报告。

## Part 4 Markdown 摘要流

`render_summary` 只读 `Verdict.to_dict()` 的结果，所以摘要和 JSON 报告不会说法不一。版式在 docstring 和测试的完整样例里：

- 标题行照报告里的 passed 写 PASSED 或 FAILED。只有 warn 和 info 的报告是 PASSED：课里说 warn 只给结论加批注，block 才挡住 `passed: true`。
- head 行在 strict 时加 `, strict`，读摘要的人要知道 warn 是不是被升成了 block。
- 每个有 finding 的严重级别一节，顺序固定为 block、warn、info、overridden，节内保持报告顺序，没有 finding 的级别不写。先看挡路的，再看批注，最后看人放行了什么。overridden 的表多 by 和 reason 两列，被覆盖的 block 要写明谁签的、为什么。
- 单元格按 docstring 写明的顺序转义：先把反斜杠写成 `\\`，再给 `` ` * _ | `` 前面加反斜杠。竖线会把表格切错，星号、下划线、反引号会变成格式；反斜杠不先转义，`deploy\prod.ps1` 里的 `\p` 读出来就不是原文了。参考实现逐个字符判断，没有先后的问题。

`stream_summaries` 是一个 async generator：

```python
last = render_summary(gate(list(feedback)))
yield last
async for record in records:
    feedback.append(record)
    text = render_summary(gate(list(feedback)))
    if text != last:
        yield BREAK + text
        last = text
```

- 第一份摘要在读第一条记录之前就发出去，这时验收命令都还没跑；流里一条记录都没有，发出的就只有这一份。把它挪进循环、等第一条记录到了再发，测试数得出来。
- 用摘要文本去重，文本变了就发：c1 之后结论还是 FAILED，但 lint 不再缺失，要发；只看 PASSED 和 FAILED 是否翻转、只看每节的个数，都会漏掉一份。重复的失败、无关的 `git status` 不产生输出。`last` 要跟着更新，否则每份都在和第一份比。
- 分隔符是空行、`---`、空行，只放在两份摘要之间，放在后一份的开头。通过的摘要最后一行是 `head ...` 这段文字，紧跟一行 `---` 会被 Markdown 读成 setext 标题，所以前面必须有空行。
- 只和上一份比：摘要回到以前发过的样子也要发，c8 重跑 lint 通过、回到 PASSED 就是这种情况，用集合记下发过的摘要会漏掉它，PR 评论最后停在 FAILED。
- 记录一到就重算，摘要一变就发，测试数过：第三份摘要出来时只读了两条记录。

## Part 5 堆叠提交

`verify_stack` 先检查输入：每个 sha 只出现一次，也不能和 base 同名；每个父提交要么是 base，要么在栈里。然后从 base 出发做深度优先遍历，子提交按给定顺序，每一步带着三样东西往上传：比较基准、父提交是否在等、到目前为止第一个没通过的提交。

- **比较基准**。提交的覆盖率报告换一份新的 dict，`previous` 改成它所在位置的基准：父提交的 current；父提交没有覆盖率报告时，用父提交自己的基准，一路到 base_coverage。CI 自己算的 previous 比的是任务运行时的 main，正是要纠正的东西。传进来的 artifacts 不改。
- **覆盖绑定 HEAD**。每个提交用自己的 artifacts 调 `verify`，覆盖按 task 和 HEAD 匹配，a1 上签的豁免到不了 d1。父提交靠覆盖通过，不代表子提交的同一个问题也被批准了。strict 和 coverage_floor 原样传给每一次 `verify`。
- **等待**。没有 artifacts、artifacts 的 head_commit 不是这个 sha（作者又推了一次，CI 还没重跑）、父提交在等，都是 waiting，没有 verdict。
- **blocked_by**。沿路记下第一个没通过的提交，它挡住上面所有的提交。e1 自己干净，但 d1 没过，e1 就不能合入。
- 遍历结束后还有没走到的提交，说明它们连不到 base（比如互为父提交的环），报 ValueError。

## 这套题证明了什么，没证明什么

通过了说明你能在一个确定性的验证闸门里调试命令匹配、重试和签名覆盖，能设计一份只追加、可审计的签名日志，能把四类产物、strict、fail closed、覆盖率的浮点边界和覆盖的先后顺序合成一个可复现的结论，并写到 CI 读取的唯一路径，能写出随运行记录增量更新的摘要流，也能在堆叠提交上选对比较基准、传播等待和阻塞。

它没有涉及真正的 CI 接线：GitHub Actions 的 status check、合并保护、pre-commit 和 pre-tool hook 组成的纵深防御都只停在追问里。覆盖率是给定的数字，没有真的去跑 coverage.py；diff 和 `scope.allowed_files` 的比对没有实现，第 36 课负责 scope 报告本身。HMAC 只能证明持有共享密钥，个人签名和审批服务没有考。课后练习 4 的 `time_since_last_human_touch` 豁免和练习 5 拿真实 diff 跑闸门，需要另外动手。LLM 打分属于第 39 课的 reviewer，不在闸门里。
