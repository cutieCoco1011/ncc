from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ncc.api import create_app
from ncc.models import ArtifactStatus, CandidateSet
from ncc.orchestrator import InvalidArtifactError, NccOrchestrator


def test_health_providers_and_project_creation(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    assert client.get("/health").json() == {"status": "ok"}
    providers = client.get("/providers").json()
    assert providers["llm"]["provider"] == "mock"

    response = client.post("/projects", json={"title": "데모", "source_text": "하린이 달린다.", "panel_count": 6})
    assert response.status_code == 200
    payload = response.json()
    assert payload["project_id"]
    assert payload["artifact_status"]["analysis"] == "missing"
    listed = client.get("/projects").json()[0]
    assert listed["title"] == "데모"
    assert listed["created_at"]
    assert listed["updated_at"]


def test_api_artifact_edit_selection_lettering_and_file_flow(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    gold = client.post("/gold-path", json={}).json()
    project_id = gold["project_id"]

    artifacts = client.get(f"/projects/{project_id}/artifacts").json()
    assert len(artifacts["storyboard"]["panels"]) == 6
    assert len(artifacts["image_candidates"]["candidates"]) == 18

    character = client.patch(
        f"/projects/{project_id}/characters/harin",
        json={"visual_lock_traits": ["short black hair", "round glasses", "yellow raincoat", "wet bangs"]},
    ).json()
    assert "panel_specs" in character["invalidation"]["invalid_artifacts"]
    assert character["manifest"]["artifact_status"]["image_candidates"] == "invalid"
    edited = client.patch(
        f"/projects/{project_id}/storyboard/p1",
        json={"beat": "하린이 브로치를 더 가까이 살핀다."},
    ).json()
    assert edited["manifest"]["artifact_status"]["panel_specs"] == "invalid"
    assert edited["manifest"]["artifact_status"]["export"] == "invalid"
    stale_export = client.get(f"/projects/{project_id}/exports/latest")
    assert stale_export.status_code == 409
    assert "export is invalid" in stale_export.json()["diagnostics"][0]
    stale_file = client.get(f"/projects/{project_id}/files/exports/webtoon_export.png")
    assert stale_file.status_code == 409
    invalid_select = client.post(f"/projects/{project_id}/candidates/p1-c1/select")
    assert invalid_select.status_code == 409
    assert "image_candidates is invalid" in invalid_select.json()["diagnostics"][0]
    invalid_export = client.post(f"/projects/{project_id}/stages/export")
    assert invalid_export.status_code == 409
    assert "image_candidates is invalid" in invalid_export.json()["diagnostics"][0]
    assert client.post(f"/projects/{project_id}/stages/prompts").status_code == 409
    refreshed_specs = client.post(f"/projects/{project_id}/stages/panel-specs")
    assert refreshed_specs.status_code == 200
    assert client.post(f"/projects/{project_id}/stages/prompts").status_code == 200
    assert client.post(f"/projects/{project_id}/stages/images").status_code == 200
    artifacts_after_images = client.get(f"/projects/{project_id}/artifacts").json()
    assert artifacts_after_images["project"]["artifact_status"]["export"] == "invalid"
    assert client.get(f"/projects/{project_id}/exports/latest").status_code == 409
    assert client.post(f"/projects/{project_id}/stages/qa").status_code == 200
    assert client.post(f"/projects/{project_id}/candidates/p1-c1/select").status_code == 200
    refreshed_artifacts = client.get(f"/projects/{project_id}/artifacts").json()
    assert refreshed_artifacts["panel_specs"]["panels"][0]["beat"] == "하린이 브로치를 더 가까이 살핀다."

    # Regenerate the mock gold path state for selection/lettering endpoint checks.
    project_id = client.post("/gold-path", json={}).json()["project_id"]
    reject = client.post(
        f"/projects/{project_id}/candidates/p1-c2/reject",
        json={"reason": "bad trait"},
    )
    assert reject.status_code == 200
    selected = client.post(f"/projects/{project_id}/candidates/p1-c1/select").json()
    rejected = next(
        candidate
        for candidate in selected["image_candidates"]["candidates"]
        if candidate["candidate_id"] == "p1-c2"
    )
    assert rejected["state"] == "rejected"
    assert rejected["rejected_reason"] == "bad trait"
    rejected_selected = client.post(
        f"/projects/{project_id}/candidates/p1-c1/reject",
        json={"reason": "changed mind"},
    ).json()
    assert rejected_selected["manifest"]["artifact_status"]["export"] == "invalid"
    assert client.post(f"/projects/{project_id}/candidates/p1-c3/select").status_code == 200

    patched = client.patch(
        f"/projects/{project_id}/lettering/p1-speech",
        json={"text": "정말 반짝이잖아."},
    ).json()
    assert patched["manifest"]["artifact_status"]["export"] == "invalid"
    refreshed = client.post(f"/projects/{project_id}/stages/lettering")
    assert refreshed.status_code == 200
    exported = client.post(f"/projects/{project_id}/stages/export")
    assert exported.status_code == 200

    file_response = client.get(f"/projects/{project_id}/exports/latest")
    assert file_response.status_code == 200
    assert file_response.headers["content-type"] == "image/png"


def test_api_returns_diagnostics_for_invalid_stage_order(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    project = client.post(
        "/projects",
        json={"title": "데모", "source_text": "하린이 달린다.", "panel_count": 6},
    ).json()
    response = client.post(f"/projects/{project['project_id']}/stages/prompts")
    assert response.status_code == 409
    assert "panel_specs is missing" in response.json()["diagnostics"][0]


def test_lettering_refresh_updates_storyboard_dialogue(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    project_id = client.post("/gold-path", json={}).json()["project_id"]
    client.patch(
        f"/projects/{project_id}/storyboard/p1",
        json={"draft_dialogue": "새로 저장한 말풍선"},
    )
    client.post(f"/projects/{project_id}/stages/panel-specs")
    client.post(f"/projects/{project_id}/stages/prompts")
    client.post(f"/projects/{project_id}/stages/images")
    client.post(f"/projects/{project_id}/stages/qa")
    client.post(f"/projects/{project_id}/candidates/p1-c1/select")
    client.post(f"/projects/{project_id}/stages/lettering")
    artifacts = client.get(f"/projects/{project_id}/artifacts").json()
    balloon = next(
        item
        for item in artifacts["lettering"]["balloons"]
        if item["balloon_id"] == "p1-speech"
    )
    assert balloon["text"] == "새로 저장한 말풍선"


def test_export_file_route_only_serves_current_export(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    gold = client.post("/gold-path", json={}).json()
    project_id = gold["project_id"]
    project_dir = Path(gold["project_dir"])
    old_export = project_dir / "exports" / "old_export.png"
    old_export.write_bytes((project_dir / "exports" / "webtoon_export.png").read_bytes())

    response = client.get(f"/projects/{project_id}/files/exports/old_export.png")
    assert response.status_code == 409
    assert "current export" in response.json()["diagnostics"][0]


def test_lettering_refresh_removes_cleared_storyboard_dialogue(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    project_id = client.post("/gold-path", json={}).json()["project_id"]
    client.patch(
        f"/projects/{project_id}/storyboard/p1",
        json={"draft_dialogue": ""},
    )
    client.post(f"/projects/{project_id}/stages/panel-specs")
    client.post(f"/projects/{project_id}/stages/prompts")
    client.post(f"/projects/{project_id}/stages/images")
    client.post(f"/projects/{project_id}/stages/qa")
    client.post(f"/projects/{project_id}/candidates/p1-c1/select")
    client.post(f"/projects/{project_id}/stages/lettering")
    artifacts = client.get(f"/projects/{project_id}/artifacts").json()
    balloon_ids = {item["balloon_id"] for item in artifacts["lettering"]["balloons"]}
    assert "p1-speech" not in balloon_ids


def test_api_rejects_project_traversal(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    response = client.get("/projects/%2E%2E/artifacts")
    assert response.status_code == 422
    assert "project_id" in response.json()["diagnostics"][0]


def test_novelai_provider_selection_does_not_silently_use_mock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NCC_IMAGE_PROVIDER", "novelai")
    monkeypatch.setenv("NOVELAI_API_TOKEN", "token")
    from PIL import Image

    class FakeNovelAIBackend:
        def __init__(self, api_token: str) -> None:
            assert api_token == "token"

        def generate(self, _prompt, output_path, seed, panel_order, candidate_index):
            output_path.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (64, 96), (20, 70, 110)).save(output_path, "PNG")
            return {
                "provider": "novelai",
                "model": "fake-model",
                "seed": seed,
                "panel_order": panel_order,
                "candidate_index": candidate_index,
                "width": 64,
                "height": 96,
            }

    monkeypatch.setattr("ncc.orchestrator.NovelAIImageBackend", FakeNovelAIBackend)
    orchestrator = NccOrchestrator(tmp_path)
    context = orchestrator.create_project("demo", "하린이 달린다.")
    orchestrator.run_story_stage(context.project_id)
    orchestrator.run_prompt_stage(context.project_id)
    orchestrator.run_image_stage(context.project_id)
    candidates = orchestrator.storage.read_model(
        orchestrator.open_project(context.project_id).project_dir,
        "image_candidates",
        CandidateSet,
    )
    assert candidates.candidates[0].provider_metadata["provider"] == "novelai"


def test_novelai_provider_without_token_reports_not_configured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NCC_IMAGE_PROVIDER", "novelai")
    monkeypatch.delenv("NOVELAI_API_TOKEN", raising=False)
    orchestrator = NccOrchestrator(tmp_path)
    context = orchestrator.create_project("demo", "하린이 달린다.")
    orchestrator.run_story_stage(context.project_id)
    orchestrator.run_prompt_stage(context.project_id)

    with pytest.raises(ValueError, match="not_configured"):
        orchestrator.run_image_stage(context.project_id)


def test_unknown_image_provider_reports_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    from ncc.settings import AppSettings

    monkeypatch.setenv("NCC_IMAGE_PROVIDER", "novel-ai")
    status = AppSettings.from_env().public_provider_status()
    assert status["image"]["provider"] == "not_configured"


def test_orchestrator_refuses_invalid_downstream_artifacts(tmp_path: Path) -> None:
    orchestrator = NccOrchestrator(tmp_path)
    context = orchestrator.create_project("demo", "source")
    context.manifest.artifact_status["prompt_ir"] = ArtifactStatus.INVALID
    with pytest.raises(InvalidArtifactError, match="prompt_ir is invalid"):
        orchestrator.require_valid(context.manifest, "prompt_ir")
