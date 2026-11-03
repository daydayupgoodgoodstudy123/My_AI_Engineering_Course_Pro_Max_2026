# 代码讲解 · probe.py

> **所属小节**：阶段 13 · 工具与协议 · 第 26 节 Skill 权限、Sandboxes 与信任 ｜ 讲义：[../../docs/zh.md](../../docs/zh.md) ｜ 测验：[../../quiz/quiz.md](../../quiz/quiz.md) ｜ 主文件讲解：[../main.讲解.md](../main.讲解.md)
>
> **运行方式**：设计为在容器内运行（见下方 `docker build` / `docker run` 命令），入口为 `python3 -I /app/probe.py` ｜ **依赖**：仅标准库（`json`、`os`、`socket`、`pathlib`、`typing`）；外部需要 Docker（或其它 OCI 运行时）和 `python:3.13-alpine` 基础镜像

同目录还有两个配套文件，一并在此说明：

- `Containerfile`：以 `python:3.13-alpine` 为基础，把 `probe.py` 复制到 `/app`，切换到 UID/GID `65532`（非 root），入口 `python3 -I /app/probe.py`（`-I` 隔离模式：忽略 `PYTHON*` 环境变量和用户 site-packages；Python 3.11+ 中还隐含 `-P`，不把脚本所在目录加进 `sys.path`）。
- `input/message.txt`：内容为 `declared read-only input`，运行时以只读 bind mount 挂到容器的 `/input`。

---

## 1. 这份代码在考察什么

`main.py` 演示的是**执行前的策略审查**；`probe.py` 演示的是**执行时的隔离边界**。讲义："Policy review and isolation are different controls." 它在容器里依次尝试四件事，并把结果打印成 JSON：

| 探测 | 期望结果 | 对应的 `docker run` 参数 |
|------|---------|------------------------|
| 读声明的输入 `/input/message.txt` | 成功 | `--mount type=bind,...,dst=/input,readonly` |
| 写镜像文件系统 `/app/escape.txt` | 失败 | `--read-only`（以及非 root 用户） |
| 写并读回 `/tmp/probe.txt` | 成功 | `--tmpfs /tmp:rw,noexec,nosuid,size=16m` |
| 连接 `example.com:443` | 失败 | `--network none` |
| 环境变量 `DEMO_VALUE` | 等于 `bounded` | `--env DEMO_VALUE=bounded` |

> 一句话：**用一个无害的探针"观察"容器确实施加了边界，而不是只在文档里声称有边界**——同时也要看清这个探针能证明什么、不能证明什么。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `attempt(operation)` | 函数 | 执行一个零参函数，把成功/异常统一包装成 `{"ok": ..., ...}` | 结构化输出 |
| `read_input` | 函数 | 读只读挂载的输入 | 声明的输入 |
| `write_image` | 函数 | 试图写 `/app/escape.txt` | 只读根文件系统 |
| `write_temporary` | 函数 | 写 `/tmp/probe.txt` 并读回 | 有界的临时可写空间 |
| `open_network` | 函数 | 1 秒超时连 `example.com:443` | 网络出站策略 |
| `main` | 函数 | 汇总报告、计算 `passed`、按结果设置退出码 | 验证闸门 |

数据流：`main()` → 四次 `attempt(...)` → 组装 `report`（含全部可见环境变量名）→ 计算 `passed` → `print(json.dumps(...))` → `SystemExit(0 或 1)`。

---

## 3. 逐段精讲

### 3.1 `attempt`：把异常变成数据

```python
def attempt(operation: Callable[[], str]) -> dict[str, object]:
    try:
        return {"ok": True, "result": operation()}
    except Exception as error:
        return {"ok": False, "error": type(error).__name__}
```

- 传入的是**函数对象**而不是调用结果，`attempt` 自己负责调用并捕获异常——一个小型的"高阶函数"。
- 失败时只记录异常**类型名**（如 `PermissionError`、`gaierror`），不记录消息文本：消息里可能带路径、主机名等细节，结构化输出只保留判断所需的最少信息。这也符合讲义"脚本应该无聊"：确定性、结构化输出。
- `except Exception` 捕获面很宽，任何意外错误都会被记为"失败"——对于"期望失败"的探测（写镜像、连网络）这会导致**假阳性的"隔离生效"**（见 3.4、3.5）。

### 3.2 读输入与写临时目录

```python
def read_input() -> str:
    return Path("/input/message.txt").read_text(encoding="utf-8").strip()

def write_temporary() -> str:
    target = Path("/tmp/probe.txt")
    target.write_text("bounded\n", encoding="utf-8")
    return target.read_text(encoding="utf-8").strip()
```

- `/input` 是只读 bind mount：能读，说明"声明的输入"确实可达。
- `/tmp` 是 `tmpfs`：在 `--read-only` 根文件系统上，这是唯一可写的地方，而且 `size=16m` 限制了容量，`noexec` 禁止从这里执行文件，`nosuid` 忽略 setuid 位。探针只验证了"可写"，并没有验证 `noexec` 和容量上限。

### 3.3 写镜像文件系统

```python
def write_image() -> str:
    target = Path("/app/escape.txt")
    target.write_text("unexpected\n", encoding="utf-8")
    return str(target)
```

- 期望在 `--read-only` 下抛 `OSError`（`EROFS`，Read-only file system）。
- ⚠️ **这个探测不能单独证明 `--read-only` 生效**：Containerfile 中 `WORKDIR /app` 和 `COPY` 都以 root 身份执行，`/app` 归 root 所有；运行时 `USER 65532:65532` 是普通用户，本来就没有写 `/app` 的权限。即使忘了 `--read-only`，这里也会因为 `PermissionError` 失败，`passed` 照样为真（这是根据 Containerfile 推断；本环境没有 Docker 守护进程，未能在容器里实际验证）。要让失败只能归因于只读根文件系统，应写一个非 root 用户**本来有权写**的路径，例如构建时 `RUN mkdir /app/writable && chown 65532:65532 /app/writable`，或者检查 `/proc/self/mountinfo` 中根挂载是否带 `ro`。

### 3.4 网络探测

```python
def open_network() -> str:
    with socket.create_connection(("example.com", 443), timeout=1.0) as connection:
        return str(connection.getpeername())
```

- `create_connection` 会先做 DNS 解析，再建立 TCP 连接；`with` 保证连接关闭。
- 在 `--network none` 下容器只有 loopback，DNS 解析失败，抛 `socket.gaierror`。
- ⚠️ 失败原因不加区分：DNS 被屏蔽但直连 IP 的出站仍开放时，探针也会报 `gaierror` 并认为"网络已隔离"；网络很慢、1 秒超时也会被当成"隔离生效"。更可靠的做法是同时尝试 IP 字面量（TCP 443）和 UDP 53，并在报告里区分 `gaierror` / `ConnectionRefusedError` / `TimeoutError`。

### 3.5 汇总与退出码

```python
    report = {
        "declaredInput": input_result,
        "imageFilesystemWrite": image_write,
        "temporaryWrite": temporary_write,
        "networkConnection": network,
        "visibleEnvironmentNames": sorted(os.environ),
        "declaredEnvironmentValue": os.environ.get("DEMO_VALUE"),
    }
    report["passed"] = bool(
        input_result["ok"]
        and not image_write["ok"]
        and temporary_write["ok"]
        and not network["ok"]
        and report["declaredEnvironmentValue"] == "bounded"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    raise SystemExit(0 if report["passed"] else 1)
```

- `sorted(os.environ)`：对字典排序得到的是**键名**列表，只暴露变量名不暴露值——查看"容器里有哪些环境变量"而不泄露秘密值。
- ⚠️ `passed` **没有检查** `visibleEnvironmentNames`。讲义说"The container receives no host credential variables"，但如果有人用 `--env-file` 塞进了 `AWS_SECRET_ACCESS_KEY`，`passed` 依然为真。应加一个环境变量白名单检查。
- 通过退出码表达结果（0/1），便于 CI 或执行器直接据此判断，这是讲义"Return distinct exit codes"的简化版。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用真实容器而非模拟 | 观察**被强制执行**的边界 | 依赖本地 Docker；仍共享宿主内核（讲义明确指出） |
| 探针本身无害 | 写的都是自己的小文件，连的是公共域名 | 生产的隔离测试还应覆盖 `noexec`、pids 上限、内存上限、capabilities |
| 只记录异常类型名 | 输出简洁、不泄露细节 | 无法区分"因为只读失败"与"因为没权限失败" |
| 非 root 用户 + `--read-only` 双重防护 | 纵深防御 | 让"写镜像失败"这一项失去区分度 |
| `FROM python:3.13-alpine` | 小巧、易得 | 未按 digest 固定，讲义也提醒"Pin the base image by digest" |
| 退出码表示通过与否 | 机器可读 | `passed` 的条件不完整（未检查凭据环境变量） |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 模块文档字符串 | `"""Probe observable container boundaries ..."""` | 文件第一个字符串字面量，`help()` 可见 |
| `Callable` 类型注解 | `operation: Callable[[], str]` | "无参数、返回 `str` 的可调用对象" |
| 函数作为参数 | `attempt(read_input)` | 传函数对象本身，不加括号 |
| `try / except Exception` | `attempt` 内部 | 捕获几乎所有异常（不含 `KeyboardInterrupt`、`SystemExit`） |
| `type(error).__name__` | `{"ok": False, "error": type(error).__name__}` | 取异常类名字符串 |
| `pathlib` 读写 | `Path(...).read_text(encoding="utf-8")`、`.write_text(...)` | 一行完成打开、读写、关闭 |
| `with` 管理网络连接 | `with socket.create_connection(...) as connection:` | 退出时自动关闭 socket |
| `sorted(dict)` | `sorted(os.environ)` | 迭代映射得到键，排序后返回列表 |
| `dict.get` | `os.environ.get("DEMO_VALUE")` | 不存在时返回 `None`，不抛 `KeyError` |
| `and` 链 + `bool()` | `report["passed"] = bool(... and ...)` | 短路求值，最终转为布尔值 |
| `raise SystemExit(code)` | `raise SystemExit(0 if report["passed"] else 1)` | 以指定退出码结束进程；条件表达式选择 0/1 |
| `python3 -I` | Containerfile 的 `ENTRYPOINT` | 隔离模式，不受 `PYTHONPATH` 等环境变量影响 |

---

## 6. 运行结果解读

**未能在容器中实际运行**，原因：本环境虽然装有 docker CLI，但没有 Docker 守护进程（`docker info` 报 `failed to connect to the docker API at unix:///var/run/docker.sock`），也无法拉取基础镜像。

讲义描述的预期结果（在容器内按讲义参数运行时）：

- `declaredInput.ok = true`，`result = "declared read-only input"`；
- `imageFilesystemWrite.ok = false`（错误类型应为 `OSError` 或 `PermissionError`，见 3.3）；
- `temporaryWrite.ok = true`，`result = "bounded"`；
- `networkConnection.ok = false`（应为 `gaierror`）；
- `declaredEnvironmentValue = "bounded"`，`passed = true`，退出码 0。

作为对照，我们在容器**外**做了一次替身运行：用一个包装脚本导入 `probe`，把 `/input`、`/app`、`/tmp` 三个路径重定向到临时目录（"镜像目录"设为 `chmod 555`），并设置 `DEMO_VALUE=bounded`，以 root 身份执行 `probe.main()`。实际输出摘要：

```text
declaredInput:        {"ok": true,  "result": "declared read-only input"}
imageFilesystemWrite: {"ok": true,  "result": ".../p26/ro/escape.txt"}   ← root 无视 555 权限，写成功
temporaryWrite:       {"ok": true,  "result": "bounded"}
networkConnection:    {"ok": false, "error": "gaierror"}                 ← 本沙盒无 DNS
visibleEnvironmentNames: 205 个变量名
passed: false，退出码 1
```

解读：

- 在没有容器边界时，探针正确地报告 `passed: false`——说明它不是"永远通过"的摆设。
- "写镜像"那一项在 root 下成功，反过来说明这项检查的结果**取决于运行身份**：容器里以 UID 65532 运行时，即使不加 `--read-only` 也会失败（3.3 的推断）。
- 网络项报 `gaierror`：本沙盒没有 DNS，和 `--network none` 的表现相同，但两者原因不同——这正是"只看 DNS 失败"会产生误判的例子。
- 可见环境变量有 205 个，而 `passed` 对此不做任何判断。

---

## 7. 动手改一改

1. **让只读检查有区分度**：在 Containerfile 加 `RUN mkdir /app/writable && chown 65532:65532 /app/writable`，探针改写 `/app/writable/escape.txt`；分别带和不带 `--read-only` 运行，比较结果。
2. **区分网络失败原因**：新增 `open_network_ip()` 连接 `("1.1.1.1", 443)`，报告中保留异常类型，`passed` 要求两项都失败。
3. **环境变量白名单**：定义 `ALLOWED_ENV = {"PATH", "HOME", "HOSTNAME", "LANG", "GPG_KEY", "PYTHON_VERSION", "PYTHON_SHA256", "DEMO_VALUE"}`（以实际镜像为准），出现白名单外的名字即 `passed = False`。
4. **验证 `noexec`**：把一个脚本写进 `/tmp` 并 `chmod +x`，尝试用 `subprocess.run` 执行，期望 `PermissionError`。
5. **验证资源上限**：在一个子进程里 fork 超过 64 个进程或分配超过 128 MB 内存，观察 `--pids-limit` / `--memory` 的效果（注意只在一次性容器中做）。
6. **固定镜像**：把 `FROM python:3.13-alpine` 改为 `FROM python:3.13-alpine@sha256:<digest>`，并在 README 中记录 digest 的来源。

---

## 8. 常见坑

- **以为"写失败"就等于"只读生效"**：非 root 用户、目录权限、SELinux 都会导致写失败，探针要设计成只有一个原因能导致失败。
- **以为"连不上 example.com"就等于"无出站"**：可能只是 DNS 不通；直连 IP、UDP、代理环境变量都要考虑。
- **容器 ≠ 安全边界的全部**：讲义"This drill still shares the host kernel"；挂载宿主 Docker socket 或 home 目录会让边界失去意义。
- **在宿主上直接运行 probe.py**：它会尝试在 `/app`、`/tmp` 写文件、连接外网；以 root 运行时还可能真的写成功。只在一次性容器中运行。
- **忽略 `-I`**：去掉 `-I` 后，`PYTHONPATH` 等环境变量可以影响导入，让探针加载到非预期的代码。
