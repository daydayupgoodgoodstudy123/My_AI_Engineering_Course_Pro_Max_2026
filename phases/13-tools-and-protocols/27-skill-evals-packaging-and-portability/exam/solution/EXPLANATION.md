# 参考答案讲解：SkillEval（13/27）

计时结束后再看。参考实现在同目录的 `skilleval/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修触发报告和安装校验

**现象**：解锁后第一个错误是 "a case passes only when every one of its runs matched"。audit-tag 的三次运行是 (release-readiness, None, release-readiness)，matched 是 2，passed 却是 True。

**依次修五处**：

1. `trigger_report`：`"passed": all(matched)`。原来的 `matched[0]` 只看第 0 次运行。课里专门说过，重复运行要保留每一次的结果，只看第一次和通过率，会把不同的运行时行为当成一样。
2. `trigger_report`：误触发按 `case.category` 记。原来的写法默认负例只有两种：期望别的 skill 的算 competing，什么都不期望的算 clear_negative。near miss 和对抗措辞因此都记错了栏，near_miss 一栏是 0，Part 3 的闸门拿这一栏和 `max_near_miss_false_positives` 比，永远不会拦。
3. `classification_metrics`：precision 和 recall 都是 0 时 F1 记 0.0。一个从来不触发的描述（recall 是 0/6，precision 是 0/0）原来会让整份报告报 ZeroDivisionError。
4. `build_manifest`：键用 `path.relative_to(root).as_posix()`。原来的 `os.path.join(os.path.relpath(dirpath, root), name)` 对根目录下的文件给出 `./SKILL.md`，因为 `os.path.relpath(root, root)` 是 `"."`。错误报在下一层：`verify_manifest` 照规则拒绝了这个键，报告里同时出现 `invalid manifest path: './SKILL.md'` 和 `unexpected: ['./SKILL.md']`。这一关想练的是：报错的地方（拒绝了一个键）不是出 bug 的地方（写出了这个键）。
5. `verify_manifest`：整棵树的 manifest 只建一次，再逐条比。原来的 `_current_digest` 每查一个条目就重建一次，206 个文件要哈希四万多次，本机 1.4 到 2.6 秒；建一次大约 8 毫秒。

**护栏**：

- 键的规则在 `verify_manifest` 的 docstring 里，也在课里：`./SKILL.md`、反斜杠、绝对路径、空段和 `..` 都直接拒绝，不规范化。看到第 4 处的报错就去放宽 `verify_manifest`，测试会把这三种写法分别换进清单，要求每一种都被拒绝。
- 修第 4 处时用 `lstrip("./")` 也不行。`lstrip` 去掉的是开头所有属于这个字符集合的字符，旧安装留下的 `.install-state` 会变成 `install-state`。
- 修第 5 处时，缓存只能在一次调用之内。按 root 缓存 `build_manifest`，测试在两次校验之间改了安装目录，第二次看到的还是旧结果。只哈希清单里列出的文件、不遍历目录，也不行：多出来的文件发现不了，符号链接会被跟过去。
- `assets/manifest.json` 不进自己的清单，清单里列了它也要拒绝。保留的是这一个完整路径，别的目录里叫 `manifest.json` 的文件照常校验。一个文件没法在自己的内容里带上自己完整内容的哈希，manifest 的真实性要靠外部渠道。

## Part 2 逐次运行记录

参考实现一次追加一行，文件是空的才先写表头：

```python
_check(observation)
with open(self.path, "a", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    if f.tell() == 0:
        writer.writerow(COLUMNS)
    writer.writerow([observation.case_id, observation.run, observation.category,
                     "" if observation.predicted_skill is None else observation.predicted_skill,
                     repr(observation.latency_ms), observation.trace])
```

读的时候 `csv.reader` 解析，run 用 `int`，latency 用 `float`，只有 predicted_skill 的空格子变成 None。每个用例的运行先放进 `{run: observation}`，重复的 run 报错，最后检查编号正好是 0 到 n-1，再按编号排成列表。

容易漏的几点：

- **弃权和空字符串**：弃权是 None，写成空格子。空字符串不是合法的 skill 名字，append 要拒绝，不能悄悄当成弃权。trace 的空格子就是空字符串，不能也变成 None。
- **latency 原样往返**：`repr(float)` 是能还原的最短写法，`float()` 读回来是同一个数。保留几位小数、`%g`、换成 Decimal 或 int 都会变。测试最后用 `observations_digest` 重算一次摘要：`812.0` 读成 `812` 时 dataclass 比较还相等，摘要就不一样了，因为规范 JSON 里一个是 `812.0`，一个是 `812`。
- **`newline=""`**：csv 模块要求读写都这样打开。trace 里的 `\r\n` 在通用换行模式下会被改成 `\n`。
- **运行顺序**：并发的运行按完成顺序追加，读回来要按 run 排序，返回列表。
- **两个 worker**：都在追加的那一刻看文件是不是空的，表头只会写一次。
- **先校验后写**：被拒绝的 observation 不能留下半行或一整行。NaN、无穷大、负数的 latency 也要拒绝；规范 JSON 本来就不允许 NaN。整数 latency 同样拒绝，因为它读回来会变成 float。

## Part 3 发布闸门

参考实现先用 Part 1 的 `trigger_report` 拿到原始计数，再逐层判定：

```python
precision = tp / (tp + fp) if tp + fp else 0.0
recall = tp / (tp + fn) if tp + fn else 0.0
checks = {
    "structure": sum(not code.startswith("W_") for code in evidence.lint_issues) <= policy.max_structure_errors,
    "precision": precision >= policy.min_precision,
    "recall": recall >= policy.min_recall,
    "near_miss": has_near_misses and report["false_positives"]["near_miss"] <= policy.max_near_miss_false_positives,
    "artifact_pass_rate": bool(with_skill) and sum(with_skill) / len(with_skill) >= policy.min_artifact_pass_rate,
    "no_regression": not regressions,
    "scripts": bool(evidence.script_checks) and all(check.passed for check in evidence.script_checks),
    "safety": bool(evidence.safety_checks) and all(check.passed for check in evidence.safety_checks),
    "portability": all(evidence.host_verdicts.get(host) in INSTALLABLE_VERDICTS for host in policy.required_hosts),
    "installed_tree": installed["passed"] is True,
}
```

几个要点：

- **不用四舍五入后的值判阈值**。报告里的比值保留 4 位小数，19999/25000 = 0.79996 显示成 0.8。拿显示值和 0.8 比就会误判通过。这是本课测验 Q10 第 3 小题提的问题。
- **阈值是“至少”**。夹具里 precision 正好 0.95，near miss 误触发正好 1 次，artifact 通过率正好 0.85。测试的 policy 把 artifact 门槛设成 0.85 而不是课里的 0.90，是因为浮点数 0.9 比 9/10 略大：用 Fraction 精确比较时 18/20 达不到 0.9，用浮点除法却正好相等，两种合理写法会给出不同结果。0.85 和 0.95 没有这个问题。
- **按任务比回退**。课里说平均提高了也要报告每个任务的回退。比的是两组各自的通过率，不能把运行按位置配对，也不能用总数比。
- **artifact 通过率按运行合计**。docstring 定义的是所有 with-skill 运行里通过的比例；各任务运行次数不同时，按任务平均会让运行少的任务占太大权重。
- **没有证据就不算过**。scripts 或 safety 一个检查都没有时，`all([])` 是 True，要单独判失败。safety 必须全部通过，不能拿通过率去比门槛。
- **evidence root**：`canonical_digest({"policy": asdict(policy), "evidence": asdict(evidence)})`。放进 policy，事后改阈值会让旧的 attestation 失效，这就是“阈值在看结果之前声明”能被检查的方式。放进原始的逐次预测，换一下运行顺序（第一次的值和通过率都不变）也会让 root 变。规范 JSON 排了键，字典的构造顺序不影响结果。
- **trust anchor**：先比 attestation 原始字节的摘要和带外给的 trusted_digest，再解析。`attestationVersion` 要 `type(...) is int`，因为 JSON 的 `true` 解析出来是 `True`，而 `True == 1`。解析失败返回 False，`UnicodeDecodeError` 和 `JSONDecodeError` 都是 ValueError 的子类。
- **三种“通过”分开**：`fixture_passed` 只说明夹具上的机制没问题；`local_evidence_ready` 只说明标签和来源齐全，本地摘要谁都能重算；`production_ready` 要 checks、本地证据和 trust anchor 三者都成立，`passed` 跟随它。

## Part 4 JUnit 流

参考实现先为每个用例建一个任务，开标签在任何等待之前发出，然后按声明顺序等这些任务：

```python
pending = [asyncio.ensure_future(every_run(case)) for case in cases]
try:
    yield f'<testsuite name={quoteattr(skill)} tests="{len(cases)}">'
    for case, task in zip(cases, pending):
        replies = await task
        ...
        yield _testcase(case, replies, matched)
    yield ET.tostring(properties, encoding="unicode") + "</testsuite>"
finally:
    for task in pending:
        task.cancel()
```

- 所有任务一开始就排进事件循环，按声明顺序 `await`，先完成的后面用例自然就缓存在任务里；前面的都发完时，下一个任务一完成就发。
- 每次路由器调用都在同一个 `asyncio.Semaphore(concurrency)` 里，上限管的是调用，不是用例。`gather` 按传入的顺序返回结果，失败文本里的运行编号因此是对的。
- testcase 用 `ET.Element` 和 `ET.tostring` 生成。ElementTree 会把属性里的 `"`、`&`、`<`、`>` 和换行转义成实体，文本里的 `&` 和 `<` 也会转义。手写字符串时，`html.escape` 不处理换行，XML 解析器会按属性值规范化把换行变成空格。
- 失败数在开头还不知道，所以放在结尾的 properties 里。JUnit 的 XSD 要求 properties 在 testcase 之前，这是流式输出的代价，追问里可以讨论。
- `finally` 里取消没完成的任务：消费者中途 `aclose()` 时，路由器调用不会在后台继续跑。

## Part 5 能力矩阵

参考实现先检查整个 catalog（用当前路径查环，用完成集合跳过已检查的节点），再对每个宿主做带记忆的递归：

```python
def resolve(name):
    if name not in memo:
        worst, cause = own(name)[0], name
        for dependency in catalog[name]:
            level, source = resolve(dependency)
            if level > worst:
                worst, cause = level, source
        memo[name] = (worst, cause)
    return memo[name]
```

- `own` 把没有声明、或者 evidence 是空白的能力当成 unsupported，evidence 记 UNCLAIMED。课里说能力声明要指向测试或当前的官方契约，没有证据的声明不算数。
- 严格大于才换 cause：自己的声明在平手时胜出，依赖之间平手时声明顺序靠前的胜出。
- outcome 再看文档化的 fallback：有 fallback 的 degraded 或 unsupported 是 degraded；没有的话，degraded 是静默降级，unsupported 就是 unsupported。课里的四种结局正好对应 supported、adapter、degraded 和让安装失败。
- 只有必需能力会挡住安装。verdict 先看有没有挡住的，再看最差的必需能力是 degraded 还是 adapter。
- memo 放在每个宿主的循环里面。共享缓存会把第一个宿主的结论带给后面的宿主。
- 环要用当前路径判断。全局的 visited 集合会把共享的依赖（很多能力都依赖 catalog-entry）误判成环。整个 catalog 都要查，没人用到的两项能力互相依赖也是坏的 catalog。

## 这套题证明了什么，没证明什么

通过了说明你能在一份带重复运行的触发报告和一个安装校验里顺着报错找到根因，知道规范路径为什么要拒绝而不是规范化；能把逐次运行的原始观测无损地存进 CSV 并重算出同一个摘要；能写出逐层判定、阈值和证据绑定、需要带外信任锚的发布闸门；能写出有并发上限、按顺序流式输出、转义正确的 JUnit XML；能沿依赖图算出每个宿主的能力结论。它不涉及模型驱动的路由（课里说词法模拟证明不了运行时行为，路由是第 25 课的内容），不涉及 SKILL.md 的解析和 lint（第 22 课），也不涉及真实宿主的安装、探测、升级和卸载。本课 Real-Host Portability Checkpoint 那一节要在真实宿主上另外动手做。
