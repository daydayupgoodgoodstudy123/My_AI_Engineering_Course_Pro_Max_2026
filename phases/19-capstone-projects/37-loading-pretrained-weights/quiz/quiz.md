# 测验 · 加载预训练 Weights（Loading Pretrained Weights）

> **阶段 19 · 综合项目 · 第 37 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 权重 = 名字 + 形状 + 字节布局 | 同一个参数在发布的 checkpoint 和本地模型里有三重"身份"，loader 要把三者都对齐，盲目复制会得到一个只会胡言乱语的模型 |
| 2 | Name map（键重映射） | 一个固定的 `dict`：`wte → tok_embed`、`h.N.attn.c_attn → blocks.N.attn.qkv`、`ln_1.weight → ln1.scale` 等；按层号循环展开，每层 12 条，外加 4 条全局条目 |
| 3 | Transpose-on-load（Conv1D 布局） | GPT-2 的 `c_attn`、`c_proj`、`c_fc` 权重存成 `(in, out)`，而 `nn.Linear.weight` 是 `(out, in)`；只对这三种 `.weight` 后缀做 `.t()`，bias 与 LayerNorm 不转置 |
| 4 | Shape check | 映射、转置之后逐个比较形状；不一致就记入 `shape_mismatch`、拒绝赋值。**注意**：它查不出方阵（如 `attn.c_proj`）忘了转置 |
| 5 | 先校验、后赋值 | 代码把通过检查的张量先放进 `pending`，只要有任何 shape mismatch 就一个都不写；赋值在 `torch.no_grad()` 里用 `copy_` 原地完成 |
| 6 | Weight tying alias | LM head 不在文件里：它与 `tok_embed` 共享同一块存储（`lm_head.weight = tok_embed.weight`）；改成"复制一份"会打断共享并让参数量悄悄增加 `V × d` |
| 7 | `LoadReport` | 记录 `loaded / missing / unexpected / shape_mismatch` 四个列表；`ok()` = 没有 missing 且没有 mismatch（`unexpected` 不影响 `ok`） |
| 8 | Stub fixture | 用与真实 GPT-2 相同的命名和 Conv1D 布局生成一个小 safetensors 文件，离线、秒级跑通全部代码路径 |
| 9 | 加载后的健全性检查 | 参数"指纹"（各参数 L2 范数之和）必须变化、同一 prompt 的贪心生成必须变化、`lm_head` 与 `tok_embed` 的 `data_ptr()` 必须相同 |
| 10 | safetensors 格式 | 纯张量容器、不执行代码；`safe_open` 可以按名字懒加载单个张量；`save_file` 拒绝保存共享内存的张量 |

### 核心技能（能动手做到）

- [ ] 给定任意 GPT-2 尺寸，写出完整的 pretrained → local 名称映射，并算出文件中应有的张量个数（`4 + 12 × 层数`）
- [ ] 说清楚哪些张量需要转置、为什么，以及"只靠 shape check"会漏掉哪一类转置错误
- [ ] 读懂 `load_safetensors` 的两阶段流程（收集 → 统一赋值），并指出它在"缺张量"时并不是原子的
- [ ] 用 `data_ptr()` 验证 weight tying 在加载后仍然成立，并解释 `named_parameters()` 为什么只有 52 个而 `state_dict()` 有 53 个键
- [ ] 为 loader 增加 `dtype` 转换、`expected_layers` 检查、前缀剥离（如 `transformer.`）等工程化功能
- [ ] 用"加载前后指纹 + 贪心样本对比"给任何权重加载流程加一道最便宜的门禁

---

## 二、基础自测（选择题）

**Q1.** 在发布的 GPT-2 Small checkpoint 里，`h.0.attn.c_attn.weight` 的形状是什么？本节 loader 会怎么处理它？

- A. `(768, 2304)`；loader 对它做 `.t()` 得到 `(2304, 768)`，再与 `blocks.0.attn.qkv.weight` 比较形状
- B. `(2304, 768)`；与 `nn.Linear` 布局一致，直接复制
- C. `(768, 768)`；loader 把它复制三次分别给 Q、K、V
- D. `(3, 768, 768)`；loader 沿第 0 维切分成三个矩阵

**Q2.** 下列张量中，`_needs_transpose` 返回 `True` 的是：

- A. `h.0.attn.c_attn.bias`
- B. `wte.weight`
- C. `h.3.mlp.c_proj.weight`
- D. `h.0.ln_1.weight`

**Q3.** 为什么 safetensors 文件里没有 `lm_head.weight`？

- A. LM head 太大，需要单独下载
- B. LM head 在推理时由 logits 反推得到
- C. LM head 是随机初始化的，不需要预训练
- D. GPT-2 使用 weight tying：输出层与 token embedding 共享同一块存储，加载 `wte` 之后 head 自然就有了正确的值

**Q4.** 本节 demo 的配置为 4 层、`d_model=192`、`vocab=256`。`make_stub_safetensors` 生成的文件中有多少个张量？

- A. 48
- B. 52
- C. 53
- D. 56

**Q5.** demo 把 `wte.weight` 换成 `(256, 193)` 的错误张量后重新加载，`bad report` 的输出是：

- A. `loaded=51 missing=1 unexpected=0 shape_mismatch=1`
- B. `loaded=51 missing=0 unexpected=0 shape_mismatch=1`
- C. `loaded=0 missing=52 unexpected=0 shape_mismatch=1`
- D. `loaded=0 missing=0 unexpected=1 shape_mismatch=1`

**Q6.** 假设你把 `CONV1D_SUFFIXES` 里的 `"c_proj.weight"` 写成了 `"mlp.c_proj.weight"`（于是注意力输出投影 `attn.c_proj.weight` 不再被转置）。加载本节的 stub 会发生什么？

- A. 加载"成功"：`loaded=52 shape_mismatch=0`，但每层注意力输出投影都装成了转置后的错误矩阵
- B. 每层报告一个 shape mismatch，共 4 个
- C. 所有张量都进入 `unexpected`
- D. 抛出 `RuntimeError`，因为 `copy_` 的形状不匹配

**Q7.** demo 中随机初始化的模型对 prompt `[7, 11, 13, 17]` 做 8 步贪心生成，得到 `[7, 11, 13, 17, 17, 17, 17, ...]`，一直重复最后一个 token。最主要的原因是：

- A. `quick_generate` 的随机种子固定为 0
- B. 因果 mask 写反了，模型只能看到当前 token
- C. 随机初始化时注意力权重全为 0
- D. `nn.Embedding` 默认按 N(0, 1) 初始化，范数远大于各层输出，残差流基本就是当前 token 的 embedding；而 weight tying 让 logits = `LN(x) · Eᵀ`，与自身 embedding 的点积最大

**Q8.** 对开启 weight tying 的 `GPTModel`，下列说法正确的是：

- A. `named_parameters()` 会返回 `lm_head.weight` 和 `tok_embed.weight` 两个条目，参数量被重复计算
- B. `named_parameters()` 会对共享参数去重，所以本节 demo 中只有 52 个条目、不含 `lm_head.weight`；而 `state_dict()` 有 53 个键
- C. `state_dict()` 不包含 `lm_head.weight`
- D. 用 `safetensors.torch.save_file(model.state_dict(), ...)` 可以直接保存，并在磁盘上自动去重

---

## 三、动手 / 代码题

**Q9.** 讲义的生产经验第一条是"在任何赋值之前先校验整个文件，半加载的模型是沉默的故障机器"。阅读下面的代码：

```python
    if report.shape_mismatch:
        expected = set(local_params.keys())
        for name in sorted(expected - seen_local):
            report.missing.append(name)
        return report

    with torch.no_grad():
        for src_name, local_name, tensor in pending:
            target = local_params[local_name]
            target.copy_(tensor.to(device=target.device, dtype=target.dtype))
            seen_local.add(local_name)
            ...
    expected = set(local_params.keys())
    for name in sorted(expected - seen_local):
        report.missing.append(name)
```

1. 如果 stub 文件里**少了** `ln_f.bias`（没有 shape mismatch），报告是什么？模型被修改了吗？
2. 这与讲义的原则有什么矛盾？请修改代码，使"缺张量"与"形状不匹配"一样在赋值**之前**被拒绝。

**Q10.** demo 的 shape mismatch 路径打印 `loaded=0 missing=52 unexpected=0 shape_mismatch=1`。

1. 文件里明明 52 个张量都在（只有 `wte` 形状错），为什么报告"missing=52"？这对排错有什么误导？
2. 代码中 `seen_local.add("lm_head.weight")` 和 `if model.lm_head.weight.data_ptr() != model.tok_embed.weight.data_ptr(): model.lm_head.weight = model.tok_embed.weight` 这两处，在 demo 配置下实际起作用吗？为什么？

**Q11.** 讲义 "The Problem" 一节写的是 `transformer.h.0.attn.c_attn.weight`，而 name map 的键是 `h.0.attn.c_attn.weight`。

1. 把 stub 的每个键都加上 `transformer.` 前缀后再加载，报告是什么？`ok()` 返回什么？
2. 写一个 `normalize_name(src_name)`，在映射前剥离可选前缀；并说明如果文件里还有不是参数的条目（例如某些实现会把因果 mask buffer 存成 `h.N.attn.bias`），loader 会怎么处理它们，是否影响 `ok()`。

**Q12.** 完成讲义练习 1 和 2：给 `load_safetensors` 增加 `dtype=None` 与 `expected_layers=None` 两个参数。

1. `dtype` 不为空时在赋值时把张量转换为目标类型；说明现有代码的 `tensor.to(dtype=target.dtype)` 已经在做什么，以及"把 float32 模型降到 bfloat16"应该转换张量还是转换模型。
2. `expected_layers` 不为空时，扫描文件中出现的 `h.N` 层号，若最大层号 + 1 不等于它就在赋值前抛出 `ValueError`。为什么不能只依赖 `missing`/`unexpected` 来发现层数不一致？

---

## 四、面试高频题

**Q13.**（基础必考）把一个开源 checkpoint 加载进你自己写的模型，需要处理哪几类不一致？各自如何检测？

**Q14.**（原理深挖）什么是 weight tying？加载时为什么要"别名"而不能"复制"？它对参数量、优化器和保存 checkpoint 各有什么影响？

**Q15.**（工程实践）请设计一个生产级的权重 loader：要处理哪些失败模式？报告里要包含什么？PyTorch 自带的 `load_state_dict(strict=...)` 能帮你做到哪些、做不到哪些？

**Q16.**（场景设计）要把同一个 loader 扩展到 LLaMA 类模型（讲义练习 5），name map 和形状检查需要做哪些改变？

**Q17.**（追问型）为什么业界越来越多用 safetensors 而不是 `torch.save` 的 pickle 文件？`safe_open` 的懒加载对大模型有什么意义？

---

## 五、参考答案与解析

### Q1 — 答案：A

讲义表格："`h.N.attn.c_attn.weight` | (768, 2304) | Fused QKV linear weight"。GPT-2 原始实现的 `Conv1D` 用 `x @ W + b`，权重是 `(in, out)`；`nn.Linear` 计算 `x @ W.T + b`，权重是 `(out, in)`。所以 loader 做 `.t()` 得到 `(2304, 768)` 再比对形状。本节 stub 里同样如此：实际读出 `h.0.attn.c_attn.weight` 形状为 `(192, 576)`，转置后为 `(576, 192)`。

- B：讲义 "The Problem" 一节确实写了 `(2304, 768)`，但与它自己的表格矛盾——以表格和代码为准，原始文件是 `(in, out)`。
- C、D：GPT-2 的 QKV 是一个融合的 `768 → 2304` 线性层，本地模型同样是融合的 `qkv`，之后才在前向中 `split`。

### Q2 — 答案：C

`CONV1D_SUFFIXES = ("c_attn.weight", "c_proj.weight", "c_fc.weight")`，`_needs_transpose` 用 `endswith` 判断。`h.3.mlp.c_proj.weight` 以 `c_proj.weight` 结尾，返回 True。bias（A）是一维向量无所谓转置；`wte`（B）是 embedding 表，本来就是 `(vocab, d)`，与 `nn.Embedding.weight` 一致；LayerNorm 的 weight（D）也是一维。测试 `test_only_conv1d_suffixes_transpose` 正是验证这一点。

### Q3 — 答案：D

讲义："The LM head is not in the file at all; the model relies on weight tying with `wte`"。本地模型在 `__init__` 里执行 `self.lm_head.weight = self.tok_embed.weight`，两者是同一个 `Parameter` 对象。loader 用 `copy_` 原地写入 `tok_embed.weight`，LM head 自动获得同样的值。demo 实测加载后 `lm_head tied to tok_embed: True`。A、B、C 都不是原因。

### Q4 — 答案：B

全局 4 个（`wte`、`wpe`、`ln_f.weight`、`ln_f.bias`）+ 每层 12 个（2 个 LayerNorm × 2、`c_attn`/`attn.c_proj`/`c_fc`/`mlp.c_proj` 各有 weight 和 bias）× 4 层 = 52。测试 `test_stub_writes_expected_tensor_count` 用的公式就是 `4 + 12 × num_layers`。C（53）是 `state_dict()` 的键数（多了一个 `lm_head.weight` 别名）；GPT-2 Small（12 层）对应 148 个张量。

### Q5 — 答案：C

实际运行输出：`bad report : loaded=0 missing=52 unexpected=0 shape_mismatch=1`，`first mismatch : ('wte.weight', (256, 193), (256, 192))`。loader 先遍历全部张量，只把通过检查的放进 `pending`；一旦 `report.shape_mismatch` 非空就直接返回，`pending` 里的 51 个张量一个都不写，所以 `loaded=0`。而 `missing` 被填成"所有没赋值的本地参数"，于是是 52（这个语义有误导性，见 Q10）。A、B 描述的是"部分加载"，恰恰是本节刻意避免的行为。

### Q6 — 答案：A

已实际验证：只漏掉注意力 `c_proj` 时，报告是 `loaded=52 missing=0 unexpected=0 shape_mismatch=0`，`ok()` 为 True。原因是 `attn.c_proj.weight` 是 `(d, d)` 方阵，转置前后形状相同，shape check 无能为力。对比：若整个 `c_proj.weight` 后缀都漏掉，`mlp.c_proj.weight` 是 `(768, 192)` vs `(192, 768)`，会报 4 个 mismatch（B 描述的是这种情况）；若完全不转置，报 12 个。教训：**shape check 是必要条件不是充分条件**，还需要数值级的检查（例如用参考实现在同一输入上对比 logits）。C、D 都不会发生——名字映射没变，且 mismatch 时根本不会调用 `copy_`。

### Q7 — 答案：D

实测：随机初始化的 demo 模型对 256 个单 token 输入做一次前向，`argmax == 输入 token` 的比例是 256/256。`nn.Embedding` 默认 N(0, 1) 初始化，`tok_embed` 的 Frobenius 范数约 221.7（每行范数约 √192 ≈ 13.9），而各线性层用 PyTorch 默认的小尺度初始化，残差流几乎就是当前 token 的 embedding（加上较小的位置 embedding）；经过 `final_ln` 后与 `Eᵀ` 相乘，与自己的点积 ≈ ‖e‖² 远大于与其它随机向量的点积。A 错：`quick_generate` 用的是 `argmax`，种子根本不影响结果；B、C 不是事实。加载 stub（embedding std = 0.02）后这种"自我复读"被打破，生成变为 `[..., 17, 191, 191, 191, 191, 191, 150, 241]`。

### Q8 — 答案：B

实测：`len(dict(model.named_parameters())) = 52`，`'lm_head.weight' in ...` 为 False；`len(model.state_dict()) = 53`，多出的正是 `lm_head.weight`。`named_parameters()`/`parameters()` 默认对同一个 `Parameter` 去重，所以参数量（1,841,280）不会重复计算，A 错；C 错，`state_dict` 会保留别名键。D 错：实测 `save_file(model.state_dict(), ...)` 抛出 `RuntimeError: Some tensors share memory ... [{'tok_embed.weight', 'lm_head.weight'}]`，提示改用 `save_model`。这也解释了为什么 GPT-2 文件里干脆不存 LM head。

### Q9 — 参考答案

1. 实测：删掉 `ln_f.bias` 后加载，报告为 `loaded=51 missing=1 unexpected=0 shape_mismatch=0`，`missing=['final_ln.shift']`，`ok()` 为 False，但**模型指纹已经变化**——51 个张量已被写入。`final_ln.shift` 保留随机初始化值（这里恰好是 0，所以数值上看不出问题；换成其它参数就会是半随机半预训练的"弗兰肯斯坦"模型）。
2. 矛盾：讲义要求"Open the file ... run the full mapping with shape checks, and only on success start assigning"，但代码只对 shape mismatch 做了"先校验"，缺失检查放在赋值之后。修改：在赋值前根据 `pending` 计算缺失集合，任何一类问题都提前返回。

```python
    planned = {local for _, local, _ in pending}
    expected = set(local_params.keys())
    if model.cfg.weight_tying:
        expected.discard("lm_head.weight")       # 别名不需要来自文件
    missing = sorted(expected - planned)
    if report.shape_mismatch or missing:
        report.missing.extend(missing)          # 只列真正缺的
        return report                           # 一个都不写
    with torch.no_grad():
        ...                                     # 原有赋值循环
```

要点：把"是否赋值"做成全有或全无；`missing` 的含义固定为"文件里找不到来源的本地参数"。如需容忍某些缺失（如分类头），应显式传入 `allow_missing` 白名单，而不是默认放行。

### Q10 — 参考答案

1. mismatch 分支里 `seen_local` 还是空集（只在赋值时才 `add`），于是 `expected - seen_local` 等于全部 52 个本地参数，都被当成 missing。"missing" 被混用为"未赋值"和"文件里没有"两种含义：看到 `missing=52` 的人会以为是名字映射全错了，实际上只有一个张量形状不对。修法见 Q9：mismatch 分支里只报告真正没有来源的参数，或干脆在报告里另设 `not_assigned` 字段。
2. 都不起作用：
   - `named_parameters()` 对共享参数去重，`local_params` 里根本没有 `lm_head.weight`，所以 `seen_local.add("lm_head.weight")` 对 `expected - seen_local` 毫无影响（是一行死代码）。如果 `weight_tying=False`，`lm_head.weight` 会出现在 `local_params` 里，而文件里没有对应张量，就会被正确地报告为 missing、`ok()` 为 False——这恰恰说明"不共享权重的模型无法从 GPT-2 文件完整加载"。
   - `copy_` 是**原地**写入 `tok_embed.weight`，不会替换 `Parameter` 对象，别名关系始终保持，`data_ptr()` 本来就相等，`if` 分支永远不会进入。它只在有人用 `model.tok_embed.weight = nn.Parameter(...)` 这种"替换对象"的方式加载时才有意义——作为防御性代码可以保留，但要知道它在本流程中不触发。

### Q11 — 参考答案

1. 实测：`loaded=0 missing=52 unexpected=52 shape_mismatch=0`，`ok()` 为 False。所有键都查不到映射，进入 `unexpected`；本地参数一个都没被赋值，进入 `missing`。注意此时既没有异常、也没有 mismatch，如果调用方只看"有没有 mismatch"就会误以为加载成功——这正是讲义说的"mapping silently missed every tensor"。
2. 参考实现：

```python
PREFIXES = ("transformer.", "model.")

def normalize_name(src_name: str) -> str:
    for p in PREFIXES:
        if src_name.startswith(p):
            return src_name[len(p):]
    return src_name

# load_safetensors 内：
#     local_name = mapping.get(normalize_name(src_name))
```

非参数条目（如被存下来的因果 mask buffer `h.N.attn.bias`）在 name map 中查不到，会进入 `unexpected` 并打印 `[skip]`。`ok()` 只检查 `missing` 和 `shape_mismatch`，因此**不受影响**。更严谨的做法是维护一个"已知可忽略"的正则列表（例如 `r"h\.\d+\.attn\.(masked_)?bias"`），命中的静默跳过，其它 unexpected 仍然报警。

### Q12 — 参考答案

```python
import re

def load_safetensors(model, path, verbose=True, dtype=None, expected_layers=None):
    ...
    with safe_open(str(path), framework="pt") as reader:
        pretrained_names = list(reader.keys())
        if expected_layers is not None:
            layer_ids = {int(m.group(1)) for n in pretrained_names
                         if (m := re.match(r"h\.(\d+)\.", n))}
            found = max(layer_ids) + 1 if layer_ids else 0
            if found != expected_layers:
                raise ValueError(f"checkpoint has {found} layers, expected {expected_layers}")
        for src_name in pretrained_names:
            ...
            tensor = reader.get_tensor(src_name)
            if dtype is not None:
                tensor = tensor.to(dtype)
            ...
```

1. 现有代码在 `copy_` 时执行 `tensor.to(device=target.device, dtype=target.dtype)`，即"**按目标参数的 dtype** 转换"：文件是 fp32、模型是 bf16 时会自动降精度。所以想得到一个 bf16 模型，正确做法是先 `model.to(torch.bfloat16)` 再加载（或加载后再 `.to`）；只转换张量而模型仍是 fp32，`copy_` 又会把它转回 fp32，等于白做（只是多了一次精度损失）。`dtype` 参数更适合"文件 dtype 与模型不同、需要显式控制中间精度"的场景。
2. 层数不一致时：checkpoint 层数**多于**模型，多出的 `h.N.*` 不在 name map 里，只会进 `unexpected`，`ok()` 仍为 True——模型加载"成功"，但其实丢掉了顶层几层，输出完全不对；层数**少于**模型时会有一批 missing，结合 Q9 的问题还会半加载。显式的 `expected_layers` 检查让这类错误在任何赋值前以清晰的异常暴露出来。

### Q13 — 参考回答要点

- **名字不一致**：不同实现的命名历史不同（`wte` vs `tok_embed`，`ln_1.weight` vs `ln1.scale`），用显式 name map 解决；检测：映射后查不到的进 `unexpected`，本地没被赋值的进 `missing`。
- **形状/布局不一致**：Conv1D `(in, out)` vs Linear `(out, in)`；融合 QKV vs 分开的 Q/K/V；检测：shape check。但方阵转置错误 shape check 发现不了（见 Q6），要靠数值对照。
- **结构性不一致**：层数、词表大小、是否有 bias、是否 weight tying、是否有位置 embedding。用配置比对 + `expected_layers` 之类的显式检查。
- **dtype / device**：fp32/bf16/fp16；加载时统一转换到目标参数的 dtype 和 device。
- 加分点：加载后用参考实现（或官方推理代码）在相同输入上比较 logits（如最大绝对误差 < 1e-4）是最可靠的端到端验证；本节用"前后样本是否变化"只是最便宜的一道门。

### Q14 — 参考回答要点

- **定义**：输出投影矩阵直接使用 token embedding 矩阵 `E`（`logits = h · Eᵀ`），同一个 `Parameter` 两处用。GPT-2 Small 由此少存 `50257 × 768 ≈ 38.6M` 个参数。
- **别名 vs 复制**：`lm_head.weight = tok_embed.weight` 让两者共享存储，梯度来自输入、输出两侧会累加到同一张量上。复制一份（`nn.Parameter(E.clone())`）则变成两个独立参数：参数量增加 `V × d`（本节 demo 实测从 1,841,280 变成 1,890,432），训练时两者各自更新，逐渐分叉，再也不是"tied"。
- **优化器**：`model.parameters()` 去重，共享参数只进优化器一次；若是复制，就是两个独立的优化器状态（Adam 还要额外 2 倍的动量/方差显存）。
- **保存**：`state_dict()` 会同时出现 `tok_embed.weight` 和 `lm_head.weight`；`safetensors.torch.save_file` 会因"Some tensors share memory"拒绝保存（实测），要用 `save_model` 或手动去掉别名键，加载后再重建别名——这正是 GPT-2 文件里没有 LM head 的原因。
- 常见误区：加载后忘了检查 tie 是否仍成立；以 `load_state_dict` 方式加载时如果文件里含 `lm_head.weight` 且与 `wte` 数值不同，后加载的会覆盖先加载的。

### Q15 — 参考回答要点

- **失败模式清单**：文件不存在 / 损坏；名字查不到（前缀、命名风格）；本地参数缺来源；形状不一致；方阵转置错；层数不一致；dtype 不一致；设备显存不够；weight tying 被打断；部分加载。
- **流程**：①只读 header 列出所有张量名、dtype、形状（safetensors 可以不读数据就拿到这些）；②跑完整的名字映射 + 形状检查 + 层数检查；③**全部通过**才进入赋值，否则抛异常或返回失败报告；④赋值在 `no_grad` 下原地 `copy_`；⑤重建别名并断言 `data_ptr` 相等；⑥做一次数值冒烟测试（固定输入的 logits 与参考值比对，或至少前后样本不同）。
- **报告内容**：`loaded`（源名 → 目标名 → 形状）、`missing`、`unexpected`、`shape_mismatch`（源形状 vs 目标形状）、被忽略的已知条目、dtype 转换记录、最终 `ok`。
- **`load_state_dict(strict=...)`**：它要求键名已经与本地完全一致；`strict=True` 遇到 missing/unexpected 抛错，`strict=False` 返回 `missing_keys` 和 `unexpected_keys`；形状不一致会报错。它**不会**帮你做名字映射、Conv1D 转置、前缀剥离、层数语义检查，也不做数值验证。常见做法是先自己把 checkpoint 的键和形状转换成本地格式，再交给 `load_state_dict(strict=True)`。
- 加分点：日志写清"源名 → 目标名"，排错时比看十六进制快得多（讲义原话的意思）。

### Q16 — 参考回答要点

- **名字**：LLaMA 风格（以 Hugging Face 命名为例）常见 `embed_tokens`、`layers.N.self_attn.q_proj/k_proj/v_proj/o_proj`、`mlp.gate_proj/up_proj/down_proj`、`input_layernorm`、`post_attention_layernorm`、`norm`、`lm_head`。需要一张新的 name map。
- **结构差异**（讲义练习 5 提到"无 bias、RMSNorm、qkv 布局"）：
  - 无 bias：映射里没有 bias 条目，本地模型的 `use_bias=False`；
  - RMSNorm：只有 scale，没有 shift；
  - Q/K/V 分开存储：若本地是融合 `qkv`，加载时要 `torch.cat([q, k, v], dim=0)` 拼起来；GQA 下 K/V 的输出维是 `num_kv_heads × head_dim`，比 Q 小，形状检查要按这个算；
  - 没有可学习的位置 embedding（RoPE），映射里不应出现 `wpe`；
  - SwiGLU MLP 有三个矩阵（gate/up/down）；
  - LM head 通常不 tie（较小的模型可能 tie），文件里会有 `lm_head.weight`。
- **布局**：这些权重通常已经是 `nn.Linear` 的 `(out, in)` 布局，不需要 Conv1D 式转置；但要留意不同转换脚本对 Q/K 维度顺序的处理（与 RoPE 的实现方式有关），这类错误同样逃得过 shape check，必须用数值对照验证。
- 保持不变：shape check、两阶段加载、`LoadReport`、前后指纹/样本检查。

### Q17 — 参考回答要点

- **安全**：`torch.save` 默认用 pickle，加载 pickle 可能执行任意代码；safetensors 只存"JSON header + 原始张量字节"，不执行代码。
- **性能**：header 记录每个张量的 dtype、形状和字节偏移，可以 mmap 文件、按需读取单个张量（`safe_open(...).get_tensor(name)`），不必先把整个文件反序列化到内存。对几十 GB 的模型，这意味着可以只读 header 做完整校验、逐张量流式加载到 GPU，峰值内存更低。本节的 loader 正是先遍历 `reader.keys()`，再逐个 `get_tensor`。
- **限制**：只存张量（不存任意 Python 对象）；`save_file` 拒绝共享内存的张量（实测报错，见 Q8）。元数据只能是字符串字典（本节 stub 的 `metadata()` 为 `None`）。
- 加分点：本节 stub 文件 7,369,512 字节，其中数据 1,841,280 × 4 = 7,365,120 字节，其余 4,392 字节是 header 与对齐——header 很小，读 header 几乎零成本。

---

## 六、关联知识点

### 前置知识
- [阶段 19 · 35 组装 GPT 模型](../../35-gpt-model-assembly/docs/zh.md)：本节加载权重的目标架构（`tok_embed`、`blocks.N.attn.qkv`、`final_ln` 等命名都来自这里）。
- [阶段 19 · 36 训练循环与 Evaluation](../../36-training-loop-eval/docs/zh.md)：训练循环产出的 checkpoint 与本节加载的是同一种形状。
- [阶段 19 · 32 Token 与位置 Embeddings](../../32-token-positional-embeddings/docs/zh.md)：`wte`/`wpe` 的含义与形状。
- [阶段 19 · 33 多头 Self-Attention](../../33-multihead-self-attention/docs/zh.md)：理解融合 QKV 与 `split` 的布局。
- [阶段 10 · 04 预训练 Mini GPT](../../../10-llms-from-scratch/04-pre-training-mini-gpt/docs/zh.md)：GPT-2 参数量与 weight tying 的来源。

### 本节被哪些后续内容用到
- [阶段 19 · 38 通过替换输出头进行分类器 Fine-Tuning](../../38-classifier-finetuning/docs/zh.md)：在加载好的 backbone 上换头微调。
- [阶段 19 · 39 通过监督式 Fine-Tuning 进行指令微调](../../39-instruction-tuning-sft/docs/zh.md)、[阶段 19 · 40 从零实现直接偏好优化](../../40-dpo-from-scratch/docs/zh.md)：都从一个预训练（或 SFT）checkpoint 出发。
- [阶段 19 · 47 Checkpoint 保存与恢复](../../47-checkpoint-save-resume/docs/zh.md)：保存与加载是同一枚硬币的两面。
- [阶段 10 · 11 Quantization](../../../10-llms-from-scratch/11-quantization/docs/zh.md)：显存紧张时如何处理已加载的权重（讲义延伸阅读）。
- [阶段 10 · 13 构建一个完整的 LLM Pipeline](../../../10-llms-from-scratch/13-building-complete-llm-pipeline/docs/zh.md)：加载与推理所在的完整生命周期（讲义延伸阅读）。
- [阶段 10 · 14 开放模型：架构详解](../../../10-llms-from-scratch/14-open-models-architecture-walkthroughs/docs/zh.md)：扩展 name map 到 LLaMA/Mistral/Qwen 时需要的结构知识。

### 延伸关键词
`safetensors` · `safe_open / get_tensor` · `Conv1D vs nn.Linear` · `key remapping` · `load_state_dict(strict=True)` · `missing_keys / unexpected_keys` · `weight tying` · `data_ptr` · `mmap` · `pickle 安全` · `RMSNorm` · `GQA` · `SwiGLU`
