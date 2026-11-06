# 测验 · Python 环境（Python Environments）

> **阶段 00 · 环境搭建与工具 · 第 06 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/env_setup.sh](../code/env_setup.sh)（Shell 脚本，本节没有 `.py` 文件，动手题围绕这个脚本和 `pyproject.toml` 展开）
>
> **用法**：学完讲义、在仓库根目录跑过 `bash phases/00-setup-and-tooling/06-python-environments/code/env_setup.sh` 后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 依赖地狱（dependency hell） | 框架自带 CUDA 绑定、模型库锁定框架版本、全局 `pip install` 互相覆盖，导致"修好 A 项目就弄坏 B 项目" |
| 2 | 虚拟环境 | 一个独立目录，包含 Python 解释器（的引用）和自己的包，与系统 Python 隔离；每个项目一个 |
| 3 | 三种工具 | **uv**（推荐，极快，同时管理 Python 版本、虚拟环境与依赖解析）、**venv**（内置、到处可用）、**conda**（能管理 CUDA toolkit、cuDNN、C 库等非 Python 依赖） |
| 4 | conda 的规则 | 一个 conda 环境里尽量全用 conda 装；必须用 pip 时，先装完所有 conda 包，最后再 pip |
| 5 | 按阶段分环境 | 课程不要只用一个大环境：轻量共享环境给阶段 0–3，PyTorch、Transformer、LLM API 等阶段按需各自建环境 |
| 6 | `pyproject.toml` | 标准项目配置：`[project]` 写 `requires-python`、`dependencies`，`[project.optional-dependencies]` 写可选依赖组，用 `.[torch,llm]` 安装 |
| 7 | 锁文件（lockfile） | 把**包括传递依赖在内**的每个包锁到精确版本；`uv add` 自动生成 `uv.lock`，或用 `uv pip compile` 生成；锁文件要提交到 Git |
| 8 | 常见错误 | 全局安装、忘记激活（用 `which python` 检查）、把 `.venv` 提交进 Git、CUDA 版本不匹配 |
| 9 | CUDA 兼容规则 | `nvidia-smi` 显示驱动支持的 CUDA 版本，`torch.version.cuda` 显示 PyTorch 编译用的版本；**PyTorch 的 CUDA 版本必须 ≤ 驱动支持的版本** |
| 10 | `env_setup.sh` 的流程 | 检测 uv → 找 Python 3.11+ → 创建/复用 `.venv` → 激活并确认路径 → 安装核心包 → 逐个验证导入 → PyTorch 可选 |

### 核心技能（能动手做到）

- [ ] 用 `uv venv` 和 `python3 -m venv` 各建一个环境，激活后用 `which python`、`which pip` 确认都指向 `.venv/bin/`
- [ ] 建两个虚拟环境，分别装不同版本的 numpy，用 `python -c "import numpy; print(numpy.__version__)"` 证明它们互相隔离
- [ ] 为"需要 PyTorch + Anthropic SDK"的项目写 `pyproject.toml`（基础依赖 + 可选依赖组），并用 `uv pip install -e ".[torch,llm]"` 安装
- [ ] 生成锁文件，说清楚 `uv.lock` 与 `uv pip compile` 产物的区别，以及为什么要提交它而不是 `.venv`
- [ ] 读懂 `env_setup.sh` 的每一段，能解释 `set -euo pipefail`、`command -v`、`${2:-$1}` 的作用，并能指出脚本中的两个隐患
- [ ] 对比 `nvidia-smi` 与 `torch.version.cuda`，判断某个 PyTorch CUDA 构建能否在当前驱动上使用

---

## 二、基础自测（选择题）

**Q1.** 激活虚拟环境后，下列哪个现象说明你**确实**在用虚拟环境里的 Python？

- A. 终端背景颜色变了
- B. `pip --version` 显示的版本号比较新
- C. `which python` 输出 `.../your-project/.venv/bin/python`，而不是 `/usr/bin/python`
- D. `python --version` 显示 3.12

**Q2.** 你安装了包 A，A 依赖 B，B 又依赖 C。对你的项目来说，C 是：

- A. 可选依赖（optional dependency）
- B. 传递依赖（transitive dependency）
- C. 开发依赖（dev dependency）
- D. 系统依赖（system dependency）

**Q3.** 在一个 conda 环境里，有个库只能通过 pip 安装。按讲义的建议，正确的做法是：

- A. 先 pip 装这个库，再用 conda 装其余所有包
- B. 先用 conda 装完所有 conda 包，最后再用 pip 装这个库
- C. conda 环境里绝对不能用 pip，只能放弃这个库
- D. pip 和 conda 交替安装，哪个快用哪个

**Q4.** `nvidia-smi` 右上角显示 `CUDA Version: 12.4`。按"PyTorch 的 CUDA 版本必须 ≤ 驱动支持的 CUDA 版本"规则，下列哪个 PyTorch 构建**最可能**无法使用 GPU？

- A. cu118（CUDA 11.8）
- B. cu121（CUDA 12.1）
- C. cu124（CUDA 12.4）
- D. cu126（CUDA 12.6）

**Q5.** 按讲义中的 `pyproject.toml`，执行 `uv pip install -e ".[llm]"` 会安装：

- A. 只有 `anthropic` 和 `openai`
- B. 基础依赖（numpy、matplotlib、jupyter、scikit-learn）+ `anthropic`、`openai`
- C. 基础依赖 + torch + LLM SDK 全部
- D. 只有基础依赖，`[llm]` 会被忽略

**Q6.** 团队协作时，应该提交到 Git 的是：

- A. `.venv/` 目录，这样同事 clone 下来就能直接用
- B. `pyproject.toml` 和锁文件
- C. 只提交 `.venv/` 里的 `site-packages`
- D. 什么都不用提交，让每个人自己装最新版

**Q7.** 下列哪种情况讲义建议使用 conda 而不是 uv/venv？

- A. 你想要最快的安装速度
- B. 在共享集群上无法安装系统包，又需要某个特定版本的 CUDA toolkit
- C. 项目只依赖纯 Python 包
- D. 你想让 `pip install` 更快

---

## 三、动手 / 代码题

**Q8.**（读脚本）`env_setup.sh` 的开头和中间有这几行。请分别解释它们的作用：

```bash
set -euo pipefail
# ...
REPO_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
cd "$REPO_ROOT"
# ...
if command -v uv &> /dev/null; then
# ...
    uv pip install $CORE_PACKAGES
```

特别回答：(a) `../../../..` 为什么是四层？(b) 为什么 `$CORE_PACKAGES` 这里**故意不加引号**，而脚本其他地方几乎都加了引号？

**Q9.**（找 bug）下面是脚本的验证部分。假设 scikit-learn 因为某种原因 import 失败，脚本会输出什么？开发者设计的 `FAILURES` 计数和最后的 `N package(s) failed verification` 汇总能否按预期工作？如何修复？

```bash
FAILURES=0

verify_package() {
    local pkg=$1
    local import_name=${2:-$1}
    if python -c "import $import_name; print(f'  $pkg: {${import_name}.__version__}')" 2>/dev/null; then
        return 0
    else
        fail "$pkg"
        FAILURES=$((FAILURES + 1))
        return 1
    fi
}

verify_package "numpy" "numpy"
verify_package "matplotlib" "matplotlib"
verify_package "scikit-learn" "sklearn"
verify_package "pandas" "pandas"
verify_package "jupyter" "jupyter_core"
# ...
if [ "$FAILURES" -gt 0 ]; then
    fail "$FAILURES package(s) failed verification"
    exit 1
```

**Q10.**（找 bug + 实测现象）在一台系统 `python3` 是 3.13、同时装有一个 **uv 管理的 Python 3.9** 的机器上运行 `env_setup.sh`，实测输出节选如下：

```text
  [PASS] uv found: uv 0.11.32 (x86_64-unknown-linux-gnu)
  [PASS] Python: Python 3.13.16

--- Creating virtual environment ---

Using CPython 3.9.25
Creating virtual environment at: .venv
...
  Python:       Python 3.9.25
...
  [PASS] All checks passed
```

(a) 脚本要求 Python 3.11+，为什么最后建出来的 `.venv` 是 3.9，还报告"全部通过"？(b) 给出修复方法。(c) 脚本里的版本判断 `[ "$major" -ge 3 ] && [ "$minor" -ge 11 ]` 还隐藏着另一个逻辑问题，是什么？

**Q11.**（写配置）完成讲义练习 3：为一个同时需要 PyTorch 和 Anthropic SDK 的项目写 `pyproject.toml`（基础依赖只放 numpy，torch 与 anthropic 各放一个可选依赖组），然后写出：(1) 安装全部依赖的命令；(2) 生成**包含可选依赖**的锁文件的命令。并说明讲义中的 `uv pip compile pyproject.toml -o requirements.lock` 会不会锁住 torch。

---

## 四、面试高频题

**Q12.**（基础必考）venv、conda、uv 有什么区别？你在 AI 项目里怎么选？

**Q13.**（原理深挖）"激活虚拟环境"到底做了什么？不激活能不能用虚拟环境里的包？为什么说 `.venv` 不能在机器之间拷贝？

**Q14.**（工程实践）`pyproject.toml` 里的版本范围（如 `numpy>=1.26`）和锁文件里的精确版本分别解决什么问题？在 CI 和生产部署中你会怎么用？

**Q15.**（场景设计）同一台 GPU 服务器上，一个老项目必须用 torch 2.1 + CUDA 11.8，一个新的微调项目要用 torch 2.4 + CUDA 12.4。请设计环境方案，并说明对 NVIDIA 驱动版本的要求。

**Q16.**（追问型）同事说"在我机器上能跑，在你机器上就报错"，怀疑是依赖版本不一致。你会按什么步骤排查？

---

## 五、参考答案与解析

### Q1 — 答案：C

`which python` 显示的是 shell 按 PATH 找到的解释器路径，这是讲义推荐的检查方法（`which pip` 也应指向 `.venv/bin/pip`）。D 不可靠：系统 Python 也可能是 3.12。激活后提示符通常会出现 `(.venv)` 前缀，但颜色变化不是判断依据。

### Q2 — 答案：B

讲义 Key Terms：B 依赖 C，你安装的 A 依赖 B，那么 C 就是 A 的传递依赖。锁文件的价值之一就是把传递依赖也锁住——你没有直接写它，但它的版本变化同样能让项目出问题。

### Q3 — 答案：B

讲义："如果必须在 conda 里用 pip（有些包只有 pip 版），先装所有 conda 包，最后装 pip 包。"原因是 pip 安装会绕过 conda 的依赖跟踪，conda 不知道环境的真实状态，之后再用 conda 安装/更新时可能覆盖或破坏 pip 装的包。

### Q4 — 答案：D

规则是 PyTorch 的 CUDA 版本 ≤ 驱动支持的 CUDA 版本。驱动支持到 12.4，cu126 超出范围，最可能无法使用 GPU（`torch.cuda.is_available()` 为 False 或运行时报错），需要升级驱动或换 cu124 及以下的构建。

⚠️ 注意：讲义"问题"一节中写道"CUDA 11.8 builds don't work with CUDA 12.x drivers (and vice versa)"，与它自己在"常见错误"一节给出的 ≤ 规则相矛盾。NVIDIA 驱动是**向后兼容**的：较新的驱动可以运行用较旧 CUDA 版本构建的程序，所以 cu118 在支持 12.4 的驱动上通常可以工作（A 不是答案）；反过来"新构建 + 旧驱动"才是问题所在。以 ≤ 规则为准。

### Q5 — 答案：B

`.[llm]` 的意思是"安装当前目录这个项目（含 `dependencies` 中的基础依赖），并额外安装 `llm` 这个可选依赖组"。`-e` 表示可编辑安装：修改项目源码后无需重装。想要全部可选依赖就写 `.[torch,llm]`。

### Q6 — 答案：B

讲义：虚拟环境有 200MB–2GB，而且是本机专属、不能在机器间移植；应提交 `pyproject.toml` 和锁文件，并把 `.venv/` 加入 `.gitignore`。同事 clone 后按锁文件安装，就能得到完全相同的版本。D 会导致每个人的环境都不一样。

### Q7 — 答案：B

讲义列出的 conda 适用场景：需要特定 CUDA toolkit 版本又不想装到系统里；在无法安装系统包的共享集群上；某个库的安装说明要求用 conda。A、D 恰好是 uv 的强项；C 用 uv/venv 即可。

### Q8 — 参考答案

- `set -euo pipefail`——"严格模式"三件套：
  - `-e`：任何命令返回非 0 时立即退出脚本；
  - `-u`：使用未定义的变量时报错退出，防止拼错变量名后悄悄得到空字符串；
  - `-o pipefail`：管道 `a | b` 中只要有一个命令失败，整个管道就算失败（默认只看最后一个命令）。
- `REPO_ROOT=...; cd "$REPO_ROOT"`：`$0` 是脚本自身路径，`dirname` 取它所在目录 `.../code`，再向上找到仓库根目录，`pwd` 把它变成绝对路径。之后 `cd` 过去，保证无论你在哪个目录执行 `bash .../env_setup.sh`，`.venv` 都建在**仓库根目录**。
- `command -v uv &> /dev/null`：判断 `uv` 命令是否存在（POSIX 推荐写法，比 `which` 更可靠）；`&> /dev/null` 把标准输出和标准错误都丢弃，只关心退出码。

(a) 四层：脚本在 `phases/00-setup-and-tooling/06-python-environments/code/` 中。从 `code` 往上：第 1 个 `..` 到 `06-python-environments`，第 2 个到 `00-setup-and-tooling`，第 3 个到 `phases`，第 4 个到仓库根。

(b) `CORE_PACKAGES="numpy matplotlib jupyter scikit-learn pandas"` 是一个用空格分隔的字符串。不加引号时 shell 会做**单词拆分**，`uv pip install` 收到 5 个参数；如果写成 `"$CORE_PACKAGES"`，它会收到**一个**参数 `"numpy matplotlib jupyter scikit-learn pandas"`，被当作一个（不存在的）包名。更规范的写法是用 bash 数组：`CORE_PACKAGES=(numpy matplotlib ...)`，再用 `"${CORE_PACKAGES[@]}"` 展开。

### Q9 — 参考答案

输出（`numpy`、`matplotlib` 正常，`sklearn` 失败）：

```text
  numpy: <版本>
  matplotlib: <版本>
  [FAIL] scikit-learn
```

然后脚本**立即以退出码 1 结束**——不会验证 pandas、jupyter，也不会打印 `=== Summary ===` 和 `N package(s) failed verification`。

原因：脚本开头有 `set -e`。`verify_package` 在失败时 `return 1`，它作为一条普通命令在顶层被调用，返回非 0 就触发 `set -e` 退出。`FAILURES` 虽然被加了 1，但永远没有机会被汇总——计数逻辑实际上是"死代码"。（在 `if` 条件里调用的命令不受 `set -e` 影响，所以函数内部的 `if python -c ...` 本身没问题。）用一个最小复现脚本实测，确实是打印第一个 `[FAIL]` 后就以退出码 1 退出。

修复（任选其一）：

```bash
# 方案 1：调用处吞掉返回值，让汇总逻辑生效
verify_package "scikit-learn" "sklearn" || true

# 方案 2：函数失败分支不返回非 0（计数已经记录了失败）
    else
        fail "$pkg"
        FAILURES=$((FAILURES + 1))
    fi
```

另一个小细节：`2>/dev/null` 把 import 的错误信息丢掉了，失败时只看到 `[FAIL] scikit-learn`，不知道原因；排查时可以去掉它，看到完整的 `ImportError`。

### Q10 — 参考答案

(a) 版本检查和建环境用的**不是同一个 Python**：
- 脚本检查的是 PATH 上的 `python3`（3.13，通过）；
- 但有 uv 时，建环境用的是 `uv venv "$VENV_DIR"`，**没有指定 Python**，由 uv 自己的发现规则挑选解释器——uv 默认优先使用它自己管理的 Python 安装，于是选中了 3.9.25；
- 之后的验证只检查"包能不能导入"和"python 路径是否在 `.venv` 里"，**没有再检查 venv 里的 Python 版本**，所以报告全部通过，最后的 Summary 里却明明白白写着 `Python 3.9.25`。

（本题输出来自真实运行：测试机上为了验证另一个脚本临时装了 uv 管理的 3.9。学习者如果为别的项目执行过 `uv python install 3.10` 之类的命令，同样可能遇到。）

(b) 修复：让 uv 使用检测通过的那个解释器，或直接把版本约束交给 uv：

```bash
uv venv --python "$(command -v "$PYTHON_CMD")" "$VENV_DIR"
# 或
uv venv --python ">=3.11" "$VENV_DIR"
```

实测这两种写法分别得到 3.13.16 和 3.13.16 的 `.venv`；而 `--python python3` 仍会被 uv 理解为"任意 Python 3"的版本请求，依旧可能选中 3.9，所以要传**绝对路径**。更稳妥的做法是激活后再验证一次：`python -c "import sys; sys.exit(sys.version_info < (3, 11))"`。

(c) 主次版本号被**分开比较**：只要次版本号小于 11 就会被拒绝，因此将来的 Python 4.0（major=4, minor=0）会被错误地判为不合格。正确的比较应作为一个整体：

```bash
"$cmd" -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"
```

把比较交给 Python 的元组比较，既简单又不会出错。

### Q11 — 参考答案

```toml
[project]
name = "torch-claude-demo"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "numpy>=1.26",
]

[project.optional-dependencies]
torch = ["torch>=2.3"]
llm = ["anthropic>=0.39"]
```

(1) 安装全部依赖（基础 + 两个可选组）：

```bash
uv pip install -e ".[torch,llm]"
```

(2) 生成包含可选依赖的锁文件：

```bash
uv pip compile pyproject.toml --all-extras -o requirements.lock
# 或只锁某一组：
uv pip compile pyproject.toml --extra llm -o requirements-llm.lock
uv pip install -r requirements.lock
```

讲义中的 `uv pip compile pyproject.toml -o requirements.lock` **默认只解析 `dependencies`**，不包含可选依赖组，所以不会锁住 torch。实测：同一个 `pyproject.toml`，不加参数时锁文件里只有 `numpy==...` 一个包；加上 `--extra llm` 后锁住 16 个包——`anthropic` 及其全部传递依赖（如 `pydantic`），每个都带精确版本和 `# via ...` 来源注释。

补充：如果用 `uv init` + `uv add torch numpy` 的项目式工作流，uv 会自动维护 `uv.lock`（讲义："uv generates uv.lock automatically when using uv add"），它会覆盖所有依赖组，团队成员用 `uv sync` 按锁文件同步环境。

### Q12 — 参考回答要点

- **venv**：Python 内置，只负责"建一个隔离目录"；包管理用 pip，不能安装 Python 本身，也不能管理非 Python 依赖。优点是到处可用、零安装。
- **conda**：跨语言的包与环境管理器，能安装 Python 本身以及 CUDA toolkit、cuDNN、C/C++ 库等二进制依赖；有自己的依赖求解器和软件源。适合共享集群、需要特定 CUDA toolkit 的场景；代价是较慢、与 pip 混用容易出问题。
- **uv**：用 Rust 写的 Python 包管理器，比 pip 快 10–100 倍；一个工具同时完成 Python 版本安装、虚拟环境、依赖解析、锁文件（`uv add` 自动生成 `uv.lock`）。课程推荐的默认选择。
- **怎么选**：默认 uv；装不了 uv 用 venv + pip；需要管理系统级二进制依赖或安装说明要求时用 conda（且尽量全程用 conda）。
- **加分点**：指出 PyTorch 的 pip wheel 已经自带 CUDA 运行时库，很多场景下不再需要 conda 来提供 CUDA；需要完整 CUDA 编译工具链（如编译自定义 kernel）时 conda 或 Docker 更方便。
- **常见误区**：在同一个环境里 conda 和 pip 交替安装。

### Q13 — 参考回答要点

- **激活做了什么**：`source .venv/bin/activate` 本质上只是修改当前 shell 的环境——把 `.venv/bin` 放到 `PATH` 最前面，设置 `VIRTUAL_ENV` 环境变量，并修改提示符显示 `(.venv)`。于是你输入 `python`/`pip` 时先找到 `.venv/bin` 里的版本。`deactivate` 则恢复原样。
- **不激活也能用**：直接执行 `.venv/bin/python train.py` 就会使用该环境的包——激活只是为了少打字。脚本、cron、IDE、Jupyter kernel 中常用这种"绝对路径"方式。
- **为什么不能拷贝**：`.venv` 里的解释器通常是指向创建时那个基础 Python 的链接（`pyvenv.cfg` 记录了基础解释器位置），脚本的 shebang 等也写死了绝对路径；编译好的扩展模块（如 numpy、torch 的二进制文件）还与操作系统、CPU 架构相关。换一台机器或换个目录就可能失效——这就是讲义说 venv "local, not portable" 的原因，正确做法是提交 `pyproject.toml` + 锁文件，在新机器上重建。
- **加分点**：`env_setup.sh` 用 `which python` 是否包含 `.venv` 来确认激活成功；在激活状态下用 `python -m pip` 可以确保 pip 与当前 python 是同一个环境。

### Q14 — 参考回答要点

- **版本范围（`pyproject.toml`）**：表达"我的代码兼容哪些版本"，是给人和依赖解析器看的**约束**。对于会被别人安装的库，应该尽量宽松，避免与使用方的其他依赖冲突。
- **锁文件**：记录"某一次解析得到的、包括传递依赖在内的**确切**版本"，解决**可复现性**：今天能跑、三个月后在另一台机器上也能得到一模一样的环境。对于应用、训练项目、服务，这是必需的。
- **CI 与生产**：CI 和部署一律从锁文件安装（如 `uv pip install -r requirements.lock` 或基于 `uv.lock` 的同步），并在 CI 中检查锁文件是否与 `pyproject.toml` 一致；升级依赖是一个**显式的动作**（重新生成锁文件 → 跑测试 → 提交），而不是每次安装时悄悄发生。
- **加分点**：锁文件可能因平台不同而不同（例如 CUDA 版 vs CPU 版 torch），需要注意目标平台；搭配 Docker 镜像（第 07 节）可以连系统层一起锁住。
- **常见误区**：在 `pyproject.toml` 里把所有版本都写成 `==` 来"代替锁文件"——传递依赖仍然没锁，还让依赖解析更容易冲突。

### Q15 — 参考回答要点

- **环境隔离**：两个项目各自一个虚拟环境（或各自一个 Docker 镜像），老项目装 cu118 版 torch 2.1，新项目装 cu124 版 torch 2.4；各自用锁文件固定版本。讲义的"按阶段/按项目分环境"正是这个思路。
- **驱动要求**：同一台机器只有**一个** NVIDIA 驱动，所有环境共用。根据"PyTorch 的 CUDA 版本 ≤ 驱动支持的版本"，驱动必须支持到 **CUDA 12.4 或更高**；由于驱动向后兼容，这样的驱动同样能运行 cu118 构建。所以应该升级驱动以满足**最高**需求，而不是试图在一台机器上装两个驱动。
- **验证**：在每个环境里分别运行 `python -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available())"`，并对照 `nvidia-smi`。
- **加分点**：用 Docker + NVIDIA 容器工具链能进一步把用户态 CUDA 库封装进镜像，宿主机只需要一个足够新的驱动；需要特定 CUDA toolkit（如编译扩展）时可以考虑 conda 环境。
- **常见误区**：以为"CUDA 11.8 的项目需要 11.8 的驱动"，于是把驱动降级，结果新项目跑不了。

### Q16 — 参考回答要点

1. **确认解释器**：两边都执行 `which python` 和 `python -c "import sys; print(sys.version, sys.executable)"`，排除"根本没激活环境/用错了 Python"这种最常见的情况（讲义常见错误 1、3）。
2. **对比已安装的包**：`uv pip freeze`（或 `python -m pip freeze`）导出两边的精确版本做 diff，重点看报错相关的包及其传递依赖。
3. **对比安装来源**：是否都从同一个锁文件安装？锁文件是否提交并且是最新的？`pyproject.toml` 中宽松的版本范围在不同时间解析会得到不同结果。
4. **平台差异**：操作系统、CPU 架构、Python 小版本，以及 GPU 相关的 `torch.version.cuda` 与 `nvidia-smi`（讲义常见错误 5）。
5. **复现与固化**：在一个全新的虚拟环境中按锁文件重装，能复现就说明是环境漂移；修复后更新锁文件，必要时用 Docker 固化。
- **加分点**：把第 01 节的预检脚本和本节的 `env_setup.sh` 这类检查纳入 CI，让"在我机器上能跑"尽早暴露。

---

## 六、关联知识点

### 前置知识
- [阶段 00 · 01 开发环境](../../01-dev-environment/docs/zh.md)：安装 uv、Python 3.12，第一次接触 `uv venv`。
- [阶段 00 · 02 Git & 协作](../../02-git-and-collaboration/docs/zh.md)：`.gitignore` 忽略 `.venv/`、提交锁文件。

### 本节被哪些后续内容用到
- [阶段 00 · 03 GPU 设置和云](../../03-gpu-setup-and-cloud/docs/zh.md)：CUDA 版本、`torch.version.cuda` 与驱动的关系。
- [阶段 00 · 05 Jupyter 笔记本](../../05-jupyter-notebooks/docs/zh.md)：notebook 的 kernel 必须指向正确的虚拟环境，否则"装了却 import 不到"。
- [阶段 00 · 07 用于 AI 的 Docker](../../07-docker-for-ai/docs/zh.md)：把 Python 环境连同系统库、CUDA 一起打包，是虚拟环境的进一步升级。
- [阶段 00 · 11 面向人工智能的 Linux](../../11-linux-for-ai/docs/zh.md)：PATH、shell 脚本、权限等本节脚本用到的 Linux 基础。
- [阶段 03 · 11 PyTorch 入门](../../../03-deep-learning-core/11-intro-to-pytorch/docs/zh.md)：按讲义的分阶段策略，从这里开始需要带 PyTorch 的环境。
- [阶段 11 · 01 提示工程](../../../11-llm-engineering/01-prompt-engineering/docs/zh.md)：LLM API 阶段只需要 SDK、不需要 torch，适合单独的轻量环境。

### 延伸关键词
`uv.lock / uv sync` · `uv pip compile --extra / --all-extras` · `PEP 621（pyproject 元数据）` · `PEP 668（externally managed）` · `pyvenv.cfg` · `bash 严格模式 set -euo pipefail` · `CUDA 驱动向后兼容` · `conda-forge` · `Docker 多阶段构建`
