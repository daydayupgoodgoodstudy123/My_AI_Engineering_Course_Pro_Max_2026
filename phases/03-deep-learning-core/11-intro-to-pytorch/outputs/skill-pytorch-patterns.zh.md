---
name: skill-pytorch-patterns
description: Reference patterns for PyTorch training, evaluation, and deployment
version: 1.0.0
phase: 03
lesson: 11
tags: [pytorch, training, deep-learning, gpu, patterns]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="canonical-training-loop"></a>

## 规范训练循环

```python
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = Model().to(device)
criterion = nn.CrossEntropyLoss()
optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=0.01)

for epoch in range(num_epochs):
    model.train()
    for inputs, targets in train_loader:
        inputs, targets = inputs.to(device), targets.to(device)
        optimizer.zero_grad()
        outputs = model(inputs)
        loss = criterion(outputs, targets)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()

    model.eval()
    with torch.no_grad():
        for inputs, targets in val_loader:
            inputs, targets = inputs.to(device), targets.to(device)
            outputs = model(inputs)
```

<a id="mixed-precision-training"></a>

## Mixed Precision 培训

```python
from torch.amp import autocast, GradScaler

scaler = GradScaler()
for inputs, targets in train_loader:
    inputs, targets = inputs.to(device), targets.to(device)
    optimizer.zero_grad()
    with autocast(device_type="cuda"):
        outputs = model(inputs)
        loss = criterion(outputs, targets)
    scaler.scale(loss).backward()
    scaler.step(optimizer)
    scaler.update()
```

使用时间：使用支持 float16 的硬件（V100、A100、H100、RTX 3090+）在 GPU 上进行训练。预计速度提升约 1.5-2 倍，内存减少约 50%。

<a id="gradient-accumulation"></a>

## Gradient Accumulation

```python
accumulation_steps = 4
optimizer.zero_grad()
for i, (inputs, targets) in enumerate(train_loader):
    inputs, targets = inputs.to(device), targets.to(device)
    outputs = model(inputs)
    loss = criterion(outputs, targets) / accumulation_steps
    loss.backward()
    if (i + 1) % accumulation_steps == 0:
        optimizer.step()
        optimizer.zero_grad()
```

使用时：有效的batch size需要大于GPU内存允许。将损失除以累积_steps可以使gradient规模保持一致。

<a id="save-and-load"></a>

## 保存和加载

```python
torch.save({
    "epoch": epoch,
    "model_state_dict": model.state_dict(),
    "optimizer_state_dict": optimizer.state_dict(),
    "loss": loss.item(),
}, "checkpoint.pt")

checkpoint = torch.load("checkpoint.pt", weights_only=True)
model.load_state_dict(checkpoint["model_state_dict"])
optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
```

始终保存 optimizer 状态以恢复训练。仅对于 inference，仅保存 `model.state_dict()`。

<a id="custom-dataset"></a>

## 自定义数据集

```python
class CustomDataset(torch.utils.data.Dataset):
    def __init__(self, data_dir, transform=None):
        self.samples = self._load_samples(data_dir)
        self.transform = transform

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        x, y = self.samples[idx]
        if self.transform:
            x = self.transform(x)
        return x, y

    def _load_samples(self, data_dir):
        ...
```

<a id="dataloader-configuration"></a>

## 数据加载器配置

```python
train_loader = torch.utils.data.DataLoader(
    dataset,
    batch_size=64,
    shuffle=True,
    num_workers=4,
    pin_memory=True,
    drop_last=True,
    persistent_workers=True,
)
```

| Parameter | 它的作用 | 何时使用 |
|-----------|-------------|-------------|
| num_workers=4 | 并行数据加载 | 始终在多核机器上 |
| pin_memory=True | 页锁定 CPU 内存 | 在GPU上训练时 |
| drop_last=True | 丢弃不完整的最终批次 | 使用BatchNorm时 |
| persistent_workers=True | 让工人跨epoch生存 | 当 num_workers > 0 时 |

<a id="learning-rate-schedules"></a>

## Learning Rate Schedules

```python
scheduler = torch.optim.lr_scheduler.OneCycleLR(
    optimizer,
    max_lr=1e-3,
    total_steps=num_epochs * len(train_loader),
    pct_start=0.1,
)

for epoch in range(num_epochs):
    for inputs, targets in train_loader:
        ...
        optimizer.step()
        scheduler.step()
```

OneCycleLR：大多数任务的最佳默认值。预热至 max_lr，然后余弦衰减。每个批次后调用 `scheduler.step()`，而不是每个 epoch。

<a id="weight-initialization"></a>

## Weight 初始化

```python
def init_weights(module):
    if isinstance(module, nn.Linear):
        nn.init.kaiming_normal_(module.weight, nonlinearity="relu")
        if module.bias is not None:
            nn.init.zeros_(module.bias)
    elif isinstance(module, nn.Conv2d):
        nn.init.kaiming_normal_(module.weight, mode="fan_out", nonlinearity="relu")

model.apply(init_weights)
```

<a id="inference-mode"></a>

## Inference模式

```python
model.eval()

with torch.inference_mode():
    outputs = model(inputs)
```

`torch.inference_mode()` 比 `torch.no_grad()` 更快，因为它完全禁用 autograd 而不是仅仅抑制 gradient 计算。

<a id="common-mistakes-checklist"></a>

## 常见错误清单

1. 在CrossEntropyLoss之前应用softmax（内部包括log_softmax）
2. 验证期间忘记调用 model.eval()
3. 忘记将 tensors 移动到与模型相同的设备
4. 不调用optimizer.zero_grad()（gradients默认累加）
5. 在训练期间使用 torch.no_grad() （禁用 gradient 计算）
6. 将 num_workers 设置得太高（产生太多进程，破坏内存）
7. 在 GPU 上训练时不使用 pin_memory=True
8. 保存整个模型对象而不是 state_dict （重构时中断）
