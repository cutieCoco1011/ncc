from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from .fixtures import MULTI_SOURCE_KOREAN_FIXTURES
from .images import CandidateGenerationService
from .models import NAIPromptSet
from .orchestrator import NccOrchestrator


def main() -> None:
    args = _parser().parse_args()
    _load_env_file(Path(args.env_file))
    if os.environ.get("NCC_IMAGE_PROVIDER", "").lower() != "novelai":
        print(json.dumps({"status": "skipped", "reason": "NCC_IMAGE_PROVIDER is not novelai"}, ensure_ascii=False))
        return
    if not os.environ.get("NOVELAI_API_TOKEN"):
        print(json.dumps({"status": "skipped", "reason": "NOVELAI_API_TOKEN is missing"}, ensure_ascii=False))
        return

    title, source = MULTI_SOURCE_KOREAN_FIXTURES[args.source_index]
    orchestrator = NccOrchestrator(args.projects_dir)
    if args.full_demo:
        result = orchestrator.run_mock_gold_path(title, source, panel_count=6)
        result["status"] = "passed"
        result["mode"] = "full-demo"
        print(json.dumps(_redacted_result(result), ensure_ascii=False, indent=2))
        return

    context = orchestrator.create_project(title, source, panel_count=6)
    orchestrator.run_story_stage(context.project_id)
    orchestrator.run_prompt_stage(context.project_id)
    project = orchestrator.open_project(context.project_id)
    prompts = orchestrator.storage.read_model(project.project_dir, "nai_prompts", NAIPromptSet)
    subset = NAIPromptSet(project_id=project.project_id, prompts=prompts.prompts[: args.panel_limit])
    candidates = CandidateGenerationService(orchestrator._image_backend()).generate_candidates(
        project.project_id,
        project.project_dir,
        subset,
        candidates_per_panel=args.candidates_per_panel,
    )
    orchestrator.storage.write_model(project.project_dir, "image_candidates", candidates)
    print(
        json.dumps(
            {
                "status": "passed",
                "mode": "minimal-smoke",
                "project_id": project.project_id,
                "project_dir": str(project.project_dir),
                "candidate_count": len(candidates.candidates),
                "provider": candidates.candidates[0].provider_metadata.get("provider"),
                "model": candidates.candidates[0].provider_metadata.get("model"),
                "image_paths": [candidate.image_path for candidate in candidates.candidates],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Opt-in NovelAI image provider smoke test.")
    parser.add_argument("--env-file", default=".env.local", help="Local env file to load without printing secrets.")
    parser.add_argument("--projects-dir", default=None, help="Override NCC_PROJECTS_DIR for smoke artifacts.")
    parser.add_argument("--source-index", type=int, default=0, choices=range(len(MULTI_SOURCE_KOREAN_FIXTURES)))
    parser.add_argument("--panel-limit", type=int, default=1, choices=range(1, 7))
    parser.add_argument("--candidates-per-panel", type=int, default=1, choices=range(1, 4))
    parser.add_argument("--full-demo", action="store_true", help="Generate 6 panels x 3 candidates and export PNG.")
    return parser


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _redacted_result(result: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in result.items() if "token" not in key.lower() and "key" not in key.lower()}


if __name__ == "__main__":
    main()
