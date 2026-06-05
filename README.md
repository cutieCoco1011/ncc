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

Tag conversion and image generation are separate provider surfaces. `NCC_TAG_PROVIDER=mock` is a fixture path. `NCC_TAG_PROVIDER=local` runs the local Danbooru compiler without an LLM. `NCC_TAG_PROVIDER=deepseek` keeps DeepSeek as the candidate-suggestion provider identity, but final tags and prompts still pass through the deterministic local Danbooru compiler before image generation. External tag-suggestion calls are off by default; set `NCC_TAG_SUGGESTION_MODE=external` only when you intentionally want the configured model provider to spend API tokens on candidate suggestions.

Mock image generation is a test/development path, not the user-facing completion gate. When `NCC_IMAGE_PROVIDER=novelai` and `NOVELAI_API_TOKEN` are set, the image stage calls NovelAI and stores returned candidate PNGs locally with provider metadata. Real NovelAI image generation is refused while tag conversion is still `mock`; run the prompt dry-run gate with `NCC_TAG_PROVIDER=local` or a model-assisted provider first.

## Creator UI Workflow

The first screen must make the user flow explicit:

1. paste a short Korean source scene;
2. review character locks and the 6 storyboard panels;
3. select one image candidate per panel;
4. edit Korean speech balloons and export the vertical PNG.

The UI must also show the active backend image mode. `backend mock` means the images are sample flow-check outputs. `실제 NovelAI` means the image prompts are sent to NovelAI and the returned candidate PNGs are stored in the local project directory.

Before spending image credits, run story and prompt stages only with image generation disabled:

```bash
NCC_TAG_PROVIDER=local NCC_IMAGE_PROVIDER=mock ncc-api
```

Then create a project and run `/stages/story` followed by `/stages/prompts`. The dry run passes only when `prompt_ir.yaml` and `nai_prompts.yaml` contain canonical Danbooru-style tag provenance, storyboard/panel-spec visual motifs are preserved in the NAI prompt, and no `images/` directory is created.

To test only the source-text to Danbooru prompt conversion, without API or image generation:

```bash
.venv/bin/ncc-compile-prompt <<'EOF'
노란 우비를 입은 소녀가 겨울 바닷가에서 오래된 엽서를 발견한다.
멀리 등대 불빛이 켜지고 비가 내린다.
EOF
```

Copy `POSITIVE` into NovelAI's prompt field and `NEGATIVE` into the undesired/negative prompt field. Use `--json` to inspect canonical tags, `provider=local`, and `extractor=local_alias` provenance:

```bash
.venv/bin/ncc-compile-prompt --json "노란 우비와 엽서가 있는 겨울 바닷가 장면"
```

This path uses the local candidate extractor and canonical compiler only. It does not call the API, NovelAI, DeepSeek, OpenAI, or Hugging Face. The compiler is tested for Korean/English/Japanese convergence, basic negation filtering such as `no rain`, `아닌/없는`, and `ではない`, and deterministic 50-run output.

For a model-assisted prompt dry run, set `NCC_TAG_PROVIDER=deepseek`, `DEEPSEEK_API_KEY`, `DEEPSEEK_MODEL=deepseek-v4-pro`, `DEEPSEEK_BASE_URL=https://api.deepseek.com`, and `NCC_TAG_SUGGESTION_MODE=external` before running the backend prompt stage. The external model may suggest candidate tags, but unknown tags and blocked tags are filtered by the local compiler before they reach `nai_prompts.yaml`. If the external suggestion call fails, prompt generation reports a diagnostic instead of pretending DeepSeek contributed candidates.

## Backend

Start the local API:

```bash
set -a
[ -f .env.local ] && . .env.local
set +a
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

Run an explicit NovelAI smoke after setting local credentials:

```bash
ncc-novelai-smoke
```

That command performs a minimal 1-panel/1-candidate real-provider smoke. To spend credits on the full product completion demo, run:

```bash
ncc-novelai-smoke --full-demo
```

The full demo must produce 18 real NovelAI candidate images for a 6-panel project, show `provider=novelai` in candidate metadata, and export a 1080px+ PNG from selected real images.
