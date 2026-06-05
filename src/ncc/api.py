from __future__ import annotations

from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from .fixtures import DEFAULT_PROJECT_TITLE, GOLD_PATH_KOREAN_SOURCE
from .invalidation import build_invalidation_event
from .exporter import selection_revision_hash
from .models import (
    CandidateSet,
    CharacterBible,
    ExportRecord,
    LetteringLayout,
    NAIPromptSet,
    PanelSpecSet,
    PromptIRSet,
    ProjectManifest,
    StoryAnalysis,
    Storyboard,
    validate_artifact_relative_path,
)
from .orchestrator import InvalidArtifactError, NccOrchestrator
from .qa import SelectionService
from .storage import safe_project_path


class CreateProjectRequest(BaseModel):
    title: str = Field(default=DEFAULT_PROJECT_TITLE, min_length=1)
    source_text: str = Field(default=GOLD_PATH_KOREAN_SOURCE, min_length=1)
    panel_count: int = Field(default=6, ge=4, le=8)


class GoldPathRequest(BaseModel):
    title: str = Field(default=DEFAULT_PROJECT_TITLE, min_length=1)
    source_text: str = Field(default=GOLD_PATH_KOREAN_SOURCE, min_length=1)
    panel_count: int = Field(default=6, ge=4, le=8)


class CharacterPatch(BaseModel):
    aliases: list[str] | None = None
    visual_lock_traits: list[str] | None = None
    allowed_variations: list[str] | None = None
    forbidden_traits: list[str] | None = None
    voice_personality_summary: str | None = None
    positive_tags: list[str] | None = None
    negative_tags: list[str] | None = None


class StoryboardPanelPatch(BaseModel):
    beat: str | None = None
    camera: str | None = None
    composition: str | None = None
    visible_characters: list[str] | None = None
    setting: str | None = None
    emotion: str | None = None
    draft_dialogue: str | None = None
    caption: str | None = None


class RejectCandidateRequest(BaseModel):
    reason: str = Field(min_length=1)


class LetteringPatch(BaseModel):
    text: str | None = None
    x: int | None = Field(default=None, ge=0)
    y: int | None = Field(default=None, ge=0)
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    tail_direction: str | None = None


def create_app(projects_root: Path | str | None = None) -> FastAPI:
    app = FastAPI(title="ncc local API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:3000", "http://localhost:3000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    orchestrator = NccOrchestrator(projects_root)

    @app.exception_handler(InvalidArtifactError)
    async def invalid_artifact_handler(_request, exc: InvalidArtifactError) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={"status": "failed", "diagnostics": [str(exc)]},
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(_request, exc: ValueError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"status": "failed", "diagnostics": [str(exc)]},
        )

    @app.exception_handler(FileNotFoundError)
    async def file_not_found_handler(_request, exc: FileNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"status": "failed", "diagnostics": [str(exc)]},
        )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/providers")
    def providers() -> dict[str, dict[str, str | bool | None]]:
        return orchestrator.provider_status()

    @app.post("/projects")
    def create_project(payload: CreateProjectRequest) -> dict[str, Any]:
        context = orchestrator.create_project(payload.title, payload.source_text, payload.panel_count)
        return {
            "project_id": context.project_id,
            "project_dir": str(context.project_dir),
            "artifact_status": {
                name: status.value for name, status in context.manifest.artifact_status.items()
            },
        }

    @app.get("/projects")
    def list_projects() -> list[dict[str, Any]]:
        return [
            {
                "project_id": context.project_id,
                "title": context.manifest.title,
                "project_dir": str(context.project_dir),
                "created_at": context.manifest.created_at.isoformat(),
                "updated_at": context.manifest.updated_at.isoformat(),
            }
            for context in orchestrator.storage.list_projects()
        ]

    @app.get("/projects/{project_id}/artifacts")
    def read_artifacts(project_id: str) -> dict[str, Any]:
        context = orchestrator.open_project(project_id)
        return _artifact_snapshot(orchestrator, context.project_dir)

    @app.patch("/projects/{project_id}/characters/{character_id}")
    def patch_character(project_id: str, character_id: str, patch: CharacterPatch) -> dict[str, Any]:
        context = orchestrator.open_project(project_id)
        bible = orchestrator.storage.read_model(context.project_dir, "characters", CharacterBible)
        updates = patch.model_dump(exclude_none=True)
        changed = False
        characters = []
        for character in bible.characters:
            if character.character_id == character_id:
                changed = True
                characters.append(character.__class__.model_validate({**character.model_dump(mode="json"), **updates}))
            else:
                characters.append(character)
        if not changed:
            raise HTTPException(status_code=404, detail=f"character {character_id} not found")
        updated = bible.model_copy(update={"characters": characters})
        orchestrator.storage.write_model(context.project_dir, "characters", updated)
        event = build_invalidation_event("character_settings", [character_id])
        manifest = orchestrator.storage.mark_invalid(context.project_dir, event.invalid_artifacts)
        return {"characters": updated.model_dump(mode="json"), "invalidation": event.model_dump(mode="json"), "manifest": manifest.model_dump(mode="json")}

    @app.patch("/projects/{project_id}/storyboard/{panel_id}")
    def patch_storyboard_panel(project_id: str, panel_id: str, patch: StoryboardPanelPatch) -> dict[str, Any]:
        context = orchestrator.open_project(project_id)
        storyboard = orchestrator.storage.read_model(context.project_dir, "storyboard", Storyboard)
        updates = patch.model_dump(exclude_none=True)
        changed = False
        panels = []
        for panel in storyboard.panels:
            if panel.panel_id == panel_id:
                changed = True
                panels.append(panel.__class__.model_validate({**panel.model_dump(mode="json"), **updates}))
            else:
                panels.append(panel)
        if not changed:
            raise HTTPException(status_code=404, detail=f"panel {panel_id} not found")
        updated = storyboard.model_copy(update={"panels": panels})
        orchestrator.storage.write_model(context.project_dir, "storyboard", updated)
        event = build_invalidation_event("storyboard", [panel_id])
        manifest = orchestrator.storage.mark_invalid(context.project_dir, event.invalid_artifacts)
        return {"storyboard": updated.model_dump(mode="json"), "invalidation": event.model_dump(mode="json"), "manifest": manifest.model_dump(mode="json")}

    @app.post("/projects/{project_id}/stages/story")
    def run_story(project_id: str) -> dict[str, Any]:
        return orchestrator.run_story_stage(project_id).model_dump(mode="json")

    @app.post("/projects/{project_id}/stages/prompts")
    def run_prompts(project_id: str) -> dict[str, Any]:
        return orchestrator.run_prompt_stage(project_id).model_dump(mode="json")

    @app.post("/projects/{project_id}/stages/panel-specs")
    def run_panel_specs(project_id: str) -> dict[str, Any]:
        return orchestrator.run_panel_specs_stage(project_id).model_dump(mode="json")

    @app.post("/projects/{project_id}/stages/images")
    def run_images(project_id: str) -> dict[str, Any]:
        return orchestrator.run_image_stage(project_id).model_dump(mode="json")

    @app.post("/projects/{project_id}/stages/qa")
    def run_qa(project_id: str) -> dict[str, Any]:
        return orchestrator.run_qa_stage(project_id).model_dump(mode="json")

    @app.post("/projects/{project_id}/selection/default")
    def select_defaults(project_id: str) -> dict[str, Any]:
        return orchestrator.select_first_candidates(project_id).model_dump(mode="json")

    @app.post("/projects/{project_id}/candidates/{candidate_id}/select")
    def select_candidate(project_id: str, candidate_id: str) -> dict[str, Any]:
        context = orchestrator.open_project(project_id)
        orchestrator.require_valid(context.manifest, "image_candidates")
        candidates = orchestrator.storage.read_model(context.project_dir, "image_candidates", CandidateSet)
        candidate = next((item for item in candidates.candidates if item.candidate_id == candidate_id), None)
        if candidate is None:
            raise HTTPException(status_code=404, detail=f"candidate {candidate_id} not found")
        updated, event = SelectionService().select_candidate(candidates, candidate.panel_id, candidate_id)
        orchestrator.storage.write_model(context.project_dir, "image_candidates", updated)
        manifest = orchestrator.storage.mark_invalid(context.project_dir, event.invalid_artifacts)
        return {"image_candidates": updated.model_dump(mode="json"), "invalidation": event.model_dump(mode="json"), "manifest": manifest.model_dump(mode="json")}

    @app.post("/projects/{project_id}/candidates/{candidate_id}/reject")
    def reject_candidate(project_id: str, candidate_id: str, payload: RejectCandidateRequest) -> dict[str, Any]:
        context = orchestrator.open_project(project_id)
        orchestrator.require_valid(context.manifest, "image_candidates")
        candidates = orchestrator.storage.read_model(context.project_dir, "image_candidates", CandidateSet)
        was_selected = any(
            candidate.candidate_id == candidate_id and candidate.selected
            for candidate in candidates.candidates
        )
        updated = SelectionService().reject_candidate(candidates, candidate_id, payload.reason)
        orchestrator.storage.write_model(context.project_dir, "image_candidates", updated)
        response: dict[str, Any] = {"image_candidates": updated.model_dump(mode="json")}
        if was_selected:
            event = build_invalidation_event("candidate_selection", [candidate_id])
            manifest = orchestrator.storage.mark_invalid(context.project_dir, event.invalid_artifacts)
            response["invalidation"] = event.model_dump(mode="json")
            response["manifest"] = manifest.model_dump(mode="json")
        return response

    @app.post("/projects/{project_id}/stages/lettering")
    def run_lettering(project_id: str) -> dict[str, Any]:
        return orchestrator.run_lettering_stage(project_id).model_dump(mode="json")

    @app.patch("/projects/{project_id}/lettering/{balloon_id}")
    def patch_lettering(project_id: str, balloon_id: str, patch: LetteringPatch) -> dict[str, Any]:
        context = orchestrator.open_project(project_id)
        lettering = orchestrator.storage.read_model(context.project_dir, "lettering", LetteringLayout)
        updates = patch.model_dump(exclude_none=True)
        if "text" in updates:
            updates["manual_text"] = True
        changed = False
        balloons = []
        for balloon in lettering.balloons:
            if balloon.balloon_id == balloon_id:
                changed = True
                balloons.append(balloon.__class__.model_validate({**balloon.model_dump(mode="json"), **updates}))
            else:
                balloons.append(balloon)
        if not changed:
            raise HTTPException(status_code=404, detail=f"balloon {balloon_id} not found")
        updated = lettering.model_copy(update={"balloons": balloons})
        orchestrator.storage.write_model(context.project_dir, "lettering", updated)
        event = build_invalidation_event("lettering", [balloon_id])
        manifest = orchestrator.storage.mark_invalid(context.project_dir, event.invalid_artifacts)
        return {"lettering": updated.model_dump(mode="json"), "invalidation": event.model_dump(mode="json"), "manifest": manifest.model_dump(mode="json")}

    @app.post("/projects/{project_id}/stages/export")
    def run_export(project_id: str) -> dict[str, Any]:
        return orchestrator.run_export_stage(project_id).model_dump(mode="json")

    @app.get("/projects/{project_id}/files/{relative_path:path}")
    def read_project_file(project_id: str, relative_path: str) -> FileResponse:
        context = orchestrator.open_project(project_id)
        validate_artifact_relative_path(relative_path)
        if relative_path.startswith("exports/"):
            orchestrator.require_valid(context.manifest, "export")
            orchestrator.require_valid(context.manifest, "image_candidates")
            orchestrator.require_valid(context.manifest, "lettering")
            candidates = orchestrator.storage.read_model(context.project_dir, "image_candidates", CandidateSet)
            export = orchestrator.storage.read_model(context.project_dir, "export", ExportRecord)
            if relative_path != export.export_path:
                raise InvalidArtifactError("requested export is not the current export artifact")
            if export.source_selection_hash != selection_revision_hash(candidates):
                raise InvalidArtifactError("export is stale; refresh lettering and export before download")
        path = safe_project_path(context.project_dir, relative_path)
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"file {relative_path} not found")
        return FileResponse(path)

    @app.get("/projects/{project_id}/exports/latest")
    def read_latest_export(project_id: str) -> FileResponse:
        context = orchestrator.open_project(project_id)
        orchestrator.require_valid(context.manifest, "export")
        orchestrator.require_valid(context.manifest, "image_candidates")
        orchestrator.require_valid(context.manifest, "lettering")
        candidates = orchestrator.storage.read_model(context.project_dir, "image_candidates", CandidateSet)
        export = orchestrator.storage.read_model(context.project_dir, "export", ExportRecord)
        if export.source_selection_hash != selection_revision_hash(candidates):
            raise InvalidArtifactError("export is stale; refresh lettering and export before download")
        path = safe_project_path(context.project_dir, export.export_path)
        if not path.exists():
            raise HTTPException(status_code=404, detail="export file not found")
        return FileResponse(path, media_type="image/png", filename=Path(export.export_path).name)

    @app.post("/gold-path")
    def run_gold_path(payload: GoldPathRequest | None = None) -> dict[str, Any]:
        request = payload or GoldPathRequest()
        return orchestrator.run_mock_gold_path(request.title, request.source_text, request.panel_count)

    app.state.orchestrator = orchestrator
    return app


app = create_app()


def run() -> None:
    uvicorn.run("ncc.api:app", host="127.0.0.1", port=8000, reload=False)


def _artifact_snapshot(orchestrator: NccOrchestrator, project_dir: Path) -> dict[str, Any]:
    specs: list[tuple[str, type]] = [
        ("project", ProjectManifest),
        ("analysis", StoryAnalysis),
        ("characters", CharacterBible),
        ("storyboard", Storyboard),
        ("panel_specs", PanelSpecSet),
        ("prompt_ir", PromptIRSet),
        ("nai_prompts", NAIPromptSet),
        ("image_candidates", CandidateSet),
        ("lettering", LetteringLayout),
        ("export", ExportRecord),
    ]
    snapshot: dict[str, Any] = {"source": orchestrator.storage.read_source(project_dir)}
    for artifact_name, model_type in specs:
        path = orchestrator.storage.artifact_path(project_dir, artifact_name)
        if path.exists():
            snapshot[artifact_name] = orchestrator.storage.read_model(
                project_dir, artifact_name, model_type
            ).model_dump(mode="json")
    return snapshot
