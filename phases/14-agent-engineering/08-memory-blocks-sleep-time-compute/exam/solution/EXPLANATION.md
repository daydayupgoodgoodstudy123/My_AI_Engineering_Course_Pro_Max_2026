# 参考答案讲解：MemBlocks（14/08）

计时结束后再看。参考实现在同目录的 `memblocks/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修块工具和 sleep pass

**现象**：解锁后第一个失败是 "a write that would pass the limit is refused"。`Block._commit` 是所有写入的必经之路，但它从不看 `limit`，所以 append 到 61/60 也会成功。这就是讲义说的 Block bloat。

**依次修四处**：

1. `_commit` 先检查新值的长度（含换行），超过 `limit` 就返回 `error:` 开头的 observation，直接返回，不 push history、不加版本。放在 `_commit` 里，append、replace、rewrite 一起受约束。
2. `replace` 拒绝空的 old。`"" in value` 永远为真，`str.replace("", "-")` 会在每个字符之间插入 `-`。这一处要等上限修好才看得到：在那之前测试先挂在上限上。
3. `summarize` 的记账：`used += len(line)` 没算行与行之间的 `\n`。sleep pass 把 86 字符的 task 块压成 52 字符，超过了一半（50）。这个错误在两层调用之外才报出来：测试接着让主 agent 写一行 49 字符的事实，`_commit` 算出 102/100 拒绝了它。顺着 observation 往回查：sleep pass 之后块有多长？summarize 承诺不超过 target_len，返回的却是 52。改成 `used += len(line) + 1` 就对了。
4. `Archival.get` 是线性扫描，`SleepTimeAgent.run` 每作废一条记录都要 `invalidate → get` 从头扫一遍。3.2 万条记录里作废 8000 条，本机约 1 秒。插入时顺手建一个 `rid → record` 的字典，同样的 pass 只要 2 到 3 毫秒。

**护栏**：

- 拒绝不是截断。把写入截到上限能让测试的第一句通过，但会悄悄丢掉事实，下一句 "a refused write changes nothing" 会抓住它；先 push history 再检查也一样。
- 恰好等于上限的写入要接受，上限按整个值算，含换行。
- 只拒绝空的 old。空的 new 是删除：`block_replace(", at home", "")` 要成功，这正是拒绝信息里建议模型做的“替换掉一行旧的”。
- summarize 保留的是“最新的若干整行”。`text[-target_len:]` 长度合格但会切断一行；放不下就 `continue` 去取更旧的短行，会把旧事实拼回来，违背“保新弃旧”。课里的 `_summarize` 从前往后取，正好保留了最旧的，测验 Q9 讲过这个问题。
- 作废的记录要留着，带原因。直接在 `run` 里改 `record.valid` 也能提速，但别忘了 `reason`。

## Part 2 块版本日志

每个块一个追加写的日志文件 `<root>/<label>.log`，每个版本一行 JSON：`{"version": n, "op": ..., "value": ...}`。存完整的值，`value_at` 就只是一次查找。

容易漏的几点：

- **一行一个版本**：值里有 `\n`、`\r\n`，自己拼分隔符的格式会把一个版本拆成几行。`json.dumps` 默认把控制字符和所有非 ASCII 字符都转义，写出来的每行只有 ASCII。
- **撕裂的尾行要从文件里截掉**：崩溃可能留下没有换行的半行。只在读的时候跳过是不够的，下一次追加会接在半行后面，那一整行以后都读不出来。参考实现在第一次读日志时找到最后一个 `b"\n"`，用 `truncate` 截到那里，下一个版本就从半行开始的位置写。截断位置要按字节算，按字符数算的话，emoji 会让位置偏到前一行里。先补一个换行把半行封起来也不行：半行留在日志中间，以后只能靠“跳过坏行”读下去，真正的损坏也会被一起跳过。测试在恢复后数一遍文件里的换行。
- **版本号要连续，跨重开也一样**：`record` 先读出已有的版本，下一个必须是最后一个加一。重开后的第一个调用就可能是 `record`，所以它自己要先读日志，不能只信这个实例已经读过的。op 只能是 append、replace、rewrite；label 只能是小写名字，要用 `fullmatch` 整串匹配：`../human` 不能变成路径，`re.match` 只管开头，`human/../persona` 会混过去。
- **restore**：history 是每次写之前的值，所以是 `["", v1, ..., v(n-1)]`，和 Part 1 的 `Block` 完全一致，测试直接用 dataclass 的 `==` 比较。
- **换行符不止 `\n`**：`str.splitlines()` 还会在 U+2028、U+0085 这些地方切。如果写的时候用了 `ensure_ascii=False`，这些字符原样进了文件，`splitlines()` 一切就是 JSONDecodeError。读的时候只按 `b"\n"` 切，或者保持 ASCII 转义，都没问题。

## Part 3 sleep-time 整理

课里的 `SleepTimeAgent.run` 要调用方把矛盾传进来，再用子串匹配作废。这一关让 sleep-time agent 自己找。

参考实现分三步：

1. 只取有效记录，按 `(at, 插入顺序)` 排好。`sorted` 是稳定排序，所以只按 `at` 排就够了。
2. 解析 fact：`key=value`，去掉末尾括号里的注释。每个 key 在时间顺序里的最后一条留下，前面的都作废，原因是 `superseded by <rid>`。
3. 自由文本按时间顺序过一遍：和之前留下的自由文本比较小写字母数字词的集合，Jaccard 严格大于 0.9 就作废，原因是 `duplicate of <第一条的 rid>`。

最后按插入顺序调用 `invalidate`，返回 `(rid, reason)` 列表。

测试里每条记录对应一个陷阱：

- `city=Lisbon (updated from Berlin)` 提到了 Berlin。子串匹配会把它当成旧事实作废，按 key 解析就不会。
- `city=Porto` 来自一段更早的对话，插入得最晚，但 at=200 比 Lisbon 的 300 早，不能赢。
- `pet=cat` 和 `pet=dog` 在同一秒，后写的赢。
- `city=Pyongyang` 是被投毒、已经作废的记录，它不参与整理（讲义的 Poisoned consolidation）。
- role 从 staff engineer 改成 manager 又改回来。先按全文去重的话，最新那条会被当成第一条的重复作废，最后的值就成了 manager。所以 fact 只按 key 处理，不参加去重。
- 两条只差大小写和标点（逗号、句号、连字符）的偏好是重复；10 个词和 11 个词（10/11）是重复，9 个词和 10 个词（正好 0.9）不是，多了 every friday 的 12 个词（10/12）也不是。重叠要除以两条合起来的词数：只除以旧记录的词数，every friday 那条算出 1.0；只除以新记录的词数，9 个词那条算出 1.0。

第二遍整理返回空：没有新的矛盾，已作废的记录也不再参与。

## Part 4 主 agent 和 sleep-time agent 并发

`Session` 里有一个队列和一个后台 worker：

```python
async def _work(self):
    while self._queue:
        label = self._queue[0]          # 整理完才出队，所以“正在整理”也算在队里
        while True:
            block = self.store.get(label)
            version, value = block.version, block.value
            result = await self.consolidate(label, value)
            if self.rewrite(label, result, version) or block.version == version:
                break                   # 提交了，或者没什么可提交的
        self._queue.popleft()
```

- **turn 不等**：`turn` 只做写入，把改过的块放进队列，没有 worker 就 `create_task` 起一个，然后立刻返回。测试的脚本模型会一直卡着，直到测试放行，所以 turn 里只要 `await` 了 sleep pass 就会超时。
- **compare-and-swap**：`rewrite` 只在块仍是读到的那个版本时才提交。asyncio 是单线程的，检查版本和写入之间没有 `await`，这一段就是原子的。模型读的是 v3，期间主 agent 写了 v4（`pet=cat`），重写被拒，worker 重新读、重新调用模型，在 v4 上提交 v5，`pet=cat` 保住了。这就是测验 Q12 里的 lost update。
- **不重复排队**：正在整理的块又被写了，不需要再排一次，重试会把新写入一起整理进去。重新排队会让昂贵的模型多调用一次。
- **正在整理的块还在队里**：参考实现整理完才出队，所以去重看得见正在整理的块，`idle()` 只要等 worker 结束。先出队再整理的话，`idle()` 不能只看队列空没空：测试里最后排队的是 task，它出队以后还在整理。
- **worker 跑完以后还要能再起来**：`_enqueue` 看到 worker 已经结束，就再起一个。测试在第一次 `idle()` 之后又写了 task 和 persona，再 `idle()` 一次，两个块都要整理完，而且按写入的先后（先 task 后 persona），按 label 排序会反过来。
- **没东西可提交就停**：模型返回原值（persona）或者超过上限时直接结束这个块。只看 `rewrite` 的返回值来决定重试，会在 persona 上无限循环。
- **trace**：每次提交一段 unified diff。参考实现用 `difflib.unified_diff(before.split("\n"), after.split("\n"), fromfile=f"{label}@v{old}", tofile=f"{label}@v{new} ({writer})", lineterm="")`，每行后面加 `\n`。空值没有行，所以 persona 的第一段是 `@@ -0,0 +1 @@`。被拒的写入和重写都不进 trace，版本号因此是连续的。测试的 `replay` 把所有 diff 依次打到初始状态上，必须重建出每个块。

## Part 5 派生记录的传递失效

`Lineage` 记下每条派生记录的来源，以及每条记录被谁用过（反向边）。`derive` 先确认每个来源都在档案里，再插入新记录，所以报 KeyError 时档案里不会多出一条没有来源的记录。`invalidate(rid, reason)`：

1. 作废 rid。如果它已经作废，保留原来的原因（`Archival.invalidate` 本来就是这样）。
2. 用栈沿反向边找出所有能到达的记录。不用递归，因为滚动摘要的链可能有上千层。遇到已经作废的记录也要往下走：它可能是因为别的原因作废的，由它派生的记录还有效。
3. 按创建顺序处理。来源必须先存在，所以创建顺序天然是拓扑序。每条记录的链取它所有已到达来源里最短的那条链再接上自己，一样短时取先创建的来源。
4. 对还有效的记录调用 `invalidate(child, f"derived from {链上前一条}")`，成功的才放进结果。

为什么不能直接用遍历顺序：在测试的图里，宽度优先会把 brief 排在它的来源 voice 前面，深度优先的先序会把 weekly 排在它的来源 commute 前面。按这样的顺序重建，用到的还是旧的来源。按 `at` 排也不对，brief 的 at 是它覆盖的时间，比它的来源还早。

链也不能直接取宽度优先第一次找到它的那条路。第二层的平局（weekly）碰巧没区别，第三层就有了：budget 由 food 和 vet 派生，两条链一样长，宽度优先先经过 owner 找到 food，但 vet 先创建，链要走 vet。按 `at` 断平局也会选 food。

最后两段是整合检查：`pet=cat` 已经被 Part 3 的 `consolidate` 作废了，owner_copy 也被它当成 owner 的重复作废了。再调用 `lineage.invalidate(pet, ...)`，仍要找到 owner、food，以及经过 owner_copy 派生出来的 vet 和 budget，结果里的 reason 是档案里存的 `superseded by ...`。1500 层的滚动摘要必须完整返回，最后一条的链长 1501。

## 这套题证明了什么，没证明什么

通过了说明你能在这个规模的代码里顺着 observation 找到两层之外的根因，能写一个经得起崩溃和任意 Unicode 的追加日志，能把“按 key 取最新、按词去重、作废不删除”实现成确定的整理规则，能在 asyncio 里写出不阻塞主回合、用版本号做 compare-and-swap 的后台 worker，并把每次变更变成可重放的 diff，还能在来源图上给出正确的重建顺序和原因链。

它没有涉及真正的模型：摘要是按行截取，整理是确定的规则，矛盾只认 key=value。语义去重、自由文本的矛盾判断、Persona 和 Safety 块的审核门（讲义练习 4）、Letta API（`letta_v1_agent`，练习 5）和 recall 层都需要另外动手。
