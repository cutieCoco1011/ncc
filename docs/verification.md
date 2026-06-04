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

## Real Provider Notes

Real providers are opt-in and are not required by the default suite. Configure them only in local environment files:

- `NCC_LLM_PROVIDER=openai` with `OPENAI_API_KEY`;
- `NCC_LLM_PROVIDER=openrouter` with `OPENROUTER_API_KEY`;
- `NCC_IMAGE_PROVIDER=novelai` with `NOVELAI_API_TOKEN`;
- `NCC_TAG_PROVIDER=local` or `mock`.

If a real provider credential is missing, the adapter reports `not_configured`. The app should continue to support scaffold, mock generation, UI review, candidate selection, lettering, and PNG export without those credentials.

## Secret Safety

Project artifacts are stored under the local project root. Storage rejects writes that include configured provider secret values. `.env*`, `.dryforge/`, generated projects, cache directories, and local exports are ignored by git.
