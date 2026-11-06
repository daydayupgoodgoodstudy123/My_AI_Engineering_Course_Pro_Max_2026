# 测验 · 编辑器设置（Editor Setup）

> **阶段 00 · 环境搭建与工具 · 第 08 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/vscode/settings.json](../code/vscode/settings.json)、[code/vscode/extensions.json](../code/vscode/extensions.json)（两个 VS Code 配置文件，本节没有 `.py` 文件，动手题围绕配置和 SSH 展开）
>
> **用法**：装好 VS Code 和扩展、把本节的 `settings.json` 用起来、最好再连过一次远程机器后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> ⚠️ 注意：讲义正文写的是 `code/.vscode/`，但仓库里的实际目录是 `code/vscode/`（没有点）。第三部分 Q10 专门讨论这一点。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | AI 编辑器的五层 | 基础编辑器 → 扩展 → AI 相关设置 → 终端集成 → 远程开发，自下而上搭建 |
| 2 | LSP（Language Server Protocol） | 编辑器与"语言服务器"之间的标准协议，补全、跳转、类型信息、诊断都来自服务器；Pylance 是基于 Pyright 的 Python 语言服务器 |
| 3 | 核心扩展分工 | Python（解释器/运行）、Pylance（类型与补全）、Jupyter、Debugpy（断点调试）、Black（格式化）、Ruff（lint）、GitLens、Remote SSH |
| 4 | 静态类型检查 | `typeCheckingMode: "basic"` 在运行前发现参数类型错、属性不存在等问题；它看不到张量的运行时形状 |
| 5 | 保存即格式化 + 标尺 | Black 默认行宽 88；`editor.rulers: [88, 120]` 只是视觉参考线，不强制 |
| 6 | 自动保存 | `files.autoSave: "afterDelay"` 防止"终端里跑的是旧代码"；但按延迟自动保存**不会**触发 format on save |
| 7 | 输出与终端 | `notebook.output.scrolling` 防止训练日志撑爆输出区；终端 scrollback 调到 10000；分屏一边跑脚本一边 `watch -n 1 nvidia-smi` |
| 8 | Remote SSH | 在远程机上自动安装 VS Code Server，文件、终端、语言服务器都在远端跑，本地只负责界面 |
| 9 | SSH 密钥与 config | `ssh-keygen -t ed25519` + `ssh-copy-id` 实现免密；`~/.ssh/config` 里给主机起别名 |
| 10 | 替代编辑器 | Cursor / Windsurf 是 VS Code 分支，设置和扩展通用；Neovim 需要自己拼 LSP、格式化、notebook 插件，不熟 Vim 就别现在学 |

### 核心技能（能动手做到）

- [ ] 用 `code --install-extension` 装好讲义 Step 2 的 8 个扩展，并用 `code --list-extensions` 确认
- [ ] 把本节的两个 JSON 放到项目根目录的 `.vscode/` 下，打开项目时看到"推荐扩展"提示
- [ ] 写一个参数类型错误的函数调用，看到 Pylance 在编辑器里画红线；再写一段格式混乱的代码，`Ctrl+S` 后被 Black 格式化
- [ ] 能解释 `settings.json` 中 `"[python]"` 块、`files.exclude` 与 `search.exclude` 的区别
- [ ] 生成 ed25519 密钥、写好 `~/.ssh/config` 的 `Host` 别名，用 Remote SSH 打开远程 GPU 机上的文件夹
- [ ] 在集成终端里分屏：左边跑训练脚本，右边 `watch -n 1 nvidia-smi` 监控显存

---

## 二、基础自测（选择题）

**Q1.** 关于 LSP（Language Server Protocol），下列说法正确的是：

- A. 它是一种在编辑器之间同步文件的网络协议
- B. 它规定了编辑器如何从"语言服务器"获取补全、类型信息和诊断，因此同一个语言服务器可以服务多种编辑器
- C. 它是 VS Code 独有的插件格式，Neovim 无法使用
- D. 它负责把 Python 代码编译成字节码

**Q2.** 把 Pylance 的 `python.analysis.typeCheckingMode` 设为 `"basic"` 后，下列哪类问题**最可能**在运行前就被标出来？

- A. 两个张量 `(32, 128)` 和 `(64, 128)` 做矩阵乘时的形状不匹配
- B. 把一个字符串传给了类型注解为 `int` 的参数，或访问了对象上不存在的属性
- C. 训练过程中 GPU 显存溢出（CUDA OOM）
- D. 学习率设置得过大导致 loss 变成 NaN

**Q3.** 使用 Remote SSH 打开远程 GPU 机器上的项目时，下列描述正确的是：

- A. VS Code 先把远程项目完整同步到本地，编辑完再上传
- B. VS Code 会在远程机器上安装一个服务端组件，语言服务器和终端都在远端运行，本地主要负责界面
- C. 远程机器必须装有图形界面和 VS Code 桌面版
- D. 只能编辑文件，无法在远端调试或打开终端

**Q4.** 关于 `"editor.rulers": [88, 120]`，正确的理解是：

- A. 超过 88 列的代码会被编辑器禁止输入
- B. 88 对应 Black 的默认行宽，120 用来提示注释和 docstring 过长；标尺只是视觉参考线
- C. 88 是 PEP 8 规定的强制上限
- D. 设置后 Ruff 会自动把超过 120 列的行折行

**Q5.** 讲义推荐 `"files.autoSave": "afterDelay"`，在 AI 工作流中最主要是为了避免：

- A. 编辑器崩溃丢失代码
- B. 在终端里运行训练脚本时，跑的是还没保存的旧版本代码
- C. Git 提交时漏掉文件
- D. 远程连接断开

**Q6.** 项目里的 `.vscode/extensions.json` 写了一组 `recommendations`。团队成员打开这个项目时会发生什么？

- A. 所有扩展被静默自动安装
- B. VS Code 会提示安装推荐扩展，由用户确认
- C. 没有安装这些扩展就无法打开项目
- D. 它会覆盖用户已经安装的扩展版本

**Q7.** 在本节的配置里，Black 和 Ruff 的分工是：

- A. Black 负责 lint，Ruff 负责格式化
- B. 两者都只负责格式化，同时启用会冲突
- C. Black 被设为 Python 的默认格式化器（保存时格式化），Ruff 在保存时做 lint 检查
- D. Ruff 负责类型检查，Black 负责导入排序

**Q8.** 执行 `ssh-copy-id user@your-gpu-box-ip` 实际做了什么？

- A. 把远程服务器的私钥复制到本地
- B. 把本地公钥追加到远程用户的 `~/.ssh/authorized_keys` 中，之后可以用密钥免密登录
- C. 在远程服务器上生成一对新的密钥
- D. 把本地的 `~/.ssh/config` 同步到远程

---

## 三、动手 / 代码题

**Q9.** 阅读本节 `settings.json` 的这几行：

```json
    "[python]": {
        "editor.defaultFormatter": "ms-python.black-formatter",
        "editor.formatOnSave": true,
        "editor.codeActionsOnSave": {
            "source.organizeImports": "explicit"
        }
    },
```

```json
    "files.autoSave": "afterDelay",
    "files.autoSaveDelay": 1000,
```

你在一个 `.py` 文件里写了一段缩进、空格都很乱的代码，还在中间插了一行 `import os`，然后**什么键都不按**，等了 3 秒。

1. 文件会被保存吗？会被 Black 格式化吗？import 会被整理吗？
2. 接着你按了一次 `Ctrl+S`（macOS 为 `Cmd+S`），又会发生什么？
3. 为什么 `editor.formatOnSave` 写在 `"[python]"` 块里而不是顶层？对一个 `.yaml` 文件有什么影响？

**Q10.** 讲义说"把 `code/.vscode/settings.json` 复制过去""打开项目文件夹时 VS Code 会提示安装推荐扩展"，但仓库里的实际路径是 `code/vscode/settings.json` 和 `code/vscode/extensions.json`。

1. 直接用 VS Code 打开仓库根目录，这两个文件会生效吗？为什么？
2. 写出让它们对"整个仓库"生效的命令（假设当前在仓库根目录）。
3. 如果你的用户设置（User Settings）里 `editor.rulers` 是 `[100]`，而项目 `.vscode/settings.json` 里是 `[88, 120]`，最终生效的是哪个？

**Q11.** 你有一台云 GPU 机器：IP `203.0.113.50`，用户 `ubuntu`，私钥 `~/.ssh/id_ed25519`。你想要：

- 用 `ssh gpu-box` 一条命令登录，Remote SSH 里也能直接选 `gpu-box`；
- 登录时顺便把远程的 Jupyter（8888）和 TensorBoard（6006）端口转发到本地同名端口。

1. 写出 `~/.ssh/config` 中对应的配置块。
2. 讲义的示例配置里有 `ForwardAgent yes`。在多人共用的实验室服务器上，这行有什么风险？什么时候才应该打开？

---

## 四、面试高频题

**Q12.**（基础必考）什么是 LSP？它解决了编辑器生态里的什么问题？Pylance、Pyright 和 VS Code 的 Python 扩展分别是什么关系？

**Q13.**（原理深挖）静态类型检查在 ML/深度学习代码里能帮你抓到什么、抓不到什么？对于张量形状错误，你会用哪些手段在"运行前 / 运行早期"发现它？

**Q14.**（工程实践）团队里有人用 VS Code、有人用 PyCharm、有人用 Neovim。仅靠编辑器的"保存即格式化"能保证代码风格统一吗？你会怎么设计一套不依赖个人编辑器的规范保障？

**Q15.**（场景设计）你在云 GPU 机器上用 Remote SSH 开发，启动了一个预计跑 10 小时的训练，在 VS Code 集成终端里运行。半夜 Wi-Fi 断了一次，第二天发现训练进程没了。分析原因，并给出更稳妥的远程训练工作流。

**Q16.**（追问型）Cursor、Windsurf 这类 AI 原生编辑器和"VS Code + 扩展"相比，你在团队里选型时会关注哪些方面？讲义说"不熟 Vim 就别现在开始学"，你怎么看？

---

## 五、参考答案与解析

### Q1 — 答案：B

LSP 是编辑器（客户端）和语言服务器之间的标准协议：服务器负责理解代码（补全、跳转定义、类型信息、错误诊断），编辑器只负责展示。所以同一个 Pyright 可以被 VS Code、Neovim（经 nvim-lspconfig）等多种编辑器使用——讲义里 Neovim 方案正是靠 pyright/pylsp + nvim-lspconfig。A 是文件同步，C 错在 LSP 是开放标准，D 是解释器的工作。

### Q2 — 答案：B

静态类型检查只能看到**类型**（`str` vs `int`、某类有没有这个属性、函数参数个数），看不到运行时的**值**。张量形状是运行时的值，`torch.Tensor` 这个类型并不携带 `(32, 128)` 这样的形状信息，所以 A 抓不到——讲义说类型检查能省"tensor shape mismatches"的调试时间，这一点要打个折扣，它能帮你的是"参数传错类型、API 参数名写错"这类问题。C、D 都是运行时数值/资源问题。

### Q3 — 答案：B

讲义 Step 5 第 4 步："VS Code installs its server component on the remote machine automatically."（安装在远程用户的 `~/.vscode-server` 下）。文件留在远端，Pylance、终端、调试器都在远端执行，本地窗口负责渲染界面——所以能直接用远程 GPU 调试。A 描述的是"同步型"方案；C、D 都与事实相反，远程机只需要能 SSH 登录。

### Q4 — 答案：B

讲义原文："Black wraps at 88. The 120 marker shows when docstrings and comments are getting too long." 标尺只是参考线，不会阻止输入，也不会自己折行（A、D 错）。PEP 8 建议的是 79 列，88 是 Black 的默认值（C 错）。本节还用 `"black-formatter.args": ["--line-length", "88"]` 显式固定了行宽。

### Q5 — 答案：B

讲义："You will forget to save. Your training script will run stale code. Auto-save prevents that." 在编辑器里改了超参数、没保存就去终端 `python train.py`，跑的其实是磁盘上的旧版本——几小时 GPU 时间白费，而且很难察觉。`files.autoSaveDelay: 1000` 表示停止输入 1 秒后自动保存。

### Q6 — 答案：B

`extensions.json` 的 `recommendations` 是"推荐"，VS Code 打开工作区时会弹出提示（也可以在扩展面板里用"显示推荐的扩展"查看），由用户决定是否安装，不会静默安装，也不会强制或改版本。它的价值是把"这个项目需要哪些扩展"写进仓库，新人一键装齐。

### Q7 — 答案：C

`"[python]"` 里 `"editor.defaultFormatter": "ms-python.black-formatter"` 指定 Black 为默认格式化器；`"ruff.lint.run": "onSave"` 让 Ruff 在保存时跑 lint。讲义扩展表也写明：Black — "Auto-format on save"，Ruff — "Fast linting, catches common mistakes"。类型检查是 Pylance 的工作（D 错）。（Ruff 本身也能格式化，但本节配置没有让它承担这个角色。）

### Q8 — 答案：B

`ssh-copy-id` 把本地公钥（默认 `~/.ssh/id_*.pub`，本节是 `id_ed25519.pub`）追加到远程用户的 `~/.ssh/authorized_keys`，之后 SSH 用私钥完成认证，不再需要密码。私钥永远只留在本地，不应被复制到任何地方（A 是严重的安全错误）。

### Q9 — 参考答案

1. **会被保存，但不会被格式化，import 也不会被整理。** 3 秒后 `afterDelay` 自动保存触发了，但 VS Code 的 `editor.formatOnSave` 只在"非延迟自动保存"时执行——设置说明里写明了"the file must not be saved after delay"。`codeActionsOnSave` 里的 `"explicit"` 也表示只在**显式保存**（手动 `Ctrl+S`）时执行。
2. 按 `Ctrl+S` 是显式保存：先执行 code action 整理 import（`source.organizeImports`），再由 Black 格式化，文件变整齐。所以讲义"Never think about formatting again"在开启延迟自动保存后要打个折扣——要么养成手动 `Ctrl+S` 的习惯，要么改用 `"files.autoSave": "onFocusChange"`（切走焦点时保存，这种模式会触发格式化），并在 pre-commit / CI 中再兜底。
3. `"[python]"` 是**语言级设置**，只对 Python 文件生效。把格式化器和保存即格式化限定在 Python 上，可以避免对 YAML、JSON、Markdown 等文件用错格式化器或产生意外改动。对 `.yaml` 文件：这几行不起作用，保存时不会被格式化（除非用户/其他设置对 YAML 单独开启，例如装了 `redhat.vscode-yaml` 并另行配置）。

### Q10 — 参考答案

1. **不会自动生效。** VS Code 只把**被打开的工作区文件夹根目录**下的 `.vscode/settings.json`、`.vscode/extensions.json` 当作工作区配置。`code/vscode/` 既不在根目录，目录名也少了前面的点，VS Code 只会把它当普通文件。讲义写的 `code/.vscode/` 与仓库实际路径不一致，即使是 `code/.vscode/`，也只有在直接打开 `code/` 这个目录时才会生效。
2. 在仓库根目录执行：

```bash
mkdir -p .vscode
cp phases/00-setup-and-tooling/08-editor-setup/code/vscode/settings.json .vscode/
cp phases/00-setup-and-tooling/08-editor-setup/code/vscode/extensions.json .vscode/
```

   然后 `Ctrl+Shift+P` → "Developer: Reload Window"。如果想对**所有项目**生效，就把 `settings.json` 的内容合并进用户设置（"Preferences: Open User Settings (JSON)"）。
3. 生效的是 **`[88, 120]`**。VS Code 设置的优先级是：默认值 < 用户设置 < 工作区设置（< 工作区文件夹设置），越具体的作用域越优先；语言级设置（如 `"[python]"`）又会覆盖同作用域内的通用设置。

### Q11 — 参考答案

1. 配置块：

```
Host gpu-box
    HostName 203.0.113.50
    User ubuntu
    IdentityFile ~/.ssh/id_ed25519
    LocalForward 8888 localhost:8888
    LocalForward 6006 localhost:6006
```

   之后 `ssh gpu-box` 登录，同时本地访问 `http://localhost:8888` 就会转发到远端的 8888。Remote SSH 会读取同一个 `~/.ssh/config`，在 "Connect to Host" 列表里直接出现 `gpu-box`。（Remote SSH 本身也会对终端里检测到的端口自动转发，手写 `LocalForward` 的好处是普通 `ssh` 登录时也生效。）
2. `ForwardAgent yes` 会把本地的 ssh-agent 转发到远程。远端上**拥有 root 权限的人**（或攻破了你账户的人）可以在你登录期间借用这个 agent 套接字，以你的身份去登录你的密钥能访问的其他机器（比如 GitHub、公司跳板机）。所以只在**你信任的、单人独占**的机器上、且确实需要（例如要在远端 `git push` 而又不想把私钥放到远端）时才开启；共享服务器上建议关掉，或改用远端专用的 deploy key / `ProxyJump` 跳转。

### Q12 — 参考回答要点

- **定义**：LSP 是微软提出的开放协议，规定编辑器（client）与语言服务器（server）之间如何交换"补全、悬停信息、跳转定义、查找引用、重命名、诊断"等信息，通常基于 JSON-RPC。
- **解决的问题**：没有 LSP 时，M 个编辑器 × N 种语言需要 M×N 套插件；有了 LSP，每种语言写一个 server、每个编辑器实现一次 client，变成 M+N。这也是 Neovim 能用上和 VS Code 同等级 Python 智能提示的原因。
- **关系**：Pyright 是微软开源的 Python 类型检查器/语言服务器；Pylance 是基于 Pyright 的 VS Code 专用语言服务器扩展（讲义："Microsoft's Python language server using Pyright"），提供补全、类型检查、自动导入；`ms-python.python` 是总入口，负责解释器/虚拟环境选择、运行和调试集成。
- **加分点**：Pylance 的 `typeCheckingMode` 有 `off / basic / standard / strict` 几档；团队里可以把检查配置写进 `pyproject.toml`（`[tool.pyright]`），让 CI 里的 pyright 和编辑器里的 Pylance 用同一套规则。

### Q13 — 参考回答要点

- **能抓到**：参数类型错（传了 `str` 给 `int`）、`None` 未处理（`Optional` 没判空就调用方法）、拼错属性/方法名、函数参数个数不对、返回类型与注解不符、导入不存在的模块。这些在 ML 代码里非常常见，尤其是配置对象、数据管道里。
- **抓不到**：张量形状、dtype 不匹配、device 不一致（CPU vs CUDA）、数值问题（NaN/Inf）、显存溢出——它们都由运行时的值决定。
- **补救手段**：
  - 关键位置写 `assert x.shape == (B, T, C)` 之类的形状断言，失败时立刻定位；
  - 用 jaxtyping 等库给张量写带形状的注解，并配合运行时检查；
  - 先用极小的 batch / 极少的步数跑一遍（smoke test），几秒内暴露形状错误，而不是训练几小时后才崩；
  - 在调试器里打断点检查中间张量（第 12 节的内容）。
- **常见误区**：以为开了类型检查就能防止 shape bug；或者因为 ML 代码"动态"就完全不写类型注解。

### Q14 — 参考回答要点

- **结论**：不能。编辑器设置是"个人便利"，不是"团队约束"——有人没装扩展、有人用别的编辑器、还有 Q9 里"延迟自动保存不触发格式化"这种情况。
- **单一事实来源**：把 Black / Ruff / pyright 的配置写进仓库的 `pyproject.toml`，编辑器、命令行、CI 都读这一份。
- **三道关卡**：
  1. 编辑器：`.vscode/settings.json` + `extensions.json` 给 VS Code 用户开箱即用（本节内容）；
  2. 提交前：pre-commit 钩子跑 `ruff check`、`black --check`（或自动修复），不合规不让提交；
  3. CI：同样的检查在 CI 中再跑一遍，作为最终把关，PR 不通过不能合并。
- **配套**：`.editorconfig` 统一缩进/换行/结尾空行这类跨编辑器的基础设置；格式化一次性全仓库执行，并把那个提交加入 `.git-blame-ignore-revs`，避免污染 blame。
- **加分点**：强调"让工具来争论风格，而不是让人在 code review 里争论"。

### Q15 — 参考回答要点

- **原因**：VS Code 集成终端里的进程是远端 VS Code Server 会话的子进程（本质上挂在一次 SSH 连接上）。连接断开、窗口关闭、服务端重连失败时，终端会话可能被回收，前台进程收到挂断信号（SIGHUP）后退出。即便有时能自动重连，也不能指望它。
- **稳妥做法**：
  1. 用 `tmux` / `screen` 跑长任务：`tmux new -s train` → 运行 → `Ctrl+B D` 脱离，断线后 `tmux attach -t train` 回来（第 10 节）；
  2. 或 `nohup python train.py > train.log 2>&1 &`，再用 `tail -f train.log` 看日志；
  3. 训练脚本本身要**定期保存 checkpoint**，支持从断点恢复——这才是根本保障（机器被回收、OOM 时同样有效）；
  4. 日志写文件或上报到实验追踪平台，而不是只依赖终端滚动输出；
  5. 用分屏终端 `watch -n 1 nvidia-smi` 监控 GPU。
- **加分点**：区分"编辑器连接"（可断可重连）与"训练进程"（必须独立于连接存活）；生产训练用作业调度系统（如 Slurm、Kubernetes Job）而不是交互式终端。

### Q16 — 参考回答要点

- **兼容性**：讲义指出 Cursor、Windsurf 都是 VS Code 分支，沿用同样的扩展生态、设置格式和 Remote SSH，迁移成本低——本节的 `settings.json` / `extensions.json` 可以直接导入。
- **选型关注点**：
  - 代码与数据隐私：代码片段会不会发送到第三方云端、是否支持企业级的数据不留存策略、能否使用自有模型或 API key；
  - 密钥安全：`.env`、凭据文件是否会被纳入 AI 的上下文，是否支持忽略规则；
  - 生成质量与可控性：对大仓库的上下文理解、能否精细地审阅和回滚 AI 的改动；
  - 成本与团队统一：订阅费用、是否与现有 CI、代码规范、远程开发流程兼容。
- **关于 Vim**：讲义的立场是"已经熟练就留在 Vim；不熟就别现在学"，理由是学习曲线会和学习 AI 工程本身抢时间。这是务实的建议：编辑器只是工具，核心竞争力在于把模型、数据、系统做对。
- **加分点**：无论用哪个编辑器，团队约束都应落在仓库配置和 CI 上（见 Q14），而不是依赖某个编辑器的特性。

---

## 六、关联知识点

### 前置知识
- [阶段 00 · 01 开发环境](../../01-dev-environment/docs/zh.md)：Python、包管理器装好，编辑器才能识别解释器。
- [阶段 00 · 06 Python 环境](../../06-python-environments/docs/zh.md)：`.venv` 与解释器选择，Pylance 解析 import 依赖它。

### 本节被哪些后续内容用到
- [阶段 00 · 02 Git & 协作](../../02-git-and-collaboration/docs/zh.md)：GitLens、`git.autofetch` 等设置服务于日常 Git 工作流。
- [阶段 00 · 05 Jupyter 笔记本](../../05-jupyter-notebooks/docs/zh.md)：在 VS Code 里运行 notebook、`notebook.output.*` 设置。
- [阶段 00 · 03 GPU 设置和云](../../03-gpu-setup-and-cloud/docs/zh.md)：Remote SSH 的主要使用场景就是云 GPU 机器。
- [阶段 00 · 10 终端与 Shell](../../10-terminal-and-shell/docs/zh.md)：集成终端、tmux 保活长任务（对应 Q15）。
- [阶段 00 · 11 面向人工智能的 Linux](../../11-linux-for-ai/docs/zh.md)：SSH、权限、远程机器管理。
- [阶段 00 · 12 调试与性能分析](../../12-debugging-and-profiling/docs/zh.md)：Debugpy 断点调试的完整用法。
- [阶段 03 · 13 调试神经网络](../../../03-deep-learning-core/13-debugging-neural-networks/docs/zh.md)：形状、NaN 等静态检查抓不到的问题（对应 Q13）。
- [阶段 15 · 09 编码 Agent 版图](../../../15-autonomous-systems/09-coding-agent-landscape/docs/zh.md)：AI 原生编辑器与编码 Agent 的全景（对应 Q16）。

### 延伸关键词
`LSP / JSON-RPC` · `Pyright 配置 (pyproject.toml)` · `pre-commit` · `.editorconfig` · `Dev Containers` · `SSH ProxyJump / LocalForward` · `tmux` · `jaxtyping` · `.git-blame-ignore-revs`
