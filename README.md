# ncc

`ncc` is a local-first BYOK tool for turning a short Korean prose scene into a vertical webtoon workflow.

The v1 path is:

`source -> analysis -> characters -> storyboard -> panel specs -> tag candidates -> prompt IR -> NAI prompts -> image candidates -> QA/provenance -> candidate selection -> lettering -> export`

## Setup

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
pytest
```

For the creator UI:

```bash
cd frontend
npm install
npm test
npm run build
```

## Local-First And BYOK

Projects are stored on your machine under `NCC_PROJECTS_DIR` or `ncc-projects` by default. The default providers are deterministic mocks, so tests and the gold-path smoke run do not need API keys.

Real providers are opt-in through local environment variables. Source text may be sent to the selected LLM provider when story analysis runs. Prompts, settings, and reference images may be sent to the image provider when image generation runs. The app never writes API keys into artifacts and never uploads the entire project directory automatically.

## Backend

Start the local API:

```bash
ncc-api
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

Run a deterministic gold path through the API:

```bash
curl -X POST http://127.0.0.1:8000/gold-path
```

The mock gold path creates a 6-panel project, writes 18 candidate image records, selects one candidate per panel, writes Korean lettering data, and exports a 1080px-wide vertical PNG.
