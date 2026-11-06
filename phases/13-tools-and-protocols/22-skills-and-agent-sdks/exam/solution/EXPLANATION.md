# 参考答案讲解：SkillPack（13/22）

计时结束后再看。参考实现在同目录的 `skillpack/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修 frontmatter 和命名

**现象**：解锁后的第一个错误是 `FrontmatterSyntaxError: SKILL.md must begin with an exact --- line`，出在 Windows 换行的那份文件上。文件第一行明明就是 `---`。

**顺着往下找**：这句报错来自 `parse_frontmatter` 的第一个检查，`line_content(raw[0]) != "---"`。打印 `repr(line_content(raw[0]))` 得到 `'---\r'`：`line_content` 只去掉了 `\n`，`\r\n` 里的 `\r` 留在了行里。报错的位置是对的，错的是它下面那一层。

**依次修五处**：

1. `line_content` 先看 `\r\n`，再看 `\n`：

   ```python
   if line.endswith("\r\n"):
       return line[:-2]
   if line.endswith("\n"):
       return line[:-1]
   return line
   ```

2. `decode_scalar` 的单引号分支改成 `value[1:-1].replace("''", "'")`。YAML 的单引号标量里，`''` 代表一个 `'`，本课 `code/main.py` 也是这么写的。
3. `NAME_PATTERN` 改成 `[a-z0-9]+(?:-[a-z0-9]+)*`，配合 `fullmatch`：小写字母和数字成组，组与组之间只能有一个连字符，不能出现在两头。
4. `parse_frontmatter` 在写入任何顶层字段前检查 `key in fields`，出现过就抛 `FrontmatterSyntaxError`，不能让第二次赋值盖掉第一次。两个值相同也不行，first-wins 和 last-wins 都不是合法解析。这个检查放在标量、块标量和 metadata 分支之前；metadata 内部的重复检查本来正确，不同映射可以各有同一个键。目录的 exact 比较已经给定，不能改成 lower 或 casefold。
5. `split_lines` 改成按位置切，不再每行复制一次剩下的文本：

   ```python
   start = 0
   while start < len(text):
       cut = text.find("\n", start) + 1 or len(text)
       lines.append(text[start:cut])
       start = cut
   ```

   原来的 `rest = rest[cut:]` 每切一行，就要把后面的全部文本复制一遍。5 万行、2.6 MB 的文件，本机实测要 1.0 到 1.9 秒；改完以后中位数 5 到 9 毫秒。更快的写法是找到结束行就停，正文直接用 `text[offset:]` 切出来，不到 0.1 毫秒。

**护栏**：

- CRLF 只去掉行尾的 `\r`。用 `strip()` 会把块标量和 metadata 下面的缩进也去掉，缩进行变成顶层行，第一条断言就报 `malformed top-level line 4`。
- 名字规则不能收得太紧：`2fa-helper`、`v2`、`a`、`skill-contract-reviewer`、64 个 `x` 都合法。要求字母开头、只许一个连字符、不许数字，都会挂。`re.match` 不检查到结尾，`release-` 会漏过去；`isalnum()` 认任何文字，`café-notes` 会漏过去。
- 提速不能改语义：结束行可以是文件的最后一行，后面没有换行；结束行可能是 `---\r\n`，正文要从它后面开始。用 `text.find("\n---\n")`、固定加 4 个字符、`split("\n")[:-1]` 都会在其中一种文件上出错。
- `splitlines(keepends=True)` 能通过测试，但它会在 U+2028、换页符、单独的 `\r` 处断行。docstring 说只有 `\n` 结束一行，这个解析器里的 `split_lines` 就是按这个写的。

## Part 2 写回 SKILL.md

参考实现逐个字段写一行。字符串值先判断能不能写成 plain，不能的话，带换行且能放进 `|` 块的写成块，其余用 `json.dumps(value, ensure_ascii=False)` 写成双引号：

```python
def _plain_ok(value, typed):
    if not value or value != value.strip() or value[0] in INDICATORS:
        return False
    if ": " in value or " #" in value or value.endswith(":") or not value.isprintable():
        return False
    if typed and (value[0] in "0123456789.+~" or value.lower() in YAML_WORDS):
        return False
    return True
```

- **为什么要两套检查**：测试有两类断言。一类是读回来要完全一致，这抓的是本课解析器自己会读错的写法：首尾空白会被去掉，以 `'` 或 `"` 开头会被当成引号，`|` 和 `>` 会被当成块标量，`[ { & * !` 会被拒绝。另一类是精确文本，抓的是本课解析器读得对、真实 YAML 会读错的写法：`": "` 和行尾的 `:`、`" #"` 开始的注释、`#` 开头的整行、空值读成 null、`22` 读成数字。宿主用的是完整的 YAML 解析器，两类都得对。
- **类型规则只给核心字段和 metadata**：可移植合同里它们都是字符串，`lesson: "22"` 是本课自己的写法。运行时扩展字段的类型由宿主决定，`user-invocable: false` 要保持成 YAML 的布尔值。
- **`|` 块的条件**：本课的解析器把块里每一行 `lstrip()`，再把整个值 `strip()`，还把 `\r\n` 当成换行。所以只有不以空白开头和结尾、没有 `\r`、每行都可打印且不以空白开头的值，写成块才能原样读回。其余的退回双引号。metadata 的值从不写成块，嵌套映射只读 `key: scalar`。
- **正文原样**：结束行后面直接接正文，不加空行，也不 strip。本课自己的 SKILL.md 正文以一个空行开头，第一条断言就是它。
- **装不下就拒绝**：键必须符合字段名规则（`allowed_tools` 写进去，解析器读回来会报语法错误），值必须是字符串，metadata 必须是非空的一层字符串映射。

## Part 3 有序问题码

照 docstring 的顺序一条一条写，每一行最多出一个问题：

```python
allowed = set(allowed_runtime_extensions)
try:
    fields, body = parse_frontmatter(text)
except FrontmatterSyntaxError as error:
    return SkillReport(False, None, None, "", (), (), (ValidationIssue("frontmatter-syntax", str(error)),))
```

- 语法错误直接返回，只有一条。剩下的规则依次是 name（交给 `name_issue`）、description、compatibility、metadata、allowed-tools、正文、扩展字段。
- 空白一律算缺失：`description.strip()`、`compatibility.strip()`、`body.strip()`。正文在 Part 1 里原样保留，所以只有空行的正文必须用 `strip()` 判断。
- 长度用 `len()`，按字符。1024 个汉字是 3072 个字节，仍然合法。
- allowed-tools 要有至少一个工具名，工具之间只能是空格：`any(c.isspace() and c != " " for c in tools)` 就是形状错误。
- 扩展字段按名字排序，宿主没有允许的每个出一条。`allowed_runtime_extensions` 先转成 set，传进来的可能是一次性的迭代器。
- `runtime_extensions` 列出全部非核心字段，包括允许的那些，这样同一个文件在“只认便携核心”和“认这个宿主的扩展”两种策略下，报告都能看出它带了扩展（本课练习 3）。

## Part 4 生命周期 TAP 检查

每个 skill 一个会话对象，记下已经发生的阶段、校验是否失败、有没有未验证的工具调用，以及第一个问题：

```python
async for event in events:
    skill, stage = event["skill"], event["stage"]
    session = sessions.get(skill)
    if session is None:
        session = sessions[skill] = _Session()
    if stage == "ended":
        del sessions[skill]
        count += 1
        yield _line(count, skill, session.verdict())
    else:
        session.see(stage, event)
for skill, session in sessions.items():
    count += 1
    yield _line(count, skill, session.reason or "session not ended")
yield f"1..{count}\n"
```

- **结论什么时候出**：收到 `ended` 就 yield，编号跟着结束的顺序走。`ended` 时把会话从字典里删掉，同一个 skill 再出现时就是新会话，旧状态不会带过去。
- **规则的先后**：`see()` 先看校验是否已经失败，再看 NEEDS。deploy-helper 校验失败后被直接激活，原因是 `activated after failed validation`。校验失败以后的任何阶段都算，包括 cataloged：坏包不能进目录。只有校验失败、后面什么都没发生，不算失败：宿主做对了。
- **工具调用要被验证**：`tool_called` 把标记置上，`verified` 把它清掉，会话结束时标记还在就是 `tool_called not verified`。所以 changelog-style 先验证、后来又调用一次，结果仍然是失败。
- **流结束**：字典按插入顺序保存还开着的会话，也就是它们开启的顺序。每个出一行，原因是它的第一个问题，或者 `session not ended`，最后是计划行。
- 格式由测试的解析决定：每行一个 `\n`，计划行在最后，没有会话时是 `1..0`。

## Part 5 工作流依赖边

先用 Part 1 的解析器取出正文，把代码块里的行换成空行（保留行数），再在剩下的文本上找引用和护栏：

```python
REFERENCE = re.compile(r"\b[Ii]nvoke\s+the\s+`([a-z0-9]+(?:-[a-z0-9]+)*)`\s+skill\b")
GUARD = re.compile(r"\b[Ii]f\s+that\s+skill\s+is\s+unavailable\b")
```

- `\s+` 让短语可以跨行；名字必须在反引号里，而且符合命名规则；`[Ii]` 同时认句首和句中。
- 代码块从一行去掉缩进后以 ```` ``` ```` 开头算起，到下一个这样的行为止。列表项里的代码块通常是缩进的。
- 把引用和护栏按位置排在一起，从前往后走：遇到引用就记下来，遇到护栏就把最近一个引用标成有护栏。一条边只要有一次引用没被标上，就是 unguarded。
- 安装顺序：一个技能的轮次是 1 加上它在集合里的依赖的最大轮次，没有依赖就是 1，用递归加缓存算。然后按（轮次，名字）排序。缺失的依赖不在集合里，不参与轮次计算，所以 incident-triage 在第一轮、release-risk-review 在第二轮。
- 为什么缺失的依赖不挡安装：技能之间没有 import，第二个技能要在运行时经过发现、资格检查和激活。依赖不在的时候，护栏写明了怎么办（停下并报告，或者换一个明确的回退），所以要单独报告的是没有护栏的边。

## 这套题证明了什么，没证明什么

通过了说明你能在一个小的 frontmatter 解析器里顺着报错找到下一层的根因、拒绝会覆盖配置的重复字段、按规格写出能被真实 YAML 读对的写回逻辑、按固定顺序做包校验、写一个按会话实时出结论的流式检查器，以及从正文里抽出依赖图并按轮次排序。它没有用真实的 YAML 库对拍，也没有在真正的宿主里安装、发现和调用技能。讲义开头的 Ten-Minute First Success（用 `npx skills add` 安装、显式调用、清理）需要另外动手做，而技能发现、路由、权限和评测分别是第 24 到 27 课的内容。
