# JSM apps

Client applications. They talk to the JSM backend over its HTTP API and
contain no model, tokenizer or inference code — that all lives in `src/`.

```
apps/
├── public/                  customer-facing products
│   ├── website/web/         served at /
│   └── chat/web/            served at /chat   (ios/ and android/ come later)
├── internal/                company staff tools
│   └── admin_console/web/   served at /admin  (read-only)
└── shared/                  design tokens and Next.js config used by every web app
```

Each `web/` folder is a Next.js + Tailwind CSS app, built as a static export
(`out/`) that the API server serves. This directory is one npm workspace.

```
npm install          # once
npm run build        # build all three; restart `python -m scripts.serve` afterwards
npm run lint

npm run dev:website  # http://localhost:3000/
npm run dev:chat     # http://localhost:3001/chat/
npm run dev:admin    # http://localhost:3012/admin/
```

The dev servers proxy API calls to `http://127.0.0.1:8000`
(override with `JSM_API_URL`), so keep `python -m scripts.serve` running.

`/admin` has no authentication yet. It must before this runs anywhere but localhost.
