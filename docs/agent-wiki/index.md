# ncc Agent Wiki

This is the project-local LLM wiki for reusable agent memory. It exists so later work can retrieve prior mistakes, user corrections, architectural decisions, and verification rules without relying on chat history.

## How To Use

1. Before prompt/tagging/provider work, read the high-priority memories below.
2. When a mistake or user correction happens, add an incident page.
3. When an incident contains a reusable rule, update the matching concept page.
4. Keep pages concise and link to concrete files, tests, sources, or commands.

## High-Priority Memories

- [Broad Solution Search](concepts/broad-solution-search.md)
- [Danbooru Prompt Research](concepts/danbooru-prompt-research.md)
- [DeepSeek API Call Required](incidents/2026-06-05-deepseek-api-call-required.md)
- [Narrow Prompt Compiler Design](incidents/2026-06-05-narrow-prompt-compiler-design.md)
- [Prompt Tagging Architecture](concepts/prompt-tagging-architecture.md)
- [Small Commit Discipline](concepts/small-commit-discipline.md)

## Retrieval Triggers

Use this wiki when the work mentions:

- Danbooru prompts
- NovelAI prompt quality
- multilingual Korean/English/Japanese source conversion
- tag compiler determinism
- substring or alias matching
- DeepSeek/OpenAI/MiMo tag providers
- WD14, DeepDanbooru, DanTagGen, Danbooru datasets
- solution search feels too local or too implementation-first
- committing, pushing, or landing local changes
- libraries, existing models, open-source tools, datasets, papers, or community discussions might already exist

## Update Template

For incidents, include:

- Context
- What went wrong
- Root cause
- User correction
- Future retrieval triggers
- Required next behavior
- Verification hook
