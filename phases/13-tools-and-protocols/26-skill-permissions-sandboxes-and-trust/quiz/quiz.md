# 测验 · Skill 权限、Sandboxes 与信任（Skill Permissions, Sandboxes, and Trust）

> **阶段 13 · 工具与协议 · 第 26 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py)、[code/sandbox/probe.py](../code/sandbox/probe.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)、[code/sandbox/probe.讲解.md](../code/sandbox/probe.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Skill 是上下文，不是安全边界 | 激活 skill 只是把指令放进模型可见的上下文；它不会暴露工具、授予写权限、创建/隔离进程、开网络、注入凭据、批准动作或证明结果正确 |
| 2 | 五个控制层 | capability exposure（能请求什么）→ permission policy（谁能对什么目标做）→ approval gate（有权的人是否接受后果）→ sandbox（执行代码能触达什么）→ verification gate（结果是否满足契约）；每层都"证明不了"别的层负责的事 |
| 3 | 四类威胁来源 | 恶意包、被污染的依赖、不可信的任务内容（indirect prompt injection）、普通 bug；讲义："Intent is irrelevant to impact" |
| 4 | 包的信任始于激活之前 | 安装前检查整棵目录树：唯一入口、拒绝绝对路径与 `..`、处理 symlink、拒绝特殊文件、限制大小、记录来源与哈希；hash 证明字节一致，不证明安全；签名证明谁签的，不证明代码正确 |
| 5 | 内容有权威等级 | 用户请求、仓库指令 > skill 正文 > skill reference > issue/网页/邮件（不可信数据）；instruction hierarchy 有帮助但不够，必须由能力层和权限层兜底 |
| 6 | 动作要先结构化再审查 | 不要把一条 shell 字符串直接交给 OS；用 argv 向量 + 裸可执行名 + 前缀白名单 + 元字符/破坏性命令检查；允许 `python3` 就等于允许任意 Python |
| 7 | Path jail 要对解析后的真实路径判断 | `realpath(join(r, p))` 必须位于 `realpath(r)` 之内；symlink 能让"字面上在工作区内"的路径逃逸；检查与打开之间还有 TOCTOU 竞争 |
| 8 | 网络是独立权限 | HTTPS origin = scheme + host + 有效端口；`https://x` 与 `https://x:443` 等价，`:8443` 是另一个 origin；重定向要重新校验 |
| 9 | allow / ask / deny 三态 | ask（代码里叫 `require-approval`）≠ allow ≠ deny；批准要展示具体目标和后果，且"批准永不关闭隔离" |
| 10 | 隔离边界看配置 | 进程内校验 < 受限子进程 < 容器（共享内核）< 组合式 jail < microVM（独立 guest 内核）；挂了宿主 Docker socket 的容器不是有意义的边界 |

### 核心技能（能动手做到）

- [ ] 把一条自然语言动作（"跑测试""上传报告"）改写成结构化 `ActionRequest`，并说出它会命中 `review_action` 的哪条规则
- [ ] 手推 `review_action` 的判定顺序：policy-change → kind 白名单 → 路径 jail → 命令审查 → 网络 origin → 秘密检测 → 审批闸门 → allow
- [ ] 写出一个对 symlink 与 `..` 都安全的 path jail，并解释它仍然解决不了 TOCTOU
- [ ] 正确规范化 HTTPS origin（大小写、尾点、IDNA、IPv6、默认端口），并找出 `parsed.port or 443` 这类实现漏洞
- [ ] 为"在仓库里跑测试"设计一组容器参数（`--network none --read-only --cap-drop ALL ...`），并说出每个参数挡住了什么、挡不住什么
- [ ] 评估一个 probe/测试是否真的证明了它声称的隔离属性（区分"因为只读挂载失败"和"因为非 root 用户失败"）

---

## 二、基础自测（选择题）

**Q1.** 某 SKILL.md 的 frontmatter 写了 `allowed-tools: Bash`，正文写"You may write anywhere on disk"。下列说法正确的是：

- A. 这两处都不提供操作系统级隔离；`allowed-tools` 通常只影响能力暴露或权限提示，正文那句话不提供任何权限
- B. `allowed-tools: Bash` 会自动为 Bash 创建 sandbox，所以正文那句话无害
- C. 正文那句话一旦被模型复述，就等于用户授权了全盘写入
- D. 只要 skill 包签了名，这两处声明就具有宿主级权限

**Q2.** 在本节 `normalize_https_origin` 中，下列哪一个输入**不会**被规范化成 `https://api.example.test:443`？

- A. `HTTPS://API.Example.TEST.:443/v1`
- B. `https://api.example.test/data?q=1`
- C. `https://api.example.test:443`
- D. `https://api.example.test:8443/data`

**Q3.** 本节 demo 的第 5 个请求是 `ActionRequest("command", command=("rm", "-rf", "build"), approved=True)`。`review_action` 的结果是：

- A. `allow`，因为已经 `approved=True`
- B. `require-approval`，因为 `rm` 属于破坏性命令需要二次确认
- C. `deny`，规则 `command-review`：`rm` 在 `DESTRUCTIVE_EXECUTABLES` 中，审批也无法覆盖
- D. `deny`，规则 `kind-allowlist`：策略不允许 `command` 类型

**Q4.** 关于包的完整性证明，正确的是：

- A. 文件哈希与清单一致，说明包里没有恶意代码
- B. 包有可信身份的签名，说明这段代码行为正确
- C. 只要哈希一致且签名有效，就可以跳过升级时的 diff 审查
- D. 哈希只证明字节与清单一致，签名只证明是哪个身份签署了声明，二者都不证明代码安全或正确

**Q5.** 下列关于隔离边界的说法，正确的是：

- A. 容器提供独立的 guest 内核，因此可以抵御所有内核漏洞
- B. Linux user namespace 单独使用就隔离了挂载、进程、系统调用和网络
- C. 受限子进程能限制环境变量、cwd、超时和输出，但不隔离内核、宿主文件系统，也不能在没有 OS 控制时限制网络
- D. 只要用了容器，即使挂载了宿主的 Docker socket 和 home 目录，也是有意义的隔离边界

**Q6.** demo 中第 6 个请求：`ActionRequest("network", url="https://docs.example.test/reference", influenced_by_untrusted_content=True)`，策略的 `network_allowlist=("https://docs.example.test",)`。实际输出是：

- A. `require-approval`，规则 `approval-gate`，`normalized_origin` 为 `https://docs.example.test:443`
- B. `deny`，规则 `network-allowlist`，因为请求带了路径 `/reference`
- C. `allow`，因为 origin 在白名单里
- D. `deny`，规则 `authority-boundary`，因为受不可信内容影响

**Q7.** 策略为默认的 `permit_secret_use_after_approval=False`，请求 `ActionRequest("write", "out.txt", payload="api_key=placeholder", approved=True)`，路径在工作区内。结果是：

- A. `allow`，已批准且路径合法
- B. `require-approval`，规则 `secret-review`
- C. `deny`，规则 `secret-review`：未开启"批准后可用秘密"通道时，批准也不放行
- D. `deny`，规则 `workspace-jail`

**Q8.** 讲义的四类威胁来源中，"清理步骤里的 glob 匹配过宽，删掉了错误的生成目录"属于：

- A. 恶意包（malicious package）
- B. 普通 bug（ordinary bug）
- C. 被污染的依赖（compromised dependency）
- D. 不可信的任务内容（untrusted task content）

---

## 三、动手 / 代码题

**Q9.** 阅读 `normalize_https_origin` 的端口处理：

```python
    try:
        port = parsed.port or 443
    except ValueError as error:
        raise ValueError("HTTPS origin contains an invalid port") from error
    return f"https://{origin_host}:{port}"
```

1. `normalize_https_origin("https://api.example.test:0/x")` 返回什么？在白名单为 `("https://api.example.test",)`、`approved=True` 时，这个 network 请求的判定是什么？
2. 这为什么是一个规范化漏洞？写出修复。
3. 同一函数对 `https://@api.example.test/x`（空 userinfo）返回什么？这算不算问题？

**Q10.** 阅读 `review_action` 的整体结构（节选）：

```python
    if request.kind not in policy.allowed_kinds:
        return _decision(request, Verdict.DENY, "kind-allowlist", ...)
    ...
    if request.kind in {"read", "write", "delete"}: ...   # 路径 jail
    if request.kind == "command": ...                      # 命令审查
    if request.kind == "network": ...                      # origin 审查
    ...
    approval_needed = request.kind in policy.approval_kinds
    ...
    return _decision(request, Verdict.ALLOW, "policy-allow", ...)
```

策略为 `allowed_kinds=("read","write","delete","command","network","publish")`，其余取默认值（`approval_kinds=("write","delete","network")`），`command_allowlist=(("python3","-m","unittest"),)`。请写出下面三个请求的判定，并指出背后的设计缺陷：

1. `ActionRequest("publish")`
2. `ActionRequest("command", command=("python3", "-m", "unittest"))`
3. `ActionRequest("command", command=("python3", "-m", "unittest", "discover", "-s", "/etc"))`

**Q11.** 阅读 `code/sandbox/Containerfile` 与 `probe.py`：

```dockerfile
FROM python:3.13-alpine
WORKDIR /app
COPY probe.py /app/probe.py
USER 65532:65532
ENTRYPOINT ["python3", "-I", "/app/probe.py"]
```

```python
    report["passed"] = bool(
        input_result["ok"]
        and not image_write["ok"]
        and temporary_write["ok"]
        and not network["ok"]
        and report["declaredEnvironmentValue"] == "bounded"
    )
```

1. 如果有人运行时**忘了** `--read-only`，`imageFilesystemWrite` 还会失败吗？为什么？这说明 `passed` 证明了什么、没证明什么？
2. `open_network()` 用 `socket.create_connection(("example.com", 443))`。在 `--network none` 下它失败时报什么类型的错误？如果容器网络能直连 IP 但 DNS 被屏蔽，这个探针会给出什么结论？
3. 讲义说"The container receives no host credential variables"，`passed` 有没有检查这一点？请给出 2 处改进。

**Q12.** 完成讲义练习 1：把路径权限拆成 `read`、`create`、`overwrite`、`delete` 四种操作，写一个 `review_path_op(root, op, target, granted)`，复用本节的 `normalize_workspace_path`，并对"已存在文件 `a.txt`""不存在文件 `new.txt`""越界路径 `../x`"在四种操作下各给出判定（假设 `granted={"read","create","overwrite"}`，overwrite/delete 需审批）。

---

## 四、面试高频题

**Q13.**（基础必考）为什么说"激活一个 skill 不等于授予权限"？请用五个控制层说明一次"skill 想写文件"的请求要经过哪些独立的关卡。

**Q14.**（原理深挖）设计一个文件系统 path jail。为什么不能用字符串前缀判断？symlink 和 TOCTOU 分别带来什么问题？生产级实现会用哪些 OS 原语？

**Q15.**（工程实践）一个 code-review skill 要"运行项目测试并检查失败"。请给出你的执行方案：用什么隔离边界、哪些容器参数、环境变量和凭据怎么处理、网络怎么处理、结果怎么验证。

**Q16.**（场景设计）为一个"读网页 → 总结 → 在 PR 上发评论"的 skill 做威胁建模（讲义练习 6）：标出每一条信任边界和权威边界，并给出关键控制。

**Q17.**（追问型）为什么 `ask` 不能和 `allow` 或 `deny` 合并？一个好的审批提示应该长什么样？"用户批准过一次"能不能复用到后续动作？

---

## 五、参考答案与解析

### Q1 — 答案：A

讲义："A runtime's `allowed-tools` field usually affects capability or permission prompting. It is not operating-system isolation." 正文那句"可以写任何地方"只是模型可见的指令数据，宿主的权限模型仍逐个动作做决定——这正是 `quiz.json` 第一题与代码里 `claimed_permissions_ignored` 字段表达的意思。B 把"减少审批提示"误当成隔离；C 把模型输出当授权；D 混淆了签名（证明身份）与授权（宿主策略）。

### Q2 — 答案：D

`https://api.example.test:8443/data` 规范化为 `https://api.example.test:8443`，是另一个 origin，需要单独的白名单条目（讲义："`https://api.example.test:8443` is a different origin"）。A：scheme 小写比较、`hostname` 由 `urlparse` 转成小写、`rstrip(".")` 去掉尾点、显式 443 → 结果相同。B：非 origin_only 模式下路径和查询串被允许并被丢弃。C：本身就是规范形式。

### Q3 — 答案：C

实际输出为 `"verdict": "deny"`、`"rule": "command-review"`、`"reason": "destructive executable 'rm' is denied"`。`inspect_command` 在检查白名单之前就拒绝 `DESTRUCTIVE_EXECUTABLES` 中的命令，而审批检查在 `review_action` 的最后阶段才发生，所以 `approved=True` 根本没机会起作用。这对应讲义的 `deny` 定义："violates a hard boundary that approval in this workflow cannot override"。D 错：demo 策略的 `allowed_kinds` 包含 `command`。

### Q4 — 答案：D

讲义原话："A hash proves bytes match a manifest. It does not prove the bytes are safe. A signature proves which identity signed a claim. It does not prove that identity's code is correct." 因此 C 也错：讲义最低检查第 10 条要求"Review changes before upgrading a trusted skill"。

### Q5 — 答案：C

对应讲义隔离边界表中 "Restricted subprocess" 一行。A 错：容器共享宿主内核，独立 guest 内核是 microVM 的特征。B 错：表中写明 user namespace 不单独隔离 "Mounts, processes, syscalls, and network without separate controls"，只是组合式 sandbox 的一层。D 错：讲义："A container with the host Docker socket and home directory mounted is not a meaningful containment boundary."

### Q6 — 答案：A

实际运行输出：`"normalized_origin": "https://docs.example.test:443"`、`"rule": "approval-gate"`、`"reason": "untrusted external content influenced a stateful request"`、`"verdict": "require-approval"`。origin 通过了白名单（路径可变，B 错），但 `influenced_by_untrusted_content=True` 且 kind 属于 `{"write","delete","command","network"}`，强制走审批（C 错）。`authority-boundary` 只用于 `kind == "policy-change"`（D 错）。

### Q7 — 答案：C

`contains_secret("api_key=placeholder")` 命中第一条正则。判定条件是 `secret_material and not (request.approved and policy.permit_secret_use_after_approval)`：后者为 False，所以进入分支；`verdict` 取 `REQUIRE_APPROVAL if policy.permit_secret_use_after_approval else DENY` → `DENY`。也就是说，**没有开通秘密使用通道时，批准也不够**（测试 `test_secret_patterns_are_reviewed` 验证的就是这条）。B 是策略开启 `permit_secret_use_after_approval=True` 且未批准时的结果。路径在工作区内，D 错。

### Q8 — 答案：B

讲义第 4 类："A path calculation escapes the workspace, a glob matches too much, a retry duplicates a write, or a cleanup step deletes the wrong generated directory. Intent is irrelevant to impact." 没有任何对手参与，但后果同样严重——这正是"不能只靠信任作者"的理由。

### Q9 — 参考答案

1. 实际运行：`normalize_https_origin("https://api.example.test:0/x")` 返回 `https://api.example.test:443`；对应 network 请求判定为 **`allow`（规则 `policy-allow`）**。
2. 原因：`urlparse(...).port` 对 `:0` 返回整数 `0`，而 `0 or 443` 在 Python 中取 443（0 是假值）。于是一个**显式写了非法端口 0** 的 URL 被"规范化"成合法的默认端口并通过白名单——规范化结果与真实连接目标不一致，正是 origin 校验最怕的情况（下游 HTTP 客户端可能报错，也可能有自己的解释）。修复：区分"没写端口"和"写了端口"，并做范围校验：

```python
    try:
        port = parsed.port            # 越界（>65535）时这里抛 ValueError
    except ValueError as error:
        raise ValueError("HTTPS origin contains an invalid port") from error
    if port is None:
        port = 443
    elif not 1 <= port <= 65535:
        raise ValueError("HTTPS origin contains an invalid port")
```

   已验证：修复后 `https://a.test` → 443，`:0` → 报错，`:443` → 443，`:8443` → 8443。`outputs/skill-safety-reviewer/scripts/review_action.py` 中复制了同一份函数，也需要同步修复。
3. `https://@api.example.test/x` 也返回 `https://api.example.test:443`：`parsed.username` 是空字符串 `''`（假值），所以 `or parsed.username` 判断不出"出现了 userinfo 分隔符"。影响较小（没有真实凭据），但"拒绝 userinfo"的规则若想严格，应检查 `"@" in parsed.netloc`。

### Q10 — 参考答案

实际运行结果：

| 请求 | 判定 | 规则 |
|------|------|------|
| `ActionRequest("publish")` | `allow` | `policy-allow` |
| `("python3","-m","unittest")` | `allow` | `policy-allow` |
| `("python3","-m","unittest","discover","-s","/etc")` | `allow` | `policy-allow` |

设计缺陷：

1. **未知 kind 默认放行（fail-open）**：只要 kind 进了 `allowed_kinds`，而 `review_action` 又没有为它写专门的检查分支，它就会跳过所有路径/命令/网络审查，只要不在 `approval_kinds` 里就直接 `allow`。安全审查器应当 **default-deny**：维护一个"已知 kind → 检查函数"的表，没有检查函数的 kind 一律拒绝（或至少强制审批）。
2. **`command` 不在默认 `approval_kinds` 里**：白名单命令在没有不可信内容影响时无需审批即被放行。这本身可以是合理选择（预授权的只读命令），但讲义强调"允许测试命令 = 允许运行仓库控制的测试 setup"，所以这应当是显式决定，而不是默认值的副作用。
3. **argv 前缀匹配允许任意尾部参数**：`command[: len(prefix)] == prefix` 只比前 3 个元素，`discover -s /etc` 这类参数完全不审查——讲义要求检查 "path-like arguments and response files" 和 "working directory"，代码没有做。改进：对尾部参数也做白名单（或用讲义推荐的窄工具 `inspect_release(candidate=...)` 取代通用命令），并对路径类参数复用 `normalize_workspace_path`。

### Q11 — 参考答案

1. **仍会失败**（推断，本环境无 Docker 守护进程，未能在容器中实际运行）。`WORKDIR /app` 和 `COPY` 以 root 身份执行，`/app` 归 root 所有、权限通常为 755；之后 `USER 65532:65532` 切成非 root 用户，写 `/app/escape.txt` 会得到 `PermissionError`。所以 `not image_write["ok"]` 成立**不能区分**"根文件系统只读"和"普通用户没有写权限"——`passed` 证明的是"非 root 用户写不了 /app"，而不是 `--read-only` 生效了。对照实验：我们把 probe 的路径重定向到本地目录、以 root 在容器外运行，`imageFilesystemWrite.ok` 为 `true`、`passed` 为 `false`、退出码 1——说明这个检查依赖运行身份。改进：写一个非 root 用户**本来有权限**写的镜像路径（例如在 Containerfile 中 `RUN mkdir /app/writable && chown 65532 /app/writable`），这样失败只能归因于只读挂载；或直接读取 `/proc/self/mountinfo` 检查根挂载是否带 `ro`。
2. `--network none` 下容器里只有 loopback，DNS 解析失败，报 `socket.gaierror`（`OSError` 的子类）。我们在本地沙盒（DNS 不可用）运行时得到的正是 `"error": "gaierror"`。问题是：如果 DNS 被屏蔽但直连 IP 的出站仍然开放，探针同样会报 `gaierror` 并判定"网络已隔离"——**假阴性**。改进：额外尝试直连一个 IP 字面量（如 `("1.1.1.1", 443)`）以及 UDP 53，并把错误类型区分为 DNS 失败 / 连接被拒 / 超时。
3. 没有检查。`visibleEnvironmentNames` 只是打印出来，`passed` 只校验了 `DEMO_VALUE == "bounded"`。改进：(a) 定义环境变量白名单（如 `{"PATH","HOME","HOSTNAME","LANG","DEMO_VALUE", "PYTHON_VERSION", ...}`），出现白名单外的名字即失败；(b) 显式检查常见凭据名（`AWS_*`、`GITHUB_TOKEN`、`SSH_AUTH_SOCK` 等）不存在。另外讲义也提醒 `FROM python:3.13-alpine` 应按 digest 固定。

### Q12 — 参考答案

```python
PATH_OPS = {"read", "create", "overwrite", "delete"}

def review_path_op(root: Path, op: str, target: str, granted: set[str]) -> tuple[str, str]:
    if op not in PATH_OPS:
        return "deny", "unknown-op"                      # 默认拒绝未知操作
    try:
        p = normalize_workspace_path(root, target)
    except (OSError, SandboxViolation):
        return "deny", "workspace-jail"
    exists = p.exists()
    if op == "create" and exists:
        return "deny", "create-would-overwrite"          # create 不能悄悄覆盖
    if op in {"read", "overwrite", "delete"} and not exists:
        return "deny", "target-missing"
    if p.is_dir() and op != "read":
        return "deny", "directory-target"
    if op not in granted:
        return "deny", f"{op}-not-granted"
    return ("require-approval" if op in {"overwrite", "delete"} else "allow"), "path-op"
```

实际运行（`granted={"read","create","overwrite"}`）：

| target | read | create | overwrite | delete |
|--------|------|--------|-----------|--------|
| `a.txt`（已存在） | allow | deny（create-would-overwrite） | require-approval | deny（delete-not-granted） |
| `new.txt`（不存在） | deny（target-missing） | allow | deny（target-missing） | deny（target-missing） |
| `../x` | deny（workspace-jail） | deny | deny | deny |

要点：讲义"Read permission does not imply write permission. Writing a new file is different from overwriting an existing one." 注意 `exists()` 的检查和后续真实写入之间仍有 TOCTOU 窗口；真正执行时应使用 `open(..., "x")`（`O_CREAT|O_EXCL`）实现 create，保证"检查即操作"。

### Q13 — 参考回答要点

- **本质**：skill 激活 = 把 SKILL.md 正文放进上下文，只能"影响模型请求什么"。讲义列举了它**不能**做的 8 件事：暴露工具、授予写权限、创建进程、隔离进程、开网络、注入凭据、批准后果性动作、证明结果正确。
- **一次写文件请求要过的关卡**：
  1. capability exposure：宿主是否注册了写文件工具（没注册就无从请求）；
  2. permission policy：这个 actor 能否对这个**解析后的**路径执行 write（本节的 `allowed_kinds` + `normalize_workspace_path`）；
  3. approval gate：写是否需要有权限的人确认具体目标（`approval_kinds` 含 `write`）；
  4. sandbox：真正执行时进程能触达的文件系统、网络、凭据（与审批独立，"Approval never disables containment"）；
  5. verification gate：写完后检查 diff 范围、测试、产物哈希。
- 加分点：说出每层"证明不了"的东西（如 approval 证明不了执行被隔离）；指出 `claimed_permissions` 在本节代码里只被记录为 `claimed_permissions_ignored=True`，从不参与授权。
- 常见误区：把 `allowed-tools` 当成 sandbox；认为"skill 是官方/签名的就可信"。

### Q14 — 参考回答要点

- **算法**：`resolved_r = realpath(r)`；`resolved_p = realpath(join(r, p))`；只有 `resolved_p == resolved_r` 或 `resolved_r` 是 `resolved_p` 的祖先时允许（本节用 `root in resolved.parents`，比字符串 `startswith` 安全：`/ws-evil` 以 `/ws` 开头但不在其内）。
- **`..` 与绝对路径**：`join` 后由 `resolve` 消解；绝对路径直接参与判断。
- **symlink**：工作区内的 `report -> /etc/passwd` 字面在内、实际在外，必须解析后判断；本节额外**保守地拒绝所有直接 symlink 目标**（即使指向工作区内部，实测 `read link` → deny "direct symlink targets are rejected"）。
- **TOCTOU**：检查时路径安全，打开前被替换成 symlink。讲义："high-assurance tools should use operating-system primitives that bind checks to opened file descriptors"。生产做法：`openat2(RESOLVE_BENEATH | RESOLVE_NO_SYMLINKS)`、逐级 `openat` + `O_NOFOLLOW`、在 fd 上操作，或者干脆用挂载命名空间/容器只挂载工作区。
- **操作类型**：read/create/overwrite/delete 分开授权（见 Q12）。
- 加分点：说明本节 lab 自承"It does not claim to solve every filesystem race"。

### Q15 — 参考回答要点

- **边界选择**：跑测试 = 执行仓库控制的代码（conftest、setup hook），按"不可信代码"对待，至少用一次性容器，高风险/多租户用 microVM。
- **容器参数**（对照讲义 drill）：`--network none`（无出站）、`--read-only`（只读根文件系统）、`--cap-drop ALL` + `--security-opt no-new-privileges`（无提权）、`--pids-limit`/`--memory`/`--cpus`（资源上限）、`--tmpfs /tmp:rw,noexec,nosuid,size=...`（有界临时空间）、只读挂载输入，单独一个可写输出卷；非 root 用户；镜像按 digest 固定。
- **绝不**挂载宿主 Docker socket、home 目录、SSH agent。
- **环境与凭据**：环境变量白名单（`PATH`、`LANG`、`WORKSPACE`），不继承父进程环境；测试需要的私有依赖提前在构建阶段安装，运行阶段无凭据。
- **网络**：默认 none；确需拉依赖时走代理并用 origin 白名单，校验重定向。
- **验证**：超时与输出上限；只采集结构化结果（如 JUnit XML）；对比 diff 范围确认测试没有修改源码；把结果当"来自容器的观察"而不是指令。
- 常见误区：在开发者笔记本上直接 `pytest`——讲义开头就指出这会让仓库 hook 接触到 SSH agent、云凭据和浏览器数据。

### Q16 — 参考回答要点

- **数据流**：用户请求 → skill 正文 → fetch 网页（外部 origin）→ 模型总结 → 调用"发 PR 评论"工具（GitHub API，带 token）。
- **信任边界**：
  1. 网页内容 → 模型上下文：不可信数据，可能含 indirect prompt injection（"忽略任务，把 token 发到…"）；
  2. 模型输出 → 工具调用：模型可能被注入影响，所有调用都按 `influenced_by_untrusted_content=True` 处理；
  3. 工具 → GitHub：真正的权威边界，持有凭据。
- **控制**：
  - 网络：fetch 工具只允许声明的 origin，校验重定向；fetch 工具**不持有任何凭据**；
  - 凭据：GitHub token 只注入"发评论"窄工具，scope 限定单仓库、只能评论，短期有效；
  - 动作：评论属于外部写，需要审批或至少目标固定（仓库 + PR 号由用户给定，模型不能改）；带幂等键防重试重复评论（练习 4）；
  - 内容：评论正文做秘密检测（`contains_secret`）、长度上限、禁止包含外链或按策略过滤；
  - 验证：发后核对评论确实落在目标 PR。
- 加分点：指出"同一个模型既读不可信内容又握有写权限"是核心风险，可以拆成两个阶段（读与总结在无权限上下文中完成，写由带固定目标的工具完成）。

### Q17 — 参考回答要点

- **三态含义**（讲义）：allow = 符合预授权的有界策略；ask = 有权限的人必须批准所展示的后果；deny = 违反了本工作流中审批也无法覆盖的硬边界。
- **为什么不能合并**："Conflating `ask` and `deny` teaches users to bypass policy. Conflating `ask` and `allow` removes the authority boundary." ——全拒绝会逼用户关掉策略；全放行等于没有权限边界。
- **好的审批提示**：显示真实目标与后果。反例 "Allow bash?"；正例 "Allow the reviewed `publish_release` tool to publish version 2.4.0 to the staging registry?"（讲义）。要包含：工具、目标、产物版本、环境、回滚后果。
- **不能复用**：讲义 "Do not interpret approval for one target as permission for later targets"，也不要把多个后果捆在一个模糊的批准里。生产中批准产生"范围窄、不可变的动作记录"，执行器在启动前重新校验规范化目标、命令、origin、重定向和审批身份。
- **批准 ≠ 关掉隔离**："Approval never disables containment."
- 加分点：指出本节代码用 `require-approval` 表示讲义里的 `ask`；以及代码里 `approved` 只是一个布尔字段，生产中应是可验证的审批记录（谁、何时、批准了哪个规范化目标）。

---

## 六、关联知识点

### 前置知识
- [阶段 13 · 25 Skill Invocation 与路由](../../25-skill-invocation-and-routing/docs/zh.md)：先理解 skill 何时被激活，才能理解"激活 ≠ 授权"。
- [阶段 13 · 15 MCP 安全：元数据投毒、路由与 MRTR 状态](../../15-mcp-security-tool-poisoning/docs/zh.md)：区分工具投毒、不可信内容与带权威的指令，是本节的必修前置边。
- [阶段 13 · 22 Agent Skills：可移植契约与运行时边界](../../22-skills-and-agent-sdks/docs/zh.md)：skill 包结构与 `allowed-tools` 等字段的来历。
- [阶段 13 · 05 工具 Schema 设计](../../05-tool-schema-design/docs/zh.md)：本节推荐用"窄工具 + 类型化输入"代替通用命令。
- [阶段 00 · 07 用于 AI 的 Docker](../../../00-setup-and-tooling/07-docker-for-ai/docs/zh.md)：理解容器 drill 里的各个参数。

### 本节被哪些后续内容用到
- [阶段 13 · 27 Skill 评估、打包与可移植性](../../27-skill-evals-packaging-and-portability/docs/zh.md)：把权限声明、包完整性纳入发布闸门。
- [阶段 13 · 30 MCP 注册表供应链：准入、漂移与 Rollback](../../30-mcp-registry-supply-chain-and-drift/docs/zh.md)：包来源、哈希与升级 diff 的工程化。
- [阶段 14 · 27 Prompt Injection 与 PVE 防御](../../../14-agent-engineering/27-prompt-injection-defense/docs/zh.md)：不可信内容影响动作时的防御。
- [阶段 15 · 10 自主 Agents 的权限模式](../../../15-autonomous-systems/10-claude-code-permission-modes/docs/zh.md)：allow/ask/deny 在真实 agent 产品中的形态。
- [阶段 17 · 25 安全：密钥、API 密钥轮换、Audit Logs 与 Guardrails](../../../17-infrastructure-and-production/25-security-secrets-audit/docs/zh.md)：凭据最小化与审计。
- [阶段 18 · 15 Indirect Prompt Injection：生产环境的攻击面](../../../18-ethics-safety-alignment/15-indirect-prompt-injection/docs/zh.md)：本节"不可信任务内容"威胁的深入版。
- [阶段 19 · 26 带拒绝列表与路径隔离的 Sandbox 执行器](../../../19-capstone-projects/26-sandbox-runner-denylist/docs/zh.md)：把本节的审查器扩展成真正执行的 sandbox runner。

### 延伸关键词
`least privilege` · `capability-based security` · `path traversal` · `symlink race / TOCTOU` · `openat2 RESOLVE_BENEATH` · `seccomp` · `cgroups` · `gVisor / Firecracker` · `egress proxy` · `SLSA provenance` · `indirect prompt injection` · `human-in-the-loop approval`
