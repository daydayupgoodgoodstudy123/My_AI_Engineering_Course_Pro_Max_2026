# 测验 · 终端与 Shell（Terminal & Shell）

> **阶段 00 · 环境搭建与工具 · 第 10 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/shell_aliases.sh](../code/shell_aliases.sh)（Shell 脚本，本节没有 `.py` 文件，动手题围绕这个脚本和命令行操作展开）
>
> **用法**：学完讲义、`source code/shell_aliases.sh` 并按练习 3 生成过 `fake_train.log` 后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。动手题建议在一个临时目录里做，涉及 `pkill`、`rsync` 的命令先看清楚再执行。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Shell 与常用快捷键 | bash / zsh 都行；`Ctrl+R` 搜历史、`Ctrl+C` 中断、`Ctrl+Z` 挂起（不是放到后台继续跑）、`Ctrl+L` 清屏 |
| 2 | 三个标准流与重定向 | stdout（1）、stderr（2）；`>` 覆盖、`>>` 追加、`2>` 写 stderr、`2>&1` 让 stderr 跟随 stdout，**顺序有讲究** |
| 3 | 管道与文本三剑客 | `|` 把前一个命令的 stdout 接到后一个的 stdin；`grep` 过滤、`awk '{print $NF}'` 取最后一列、`sort -t= -k2 -n -r` 按字段数值倒序 |
| 4 | 实时盯日志 | `tail -f log | grep --line-buffered loss`；`tee` 一边显示一边写文件 |
| 5 | 后台运行与挂断信号 | `&` 只是放后台，关终端会被 SIGHUP 带走；`nohup` 忽略挂断但无法重新接入；tmux / screen 既能存活又能重连 |
| 6 | tmux | 会话（session）→ 窗口 → 窗格（pane）；`Ctrl+B "` 上下分、`Ctrl+B %` 左右分、`Ctrl+B d` 脱离、`tmux attach -t 名字` 回来 |
| 7 | 资源监控 | `htop` 看 CPU/内存进程、`nvtop` / `watch -n1 nvidia-smi` 看 GPU、`nvidia-smi --query-compute-apps=pid,name,used_memory --format=csv` 查谁占显存 |
| 8 | SSH 三件套 | `ssh -i` 指定密钥、`scp` 拷文件、`rsync -avz` 增量同步目录、`ssh -L 8888:localhost:8888` 把远程端口映射到本地 |
| 9 | alias 与函数 | 固定命令用 alias，要参数（`$1`、默认值 `${1:-loss}`）用函数；要 `source` 进当前 shell 才生效 |
| 10 | 磁盘与文件查找 | `df -h` 看磁盘、`du -sh` 看目录、`find ... | xargs du -h | sort -rh | head` 找大文件 |

### 核心技能（能动手做到）

- [ ] 用一条管道从训练日志里提取所有 loss 值、统计行数、找出 loss 最小的 epoch
- [ ] 正确写出"stdout 和 stderr 分开存""合并存""一边看一边存"三种重定向，并解释 `2>&1 > f` 和 `> f 2>&1` 的区别
- [ ] 用 `nohup ... &` 后台启动任务，再用 `jobs`、`pgrep -f`、`kill` 找到并停止它
- [ ] 创建名为 `training` 的 tmux 会话，分出三个窗格分别跑脚本、`watch -n1 nvidia-smi`、`tail -f` 日志，脱离后重新接入
- [ ] 用 `ssh -L` 在本地浏览器打开远程 Jupyter / TensorBoard，用 `rsync` 正确同步目录（理解源路径尾部斜杠）
- [ ] `source shell_aliases.sh` 后能用 `gpu`、`taillog`、`trainenv`、`newexp`，并能指出脚本中至少两处可移植性或边界问题

---

## 二、基础自测（选择题）

**Q1.** 想把 `train.py` 的正常输出**和**报错都写进 `out.log`，下面哪条命令能做到？

- A. `python train.py 2>&1 > out.log`
- B. `python train.py > out.log 2>&1`
- C. `python train.py 2> out.log`
- D. `python train.py | out.log`

**Q2.** 对命令 `tail -f train.log | grep loss | awk '{print $NF}'`，如果 `grep` **不加** `--line-buffered`，最可能出现的现象是：

- A. `grep` 会漏掉部分匹配行
- B. `awk` 收到的数据被攒成大块，屏幕上的 loss 要隔很久才成批出现
- C. `tail -f` 会提前退出
- D. 完全没有区别

**Q3.** 训练正在前台运行，你按了 `Ctrl+Z`。此时训练进程的状态是：

- A. 已被杀死，需要重新启动
- B. 在后台继续运行，和 `&` 效果一样
- C. 被暂停（stopped），直到你用 `fg` 或 `bg` 让它继续
- D. 已经和终端脱离，关闭终端也不受影响

**Q4.** 下列哪种方式既能在你关闭终端 / SSH 断开后继续运行，又能事后**重新接入**看到实时输出？

- A. `python train.py &`
- B. `nohup python train.py > train.log 2>&1 &`
- C. 在 tmux 会话里运行 `python train.py`，然后 `Ctrl+B d` 脱离
- D. 在 VS Code 集成终端里直接运行

**Q5.** 执行 `ssh -L 8888:localhost:8888 user@gpu-box-ip` 后，本地浏览器访问 `localhost:8888` 实际连到的是：

- A. 本地机器上的 8888 端口服务
- B. 通过 SSH 隧道，连到 gpu-box **自己的** 8888 端口（命令中的 `localhost` 是从远程机器的角度解析的）
- C. gpu-box 的 22 端口
- D. 任意一台局域网机器的 8888 端口

**Q6.** 本地有 `./data/a.csv`，下面两条命令执行后，远程分别得到什么路径？

```bash
rsync -avz ./data/ user@gpu:~/data/   # 命令 1
rsync -avz ./data  user@gpu:~/data/   # 命令 2
```

- A. 两者都得到 `~/data/a.csv`
- B. 命令 1 得到 `~/data/a.csv`；命令 2 得到 `~/data/data/a.csv`
- C. 命令 1 得到 `~/data/data/a.csv`；命令 2 得到 `~/data/a.csv`
- D. 命令 2 会报错

**Q7.** `shell_aliases.sh` 里，`killtraining` 写成了 alias，而 `killtrain`、`taillog`、`syncto` 写成了函数。主要原因是：

- A. 函数执行得更快
- B. alias 不能在命令中间使用位置参数（`$1`）和默认值，需要参数时用函数
- C. alias 只能在 bash 中用，函数只能在 zsh 中用
- D. 函数会自动写入 `~/.bashrc`

**Q8.** 你执行了 `bash code/shell_aliases.sh`，然后输入 `gpu`，提示 `command not found`。原因是：

- A. 脚本有语法错误
- B. `bash 脚本` 在一个**子进程**里执行，alias 和函数定义在子进程退出时就消失了；应该用 `source`（或 `.`）在当前 shell 中加载
- C. 必须先重启电脑
- D. alias 只在 zsh 中有效

---

## 三、动手 / 代码题

**Q9.** `shell_aliases.sh` 中的 `memhogs` 想做到"Linux 上用 GNU ps 的 `--sort`，macOS 上不支持就退回 `ps aux -m`"：

```bash
memhogs() {
    ps aux --sort=-%mem 2>/dev/null | head -11 || ps aux -m | head -11
}
```

1. 在 macOS 上运行它，会看到什么？`||` 后面的备用命令会执行吗？为什么？
2. 改写这个函数，让回退逻辑真正生效。

**Q10.** `syncto` 函数和它自带的用法示例：

```bash
syncto() {
    # ...参数检查省略...
    local host="$1"
    local remote="$2"
    local local_path="${3:-.}"
    rsync -avz --progress "$local_path" "${host}:${remote}"
}
# Example: syncto gpu ~/data ./data
```

假设本地是 macOS，用户名 `alice`（家目录 `/Users/alice`），远程 `gpu` 是 Ubuntu，用户 `ubuntu`。

1. 输入 `syncto gpu ~/data ./data` 后，实际执行的 `rsync` 命令是什么？数据最终会落到远程的哪个路径？
2. 怎样调用（或修改函数）才能把本地 `./data` 目录的**内容**同步到远程的 `/home/ubuntu/data/`？

**Q11.** `trainenv` 函数一键搭建训练用的 tmux 布局：

```bash
trainenv() {
    local name="${1:-train}"
    tmux new-session -d -s "$name"
    tmux split-window -h -t "$name"
    tmux split-window -v -t "$name"
    tmux send-keys -t "$name:0.1" 'watch -n1 nvidia-smi' C-m
    tmux send-keys -t "$name:0.2" 'htop' C-m
    tmux select-pane -t "$name:0.0"
    tmux attach -t "$name"
}
```

1. 画出运行 `trainenv` 后的窗格布局，标出 0、1、2 号窗格各在哪里、跑着什么。
2. 同一个名字连续运行两次 `trainenv train` 会发生什么？
3. 如果用户的 `~/.tmux.conf` 里写了 `set -g base-index 1`（很多人这么配），这个函数哪里会出问题？
4. 给函数加上"会话已存在就直接接入"的保护。

**Q12.** 用讲义练习 3 生成日志（去掉 `sleep` 可以立刻生成）：

```bash
for i in $(seq 1 100); do echo "epoch $i loss: $(echo "scale=4; 1/$i" | bc)"; done > fake_train.log
```

1. 文件前三行长什么样？（注意 `bc` 的输出格式）
2. 分别写出命令：①只输出所有 loss 值；②统计包含 loss 的行数；③找出 loss 最小的那一行的 epoch 和 loss。
3. 在一个**没有任何模型文件**的目录里运行 `bigmodels`（`find ... | xargs du -h 2>/dev/null | sort -rh | head -20`），在 Linux 上会输出什么？为什么？

---

## 四、面试高频题

**Q13.**（基础必考）解释 stdin / stdout / stderr 和文件描述符。`cmd > f 2>&1`、`cmd 2>&1 > f`、`cmd &> f`、`cmd 2>&1 | tee f` 分别是什么效果？为什么训练脚本的日志要特别注意 stderr？

**Q14.**（原理深挖）SSH 断开后，远程机器上你启动的训练进程为什么会死？`nohup`、`tmux` 分别是怎样让进程活下来的？两者有什么本质区别？

**Q15.**（工程实践）你租了一台云 GPU，需要在上面连续训练两天。请描述你从本地到远程的完整终端工作流：连接、代码同步、启动、监控、取回结果，以及如何避免"断线丢进度"。

**Q16.**（场景设计 / 排障）共享 GPU 服务器上，你的训练突然比昨天慢了一倍，偶尔还报 CUDA OOM。只用终端工具，你会按什么顺序排查？

**Q17.**（追问型）`alias killtraining='pkill -f "python.*train"'` 有什么风险？生产或共享环境里应该怎样"优雅地"停止一个训练任务？

---

## 五、参考答案与解析

### Q1 — 答案：B

重定向**从左到右**依次生效：B 先把 stdout（fd 1）指向 `out.log`，再让 stderr（fd 2）复制"fd 1 此刻指向的地方"，于是两者都进文件。A 的顺序反了：`2>&1` 执行时 fd 1 还指向终端，所以 stderr 去了终端，之后 stdout 才改指向文件——报错仍然打在屏幕上。C 只存 stderr；D 语法错误（管道后面要接命令，不是文件名）。

### Q2 — 答案：B

C 标准库的惯例：输出到**终端**时按行缓冲，输出到**管道或文件**时按块缓冲（通常几 KB）。`grep` 的输出接给了 `awk`，不是终端，于是匹配行在 grep 的缓冲区里攒满一块才一起送出，看起来就像"日志卡住了"。`--line-buffered` 强制 grep 每行立即输出。数据不会丢（A 错）。注意：如果 `grep` 是管道最后一个命令、直接输出到终端，那时它本来就是行缓冲的；在中间环节时这个参数才是关键。

### Q3 — 答案：C

`Ctrl+Z` 发送 SIGTSTP，进程被**暂停**，不再占用 CPU / GPU 计算（但显存、内存仍然占着）。讲义写的是"Suspend a running command (resume with fg)"：`fg` 让它回到前台继续，`bg` 让它在后台继续。很多人误以为 `Ctrl+Z` 等于"放到后台跑"（B），结果训练一晚上原地不动。

### Q4 — 答案：C

对照讲义的表格：`&` 关终端就会被挂断信号带走；`nohup` 能活下来，但只能看日志文件，**不能重新接入**；tmux / screen 两者都满足。D：VS Code 集成终端里的进程依附于那次远程连接，断线后不可靠（第 08 节测验 Q15 讨论过）。

### Q5 — 答案：B

`-L 本地端口:目标主机:目标端口` 的意思是"在本地监听 `本地端口`，收到的连接经 SSH 隧道转发到**远程服务器所能访问的** `目标主机:目标端口`"。这里的 `localhost` 是在 gpu-box 上解析的，所以就是 gpu-box 自己的 8888（远程 Jupyter）。好处是远程服务只需监听自己的回环地址，不必对公网开放端口。

### Q6 — 答案：B

rsync 的规则：源路径**带尾部斜杠**表示"复制目录里的内容"，**不带**表示"复制这个目录本身"。所以命令 2 会在 `~/data/` 下再建一个 `data/`，得到 `~/data/data/a.csv`。这是 rsync 最常见的坑之一；讲义 Step 6 的写法 `./data/` → `~/data/` 是正确的。

### Q7 — 答案：B

alias 只是简单的文本替换：输入 `killtraining` 时替换成固定的命令。它无法在命令中间插入参数，也不能写 `${1:-loss}` 这种默认值或 `if` 判断。需要参数、分支、局部变量（`local`）的场景都要用函数。两者在 bash 和 zsh 中都可用（C 错）。

### Q8 — 答案：B

`bash script.sh` 会启动一个新的 bash 进程来执行脚本，脚本里定义的 alias、函数、`cd`、`export` 都只作用于那个子进程，子进程退出就全部消失。`source script.sh`（或 `. script.sh`）是在**当前 shell** 中逐行执行，定义才会留下来。这也是讲义让你把 `source .../shell_aliases.sh` 写进 `~/.bashrc` / `~/.zshrc` 的原因；同理，激活虚拟环境也必须用 `source .venv/bin/activate`。

### Q9 — 参考答案

1. 在 macOS 上**什么都不输出**，备用命令也**不会执行**。BSD 版 `ps` 不认识 `--sort`，报错（错误信息被 `2>/dev/null` 吞掉）后没有任何输出；但 `||` 判断的是**整条管道**的退出状态，而在默认设置下，管道的退出状态等于**最后一个命令**（`head -11`）的退出状态。`head` 读到空输入、正常结束，返回 0，于是 `||` 认为"成功了"，不会走备用分支。可以用 `false 2>/dev/null | head -11 || echo FALLBACK; echo $?` 验证：不会打印 `FALLBACK`，`$?` 为 0。
2. 先探测、再选择：

```bash
memhogs() {
    if ps aux --sort=-%mem >/dev/null 2>&1; then
        ps aux --sort=-%mem | head -11          # GNU ps（Linux）
    else
        ps aux -m | head -11                    # BSD ps（macOS），-m 按内存排序
    fi
}
```

   另一种思路是在子 shell 里打开 `pipefail`：`(set -o pipefail; ps aux --sort=-%mem 2>/dev/null | head -11) || ps aux -m | head -11`。`pipefail` 让管道中任一命令失败都使整条管道失败。用子 shell 是为了不影响当前交互 shell 的设置。

### Q10 — 参考答案

1. `~/data` 没有加引号，并且位于单词开头，所以**本地 shell 在调用函数之前**就把它展开成了 `/Users/alice/data`。实际执行的是：

```bash
rsync -avz --progress ./data gpu:/Users/alice/data
```

   远程是 Ubuntu，没有 `/Users/alice`，`rsync` 会因为父目录不存在、无法创建目标目录而报错；就算远程恰好有这个路径（比如两边用户名、家目录相同），源路径 `./data` 不带尾部斜杠，也会得到 `/Users/alice/data/data/...`，多套一层。两个坑叠在一起。
2. 正确调用方式（任选其一）：

```bash
syncto gpu '~/data/' ./data/     # 加引号阻止本地展开，交给远端 shell 展开 ~
syncto gpu data/ ./data/         # rsync 的远程相对路径默认相对于远程家目录
syncto gpu /home/ubuntu/data/ ./data/   # 直接写远程绝对路径
```

   三种写法的源路径都带尾部斜杠，目标都是 `/home/ubuntu/data/`。也可以修改函数本身：在函数里检测 `remote` 是否以本地 `$HOME` 开头并给出警告，或在用法说明里把示例改成 `syncto gpu data/ ./data/`。

### Q11 — 参考答案

1. 布局（在 80×24 的终端里实测得到相同结构）：

```
+------------------+-----------------------+
|                  | 1: watch -n1          |
|  0: 空的 shell    |    nvidia-smi         |
|  （光标在这里，     +-----------------------+
|   用来跑训练）     | 2: htop               |
|                  |                       |
+------------------+-----------------------+
```

   `split-window -h` 把 0 号窗格左右分开，新窗格 1 在右边并成为活动窗格；`split-window -v` 不指定窗格，就切分当前活动窗格（右边的 1），新窗格 2 在它下方。最后 `select-pane` 把光标放回左边的 0 号窗格。
2. 第二次运行时，`tmux new-session` 报 `duplicate session: train` 并失败，但函数没有检查返回值，**继续执行**：在已有会话上再切出两个窗格（变成 5 个），并把 `watch` 和 `htop` 发送到此时编号为 1、2 的窗格——这两个编号已经指向新切出来的窗格，于是又多开了一份监控，布局被打乱。
3. `send-keys -t "$name:0.1"` 中的 `0` 是**窗口编号**。设置 `base-index 1` 后第一个窗口编号是 1，不存在窗口 0，`send-keys` 和 `select-pane` 都会报 `can't find window: 0`（已实测）。类似地，`pane-base-index 1` 会让窗格编号从 1 开始，`0.2` 也不对了。更稳妥的写法是不写死编号，例如用位置记号 `-t "$name:.{top-right}"`、`-t "$name:.{bottom-right}"`（表示该会话当前窗口中右上、右下的窗格），或者在创建窗格时用 `split-window -P -F '#{pane_id}'` 拿到窗格 ID（形如 `%3`），再用 ID 作为目标。
4. 加一个存在性检查：

```bash
trainenv() {
    local name="${1:-train}"
    if tmux has-session -t "$name" 2>/dev/null; then
        echo "Session '$name' already exists, attaching..."
        tmux attach -t "$name"
        return
    fi
    tmux new-session -d -s "$name" || return 1
    # ...其余不变...
}
```

### Q12 — 参考答案

1. 前三行：

```
epoch 1 loss: 1.0000
epoch 2 loss: .5000
epoch 3 loss: .3333
```

   注意 `bc` 对小于 1 的数**不输出前导 0**（`.5000`）。`sort -n`、`awk` 的数值运算和 Python 的 `float(".5")` 都能正确处理，但如果你用正则 `[0-9]+\.[0-9]+` 去匹配，就会漏掉它们。
2. 三个命令（均已实际运行验证）：

```bash
# ① 只输出 loss 值
grep "loss:" fake_train.log | awk '{print $NF}'

# ② 统计包含 loss 的行数（比 cat | grep | wc -l 更简洁）
grep -c "loss" fake_train.log                  # 输出 100

# ③ loss 最小的 epoch：按第 4 列数值升序排序取第一行
sort -k4 -n fake_train.log | head -1           # 输出 epoch 100 loss: .0100
# 或者用 awk 一次扫描完成，不需要排序
awk '/loss:/ { if (min == "" || $NF+0 < min) { min = $NF+0; ep = $2 } } END { print "best epoch", ep, "loss", min }' fake_train.log
# 输出 best epoch 100 loss 0.01
```

   `$NF` 是"最后一个字段"，`$NF+0` 强制转换成数值，避免按字符串比较。
3. 在 Linux（GNU `xargs`）上，`find` 什么都没找到时，`xargs` 默认**仍会执行一次** `du -h`，而且不带任何参数——等于对当前目录执行 `du -h`，于是打印出当前目录下**所有子目录**的大小，看起来像"找到了很多大模型"。实测：一个只有 `sub/a.txt` 的目录里，`find . -name "*.pt" | xargs du -h` 输出了 `./sub` 和 `.` 两行。修复：GNU 下用 `xargs -r`（输入为空时不执行），或者改用 `find ... -exec du -h {} +`。另外 `xargs` 默认按空白切分参数，文件名带空格会出错，稳妥写法是 `find ... -print0 | xargs -0 du -h`。

### Q13 — 参考回答要点

- **定义**：每个进程启动时默认打开三个文件描述符：0 = stdin，1 = stdout，2 = stderr。重定向就是在执行命令前修改这些描述符指向哪里。
- **四种写法**：
  - `cmd > f 2>&1`：stdout 进 f，stderr 复制 stdout 的指向，也进 f；
  - `cmd 2>&1 > f`：stderr 指向原来的 stdout（终端），stdout 再改指向 f——报错仍在屏幕上；
  - `cmd &> f`：bash / zsh 的简写，等价于第一种（不是 POSIX 标准写法，`sh` 里不可用）；
  - `cmd 2>&1 | tee f`：两者合并后经管道交给 `tee`，屏幕和文件各一份（讲义 Step 8 的写法）。
- **为什么训练要注意 stderr**：Python 的异常堆栈、警告（`warnings`）、`logging` 模块默认的输出、tqdm 进度条都写到 **stderr**。只写 `> train.log` 的话，程序崩溃时日志里看不到任何报错，只剩一个莫名其妙停止的 loss 曲线。
- **加分点**：提到 `/dev/null` 丢弃输出；Python 输出到文件时的块缓冲问题，可以用 `python -u` 或 `PYTHONUNBUFFERED=1` 让日志实时可见（第 07 节 Dockerfile 正是这样设置的）。

### Q14 — 参考回答要点

- **为什么会死**：SSH 登录时会分配一个伪终端（pty），你的 shell 是这个会话的首进程，训练进程是它的子进程。连接断开时伪终端被关闭，内核向会话发送 **SIGHUP**（挂断信号），shell 收到后通常还会把 SIGHUP 转发给它的作业；进程对 SIGHUP 的默认处理是退出。另外，进程如果还在向已关闭的终端写输出，也可能因写入错误而退出。
- **nohup**：让进程**忽略 SIGHUP**，并且在 stdout 是终端时把输出重定向到 `nohup.out`。进程本身还是那个子进程，只是不怕挂断。缺点是没有办法再"接入"它的终端，只能看日志文件（讲义表格："Can reattach? No (check log file)"）。
- **tmux**：tmux 是客户端 / 服务端架构。第一次运行时会启动一个**后台常驻的 tmux 服务端进程**，它不依赖你的 SSH 终端；每个窗格都是服务端持有的一个伪终端，你的训练进程跑在这个伪终端里。SSH 断开只是让 tmux **客户端**退出，服务端和其中的进程不受影响；重新登录后 `tmux attach` 就能接回原来的屏幕，包括滚动历史。
- **本质区别**：nohup 是"让进程对挂断免疫"，tmux 是"让进程根本不挂在 SSH 的终端上"。
- **加分点**：知道 `setsid`、`disown`；更正式的长期任务交给 `systemd` 服务或作业调度系统（Slurm、Kubernetes Job）；并且强调**无论用哪种方式，训练代码都要定期保存 checkpoint**——机器重启、被抢占时 tmux 也救不了。

### Q15 — 参考回答要点

1. **连接**：本地 `ssh-keygen` 生成密钥，`~/.ssh/config` 里写 `Host gpu`（HostName / User / IdentityFile），之后只需 `ssh gpu`。
2. **代码同步**：用 git 推拉代码，或 `rsync -avz --exclude .venv --exclude data ./ gpu:~/project/`；大数据集直接在远程下载，不要从本地上传。
3. **启动**：`ssh gpu` → `tmux new -s train`（或 `trainenv`）→ 激活环境 → `python train.py 2>&1 | tee logs/train.log`；`Ctrl+B d` 脱离后再断开 SSH。
4. **监控**：另一个窗格里 `watch -n1 nvidia-smi` / `nvtop`；`tail -f logs/*.log | grep --line-buffered loss`；用 `ssh -L 6006:localhost:6006 gpu` 在本地浏览器看 TensorBoard。
5. **取回结果**：`rsync -avz gpu:~/project/checkpoints/ ./checkpoints/`，rsync 增量传输，断了可以重新执行续传（大文件可加 `--partial`）。
6. **防丢进度**：tmux 保活 + 训练脚本定期保存 checkpoint 并支持恢复 + 日志写文件 + 磁盘空间监控（`df -h`，checkpoint 写满磁盘是常见的崩溃原因）+ 完成后通知（讲义 Step 8 的 `mail`，或用 webhook）。
- **加分点**：按 GPU 计费的机器要在训练结束后及时关机；关键 checkpoint 同步到对象存储，避免实例被回收导致数据丢失。

### Q16 — 参考回答要点

1. `nvidia-smi`：看 GPU 利用率和显存。利用率低说明 GPU 在等数据（瓶颈在 CPU / IO）；显存被占满则看下一步。
2. `nvidia-smi --query-compute-apps=pid,name,used_memory --format=csv`：看**是不是别人的进程**也在用这张卡——共享服务器上最常见的原因是有人把任务跑到了你的卡上，导致抢算力和 OOM。可以用 `CUDA_VISIBLE_DEVICES` 指定空闲的卡。
3. `ps aux | grep python` 或 `ps -o pid,user,etime,cmd -p <PID>`：确认这些 PID 属于谁、跑了多久；是不是自己之前残留的僵死训练进程（`Ctrl+Z` 暂停后忘掉的进程同样占着显存）。
4. `htop`：CPU 是否被其他任务占满（数据加载 worker 抢不到 CPU），内存是否吃紧、开始使用 swap。
5. `df -h`、`du -sh`：磁盘是否接近写满（日志或 checkpoint 写不进去会导致各种异常）。
6. `env | grep -i cuda`：环境变量是否被改过（比如 `CUDA_VISIBLE_DEVICES` 指到了别的卡）。
- **思路**：先区分"资源被别人占用"和"自己的程序变了"，再看是 GPU、CPU、内存还是磁盘的瓶颈。
- **加分点**：用 `watch -n1 nvidia-smi` 观察显存随时间的变化，判断是一开始就不够，还是在逐步增长（可能存在显存泄漏）；第 12 节会介绍用 profiler 定位代码级瓶颈。

### Q17 — 参考回答要点

- **风险**：
  1. `-f` 匹配**完整命令行**，正则 `python.*train` 会误杀所有沾边的进程：别人或自己的其他实验、`python -m tensorboard --logdir train_runs`、名字里带 train 的 Jupyter kernel 等；
  2. 默认发送 SIGTERM 后**不确认结果**，`killtrain` 还会无条件打印 "Killed ..."，哪怕什么都没匹配到；
  3. 如果以 root 身份运行，会波及其他用户的进程。
- **更安全的做法**：
  1. 启动时记录 PID：`nohup python train.py > train.log 2>&1 & echo $! > train.pid`，停止时 `kill "$(cat train.pid)"`；
  2. 先用 `pgrep -af "<更精确的模式>"` **预览**会匹配到哪些进程，确认后再执行 `pkill`；用 `-u "$USER"` 限定只匹配自己的进程；
  3. 先发 SIGTERM（`kill` 默认），等待程序清理退出，超时仍未退出再用 `kill -9`（SIGKILL 无法被捕获，进程没有机会保存任何东西）。
- **优雅停止**：训练代码中注册 SIGTERM 处理函数，收到信号后设置标志位，在当前 step 结束时保存 checkpoint 并正常退出。Kubernetes、Slurm 等调度系统在抢占或停止任务时也是先发 SIGTERM，留出一段宽限时间。
- **加分点**：tmux 里的任务可以直接切到对应窗格按 `Ctrl+C`（发送 SIGINT，Python 中表现为 `KeyboardInterrupt`，可以用 `try/finally` 保存状态）。

---

## 六、关联知识点

### 前置知识
- [阶段 00 · 01 开发环境](../../01-dev-environment/docs/zh.md)：能打开终端、知道自己用的是 bash 还是 zsh。
- [阶段 00 · 08 编辑器设置](../../08-editor-setup/docs/zh.md)：VS Code 集成终端、Remote SSH 与 `~/.ssh/config`。

### 本节被哪些后续内容用到
- [阶段 00 · 03 GPU 设置和云](../../03-gpu-setup-and-cloud/docs/zh.md)：租用云 GPU 后，SSH + tmux + rsync 就是日常操作。
- [阶段 00 · 07 用于 AI 的 Docker](../../07-docker-for-ai/docs/zh.md)：`docker logs -f`、`docker exec` 同样依赖管道与重定向。
- [阶段 00 · 11 面向人工智能的 Linux](../../11-linux-for-ai/docs/zh.md)：进程、信号、权限、systemd 等更底层的 Linux 知识（对应 Q14、Q17）。
- [阶段 00 · 12 调试与性能分析](../../12-debugging-and-profiling/docs/zh.md)：在终端里定位训练变慢的代码级原因（对应 Q16）。
- [阶段 19 · 47 检查点保存与恢复](../../../19-capstone-projects/47-checkpoint-save-resume/docs/zh.md)：tmux 之外真正防止丢进度的手段。
- [阶段 19 · 01 终端原生编码 Agent](../../../19-capstone-projects/01-terminal-native-coding-agent/docs/zh.md)：让 Agent 在终端里执行命令，管道、退出码、stderr 都是它要处理的信号。
- [阶段 19 · 26 沙箱执行器与命令黑名单](../../../19-capstone-projects/26-sandbox-runner-denylist/docs/zh.md)：像 `pkill -f`、`rm -rf` 这类危险命令为什么要被限制（对应 Q17）。

### 延伸关键词
`文件描述符 / dup2` · `SIGHUP / SIGTERM / SIGKILL / SIGTSTP` · `pipefail` · `tmux base-index / pane_id` · `rsync --partial / --exclude` · `ssh ProxyJump / LocalForward` · `xargs -r / -0` · `process substitution <( )` · `CUDA_VISIBLE_DEVICES`
