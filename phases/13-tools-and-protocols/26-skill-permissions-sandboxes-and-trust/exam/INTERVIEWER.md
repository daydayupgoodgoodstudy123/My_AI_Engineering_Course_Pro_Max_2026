# 面试官手册：SandboxPol（13/26）

候选人计时期间不要看。候选人手里只有 README、`sandboxpol/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查 Python 官方文档和本课讲义。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 端口 0 要不要当成 443？ | "No. Ports run from 1 to 65535. Anything else makes the URL invalid." |
| 1 | 命令在前缀后面还能带参数吗？ | "Yes. The allowlist holds argv prefixes. What follows the prefix is free." |
| 1 | 那个正则能整个换掉吗？ | "Yes, as long as the three kinds of secrets in the docstring are still caught." |
| 1 | 批准过的 deny 能不能放行？ | "No. A deny is a hard boundary. Approval only turns require-approval into allow." |
| 2 | 空目录要保存吗？ | "No. Directories come back with the files in them." |
| 2 | 源目录里有符号链接怎么办？ | "Not in this part. Raise a ValueError if you meet one. The archive check keeps them out." |
| 2 | 还原时要不要校验 blob？ | "It's a good idea. The tests don't damage blobs, so how you do it is your call." |
| 2 | 计划之后源目录又变了？ | "The upgrade installs what was planned. It doesn't read the source again." |
| 2 | restore 能写进已有的目录吗？ | "No. dest must not exist yet." |
| 3 | 有 overwrite 权限就能 create 吗？ | "No. Each operation has its own roots." |
| 3 | 请求自称 read_only，实际在写？ | "The review goes by what the request does. side_effect is only the requester's description." |
| 3 | 已经批准的后果还要列在计划里吗？ | "Yes. The plan lists all of them. Approval only changes the verdict." |
| 3 | 跳转后还能带凭据吗？ | "Only to the credential's own origin." |
| 3 | 写一个已存在的目录？删除？ | "Not covered. read and write only, and an existing path is an overwrite." |
| 4 | 截断标记算不算进上限？ | "No. The limit is for the output itself." |
| 4 | 超过上限要不要杀进程？ | "No. Keep reading until it exits, and forward nothing more." |
| 4 | 超时的时候还压着没发的字节怎么办？ | "Forward them, redacted. The process wrote them before the deadline." |
| 4 | 两个秘密会重叠吗？ | "One can be a prefix of another. Prefer the longest match." |
| 4 | 输出不是合法 UTF-8？ | "Forward the bytes as they are. Just don't cut a character in half." |
| 4 | 被杀掉的进程退出码是多少？ | "Whatever wait() says, negative here. The status is timed-out anyway." |
| 5 | 遇到第一个问题就返回行吗？ | "No. Report all of them." |
| 5 | 归一化以后还在包里的 .. 算不算越界？ | "No. Only a path that leaves the archive is an escape." |
| 5 | 目录算不算文件数？ | "No." |
| 5 | 指向包内的符号链接也不行？ | "Still a link problem. This host forbids links." |
| 5 | 同一个目录出现两次？ | "That's fine. Only non-directory members can be duplicates." |
| 5 | 被拒的条目算不算大小和数量？ | "Yes. Every member counts toward the limits." |

## 每关：要看什么、提示、追问

### Part 1 修审查器和闸门（目标 11 分钟）

一个测试里叠了 5 个缺陷：

1. `origin_allowed` 用 `urlsplit(...).hostname` 只比主机，`https://api.example.test:8443` 被当成白名单里的 `https://api.example.test`。测试先看到的是“a non-default port is a different origin”。
2. `normalize_https_origin` 只有 URL 自己写了端口才写端口，没写的不补 443。第 1 条修好、改成整串比较以后，`https://API.example.test.:443/...` 变成 `https://api.example.test:443`，白名单那一条还是 `https://api.example.test`，两者对不上，这个显式 443 的请求被拒。错误出在 `review_action` 的判定上，根因在下一层的规范化函数里。原来只比主机时它被掩盖了。
3. `inspect_command` 只比可执行文件名，`python3 -c ...`、`python3 -m http.server` 都过了。课里那句 "Allowing python3 means allowing arbitrary Python unless you constrain which script and arguments are permitted"。
4. `ActionGate.submit` 只拦 deny，require-approval 也交给了 runner。课里 "Conflating ask and allow removes the authority boundary"。
5. `contains_secret` 的 key=value 规则前面多了 `[\w.-]*`，想把 `DB_PASSWORD` 这样的整个键名也匹配进来。布尔搜索根本不需要这一段，但遇到一长串字母、数字、点和横线，每个起点都把它吃到串尾再一个个退回来找关键词，是 O(n²)。测试审的是一个 10,804 个字符、横线隔开的缓存键，后面接一段 4,096 个字符、中间没有任何分隔的十六进制转储：本机负载 7 左右时，慢版本 1.13 到 1.17 秒（check_traps 里 1.35 秒），修好后 0.39 到 0.59 毫秒，限值 0.05 秒。

护栏：
- 端口 0：顺手写成 `parsed.port or 443`（课里的原代码，quiz Q9 专门讲过）会把 `:0` 当成 443 放行。补了默认端口却不查 1 到 65535 的范围，`:0` 变成白名单之外的源，规则名不对。
- 规范形式要带 `:443`。只把 443 去掉、用 `https://host` 当规范形式，判定碰巧对，但测试检查 `normalized_origin`。
- 命令：改成整个 argv 必须和白名单完全相等，`--format json` 这种参数就被拒了；把 argv 拼成字符串再比前缀，`scripts/inspect_release.py.bak` 会混过去。
- 闸门：批准过的 deny（`rm -rf out`）不能跑；不需要批准的读要照跑；runner 收到的是审查后的绝对路径，不是请求里的原始字符串。
- 正则：退回课里带 `\b` 的写法，`DB_PASSWORD=` 抓不到（`_P` 之间没有词边界）；保留前缀只在前面加 `\b`，横线隔开的串里到处是词边界，还是平方级，本机 0.24 到 0.34 秒；改成惰性的 `[\w.-]*?` 一样慢（1.2 到 1.5 秒）；以为横线是祸首、把前缀缩成 `\w*`，缓存键那段快了，十六进制转储那段一整串都是 `\w`，还是平方级，本机约 0.14 秒；删掉这条规则、只扫前 4 KB、加“长串就算秘密”的规则、把 PEM 放宽到任意 BEGIN 行、去掉 Bearer 规则，都会被后面的检测断言抓住。证书和 sha256 摘要都不是秘密。
- 可以接受的修法：去掉前缀；用 `(?<![\w.-])` 只从串首开始（约 0.55 毫秒）；或者给前缀加上限 `{0,64}`（17 到 22 毫秒，能过，但离限值只有两三倍，可以追问为什么还是不如去掉前缀）。

看什么：先读断言消息再读代码；会不会在 REPL 里打印两种写法的 `normalize_https_origin`；第 1 条修好后又冒出新的失败，能不能意识到是原来被掩盖的问题；碰到超时会不会先计时、再用二分或 `cProfile` 找到是哪条正则。

提示：
- H1："For the two URLs that should be the same origin, what does normalize_https_origin return?"
- H2："What exactly does origin_allowed compare? And inspect_command?"
- H3：直接指出 `if port else`，以及 key=value 规则开头的 `[\w.-]*`。

追问：
- "The runner got /work/out/summary.json. What should the executor check right before it writes?"（重新校验规范化后的目标、命令、源和批准身份，课里 "The executor revalidates ... immediately before launch"；检查和使用之间还有 TOCTOU）
- "The scan says no secret. Is the payload safe to send?"（不能这么说。课里 "Pattern matching can catch obvious credential shapes, but it cannot establish that arbitrary text is non-sensitive"，还要看数据分类和目的地策略）
- "What does https://@api.example.test/x normalize to?"（空的 userinfo 让 `parsed.username` 是空串，`@` 混过去了；要严格就查 netloc 里有没有 `@`，quiz Q9）
- "`python3 scripts/inspect_release.py --out /etc/cron.d/x` passes the prefix. Is that fine?"（前缀后面的参数没人管，路径类参数和 response file 也要查，quiz Q10）

### Part 2 安装库（目标 12 分钟）

坑：
- 可执行位要同时满足两条：在 reviewed_scripts 里，源文件本身有执行位。`postinstall.sh` 是 0o775 但没被审查，要丢掉执行位；`render.py` 被审查了但源文件是 0o644，也不能加。
- 还原时的权限要写死成 0o755 或 0o644。源文件是 0o600、0o640、0o666、0o775，复制源权限或者给 0o777/0o666 都不对；只给属主加 x（0o744）也不对。只给可执行文件 chmod、其他文件交给默认权限也不行：测试在还原时把 umask 设成 0o077，新建的文件是 0o600。
- 内容按字节存取：`inspect_release.py` 是 CRLF 而且没有结尾换行，`icon.bin` 含 0x00 到 0xFF，`empty.txt` 是空文件。用文本方式读写会改坏字节。
- 8 个文件只有 7 种内容（两份 LICENSE，权限还不同），blobs 里必须正好 7 个。按路径或按“内容加权限”算摘要都会多出来。
- 清单里的路径是包内相对的 POSIX 路径。`str(path)` 是绝对路径，从字符串里截出来的会多一个开头的 `/`。
- 重复安装同名包要报 FileExistsError；不存在的包报 KeyError，不是 FileNotFoundError。
- 升级计划的三张表都要排好序。`render.py` 字节没变、只多了执行位，也要算在 changed 里：只比摘要会漏掉它。
- 做计划不能动已安装的东西；计划时就要把新内容存进 blobs，因为测试在计划之后改了源目录里的 SKILL.md，`upgrade` 必须装审查过的那份字节，不能再去读源目录。
- 按旧版本做的计划，在已经升级之后再拿来用，要报 ValueError。课里 "Do not interpret approval for one target as permission for later targets" 在这里的样子。
- 升级以后被删掉的文件要真的消失，不能把新旧清单合并。

追问：
- "Someone edits a blob on disk. What happens on the next restore?"（参考实现还原前重新算 sha256，对不上就拒绝。课里 "A hash proves bytes match a manifest. It does not prove the bytes are safe"）
- "When can a blob be deleted?"（没有任何清单、也没有进行中的计划引用它的时候；按清单做 mark and sweep）
- "Two installs of the same name at once?"（清单写入要加锁，参考实现用临时文件加 `os.replace` 保证读者看不到半个清单）
- "Why keep only the executable bit and not the whole mode?"（课里第 7 条只为审查过、确实需要的脚本保留执行位；setuid、组写权限都不该跟着包走）

### Part 3 启动计划（目标 13 分钟）

坑：
- 写操作是 create 还是 overwrite，看的是解析后的目标在不在。`./out/tmp/../cache/index.json` 里的 `out/tmp` 并不存在，拿原始路径去 `exists()` 会得到 False，把一次覆盖当成新建放过去。
- 每种操作有自己的根：读的根是 `scripts`、`src`、`out`，工作区根上的 `.env` 不在里面，读它是 path-read；读权限覆盖 `src/`，不等于能在 `src/` 里新建（"Read permission does not imply write permission"）；能在 `out/` 新建，不等于能覆盖 `out/report.json`（"Writing a new file is different from overwriting an existing one"）。
- 判断在不在根下面也要用解析后的路径，后果里写的也是解析后、相对工作区的 POSIX 路径：`overwrite out/cache/index.json`，不是请求里的原样字符串，也不是绝对路径。课里 "Approval must show the actual target and consequence"。
- `side_effect="read_only"` 是请求者自己说的，不能因此跳过审批。
- 批准按条算：批准了 index.json 不等于批准了 old.json；已批准的计划仍然列出全部后果，测试会看。
- 环境变量：只有 policy.env 加上 pass_env 里宿主确实设置了的变量。`CI` 宿主没有，不能 KeyError，也不能塞个空串；`LANG` 两边都有时 policy.env 赢；按黑名单去掉 TOKEN、SECRET 的写法会把 `HOME`、`SSH_AUTH_SOCK` 漏进去。
- 凭据：策略里要有它的作用域，作用域的源还必须在这次请求的网络源里；inject 只给那一个源。发送凭据本身是一条要批准的后果。
- 检查顺序：路径、URL、凭据，第一条失败就决定 deny，被拒的计划什么都不带。测试里有两条专门看顺序的断言。
- 跳转：Location 可能是相对的，要先 `urljoin`；`//api.example.test/collect` 这种以 `//` 开头的相对写法换了源，凭据不能跟过去；拿 `startswith("/")` 判断“同源”正好栽在这里。跳转目标要像新请求一样过白名单，`http://` 是 network-shape。
- inject 和 consequences 的值是元组，和 dataclass 的注解一致。

追问：
- "Why not str.startswith for the roots?"（`/work/out-old` 会被当成在 `/work/out` 下面，要按路径组件比较。测试没有这个例子，看候选人自己有没有想到）
- "Between planning and launch, out/cache/index.json becomes a symlink to ~/.ssh/config. What now?"（检查到使用之间的竞态。课里说高保证的工具要用和已打开文件描述符绑定的系统调用，比如 openat2 的 RESOLVE_BENEATH、O_NOFOLLOW，或者干脆只把工作区挂进容器）
- "Why should the process never see RELEASE_TOKEN?"（进程里的任何代码都能把环境变量发到任何地方；由出口代理按目的地注入，才是课里的 "only for the intended destination"）
- "A redirect to the same host on port 8443?"（另一个源，重新过白名单，凭据不带）

### Part 4 输出转发（目标 13 分钟）

坑：
- starter 里的 `relay` 是普通 `async def`，测试会报 `'async for' requires an object with __aiter__`，要看出来这里需要 async generator。
- 跨块的秘密：要压住末尾“最长秘密长度减一”个字节，等下一块来了再判断。每块单独替换会漏；窗口少一个字节，1 字节一块的切法会漏；按最短的秘密算窗口，长的那个（`pypi-placeholder-token`）会漏。
- 流结束时要把压住的尾巴放出来，超时的时候也一样，那些字节是截止前写的。
- 不能等进程结束才转发：探针在第一块出来时数进程已经产出了几块。探针的输出里没有换行，按行攒着再脱敏的写法也会在这里挂掉：压住的只能是秘密长度决定的那一小段尾巴。
- 秘密之间可能有包含关系：测试同时注入了 `pypi-placeholder` 和 `pypi-placeholder-token`。先替换短的，长的那个就剩下 `-token` 漏出去；按传入顺序依次 `replace` 也一样。要按长度从长到短匹配。
- 上限按脱敏后的字节算，不算标记。切点落在多字节字符中间要退到字符开头；1 字节一块时，还要在字符没收全之前就压住它的开头几个字节，否则半个字符已经发出去了。正好等于上限的输出不截断、不加标记。
- 截断以后只发一次标记，之后什么都不发，但要继续读到进程退出：退出码还是要的，测试要求截断的运行仍然是 ok。
- 超时是整个运行的期限，不是每块的：每块都等 `asyncio.wait_for(..., remaining)`。只在收到下一块时才看时间，就会等上 1 秒、还把晚到的那块发出去。超时要 kill 进程，状态一律是 timed-out，不看退出码。
- 退出码：0 是 ok，2 是 invalid-input，3 是 policy-denied，其他都是 execution-failed（1 也是）。
- 没有秘密时 `max()` 不能对空序列报错。
- Python 3.10 里 `asyncio.TimeoutError` 和内置的 `TimeoutError` 还不是同一个类，3.11 起才合并，要接住 `asyncio.TimeoutError`。

追问：
- "The consumer disconnects in the middle. What happens to the process?"（`aclose()` 会在 yield 处抛 GeneratorExit，参考实现在 finally 里 kill 掉进程）
- "Why not redact once at the end?"（要攒下全部输出，内存和延迟都没有上界；课里 "Use bounded time and output"）
- "The script prints the token base64-encoded. Does the relay catch it?"（不会。按原值替换只能挡原值，所以 Part 3 让进程根本拿不到令牌）
- "Why do distinct exit codes matter to the host?"（下一步不同：输入错了要改参数，策略拒绝不该重试，执行失败可以重试或者上报）

### Part 5 归档检查（目标 11 分钟）

坑：
- 先归一化再判断：`release-readiness/../../home/.ssh/authorized_keys` 只看开头的 `../` 发现不了；`release-readiness/scripts/../README.md` 归一化后还在包里，是合法的，把所有 `..` 一律拒掉会让干净的包报错。`./`、`//`、`/./` 都要先去掉；归档根 `./` 这个目录直接忽略；包目录本身（`./release-readiness/`）不算包外。
- 一个条目最多一个路径问题，有了路径问题就不再报别的。
- 硬链接和符号链接一样拒；字符设备也是特殊文件。
- not-a-directory 两个方向都要查：先出现文件、后出现它下面的条目；先被当成目录用、后又出现同名文件。符号链接 `lib` 下面的 `lib/ssl/libssl.so` 也是这一类，而且它的直接父目录 `lib/ssl` 从没出现过，只看直接父目录会漏掉，要查所有祖先。
- duplicate 要在归一化以后比：`release-readiness/./SKILL.md` 和 `release-readiness/SKILL.md` 是同一个路径。同一个目录出现两次没问题。
- 入口必须是 `<name>/SKILL.md` 上的普通文件：符号链接不算，`docs/SKILL.md` 不算（而且要报 extra-entry-point）。
- 上限：目录不计数，但符号链接、硬链接、特殊文件都算（测试里有一个 1 个文件加 5 个符号链接的归档）；比较用 `>` 而不是 `>=`，干净的包正好卡在 5 个文件、单个 1000 字节、总计 2600 字节；被拒的条目也要计入，测试里有一个 5 个绝对路径加起来超限的归档。
- 顺序：先按归档顺序列每个条目的问题，再按固定顺序列整个归档的问题。排序或者先报整体问题都不对。

追问：
- "Why check the member list instead of extracting into a temp dir and looking?"（解压本身就会顺着符号链接和 `..` 写到外面；Python 3.12 的 `tarfile` 有 `filter="data"`，原理相同）
- "Is release-readiness-old/SKILL.md inside the package?"（不在。按 `startswith(name)` 判断会把它当成包里的；要和 `name + "/"` 比，或者按路径组件比。测试没有这个例子）
- "macOS treats SKILL.md and skill.md as the same file. Does the check catch that?"（不能。大小写不敏感的文件系统上要按小写再比一次重复）
- "Where does the mode field matter?"（Part 2：只有审查过的脚本保留执行位；setuid 这类位应该直接拒或者清掉）
- "Do the limits use compressed or unpacked sizes?"（解压后的大小。压缩包炸弹就是靠压缩比绕过按压缩大小设的上限）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看数据、一次只改一处、用 `-x -k`、慢的时候先计时再找 |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出 TOCTOU、凭据注入、垃圾回收、断开连接、大小写冲突这些问题 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
