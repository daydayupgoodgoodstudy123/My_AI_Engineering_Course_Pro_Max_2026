# 参考答案讲解：ToolLint（13/05）

计时结束后再看。参考实现在同目录的 `toollint/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修 linter

**现象**：解锁后的第一个错误是 `lint_name` 里的 TypeError（`argument of type 'NoneType' is not iterable`，Python 3.14 的措辞略有不同），而 `lint_name` 本身没有 bug。

**顺着往上找**：`params` 是 None。它是 `lint_tool` 传进来的 `schema.get("required")`，而课里 BAD_REGISTRY 的三个 schema 都没有 required 列表。第一个工具 `DoEverything` 的名字不匹配 `_(in|for|at|by)_x` 的正则，`m and ...` 短路了，到第二个工具 `get_weather_in_tokyo` 才真正去查 `"tokyo" in None`。这一关想练的是：报错的位置往往不是出 bug 的位置。

**依次修四处**：

1. `lint_tool`：参数是 input schema 的全部 properties，`lint_name(name, schema.get("properties", {}))`。只把 None 改成空列表不够：`notes_export_for_user` 的 `user` 是可选参数，不在 required 里，照样会被报成“参数写进了名字”。这正是课里规则 6 的意思，`get_weather_for_city(city)` 写的是参数名，`get_weather_in_tokyo()` 写的是参数值。
2. `lint_description`：长度用 `len(desc)`。`len(desc.encode())` 数的是 UTF-8 字节，一个汉字占 3 个字节，696 个字符的描述被算成 1,896，超过了课里的 1024 字符上限。
3. `duplicate_names`：每个重复的名字只列一次。
4. 同一个函数：`names.count(name)` 每次都扫一遍整个列表，2 万个名字大约 2 秒。用 `Counter` 数一遍就够了，而且 `Counter` 按插入顺序保存键，第一次出现的顺序是现成的：

```python
counts = Counter(names)
return [name for name, n in counts.items() if n > 1]
```

**护栏**：提速最常见的写法是 `set`。`sorted(set(...))` 的顺序是字母序，`list(set(...))` 的顺序每次运行都可能不同，用 seen 集合在第二次见到时记下来，得到的是第二次出现的顺序；`Counter.most_common()` 按次数排，测试里 `notes_list` 出现 3 次、`notes_search` 2 次，次数多的反而后出现。测试要的是第一次出现的顺序。只报一条 “registry has duplicate tool names” 也不行，CI 日志要指出是哪个名字。另一种“提速”是每个名字只 lint 一次，第二个副本自己的 finding 就丢了。

## Part 2 内容寻址的发布库

目录结构在 `ReleaseStore` 的 docstring 里：`blobs/<digest>` 存每个不同的 descriptor，内容是 `encode_descriptor()` 的字节，文件名是这些字节的 SHA-256；`releases/<version>.json` 是清单，按发布顺序把工具名映射到摘要。

```python
path = self._manifest_path(version)          # 先校验版本号
if path.exists():
    raise ValueError(f"release {version} already exists")
for tool in tools:                            # 先全部校验、算好摘要
    ...
for digest, data in blobs:                    # 再写 blob，已有的跳过
    if not (self.blobs / digest).exists():
        _write_atomic(self.blobs / digest, data)
_write_atomic(path, json.dumps(manifest).encode("utf-8"))   # 清单最后写
```

容易漏的几点：

- **语义版本排序**：`parse_version` 返回 `(major, minor, patch)` 三个整数，`versions()` 用它做 key。字符串排序会把 1.10.0 排到 1.2.0 前面；把点去掉当整数排，1.2.10 变成 1210，排到了 1.10.0（1100）后面。
- **版本格式**：用 `re.fullmatch(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", version)`。`int()` 接受 `"02"`，也接受 `"0\n"`；`re.match(... + "$")` 也会放过末尾的换行。
- **发布顺序和版本顺序不是一回事**：1.9.1 和 1.2.10 在 1.10.0 之后才发布，`versions()` 和 `history()` 都按版本号排。
- **相等不等于相同**：重新生成的 schema 把 `maximum: 50` 写成了 `50.0`。Python 里 `50 == 50.0`，两个 dict 也相等，但它们的字节不同、摘要不同，是两个 blob。拿 `==` 判断“没变就复用上一版的摘要”，1.10.0 就会读回 50。测试用 `encode_descriptor` 比较读回的结果，int 和 float、中文描述的字节都要一致。
- **读的时候校验**：`load` 对每个 blob 读到的字节重新算 SHA-256，和清单里的摘要不一致就报 ValueError。先 `json.loads` 再拿 `descriptor_digest` 重算，校验的是重新编码后的内容：blob 末尾多一个换行，解析结果不变，摘要也不变，查不出来。测试先加一个换行，再把一段文字改成另一段合法的 JSON，所以光靠 `json.loads` 报错也不够。
- **不可变、先校验再写**：同一版本再发一次、一个版本里两个同名工具、格式不对的版本号，都在写任何文件之前报 ValueError，所以被拒绝的发布不会留下 blob。测试里这三种被拒的发布都带着一个新的 descriptor，哪一项检查放到写 blob 之后，`blobs/` 里都会多一个文件。
- **未知版本**：`_manifest` 先判断清单在不在，不在就报 KeyError，不要让 FileNotFoundError 漏出去。

## Part 3 破坏性变更分类

先按名字把两个版本的工具对上，再逐个比较参数：

```python
for name, tool in before.items():
    if name not in after:
        changes.append(Change(name, "removed", "safe" if tool.get("deprecated") is True else "breaking"))
for name, tool in after.items():
    if name not in before:
        changes.append(Change(name, "added", "safe"))
        continue
    if tool.get("deprecated") is True and before[name].get("deprecated") is not True:
        changes.append(Change(name, "deprecated", "safe"))
    changes.extend(_parameter_changes(name, before[name], tool))
return sorted(changes)
```

每条规则都来自课里 Versioning 一节：

- **不改名**：按名字匹配，改名就是一条 removed 加一条 added，removed 是破坏。不去猜哪个新工具是旧工具改的名。
- **不改参数类型，放宽也不行**：类型先归一成集合，`"string"` 和 `["string"]` 相同，`["string", "number"]` 和 `["number", "string"]` 相同；没有 type 记作 None，表示接受任何类型。集合不同就是 type changed，放宽（string 变成 string 或 number）同样是破坏，课里写明了 "requires a new version"。
- **可以随时加可选参数**：新参数不在 required 里是 added optional（safe），在 required 里是 added required（breaking）。同理，可选变必填是 breaking，必填变可选是 safe，删掉参数是 breaking。没有 required 列表时，什么都不必填；没有 properties 时，没有参数。新加的工具只报一条 added，它的参数不逐个报。
- **删除要有弃用窗口**：只有旧版本里标了 `deprecated: true` 的工具，删掉才是 safe。标记要在旧版本里找，新版本里已经没有这个工具了。标记出现的那一版报一次 deprecated，之后一直带着这个标记不再重复报。

一个参数可以一次变好几处。把 `units` 改成 strict 模式的写法（全部字段 required、原来可选的改成可空 `["string", "null"]`），既是 made required 又是 type changed，所以这几个判断是并列的 `if`，不是 `elif`。最后按 (path, change) 排序，`Change` 是 NamedTuple，直接 `sorted` 就是这个顺序。

端到端那一段用的是给好的 `ToolRegistry`：lint 出 block 或者出现 breaking 变化就拒绝发布。它走的是课里的路子：`get_weather` 直接改名被拒；先加 `get_weather_v2` 并把 `get_weather` 标成 deprecated，发 1.1.0；2.0.0 再删掉 `get_weather`。补丁版本 1.0.1 和它下面的 1.0.0 比较，所以加一个可选参数是安全的。

## Part 4 分页注册表的流式检查

```python
async for page in pages:
    for tool in page:
        name = tool.get("name", "")
        found = []
        if name not in seen:
            seen.add(name)
        elif name not in reported:
            reported.add(name)
            found.append(Finding("block", name, "duplicate tool name"))
        if baseline is None or baseline.get(name) != descriptor_digest(tool):
            found.extend(lint_tool(tool))
        for finding in found:
            logged.append(finding)
            yield str(finding)
yield summary_line(logged)
yield "FAIL" if any(f.severity == "block" for f in logged) else "PASS"
```

- **格式**：每行就是 `str(finding)`，`{severity:5s}` 把 warn 补成 `[warn ]`。测试按 `[block]`、`[warn ]`、`[nit  ]` 这三个前缀数行数，再和 summary 里的数字对。
- **重复名**：流式时不知道后面还有什么，只能在第二次见到时报，报一次，放在这个副本自己的 finding 前面。这和 Part 1 的批量结果顺序不同：批量时所有重复都放在最前面。第二个副本照常 lint。
- **baseline**：上一版的清单（Part 2 存的那种）。摘要一样就说明工具没变，不再 lint，但名字照样记进 seen，否则 PR 新加了一个同名工具也发现不了。按名字判断会漏掉改过描述的工具，不在 baseline 里的新工具当然要 lint。
- **结论**：只有 block 让构建失败，这是练习 4 的要求；课的 skill 输出也是“每条 finding 一行，然后是 summary 和 pass/fail 结论”。空注册表照样输出 summary 和 PASS。
- **及时输出**：一页查完就输出，不预读下一页。测试拿第一行时检查只拉取了第一页。

## Part 5 描述的交叉引用图

引用的语法用一条正则表示：

```python
REFERENCE = re.compile(r"\b(?i:use)\s+`?([a-z][a-z0-9]*_[a-z0-9_]*)")
```

- `\b` 让 "reuse" 里的 use 不算；`(?i:use)` 只让 use 这个词不分大小写，句首的 "Use notes_list" 也算；工具名必须带下划线，所以 "use when"、"use for"、"use this" 都不是引用；名字里可以有数字和多个下划线（`maps_route_v2`），名字后面的 `.`、`)`、`,` 和反引号都不在字符集里，自然被排除。
- 同一个工具提到几次都只记一条边：`list(dict.fromkeys(found))`，保留第一次提到的顺序。

`check_references` 先逐个工具报自引用和悬空引用。课里的 GOOD_REGISTRY 正好有两条悬空引用：`notes_list` 指向 `notes_get`，`notes_create` 指向 `notes_update`，注册表里都没有，和测验 Q11 的结论一致。悬空引用指注册表里没有的任何名字。测验 Q11 的 `lint_cross_refs` 只查和已有工具同前缀的名字，这里不加这个限制：`geo_lookup` 指向的 `maps_route_v2`，maps 前缀在注册表里一个工具都没有，也要报。

然后是命名空间分组。同一个前缀（第一个下划线之前的部分）下的工具是彼此的近邻，它们的 "Do not use for" 应该把它们连起来。对每一组，只用组内两个工具之间的引用建一张无向图，求连通块：

- 方向不限：`notes_search` → `notes_list` 只有一个方向，也算连上。
- 只算组内的边：`weather_alerts` → `geo_lookup` → `weather_now` 绕到别的命名空间，不能把 `weather_alerts` 和 `weather_now` 连起来。
- 不存在的工具不是节点：`notes_archive` 和 `notes_purge_all` 都指向不存在的 `notes_trash`，不能因此连在一起。

块数大于 1 就报一条 nit，块内名字排序，块按第一个名字排，分组按前缀排。参考实现用的是从排好序的成员出发的迭代 DFS，并查集也一样。

## 这套题证明了什么，没证明什么

通过了说明你能在 linter 这样的规则代码里沿着调用链找根因、设计一个内容寻址的发布库、把课里的版本规则写成可执行的兼容性检查、写一个按页流式输出的 CI 检查，以及在描述的引用上做图的连通性分析。它不证明这些规则真的能提高工具选择的准确率：课里引用的 StableToolBench、MCPToolBench++ 这类评测需要真实模型来跑，正则式的启发规则会有误报和漏报，也没有涉及工具投毒的系统防御（第 15 节）和 strict 模式下的 schema 约束（第 02、04 节）。
