"""Explicit lesson-by-lesson core/bonus selections; sorted numeric lesson order.

Kernels are intentionally shared when the same underlying skill recurs.
This mapping is reviewed content, not a keyword classifier.
"""
ROUTES = {
"00": """
environment/versions git_plan/manifest params/amdahl config/redact profile/statistics
versions/config manifest/argv environment/config split/manifest argv/path path/permissions profile/latency
""",
"01": """
dot/normalize matmul/transpose transform/eigen differentiate/gradient gradient/gd
sample_cdf/entropy bayes/classification gd/clip entropy/cross_entropy eigen/standardize
eigen/linear_solve transpose/params softmax/logsumexp distance/cosine statistics/calibration
sample_cdf/markov linear_solve/matmul eigen/gradient dft/transform dft/frames bfs/topology markov/returns
""",
"02": """
split/classification linear/mse sigmoid/cross_entropy gini/entropy distance/knn knn/standardize
codebook/distance standardize/bow classification/calibration mse/statistics ensemble/classification
grid/topk standardize/split bow/bayes lag/mse anomaly/statistics weights/classification standardize/topk
""",
"03": """
linear/activation linear/matmul gradient/differentiate activation/sigmoid cross_entropy/mse gd/clip
gd/mse statistics/params schedule/gd linear/gradient params/batch gradient/matmul clip/anomaly
""",
"04": """
transpose/standardize conv/pool params/conv classification/ensemble params/lora iou/nms
dice/classification patches/iou cross_entropy/gradient diffusion/schedule diffusion/params
frame_sample/frames transform/attention patches/attention latency/params topology/latency
cosine/cross_entropy cosine/topk ctc/edit_distance distance/retrieval heatmap/transform
transform/flow flow/diffusion rle/dice attention/patches depth/mse iou/state_machine frame_sample/kv
""",
"05": """
tokens/ngrams bow/cosine ngrams/cosine bpe/tokens bow/classification bio/tokens
markov/topk conv/pool lag/masked attention/softmax ngrams/token_f1 token_f1/retrieval
token_f1/retrieval rrf/bow bow/entropy perplexity/ngrams routing/dialogue cosine/classification
bpe/ngrams masked/softmax bow/classification cosine/retrieval chunks/context bio/dialogue
cosine/topk provenance/bfs retrieval/token_f1 context/retrieval dialogue/state_machine
""",
"06": """
dft/rms frames/mel rms/knn ctc/edit_distance chunks/params cosine/calibration
lag/schedule cosine/watermark ngrams/sample_cdf frames/attention rms/latency
state_machine/budget codebook/mse rms/state_machine codebook/latency watermark/classification edit_distance/calibration
""",
"07": """
amdahl/attention attention/softmax matmul/attention positions/transform attention/causal_mask
masked/cross_entropy causal_mask/perplexity attention/masked patches/positions frames/attention
topk/softmax kv/attention params/amdahl causal_mask/params causal_mask/topk speculative/perplexity
""",
"08": """
entropy/sample_cdf mse/sample_cdf cross_entropy/gd transform/mse statistics/linear
diffusion/schedule diffusion/quantize lora/flow rle/diffusion frame_sample/flow
frames/codebook transform/flow flow/gd cosine/statistics causal_mask/masked
""",
"09": """
bellman/markov bellman/returns returns/statistics q_update/returns q_update/clip
returns/softmax advantage/gd ppo/advantage dpo/classification consensus/q_update drift/anomaly bellman/ucb
""",
"10": """
tokens/bpe bpe/ngrams chunks/split causal_mask/cross_entropy shards/reduce
masked/cross_entropy advantage/returns dpo/sigmoid moderation/gate perplexity/calibration
quantize/mse kv/latency topology/manifest params/kv speculative/latency
attention/layernorm causal_mask/topk lag/causal_mask pipeline/shards topk/params
markov/attention idempotency/rate_limit speculative/causal_mask params/amdahl
""",
"11": """
context/config context/token_f1 config/tool_schema cosine/retrieval context/memory
chunks/retrieval rrf/retrieval lora/params tool_schema/rpc classification/calibration
ttl/cost moderation/permissions state_machine/budget rpc/config lru/ttl
state_machine/topology routing/gate
""",
"12": """
patches/positions cosine/cross_entropy attention/matmul attention/flow masked/context
patches/batch params/quantize frame_sample/patches frame_sample/context patches/params
chunks/masked causal_mask/codebook diffusion/causal_mask masked/diffusion cosine/linear
queue/latency frame_sample/iou context/kv frames/ctc topology/queue flow/permissions
bio/patches cosine/retrieval rrf/context permissions/path
""",
"14": """
state_machine/budget topology/context memory/drift bfs/ucb gate/drift tool_schema/idempotency
memory/context memory/manifest ttl/rrf routing/manifest topology/pareto topology/queue
state_machine/idempotency queue/rpc routing/handoff handoff/permissions permissions/path
state_machine/profile classification/provenance permissions/latency permissions/iou rms/state_machine
profile/redact latency/cost consensus/provenance retry/state_machine permissions/provenance
topology/queue idempotency/manifest gate/classification config/provenance state_machine/gate
config/permissions memory/manifest environment/argv config/path profile/gate gate/manifest
provenance/git_plan handoff/memory manifest/git_plan topology/gate config/risk provenance/topology
shards/permissions drift/manifest gate/profile topology/handoff risk/provenance
context/budget config/gate classification/latency gate/provenance drift/gate
""",
"15": """
budget/state_machine returns/provenance pareto/gate ucb/manifest topology/provenance
gate/drift drift/gate budget/risk routing/config permissions/argv permissions/path
idempotency/handoff budget/cost canary/gate gate/git_plan manifest/drift moderation/provenance
moderation/calibration risk/gate gate/risk calibration/classification risk/fairness
""",
"16": """
amdahl/cost rpc/config rpc/idempotency state_machine/routing topology/queue
topology/handoff consensus/provenance routing/permissions shards/reduce queue/routing
handoff/state_machine state_machine/rpc memory/ttl consensus/classification ensemble/consensus
pareto/budget markov/routing bayes/routing topk/pareto q_update/consensus budget/idempotency
queue/idempotency drift/consensus classification/latency provenance/risk
""",
"17": """
routing/cost cost/amdahl autoscale/queue kv/batch speculative/latency lru/kv
quantize/params latency/profile quantize/mse environment/latency lru/ttl params/quantize
profile/redact cosine/ttl batch/budget routing/latency queue/kv lru/batch
permissions/rate_limit canary/latency classification/calibration rate_limit/latency gate/latency
retry/gate redact/permissions provenance/gate cost/budget pareto/params
""",
"18": """
config/classification drift/classification dpo/cross_entropy classification/calibration
moderation/provenance gate/drift drift/gate permissions/provenance drift/calibration
permissions/risk gate/provenance classification/risk context/budget tokens/moderation
provenance/permissions moderation/classification classification/weights risk/gate provenance/risk
fairness/classification fairness/calibration privacy/budget watermark/provenance config/provenance
permissions/redact config/handoff provenance/manifest provenance/topology moderation/calibration risk/permissions
""",
"19": """
argv/path chunks/retrieval rms/state_machine patches/token_f1 topology/provenance
environment/topology schedule/lora rrf/context git_plan/manifest topology/handoff
profile/latency frame_sample/context rpc/manifest speculative/kv moderation/gate
git_plan/gate context/classification
state_machine/budget tool_schema/config rpc/idempotency routing/tool_schema topology/state_machine
gate/budget argv/permissions classification/config profile/redact topology/gate bpe/ngrams
chunks/causal_mask positions/linear attention/matmul layernorm/activation params/causal_mask
cross_entropy/gd manifest/params linear/classification masked/cross_entropy dpo/sigmoid
classification/calibration manifest/retry chunks/manifest schedule/clip clip/gd reduce/gd
manifest/state_machine shards/reduce perplexity/retrieval context/pareto rrf/provenance
queue/budget statistics/calibration provenance/config drift/gate ucb/budget topology/provenance
patches/positions attention/params linear/cosine attention/causal_mask cross_entropy/cosine
retrieval/token_f1 chunks/context rrf/cosine topk/retrieval bow/rrf retrieval/provenance
topology/retrieval config/tool_schema token_f1/ngrams permissions/argv perplexity/calibration
statistics/classification gate/provenance reduce/shards reduce/gradient shards/params
pipeline/queue manifest/shards shards/pipeline risk/config tokens/provenance
classification/moderation moderation/risk config/moderation gate/permissions
""",
"20": """
returns/amdahl amdahl/params amdahl/queue bellman/returns classification/weights
dpo/calibration sample_cdf/gate gd/gradient pareto/ucb ucb/pareto
ucb/provenance bfs/routing calibration/statistics drift/gate provenance/manifest
entropy/sample_cdf normalize/dot permissions/manifest risk/budget calibration/drift
""",
}

PHASE_ZH = {
"00":"环境与工具", "01":"数学基础", "02":"机器学习基础", "03":"深度学习核心",
"04":"计算机视觉", "05":"自然语言处理", "06":"语音与音频", "07":"Transformer",
"08":"生成模型", "09":"强化学习", "10":"从零构建 LLM", "11":"LLM 工程",
"12":"多模态 AI", "14":"Agent 工程", "15":"自主系统", "16":"多 Agent 系统",
"17":"基础设施与生产", "18":"安全与对齐", "19":"综合项目", "20":"递归自改进",
}
