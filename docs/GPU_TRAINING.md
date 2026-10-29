# GPU training runbook

This prepares **one NVIDIA GPU** to train the existing JSM text model and custom
TTS model. GPU model, memory budget and precision are configurable. This is a
training workflow, not a claim that the current checkpoints are production-quality
assistants. Whisper remains a pretrained ASR backend; this repository does not
implement Whisper fine-tuning or native audio-token training.

The existing chat checkpoints and `fahd-test.pt` are not overwritten. New text
runs live in their own output directories. New voice stages use new voice names.
Do not run text and voice training simultaneously on the same GPU until their
combined memory use has been measured.

## 1. Prepare locally

Use Python 3.12 and run each project's commands from its own directory. Both
projects use a top-level `src` package: do not combine their imports in one process.

The October 29 preparation already created `jsm_0.1/storage/training/prepared/`
from the current Day 1 dataset: 2,345 training documents / 15,249,484 tokens,
126 validation documents and 110 test documents. This directory is ignored by
Git and must be transferred separately or included in the bundle below.

For a new dataset, run the existing intake, inspection, provenance, ingestion,
raw deduplication, extraction, cleaning, dataset building and tokenization steps.
Tokenization supports `--workers N` (default capped at 8) to bound CPU workers.
Then prepare a **new** versioned output directory:

```bash
cd jsm_0.1
.venv/bin/python -m scripts.prepare_training --output storage/training/prepared-day02
```

`prepare_training` verifies every tokenized document decodes to its source text,
requires nonempty train/validation/test splits, rejects duplicate IDs and exact
content duplicates within/across splits, validates token ranges and BOS/EOS, and
writes checksummed uint32 memory-mapped files plus a tokenizer snapshot. This
checks exact duplication, not semantic/near-duplicate leakage or corpus quality.
Preparation still holds source text records for one split in CPU RAM; training
uses memory-mapped token files. Train windows omit at most one incomplete final
window per split.

Days 2–10 are staged, not automatically admitted. `scripts.r2_intake --day 2`
only fetches and intakes that day's files; finish the remaining pipeline before
building a dataset. Never retrain/change the tokenizer while continuing existing
weights. Use a new tokenizer only with a compatible new model trained from scratch.

## 2. Build a transfer bundle

From the repository root:

```bash
python3 tools/export_training_bundle.py \
  --text-data jsm_0.1/storage/training/prepared \
  --text-checkpoint jsm_0.1/artifacts/checkpoints/best_jsm_small.pt \
  --speaker fahd \
  --voice-checkpoint jsm-voice/artifacts/models/tts/fahd-test.pt \
  --output training-bundles/berhot-gpu.tar.gz
```

Omit the speaker and voice checkpoint options for text-only training. The exporter
includes current source (including uncommitted source edits), the selected prepared
dataset, selected seed weights, tokenizer, and the selected speaker corpus. It
excludes `.env`, other storage, other artifacts, virtual environments, downloaded
ASR/Piper models and frontend builds. It records a SHA-256 for every bundled file.
It does **not** upload anything. Transfer the archive to a persistent volume on
the rented machine using your provider's file transfer or `scp`.

On the GPU machine:

```bash
tar -xzf berhot-gpu.tar.gz
cd berhot-ai
python3 tools/verify_training_bundle.py
```

Archive seed paths are standardized as:

- Text: `jsm_0.1/artifacts/checkpoints/gpu-seed.pt`
- Voice: `jsm-voice/artifacts/models/tts/gpu-seed.pt`
- Data: `jsm_0.1/storage/training/prepared/`

The bundle is for initializing a new training stage. To recover an interrupted
GPU run, also transfer its **entire output directory**, including `latest.pt`
(text) or `NAME.training.pt` (voice), rather than exporting only its best weights.

## 3. Install and check the GPU

Use a Linux NVIDIA host with Python 3.12. The driver and CUDA wheel must match;
choose the CUDA wheel index using the [official PyTorch installer](https://pytorch.org/get-started/locally/).
These training requirements pin the versions exercised locally. They do not lock
all platform-dependent CUDA transitive packages; record the resolved environment
on the actual host.

```bash
nvidia-smi
python3.12 -m venv .venv-training
source .venv-training/bin/activate
python -m pip install --upgrade pip
# Install torch==2.14.1 using the matching official CUDA wheel index if needed.
python -m pip install -r jsm-voice/requirements-training.txt pytest==9.1.1
python -m pip check
python -m pip freeze > training-environment.txt
python -c 'import torch; assert torch.cuda.is_available(); print(torch.__version__, torch.version.cuda, torch.cuda.get_device_name(0))'
```

For text-only training use `jsm_0.1/requirements-training.txt`. The training-only
requirements omit browser, ASR, Piper and microphone dependencies. Full application
requirements remain separate. Keep `training-environment.txt` with run backups.

Run the CUDA regression tests before spending hours on a job:

```bash
cd jsm_0.1
python -m pytest tests/test_gpu_training.py -q
cd ../jsm-voice
python -m pytest tests/test_voice_training_recovery.py -q
cd ..
```

CPU verification is complete locally. CUDA fp32/fp16/bf16 tests are deliberately
skipped without CUDA; bf16 also skips on unsupported GPUs. Confirm CUDA tests
actually execute on the rental. Automatic mixed precision follows PyTorch's
[autocast and GradScaler guidance](https://docs.pytorch.org/docs/stable/notes/amp_examples.html).

## 4. Text: preflight, smoke run, then train

Commands below assume the transfer bundle layout, activated `.venv-training`, and
`jsm_0.1` as the working directory. For this original checkout, substitute
`artifacts/checkpoints/best_jsm_small.pt` for `gpu-seed.pt`.

```bash
cd jsm_0.1
python -m scripts.train --config configs/training.gpu.json \
  --data storage/training/prepared --output artifacts/training/text-smoke \
  --init-from artifacts/checkpoints/gpu-seed.pt --allow-legacy-init --preflight

python -m scripts.train --config configs/training.gpu.json \
  --data storage/training/prepared --output artifacts/training/text-smoke \
  --init-from artifacts/checkpoints/gpu-seed.pt --allow-legacy-init --max-steps 3
```

Preflight is read-only and checks data hashes, tokenizer, architecture, recovery
compatibility and CUDA availability. It does not prove memory fit. The smoke run
executes real optimizer steps in a disposable output directory. Old seed files
lack tokenizer fingerprints; `--allow-legacy-init` is an explicit acknowledgement
that you verified the original tokenizer. New checkpoints store its hash.

Start the actual run in a **different** output directory, preferably under a
persistent mounted volume. For example, replace the output below with your
provider's persistent path, and use `tmux` to survive an SSH disconnect:

```bash
python -m scripts.train --config configs/training.gpu.json \
  --data storage/training/prepared --output artifacts/training/text-day01 \
  --init-from artifacts/checkpoints/gpu-seed.pt --allow-legacy-init
```

Default GPU settings: microbatch 16, accumulation 4, effective batch 64,
256-token context, two epochs, auto precision. These are starting settings, not
measured memory guarantees. On CUDA, auto selects bf16 if supported, otherwise
fp16 with gradient scaling. `--device cuda` fails if CUDA is unavailable; it never
silently trains on CPU. `--device cpu --precision fp32` is available for diagnostics.

If the smoke run runs out of memory, use a new smoke output and lower both
`--batch-size` and `--eval-batch-size`; increase `--gradient-accumulation-steps`
to preserve the effective batch size. For example:

```bash
# Add these overrides to the initialization command:
# --batch-size 4 --gradient-accumulation-steps 16 --eval-batch-size 4
```

Keep those same overrides when resuming. Changing batch grouping, optimizer
settings, seed, tokenizer or dataset requires a new stage with `--init-from`.
Architecture changes require compatible weights or explicit `--fresh` training.
This workflow does not automatically resize embeddings or claim that a larger
randomly initialized model will be better.

## 5. Text recovery and additional data

Resume the same interrupted run using the same dataset/config/batch settings:

```bash
python -m scripts.train --config configs/training.gpu.json \
  --data storage/training/prepared --output artifacts/training/text-day01 --resume
```

`latest.pt` stores model, optimizer, AMP scaler, RNG state, epoch/batch cursor,
learning-rate schedule, dataset identity and tokenizer hash. Recovery occurs at
optimizer boundaries, including gradient accumulation. Checkpoints are written
every 100 optimizer steps and after evaluations/epochs. SIGINT/SIGTERM request a
save after the current optimizer update (and any scheduled validation); hard kills
recover the last completed checkpoint. Do not assume an interruption handler can
finish within a cloud provider's eviction grace period. Use persistent storage and
copy backups off the instance before terminating the rental.

`run.json` reports completion, interruption, limits or failure; `metrics.jsonl`
contains training/validation events. `best.pt` is a weights-only selection by
validation loss, not a resumable checkpoint. It appears after the first evaluation.
One filesystem lock prevents two CLI trainers writing the same output directory.
Only the latest recovery checkpoint and best weights are kept; use external backups
for older recovery points.

`epochs` is the total target. A completed run produces an actionable error instead
of silently doing zero training. Extend it explicitly:

```bash
python -m scripts.train --config configs/training.gpu.json \
  --data storage/training/prepared --output artifacts/training/text-day01 \
  --resume --additional-epochs 2
```

When data changes, start a **new stage**, preserving learned weights but resetting
the optimizer, schedule and validation best:

```bash
python -m scripts.train --config configs/training.gpu.json \
  --data storage/training/prepared-day02 --output artifacts/training/text-day02 \
  --init-from artifacts/training/text-day01/best.pt
```

Changing the corpus changes the validation distribution. Compare checkpoints on
one frozen evaluation set as well as each stage's validation set. Keep data-source
balance intentional: ingesting all remaining Wikipedia/forum text is not evidence
of improved instruction following. Curated dialogue/instruction examples should
use one utterance per line, matching web/CLI prompting. The trainer still uses
next-token loss across all tokens; assistant-only loss masking, preference training
and multi-GPU/DDP are not implemented.

## 6. Evaluate before selecting a checkpoint for chat

```bash
python -m scripts.evaluate --checkpoint artifacts/training/text-day01/best.pt \
  --data storage/training/prepared --device cuda --batch-size 16 \
  --output artifacts/training/text-day01/evaluation.json

python -m scripts.benchmark_chat --checkpoint artifacts/training/text-day01/best.pt \
  --tokenizer artifacts/training/text-day01/tokenizer.json --device cuda \
  --output artifacts/training/text-day01/chat-evaluation.json
```

Evaluation uses token-weighted cross entropy on full packed windows. Historical
losses used an average of per-document chunks, so they are not directly comparable.
The Arabic sanity suite includes facts, arithmetic, Saudi language, instructions,
context use and human review cases. Automated substring matches can be misleading:
review answers, relevance, uncertainty and coherence manually. Do not train on the
benchmark prompts or choose releases using test loss repeatedly.

No automatic promotion occurs. After evaluation, copy chosen weights into
`artifacts/checkpoints/` under a new model name and select it in chat. Keep its
original tokenizer. Serving checks tokenizer fingerprints for new checkpoints;
it still supports old weights without hashes. The voice CLI now defaults to
`best_jsm_small.pt` and uses the same newline/reply format as web chat. Selecting a
new production model still requires updating `configs/llm.json` deliberately.

## 7. Voice: preflight, train and resume

From `jsm-voice`, with the same training environment activated:

```bash
cd ../jsm-voice
python -m scripts.train_voice --speaker fahd --voice fahd-gpu-smoke \
  --init-from artifacts/models/tts/gpu-seed.pt --device cuda --precision auto \
  --frame-budget 6000 --preflight

python -m scripts.train_voice --speaker fahd --voice fahd-gpu-smoke \
  --init-from artifacts/models/tts/gpu-seed.pt --device cuda --precision auto \
  --frame-budget 6000 --max-steps 3

python -m scripts.train_voice --speaker fahd --voice fahd-gpu-v1 \
  --init-from artifacts/models/tts/gpu-seed.pt --device cuda --precision auto \
  --frame-budget 6000 --minutes 120
```

For the original checkout, substitute `fahd-test.pt` for `gpu-seed.pt`. Lower
`--frame-budget` for smaller GPUs; the budget must still fit the longest usable
recording. Preflight verifies corpus identity and frame budget but does not execute
GPU inference. Voice mel features are prepared in CPU RAM; the alignment search
still runs on CPU. This is not an unlimited-size streaming corpus trainer.

Resume with the same options and **without** `--init-from`:

```bash
python -m scripts.train_voice --speaker fahd --voice fahd-gpu-v1 \
  --device cuda --precision auto --frame-budget 6000 --minutes 120
```

`--minutes` is additional wall time for this invocation. Checkpoints are written
every 200 updates (configurable with `--checkpoint-every`), at the time/step limit,
and on graceful interruption. Keep `fahd-gpu-v1.training.pt` for recovery;
`fahd-gpu-v1.pt` is latest inference weights and `fahd-gpu-v1.best.pt` is the best
held-out mel-loss snapshot. Corpus and optimizer changes require a new voice name
and `--init-from`. Duplicate normalized prompts stay on the same validation side.
Speaker consent metadata must travel with the WAVs and transcript metadata.

The current corpus has only 23 recordings (~3.4 minutes). Training infrastructure
cannot make that corpus a proven production voice. Expand it with clean,
transcript-matched speech, then evaluate unseen sentences, pronunciation, noise,
prosody and intelligibility. Griffin-Lim synthesis and the existing character
frontend remain; a trained neural vocoder is separate future work. Held-out mel
loss alone is not a listening-quality or identity guarantee.

## Operational limits

- One process / one GPU; no `torchrun`, distributed training or automatic GPU rental.
- Exact CPU resume parity is tested. Different hardware/precision/kernels can
  produce numerical differences. Record the GPU and resolved environment.
- A GPU smoke run is required to validate memory fit and the installed CUDA stack.
- Checkpoints and recordings are local files; storage persistence/backups belong
  to the operator. Interrupted native kernels are not immediately preempted.
- Existing checkpoints are still experimental. Production serving, ASR dialect
  quality and TTS listening acceptance need their own evaluations.
