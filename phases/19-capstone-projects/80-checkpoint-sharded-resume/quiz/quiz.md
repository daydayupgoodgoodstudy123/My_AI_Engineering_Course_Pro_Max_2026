# 测验 · 分片 Checkpoint 与原子恢复（Sharded Checkpoint and Atomic Resume）

> **阶段 19 · 综合项目 · 第 80 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | gather-then-write 的瓶颈 | 全部状态汇总到 rank 0 再写一个文件：写带宽等于"单个 rank 的网络/IO 链路"，其它 rank 全部空等；70B 模型约 1.1 TB 状态时要写几个小时 |
| 2 | Sharded checkpoint | 每个 rank 并行写自己的分片文件 `rankN.bin`，总写带宽随集群规模线性扩展（讲义：1 TB 单 rank 4 小时 → 64 rank 约 4 分钟） |
| 3 | Manifest（清单） | 一个 JSON 记录 `world_size`、`step`、`schema_version` 以及每个分片的 `rank / path / sha256 / param_shard_offset / param_shard_numel`，是加载端的"合同" |
| 4 | 原子写（tmp + rename） | 先写 `<name>.tmp` 并 `fsync`，再 `os.replace` 成正式名；POSIX 同一文件系统内的 rename 是原子的，崩溃时要么是旧文件、要么是新文件 |
| 5 | manifest 最后落地 | 所有分片 rename 完成后才 rename manifest；"manifest 存在"即意味着"所有分片已就位"，因此 manifest 是整个 checkpoint 的提交点（commit point） |
| 6 | 三种失败模式 | world_size 变化 → 比对 manifest 大声报错；分片缺失 → 逐个检查文件存在；部分写 / 截断 → 加载时校验 sha256 |
| 7 | 加载端的额外防御 | 本节代码还检查 schema_version、分片数、rank 越界、重复 rank、路径穿越（绝对路径、`..`、子目录） |
| 8 | Rotation（轮转） | 只保留最近 K 个 checkpoint（常见 3–5 个），避免训练中途磁盘写满导致下一次保存失败 |
| 9 | 生产模式 | 异步写（不阻塞训练，下次保存前等待上次完成）、本地 NVMe 先写再异步上传对象存储（两级存储）、DeepSpeed / FSDP `torch.distributed.checkpoint` / NeMo 都是每 rank 一个文件 |
| 10 | 本节实现的简化 | 单进程顺序写 4 个分片（并非真并行）；offset/numel 只记录不校验；rotation 按目录 mtime 排序且不区分完整/不完整的 checkpoint |

### 核心技能（能动手做到）

- [ ] 写出 "写 tmp → flush → fsync → os.replace → fsync 目录" 的原子写流程，并解释每一步防的是哪种崩溃
- [ ] 设计一个 manifest schema，并在加载时按"先校验合同、再触碰状态"的顺序拒绝坏 checkpoint
- [ ] 用 sha256 检测截断/损坏的分片，并说清它**不能**防什么（例如 manifest 与分片被同时篡改、pickle 反序列化的代码执行）
- [ ] 估算一个模型的 checkpoint 体积（混合精度 Adam 每参数约 16 字节）和不同 rank 数下的写入时间
- [ ] 利用 `param_shard_offset / numel` 实现从 N=4 到 N=8 的跨 world size 重分片（讲义练习 4）
- [ ] 找出本节 `rotate_checkpoints` 在"不完整目录"和"mtime 与 step 不一致"时的错误行为，并给出修复

---

## 二、基础自测（选择题）

**Q1.** 讲义说 vanilla checkpoint（全部状态 gather 到 rank 0 再写单个文件）在大规模下不可行，最根本的原因是：

- A. pickle 无法序列化超过 4 GB 的对象
- B. rank 0 的 CPU 无法同时计算 sha256
- C. 所有状态都要经过 rank 0 一条链路写出，写带宽是"最慢的单个链路"而非集群总带宽，其它 rank 全部空等
- D. POSIX 不允许单个文件超过 1 TB

**Q2.** 用混合精度 + Adam 训练一个 70B 参数模型（fp16 参数 2 B + fp16 梯度 2 B + fp32 主参数 4 B + Adam m 4 B + Adam v 4 B），按每参数 16 字节估算，全部训练状态约为多少？（讲义称约 1.1 TB）

- A. 约 1.12 TB
- B. 约 140 GB
- C. 约 560 GB
- D. 约 280 GB

**Q3.** 关于本节 `save_sharded` 的原子写，下列说法正确的是：

- A. 所有文件通过**一次** rename 同时变为正式名，因此整个 checkpoint 是一个原子操作
- B. 既然 rename 是原子的，写 tmp 文件之后就没必要再 `fsync`
- C. `os.replace` 在跨文件系统时同样保证原子性
- D. manifest 在所有分片 rename 之后才 rename，因此"manifest.json 存在"可以作为"本次 checkpoint 已完整提交"的标志（前提是写入的是一个新目录）

**Q4.** manifest 中每个分片的 `sha256` 主要防御的是：

- A. 加载恶意 checkpoint 时 pickle 执行任意代码
- B. 分片在写入过程中被截断或损坏（partial write），在它污染优化器状态之前就拒绝加载
- C. 用错误的 world_size 恢复训练
- D. 加快加载速度，因为只需比较哈希不必读文件

**Q5.** 对一个 4-rank 的 checkpoint 调用 `load_sharded(step_dir, expected_world_size=8)`，会发生什么？

- A. 读完 manifest 后立即抛出 `CheckpointError: world_size mismatch: manifest=4, expected=8`，任何分片文件都不会被读取
- B. 正常加载 4 个分片，剩下 4 个 rank 得到 `None`
- C. 自动把 4 个分片重新切成 8 份
- D. 先校验 4 个分片的 sha256，全部通过后才报 world_size 错误

**Q6.** 下列 manifest 字段中，哪一个在本节 `load_sharded` 里**只被记录、从未被校验**？

- A. `world_size`
- B. `sha256`
- C. `schema_version`
- D. `param_shard_offset` / `param_shard_numel`

**Q7.** 本节 `main()` 先写了 `step_0100`，又写了 `step_0000`～`step_0007` 共 8 个目录，然后调用 `rotate_checkpoints(workdir, keep_last=5)`。实际输出是什么？

- A. `rotated 3 oldest: ['step_0000', 'step_0001', 'step_0002']`
- B. `rotated 4 oldest: ['step_0100', 'step_0000', 'step_0001', 'step_0002']`
- C. `rotated 0 oldest: []`，因为 step_0100 的 step 最大
- D. `rotated 4 oldest: ['step_0004', 'step_0005', 'step_0006', 'step_0007']`

**Q8.** 本节用 `torch.save(state, buf, pickle_protocol=4)` 序列化、`torch.load(buf, weights_only=False)` 反序列化。在 PyTorch 2.14 上实测，下列说法正确的是：

- A. `weights_only=False` 只影响加载速度，与安全无关
- B. 只要 sha256 校验通过，`weights_only=False` 就是安全的
- C. 用 protocol 4 保存的文件改用 `weights_only=True` 加载会报 `Unsupported operand 149`；代码只能用 `weights_only=False`，加载来源不可信的 checkpoint 时存在任意代码执行风险
- D. `torch.save` 每次输出的字节都不同，所以 sha256 必须在写盘后重新读取文件计算

---

## 三、动手 / 代码题

**Q9.** 下面是 `save_sharded` 的提交阶段：

```python
    for tmp, final in tmp_paths:
        os.replace(tmp, final)
    os.replace(manifest_tmp, manifest_final)
    _fsync_dir(dest)
```

模块 docstring 写的是："the manifest writes last, then a single rename moves everything to the final names. A crash mid-write leaves the previous checkpoint intact."

1. 这段代码实际做了几次 rename？docstring 的说法哪里不准确？
2. 假设**向一个已经存在 checkpoint 的同一目录**再次保存（例如重跑同一个 step），并在第 3 次 `os.replace` 时崩溃。目录里会留下什么？再调用 `load_sharded` 会怎样？"previous checkpoint intact" 还成立吗？
3. 给出一种让"整个 checkpoint 只有一个提交点"的改法。

**Q10.** 阅读 `rotate_checkpoints`：

```python
    children = sorted(
        [c for c in parent.iterdir() if c.is_dir() and c.name.startswith("step_")],
        key=lambda c: (c.stat().st_mtime, c.name),
    )
    ...
    elif len(children) > keep_last:
        to_delete = children[:-keep_last]
```

1. 父目录下有 `step_0000`、`step_0001`、`step_0002` 三个完整 checkpoint，以及一个刚才崩溃、没有 manifest 的空目录 `step_0003`（mtime 最新）。调用 `rotate_checkpoints(parent, keep_last=1)` 会删掉什么、留下什么？后果是什么？
2. 指出排序键的第二个问题（提示：Q7）。
3. 写一个修复版 `rotate_complete(parent_dir, keep_last)`。

**Q11.** 讲义练习 4：实现跨 world size 的重分片。写一个函数 `reshard(src_dir, old_world_size, new_world_size)`：读取一个 N=4 的 checkpoint，利用 manifest 中的 `param_shard_offset / param_shard_numel` 把 `param_shard / m_shard / v_shard` 拼回扁平张量，再切成 N=8 份。要求：拼接前验证 offset 恰好无缝铺满 `[0, total)`；切完后用 `save_sharded` 写出并能被 `load_sharded(..., 8)` 加载，且拼回后与原始数据逐字节相等。

**Q12.** 计算题（均用 Python 实际算过）：

1. 本节每个 rank 的状态里有 3 个长度 1024 的 float32 张量，实测 `rank0.bin` 为 14,241 字节。原始张量数据是多少字节？多出来的约 1.9 KB 是什么？
2. manifest 中 4 个分片的 `param_shard_offset` 分别是多少？
3. 讲义："A 1 TB checkpoint that took 4 hours through one rank takes 4 minutes through 64 ranks"。按理想线性扩展精确算是多少分钟？实际集群中这个线性假设会在哪里失效？

---

## 四、面试高频题

**Q13.**（基础必考）sharded checkpoint 和 consolidated（汇总成单文件）checkpoint 各有什么优缺点？什么时候仍然需要 consolidated 格式？

**Q14.**（原理深挖）请完整描述一次"崩溃安全"的文件写入：为什么要写 tmp、为什么要 `fsync` 文件、为什么 rename 之后还要 `fsync` 目录？多文件的 checkpoint 怎样做到"要么全有、要么全无"？

**Q15.**（工程实践）为一个在 1024 张 GPU 上训练的 70B 模型设计 checkpoint 系统：保存频率、存储分层、异步化、校验、轮转和恢复时间目标，你会怎么定？

**Q16.**（场景设计）训练到第 3 天，一台 8 卡机器永久故障，你只能用剩下的 56 张卡继续（world size 从 64 变成 56）。基于 manifest 的 checkpoint 要怎样恢复？哪些状态需要重分片、哪些不需要？

**Q17.**（追问型）"恢复后 byte-equal" 就等于"训练可以无缝继续"吗？要做到恢复后的 loss 曲线与不中断时完全一致，checkpoint 里还必须保存什么？

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义原文："The IO bandwidth is the slowest single GPU's network link, not the aggregate." gather 之后只有 rank 0 在写，其它 rank 在等待集合通信，整个作业停摆。A 错：pickle protocol 4 起就支持超过 4 GB 的对象；B 不是瓶颈所在；D 不是 POSIX 的限制。分片写让每个 rank 用自己的链路并行写，总带宽随 rank 数扩展。

### Q2 — 答案：A

`70e9 × 16 B = 1.12e12 B ≈ 1.12 TB`，与讲义"1.1 TB"一致。B 是只算 fp16 参数（2 B/参数）；D 是 4 B/参数（只算 fp32 主参数）；C 是 8 B/参数。面试中常用"混合精度 Adam ≈ 16 字节/参数"作为速算（ZeRO 论文的 2+2+12 分解）。

### Q3 — 答案：D

代码中先逐个 rename 分片，最后才 rename manifest，所以对一个**新目录**而言，manifest 出现即代表所有分片都已就位——这就是提交点。A 是 docstring 的说法，但实际是 N+1 次独立 rename（见 Q9）；B 错：rename 只保证目录项的原子切换，不保证文件内容已经落盘，掉电后可能出现"新名字指向空/半截文件"，所以 rename 前必须 fsync 文件；C 错：跨文件系统时 `os.replace` 直接失败（`OSError: [Errno 18] Invalid cross-device link`），tmp 文件必须和目标在同一文件系统。

### Q4 — 答案：B

讲义的失败模式表："Partial write | shard file truncated mid-flush | sha256 verification on load"。实测把 `rank1.bin` 截掉一半后加载，报 `sha256 mismatch on rank 1`。A 错：sha256 写在同目录的 manifest 里，攻击者能改分片也就能改 manifest，它只是**完整性校验**而不是**真实性校验**；而且 `weights_only=False` 的风险与哈希无关（见 Q8）。C 由 `world_size` 字段负责。D 错：校验 sha256 必须完整读一遍文件。

### Q5 — 答案：A

`load_sharded` 的检查顺序是：manifest 是否存在 → `world_size` → `schema_version` → 分片数 → 逐个分片（rank 范围、重复、路径安全、存在、sha256）。world_size 不符在第二步就抛出，实际输出 `world_size mismatch: manifest=4, expected=8`。这正是"在触碰任何状态之前先校验合同"。B 是讲义说的"静默错误"；C 是讲义练习 4 要你自己实现的重分片，不会自动发生；D 顺序错。

### Q6 — 答案：D

实测：把 manifest 里 rank 1 的 offset 改成 999999、rank 2 的 numel 改成 7，`load_sharded` 照样成功返回。讲义说 offset/numel "let the loader reconstruct the flat parameter tensor at the correct position"，但本节加载端返回的是每个 rank 的 state dict，根本没用到这两个字段。world_size、sha256、schema_version 都有对应的检查。若要真正"防御"，应校验 offsets 无缝铺满 `[0, total)` 且 `numel` 与实际张量一致（见 Q11）。

### Q7 — 答案：B

实际运行输出：`rotated 4 oldest: ['step_0100', 'step_0000', 'step_0001', 'step_0002']`。原因：
- 目录里共有 9 个 `step_*`（step_0100 并没有被删掉），keep 5 就要删 4 个；
- 排序键是 `(st_mtime, name)`，`step_0100` 最先创建，mtime 最早，所以第一个被删——尽管它的 step（100）是所有 checkpoint 里最大的。

A 忽略了 step_0100；C 误以为按 step 排序；D 把顺序弄反。这说明"按 mtime 轮转"在"手动复制/重写目录、时钟回拨、从备份恢复"等情况下会删错。

### Q8 — 答案：C

实测（PyTorch 2.14.1）：对 protocol 4 保存的分片用 `weights_only=True` 加载，报 `UnpicklingError ... Unsupported operand 149`（opcode 149 是 protocol 4 引入的 FRAME）；同样的 state 用默认协议保存则可以 `weights_only=True` 正常加载。`weights_only=False` 走完整 pickle，可以执行任意代码，PyTorch 自己的报错信息也写着 "it can result in arbitrary code execution. Do it only if you got the file from a trusted source"。B 错：sha256 和分片放在一起，不能证明来源可信。D 错：实测同一 state 连续两次 `_serialize_state` 字节完全相同；而且代码本来就是对"要写入的那份 payload"计算哈希，不依赖确定性。

### Q9 — 参考答案

1. **N+1 次 rename**：4 个分片各一次 `os.replace`，manifest 再一次。每次 rename 自身是原子的，但它们合在一起不是一个原子操作。docstring 中"a single rename moves everything"不准确；真正起到"单一提交点"作用的是**最后那次 manifest rename**，而且只在写入新目录时成立。
2. 用 monkeypatch 让第 3 次 `os.replace` 抛异常实测，目录中留下：

   ```text
   ['manifest.json', 'manifest.json.tmp', 'rank0.bin', 'rank1.bin', 'rank2.bin', 'rank2.bin.tmp', 'rank3.bin', 'rank3.bin.tmp']
   ```

   此时 `rank0.bin`、`rank1.bin` 已是**新**数据，`rank2/3.bin` 和 `manifest.json` 仍是**旧**的。`load_sharded` 报 `sha256 mismatch on rank 0`——sha256 把这次"新旧混合"拦住了，没有静默损坏；但这个目录里的旧 checkpoint 也已经坏了，"previous checkpoint intact" 不成立。
3. 改法（任选其一）：
   - **目录级提交**：所有文件写进 `step_0100.tmp/`，全部 fsync 后一次 `os.replace("step_0100.tmp", "step_0100")`，再 fsync 父目录（注意：目标目录已存在且非空时 rename 会失败，所以每个 step 必须是新目录）；
   - **指针文件提交**：每次保存都写新目录，完成后原子更新一个 `latest` 文件（写 `latest.tmp` → fsync → rename），加载时只认 `latest` 指向的目录。DeepSpeed 的 `latest` 文件就是这种做法（讲义 Use It 一节）。

### Q10 — 参考答案

1. 实测：`rotate_checkpoints(parent, keep_last=1)` 返回 `['step_0000', 'step_0001', 'step_0002']`，只留下空的 `step_0003`。**所有完整的 checkpoint 都被删了**，下一次恢复无 checkpoint 可用。函数只看目录名前缀，不检查 manifest 是否存在。
2. 排序用 mtime 而不是 step：目录 mtime 反映"最后一次增删条目的时间"，与训练步数没有必然关系（Q7 中 step_0100 被优先删除）。另外 `shutil.rmtree(..., ignore_errors=True)` 删除失败也会把名字记入 `deleted`，返回值可能撒谎。
3. 修复版（已运行验证：在 step_0100 + step_0000..0002 + 空的 step_0200 上 keep_last=1，删除 `['step_0000', 'step_0001', 'step_0002']`，保留 `step_0100` 和未完成的 `step_0200`）：

```python
import json, shutil
from pathlib import Path

def rotate_complete(parent_dir, keep_last=5):
    parent = Path(parent_dir)
    complete = []
    for c in parent.iterdir():
        mf = c / "manifest.json"
        if c.is_dir() and c.name.startswith("step_") and mf.exists():   # 只统计已提交的 checkpoint
            complete.append((json.loads(mf.read_text())["step"], c))
    complete.sort()                                                    # 按 manifest 中的 step 排序
    doomed = complete[:-keep_last] if keep_last > 0 else complete
    for _, c in doomed:
        shutil.rmtree(c)                                               # 失败就抛异常，不要谎报
    return [c.name for _, c in doomed]
```

要点：只计数完整的 checkpoint；按 step 排序；**先成功保存新的、再删除旧的**（讲义写的是"next save deletes the oldest first"，这样做能腾出磁盘，但若新保存失败就只剩 K−1 个，磁盘预算应按 K+1 个来留）；未完成目录应另行清理而不是挤占名额。

### Q11 — 参考答案

```python
import torch
from main import load_sharded, CheckpointError

def reshard(src_dir, old_world_size, new_world_size, keys=("param_shard", "m_shard", "v_shard")):
    manifest, states = load_sharded(src_dir, expected_world_size=old_world_size)
    entries = sorted(manifest.shards, key=lambda e: e.param_shard_offset)
    pos = 0
    for e in entries:                                   # offset 必须无缝、无重叠地铺满 [0, total)
        if e.param_shard_offset != pos:
            raise CheckpointError(f"gap/overlap at rank {e.rank}: offset {e.param_shard_offset} != {pos}")
        if states[e.rank]["param_shard"].numel() != e.param_shard_numel:
            raise CheckpointError(f"numel mismatch at rank {e.rank}")
        pos += e.param_shard_numel
    total = pos
    flat = {k: torch.cat([states[e.rank][k] for e in entries]) for k in keys}
    chunk = -(-total // new_world_size)                 # 向上取整
    new_states = []
    for r in range(new_world_size):
        lo, hi = r * chunk, min((r + 1) * chunk, total)
        st = {k: flat[k][lo:hi].clone() for k in keys}
        st.update(rank=r, world_size=new_world_size, step=states[0]["step"])
        new_states.append(st)
    return new_states
```

实际运行：N=4 → N=8 后 `save_sharded` 写出的新 manifest offsets 为 `[0, 512, 1024, ..., 3584]`、numel 全为 512；`load_sharded(..., 8)` 成功，拼回的 `param_shard` 与原 4 个分片拼接结果 `torch.equal` 为 `True`。

注意：
- 必须按 **offset** 排序拼接，而不是按 rank——生产系统中 rank 与参数区间的对应关系不一定单调；
- m、v 要和参数**用同样的切分**一起重分片，否则 Adam 状态与参数错位；
- 不能整除时（ZeRO 常见）要处理 padding：新 world size 下最后一个分片较短，或像 81 节那样补零对齐；
- 真实系统（`torch.distributed.checkpoint`）的做法是：保存时记录每块数据的全局坐标（类似这里的 offset），加载时由 planner 按新的分片布局读取需要的区间，而不是先在一个进程里拼出完整张量。

### Q12 — 参考答案

1. 原始数据 `3 × 1024 × 4 B = 12,288 B`。多出的 `14,241 − 12,288 = 1,953 B` 是 `torch.save` 的 zip 容器（每个 storage 是 zip 中的一个条目，含文件头与中央目录）以及 pickle 后的字典结构（键名、`rank`、`world_size`、`step` 等标量、张量元数据）。张量越大，这部分开销占比越小。
2. `0, 1024, 2048, 3072`（每个 rank 的 `param_shard` 都有 1024 个元素，offset 是前面所有分片 numel 的累加和）。
3. `240 / 64 = 3.75` 分钟，讲义取整为"4 分钟"。线性扩展的前提是：存储系统的总带宽足够大（Lustre/GPFS 的 OST 数量、对象存储的吞吐配额）、元数据服务器扛得住同时创建上千个文件、网络没有其它流量竞争。实际中往往在共享文件系统的总带宽或元数据操作上先饱和，所以还要配合"先写本地 NVMe、再异步上传"（讲义的两级存储）。

### Q13 — 参考回答要点

- **Sharded**：每 rank 并行写自己的分片；优点是写带宽随规模扩展、无需 gather（不占 rank 0 内存）、保存/恢复都快；缺点是文件多、与并行布局（world size、ZeRO 切分方式）绑定，换布局要重分片，离线使用（评测、发布）不方便。
- **Consolidated**：一个完整的 state dict；优点是与并行布局无关、可直接用于推理/微调/发布；缺点是需要把全部状态 gather 到一个节点，内存和带宽都受限。
- 典型实践：**训练中用 sharded**（频繁、要快），**训练结束或里程碑时离线转换成 consolidated**（例如 DeepSpeed 提供 `zero_to_fp32.py` 把 ZeRO 分片合成单个 fp32 权重文件；FSDP 可用 `FULL_STATE_DICT` 或 DCP 的格式转换工具）。
- 加分点：发布权重时通常只需要参数（不需要优化器状态），体积约为训练 checkpoint 的 1/8（16 B → 2 B/参数）。

### Q14 — 参考回答要点

- **写 tmp**：直接写正式名时，崩溃会留下半截文件且名字是"正式的"，读者无法区分。写 tmp 让"未完成"的文件永远不会出现在正式名下。
- **fsync 文件**：`write` 只把数据交给页缓存；不 fsync 就 rename，掉电后文件系统可能已经记录了 rename、但数据块还没落盘，结果是正式名指向空或部分数据（ext4 的 `data=ordered` 对 rename 替换有特殊处理，但不能依赖）。
- **rename**：POSIX 规定同一文件系统内 `rename` 原子地替换目标；读者只会看到旧文件或新文件。
- **fsync 目录**：rename 修改的是目录项，目录本身的元数据也要 fsync 才能保证 rename 在掉电后仍然生效。本节 `_fsync_dir` 就是做这个（在不支持的平台上静默跳过）。
- **多文件全有或全无**：单个文件靠 rename；多文件要有一个**单一提交点**——最后写 manifest（本节做法）、目录级 rename、或原子更新 `latest` 指针。加载端只认已提交的 checkpoint，并用 sha256 兜底检测漏网的损坏。
- 常见误区：以为 `f.flush()` 就等于落盘（它只是把 Python 缓冲交给操作系统）；在 NFS/对象存储上照搬 POSIX rename 语义（S3 没有原子 rename，通常靠"最后上传 manifest/标记对象"实现提交）。

### Q15 — 参考回答要点

- **频率**：按 wall-clock（例如每 10–30 分钟）而不是按 step（81 节讲义 "Checkpoint every K minutes, not every K steps"）。用"期望损失 = 故障间隔内平均丢失的进度 + 保存开销"权衡：保存越快，就能越频繁。
- **分层存储**：每 rank 先写本地 NVMe（秒级），再后台异步上传到对象存储（持久化）；manifest 记录本地路径，另有上传 manifest 记录远端路径（讲义的 two-tier）。
- **异步**：保存时先把 GPU 状态拷到固定内存（pinned memory）快照，训练立即继续，后台线程/进程写盘；下一次保存前必须等上一次完成（讲义的 barrier）。
- **校验**：manifest 含 world_size、schema_version、每分片 sha256（或更快的 CRC，用于高频场景，讲义练习 3）、offset/numel；加载前先验合同。
- **轮转**：本地保留最近 2–3 个，远端保留更多并设里程碑永久保存；只计数完整的 checkpoint（见 Q10）。
- **恢复目标**：明确 RTO（例如 10 分钟内恢复训练），定期演练"从 checkpoint 恢复并比对 loss"——没有演练过的恢复等于没有备份。
- 加分点：估算体积 70B × 16 B ≈ 1.1 TB，1024 个 rank 每个约 1.1 GB，本地 NVMe 几 GB/s，写入只需数秒。

### Q16 — 参考回答要点

- manifest 记录的是 world_size=64，直接加载会被 world_size 检查拒绝——这是**期望的行为**，迫使你走显式的重分片路径（讲义 quiz："loud rejection forces the operator to use the cross-world-size rebalance path"）。
- **需要重分片的**：ZeRO/FSDP 切分的状态——fp32 主参数、Adam m/v（以及 ZeRO-2/3 下的梯度和参数分片）。用 offset/numel 拼回扁平空间再按 56 重新切（Q11），或用 `torch.distributed.checkpoint` 的 resharding 能力按新布局直接读取需要的区间。
- **不需要重分片的**：每个 rank 都持有完整副本的东西（DDP 下的模型参数、学习率调度器状态、全局 step）。
- **还要调整的**：全局 batch = 每卡 batch × 卡数；卡数从 64 变 56 后，要么调整每卡 batch / 梯度累积步数保持全局 batch 不变，要么相应调整学习率；数据加载器的位置要按"已消费的全局样本数"重新计算每个 rank 的起点，避免重复或跳过数据。
- 张量并行 / 流水线并行的布局变化更复杂（要切分的是权重矩阵本身），通常尽量只改变数据并行维度。

### Q17 — 参考回答要点

- byte-equal 只证明"存进去的等于读出来的"，不证明"存进去的东西足够"。本节 demo 只比较了 `param_shard`（测试也是），连 `m_shard`、`v_shard` 都没比较（我们额外验证了全部键均相等）。
- 要做到恢复后与不中断时**逐位一致**，还需要：
  - 优化器全部状态（m、v、step count——Adam 的偏差校正依赖 step）；
  - 学习率调度器状态；混合精度的 loss scaler 状态；
  - 所有 RNG 状态：Python `random`、NumPy、torch CPU 与每块 GPU 的生成器（dropout、数据增强依赖它们）；
  - 数据加载器的位置：epoch、sampler 的随机种子与已消费的样本偏移；
  - 训练元数据：global step、已见 token 数、wall clock（本节 manifest 里有 `wall_clock_seconds`）。
- 即使全部保存，GPU 上的非确定性算子（原子加、不同的归约顺序）也会让结果只能"统计一致"而非逐位一致；要逐位一致还需开启确定性算法并固定通信归约顺序。
- 81 节讲义练习 3 正是"从 step 10 恢复并继续训练到 step 20，验证最终 loss 与原始运行相同"——这才是对恢复合同的真正检验。

---

## 六、关联知识点

### 前置知识
- [阶段 19 · 47 Checkpoint 保存与恢复](../../47-checkpoint-save-resume/docs/zh.md)：单机 checkpoint 的保存/恢复内容，本节把它扩展到多 rank。
- [阶段 19 · 78 ZeRO Optimizer 状态分片](../../78-zero-parameter-sharding/docs/zh.md)：本节保存的 `param_shard / m_shard / v_shard` 正是 ZeRO 的分片形状。
- [阶段 19 · 77 从零实现数据并行 DDP](../../77-data-parallel-ddp/docs/zh.md)：rank、world size 的概念与参数复制。
- [阶段 19 · 48 从零实现分布式数据并行与 FSDP](../../48-distributed-fsdp-ddp/docs/zh.md)：FSDP 的分片方式决定了 checkpoint 的布局。
- [阶段 10 · 05 扩展：分布式训练、FSDP、DeepSpeed](../../../10-llms-from-scratch/05-scaling-distributed/docs/zh.md)：混合精度 Adam 每参数 16 字节的内存账。

### 本节被哪些后续内容用到
- [阶段 19 · 81 端到端分布式训练](../../81-end-to-end-distributed-train/docs/zh.md)：在 DDP + ZeRO-1 训练中途保存分片 checkpoint 并验证恢复。
- [阶段 17 · 24 LLM 生产环境中的混沌工程](../../../17-infrastructure-and-production/24-chaos-engineering-llm/docs/zh.md)：故意注入节点故障，检验 checkpoint/恢复链路。
- [阶段 17 · 23 AI 的 SRE](../../../17-infrastructure-and-production/23-sre-for-ai/docs/zh.md)：恢复时间目标、操作手册与演练。

### 延伸关键词
`torch.distributed.checkpoint (DCP)` · `DeepSpeed save_checkpoint / latest` · `zero_to_fp32` · `fsync / O_DIRECT` · `crash consistency` · `commit point` · `two-tier storage` · `async checkpointing` · `resharding` · `weights_only / safetensors` · `RTO / RPO`
