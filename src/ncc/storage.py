from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar
from uuid import uuid4

from pydantic import BaseModel

from .artifacts import dump_model, load_model
from .models import ArtifactStatus, ProjectManifest, text_hash, utc_now
from .settings import AppSettings

ModelT = TypeVar("ModelT", bound=BaseModel)


ARTIFACT_FILES = {
    "project": "project.yaml",
    "source": "source.md",
    "analysis": "analysis.json",
    "characters": "characters.yaml",
    "storyboard": "storyboard.yaml",
    "panel_specs": "panel_specs.yaml",
    "prompt_ir": "prompt_ir.yaml",
    "nai_prompts": "nai_prompts.yaml",
    "image_candidates": "images/candidates.yaml",
    "candidates": "images/candidates.yaml",
    "lettering": "lettering/layout.yaml",
    "export": "exports/export.yaml",
}


@dataclass(frozen=True)
class ProjectContext:
    project_dir: Path
    manifest: ProjectManifest

    @property
    def project_id(self) -> str:
        return self.manifest.project_id


class ProjectStorage:
    def __init__(self, root: Path, settings: AppSettings | None = None) -> None:
        self.root = Path(root)
        self.settings = settings or AppSettings.from_env()
        self.root.mkdir(parents=True, exist_ok=True)

    def create_project(
        self,
        title: str,
        source_text: str,
        panel_count: int = 6,
        project_id: str | None = None,
    ) -> ProjectContext:
        source_hash = text_hash(source_text)
        safe_id = _validate_project_id(project_id) if project_id else _project_id(title, source_hash)
        project_dir = safe_project_path(self.root, safe_id)
        project_dir.mkdir(parents=True, exist_ok=True)
        for dirname in ("refs", "lettering", "exports"):
            (project_dir / dirname).mkdir(exist_ok=True)

        manifest = ProjectManifest(
            project_id=safe_id,
            title=title,
            source_hash=source_hash,
            panel_count=panel_count,
            artifact_status={
                "analysis": ArtifactStatus.MISSING,
                "characters": ArtifactStatus.MISSING,
                "storyboard": ArtifactStatus.MISSING,
                "panel_specs": ArtifactStatus.MISSING,
                "prompt_ir": ArtifactStatus.MISSING,
                "nai_prompts": ArtifactStatus.MISSING,
                "image_candidates": ArtifactStatus.MISSING,
                "lettering": ArtifactStatus.MISSING,
                "export": ArtifactStatus.MISSING,
            },
            external_disclosures=self._current_external_disclosures(),
        )
        self.write_source(project_dir, source_text)
        self.write_model(project_dir, "project", manifest)
        return ProjectContext(project_dir=project_dir, manifest=manifest)

    def open_project(self, project_id: str) -> ProjectContext:
        safe_id = _validate_project_id(project_id)
        project_dir = safe_project_path(self.root, safe_id)
        if not project_dir.exists():
            raise FileNotFoundError(f"project {project_id} not found")
        manifest = self.read_model(project_dir, "project", ProjectManifest)
        return ProjectContext(project_dir=project_dir, manifest=manifest)

    def artifact_path(self, project_dir: Path, artifact_name: str) -> Path:
        try:
            relative = ARTIFACT_FILES[artifact_name]
        except KeyError as exc:
            raise ValueError(f"unknown artifact: {artifact_name}") from exc
        return project_dir / relative

    def write_source(self, project_dir: Path, source_text: str) -> None:
        _assert_no_secret_values(source_text, self.settings.secret_values)
        self.artifact_path(project_dir, "source").write_text(source_text, encoding="utf-8")

    def read_source(self, project_dir: Path) -> str:
        return self.artifact_path(project_dir, "source").read_text(encoding="utf-8")

    def write_model(self, project_dir: Path, artifact_name: str, model: BaseModel) -> None:
        path = self.artifact_path(project_dir, artifact_name)
        serialized = str(model.model_dump(mode="json"))
        _assert_no_secret_values(serialized, self.settings.secret_values)
        dump_model(model, path)
        if artifact_name != "project":
            self._mark_status(project_dir, artifact_name, ArtifactStatus.VALID)

    def read_model(self, project_dir: Path, artifact_name: str, model_type: type[ModelT]) -> ModelT:
        return load_model(self.artifact_path(project_dir, artifact_name), model_type)

    def write_bytes(self, project_dir: Path, relative_path: str, data: bytes) -> Path:
        path = safe_project_path(project_dir, relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def list_projects(self) -> list[ProjectContext]:
        contexts = []
        for project_yaml in sorted(self.root.glob("*/project.yaml")):
            contexts.append(self.open_project(project_yaml.parent.name))
        return contexts

    def mark_invalid(self, project_dir: Path, artifact_names: list[str]) -> ProjectManifest:
        manifest = self.read_model(project_dir, "project", ProjectManifest)
        for artifact in artifact_names:
            manifest.artifact_status[artifact] = ArtifactStatus.INVALID
        manifest.external_disclosures = self._current_external_disclosures()
        manifest.updated_at = utc_now()
        dump_model(manifest, self.artifact_path(project_dir, "project"))
        return manifest

    def _mark_status(self, project_dir: Path, artifact_name: str, status: ArtifactStatus) -> None:
        manifest_path = self.artifact_path(project_dir, "project")
        if not manifest_path.exists():
            return
        manifest = load_model(manifest_path, ProjectManifest)
        manifest.artifact_status[artifact_name] = status
        manifest.external_disclosures = self._current_external_disclosures()
        manifest.updated_at = utc_now()
        dump_model(manifest, manifest_path)

    def _current_external_disclosures(self) -> list[str]:
        return [
            self.settings.llm.disclosure,
            self.settings.tag.disclosure,
            self.settings.image.disclosure,
        ]


def _project_id(title: str, source_hash: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9가-힣]+", "-", title).strip("-").lower()
    slug = slug or "project"
    return f"{slug}-{source_hash[:8]}-{uuid4().hex[:6]}"


def _validate_project_id(project_id: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9가-힣_-]+", project_id):
        raise ValueError("project_id must not contain path separators or traversal")
    return project_id


def _assert_no_secret_values(serialized: str, secret_values: tuple[str, ...]) -> None:
    for secret in secret_values:
        if secret and secret in serialized:
            raise ValueError("refusing to write provider secret into project artifact")


def safe_project_path(project_dir: Path, relative_path: str) -> Path:
    relative = Path(relative_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("path must stay inside the project directory")
    root = project_dir.resolve()
    path = (project_dir / relative).resolve()
    if path != root and root not in path.parents:
        raise ValueError("path must stay inside the project directory")
    return path
