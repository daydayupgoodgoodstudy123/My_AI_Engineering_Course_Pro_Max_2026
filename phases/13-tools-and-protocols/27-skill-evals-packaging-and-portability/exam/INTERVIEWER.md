# 面试官手册：SkillEval（13/27）

候选人计时期间不要看。候选人手里只有 README、`skilleval/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。
- 题里没有模型，也不联网。路由器和宿主都是测试里按脚本回答的替身，本课讲的路由本身不在这套题里。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 多数运行对了，算这个用例通过吗？ | "No. A case passes only when every run matched. The rate is in matched and runs." |
| 1 | competing 用例上的误触发算 near miss 吗？ | "No. A false positive counts under the category of the case it happened on." |
| 1 | 从来不触发的 skill，F1 是多少？ | "0.0, like precision and recall. A report never crashes on it." |
| 1 | verify_manifest 能不能把 `./SKILL.md` 规范化成 `SKILL.md`？ | "No. Keys must already be canonical. Anything else is rejected, not normalized." |
| 1 | 能不能把 build_manifest 的结果缓存起来？ | "Not across calls: the installed tree can change between two checks. Within one call, build it once." |
| 2 | 弃权怎么写？ | "An empty predicted_skill cell. An empty string isn't a skill name, so append refuses it." |
| 2 | latency 能不能保留三位小数？ | "No. Write it so float() gives back the same float." |
| 2 | 同一个 run 追加了两次呢？ | "Refuse it, either when it's appended or when the log is read." |
| 2 | load 要不要把用例排序？ | "Case order doesn't matter. Each case's runs come back in run order." |
| 2 | 能多加一列吗？ | "No. COLUMNS is the header other tools read." |
| 2 | 要 fsync 或者文件锁吗？ | "The tests don't cover crashes or writers on other machines. Tell me where they'd go." |
| 3 | W_ 开头的 lint 问题算错误吗？ | "No, those are reviewed warnings. Every other code is an error, including codes without a prefix." |
| 3 | precision 正好 0.95，过 0.95 的门槛吗？ | "Yes. At least the minimum passes." |
| 3 | 能直接用报告里的 precision 和 recall 吗？ | "No. Those are rounded for people. Compare the thresholds with ratios from the raw counts." |
| 3 | 什么算回退？ | "A task whose with-skill pass rate is below its baseline pass rate. Equal is not a regression." |
| 3 | 一个 script check 都没有呢？ | "Then that layer fails. No evidence is not a pass." |
| 3 | degraded 的宿主算可移植吗？ | "Yes, degraded means a documented fallback. blocked doesn't, and neither does a missing verdict." |
| 3 | evidence root 里放什么？ | "The policy and every piece of evidence, raw runs included, as canonical JSON." |
| 3 | attestation 比的是原始字节还是解析后的 JSON？ | "The exact bytes against the trusted digest first, then what they decode to." |
| 3 | fixture 模式加一个有效的 attestation 呢？ | "Still not a release. Local evidence needs captured mode and a source for every layer." |
| 4 | time 用秒还是毫秒？ | "Seconds, as JUnit does. It's the sum of the case's latencies." |
| 4 | 要写 XML 声明吗？ | "Not needed. If you write one, it goes at the start of the first chunk." |
| 4 | 计数能放在 testsuite 的开标签上吗？ | "Not the failures: you don't know them yet. They go in properties at the end." |
| 4 | 失败信息里的运行按什么顺序？ | "Run order, 0 to n-1, whatever order they finished in." |
| 4 | 路由器抛异常怎么办？ | "The tests don't cover it. Say what you'd do." |
| 5 | 宿主没有声明某项能力呢？ | "It counts as unsupported, with the evidence 'no claim recorded'." |
| 5 | 有声明但 evidence 是空的？ | "Same as no claim." |
| 5 | 两个依赖一样差，cause 写哪个？ | "The first one declared. And a capability's own claim wins a tie with its dependencies." |
| 5 | 可选能力缺失会挡住安装吗？ | "No. Only required capabilities block." |
| 5 | unsupported 但有文档化的 fallback 呢？ | "Then it's degraded: the fallback covers it." |
| 5 | 只检查用到的能力，还是整个 catalog？ | "The whole catalog." |

## 每关：要看什么、提示、追问

### Part 1 修触发报告和安装校验（目标 12 分钟）

一个测试里叠了 5 个缺陷和几道护栏：

1. `trigger_report` 的 `"passed": matched[0]` 只看第 0 次运行。audit-tag 是 (release-readiness, None, release-readiness)，第 0 次对了就算通过。docstring 和课里都说每一次运行都要对。
2. `trigger_report` 按 `"competing" if case.expected_skill else "clear_negative"` 记误触发，没有用用例自己的类别。build-failed 是归 ci-triage 管的 near miss，它的两次误触发记进了 competing；stack-trace 是对抗措辞，误触发记进了 clear_negative。near_miss 一栏成了 0，Part 3 的闸门正是读这一栏和 `max_near_miss_false_positives` 比。
3. `classification_metrics` 的 F1 没有处理 precision 和 recall 都为 0 的情况。一个从不触发的描述让报告报 `ZeroDivisionError`。
4. `build_manifest` 用 `os.path.join(os.path.relpath(dirpath, root), name)` 拼键，根目录下的文件变成 `./SKILL.md`。错误不在这里报出来：测试先断言 `verify_manifest(installed, manifest)` 是干净的，结果是 `issues: ["invalid manifest path: './SKILL.md'"]`，`unexpected: ['./SKILL.md']`。`verify_manifest` 拒绝这个键是对的，根因在上一层生成清单的地方。
5. `verify_manifest` 通过 `_current_digest` 查每个条目，而 `_current_digest` 每次都重建整棵树的 manifest。206 个文件要哈希四万多次，本机 1.4 到 2.6 秒，限值 0.15 秒；只建一次是 7 到 16 毫秒。

护栏：
- 看到 `invalid manifest path: './SKILL.md'` 就去 `verify_manifest` 里把键规范化，会挂在 "manifest keys must already be canonical"：测试把 `./SKILL.md`、`references\release-policy.md`、`references//release-policy.md` 分别换进清单，都必须被拒绝。课里写得很清楚：这些键要拒绝，不规范化。
- 用 `relative.lstrip("./")` 去掉前缀：`lstrip` 去的是字符，不是前缀，安装目录里旧安装留下的 `.install-state` 会变成 `install-state`，挂在 "an edited file, a lost file and a stale file"。
- 为了提速把 `build_manifest` 按 root 缓存（`lru_cache`）：测试在两次校验之间改了安装目录，缓存的结果看不到。只哈希清单里列出的文件、不遍历目录：多出来的旧文件发现不了，符号链接还会被跟过去，指向外面一个内容相同的文件也能通过。
- 改写 `build_manifest` 时漏掉保留路径：清单里出现 `assets/manifest.json`，第一个断言就挂。反过来按文件名 `manifest.json` 跳过也不对：`evals/manifest.json` 是普通文件，被漏掉就没人校验它，挂在 "only the exact path assets/manifest.json is reserved"。去掉 `_entry_problem` 里的保留路径检查或摘要格式检查，或者把大写的摘要转成小写再比，都会被单独的断言抓住。
- 把“多数运行对了”当通过，或者把每个负例的误触发只记一次（`any` 而不是 `sum`），都挂在对应的断言上。
- 用四舍五入后的 precision 和 recall 去算 F1，这组数据上结果一样，测试分不出来。看到了要指出：取整只用于展示，F1 要用原始比值算，和 Part 3 的道理相同。

看什么：第 4 处是不是先看 issues 和 unexpected 里那个 `./SKILL.md` 是谁写出来的，而不是直接放宽 `verify_manifest`；读到第 5 处时能不能说出复杂度；每改一处就重跑。

提示：
- H1："verify_manifest rejected a key. Who wrote that key?"
- H2："Print build_manifest(installed). What do the keys of files at the root look like?"
- H3：直接指出 `build_manifest` 里拼 `relative` 的那一行，以及 `_current_digest` 每次调用做了什么。

追问：
- "Why bind provenance to every run's prediction, not the first run and the rate?"（课里说：第一次的值和通过率都一样的两组预测，可能是完全不同的运行时行为。Part 3 的 evidence root 就是这样绑定的）
- "The hashes match. Does that prove the manifest is authentic?"（不能。哈希只发现漂移；manifest 本身要靠签名发布或可信注册表这样的外部渠道）
- "Why reject `./SKILL.md` instead of normalizing it?"（一个文件有两种写法，清单就可以同时列两个不同的摘要，含义不唯一；各工具的规范化规则也不一样，比如 Windows 的反斜杠）
- "A bundle with fifty thousand files?"（一次遍历；流式哈希；可以并行；可以先比大小再算哈希，但发布校验不能跳过内容哈希）

### Part 2 逐次运行记录（目标 10 分钟）

坑：
- 弃权是空格子，读回来是 None。写成 `str(None)` 会落成 `None` 这四个字母；读回来不转成 None，就是空字符串。两种写法读回来都不是 None：`load` 里做了校验会报 "is not a skill name"，没做校验就挂在相等比较上。
- 空字符串不是弃权：它不是合法的 skill 名字，append 要拒绝。用 `if observation.predicted_skill and ...` 做检查会把它放过去。
- 只把 predicted_skill 的空格子转成 None。trace 可以是空字符串，`[cell or None for cell in row]` 会把它变成 None。
- latency 要原样往返：`repr` 或 `str` 都行。保留三位小数、`%g`、四舍五入到微秒，都会把 `1e-07`、`0.1 + 0.2`、`1234.5678901234567` 改掉。写成 Decimal 或者整数（`812.0` 写成 `812` 再读成 int）时，dataclass 的相等比较可能还过得去，重算的摘要就对不上了：测试最后用 `observations_digest` 比一次，抓的就是类型漂移。
- 读写都要 `newline=""`。trace 里有 Windows 宿主写出的 `\r\n`，读的时候不加 `newline=""`，通用换行模式会把它改成 `\n`。也不能 `strip()` 格子，trace 前后的空格和制表符要原样保留。
- 运行是按完成顺序追加的（第 2 次可能先于第 0 次），load 要按 run 排好。按文件顺序返回，或者返回 tuple，都过不了相等比较。
- 两个 worker 往同一个文件追加：表头只写一次，判断要在追加的那一刻做（文件是空的才写）。在构造函数里记下“这是新文件”，两个对象都会写表头，第二个表头读进来就是 `int('run')` 报错。每次追加都用 `"w"` 打开，前面的行就没了。
- 先校验再写：被拒绝的 observation 不能在文件里留下一行。NaN、无穷大、负数的 latency 和未知类别都要拒绝。整数 latency（`5`）也要拒绝：写进去是 `5`，读回来是 `5.0`，往返就不精确了。只用 `math.isfinite(x) and x >= 0` 检查会把它放过，要检查类型是 float。
- 同一个 run 记了两次、或者 run 编号有缺口（只有 0 和 2），load 要报 ValueError。重复的那次在 append 时拒绝也可以。
- 手工用逗号拼行不加引号，trace 里的逗号、引号和换行会把一行拆坏。

追问：
- "Why CSV and not JSON lines?"（表格工具能直接打开，按类别透视很方便；代价是格子都是文本，类型要靠读的一方恢复，JSON lines 能保留类型）
- "Workers on two machines append to one file on a network drive?"（跨机器的追加没有原子性保证；每个 worker 写自己的文件再合并，或者换数据库）
- "A trace contains a token the host printed."（写入前脱敏；课里的密钥扫描只是挡明显的错误，不能证明没有敏感数据）
- "Why recompute the digest from the log instead of storing it next to the rows?"（存在同一个文件里的摘要可以和数据一起被改掉；重算的摘要要和带外可信的 attestation 比）

### Part 3 发布闸门（目标 15 分钟）

坑：
- structure：只有 W_ 开头的是复核过的警告，其余都是错误，包括没有前缀的 `name-directory`。只数 `E_` 会把它放过；把警告也算上，夹具第一步就挂。
- precision 和 recall 用原始计数算比值再和阈值比。报告里的值是四舍五入到 4 位的：19999/25000 = 0.79996，报告里是 0.8，拿它去比 `min_recall=0.8` 就会误判通过。这正是本课测验 Q10 第 3 小题讲的问题。
- 阈值是“至少”：夹具里 precision 正好 0.95、near miss 误触发正好 1 次、artifact 通过率正好 0.85，用 `>` 或 `<` 都会挂。
- near miss 只数 near_miss 一栏，competing 的那次误触发不算。同一个 near miss 用例里的两次误触发是两次，按用例数会少算。触发集里没有 near miss 用例时，这一层不通过：没测过的边界不算过了。
- artifact 通过率只看 with-skill 的运行；把 baseline 也混进来，夹具就挂。它是所有 with-skill 运行合在一起的通过率，不是各任务通过率的平均：一个任务 1 次全过、另一个 20 次过 16 次，合起来是 17/21，低于 0.85；按任务平均是 0.9，会误判通过。
- 回退按任务比通过率：平均从 0.8 升到 0.85，evidence-paths 从 5/5 掉到 4/5、blocking-findings 从 4/5 掉到 3/5，仍然要失败，`regressions` 按任务顺序列出这两个，排序就错了。通过率相等不算回退。把两组运行按位置一一配对去比也不对：evidence-paths 的 baseline 第 0 次过了、with-skill 第 0 次没过，但通过率从 0.2 升到 0.8。
- scripts 和 safety：至少一个检查，并且全部通过。`all([])` 是 True，空的一层要单独判失败。safety 不能用通过率比阈值，10 个里错 1 个就是 0.9，比 0.85 高，但这一层必须失败。scripts 也不能用 `any`。
- portability：每个必需宿主都要有结论，并且是 native、adapter 或 degraded。只遍历已有结论的宿主，缺了 codex 也能过；要求全是 native，degraded 的 codex 就被冤枉了；不是必需的宿主（prompt-only）是 blocked 也不影响。
- installed_tree 要真的调 `verify_manifest(installed_root, evidence.manifest)`，测试会给一个改过的安装目录。
- 每一层单独判定，`failed` 按 LAYERS 的顺序列出失败的层。不能算一个总分，让别的层把失败的层抵消掉。
- evidence root 要绑定 policy 和全部证据。不放 policy，事后把 `min_precision` 降到 0.9，旧的 attestation 照样有效；只放 checks 或者每个用例的第一次运行和通过率，把 audit 的运行换个顺序（第一次的值和通过率都不变），旧的 attestation 也照样有效。要用规范 JSON：直接 `json.dumps` 不排序，同样的证据换个字典顺序就是另一个 root。
- trust anchor：先用 trusted_digest 比 attestation 的原始字节（测试里的 attestation 是带缩进和换行的 JSON），再解析。重新序列化之后再算摘要会对不上。`attestationVersion` 必须是整数 1，`True == 1` 和 `1.0 == 1` 在 Python 里都成立，要比类型。解析失败（包括不是 UTF-8 的字节）返回 False，不能抛异常；只接 `json.JSONDecodeError` 接不住 `UnicodeDecodeError`。数组不是对象，`.get` 会报 AttributeError。
- `production_ready` 三个条件都要：checks 通过、本地证据就绪、trust anchor 有效。fixture 模式下即使 sources 齐全、attestation 有效也不是发布（local_evidence_ready 要先看 mode）；attestation 也不能让失败的层变成发布。`passed` 跟随 `production_ready`，不是 `checks_passed`；`fixture_passed` 只在 fixture 模式下为真。
- local_evidence_ready：captured 模式，并且 EVIDENCE_LAYERS 里每一层都有非空白的 source。只看 sources 是否为空，或者不 strip，都会放过 `"hosts": "  "`。

追问：
- "Thresholds must be declared before the results. How do you enforce that in a real pipeline?"（policy 在运行前版本化、签名；evidence root 绑定 policy；attestation 签的是这个 root）
- "Why can't local digests prove the results were captured?"（能改 bundle 的人可以把夹具改标成 captured、编一个 source、重算所有本地摘要；只有带外可信渠道给的摘要才是信任锚）
- "Ten runs at 0.95 precision. Is that enough to ship?"（十分之十和一百分之一百都是 100%，证据强度不同；看置信区间，样本量要和风险相称，课里也说要同时报原始计数）
- "Why not one weighted score?"（课里说：不能让文字质量的高分抵消一次越权）

### Part 4 JUnit 流（目标 12 分钟）

坑：
- 格式由测试的解析代码决定：所有块拼起来用 ElementTree 解析。属性值里有引号、`&`、`<` 和换行。`xml.sax.saxutils.escape` 不转义引号，会 ParseError；`html.escape` 不处理换行，XML 的属性值规范化会把 `\n` 变成空格；先转义 `<` 再转义 `&` 会把 `&lt;` 变成 `&amp;lt;`。用 `ET.Element` 加 `ET.tostring`，或者 `quoteattr`，都能处理。失败信息的文本（每次运行的 trace）里也有 `<` 和 `&`。
- 第一个块是 `<testsuite ...>` 开标签，在任何一次运行结束之前发出。先等第一个用例再发开标签会挂在探针上。
- 每个用例一个块，是完整的 `<testcase>` 元素，按声明顺序发。先完成的后面用例要缓存：build-failed 比 audit-tag 先跑完，但要等 audit-tag 发出之后才发。
- 一个用例和它前面的用例都完成了就马上发。测试在每个块到达时记下哪些运行已经结束：ship 发出时 audit-tag 还没跑完。先 `gather` 所有用例再输出会挂在这里；按完成顺序（`as_completed`）输出会挂在顺序上。
- 并发上限管的是路由器调用，跨所有用例共用，而且要用满：测试要求峰值正好是 4。一个用例一个用例地跑，峰值只有 3；信号量套在用例外面，峰值是 12；不加信号量是 15。
- 失败信息写 `matched/runs runs matched: prompt`，matched 是对了的次数，不是错了的次数（build-failed 是 1/3，其余两个失败用例是 2/3）。全对的用例不带 failure。failure 的 type 是 `trigger-mismatch`。
- 失败文本按运行编号列 trace，不是按完成顺序：stack-trace 的第 0 次最后才结束。
- time 是秒，JUnit 的惯例，是这个用例所有运行的延迟之和。写成毫秒差 1000 倍；取最大值或者四舍五入到整秒都不对。
- 结尾是 properties 里的 failures、runs、matched，然后闭合 `</testsuite>`。failures 数的是失败的用例（3 个），不是没对上的运行（4 次）；matched 数的是对了的运行（11 次）。
- runs 或 concurrency 小于 1 要在任何调用之前报 ValueError。`Semaphore(0)` 会让所有调用永远等下去，测试的 2 秒超时会把它报成 TimeoutError。
- 写成普通的 async 函数（只有 return、没有 yield）时，测试报 `'async for' requires an object with __aiter__ method, got coroutine`，要会看出来这里需要 async generator。

追问：
- "Your CI validates JUnit files against the XSD, which wants properties first and counts on the testsuite tag. What changes?"（流式就做不到：可以先写临时文件、结束时把开标签补上计数，或者每个用例一个 testsuite；取舍是实时性和兼容性）
- "A trace has ANSI color codes in it."（XML 1.0 连字符引用都不能表示大部分 C0 控制字符；要替换或转写，pytest 的 junitxml 就是这样做的）
- "The CI runner disconnects halfway through."（`aclose()` 会在 finally 里取消还没完成的任务；不取消的话路由器调用还在花钱）
- "One router call hangs."（每次调用要有超时，记成 error；按顺序输出的代价是队头阻塞，一个慢用例会挡住后面已经完成的用例）

### Part 5 能力矩阵（目标 11 分钟）

坑：
- 有效状态是自己的声明和所有依赖的有效状态里最差的那个，要一路往下传：invocation-policy 依赖 implicit-invocation，implicit-invocation 依赖 host-router。只看自己的声明，copy-entry-host 和 legacy-host 的 script-execution 都不会被挡住；只看一层依赖，legacy-host 的 script-execution 仍然漏掉，它的降级在两层以下的 body-activation。
- adapter 也会往上传：adapter-host 的 body-activation 走适配器，companion-files 和 script-execution 也只能算 adapter。
- 没有声明，或者 evidence 是空白，都算 unsupported，evidence 写 "no claim recorded"。默认当 supported 是错的，`claims[name]` 会报 KeyError。
- outcome：degraded 或 unsupported，有文档化的 fallback 就是 degraded；没有的话分别是 silent-degradation 和 unsupported。fallback 只认 degraded 不认 unsupported，no-ui-host 的 explicit-invocation 就会把安装挡住。没有 fallback 的 degraded 当成 degraded，就是课里说的静默降级。
- 只有必需能力会挡住安装，可选能力再差也只是记下来。
- cause 和 evidence：自己的声明不比依赖好时，cause 是自己；否则是声明顺序里第一个最差的依赖的 cause。平手时归依赖、或者取最后一个依赖，都会挂。evidence 是 cause 的 evidence，不是这项能力自己的。fallback 只在用上时才写出来。
- verdict 先看 blocked，再看 degraded，再看 adapter。adapter 放在 degraded 前面判，no-ui-host 就成了 adapter。
- 记忆化按宿主分开。所有宿主共用一个缓存，第二个宿主拿到的是第一个宿主的结果。
- 环用当前路径检查。用一个全局的 visited 集合当环来判，共享的依赖（catalog-entry 被好几项能力依赖）会被误判成环。不查环会 RecursionError。整个 catalog 都要检查：lifecycle-hooks 依赖了一个不存在的能力，或者和 context-preservation 互相依赖，虽然没人用它们，也要报 ValueError；只在解析用到的能力时查环，会漏掉后一种。未知状态和不在 catalog 里的必需能力也报 ValueError，不能等到查表时报 KeyError。fallbacks 里的名字也要在 catalog 里；同一项能力既是必需又是可选，也报 ValueError。
- capabilities 按先必需、后可选的声明顺序列出，不要排序。

追问：
- "Where do the claims come from?"（对真实安装做探测，或者引用当前的官方契约；记下宿主版本、适配器版本和日期；宿主升级后重跑）
- "A host update silently drops a capability. How do you notice?"（定期探测，比较矩阵的摘要；课里的升级和卸载检查）
- "Why is silent degradation worse than unsupported?"（unsupported 会让安装大声失败；静默降级装上了，到运行时才悄悄少了行为）
- "An optional capability degrades with no fallback. Warn or ignore?"（报出来，但不挡安装；用户应该知道少了什么）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出 manifest 的真实性、多 worker 写日志、阈值的预先声明和带外信任锚、样本量、JUnit 的兼容性和取消、能力声明的来源和静默降级 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
