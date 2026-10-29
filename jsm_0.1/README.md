# JSM text model

Own Arabic causal language model, corpus processing, tokenizer, training and web
chat. See the [GPU training runbook](../docs/GPU_TRAINING.md) for the supported
training commands, data preparation, recovery and evaluation.

Training now requires an explicit prepared dataset, output directory and one of
`--init-from`, `--resume`, or `--fresh`. The old bare `python -m scripts.train`
command no longer silently reuses a completed checkpoint. Serving remains
`python -m scripts.serve`; see [apps](apps/README.md).
