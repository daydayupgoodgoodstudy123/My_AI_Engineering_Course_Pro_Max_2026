---
name: checkpoint-save-resume
description: Atomic, sharded checkpoints with full RNG capture so a killed run resumes mid-epoch with the same loss trajectory.
version: 1.0.0
phase: 19
lesson: 47
tags: [training, durability, resume, sharded-state]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="when-to-use"></a>

## 何时使用

任何训练都比集束的墙上盖长 任何必须维持节点重开的飞行 任何模型都太大 无法承受一个有效载荷

<a id="payload-shape"></a>

## 有效载荷形状

```python
{
  "schema": "ckpt.v1",
  "model": model.state_dict(),
  "optimizer": opt.state_dict(),
  "scheduler": sched.state_dict(),
  "state": {"step": int, "epoch": int, "batch_in_epoch": int, "losses": [float, ...]},
  "rng": {"python": ..., "numpy": ..., "torch_cpu": ..., "torch_cuda": ...},
  "wall_saved_at": time.time(),
}
```

<a id="atomic-save"></a>

## 原子保存

1. 将有效载荷写入目标所在的同一目录中的独特临时文件。
2. `os.replace(tmp, target)` 来交换原子。
3. 千万不要直接写到目标名

<a id="sharded-layout"></a>

## 碎版版版式

- `model.shard-NNN.pt` 每片碎片, 键上的圆 Robin 或者被分割 parameter group.
- `meta.pt` carries optimizer,排程器,列车状态,RNG,和散装货单。
- `index.json` carries `sha256` 每一片石头和每片石头 `meta.pt`.
- 装入器在合并和拒绝外部的碎条路径前验证每个散列 checkpoint directory.
- 装入每个文件 `torch.load(path, map_location="cpu", weights_only=True)`。保持 RNG 状态为普通列表,以便它能生存下来 weights-只有装货机

<a id="mid-epoch-resume"></a>

## Mid-epoch resume

- Save `(epoch, batch_in_epoch)` 旁边 `step`.
- 在第一批恢复之前恢复 RNG 状态 epoch.
- 发电机过去消耗的批量

<a id="failure-modes"></a>

## 失效模式

- 交叉设置重命名: 不是原子, 丢失上一个文件。 请将临时设置在同一目录中 。
- 忘记RNG: 恢复的损失与基线不同。运行演示的主张 。
- Forgetting optimizer 状态:下一步,阴茎。同样的阴茎会爆炸。
- 摆弄错 checkpoint:保持最后K+最佳状态。
- 装入 `weights_only=False`: 一个 `.pt` 文件是泡菜,所以不可信 checkpoint 运行载荷代码 。
