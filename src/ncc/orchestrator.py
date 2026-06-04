from __future__ import annotations

from pathlib import Path
import os

from .exporter import build_default_lettering, export_vertical_png, selection_revision_hash
from .images import CandidateGenerationService, MockImageBackend, NovelAIImageBackend
from .models import (
    ArtifactStatus,
    CandidateSet,
    CharacterBible,
    ExportRecord,
    LetteringLayout,
    NAIPromptSet,
    PanelSpecSet,
    ProjectManifest,
    ProviderKind,
    PromptIRSet,
    StageRun,
    StoryAnalysis,
    Storyboard,
    utc_now,
)
from .prompts import PromptCompiler
from .qa import CandidateQAService, SelectionService
from .settings import AppSettings
from .storage import ProjectContext, ProjectStorage
from .story_pipeline import MockLLMStoryProvider, panel_specs_from_storyboard


class InvalidArtifactError(RuntimeError):
    pass


class NccOrchestrator:
    def __init__(self, projects_root: Path | str | None = None, settings: AppSettings | None = None) -> None:
        self.settings = settings or AppSettings.from_env()
        self.storage = ProjectStorage(Path(projects_root or self.settings.projects_dir), self.settings)
        self.stage_runs: list[StageRun] = []

    def create_project(self, title: str, source_text: str, panel_count: int = 6) -> ProjectContext:
        return self.storage.create_project(title, source_text, panel_count=panel_count)

    def open_project(self, project_id: str) -> ProjectContext:
        return self.storage.open_project(project_id)

    def provider_status(self) -> dict[str, dict[str, str | bool | None]]:
        return self.settings.public_provider_status()

    def require_valid(self, manifest: ProjectManifest, artifact_name: str) -> None:
        status = manifest.artifact_status.get(artifact_name, ArtifactStatus.MISSING)
        if status != ArtifactStatus.VALID:
            raise InvalidArtifactError(f"{artifact_name} is {status.value}; refresh it before continuing")

    def begin_stage(self, stage: str) -> StageRun:
        run = StageRun(stage=stage, status="running")
        self.stage_runs.append(run)
        return run

    def finish_stage(
        self,
        run: StageRun,
        status: str = "done",
        message: str = "",
        diagnostics: list[str] | None = None,
    ) -> StageRun:
        completed = run.model_copy(
            update={
                "status": status,
                "message": message,
                "diagnostics": diagnostics or [],
                "finished_at": utc_now(),
            }
        )
        self.stage_runs[-1] = completed
        return completed

    def run_story_stage(self, project_id: str) -> StageRun:
        run = self.begin_stage("story")
        context = self.open_project(project_id)
        source_text = self.storage.read_source(context.project_dir)
        bundle = MockLLMStoryProvider().analyze(project_id, source_text, context.manifest.panel_count)
        self.storage.write_model(context.project_dir, "analysis", bundle.analysis)
        self.storage.write_model(context.project_dir, "characters", bundle.characters)
        self.storage.write_model(context.project_dir, "storyboard", bundle.storyboard)
        self.storage.write_model(context.project_dir, "panel_specs", bundle.panel_specs)
        self.storage.mark_invalid(
            context.project_dir,
            ["prompt_ir", "nai_prompts", "image_candidates", "lettering", "export"],
        )
        return self.finish_stage(run, message="analysis, characters, storyboard, and panel specs generated")

    def run_prompt_stage(self, project_id: str) -> StageRun:
        run = self.begin_stage("prompts")
        context = self.open_project(project_id)
        self.require_valid(context.manifest, "panel_specs")
        characters = self.storage.read_model(context.project_dir, "characters", CharacterBible)
        panel_specs = self.storage.read_model(context.project_dir, "panel_specs", PanelSpecSet)
        compiler = PromptCompiler()
        prompt_ir = compiler.build_prompt_ir(project_id, panel_specs, characters)
        nai_prompts = compiler.compile_nai_prompts(project_id, prompt_ir)
        self.storage.write_model(context.project_dir, "prompt_ir", prompt_ir)
        self.storage.write_model(context.project_dir, "nai_prompts", nai_prompts)
        self.storage.mark_invalid(context.project_dir, ["image_candidates", "lettering", "export"])
        return self.finish_stage(run, message="prompt IR and NAI prompts generated")

    def run_panel_specs_stage(self, project_id: str) -> StageRun:
        run = self.begin_stage("panel_specs")
        context = self.open_project(project_id)
        storyboard = self.storage.read_model(context.project_dir, "storyboard", Storyboard)
        panel_specs = panel_specs_from_storyboard(project_id, context.manifest.source_hash, storyboard)
        self.storage.write_model(context.project_dir, "panel_specs", panel_specs)
        self.storage.mark_invalid(
            context.project_dir,
            ["prompt_ir", "nai_prompts", "image_candidates", "lettering", "export"],
        )
        return self.finish_stage(run, message="panel specs refreshed from edited storyboard")

    def run_image_stage(self, project_id: str) -> StageRun:
        run = self.begin_stage("images")
        context = self.open_project(project_id)
        self.require_valid(context.manifest, "nai_prompts")
        if self.settings.image.provider == ProviderKind.NOT_CONFIGURED:
            raise ValueError("image provider is not_configured; set NCC_IMAGE_PROVIDER=mock or configure NOVELAI_API_TOKEN")
        nai_prompts = self.storage.read_model(context.project_dir, "nai_prompts", NAIPromptSet)
        candidates = CandidateGenerationService(self._image_backend()).generate_candidates(
            project_id,
            context.project_dir,
            nai_prompts,
        )
        self.storage.write_model(context.project_dir, "image_candidates", candidates)
        self.storage.mark_invalid(context.project_dir, ["lettering", "export"])
        return self.finish_stage(run, message=f"{len(candidates.candidates)} image candidates generated")

    def _image_backend(self) -> MockImageBackend | NovelAIImageBackend:
        if self.settings.image.provider == ProviderKind.MOCK:
            return MockImageBackend()
        if self.settings.image.provider == ProviderKind.NOVELAI:
            return NovelAIImageBackend(api_token=os.environ.get("NOVELAI_API_TOKEN", ""))
        raise ValueError(f"unsupported image provider: {self.settings.image.provider.value}")

    def run_qa_stage(self, project_id: str) -> StageRun:
        run = self.begin_stage("qa")
        context = self.open_project(project_id)
        self.require_valid(context.manifest, "image_candidates")
        characters = self.storage.read_model(context.project_dir, "characters", CharacterBible)
        candidates = self.storage.read_model(context.project_dir, "image_candidates", CandidateSet)
        evaluated = CandidateQAService().evaluate(candidates, characters)
        self.storage.write_model(context.project_dir, "image_candidates", evaluated)
        return self.finish_stage(run, message="candidate QA and provenance updated")

    def select_first_candidates(self, project_id: str) -> StageRun:
        run = self.begin_stage("selection")
        context = self.open_project(project_id)
        self.require_valid(context.manifest, "image_candidates")
        candidates = self.storage.read_model(context.project_dir, "image_candidates", CandidateSet)
        selected, events = SelectionService().select_first_per_panel(candidates)
        self.storage.write_model(context.project_dir, "image_candidates", selected)
        for event in events:
            self.storage.mark_invalid(context.project_dir, event.invalid_artifacts)
        return self.finish_stage(run, message="one candidate selected for each panel")

    def run_lettering_stage(self, project_id: str) -> StageRun:
        run = self.begin_stage("lettering")
        context = self.open_project(project_id)
        self.require_valid(context.manifest, "image_candidates")
        storyboard = self.storage.read_model(context.project_dir, "storyboard", Storyboard)
        candidates = self.storage.read_model(context.project_dir, "image_candidates", CandidateSet)
        lettering_path = self.storage.artifact_path(context.project_dir, "lettering")
        if lettering_path.exists():
            existing = self.storage.read_model(context.project_dir, "lettering", LetteringLayout)
            fresh = build_default_lettering(project_id, storyboard, candidates)
            fresh_by_id = {balloon.balloon_id: balloon for balloon in fresh.balloons}
            balloons = [
                fresh_by_id[balloon.balloon_id].model_copy(
                    update={
                        "x": balloon.x,
                        "y": balloon.y,
                        "width": balloon.width,
                        "height": balloon.height,
                        "tail_direction": balloon.tail_direction,
                    }
                )
                for balloon in existing.balloons
                if balloon.balloon_id in fresh_by_id
            ]
            existing_ids = {balloon.balloon_id for balloon in existing.balloons}
            balloons.extend(balloon for balloon in fresh.balloons if balloon.balloon_id not in existing_ids)
            lettering = existing.model_copy(
                update={
                    "balloons": balloons,
                    "source_selection_hash": selection_revision_hash(candidates),
                }
            )
        else:
            lettering = build_default_lettering(project_id, storyboard, candidates)
        self.storage.write_model(context.project_dir, "lettering", lettering)
        return self.finish_stage(run, message="Korean speech balloons and captions prepared")

    def run_export_stage(self, project_id: str) -> StageRun:
        run = self.begin_stage("export")
        context = self.open_project(project_id)
        self.require_valid(context.manifest, "image_candidates")
        self.require_valid(context.manifest, "lettering")
        storyboard = self.storage.read_model(context.project_dir, "storyboard", Storyboard)
        candidates = self.storage.read_model(context.project_dir, "image_candidates", CandidateSet)
        lettering = self.storage.read_model(context.project_dir, "lettering", LetteringLayout)
        export = export_vertical_png(project_id, context.project_dir, storyboard, candidates, lettering)
        self.storage.write_model(context.project_dir, "export", export)
        return self.finish_stage(run, message=f"exported {export.width}x{export.height} PNG")

    def run_mock_gold_path(
        self,
        title: str,
        source_text: str,
        panel_count: int = 6,
    ) -> dict[str, object]:
        self.stage_runs = []
        context = self.create_project(title, source_text, panel_count)
        self.run_story_stage(context.project_id)
        self.run_prompt_stage(context.project_id)
        self.run_image_stage(context.project_id)
        self.run_qa_stage(context.project_id)
        self.select_first_candidates(context.project_id)
        self.run_lettering_stage(context.project_id)
        self.run_export_stage(context.project_id)
        final_context = self.open_project(context.project_id)
        analysis = self.storage.read_model(final_context.project_dir, "analysis", StoryAnalysis)
        prompt_ir = self.storage.read_model(final_context.project_dir, "prompt_ir", PromptIRSet)
        candidates = self.storage.read_model(final_context.project_dir, "image_candidates", CandidateSet)
        export = self.storage.read_model(final_context.project_dir, "export", ExportRecord)
        return {
            "project_id": final_context.project_id,
            "project_dir": str(final_context.project_dir),
            "panel_count": final_context.manifest.panel_count,
            "event_count": len(analysis.event_order),
            "prompt_count": len(prompt_ir.prompts),
            "candidate_count": len(candidates.candidates),
            "selected_count": sum(1 for candidate in candidates.candidates if candidate.selected),
            "image_provider": self.settings.image.provider.value,
            "export_path": str(final_context.project_dir / export.export_path),
            "export_width": export.width,
            "export_height": export.height,
            "stage_runs": [run.model_dump(mode="json") for run in self.stage_runs],
        }
