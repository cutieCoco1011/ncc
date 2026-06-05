# Prompt Tagging Architecture

## Current Lesson

The Danbooru prompt compiler must not be treated as a semantic analyzer. A small hand-written YAML alias list plus substring matching is only a prototype and is not enough for user-facing NovelAI prompt quality.

The correct shape is:

```text
source text -> semantic facts/candidate extractors -> canonical Danbooru compiler -> NovelAI prompt
```

The canonical compiler is the final deterministic gate. It owns canonical tag validation, alias normalization, provider provenance, blocklists, negative defaults, ordering, and reproducibility. It must not blindly trust raw model output.

Current implementation:

- `LocalAliasCandidateExtractor` extracts deterministic local candidates with language-aware boundaries.
- `SourceTextTagPipeline` combines source-text candidates with base style candidates.
- `CanonicalTagCompiler` normalizes, filters, orders, and records provenance.
- `ncc-compile-prompt` exposes POSITIVE/NEGATIVE/provenance for direct NovelAI web testing.
- Project prompt compilation feeds the local compiler with panel beat, setting, camera, composition, and emotion so storyboard/panel-spec motifs are not dropped on the non-mock path.

## Candidate Extractors

- `local_alias`: conservative multilingual alias matching with language-aware boundaries.
- `dantaggen`: optional local/Hugging Face Danbooru prompt/tag generation candidate source.
- `deepseek/openai/mimo`: structured JSON facts and tag candidates only; raw text must not become a final prompt. External calls require explicit `NCC_TAG_SUGGESTION_MODE=external`.
- `danbooru_vocab`: imported Danbooru tag vocabulary, aliases, and wiki metadata.
- `image_tagger_qa`: WD/DeepDanbooru/Danbooru autotagger output for generated-image QA, not for original text conversion.

Provider correctness:

- DeepSeek's current official OpenAI-compatible base URL is `https://api.deepseek.com`, with chat completions at `/chat/completions`.
- Use `deepseek-v4-pro` or `deepseek-v4-flash`; do not document `deepseek-4-pro`.
- For tag suggestions, disable DeepSeek thinking mode to avoid extra reasoning token spend on a JSON extraction task.
- If external suggestion mode is enabled and the provider call fails or returns malformed JSON, fail the prompt stage with diagnostics instead of silently falling back to local-only output.
- Completion claims for model-assisted providers require at least one real provider call when credentials are configured; fake OpenAI-compatible responses are not enough.
- Real calls must verify both direct extractor output and prompt-stage provenance/retained canonical tags.

## Required Tests

- Korean, English, and Japanese equivalents converge to the same core canonical tag set.
- `raincoat` must not imply `rain`.
- `엽서가` must not imply `서가` or `library`.
- Negated aliases such as `no rain`, `아닌/없는`, and `ではない` must not become positive tags.
- Current-project motifs must survive prompt compilation: cat/brooch, blue station display, tram stop/tram, rain, narrow alley, memory light, and shadow creature.
- Repeated source conversion must be deterministic after candidate normalization.
- Prompt lab output must expose positive prompt, negative prompt, tags, and provenance.

## External Sources To Recheck

- KBlueLeaf DanTagGen: https://huggingface.co/collections/KBlueLeaf/dantaggen
- DanTagGen beta model card: https://huggingface.co/KBlueLeaf/DanTagGen-beta
- Danbooru2023 dataset: https://huggingface.co/datasets/nyanko7/danbooru2023
- Japanese Danbooru tag pairs: https://huggingface.co/datasets/p1atdev/danbooru-ja-tag-pair-20240715
- SmilingWolf WD tagger: https://huggingface.co/SmilingWolf/wd-vit-tagger-v3
- Danbooru autotagger: https://github.com/danbooru/autotagger
