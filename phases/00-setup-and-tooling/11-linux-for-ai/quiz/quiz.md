# 测验 · 面向人工智能的 Linux（Linux for AI）

> **阶段 00 · 环境搭建与工具 · 第 11 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：本节为概念课（Learn），没有代码文件，动手题以命令行操作和排障为主
>
> **用法**：学完讲义、在一台 Linux 机器（云 GPU、虚拟机或 WSL2 都行）上把讲义练习做一遍后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。涉及 `rm -rf`、`chmod`、`kill` 的题目请在临时目录或自己的测试机上练习。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 单根目录树 | 一切都挂在 `/` 下：`/home/用户名`（你的工作区，即 `~`）、`/tmp`（重启清空）、`/etc`（配置）、`/var/log`（日志）、`/mnt`（外挂盘）、`/proc` `/sys`（内核与硬件的虚拟文件） |
| 2 | 15 个生存命令 | `pwd ls cd mkdir cp mv rm cat head tail less grep find` 等；`rm -rf` 没有回收站 |
| 3 | 权限位 | `-rwxr-xr--`：属主 / 属组 / 其他人 各三位 rwx；数字写法 r=4、w=2、x=1，`755`、`644` 最常用 |
| 4 | chmod / chown / sudo | `chmod +x` 让脚本可执行；`chown` 改属主（一般要 sudo）；sudo 只在需要时用，别全程 root |
| 5 | apt 包管理 | 先 `sudo apt update` 刷新索引，再 `apt install -y`；`build-essential` 是编译很多 Python 包的前提 |
| 6 | 进程与 systemd | `htop`、`ps aux | grep`、`kill`（温和，SIGTERM）与 `kill -9`（强制，SIGKILL）；长期服务交给 `systemctl start/enable` |
| 7 | 磁盘空间 | `df -h` 看各分区剩余、`du -sh` 看目录大小；`~/.cache` 里的 pip 和 Hugging Face 缓存是头号"吃盘大户" |
| 8 | 网络与传输 | `wget` / `curl -O` 下载，`scp` 简单拷贝，`rsync` 增量同步大目录 |
| 9 | tmux 保活 | 远程训练一律放进 tmux，`Ctrl+B` 后按**小写** `d` 脱离（讲义写成了大写 `D`，大写是"选择要断开的客户端"），断开 SSH 后训练继续 |
| 10 | WSL2 与 macOS 差异 | WSL2 用 Windows 侧 NVIDIA 驱动即可用 CUDA；Linux 文件名区分大小写、`sed -i` 语法不同、`\r\n` 换行会弄坏 bash 脚本 |

### 核心技能（能动手做到）

- [ ] 读懂 `ls -l` 输出的权限串，能在权限串和 `755` / `644` / `600` 之间互相换算
- [ ] 遇到 `Permission denied` 时，能区分"缺执行权限""目录不可写""文件属于 root"三种情况并分别修复
- [ ] 在一台全新的 Ubuntu GPU 机器上，用一条 `apt` 命令装好讲义列出的基础包，并用 `nvidia-smi` 确认 GPU 可用
- [ ] 用 `df -h` + `du -h --max-depth=1` 层层定位"磁盘被谁占满"，并安全地清理 pip / HF 缓存
- [ ] 用 `ps`、`htop`、`nvidia-smi` 找到卡死的训练进程，先 `kill` 再必要时 `kill -9`
- [ ] 用 `rsync` 在本地和远程之间同步目录，并说明它相对 `scp` 的优势和局限
- [ ] 把一段在 macOS 上写的 shell 脚本改到在 Linux 上能运行（`sed -i`、换行符、大小写）

---

## 二、基础自测（选择题）

**Q1.** `ls -l` 显示 `-rwxr-xr-- 1 alice ml 2048 Mar 19 10:00 train.py`。下列说法正确的是：

- A. 所有人都可以执行 `train.py`
- B. 属主 alice 可读写执行；`ml` 组成员可读、可执行；其他人只能读；对应数字是 `754`
- C. `ml` 组成员可以修改这个文件
- D. 对应数字是 `755`

**Q2.** 你希望一个部署脚本：属主可读写执行，其他所有人可读、可执行但不能修改。应该用：

- A. `chmod 644 deploy.sh`
- B. `chmod 755 deploy.sh`
- C. `chmod 777 deploy.sh`
- D. `chmod 700 deploy.sh`

**Q3.** 关于 `sudo apt update`，正确的是：

- A. 它会把所有已安装的软件升级到最新版本
- B. 它只刷新本地的软件包索引（有哪些包、什么版本），之后的 `apt install` 才能装到正确的版本
- C. 它会更新 Linux 内核
- D. 它只在第一次开机时需要运行

**Q4.** 训练进程（PID 12345）卡住了。`kill 12345` 和 `kill -9 12345` 的区别是：

- A. 没有区别，`-9` 只是更快
- B. `kill` 默认发送 SIGTERM，程序可以捕获它并做清理（例如保存 checkpoint）后退出；`kill -9` 发送 SIGKILL，进程立即被内核终止，无法捕获、无法清理
- C. `kill -9` 会同时杀死所有 Python 进程
- D. `kill` 只是暂停进程，`kill -9` 才会结束进程

**Q5.** 你在 macOS 上写了 `sed -i '' 's/lr=0.01/lr=0.001/' config.txt`，放到 Ubuntu 服务器上运行，会怎样？

- A. 完全正常
- B. GNU sed 会把 `''` 当作脚本、把 `'s/lr=0.01/lr=0.001/'` 当作文件名，报错找不到文件（Linux 上应写 `sed -i 's/.../.../' config.txt`）
- C. Linux 上的 sed 不支持就地修改
- D. 会把 config.txt 清空

**Q6.** 项目在 Mac 上跑得好好的，部署到 Linux 后报 `ModuleNotFoundError: No module named 'Model'`，而目录里有 `model.py`。最可能的原因是：

- A. Linux 上的 Python 版本太旧
- B. macOS 默认文件系统不区分大小写，`import Model` 在 Mac 上能找到 `model.py`；Linux 区分大小写，`Model` 和 `model` 是两个不同的名字
- C. Linux 不支持大写的模块名
- D. 需要先 `chmod +x model.py`

**Q7.** 在 Windows 上用 WSL2 跑 CUDA，正确的做法是：

- A. 在 WSL2 的 Ubuntu 里安装 Linux 版 NVIDIA 显卡驱动
- B. 在 Windows 侧安装 NVIDIA 驱动，WSL2 内部即可使用 CUDA，不要在 WSL2 里再装 Linux 驱动
- C. WSL2 不支持 GPU，必须双系统
- D. 必须先在 WSL2 里编译 Linux 内核

**Q8.** 关于 `rsync` 和 `scp`，下列说法最准确的是：

- A. `rsync` 只能在局域网使用
- B. `rsync` 会比较两端的文件，只传输新增或变化的部分；中断后重新执行同一条命令，已经传完的文件会被跳过
- C. `scp` 和 `rsync` 都会自动跳过目标端已存在的相同文件
- D. `rsync` 不加任何参数就能从断点续传同一个大文件的剩余字节

---

## 三、动手 / 代码题

**Q9.**（权限排障）依次遇到下面三个报错，分别说明原因并写出修复命令：

```text
$ ./train.sh
bash: ./train.sh: Permission denied
$ ls -l train.sh
-rw-r--r-- 1 ubuntu ubuntu 512 Mar 19 10:00 train.sh
```

```text
$ ssh -i ~/.ssh/gpu_key ubuntu@203.0.113.50
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@         WARNING: UNPROTECTED PRIVATE KEY FILE!          @
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
Permissions 0644 for '/home/me/.ssh/gpu_key' are too open.
```

```text
$ python download.py          # 往 ~/models/ 写文件
PermissionError: [Errno 13] Permission denied: '/home/ubuntu/models/config.json'
$ ls -ld ~/models
drwxr-xr-x 2 root root 4096 Mar 19 09:00 /home/ubuntu/models
```

另外，讲义说"`chmod +x` 或 `sudo` 能解决大多数 Permission denied"——对第三个问题，为什么"直接 `sudo python download.py`"不是好办法？

**Q10.**（磁盘排障）训练跑到一半报错 `OSError: [Errno 28] No space left on device`，保存 checkpoint 失败。

1. 写出从"确认哪个分区满了"到"定位具体是哪个目录"的命令序列。
2. 列出 3 种讲义提到的安全清理方式，以及一种"清理之前务必确认"的操作。
3. 有时 `df -h` 显示磁盘 100%，但 `du` 加起来远小于分区大小。可能是什么原因？怎么确认？

**Q11.**（跨平台移植）同事在 macOS / Windows 上写了下面的脚本 `prep.sh`，在 Ubuntu GPU 机器上运行出错。逐行指出会在 Linux 上出问题的地方并给出修复：

```bash
#!/bin/bash
sed -i '' 's/batch_size: 64/batch_size: 128/' config.yaml
brew install jq
cat results.json | jq '.accuracy' | pbcopy
open report.html
```

已知：这个文件是同事在 Windows 记事本里最后保存的，运行时第一行就报 `/bin/bash^M: bad interpreter: No such file or directory`。

---

## 四、面试高频题

**Q12.**（基础必考）讲一讲 Linux 的文件权限模型。`r`、`w`、`x` 对**文件**和对**目录**分别意味着什么？遇到 `Permission denied` 你的排查思路是什么？为什么说"不要什么都用 sudo"？

**Q13.**（原理深挖）`nvidia-smi` 显示某张卡的显存被占了 20 GB，但你确认自己的训练早已结束。可能是什么情况？你会怎样找到并清理这些"幽灵占用"？`kill`、`kill -9` 应该怎么用？

**Q14.**（工程实践）你刚拿到一台全新的 Ubuntu 云 GPU 实例。请给出你的"开机 30 分钟初始化清单"，确保接下来几天的实验不会被环境问题打断。

**Q15.**（场景设计）你要在一台 Linux 服务器上长期运行一个模型推理服务（HTTP API），要求机器重启后自动启动、进程崩溃后自动拉起、日志可查。tmux、nohup、systemd 你会选哪个？给出关键配置。

**Q16.**（追问型）讲义说 `rsync` "只传输变化的字节，并能处理中断的连接"。这句话准确吗？在传输一个 50 GB 的 checkpoint 时，如何确保中断后能真正续传、传完后文件没有损坏？

---

## 五、参考答案与解析

### Q1 — 答案：B

权限串第 1 位是文件类型（`-` 普通文件，`d` 目录），后面每 3 位一组：属主 `rwx`=4+2+1=7，属组 `r-x`=4+1=5，其他人 `r--`=4，合起来是 `754`。A 错：其他人没有 `x`；C 错：组没有 `w`；D 错：最后一组是 4 不是 5。

### Q2 — 答案：B

`755` = 属主 `rwx`、组 `r-x`、其他人 `r-x`，正是讲义注释的"Owner: full, others: read+execute"。`644` 没有执行权限，适合配置文件；`777` 让任何人都能改，存在安全风险；`700` 让别人连读都不行。

### Q3 — 答案：B

`apt update` 只下载最新的软件包**索引**；真正升级已装软件的是 `apt upgrade`（A 描述的是它）。讲义强调"always do this first"：在一台新机器上不先 update，`apt install` 可能找不到包，或者去下载已经从镜像上删除的旧版本而失败。

### Q4 — 答案：B

`kill` 不带参数发送 SIGTERM（15），程序可以注册处理函数做收尾，例如保存 checkpoint、关闭文件、释放资源；`kill -9` 发送 SIGKILL（9），不能被捕获或忽略，进程立即结束，可能留下写了一半的文件。正确顺序是先 `kill`，等几秒仍不退出再 `kill -9`。D 描述的是 SIGSTOP / `Ctrl+Z`。

### Q5 — 答案：B

BSD sed（macOS）的 `-i` 后面必须跟一个备份文件后缀参数，所以写成 `-i ''` 表示"不备份"。GNU sed（Linux）的 `-i` 后缀是可选的、且必须紧贴着写（如 `-i.bak`），于是单独的 `''` 被当成了 sed 脚本（空脚本），后面的 `'s/.../.../'` 被当成了要处理的文件名，报 `No such file or directory`。跨平台写法：`sed -i.bak 's/.../.../' file && rm file.bak`，在两边都能工作。

### Q6 — 答案：B

macOS 默认的 APFS 格式不区分大小写，`import Model` 能匹配到 `model.py`；Linux 的文件系统区分大小写（讲义："`Model.py` and `model.py` are two different files on Linux"）。修复：统一使用与文件名完全一致的大小写。同类问题还会出现在数据文件路径（`Data/` vs `data/`）和 git 中只改了大小写的重命名上。

### Q7 — 答案：B

讲义："Install the Windows NVIDIA driver (not the Linux one), and CUDA will be available inside WSL2." Windows 侧驱动会把 GPU 能力暴露给 WSL2；在 WSL2 里再装 Linux 版显卡驱动反而会覆盖掉这层映射，导致 CUDA 不可用。WSL2 中可以按需安装 CUDA toolkit（用户态库），但不要装驱动。

### Q8 — 答案：B

rsync 会比较两端文件（默认看大小和修改时间），只传新增或变化的文件，对变化的文件还能只传差异块。所以中断后重新执行同一条命令，已经传完的文件会被跳过。但 D 不对：默认情况下，传到一半被中断的那个文件的临时文件会被删除，下次从头传；要保留半截文件以便续传，需要加 `--partial`（或 `-P`，等于 `--partial --progress`）。scp 每次都全量复制（C 错）。

### Q9 — 参考答案

**问题一：脚本没有执行权限。** 权限串 `-rw-r--r--` 中没有任何 `x`。

```bash
chmod +x train.sh      # 或 chmod 755 train.sh
./train.sh
# 也可以不加执行权限，直接交给解释器：bash train.sh
```

**问题二：私钥权限过于开放，SSH 拒绝使用。** 私钥被组和其他人可读（`0644`），OpenSSH 出于安全考虑直接拒绝使用它。

```bash
chmod 600 ~/.ssh/gpu_key     # 只有属主可读写
chmod 700 ~/.ssh             # 目录本身也应只属于自己
```

**问题三：目录属于 root，你没有写权限。** `~/models` 的属主是 `root`，权限 `drwxr-xr-x`，其他人（你）没有 `w`，无法在里面创建文件。常见成因：之前用 `sudo` 运行过某个程序，或者被 Docker 以 root 身份自动创建（第 07 节测验 Q10）。

```bash
sudo chown -R ubuntu:ubuntu ~/models     # 把目录还给自己（-R 递归）
```

**为什么不直接 `sudo python download.py`**：①用 sudo 运行时 `~` 和环境变量可能指向 root 的家目录和 root 的 Python 环境，模型可能被下载到 `/root/.cache`，或者找不到你虚拟环境里的包；②即使成功，新写入的文件依然属于 root，下一次以普通用户运行时还会遇到同样的错误，越来越多的 root 文件会散落在你的家目录里；③以 root 运行任意第三方代码，出了问题破坏范围是整台机器。正确思路是**修复属主**，而不是提升权限。

### Q10 — 参考答案

1. 定位命令序列：

```bash
df -h                                   # 哪个分区满了？看 Use% 和挂载点
df -h /home                             # 只看某个挂载点
sudo du -h --max-depth=1 -x / 2>/dev/null | sort -hr | head -20   # 根分区下哪个一级目录最大
du -sh ~/.cache/*                       # 缓存里谁最大（pip、huggingface……）
du -sh ~/project/checkpoints/*          # checkpoint 占多少
find ~ -name "*.ckpt" -size +1G         # 找出超过 1 GB 的 checkpoint
```

   讲义原命令是 `du -h --max-depth=1 / 2>/dev/null | sort -hr | head -20`。这里加了 `-x`，让 `du` 不跨越到其他文件系统（比如 `/proc`、单独挂载的数据盘），结果更准确也更快。
2. 讲义提到的清理方式：`pip cache purge` 清 pip 缓存；`sudo apt clean` 清 apt 下载的安装包缓存；删除不再需要的旧 checkpoint（如 `rm -rf checkpoints/epoch_01/ checkpoints/epoch_02/`）。**务必确认**的是 `rm -rf`：讲义强调它没有回收站、无法撤销。执行前先用 `ls` / `du -sh` 查看目标路径，确认没有通配符或变量展开错误（例如 `rm -rf $DIR/*` 中 `$DIR` 为空时就变成了 `rm -rf /*`）。
3. 最常见原因是**文件已被删除，但仍被某个进程打开**：例如你删掉了一个正在被训练进程写入的巨大日志文件，目录里已经看不到它（`du` 不再计算），但进程还持有文件句柄，磁盘空间直到进程退出才会真正释放。确认方法：`sudo lsof +L1`（列出链接数为 0、即已删除但仍被打开的文件），找到进程后重启它，或者截断文件（`: > /proc/<PID>/fd/<FD>`）。另一个可能是 **inode 耗尽**：大量小文件（例如数百万张小图片）把 inode 用光了，`df -i` 可以看到 `IUse%` 达到 100%，此时 `df -h` 不一定显示满。

### Q11 — 参考答案

| 行 | 问题 | 修复 |
|----|------|------|
| 文件整体 | 用 Windows 记事本保存后换行符变成 `\r\n`，第一行变成 `#!/bin/bash\r`，内核去找名为 `bash\r` 的解释器，于是报 `bad interpreter` | `dos2unix prep.sh`（需 `sudo apt install dos2unix`），或 `sed -i 's/\r$//' prep.sh`；在编辑器里把换行符设成 LF，git 里可以用 `.gitattributes` 统一 |
| `sed -i ''` | BSD sed 写法，GNU sed 会把 `''` 当脚本 | Linux 上写 `sed -i 's/batch_size: 64/batch_size: 128/' config.yaml`；需要两边通用就写 `sed -i.bak ... && rm config.yaml.bak` |
| `brew install jq` | Ubuntu 上一般没有 Homebrew | `sudo apt update && sudo apt install -y jq` |
| `pbcopy` | macOS 专有，SSH 远程会话里没有剪贴板 | 直接输出到终端，或者写到文件：`jq '.accuracy' results.json > accuracy.txt`，再 `scp` / `rsync` 取回本地 |
| `open report.html` | macOS 专有；Linux 桌面对应的是 `xdg-open`，但远程服务器通常没有图形界面 | 把文件拷回本地查看（`scp user@remote:~/report.html .`），或在远程起一个临时 HTTP 服务（`python3 -m http.server 8000`），再用 `ssh -L 8000:localhost:8000` 映射到本地浏览器 |

修复后：

```bash
#!/bin/bash
set -euo pipefail
sed -i 's/batch_size: 64/batch_size: 128/' config.yaml
command -v jq >/dev/null || { sudo apt update && sudo apt install -y jq; }
jq '.accuracy' results.json | tee accuracy.txt
echo "report.html 已生成，请用 scp 拷回本地查看"
```

`set -euo pipefail` 让脚本遇到错误、未定义变量或管道中任一命令失败时立即停止，避免"前一步失败、后面继续乱跑"。顺带去掉了 `cat file | jq` 这种多余的 `cat`。

### Q12 — 参考回答要点

- **三组 × 三位**：属主（user）、属组（group）、其他人（others），各有读（r=4）、写（w=2）、执行（x=1）。`chmod` 改权限、`chown` 改属主和属组。
- **对文件**：r = 读内容，w = 改内容，x = 作为程序执行。
- **对目录**（面试常考点）：r = 列出目录里有哪些文件名（`ls`）；w = 在目录里**创建、删除、重命名**文件（所以能不能删一个文件，看的是它所在**目录**的 w，而不是文件本身的 w）；x = 进入目录、访问其中的文件（`cd`、按路径打开文件）。只有 r 没有 x 的目录，能看到文件名却打不开任何文件。
- **排查思路**：①看清报错的是哪个路径；②`ls -l 文件`、`ls -ld 所在目录`，逐级检查路径上每一层目录是否有 x；③`whoami`、`id` 确认自己是谁、属于哪些组；④判断是缺权限位（`chmod`）、属主不对（`chown`）还是需要加入某个组（如 `sudo usermod -aG docker $USER` 后要重新登录才生效，第 07 节）。另外，SSH 的 `Permission denied (publickey)` 是**认证失败**，和文件权限是两回事。
- **为什么不滥用 sudo**：root 产生的文件会让普通用户后续无法写入；`sudo pip install` 可能破坏系统自带的 Python（Ubuntu 很多系统工具依赖它）；以 root 运行第三方代码，一旦出问题影响的是整台机器；`rm -rf` 之类的手误后果也会被放大。原则是**最小权限**：只对确实需要 root 的单条命令使用 sudo（讲义："Use sudo only when needed"）。
- **加分点**：知道 `umask` 决定新建文件的默认权限，知道 setuid / sticky bit（`/tmp` 的 `t` 位让用户只能删除自己的文件）。

### Q13 — 参考回答要点

- **可能情况**：
  1. 进程其实**还活着**：训练主进程退出了，但 DataLoader 的 worker 子进程或者分布式训练里的某个 rank 没退出，仍持有 CUDA 上下文；
  2. 进程被 `Ctrl+Z` **暂停**了，忘在后台——暂停的进程照样占着显存；
  3. 另一个用户或另一个容器在用这张卡（反过来，如果你是在容器**内部**运行 `nvidia-smi`，由于 PID 命名空间隔离，常常看不到进程列表，需要到宿主机上查）；
  4. 进程已成为僵尸进程，等待父进程回收。
- **定位**：
  - `nvidia-smi --query-compute-apps=pid,name,used_memory --format=csv` 列出占用显存的 PID；
  - `ps -o pid,ppid,user,stat,etime,cmd -p <PID>` 查看是谁的、运行多久了、状态（`T` 表示被暂停，`Z` 表示僵尸）；
  - `ps aux | grep python`、`htop` 的树状视图（F5）找出残留的子进程；
  - `jobs` 查看当前 shell 中被暂停的作业。
- **清理**：先 `kill <PID>`（SIGTERM）给程序清理的机会，等几秒仍在就 `kill -9 <PID>`；如果是父进程已退出的一组子进程，要逐个清理，或者向整个进程组发送信号。僵尸进程本身已经释放了资源，需要处理的是它的父进程。只能清理自己的进程，别人的进程要联系对方或管理员。
- **预防**：训练代码处理 SIGTERM 并正确关闭 DataLoader；用 tmux 管理任务，结束后检查 `nvidia-smi`；共享服务器上用 `CUDA_VISIBLE_DEVICES` 约定各自使用的卡。

### Q14 — 参考回答要点

1. **确认硬件**：`nvidia-smi`（驱动、GPU 型号、显存、是否有别的进程）；`nproc`、`free -h` 看 CPU 和内存；`df -h` 看磁盘——很多实例的大容量盘挂在 `/mnt`、`/data` 等位置，而不是根分区。
2. **系统包**：`sudo apt update && sudo apt install -y build-essential git curl wget tmux htop unzip python3-venv`（讲义清单）。
3. **缓存与数据放在大盘上**：设置 `HF_HOME`、pip 缓存目录等环境变量指向数据盘，避免模型下载把根分区塞满（讲义："GPU boxes often have limited disk space"）。
4. **Python 环境**：用 venv / uv 建项目环境，安装与驱动匹配的 PyTorch，运行 `python -c "import torch; print(torch.cuda.is_available())"` 验证。
5. **代码与凭据**：配置 git 身份，用 SSH key 或 token 拉取私有仓库；API key 放在环境变量或 `.env` 中，并确保已加入 `.gitignore`。
6. **会话保活**：所有长任务都在 tmux 里运行（讲义："Always run long training jobs inside tmux. Always."）。
7. **安全与成本**：使用普通用户 + sudo，不要一直以 root 身份工作；不要对公网开放 Jupyter 等端口，用 SSH 端口转发访问；设置预算提醒，实验结束后及时关机或释放实例。
- **加分点**：把以上步骤写成一个可重复执行的初始化脚本（或者直接用第 07 节的 Docker 镜像），下次换机器几分钟就能恢复环境。

### Q15 — 参考回答要点

- **选择 systemd**。tmux 适合交互式的开发和训练；nohup 适合临时的后台任务；但两者都**不会在机器重启后自动启动**，进程崩溃后也**不会自动拉起**。systemd 正是为长期运行的服务（daemon）设计的：开机自启（`enable`）、失败自动重启（`Restart=`）、统一的日志（`journalctl`）、依赖顺序和资源限制。讲义中 `systemctl start / stop / restart / status / enable` 这组命令就是用来管理这类服务的。
- **关键配置**（`/etc/systemd/system/llm.service`）：

```ini
[Unit]
Description=LLM inference server
After=network-online.target
Wants=network-online.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/app
Environment=HF_HOME=/data/hf
ExecStart=/home/ubuntu/app/.venv/bin/python -m server --port 8000
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload          # 让 systemd 读取新的 unit 文件
sudo systemctl enable --now llm       # 设置开机自启并立即启动
sudo systemctl status llm             # 查看状态
journalctl -u llm -f                  # 实时查看日志
```

- **要点**：`User=` 以普通用户运行，而不是 root；`ExecStart` 写虚拟环境中 Python 的**绝对路径**（systemd 不会读取你的 `~/.bashrc`，也不会激活虚拟环境）；`Restart=on-failure` 加 `RestartSec` 防止崩溃后疯狂重启；停止服务时 systemd 先发 SIGTERM，超时后才发 SIGKILL，所以服务应能优雅退出。
- **加分点**：生产环境也常用 Docker（`--restart unless-stopped`）或 Kubernetes 来做同样的事；服务前面通常再加一层 nginx 做反向代理和 TLS。

### Q16 — 参考回答要点

- **不完全准确**。rsync 的增量是**文件级跳过 + 差异块传输**：重新执行时，已经完整传完的文件会被跳过，修改过的文件只传差异部分。但默认情况下，传到一半被中断的文件（写在临时文件里）会被**删除**，下次从头开始。所以对单个 50 GB 文件，"能处理中断"需要额外参数。
- **真正续传**：使用 `rsync -avP`（`-P` = `--partial --progress`），保留半截文件；重新执行时 rsync 用已有部分作为差异传输的基础，只补传剩下的内容。`--append-verify` 也是一种选择（续写到文件末尾，并在完成后校验整个文件）。
- **校验完整性**：rsync 每次传输结束时会对传输的文件做校验，正常完成通常就可信；更稳妥的做法是两端各算一次哈希比对（`sha256sum ckpt.pt`），或者事后执行 `rsync -avc --dry-run`（`-c` 按校验和比较）确认没有差异。checkpoint 最好使用 safetensors 等能在加载时发现损坏的格式。
- **其他实践**：在 tmux 里运行传输任务，防止 SSH 断开导致传输中断；跨地域传输大文件时，考虑先上传到对象存储，再由目标机器下载。
- **常见误区**：以为 `-z`（压缩）总能加速——对已经高度压缩的数据（如 `.tar.gz`、大多数模型权重的二进制数据）压缩收益很小，反而会消耗 CPU。

---

## 六、关联知识点

### 前置知识
- [阶段 00 · 01 开发环境](../../01-dev-environment/docs/zh.md)：本地开发环境，与远程 Linux 环境做对照。
- [阶段 00 · 10 终端与 Shell](../../10-terminal-and-shell/docs/zh.md)：管道、重定向、后台任务、tmux、SSH，本节在其基础上补充 Linux 系统层面的知识。

### 本节被哪些后续内容用到
- [阶段 00 · 03 GPU 设置和云](../../03-gpu-setup-and-cloud/docs/zh.md)：租到的云 GPU 几乎都是 Ubuntu，本节是"上手第一天"的必备技能。
- [阶段 00 · 07 用于 AI 的 Docker](../../07-docker-for-ai/docs/zh.md)：`usermod -aG docker`、root 拥有的挂载目录、容器内也是 Linux。
- [阶段 00 · 12 调试与性能分析](../../12-debugging-and-profiling/docs/zh.md)：在 Linux 上定位卡死、内存泄漏、显存占用。
- [阶段 17 · 23 面向 AI 的 SRE](../../../17-infrastructure-and-production/23-sre-for-ai/docs/zh.md)：把 systemd、日志、磁盘监控上升为生产运维体系（对应 Q15）。
- [阶段 17 · 25 安全、密钥与审计](../../../17-infrastructure-and-production/25-security-secrets-audit/docs/zh.md)：最小权限、密钥文件权限（对应 Q9、Q12）。
- [阶段 19 · 06 DevOps 排障 Agent](../../../19-capstone-projects/06-devops-troubleshooting-agent/docs/zh.md)：让 Agent 用本节这些命令自动排查服务器问题。
- [阶段 19 · 26 沙箱执行器与命令黑名单](../../../19-capstone-projects/26-sandbox-runner-denylist/docs/zh.md)：`rm -rf`、`sudo` 这类命令为什么需要被拦截。

### 延伸关键词
`FHS 文件系统层级标准` · `umask` · `sticky bit / setuid` · `SIGTERM vs SIGKILL` · `systemd unit / journalctl` · `lsof +L1` · `df -i (inode)` · `rsync --partial / -c` · `dos2unix / .gitattributes` · `WSL2 CUDA`
