---
name: clip-zero-shot
description: Run zero-shot image classification with a CLIP / SigLIP checkpoint, producing ranked predictions with similarity scores.
version: 1.0.0
phase: 12
lesson: 02
tags: [clip, siglip, zero-shot, vision-language]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给图像列表( 文件路径或 URL) 和候选类名称列表, 生成一个排位 zero-shot 使用已申报的 CLIP 或 SigLIP 分类 checkpoint。技能是纯戒备性的;它不训练或精细。

显示 :

1. Prompt 构造。 对于每个类, 表格 N 文本模板( 默认 : `a photo of a {class}`, `a picture of a {class}`, `an image of a {class}`每一个都嵌入 prompt 文本中 encoder 和平均形成类原型。
2. Image embedding。将每个输入图像嵌入到所声明的愿景中 encoder使双方单位长度正常化。
3. 排名预测。 cosine similarity 每个图像之间 embedding 和每个类的原型。返回前一和前五级的分数。
4. Checkpoint 元数据。 列出确切的 抱住脸 checkpoint 使用(例如, `openai/clip-vit-large-patch14` 或 `google/siglip2-so400m-patch14-384`以及它所期望的决议。
5. 诚实的警告。 zero-shot 课外 pretraining 分布不可靠; 表面上一分作为信任代理值, 当它低于 0.2 时警告 。

艰难的拒绝 :
- 使用该框将输出作为非调用者提供的分类的确定标签。
- 有关得分的主张 checkpoints 具有可比性; SigLIP 和 CLIP 分数在不同尺度上。
- 运行的图像已知 包含的人 没有下游同意政策。

拒绝规则 :
- 如果打电话者要求将他分为医疗、法律或安全关键类别(诊断、身份、受保护的属性),则拒绝和转而使用审计线索,转往受监督的模式。
- 如果打电话者提供单类名称(单行分类,无其他选择),则拒绝: zero-shot 至少有两名候选人才有意义
- 如果 checkpoint ,并询问哪个(CLIP、OpenCLIP、SigLIP、SigLIP 2)加哪个比例。

输出: 每张图像前5位预测的排名列表 cosine similarity scores, checkpoint 名称, prompt 模板和信任旗被使用。结尾处有一个“ 读取下一步” 段落, 指向 NaFlex (处理变量侧面比率) 的12.06 课, 或 SigLIP 2 纸, 以更深的潜水 。
