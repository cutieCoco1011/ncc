from pathlib import Path

import pytest

from ncc.models import StoryAnalysis, text_hash
from ncc.settings import AppSettings
from ncc.storage import ProjectStorage


def test_project_storage_creates_expected_layout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NCC_PROJECTS_DIR", str(tmp_path))
    settings = AppSettings.from_env()
    storage = ProjectStorage(tmp_path, settings)

    context = storage.create_project("테스트 프로젝트", "하린은 빗속에 섰다.", panel_count=6)

    assert (context.project_dir / "project.yaml").exists()
    assert (context.project_dir / "source.md").read_text(encoding="utf-8").startswith("하린")
    assert not (context.project_dir / "images").exists()
    assert (context.project_dir / "lettering").is_dir()
    assert (context.project_dir / "exports").is_dir()
    assert context.manifest.artifact_status["analysis"].value == "missing"
    image_path = storage.write_bytes(context.project_dir, "images/p1_candidate_1.png", b"png")
    assert image_path == context.project_dir / "images" / "p1_candidate_1.png"
    assert (context.project_dir / "images").is_dir()


def test_artifact_write_roundtrip_and_rerun(tmp_path: Path) -> None:
    storage = ProjectStorage(tmp_path)
    context = storage.create_project("demo", "source")
    analysis = StoryAnalysis(
        project_id=context.project_id,
        source_hash=text_hash("source"),
        summary="초기 요약",
        event_order=["a"],
        emotional_progression=["calm"],
    )
    storage.write_model(context.project_dir, "analysis", analysis)
    loaded = storage.read_model(context.project_dir, "analysis", StoryAnalysis)
    assert loaded.summary == "초기 요약"

    rerun = analysis.model_copy(update={"summary": "갱신된 요약"})
    storage.write_model(context.project_dir, "analysis", rerun)
    assert storage.read_model(context.project_dir, "analysis", StoryAnalysis).summary == "갱신된 요약"


def test_provider_secret_values_are_not_written_to_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NCC_LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-secret")
    settings = AppSettings.from_env()
    storage = ProjectStorage(tmp_path, settings)
    context = storage.create_project("demo", "safe source")

    unsafe = StoryAnalysis(
        project_id=context.project_id,
        source_hash=text_hash("safe source"),
        summary="test-openai-secret",
        event_order=["a"],
        emotional_progression=["calm"],
    )
    with pytest.raises(ValueError, match="secret"):
        storage.write_model(context.project_dir, "analysis", unsafe)


def test_public_provider_status_hides_secret_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NCC_IMAGE_PROVIDER", "novelai")
    monkeypatch.setenv("NOVELAI_API_TOKEN", "nai-secret")
    status = AppSettings.from_env().public_provider_status()
    assert status["image"]["configured"] is True
    assert "nai-secret" not in str(status)


def test_explicit_project_id_rejects_path_traversal(tmp_path: Path) -> None:
    storage = ProjectStorage(tmp_path)
    with pytest.raises(ValueError, match="project_id"):
        storage.create_project("demo", "source", project_id="../outside")
