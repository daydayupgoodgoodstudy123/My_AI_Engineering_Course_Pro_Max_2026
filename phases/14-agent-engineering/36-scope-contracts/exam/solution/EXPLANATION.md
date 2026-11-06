# 参考答案讲解：TaskScope（14/36）

计时结束后再看。参考实现在同目录的 `taskscope/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修 checker

**现象**：解锁后第一条断言说 `lib/upload/pdf.py` 和 `tests/test_upload_pdf.py` 是越界写入，可两份合同明明都允许它们。

**顺着往上找**：`scope_check` 和 `Classifier` 都没问题，它们只是照着合并后的合同分类。打印 `effective.allowed_files` 就能看到只剩 `["app.py"]`：`merge_contracts` 把 `{"app.py", "tests/test_*.py", "lib/**/*.py"}` 和 `{"app.py", "lib/upload/*.py", ...}` 当字符串集合求交集，两边字面相同的只有 `app.py`。glob 描述的是路径集合，字符串不同不等于集合不相交（测验 Q9）。这一关想练的是：报错的位置往往不是出 bug 的位置。

**依次修四处**：

1. `merge_contracts` 保留两张表：`allowed_files` 取子合同的，`allowed_within` 依次放父合同的 `allowed_within`、父合同的 `allowed_files`、子合同的 `allowed_within`。`Classifier` 本来就要求路径命中每一张表。子合同自己的 `allowed_within` 不能丢：合并好的合同再被合并一次时（测试把它放到一个只写了 `**` 的合同下面），项目的表就在那里面。
2. `over_budget` 改成数不同的越界文件：`len(off_scope) > violation_budget`。原来数的是 warn 级 finding，而所有越界文件只产生一条 finding，预算 ≥ 1 时越界多少个都通过（测验 Q5、Q10）。
3. 主机先规范化再比较，两边都要规范化：

   ```python
   def normalize_host(host):
       host = host.strip().lower()
       if host.startswith("["):              # [2001:db8::1]:443
           return host[: host.find("]") + 1]
       return host.split(":", 1)[0] if host.count(":") == 1 else host
   ```

4. 计时。原来每个路径都要对 3,000 条 glob 各 `fnmatch` 一次，1,700 个路径一共约 500 万次，本机 1 到 2.5 秒。glob 第一个通配符前面的那几段目录是字面量，能匹配它的路径一定在这个目录下。按这个字面目录给 glob 分桶，没有通配符的 glob 放进一个精确匹配的集合；查一个路径时只看 `""`、`services`、`services/svc-2480`、`services/svc-2480/src` 这几个桶。参考实现 5 到 10 毫秒。

**护栏**：
- 合并用并集、只留一边、或者把空的 allow-list 当成“不限制”，都会被抓住。只读任务的 `allowed_files` 就是空的。
- 没有字面目录的 glob（`**/secrets/**`、`*.lock`）放在 `""` 桶里，对每个路径都要检查。只按第一段目录分桶不够：3,000 条 `services/svc-NNNN/**` 全落在 `services` 一个桶里，还是要 0.4 到 0.9 秒。
- 只编译用得到的 glob。在 `PatternSet.__init__` 里把 3,000 条全部预编译（60 到 120 毫秒），或者拼成一条大正则（60 到 180 毫秒），都贴着 0.1 秒的上限，时过时不过；沿用 `fnmatch` 自带的缓存，只有候选桶里的几十条会被编译。
- 拿 `tests/test_` 这种截在段中间的前缀当桶名，路径的各级目录里永远不会出现它，`tests/test_*.py` 就失效了。分桶键必须是完整的目录。
- forbidden 先于 allowed，allowed 先于 soft：允许范围内的 `services/svc-2484/README.md` 是 in scope，不是 soft。

## Part 2 归档

一个任务一个文件：`closed/<task_id>.json`。写之前先把整条记录序列化成字节：

```python
payload = (json.dumps(record, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
```

- **独占创建**：`O_CREAT | O_EXCL` 在路径以任何形式存在时都失败，包括悬空的符号链接，也不会顺着链接写到别处。先 `exists()` 再写，悬空链接会骗过检查，把文件写到仓库外面；先写临时文件再 `os.replace`，会把已有的条目换掉。两种做法在并发时也都有竞态。
- **严格 JSON，失败不留痕**：`allow_nan=False` 遇到 NaN 报 ValueError。序列化在建文件之前完成，所以失败时磁盘上什么都没有，修好记录后还能再关一次。先建文件再 `json.dump`，会留下一个写了一半的文件，这个任务就永远关不上了。
- **往返完全一致**：用 `asdict` 写，读回来时把 findings 还原成 `Finding`，其余字段直接 `ScopeContract(**...)`、`RunSummary(**...)`。要守住的是这个领域的值：`network_egress` 的 `None`（不检查）和 `[]`（全部拒绝）、表的表 `allowed_within`、原样的 `touched_files`（重复也是证据）、`0.1 + 0.2` 和 7 位小数的 `closed_at`。Python 的 float 经过 JSON 能原样还原；转成 ISO 时间只到微秒。
- **给审计看的顶层字段**：`task_id`、`passed`（JSON 布尔值）、`closed_at`。
- **task_id 是普通文件名**：在写盘和读盘之前都检查，`../T-004`、`T-004/x` 都会让路径越出 `closed/`。
- `task_ids()` 只认 `<合法 id>.json`，临时文件、`notes.txt` 和 macOS 的 `._T-001.json` 都跳过。

## Part 3 glob 方言

`translate` 按 `/` 切段，一段一段翻译成正则，再交给 `re.fullmatch`：

| 写法 | 正则 |
|---|---|
| 整段的 `**`，在开头或中间 | `(?:[^/]+/)*`（零个或多个整段目录，连同后面的 `/`） |
| 整段的 `**`，在结尾 | `.+`（目录下面的所有文件） |
| `*` / `?` | `[^/]*` / `[^/]` |
| `[!abc]` | `[^abc/]` |
| `[abc]`、`[a-z]` | `(?!/)[a-z]`（范围可能跨过 `/`，比如 `[+-0]`） |
| `\x` | `re.escape("x")` |
| 其他字符 | `re.escape(c)` |

结尾的 `/` 先换成 `/**`。所以 `lib/**/*.py` 是 `lib/(?:[^/]+/)*[^/]*\.py`，`lib/x.py` 和 `lib/a/b/x.py` 都匹配；`docs/**` 是 `docs/.+`，不匹配 `docs` 本身，也不匹配 `docsite/`。空模式、绝对路径、末尾单独的反斜杠、没闭合的 `[` 都报 ValueError，不像 fnmatch 那样当字面量。

`normalize_path` 不用 `posixpath.normpath`：它把 `lib/../../x` 变成 `../x`、把空串变成 `.`，都不报错。自己逐段处理：空段和 `.` 丢掉，`..` 弹出上一段，弹空了就是越出仓库。`..notes` 和 `...` 是普通名字。

接进 checker 有三处：
- `PatternSet` 改用 `compile_glob`。分桶键要和方言一致：参考实现的 `index_key` 把结尾的 `/` 当成 `/**`，带反斜杠的模式先解转义再算字面目录；glob 在第一次成为候选时才编译（`compile_glob` 带缓存），3,000 条全部预编译要 60 到 120 毫秒，会贴着 Part 1 的上限。
- `scope_check` 先规范化再去重，`./lib/pdf.py` 和 `lib/pdf.py` 是同一个文件。
- 越出仓库的路径归为 forbidden，报告里保留 agent 写的原样。

## Part 4 流式 diff 检查

状态只有三样：未拼完的半行（`bytearray`）、当前文件头的若干行、已报告过的路径和越界计数。

```python
async for chunk in chunks:
    buffer += chunk
    start = 0
    while (end := buffer.find(b"\n", start)) != -1:
        for result in feed(bytes(buffer[start:end])):
            yield result
        start = end + 1
    del buffer[:start]
```

- `feed` 看到 `diff --git` 就结束上一个文件、开始新文件；看到 `@@` 就说明文件头完整了，立即判定并输出，之后的 hunk 行一律忽略。所以 hunk 里的 `--- a/b test cohort`（删掉的一行 SQL 注释）不会被当成文件头。流结束时先补上没有换行的最后一行，再判定最后一个文件；后一步不能放在“还剩半行”的分支里，否则以换行结尾、没有 hunk 的最后一个文件（只改权限位）会被漏掉。
- 路径来源：有 `rename from/to` 就取两边，有 `copy to` 只取目标，否则取 `diff --git` 头。不靠 `---`/`+++`，因为二进制文件、只改权限位、新建空文件、100% 相似的重命名都没有这两行。
- 文件头里的路径：带引号就按 C 转义还原成字节（`\ooo` 是一个字节），再按 UTF-8 解码；不带引号时两边是同一个路径，`a/P b/P` 按长度对半分，空格和 ` b/` 都不怕。
- 判定复用 `Classifier`；不同的越界文件第一次超过预算时，紧跟着补一条 `scope/over-budget`。先查重再计数，同一个越界文件出现两次只算一个。
- 输出是 SARIF 风格的 result，一行一个；`uri` 用 `urllib.parse.quote`。

## Part 5 合同链

`resolve_chain` 先建 `task_id -> 合同` 的表（重复就报错），再从目标往上走：每一步检查 parent 存在，并且正好高一个 altitude（project、feature、task、subtask），走到 project 为止（project 合同自己不能有 parent），最后反转成从项目往下的顺序。altitude 每一步都严格往上，所以不会绕圈。

`explain` 分两趟，都从项目往下：
1. 第一趟只看 forbidden，哪一层先命中就报哪一层，以及这一层里第一条命中的 glob；
2. 第一趟没有命中，第二趟看每层的 allowed（`allowed_files` 和 `allowed_within`），哪一层先不允许就报哪一层。

分两趟是为了让 forbidden 压过 not allowed，不管它们出自哪一层，这和 checker 的分类顺序一致。`explain_host` 跳过 `None` 的层，`[]` 的层拒绝一切。`effective()` 从项目往下依次 `merge_contracts`：`[]` 和任何表求交还是 `[]`，`None` 服从另一边，预算取最小，审批按从上到下的顺序累加。

## 这套题证明了什么，没证明什么

通过了说明你能在一个范围检查器里顺着结果往上游找到合并逻辑的错误、给大合同的 glob 建索引、写出一个说得清楚的 glob 方言、把证据安全地落盘、解析流式的 git diff，以及在一条合同链上做最小权限合并和归因。它不涉及真正的 git 仓库和 CI，没有覆盖 `feature_list.json` 的“最多一个 in_progress”启动检查、验收命令的退出码、时间预算到点时的中断，也不涉及 YAML 合同和 LangGraph 的中断审批。这些需要另外动手。
