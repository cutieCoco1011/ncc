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
- `NCC_IMAGE_PROVIDER=novelai` with `NOVELAI_API_TOKEN`;
- optional `NOVELAI_IMAGE_ENDPOINT`, `NOVELAI_IMAGE_MODEL`, and `NOVELAI_TIMEOUT_SECONDS`;
- `NCC_TAG_PROVIDER=local` or `mock`.

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

## Secret Safety

Project artifacts are stored under the local project root. Storage rejects writes that include configured provider secret values. `.env*`, `.dryforge/`, generated projects, cache directories, and local exports are ignored by git.
