# 代码讲解 · main.py

> **所属小节**：阶段 04 · 计算机视觉 · 第 16 节 构建完整的视觉流程——Capstone 综合项目 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数，CPU 上 1 秒内跑完） ｜ **依赖**：`numpy`、`torch`（`torch.nn`、`torch.nn.functional`）、`pydantic`（v2，用到 `model_dump_json`）、标准库 `time`、`typing`；无需联网、无需下载权重（检测器和分类器都是桩模型）

---

## 1. 这份代码在考察什么

讲义的 FastAPI 服务和 Mask R-CNN / ConvNeXt 都需要下载权重。这份代码把两个模型换成**桩（stub）**，只保留流水线的"骨架"，让你把注意力放在讲义所说的"bug 的温床"上——模型之间的接口：

1. **数据契约**：用 Pydantic 定义 `Detection / Classification / PipelineResult`，每个边界都是带类型、带取值范围的对象。
2. **接口防御**：输入格式检查、坐标转整数并夹紧到图像内、过小的框跳过分类。
3. **两段式推理**：检测 → 裁剪缩放 → **批量**分类 → 用 `valid_indices` 把分类结果映射回检测框。
4. **结构化输出**：`model_dump_json` 生成可直接返回给客户端的 JSON。
5. **分阶段 benchmark**：分别计时预处理、检测、分类（含裁剪），并在 GPU 上正确同步。

> 一句话：**模型是可替换的零件，接口才是系统**；这份代码就是那个"零件可插拔、接口有契约"的骨架。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Detection` | Pydantic 模型 | 一个检测框：`box`、`score ∈ [0,1]`、`class_id ≥ 0`、可选 `mask_rle` | 检测器的输出契约 |
| `Classification` | Pydantic 模型 | 一个分类结果，通过 `detection_index` 指回检测框 | 分类器的输出契约 |
| `PipelineResult` | Pydantic 模型 | 整张图的结果 + 推理耗时 | 服务的响应契约 |
| `StubDetector` | `nn.Module` | 按图像尺寸的相对位置返回固定的 3 个框 | 代替 Mask R-CNN，接口与 torchvision 检测模型一致 |
| `StubClassifier` | `nn.Module` | 全局平均池化 → `Linear(3, 10)` | 代替 ConvNeXt-Tiny |
| `VisionPipeline` | 普通类 | `preprocess / detect / classify / run` | 流水线主体 |
| `benchmark(pipe, ...)` | 函数 | 分阶段计时并打印 p50 / p95 | 找瓶颈 |
| `main()` | 入口 | 跑一次流水线打印 JSON，再跑 benchmark | — |

数据流：`np.ndarray (H,W,3) uint8` → `preprocess` → `(3,H,W) float [0,1]` → `detect` → `{"boxes", "scores", "labels"}` → 逐框：转整数、夹紧、构造 `Detection`、过滤小框、裁剪并缩放到 64×64 → `classify`（一次批量前向）→ `Classification` 列表 → `PipelineResult`。

---

## 3. 逐段精讲

### 3.1 数据契约：三个 Pydantic 模型

```python
class Detection(BaseModel):
    box: Tuple[float, float, float, float]
    score: float = Field(ge=0, le=1)
    class_id: int = Field(ge=0)
    mask_rle: Optional[str] = None


class Classification(BaseModel):
    detection_index: int
    class_id: int
    class_name: str
    score: float = Field(ge=0, le=1)


class PipelineResult(BaseModel):
    image_id: str
    detections: List[Detection]
    classifications: List[Classification]
    inference_ms: float
```

- **`BaseModel`**：继承它的类会根据类型注解自动生成构造函数和校验逻辑。构造时，类型不符或越界会抛出 `ValidationError`，错误信息会指明是哪个字段、什么原因。
- **`Field(ge=0, le=1)`**：取值范围约束（greater-or-equal / less-or-equal）。如果分数被误传成 logit（如 2.3）或百分比（如 92），会立刻报错。
- **`Tuple[float, float, float, float]`**：要求恰好 4 个数。传 3 个数会报 `missing`。
- **`Optional[str] = None`**：可选字段，默认 `None`，序列化后是 `null`。讲义练习 2 要求在这里放 RLE 编码的 mask。
- **两个列表 + `detection_index`**：检测和分类分开存放，分类结果通过下标指回检测框。好处是分类可以**部分缺失**（小框被跳过、分类器超时降级时），响应依然合法。
- ⚠️ **契约的局限**（已用 Pydantic 2.13 实际验证）：
  - `box=(50.0, 50.0, 20.0, 30.0)`（x2 < x1）能通过校验；
  - 默认的"宽松模式"还会把字符串 `"1"` 自动转成 `1.0`。
  - 讲义说检测器返回 `(cx, cy, w, h)` 时"Pydantic 的校验会在边界处失败"——对这个契约而言并不成立，因为 4 个浮点数的类型完全合法。需要自己加 `model_validator` 检查 `x2 > x1`、`y2 > y1`，并开启 `strict` 模式（见测验 Q9）；即便如此，也只能拦住一部分格式错误。

### 3.2 `StubDetector`：接口与真模型一致的桩

```python
class StubDetector(nn.Module):
    """Minimal stand-in for Mask R-CNN that produces a fixed set of detections."""

    def __init__(self):
        super().__init__()
        self.dummy = nn.Parameter(torch.zeros(1))

    def forward(self, images):
        results = []
        for img in images:
            H, W = img.shape[-2:]
            boxes = torch.tensor(
                [
                    [W * 0.1, H * 0.1, W * 0.4, H * 0.6],
                    [W * 0.5, H * 0.3, W * 0.9, H * 0.9],
                    [W * 0.2, H * 0.6, W * 0.45, H * 0.85],
                ],
                device=img.device,
            )
            scores = torch.tensor([0.92, 0.85, 0.71], device=img.device)
            labels = torch.tensor([1, 2, 1], device=img.device)
            results.append({"boxes": boxes, "scores": scores, "labels": labels})
        return results
```

- **接口对齐**：torchvision 的检测模型（Faster/Mask R-CNN 等）在 eval 模式下接受 **图像张量的列表**（每张 `(3, H, W)`，尺寸可以不同），返回 **字典的列表**，键为 `boxes`（`(K,4)`，xyxy 绝对像素）、`scores`、`labels`。桩模型照搬了这个接口，所以 `VisionPipeline` 不用改一行代码就能换上真模型——这就是"零件可插拔"。
- **按比例生成框**：框的位置随图像尺寸缩放，任何分辨率都能得到合理的框，便于测试不同尺寸（见测验 Q8）。
- **`self.dummy = nn.Parameter(...)`**：一个用不到的参数。有了它，`.to(device)`、`.parameters()` 等操作都有对象可作用，与真实模型的行为保持一致（例如有些代码会用 `next(model.parameters()).device` 获取模型所在设备）。
- **`device=img.device`**：输出张量与输入放在同一设备上，避免 CPU/GPU 混用的错误。

### 3.3 `StubClassifier`：只看平均颜色的"分类器"

```python
class StubClassifier(nn.Module):
    def __init__(self, num_classes=10):
        super().__init__()
        self.head = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),
            nn.Flatten(),
            nn.Linear(3, num_classes),
        )
```

- `AdaptiveAvgPool2d(1)` 把任意尺寸压成 `1×1`，即每个通道的平均值；`Flatten` → `(N, 3)`；`Linear(3, 10)` → 10 类 logits。
- 它的作用只是提供一个"接受 `(N,3,h,w)`、输出 `(N,num_classes)`"的模块，验证批量分类的管道是否接通。
- ⚠️ 权重随机初始化，`main()` 也没有设置随机种子，所以每次运行的分类结果都不同。

### 3.4 `VisionPipeline.__init__` 与 `preprocess`

```python
class VisionPipeline:
    def __init__(self, detector, classifier, class_names,
                 device="cpu", min_crop=16):
        self.detector = detector.to(device).eval()
        self.classifier = classifier.to(device).eval()
        # ...

    def preprocess(self, image):
        if isinstance(image, np.ndarray):
            if image.ndim != 3 or image.shape[-1] != 3:
                raise ValueError(f"expected HxWx3 RGB image, got shape {image.shape}")
            tensor = torch.from_numpy(image).permute(2, 0, 1).float() / 255.0
        elif isinstance(image, torch.Tensor):
            if image.ndim != 3 or image.shape[0] != 3:
                raise ValueError(f"expected (3, H, W) tensor, got shape {tuple(image.shape)}")
            tensor = image.float()
        else:
            raise TypeError(f"image must be numpy ndarray or torch Tensor, got {type(image)}")
        return tensor.to(self.device)
```

- **构造时就 `.eval()`**：模型在流水线创建时就固定为推理模式，不依赖调用方记得这件事。
- **依赖注入**：检测器、分类器、类别名都从外部传入，`VisionPipeline` 不关心它们具体是什么模型——测试用桩，上线用真模型。
- **`min_crop=16`**：讲义版本是 32，这里配合 64×64 的分类输入调小了。
- **布局转换**：numpy 图像是 HWC（高、宽、通道），PyTorch 是 CHW，所以要 `permute(2, 0, 1)`；`/ 255.0` 把 `uint8` 的 0–255 归一化到 0–1。`torch.from_numpy` 与 numpy 数组共享内存（零拷贝），随后的 `.float()` 才会生成新张量。
- **"大声失败"**：形状不对抛 `ValueError`，类型不对抛 `TypeError`，并把实际收到的形状/类型写进错误信息——比在下游某个卷积里报一个看不懂的维度错误好得多。讲义版本只接受 PIL 和 numpy，代码版本改为接受 numpy 和 Tensor，并加了检查。
- ⚠️ **值域不一致的 bug**：Tensor 分支只做了 `.float()`，**没有除以 255**。如果传入 `torchvision.io.read_image` 读出的 `uint8` 张量，像素值会是 0–255，而 numpy 分支得到的是 0–1——两个入口对同一个契约的理解不一致，而且不会报任何错。修复方法见测验 Q10：按 dtype 分别处理，所有入口统一到 [0, 1]。
- ⚠️ 不再支持 `PIL.Image`：讲义 Step 4 的 FastAPI 端点把 PIL 图像传给 `pipe.run`，如果配合本文件的 `VisionPipeline` 使用，会抛 `TypeError`。
- ⚠️ 没有检查 dtype：`float64` 的 numpy 数组（比如已经是 0–1 的图）会被再除一次 255。

### 3.5 `detect` 与 `classify`

```python
    @torch.no_grad()
    def detect(self, image_tensor):
        return self.detector([image_tensor])[0]

    @torch.no_grad()
    def classify(self, crops):
        if len(crops) == 0:
            return []
        batch = torch.stack(crops).to(self.device)
        logits = self.classifier(batch)
        probs = logits.softmax(-1)
        scores, cls = probs.max(-1)
        return list(zip(cls.tolist(), scores.tolist()))
```

- **`@torch.no_grad()` 装饰器**：`torch.no_grad` 既能当上下文管理器（`with`），也能当装饰器，作用于整个函数——推理时不构建计算图，省内存、更快。
- **`detect`**：把单张图包成长度为 1 的列表送进检测器（符合 torchvision 接口），再取 `[0]` 拿回这张图的结果字典。
- **空列表守卫**：`torch.stack([])` 会报错，所以没有 crop 时直接返回空列表——对应讲义的失败模式"空检测返回空列表，不要崩溃"。
- **批量分类**：所有 crop 已经缩放到相同的 64×64，可以 `stack` 成 `(K, 3, 64, 64)`，一次前向完成 K 个分类。比逐个调用快得多，也是讲义中"微批处理"思想在单请求内的体现。
- **`probs.max(-1)`**：在类别维上同时返回最大概率和对应下标；`.tolist()` 转成 Python 列表；`zip` 组合成 `[(类别, 分数), ...]`。

### 3.6 `run`：流水线主循环

```python
    def run(self, image, image_id="anonymous"):
        t0 = time.perf_counter()
        tensor = self.preprocess(image)
        det = self.detect(tensor)

        crops = []
        valid_indices = []
        detections = []
        for i, (box, score, cls) in enumerate(
            zip(det["boxes"], det["scores"], det["labels"])
        ):
            x1, y1, x2, y2 = [max(0, int(b)) for b in box.tolist()]
            x2 = min(x2, tensor.shape[-1])
            y2 = min(y2, tensor.shape[-2])
            detections.append(Detection(
                box=(x1, y1, x2, y2),
                score=float(score),
                class_id=int(cls),
            ))
            if (x2 - x1) < self.min_crop or (y2 - y1) < self.min_crop:
                continue
            crop = tensor[:, y1:y2, x1:x2]
            crop = F.interpolate(
                crop.unsqueeze(0), size=(64, 64), mode="bilinear", align_corners=False
            )[0]
            crops.append(crop)
            valid_indices.append(i)
```

逐步拆解：

1. **转整数 + 下限夹紧**：`int(b)` 向零截断成像素下标，`max(0, ...)` 把负坐标夹到 0。
2. **上限夹紧**：`x2` 夹到图像宽度 `tensor.shape[-1]`、`y2` 夹到高度 `tensor.shape[-2]`。切片 `[y1:y2]` 是左闭右开的，所以上限取 W/H（而不是 W−1/H−1）正好。这对应讲义的失败模式"越界框——裁剪前先夹紧到图像尺寸"。
3. **先记录、后过滤**：无论框大小，先构造 `Detection` 放进 `detections`；只有通过 `min_crop` 检查的框才进入分类。小框不会从响应里消失，只是没有分类结果——"命名的跳过"，而不是静默丢弃。
4. **裁剪的行列顺序**：`tensor[:, y1:y2, x1:x2]`——第 1 维是行（y），第 2 维是列（x）。把 x、y 写反是最经典的静默 bug 之一。
5. **缩放**：`F.interpolate` 需要 4D 输入 `(N,C,H,W)`，所以先 `unsqueeze(0)` 增加 batch 维，缩放完再用 `[0]` 去掉。`bilinear` + `align_corners=False` 是图像缩放的常规设置。
6. **`valid_indices`**：记录通过过滤的框在 `detections` 中的原始下标。因为 `crops` 中可能跳过了一些框，`crops` 的位置与 `detections` 的位置不再一一对应，必须用这个列表做映射（测验 Q8 第 3 问）。

```python
        class_preds = self.classify(crops)

        classifications = []
        for valid_idx, (cls_id, cls_score) in zip(valid_indices, class_preds):
            classifications.append(Classification(
                detection_index=valid_idx,
                class_id=int(cls_id),
                class_name=self.class_names[cls_id] if cls_id < len(self.class_names) else f"class_{cls_id}",
                score=float(cls_score),
            ))

        return PipelineResult(
            image_id=image_id,
            detections=detections,
            classifications=classifications,
            inference_ms=(time.perf_counter() - t0) * 1000,
        )
```

- `zip(valid_indices, class_preds)` 把原始下标与分类结果配对。
- **类别名兜底**：分类器输出的类别 id 超出 `class_names` 的长度时，用 `class_{id}` 代替，而不是抛 `IndexError`。讲义版本直接用 `self.class_names[cls_id]`。⚠️ 这种兜底能保证服务不崩溃，但也可能掩盖"标签表与模型不匹配"这一真实错误，生产中至少应该记录告警日志。
- `inference_ms` 包含预处理、检测、裁剪、分类和所有 Pydantic 构造的时间，是端到端的服务内耗时（不含 HTTP 和 JSON 序列化）。
- ⚠️ 简化之处：
  - 没有按 score 阈值过滤（真实检测器会返回大量低分框）；
  - `x1 ≥ W` 的完全越界框会得到 `x2 < x1` 的"负宽度"框，并被原样写进 `detections`；
  - crop 直接拉伸到 64×64，不保持长宽比；
  - 分类器输入没有做 ImageNet 均值/方差归一化——换成真实的 ConvNeXt 时必须补上（讲义 Step 3 也漏了这一步）。

### 3.7 `benchmark`：分阶段计时

```python
def benchmark(pipe, num_runs=10, image_size=(400, 600)):
    img = (np.random.rand(*image_size, 3) * 255).astype(np.uint8)
    pipe.run(img)
    stages = {"preprocess": [], "detect": [], "classify": [], "total": []}

    def sync():
        if pipe.device == "cuda" and torch.cuda.is_available():
            torch.cuda.synchronize()

    for _ in range(num_runs):
        sync()
        t0 = time.perf_counter()
        tensor = pipe.preprocess(img)
        sync()
        t1 = time.perf_counter()
        det = pipe.detect(tensor)
        sync()
        t2 = time.perf_counter()
        # ... 与 run() 相同的夹紧/过滤/裁剪/缩放
        pipe.classify(crops)
        sync()
        t3 = time.perf_counter()
        stages["preprocess"].append((t1 - t0) * 1000)
        # ...
    for stage, times in stages.items():
        times.sort()
        print(f"  {stage:10s}  p50={times[len(times)//2]:7.2f}  p95={times[int(len(times)*0.95)]:7.2f}")
```

- **warmup**：先完整跑一次 `pipe.run(img)`，再开始计时。
- **在每个阶段边界同步**：GPU 上 kernel 是异步的，如果不同步，某个阶段的 GPU 时间会被"记到"下一个阶段头上。`sync()` 是一个闭包，CPU 上什么都不做。讲义版本没有同步，代码补上了（呼应第 15 节的测量纪律）。
- **"classify" 一栏包含裁剪和缩放**：`t2` 到 `t3` 之间既有 crop/interpolate，也有分类前向。⚠️ 如果想知道"裁剪缩放"本身有多慢（skill 文件为它单独分配了 5% 的预算），需要再插一个时间点。
- ⚠️ **代码重复**：这里把 `run()` 的裁剪逻辑抄了一遍，两边将来很容易改得不一致。更好的做法是把"框 → crops + valid_indices"抽成一个方法，或者在 `run()` 内部记录各阶段耗时（相当于讲义"Use It"中的逐请求 trace）。
- ⚠️ **"preprocess" 不含 JPEG 解码**：输入已经是 numpy 数组。讲义说"预处理常是 CPU 上最大的单块"，指的是包含解码在内的完整预处理；这里测到的只是一次 permute 加除法，所以会显得很小。
- ⚠️ **百分位**：`num_runs=10` 时 `int(10 × 0.95) = 9`，打印的 p95 其实是 10 次中的最大值（与第 15 节同样的问题）。

### 3.8 `main()`

```python
    img = (np.random.rand(400, 600, 3) * 255).astype(np.uint8)
    result = pipe.run(img, image_id="demo")
    print("[result]")
    print(result.model_dump_json(indent=2)[:400])
    print("...")
```

- `np.random.rand(...)` 生成 [0,1) 的浮点数，乘 255 再转 `uint8`，得到一张随机噪声"图像"。
- `model_dump_json(indent=2)` 是 Pydantic v2 的 API（v1 中叫 `.json()`），把模型序列化成缩进 2 格的 JSON 字符串。`[:400]` 只打印前 400 个字符，避免刷屏。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用桩模型代替真模型 | 不下载权重、秒级运行，专注于接口 | 测不到真实精度和延迟；接口必须与真模型严格一致 |
| 每个边界一个 Pydantic 模型 | 把类型/范围错误变成显式报错 | 只管类型不管语义；需要自定义校验器与严格模式 |
| 检测与分类分开存放，用下标关联 | 分类可部分缺失（小框、超时降级） | 下标映射容易写错（必须用 `valid_indices`） |
| 先记录检测、再过滤小框 | 响应保留全部检测，不静默丢失 | 下游要能处理"没有分类的检测" |
| crop 统一缩放到 64×64 后批量分类 | 一次前向处理所有框 | 拉伸会变形；真实分类器需要 224 输入和 ImageNet 归一化 |
| 类别名越界时兜底 | 服务不因标签表问题崩溃 | 可能掩盖配置错误，应记录告警 |
| benchmark 中每段都同步 | GPU 计时准确 | 同步本身打断流水并行，测到的是"串行"耗时 |
| 不包含 FastAPI 层 | 保持依赖最少 | 讲义 Step 4 中服务层的失败处理（400、启动加载）需要另行实现 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 类型注解 | `box: Tuple[float, float, float, float]`、`detections: List[Detection]` | Pydantic 用这些注解做运行时校验；Python 3.9+ 也可直接写 `list[...]`、`tuple[...]`，3.10+ 的 `Optional[X]` 可写成"X 竖线 None"的联合类型 |
| `Optional[...] = None` | `mask_rle: Optional[str] = None` | 可为 `None` 的可选字段 |
| 字段约束 `Field` | `score: float = Field(ge=0, le=1)` | 声明取值范围，违反时抛 `ValidationError` |
| 关键字参数构造对象 | `Detection(box=..., score=..., class_id=...)` | Pydantic 模型按字段名传参 |
| 文档字符串 | `"""Minimal stand-in for Mask R-CNN ..."""` | 类/函数的第一行字符串，`help()` 可以读到 |
| 元组解包 | `H, W = img.shape[-2:]`、`scores, cls = probs.max(-1)` | 一次取多个值 |
| 字典字面量 | `{"boxes": boxes, "scores": scores, "labels": labels}` | 与 torchvision 检测输出的格式一致 |
| `isinstance` 分支 | `if isinstance(image, np.ndarray): ... elif isinstance(image, torch.Tensor): ...` | 按输入类型走不同的处理逻辑 |
| `raise` 带信息的异常 | `raise ValueError(f"expected HxWx3 RGB image, got shape {image.shape}")` | 错误信息中写出实际收到的值 |
| 装饰器 | `@torch.no_grad()` | 用一个函数包装另一个函数，这里是整个函数内关闭梯度 |
| `enumerate` + `zip` 嵌套解包 | `for i, (box, score, cls) in enumerate(zip(...))` | 同时拿到下标和三个并行序列的元素 |
| 列表推导式 | `[max(0, int(b)) for b in box.tolist()]` | 一行完成截断和夹紧 |
| `continue` | `if ...: continue` | 跳过本次循环剩余部分 |
| 条件表达式 | `self.class_names[cls_id] if cls_id < len(self.class_names) else f"class_{cls_id}"` | `A if 条件 else B` |
| `list(zip(...))` | `list(zip(cls.tolist(), scores.tolist()))` | 把两个列表配对成元组列表 |
| 嵌套函数 | `def sync(): ...` 定义在 `benchmark` 内 | 闭包，读取外层的 `pipe` |
| `dict.items()` | `for stage, times in stages.items()` | 同时遍历键和值 |
| `*` 解包实参 | `np.random.rand(*image_size, 3)` | `(400, 600)` 拆成两个参数，再加一个 3 |
| f-string 格式符 | `{stage:10s}`、`{...:7.2f}` | 宽度 10 的字符串；宽度 7、两位小数 |
| 字符串切片 | `result.model_dump_json(indent=2)[:400]` | 只取前 400 个字符 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()` |

---

## 6. 运行结果解读

**未实际运行（当前环境缺少 `torch`）。** 不过，JSON 输出的前 400 个字符是确定的：我用 NumPy 的 float32 模拟 `torch.tensor` 的默认精度，配合相同的 Pydantic 模型（环境中有 Pydantic 2.13）复现了这一部分，结果如下。分类结果因权重随机而每次不同，但它在 400 字符之后，不会被打印出来。耗时数字取决于机器。

```text
[result]
{
  "image_id": "demo",
  "detections": [
    {
      "box": [
        60.0,
        40.0,
        240.0,
        240.0
      ],
      "score": 0.9200000166893005,
      "class_id": 1,
      "mask_rle": null
    },
    {
      "box": [
        300.0,
        120.0,
        540.0,
        360.0
      ],
      "score": 0.8500000238418579,
      "class_id": 2,
      "mask_rle": null
    },
    {
    
...

[benchmark]
  preprocess  p50=   x.xx  p95=   x.xx
  detect      p50=   x.xx  p95=   x.xx
  classify    p50=   x.xx  p95=   x.xx
  total       p50=   x.xx  p95=   x.xx
```

逐项解读：

- **`box: [60.0, 40.0, 240.0, 240.0]`**：600×400 图像上 `[W·0.1, H·0.1, W·0.4, H·0.6]`。`run()` 传入的是整数，Pydantic 按 `float` 注解转成了 `60.0`。三个框都大于 16 像素，全部会被分类（第 3 个框是 `(120, 240, 270, 340)`，150×100）。
- **`"score": 0.9200000166893005`**：0.92 先被存成 float32 张量，`float(score)` 再转回 Python 的 float64，暴露出 float32 的表示误差。生产中常在序列化时做舍入（如保留 4 位小数），既省带宽又不让客户端困惑。
- **`"mask_rle": null`**：可选字段的默认值。
- **完整 JSON** 约 960 个字符：`classifications` 中会有 3 条，`detection_index` 分别为 0、1、2，`class_name` 形如 `class_7`，`inference_ms` 通常在毫秒量级。
- **benchmark**：桩模型几乎没有计算量，所有阶段都在毫秒级甚至更低，具体数字因机器而异。"classify" 一栏还包含 3 次裁剪和缩放。换成讲义中的真实模型后，讲义给出的典型 CPU 数字为：预处理约 3 ms、检测 300–500 ms、分类 20–40 ms，总计 350–550 ms；GPU 上检测降到 20–40 ms，预处理和分类的相对占比随之上升。

---

## 7. 动手改一改

1. **补契约**：给 `Detection` 加 `ConfigDict(strict=True)` 和检查 `x2 > x1`、`y2 > y1` 的 `model_validator`；再给 `PipelineResult` 加 `image_width / image_height` 字段，校验所有框都在图像内。
2. **修 `preprocess`**：按 dtype 处理 Tensor 输入（`uint8` 除以 255），并重新支持 `PIL.Image`（测验 Q10）。
3. **阈值过滤**：给 `VisionPipeline` 加 `score_threshold=0.5` 参数，低于阈值的检测不进入 `detections`；把 `StubDetector` 的第 3 个分数改成 0.3 来验证。
4. **消除重复**：把"框 → crops + valid_indices"抽成 `_make_crops(tensor, det)`，让 `run` 和 `benchmark` 共用，并在 `run` 中记录每个阶段的耗时，放进 `PipelineResult`（例如 `stage_ms: dict[str, float]`）。
5. **保持长宽比**：裁剪后先按长边缩放再 padding 到 64×64，比较与直接拉伸的差异。
6. **（进阶）讲义练习 3**：为分类器实现一个 micro-batcher——用 `asyncio.Queue` 收集最多 10 ms 内的 crop，一次前向后把结果分发回各个请求；测量吞吐量与额外延迟。

---

## 8. 常见坑

- **以为类型校验 = 语义校验**：`Tuple[float × 4]` 不知道这是 xyxy 还是 cxcywh。
- **`crops` 下标当成检测下标**：有框被跳过后，分类结果会整体错位，而且不会报错。
- **两个入口的值域不一致**：numpy 分支除了 255，Tensor 分支没有除。
- **裁剪时 x、y 写反**：`tensor[:, x1:x2, y1:y2]` 在方形图上甚至"看起来能跑"。
- **分类器缺少归一化**：torchvision 检测器内部会做归一化，分类器不会，换成真模型时要补上 ImageNet 的均值/方差。
- **在 `async def` 端点里直接调用同步推理**：会阻塞事件循环，并发一上来延迟就线性堆积（测验 Q14）。
- **用宽泛的 `try/except` 处理失败**：讲义明确反对；每类失败都应该有具名的错误码。
