# 测验 · 开发环境（Dev Environment）

> **阶段 00 · 环境搭建与工具 · 第 01 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/verify.py](../code/verify.py) ｜ 代码讲解：[code/verify.讲解.md](../code/verify.讲解.md)
>
> **用法**：学完讲义、在仓库根目录跑过 `verify.py` 后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 四层环境栈 | 系统基础（OS/shell/git/驱动）→ 包管理器（uv/pnpm/cargo/juliaup）→ 语言运行时 → AI/ML 库，**自底向上**安装 |
| 2 | 为什么包管理器在运行时下面 | `uv python install`、`fnm install 22`、`rustup` 本身负责安装和切换运行时版本，所以先有管理器再有运行时 |
| 3 | uv + 虚拟环境 | uv 比 pip 快 10–100 倍，`uv venv` 建 `.venv`，`source .venv/bin/activate` 后安装的包只属于这个项目 |
| 4 | Node 工具链 | 用 fnm 管理 Node 版本（课程用 22），pnpm 做包管理；Linux 上 fnm 安装脚本依赖 `unzip` |
| 5 | GPU 后端的平台差异 | NVIDIA 用 CUDA wheel（`--index-url .../cu124`）；macOS **没有 CUDA**，装普通版 PyTorch，走 MPS（Metal） |
| 6 | GPU 验证 | `torch.cuda.is_available()`、`torch.backends.mps.is_available()`；Mac 上前者为 False 是正常现象 |
| 7 | 按路线预检（route-aware preflight） | `verify.py --route X` 只检查**开始这条路线所必需**的工具，其余默认跳过，避免新手被一堆警告淹没 |
| 8 | PASS / FAIL / LATER 与退出码 | 必需项失败是 FAIL、可选项缺失是 LATER；只有必需项决定退出码（全过 0，否则 1） |
| 9 | 可执行的修复建议 | 每个失败项都打印检测到的细节（路径/错误）和一条**确切的修复命令**；脚本证明不了的事列为 MANUAL 人工检查 |
| 10 | 语言—阶段映射 | Python（阶段 1–12，uv）、TypeScript（阶段 13–17，pnpm）、Rust（性能敏感部分，cargo）、Julia（阶段 1 数学，可选） |

### 核心技能（能动手做到）

- [ ] 用 uv 安装 Python 3.12、创建 `.venv` 并激活，装好 numpy 后运行讲义中的验证片段，打印出 `dot product with itself: 14`
- [ ] 在仓库根目录运行 `python3 phases/00-setup-and-tooling/01-dev-environment/code/verify.py --route beginner`，能读懂每一行 PASS/FAIL/LATER，并用 `echo $?` 看退出码
- [ ] 加上 `--show-later` 再跑一次，说出哪些工具"现在不需要但以后会用到"
- [ ] 按自己的平台装对 PyTorch（NVIDIA 用 cu124 索引、Mac 用默认索引），并验证 CUDA 或 MPS 是否可用
- [ ] 遇到"装了包却 import 失败"时，能用 `which python` / `sys.executable` 定位是不是用错了解释器
- [ ] 能给 `verify.py` 新增一个探针（probe）和一条路线（route），并让它出现在 `--help` 的可选项里
- [ ] 用 Python、TypeScript、Rust、Julia 各写一个 hello world 并跑通

---

## 二、基础自测（选择题）

**Q1.** 讲义的四层环境栈里，uv、pnpm、cargo 所在的"包管理器层"被画在"语言运行时层"**下面**。最合理的解释是：

- A. 包管理器是用 C 写的，比运行时更底层
- B. 这些工具同时负责安装/切换运行时版本（如 `uv python install 3.12`），所以要先有它们
- C. 这只是画图习惯，两层顺序可以随意交换
- D. 包管理器直接与 GPU 驱动通信

**Q2.** 你在一台 M3 MacBook 上执行 `uv pip install torch --index-url https://download.pytorch.org/whl/cu124`，安装失败。最可能的原因是：

- A. uv 不支持 Apple Silicon
- B. Mac 需要先手动安装 CUDA Toolkit
- C. cu124 是 Linux/Windows 的 CUDA wheel，macOS 没有 CUDA，应该用默认索引安装、走 MPS 后端
- D. PyTorch 只支持 Python 3.11 以下

**Q3.** 本机没有安装 Node.js，运行 `python3 verify.py --route beginner`（不加任何其他参数），且 Python 3.12 和 git 都正常。会发生什么？

- A. 打印 `[FAIL] Node.js 20+`，退出码为 1
- B. 打印 `[LATER] Node.js 20+`，退出码为 0
- C. 根本不检查 Node，只提示跳过了 9 个后续工具，退出码为 0
- D. 抛出 `FileNotFoundError` 异常

**Q4.** 同样的机器运行 `python3 verify.py --route agent-skills`，结果是：

- A. 退出码 0，因为 Node 只是可选项
- B. Node 和 npx 显示为 FAIL，结果 `2/4 required checks passed`，退出码 1
- C. Node 显示为 LATER，结果 `2/2 required checks passed`
- D. 脚本提示 `agent-skills` 不是合法路线

**Q5.** 你确认已经 `uv pip install numpy`，但运行脚本时仍然报 `ModuleNotFoundError: No module named 'numpy'`。**首先**应该检查什么？

- A. 重新安装操作系统
- B. 当前运行脚本的 `python` 是不是你装包的那个虚拟环境里的解释器（`which python` / 激活 `.venv`）
- C. 用 `sudo pip install numpy` 装到系统里
- D. 升级 GPU 驱动

**Q6.** 在 Apple Silicon Mac 上，`torch.cuda.is_available()` 返回 `False`，`torch.backends.mps.is_available()` 返回 `True`。正确的结论是：

- A. PyTorch 安装损坏，需要重装
- B. 一切正常：Mac 没有 CUDA，GPU 加速走 MPS
- C. 需要安装 NVIDIA 驱动
- D. 只能用 CPU 训练

**Q7.** 在 Ubuntu 上执行 fnm 安装脚本，输出 `Not installing fnm due to missing dependencies.` 后退出。最可能缺的是：

- A. `unzip`
- B. `cargo`
- C. `pnpm`
- D. `nvidia-smi`

---

## 三、动手 / 代码题

**Q8.** 机器上 Python、git、npx 都正常，但 Node 是旧版本，`node --version` 输出 `v18.19.0`。运行：

```bash
python3 phases/00-setup-and-tooling/01-dev-environment/code/verify.py --route agent-skills
```

结合下面的源码，写出 **Node 那一项打印的三行**、最后的 `Result:` 行，以及进程退出码。

```python
    if minimum_major is not None:
        digits = "".join(character if character.isdigit() else " " for character in detail)
        parts = digits.split()
        if not parts:
            return Result(False, f"could not parse a version from {detail!r}")
        major = int(parts[0])
        if major < minimum_major:
            return Result(False, f"found {detail}; need version {minimum_major}+")
```

**Q9.** `PROBES` 字典里是这样定义 git 探针的：

```python
    "git": Probe("Git", lambda: command_result("git"), git_fix()),
```

(a) 为什么 `run` 参数要包一层 `lambda`，而 `fix` 参数却直接调用 `git_fix()`？
(b) 如果有人把它"简化"成 `Probe("Git", command_result("git"), git_fix())`，运行时会出什么问题？

**Q10.** 给 `verify.py` 做一个扩展：

1. 新增一个探针 `"uv"`，检查 `uv` 命令是否在 PATH 上，修复命令用讲义里的安装脚本；
2. 新增一条路线 `"rust-systems"`（标签 `Rust systems`），必需项为 `python`、`git`、`cargo`，可选项为 `uv`，下一步命令可以写 `cargo --version`。

写出需要添加的代码，并说明为什么不用改 `parse_args()`，新路线就会自动出现在 `--route` 的可选值里。

---

## 四、面试高频题

**Q11.**（基础必考）为什么每个 AI 项目都应该用独立的虚拟环境？不用会出什么问题？`sudo pip install` 为什么是反模式？

**Q12.**（原理深挖）NVIDIA 驱动、CUDA、PyTorch 的 `cu124` wheel 三者是什么关系？`nvidia-smi` 能正常输出，但 `torch.cuda.is_available()` 是 `False`，你会怎么排查？

**Q13.**（工程实践）团队新人入职，经常花一两天配环境。请设计一套方案，让"克隆仓库 → 能跑第一个实验"尽量短且可复现。

**Q14.**（场景设计）请你为一个多语言（Python/TS/Rust）AI 课程设计环境预检脚本。你会如何划分检查项、如何呈现结果、如何让它适合放进 CI？

**Q15.**（追问型）面试官追问："你说预检脚本只检查必需项，那可选项缺了怎么办？脚本证明不了的东西（比如 AI 宿主有没有加载某个 skill）又怎么处理？"

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义的层次图是"每一层依赖下面一层"。uv 能 `uv python install 3.12`，fnm 能 `fnm install 22`，rustup 安装 rustc/cargo——**版本管理器负责把运行时装上**，所以它们在运行时之下。A 是编造的；C 错在顺序有真实依赖含义；D 错在包管理器与 GPU 驱动无直接关系（驱动属于第 1 层系统基础）。

### Q2 — 答案：C

讲义明确写到：Mac 上没有 CUDA，这是预期而不是故障；**不要**传 `--index-url .../cuXXX`，那些 wheel 只适用于 Linux/Windows，所以安装会失败。正确做法是 `uv pip install torch torchvision torchaudio`，默认构建自带 Apple 的 MPS（Metal）后端。B 错在 macOS 上根本没有 CUDA 可装。

### Q3 — 答案：C

`beginner` 路线的必需项只有 `("python", "git")`，Node 在 `BASE_OPTIONAL` 里。没加 `--show-later` 时，可选项一个都不运行，只打印：

```text
Later checks skipped: 9 tools are not needed to start. Add `--show-later` when you want to inspect them.
```

2/2 通过，退出码 0。B 只有加了 `--show-later` 才会出现；D 错在 `shutil.which` 找不到命令时返回 `None`，脚本会优雅处理而不是抛异常。

### Q4 — 答案：B

`agent-skills` 的必需项是 `("python", "git", "node", "npx")`，Node 和 npx 都缺，两项都是 `[FAIL]`，并各自打印 `Fix:` 修复命令；结果 `2/4 required checks passed`，打印 `Not ready yet...`，`main()` 返回 1。这条路线还会打印两条 `[MANUAL]` 人工检查项。

### Q5 — 答案：B

"装了却 import 不到"最常见的原因是**装包用的环境和运行用的解释器不是同一个**（没激活 `.venv`、IDE 选错解释器、Jupyter kernel 不对等）。课程配套的诊断提示词里也写到：import 报错时先用 `which python` 确认是否在正确的虚拟环境中。C 是反模式（讲义配套提示词明确说"永远不要 `sudo pip install`"）；A、D 与问题无关。

### Q6 — 答案：B

讲义的验证片段注释就写着：`CUDA available` 在 macOS 上为 False——expected；`MPS available` 在 Apple Silicon 上为 True。MPS 是 PyTorch 在 Apple GPU 上的后端，代码里用 `device="mps"` 即可。

### Q7 — 答案：A

讲义说明：fnm 安装脚本会先检查 `unzip`，缺失时以 `Not installing fnm due to missing dependencies.` 退出——因为在 Linux 上它需要解压 zip 包。第 1 步的 apt 命令里已经包含 `unzip`；跳过第 1 步的话补一句 `sudo apt install -y unzip` 即可。

### Q8 — 参考答案

Node 那一项：

```text
  [FAIL] Node.js 20+ (required now)
         found v18.19.0; need version 20+
         Fix: Run `fnm install 22 && fnm use 22`, then `node --version`.
```

最后：

```text
Result: 3/4 required checks passed
Not ready yet. Run each Fix command above, then repeat this preflight.
```

退出码为 **1**。

解析：
- `detail` 是 `--version` 输出的第一行 `v18.19.0`。
- 把所有非数字字符换成空格得到 `" 18 19 0"`，`split()` 后为 `['18', '19', '0']`，取第一个 `18` 作为主版本号。
- `18 < 20`，返回失败。注意失败信息里**不带路径**（只有成功分支才拼接 `at {path}`）。
- 3 个必需项通过、1 个失败，`main()` 走到 `return 1`，`raise SystemExit(1)` 让进程退出码为 1。

### Q9 — 参考答案

(a) `run` 的类型是 `Callable[[], Result]`，需要的是"**以后**再执行的函数"。`PROBES` 在模块导入时就会构造，如果直接调用 `command_result("git")`，每个工具都会在导入阶段立刻跑一次 `--version` 子进程——包括本次路线根本不需要检查的工具，既慢又违背"只检查需要的东西"的设计。`lambda` 把调用**延迟**到 `print_probe` 里 `probe.run()` 时才执行。

而 `fix` 只是一个字符串；`git_fix()` 只根据 `platform.system()` 选一条修复命令，开销极小、没有副作用，所以在构造时算好即可。

(b) 那样 `run` 的值就成了一个 `Result` 对象而不是函数。导入时会立即执行 git 检查（副作用提前），等到 `print_probe` 调用 `probe.run()` 时会抛出：

```text
TypeError: 'Result' object is not callable
```

`frozen=True` 的 dataclass 不会做类型检查，所以错误要到运行时才暴露——这也是类型注解 + mypy 这类静态检查的价值。

### Q10 — 参考答案

```python
# 1) 在 PROBES 字典中新增一项
PROBES["uv"] = Probe(
    "uv",
    lambda: command_result("uv"),
    "Run `curl -LsSf https://astral.sh/uv/install.sh | sh`, restart the shell, then run `uv --version`.",
)

# 2) 在 ROUTES 字典中新增一条路线
ROUTES["rust-systems"] = Route(
    "Rust systems",
    ("python", "git", "cargo"),
    ("uv",),
    "cargo --version",
)
```

（也可以直接写进两个字典的字面量里，效果相同；但必须在 `parse_args()` 被调用之前完成。）

注意 `("uv",)` 末尾的逗号：单元素元组必须带逗号，否则 `("uv")` 只是字符串 `"uv"`。不加 `--show-later` 时它会悄悄打印错误的 `Later checks skipped: 2 tools`（`len("uv") == 2`）；加上 `--show-later` 遍历时得到 `"u"`、`"v"` 两个"key"，直接 `KeyError: 'u'`（实测如此）。

为什么不用改 `parse_args()`：它写的是 `choices=tuple(ROUTES)`，遍历字典得到的是所有 key，所以 `--route` 的合法值**由 `ROUTES` 字典驱动**。这是"数据驱动/表驱动"设计：新增路线只改数据，不改控制流。运行 `verify.py --help` 就能看到 `rust-systems` 出现在可选值里。

### Q11 — 参考回答要点

- **定义**：虚拟环境是项目私有的一套解释器 + `site-packages`，激活后 `pip/uv` 安装的包只进入这个目录。
- **不用的后果**：所有项目共享全局包。A 项目要 `torch 2.x + transformers` 新版本，B 项目锁在旧版本，升级一个就打坏另一个；也无法准确导出"这个项目到底依赖什么"，复现困难。
- **`sudo pip install` 为什么是反模式**：以 root 写入系统 Python 的目录，可能覆盖操作系统自身依赖的包（很多 Linux 发行版的工具是 Python 写的），还会留下 root 拥有的文件导致后续权限错误。正确做法是 uv + 虚拟环境（配套诊断提示词原话："Never use `sudo pip install`"）。
- **加分点**：提到很多新版 Linux 发行版的系统 Python 会拒绝直接 `pip install`（"externally managed environment"）；提到锁文件让环境可复现；提到 Jupyter kernel 也要指向同一个环境。
- **常见误区**：以为虚拟环境能"让代码更快"或"提供 GPU"——它只做依赖隔离。

### Q12 — 参考回答要点

- **三者关系**：
  - **NVIDIA 驱动**（第 1 层系统基础）：让操作系统能使用 GPU；`nvidia-smi` 能跑说明驱动正常。它显示的 "CUDA Version" 是**该驱动最高能支持的** CUDA 版本，不代表你装了 CUDA Toolkit。
  - **CUDA**：NVIDIA 的并行计算平台，PyTorch 的 GPU 算子跑在它上面。
  - **`cu124` wheel**：针对 CUDA 12.4 编译、并**自带对应 CUDA 运行时库**的 PyTorch 安装包。用 PyTorch 本身一般不需要另装完整 CUDA Toolkit，但驱动版本必须足够新以支持该 CUDA 版本。
- **排查顺序**：
  1. `python -c "import torch; print(torch.__version__, torch.version.cuda)"`：如果 `torch.version.cuda` 是 `None`，说明装的是 CPU 版（常见原因：没带 `--index-url`）。
  2. 确认运行的是装了 GPU 版 torch 的那个虚拟环境（`sys.executable`）。
  3. 对比 `nvidia-smi` 显示的驱动支持版本和 wheel 的 CUDA 版本，驱动太旧就升级驱动或换更低 CUDA 版本的 wheel。
  4. 容器/云主机里还要确认 GPU 是否真的透传进来了（下一节会讲）。
- **常见误区**：在 Mac 上追查 CUDA——Mac 没有 CUDA，应检查 MPS。

### Q13 — 参考回答要点

- **分层思路**（对应四层栈）：系统层写清楚支持的 OS 与必装包（如 `build-essential git curl unzip`），Windows 统一走 WSL2；包管理器统一（Python 用 uv、Node 用 pnpm）；运行时版本固定（如 Python 3.12、Node 22）；AI 库通过锁文件固定版本。
- **可复现**：提交依赖声明 + 锁文件；固定 Python 版本；GPU 相关依赖按平台区分安装方式（CUDA 索引 vs 默认索引）。
- **快速反馈**：提供类似 `verify.py` 的预检脚本——只检查当前任务必需的工具，每个失败项给出可直接复制的修复命令，成功时直接告诉你"下一步运行哪个命令"。
- **兜底方案**：提供 Docker 镜像或云端 notebook（无 GPU 时用 Colab/云 GPU），新人可以先跑起来再慢慢配本地。
- **持续保障**：在 CI 里跑同一份预检脚本 + 冒烟测试，防止依赖漂移。
- **加分点**：强调"按需安装"——讲义的观点是不要让第一课被整套工具链阻塞，后续工具等课程需要时再装。

### Q14 — 参考回答要点

- **检查项建模**：把每个检查抽象成"探针"（标签、执行函数、修复命令），结果统一为 `(ok, detail)`；路线 = 必需探针 + 可选探针 + 下一步命令 + 人工检查项。数据驱动，新增工具只改表。
- **检查方式**：命令行工具用 `shutil.which` + `--version`（加超时、不用 `shell=True`）；Python 包用 `importlib.util.find_spec` 只探测不导入；需要真实导入的（如 GPU 检测）要捕获所有异常并给出原因。
- **结果呈现**：三态（PASS / FAIL / LATER）区分"现在必须修"和"以后再说"；失败项给出**检测到的细节 + 精确修复命令**；结尾给汇总和"下一步"。
- **适合 CI**：只由必需项决定退出码（0/1），参数用 `argparse` 的 `choices` 校验，非法参数退出码 2；输出纯文本、稳定，便于日志检索。
- **加分点**：避免"一墙警告"——默认只显示必需项，可选项用开关（`--show-later`）展开；把脚本无法验证的事项显式列为 MANUAL，而不是假装通过。

### Q15 — 参考回答要点

- **可选项**：默认不检查，只打印"跳过了 N 个工具"的提示；用户加 `--show-later` 时才运行，缺失标为 `LATER` 并给出修复命令，但**永远不影响退出码**（讲义原话：A missing later tool never blocks the selected route）。理由是让新手先跑起来，工具等课程需要时再装。
- **证明不了的事**：例如"AI 宿主是否发现了某个 skill"、"所选 skill 作用域是否可写"，Python 脚本无法可靠验证。正确做法是把它们列为 `[MANUAL]` 清单让人确认，而不是写一个不可靠的检测给出虚假的 PASS。
- **加分点**：指出 `gpu_result` 在只有 CPU 时也返回 `ok=True`——"没有 GPU"对入门课程不是错误；工程上要区分"错误"和"能力缺失但可接受"。
- **常见误区**：把所有检查都设为必需，导致任何一项可选工具缺失都让 CI 变红，大家最终习惯性忽略预检结果。

---

## 六、关联知识点

### 前置知识
- 无硬性前置。会打开终端、执行命令、知道"PATH 是系统找命令的目录列表"即可。

### 本节被哪些后续内容用到
- [阶段 00 · 02 Git & 协作](../../02-git-and-collaboration/docs/zh.md)：预检里的 git 是所有路线的必需项，下一节学会日常使用。
- [阶段 00 · 03 GPU 设置和云](../../03-gpu-setup-and-cloud/docs/zh.md)：深入 CUDA/MPS 检测与云 GPU 选择，是本节第 6 步的展开。
- [阶段 00 · 06 Python 环境](../../06-python-environments/docs/zh.md)：系统讲解虚拟环境、uv、锁文件与依赖冲突。
- [阶段 00 · 07 用于 AI 的 Docker](../../07-docker-for-ai/docs/zh.md)：用容器把整个四层栈打包成可复现镜像。
- [阶段 00 · 10 终端与 Shell](../../10-terminal-and-shell/docs/zh.md)：PATH、shell 配置文件（如 `~/.zshrc`）等本节用到的终端基础。
- [阶段 01 · 01 线性代数直觉](../../../01-math-foundations/01-linear-algebra-intuition/docs/zh.md)：beginner 预检通过后打印的"下一步"就是运行这一节的 `vectors.py`。
- [阶段 11 · 01 提示工程](../../../11-llm-engineering/01-prompt-engineering/docs/zh.md)、[阶段 14 · 01 Agent 循环](../../../14-agent-engineering/01-the-agent-loop/docs/zh.md)、[阶段 13 · 06 MCP 基础](../../../13-tools-and-protocols/06-mcp-fundamentals/docs/zh.md)：分别是 llm-engineering、agents、mcp 路线预检通过后的起点。

### 延伸关键词
`uv.lock / 锁文件` · `pyenv / fnm / rustup 版本管理器` · `WSL2` · `CUDA Driver vs Toolkit` · `PyTorch MPS 后端` · `Dev Container` · `preflight check` · `进程退出码与 CI`
