# 参考答案讲解：SandboxPol（13/26）

计时结束后再看。参考实现在同目录的 `sandboxpol/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修审查器和闸门

**现象**：解锁后第一个失败是 “a non-default port is a different origin”：`https://api.example.test:8443` 被当成了白名单里的 `https://api.example.test`。

**依次修五处**：

1. `origin_allowed` 用 `urlsplit(...).hostname` 只比主机。两边都已经是规范化的源，直接 `origin in set(allowed)` 整串比较就对了。
2. 改完第 1 条，“the default port is the same origin” 挂了：`https://API.example.test.:443/...` 被拒。往下一层看 `normalize_https_origin`，它只有 URL 自己写了端口才写端口，于是同一个源有两种写法，`https://api.example.test` 和 `https://api.example.test:443`。原来只比主机时，这个问题被盖住了。课里说源是 scheme、host 和有效端口，规范形式要把端口写出来：

   ```python
   if port is None:
       port = 443
   elif not 1 <= port <= 65535:
       raise ValueError("HTTPS origin contains an invalid port")
   return f"https://{origin_host}:{port}"
   ```

   不要写成课里的 `parsed.port or 443`：端口 0 是假值，`https://api.example.test:0` 会被当成 443 放行，quiz Q9 讲的就是这个。
3. `inspect_command` 只比可执行文件名，白名单里有 `python3 scripts/inspect_release.py`，`python3 -c ...` 和 `python3 -m http.server` 就都过了。恢复成逐个元素比较 argv 前缀，前缀后面的参数不管。整串拼起来比 `startswith` 不行，`scripts/inspect_release.py.bak` 会混过去。
4. `ActionGate.submit` 只拦 deny，require-approval 也被交给了 runner。改成只有 allow 才运行。批准过的 deny 仍然是 deny，`rm -rf out` 不管批没批都不跑；不需要批准的读要照常运行。
5. 最后是计时：`review_action` 审一个 10,804 字符的缓存键加一段 4 KB 的十六进制转储，要 1 秒多。慢在 `contains_secret` 的 key=value 规则，它前面多了一段 `[\w.-]*`，本意是把 `DB_PASSWORD` 这样的整个键名都匹配进来。可是 `contains_secret` 只回答“有没有”，`re.search` 本来就会在任何位置开始找，这段前缀对结果毫无影响。代价却很大：缓存键是一长串字母、数字和横线，每个起点都把 `[\w.-]*` 吃到串尾，再一个字符一个字符地退回来试关键词，总共是 O(n²)。去掉前缀，同样能在 `DB_PASSWORD=` 里找到 `PASSWORD=`，审一次只要 0.4 毫秒左右。只把前缀缩成 `\w*` 不够：缓存键那段被横线切短了，十六进制转储却是一整串 `\w`，还是平方级。

**护栏**：退回课里带 `\b` 的写法会漏掉 `DB_PASSWORD=`，因为 `_` 和 `P` 之间没有词边界。保留前缀、只在前面加 `\b` 也不行：横线把串切成了上千段，每段开头都是词边界，还是平方级。只扫前 4 KB、把所有长串都当秘密、把 PEM 规则放宽到任意 `BEGIN` 行，都会被后面那组检测断言抓住：证书和 sha256 摘要不是秘密，串尾的 `access_token=` 是。

## Part 2 安装库

参考实现的布局就是模块 docstring 里写的两部分：`blobs/<sha256>` 存内容，`packages/<name>.json` 存清单。`_capture` 递归遍历源目录，只收普通文件（遇到符号链接或特殊文件直接报错），对每个文件：

```python
rel = path.relative_to(source).as_posix()
data = path.read_bytes()
digest = hashlib.sha256(data).hexdigest()
executable = rel in reviewed and bool(path.stat().st_mode & 0o111)
```

- **可执行位**：两个条件都要满足。没被审查的 `postinstall.sh` 即使是 0o775 也丢掉执行位；被审查的 `render.py` 源文件没有执行位，也不加。这是课里第 7 条 “Preserve executable bits only for reviewed scripts that need them”。
- **按字节**：读写都用 bytes。CRLF、0x00 到 0xFF、空文件都原样还原。
- **去重**：blob 以内容的 sha256 命名，两份 LICENSE 只存一份，blobs 里正好 7 个。
- **权限**：还原时显式 `chmod(0o755 if executable else 0o644)`，不管源文件原来是 0o600 还是 0o666，也不依赖 umask：测试在还原时把 umask 设成了 0o077。
- **清单**：JSON，`sort_keys`，经临时文件加 `os.replace` 写入。重开后读出来的 Manifest 和写进去的相等。

升级分两步，对应课里第 9、10 条：

- `plan_upgrade` 先把新版本的内容存进 blobs，再和已安装的清单比：新增、改变（字节或可执行位任一不同）、删除，各自排序。只比摘要会漏掉 `render.py`：字节没变，只是多了执行位，而这恰恰是审查者最该看见的变化。做计划不改动已安装的清单。
- `upgrade` 只认计划里的 `target`，不再读源目录。测试在计划之后改了源目录里的 SKILL.md，升级装上的必须是审查过的那份。它还要求 `plan.base` 等于现在装着的清单，按旧版本做的计划拿到新版本上用，直接报 ValueError。审查和安装之间这段时间里发生的变化，都不能借着那次审查混进来。

还原时参考实现会重新算一遍 sha256，对不上就拒绝。测试不破坏 blob，所以这一点不考，留作追问。

## Part 3 启动计划

`plan_launch` 按 docstring 的顺序一路检查，第一条失败就返回一个什么都不带的 deny：

1. argv 交给 Part 1 修好的 `inspect_command`。
2. 每个路径用 `normalize_workspace_path` 解析成真实路径。读就是 read；写要看解析后的目标在不在，在就是 overwrite，不在就是 create。然后看这种操作的根里有没有一个包含它（根也先解析，再按路径组件比较）。
3. 每个 URL 先规范化成源，再过白名单。
4. 每个凭据要在策略里有作用域，而且作用域的源必须是这次请求要访问的源之一。

```python
if use.access == "read":
    operation = READ
else:
    operation = OVERWRITE if target.exists() else CREATE
if not _granted(root, policy.grants.get(operation, ()), target):
    return LaunchPlan(Verdict.DENY, f"path-{operation}")
```

`./out/tmp/../cache/index.json` 这一条同时考三件事：存在性要看解析后的路径（`out/tmp` 并不存在，拿原始路径去 `exists()` 会得到 False）；权限要按解析后的路径判断；后果里写的也是解析后的 `overwrite out/cache/index.json`。课里那句 "Approval must show the actual target and consequence" 落在这里。

后果按请求顺序列出：先是需要批准的路径操作，再是 `send <凭据> to <源>`。只要有一条不在 `approved` 里，判定就是 require-approval；全部批准了才是 allow，计划里仍然列着全部后果。批准了 index.json 不等于批准了 old.json，这是 "Do not interpret approval for one target as permission for later targets"。`side_effect` 是请求自己的说法，和 Part 1 里被忽略的 `claimed_permissions` 一样，不影响审查。

环境变量是白名单，不是黑名单：policy.env 加上 pass_env 里宿主确实设置了的变量，policy.env 优先。`HOME`、`SSH_AUTH_SOCK`、`NPM_TOKEN` 一个都进不去。凭据从不进环境变量，而是写进 `inject`，由出口代理只对那一个源附加。课里说 "Inject a credential only into the narrow tool that needs it ... and only for the intended destination"：进程拿不到令牌，就没法把它发到别处。

`follow_redirect` 把跳转当成一个新请求：先 `urljoin`，相对路径和 `//host/...` 都能正确解析；再规范化、过白名单；带的凭据只取 `plan.inject` 里给新源的那一份。所以同源跳转还带着 RELEASE_TOKEN，跳到 api.example.test 就不带了，跳到白名单外的源直接拒。

## Part 4 输出转发

参考实现把工作分给两个小类，`relay` 只负责读、超时和收尾：

- `_Redactor` 把收到的字节攒在 `_pending` 里，每来一块，就把除了最后 `最长秘密长度 − 1` 个字节以外的部分放出去。为什么正好这么多：凡是起点落在放出去那部分的秘密，整个都已经在缓冲区里了，用按长度从长到短排好的正则一次就能判断，最长的优先。测试同时注入了 `pypi-placeholder` 和 `pypi-placeholder-token`，先试短的就会漏出 `-token`。放出去之前还要看末尾有没有收了一半的 UTF-8 字符，有就一起压住。
- `_Limiter` 记着还剩多少字节的额度。放得下就整块转发；放不下时从额度处往回退到字符开头，切下前面的部分，接上 TRUNCATED，以后什么都不发。因为 `_Redactor` 从不放出半个字符，切点总能在手上的数据里找到。

```python
remaining = deadline - loop.time()
if remaining <= 0:
    raise asyncio.TimeoutError
chunk = await asyncio.wait_for(chunks.__anext__(), remaining)
```

超时是整个运行的期限：每次等下一块都只给剩下的时间。到点时 `wait_for` 取消正在睡的那一次读取，进程那边的生成器随之结束，晚到的那块根本不会产生；再 kill 进程，把截止前收到、还压着的字节放出来，最后 `wait()` 拿退出码。超时的状态一律是 timed-out。没有超时时，0 是 ok，2 是 invalid-input，3 是 policy-denied，其余都是 execution-failed。截断不影响状态，只在报告里记一笔：进程照常运行到退出，这样它的退出码仍然有意义。

`relay` 外面包了一层 `try/finally`：如果消费者中途 `aclose()`，进程会被 kill 掉。测试没考这一点。

## Part 5 归档检查

每个条目先用 `posixpath.normpath` 归一化，然后按顺序判断：

1. 原始路径以 `/` 开头是 absolute-path；归一化后是 `..` 或以 `../` 开头是 path-escape；不是 `<name>` 也不在 `<name>/` 下面是 outside-package。有了路径问题，这个条目就不再检查别的。归档根 `.` 这个目录直接跳过。
2. 包里的条目再依次看：链接（符号链接和硬链接一样）、特殊文件、超大文件、重复、not-a-directory、多余的入口。

重复和 not-a-directory 靠一张 `seen` 表：键是归一化后的路径，值是 `dir` 或 `other`。每个条目的祖先都记成 `dir`（已经是 `other` 的不改），自己按类型记。于是：

- 一个非目录条目落在已经出现过的非目录路径上，就是 duplicate，`./SKILL.md` 和 `SKILL.md` 归一化后相撞；目录重复出现没关系。
- 祖先里有 `other`，说明它在一个文件或链接“下面”，比如符号链接 `lib` 下面的 `lib/ssl/libssl.so`，这正是借符号链接写到包外的老办法。要查所有祖先，不只是直接父目录：`lib/ssl` 从没出现过；非目录落在 `dir` 上，或者目录落在 `other` 上，也是 not-a-directory。两个方向都在报后来的那个条目。

计数在最前面做，所有条目都算，包括被拒的：数量只数非目录条目（链接和特殊文件也算），大小只加普通文件。比较用 `>`，正好卡在上限上不算超。最后依次补上 too-many-files、too-large 和 missing-entry-point。入口必须是 `<name>/SKILL.md` 上的普通文件：符号链接不算，`docs/SKILL.md` 也不算，后者还要报 extra-entry-point。

## 这套题证明了什么，没证明什么

通过了说明你能在课里这个审查器的规模上调试源的规范化、argv 前缀和 ask 与 allow 的边界，能看出一条正则的回溯代价；能写一个内容寻址、带审查计划的安装库；能把一个结构化请求变成有确定规则、真实目标、按目的地注入凭据的启动计划；能写一个跨块脱敏、有界、准时停下的流式转发；能在解压之前检查一棵归档树。

它不涉及真正的隔离。题里没有启动过一个进程、打开过一个连接，课里 Run the isolation drill 那一节的容器参数（`--network none --read-only --cap-drop ALL` 等）、seccomp、cgroups、microVM 都要另外动手。它也没有解决文件系统竞态：从检查到使用之间，路径仍然可能被换成符号链接，课里说这需要绑定到已打开文件描述符的系统调用。按模式和按原值脱敏只能挡住明显的秘密，挡不住编码过的或者推断出来的信息。
