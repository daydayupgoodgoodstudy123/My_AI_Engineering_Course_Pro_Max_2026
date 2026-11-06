# 参考答案讲解：TraceJudge（14/24）

计时结束后再看。参考实现在同目录的 `tracejudge/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修会话看板

**现象**：解锁后的第一个错误是 `scripted_llm_judge` 里的 `TypeError: '>' not supported between instances of 'str' and 'int'`，而 judge 本身没有 bug。

**顺着往上找**：judge 拿到的 `tokens` 是字符串 `"700"`。span 是 `load_spans` 从导出的 JSON 行里解析出来的，有的导出器把数字写成字符串，而 `load_spans` 的 docstring 写明加载后 `tokens` 一定是 int，代码却原样保留了。只在 judge 里加 `int(...)` 不够：`summarize_session` 里给 tokens 求和时还会报 `unsupported operand type(s) for +: 'int' and 'str'`。类型问题要在数据进来的地方修。在 judge 和求和两处都转一次，看板的数也对得上，但以后每个读 tokens 的地方都得记着转；测试在看板之后直接检查 `load_spans` 的输出。

**依次修五处**：

1. `load_spans`：`tokens` 转成 int。
2. `TraceCollector.ingest`：用 `(trace_id, span_id)` 的集合去重，重复的返回 False。导出器等不到确认就会重发，同一个 span 进来两次，错误数、tokens 和 span 数都会翻倍。
3. `trace_count` 数不同的 trace_id，不是 span 数。
4. 每条 trace 单独交给 judge，再对会话求均值。课里的代码把整个会话的 span 一起打分：sess-a 里一条好 trace（1.0）和一条坏 trace（0.4）混在一起，整体看“有错误、有工具、有最终回答、有超长”，得 0.5，逐条平均是 0.7。规则里的“有没有工具调用”“有没有最终回答”本来就是针对一次 run 的。
5. `summarize` 只调一次 `by_session()`。原来对每个会话都把全部 span 重新分组一遍，是 O(会话数 × span 数)，5000 个会话大约 2 秒。

**护栏**：
- sess-a 每条 trace 里都有两个 chat span。按 `(trace_id, name)` 去重会把第二个吃掉。
- sess-b 的导出器在每条 trace 里都把 span 编成 1、2、3。只按 `span_id` 去重会把 b2 整条丢掉。span id 只在一条 trace 内唯一。
- 用 `any(...)` 扫一遍已存的 span 来判断重复是 O(n²)，把 key 存进列表再用 `in` 也一样。测试让导出器把 8000 个 span 整批重发一遍，集合去重 2 毫秒左右，扫描 1.2 秒左右，列表 0.45 秒左右，限值 0.05 秒。用集合。

## Part 2 标注队列

参考实现两张表：`queue(seq, trace_id UNIQUE)` 和 `annotations(seq, trace_id, annotator, label, score REAL, note, created_ns INTEGER)`。两张表都用自增的 `seq` 记顺序。

- **纳秒时间戳**：1767225600123456789 有 19 位，超过了 double 能精确表示的 2⁵³。列声明成 REAL 时，SQLite 按列的类型亲和性把整数转成浮点，读回来末几位变了。INTEGER 列存 64 位整数，原样读回。
- **0.0 和 None**：0.0 是“完全错误”，None 是“没打分”。`score or None` 和 `score or 0.0` 都会把两者混起来。REAL 列配上 NULL 能区分它们，1/3 和 0.1 + 0.2 也能原样读回。
- **顺序**：标注按记录顺序（`ORDER BY seq`）返回。测试里 li 的时钟比 maya 慢，按 `created_ns` 排会把顺序弄反。
- **重复入队**：`INSERT OR IGNORE` 保住原来的位置。`INSERT OR REPLACE` 遇到唯一键冲突时先删旧行再插新行，新行拿到新的 `seq`，trace 就排到了队尾。
- **pending**：`queue` 里没有任何标注的 trace，按 `seq` 排。按 trace_id 排序时 tr-10 会在 tr-9 前面。
- **校验在写之前**：分数用 `0.0 <= score <= 1.0` 检查，NaN 和任何数比较都是 False，所以会被拒绝；没入队的 trace 报 KeyError。两种情况都不能写进任何东西。

## Part 3 按 prompt 版本二分

先按版本统计 (PASS 数, 总数)，只有 PASS 算通过。然后：

```python
for version in sorted(counts, key=version_key):        # (1, 10) > (1, 9)
    if version_key(version) <= good_key:
        continue                                        # 早于 known_good 的不看
    passed, n = counts[version]
    since_good.append(version)
    if n < min_traces:
        continue                                        # 不下结论
    if 100 * (base_pass * n - passed * base_n) > max_drop * base_n * n:
        return Bisection(last_good, version, since_good)
    last_good, since_good = version, []
```

- **版本号**：拆成整数元组比较。字符串排序时 `"v1.10" < "v1.9"`。
- **基线固定为 known_good**：v4.0 到 v4.3 是 90%、85%、82.5%、77.5%，相邻两版最多差 5 个点，逐版比较永远不报；和基线比，v4.3 掉了 12.5 个点。
- **精确比较**：通过率是分数，阈值是整数个百分点，交叉相乘后全是整数，“正好掉 10 个点”就是相等。浮点里 0.68 − 0.58 = 0.10000000000000009，`(b - c) * 100 > 10`、`b - c > 0.1`、`b * 100 - c * 100 > 10` 都会把它算成回归。先算百分数 `100 * passed / n` 再相减，在这一组上碰巧是 68.0 − 58.0，正好 10；换成 9/14 对 19/35（64.29% 对 54.29%）就是 10.000000000000007，所以测试两组都有。
- **也不能取整**：10/11 对 21/26 掉了 10.14 个点，是回归。`int(...)`、`round(...)` 或者 `100 * passed // n` 这种整数百分数都会把它算成 10。
- **不下结论的版本**：少于 min_traces 条的版本跳过，但留在 `since_good` 里。v1.9 只有 5 条，通过率 60%，不能当 culprit；它后面的 v1.10 和 v1.11 正常，所以它也不在 suspects 里。v1.12 只有 2 条，夹在 last_good（v1.11）和 culprit（v1.13）之间，改坏的可能就是它，所以要列进 suspects。
- **边界**：v1.11 正好 10 条（有结论），通过率正好低 10 个点（不算回归）。

## Part 4 批量摄取和 SSE

参考实现给每个 span 记一张“字段 → 戳”的表，戳是 `(ts, 到达序号)`：create 给 status 和每个 attribute 打上自己的戳，update 只在戳更大时覆盖对应字段。这样：

- 第 2 批先到 ts=30 的 tokens 2600，再到 ts=20 的 900，后者的戳小，不生效。
- 重发的 create 直接跳过，不会把 tokens 改回 100。
- create 之前到的 update 放进等待列表，记下到达的批号。create 到了就把等它的 update 按原来的戳应用一遍，戳保证结果和到达顺序无关。第 4 批 t4 等着的 update 是 ts=49，create 是 ts=50，create 给 tokens 打的戳更大，所以 tokens 仍是 10。
- 第 4 批 t1 的 chat 先到 ts=35 的 status 和 error.reason，再到 ts=32 的 tokens。tokens 上一次的戳是 30，32 更大，照样生效，s-a 的 tokens 是 2700。整个 span 只记一个戳的话，32 比 35 小，这条 tokens 就丢了。update 带来的 attributes 合并进旧的，整个替换的话 ts=35 那条会把 tokens 冲掉。

每批结束时：

1. 对这一批碰到的会话按 id 排序，重新算 `summarize_session`，和上次发出的摘要不同才发 `session` 事件。第 2 批把 t3 的 status 设成它原来的值，s-b 不发。
2. 等待列表里 `批号 - 到达批号 >= orphan_ttl` 的 update 丢掉，发一个 `dropped` 事件。t9 在第 1 批到达，第 3 批结束时丢。
3. 这些都在 `async for` 的循环体里 `yield`，所以下一批还没被拉取，测试的探针只看到 1 批。

流结束后，等待列表里剩下的 update（t8）再报一次 `dropped`。id 是整条流共用的计数器。

`sse()` 已经给出：`id:`、`event:`、`data:` 三行，再加一个空行；`json.dumps` 默认不换行，所以 data 只有一行。

## Part 5 trace 结构聚类

`signature` 只看一条 trace：

1. 按 `span_id` 建索引。父 span 在索引里的，挂到父 span 下面；没有 `parent_id` 或父 span 不在本 trace 里的，是根。
2. 从每个根往下递归，子节点按 `(start_ns, span_id)` 排序，写成 `名字(子,子,...)`，名字里的 `\`、`(`、`)`、`,` 前面加反斜杠。r1 里工具调用的 id 最小、开始得却比第一个 chat 晚，只按 id 排会把它排到最前。用 `str.replace` 转义时要先换反斜杠，否则前面加进去的反斜杠会被再转义一次。
3. 多个根同样排序后用逗号连起来。r5 的孤儿根在输入里排第一，但开始得比 invoke_agent 晚。
4. 递归时记下到达过的 span。成环的 span（包括指向自己的）的父 span 永远在环里，它们不会被当成根，也不会从任何根到达。最后还有没到达的，就报 ValueError。

转义是为了让签名是单射：不转义时，名为 `chat(retry)` 的叶子和 chat 下面挂一个 retry 的树都写成 `invoke_agent(chat(retry))`，r6 会混进 r7、r8 那一簇。

`cluster_traces` 先按 trace_id 分组（span id 只在 trace 内唯一，所以必须先分组再建树），算签名，再按签名分组，簇里的 trace_ids 保持第一次出现的顺序（r8 在 r7 前面）。占比的分母是 trace 总数，严格小于 min_share 才算异常，2/8 正好等于 0.25，不算。分母用簇数的话，第一组碰巧标得一样，第二组（r3、r4、r1、r2，min_share 0.3）里 web_fetch 的 1/4 会变成 1/2。排序是簇大小降序，再按签名字符串。

## 这套题证明了什么，没证明什么

通过了说明你能在一个可观测性后端里顺着 traceback 找到上游的类型问题，能处理导出器重发和按 trace 打分这类口径问题，能把人工标注精确地存进 SQLite，能把一次质量回归二分到具体的 prompt 版本，能写一个按时间戳合并乱序事件、按批推送 SSE 的异步生成器，也能把 span 树规范成签名做聚类和异常标记。

它没有涉及真实的 Langfuse、Phoenix、Opik，也没有 OpenInference 自动埋点、OTel 导出和真实的 LLM 评审。评审是课里那套脚本化规则，没有外部工具做事实核验。课里的练习 1（把一周的 trace 导到 Langfuse）、练习 4（接 Opik 的 PII 护栏）和练习 5（在自己的语料上测三家）需要另外动手跑。span 的 GenAI 语义约定在本章 23 课，失败模式的分类在 26 课，用评测做发布闸门在 30 课。
