# 测验 · 用于 AI 的 Docker（Docker for AI）

> **阶段 00 · 环境搭建与工具 · 第 07 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/Dockerfile](../code/Dockerfile)、[code/docker-compose.yml](../code/docker-compose.yml)（本节没有 `.py` 文件，动手题围绕这两个配置文件和 docker 命令展开）
>
> **用法**：学完讲义、至少成功 `docker build` 一次并用 `docker compose up -d` 起过 ai-dev + qdrant 后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。没有 NVIDIA GPU 也能做大部分题，去掉 `--gpus all` 和 compose 里的 `deploy` 块即可。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 容器 ≠ 虚拟机 | 容器是共享宿主内核的隔离进程，有自己的文件系统和网络，所以秒级启动；VM 要跑一整套客户机 OS |
| 2 | Image / Container / Dockerfile / Volume / Compose | Dockerfile 是"菜谱"，Image 是只读模板，Container 是镜像跑起来的实例，Volume 是活得比容器久的存储，Compose 用 YAML 编排多容器 |
| 3 | 镜像分层与构建缓存 | 每条指令产生一层；某层变了，它**之后**的所有层都要重建，所以"变化少的放前面、变化多的放后面" |
| 4 | GPU 进容器的分工 | CUDA toolkit/runtime 装在镜像里，GPU **驱动**留在宿主机，由 NVIDIA Container Toolkit 在运行时通过 `--gpus` 暴露给容器 |
| 5 | 基础镜像选择 | `devel` 带 nvcc（编译 flash-attn 等用，约 4 GB）；`runtime` 只有运行时（约 1.5 GB）；`pytorch/pytorch` 预装 PyTorch；`python:3.12-slim` 纯 CPU、约 150 MB |
| 6 | 挂载模型、数据、代码 | 14 GB 的 7B fp16 权重放宿主机，用 `-v ~/models:/models` 挂进去，重建容器不必重新下载 |
| 7 | Docker Compose 与服务发现 | Compose 自动建一张共享网络，服务之间用**服务名**当主机名互访（`http://qdrant:6333`） |
| 8 | 三类 AI 容器 | 开发容器（全家桶 + Jupyter）、训练容器（精简，只放训练脚本和依赖）、推理容器（镜像小、冷启动快） |
| 9 | Apple Silicon 的特殊处理 | `FROM --platform=linux/amd64`：cu124 的 torch wheel 只有 x86_64 版本，Mac 上走模拟运行、没有 GPU |

### 核心技能（能动手做到）

- [ ] 用 `docker build -t ai-dev -f phases/00-setup-and-tooling/07-docker-for-ai/code/Dockerfile .` 构建镜像，并在容器里打印出 `PyTorch 2.6.0+cu124, CUDA: True/False`
- [ ] （Linux + NVIDIA）装好 NVIDIA Container Toolkit，用 `docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi` 看到显卡信息
- [ ] 用 `-v` 同时挂载代码、模型、数据三个目录，删掉容器后能说清哪些数据还在、哪些没了
- [ ] 用 `docker compose up -d` 起 ai-dev + qdrant，在 ai-dev 容器里访问 `http://qdrant:6333/collections` 成功
- [ ] 逐行解释本节 Dockerfile 每条指令的作用，并能说出为什么 torch 单独一层、为什么 `rm -rf /var/lib/apt/lists/*` 要和 `apt-get install` 写在同一个 `RUN` 里
- [ ] 把基础镜像从 `devel` 换成 `runtime`，用 `docker images` 对比体积，并说明什么情况下不能换
- [ ] 能排查三类常见故障：Mac 上 `No matching distribution found for torch==2.6.0+cu124`、`--gpus` 不可用、宿主浏览器打不开容器里的服务

---

## 二、基础自测（选择题）

**Q1.** 关于容器和虚拟机的区别，下列说法正确的是：

- A. 容器内运行着一个完整的客户机内核，所以比 VM 更安全
- B. 容器共享宿主机内核，本质是被隔离的进程，因此启动以秒计
- C. 容器只是一个压缩包，运行时没有独立的文件系统和网络
- D. 容器和 VM 只是叫法不同，资源开销基本一样

**Q2.** 本节 Dockerfile 已经成功构建过一次。现在你只在**最后一个** `pip install`（numpy、pandas……那一行）里加了一个 `flask`，再次 `docker build`。会发生什么？

- A. 从 `FROM` 开始全部重建，因为 Dockerfile 文件变了
- B. 只有安装 torch 的那一层重建
- C. 加 flask 的那条 `RUN` 及其之后的指令重新执行，前面（包括 torch 那一层）全部命中缓存
- D. 什么都不会重建，Docker 只对比镜像名

**Q3.** 关于"在容器里用 GPU"，下列哪项描述是对的？

- A. 镜像里必须装好 NVIDIA 显卡驱动，宿主机可以不装驱动
- B. CUDA toolkit 放在镜像里，GPU 驱动由宿主机提供，NVIDIA Container Toolkit 在运行时把 GPU 暴露给容器
- C. 只要镜像基于 `nvidia/cuda`，不加 `--gpus` 参数容器也能自动看到 GPU
- D. NVIDIA Container Toolkit 的作用是在 `docker build` 时编译 CUDA 代码

**Q4.** 你的项目需要从源码编译 flash-attn（需要 `nvcc`）。最合适的基础镜像是：

- A. `python:3.12-slim`
- B. `nvidia/cuda:12.4.1-runtime-ubuntu22.04`
- C. `nvidia/cuda:12.4.1-devel-ubuntu22.04`
- D. `nvidia/cuda:12.4.1-base-ubuntu22.04`

**Q5.** 用本节的 `docker-compose.yml` 起服务后，在 `ai-dev` 容器里的 Python 代码应该怎样连接 Qdrant？

- A. `QdrantClient(host="localhost", port=6333)`
- B. `QdrantClient(host="qdrant", port=6333)`
- C. 必须先查宿主机局域网 IP，再用该 IP 连接
- D. 必须让两个容器挂载同一个 volume 才能通信

**Q6.** 执行 `docker compose down -v` 后，下面哪种说法正确？

- A. 容器、网络被删除；命名卷 `qdrant_data` 也被删除；宿主机上的 `~/models` 目录不受影响
- B. 容器被删除，但 `qdrant_data` 保留；`~/models` 也被清空
- C. 只停止容器，不删除任何东西
- D. 会删除 `ai-dev` 镜像本身，下次 `up` 必须重新构建

**Q7.** 在 M 系列 Mac 上，Dockerfile 第一行写 `FROM --platform=linux/amd64 ...` 的主要原因是：

- A. `nvidia/cuda` 镜像没有 arm64 版本
- B. PyTorch 的 `cu124` wheel 只发布了 x86_64 版本，不固定平台的话 `pip install torch==2.6.0+cu124` 会找不到包
- C. 固定 amd64 后 Mac 的 GPU 就能通过 CUDA 被容器使用
- D. amd64 模拟比原生 arm64 运行得更快

**Q8.** Dockerfile 中 `ENV PYTHONUNBUFFERED=1` 的主要作用是：

- A. 关闭 Python 的垃圾回收，加速训练
- B. 让 `print` 等输出不经过缓冲、立刻出现在 `docker logs` 里
- C. 禁止 pip 使用缓存目录
- D. 让 Python 以无交互模式安装系统包

---

## 三、动手 / 代码题

**Q9.** 阅读 Dockerfile 的这两段，回答问题：

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    software-properties-common \
    git \
    curl \
    build-essential \
    && add-apt-repository -y ppa:deadsnakes/ppa \
    && apt-get update && apt-get install -y --no-install-recommends \
    python3.12 \
    python3.12-venv \
    python3.12-dev \
    && rm -rf /var/lib/apt/lists/*
```

```dockerfile
RUN curl -sSL https://raw.githubusercontent.com/pypa/get-pip/3b73145063be545b649ad9ca83ea8da5fc915a4f/public/get-pip.py -o /tmp/get-pip.py \
    && echo "a341e1a43e38001c551a1508a73ff23636a11970b61d901d9a1cad2a18f57055  /tmp/get-pip.py" | sha256sum -c - \
    && python /tmp/get-pip.py \
    && rm /tmp/get-pip.py \
    && update-alternatives --install /usr/bin/pip pip /usr/local/bin/pip3.12 1
```

1. 如果把 `rm -rf /var/lib/apt/lists/*` 单独拆成下一条 `RUN`，镜像会变小吗？为什么？
2. `--no-install-recommends` 和后面 pip 的 `--no-cache-dir` 分别省掉了什么？
3. 下载 `get-pip.py` 时为什么要固定到某个 commit 并校验 sha256？如果校验失败，构建会怎样？

**Q10.** `docker-compose.yml` 位于 `phases/00-setup-and-tooling/07-docker-for-ai/code/`，其中写着：

```yaml
    volumes:
      - ../../../:/workspace
      - ~/models:/models
      - ~/datasets:/data
```

而讲义里的 `docker run` 是在仓库根目录执行的：`-v $(pwd):/workspace`。

1. compose 里的 `../../../` 是相对于哪个目录解析的？它实际挂载的是宿主机上的哪个目录？
2. 这和 `docker run` 版本挂载的 `/workspace` 一样吗？如果你想让两者都挂载仓库根目录，compose 里应该怎么改？
3. 如果宿主机上还没有 `~/datasets` 目录，`docker compose up` 时会发生什么？可能带来什么麻烦？

**Q11.** 讲义练习 3：给镜像加上 `flask`，在容器里跑一个简单 API 并用 `-p 5000:5000` 映射端口。很多人照做后，宿主机 `curl http://localhost:5000/` 却连不上。

1. 写出最小的 `app.py` 和 `docker run` 命令，让宿主机能访问到容器里的 Flask 服务。
2. 解释"连不上"的最常见原因，并说明它和讲义里 Jupyter 命令中的 `--ip=0.0.0.0` 是同一个道理。

---

## 四、面试高频题

**Q12.**（基础必考）容器和虚拟机有什么区别？为什么说容器"轻量"？它的隔离是靠什么实现的？

**Q13.**（原理深挖）在 Docker 里跑 PyTorch + CUDA 时，宿主机驱动、容器内 CUDA 版本、PyTorch wheel 的 CUDA 版本三者是什么关系？为什么说"CUDA 装在镜像里，驱动留在宿主机"？

**Q14.**（工程实践）一个 AI 镜像动辄 10 GB 以上、每次改一行代码构建 20 分钟。你会从哪些方面优化镜像体积和构建速度？

**Q15.**（场景设计）请设计一个 RAG 服务在单机上的 Docker Compose 部署：包括 LLM 推理服务、向量数据库、API 层。要考虑 GPU 分配、模型权重、数据持久化、服务间通信和启动顺序。

**Q16.**（追问型）模型权重应该"打进镜像"还是"运行时挂载 / 下载"？各有什么取舍？生产环境一般怎么做？

---

## 五、参考答案与解析

### Q1 — 答案：B

容器共享宿主机内核，在内核层面被隔离成拥有独立文件系统、网络的进程，不需要启动一个新内核，所以启动是秒级的。A 说的是 VM；C 错在容器有自己的根文件系统和网络栈；D 错在 VM 要额外跑整套客户机 OS，开销明显更大。

### Q2 — 答案：C

构建缓存按指令逐层判断：某条 `RUN` 的命令字符串变了，这一层缓存失效，**它之后的所有层**也都要重建；它之前的层不受影响。本节 Dockerfile 刻意把 torch（约数 GB、变动少）放在通用库之前的独立一层，正是为了"改通用库时不重新下载 torch"。A 错在 Docker 不是按"整个文件变没变"判断；B 把方向搞反了。

⚠️ 延伸：缓存的判断依据是**指令文本**，不是"包有没有新版本"。`pip install numpy` 这一行没变，就算 numpy 发布了新版也会直接命中旧缓存；而换一台机器或加 `--no-cache` 重建，就可能装到不同版本——这也是生产镜像要锁版本的原因。

### Q3 — 答案：B

讲义的原话是："Docker isolates the CUDA toolkit inside the container while sharing the host GPU driver through the NVIDIA Container Toolkit"。驱动是内核模块，必须装在宿主机；镜像里只放用户态的 CUDA 库。A 反了；C 错在不加 `--gpus`（或 compose 里的 `deploy.resources.reservations.devices`）容器看不到 GPU；D 混淆了运行时钩子和编译工具（编译要靠 `devel` 镜像里的 nvcc）。

### Q4 — 答案：C

只有 `devel` 镜像带完整 CUDA toolkit 和编译器（nvcc），讲义明确写了 "Use for: building packages that need nvcc (flash-attn, bitsandbytes)"。`runtime` 只有运行时库，`base` 更精简，`python:3.12-slim` 根本没有 CUDA。代价是 devel 体积大（约 4 GB）。常见做法是"devel 里编译、runtime 里运行"的多阶段构建。

### Q5 — 答案：B

Compose 会为项目自动创建一张共享网络，并提供以**服务名**为主机名的 DNS 解析，所以在 ai-dev 里用 `qdrant:6333` 即可。A 是最经典的坑：容器里的 `localhost` 指的是**容器自己**，不是宿主机，也不是其他容器。C 能凑合但脆弱（宿主 IP 会变）；D 中共享 volume 是共享文件，不是网络通信。

### Q6 — 答案：A

`docker compose down` 删除容器和 Compose 创建的网络，**默认保留命名卷**；加 `-v` 才会连 `volumes:` 里声明的命名卷（`qdrant_data`）一起删——Qdrant 里的向量数据就没了。`~/models` 是 bind mount（宿主机目录直接映射），Docker 不会删宿主机目录。D 错：`down` 不删镜像（`--rmi` 才删）。

### Q7 — 答案：B

讲义解释：CUDA 基础镜像其实有 arm64 版本，Docker Desktop 在 Apple Silicon 上会自动选它（所以 A 错），但 PyTorch 的 `cu124` wheel 只有 x86_64 版本，于是 `pip install torch==2.6.0+cu124` 报 `No matching distribution found`。固定平台后拉取 x86_64 镜像、在模拟下运行：构建更慢，而且**没有 GPU**（C 错、D 错）。Mac 上要用 GPU，应按第 01 节在宿主机上原生运行 MPS 版 PyTorch。

### Q8 — 答案：B

当 stdout 不是终端（比如被 Docker 收集日志）时，Python 默认对输出做块缓冲，训练日志可能攒很久才一次性出现，进程崩溃时甚至会丢失最后几行。`PYTHONUNBUFFERED=1` 让输出不缓冲、实时可见。C 是 `--no-cache-dir` 的作用；D 是 `DEBIAN_FRONTEND=noninteractive` 的作用。

### Q9 — 参考答案

1. **不会变小。** 每条 `RUN` 生成一层，层是只读、叠加的。如果下一层再 `rm`，前一层里已经写入的 apt 索引文件仍然存在于那一层中，只是在最终文件系统视图里"被遮住"了，镜像体积不减。必须在**产生这些文件的同一条 `RUN`** 里删掉，它们才不会进入任何一层。这也是为什么整段要用 `&&` 串成一条长命令。
2. `--no-install-recommends`：apt 只装硬依赖，不装"推荐"包（文档、额外工具等），能显著减少体积。`--no-cache-dir`：pip 不在 `~/.cache/pip` 里保留下载的 wheel——在镜像里这份缓存永远不会被复用，只会白白占几百 MB 到几 GB（torch 的 wheel 本身就很大）。
3. 固定 commit 保证每次下载到的是**同一份** `get-pip.py`（可复现），sha256 校验保证内容没被篡改或下载损坏（供应链安全）。`sha256sum -c -` 校验失败会返回非 0 退出码，`&&` 链条中断，这条 `RUN` 失败，**整个构建失败**——宁可构建失败，也不要悄悄执行一个来历不明的脚本。

### Q10 — 参考答案

1. Compose 文件里的相对路径**相对于 compose 文件所在目录**解析。从 `code/` 往上三级：`..` → `07-docker-for-ai`，`../..` → `00-setup-and-tooling`，`../../..` → `phases/`。所以 compose 版本的 `/workspace` 实际是仓库里的 **`phases/` 目录**。
2. 不一样。讲义的 `docker run` 在仓库根目录执行 `-v $(pwd):/workspace`，挂的是**仓库根目录**。想让 compose 也挂仓库根，应改为再往上一级：

```yaml
    volumes:
      - ../../../../:/workspace
```

   这类"差一级"的路径问题非常常见，排查办法是进容器 `ls /workspace` 看一眼到底挂了什么。
3. bind mount 的宿主机源目录不存在时，Docker 会**自动创建它**，而且通常由 root（Docker 守护进程）创建，属主是 root。后果是：容器里写进去的文件、甚至目录本身，在宿主机上你的普通用户可能没有写权限，需要 `sudo chown`。稳妥做法是提前 `mkdir -p ~/models ~/datasets`。

### Q11 — 参考答案

1. 最小实现（假设已在 Dockerfile 的最后一个 `pip install` 里加上 `flask` 并重新构建）：

```python
# app.py（放在仓库根目录，会被挂载到 /workspace）
from flask import Flask

app = Flask(__name__)


@app.route("/")
def hello():
    return {"status": "ok"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
```

```bash
docker run --rm -it \
    -v $(pwd):/workspace \
    -p 5000:5000 \
    ai-dev python app.py

# 另开一个终端
curl http://localhost:5000/
# {"status":"ok"}
```

2. 最常见原因是服务只监听在容器内的 `127.0.0.1`：Flask 的 `app.run()` 默认 `host="127.0.0.1"`。`-p 5000:5000` 是把宿主机端口转发到**容器的网络接口**上，而容器内的 `127.0.0.1` 只接受容器自己发来的连接，转发进来的流量自然进不去。改成监听 `0.0.0.0`（所有网卡）即可。Jupyter 命令里的 `--ip=0.0.0.0` 解决的是同一个问题。另外两个次要原因：忘了 `-p`（只写 `EXPOSE` 不会真的发布端口，`EXPOSE` 只是文档性声明）、或宿主机 5000 端口被占用（macOS 上 AirPlay 接收器默认占用 5000，可改用 `-p 5001:5000`）。

### Q12 — 参考回答要点

- **定义**：容器是被隔离的进程，共享宿主机内核，自带文件系统、网络；VM 通过 hypervisor 虚拟出硬件，每台 VM 跑完整的客户机 OS 和内核。
- **为什么轻量**：不用启动内核和整套系统服务，启动是秒级（VM 是分钟级）；镜像分层共享，多个容器复用同一份只读基础层；内存只占应用本身。
- **隔离机制**：Linux namespaces（PID、网络、挂载、UTS、IPC、用户等）负责"看不见彼此"，cgroups 负责"限制资源用量"（CPU、内存、IO），再叠加 capabilities、seccomp 等做权限收缩。
- **取舍**：隔离强度弱于 VM（共享内核，内核漏洞影响所有容器）；不能在 Linux 宿主上原生跑 Windows 容器；Mac/Windows 上的 Docker Desktop 实际上是在一台轻量 Linux VM 里跑容器。
- **加分点**：提到多租户、跑不可信代码（例如 Agent 执行用户代码）时，会选 gVisor、Kata Containers、Firecracker microVM 等更强隔离方案。

### Q13 — 参考回答要点

- **分层**：GPU 驱动（内核模块 + 用户态驱动库）在宿主机；CUDA toolkit/runtime 在镜像里；PyTorch wheel 编译时绑定了某个 CUDA 版本（如 `+cu124`），自带或依赖相应的 CUDA 运行时库。
- **兼容规则**：宿主机驱动版本必须**足够新**，能支持容器里 CUDA 版本的要求。新驱动可以跑旧 CUDA 的镜像，旧驱动跑不了新 CUDA 镜像。`nvidia-smi` 右上角的 "CUDA Version" 表示该驱动**最高支持**的 CUDA 版本，不是"已安装的 CUDA"。
- **为什么这样拆**：驱动和内核强绑定，放进镜像既不可能也不安全；而 CUDA toolkit 是普通用户态库，放进镜像就能做到"同一镜像在不同机器上 CUDA/cuDNN/PyTorch 组合完全一致"——这正是讲义开头"你的 12.4、同事的 11.8"问题的解法。NVIDIA Container Toolkit 是运行时钩子，在容器启动时把宿主机的设备文件和驱动库注入容器。
- **排查顺序**：宿主 `nvidia-smi` → `docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi` → 容器内 `python -c "import torch; print(torch.cuda.is_available())"`，逐层定位是驱动、Toolkit 还是 wheel 版本的问题。
- **常见误区**：以为镜像里装了 CUDA 就不需要宿主驱动；把 `nvidia-smi` 显示的 CUDA 版本当成 PyTorch 实际使用的版本（后者看 `torch.version.cuda`）。

### Q14 — 参考回答要点

- **选对基础镜像**：只运行不编译就用 `runtime` 而不是 `devel`；纯 CPU 推理用 `python:3.12-slim`。
- **多阶段构建**：在 devel 阶段编译 flash-attn 等扩展、产出 wheel，在 runtime 阶段只 `COPY` 产物，编译器和中间文件不进最终镜像。
- **缓存友好的指令顺序**：系统依赖 → 大而稳定的依赖（torch）→ 其他 Python 依赖 → 最后才 `COPY` 代码。先 `COPY requirements.txt` 并安装，再 `COPY . .`，这样改代码不会让依赖层失效。
- **同层清理**：`apt-get install` 与 `rm -rf /var/lib/apt/lists/*` 同一条 `RUN`；`--no-install-recommends`、`pip --no-cache-dir`。
- **控制构建上下文**：加 `.dockerignore`，排除 `.git`、数据集、模型权重、`.venv`、`__pycache__`；不要把权重 `COPY` 进镜像（见 Q16）。
- **锁版本**：用锁文件固定所有依赖，保证缓存失效后重建出的镜像仍一致。
- **加分点**：BuildKit 的 cache mount（`RUN --mount=type=cache,target=/root/.cache/pip`）可以让 pip 缓存跨构建复用又不进入镜像层；CI 中使用远程构建缓存（registry cache）。

### Q15 — 参考回答要点

- **服务拆分**：`llm`（推理服务，如 vLLM/TGI，独占 GPU）、`qdrant`（向量库）、`api`（RAG 编排层，做检索 + 拼 prompt + 调 llm，纯 CPU），按需加 `frontend`。
- **GPU 分配**：只给 `llm` 写 `deploy.resources.reservations.devices`（`driver: nvidia`、`capabilities: [gpu]`），多卡时用 `device_ids` 指定具体卡，避免多个服务争抢显存。
- **模型权重**：宿主机目录（或命名卷）挂载到 `/models`，作为 HF 缓存目录共享，重建容器不重新下载。
- **持久化**：Qdrant 用命名卷（如本节的 `qdrant_data:/qdrant/storage`）；注意 `docker compose down -v` 会删掉它。
- **通信**：服务之间用服务名（`http://qdrant:6333`、`http://llm:8000`）；只对外发布 `api`（和需要的调试端口）的端口，向量库和推理服务不必暴露到宿主机，减少攻击面。
- **启动顺序与健康检查**：`depends_on` 只保证启动顺序，不保证"已就绪"；给 llm、qdrant 配 `healthcheck`，并用 `depends_on: condition: service_healthy`；api 侧还要有重试——大模型加载可能要几分钟。
- **配置与密钥**：用 `.env` / 环境变量注入 API key、模型名，不要写进镜像。
- **加分点**：日志统一输出到 stdout（配合 `PYTHONUNBUFFERED=1`）；设置 `restart: unless-stopped`；单机 Compose 适合开发和小规模部署，多机扩缩容会迁移到 Kubernetes（阶段 17）。

### Q16 — 参考回答要点

| 方式 | 优点 | 缺点 |
|------|------|------|
| 打进镜像 | 镜像即完整制品，版本绑定、可复现；不依赖运行时网络或外部存储 | 镜像巨大（7B fp16 就 14 GB），拉取慢、冷启动慢；换模型就要重新构建、推送；镜像仓库成本高 |
| 运行时挂载 | 镜像小、重建快；权重可在多个容器/版本间共享（讲义的 `-v ~/models:/models`） | 依赖宿主机状态，"换台机器没有这个目录"就跑不起来；需要另外管理权重版本 |
| 运行时下载（对象存储 / HF Hub / 模型仓库） | 镜像小，模型版本与代码解耦，便于灰度切换 | 冷启动要下载；依赖网络和凭据；需要缓存层 |

- **生产常见做法**：镜像只放代码和依赖；权重存放在对象存储或模型仓库里，用**固定版本号/哈希**引用；节点本地盘或共享卷做缓存，启动时（或用 init 容器）预拉取；配合预热和副本常驻缓解冷启动。
- **加分点**：用 safetensors 格式加载更快更安全；对权重做哈希校验；镜像标签与模型版本一起记录，便于回滚。
- **常见误区**：在 Dockerfile 里 `COPY` 整个仓库时顺手把 `models/` 目录也带进了构建上下文——没有 `.dockerignore` 时构建既慢又可能把大文件打进镜像。

---

## 六、关联知识点

### 前置知识
- [阶段 00 · 01 开发环境](../../01-dev-environment/docs/zh.md)：本地 Python / PyTorch（含 Mac 的 MPS 版）安装，是"为什么需要容器"的对照组。
- [阶段 00 · 03 GPU 设置和云](../../03-gpu-setup-and-cloud/docs/zh.md)：驱动、CUDA、`nvidia-smi`，理解"驱动在宿主、CUDA 在镜像"的前提。
- [阶段 00 · 06 Python 环境](../../06-python-environments/docs/zh.md)：虚拟环境和依赖锁定，镜像是更彻底的"环境封装"。

### 本节被哪些后续内容用到
- [阶段 00 · 11 面向人工智能的 Linux](../../11-linux-for-ai/docs/zh.md)：用户组（`usermod -aG docker`）、权限、进程管理，是理解容器的 Linux 基础。
- [阶段 11 · 06 RAG](../../../11-llm-engineering/06-rag/docs/zh.md)：本节 compose 里起的 Qdrant 就是 RAG 的向量库。
- [阶段 17 · 03 GPU 自动扩缩容与 Kubernetes](../../../17-infrastructure-and-production/03-gpu-autoscaling-kubernetes/docs/zh.md)：从单机 Compose 走向集群编排。
- [阶段 17 · 04 vLLM 服务内部原理](../../../17-infrastructure-and-production/04-vllm-serving-internals/docs/zh.md)：推理容器里最常跑的服务。
- [阶段 17 · 10 冷启动缓解](../../../17-infrastructure-and-production/10-cold-start-mitigation/docs/zh.md)：镜像体积、权重加载直接决定冷启动时间（对应 Q16）。
- [阶段 17 · 25 安全、密钥与审计](../../../17-infrastructure-and-production/25-security-secrets-audit/docs/zh.md)：镜像里不放密钥、最小权限运行。
- [阶段 19 · 26 沙箱执行器与命令黑名单](../../../19-capstone-projects/26-sandbox-runner-denylist/docs/zh.md)：用隔离环境执行 Agent 生成的代码。

### 延伸关键词
`多阶段构建 (multi-stage build)` · `.dockerignore` · `BuildKit cache mount` · `namespaces / cgroups` · `NVIDIA Container Toolkit / CDI` · `Dev Containers` · `healthcheck / depends_on` · `distroless 镜像` · `镜像漏洞扫描` · `gVisor / Firecracker`
