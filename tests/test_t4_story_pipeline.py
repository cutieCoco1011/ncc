from ncc.fixtures import GOLD_PATH_KOREAN_SOURCE
from ncc.story_pipeline import MockLLMStoryProvider


def test_mock_story_pipeline_produces_valid_six_panel_bundle() -> None:
    bundle = MockLLMStoryProvider().analyze("demo", GOLD_PATH_KOREAN_SOURCE, panel_count=6)

    assert bundle.analysis.event_order[0].startswith("비 오는 밤")
    assert len(bundle.storyboard.panels) == 6
    assert len(bundle.panel_specs.panels) == 6
    assert bundle.characters.characters[0].name == "하린"
    assert len(bundle.characters.characters[0].visual_lock_traits) >= 3
    assert bundle.panel_specs.panels[0].dialogue


def test_story_pipeline_keeps_dialogue_as_lettering_metadata() -> None:
    bundle = MockLLMStoryProvider().analyze("demo", GOLD_PATH_KOREAN_SOURCE, panel_count=6)
    panel = bundle.panel_specs.panels[1]

    assert "동생" in panel.dialogue
    assert "동생" not in panel.composition
