---
name: distributed-fsdp-ddp
description: Bring up multi-rank training with a from-scratch DDP wrapper and an FSDP parameter sharding sketch on the gloo or nccl backend.
version: 1.0.0
phase: 19
lesson: 48
tags: [distributed, ddp, fsdp, collectives]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="when-to-use"></a>

## 何时使用

该模型适合一个设备,但您需要更多的传输( DDP) 。 该模型不适合一个设备( FSDP) 。 任何一种情况: 设置多级培训, 使用相同的代码路径 。

<a id="bring-up-the-process-group"></a>

## 启动进程组

```python
os.environ["MASTER_ADDR"] = "127.0.0.1"
os.environ["MASTER_PORT"] = str(port)
dist.init_process_group(backend="gloo", rank=rank, world_size=world_size)
```

`gloo` 是该 CPU backend; `nccl` 是该 GPU 后端。 两者执行相同的集体表面 。

<a id="wrap-the-model"></a>

## 绕开模型

1. 在0级,从你的种子建立模型。
2. 把它包在DDP壳上
3. 贝壳 `__init__` calls `dist.broadcast(p.data, src=0)` 用于每 parameter 和缓冲。
4. 之后的每一个 `loss.backward()`教练打电话来 `sync_grads()`.
5. `sync_grads()` calls `dist.all_reduce(p.grad, op=SUM)` 和 `p.grad.div_(world_size)`.
6. Optimizer 每一个级别都站在同一位 gradient.

<a id="shard-parameters-fsdp-sketch"></a>

## Shard parameters (FSPD草图)

1. 各自平开 parameter,将 `world_size`.
2. 将您的碎片保留在本地; 释放 rest.
3. 前面说 `dist.all_gather(...)` 重建整个 tensor 每一个级别。
4. 向前,把满的放下 tensor.

<a id="failure-modes"></a>

## 失效模式

- 跳过广播: 排名从不同的字母开始, 悄悄地变换。
- 忘记将之分为两部分: gradients 按世界规模_size, optimizer 脚步太大了
- 使用交叉设备重命名 checkpoints:不是原子;同样的课程47陷阱。
- Mixing CPU 和 CUDA tensors 在同一组:后端不匹配,运行挂。
