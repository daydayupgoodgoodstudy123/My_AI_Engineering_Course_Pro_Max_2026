---
name: skill-recall-at-k-runner
description: Write a clean evaluation harness for recall@K with train/val/gallery splits and proper data contract
version: 1.0.0
phase: 4
lesson: 20
tags: [retrieval, evaluation, recall, faiss]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="recallk-runner"></a>

# Recall@K 跑步者

将查询和图库图像以及标签的文件夹转换为可复制的 recall@K 编号。

<a id="when-to-use"></a>

## 何时使用

- 新骨干网的第一个检索基准。
- 跨微调时期跟踪 embedding 质量。
- 比较同一数据集上的两个检索系统。

<a id="inputs"></a>

## 输入

- `query_images`：路径列表。
- `gallery_images`：路径列表（查询可能重叠也可能不重叠）。
- `query_labels`、`gallery_labels`：类或实例 ID。
- `encoder_fn`：可调用`image -> embedding`（预先计算或实时）。
- `ks`：类似`[1, 5, 10]`的列表。

<a id="steps"></a>

## 步骤

1. 对每个画廊图像进行一次编码。保存为 numpy 数组。
2. 对每个查询图像进行编码。
3. L2-标准化两组 embeddings。
4. 对于每个查询，计算所有图库项目的相似度。
5. 降序排序，取顶部 max(ks)。
6. 对于每个 K，检查前 K 个库项目中是否有任何共享查询的标签。
7. 报告`recall@K = fraction of queries that had at least one correct neighbour in top K`。

<a id="output-template"></a>

## 输出模板

```python
import numpy as np
from sklearn.preprocessing import normalize

def encode_all(images, encoder_fn, batch=32):
    out = []
    for i in range(0, len(images), batch):
        embs = encoder_fn(images[i:i + batch])
        out.append(embs)
    return np.concatenate(out)


def recall_at_k(query_emb, gallery_emb, q_labels, g_labels,
                ks=(1, 5, 10), query_ids=None, gallery_ids=None):
    if len(query_emb) == 0 or len(gallery_emb) == 0:
        return {f"recall@{k}": 0.0 for k in ks}

    g_label_set = set(g_labels.tolist())
    keep = np.array([lbl in g_label_set for lbl in q_labels])
    if not keep.any():
        return {f"recall@{k}": 0.0 for k in ks}

    q_emb_f = query_emb[keep]
    q_lab_f = q_labels[keep]
    q_id_f = query_ids[keep] if query_ids is not None else None

    q = normalize(q_emb_f)
    g = normalize(gallery_emb)
    sims = q @ g.T

    if q_id_f is not None and gallery_ids is not None:
        self_mask = q_id_f[:, None] == gallery_ids[None, :]
        sims = np.where(self_mask, -np.inf, sims)

    top_k_max = min(max(ks), g.shape[0])
    if top_k_max <= 0:
        return {f"recall@{k}": 0.0 for k in ks}

    top = np.argpartition(-sims, top_k_max - 1, axis=1)[:, :top_k_max]
    sorted_top = np.take_along_axis(
        top, np.argsort(-sims[np.arange(len(q))[:, None], top], axis=1), axis=1
    )
    out = {}
    for k in ks:
        k_eff = min(k, top_k_max)
        hits = np.any(g_labels[sorted_top[:, :k_eff]] == q_lab_f[:, None], axis=1)
        out[f"recall@{k}"] = float(hits.mean())
    return out


def evaluate(query_images, query_labels, gallery_images, gallery_labels, encoder_fn, ks=(1, 5, 10)):
    q_emb = encode_all(query_images, encoder_fn)
    g_emb = encode_all(gallery_images, encoder_fn)
    return recall_at_k(q_emb, g_emb, np.array(query_labels), np.array(gallery_labels), ks)
```

<a id="report"></a>

## 报告

```
[evaluation]
  num queries:   <int>
  num gallery:   <int>
  embedding_dim: <int>

[recall]
  recall@1:  <float>
  recall@5:  <float>
  recall@10: <float>
```

<a id="rules"></a>

## 规则

- 在计算相似度之前对embeddings进行归一化；归一化向量上的 FAISS IndexFlatIP 等于余弦。
- 当查询的真实标签在图库中不存在时，将其排除；否则召回率通常会限制在 1 以下。
- 如果查询和图库重叠，请将查询本身从其自己的 top-K 中排除，或者测量自相似性，而不是检索。
- 对于`num_queries > 10,000`，批量相似性matmul以避免OOM。
