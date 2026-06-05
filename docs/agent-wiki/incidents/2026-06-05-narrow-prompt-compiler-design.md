# Narrow Prompt Compiler Design

## Context

During Danbooru prompt conversion work, the implementation focused too narrowly on a local YAML lexicon and substring alias matching.

## What Went Wrong

The agent treated a small deterministic compiler as if it were enough for semantic source-text conversion. The approach missed broader options such as DanTagGen, Danbooru datasets, multilingual alias corpora, and image taggers for generated-image QA.

The immediate technical symptom was false-positive alias matching:

- `엽서가` could trigger `서가` and therefore `library`.
- `yellow raincoat` could trigger `rain`.

## Root Cause

The compiler used plain substring checks where language-aware semantic extraction and canonical validation boundaries were needed. The architecture mixed candidate extraction and final prompt compilation.

## User Correction

The user pointed out that the agent's view was too narrow and that existing Hugging Face models, similar open-source work, or community implementations might solve parts of the problem better than a local hand-written rule patch.

## Future Retrieval Triggers

- prompt compiler
- Danbooru prompt conversion
- multilingual source text
- Korean English Japanese equivalence
- substring alias
- Hugging Face tagger
- DanTagGen
- NovelAI manual prompt testing

## Required Next Behavior

Before implementing prompt conversion fixes, broaden the design:

1. Separate semantic candidate extraction from deterministic canonical compilation.
2. Check existing model/data sources before extending local rules.
3. Add tests for multilingual equivalence and false positives.
4. Keep raw LLM/model output out of final NovelAI prompts.
5. Use generated-image taggers as QA signals, not as source-text converters.

## Verification Hook

The next implementation pass should not be accepted until targeted tests prove:

- Korean/English/Japanese equivalent source texts converge on the same core tags.
- `raincoat` does not emit `rain`.
- `엽서가` does not emit `library`.
- Prompt lab output is copyable into NovelAI and includes provenance.
