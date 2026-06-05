# Broad Solution Search

## Operating Rule

For non-trivial problems, do not jump from the observed local symptom directly to a local patch. First widen the search space.

This applies especially when the task involves:

- model or provider choice;
- prompt quality;
- data extraction or normalization;
- multilingual behavior;
- architecture;
- product workflow quality;
- anything the user will validate manually against an external system.

## Search Order

Before implementing, check enough of these to avoid tunnel vision:

1. Local code and tests: what exactly is broken or missing?
2. Official docs or model cards: what are the intended contracts and constraints?
3. Existing open-source implementations: has someone already built this workflow?
4. Model/data hubs: Hugging Face models, datasets, benchmarks, or tag vocabularies.
5. Public technical discussion: issues, PRs, blog posts, forum threads, or community reports.
6. Comparable product behavior: how do adjacent tools solve the same user workflow?

The answer may still be a local patch, but it should be chosen after seeing the broader option set.

## Anti-Pattern

Bad:

```text
Observed bug -> inspect nearest function -> patch nearest function -> call it done
```

Better:

```text
Observed problem -> define user outcome -> map solution space -> inspect local code -> compare external options -> choose smallest defensible implementation -> verify
```

## Retrieval Triggers

- "시야가 좁다"
- "더 좋은 방법이 있을 수 있다"
- "이미 있는 모델/라이브러리/오픈소스가 있을 수 있다"
- Hugging Face
- GitHub implementation search
- public discussions or issues
- model selection
- dataset selection
- architecture alternatives

## Verification Hook

When this rule applies, the work summary should include:

- what external/internal options were checked;
- why the chosen approach is better for this repo now;
- what remains uncertain or should be revisited.
