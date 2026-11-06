---
name: skill-linear-probe-runner
description: Write the complete linear-probe evaluation for any frozen encoder and labelled dataset
version: 1.0.0
phase: 4
lesson: 17
tags: [self-supervised, evaluation, linear-probe, pytorch]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="linear-probe-runner"></a>

# 线性探针运行器

通过在顶部训练单个线性分类器来评估冻结的 encoder 的 features。每篇自我监督论文的标准 evaluation。

<a id="when-to-use"></a>

## 何时使用

- 比较自监督checkpoints。
- 在 pretraining 历元内跟踪 feature 质量。
- 决定预训练的 encoder 是否足以胜任没有 fine-tuning 的下游任务。

<a id="inputs"></a>

## 输入

- `encoder`：冻结的 `nn.Module` 返回每个图像的固定暗淡 feature。
- `feature_dim`：encoder 输出的维数。
- `train_dataset`：标记数据集（图像，class_id）。
- `val_dataset`：保留集。
- `num_classes`：任务类。
- `epochs`：对于 ImageNet 规模，通常为 100，对于较小的数据集，通常为 50。

<a id="steps"></a>

## 步骤

1. 将 encoder 设置为 eval 模式，并在每个 parameter 上设置 `requires_grad=False`。
2. Feature-将train和val集都提取一次。存储为 numpy 数组或内存映射文件。
3. 使用 SGD + 余弦时间表在缓存的 features 上训练 `nn.Linear(feature_dim, num_classes)`。
4. 标准hyperparameters：`lr=0.1`、`momentum=0.9`、`weight_decay=0`、`batch_size=1024`。线性探头对 `lr` 非常敏感 — 如果精度较差则进行扫描。
5. 在训练结束时报告 val 的 top-1 准确率。

<a id="output-template"></a>

## 输出模板

```python
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader
from torch.optim import SGD
from torch.optim.lr_scheduler import CosineAnnealingLR

def extract(encoder, loader, device="cpu"):
    encoder.eval()
    feats, labels = [], []
    with torch.no_grad():
        for x, y in loader:
            f = encoder(x.to(device)).cpu()
            feats.append(f)
            labels.append(y)
    return torch.cat(feats), torch.cat(labels)


def linear_probe(encoder, feature_dim, train_loader, val_loader,
                 num_classes, epochs=50, lr=0.1, device="cpu"):
    for p in encoder.parameters():
        p.requires_grad = False

    f_train, y_train = extract(encoder, train_loader, device)
    f_val, y_val = extract(encoder, val_loader, device)

    head = nn.Linear(feature_dim, num_classes).to(device)
    opt = SGD(head.parameters(), lr=lr, momentum=0.9, weight_decay=0)
    sched = CosineAnnealingLR(opt, T_max=epochs)

    ds = torch.utils.data.TensorDataset(f_train, y_train)
    train_iter = DataLoader(ds, batch_size=1024, shuffle=True)

    best_val = 0.0
    for ep in range(epochs):
        head.train()
        for x, y in train_iter:
            x, y = x.to(device), y.to(device)
            loss = F.cross_entropy(head(x), y)
            opt.zero_grad(); loss.backward(); opt.step()
        sched.step()

        head.eval()
        with torch.no_grad():
            acc = (head(f_val.to(device)).argmax(-1).cpu() == y_val).float().mean().item()
        best_val = max(best_val, acc)
    return best_val
```

<a id="report"></a>

## 报告

```
[linear probe]
  encoder:     <name + pretrain checkpoint>
  feature_dim: <int>
  epochs:      <int>
  best_val_top1: <float>
```

<a id="rules"></a>

## 规则

- 线性探测期间切勿更新 encoder weights；这将是一次微调，而不是一次探索。
- 预计算一次features；在每个 epoch 上重新训练 encoder 会浪费 100 倍的计算量。
- 使用带有余弦时间表的 SGD，并且没有 weight decay； Adam 有时在这里表现不佳。
- 每个encoder家族至少扫描一次learning rates；最佳值因 SSL 方法而异。
