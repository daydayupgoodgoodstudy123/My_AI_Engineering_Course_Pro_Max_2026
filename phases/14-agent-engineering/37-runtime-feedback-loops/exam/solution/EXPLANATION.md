# 参考答案讲解：FeedLog（14/37）

计时结束后再看。参考实现在同目录的 `feedlog/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修 runner

**现象**：解锁后的第一个错误是 `TypeError: Object of type bytes is not JSON serializable`，报在 `record.py` 的 `to_json` 里，调用它的是 `JsonlSink.append`。这两个函数都没有错。

**顺着往上找**：哪个字段是 bytes？是 `wait-for-db` 那条超时记录的 `stdout_tail`。正常分支把执行器给的 bytes 交给 `_decode` 和 `_capture`，超时分支却直接用了 `exc.stdout`。`subprocess.run` 超时时，`TimeoutExpired.stdout` 里放的是已经读到的原始字节，即使调用时写了 `text=True` 也是这样，课里的代码因此专门判断了一次类型。这一层想练的是：报错的位置往往不是出 bug 的位置。

**依次修五处**：

1. **超时的输出照常处理**。超时分支也走 `self._capture(_decode(...))`，stdout 和 stderr 都要。只解码不够，docstring 写的是 captured like any other output：37 行输出要截到 30 行，里面的 Bearer token 要换掉，stderr 里 dsn 那一行的 password 也要换掉，截断和脱敏的计数也要记下来。
2. **先脱敏，再截断**。`_capture` 原来先截断：bootstrap 打印的私钥有 52 行，截断去掉了 BEGIN 那一行，私钥规则要从 BEGIN 匹配到 END，于是一次也没命中，27 行密钥原样进了记录。`redact` 本身是对的，错在两步的顺序。先在完整文本上脱敏，整块私钥变成一行 `[REDACTED PRIVATE KEY]`，再截断，就不会有残片。课里的测验 Q11 讲的就是这件事，课程代码的 docstring 甚至写着 “Truncate first, then redact”。
3. **起不来的命令没有退出码**。找不到程序时原来记的是 127，这是 shell 的约定，这里没有 shell，argv 直接交给 exec，失败时 Python 抛的是 `FileNotFoundError`（测验 Q6）。记成 127，`loop_can_advance` 就会把它当成一条反馈，agent 的循环会接着往下走。改成 None，error 写明原因。
4. **所有启动失败都要留记录**。原来只捕获 `FileNotFoundError`，没有执行权限的脚本抛 `PermissionError`，直接冒出 runner，一条记录都不写，违背了课里 “If the runner errors before capturing exit, the record carries exit_code: null”（测验 Q12）。`except OSError` 一并盖住 `PermissionError`、`NotADirectoryError` 等。测试里还有一个没有 `#!` 行的 `migrate.sh`，exec 报的是普通的 `OSError`（Exec format error），只多捕获一个 `PermissionError` 盖不住它；`run_process` 的 docstring 写的就是起不来时抛 `OSError`。
5. **非 UTF-8 的字节不能毁掉记录**。`_decode` 原来严格解码，`cat` 一个 PNG 就抛 `UnicodeDecodeError`，退出码和记录一起丢了。用 `errors="replace"`，坏字节变成 U+FFFD。

**护栏**：

- `loop_can_advance` 判断的是有没有反馈，不是成功与否。退出码 1 也要返回 True，agent 要读 stderr、修代码、再重试（测验 Q3）。改成 `exit_code == 0` 会被第一条断言抓住。
- 为了堵泄漏把含 key、token 的行整行删掉，会删掉 `keyboard: us-intl`、`tokenizer=fast` 和 `--- deploy_key ---`；截断后再删“像 base64 的行”，还会留下 END 那一行；逐行脱敏永远匹配不上多行的私钥。测试精确比较整段文本，这几种都过不去。
- 让 `loop_can_advance` 把 127 也当成没有反馈，等于让一个真的以 127 退出的命令失去反馈，测试会接着查 `exit_code is None`。
- error 的格式是“异常类名: 消息”，只写 `str(exc)` 或只写类名都不够。超时的 error 用 timeout_s 拼出来，不用 `str(exc)`：`TimeoutExpired` 的字符串里会把整条 argv 再抄一遍，argv 里如果有秘密，就又泄漏了一次。
- 每条命令恰好一条记录，超时和起不来的命令也算；cwd 和 timeout 原样交给执行器；重试记下 parent。最后用真实的 `python -c` 跑一次默认执行器。

## Part 2 轮转的 JSONL 日志

参考实现每次追加前从磁盘取当前文件的大小：

```python
line = (record.to_json() + "\n").encode("utf-8")
size = self.path.stat().st_size if self.path.exists() else 0
if size and size + len(line) > self.max_bytes:
    self._rotate()
with open(self.path, "ab") as fh:
    fh.write(line)
```

- **写入前判断，按字节算**。课里的 `maybe_rotate` 在文件已经到上限之后才轮转，所以文件总会多出一条记录（测验 Q8）。这里判断的是“写进去以后会不会超”，`size` 和 `len(line)` 都是字节数，`line` 里包括结尾的换行。测试的记录里填了 📦，一个字符 4 个字节，按字符算会在一个文件里塞进四条；判断时漏掉换行，1400 字节的文件会再收下一条 401 字节的记录，变成 1801。
- **正好填满是可以的**。比较用 `>`，那条 400 字节的记录让文件正好到 1800。
- **大小从文件取**。中途重新打开日志，如果大小记在内存里、从 0 开始，第一个文件就会超。
- **大记录单独一个文件**。当前文件有内容、写不下时先轮转；`size` 为 0 时不轮转，所以比 max_bytes 还大的记录直接写进空文件，新日志的第一条也一样。下一条记录来时它被整条轮转出去。记录从不拆开。
- **轮转从大到小改名**。先删 `.keep`，再 `.11` 到 `.12`、……、`.1` 到 `.2`，最后当前文件变 `.1`。从小到大改名会一路覆盖。
- **按数字读**。`load_all` 用 `range(self.keep, 0, -1)` 拼出文件名，不用 glob 加 `sorted`：按字符串排序时 `.10` 到 `.12` 会排在 `.1` 和 `.2` 中间，合并出来的记录顺序就错了。用 glob 还会把目录里的 `feedback.jsonl.bak` 当成日志的一部分。
- **两种读法**。`current()` 只读当前文件，agent 每一轮读它，成本有上界；`load_all()` 读全部，从旧到新，给 CI 和 reviewer，重试链也能沿着它跨文件找回去。

记录用 `record.to_json()` 写，`ensure_ascii=False`，非 ASCII 原样存成 UTF-8，读回来用 `from_json`，和写进去时完全一样。读文件时按 \n 切行。测试的数据里没有 U+2028 这类字符，但如果有，`str.splitlines()` 会把一条记录切成两半。

## Part 3 确定性截断

```python
closed = text.endswith("\n")
body = text[:-1] if closed else text
lines = body.split("\n") if text else []
if len(lines) <= head + tail:
    return text, 0
cut = len(lines) - head - tail
kept = lines[:head] + [f"...truncated {cut} lines..."] + lines[len(lines) - tail:]
return "\n".join(kept) + ("\n" if closed else ""), cut
```

- **只按 \n 分行**。`str.splitlines()` 还会在 \r、\x0b、\x0c、\x1c 到 \x1e、\x85、U+2028、U+2029 处断行，进度条的 \r 和日志里的控制字符都会让行数对不上，截断结果也就不再是原文的头尾。\r\n 的行留着它的 \r，拼回去和原文逐字节一致。
- **结尾的 \n 只结束最后一行**。先去掉恰好一个结尾的 \n 再切，最后再按原文补回去。`rstrip("\n")` 会把结尾的空行一起吃掉。
- **tail=0**。`lines[-tail:]` 在 tail 为 0 时是整个列表，所以写成 `lines[len(lines) - tail:]`。
- **不重叠才截**。行数不超过 head + tail 时原样返回，没有标记。
- **负数报错**。不检查的话 `lines[:-1]` 会悄悄给出一个错的结果。
- **线性时间**。“从前面一行一行地丢”每次都复制剩下的整个字符串，6 万行要 1.2 秒左右；对列表反复 `pop(0)` 也是平方级，约 0.25 秒；`split` 加两次切片 2 到 3 毫秒。课里说 A 50 MB log destroys the loop，截断本身不能也变成瓶颈。

最后一段把 Part 1 的 runner 和真正的截断接在一起：provision 脚本先打印私钥，BEGIN 落在头 5 行里，END 落在被截掉的中间。先脱敏时整块私钥只剩一行，记录里头 5 行、标记、尾 30 行，截掉 9 行；先截断的话，头部会留下 BEGIN 和三行密钥。

## Part 4 实时跟随

参考实现给两个管道各挂一个读任务，用 `asyncio.wait(..., return_when=FIRST_COMPLETED)` 等先到的那个，超时时间每次按剩余时间算：

```python
done, _ = await asyncio.wait(reading.values(), timeout=max(0.0, deadline - loop.time()),
                             return_when=asyncio.FIRST_COMPLETED)
if not done:
    timed_out = True
    break
```

- **同时读两个管道**。假管道一次只装一次写入，进程要等它被读走才继续写，和装满的系统管道一样。只读 stdout、或者先把 stdout 读到底，进程就卡在写 stderr 上，双方一直等到截止时间。subprocess 的文档专门警告过这种死锁。`read()` 不带大小会一直读到 EOF，这是 `StreamReader` 的语义，也就没有“边读边发”了。
- **每个管道自己拼行**。`_Kept.feed` 把上次剩下的半行接上新 chunk，按 b"\n" 切开，最后一段留着等下一块。切的是字节，UTF-8 的多字节字符里不会出现 0x0A，所以不会切坏字符。
- **进度原样转发**。每个 chunk 补全的行合成一次 yield，前面加 `[stdout] ` 或 `[stderr] `，字节不解码、不去 \r。
- **内存有界**。每个管道只留前 head 行（列表）、后 tail 行（`deque(maxlen=tail)`）和正在拼的那一行。tracemalloc 量到的峰值约 60 KB，把所有行都留着、最后再切尾巴，峰值约 5 MB。
- **截止时间管整个运行**。截止时间在 follow 一开始就定下，一直没有输出的命令也按时 kill。等进程退出也用剩余时间 `wait_for`：守护进程关掉了管道却没退出时，照样按时 kill；这时重新给满 timeout_s，整个运行就会超过 timeout_s。只在 chunk 到达时检查截止时间，会多等一个 chunk；每次读都给满 timeout_s，持续有输出时永远不会超时。
- **到点就停**。kill，取消还挂着的读任务，不再读；正在写的那一行照样作为最后一行发出；exit_code 记 None，不记被 kill 后的 -9。
- **最后是记录**。单独一次 yield，`[record] ` 加一行 JSON。tail 的排版和 truncate_lines 一样，解码时坏字节换成 U+FFFD。

这里什么都没有脱敏，docstring 说明了原因：这是 agent 的实时视图，不写到任何地方。要把它写进反馈日志，就得在每一行进入头尾之前脱敏，否则又成了先截后脱。

## Part 5 重试链

参考实现先记下每条记录在 records 里的位置，再找出所有被重试过的尝试。没有被任何记录重试过的尝试是一条链的终点，从它沿 parent 往回走到第一个尝试：

```python
for record in records:
    if record.command_id in retried:
        continue
    path = [record]
    while path[-1].parent_command_id in position:
        path.append(records[position[path[-1].parent_command_id]])
    path.reverse()
```

- **分叉**。d2 被 d3、d4 各重试一次，就有两个叶子、两条链，共用 d1、d2。从根往下走、用 `child[parent]` 只记一个孩子的写法，不管留下 d3 还是 d4，都会丢掉一条。为了不重复走共用的 d1、d2，让所有链共用一个“走过”集合，d4 那条链会在 d2 停下，只剩它自己。从叶子往上走时每条链各走各的，没有这两个问题。
- **孤儿链**。父记录不在 records 里（被轮转掉了）时停下，`orphaned_from` 就是第一个尝试的 parent，也就是那个已经不在的 id；真正的根这里是 None。直接 `records[position[parent]]` 会 KeyError；当成普通的根，就看不出这条链前面还有被轮转掉的尝试。f1 和 g1 都指向 gone-3，是两条孤儿链：它们原本是 gone-3 上的分叉，共用的那一段已经轮转掉了。
- **last_failure**。这条链上最近一次退出码不为 0 的尝试。None 不算：命令没跑完，没有退出码可看（e 链里是 e1）；-9 算：被信号杀掉也是一种退出（d3）。只看这条链自己的尝试，在整棵重试树上找的话，d4 那条链会拿到另一条分叉上的 d3。链最后成功了也照样要填：a 链最后是 a3 的 0，last_failure 是 a2，这正是复盘要看到的失败历史。
- **用循环，不用递归**。1500 次的轮询链会超过 Python 默认 1000 层的递归上限。往上找父记录、从第一个尝试往下 DFS、带缓存的递归都一样会 RecursionError。课里的 `retry_chain` 也是一个 while 循环。
- **坏输入报错**。id 重复时位置表会被覆盖；重试一个写在它后面的记录（包括环和自己指向自己），在正常的日志里不可能出现。两种都报 ValueError。按位置比较时环自然会被拦下，只查环则会放过不成环的那种（测试里的 w2 和 w1）。
- **先后看写入位置**。docstring 写明了：链的顺序和“重试了后面才写入的记录”，都看在 records 里的位置，不看 started_at。按 records 的顺序遍历叶子，输出自然就按链尾的写入位置排好了。测试顺带检查这一点：a3 的时钟回拨到了 99.0，按 started_at 排序或判断先后都会出错。

## 这套题证明了什么，没证明什么

通过了说明你能在 feedback runner 这样的代码里顺着 traceback 找到根因，知道超时和启动失败都要留下没有退出码的记录、脱敏要在截断之前，能把记录精确地写进按字节轮转的 JSONL 并按正确的顺序读回，能写出确定性、线性时间的头尾截断，能用 asyncio 同时读两个管道、在有界内存里流式转发并守住截止时间，也能把重试记录组成带分叉和孤儿的链。

它没有涉及真实 agent 框架里的 shell 工具，也没有用到真实的 LLM，所有命令输出都是测试写好的。argv、agent_note 里的秘密，多个进程同时追加和文件锁，崩溃留下的半行，单行超长输出的字符上限，流式输出里的脱敏（第 13 章 26 课），feedback 和 telemetry 的分离（本章 23、24 课），以及 verification gate 怎样读这些记录（本章 38 课），都只在追问里出现，需要另外动手。
