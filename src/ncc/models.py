from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
from pathlib import PurePosixPath
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def text_hash(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


class NccModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        str_strip_whitespace=True,
        validate_assignment=True,
    )


SAFE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


def validate_safe_id(value: str, field_name: str = "id") -> str:
    if not SAFE_ID_PATTERN.fullmatch(value):
        raise ValueError(f"{field_name} must contain only letters, numbers, underscore, or hyphen")
    return value


def validate_artifact_relative_path(value: str) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or not value.strip():
        raise ValueError("artifact path must be project-relative and cannot contain '..'")
    return value


class ArtifactStatus(str, Enum):
    MISSING = "missing"
    VALID = "valid"
    INVALID = "invalid"


class ProviderKind(str, Enum):
    MOCK = "mock"
    OPENAI = "openai"
    OPENROUTER = "openrouter"
    NOVELAI = "novelai"
    LOCAL = "local"
    NOT_CONFIGURED = "not_configured"


class CandidateState(str, Enum):
    GENERATED = "generated"
    FLAGGED = "flagged"
    REJECTED = "rejected"
    SELECTED = "selected"


class QAStatus(str, Enum):
    PENDING = "pending"
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


class ProjectManifest(NccModel):
    project_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    source_hash: str = Field(min_length=64, max_length=64)
    panel_count: int = Field(default=6, ge=4, le=8)
    artifact_status: dict[str, ArtifactStatus] = Field(default_factory=dict)
    external_disclosures: list[str] = Field(default_factory=list)


class StoryAnalysis(NccModel):
    project_id: str
    source_hash: str = Field(min_length=64, max_length=64)
    summary: str
    event_order: list[str] = Field(min_length=1)
    emotional_progression: list[str] = Field(min_length=1)
    provider: ProviderKind = ProviderKind.MOCK
    provider_metadata: dict[str, Any] = Field(default_factory=dict)


class ReferenceImageMetadata(NccModel):
    path: str | None = None
    note: str | None = None
    provider_metadata: dict[str, Any] = Field(default_factory=dict)


class CharacterProfile(NccModel):
    character_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)
    visual_lock_traits: list[str] = Field(min_length=3)
    allowed_variations: list[str] = Field(default_factory=list)
    forbidden_traits: list[str] = Field(default_factory=list)
    voice_personality_summary: str
    positive_tags: list[str] = Field(default_factory=list)
    negative_tags: list[str] = Field(default_factory=list)
    reference_image_metadata: ReferenceImageMetadata | None = None

    @field_validator("character_id")
    @classmethod
    def validate_character_id(cls, value: str) -> str:
        return validate_safe_id(value, "character_id")

    @model_validator(mode="after")
    def forbidden_traits_do_not_become_positive_tags(self) -> CharacterProfile:
        positives = {tag.lower() for tag in self.positive_tags}
        leaks = [trait for trait in self.forbidden_traits if trait.lower() in positives]
        if leaks:
            raise ValueError(f"forbidden traits cannot be positive tags: {', '.join(leaks)}")
        return self


class CharacterBible(NccModel):
    project_id: str
    source_hash: str = Field(min_length=64, max_length=64)
    characters: list[CharacterProfile] = Field(min_length=1)

    @field_validator("characters")
    @classmethod
    def unique_character_ids(cls, value: list[CharacterProfile]) -> list[CharacterProfile]:
        ids = [character.character_id for character in value]
        if len(ids) != len(set(ids)):
            raise ValueError("character ids must be unique")
        return value


class StoryboardPanel(NccModel):
    panel_id: str = Field(min_length=1)
    order: int = Field(ge=1, le=8)
    beat: str
    camera: str
    composition: str
    visible_characters: list[str] = Field(default_factory=list)
    setting: str
    emotion: str
    draft_dialogue: str = ""
    caption: str = ""

    @field_validator("panel_id")
    @classmethod
    def validate_panel_id(cls, value: str) -> str:
        return validate_safe_id(value, "panel_id")


class Storyboard(NccModel):
    project_id: str
    source_hash: str = Field(min_length=64, max_length=64)
    panels: list[StoryboardPanel] = Field(min_length=4, max_length=8)

    @field_validator("panels")
    @classmethod
    def panel_order_is_unique(cls, value: list[StoryboardPanel]) -> list[StoryboardPanel]:
        orders = [panel.order for panel in value]
        if orders != sorted(orders):
            raise ValueError("storyboard panels must be ordered")
        if len(orders) != len(set(orders)):
            raise ValueError("storyboard panel order must be unique")
        return value


class PanelSpec(NccModel):
    panel_id: str
    order: int = Field(ge=1, le=8)
    beat: str
    camera: str
    composition: str
    visible_character_ids: list[str]
    setting: str
    emotion: str
    dialogue: str = ""
    caption: str = ""
    source_panel_id: str
    status: ArtifactStatus = ArtifactStatus.VALID

    @field_validator("panel_id", "source_panel_id")
    @classmethod
    def validate_panel_ids(cls, value: str) -> str:
        return validate_safe_id(value, "panel_id")


class PanelSpecSet(NccModel):
    project_id: str
    source_hash: str = Field(min_length=64, max_length=64)
    panels: list[PanelSpec] = Field(min_length=4, max_length=8)


class TagCandidate(NccModel):
    tag: str
    source: str
    confidence: float = Field(ge=0, le=1)
    provenance: dict[str, Any] = Field(default_factory=dict)


class PromptIR(NccModel):
    panel_id: str
    base_prompt: list[str]
    character_prompts: dict[str, list[str]]
    global_undesired: list[str]
    character_undesired: dict[str, list[str]]
    tag_candidates: list[TagCandidate]
    priority_metadata: dict[str, Any] = Field(default_factory=dict)
    source_revision: str

    @field_validator("panel_id")
    @classmethod
    def validate_panel_id(cls, value: str) -> str:
        return validate_safe_id(value, "panel_id")

    @model_validator(mode="after")
    def keep_forbidden_out_of_positive_prompt(self) -> PromptIR:
        positive = {token.lower() for token in self.base_prompt}
        for tokens in self.character_prompts.values():
            positive.update(token.lower() for token in tokens)
        forbidden = {token.lower() for token in self.global_undesired}
        for tokens in self.character_undesired.values():
            forbidden.update(token.lower() for token in tokens)
        overlap = sorted(positive & forbidden)
        if overlap:
            raise ValueError(f"undesired prompt tokens cannot also be positive: {', '.join(overlap)}")
        return self


class PromptIRSet(NccModel):
    project_id: str
    prompts: list[PromptIR] = Field(min_length=1)


class NAIPrompt(NccModel):
    panel_id: str
    base_prompt: str
    character_prompts: dict[str, str]
    undesired_prompt: str
    seed: int = Field(ge=0)
    settings: dict[str, Any] = Field(default_factory=dict)
    reference_metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("panel_id")
    @classmethod
    def validate_panel_id(cls, value: str) -> str:
        return validate_safe_id(value, "panel_id")


class NAIPromptSet(NccModel):
    project_id: str
    prompts: list[NAIPrompt] = Field(min_length=1)


class QAFlag(NccModel):
    code: str
    message: str
    severity: Literal["info", "warning", "error"] = "warning"
    provenance: dict[str, Any] = Field(default_factory=dict)


class CandidateImage(NccModel):
    candidate_id: str
    panel_id: str
    image_path: str
    prompt: NAIPrompt
    seed: int = Field(ge=0)
    settings: dict[str, Any] = Field(default_factory=dict)
    provider_metadata: dict[str, Any] = Field(default_factory=dict)
    qa_status: QAStatus = QAStatus.PENDING
    qa_flags: list[QAFlag] = Field(default_factory=list)
    state: CandidateState = CandidateState.GENERATED
    selected: bool = False
    rejected_reason: str | None = None
    source_revision: str

    @field_validator("candidate_id", "panel_id")
    @classmethod
    def validate_candidate_ids(cls, value: str) -> str:
        return validate_safe_id(value, "candidate_id")

    @field_validator("image_path")
    @classmethod
    def validate_image_path(cls, value: str) -> str:
        value = validate_artifact_relative_path(value)
        if not value.startswith("images/"):
            raise ValueError("candidate image path must live under images/")
        return value


class CandidateSet(NccModel):
    project_id: str
    candidates: list[CandidateImage] = Field(default_factory=list)

    def by_panel(self) -> dict[str, list[CandidateImage]]:
        grouped: dict[str, list[CandidateImage]] = {}
        for candidate in self.candidates:
            grouped.setdefault(candidate.panel_id, []).append(candidate)
        return grouped


class LetterBalloon(NccModel):
    balloon_id: str
    panel_id: str
    text: str
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    tail_direction: Literal["left", "right", "up", "down", "none"] = "down"
    kind: Literal["speech", "caption"] = "speech"
    manual_text: bool = False

    @field_validator("balloon_id", "panel_id")
    @classmethod
    def validate_balloon_ids(cls, value: str) -> str:
        return validate_safe_id(value, "balloon_id")


class LetteringLayout(NccModel):
    project_id: str
    panel_width: int = Field(default=1080, ge=1080)
    balloons: list[LetterBalloon] = Field(default_factory=list)
    source_selection_hash: str
    status: ArtifactStatus = ArtifactStatus.VALID


class ExportRecord(NccModel):
    project_id: str
    export_path: str
    width: int = Field(ge=1080)
    height: int = Field(gt=0)
    source_selection_hash: str
    created_at: datetime = Field(default_factory=utc_now)
    status: ArtifactStatus = ArtifactStatus.VALID

    @field_validator("export_path")
    @classmethod
    def validate_export_path(cls, value: str) -> str:
        value = validate_artifact_relative_path(value)
        if not value.startswith("exports/"):
            raise ValueError("export path must live under exports/")
        return value

    @model_validator(mode="after")
    def export_is_vertical(self) -> ExportRecord:
        if self.height <= self.width:
            raise ValueError("webtoon export must be vertical")
        return self


class StageRun(NccModel):
    stage: str
    status: Literal["pending", "running", "done", "failed"]
    message: str = ""
    diagnostics: list[str] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=utc_now)
    finished_at: datetime | None = None


class InvalidationEvent(NccModel):
    edit_type: str
    edited_ids: list[str] = Field(default_factory=list)
    invalid_artifacts: list[str]
    reason: str
    created_at: datetime = Field(default_factory=utc_now)
