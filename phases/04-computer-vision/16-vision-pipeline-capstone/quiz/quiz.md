# 测验 · 构建完整的视觉流程——Capstone 综合项目（Build a Complete Vision Pipeline — Capstone）

> **阶段 04 · 计算机视觉 · 第 16 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、读过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 视觉产品 = 模型链 | 解码/预处理 → 检测 → 裁剪缩放 → 分类 → 聚合 → schema 校验 → JSON 响应；两个模型阶段最贵，其余五个阶段是 bug 的温床 |
| 2 | 数据契约（Pydantic） | 每个模型边界都是一个带类型的对象（`Detection`、`Classification`、`PipelineResult`），把静默失败变成显式报错 |
| 3 | 契约的边界 | 类型 + 范围约束（`Field(ge=0, le=1)`）只能保证"形状和取值范围"；坐标格式这类语义错误要靠自定义校验器补充 |
| 4 | 延迟分布 | CPU 上预处理（JPEG 解码、色彩转换、缩放）常是最大的单块；GPU 上检测器前向占 70–90% 的 GPU 时间；NMS/RLE 在 GPU 上便宜、在 CPU 上贵 |
| 5 | 失败模式与处理 | 空检测返回空列表；越界框先夹紧再裁剪；过小的框跳过分类；损坏上传返回 400；模型加载失败在启动时就报错 |
| 6 | 具名错误码 | 每类失败一个具体的错误码，而不是笼统的 `try/except` 或 500；客户端据此决定是否重试 |
| 7 | 微批处理（micro-batching） | 收集一个时间窗（如 20 ms）内的请求一起前向：吞吐量上升，单请求延迟增加约一个窗口；torchserve / Triton 原生支持 |
| 8 | 生产化要素 | 模型版本与权重哈希、逐请求 trace ID 与分阶段计时、降级路径（分类超时只返回检测结果）、安全过滤、健康检查 |

### 核心技能（能动手做到）

- [ ] 用 Pydantic 定义 `Detection / Classification / PipelineResult` 三个契约，并能写出至少 3 种会触发 `ValidationError` 的输入
- [ ] 为 `Detection` 增加几何校验器（`x2 > x1`、`y2 > y1`、坐标非负），并说清它能拦住哪些格式错误、拦不住哪些
- [ ] 实现 `VisionPipeline.run`：坐标夹紧、`min_crop` 过滤、批量分类，并用 `valid_indices` 把分类结果正确映射回检测框
- [ ] 写一个分阶段计时的 benchmark（含 GPU 同步），找出第一个瓶颈阶段
- [ ] 用 FastAPI 包装成服务：校验 content-type、解码失败返回 400、模型在启动时加载
- [ ] 能为给定的 p95 目标给每个阶段分配时间预算，并选出对应的优化杠杆

---

## 二、基础自测（选择题）

**Q1.** `Detection.box` 的类型是 `Tuple[float, float, float, float]`，约定为 `(x1, y1, x2, y2)`。某次升级后，检测器改为返回 `(cx, cy, w, h)`。在**不加任何自定义校验器**的情况下，会发生什么？

- A. Pydantic 立刻抛出 `ValidationError`，因为格式不对
- B. 校验照常通过——四个浮点数满足类型约束；错误会在下游以"裁剪区域为空或错位"等形式静默出现
- C. Pydantic 会自动把 `(cx, cy, w, h)` 转换成 `(x1, y1, x2, y2)`
- D. 程序在 `torch.stack` 处必然崩溃

**Q2.** 在纯 CPU 的视觉流水线中，讲义认为哪个阶段**常常**是最大的单块耗时？

- A. 读取 HTTP 请求体
- B. 图像解码与预处理（JPEG 解码、色彩空间转换、缩放），它们是 CPU 密集型操作且容易被忽视
- C. 写 JSON 响应
- D. Pydantic 校验

**Q3.** 检测器输出了一个 3×4 像素的框，分类器在它上面表现很差（甚至报错）。正确的处理方式是：

- A. 增大 batch size
- B. 设置 `min_crop` 阈值，跳过过小框的分类，但在响应中保留这个检测结果，并记录日志
- C. 用一个全局 `try/except` 包住分类，出错就返回空分类列表
- D. 把这个检测框从响应中直接删除

**Q4.** 用户上传了一个损坏的 JPEG，服务返回 500。下面哪种改法最合理？

- A. 不处理，用户会重试
- B. 在解码阶段捕获失败，返回 400 和具体错误码（如 `image_decode_failed`）
- C. 一律返回 200 和空结果
- D. 把解码挪到分类器里做

**Q5.** 给分类器加上微批处理（最多等 10 ms，凑齐后一次 GPU 前向）。预期效果是：

- A. 单请求延迟一定下降
- B. 毫无影响
- C. 吞吐量显著上升，单请求延迟最多增加约一个批处理窗口；值不值得取决于服务是吞吐受限还是延迟受限
- D. 吞吐量下降，因为要等待

**Q6.** 关于"模型加载失败"，讲义推荐的做法是：

- A. 在第一个请求到来时再懒加载，失败就返回 500
- B. 在服务启动时加载，失败就让启动直接失败，避免一个"看起来健康、实际上不能服务"的实例接收流量
- C. 加载失败时自动换成随机初始化的模型
- D. 忽略错误，继续启动

**Q7.** 分类器偶尔超时，讲义"Use It"部分建议的降级路径是：

- A. 整个请求返回 500
- B. 无限重试分类器直到成功
- C. 返回检测结果但不带分类结果，而不是让整个请求失败
- D. 用检测器的类别 id 冒充分类结果

---

## 三、动手 / 代码题

**Q8.** 本节的 `StubDetector` 对任意图像都按相对位置返回 3 个框：

```python
            boxes = torch.tensor(
                [
                    [W * 0.1, H * 0.1, W * 0.4, H * 0.6],
                    [W * 0.5, H * 0.3, W * 0.9, H * 0.9],
                    [W * 0.2, H * 0.6, W * 0.45, H * 0.85],
                ],
                device=img.device,
            )
```

`VisionPipeline` 默认 `min_crop=16`，`run()` 中的过滤逻辑是：

```python
            x1, y1, x2, y2 = [max(0, int(b)) for b in box.tolist()]
            x2 = min(x2, tensor.shape[-1])
            y2 = min(y2, tensor.shape[-2])
            detections.append(Detection(...))
            if (x2 - x1) < self.min_crop or (y2 - y1) < self.min_crop:
                continue
            # ... 裁剪、缩放到 64×64，crops.append(crop)
            valid_indices.append(i)
```

(1) 输入 400×600（H×W）的图像时，3 个框的整数坐标、宽高分别是多少？有几个会被送去分类？
(2) 输入 40×60 的图像时呢？`valid_indices` 是什么？
(3) 为什么 `Classification.detection_index` 要用 `valid_indices` 中的 `i`，而不是用 `crops` 列表中的位置？如果写错，会出现什么症状？

**Q9.** 契约漏洞修补。
(1) 已知下面的输入都能通过原始 `Detection` 的校验：`box=(50.0, 50.0, 20.0, 30.0)`（x2 < x1）、`box=("1", "2", "3", "4")`（字符串）。请给 `Detection` 加上：① 严格模式，拒绝字符串被自动转换成数字；② 一个 `model_validator`，要求坐标非负且 `x2 > x1`、`y2 > y1`。
(2) 加了这个校验器之后，`(cx, cy, w, h) = (150, 140, 180, 200)` 这样的错误格式框能被拦住吗？还需要什么信息才能拦得更彻底？

**Q10.** 找 bug。`VisionPipeline.preprocess` 对两种输入分别这样处理：

```python
        if isinstance(image, np.ndarray):
            # ...形状检查...
            tensor = torch.from_numpy(image).permute(2, 0, 1).float() / 255.0
        elif isinstance(image, torch.Tensor):
            # ...形状检查...
            tensor = image.float()
```

(1) 用户用 `torchvision.io.read_image("dog.jpg")` 读图（返回 `uint8`、形状 `(3, H, W)` 的张量）后直接调用 `pipe.run(img)`，会发生什么？为什么这类 bug 特别危险？
(2) 修复这个函数，并顺便支持讲义 FastAPI 示例中传入的 `PIL.Image`。

---

## 四、面试高频题

**Q11.**（基础必考 / 系统设计）请设计一个"上传图片 → 检测物体 → 对每个物体做细分类 → 返回 JSON"的在线服务。说说各阶段、模块之间的接口约定、失败路径和可观测性。

**Q12.**（工程实践）服务 p95 延迟超标了，你怎么定位瓶颈？对预处理、检测器、后处理、分类器分别有哪些优化杠杆？

**Q13.**（原理深挖）微批处理（micro-batching）的原理是什么？批处理窗口怎么选？什么时候不该用？

**Q14.**（工程实践 / 追问型）讲义的 FastAPI 示例中，`async def detect_endpoint` 里直接调用了同步的 `pipe.run(img)`。这有什么问题？在高并发下会出现什么现象？怎么改？

**Q15.**（场景设计 / 排障）检测器和分类器单独测试时都很准，串成流水线后分类结果却几乎随机。你会按什么顺序排查？

---

## 五、参考答案与解析

### Q1 — 答案：B

`Tuple[float, float, float, float]` 只检查"是不是 4 个数"，不检查这 4 个数的含义。已用 Pydantic 2 实际验证：`Detection(box=(50.0, 50.0, 20.0, 30.0), score=0.5, class_id=0)` 能正常构造。讲义说 cxcywh 格式"会在边界处校验失败"，这需要额外的语义校验器才能（部分）实现，见 Q9。A 是常见的误解；C 不存在这种自动转换；D 也不一定——裁剪区域可能只是错位，而不会崩溃。

### Q2 — 答案：B

讲义列出的"三条真理"之一："预处理常常是最大的单块耗时"——JPEG 解码、色彩转换、缩放都是 CPU 密集型操作，而且很容易被忽略。GPU 上则是检测器占 GPU 时间的 70–90%。原则是：先 profile 再优化，不要凭感觉。注意本节代码的 benchmark 输入已经是解码好的 numpy 数组，"preprocess" 一栏不含 JPEG 解码，所以会显得很小。

### Q3 — 答案：B

分类器是在 224×224（本节 stub 为 64×64）的输入上训练的，几个像素的 patch 放大后几乎没有信息。正确做法是"命名的、记录在案的跳过"：检测结果保留在 `detections` 中，只是没有对应的 `Classification`。C 的全局 `try/except` 会把真正的 bug 一起吞掉；D 会丢失有效的检测信息。

### Q4 — 答案：B

坏输入是客户端的问题，应该返回 4xx；5xx 表示服务端故障，会触发客户端用同样的坏输入重试，放大负载。具名错误码（`image_decode_failed`、`unsupported_content_type`、`image_too_large`）让客户端能做出正确反应。讲义的 FastAPI 示例对不支持的 content-type 和无法解码的图像都返回 400。

### Q5 — 答案：C

批量前向能更好地利用 GPU 并行，摊薄每张图的开销，吞吐量随 batch 增大而提升；代价是每个请求最多要等待一个窗口。讲义的典型配置是"收集最多 20 ms 的请求"。当服务吞吐受限、延迟有余量时值得用；延迟 SLA 很紧（如 quiz.json 提到的 50 ms 以下）时要谨慎。

### Q6 — 答案：B

讲义："模型加载失败——在服务启动时失败，而不是在第一个请求时失败。"启动即失败能让编排系统（如 Kubernetes 的就绪探针）不把流量导给坏实例，也能在部署阶段就暴露问题；懒加载会让第一个用户承担冷启动延迟和失败。

### Q7 — 答案：C

讲义："Fallback path——如果分类器超时，返回不带分类结果的检测结果，而不是让整个请求失败。"这正是数据契约中 `detections` 和 `classifications` 分成两个列表、用 `detection_index` 关联的好处：分类结果可以部分或全部缺失，响应依然合法。D 混淆了检测器的粗类别和分类器的细类别，会误导下游。

### Q8 — 参考答案

(1) 400×600（已用 NumPy 按 float32 和相同的截断逻辑核对）：

| i | 浮点框 | 整数框 `(x1,y1,x2,y2)` | 宽 × 高 | 送分类？ |
|---|-------|---------------------|--------|---------|
| 0 | `[60, 40, 240, 240]` | `(60, 40, 240, 240)` | 180 × 200 | 是 |
| 1 | `[300, 120, 540, 360]` | `(300, 120, 540, 360)` | 240 × 240 | 是 |
| 2 | `[120, 240, 270, 340]` | `(120, 240, 270, 340)` | 150 × 100 | 是 |

3 个都送去分类，`valid_indices = [0, 1, 2]`。

(2) 40×60：

| i | 整数框 | 宽 × 高 | 送分类？ |
|---|-------|--------|---------|
| 0 | `(6, 4, 24, 24)` | 18 × 20 | 是 |
| 1 | `(30, 12, 54, 36)` | 24 × 24 | 是 |
| 2 | `(12, 24, 27, 34)` | 15 × 10 | 否（两条边都小于 16） |

`valid_indices = [0, 1]`。`detections` 仍有 3 项，`classifications` 只有 2 项。

(3) `crops` 只包含**通过过滤**的框，它的下标与 `detections` 的下标在发生跳过后就不再一致。比如把第 0 个框跳过后，`crops[0]` 对应的其实是 `detections[1]`。若用 `crops` 的位置作为 `detection_index`，分类结果会被"挂"到错误的框上，而且**不会报任何错**——JSON 结构完全合法，只是语义错了。症状是：只要某张图里有小框被跳过，后面所有框的分类标签都会错位一格。`valid_indices` 记录原始下标，`zip(valid_indices, class_preds)` 保证二者一一对应。

### Q9 — 参考答案

(1) 以下代码已在 Pydantic 2.13 中实际运行验证：

```python
from typing import Optional, Tuple
from pydantic import BaseModel, ConfigDict, Field, model_validator

class Detection(BaseModel):
    model_config = ConfigDict(strict=True)      # 拒绝 "1" -> 1.0 这类隐式转换

    box: Tuple[float, float, float, float]
    score: float = Field(ge=0, le=1)
    class_id: int = Field(ge=0)
    mask_rle: Optional[str] = None

    @model_validator(mode="after")
    def check_box(self):
        x1, y1, x2, y2 = self.box
        if x1 < 0 or y1 < 0:
            raise ValueError(f"box has negative coordinates: {self.box}")
        if x2 <= x1 or y2 <= y1:
            raise ValueError(f"box must be (x1, y1, x2, y2) with x2 > x1 and y2 > y1, got {self.box}")
        return self
```

实测结果：

```text
box=(60.0, 40.0, 240.0, 240.0)     → OK
box=(150.0, 140.0, 80.0, 60.0)     → ValidationError: value_error（x2 <= x1）
box=(60, 40, 240, 240)  整数        → OK（严格模式仍允许 int → float）
box=("60", 40.0, 240.0, 240.0)     → ValidationError: float_type
```

要点：
- `mode="after"` 表示在字段级校验和类型转换完成之后运行，此时 `self.box` 已经是 4 个 float；
- 校验器失败时抛出的 `ValueError` 会被 Pydantic 包装成 `ValidationError`；
- 严格模式下 int 仍然可以赋给 float 字段（无损），但字符串不行。

注意：`run()` 中会把 `x2` 夹到图像边界内，当框完全落在图像外（例如 `x1 ≥ W`）时，夹紧后会出现 `x2 ≤ x1`，此时这个校验器会让整个请求失败。工程上要先决定这种框的策略——丢弃并记录日志，还是保留但标记为无效——再决定校验器写在哪里。

(2) 拦不住。`(150, 140, 180, 200)` 被当作 `(x1, y1, x2, y2)` 时恰好满足 `x2 > x1`、`y2 > y1`，是一个"合法"的框。几何校验器只能拦住一部分格式错误（当 `w < cx` 或 `h < cy` 时）。要拦得更彻底，需要：
- **图像尺寸作为上下文**：校验 `x2 ≤ W`、`y2 ≤ H`（可以放在包含图像宽高的上层模型中，例如在 `PipelineResult` 里加 `image_width/height` 字段并在其校验器里检查所有框）；
- **在类型层面区分格式**：比如定义 `BoxXYXY` 和 `BoxCXCYWH` 两种类型，由检测器适配层显式转换；
- **回归测试**：用已知图像和已知框做端到端断言。

结论：数据契约能把很多静默失败变成显式失败，但"类型正确 ≠ 语义正确"，语义约束需要显式写出来。

### Q10 — 参考答案

(1) `read_image` 返回 `uint8` 张量，取值 0–255。走 `torch.Tensor` 分支时只做了 `.float()`，**没有除以 255**，于是像素值是 0–255，而 numpy 分支得到的是 0–1。检测器和分类器拿到的输入数值放大了 255 倍——**不会报错**，形状和类型都对，只是结果悄悄变差（torchvision 检测器内部会按 0–1 的假设做均值方差归一化，输入尺度错了，置信度和框都会异常）。这正是讲义说的"每个归一化都是静默失败的候选"：两个入口对"像素值范围"这个契约的理解不一致。

(2)

```python
from PIL import Image

    def preprocess(self, image):
        if isinstance(image, Image.Image):                 # 讲义 FastAPI 示例传入的是 PIL 图像
            image = np.asarray(image.convert("RGB"))
        if isinstance(image, np.ndarray):
            if image.ndim != 3 or image.shape[-1] != 3:
                raise ValueError(f"expected HxWx3 RGB image, got shape {image.shape}")
            if image.dtype != np.uint8:
                raise ValueError(f"expected uint8 image, got {image.dtype}")
            tensor = torch.from_numpy(image).permute(2, 0, 1).float() / 255.0
        elif isinstance(image, torch.Tensor):
            if image.ndim != 3 or image.shape[0] != 3:
                raise ValueError(f"expected (3, H, W) tensor, got shape {tuple(image.shape)}")
            if image.dtype == torch.uint8:
                tensor = image.float() / 255.0               # 统一到 [0, 1]
            elif image.is_floating_point():
                tensor = image.float()
                if tensor.numel() and tensor.max() > 1.0:    # 浮点输入也要符合 [0, 1] 契约
                    raise ValueError("float tensor input must be in [0, 1]")
            else:
                raise TypeError(f"unsupported tensor dtype {image.dtype}")
        else:
            raise TypeError(f"image must be PIL.Image, numpy ndarray or torch Tensor, got {type(image)}")
        return tensor.to(self.device)
```

（当前环境无 torch，以上代码未实际运行。）

关键点：
- 所有入口都显式归一化到同一个值域；
- 对 dtype 做显式检查，而不是靠隐式转换；
- 对不符合契约的输入**大声报错**，而不是猜测用户的意图。

### Q11 — 参考回答要点

- **阶段**：
  1. HTTP 接收：校验 content-type 和大小；
  2. 解码与预处理：转 RGB、转张量、归一化；
  3. 检测器：YOLO 或 Mask R-CNN；
  4. 后处理：NMS、按阈值过滤、坐标夹紧；
  5. 裁剪 + 缩放：小于 `min_crop` 的框跳过分类；
  6. 分类器：批量前向；
  7. 聚合：把分类结果通过 `detection_index` 关联回检测框；
  8. schema 校验与序列化。
- **接口约定**：
  - 每个边界都用 Pydantic 定义类型，写清坐标格式（xyxy、绝对像素）、值域（score ∈ [0,1]）、类别 id 的来源（是检测器的标签表还是分类器的标签表）；
  - 加几何校验器；
  - 检测与分类分成两个列表，允许分类结果部分缺失。
- **失败路径**：

  | 失败 | 处理 |
  |------|------|
  | 坏输入 | 400 + 具名错误码 |
  | 空检测 | 返回空列表 + 日志 |
  | 越界框 | 夹紧 |
  | 过小框 | 跳过分类 |
  | 分类器超时 | 降级为只返回检测结果 |
  | 模型加载失败 | 启动失败 |

  不使用吞掉一切的 `try/except`。
- **可观测性**：
  - 每个请求一个 trace ID，记录各阶段耗时；
  - 响应中带上模型名称和权重哈希；
  - 提供健康检查端点；
  - 监控 p50/p95 延迟、错误码分布、每张图的检测数分布。
- **加分点**：
  - 安全过滤（NSFW / PII）放在响应离开服务之前；
  - 规模扩大后迁移到 Triton / torchserve / BentoML，以获得批处理、版本管理和指标。

### Q12 — 参考回答要点

- **定位**：
  1. 先有分阶段计时：本节 `benchmark` 的思路，GPU 上每段前后都要同步，或用逐请求 trace；
  2. 看 p95 而不只看 p50；
  3. 把测得的各阶段耗时与预算对比（skill 文件的默认分配：解码+预处理 15%、检测器 55%、检测后处理 5%、裁剪缩放 5%、分类器 15%、校验 <1%、序列化 4%），找出**第一个**超预算的阶段。
- **杠杆**（来自 skill 文件）：
  - **解码 / 预处理**：Pillow-SIMD、libjpeg-turbo、NVJPEG 在 GPU 上解码；
  - **检测器**：更小的 backbone、更低的输入分辨率、INT8、TensorRT；超预算 30% 以上就直接换模型；
  - **后处理**：用 `torchvision.ops` 在 GPU 上做 NMS，融合 mask 处理；
  - **裁剪缩放**：用 `grid_sample` 或批量 `interpolate` 在 GPU 上完成；
  - **分类器**：更小的模型、INT8、批处理；
  - **序列化**：orjson / protobuf。
- **常见误区**：
  - 默认认为模型最慢，直接去优化模型，结果瓶颈其实在解码；
  - 为了提速把 schema 校验从生产路径拿掉——skill 文件明确反对，正确做法是只在边界处校验。

### Q13 — 参考回答要点

- **原理**：GPU 在 batch=1 时利用率很低；把一个时间窗内到达的请求（或多个请求的 crop）拼成一个 batch，一次前向，再把结果分发回各请求，从而摊薄 kernel 启动和权重读取的开销。
- **取舍**：
  - 吞吐量提升，但每个请求最多多等一个窗口；
  - 负载很低时凑不满 batch，只会白白增加延迟——所以通常同时设置"最大 batch 大小"和"最长等待时间"两个条件，哪个先满足就触发。
- **窗口怎么选**：从延迟预算倒推（例如 p95 目标减去其余阶段耗时后的余量），再结合实际 QPS 压测；讲义的典型值是 20 ms，练习 3 用的是 10 ms。
- **不该用的场景**：
  - 延迟 SLA 很紧；
  - QPS 很低；
  - 模型本身已经能吃满硬件；
  - 输入尺寸差异很大、难以拼 batch（需要 padding 或按尺寸分桶）。
- **实现**：torchserve、Triton 原生支持动态批处理；小服务可以自己用 `asyncio.Queue` + 定时器实现一个 micro-batcher。

### Q14 — 参考回答要点

- **问题**：FastAPI 在单个事件循环中运行 `async def` 端点。`pipe.run` 是同步的、CPU/GPU 密集的调用，执行期间（可能几百毫秒）会**阻塞整个事件循环**，其他请求连读取请求体都做不了；健康检查也可能超时，导致实例被判定为不健康。
- **现象**：并发一上来，延迟按请求数线性堆积，吞吐量几乎不随并发增长；偶发健康检查失败。
- **改法**：
  1. 把端点写成普通的 `def`：FastAPI 会把它放到线程池中执行；
  2. 或在 `async def` 中用 `await run_in_threadpool(pipe.run, img)`（`starlette.concurrency`），文件读取仍然保持异步；
  3. 推理放到独立的推理服务器（Triton / torchserve）或进程池中，Web 层只负责 I/O；
  4. 配合 micro-batcher，用队列把并发请求聚合起来。
- **加分点**：
  - 线程池中跑 PyTorch 时注意 `torch.set_num_threads`，避免线程过度订阅；
  - 新版 FastAPI 推荐用 `lifespan` 代替 `@app.on_event("startup")` 来加载模型。

### Q15 — 参考回答要点

按"接口"逐个排查，因为单个模型没问题，说明问题出在拼接处：

1. **像素值域与归一化**：
   - 分类器是否需要 ImageNet 的均值/方差归一化？torchvision 的检测模型会在内部做归一化，但 ConvNeXt 等分类模型不会。讲义 Step 3 把 0–1 的 crop 直接送进 `convnext_tiny`，就缺了这一步；
   - 值域是 0–1 还是 0–255（见 Q10）？
2. **通道顺序**：RGB 还是 BGR（OpenCV 读图默认 BGR）？
3. **坐标格式**：xyxy 还是 cxcywh？绝对像素还是归一化坐标？裁剪时行列有没有写反（`tensor[:, y1:y2, x1:x2]`）？
4. **缩放方式**：训练时是保持长宽比缩放再中心裁剪，还是直接拉伸？本节代码直接把 crop 拉伸到固定尺寸，与分类器训练时的预处理可能不一致。
5. **索引映射**：`detection_index` 是否因为跳过了小框而错位（见 Q8）？
6. **类别表**：分类器的类别 id 与 `class_names` 是否来自同一个标签映射？

方法：把一张已知图像的中间结果逐阶段落盘（裁剪出的 crop 存成图片，看看裁对了没有），并在每个边界加断言或契约校验。

---

## 六、关联知识点

### 前置知识
- [阶段 04 · 06 物体检测——从头开始的 YOLO](../../06-object-detection-yolo/docs/zh.md)：检测器输出格式、NMS、框坐标约定。
- [阶段 04 · 08 实例分割——Mask R-CNN](../../08-instance-segmentation-mask-rcnn/docs/zh.md)：讲义中流水线使用的检测器。
- [阶段 04 · 04 图像分类](../../04-image-classification/docs/zh.md)：分类器的预处理与输出。
- [阶段 04 · 15 实时视觉——边缘部署](../../15-real-time-edge/docs/zh.md)：延迟测量纪律、百分位、量化与运行时。
- [阶段 04 · 01 图像基础知识](../../01-image-fundamentals/docs/zh.md)：通道顺序、值域、色彩空间这些"静默失败"的来源。

### 本节被哪些后续内容用到
- [阶段 04 · 19 OCR 和文档理解](../../19-ocr-document-understanding/docs/zh.md)：检测 + 识别的两阶段流水线。
- [阶段 04 · 27 多目标跟踪与视频记忆](../../27-multi-object-tracking/docs/zh.md)：在检测流水线后面接跟踪器。
- [阶段 11 · 03 结构化输出](../../../11-llm-engineering/03-structured-outputs/docs/zh.md)：同样用 Pydantic 约束模型输出。
- [阶段 11 · 13 生产级应用](../../../11-llm-engineering/13-production-app/docs/zh.md)：把模型包装成可靠服务的通用做法。
- [阶段 17 · 08 推理指标与 goodput](../../../17-infrastructure-and-production/08-inference-metrics-goodput/docs/zh.md)：吞吐、延迟与 SLA。
- [阶段 17 · 13 LLM 可观测性](../../../17-infrastructure-and-production/13-llm-observability/docs/zh.md)：trace ID 与分阶段计时的体系化做法。
- [阶段 19 · 04 多模态文档问答](../../../19-capstone-projects/04-multimodal-document-qa/docs/zh.md)、[阶段 19 · 12 视频理解流水线](../../../19-capstone-projects/12-video-understanding-pipeline/docs/zh.md)：更大规模的综合项目。

### 延伸关键词
`Pydantic model_validator` · `strict mode` · `FastAPI lifespan` · `run_in_threadpool` · `dynamic batching` · `Triton Inference Server` · `torchserve / BentoML` · `NVJPEG / Pillow-SIMD` · `trace ID` · `graceful degradation` · `RLE mask 编码`
