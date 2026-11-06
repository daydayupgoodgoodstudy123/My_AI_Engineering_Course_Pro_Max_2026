# 测验 · 具身 VLA：RT-2、OpenVLA、π0、GR00T（Embodied VLAs: RT-2, OpenVLA, π0, GR00T）

> **阶段 12 · 多模态 AI · 第 21 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 说明：中文讲义为机器翻译，π0 在多处被乱码成"=0""++0""%0"，"33ms"被译成"330米"，请以英文讲义为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | VLA 是什么 | vision-language-action：与 VQA 相同的 VLM 架构，但输出是动作（关节力矩、末端位姿、离散指令）而不是文本 |
| 2 | VLA 的四个难点 | 动作连续且高维（7-DOF 臂 + 3-DOF 夹爪 = 10 维 × 30 Hz）、机器人数据稀缺（~1M 轨迹 vs 5B+ 图文）、控制频率（30 Hz 只有 33 ms）、安全 |
| 3 | 离散分箱（RT-2） | 把归一化到 `[-1, 1]` 的每一维动作量化为 256 个 bin、映射到词表 ID；10-DOF 动作每步 10 个 token；讲义：RT-2 推理 3–5 Hz |
| 4 | Co-fine-tuning | 网页图文（描述、VQA）与机器人演示混合训练，保住网页知识的迁移（"move towards the fast-moving object"）；比例是超参数：VQA 太多忘动作，机器人太多丢常识 |
| 5 | OpenVLA | 开源 7B 参考：Llama 骨干 + DINOv2 + SigLIP 双视觉编码器，256-bin 动作 token，Open X-Embodiment 上 970k 轨迹训练，支持 LoRA 适配新机器人，讲义：A100 量化后 4–5 Hz |
| 6 | FAST tokenizer | 对动作序列按维度做 DCT、量化系数，压缩平滑轨迹；讲义：30 步轨迹从 300 个分箱 token 降到 ~10 个，推理快 3–5 倍 |
| 7 | π0 flow-matching 动作专家 | 小的动作 Transformer 读 VLM 隐状态，用 rectified flow 直接输出连续的 50 步动作块；讲义：~5 步去噪，等效 50 Hz 控制；连续动作保住平滑性 |
| 8 | GR00T N1 双系统 | System 2（大 VLM，讲义：~1 Hz）出子目标，System 1（小动作头，50–100 Hz）出关节指令；对应 Kahneman 的快慢思考，面向 >30 DOF 的人形机器人 |
| 9 | Open X-Embodiment | RT-X 汇集的跨机器人数据集（讲义：~1M 轨迹、22 种机器人）；训练前统一动作空间、归一化关节范围、统一相机尺寸；新机器人用 100–1000 条演示做 LoRA |
| 10 | 安全层在 VLA 之外 | 关节硬限位、速度软限幅、工作空间边界、新任务人工审批；"VLA 的输出是建议，不是命令" |

### 核心技能（能动手做到）

- [ ] 实现 256-bin 动作离散化与反离散化，算出量化误差上界，并能把截断改成四舍五入以减半误差
- [ ] 给定 DOF 和控制频率，算出离散分箱每秒需要的 token 数，判断 7B 自回归 VLM 能否跟上
- [ ] 实现 DCT 的逆变换，测量"只保留前 k 个系数 + 量化"对轨迹的重建误差，解释 FAST 对高频动作的局限
- [ ] 比较离散分箱、FAST、flow-matching 三种动作格式的 token 数、推理方式和平滑性
- [ ] 为一个新机器人设计微调与部署方案：数据量、动作归一化、控制频率核算、安全层
- [ ] 说清双系统架构的动机，并能为双足行走提出更细的分层

---

## 二、基础自测（选择题）

**Q1.**（讲义练习 1）一个 10-DOF 机械臂以 30 Hz 控制，用 256-bin 离散分箱，每秒需要生成多少个动作 token？

- A. 300
- B. 30
- C. 2,560
- D. 7,680

**Q2.** 用本节代码 `discretize([0.0])` 得到 bin 127，再 `undiscretize([127])` 得到的值是：

- A. 0.0
- B. +0.0039
- C. −0.0039
- D. −1.0

**Q3.** 本节 `discretize` 用 `int()` 截断，`undiscretize` 把 bin 映射回 `2t/255 − 1`。在 `[-1, 1]` 上，一次往返的最大绝对误差约为：

- A. 0（无损）
- B. 1/255 ≈ 0.0039
- C. 1/256 ≈ 0.0039，与 bin 数无关
- D. 2/255 ≈ 0.0078，即一整个 bin 宽

**Q4.** FAST tokenizer 的核心思路是：

- A. 把 bin 数从 256 增加到 4,096，提高精度
- B. 对每个动作维度沿时间做 DCT，保留并量化（主要是低频的）系数，从而用很少的 token 表示平滑轨迹
- C. 用扩散模型直接生成连续动作
- D. 把动作写成自然语言句子交给 LLM

**Q5.** 关于 π0 的动作输出，讲义的描述是：

- A. 每个时间步逐维自回归生成 256-bin token
- B. 只输出高层子目标，由另一个系统转换成关节指令
- C. 一个读取 VLM 隐状态的小型动作 Transformer，用 flow matching 训练，经少量去噪步直接输出连续的 50 步动作序列
- D. 把动作序列做 DCT 后量化成离散 token

**Q6.** GR00T N1 的双系统设计是：

- A. System 2 是大 VLM，慢速（讲义：~1 Hz）读场景和指令产出子目标；System 1 是小动作头，以 50–100 Hz 产出底层关节指令
- B. System 1 是大 VLM 负责规划，System 2 是小网络负责执行
- C. 两个系统都以 30 Hz 运行，只是参数量不同
- D. System 2 负责安全检查，System 1 负责所有决策

**Q7.** 按讲义，生产中 VLA 的安全措施应当：

- A. 完全交给 VLA 在训练中学会，不需要额外检查
- B. 只在仿真里测试，真机不需要
- C. 通过提高 co-fine-tuning 中网页数据的比例来保证
- D. 放在 VLA 之外的控制层：关节硬限位、速度限幅、工作空间边界、新任务人工审批；VLA 的输出只是建议

**Q8.** 本节 `compare_formats()` 打印：离散 300 token、FAST 40 token、flow-matching 1 token，"speedup: FAST ~7.5x"。下列说法正确的是：

- A. FAST 的 40 个 token 与讲义"~10 个 FAST token"一致
- B. "flow-matching 1 token"不可直接比较：π0 输出的是连续向量、要经过多步去噪，并不生成 token；7.5x 也只是 token 数之比，不是实测速度
- C. 代码实现了 FAST 的解码器，所以能报告重建误差
- D. 300 个离散 token 可以在一次前向中并行生成

---

## 三、动手 / 代码题

**Q9.** 阅读离散化代码：

```python
def discretize(action: list[float], bins: int = 256) -> list[int]:
    tokens = []
    for a in action:
        idx = int((a + 1) / 2 * (bins - 1))
        idx = max(0, min(bins - 1, idx))
        tokens.append(idx)
    return tokens


def undiscretize(tokens: list[int], bins: int = 256) -> list[float]:
    return [(2 * t / (bins - 1)) - 1 for t in tokens]
```

1. 为什么最大误差接近一整个 bin 宽（2/255），而运行输出写的 "max abs error: 0.0069 (bin width = 2/255 ~ 0.0078)"？
2. 改一处让最大误差减半，写出改后 demo 动作的 token 与最大误差。
3. 输入 `1.5` 或 `-2.0` 会发生什么？这在机器人上意味着什么？

**Q10.** `fast_compress` 只有编码没有解码：

```python
def fast_compress(trajectory, keep_coeff=4, bins=32):
    D = len(trajectory[0])
    tokens = []
    for d in range(D):
        series = [step[d] for step in trajectory]
        coeffs = dct(series)[:keep_coeff]
        for c in coeffs:
            c_norm = max(-1.0, min(1.0, c / len(series)))
            idx = int((c_norm + 1) / 2 * (bins - 1))
            tokens.append(idx)
    return tokens
```

1. 写出与代码中未归一化 DCT-II 配套的逆变换 `idct(coeffs, n)`。
2. 对代码中的平滑轨迹（30 步 × 10 维），分别在"只截断不量化"和"截断 + 32-bin 量化"两种情况下，计算保留 1、2、4、8、30 个系数时的最大重建误差。你观察到什么反常现象？原因是什么？

**Q11.**（讲义练习 2）把轨迹换成高频运动（如打鼓：`sin(2π·0.4·t + d)`，每 2.5 步一个周期），只截断不量化，保留 4、8、30 个系数时的误差各是多少？用户会失去什么？FAST 类方法应如何应对？

**Q12.**（讲义练习 3 的变体）要以 30 Hz 执行一个 10-DOF 动作流，分别计算三种格式对模型推理的要求：

1. 离散分箱：每秒要解码多少 token？
2. FAST：按讲义"30 步 ≈ 10 个 token"、以及按本节代码"30 步 = 40 个 token"，每秒各要多少 token？
3. π0 式动作块：每次推理输出 50 步，30 Hz 执行时每隔多久必须完成一次推理？讲义说"~5 步去噪"，若每步去噪 10 ms、视觉语言前缀 50 ms，单次推理约多久？这种"动作块"方式的隐患是什么？

---

## 四、面试高频题

**Q13.**（基础必考）什么是 VLA？动作可以怎样表示？请比较离散分箱、FAST、flow-matching 三种动作表示的优缺点。

**Q14.**（原理深挖）为什么 co-fine-tuning（网页数据 + 机器人数据混合）能让 VLA 泛化到新指令？比例失衡会出现什么问题？

**Q15.**（原理深挖）为什么 π0 用 flow matching 输出连续动作块，而不是像 RT-2 那样输出离散 token？"动作块"（action chunking）带来了什么好处和风险？

**Q16.**（场景设计）仓库里要把一台新型号机械臂接入一个开源 VLA 来做分拣，你会怎么做？请覆盖数据、微调、控制频率核算、安全层和评测。

**Q17.**（追问型）GR00T 为什么要拆成 System 1 / System 2？如果让你为双足行走再加一层"System 3"，它应该负责什么、以什么频率运行？

---

## 五、参考答案与解析

### Q1 — 答案：A

每个控制步 10 个 token（每维一个），`10 × 30 = 300` token/s。讲义说 OpenVLA 在 A100 上只有 4–5 Hz，也就是每秒约 40–50 个动作 token 的量级，离 300 token/s 差得很远，所以离散分箱无法支撑 30 Hz 控制（skill 文件："Claiming discrete-bin tokenization is fast enough for 30 Hz control. It is not."）。C 是 `10 × 256`；D 是 `30 × 256`，都把 bin 数当成了 token 数。

### Q2 — 答案：C

`int((0 + 1) / 2 × 255) = int(127.5) = 127`，`2 × 127 / 255 − 1 = −0.00392`（已实际运行验证，demo 输出中 0.0 恢复为 −0.004）。256 个 bin 均匀分布在 `[-1, 1]` 上时，0 恰好落在 bin 127 与 128 之间，**没有任何一个 bin 能精确表示 0**。这对"保持不动"这种最常见的动作并不友好。

### Q3 — 答案：D

`int()` 对非负数向下取整，`a` 被映射到它左侧的 bin 边界，最坏情况下差将近一整格：在 `[-1, 1]` 上取 100,001 个点实测最大误差为 0.007843 ≈ 2/255。改成 `round()` 后实测最大误差为 0.003922 ≈ 1/255（B 是改进后的结果）。C 的表述错误：误差上界随 bin 数变化（bin 越多越小）。

### Q4 — 答案：B

讲义："FAST (Frequency-domain Action Sequence Tokenizer) compresses action sequences via DCT and quantizes the coefficients." 平滑轨迹的能量集中在低频，少数系数就能表示。A 只会让 token 更精细，不会变少；C 是扩散/flow 类动作头；D 不是 FAST。（补充：据 FAST 论文，量化后的系数还会再经 BPE 压缩，token 数随轨迹复杂度变化，这一步本节代码没有实现。）

### Q5 — 答案：C

讲义："A small action transformer reads the VLM's hidden states and outputs a continuous 50-step action sequence via rectified flow ... Inference: full action sequence emitted in ~5 denoising steps, effectively 50 Hz control." A 是 RT-2/OpenVLA；B 是 GR00T 的 System 2；D 是 FAST。

### Q6 — 答案：A

讲义："System 2: a large VLM ... producing high-level subgoals at ~1 Hz. System 1: a small action-head transformer producing low-level 50-100 Hz joint commands conditioned on the subgoals." B 把两个系统弄反了（Kahneman 的 System 1 是"快"的直觉系统）；C、D 无依据。（具体运行频率以 GR00T N1 论文为准，讲义给出的是近似值。）

### Q7 — 答案：D

讲义 "Safety and action limits"：四项措施 "sit outside the VLA as control-layer checks. The VLA's output is a suggestion, not a command." skill 文件的硬性否决第一条也是"Recommending VLA without a safety-layer spec"。A、C 把安全寄托在模型行为上，模型总会遇到分布外输入；B 忽略了真机风险。

### Q8 — 答案：B

- "1 token" 是代码里写死的 `continuous_flow_count = 1`。π0 不输出 token，而是输出连续动作向量，并需要多步去噪（每步都是一次动作专家前向），用"token 数"比较三者没有意义。
- "~7.5x" 只是 `300 / 40`，不是实测推理加速。
- A 错：代码每维保留 4 个系数，10 维共 40 个 token，是讲义"~10 个"的 4 倍。
- C 错：代码没有逆 DCT，无法知道 40 个 token 能否重建出原轨迹（Q10 的实测表明 32-bin 量化损失很大）。
- D 错：离散分箱是逐 token 自回归生成的（代码注释 "per-step autoregressive"）。

### Q9 — 参考答案

1. `int()` 截断把每个值"往下"推到左侧的 bin 边界，误差范围是 `[0, 2/255)`，最坏接近一个 bin 宽；demo 的 10 个值碰巧最大只差 0.0069（来自 `-0.75` → bin 31 → −0.7569），没有触到上界。运行输出中的 "bin width = 2/255" 说的正是这个上界。
2. 把 `int(...)` 改成 `round(...)`：

```python
idx = round((a + 1) / 2 * (bins - 1))
```

   实测：demo 动作的 token 变为 `[140, 64, 159, 32, 242, 115, 128, 170, 42, 191]`（原为 `[140, 63, 159, 31, 242, 114, 127, 169, 42, 191]`），最大误差 0.0039；在整个 `[-1, 1]` 上的最大误差也从 0.00784 降到 0.00392，正好减半。更彻底的做法是让 bin 代表区间中心（RT-2/OpenVLA 一类实现通常这样做），并按数据的分位数确定归一化范围。

3. 越界值被 `max(0, min(255, idx))` 截到 bin 0 或 255，即悄悄变成 −1.0 或 1.0。好处是不会产生非法 token；坏处是**静默失真**——如果上游归一化范围设错（比如真实关节范围比假设的大），机器人会在边界处"卡住"而没有任何报警。工程上应该在归一化阶段统计越界比例并告警，同时由控制层的硬限位兜底。

### Q10 — 参考答案

1. 代码中的 DCT 是未归一化的 DCT-II：`X_k = Σ_i x_i · cos(π/n · (i + 0.5) · k)`。对应的逆变换为 `x_i = X_0 / n + (2/n) Σ_{k≥1} X_k · cos(π/n · (i + 0.5) · k)`：

```python
import math

def idct(coeffs, n):
    """未归一化 DCT-II 的逆变换；没保留的高频系数视为 0"""
    c = list(coeffs) + [0.0] * (n - len(coeffs))
    return [c[0] / n + 2 / n * sum(c[k] * math.cos(math.pi / n * (i + 0.5) * k)
                                   for k in range(1, n))
            for i in range(n)]
```

   验证：保留全部 30 个系数、不量化时重建误差为 0。

2. 实测（10 个维度中的最大误差，轨迹幅度为 ±1）：

| 保留系数数 | 只截断 | 截断 + 32-bin 量化（代码方案） |
|-----------|--------|----------------------------|
| 1 | 1.132 | 1.159 |
| 2 | 0.543 | 0.607 |
| 4 | 0.155 | 0.332 |
| 8 | 0.044 | 0.580 |
| 30 | 0.000 | 1.341 |

   反常现象：加了量化后，**保留越多系数误差反而越大**（8 个比 4 个差，30 个最差）。原因：
   - 代码把每个系数除以 `len(series)` 再按 32 个 bin 量化，步长约 `2/31 ≈ 0.065`（归一化单位），而逆变换中高频系数要乘以 `2`，量化误差被放大；
   - `int()` 截断引入了系统性偏差（总是偏小），每多保留一个系数就多叠加一份偏差；
   - 高频系数本身很小（第 3 个以后的 `c/n` 约 0.001–0.04），32-bin 量化根本分辨不出来，量化噪声比信号还大。

   结论：本节的 `fast_compress` 只演示了"DCT + 截断 + 量化"的形状，并不是一个能用的编码器。据 FAST 论文，实际做法是对 DCT 系数乘一个缩放因子后四舍五入（高频系数大多变成 0），再用 BPE 把稀疏的整数序列压缩成 token，而不是固定"每维 4 个系数 × 32 bin"。

### Q11 — 参考答案

实测（只截断不量化）：保留 4 个系数误差 1.078，保留 8 个 1.142，保留 30 个才回到 0。轨迹每 2.5 步一个周期，能量集中在高频，低频系数几乎为零，**截掉高频就等于把整个动作抹掉**——重建出来的是一条接近平直的线，误差和信号幅度相当。

- 用户会失去：快速往复动作的节奏与幅度（打鼓、拧螺丝、擦拭、摇晃），机器人会变得"迟缓"或干脆不动。
- 应对：不要固定保留前 k 个系数，而是按幅值保留（像 FAST 那样缩放后四舍五入，保留所有非零系数，再用 BPE 压缩），token 数随轨迹复杂度自适应；或者对高频任务缩短轨迹块、提高控制频率；或者改用连续动作头（flow matching），不受频域截断限制。

### Q12 — 参考答案

1. 离散分箱：`10 × 30 = 300 token/s`。
2. FAST：一个 30 步轨迹块覆盖 1 秒（30 Hz）。按讲义 ~10 token/块，即约 **10 token/s**；按本节代码 40 token/块，即 **40 token/s**。注意这是"吞吐"要求；首个动作要等整块 token 解码完、逆 DCT 之后才能执行，块越长延迟越大。
3. π0 式动作块：一块 50 步，30 Hz 执行可用 `50 / 30 ≈ 1.67 s`（若按讲义的 50 Hz 执行则正好 1 s），推理必须在这段时间内完成下一块。按题设，单次推理约 `50 + 5 × 10 = 100 ms`，远小于 1.67 s，吞吐很充裕。
   - 隐患：块内是**开环执行**，环境在这 1–1.7 秒里变化（物体被碰歪、人伸手进来）时，模型要等到下一块才能反应；常见缓解是"边执行边提前推理下一块、重叠部分做平滑融合"或缩短实际执行的步数。
   - 对比讲义："Compare throughput to OpenVLA's autoregressive decode at 4-5 Hz"——OpenVLA 每次推理只产出 1 步动作，每秒 4–5 步；π0 每次产出 50 步，靠的就是"连续动作块 + 少量去噪步"。（π0 论文中的去噪步数与讲义的"~5"可能不同，具体以论文为准。）

### Q13 — 参考回答要点

- **定义**：VLA 以图像（多相机）+ 语言指令（+ 机器人本体状态）为输入，输出机器人动作；骨干通常是预训练 VLM。
- **三种动作表示**：

| 表示 | 代表 | 优点 | 缺点 |
|------|------|------|------|
| 离散分箱 | RT-2、OpenVLA | 直接复用 LLM 的 token 预测和交叉熵，实现简单，能与网页数据共训 | 每步每维一个 token，自回归慢（讲义 3–5 Hz）；量化误差；动作不平滑 |
| FAST（DCT + 量化） | π0-FAST 等 | 平滑轨迹压缩率高，token 少、解码快（讲义 3–5 倍） | 高频动作需要更多系数；量化与压缩细节影响精度 |
| 连续 flow matching | π0、GR00T 的 System 1 | 连续、平滑、一次输出整个动作块，控制频率高 | 训练和推理都比交叉熵复杂；需要多步去噪；与语言 token 的统一建模更难 |

- 加分点：说明"动作 token 化"让 VLA 能继承 LLM 的训练基础设施，这是 RT-2 能 co-fine-tune 的前提。

### Q14 — 参考回答要点

- **机制**：网页图文数据里有大量物体、属性、空间关系、常识（"快速移动的物体""第三大的物体"）；机器人演示只覆盖有限的任务和措辞。混合训练让模型在学动作的同时不忘语义理解，新指令可以借助网页知识映射到已学过的动作原语上。讲义例子："RT-2 can follow 'move towards the fast-moving object' even though 'fast-moving' isn't in training data"。
- **比例失衡**：VQA 太多 → 动作头学不扎实，"forgets actions"；机器人数据太多 → 灾难性遗忘语言和视觉常识，只能执行演示里的原话（"pick up the red cube (in demo)"），换个说法就失败。
- **比例**：讲义给出 RT-2 约 1:1、OpenVLA 约 0.5:1（网页:机器人），并强调这是要随数据规模调的超参数；skill 文件建议从 0.5:1 起步。
- 加分点：机器人数据内部也要配比（不同机器人、不同任务的采样权重），否则大数据集会淹没小数据集。

### Q15 — 参考回答要点

- **离散 token 的问题**：量化误差；每维每步一个 token 导致序列长、自回归慢；相邻 bin 在交叉熵里是"不同类别"，模型不知道 127 和 128 很接近，输出可能抖动、不平滑。
- **flow matching 的好处**：直接在连续空间建模动作分布，能表示多峰分布（同一个场景有多种合理动作）；一次输出整个动作块，少数几步去噪即可，支持高频控制；讲义："The continuous-action formulation preserves smoothness that discretization destroys"。
- **动作块的好处**：摊薄 VLM 推理开销；块内动作时间上连贯；减少"每步重新决策"造成的抖动。
- **风险**：块内开环，对突发变化反应慢；块与块衔接处可能跳变（需平滑融合）；去噪步数太少质量下降，太多又慢。
- 加分点：讲义说 π0 动作头单独用 flow-matching loss 训练，VLM 预训练不变，这种"冻结主干 + 专家头"的结构便于复用强大的 VLM。

### Q16 — 参考回答要点

1. **选型**：单臂分拣、对平滑性有要求 → OpenVLA（LoRA 微调成本低）或 π0 类 flow-matching 方案；skill 文件建议预算有限时不要从零训练，在 OpenVLA 上微调。
2. **数据**：遥操作采集 500–1,000 条覆盖各类物品、位置和光照的演示（skill 文件：LoRA 约 500–1,000 条，全量微调约 1 万条）；统一动作空间（末端增量位姿 + 夹爪开合），按本机关节范围归一化到 `[-1, 1]`，统计越界比例；相机分辨率与预训练一致。
3. **微调**：LoRA 微调；混入少量通用 VQA / 原始 OpenX 数据防止遗忘；保留验证集（新物品、新摆放）。
4. **控制频率核算**：分拣通常 5–10 Hz 末端控制即可；离散分箱 7B 只有 4–5 Hz，若需要更高频，换 FAST 或 flow-matching 动作头，或用动作块 + 底层插值控制器。
5. **安全层**：关节限位、速度/加速度限幅、工作空间与禁区（人员通道）、力矩异常检测与急停、新 SKU 首次抓取需人工确认；全部在 VLA 外部的控制器实现。
6. **评测**：先仿真后真机；指标包括成功率、平均耗时、碰撞/掉落次数、触发安全层的次数；分布内物品与新物品分开统计；灰度上线并保留人工接管。

### Q17 — 参考回答要点

- **为什么拆**：大 VLM 推理慢（秒级或亚秒级），人形机器人全身 >30 DOF 需要 50–100 Hz 以上的闭环控制；把"想做什么"（慢、需要语义）和"怎么动"（快、需要反应）分开，慢规划不会阻塞快控制，System 1 可以保持小而快。讲义："slow VLM-sized planning does not block fast control; System 1 stays small for latency"。skill 文件也规定 >30 DOF 的人形必须用双系统。
- **System 3 提案（双足行走）**：在 System 1 之下加一个**平衡/反射层**：
  - 职责：基于 IMU、足底力传感器、关节编码器做姿态稳定、落脚点微调、被推后的恢复、跌倒保护；
  - 频率：几百 Hz 到 1 kHz（与电机控制环同级）；
  - 实现：模型预测控制（MPC）或在仿真中用强化学习训练的小策略（sim-to-real），不依赖视觉语言输入；
  - 接口：System 1 给出期望的身体速度/姿态轨迹，System 3 负责在物理约束下跟踪并保证不摔倒，必要时可以否决 System 1 的指令。
- 结果形成"语义规划（~1 Hz）→ 动作生成（50–100 Hz）→ 平衡反射（~1 kHz）"三层，越往下越快、越小、越接近物理。

---

## 六、关联知识点

### 前置知识
- [阶段 12 · 05 LLaVA 与视觉指令微调](../../05-llava-visual-instruction-tuning/docs/zh.md)：本节的先修课，VLA 的骨干就是这样的 VLM。
- [阶段 08 · 13 Flow Matching 与 Rectified Flows](../../../08-generative-ai/13-flow-matching-rectified-flows/docs/zh.md)：理解 π0 动作专家的训练目标。
- [阶段 10 · 01 Tokenizers: BPE, WordPiece, SentencePiece](../../../10-llms-from-scratch/01-tokenizers/docs/zh.md)：FAST 在 DCT 量化后用 BPE 再压缩，以及"动作 token 化"与文本 token 化的类比。
- [阶段 11 · 08 Fine-Tuning 与 LoRA & QLoRA](../../../11-llm-engineering/08-fine-tuning-lora/docs/zh.md)：用 LoRA 把 OpenVLA 适配到新机器人。
- [阶段 09 · 11 从仿真到现实的迁移](../../../09-reinforcement-learning/11-sim-to-real-transfer/docs/zh.md)：GR00T 使用的 sim-to-real 数据思路。

### 本节被哪些后续内容用到
- [阶段 12 · 25 多模态 Agents 与计算机操作（综合项目）](../../25-multimodal-agents-computer-use/docs/zh.md)："看—想—动"的闭环从机器人迁移到屏幕操作。
- [阶段 15 · 01 从聊天机器人转向长程 Agents](../../../15-autonomous-systems/01-long-horizon-agents/docs/zh.md)：讲义说 VLA 是通往阶段 15 自主系统的桥梁。
- [阶段 15 · 14 紧急停止开关、Circuit Breakers 与金丝雀 Tokens](../../../15-autonomous-systems/14-kill-switches-canaries/docs/zh.md)：与 VLA 外部安全层同一思路的"急停"设计。
- [阶段 15 · 15 Human-in-the-Loop：先提出方案，再 Commit](../../../15-autonomous-systems/15-propose-then-commit/docs/zh.md)：对应"新任务需人工审批、VLA 输出只是建议"。
- [阶段 04 · 28 世界模型与视频扩散](../../../04-computer-vision/28-world-models-video-diffusion/docs/zh.md)：用世界模型生成机器人训练数据与做规划的方向。

### 延伸关键词
`VLA` · `action tokenization` · `256-bin discretization` · `co-fine-tuning` · `OpenVLA` · `FAST / DCT` · `π0 / flow matching` · `action chunking` · `GR00T N1` · `System 1 / System 2` · `Open X-Embodiment` · `LoRA adaptation` · `safety envelope`
