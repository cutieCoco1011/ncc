import pytest

from ncc.fixtures import GOLD_PATH_KOREAN_SOURCE, MULTI_SOURCE_KOREAN_FIXTURES
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


@pytest.mark.parametrize(("title", "source"), MULTI_SOURCE_KOREAN_FIXTURES)
def test_story_pipeline_supports_multiple_korean_sources(title: str, source: str) -> None:
    bundle = MockLLMStoryProvider().analyze(title, source, panel_count=6)

    assert len(bundle.analysis.event_order) >= 3
    assert len(bundle.storyboard.panels) == 6
    assert len(bundle.panel_specs.panels) == 6
    assert all(panel.dialogue or panel.caption for panel in bundle.panel_specs.panels)
    assert len({panel.beat for panel in bundle.storyboard.panels}) == len(bundle.storyboard.panels)

    first_sentence = source.split(".")[0] + "." if "." in source else source
    assert bundle.storyboard.panels[0].beat == first_sentence

    if "하린" not in source:
        primary = bundle.characters.characters[0]
        assert primary.name in source
        assert primary.character_id == "main_character"
        assert all("rainy old tram stop" not in panel.setting for panel in bundle.panel_specs.panels)
        assert all("Harin" not in panel.composition for panel in bundle.panel_specs.panels)
