# 参考答案讲解：SkillCat（13/24）

计时结束后再看。参考实现在同目录的 `skillcat/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修发现流水线

**现象**：解锁后的第一个错误是 `resolve_collisions` 里的 `CollisionError: ambiguous 'release-readiness' at rank 0`，而冲突检查本身没有 bug。

**顺着往上找**：消息里列了两条路径，第二条是 `skill-author/examples/release-readiness`。那是 skill-author 包里给作者看的示例，不是一个已安装的包。它会出现，是因为 `package_dirs` 用 `rglob("SKILL.md")` 递归找文件，而 docstring 写的是“只有 scope 根目录的直接子目录才是包”。讲义 “Why discovery is shallow” 一节讲的就是这件事：递归会把包里的示例和测试夹具当成独立的 skill 发布出去。这一关想练的是：报错的位置往往不是出 bug 的位置，这里根因甚至不在 traceback 的调用链上。

**依次修四处**：

1. `package_dirs`：只遍历 `root.iterdir()`，保留里面有 `SKILL.md` 的目录，按名字排序。
2. `resolve_collisions`：排序键改成 `(c.rank, str(c.source))`。原来路径排在前面，等于按目录名字母序选赢家，讲义说 "Never invent precedence from directory names"。路径只用来让同 rank 的报错信息稳定。
3. `validate_reference`：先 `resolve()`，再判断 `root in target.parents`。原来判断的是没解析过的路径，它在字面上永远在包里，指向包外的符号链接就这样漏过去了。讲义的原话是 "verify that the resolved candidate remains under the resolved root"。
4. `build_catalog`：讲义代码的 while 循环每弹出一个条目就重新序列化整个目录，n 个条目是 O(n²)，1800 个条目要 2 秒左右。条目在 `model_json` 里的长度是可加的：外壳 `{"entries":[]}` 的 14 个字符，加每个条目自己的 JSON，再加条目之间的逗号。所以一遍累加，第一次放不下就停。

**护栏**：

- 删掉平票检查能让第一个错误消失，但同 rank 的两个 `pdf-tools` 就会被静默选掉一个。正确的修法在发现那一层。
- 拒绝所有符号链接也能挡住逃逸，但宿主策略允许包内的链接，`latest.md -> python-release.md` 必须能读。
- 只看最后一段是不是链接不够：`references/vendor` 这个目录本身就是指向包外的链接。
- 包根和目标都要 resolve：测试故意从一个符号链接的根目录访问同一个包。
- 累加长度时，`catalog_chars` 必须等于 `len(model_json(entries))`。漏掉逗号、换了分隔符、放不下就跳过去试下一个、omitted 的顺序反了，测试都会抓住。

## Part 2 发现结果的 JSON 快照

参考实现的快照是一个 JSON 文件：`{"version": 1, "packages": {目录路径: 记录}}`。每条记录有 `SKILL.md` 字节的 SHA-256，再加上检查结果：合格的存 name、description 和 metadata，被拒的存原因。

`discover(scope)` 用 `package_dirs` 列出磁盘上现在的包，逐个算摘要：

- 快照里没有，或者摘要变了，就用 `inspect_package` 重新检查，记进 `parsed`，结果直接返回；
- 摘要没变，就用记录重建结果，scope 和 rank 用这次调用的 scope；
- 磁盘上已经没有的包，从快照里删掉；别的 scope 的记录不动；
- 最后先写临时文件，再 `os.replace` 换上去。

几个要点：

- **按内容判断**：编辑可以保持大小和 mtime 不变，文件系统的 mtime 精度也有限。测试改了一个字符，再把纳秒级 mtime 改回去。摘要要用 SHA-256 这种跨进程稳定的算法，内置的 `hash()` 对 bytes 每个进程加的盐不同，下一个会话就全部失效；测试检查快照里存了 SHA-256。
- **身份是目录**：同一份字节装在两个目录里是两个包。`incident-review-old` 的名字和目录不符，必须被拒绝，按摘要查表会把它当成合格候选。这正是讲义 "Collisions need identity beyond name" 的另一面。
- **策略不进缓存**：scope 的名字和 rank 属于宿主策略，讲义 Use It 第 10 条说安装或策略变了就要重建目录。参考实现只缓存从文件里检查出来的东西，scope 每次现盖。
- **类型要还原**：JSON 读回来是 list 和 str。metadata 要变回二元组的 tuple，source 要变回 Path，否则重开以后的比较不相等。
- **失败也是结果**：被拒的包和它的原因同样进快照，讲义要求每一级都产出“结构化的失败”。

## Part 3 目录预算

预算规则照讲义里的 Codex 现行策略：上下文窗口大小已知时，目录占窗口的 2%，按 token 计，向下取整；只有窗口未知时，才用 8,000 字符兜底。两者不叠加，窗口已知时不能再用 8,000 字符卡一次，窗口为 0 是错误，不是“未知”。

`fit_catalog` 的成本永远量 `model_json(entries)` 这段精确文本：token 预算用 `count_tokens`，字符预算用 `len()`。键名、引号、转义、source 路径都算在里面，中文字符按一个字符算，不按 UTF-8 字节算。

超预算时：

1. 从优先级最低的条目开始，一条一条把超过 `SHORT_DESCRIPTION_CHARS` 的描述用 `shorten()` 缩短，每缩一条重新量一次，放得下就停；
2. 全部缩短后还放不下，再从优先级最低的开始省略条目。

成本刚好等于预算算放得下：测试里有一个窗口，它的 2% 正好是完整目录的 2,511 个 token，这时一条都不缩短。

被省略的条目只出现在 omitted 里。name 从不缩短，它是身份。优先级是 (rank, name)，和输入顺序无关，所以测试传进来的是打乱的列表。

这组 33 个 skill 的完整目录是 8,415 个字符、2,511 个 token：窗口未知时缩短 5 条；120,000 的窗口（2,400 token）缩短 7 条；40,000 的窗口（800 token）全部缩短后还要省略 21 条。

参考实现每缩短或省略一条都重新量一次。几十个条目时这样最简单；条目上千时，成本随缩短数和省略数单调下降，可以二分。真实的 tokenizer 不能按条目相加，所以只能量最终文本。

## Part 4 logfmt 披露事件

`disclosure_events` 是一个 async generator：每来一个请求处理一个，立刻 `yield` 一行。会话状态只有一张表：已激活的 skill → 它的决策图（`decision_map(body)`）。

读取请求按顺序检查：skill 没激活 → `not_active`；决策图里没有这个资源 → `not_declared`；`validate_reference` 拒绝 → `invalid_path`；超过 `max_read_bytes` → `too_large`。几条同时成立时取第一条，所以没声明的 `../incident-review/SKILL.md` 报 `not_declared`。读文件时只读 `max_read_bytes + 1` 个字节，多出 1 个字节就说明超限，不用把大文件整个读进来。字节数都按 UTF-8 计：1,000 个字符的德文文件有 1,088 个字节，要拒绝；刚好 1,024 个字节的文件可以读。

`format_event` 的规则：值是空的，或者含空格、`=`、`"`、反斜杠、控制字符，就加引号，里面的反斜杠、引号、换行、回车、制表符分别写成 `\\`、`\"`、`\n`、`\r`、`\t`，其余控制字符写成 `\u00XX`；别的值直接写。测试的解析器很严格，原样放一个空格或换行进去，一行就会被拆坏。

事件里只有 skill、资源、原因和字节数，从不放内容。讲义 "Loading must be observable" 一节给的就是这几个字段：原因让每次往上下文里加东西都有据可查。

## Part 5 引用图一跳可达

从 `SKILL.md` 开始做广度优先搜索，每个文件第一次被发现时的跳数就是最少跳数。对每个 Markdown 文件：

- 跳过围栏代码块里的行（``` 和 ~~~，按开头的那种符号配对）；
- 用 `LINK` 找出 `[text](target)`，去掉 `#fragment` 和 `?query`；没剩下东西，或者带 scheme（https:、mailto:），就不是引用；
- 目标相对于当前文件所在的目录拼接，再用 `posixpath.normpath` 规范化；以 `/` 开头或者跑到 `..` 外面的是坏链接，哪怕那个文件确实存在；坏链接报告的是去掉片段和查询之后的写法；
- 指向目录的链接记进 directory_links，不展开；不存在的文件记进 broken；存在的文件第一次见到就记下深度、入队；
- 只有 `.md` 文件会继续读链接，脚本和资源只算节点。

最后，跳数大于等于 2 的是 deep，`references/` 下面没被走到的文件是 dead。

用 DFS 会错：先沿着 python-release.md 走下去，container-release.md 就被记成 2 跳，后面的文件跟着全错。讲义 "Branch-specific references beat topic dumps" 说要让引用图保持一跳：每个引用都由 `SKILL.md` 直接点名，并写明加载条件。这份报告给出的正是要修改的地方：四个 deep 文件、两个死文件，以及一句没有条件的 "read the references for more"。

## 这套题证明了什么，没证明什么

通过了说明你能在这个规模的代码里调试一条多级的发现流水线，守住包内路径这道信任边界，设计一个按内容失效的缓存，实现宿主的目录预算策略，写一个即时输出的结构化日志流，以及在文件之间的链接图上做最短路径分析。

它不涉及真实的 YAML 解析和 frontmatter 校验（第 22 课），不涉及按相关性路由和激活（第 25 课），也不涉及引用内容本身是否可信、沙箱和权限（第 26 课）。题里的 tokenizer 是一个按词和标点计数的替身，真实宿主的 token 数会不同；2% 和 8,000 字符是讲义所说的 Codex 当前策略，不是 Agent Skills 标准的一部分。
