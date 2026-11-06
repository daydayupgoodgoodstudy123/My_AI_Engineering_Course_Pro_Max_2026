# 测验 · Git & 协作（Git & Collaboration）

> **阶段 00 · 环境搭建与工具 · 第 02 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：本节为概念课（Learn），没有代码文件，动手题以命令行操作为主
>
> **用法**：学完讲义、在自己的 fork 上实际操作过一遍后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。动手题建议在一个临时目录里 `git init` 一个练习仓库来做，不要在课程仓库上试错。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 四个区域 | 工作区（Working Directory）→ 暂存区（Staging Area）→ 本地仓库（Local Repo）→ 远程仓库（Remote，如 GitHub） |
| 2 | 日常三步 | `git add` 放进暂存区 → `git commit` 生成快照 → `git push` 备份到远程 |
| 3 | Commit 是什么 | 某一时刻**整个项目的快照**，不是"保存一个文件" |
| 4 | Branch 是什么 | 一个**指向某个 commit 的指针**，随着你提交不断向前移动，不是"整份代码的拷贝" |
| 5 | 分支做实验 | `git checkout -b experiment/xxx` 新建并切换分支，实验不影响 main；成功了再 `git merge` 回 main |
| 6 | fetch vs pull | `fetch` 只把远程的新提交下载到本地仓库；`pull` = fetch + 合并进当前分支和工作区 |
| 7 | Fork 工作流 | 课程仓库只有维护者能写，要先 Fork 到自己账号，再 clone 自己的 fork，`origin` 才指向你能 push 的地方 |
| 8 | `.gitignore` | 排除模型权重（`.pt`/`.pth`/`.safetensors`）等大二进制文件；**只对未被跟踪的文件生效** |
| 9 | 查看历史 | `git log --oneline` 一行一个提交，快速了解项目如何演进 |

### 核心技能（能动手做到）

- [ ] 用 `git config --global` 配好 `user.name` 和 `user.email`，并用 `git config --global --list` 确认
- [ ] Fork 课程仓库 → clone 自己的 fork → 新建 `my-progress` 分支 → 新建文件、提交、`git push origin my-progress`，在 GitHub 网页上看到这个分支
- [ ] 在实验分支上提交改动，切回 main 观察文件"消失"，再 merge 回来，说出这次合并是不是 fast-forward
- [ ] 写一个 AI 项目的 `.gitignore`（权重、虚拟环境、缓存、`.env`），并用 `git check-ignore -v <文件>` 验证规则命中
- [ ] 把一个**已经被提交过**的权重文件从跟踪中移除（`git rm --cached`），同时保留本地文件
- [ ] 用 `git log --oneline` 阅读课程仓库的历史，找出某一节是哪次提交加入的

---

## 二、基础自测（选择题）

**Q1.** 你修改了已被跟踪的 `train.py`，没有执行 `git add`，直接运行 `git commit -m "tweak lr"`。结果是：

- A. 修改被正常提交
- B. Git 提示 `no changes added to commit`，什么都没有提交
- C. 修改被提交，但不会被 push
- D. Git 自动执行 `git add .` 后提交

**Q2.** 关于 branch（分支），下列说法**最准确**的是：

- A. 新建分支会把整个项目复制一份到新目录
- B. 分支是一个指向某个 commit 的指针，在该分支上提交时指针向前移动
- C. 分支只能在 GitHub 网页上创建
- D. 每个分支都有自己独立的远程仓库

**Q3.** 执行 `git checkout -b experiment/new-optimizer` 的效果是：

- A. 删除名为 `experiment/new-optimizer` 的分支
- B. 从 GitHub 下载名为 `experiment/new-optimizer` 的分支
- C. 基于当前提交新建 `experiment/new-optimizer` 分支，并切换过去
- D. 把当前分支重命名为 `experiment/new-optimizer`

**Q4.** 你已经把 `model.pt` 提交进了仓库，之后才在 `.gitignore` 里加上 `*.pt`。再修改 `model.pt`，`git status` 会显示：

- A. 什么都不显示，因为它已经被忽略
- B. ` M model.pt`，它仍然被跟踪，`.gitignore` 对已跟踪文件无效
- C. Git 自动把 `model.pt` 从仓库中删除
- D. 报错：`.gitignore` 与已提交文件冲突

**Q5.** 关于 `git fetch` 和 `git pull`，正确的是：

- A. 两者完全相同
- B. `fetch` 下载远程的新提交但不改动你的工作区；`pull` 在 fetch 之后还会合并进当前分支
- C. `pull` 只下载不合并，`fetch` 会合并
- D. `fetch` 用于上传，`pull` 用于下载

**Q6.** 你直接 `git clone` 了课程原仓库（不是自己的 fork），然后 `git push origin my-progress` 被拒绝。根本原因是：

- A. 分支名不能包含连字符
- B. 你还没有 `git add`
- C. `origin` 指向课程原仓库，只有维护者有写权限；应先 Fork，再让 `origin` 指向自己的 fork
- D. GitHub 不允许 push 非 main 分支

**Q7.** 为什么讲义建议把 `.pt`、`.pth`、`.safetensors` 加入 `.gitignore`？

- A. Git 完全无法存储二进制文件
- B. 它们是模型权重/检查点文件，常常有几百 MB 到几 GB，Git 不是为大二进制文件设计的
- C. 它们是测试文件，不应该提交
- D. 它们一定包含 API 密钥

---

## 三、动手 / 代码题

**Q8.**（预测输出）在一个空目录执行以下命令（`git init -b main` 把默认分支命名为 main）。写出两次 `ls` 的输出，并判断 `git merge` 这一步是不是 fast-forward，为什么？

```bash
git init -q -b main demo && cd demo
echo a > a.txt && git add a.txt && git commit -qm "init"
git checkout -b experiment/new-optimizer
echo b > b.txt && git add b.txt && git commit -qm "try adamw"
git checkout main
ls
git merge experiment/new-optimizer
ls
```

**Q9.**（写配置 + 验证）为一个 AI 项目写 `.gitignore`，要求忽略：PyTorch/safetensors 权重、虚拟环境 `.venv/`、Python 字节码缓存、Jupyter 自动保存目录、存放密钥的 `.env` 文件。然后写出验证某个文件是否被忽略、被哪条规则忽略的命令。

**Q10.**（找 bug + 修复）同事的操作记录如下，他说"我明明把 `*.pt` 加进 `.gitignore` 了，为什么 `git status` 还一直显示 `model.pt` 被修改？"

```bash
git add model.pt train.py
git commit -m "first training run"
echo '*.pt' >> .gitignore
# ……之后重新训练，model.pt 被覆盖……
git status --short
#  M model.pt
```

(a) 解释原因；(b) 给出"停止跟踪 `model.pt` 但保留本地文件"的命令序列；(c) 如果这个提交已经 push 到了 GitHub，仅做 (b) 够不够？

**Q11.**（设计）你按讲义 Fork 并 clone 了自己的 fork，在 `my-progress` 分支学习。一个月后课程原仓库新增了很多课程，你想把更新同步到自己的分支。写出需要的命令，并说明每个 remote 的作用。

---

## 四、面试高频题

**Q12.**（基础必考）解释 Git 的工作区、暂存区、本地仓库、远程仓库。为什么要有"暂存区"这一层？

**Q13.**（原理深挖）Git 的 commit 和 branch 在底层分别是什么？为什么说在 Git 里"建分支几乎零成本"？

**Q14.**（工程实践）ML 项目里有代码、配置、数据集、模型权重、实验日志。哪些放进 Git，哪些不放？不放的怎么做版本管理？

**Q15.**（场景设计）你训练出一个效果很好的模型，三周后想精确复现它。从版本控制的角度，你需要提前记录什么？

**Q16.**（追问型）"如果你不小心把 OpenAI/Anthropic 的 API key 提交并 push 到了公开的 GitHub 仓库，你会怎么处理？只删掉文件再提交一次行不行？"

---

## 五、参考答案与解析

### Q1 — 答案：B

`git commit` 只提交**暂存区**里的内容。修改了已跟踪文件却没 `git add`，暂存区与上次提交相同，Git 会打印：

```text
Changes not staged for commit:
	modified:   train.py

no changes added to commit (use "git add" and/or "git commit -a")
```

并以非 0 退出码结束。D 错：只有 `git commit -a` 才会自动暂存**已跟踪**文件的修改（新文件仍不会被包含）。

### Q2 — 答案：B

讲义的 Key Terms 专门纠正了"分支 = 一份拷贝"的误解：分支只是一个指向 commit 的指针，在它上面提交时指针前移。A 是 SVN 等老工具的"目录拷贝式"分支给人的印象；C、D 都不对，分支可以在本地随意创建，也不需要独立远程。

### Q3 — 答案：C

`-b` 表示"新建并切换"。新分支从**当前所在的提交**出发。新版 Git 中等价命令是 `git switch -c experiment/new-optimizer`。分支名中的 `/` 只是命名约定（常用来分组，如 `experiment/`、`fix/`），不是目录。

### Q4 — 答案：B

`.gitignore` 只决定"**未跟踪**的文件要不要出现在 `git status` 里、`git add .` 时要不要加进来"。一旦文件被提交过，它就是已跟踪文件，之后的修改照样会显示为 ` M model.pt`。要停止跟踪必须显式执行 `git rm --cached model.pt`（见 Q10）。

### Q5 — 答案：B

`git fetch` 把远程的新提交下载到本地仓库（更新 `origin/main` 这类远程跟踪分支），不动你的工作区和当前分支；`git pull` = `git fetch` + 把远程分支合并进当前分支（默认 merge，可配置为 rebase）。讲义的时序图把这两步画成 `Remote → Local Repo（fetch）`、`Local Repo → Working Directory（pull）`，是一种简化的示意。先 fetch 再看差异（`git log main..origin/main`）是更稳妥的习惯。

### Q6 — 答案：C

讲义第 4 步：课程仓库只有维护者有写权限。直接 clone 原仓库时，`origin` 指向原仓库，push 自然被拒（403 / permission denied）。正确做法是先在 GitHub 上点 Fork，再 clone `https://github.com/YOUR-USERNAME/ai-engineering-from-scratch.git`。已经 clone 错了也不用重来：`git remote set-url origin <你的 fork 地址>` 即可。

### Q7 — 答案：B

模型检查点动辄数百 MB 到数 GB。Git 会把每个版本的完整内容存进历史，大文件会让仓库迅速膨胀、clone 变慢；GitHub 对单文件大小也有限制。A 错：Git 能存二进制，只是不擅长（无法有效 diff/压缩）。D 错：权重文件里不是密钥——密钥应放在 `.env` 并忽略它（见第 04 节）。

### Q8 — 参考答案

```text
ls（第一次，在 main 上）:
a.txt

git merge 输出（节选）:
Updating xxxxxxx..yyyyyyy
Fast-forward
 b.txt | 1 +
 1 file changed, 1 insertion(+)
 create mode 100644 b.txt

ls（第二次）:
a.txt
b.txt
```

解析：
- 切回 main 后，工作区会被替换成 main 指向的快照，`b.txt` 只存在于实验分支的提交里，所以第一次 `ls` 只有 `a.txt`。这正是"分支做实验不影响 main"的直观体现。
- 是 **fast-forward**：main 自从分出实验分支之后没有任何新提交，main 指向的提交是实验分支的祖先。Git 只需要把 main 这个指针"快进"到 `try adamw` 那个提交，不需要生成合并提交。
- 如果在 merge 之前 main 上也有新提交，两条线就分叉了，Git 会做三方合并并生成一个 merge commit（有冲突时需要手动解决）。

### Q9 — 参考答案

```gitignore
# 模型权重 / 检查点
*.pt
*.pth
*.safetensors

# 虚拟环境
.venv/

# Python 字节码缓存
__pycache__/

# Jupyter 自动保存
.ipynb_checkpoints/

# 密钥与本地配置
.env
```

验证：

```bash
git check-ignore -v new.pth .env w.safetensors .venv/x
```

实测输出格式为"`来源文件:行号:规则<TAB>路径`"：

```text
.gitignore:2:*.pth	new.pth
.gitignore:7:.env	.env
.gitignore:3:*.safetensors	w.safetensors
.gitignore:4:.venv/	.venv/x
```

要点：
- 结尾的 `/` 表示只匹配目录。
- ⚠️ `git check-ignore` 默认**不会**报告已经被跟踪的文件（即使规则匹配）——这又一次说明 `.gitignore` 对已跟踪文件不起作用；需要时可加 `--no-index`。
- 加分：还可以忽略 `wandb/`、`mlruns/`、`data/` 等实验输出与数据目录（数据管理见第 09 节）。

### Q10 — 参考答案

(a) `model.pt` 在加规则之前已经被 commit，成了**已跟踪**文件；`.gitignore` 对已跟踪文件不生效，所以每次重新训练覆盖它都会显示为修改。

(b)

```bash
git rm --cached model.pt        # 只从暂存区/索引中删除，保留磁盘上的文件
git add .gitignore
git commit -m "Stop tracking model checkpoints"
```

执行 `git rm --cached` 后 `git status --short` 会显示 `D  model.pt`（下一次提交将删除它的跟踪），提交之后本地的 `model.pt` 仍在，且之后会被 `*.pt` 规则忽略。注意不要漏了 `--cached`，否则本地文件也会被删掉。

(c) 不够。之前的提交仍然在历史里，任何人 clone 仓库都会下载这个大文件，仓库体积不会变小。要彻底移除需要**改写历史**（如 `git filter-repo` 等工具）并强制推送，这会影响所有协作者，需要事先沟通。对于确实需要版本化的大文件，应改用 Git LFS 或 DVC（第 09 节）。如果泄露的是密钥而不是权重，第一步永远是**作废/轮换密钥**（见 Q16）。

### Q11 — 参考答案

```bash
# 一次性：添加原仓库为 upstream
git remote add upstream https://github.com/<原作者>/ai-engineering-from-scratch.git
git remote -v        # origin = 你的 fork（可 push），upstream = 原仓库（只读）

# 每次同步
git fetch upstream
git checkout my-progress
git merge upstream/main          # 把原仓库 main 的新提交合并进你的学习分支
git push origin my-progress      # 备份到你自己的 fork
```

说明：
- `origin` 是你 clone 的来源，也就是你的 fork，有写权限；`upstream` 是约定俗成的名字，指向原仓库，只用来拉取更新。
- 你的学习代码在独立分支上，和课程新增内容通常不冲突；如果改过课程原文件，可能需要解决冲突。
- 讲义说本课程不需要 rebase，所以这里用 merge 即可。GitHub 网页上的 "Sync fork" 按钮可以同步 fork 的 main，但不会帮你合并进 `my-progress`。

### Q12 — 参考回答要点

- **四个区域**：工作区是你正在编辑的文件；暂存区（index）是"下一次提交将包含什么"的清单；本地仓库保存所有提交历史（`.git` 目录）；远程仓库是托管在 GitHub/GitLab 上的副本，用于备份与协作。
- **为什么要暂存区**：让你**挑选**要提交的内容。一次改了模型代码、顺手调了日志格式、还临时加了 debug print——可以只 `git add` 前者，把一次修改拆成多个语义清晰的提交，便于 review 和回滚。`git add -p` 甚至能按代码块挑选。
- **加分点**：提到 `git diff`（工作区 vs 暂存区）与 `git diff --staged`（暂存区 vs 最新提交）的区别。
- **常见误区**：以为 `git commit` 就已经备份到云端了——commit 只在本地，`push` 之后才在远程。

### Q13 — 参考回答要点

- **Commit**：一个对象，记录整个项目的快照（指向一个 tree 对象，tree 再指向各个文件内容 blob）、父提交、作者、时间、提交信息；用内容哈希（SHA）作为 ID。因为包含父提交指针，所有提交构成一张**有向无环图（DAG）**。
- **Branch**：一个很小的引用文件，里面只存一个 commit 哈希；`HEAD` 指向你当前所在的分支。在分支上提交时，Git 新建 commit 并把分支指针移到它上面。
- **为什么零成本**：新建分支只是新建一个指针，不复制任何文件；未变化的文件在不同快照之间共享同一个 blob。
- **加分点**：能解释 fast-forward merge 就是移动指针；merge commit 有两个父提交。
- **常见误区**：认为 commit 存的是"diff"——概念上存的是快照（底层打包时才会做增量压缩）。

### Q14 — 参考回答要点

- **放进 Git**：源代码、训练/评估配置（YAML/JSON）、依赖声明与锁文件、小型示例数据、文档、`.gitignore` 本身。
- **不放进 Git**：模型权重（`.pt`/`.pth`/`.safetensors`）、大数据集、虚拟环境、缓存、实验跟踪产物、`.env` 等密钥。
- **不放的怎么版本化**：
  - Git LFS：仓库里只存指针，真实文件存在另一个服务器上；
  - DVC：为数据和模型生成元数据文件放进 Git，真实数据放在远端存储；
  - 模型仓库（如 Hugging Face Hub）或对象存储，Git 里只记录模型的版本号/哈希/下载地址。
- **加分点**：强调"Git 里记录的东西要足以**找回**大文件"，例如配置中写明数据集版本、权重的哈希。
- **常见误区**：先把大文件提交了再加 `.gitignore`，以为就清理干净了（见 Q10）。

### Q15 — 参考回答要点

- **代码版本**：训练时的 commit 哈希（并确保没有未提交的改动——"dirty"工作区跑出的结果无法复现）。常见做法是在训练脚本启动时把 `git rev-parse HEAD` 和 `git status` 结果写进实验日志。
- **配置**：所有超参数放在配置文件里随代码提交，而不是散落在命令行参数中。
- **环境**：依赖锁文件、Python/CUDA/PyTorch 版本（与第 01、06 节呼应）。
- **数据**：数据集的版本或哈希（DVC/LFS/数据集仓库）。
- **随机性**：随机种子；了解 GPU 上部分算子的非确定性。
- **实验分支 + tag**：好的实验可以在分支上提交并打 tag（如 `exp-2026-10-adamw-best`），方便日后 checkout。
- **加分点**：提到 W&B、MLflow 等实验跟踪工具会自动记录 git 提交信息。

### Q16 — 参考回答要点

- **第一步，立刻作废/轮换密钥**：到服务商控制台 revoke 旧 key、生成新 key。公开仓库被自动化扫描器抓取可能只需要几分钟，**删除文件不等于密钥安全**。
- **为什么只删文件不行**：再提交一次"删除"只影响最新快照，旧提交里仍然有完整内容，任何人都能 `git log -p` 或在 GitHub 上翻历史看到。
- **清理历史**：用 `git filter-repo` 之类工具改写历史并强制推送，通知协作者重新 clone；但这只是"减少暴露"，不能替代第一步。
- **检查损失**：查看服务商的用量/账单，确认有没有被盗用。
- **预防**：密钥放 `.env` 并在 `.gitignore` 里忽略、用环境变量读取（第 04 节）；开启 GitHub secret scanning / push protection；加 pre-commit 密钥扫描钩子。
- **常见误区**：只把仓库改成 private 了事——密钥已经泄露过，仍必须轮换。

---

## 六、关联知识点

### 前置知识
- [阶段 00 · 01 开发环境](../../01-dev-environment/docs/zh.md)：安装好 git（预检脚本中所有路线的必需项）并会使用终端。

### 本节被哪些后续内容用到
- [阶段 00 · 04 APIs 与密钥](../../04-apis-and-keys/docs/zh.md)：`.env` + `.gitignore` 防止密钥被提交，正是本节 `.gitignore` 的直接应用。
- [阶段 00 · 05 Jupyter 笔记本](../../05-jupyter-notebooks/docs/zh.md)：notebook 的输出、`.ipynb_checkpoints/` 如何与 Git 共处。
- [阶段 00 · 09 数据管理](../../09-data-management/docs/zh.md)：用 `.gitignore`、Git LFS、DVC 管理大型数据集和模型文件。
- [阶段 00 · 10 终端与 Shell](../../10-terminal-and-shell/docs/zh.md)：熟练的命令行操作让 Git 日常工作更顺手。
- [阶段 17 · 25 安全、密钥与审计](../../../17-infrastructure-and-production/25-security-secrets-audit/docs/zh.md)：生产环境中的密钥管理与审计，是 Q16 的系统化延伸。
- 课程后续所有阶段：每一节的代码练习都在你的 `my-progress` 分支上提交和备份。

### 延伸关键词
`git switch / git restore` · `merge vs rebase` · `fast-forward` · `Pull Request / Code Review` · `Git LFS` · `DVC` · `git filter-repo` · `pre-commit hooks` · `GitHub secret scanning`
