from pathlib import Path

import pytest

from ncc.artifacts import dump_model, load_model
from ncc.invalidation import build_invalidation_event, invalidated_artifacts_for_edit
from ncc.models import (
    CandidateImage,
    CharacterBible,
    CharacterProfile,
    NAIPrompt,
    PanelSpec,
    PanelSpecSet,
    PromptIR,
    ProjectManifest,
    StoryAnalysis,
    Storyboard,
    StoryboardPanel,
    text_hash,
)


def test_schema_validation_and_serialization_round_trip(tmp_path: Path) -> None:
    source_hash = text_hash("하린은 브로치를 들었다")
    manifest = ProjectManifest(project_id="demo", title="데모", source_hash=source_hash)
    dump_model(manifest, tmp_path / "project.yaml")
    loaded = load_model(tmp_path / "project.yaml", ProjectManifest)
    assert loaded.project_id == "demo"
    assert loaded.source_hash == source_hash

    analysis = StoryAnalysis(
        project_id="demo",
        source_hash=source_hash,
        summary="하린이 브로치를 통해 동생의 기억을 찾는다.",
        event_order=["브로치를 줍는다", "전광판이 켜진다"],
        emotional_progression=["불안", "결심"],
    )
    dump_model(analysis, tmp_path / "analysis.json")
    assert load_model(tmp_path / "analysis.json", StoryAnalysis).summary.startswith("하린")


def test_character_forbidden_traits_cannot_be_positive_tags() -> None:
    with pytest.raises(ValueError, match="forbidden traits"):
        CharacterProfile(
            character_id="harin",
            name="하린",
            visual_lock_traits=["검은 단발", "둥근 안경", "노란 우비"],
            forbidden_traits=["blue eyes"],
            voice_personality_summary="조심스럽지만 용감하다.",
            positive_tags=["blue eyes"],
        )


def test_panel_and_prompt_contracts_keep_dialogue_separate() -> None:
    source_hash = text_hash("비가 온다")
    bible = CharacterBible(
        project_id="demo",
        source_hash=source_hash,
        characters=[
            CharacterProfile(
                character_id="harin",
                name="하린",
                visual_lock_traits=["short black hair", "round glasses", "yellow raincoat"],
                forbidden_traits=["long blond hair"],
                voice_personality_summary="조심스럽지만 용감하다.",
                positive_tags=["short black hair", "round glasses", "yellow raincoat"],
                negative_tags=["long blond hair"],
            )
        ],
    )
    assert bible.characters[0].name == "하린"

    storyboard = Storyboard(
        project_id="demo",
        source_hash=source_hash,
        panels=[
            StoryboardPanel(
                panel_id=f"p{i}",
                order=i,
                beat=f"beat {i}",
                camera="medium shot",
                composition="vertical panel",
                visible_characters=["harin"],
                setting="rainy tram stop",
                emotion="tense",
                draft_dialogue="여기 누구 있어?",
            )
            for i in range(1, 5)
        ],
    )
    panel_specs = PanelSpecSet(
        project_id="demo",
        source_hash=source_hash,
        panels=[
            PanelSpec(
                panel_id=panel.panel_id,
                order=panel.order,
                beat=panel.beat,
                camera=panel.camera,
                composition=panel.composition,
                visible_character_ids=panel.visible_characters,
                setting=panel.setting,
                emotion=panel.emotion,
                dialogue=panel.draft_dialogue,
                source_panel_id=panel.panel_id,
            )
            for panel in storyboard.panels
        ],
    )
    assert panel_specs.panels[0].dialogue == "여기 누구 있어?"

    prompt = PromptIR(
        panel_id="p1",
        base_prompt=["rainy tram stop", "vertical webtoon panel"],
        character_prompts={"harin": ["short black hair", "round glasses"]},
        global_undesired=["text", "watermark"],
        character_undesired={"harin": ["long blond hair"]},
        tag_candidates=[],
        source_revision=source_hash,
    )
    assert "여기 누구 있어?" not in " ".join(prompt.base_prompt)


def test_invalidation_rules_are_explicit_and_manual() -> None:
    assert invalidated_artifacts_for_edit("character_settings") == [
        "panel_specs",
        "prompt_ir",
        "nai_prompts",
        "image_candidates",
        "lettering",
        "export",
    ]
    event = build_invalidation_event("candidate_selection", ["p1:c2"])
    assert event.invalid_artifacts == ["export"]
    assert "manual" in event.reason


def test_artifact_paths_are_project_relative() -> None:
    prompt = NAIPrompt(
        panel_id="p1",
        base_prompt="rain",
        character_prompts={},
        undesired_prompt="text",
        seed=1,
    )
    with pytest.raises(ValueError, match="project-relative"):
        CandidateImage(
            candidate_id="p1-c1",
            panel_id="p1",
            image_path="../outside.png",
            prompt=prompt,
            seed=1,
            source_revision=text_hash("prompt"),
        )
