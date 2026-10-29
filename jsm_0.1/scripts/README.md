Training commands below the corpus pipeline have changed. Use the current
[GPU training runbook](../../docs/GPU_TRAINING.md) for preparation, explicit
initialization/resume, evaluation, and GPU configuration.

corpus files in Cloudflare R2 (copy .env.example to .env and fill in the bucket keys):
python -m scripts.r2_upload            copy storage/uploads and storage/staged to the bucket
python -m scripts.r2_intake            fetch uploads/ from the bucket, then run intake
python -m scripts.r2_intake --day 1    fetch one staged daily batch into uploads, then run intake

python3 -m scripts.intake
python3 -m scripts.inspection
python3 -m scripts.provenance

*** If it says:
BLOCK — review_required
python3 -m scripts.provenance_review <batch-id> allowed "Permission verified"

<!-- python -m scripts.provenance_review ali-hassan-20261004T124557Z-7d637fa5 allowed owned_data -->

python3 -m scripts.ingestion

python3 -m scripts.raw_exact_deduplication
python3 -m scripts.extraction

python3 -m scripts.cleaning

python3 -m scripts.language_classification
python3 -m scripts.arabic_variety_classification

python3 -m scripts.dataset_building

python3 -m scripts.tokenizer_training

for test : 
python -c "from paths import TOKENIZER_PATH; from src.tokenization.tokenizer import Tokenizer; t=Tokenizer.load(TOKENIZER_PATH); text='مرحبا بالعالم'; ids=t.encode(text, add_bos=True, add_eos=True); print(ids); print(t.decode(ids)); assert t.decode(ids)==text; print('PASS')"

python -m scripts.tokenize_dataset

python -m scripts.train --help

python -m scripts.inference "علي حسن"
python -m scripts.inference "مشروع"

python -m scripts.evaluate --help

web apps (build once, and again after changing anything under apps/):
cd apps && npm install && npm run build

python -m scripts.serve
http://127.0.0.1:8000/         public website
http://127.0.0.1:8000/chat     public chat
http://127.0.0.1:8000/admin    internal admin console
http://127.0.0.1:8000/docs     API docs

web apps with live reload (keep scripts.serve running), from apps/:
npm run dev:website    http://localhost:3000/
npm run dev:chat       http://localhost:3001/chat/
npm run dev:admin      http://localhost:3012/admin/


python -m scripts.model_stats


---
run dev frontend :

  1. Start the API (terminal 1)

  A copy I started is already running on port 8000, so you only need this if you stop it:

  cd jsm_0.1
  source .venv/bin/activate
  python -m scripts.serve

  2. Install the web apps (once)

  Already installed on your machine; needed again only after a fresh clone:

  cd jsm_0.1/apps
  npm install

  3. Run in dev mode with live reload (one terminal per app, from jsm_0.1/apps)

  npm run dev:website
  npm run dev:chat
  npm run dev:admin

    ┌─────────┬────────────────────────┐
  │   App   │           Dev URL            │
  ├─────────┼──────────────────────────────┤
  │ Website │ http://localhost:3000/       │
  ├─────────┼──────────────────────────────┤
  │ Chat    │ http://localhost:3001/chat/  │
  ├─────────┼──────────────────────────────┤
  │ Admin   │ http://localhost:3012/admin/ │
  └─────────┴──────────────────────────────┘

  The dev servers need the API from step 1 running, since they forward API calls to port 8000.

  4. Or build and serve everything from one port (no dev servers)

  cd jsm_0.1/apps
  npm run build
  