# 参考答案讲解：PoisonGuard（13/15）

计时结束后再看。参考实现在同目录的 `poisonguard/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修扫描和摘要

**现象**：解锁后的第一个错误是 `re.search` 里的 TypeError：expected string or bytes-like object, got 'NoneType'。正则本身没有问题。

**顺着往上找**：`scan_description` 收到的是 None，因为 `scan_catalog` 传的是 `tool.get("description")`。notes.stats 这个工具服务器没给描述，`.get` 不带默认值就是 None。这一关想练的还是那件事：报错的位置往往不是出 bug 的位置。

**依次修五处**：

1. `scan_catalog` 里改成 `tool.get("description", "")`。在 `scan_description` 里把 None 当空串处理也可以。
2. `descriptor_digest` 要哈希整个 descriptor：`canonical_json(tool)`。原来只取 name 和 description，课里那句 A description hash alone misses schema and annotation changes 说的就是它，练习 4 也是这个场景。
3. `canonical_json` 补上 `sort_keys=True`。不排序时，同一个 descriptor 只要服务器换个键序，摘要就变，每次刷新都报 rug pull，报多了就没人看了。
4. `scan_description` 补上 `re.I`。`<SYSTEM>` 和 `IGNORE Previous Instructions` 都是绕过大小写敏感正则的最省事的写法。
5. `visible_tools` 先调一次 `scan_catalog`，把有 finding 的限定名放进集合，再遍历工具。原来在循环里每个工具都把整份目录重新哈希、重新扫描一遍。

**护栏**：

- 摘要的字节必须和清单里已经存着的 pin 一样，测试用一个带德文变音、德文引号和非字母序列表的 descriptor 核对精确值。规范形式是 docstring 写的那种：键排序、紧凑分隔符、非 ASCII 转义，列表保持原顺序。`ensure_ascii=False`、`hash()`、把列表也排序，单看都“合理”，但会让所有旧 pin 对不上。
- 为了躲键序问题只挑几个字段哈希，annotations 一变就漏掉。测试里把 readOnlyHint 翻成了 true，宿主会因此跳过确认。
- 为了提速按 `id(tool)` 缓存摘要，原地改过的 descriptor 还拿旧摘要比，rug pull 就看不见了。课里 Use It 一节说得很直接：缓存的批准在 descriptor 变化时必须失效。
- shadowing 的 finding 写的是裸名，不会挡住任何工具，限定名已经把它们分开了。

## Part 2 pin 清单

一个 JSON 文件，`{"format": ..., "pins": {限定名: {...}}}`。每个调用都按文件此刻的内容读、改、写回：

```python
def approve(self, key, digest, publisher, at):
    _check_key(key)
    if not isinstance(digest, str) or not _HEX64.fullmatch(digest):
        raise ValueError(...)
    _check_time(at)
    pin = Pin(key, digest.lower(), dict(publisher), at, None)
    pins = self._load()
    pins[key] = pin
    self._save(pins)
    return pin
```

- **摘要**：`fullmatch` 64 位十六进制，大小写都收，存小写。`re.match` 配 `$` 会放过结尾的换行。
- **限定名**：原样存，区分大小写。notes.Export 和 notes.export 是两个工具，长得像正是仿冒的常见手法。点号两边都不能空，`notes.` 和 `.export` 都不是限定名。
- **时间**：`isoformat()` 写，`fromisoformat()` 读，微秒和时区都在。naive 时间直接拒绝。测试比较的是时刻，所以统一换成 UTC 存也可以，只要读回来带时区。
- **隔离**：`quarantine` 只在还没隔离时写入时间，所以一直保留第一次 rug pull 的时刻；`approve` 总是新建一条完整的 Pin 替换旧的，不带隔离，重新批准就解除了。测试里重新批准的是审查过的新版本，摘要、发布者证据和批准时间都换成新的；只把旧 pin 的隔离清掉，旧摘要还留着，新版本永远是 rug pull。
- **读不了就报错**：文件不存在是空清单；JSON 坏了、空文件、结构不对都包成 ValueError。把坏文件当空清单，所有批准会悄悄消失，接下来每个工具都变成 unknown，审查队列一下子涌进几百条，真正的问题反而被淹掉。
- **多写者**：网关刷新时写隔离，审查工具写批准，两个进程共用一个文件。打开时读一次、以后只用内存副本的写法，会看不到对方的写入，下次保存还会把它覆盖掉。参考答案每次都重新读文件。真正同时写还需要文件锁，测试没有覆盖。
- **原子写**：先写同目录的临时文件、fsync，再 `os.replace`。写到一半崩溃时旧清单还是完整的。这一章别的题已经考过崩溃恢复，这里只在追问里讨论。

## Part 3 刷新判定

```python
if findings:
    status = BLOCKED
elif pin is None:
    status = QUARANTINE_UNKNOWN
elif pin.digest != digest or pin.quarantined_at is not None:
    status = QUARANTINE_CHANGED
else:
    status = APPROVED
```

顺序就是规则：

- 扫描命中排第一，不管有没有 pin、摘要对不对。课里 Hash equality proves stability, not safety：issues.search 是带着隐瞒指令被 pin 上的，照样拦下。
- 没有 pin 就是 unknown。pin 是按限定名查的，mirror.search 和 notes.search 一字不差也没用：如果“摘要在清单里出现过”就放行，任何服务器抄一份已批准的描述就能混进来。
- 摘要不同，或者 pin 已经在隔离中，都是 changed。隔离会粘住，服务器把描述改回去也不会自动恢复，课里写的是 quarantine as a rug pull until re-approved。

`scan_descriptor` 用一个栈遍历整个 descriptor，对象和列表都往里走，把每个字符串值都交给 `scan_description`，最后按 INJECTION_PATTERNS 的顺序输出、每个标签一次。模型读到的是整个 descriptor，参数描述、参数 title、enum 值都是它会读的文字：mirror.export 的短链接就藏在 destination 的 enum 列表里。

输出部分：visible 只放 approved，每个都是改名成限定名的副本，按名字排序；notes.stats 没有重名也叫 notes.stats，名字不会因为别的服务器上线而改变。shadowed 列出被两个以上服务器提供的裸名；removed 是这次谁都没有列出的 pin。整个结果和服务器、工具的顺序无关，课里 Never let discovery order decide which wins。

`Gateway.refresh` 在判定之后只做一件写操作：pin 过的工具摘要变了，就在清单里记隔离，时间用传进来的 `at`。这里比较的是摘要，不是 status：issues.search 那次改动被扫描拦下，status 是 blocked，可它同样是 rug pull，也要记下来，否则服务器改回原样，它就直接回到 approved。新工具一律不 pin，不管见过几次。反过来，摘要没变的工具即使被扫描拦下（测试里的 notes.rotate 是审查员看过的误报），也不记隔离：它没有变过，拦下它的是扫描规则。

## Part 4 分页决策流

每个后端只跟踪最新的 listing 号和这个列表攒到的工具：

```python
async for page in pages:
    seen = newest.get(page.backend)
    if seen is not None and page.listing < seen:
        continue                      # 旧列表迟到的页
    if seen is None or page.listing > seen:
        newest[page.backend] = page.listing
        open_listings[page.backend] = []   # 新列表开始，旧的作废
    tools = open_listings.get(page.backend)
    if tools is None:
        continue                      # 这个列表已经判过
    tools.extend(page.tools)
    if not page.last:
        continue
    del open_listings[page.backend]
    own = {k: p for k, p in pins.items() if k.partition(".")[0] == page.backend}
    result = refresh(own, {page.backend: tools})
    ...  # decisions 加 removed，按 key 排序，每个一行 JSON
```

- 只有最后一页到了才判。半个列表当成整个列表，后面页上的工具会被报成 removed，模型看到工具下线又上线。
- 判定直接复用 Part 3 的 `refresh`，只交给它这个后端自己的 pin。用 `partition(".")[0]` 比较，`startswith("notes")` 会把 notes_archive 的 pin 算进来。
- listing 号更大的是新列表。后端在被列举时工具变了，网关会重新列一次，没列完的旧列表作废，旧列表后面才到的页都忽略。判完的后端以后还会有新列表，照常处理。
- 一个列表一完成就判、就输出，不等别的后端。async generator 天然是拉一页处理一页，测试的探针数过：第一条事件出来时，慢后端那 500 页一页都没被拉走。
- 流结束时没完成的列表不判。
- 每个事件 `json.dumps(event) + "\n"`。测试把所有块拼起来、按 `\n` 切开，所以一批放在一个块里也行，但每个事件必须正好占一行。

## Part 5 审计脱敏

分两步：先在原记录上把每条策略路径命中的位置找出来，再重建一份副本，遇到命中的位置就整个换成摘要，不再往里走。

```python
targets = set()
for steps in [parse_path(p) for p in paths]:
    targets.update(_locate(record, steps, ()))
return _rebuild(record, (), targets, key)
```

- `_locate` 按步走：字符串步只进对象里存在的键，`None`（`[*]`）只展开列表。走不通就什么都不产出，所以不存在的路径、穿过字符串的路径、`[*]` 碰到对象，都自然跳过。
- `_rebuild` 从根往下复制，先检查当前位置是否命中，所以外层路径总是先被遇到，里面的路径失效，摘要的是记录里原来的值。策略里两条路径谁在前都一样。
- 摘要是 `"hmac-sha256:" + HMAC-SHA256(key, canonical_json(value))`。canonical_json 让键序不同的同一个对象得到同一个摘要，不同记录之间能对账；用 HMAC 而不是普通 SHA-256，是因为短秘密可以穷举。
- 原记录一个字节都不改，网关写完审计还要拿原来的参数去执行调用。
- 路径先全部解析，解析不了就报 ValueError，再动记录。

## 这套题证明了什么，没证明什么

通过了说明你能在这个规模的代码里顺着调用链调试，能把带时区、带隔离状态的 pin 存进一个多进程共用的 JSON 文件，能按课里的四条规则写出刷新判定，能写出按后端分批、互不阻塞的异步事件流，以及按路径处理嵌套记录。它不涉及课里的另一半：请求元数据和 Streamable HTTP 路由头的校验（-32020、-32022）、MRTR 的 requestState 签名和重放存储、按 principal 授权和限流。这些要回到 `code/main.py` 和练习 1 到 3 自己动手做。
