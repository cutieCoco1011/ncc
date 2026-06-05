# Model-Agnostic Danbooru Tag Compiler Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current static/mock prompt tagging with a model-agnostic Danbooru-style tag compiler that works without relying on a specific LLM.

**Architecture:** The local compiler is the source of truth. It owns the canonical tag lexicon, alias normalization, category policy, negative-tag policy, character-lock rules, prompt ordering, and quality gates. LLMs can only suggest candidate tags with evidence; GPT, DeepSeek, MiMo, or any other model output must be normalized and filtered before it can affect the final prompt. Raw LLM text is never sent directly to NovelAI.

**Tech Stack:** Python 3.13, Pydantic, FastAPI, local YAML/JSON lexicon, pytest golden snapshots, optional provider adapters over JSON contracts.

---

## Non-Negotiable Rules

- Do not call NovelAI while building or testing tag conversion.
- Do not treat any LLM output as the final prompt.
- Do not make GPT-specific behavior part of the quality gate.
- The no-LLM `local` compiler must produce usable Danbooru-style prompts.
- Cross-model tests must prove GPT/DeepSeek/MiMo-style suggestions converge to the same canonical core tags.
- UI/API must show tag provider and image provider separately.

## Planned Environment Variables

Use these names for the first DeepSeek-assisted compiler work:

```bash
NCC_TAG_PROVIDER=deepseek
DEEPSEEK_API_KEY=...
DEEPSEEK_MODEL=deepseek-v4-pro
DEEPSEEK_BASE_URL=https://api.deepseek.com
NCC_IMAGE_PROVIDER=mock
```

`DEEPSEEK_API_KEY` is the secret. `DEEPSEEK_MODEL` is intentionally configurable because the exact model id must match the provider account/API. During compiler development, keep `NCC_IMAGE_PROVIDER=mock` so no NovelAI credits are spent.

## Files

- Create: `src/ncc/tags.py`
  - `CanonicalTagCompiler`
  - `normalize_danbooru_tag`
  - `TagProvider` protocol
  - `StaticMockTagProvider`
  - `LocalDanbooruTagProvider`
  - optional LLM suggestion parser
- Create: `src/ncc/danbooru_lexicon.yaml`
  - canonical tags
  - aliases
  - categories
  - positive blocklist
  - negative defaults
  - required character-lock categories
- Modify: `src/ncc/prompts.py`
  - inject tag provider
  - assemble final prompt from compiler output only
- Modify: `src/ncc/orchestrator.py`
  - choose tag provider from settings
  - block real image generation when tag provider is mock
- Modify: `src/ncc/settings.py`
  - support `NCC_TAG_PROVIDER=mock|local|openai|deepseek|mimo`
- Modify: `frontend/app/page.jsx`
  - show `태그 변환` and `이미지 생성` separately
- Create: `tests/test_t5_tag_compiler.py`
- Modify: `tests/test_t5_prompts.py`
- Modify: `tests/test_t3_api.py`
- Modify: `docs/verification.md`

## Completion Criteria

- `NCC_TAG_PROVIDER=mock`: current behavior preserved and clearly labeled mock.
- `NCC_TAG_PROVIDER=local`: no LLM call, no image generation, but prompt artifacts contain canonical Danbooru-style tags with `provider=local`.
- `NCC_TAG_PROVIDER=openai|deepseek|mimo`: provider suggestions are accepted only as evidence; final prompts pass through the same local compiler.
- Golden Korean fixtures produce stable core prompt tags across GPT/DeepSeek/MiMo-style responses.
- Determinism is measured explicitly: the same Korean source run 50 times through `NCC_TAG_PROVIDER=local` must produce identical `prompt_ir` and `nai_prompts` hashes.
- Optional LLM-assisted providers must report variance: the same Korean source run 50 times must show how many unique raw suggestion sets were produced and confirm the final compiled canonical tag set remains unchanged.
- Prompt dry-run can be verified without creating `images/`.
- Real NovelAI generation is refused if tag provider is mock.

---

### Task 1: Make Mock Tagging Explicit

**Files:**
- Modify: `src/ncc/prompts.py`
- Modify: `tests/test_t5_prompts.py`

- [ ] **Step 1: Add failing test**

Add to `tests/test_t5_prompts.py`:

```python
def test_default_prompt_tags_are_explicitly_mock_provenance() -> None:
    source = (
        "겨울 바닷가에서 서윤은 녹슨 우체통 안에 젖지 않은 엽서를 발견했다. "
        "서윤은 하얀 장갑을 낀 손으로 엽서를 품고 방파제를 따라 등대로 향했다."
    )
    bundle = MockLLMStoryProvider().analyze("바닷가 엽서 우체통", source, panel_count=6)
    prompt_ir = PromptCompiler().build_prompt_ir("demo", bundle.panel_specs, bundle.characters)

    first = prompt_ir.prompts[0]
    assert {candidate.source for candidate in first.tag_candidates} == {"static-mock"}
    assert all(candidate.provenance["provider"] == "mock" for candidate in first.tag_candidates)
```

- [ ] **Step 2: Run failing test**

Run:

```bash
.venv/bin/pytest tests/test_t5_prompts.py::test_default_prompt_tags_are_explicitly_mock_provenance -q
```

Expected: FAIL until `provider=mock` provenance is written.

- [ ] **Step 3: Patch mock provenance**

In the existing `TagCandidate` creation, set:

```python
provenance={"panel_id": panel_id, "provider": "mock"}
```

- [ ] **Step 4: Verify**

Run:

```bash
.venv/bin/pytest tests/test_t5_prompts.py::test_default_prompt_tags_are_explicitly_mock_provenance -q
```

Expected: PASS.

---

### Task 2: Build Canonical Local Compiler

**Files:**
- Create: `src/ncc/tags.py`
- Create: `src/ncc/danbooru_lexicon.yaml`
- Create: `tests/test_t5_tag_compiler.py`

- [ ] **Step 1: Create lexicon**

Create `src/ncc/danbooru_lexicon.yaml`:

```yaml
canonical_tags:
  yellow_raincoat:
    category: outfit
    aliases: ["yellow raincoat", "노란 우비"]
  blue_sneakers:
    category: outfit
    aliases: ["blue sneakers", "파란 운동화"]
  white_gloves:
    category: outfit
    aliases: ["white gloves", "하얀 장갑"]
  short_black_hair:
    category: hair
    aliases: ["short black hair", "short black bob hair"]
  short_brown_hair:
    category: hair
    aliases: ["short brown hair", "short brown bob hair"]
  winter_seaside:
    category: setting
    aliases: ["winter seaside", "바닷가", "방파제"]
  tram_stop:
    category: setting
    aliases: ["tram stop", "전차 정류장", "정류장"]
  postcard:
    category: prop
    aliases: ["postcard", "엽서", "우체통"]
  silver_key:
    category: prop
    aliases: ["silver key", "열쇠"]
  rain:
    category: atmosphere
    aliases: ["rain", "비", "빗속"]
  dramatic_lighting:
    category: style
    aliases: ["dramatic lighting"]
  cinematic_composition:
    category: style
    aliases: ["cinematic composition"]
  vertical_webtoon_panel:
    category: style
    aliases: ["vertical webtoon panel"]
positive_blocklist:
  - speech_bubble_text
  - watermark
  - logo
  - text
negative_defaults:
  - speech_bubble_text
  - watermark
  - logo
  - text
  - bad_hands
  - extra_fingers
required_categories:
  - hair
  - outfit
  - setting
```

- [ ] **Step 2: Add compiler tests**

Create `tests/test_t5_tag_compiler.py`:

```python
from ncc.tags import CanonicalTagCompiler, normalize_danbooru_tag


def test_normalize_danbooru_tag() -> None:
    assert normalize_danbooru_tag("Yellow Raincoat") == "yellow_raincoat"
    assert normalize_danbooru_tag("  speech bubble text  ") == "speech_bubble_text"
    assert normalize_danbooru_tag("한국어") == ""


def test_local_compiler_maps_aliases_and_filters_positive_blocklist() -> None:
    compiler = CanonicalTagCompiler.from_default_lexicon()

    result = compiler.compile_candidates(
        panel_id="p1",
        provider="local",
        candidates=["노란 우비", "winter seaside", "speech bubble text", "unknown pretty vibes"],
        evidence={"beat": "노란 우비를 입은 서윤이 겨울 바닷가에 있다."},
    )

    assert {tag.tag for tag in result.positive} == {"yellow_raincoat", "winter_seaside"}
    assert "speech_bubble_text" in {tag.tag for tag in result.negative}
    assert all(tag.provenance["provider"] == "local" for tag in result.positive)
```

- [ ] **Step 3: Run failing tests**

Run:

```bash
.venv/bin/pytest tests/test_t5_tag_compiler.py -q
```

Expected: FAIL because `ncc.tags` does not exist.

- [ ] **Step 4: Implement minimal compiler**

Create `src/ncc/tags.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass
import re

from .models import TagCandidate


def normalize_danbooru_tag(value: str) -> str:
    if re.search(r"[가-힣]", value):
        return ""
    normalized = value.strip().lower().replace(" ", "_")
    normalized = re.sub(r"[^a-z0-9_()]+", "", normalized)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized


@dataclass(frozen=True)
class CompiledTags:
    positive: list[TagCandidate]
    negative: list[TagCandidate]


class CanonicalTagCompiler:
    @classmethod
    def from_default_lexicon(cls) -> "CanonicalTagCompiler":
        aliases = {
            "yellow_raincoat": {"yellow raincoat", "노란 우비"},
            "blue_sneakers": {"blue sneakers", "파란 운동화"},
            "white_gloves": {"white gloves", "하얀 장갑"},
            "winter_seaside": {"winter seaside", "바닷가", "방파제"},
            "postcard": {"postcard", "엽서", "우체통"},
            "speech_bubble_text": {"speech bubble text"},
        }
        return cls(aliases=aliases, positive_blocklist={"speech_bubble_text"})

    def __init__(self, aliases: dict[str, set[str]], positive_blocklist: set[str]) -> None:
        self.aliases = aliases
        self.positive_blocklist = positive_blocklist

    def canonicalize(self, raw: str) -> str:
        raw_key = raw.strip().lower()
        normalized = normalize_danbooru_tag(raw)
        for canonical, aliases in self.aliases.items():
            if raw_key in {alias.lower() for alias in aliases} or normalized == canonical:
                return canonical
        return normalized if normalized in self.aliases else ""

    def compile_candidates(
        self,
        panel_id: str,
        provider: str,
        candidates: list[str],
        evidence: dict[str, str],
    ) -> CompiledTags:
        positive: list[TagCandidate] = []
        negative: list[TagCandidate] = []
        seen: set[str] = set()
        for raw in candidates:
            tag = self.canonicalize(raw)
            if not tag or tag in seen:
                continue
            seen.add(tag)
            candidate = TagCandidate(
                tag=tag,
                source=provider,
                confidence=0.8,
                provenance={"panel_id": panel_id, "provider": provider, **evidence},
            )
            if tag in self.positive_blocklist:
                negative.append(candidate)
            else:
                positive.append(candidate)
        return CompiledTags(positive=positive, negative=negative)
```

- [ ] **Step 5: Verify**

Run:

```bash
.venv/bin/pytest tests/test_t5_tag_compiler.py -q
```

Expected: PASS.

---

### Task 3: Add Local Provider To Prompt Compiler

**Files:**
- Modify: `src/ncc/tags.py`
- Modify: `src/ncc/prompts.py`
- Modify: `tests/test_t5_prompts.py`

- [ ] **Step 1: Add provider class**

Add to `src/ncc/tags.py`:

```python
class LocalDanbooruTagProvider:
    provider_name = "local"

    def __init__(self, compiler: CanonicalTagCompiler | None = None) -> None:
        self.compiler = compiler or CanonicalTagCompiler.from_default_lexicon()

    def tags_for_panel(self, panel_id: str, beat: str, emotion: str) -> list[TagCandidate]:
        candidates = [
            "vertical webtoon panel",
            "cinematic composition",
            "dramatic lighting",
            emotion,
            beat,
        ]
        compiled = self.compiler.compile_candidates(
            panel_id=panel_id,
            provider=self.provider_name,
            candidates=candidates,
            evidence={"beat": beat, "emotion": emotion},
        )
        return compiled.positive
```

- [ ] **Step 2: Inject provider**

In `src/ncc/prompts.py`, replace the embedded static class import/constructor with:

```python
from .tags import LocalDanbooruTagProvider, StaticMockTagProvider, TagProvider


class PromptCompiler:
    def __init__(self, tag_provider: TagProvider | None = None) -> None:
        self.tag_provider = tag_provider or StaticMockTagProvider()
```

- [ ] **Step 3: Add prompt test for local provider**

Add:

```python
from ncc.tags import LocalDanbooruTagProvider


def test_local_tag_provider_writes_non_mock_prompt_provenance() -> None:
    source = (
        "겨울 바닷가에서 서윤은 녹슨 우체통 안에 젖지 않은 엽서를 발견했다. "
        "서윤은 하얀 장갑을 낀 손으로 엽서를 품고 방파제를 따라 등대로 향했다."
    )
    bundle = MockLLMStoryProvider().analyze("바닷가 엽서 우체통", source, panel_count=6)
    prompt_ir = PromptCompiler(LocalDanbooruTagProvider()).build_prompt_ir(
        "demo",
        bundle.panel_specs,
        bundle.characters,
    )

    first = prompt_ir.prompts[0]
    assert any(candidate.tag == "winter_seaside" for candidate in first.tag_candidates)
    assert all(candidate.provenance["provider"] == "local" for candidate in first.tag_candidates)
```

- [ ] **Step 4: Verify**

Run:

```bash
.venv/bin/pytest tests/test_t5_prompts.py tests/test_t5_tag_compiler.py -q
```

Expected: PASS.

---

### Task 4: Add Cross-Model Suggestion Stability

**Files:**
- Modify: `src/ncc/tags.py`
- Modify: `tests/test_t5_tag_compiler.py`

- [ ] **Step 1: Add cross-model test**

Add:

```python
def test_cross_model_suggestions_compile_to_same_core_tags() -> None:
    compiler = CanonicalTagCompiler.from_default_lexicon()
    model_outputs = [
        ("openai", ["yellow raincoat", "postcard", "speech bubble text"]),
        ("deepseek", ["Yellow Raincoat", "post card", "speech bubble text"]),
        ("mimo", ["yellow_raincoat", "postcard", "text in image"]),
    ]

    compiled_sets = []
    for provider, tags in model_outputs:
        compiled = compiler.compile_candidates(
            panel_id="p1",
            provider=provider,
            candidates=tags,
            evidence={"beat": "노란 우비와 엽서"},
        )
        compiled_sets.append({tag.tag for tag in compiled.positive})

    assert compiled_sets[0] == compiled_sets[1] == compiled_sets[2] == {
        "yellow_raincoat",
        "postcard",
    }
```

- [ ] **Step 2: Add aliases needed by the test**

Add aliases:

```python
"postcard": {"postcard", "post card", "엽서", "우체통"},
"speech_bubble_text": {"speech bubble text", "text in image"},
```

- [ ] **Step 3: Verify**

Run:

```bash
.venv/bin/pytest tests/test_t5_tag_compiler.py::test_cross_model_suggestions_compile_to_same_core_tags -q
```

Expected: PASS.

---

### Task 5: Wire Settings And Orchestrator

**Files:**
- Modify: `src/ncc/settings.py`
- Modify: `src/ncc/orchestrator.py`
- Modify: `tests/test_t5_tag_compiler.py`

- [ ] **Step 1: Add settings tests**

Add:

```python
from ncc.settings import AppSettings


def test_local_tag_provider_is_configured_without_llm_key(monkeypatch) -> None:
    monkeypatch.setenv("NCC_TAG_PROVIDER", "local")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    settings = AppSettings.from_env()

    assert settings.tag.provider.value == "local"
    assert settings.tag.configured is True


def test_llm_tag_provider_reports_candidate_extraction_not_final_prompt(monkeypatch) -> None:
    monkeypatch.setenv("NCC_TAG_PROVIDER", "deepseek")

    settings = AppSettings.from_env()

    assert settings.tag.configured is True
    assert "local Danbooru compiler" in settings.tag.disclosure
```

- [ ] **Step 2: Extend settings**

In `_tag_config`, support:

```python
if provider == "local":
    return ProviderConfig(
        name="tag",
        provider=ProviderKind.LOCAL,
        configured=True,
        disclosure="Local Danbooru compiler runs on this machine.",
    )
if provider in {"openai", "deepseek", "mimo"}:
    return ProviderConfig(
        name="tag",
        provider=ProviderKind.LOCAL,
        configured=True,
        disclosure=f"{provider} may suggest tags, but final prompts are produced by the local Danbooru compiler.",
    )
```

- [ ] **Step 3: Wire provider factory**

In `NccOrchestrator`, add:

```python
def _tag_provider(self):
    if self.settings.tag.provider == ProviderKind.MOCK:
        return StaticMockTagProvider()
    if self.settings.tag.provider == ProviderKind.LOCAL:
        return LocalDanbooruTagProvider()
    raise ValueError(f"unsupported tag provider: {self.settings.tag.provider.value}")
```

Change:

```python
compiler = PromptCompiler()
```

to:

```python
compiler = PromptCompiler(tag_provider=self._tag_provider())
```

- [ ] **Step 4: Verify**

Run:

```bash
.venv/bin/pytest tests/test_t5_prompts.py tests/test_t5_tag_compiler.py -q
```

Expected: PASS.

---

### Task 6: Add Prompt Dry-Run Gate

**Files:**
- Modify: `tests/test_t3_api.py`
- Modify: `docs/verification.md`

- [ ] **Step 1: Add API dry-run test**

Add:

```python
def test_api_prompt_dry_run_does_not_generate_images(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("NCC_TAG_PROVIDER", "local")
    monkeypatch.setenv("NCC_IMAGE_PROVIDER", "mock")
    app = create_app(tmp_path)
    client = TestClient(app)
    project = client.post(
        "/projects",
        json={
            "title": "dry run",
            "source_text": "서윤은 겨울 바닷가에서 엽서를 발견했다.",
        },
    ).json()
    project_id = project["project_id"]

    assert client.post(f"/projects/{project_id}/stages/story").status_code == 200
    assert client.post(f"/projects/{project_id}/stages/prompts").status_code == 200

    artifacts = client.get(f"/projects/{project_id}/artifacts").json()
    assert artifacts["prompt_ir"]["prompts"]
    assert artifacts["nai_prompts"]["prompts"]
    assert artifacts["image_candidates"] is None
```

- [ ] **Step 2: Verify**

Run:

```bash
.venv/bin/pytest tests/test_t3_api.py::test_api_prompt_dry_run_does_not_generate_images -q
```

Expected: PASS.

- [ ] **Step 3: Document**

Add to `docs/verification.md`:

```markdown
## Prompt Dry Run Gate

Before spending NovelAI image credits, run only story + prompt stages.
The gate passes when `prompt_ir` and `nai_prompts` contain canonical non-mock tag provenance and no image files are created.
```

---

### Task 7: Add Determinism And Variance Benchmarks

**Files:**
- Create: `tests/test_t5_determinism.py`
- Modify: `docs/verification.md`

- [ ] **Step 1: Add local determinism test**

Create `tests/test_t5_determinism.py`:

```python
from ncc.prompts import PromptCompiler
from ncc.story_pipeline import MockLLMStoryProvider
from ncc.tags import LocalDanbooruTagProvider


def _compiled_prompt_signature(source: str) -> tuple[str, str]:
    bundle = MockLLMStoryProvider().analyze("determinism", source, panel_count=6)
    compiler = PromptCompiler(LocalDanbooruTagProvider())
    prompt_ir = compiler.build_prompt_ir("determinism", bundle.panel_specs, bundle.characters)
    nai_prompts = compiler.compile_nai_prompts("determinism", prompt_ir)
    return (
        prompt_ir.model_dump_json(),
        nai_prompts.model_dump_json(),
    )


def test_local_tag_compiler_is_identical_across_50_runs() -> None:
    source = (
        "겨울 바닷가에서 서윤은 녹슨 우체통 안에 젖지 않은 엽서를 발견했다. "
        "서윤은 하얀 장갑을 낀 손으로 엽서를 품고 방파제를 따라 등대로 향했다."
    )

    signatures = {_compiled_prompt_signature(source) for _ in range(50)}

    assert len(signatures) == 1
```

- [ ] **Step 2: Run local determinism test**

Run:

```bash
.venv/bin/pytest tests/test_t5_determinism.py::test_local_tag_compiler_is_identical_across_50_runs -q
```

Expected: PASS. Any failure means hidden nondeterminism in story extraction, tag ordering, dedupe ordering, or prompt serialization.

- [ ] **Step 3: Add LLM variance contract test with fixtures**

Add:

```python
from ncc.tags import CanonicalTagCompiler


def test_llm_raw_variance_does_not_change_final_canonical_tags() -> None:
    compiler = CanonicalTagCompiler.from_default_lexicon()
    raw_suggestions = [
        ["yellow raincoat", "postcard", "winter seaside"],
        ["yellow_raincoat", "post card", "winter seaside"],
        ["노란 우비", "엽서", "바닷가"],
    ] * 17

    compiled_sets = {
        tuple(
            sorted(
                tag.tag
                for tag in compiler.compile_candidates(
                    panel_id="p1",
                    provider="llm-fixture",
                    candidates=suggestions,
                    evidence={"source": "fixture"},
                ).positive
            )
        )
        for suggestions in raw_suggestions[:50]
    }

    assert len(raw_suggestions[:50]) == 50
    assert len({tuple(suggestions) for suggestions in raw_suggestions[:50]}) == 3
    assert compiled_sets == {("postcard", "winter_seaside", "yellow_raincoat")}
```

- [ ] **Step 4: Run variance contract test**

Run:

```bash
.venv/bin/pytest tests/test_t5_determinism.py::test_llm_raw_variance_does_not_change_final_canonical_tags -q
```

Expected: PASS. This proves raw model suggestion variance is absorbed by canonicalization.

- [ ] **Step 5: Document determinism reporting**

Add to `docs/verification.md`:

```markdown
## Determinism Gate

For `NCC_TAG_PROVIDER=local`, run the same source through story + prompt compilation 50 times.
The gate passes only when the unique `prompt_ir`/`nai_prompts` signature count is exactly 1.

For LLM-assisted providers, record both raw suggestion variance and final compiled tag variance.
Raw suggestions may vary; the final canonical tag set for required visual facts must remain stable.
```

---

### Task 8: Block Real Images With Mock Tags

**Files:**
- Modify: `src/ncc/orchestrator.py`
- Modify: `tests/test_t3_api.py`
- Modify: `frontend/app/page.jsx`
- Modify: `frontend/tests/onboarding.test.mjs`

- [ ] **Step 1: Add backend guard**

In `run_image_stage`, before reading prompts:

```python
if self.settings.image.provider == ProviderKind.NOVELAI and self.settings.tag.provider == ProviderKind.MOCK:
    raise ValueError("real NovelAI image generation requires NCC_TAG_PROVIDER=local or a model-assisted provider passing through the local Danbooru compiler")
```

- [ ] **Step 2: Add UI wording**

Show two separate lines:

```text
태그 변환: local Danbooru compiler
이미지 생성: 실제 NovelAI
```

When tags are mock:

```text
현재 태그 변환은 mock입니다. 실제 이미지 생성 전에 local Danbooru compiler dry-run을 통과해야 합니다.
```

- [ ] **Step 3: Verify no accidental image spend**

Run:

```bash
NCC_TAG_PROVIDER=mock NCC_IMAGE_PROVIDER=novelai .venv/bin/pytest tests/test_t3_api.py -q
```

Expected: tests assert the guard without calling NovelAI.

---

## Final Verification

Run:

```bash
.venv/bin/pytest
cd frontend
npm test
npm run lint
npm run build
cd ..
git diff --check
git grep -n -E 'sk-[A-Za-z0-9]|NOVELAI_API_TOKEN=.+|OPENAI_API_KEY=.+|Bearer [A-Za-z0-9._-]+' -- . ':!frontend/package-lock.json'
```

Expected:

- pytest: all pass;
- frontend tests: all pass;
- lint/build: exit 0;
- diff check: no output;
- secret scan: exit 1 with no output.

## Self-Review

- Spec coverage: the compiler works without LLM, LLM output is only evidence, and image spend is blocked before prompt evidence.
- Placeholder scan: no task relies on unspecified model quality.
- Type consistency: `CanonicalTagCompiler`, `LocalDanbooruTagProvider`, `StaticMockTagProvider`, `TagCandidate`, and `PromptCompiler(tag_provider=...)` are used consistently.
