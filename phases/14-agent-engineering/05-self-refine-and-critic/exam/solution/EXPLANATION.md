# 参考答案讲解：Critic（14/05）

计时结束后再看。参考实现在同目录的 `critic/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修精修循环

**现象**：解锁后的第一个失败出现在 `run_loop` 的结果上：CRITIC 在第 2 轮把含有 "The sun orbits the Earth." 的稿子判成了 `verifier: ok`，循环提前结束。判断是 `verify_external` 给出的，`run_loop` 只是照着结果停了下来。

**顺着往上找**：`verify_external` 的 for 循环遍历了 `wrong_facts`，循环体却只用了写死的两条检查（paris 和 germany、everest 和 europe 同时出现），算出来的 `key` 也没用上。这就是课里 `code/main.py` 的那段代码，测验 Q7 问的也是它：参考数据里的第三条从来没被查过。这一关想练的是：报错的地方往往不是出错的地方。

**依次修四处**：

1. 事实检查：每条 bullet 用 `normalize_claim` 规范化（去掉 "- "、转小写、去掉句末标点），和参考数据比较，按 bullet 的顺序报第一条错误事实。
2. 长度：只算 "- " 后面的正文，并且严格小于 60。原来的 `len(line) > 60` 两处都错：算进了前缀，又放过了恰好 60 个字的正文。也不要借 `normalize_claim` 量长度：它是给事实比对用的，会去掉句末的句号，而测试里那条 60 个字的正文最后一个字就是句号。
3. 停止规则：照课里那句话写成 `verifier_passes or model_says_fine and iteration >= 2 or iteration >= max_iters`。Python 里 `and` 比 `or` 先结合，这正是课里的意思：验证器通过就停；模型自己说没问题，要等到第 2 轮以后才算；到了上限一定停。停下的那一轮不再调用 refine，原代码最后一轮失败后还会白白 refine 一次。
4. 性能：参考数据先转成集合，每条 bullet 只规范化一次，再到集合里查。原来的写法对每条参考事实都把整段输出 `lower()` 一遍再找子串，是 O(事实数 × 输出长度)，2 万条事实、2000 条 bullet 要 0.5 秒以上；改完约 1 毫秒。

**护栏**：常见的"更鲁棒"写法是比较词的集合，不管词序。这样 "The earth orbits the sun" 和 "the sun orbits the earth" 的词完全一样，一条正确的说法就被当成了错误事实。参考数据里存的是整句的说法，比较也要整句比。

还有两点不是预埋的缺陷，但常见改法会碰到：先遍历参考事实、再看它在不在 bullet 里，速度够快，可报出来的是参考表里靠前的那条，而不是稿子里的第一条错误；把事实和长度放进同一个逐条 bullet 的循环，会先报出前面某条 bullet 的长度问题，而 docstring 要求先报事实。

## Part 2 修订差分链

参考实现每一轮写一行 JSON，追加到同一个文件：

```text
{"round": 0, "text": "<第 0 轮全文>", "sha256": "...", "critique": "..."}
{"round": 1, "ops": [[i1, i2, ["新行\n", ...]], ...], "sha256": "...", "critique": "..."}
```

- **差分**：用 `difflib.SequenceMatcher(None, a, b, autojunk=False)` 比较上一轮和这一轮的行，只保留不是 equal 的块，记成"把旧行 i1..i2 换成这些新行"。应用时从后往前改，前面块的长度变化就不会影响后面块的下标。
- **按行切分**：`splitlines(keepends=True)` 切、`"".join` 拼，任何字符串都能原样还原：末尾有没有换行、CRLF、单独的 `\r`、U+2028、空字符串都一样。不带 keepends 再用 `"\n".join`，这些全都会变。
- **摘要**：每条记录存 `sha256(json.dumps([output, critique]))`。读某一轮时从第 0 轮开始依次重建，每一步都和摘要核对，不一致就抛 `CorruptChain`。这样坏掉的那一条以及之后依赖它的轮次都会报错，之前的轮次照样能读。critique 也在摘要里，只改坏一条 critique 同样会报错。没有摘要的话，文件里改一个字母，读出来的就是另一段文本，而且没人知道。
- **可读、只存变化**：JSON 默认 `ensure_ascii=True`，换行、回车、U+2028 都会转义，一条记录一定只占一行；读的时候按 `"\n"` 切。改用 `ensure_ascii=False` 时，U+2028 会原样写进文件，这时再用 `str.splitlines()` 切记录就会把一条 JSON 切断。
- **落盘**：每次 append 打开文件、写一行、关闭，返回时数据已经在文件里，另一个实例马上能读到。append 之前先重建上一轮，差分总是对着文件里真正的最后一轮算。
- **逐行解析**：读的时候每一行单独解析。哪一行不是合法的 JSON（比如写到一半进程退出），就当作坏记录：之前的轮次照样能读，读它和它之后的轮次报 `CorruptChain`；append 重建不出上一轮，也会报错，不会接在半行后面。

## Part 3 工具化核验

`verify_claims` 是 CRITIC 的 verify 步骤：

1. 每条 bullet 是一条 claim，`claim_kind` 决定它是算式还是事实。
2. 按种类分组，每个工具只调用一次，带上它的全部 claim（按 bullet 顺序）。没有 claim 的工具不调用；`tools` 里没有对应工具的 claim 直接记成 unverified，证据是 `no math tool` 这样的说明。
3. 工具抛 `ToolUnavailable` 时，它的 claim 记 unverified，证据是异常消息。工具回答 unknown 也记 unverified。
4. 每条结果按 bullet 的位置放回原处，findings 始终是 bullet 顺序。

关键是三种状态：supported、contradicted、unverified。只有全部 supported 才算通过。Part 1 的验证器只认识错误清单，查不到就当作对；这里要的是有依据的支持，所以查不到、工具挂了，都不能算通过。

`refine_until_verified` 是 evaluator-optimizer：evaluator 是上面的 `verify_claims`，optimizer 是模型的 refine。每轮核验完，按这个顺序判断：

- 通过：返回 passed。
- 没有矛盾，只剩 unverified：refine 修不了"没法核验"，直接升级给人，原因是 `unverified: bullets 2, 4`。
- 到了 max_rounds：升级，原因是 `budget: round 3 of 3`。课里建议精修 1 到 3 轮，之后转人工。
- 否则 refine。新输出如果和之前任何一轮相同，就不再核验，直接升级：`no progress: round 3 repeats round 1`。evaluator 是确定的，同样的输出只会得到同样的 critique，这是课里说的 Over-refinement。

既有矛盾又有 unverified 时仍然 refine，因为矛盾是 optimizer 能修的。refine 拿到的是 critique 的文字和到目前为止的全部历史，这是 Self-Refine 的要点：去掉历史，模型会重复犯过的错。

## Part 4 流式护栏

```python
try:
    async for token in tokens:
        buffer += token
        while "\n" in buffer:
            end = buffer.index("\n") + 1
            line, buffer = buffer[:end], buffer[end:]
            reason = _check(guardrail, line)  # 护栏看到的是去掉 "\r\n" 或 "\n" 的文本
            if reason is not None:
                yield _frame("tripwire", {"line": sent + 1, "reason": reason})
                return
            sent += 1
            yield _frame("delta", {"text": line})
    ...  # 结尾剩下的 buffer 非空时同样检查，通过就发；最后 yield done
finally:
    await tokens.aclose()
```

- 每行先检查再发，客户端永远看不到被拒的那一行。
- 一凑齐一行就检查、就发，测试数到第一个 delta 出来时只拉了 2 块。
- tripwire 之后直接 return，不再拉 token。`async for` 提前结束不会关闭被迭代的生成器，所以要在 finally 里 `aclose()`：tripwire、正常结束、客户端断开，三种情况上游都会被关掉。上游不关，模型就还在生成、还在花钱。
- 以 `"\n"` 为行尾，`"\r\n"` 整个是换行符。单独的 `"\r"` 留在行里，行中间的也一样；token 恰好切在 `"\r"` 和 `"\n"` 之间也没关系，因为只有看到 `"\n"` 才算一行结束。护栏看到的文本只去掉换行符本身，行尾的空格留着。
- 结尾不带换行的最后一行在流结束后检查；结尾带换行时剩下空串，不算一行。
- 每帧 `event: <name>\ndata: <json.dumps(...)>\n\n`。`json.dumps` 会把行里的回车换行转义，data 永远只占一行。
- 只有 `OutputGuardrailTripwireTriggered` 是 tripwire。护栏的其他异常往外抛：护栏有 bug 时，应该让人看到错误，而不是把它报成内容违规。

课里说 OpenAI Agents SDK 的 output guardrail 跑在 agent 的最终输出上。这里把同样的检查挪到每一行写完的时候，好处是停得早、错误的内容不会发出去；要看全文才能判断的检查，仍然只能在最后做。

## Part 5 嵌套要点

先建树：逐行读，空行跳过；缩进由第一条缩进的行定下单位（tab 或两个空格），之后不一致就报错，同一行里混用也报错，空格数不是 2 的倍数也报错；`depth > len(stack)` 说明跳了级（第一行缩进也是这种情况）；用栈 `stack[d]` 记录深度 d 上最近的 bullet，回退几级就弹掉几层。每个错误都带原文的行号。

再检查：递归 `visit(node, path, depth)`，先算自己的问题（长度按本层的上限、错误事实、以冒号结尾却没有子项），然后在结果列表里先给自己占一个位置，再访问子节点。子节点里有失败的，就加一条 `sub-bullets failed: 2.1, 2.2`，只列直接子节点。最后把自己的那一行填回占好的位置。这样输出是先序（文档顺序），而每一行的内容要等子节点算完才知道，这是"先占位、后填写"的原因。

路径在兄弟节点之间从 1 编号，用点连起来。长度只算正文，不算缩进和 "- "，并且是严格小于：恰好 50 个字的 1.3 在第 2 层也算超长。自己的几个问题按 docstring 的顺序排：长度、错误事实、空子列表。

## 这套题证明了什么，没证明什么

通过了说明你能在这个规模的代码里调试 Self-Refine 和 CRITIC 循环，按课里的组合规则停下来；能设计一个可以逐字节还原、损坏可发现的差分存储；能把 claim 路由到不同的工具，正确处理"查不到"和"工具不可用"，并知道什么时候该把稿子交给人；能写一个逐行把关、提前停止、会关闭上游的流式护栏；能处理带缩进的嵌套结构。

它不涉及真实的 LLM：prompt 怎么写、evaluator 和 optimizer 的 prompt 怎样在结构上不同、用小模型做批评是否更好，都没有考到。也不涉及真实的搜索、代码解释器、OpenAI Agents SDK 或 Anthropic 的 API。课里的练习 2 和练习 3（有噪声的验证器、不同模型做批评）需要另外动手跑。
