<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="the-direct-preference-optimization-family"></a>

# 直接偏好优化方法家族

> Rafailov等人(2023年)显示 RLHF最佳的偏好数据有封闭的形式, 这样您就可以跳过明确的 reward model 并且直接优化政策。 DPO。 2026年,直接 alignment 运算法比训练后运行的边境系统多 PPO。但是第二课的过度优化曲线仍然适用:DAAs无法逃脱Goodhart, 它们只是移动它咬的地方。

**类型:** 学习
**语言:** Python (6种优惠损失的参照)
**先修要求:** 第18阶段 · 01(制造GPT),第18阶段 · 02(奖励黑客),第10阶段 · 08(DPO basics)
**时间:** ~75分钟

<a id="learning-objectives"></a>

## 学习目标

- 产生 DPO 关闭窗体 RLHF- 和KL最佳关系
- 说明IPO、KTO、SimPO、ORPO、BPO的每个故障模式 DPO.
- 区分“隐含的奖励差距”与“优胜力量”,
- 解释为什么Rafailov等人(NeurIPS 2024)证明尽管没有明确的RM,但DAAs过于优化。

<a id="the-problem"></a>

## 问题

该 RLHF 目标(课程1):

```
max_pi E_{x,y~pi} [ r(x, y) ] - beta * KL(pi || pi_ref)
```

拥有已知的最佳条件:

```
pi*(y|x) = (1/Z(x)) * pi_ref(y|x) * exp(r(x, y) / beta)
```

奖赏是用最佳政策与参考值之比来暗含的:

```
r(x, y) = beta * log(pi*(y|x) / pi_ref(y|x)) + beta * log Z(x)
```

将它替换为布拉德利- 特里偏好的可能性和分区函数 `Z(x)` 取消, 因为它只取决于 `x`。剩下的是保单的损失 parameters 单独——没有 reward model 需要。 这是 DPO.

皱纹: 衍生假设最佳的可以达到, 偏好数据是分布不均的, 引用策略是真正的模式锚。 这些支撑没有准确的。 每个家庭成员都会修正不同的被违反的假设 。

<a id="the-concept"></a>

## 概念

<a id="dpo-rafailov-et-al-2023"></a>

### DPO (Rafailov等人,2023年)

```
L_DPO = -log sigmoid(
  beta * log(pi(y_w | x) / pi_ref(y_w | x))
  - beta * log(pi(y_l | x) / pi_ref(y_l | x))
)
```

怎么会出错?

- 隐含的酬劳差距 `beta * (log(pi/pi_ref)_w - log(pi/pi_ref)_l)` 细微的偏好会造成任意的巨大差距。
- 丢失驱动器被选择并拒绝日志程序, 方向相反。 只要被拒绝的运行速度更快, 它就可以将选中的绝对日志程序推倒 。 这是被降级的天选响应现象 。
- 分配外优惠(罕见的对与稀有的对)产生任意的默示奖励。

<a id="ipo-azar-et-al-2024"></a>

### IPO(Azar等人,2024年)

身份偏好优化取代日志sigmoid 以偏好概率绘制身份图。 损失成为被绑定目标上的方形错误 :

```
L_IPO = (log(pi(y_w | x) / pi_ref(y_w | x)) - log(pi(y_l | x) / pi_ref(y_l | x)) - 1/(2 beta))^2
```

差值受以下因素约束: `1/(2 beta)`。优胜力量和隐性回报差距是成比例的,没有爆炸。

<a id="kto-ethayarajh-et-al-2024"></a>

### KTO(Ethayarajh等人,2024年)

Kahneman- Tverimize 优化完全会将双向结构投放到一个标签输出和一个二进制“ 理想” 或“ 不理想” 信号, 它映射到一个前景理论工具 :

```
v(x, y) = sigma(beta * log(pi(y|x) / pi_ref(y|x)) - z_ref)
```

与不同 weights 收益:您可以使用不公的数据,而这些数据则要丰富得多。

<a id="simpo-meng-et-al-2024"></a>

### SimPO(Meng等人,2024年)

简单优化将培训信号与生成匹配。 完全删除引用政策, 并按长度将日志相似性正常化 :

```
L_SimPO = -log sigmoid(
  (beta / |y_w|) * log pi(y_w | x)
  - (beta / |y_l|) * log pi(y_l | x)
  - gamma
)
```

带有边距 `gamma` 长度 normalization 消除剥削的动机 DPO长度比失败模式( 较长) `y_w` 显示通过施工产生的日志- 概率差较大 。

<a id="orpo-hong-et-al-2024"></a>

### ORPO(Hong等人,2024年)

优化给标准添加了一个优惠条件 SFT 负日志类型 :

```
L_ORPO = L_NLL(y_w) + lambda * L_OR
L_OR = -log sigmoid(log(odds(y_w) / odds(y_l)))
```

没有参考政策—— SFT 词组是正则化器。 列车从基模式到对齐模式的单阶段。 没有分开 SFT checkpoint.

<a id="bpo-iclr-2026-submission-openreview-idb97ewmuwu7"></a>

### 生物保护组织(ICLR 2026提交,OpenReview id=b97EwMUWu7)

确定降级后应对问题: DPO 保留排序 `y_w > y_l` 却以绝对的日志 `y_w` BPO 添加一条单行更正, 惩罚选中响应向下移动。 报告 +10.1% 的准确度 Llama-3.1-8B-数学推理教学 DPO.

<a id="the-universal-result-daas-still-over-optimize"></a>

### 普遍结果:地方行政管理局仍然过于优化

Rafailov等人,“扩大法律范围,以 Reward Model 直接过度优化 Alignment 师资培训政策 DPO,IPO, SLIC 用于所有 KL 预算的多个数据集。 金- 奖励 vs- KL 曲线具有相同的 Gao 等人峰值和折叠形状。 在培训期间, 隐含的奖赏查询不分布样本; KL 正则化无法稳定这一点 。

地检官不会逃脱古德哈特,他们改变地表的表面,从那里咬。reward model 通用的修复方法 — — 更好的数据、组合、早期停止 — — 适用于两者。

<a id="choosing-among-them-2026"></a>

### 选择其中之一(2026年)

- 如果您有大对齐偏好数据 : DPO 使用保守的贝塔,SimPO 如果长度偏差明显。
- 如果您有未受重视的二进制反馈: KTO 。
- 如果你想从一个基模上 找到一条单级管道: OROPO。
- 如果您看到已选中的对数程序在 DPO 日志:BPO。 (BPO: 日志)
- 如果优惠优势差异很大, DPO 饱和度:IPO。

每个实验室都用电池操作所有五个,每个任务选取赢家。 数学推理和安全性的最佳方法没有理由相同。

```figure
dpo-margin
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 比较6项损失DPO,IPO, KTO, SimPO, ORPO, BPO) 的玩具偏好数据集, 其真实偏好强度因对而异。 每种损失都与以小量样本( 500帕) 相比优化 softmax 政策. 绘制最后赢率、选择的log-rob 流和每个方法的内向利差。

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-preference-loss-selector.md`。给定数据集统计数据(paired 相对于 unpaired, 变量与统一优惠强度、长度分布)和目标(单级或单级) SFT优先选择)建议优惠损失 并报告它保护的失败模式

<a id="exercises"></a>

## 练习

1. Run `code/main.py`。报告最后选择的log-propb 投放 DPO 生物保护组织应该保留较高的绝对概率——核实这一点。

2. 修改优先数据, 使所有对子都有同等的强度。 六个方法中哪一种最强? 哪种降低? 解释IPO在这里的优势 。

3. 平均将被拒绝的答复比选择的时间长2x。不更改其它内容,请显示 DPO长度开发的数值和SimPO的修复。

4. Rafailov等人(NeurIPS 2024)称DAAs过份优化。重写一个点版本:选中的绘图减号 KL差,并观察了在 DPO 长贝塔。

5. 阅读 BPO 纸摘要 ( OpenReview b97EwMUWu7)。 写下单行校正 BPO 添加的 BPO 。 DPO确认反对执行《公约》 `code/main.py`.

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|------------------------|
| DPO | "RLHF 没有 reward model" | 封闭式表单引起的损失 RLHF 最佳; 政策 parameters 仅 |
| 隐性奖励 | 日志和标尺 | `beta * log(pi(y\|x) / pi_ref(y\|x))` — 该 DPO- 隐含的奖励 |
| IPO | "bounded DPO" | 替换日志 -sigmoid 具有身份; 以下列方式限制的隐性报酬差距: `1/(2 beta)` |
| 韩国贸易组织 | "unpaired DPO" | 单标签上带有损失规避的预期理论工具 |
| 模拟PO | "reference-free DPO" | 长度调整日志类型 + 差幅; 没有参考政策 |
| 奥尔普 | "one-stage DPO" | NLL + 概率比优选条件;从基本模型中一次性列车 |
| BPO | "chosen-preserving DPO" | DPO 加上减少所选响应绝对日志程序的处罚 |
| 降级后天选 | "选择失败" | DPO 只要被否决的日志程序下降速度更快, 则会减少 |
| DAA | "direct alignment algorithm" | 任何忽略明确 RM 的偏好损失方法 |

<a id="further-reading"></a>

## 进一步阅读

- [Rafailov等人——直接优化(NeurIPS 2023,arXiv:2305.18290)](https://arxiv.org/abs/2305.18290)
- [Azar等人——从人类的偏好中学习的一般理论范例(ASTATS 2024, arXiv:2310.12036)](https://arxiv.org/abs/2310.12036) - IPO(国际采购组织)
- [Ethayarajh等人-KTO:模型 Alignment 预想理论优化(arXiv:2402.01306)](https://arxiv.org/abs/2402.01306)
- [孟、夏、陈-西姆波(NeurIPS 2024,arXiv:2405.14734)](https://arxiv.org/abs/2405.14734)
- [洪李,索恩-奥普(EMNLP 2024,arXiv:2403.07691)](https://arxiv.org/abs/2403.07691)
- [BPO - 行为保护优化(ICLR 2026 OpenReview b97EwMUWu7)](https://openreview.net/forum?id=b97EwMUWu7)
- [Rafailov等人——《残疾歧视法》中关于降低男性生殖器功能过度优化的扩展法律(NeurIPS 2024,ArXiv:2406.02900)](https://arxiv.org/abs/2406.02900)
