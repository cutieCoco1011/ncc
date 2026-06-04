from pathlib import Path

from ncc.fixtures import GOLD_PATH_KOREAN_SOURCE
from ncc.images import CandidateGenerationService
from ncc.prompts import PromptCompiler
from ncc.qa import CandidateQAService, SelectionService
from ncc.story_pipeline import MockLLMStoryProvider


def _candidate_set(tmp_path: Path):
    bundle = MockLLMStoryProvider().analyze("demo", GOLD_PATH_KOREAN_SOURCE, panel_count=6)
    compiler = PromptCompiler()
    prompt_ir = compiler.build_prompt_ir("demo", bundle.panel_specs, bundle.characters)
    nai_prompts = compiler.compile_nai_prompts("demo", prompt_ir)
    candidates = CandidateGenerationService().generate_candidates("demo", tmp_path, nai_prompts)
    return bundle, candidates


def test_candidate_qa_preserves_provenance_and_flags_forbidden_guards(tmp_path: Path) -> None:
    bundle, candidates = _candidate_set(tmp_path)
    evaluated = CandidateQAService().evaluate(candidates, bundle.characters)

    assert evaluated.candidates[0].qa_status.value in {"pass", "warn"}
    assert evaluated.candidates[0].source_revision
    assert any(flag.code == "forbidden_trait_guarded" for flag in evaluated.candidates[0].qa_flags)


def test_selection_allows_one_candidate_per_panel_and_invalidates_export(tmp_path: Path) -> None:
    _, candidates = _candidate_set(tmp_path)
    selected, events = SelectionService().select_first_per_panel(candidates)

    assert len(events) == 6
    assert all(event.invalid_artifacts == ["export"] for event in events)
    for panel_candidates in selected.by_panel().values():
        assert sum(1 for candidate in panel_candidates if candidate.selected) == 1


def test_rejection_reason_is_preserved(tmp_path: Path) -> None:
    _, candidates = _candidate_set(tmp_path)
    rejected = SelectionService().reject_candidate(candidates, "p1-c2", "forbidden hair color")
    candidate = next(candidate for candidate in rejected.candidates if candidate.candidate_id == "p1-c2")
    assert candidate.rejected_reason == "forbidden hair color"
    assert candidate.state.value == "rejected"


def test_selection_preserves_rejected_candidate_state(tmp_path: Path) -> None:
    _, candidates = _candidate_set(tmp_path)
    service = SelectionService()
    rejected = service.reject_candidate(candidates, "p1-c2", "bad trait")
    selected, _ = service.select_candidate(rejected, "p1", "p1-c1")

    candidate = next(candidate for candidate in selected.candidates if candidate.candidate_id == "p1-c2")
    assert candidate.state.value == "rejected"
    assert candidate.rejected_reason == "bad trait"
