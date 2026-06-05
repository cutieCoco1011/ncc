# Verification

## Automated Mock Path

Default verification uses deterministic local providers and no external API keys:

```bash
. .venv/bin/activate
pytest
cd frontend
npm test
npm run build
npm audit --json
```

The backend gold-path smoke starts from the Korean fixture in `src/ncc/fixtures.py` and verifies:

- 6 storyboard panels;
- 18 image candidate records;
- one selected image per panel;
- Korean speech balloon/caption data;
- a readable PNG export at 1080px width or higher.
- multiple Korean source fixtures exercise the same mock export path.

## Real Provider Notes

Real providers are opt-in and are not required by the default suite. Configure them only in local environment files:

- `NCC_LLM_PROVIDER=openai` with `OPENAI_API_KEY`;
- `NCC_LLM_PROVIDER=openrouter` with `OPENROUTER_API_KEY`;
- `NCC_TAG_PROVIDER=local` for the local Danbooru compiler;
- `NCC_TAG_PROVIDER=deepseek` with `DEEPSEEK_API_KEY`, `DEEPSEEK_MODEL=deepseek-v4-pro`, and `DEEPSEEK_BASE_URL=https://api.deepseek.com` for tag-candidate suggestions that still pass through the local compiler;
- `NCC_TAG_SUGGESTION_MODE=external` only when a configured tag provider should actually spend API tokens for candidate suggestions;
- `NCC_IMAGE_PROVIDER=novelai` with `NOVELAI_API_TOKEN`;
- optional `NOVELAI_IMAGE_ENDPOINT`, `NOVELAI_IMAGE_MODEL`, and `NOVELAI_TIMEOUT_SECONDS`;
- `NCC_TAG_PROVIDER=mock` only for deterministic fixture tags.

If a real provider credential is missing, the adapter reports `not_configured`. The app should continue to support scaffold, mock generation, UI review, candidate selection, lettering, and PNG export without those credentials.

Run the opt-in real-provider smoke only when a user has intentionally configured credentials:

```bash
ncc-novelai-smoke
```

Expected minimal evidence:

- status is `passed`;
- `candidate_count` is at least 1;
- provider metadata is `novelai`;
- a real candidate PNG exists under the reported local project directory.

Product completion requires stronger manual evidence:

- `ncc-novelai-smoke --full-demo` or equivalent UI/API flow creates 6 panels x 3 candidates;
- the creator UI candidate gallery shows real image candidates and provider metadata;
- one candidate per panel is selected;
- lettering/export produces a 1080px+ PNG from selected real images;
- API keys/tokens are absent from artifacts, logs, screenshots, exports, and git diff.

## Prompt Dry Run Gate

Before spending NovelAI image credits, run only story + prompt stages:

```bash
NCC_TAG_PROVIDER=local NCC_IMAGE_PROVIDER=mock .venv/bin/ncc-api
```

The gate passes only when:

- `prompt_ir` and `nai_prompts` contain canonical Danbooru-style tag provenance;
- tag provenance is `provider=local` or a model-assisted provider that still passes through the local compiler;
- storyboard/panel-spec setting, camera, composition, and beat material are compiled into canonical prompt tags where the lexicon supports them;
- negated aliases such as `no rain`, `아닌/없는`, and `ではない` do not become positive tags;
- `image_candidates` is absent;
- no `images/` directory is created in the project.

Current prompt-lab regression evidence includes the Korean source pattern:

```text
비 오는 전차 정류장에서 고양이 브로치가 빛나고 푸른 전광판이 켜진다.
골목 끝에는 그림자 괴물이 있지만, 바닷가는 아니다.
```

The expected POSITIVE prompt contains `cat_brooch`, `tram_stop`, `tram`, `narrow_alley`, `rain`, `blue_station_display`, and `shadow_creature`, while `winter_seaside` is filtered out by the negation.

## Determinism Gate

For `NCC_TAG_PROVIDER=local`, run the same source through story + prompt compilation 50 times. The unique `prompt_ir`/`nai_prompts` signature count must be exactly 1.

For LLM-assisted providers, record both raw suggestion variance and final compiled tag variance. Raw suggestions may vary; the final canonical tag set for required visual facts must remain stable.

Model-assisted tag extraction is candidate-only. Tests cover that a DeepSeek-shaped suggester can add a raw candidate such as `lighthouse`, while `speech bubble text` is moved to negative tags and unknown suggestions are discarded by `compiler=local_canonical`.

When `NCC_TAG_SUGGESTION_MODE=external` is enabled, upstream model-suggestion failures must fail the prompt stage with diagnostics instead of silently falling back to local-only output. This prevents a user from believing DeepSeek/OpenAI/MiMo contributed candidates when the external call did not actually succeed.

For the current `비-오는-정류장의-약속-*` project, the prompt-stage check must prove that the local compiler preserves the project-critical motifs across `nai_prompts`: brooch/cat brooch, blue station display, tram stop/tram, rain, narrow alley, memory light, and shadow creature. The prompt must remain free of Korean source text; Korean dialogue belongs in lettering artifacts.

### 2026-06-05 Real DeepSeek Tag-Suggestion Check

This check used the real DeepSeek API with `DEEPSEEK_API_KEY` loaded from ignored `.env.local`; the key value was not printed. `.env.local` was corrected to use `DEEPSEEK_MODEL=deepseek-v4-pro`, matching the official DeepSeek V4 model id.

Direct extractor evidence:

- endpoint: `https://api.deepseek.com/chat/completions`;
- model: `deepseek-v4-pro`;
- request mode: `NCC_TAG_SUGGESTION_MODE=external`;
- raw DeepSeek candidates for the tram-stop source included `rain`, `tram stop`, `cat brooch`, `blue electric sign`, `alley`, and `shadow monster`;
- local canonical compiler accepted only canonical supported tags, including `rain`, `tram_stop`, `cat_brooch`, `narrow_alley`, and `shadow_creature`.

Prompt-stage evidence:

- `NCC_TAG_PROVIDER=deepseek NCC_TAG_SUGGESTION_MODE=external NCC_IMAGE_PROVIDER=mock` completed `/stages/prompts`;
- prompt provenance showed `provider=deepseek` and `extractor=local_alias,deepseek`;
- panel prompts preserved `cat_brooch`, `brooch`, `blue_station_display`, `tram_stop`, `tram`, `narrow_alley`, `rain`, and `shadow_creature`;
- the negated source sentence `바닷가는 아니다` did not leak `winter_seaside` or `lighthouse` after the fix.

Regression coverage added:

- DeepSeek requests use a certifi-backed SSL context;
- DeepSeek tag suggestion disables thinking mode for JSON extraction;
- malformed provider responses fail with diagnostics;
- model-suggested tags are vetoed by negated source aliases;
- a negated setting veto does not remove an explicitly positive motif such as `등대는 보인다`.

## Creator UI Flow

The creator UI completion gate is the same workflow a first-time user should follow:

1. read the first-screen guide and confirm it distinguishes `backend mock` from `실제 NovelAI`;
2. paste or open a short Korean source;
3. confirm the story review pane shows character locks and 6 panels;
4. select a visible image candidate from the gallery;
5. edit the Korean speech balloon text;
6. run `PNG Export` and confirm the backend lettering artifact and exported PNG contain the edited text.

Required visual evidence:

- desktop screenshot at `http://127.0.0.1:3000/` with the full guide visible;
- mobile screenshot proving the same guide has no horizontal overflow;
- post-export screenshot showing real image candidates, selected candidate state, edited speech balloon text, and `PNG 열기`.

### 2026-06-05 Real NovelAI Check

Credentials were present locally and the real image provider was exercised with three different Korean sources. This was not a mock-image check. This is historical evidence from before the mock-tag guard; new real-image checks must first pass the prompt dry-run gate with non-mock tag provenance.

Command shape:

```bash
# Set NOVELAI_API_TOKEN in the local shell or ignored .env.local first.
NCC_PROJECTS_DIR=/Users/mangmuse/Documents/ncc-projects-real-multi-source-v3 \
NCC_IMAGE_PROVIDER=novelai \
NCC_TAG_PROVIDER=mock \
.venv/bin/ncc-api
```

Then each source was submitted through the `/gold-path` API with `panel_count=6`.

Evidence:

- `도서관 별빛 열쇠`: 18 real NovelAI candidates, 6 selected, export `1080x8640`.
- `지하철 사탕 기계`: 18 real NovelAI candidates, 6 selected, export `1080x8640`.
- `바닷가 엽서 우체통`: 18 real NovelAI candidates, 6 selected, export `1080x8640`.
- Manual candidate QA sheet: `tmp/real-v3-manual-selected-contact.jpg` in the local workspace.
- Real export PNGs are under `/Users/mangmuse/Documents/ncc-projects-real-multi-source-v3/*/exports/webtoon_export.png`.

Quality verdict:

- Pass: real NovelAI images are generated, saved, selectable, lettered in Korean, and exported as vertical PNGs.
- Pass: prompt fixes kept the main setting from drifting on later beats and improved protagonist visibility/continuity.
- Remaining gap: automatic first-candidate selection is not a sufficient quality selector; manual candidate choice produced the acceptable exports. A future quality pass should rank/select candidates by protagonist presence, setting match, and character continuity instead of selecting the first candidate per panel.

### 2026-06-05 Creator UI Onboarding Check

The creator UI was exercised at `http://127.0.0.1:3000/` against a local API configured with `NCC_IMAGE_PROVIDER=novelai`, `NCC_TAG_PROVIDER=mock`, and `NOVELAI_API_TOKEN` from ignored local env.

Evidence:

- desktop guide screenshot: `tmp/ux-guide-desktop-final.png`;
- mobile guide screenshot: `tmp/ux-guide-mobile-final.png`;
- post-export real-flow screenshot: `tmp/ux-flow-after-export-final.png`;
- provider guide copy showed `백엔드 이미지: 실제 NovelAI`;
- the UI opened the latest real NovelAI project, selected `p1-c2`, edited the `p1-speech` text to `처음 사용자 플로우 확인`, ran `PNG Export`, and the backend artifact preserved that exact text with `manual_text=true`.

Record the exact evidence commands in the PR or handoff. The expected committed-tree secret scan is:

```bash
git grep -n -E 'sk-[A-Za-z0-9]|NOVELAI_API_''TOKEN=.+|OPENAI_API_''KEY=.+|Bearer [A-Za-z0-9._-]+' HEAD -- . ':!frontend/package-lock.json'
```

Generated project directories, screenshots, `.env.local`, `.dryforge/`, caches, and `tmp/` are ignored and must stay out of git.

## Secret Safety

Project artifacts are stored under the local project root. Storage rejects writes that include configured provider secret values. `.env*`, `.dryforge/`, generated projects, cache directories, and local exports are ignored by git.
