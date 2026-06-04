from pathlib import Path

from ncc.fixtures import GOLD_PATH_KOREAN_SOURCE
from ncc.images import CandidateGenerationService, png_dimensions
from ncc.prompts import PromptCompiler
from ncc.story_pipeline import MockLLMStoryProvider


def test_mock_image_generation_creates_eighteen_candidate_records(tmp_path: Path) -> None:
    bundle = MockLLMStoryProvider().analyze("demo", GOLD_PATH_KOREAN_SOURCE, panel_count=6)
    compiler = PromptCompiler()
    prompt_ir = compiler.build_prompt_ir("demo", bundle.panel_specs, bundle.characters)
    nai_prompts = compiler.compile_nai_prompts("demo", prompt_ir)

    candidates = CandidateGenerationService().generate_candidates("demo", tmp_path, nai_prompts)

    assert len(candidates.candidates) == 18
    assert len(candidates.by_panel()) == 6
    first_path = tmp_path / candidates.candidates[0].image_path
    assert first_path.exists()
    assert png_dimensions(first_path) == (1080, 1440)
    assert candidates.candidates[0].provider_metadata["provider"] == "mock-image"
