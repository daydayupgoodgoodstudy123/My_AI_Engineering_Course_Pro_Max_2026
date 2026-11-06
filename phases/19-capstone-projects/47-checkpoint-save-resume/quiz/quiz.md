# 测验 · Checkpoint 保存与恢复（Checkpoint Save and Resume）

> **阶段 19 · 综合项目 · 第 47 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py)、[code/test_main.py](../code/test_main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)（测试并入该讲解第 9 节）
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 五类状态 | 模型（权重与 buffer）、优化器（动量、Adam 矩估计）、调度器（lr 曲线位置）、训练计数（step、epoch、batch_in_epoch、loss 历史）、RNG 状态 |
| 2 | 为什么要存优化器 | 只恢复权重而丢掉 AdamW 的矩估计，下一步"朝训练轨迹早已离开的方向猛冲"；本节实测少存优化器后续 loss 最大偏差 0.063 |
| 3 | 原子保存 | 先写到**同目录**下唯一命名的临时文件，再 `os.replace` 成目标名；崩溃发生在 rename 前，旧文件完好；POSIX 上同一文件系统内的 rename 是原子的 |
| 4 | 原子 ≠ 持久 | rename 原子只保证"要么旧要么新"，断电后数据是否落盘还依赖 `fsync`（文件与目录）；本节代码没有 fsync |
| 5 | 安全加载 | `.pt` 是 pickle；`torch.load(..., weights_only=True)` 只接受张量和基础容器，拒绝任意对象；讲义要求 torch ≥ 2.6 |
| 6 | RNG 状态存成纯列表 | NumPy 的 key 数组 `tolist()`、torch RNG 字节 `tolist()`，这样 weights-only 加载器能读回 |
| 7 | 分片 checkpoint | 参数按键轮询分到 N 个 `model.shard-NNN.pt`，`meta.pt` 存优化器/调度器/计数/RNG 和分片清单，`index.json` 存 meta 的 sha256；加载时逐一校验哈希并拒绝逃出目录的路径 |
| 8 | 断点续训到 epoch 中间 | 保存 `(epoch, batch_in_epoch)`；数据生成器按 `12345 + epoch` 重新播种，再"快进"跳过已消费的 batch |
| 9 | schema 字段 | 格式演进的钩子：加载时按版本分支迁移；本节代码只做了 `startswith("ckpt")` 的弱检查 |
| 10 | 验证方式 | 不中断训练与"中断—保存—新进程恢复"训练的中断后 loss 序列最大差 < 1e-4（本节实测为 0.0） |

### 核心技能（能动手做到）

- [ ] 写出包含五类状态的 checkpoint payload，并在新进程中完整恢复
- [ ] 实现"同目录临时文件 + `os.replace`"的原子写，并补上 `fsync` 让它在断电下也可靠
- [ ] 用 `weights_only=True` 安全加载，并说明为什么 RNG 状态要转成纯列表
- [ ] 设计并实现带 sha256 校验与路径约束的分片 checkpoint 与索引
- [ ] 用"消融实验"判断某类状态在当前训练中是否真的必要（去掉它，看恢复后的 loss 是否偏离）
- [ ] 识别 checkpoint 恰好落在 epoch 边界时"epoch 中间恢复"并未被测试到的问题

---

## 二、基础自测（选择题）

**Q1.** 讲义说如果只恢复模型权重、不恢复优化器状态，"the next step lurches in a direction the training trajectory had already moved past"。对于 AdamW，丢失的主要是：

- A. 学习率调度的当前位置
- B. 随机数生成器状态
- C. 每个参数的一阶矩（动量）与二阶矩估计，以及步数计数（影响偏差修正）
- D. 模型的 buffer（如 BatchNorm 的滑动均值）

**Q2.** `atomic_save` 把临时文件放在**目标文件所在目录**，而不是系统的 `/tmp`。原因是：

- A. 跨文件系统（跨设备）的 rename 不是原子的，甚至会失败；同目录保证 `os.replace` 在同一文件系统内完成
- B. `/tmp` 的写入速度更慢
- C. `tempfile` 模块不支持 `/tmp`
- D. 为了让 sha256 与目标文件相同

**Q3.** `load_checkpoint` 使用 `torch.load(path, map_location="cpu", weights_only=True)`，其中 `weights_only=True` 的作用是：

- A. 只加载模型权重，忽略优化器和调度器
- B. 加载得更快，因为跳过了反序列化
- C. 自动把权重转换为 FP16
- D. 只允许反序列化张量与基础容器（dict、list、tuple、数字、字符串等），遇到任意 Python 对象就拒绝，防止恶意 `.pt` 文件在加载时执行代码

**Q4.** 默认参数 `--total-steps 24 --interrupt-at 10`，`batches_per_epoch = 5`。保存 checkpoint 时 `TrainState` 的 `(step, epoch, batch_in_epoch)` 是：

- A. `(10, 1, 5)`
- B. `(10, 2, 0)`
- C. `(10, 2, 5)`
- D. `(9, 1, 4)`

**Q5.** `train_until` 是怎样从 epoch 中间继续的？

- A. 从 checkpoint 中读取数据生成器的内部状态
- B. 用 `12345 + epoch` 重新播种该 epoch 的数据生成器，然后空跑生成 `batch_in_epoch` 个 batch 丢弃，再继续取下一个 batch
- C. 从 `losses` 列表的长度推算数据位置
- D. 跳到下一个 epoch 的开头继续

**Q6.** `load_sharded_checkpoint` 的完整性校验链是：

- A. 只检查 `index.json` 中的 `num_shards` 是否等于实际文件数
- B. 逐个分片检查 schema 字符串，不计算哈希
- C. 先加载所有分片，合并后再整体计算一个哈希
- D. 用 `index.json` 中的 `meta_sha256` 校验 `meta.pt` → 从已校验的 meta 中取分片清单 → 每个分片先检查路径不逃出目录、再校验 sha256、再检查 schema，全部通过才合并

**Q7.** `capture_rng_state` 把 NumPy 的 key 数组和 torch 的 RNG 字节都用 `.tolist()` 转成 Python 列表，主要是为了：

- A. 让 `weights_only=True` 的加载器能够读回（它不接受 NumPy 数组这类任意对象）
- B. 减小文件体积
- C. 让 JSON 能够序列化
- D. 加快随机数生成速度

**Q8.** `load_checkpoint` 的 schema 检查是 `str(payload.get("schema", "")).startswith("ckpt")`。下列哪些 schema 字符串**都会被接受**？

- A. 只有 `"ckpt.v1"`
- B. `"ckpt.v1"` 与 `"ckpt.v1-sharded"`，但不包括 `"ckpt-shard.v1"`
- C. `"ckpt.v1"`、`"ckpt.v1-sharded"`、`"ckpt-shard.v1"`、`"ckpt.v99"` 都会被接受
- D. 任何字符串都会被接受

---

## 三、动手 / 代码题

**Q9.** 消融实验：在 `run_resume_demo(total_steps=24, interrupt_at=7, seed=11)` 中（单文件模式），分别让恢复时**不恢复 RNG 状态**、**不加载优化器状态**、**不加载调度器状态**，其余不变。

1. 预测三种情况下中断后 loss 序列的最大差（0 还是明显大于 0），并解释。
2. 如果"不恢复 RNG"时最大差仍是 0，这说明本节 demo 没能验证讲义的哪条主张？
3. 怎样修改模型或数据，让 demo 真正检验 RNG 恢复？

**Q10.** 讲义说"Resume continues mid epoch… The lesson code does this exactly"。

1. 默认参数（`interrupt_at=10`、每 epoch 5 个 batch）下，checkpoint 是否落在 epoch 中间？
2. 测试 `test_mid_epoch_resume_continues_deterministically` 使用 `total_steps=14, interrupt_at=5`（每 epoch 5 个 batch），它真的测到了 epoch 中间恢复吗？哪个测试实际覆盖了 epoch 中间恢复？
3. 给出修正建议，并写出 `interrupt_at` 在 `[1, 23]` 中哪些取值会落在 epoch 中间。

**Q11.** 阅读 `atomic_save`：

```python
def atomic_save(payload, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = tempfile.NamedTemporaryFile(delete=False, dir=str(path.parent),
                                      prefix=path.name + ".", suffix=".tmp")
    tmp_path = Path(tmp.name)
    tmp.close()
    try:
        torch.save(payload, tmp_path)
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except FileNotFoundError:
                pass
    return path
```

1. 进程在 `torch.save` 写到一半时被 `SIGKILL`，目录里会留下什么？旧的 `ckpt.pt` 还在吗？
2. 机器在 `os.replace` 刚返回后断电，重启后 `ckpt.pt` 一定是新内容吗？为什么讲义的延伸阅读提到了 `fsync`？
3. 改写这个函数，补上必要的 `fsync`，并给出启动时清理孤儿临时文件的做法。

**Q12.** 讲义练习 2 与练习 5：

1. 写一个 `save_rotating(model, opt, sched, state, ckpt_dir, keep_last=3)`：文件按 step 命名（如 `ckpt-000010.pt`），保存后只保留最近 K 个，并维护一个原子更新的 `latest` 指针文件。
2. 写一个 `migrate_v1_to_v2(payload)`：v2 新增字段 `"data": {"seed_base": 12345}`，并让 `load_checkpoint` 同时接受 v1 与 v2（v1 先迁移再加载），未知版本明确报错。

---

## 四、面试高频题

**Q13.**（基础必考）一个训练 checkpoint 应该包含哪些内容？只保存 `model.state_dict()` 有什么问题？

**Q14.**（原理深挖）如何保证 checkpoint 写入是原子且持久的？`os.replace`、`fsync`、目录 `fsync` 分别解决什么问题？

**Q15.**（工程实践）为什么说加载来路不明的 `.pt` 文件有安全风险？你会采取哪些措施？

**Q16.**（场景设计）一个 18 小时的训练任务跑在单次最长 4 小时、且可能被随时抢占的集群上。请设计完整的 checkpoint 与恢复策略。

**Q17.**（追问型）"恢复后 loss 曲线与不中断时完全一致"在实际 GPU 多卡训练中能做到吗？哪些因素会破坏它？你会怎么验证恢复的正确性？

---

## 五、参考答案与解析

### Q1 — 答案：C

AdamW 的 `state_dict()` 中每个参数有 `exp_avg`（一阶矩）、`exp_avg_sq`（二阶矩）和 `step`。丢失后优化器从零重新估计：偏差修正按 t = 1 计算，第一步更新幅度约为 lr 量级、方向只由当前梯度决定。本节消融实测：恢复时不加载优化器状态，中断后 loss 最大偏差 0.063。A 是调度器（丢失它的实测偏差为 0.055）；B 是 RNG；D 是模型 buffer，属于 `model.state_dict()`。

### Q2 — 答案：A

讲义："the temporary file lives in the same directory as the target so the rename stays within the same file system; cross-device renames are not atomic."（Python 的 `os.replace` 跨设备时直接抛 `OSError`。）B、C 不成立；D 错，sha256 与文件所在位置无关。

### Q3 — 答案：D

讲义："A `.pt` file is a pickle, and unpickling an untrusted file with `weights_only=False` runs whatever code the file names. The weights-only loader accepts tensors and primitive containers and rejects everything else." 测试 `test_load_refuses_pickled_objects` 保存一个含自定义类实例的 payload，加载时得到 `pickle.UnpicklingError`。A 是常见的字面误解——它照样能加载优化器和调度器的 state_dict（它们只含张量和基础类型）。讲义还提示 torch 2.6 之前该选项存在已知绕过（CVE-2025-32434）。

### Q4 — 答案：B

已实测（在 `save_checkpoint` 处打印）：`saved state 10 2 0`。第二个 epoch 的内层循环在 `batch_in_epoch == 5` 时结束，随后 `if state.batch_in_epoch >= batches_per_epoch` 把 epoch 加 1、batch_in_epoch 归零，然后外层 `while state.step < stop_step` 因 `10 < 10` 为假而退出。A、C 是"还没来得及进位"的状态，代码不会以这种状态返回。这意味着默认 demo 的 checkpoint 恰好落在 **epoch 边界**（见 Q10）。

### Q5 — 答案：B

```python
        gen = torch.Generator()
        gen.manual_seed(12345 + state.epoch)
        for _ in range(state.batch_in_epoch):
            torch.randn(batch_size, in_dim, generator=gen)
            torch.randint(low=0, high=out_dim, size=(batch_size,), generator=gen)
```

数据顺序是 `(epoch, batch_in_epoch)` 的确定函数，所以不需要保存生成器状态，只要重新播种再"快进"即可。A 错，checkpoint 里没有这个生成器的状态；C、D 不是代码的做法。代价是快进需要真的生成被跳过的数据（对大数据集可改为记录偏移量或保存生成器状态）。

### Q6 — 答案：D

`index.json` → `meta_sha256` 校验 `meta.pt`；然后用 **meta 中**的 `shards` 列表（而不是 index 中的副本）逐个：`resolve()` 后 `is_relative_to(root)` 检查路径、`file_sha256` 比对、加载后检查 `schema == SHARD_SCHEMA`，最后 `merged.update(...)`。index 中的 `num_shards` 和 `shards` 实际上没有被用于校验（A 错）。测试 `test_sha_mismatch_is_detected`（篡改分片末尾加一个字节）和 `test_shard_path_outside_checkpoint_dir_is_rejected`（把路径改成 `../outside.pt` 并重算 meta 哈希）分别覆盖了哈希与路径两道关。

### Q7 — 答案：A

讲义："Every piece is stored as plain Python numbers, tuples, and lists (NumPy's key array goes through `tolist()`), so the loader in Step 3 can read it back without unpickling arbitrary objects." NumPy 数组不在 weights-only 的允许列表中。B 错，列表在 pickle 中通常比紧凑的数组更大（本节实测 torch CPU RNG 状态是 5,056 个整数）；C 错，这些 payload 是 `torch.save` 写的，不是 JSON；D 无关。补充：torch 张量本身是允许的，所以 torch RNG 状态其实可以直接存成张量，`tolist()` 对它不是必需的。

### Q8 — 答案：C

`startswith("ckpt")` 对所有以 `ckpt` 开头的字符串都为真。已实测：用 `schema="ckpt-shard.v1"` 的 payload 调用 `load_checkpoint` 照样成功加载。讲义说"the schema field is the upgrade hook: future format changes bump the version string and the loader dispatches"，但代码没有任何分派逻辑，未来的 `ckpt.v2` 会被当成 v1 加载。正确做法是对已知版本做精确匹配并分别迁移（Q12）。

### Q9 — 参考答案

1. 实测（`interrupt_at=7`，checkpoint 状态为 step 7、epoch 1、batch_in_epoch 2，确实在 epoch 中间）：
   - **不恢复 RNG**：最大差 **0.0**。
   - **不加载优化器**：最大差 **0.0634**——AdamW 矩估计归零，后续更新完全不同。
   - **不加载调度器**：最大差 **0.0551**——`CosineAnnealingLR` 从 `last_epoch=0` 重新开始，学习率回到 0.01 而不是第 7 步时的值。
2. RNG 恢复"看起来没用"，因为本 demo 中**没有任何东西消费全局 RNG**：模型没有 Dropout，数据来自独立的 `torch.Generator`（用 `12345 + epoch` 播种），Python `random` 和 NumPy 全程未被使用。所以讲义"Restore the RNG state… so the post-resume loss matches the uninterrupted baseline"这一主张在 demo 中**没有被检验**——删掉 `restore_rng_state` 测试也照样通过。
3. 让训练过程消费全局 RNG。例如在模型中加入 `nn.Dropout(0.2)`：实测恢复 RNG 时最大差仍为 0.0，不恢复时为 **0.0611**。也可以让数据打乱使用 `torch.randperm`（全局 RNG）或 `random.shuffle`。然后增加一个"去掉 RNG 恢复后差异必须 > 0"的负面测试，证明这条代码路径是被需要的。

### Q10 — 参考答案

1. **不是**。`10 % 5 == 0`，保存时状态为 `(step=10, epoch=2, batch_in_epoch=0)`，恢复时快进 0 个 batch，等价于"从下一个 epoch 开头开始"。
2. 也没有：`interrupt_at=5`、每 epoch 5 个 batch，保存时状态为 `(5, 1, 0)`（已实测），同样是 epoch 边界——测试名说"mid_epoch"，实际测的是边界。真正覆盖 epoch 中间恢复的是 `test_sharded_round_trip`（`interrupt_at=4`，保存时 `batch_in_epoch = 4`），而且只覆盖了分片路径。
3. 修正：把默认值和单文件测试改成不能被 `batches_per_epoch` 整除的值（如 7），并在测试中显式断言 `loaded.batch_in_epoch > 0`，避免以后有人改参数时悄悄退化成边界测试。`[1, 23]` 中除 5、10、15、20 之外的所有取值都落在 epoch 中间（共 19 个）。实测 `interrupt_at=7` 时最大差仍为 0.0，快进逻辑本身是正确的。

### Q11 — 参考答案

1. 留下一个形如 `ckpt.pt.xxxxxxxx.tmp` 的**孤儿临时文件**（`SIGKILL` 不会执行 `finally`），内容是写了一半的数据；旧的 `ckpt.pt` 完好无损，因为它从未被打开写入。这正是原子保存的价值：读者永远看不到半个文件。
2. **不一定**。`os.replace` 原子地修改了目录项，但 `torch.save` 写入的数据可能还在操作系统页缓存中、没有落盘；某些文件系统在断电后可能出现"新名字指向长度为 0 或不完整的文件"。rename 本身（目录的修改）也可能没有持久化，重启后看到的仍是旧文件。所以讲义的延伸阅读提到"the Linux kernel `fsync` documentation for the durability guarantee behind atomic rename"——要保证持久，需要先 fsync 文件、rename 后再 fsync 目录。
3. 改写：

```python
def atomic_save(payload, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as f:
            torch.save(payload, f)
            f.flush()
            os.fsync(f.fileno())                 # 1. 数据落盘
        os.replace(tmp_path, path)               # 2. 原子替换
        dir_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)                     # 3. 目录项落盘（POSIX）
        finally:
            os.close(dir_fd)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
    return path


def clean_orphans(ckpt_dir: Path, max_age_s: float = 3600) -> list[Path]:
    """启动时清理上次被杀死留下的临时文件（只删足够旧的，避免误删并发写入中的文件）。"""
    removed = []
    for p in ckpt_dir.glob("*.tmp"):
        if time.time() - p.stat().st_mtime > max_age_s:
            p.unlink(); removed.append(p)
    return removed
```

   要点：fsync 有成本（大 checkpoint 可能数秒），通常只在周期性保存时做；目录 fsync 在 Windows 上不可用，需要按平台处理。

### Q12 — 参考答案

1. 滚动保存：

```python
def save_rotating(model, opt, sched, state, ckpt_dir: Path, keep_last: int = 3) -> Path:
    if keep_last < 1:
        raise ValueError("keep_last must be >= 1")
    target = ckpt_dir / f"ckpt-{state.step:06d}.pt"
    save_checkpoint(model, opt, sched, state, target)          # 原子写入
    atomic_write_json({"latest": target.name, "step": state.step}, ckpt_dir / "latest.json")
    ckpts = sorted(ckpt_dir.glob("ckpt-*.pt"))                  # 零填充保证字典序 = 数值序
    for old in ckpts[:-keep_last]:
        old.unlink()
    return target
```

   顺序很重要：先写新 checkpoint、再更新 `latest` 指针、最后删旧文件，任何一步崩溃都至少留下一个完整可用的 checkpoint。磁盘紧张时 K 至少为 2（防止最新的那个恰好损坏），讲义 skill 文件建议"keep last K plus best"。

2. 迁移：

```python
def migrate_v1_to_v2(payload: dict) -> dict:
    if payload.get("schema") != "ckpt.v1":
        raise ValueError(f"expected ckpt.v1, got {payload.get('schema')}")
    out = dict(payload)
    out["data"] = {"seed_base": 12345}
    out["schema"] = "ckpt.v2"
    return out

MIGRATIONS = {"ckpt.v1": migrate_v1_to_v2}

def load_checkpoint(path, model, optimizer, scheduler):
    payload = torch.load(path, map_location="cpu", weights_only=True)
    schema = payload.get("schema")
    while schema in MIGRATIONS:                  # 逐级迁移到最新版本
        payload = MIGRATIONS[schema](payload)
        schema = payload["schema"]
    if schema != "ckpt.v2":
        raise ValueError(f"unknown schema {schema!r}")
    ...                                          # 其余与原实现相同
```

   要点：精确匹配版本、逐级迁移、未知版本报错；迁移函数是纯函数，便于对旧 checkpoint 样本写回归测试。

### Q13 — 参考回答要点

- **五类状态**（讲义表格）：
  - 模型：参数与 buffer（`model.state_dict()`）；
  - 优化器：动量、Adam 矩估计、step 计数；
  - 调度器：`last_epoch` 等，决定 lr 在曲线上的位置；
  - 训练计数：step、epoch、batch_in_epoch，以及 loss 历史；
  - RNG：Python、NumPy、torch CPU/CUDA 的生成器状态。
- 另加 schema 版本与保存时间等元数据；混合精度时还有 GradScaler 状态（第 45 节）；梯度累积时应在有效步边界保存（第 46 节）。
- **只存模型的问题**：优化器矩估计丢失导致恢复后更新方向与幅度突变（本节实测 loss 偏差 0.063）；调度器从头开始，学习率跳回峰值甚至重新 warmup（实测偏差 0.055）；数据位置丢失导致重复或跳过数据；RNG 丢失导致 Dropout 掩码、数据打乱不同。
- 加分点：说明哪些状态"必需"可以用消融实验验证；loss 历史在长训练中会线性增长，生产中更适合写到独立的日志系统而不是塞进 checkpoint。

### Q14 — 参考回答要点

- **问题**：直接写目标文件时，崩溃会留下半个文件，恢复时读到垃圾（讲义）。
- **`os.replace`**：把同目录临时文件原子地改名为目标名，任何时刻读者看到的要么是完整旧文件、要么是完整新文件；要求同一文件系统（同目录最稳妥）；临时文件名每次唯一，避免两个写者互相覆盖。
- **文件 `fsync`**：保证临时文件的数据在 rename 之前已经写到磁盘，而不只是在页缓存里；否则断电后可能出现"新名字、空内容"。
- **目录 `fsync`**：rename 修改的是目录项，目录本身也需要 fsync，rename 才是持久的。
- **崩溃时的遗留**：rename 前崩溃 → 旧文件完好 + 孤儿 `.tmp`；需要启动时清理。
- **代价与取舍**：fsync 会阻塞，大 checkpoint 可放到后台线程/进程中做（先把状态复制到 CPU 内存，再异步写盘），但要保证同一时刻只有一个保存在进行。
- 常见误区：认为"rename 原子 = 数据安全"；把临时文件放在 `/tmp`（常是另一个文件系统，跨设备 rename 失败或退化成复制）。

### Q15 — 参考回答要点

- **风险**：`torch.save` 默认使用 pickle。pickle 反序列化可以调用任意可调用对象（`__reduce__`），一个恶意 `.pt` 在 `torch.load` 时就能执行代码。讲义："A checkpoint pulled from a shared drive or a download is untrusted input."
- **措施**：
  - 始终 `weights_only=True`（只允许张量与基础容器），并使用讲义要求的 torch 2.6 及以上版本；
  - 让 checkpoint 只包含这类安全类型（本节把 RNG 状态转成纯列表就是为此）；
  - 对分片和 meta 做 sha256 校验，哈希清单从可信渠道获得；
  - 分片路径做目录约束，防止 `../` 路径穿越；
  - 对外分发权重时优先使用不含可执行逻辑的格式（如 safetensors）；
  - 用 `ValueError` 而不是 `assert` 做完整性检查——`python -O` 会移除 assert（讲义原话）。
- 加分点：能指出 `index.json` 自身没有签名——哈希只能防"意外损坏"，防"恶意篡改"需要签名或可信存储。

### Q16 — 参考回答要点

- **保存节奏**：讲义："Save every N steps and every wallclock-minute, whichever is shorter."——例如每 1,000 步或每 15 分钟；另外在收到抢占信号（如 SIGTERM）时立即保存一次。
- **保存内容**：五类状态 + GradScaler + 数据位置（epoch、batch_in_epoch 或样本偏移）+ 配置哈希与 schema 版本。
- **原子与持久**：同目录临时文件 + fsync + `os.replace` + 目录 fsync；大模型用分片 + 索引 + sha256。
- **保留策略**：保留最近 K 个（K ≥ 2）+ 验证集最优的一个；`latest` 指针原子更新；旧文件在新文件确认写好后再删除。
- **恢复流程**：启动时扫描目录 → 清理孤儿 `.tmp` → 从 `latest` 开始逐个校验哈希，选最新的完整 checkpoint（讲义练习 4）→ 加载全部状态 → 断言配置一致 → 从 `(epoch, batch_in_epoch)` 继续。
- **4 小时上限**：在上限前留出余量主动保存并退出，由调度系统自动重新提交任务。
- **验证**：上线前做"中断—恢复"回归测试，比较中断后 loss 序列（本节阈值 1e-4）。
- 加分点：异步保存减少训练停顿；多卡时每个 rank 只写自己的分片，由 rank 0 写索引（第 48、80 节）。

### Q17 — 参考回答要点

- **单机 CPU 小模型**（本节）：可以做到位级一致（实测最大差 0.0），因为所有随机性都可控、计算确定。
- **破坏因素**：
  - GPU 上非确定性的算子（如部分使用原子加法的反向实现）；需要开启确定性算法开关，代价是变慢；
  - DataLoader 多进程 worker 的随机状态与预取队列：worker 的 RNG、已经预取但未消费的 batch 都要处理；
  - 分布式训练：all-reduce 的归约顺序、不同的 world size 恢复；
  - 混合精度：GradScaler 状态若未保存，恢复后会重新从初始缩放开始，跳过步不同；
  - 恢复时改了 batch size、accum 或代码版本。
- **验证方法**：
  - 讲义做法：同一配置下"不中断"与"中断后恢复"两条 loss 曲线在中断后的最大差小于阈值（1e-4）；
  - 消融：去掉某类状态，差异必须变大（证明该状态被正确保存并被使用，见 Q9）；
  - 在 epoch 中间和 epoch 边界都做测试（见 Q10）；
  - 恢复后检查 lr、step、GradScaler 缩放因子与中断前一致。
- 常见误区：只要求"loss 曲线看起来连续"，而不比较数值；或者只在 epoch 边界测试恢复。

---

## 六、关联知识点

### 前置知识
- [阶段 19 · 44 带线性 Warmup 的余弦学习率](../../44-cosine-lr-warmup/docs/zh.md)：调度器与 `global_step` 必须随 checkpoint 一起保存。
- [阶段 19 · 45 Gradient Clipping 与 Mixed Precision](../../45-gradient-clipping-amp/docs/zh.md)：GradScaler 状态也是训练状态的一部分。
- [阶段 19 · 46 Gradient Accumulation](../../46-gradient-accumulation/docs/zh.md)：在有效步边界保存，累积窗口不应被切断。
- [阶段 19 · 43 HDF5 格式的分词语料](../../43-hdf5-tokenized-corpus/docs/zh.md)：数据位置（epoch、batch 偏移）的来源。
- [阶段 00 · 09 数据管理](../../../00-setup-and-tooling/09-data-management/docs/zh.md)：文件、存储与数据完整性的基础。

### 本节被哪些后续内容用到
- [阶段 19 · 48 从零实现分布式数据并行与 FSDP](../../48-distributed-fsdp-ddp/docs/zh.md)：分布式包装器的 state_dict 格式。
- [阶段 19 · 80 分片 Checkpoint 与原子恢复](../../80-checkpoint-sharded-resume/docs/zh.md)：多 rank 分片 checkpoint 的完整版本。
- [阶段 19 · 81 端到端分布式训练](../../81-end-to-end-distributed-train/docs/zh.md)：把 checkpoint 与分布式训练循环组合。
- [阶段 15 · 16 Checkpoints（检查点）与 Rollback（回滚）](../../../15-autonomous-systems/16-checkpoints-rollback/docs/zh.md)：同样的"保存状态、可回滚"思想用于自主系统。
- [阶段 10 · 05 扩展：分布式训练、FSDP、DeepSpeed](../../../10-llms-from-scratch/05-scaling-distributed/docs/zh.md)：大规模训练中的 checkpoint 分片。

### 延伸关键词
`state_dict` · `os.replace` · `fsync` · `atomic rename` · `weights_only` · `pickle security` · `safetensors` · `sha256 manifest` · `sharded checkpoint` · `RNG state` · `mid-epoch resume` · `schema migration` · `keep last K` · `preemption / SIGTERM`
