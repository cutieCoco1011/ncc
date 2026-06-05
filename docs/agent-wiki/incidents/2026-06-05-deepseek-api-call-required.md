# DeepSeek API Call Required

## Context

The prompt compiler was marked complete after unit/integration tests and fake model-suggestion tests. The user asked whether a real DeepSeek API call had actually been run, pointing out that logic tests are insufficient when the external LLM response shape can differ from assumptions.

## What Went Wrong

The implementation trusted mocked OpenAI-compatible responses before testing the real DeepSeek endpoint. The first real call exposed an SSL certificate verification failure in the tag suggester because it did not use the certifi-backed SSL context already used by the NovelAI adapter.

A real prompt-stage call then exposed a semantic issue: DeepSeek and the mock story pipeline could still leak `winter_seaside`/`lighthouse` from the negated sentence `바닷가는 아니다`.

## Root Cause

The review relied too much on local deterministic tests and fake provider tests. Those tests verified the trust boundary shape but not the actual provider transport behavior or real model candidate behavior.

## User Correction

Actual LLM calls are mandatory for model-assisted prompt conversion. Passing local logic tests is not enough if the real provider response differs.

## Required Next Behavior

- When a configured external provider is part of the completion claim, run at least one real provider call unless credentials are unavailable.
- Do not print API keys or tokens; report only presence, endpoint, model, candidate count, accepted tags, and provenance.
- Verify both direct extractor output and the product path that consumes it.
- Treat real-provider surprises as implementation evidence, not as optional smoke notes.

## Verification Hook

For DeepSeek tag suggestions:

- source `.env.local` without printing `DEEPSEEK_API_KEY`;
- run `OpenAICompatibleTagCandidateExtractor.from_env("deepseek").candidates_for_text(...)`;
- run `/stages/prompts` with `NCC_TAG_PROVIDER=deepseek` and `NCC_TAG_SUGGESTION_MODE=external`;
- confirm provenance includes `provider=deepseek` and `extractor=local_alias,deepseek`;
- confirm negated source facts do not become positive canonical tags.
