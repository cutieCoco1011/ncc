from pathlib import Path

from PIL import Image

from ncc.exporter import build_default_lettering, export_vertical_png
from ncc.fixtures import DEFAULT_PROJECT_TITLE, GOLD_PATH_KOREAN_SOURCE
from ncc.images import CandidateGenerationService
from ncc.orchestrator import NccOrchestrator
from ncc.prompts import PromptCompiler
from ncc.qa import SelectionService
from ncc.story_pipeline import MockLLMStoryProvider


def test_mock_gold_path_exports_readable_vertical_png(tmp_path: Path) -> None:
    result = NccOrchestrator(tmp_path).run_mock_gold_path(DEFAULT_PROJECT_TITLE, GOLD_PATH_KOREAN_SOURCE)

    assert result["candidate_count"] == 18
    assert result["selected_count"] == 6
    export_path = Path(str(result["export_path"]))
    assert export_path.exists()

    with Image.open(export_path) as image:
        assert image.format == "PNG"
        assert image.width >= 1080
        assert image.height > image.width


def test_gold_path_api_smoke_reaches_export(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient

    from ncc.api import create_app

    client = TestClient(create_app(tmp_path))
    response = client.post("/gold-path", json={})

    assert response.status_code == 200
    payload = response.json()
    assert payload["panel_count"] == 6
    assert payload["candidate_count"] == 18
    assert payload["export_width"] >= 1080
    assert Path(payload["export_path"]).exists()


def test_export_refuses_stale_lettering_selection_hash(tmp_path: Path) -> None:
    bundle = MockLLMStoryProvider().analyze("demo", GOLD_PATH_KOREAN_SOURCE, panel_count=6)
    compiler = PromptCompiler()
    ir = compiler.build_prompt_ir("demo", bundle.panel_specs, bundle.characters)
    nai = compiler.compile_nai_prompts("demo", ir)
    candidates = CandidateGenerationService().generate_candidates("demo", tmp_path, nai)
    selected, _ = SelectionService().select_first_per_panel(candidates)
    lettering = build_default_lettering("demo", bundle.storyboard, selected)
    reselected, _ = SelectionService().select_candidate(selected, "p1", "p1-c2")

    import pytest

    with pytest.raises(ValueError, match="stale"):
        export_vertical_png("demo", tmp_path, bundle.storyboard, reselected, lettering)
