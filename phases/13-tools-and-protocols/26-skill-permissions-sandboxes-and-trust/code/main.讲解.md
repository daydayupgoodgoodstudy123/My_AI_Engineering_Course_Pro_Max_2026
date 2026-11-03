# 代码讲解 · main.py

> **所属小节**：阶段 13 · 工具与协议 · 第 26 节 Skill 权限、Sandboxes 与信任 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`；测试：`python3 -m unittest discover -s tests -v`（在 `code/` 目录下） ｜ **依赖**：仅标准库（`json`、`ipaddress`、`re`、`tempfile`、`dataclasses`、`enum`、`pathlib`、`urllib.parse`），无需网络、不执行任何命令

---

## 1. 这份代码在考察什么

`main.py` 是一个**只做判定、从不执行**（non-executing）的策略审查器。它接收一条结构化的动作请求（`ActionRequest`）和一份宿主策略（`SandboxPolicy`），返回 `allow` / `require-approval` / `deny` 三态判定，以及命中的规则名和原因。它考察的是讲义中"执行之前的决策边界"：

1. **权威边界**：skill 或外部内容不能修改宿主权限模型（`policy-change` 一律拒绝），skill 自称的权限（`claimed_permissions`）只被记录、从不参与授权。
2. **Path jail**：对**解析后的真实路径**做包含判断，拒绝 `..` 逃逸和 symlink。
3. **命令审查**：要求 argv 向量、裸可执行名、拒绝 shell 元字符与破坏性命令、匹配前缀白名单。
4. **网络 origin 规范化**：scheme + host（小写、去尾点、IDNA、IP 字面量）+ 有效端口，精确匹配白名单。
5. **秘密检测**：用少量正则识别明显的凭据形态（讲义强调这只是"intentionally limited"的信号）。
6. **审批闸门**：按 kind 或"受不可信内容影响"决定是否需要人批准。

> 一句话：**把"skill 想做某件事"翻译成一个可以在不执行的前提下逐条审查的结构化请求，并让每个判定都能说出是哪条规则做出的**。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Verdict` | `str` 枚举 | `allow` / `deny` / `require-approval` | allow / ask / deny 三态 |
| `SandboxPolicy` | 冻结 dataclass | 工作区根、允许的 kind、命令白名单、网络白名单、需审批的 kind、秘密通道开关 | permission policy |
| `ActionRequest` | 冻结 dataclass | 一条结构化动作提议 | "Review actions as structured requests" |
| `ReviewDecision` | 冻结 dataclass | 判定 + 规则 + 原因 + 规范化目标/origin + `executed=False` | 可审计的决策记录 |
| `SandboxViolation` | 异常类 | path jail 违规 | path jail |
| `SECRET_PATTERNS` 等常量 | 模块常量 | 秘密正则、主机名标签正则、元字符、破坏性命令 | 秘密检测 / 命令策略 |
| `contains_secret` | 函数 | 正则扫描 | secret handling |
| `normalize_https_origin` | 函数 | URL → `https://host:port` | egress policy |
| `normalize_workspace_path` | 函数 | 解析路径并检查包含关系 | path jail |
| `inspect_command` | 函数 | 审查 argv | command policy |
| `_decision` | 私有函数 | 统一构造 `ReviewDecision` | — |
| `review_action` | 函数 | 按固定顺序串联所有检查 | 组合决策 |
| `demo` | 函数 | 在临时工作区上审查 7 个请求并打印 JSON | 演示 |

数据流：`demo()` 建临时工作区 → 构造 `SandboxPolicy` 与 7 个 `ActionRequest` → 逐个 `review_action` → `ReviewDecision.to_dict()` → `json.dumps` 打印（临时目录随 `with` 退出被删除）。

`review_action` 内部的判定顺序（第一条命中即返回）：

```text
policy-change? ─► deny(authority-boundary)
kind ∉ allowed_kinds? ─► deny(kind-allowlist)
read/write/delete: 无 target ─► deny(path-required)；越界/symlink ─► deny(workspace-jail)
command: inspect_command 失败 ─► deny(command-review)
network: 无 url / 形状错 / 白名单形状错 / 不在白名单 ─► deny(url-required / network-shape / network-policy-shape / network-allowlist)
payload 或 argv 含秘密且未走"批准后可用"通道 ─► deny 或 require-approval(secret-review)
需要审批且未批准 ─► require-approval(approval-gate)
否则 ─► allow(policy-allow)
```

---

## 3. 逐段精讲

### 3.1 三态判定与两份数据类

```python
class Verdict(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require-approval"


@dataclass(frozen=True)
class SandboxPolicy:
    workspace_root: Path
    allowed_kinds: tuple[str, ...] = ("read",)
    command_allowlist: tuple[tuple[str, ...], ...] = ()
    network_allowlist: tuple[str, ...] = ()
    approval_kinds: tuple[str, ...] = ("write", "delete", "network")
    permit_secret_use_after_approval: bool = False
```

- `Verdict` 同时继承 `str` 和 `Enum`：`Verdict.ALLOW == "allow"` 为 `True`，序列化友好。讲义把第二态叫 `ask`，代码叫 `require-approval`——同一个概念，名字不同。
- **默认值体现"默认收紧"**：`allowed_kinds` 默认只允许 `read`；命令和网络白名单默认为空；秘密通道默认关闭。
- 但注意 `approval_kinds` 默认是 `("write","delete","network")`，**不含 `command`**：白名单命令在没有不可信内容影响时会被直接 `allow`（见 3.7 与测验 Q10）。
- `frozen=True`：策略和请求一旦构造就不可修改，避免审查过程中被"顺手改掉"；用 `tuple` 而不是 `list` 也是为了不可变、可哈希。

```python
@dataclass(frozen=True)
class ActionRequest:
    kind: str
    target: str | None = None
    command: tuple[str, ...] = ()
    url: str | None = None
    payload: str = ""
    influenced_by_untrusted_content: bool = False
    approved: bool = False
    claimed_permissions: tuple[str, ...] = ()
```

- 对应讲义里的结构化请求 JSON（actor、capability、argv、cwd、paths、network、credentials、side_effect、reason）的**精简版**：没有 `actor`、`cwd`、`credentials`、`side_effect` 字段。讲义 Build It 一节说 `SandboxPolicy` 覆盖"side-effect rules"、`ReviewDecision` 包含"required approvals"，代码里其实都没有——这是讲义描述比代码多的地方。
- `claimed_permissions`：skill 或外部内容"声称"自己有的权限，代码**只把它是否非空记录下来**，从不读取其内容。

### 3.2 `ReviewDecision`：可审计的结果

```python
@dataclass(frozen=True)
class ReviewDecision:
    verdict: Verdict
    rule: str
    reason: str
    normalized_target: str | None = None
    normalized_origin: str | None = None
    claimed_permissions_ignored: bool = False
    executed: bool = False

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["verdict"] = self.verdict.value
        return data
```

- `rule` 是机器可读的规则名（`workspace-jail`、`approval-gate`…），`reason` 是人类可读解释——审批 UI 和日志都需要两者。
- `executed` 恒为 `False`：这是一个"自证"字段，提醒读者这个函数没有执行路径。
- `asdict` 会把嵌套 dataclass 递归转成字典；`verdict` 再手动换成字符串值，保证 JSON 输出是 `"allow"` 而不是枚举对象。

### 3.3 常量与秘密检测

```python
SECRET_PATTERNS = (
    re.compile(r"(?i)\b(?:api[_-]?key|access[_-]?token|secret|password)\s*[:=]\s*\S+"),
    re.compile(r"(?i)\bauthorization\s*:\s*bearer\s+\S+"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)
SHELL_METACHARACTERS = {";", "&&", "||", "|", ">", ">>", "<", "`"}
DESTRUCTIVE_EXECUTABLES = {"rm", "rmdir", "sudo", "chmod", "chown", "mkfs", "dd"}
```

- 三条正则分别抓 `api_key=...` / `password: ...` 这类键值对、`Authorization: Bearer ...` 头、PEM 私钥头。`(?i)` 忽略大小写，`\b` 是单词边界。
- 局限（讲义："Pattern matching can catch obvious credential shapes, but it cannot establish that arbitrary text is non-sensitive"）：实测 `"my password is hunter2"` 不命中（没有 `:`/`=`），`"--token=abc"` 也不命中（`token` 不在关键词表里，只有 `access_token`）。
- 元字符集合按**整个 argv 元素**比较：`("python3","-m","unittest","x;rm")` 中的 `"x;rm"` 不等于 `";"`，不会被拒。由于从不经过 shell，这本身不构成注入，但说明"元字符检查"只是形状检查。

### 3.4 `normalize_https_origin`：把 URL 变成规范 origin

```python
    parsed = urlparse(value)
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise ValueError("URL must use HTTPS, contain a host, and omit userinfo")
    if origin_only and (
        parsed.path not in {"", "/"} or parsed.params or parsed.query or parsed.fragment
    ):
        raise ValueError("allowlist entries must be HTTPS origins without path, query, or fragment")
```

- 只接受 HTTPS；拒绝 `https://user:pass@host` 这类把凭据放进 URL 的写法。
- `origin_only=True` 用于**校验白名单条目本身**：白名单里只能写 origin，写了路径（`https://api.example.test/private`）就是策略形状错误——对应测试 `test_allowlist_entries_must_be_origins`。

```python
    hostname = parsed.hostname.rstrip(".").lower()
    if not hostname or "%" in hostname:
        raise ValueError("HTTPS origin contains an invalid host")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        hostname = hostname.encode("idna").decode("ascii")
        labels = hostname.split(".")
        if len(hostname) > 253 or any(not HOST_LABEL_PATTERN.fullmatch(label) for label in labels):
            raise ValueError("HTTPS origin contains an invalid host")
        origin_host = hostname
    else:
        origin_host = address.compressed
        if address.version == 6:
            origin_host = f"[{origin_host}]"
    try:
        port = parsed.port or 443
    except ValueError as error:
        raise ValueError("HTTPS origin contains an invalid port") from error
    return f"https://{origin_host}:{port}"
```

- **主机名**：去掉尾点（`example.test.` 与 `example.test` 是同一主机）、小写；`%` 出现通常是 IPv6 zone id，直接拒绝。
- **IP 字面量**：`ipaddress.ip_address` 解析成功就用 `compressed` 形式（`2001:db8:0::1` → `2001:db8::1`），IPv6 加方括号。
- **域名**：`encode("idna")` 把 `bücher` 变成 `xn--bcher-kva`（Python 内置 codec 实现的是 IDNA 2003）；再逐标签匹配 `HOST_LABEL_PATTERN`（字母数字开头结尾、中间可有 `-`、最长 63），总长不超过 253。下划线等非法字符会被拒（实测 `a_b.example.test` → invalid host）。
- **端口**：`parsed.port` 对越界端口（如 99999）抛 `ValueError`，被转成"invalid port"；没写端口时为 `None`，于是 `or 443` 补上默认端口。
- ⚠️ **端口 0 漏洞**：`https://api.example.test:0` 的 `parsed.port` 是 `0`，`0 or 443` 得 443，于是被规范化为 `https://api.example.test:443` 并**通过白名单**（实测 `allow`）。应该用 `if port is None` 判断并校验 `1..65535`（见测验 Q9）。
- ⚠️ `https://@api.example.test` 的 `parsed.username` 是空字符串，`or parsed.username` 判不出来，会被接受。影响小，但"拒绝 userinfo"若要严格应检查 `"@" in parsed.netloc`。

### 3.5 `normalize_workspace_path`：path jail

```python
def normalize_workspace_path(workspace_root: Path, target: str) -> Path:
    root = workspace_root.resolve(strict=True)
    raw_target = Path(target)
    candidate = raw_target if raw_target.is_absolute() else root / raw_target
    resolved = candidate.resolve(strict=False)
    if resolved != root and root not in resolved.parents:
        raise SandboxViolation("path resolves outside the workspace jail")
    if candidate.is_symlink():
        raise SandboxViolation("direct symlink targets are rejected")
    return resolved
```

- `root.resolve(strict=True)`：工作区根必须真实存在，否则抛 `FileNotFoundError`（属于 `OSError`），在 `review_action` 中被转成 `deny(workspace-jail)`。
- `candidate.resolve(strict=False)`：目标可以不存在（写新文件），但路径上已存在的 symlink 和 `..` 都会被解析。这正是讲义伪代码 `realpath(join(r, p))`。
- `root not in resolved.parents`：用**路径组件**比较祖先关系，而不是字符串前缀——`/tmp/ws-evil` 字符串上以 `/tmp/ws` 开头，但 `Path("/tmp/ws")` 不在它的 `parents` 里。
- 逃逸型 symlink 在第一步就被"outside"拦下；第二步 `candidate.is_symlink()` 则**保守地拒绝所有直接 symlink**，即使它指向工作区内部（实测 `link -> a.txt` 被拒）。中间目录是 symlink 但仍指向工作区内的情况会被允许。
- 绝对路径也接受，只要解析后在工作区内（实测 `read /…/ws/a.txt` → allow）；`"."` 解析为根本身，也被允许。
- ⚠️ 讲义明说这不能解决 TOCTOU：检查和之后真正 `open` 之间路径可能被替换。

### 3.6 `inspect_command`：只看 argv，不执行

```python
    executable = command[0]
    if Path(executable).name != executable or "/" in executable or "\\" in executable:
        return False, "command must use an allowlisted bare executable name"
    if executable in DESTRUCTIVE_EXECUTABLES:
        return False, f"destructive executable {executable!r} is denied"
    if executable == "git" and len(command) > 1 and command[1] in {"clean", "reset"}:
        return False, f"destructive git subcommand {command[1]!r} is denied"
    if any(token in SHELL_METACHARACTERS for token in command):
        return False, "shell metacharacters are denied; pass a direct argv vector"
    allowed_prefixes = tuple(tuple(prefix) for prefix in allowlist)
    if not any(
        prefix and command[: len(prefix)] == prefix for prefix in allowed_prefixes
    ):
        return False, "command does not match an approved argv prefix"
    return True, "command argv matched an approved prefix in the non-executing review"
```

- **裸可执行名**：`/untrusted/python3` 的 `Path(...).name` 是 `python3`，不等于原字符串，被拒——防止"用路径伪装成白名单命令"（测试 `test_path_disguised_as_allowlisted_executable_is_denied`）。`"."` 的 `name` 是空串，同样被拒。
- **破坏性命令**优先于白名单：即使策略把 `("rm",)` 加进白名单也会被拒。`git clean` / `git reset` 单独处理（实测 `git clean -fdx` → deny）。
- **前缀白名单**：`prefix and ...` 跳过空前缀（空元组会匹配一切）；`command[: len(prefix)] == prefix` 是元组切片比较。
- ⚠️ 前缀匹配意味着**尾部参数完全不审查**：`("python3","-m","unittest","discover","-s","/etc")` 也匹配，实测 `allow`。讲义要求检查的"working directory""path-like arguments and response files""inherited environment""timeout…limits"都没有实现——代码自己的返回语句也很诚实："matched an approved prefix in the non-executing review"。

### 3.7 `review_action`：串联所有检查

```python
    if request.kind == "policy-change":
        return _decision(request, Verdict.DENY, "authority-boundary",
                         "skill or external content cannot modify the host permission model")
    if request.kind not in policy.allowed_kinds:
        return _decision(request, Verdict.DENY, "kind-allowlist", ...)
```

- `policy-change` 放在最前面，**即使策略把它列进 `allowed_kinds` 也拒绝**——权限模型只能由宿主改。
- 之后三个 `if` 分别处理文件系统、命令、网络。网络分支先规范化请求 URL，再规范化**白名单中的每一项**（`origin_only=True`），任一白名单项形状不对就整体拒绝（`network-policy-shape`），这是"策略写错就 fail-closed"。

```python
    secret_material = contains_secret(request.payload) or contains_secret(
        " ".join(request.command)
    )
    if secret_material and not (
        request.approved and policy.permit_secret_use_after_approval
    ):
        verdict = (
            Verdict.REQUIRE_APPROVAL
            if policy.permit_secret_use_after_approval
            else Verdict.DENY
        )
```

- 秘密检查在审批闸门**之前**：没开秘密通道时，`approved=True` 也是 `deny`；开了通道但未批准是 `require-approval`；开了且批准才继续往下（实测三种组合分别为 deny / require-approval / allow）。
- 注意它只扫 `payload` 和 argv，不扫 `url` 和 `target`——`https://host/?api_key=...` 这样的 URL 查询串不会被发现。

```python
    approval_needed = request.kind in policy.approval_kinds
    if request.influenced_by_untrusted_content and request.kind in {
        "write", "delete", "command", "network",
    }:
        approval_needed = True
    if approval_needed and not request.approved:
        ...
        return _decision(request, Verdict.REQUIRE_APPROVAL, "approval-gate", reason, ...)

    return _decision(request, Verdict.ALLOW, "policy-allow", ...)
```

- 两种需要审批的情况：kind 本身被策略列为需审批；或请求**受不可信内容影响**且是有状态动作（read 不算）。后者即使策略 `approval_kinds=()` 也会强制审批（测试 `test_untrusted_stateful_request_requires_approval`）。
- ⚠️ **未知 kind 会 fail-open**：如果策略把一个代码没有专门检查分支的 kind（例如 `"publish"`）列进 `allowed_kinds`，它会跳过所有检查并直接 `allow`（实测）。审查器更稳妥的写法是"没有检查器的 kind 默认拒绝"。
- `approved` 只是一个布尔值；生产中它应该是一条可验证的审批记录（谁批准、何时、针对哪个规范化目标），讲义："approval produces a narrowly scoped, immutable action record"。

### 3.8 `demo()`：七个请求

```python
    with tempfile.TemporaryDirectory(prefix="lesson-26-") as temp_dir:
        workspace = Path(temp_dir) / "workspace"
        workspace.mkdir()
        (workspace / "report.txt").write_text("safe demo data\n", encoding="utf-8")
        policy = SandboxPolicy(
            workspace_root=workspace,
            allowed_kinds=("read", "write", "delete", "command", "network"),
            command_allowlist=(("python3", "-m", "unittest"),),
            network_allowlist=("https://docs.example.test",),
        )
```

- 用临时目录做工作区，`with` 结束自动删除——所以输出里的 `normalized_target` 是一个已不存在的 `/tmp/lesson-26-xxxx/...` 路径。
- 7 个请求依次覆盖：带自称权限的读、未批准的写、已批准的写、`..` 逃逸、已批准的 `rm -rf`、受不可信内容影响的网络请求、策略修改。
- `print` 在 `with` 块之外，但 `result` 已在块内计算完毕，不受目录删除影响。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 只判定、不执行 | 教学聚焦决策边界，跑 demo/测试零副作用 | 真实执行器需在启动前**重新校验**规范化目标并独立应用 sandbox |
| 冻结 dataclass + tuple | 请求与策略不可变，可安全传递 | 需要 JSON 输入时要额外做类型校验（bundle 脚本用 `strict_bool` 做了） |
| 第一条命中即返回 | 判定可解释：一个规则名对应一个原因 | 只报告第一个问题，修完一个才看到下一个；审计时可能想要全部违规项 |
| 解析后判断包含 + 拒绝直接 symlink | 防 `..` 与 symlink 逃逸，保守简单 | 不解决 TOCTOU；生产用 `openat2(RESOLVE_BENEATH)`/挂载命名空间 |
| argv 前缀白名单 | 简单、可读 | 尾部参数、cwd、环境都不审查；生产用窄工具 + 类型化参数 |
| 破坏性命令黑名单 | 演示"审批也无法覆盖"的硬边界 | 黑名单永远不全（`find -delete`、`python -c` 等）；真正的控制是白名单 + 隔离 |
| origin 精确匹配 + 默认端口规范化 | 防大小写、尾点、IDNA、默认端口造成的绕过 | `parsed.port or 443` 让端口 0 漏网；重定向、DNS 解析结果不在审查范围 |
| 正则秘密检测 | 能抓明显形态，示范"秘密需要单独通道" | 漏报多；生产需数据分类 + 目的地策略 + 日志脱敏 |
| 未知 kind 不设检查器 | 代码简短 | 会 fail-open；应改为 default-deny |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件第一行 | 注解延迟求值，可在旧版本使用 `str \| None` 等新写法 |
| `str` + `Enum` 多继承 | `class Verdict(str, Enum)` | 枚举成员同时是字符串，可直接与 `"allow"` 比较、被 `json.dumps` 序列化 |
| `@dataclass(frozen=True)` | `SandboxPolicy`、`ActionRequest` | 自动生成 `__init__`/`__eq__`；frozen 后赋值会抛 `FrozenInstanceError` |
| 类型注解 | `tuple[str, ...]`、`str \| None`、`tuple[tuple[str, ...], ...]` | 变长元组、可空类型、嵌套元组 |
| `dataclasses.asdict` | `data = asdict(self)` | 把 dataclass 递归转成字典 |
| 自定义异常 | `class SandboxViolation(ValueError)` | 继承内置异常，调用方可精确捕获 |
| 预编译正则 | `re.compile(r"(?i)\b...")` | `r""` 原始字符串避免转义；`(?i)` 行内忽略大小写 |
| `any()` + 生成器 | `any(pattern.search(value) for pattern in SECRET_PATTERNS)` | 短路求值，找到一个就停 |
| 仅限关键字参数 | `def normalize_https_origin(value, *, origin_only=False)` | `*` 之后的参数必须写成 `origin_only=True` |
| 异常链 | `raise ValueError(...) from error` | 保留原始异常作为 `__cause__`，便于排错 |
| `try / except / else` | `ipaddress.ip_address(hostname)` 那段 | `else` 只在没有异常时执行 |
| `or` 取默认值 | `parsed.port or 443` | 左值为假（含 `None` 和 `0`）时取右值——本文件的端口 0 漏洞正源于此 |
| f-string `!r` | `f"destructive executable {executable!r} is denied"` | 用 `repr()` 显示，字符串带引号 |
| `pathlib` | `Path(target).is_absolute()`、`.resolve(strict=False)`、`.parents`、`.is_symlink()` | 面向对象的路径操作；`/` 运算符拼接路径 |
| 元组切片比较 | `command[: len(prefix)] == prefix` | 判断前缀 |
| 集合推导式 | `{normalize_https_origin(o, origin_only=True) for o in policy.network_allowlist}` | 生成去重集合，`in` 查找 O(1) |
| 多异常捕获 | `except (OSError, SandboxViolation) as error` | 元组里列出多个异常类型 |
| 上下文管理器 | `with tempfile.TemporaryDirectory(prefix="lesson-26-") as temp_dir` | 退出时自动删除临时目录 |
| `json.dumps` | `json.dumps(result, indent=2, sort_keys=True)` | 缩进、键排序，输出稳定可比对 |
| `if __name__ == "__main__"` | 文件末尾 | 被测试导入时不运行 demo |

---

## 6. 运行结果解读

实际运行（Python 3.13，`python3 main.py`，退出码 0）。为便于阅读，下面按请求顺序整理成表（`normalized_target` 中的临时目录名每次不同）：

| # | 请求 | verdict | rule | reason / 规范化结果 |
|---|------|---------|------|-------------------|
| 1 | `read report.txt`，`claimed_permissions=("all",)` | `allow` | `policy-allow` | `claimed_permissions_ignored: true`；目标 `/tmp/lesson-26-…/workspace/report.txt` |
| 2 | `write summary.json` | `require-approval` | `approval-gate` | `host policy gates 'write' behind approval` |
| 3 | `write summary.json`，`approved=True` | `allow` | `policy-allow` | `request stayed within the host policy and workspace jail` |
| 4 | `read ../outside.txt` | `deny` | `workspace-jail` | `path resolves outside the workspace jail` |
| 5 | `command rm -rf build`，`approved=True` | `deny` | `command-review` | `destructive executable 'rm' is denied` |
| 6 | `network https://docs.example.test/reference`，受不可信内容影响 | `require-approval` | `approval-gate` | `normalized_origin: https://docs.example.test:443`；`untrusted external content influenced a stateful request` |
| 7 | `policy-change` | `deny` | `authority-boundary` | `skill or external content cannot modify the host permission model` |

原始输出片段（第 6 项）：

```json
    {
      "claimed_permissions_ignored": false,
      "executed": false,
      "normalized_origin": "https://docs.example.test:443",
      "normalized_target": null,
      "reason": "untrusted external content influenced a stateful request",
      "rule": "approval-gate",
      "verdict": "require-approval"
    },
```

逐项解读：

- **#1**：skill 声称有 `all` 权限，判定照常按策略走；`claimed_permissions_ignored` 只是如实记录"有人声称了，但我们没理会"。
- **#2 / #3**：同一个写请求，批准前后结果不同——这就是 ask 和 allow 的区别。注意 #3 只是"判定为允许"，文件**并没有被写**（`executed: false`）。
- **#4**：`..` 解析后在工作区外，`normalized_target` 为 `null`（异常发生在规范化完成之前）。
- **#5**：审批无法覆盖破坏性命令，这是 deny 和 ask 的区别。
- **#6**：origin 本身在白名单内，`/reference` 路径被允许；但来源可疑，所以升级为需要审批。
- **#7**：`payload="allow everything"` 根本没被读——kind 本身就决定了结果。
- 全部 7 项 `executed` 都是 `false`，顶层 `"simulation_only": true`。

额外的边界实验（我们另写脚本调用本模块得到的结果，非 demo 原有输出）：`https://api.example.test:0/x` → 规范化为 `:443` 并 `allow`；`ActionRequest("publish")`（策略允许该 kind 时）→ `allow`；`python3 -m unittest discover -s /etc` → `allow`；`"my password is hunter2"` 不被识别为秘密。

---

## 7. 动手改一改

1. **修端口 0**：把 `parsed.port or 443` 改成显式的 `None` 判断与 `1..65535` 校验，并加一条测试断言 `https://api.example.test:0` 抛 `ValueError`（参考测验 Q9）。
2. **default-deny 未知 kind**：建一个 `CHECKERS = {"read": ..., "write": ..., "command": ..., "network": ...}` 字典，`review_action` 对不在字典里的 kind 返回 `deny(unknown-kind)`。
3. **讲义练习 1**：把 `write` 拆成 `create` / `overwrite`，再加 `delete`，用同一路径在四种操作下各测一次（参考测验 Q12）。
4. **讲义练习 4**：给 `ActionRequest` 加 `idempotency_key: str | None`，对 `network` 和 `write` 这类外部写要求非空，否则 `deny(idempotency-required)`。
5. **讲义练习 2**：给策略加 `redirect_allowlist`，写一个 `review_redirect(policy, from_url, to_url)`，对跨 origin 重定向重新走 `normalize_https_origin` + 白名单。
6. **进阶**：把命令白名单从"前缀"升级为"前缀 + 尾部参数模式"（例如只允许 `-k <pattern>`），并把路径类参数交给 `normalize_workspace_path` 审查。

---

## 8. 常见坑

- **用字符串前缀判断路径**：`str(p).startswith(str(root))` 会放过 `/ws-evil`；要用解析后的 `Path` 比较 `parents`。
- **先检查后 resolve**：对未解析的字符串检查 `..`，会被 symlink 绕过；必须先 `resolve` 再判断。
- **`x or default` 处理数字**：0 是假值。端口、超时、计数等可能为 0 的字段要用 `is None` 判断。
- **把审批当万能钥匙**：破坏性命令、未开通的秘密通道、策略修改，在本代码里批准了也是 `deny`。
- **白名单 origin 里写路径**：`https://api.example.test/private` 不是 origin，会让整个网络策略失效（`network-policy-shape`）。
- **以为 `allow` 就会执行**：本模块的 `allow` 只是判定，真正执行还需要独立的 sandbox 和执行前复核。
- **把正则秘密检测当数据分类**：漏报很常见，不能据此断言"这段文本不敏感"。
- **未知 kind fail-open**：给策略加新 kind 前，先确认审查器有对应的检查分支。

---

## 9. 测试在验证什么

运行方式（在 `code/` 目录下）：`python3 -m unittest discover -s tests -v`。实际结果：**18 个测试全部通过**（`Ran 18 tests in 0.020s, OK`）。测试文件开头设置 `sys.dont_write_bytecode = True` 并把 `code/` 加入 `sys.path`，因此不会产生 `__pycache__`。

| 测试 | 验证的性质 |
|------|-----------|
| `test_skill_claimed_permission_is_ignored` | 自称的 `workspace-admin` 权限不改变判定（仍是普通 `allow`），但 `claimed_permissions_ignored=True` |
| `test_relative_path_is_normalized_inside_workspace` | 不存在的相对路径 `notes/output.txt` 也能规范化到工作区内 |
| `test_parent_traversal_is_denied` | `../outside.txt` → `deny(workspace-jail)` |
| `test_symlink_escape_is_denied` | 工作区内指向外部文件的 symlink → `deny(workspace-jail)`（无 symlink 支持时跳过） |
| `test_write_requires_approval` | 默认策略下写需要审批，且 `executed=False` |
| `test_approved_write_is_allowed_but_not_executed` | 批准后 `allow`，但目标文件**确实不存在**——证明没有执行 |
| `test_destructive_command_is_denied_even_if_approved` | `rm -rf` 批准了也是 `deny(command-review)` |
| `test_allowlisted_command_is_only_classified` | 白名单命令返回 `True`，原因里含 "non-executing" |
| `test_path_disguised_as_allowlisted_executable_is_denied` | `/untrusted/python3` 被拒，原因含 "bare executable" |
| `test_network_origin_must_be_exactly_allowlisted` | 非白名单 origin，批准了也 `deny(network-allowlist)` |
| `test_https_default_port_is_normalized_before_matching` | 隐式与显式 443 都规范化为 `https://api.example.test:443` 并放行 |
| `test_non_default_port_requires_its_own_origin_entry` | `:8443` 默认被拒；白名单显式加 `:8443` 后放行 |
| `test_allowlist_entries_must_be_origins` | 白名单项带路径 → `deny(network-policy-shape)` |
| `test_origin_normalization_handles_ipv6_and_idna` | `[2001:db8::1]` 保留方括号；`BÜCHER.example` → `xn--bcher-kva.example` |
| `test_untrusted_stateful_request_requires_approval` | 即使 `approval_kinds=()`，受不可信内容影响的命令也要审批 |
| `test_external_text_cannot_change_policy` | `policy-change` → `deny(authority-boundary)` |
| `test_secret_patterns_are_reviewed` | Bearer 头被识别；带 `api_key=` 的写请求 → `deny(secret-review)` |
| `test_bundled_reviewer_enforces_claimed_boundaries` | 用 `importlib` 加载 `outputs/skill-safety-reviewer/scripts/review_action.py`（JSON 版审查器），验证秘密、不可信内容、URL userinfo、精确 origin、错误端口、伪装可执行文件、字符串 `"false"` 当布尔值（`boolean-shape`）、`approvalKinds` 写成字符串（`policy-shape`）等 8 种情况 |

测试没有覆盖的点（也就是本讲解指出的问题）：端口 0、空 userinfo、未知 kind fail-open、前缀白名单的尾部参数、`url`/`target` 中的秘密。最后一个测试也说明：bundle 脚本复制了一份 `normalize_https_origin`，两处代码需要同步维护，修端口 0 漏洞时两边都要改。
