# 代码讲解 · verify.py

> **所属小节**：阶段 00 · 环境搭建与工具 · 第 01 节 开发环境 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**（在仓库根目录执行）：`python3 phases/00-setup-and-tooling/01-dev-environment/code/verify.py [--route {beginner,ml-foundations,llm-engineering,agents,mcp,agent-skills,certification}] [--show-later]`，默认 `--route beginner` ｜ **依赖**：仅 Python 标准库（`argparse`、`importlib.util`、`platform`、`shutil`、`subprocess`、`sys`、`dataclasses`、`typing`）；`torch` 是**被检测对象**而非依赖，没装也能运行

---

## 1. 这份代码在考察什么

这是课程的第一个脚本：一个**按学习路线区分的环境预检（preflight）工具**。它本身不涉及任何 AI 算法，但浓缩了很多工程好习惯：

1. **按需检查**：不同路线（入门、ML 基础、LLM 工程、Agent、MCP……）需要的工具不同，只检查"开始这条路线必需的"，其余默认跳过，避免新手一上来就面对一墙警告。
2. **可执行的反馈**：每个失败项都给出"检测到了什么"（路径、版本、导入错误）+ "具体运行哪条命令修复"，而不是一句笼统的"请安装 Node"。
3. **数据驱动设计**：工具检查（`PROBES`）和路线（`ROUTES`）都是**表**，主流程只负责遍历；新增工具或路线只需要改数据。
4. **可靠地调用外部命令**：`shutil.which` 找命令、`subprocess.run` 加超时、捕获异常、解析版本号。
5. **对 CI 友好**：用进程退出码（0 / 1 / 2）表达结果，脚本可以直接放进自动化流水线。

> 一句话：**用 300 行标准库代码，示范一个"只说该说的、说了就能照做"的诊断工具应该长什么样。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Result` | 冻结 dataclass | 一次检查的结果：`ok`（是否通过）+ `detail`（细节说明） | 统一的结果类型 |
| `Probe` | 冻结 dataclass | 一个探针：显示名、检查函数、修复命令 | 检查项抽象 |
| `Route` | 冻结 dataclass | 一条学习路线：必需项、可选项、下一步命令、人工检查项 | 按路线预检 |
| `command_result()` | 函数 | 检查命令行工具是否存在、能否运行、版本是否达标 | 四层栈中的运行时/包管理器 |
| `python_result()` | 函数 | 检查当前解释器版本 ≥ 3.11 | 运行时层 |
| `module_result()` | 函数 | 检查 Python 包能否被当前解释器找到 | AI/ML 库层 |
| `gpu_result()` | 函数 | 检查 PyTorch 能用 CUDA、MPS 还是只有 CPU | GPU 验证（讲义第 6 步） |
| `git_fix()` | 函数 | 按操作系统返回不同的 git 安装命令 | 系统基础层 |
| `PROBES` / `BASE_OPTIONAL` / `ROUTES` | 模块级字典/元组 | 所有检查项和路线的"配置表" | 数据驱动 |
| `parse_args()` | 函数 | 解析 `--route` 和 `--show-later` | 命令行接口 |
| `print_probe()` | 函数 | 运行一个探针并打印 PASS/FAIL/LATER | 结果呈现 |
| `main()` | 函数 | 串起整个流程，返回退出码 | 入口 |

数据流：`parse_args()` 得到路线名 → 查 `ROUTES` 得到 `Route` → 对每个必需项 key 查 `PROBES` 得到 `Probe` → `print_probe()` 调用 `probe.run()` 拿到 `Result` 并打印 → `main()` 统计通过数、决定返回 0 还是 1 → `raise SystemExit(...)` 变成进程退出码。

---

## 3. 逐段精讲

### 3.1 文件头：`from __future__ import annotations` 的隐藏作用

```python
from __future__ import annotations

import argparse
import importlib.util
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Callable
```

- 全部是标准库——**环境检查脚本自己不能依赖还没装的东西**，否则"检查工具"本身就跑不起来。
- `from __future__ import annotations` 让所有类型注解延迟为字符串、不在定义时求值。后面的 `minimum_major: int | None` 这种 `X | Y` 写法是 Python 3.10 才支持的；有了这一行，脚本在更老的 Python 上也能**正常加载**，然后由 `python_result()` 友好地报告"需要 3.11+"。
- 实测：用 Python 3.9 运行原文件，会正常打印 `[FAIL] Python 3.11+ ... need Python 3.11+`；而删掉 `__future__` 这一行后，3.9 在定义 `command_result` 时就崩溃：`TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'`。
- 这就是"版本检查器必须能在旧版本上运行"的设计意识：它要检查的恰恰是"版本不够"的情况。

### 3.2 三个冻结 dataclass：把"结果 / 探针 / 路线"建模清楚

```python
@dataclass(frozen=True)
class Result:
    ok: bool
    detail: str


@dataclass(frozen=True)
class Probe:
    label: str
    run: Callable[[], Result]
    fix: str


@dataclass(frozen=True)
class Route:
    label: str
    required: tuple[str, ...]
    optional: tuple[str, ...]
    next_command: str
    manual: tuple[str, ...] = ()
```

- `@dataclass` 自动生成 `__init__`、`__repr__`、`__eq__`，省去样板代码。
- `frozen=True` 让实例**不可修改**（赋值会抛 `FrozenInstanceError`）。这些对象本质是配置常量，不可变能防止某处代码误改了全局路线表。
- `Probe.run` 的类型是 `Callable[[], Result]`：一个"不接收参数、返回 `Result`"的函数。存的是**函数本身**，而不是结果——这是"延迟执行"的关键（见 3.6）。
- `Route` 用 `tuple` 而不是 `list`，同样是为了不可变；`manual` 给了默认值 `()`，所以大多数路线可以不写这个字段。⚠️ 注意 dataclass 规则：有默认值的字段必须放在没有默认值的字段后面，`manual` 放在最后正是因此。
- `tuple[str, ...]` 表示"任意长度、元素都是 str 的元组"。

### 3.3 `command_result`：可靠地检查一个命令行工具

```python
def command_result(command: str, minimum_major: int | None = None) -> Result:
    path = shutil.which(command)
    if path is None:
        return Result(False, f"{command!r} was not found on PATH")

    try:
        process = subprocess.run(
            [path, "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return Result(False, f"could not run {path}: {exc}")

    output = (process.stdout or process.stderr).strip().splitlines()
    detail = output[0] if output else f"exit code {process.returncode} with no version output"
    if process.returncode != 0:
        return Result(False, detail)
```

逐步拆解，这是一个三道关卡的检查：

1. **在不在**：`shutil.which(command)` 模拟 shell 在 `PATH` 里查找可执行文件，找不到返回 `None`。先查再跑，比直接运行再捕获 `FileNotFoundError` 更清晰，还能在结果里报告**具体路径**（多个版本并存时非常有用）。
2. **能不能跑**：
   - 参数用**列表** `[path, "--version"]`，不经过 shell，没有注入和引号转义问题。
   - `check=False`：返回码非 0 时不抛异常，由我们自己判断。
   - `capture_output=True, text=True`：把 stdout/stderr 捕获为字符串，而不是直接打到终端。
   - `timeout=5`：防止某个工具卡住导致整个预检挂起。超时抛出的 `TimeoutExpired` 是 `SubprocessError` 的子类，会被 `except` 捕获。
   - `OSError` 覆盖"文件存在但没有执行权限"等系统级错误。
3. **输出取第一行**：`(process.stdout or process.stderr)`——有的工具把版本号打印到 stderr，这里 stdout 为空字符串时自动退回 stderr。`.strip().splitlines()` 去掉首尾空白再按行切分，取第一行作为 `detail`。

```python
    if minimum_major is not None:
        digits = "".join(character if character.isdigit() else " " for character in detail)
        parts = digits.split()
        if not parts:
            return Result(False, f"could not parse a version from {detail!r}")
        major = int(parts[0])
        if major < minimum_major:
            return Result(False, f"found {detail}; need version {minimum_major}+")

    return Result(True, f"{detail} at {path}")
```

- **版本号解析**：把非数字字符全部替换成空格，再 `split()`，取第一个数字串当主版本号。`"v22.22.0"` → `" 22 22 0"` → `['22', '22', '0']` → `22`。
- 只有 Node 用到了 `minimum_major=20`（讲义要求 Node 20+）。
- ⚠️ 刻意的简化：只比较主版本号，且假设"第一个数字就是版本号"。如果某个工具的版本行在版本号前面出现了其他数字（例如名字里带数字），就会解析错。生产中可以用正则 `r"(\d+)\.(\d+)"` 或 `packaging.version` 做更严谨的解析。
- 成功时 `detail` 拼上 `at {path}`，失败的版本不足分支**不带路径**——读输出时留意这点。

### 3.4 `python_result` 与 `module_result`：检查解释器和包

```python
def python_result() -> Result:
    version = platform.python_version()
    executable = sys.executable
    if sys.version_info < (3, 11):
        return Result(False, f"found Python {version} at {executable}; need Python 3.11+")
    return Result(True, f"Python {version} at {executable}")


def module_result(module: str) -> Result:
    if importlib.util.find_spec(module) is None:
        return Result(False, f"{module!r} is not importable by {sys.executable}")
    return Result(True, f"importable by {sys.executable}")
```

- Python 不用 `command_result("python3")` 检查，而是检查**正在运行这个脚本的解释器**本身：`sys.version_info` 是一个可比较的元组，`(3, 9, 25, ...) < (3, 11)` 按元素逐个比较。
- 两个函数都打印 `sys.executable`（当前解释器的绝对路径）。这是排查"装了包却 import 不到"的头号线索：**包装进了 A 环境，脚本却用 B 解释器在跑**。
- `importlib.util.find_spec(module)` 只问"能不能找到这个模块"，**并不真正导入**。好处是快、没有副作用（导入 `torch` 可能要好几秒）。
- ⚠️ 代价：`find_spec` 找得到不等于能成功导入——比如 torch 装了但依赖的动态库不匹配。所以下面的 `gpu_result` 选择真正 `import torch`。

### 3.5 `gpu_result`：CUDA → MPS → CPU 的降级检测

```python
def gpu_result() -> Result:
    if importlib.util.find_spec("torch") is None:
        return Result(False, "PyTorch is not installed, so no accelerator backend was checked")

    try:
        import torch
    except Exception as exc:
        return Result(False, f"PyTorch could not be imported: {type(exc).__name__}: {exc}")

    if torch.cuda.is_available():
        return Result(True, f"CUDA: {torch.cuda.get_device_name(0)}")
    mps = getattr(getattr(torch, "backends", None), "mps", None)
    if mps is not None and mps.is_available():
        return Result(True, "Apple MPS is available")
    return Result(True, "CPU only; a GPU is optional for the starting lessons")
```

- 先用 `find_spec` 快速判断有没有装，再在函数内部 `import torch`。**函数内导入**保证只有真的需要检查 GPU 时才付出导入 torch 的代价，没装 torch 时整个脚本也不会崩。
- `except Exception`：导入 torch 可能抛各种异常（动态库缺失、版本冲突），这里统一兜住，并用 `type(exc).__name__` 打印异常类型，方便定位。
- 检测顺序与讲义一致：先 CUDA（`torch.cuda.get_device_name(0)` 取第 0 块卡的名字），再 Apple MPS。
- `getattr(getattr(torch, "backends", None), "mps", None)`：**防御式属性访问**。老版本 PyTorch 没有 `torch.backends.mps`，直接写 `torch.backends.mps` 会抛 `AttributeError`；嵌套 `getattr` 带默认值 `None`，任何一级不存在都安全返回 `None`。
- 关键设计：**只有 CPU 时也返回 `ok=True`**。讲义说"没有 GPU 也没问题，大多数课程在 CPU 上就能跑"，所以"没有 GPU"是一种可接受的状态，不是错误。

### 3.6 `PROBES`：用表驱动代替一堆 if/else

```python
def git_fix() -> str:
    system = platform.system()
    if system == "Darwin":
        return "Run `xcode-select --install`, then `git --version`."
    if system == "Windows":
        return "Run `winget install --id Git.Git -e`, then `git --version`."
    return "Run `sudo apt-get update && sudo apt-get install -y git`, then `git --version`."


PROBES = {
    "python": Probe(
        "Python 3.11+",
        python_result,
        "Install it with `uv python install 3.12`, activate that environment, and rerun with `python3`.",
    ),
    "git": Probe("Git", lambda: command_result("git"), git_fix()),
    "node": Probe(
        "Node.js 20+",
        lambda: command_result("node", minimum_major=20),
        "Run `fnm install 22 && fnm use 22`, then `node --version`.",
    ),
    # ... npx / cargo / julia 同理调用 command_result
    "numpy": Probe(
        "NumPy",
        lambda: module_result("numpy"),
        "Activate the course environment and run `python3 -m pip install numpy`.",
    ),
    # ... matplotlib / jupyter / torch 同理调用 module_result
    "gpu": Probe(
        "Accelerator backend",
        gpu_result,
        "A GPU is optional. Install PyTorch first if you want CUDA or Apple MPS detection.",
    ),
}
```

- **`run` 字段存函数，`fix` 字段存字符串**，这是本文件最值得体会的一个细节：
  - `python_result` 和 `gpu_result` 本身就是无参函数，直接传函数名（**注意没有括号**）。
  - `command_result("git")` 需要参数，用 `lambda: command_result("git")` 包成一个无参函数。
  - 这样字典在模块加载时被构造，但**没有任何检查真正执行**；只有 `print_probe` 调用 `probe.run()` 时才跑。没被选中的工具一次子进程都不会启动。
  - 如果误写成 `Probe("Git", command_result("git"), ...)`，导入时就会立刻执行检查，而且 `run` 变成了 `Result` 对象，调用时报 `TypeError: 'Result' object is not callable`。
- `git_fix()` 在构造字典时就被**调用**了：它只根据 `platform.system()`（返回 `"Darwin"` / `"Windows"` / `"Linux"`）挑一条命令字符串，零成本、无副作用，提前算好没问题。三条命令分别对应讲义第 1 步的三大平台。
- 修复命令与讲义保持一致：Python 用 `uv python install 3.12`，Node 用 `fnm install 22`。

### 3.7 `ROUTES`：每条学习路线需要什么

```python
BASE_OPTIONAL = ("node", "npx", "numpy", "matplotlib", "jupyter", "torch", "gpu", "cargo", "julia")

ROUTES = {
    "beginner": Route(
        "Beginner course",
        ("python", "git"),
        BASE_OPTIONAL,
        "python3 phases/01-math-foundations/01-linear-algebra-intuition/code/vectors.py",
    ),
    "ml-foundations": Route(
        "Math and ML foundations",
        ("python", "git", "numpy"),
        ("matplotlib", "jupyter", "torch", "gpu", "julia"),
        "python3 phases/01-math-foundations/01-linear-algebra-intuition/code/vectors.py",
    ),
    # ... llm-engineering / agents / mcp 的必需项都只有 ("python", "git")
    "agent-skills": Route(
        "Agent Skills engineering",
        ("python", "git", "node", "npx"),
        (),
        "python3 phases/13-tools-and-protocols/22-skills-and-agent-sdks/code/main.py",
        (
            "Choose one skill-capable host and confirm it is installed.",
            "Choose a user or project skill scope and confirm it is writable.",
        ),
    ),
    # ... certification
}
```

可以整理成一张表：

| 路线 | 必需项 | 可选项数 | 人工检查 |
|------|--------|---------|---------|
| `beginner` | python, git | 9 | 无 |
| `ml-foundations` | python, git, numpy | 5 | 无 |
| `llm-engineering` | python, git | 6 | 无 |
| `agents` | python, git | 4 | 无 |
| `mcp` | python, git | 2 | 无 |
| `agent-skills` | python, git, node, npx | 0 | 2 条 |
| `certification` | python, git | 2 | 1 条 |

- 观察：**几乎所有路线的起步门槛都只有 Python + git**。这体现讲义"Use It"部分的观点：后面的工具等课程需要时再装，不要让第一课被整套工具链阻塞。
- `agent-skills` 路线必需 Node 和 npx（讲义说 TypeScript 用于阶段 13–17），并带有 `manual` 人工检查项——"AI 宿主是否发现了 skill""skill 作用域是否可写"是 Python 脚本证明不了的，所以诚实地交给人去确认。
- `next_command` 是预检通过后告诉学习者的"下一步"，把"环境就绪"和"开始学习"无缝衔接。

### 3.8 `parse_args`：命令行接口

```python
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check only the tools needed to start a selected curriculum route."
    )
    parser.add_argument(
        "--route",
        choices=tuple(ROUTES),
        default="beginner",
        help="learning route to prepare for (default: beginner)",
    )
    parser.add_argument(
        "--show-later",
        action="store_true",
        help="also check tools that are optional now or required by later lessons",
    )
    return parser.parse_args()
```

- `choices=tuple(ROUTES)`：遍历字典得到所有 key，所以**合法路线由 `ROUTES` 决定**，新增路线不用改这里。传入非法值时 argparse 自动打印用法并以退出码 **2** 结束。
- `action="store_true"`：开关型参数，出现即 `True`，不出现为 `False`。
- 命令行里的 `--show-later` 在代码里变成 `args.show_later`——argparse 自动把连字符 `-` 转成下划线 `_`。

### 3.9 `print_probe`：三态输出

```python
def print_probe(key: str, required: bool) -> bool:
    probe = PROBES[key]
    result = probe.run()
    if result.ok:
        status = "PASS"
    elif required:
        status = "FAIL"
    else:
        status = "LATER"
    timing = "required now" if required else "optional or needed later"
    print(f"  [{status}] {probe.label} ({timing})")
    print(f"         {result.detail}")
    if not result.ok:
        print(f"         Fix: {probe.fix}")
    return result.ok
```

- **同一个检查失败，含义取决于场景**：必需项失败是 `FAIL`（现在必须修），可选项失败是 `LATER`（以后再说）。三态比"通过/失败"二态更贴近真实决策。
- 只有失败时才打印 `Fix:`，成功时不打扰。
- `timing = A if cond else B` 是条件表达式（三元表达式）。
- 返回 `bool`，交给调用方统计。

### 3.10 `main` 与退出码

```python
def main() -> int:
    args = parse_args()
    route = ROUTES[args.route]
    # ... 打印标题
    passed = 0
    for key in route.required:
        passed += int(print_probe(key, required=True))

    if route.optional and args.show_later:
        print("\nOptional or needed later:")
        for key in route.optional:
            print_probe(key, required=False)
    elif route.optional:
        print(
            f"\nLater checks skipped: {len(route.optional)} tools are not needed to start. "
            "Add `--show-later` when you want to inspect them."
        )
    # ... 打印 manual 检查项
    total = len(route.required)
    print(f"\nResult: {passed}/{total} required checks passed")
    if passed == total:
        print(f"Ready to start {route.label}.")
        print(f"Next: {route.next_command}\n")
        return 0

    print("Not ready yet. Run each Fix command above, then repeat this preflight.\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- `int(True) == 1`，`passed += int(...)` 统计通过的必需项数量。
- **可选项的返回值被丢弃**——它们永远不影响结论，对应讲义"A missing later tool never blocks the selected route"。
- `if route.optional and ...`：空元组为假值，`agent-skills` 的可选项是 `()`，两个分支都不进，不会打印"跳过了 0 个工具"这种噪声。
- 两段相邻的字符串字面量（一个 f-string + 一个普通字符串）会被 Python **自动拼接**，方便把长句子拆成两行写。
- `raise SystemExit(main())`：把 `main()` 的返回值变成进程退出码。0 = 就绪，1 = 未就绪，（argparse 参数错误）2。在 shell 里可以 `verify.py --route mcp && echo ready`，在 CI 里非 0 就会让任务失败。
- `main()` 返回 int 而不是自己调用 `sys.exit`，好处是 `main` 本身可以被测试代码调用并检查返回值。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 只用标准库 | 检查工具不能依赖待检查的东西 | 输出没有颜色、无表格；生产可用 `rich`，但要做好缺失时降级 |
| `from __future__ import annotations` | 让脚本在旧 Python 上也能加载并报告版本不足 | 注解变成字符串，运行时需 `typing.get_type_hints` 才能取到真实类型 |
| 冻结 dataclass 建模 | 配置不可变、结构清晰、自带 `__repr__` | 无运行时类型校验；需要校验可用 pydantic |
| 表驱动（`PROBES`/`ROUTES`） | 新增工具/路线只改数据，主流程不动 | 表大了以后可以挪到 YAML/TOML 配置文件 |
| `run` 存函数（lambda 延迟执行） | 只运行当前路线需要的检查 | lambda 不便调试/序列化；可用 `functools.partial` 替代 |
| `shutil.which` + `--version` + 超时 | 能报告具体路径，避免卡死，避免 shell 注入 | 版本解析只看主版本号，较粗糙；生产用正则或 `packaging.version` |
| `find_spec` 不导入 | 快、无副作用 | 可能"找得到但导不进"；对关键库（torch）单独真实导入 |
| 三态 PASS/FAIL/LATER | 区分"现在必须修"与"以后再说" | 可选项问题容易被忽视；可在 CI 中另开严格模式 |
| CPU-only 也算 ok | 入门课程不需要 GPU | 训练类路线可能需要把 GPU 设为必需 |
| 人工检查项 MANUAL | 不伪造检测结果 | 依赖人自觉；可以要求交互式确认 |
| 退出码 0/1/2 | 方便 shell 组合与 CI | 输出是给人看的文本，机器解析可加 `--json` 选项 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 模块导入 | `import importlib.util`、`from dataclasses import dataclass` | 导入整个子模块 / 导入模块中的某个名字 |
| 函数内导入 | `gpu_result` 里的 `import torch` | 延迟导入：只有执行到这里才导入，可选依赖的常见写法 |
| f-string 与 `!r` | `f"{command!r} was not found on PATH"` | `!r` 调用 `repr()`，字符串会带上引号：`'git' was not found` |
| 条件表达式 | `"required now" if required else "optional or needed later"` | 一行版 if/else，返回其中一个值 |
| `or` 取第一个真值 | `process.stdout or process.stderr` | 左边为空字符串（假值）时返回右边 |
| 生成器表达式 + `join` | `"".join(c if c.isdigit() else " " for c in detail)` | 逐字符处理后拼回字符串 |
| 字符串方法 | `.strip()`、`.splitlines()`、`.split()`、`.isdigit()` | 去首尾空白、按行切、按空白切、判断是否数字字符 |
| 元组比较 | `sys.version_info < (3, 11)` | 按元素逐个比较，常用于版本判断 |
| 单元素元组 | `("If using the AI tutor, ...",)` | 末尾逗号不能省，否则只是带括号的字符串 |
| 字符串字面量自动拼接 | `f"...start. " "Add ..."` | 相邻字符串字面量在编译期合并 |
| `lambda` | `lambda: command_result("git")` | 匿名无参函数，用于延迟执行 |
| 函数作为值 | `Probe("Python 3.11+", python_result, ...)` | 不加括号就是传函数本身，加括号是传调用结果 |
| 嵌套 `getattr` 带默认值 | `getattr(getattr(torch, "backends", None), "mps", None)` | 属性不存在时返回默认值而不是抛异常 |
| 异常处理 | `except (OSError, subprocess.SubprocessError) as exc` | 一次捕获多种异常；`as exc` 拿到异常对象 |
| `type(exc).__name__` | `f"{type(exc).__name__}: {exc}"` | 打印异常类名，如 `ImportError` |
| 类型注解 | `def command_result(command: str, minimum_major: int \| None = None) -> Result` | 参数/返回值类型说明；`int \| None` 表示"int 或 None" |
| `typing.Callable` | `run: Callable[[], Result]` | "无参、返回 Result 的可调用对象" |
| `tuple[str, ...]` | `required: tuple[str, ...]` | 任意长度的 str 元组 |
| `from __future__ import annotations` | 文件第一行代码 | 注解延迟求值，旧版本 Python 也能解析新注解语法 |
| `@dataclass(frozen=True)` | `Result`、`Probe`、`Route` | 自动生成构造函数等；`frozen` 让实例不可变 |
| 字段默认值 | `manual: tuple[str, ...] = ()` | 有默认值的字段必须排在最后 |
| `argparse` | `choices=`、`default=`、`action="store_true"` | 声明式定义命令行参数；`--show-later` 变成 `args.show_later` |
| `subprocess.run` | `capture_output=True, text=True, timeout=5, check=False` | 运行外部命令并捕获输出 |
| `if __name__ == "__main__":` + `SystemExit` | `raise SystemExit(main())` | 直接运行时才执行，并把返回值作为退出码 |

---

## 6. 运行结果解读

在临时副本中用 Python 3.13 实际运行（本机有 python/git/node/npx/cargo/numpy/matplotlib，没有 jupyter/torch/julia）。

**默认路线 `beginner`：**

```text
=== AI Engineering from Scratch: Environment Check ===

Route: Beginner course (`--route beginner`)

  [PASS] Python 3.11+ (required now)
         Python 3.13.16 at /usr/bin/python3
  [PASS] Git (required now)
         git version 2.43.0 at /usr/bin/git

Later checks skipped: 9 tools are not needed to start. Add `--show-later` when you want to inspect them.

Result: 2/2 required checks passed
Ready to start Beginner course.
Next: python3 phases/01-math-foundations/01-linear-algebra-intuition/code/vectors.py
```

- 只检查了 2 项；9 个可选工具（`BASE_OPTIONAL` 的长度）完全没运行。
- 每个 PASS 都带上**具体路径**，`sys.executable` 显示正在用 `/usr/bin/python3`。
- 最后给出下一步命令，退出码 0。

**`--route ml-foundations --show-later`（节选）：**

```text
  [PASS] NumPy (required now)
         importable by /usr/bin/python3

Optional or needed later:
  [PASS] Matplotlib (optional or needed later)
         importable by /usr/bin/python3
  [LATER] Jupyter (optional or needed later)
         'jupyter' is not importable by /usr/bin/python3
         Fix: Activate the course environment and run `python3 -m pip install jupyter`.
  [LATER] PyTorch (optional or needed later)
         'torch' is not importable by /usr/bin/python3
         Fix: Activate the course environment and run `python3 -m pip install torch`.
  [LATER] Accelerator backend (optional or needed later)
         PyTorch is not installed, so no accelerator backend was checked
  ...
Result: 3/3 required checks passed
```

- numpy 在这条路线是必需项；缺失的 jupyter/torch 只是 `LATER`，结果仍是 3/3，退出码 0。
- GPU 探针在没有 torch 时明确说明"没检查"，而不是谎称"没有 GPU"。

**`--route agent-skills`（节选）：**

```text
  [PASS] Node.js 20+ (required now)
         v22.22.0 at /opt/node22/bin/node
  [PASS] npx (required now)
         10.9.4 at /opt/node22/bin/npx

Manual checks:
  [MANUAL] Choose one skill-capable host and confirm it is installed.
  [MANUAL] Choose a user or project skill scope and confirm it is writable.

Result: 4/4 required checks passed
```

- `v22.22.0` 解析出主版本 22 ≥ 20，通过；可选项为空元组，所以没有"Later checks skipped"那一行。

**模拟失败：把 PATH 清空（`env PATH=/nonexistent /usr/bin/python3 verify.py`）：**

```text
  [FAIL] Git (required now)
         'git' was not found on PATH
         Fix: Run `sudo apt-get update && sudo apt-get install -y git`, then `git --version`.
...
Result: 1/2 required checks passed
Not ready yet. Run each Fix command above, then repeat this preflight.
```

- 在 Linux 上 `git_fix()` 给出 apt 命令；退出码为 1。

**用 Python 3.9 运行：**

```text
  [FAIL] Python 3.11+ (required now)
         found Python 3.9.25 at /root/.local/share/uv/python/cpython-3.9-linux-x86_64-gnu/bin/python3.9; need Python 3.11+
```

- 正是 `from __future__ import annotations` 让脚本在旧版本上也能跑到这一步。

**非法路线 `--route foo`：** argparse 打印 `invalid choice: 'foo' (choose from 'beginner', ...)`，退出码 2。

---

## 7. 动手改一改

1. **加一个 `uv` 探针**：参照 `cargo` 的写法，修复命令用讲义里的 `curl -LsSf https://astral.sh/uv/install.sh | sh`，并把它加进 `ml-foundations` 的可选项。运行 `--show-later` 验证。
2. **给 Python 3 也加最低版本**：思考为什么 Python 不用 `command_result("python3", minimum_major=3)`？（提示：主版本 3 无法区分 3.9 和 3.12，而且要检查的是"正在运行的解释器"。）
3. **更严谨的版本解析**：改写版本解析，用正则 `re.search(r"(\d+)\.(\d+)", detail)` 提取主、次版本号，让 `minimum` 支持 `(3, 11)` 这样的元组。
4. **加 `--json` 输出**：收集每个探针的 `(key, status, detail)`，用 `json.dumps` 打印，方便其他程序消费。
5. **加 `--strict` 模式**：开启后可选项失败也计入退出码，用于"完整课程环境"的 CI 检查。
6. **写单元测试**：用 `unittest.mock.patch("shutil.which", return_value=None)` 模拟命令不存在，断言 `command_result("node").ok is False`；再 mock `subprocess.run` 返回 `v18.0.0`，断言版本不足分支。

---

## 8. 常见坑

- **不在仓库根目录运行**：讲义要求所有命令从包含 `README.md` 和 `phases/` 的目录执行；否则打印的 `Next:` 相对路径无法直接运行。
- **用错解释器**：`python3` 指向系统 Python 而不是 `.venv` 里的 Python，于是 numpy 显示 "not importable"。看输出里的 `by /path/to/python` 就能发现。
- **把 `run=函数` 写成 `run=函数()`**：传了调用结果而不是函数，导入时就执行，运行时 `TypeError: 'Result' object is not callable`。
- **单元素元组漏逗号**：`("uv")` 是字符串，遍历会得到单个字符 `'u'`、`'v'`，`PROBES['u']` 触发 `KeyError`。
- **以为 LATER 是错误**：可选项缺失不影响退出码，等课程需要时再装即可；反过来，CI 只看退出码也会漏掉这些提示。
- **Mac 上看到 "CPU only" 或 CUDA False 就慌**：Mac 没有 CUDA；装普通版 torch 后应显示 `Apple MPS is available`。
