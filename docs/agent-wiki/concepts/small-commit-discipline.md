# Small Commit Discipline

## Operating Rule

Commit work in small logical units without waiting for an explicit user reminder. A large working tree should be split before commit/push whenever the split can be made without creating misleading or broken history.

## Commit Shape

Prefer commits that each answer one review question:

- UI/workflow copy and frontend tests;
- backend behavior and its direct tests;
- provider/env/config changes and diagnostics;
- documentation, verification notes, and agent-wiki memory;
- purely mechanical formatting only when needed.

Avoid one commit that mixes unrelated product UI, backend provider behavior, tests, and process documentation.

## Required Behavior

Before committing a multi-file change:

1. Inspect `git status --short --branch` and the diff names.
2. Group files by user-visible behavior or verification boundary.
3. Commit each group separately with a concrete message.
4. Run or cite the relevant verification before pushing.
5. Do not include ignored local secrets such as `.env.local`.

## Retrieval Triggers

- "commit"
- "push"
- "커밋 범위"
- "작은단위"
- "너무 큰 커밋"
- "원래 이렇게 계획"
