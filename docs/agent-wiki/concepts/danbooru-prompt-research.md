# Danbooru Prompt Research

## Question

How should `ncc` convert multilingual source text into Danbooru/NovelAI prompts without relying on a narrow substring-only lexicon?

## Sources Checked

- KBlueLeaf DanTagGen collection: https://huggingface.co/collections/KBlueLeaf/dantaggen
- KBlueLeaf DanTagGen beta model card: https://huggingface.co/KBlueLeaf/DanTagGen-beta
- DeepSeek official API quick start: https://api-docs.deepseek.com/
- DeepSeek official chat completion reference: https://api-docs.deepseek.com/api/create-chat-completion
- KohakuBlueleaf KGen: https://github.com/KohakuBlueleaf/KGen
- Danbooru2023 dataset: https://huggingface.co/datasets/nyanko7/danbooru2023
- Japanese Danbooru tag pair dataset: https://huggingface.co/datasets/p1atdev/danbooru-ja-tag-pair-20240715
- SmilingWolf WD ViT Tagger v3: https://huggingface.co/SmilingWolf/wd-vit-tagger-v3
- Danbooru autotagger: https://github.com/danbooru/autotagger
- Public text-to-tag discussion: https://www.reddit.com/r/comfyui/comments/1jupfvf/looking_for_text2tag_solution_something_able_to/

## Findings

DanTagGen is a Danbooru tag-based prompt generator family. The beta model is a 0.4B text-generation model and can be run through Transformers, llama.cpp, Ollama, vLLM, and other local runtimes. KGen frames DanTagGen as an earlier prompt-generation project trained around the Danbooru tag system, while TIPO is the broader natural-language plus tag prompt-generation direction.

Danbooru2023 is the right source class for canonical vocabulary and metadata. It is a large anime image dataset with detailed Danbooru-style tags, not a direct natural-language parser.

The Japanese Danbooru tag pair dataset is a better source class for Japanese aliases than hand-writing everything. Korean still needs either a curated alias table, translation layer, or model-assisted semantic extractor.

WD taggers and Danbooru autotagger are image taggers. They are useful after image generation to check whether the produced image contains intended tags. They should not be treated as source-text converters.

Public discussion around text-to-booru conversion points toward combining LLM-based candidate generation with sanitization/canonicalization rather than trusting model text directly.

## Decision For This Repo

The immediate implementation should use a deterministic candidate-extraction interface plus canonical compiler:

```text
source text -> candidate extractor(s) -> canonical compiler -> NovelAI prompt
```

For now, `local_alias` is the default extractor because it needs no network, no API key, and preserves local-first behavior. It must use language-aware boundaries and multilingual aliases so it does not repeat substring false positives.

External model integration remains a future adapter:

- `dantaggen` or `tipo`: optional candidate extractor for richer tags.
- `deepseek/openai/mimo`: structured semantic facts and tag candidates only.
- `danbooru_vocab`: canonical tag validation and category metadata.
- `wd/danbooru_autotagger`: generated-image QA.

## Current Verification Gate

- Korean, English, and Japanese equivalent source text must converge to the same core tag set.
- `raincoat` must not emit `rain`.
- `엽서가` must not emit `library`.
- Prompt lab must output copyable POSITIVE/NEGATIVE text plus provenance without calling NovelAI or an external API.

## 2026-06-05 Implementation Pass

Internal options checked:

- Keep direct substring matching in `CanonicalTagCompiler`: rejected because it repeated false positives.
- Add only a regex patch: rejected as too narrow without a candidate-extractor boundary.
- Add a local deterministic candidate extractor before external model integration: chosen because it preserves local-first behavior, supports tests, and leaves DanTagGen/TIPO/DeepSeek adapters as explicit future candidate sources.

Implemented:

- `LocalAliasCandidateExtractor` for language-aware local candidate extraction.
- `SourceTextTagPipeline` for `source text -> candidates -> canonical compiler`.
- Japanese seed aliases for the prompt lab verification fixture.
- Prompt lab JSON provenance with `provider=local` and `extractor=local_alias`.

Verified:

- `tests/test_t5_tag_compiler.py` and `tests/test_t5_prompt_lab.py` pass.
- Full backend suite passes: `67 passed`.
- Frontend test/lint/build pass.
- `ncc-compile-prompt` produces the same core prompt for Korean, English, and Japanese equivalent sample text.

## 2026-06-05 Negation And Panel-Motif Pass

External/internal options rechecked:

- DanTagGen remains a plausible future candidate extractor, but it is not a deterministic canonical gate.
- Danbooru2023 and Japanese tag-pair datasets remain better long-term vocabulary sources than expanding a hand-written lexicon indefinitely.
- For this repo's immediate user test, local deterministic alias extraction plus canonical filtering is still the safest default because it needs no API key and can be regression-tested.

Implemented:

- Alias matches now inspect nearby language-specific negation signals before emitting candidates.
- Japanese suffix handling covers common prompt-lab forms such as `はがきだけ`.
- The local prompt stage compiles panel beat, setting, camera, composition, and emotion instead of only beat/emotion.
- The lexicon now covers the active tram-stop project motifs: `cat_brooch`, `brooch`, `blue_station_display`, `tram`, `tram_stop`, `narrow_alley`, `memory_light`, `rain`, and `shadow_creature`.
- `NCC_TAG_PROVIDER=deepseek` now remains visible as `provider=deepseek` in provider status/provenance while final prompts still go through `compiler=local_canonical`.
- `NCC_TAG_SUGGESTION_MODE=external` enables an OpenAI-compatible candidate extractor for DeepSeek/OpenAI/MiMo; by default no external tag-suggestion call is made, so tests and local prompt lab runs do not spend tokens.
- A follow-up review checked official DeepSeek docs and corrected the default model to `deepseek-v4-pro`; `deepseek-4-pro` is not the documented model id. DeepSeek tag extraction disables thinking mode and fails with diagnostics on malformed provider responses.

Verified:

- `tests/test_t5_tag_compiler.py`, `tests/test_t5_prompt_lab.py`, and `tests/test_t5_prompts.py` cover negation, multilingual convergence, prompt-lab output, panel-spec motif preservation, and deterministic local compilation.
- Model-assisted tests cover raw external suggestions as candidates only: accepted canonical tags stay positive, blocked text tags move negative, and unknown suggestions are discarded.
- External provider failure tests cover that prompt generation does not silently fall back when `NCC_TAG_SUGGESTION_MODE=external` is set.
- Full backend suite passes: `74 passed`.
- Prompt lab emits copyable POSITIVE/NEGATIVE prompts for the active tram-stop source without sending text to NovelAI, DeepSeek, OpenAI, or Hugging Face.
