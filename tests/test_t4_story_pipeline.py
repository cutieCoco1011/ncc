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


def test_story_pipeline_keeps_story_setting_after_location_keywords_drop_out() -> None:
    source = (
        "겨울 바닷가에서 서윤은 녹슨 우체통 안에 젖지 않은 엽서 한 장을 발견했다. "
        "엽서에는 아직 오지 않은 폭풍의 날짜와, 등대지기가 남긴 짧은 부탁이 적혀 있었다. "
        "서윤은 하얀 장갑을 낀 손으로 엽서를 품고, 파도가 낮게 속삭이는 방파제를 따라 등대로 향했다. "
        "바람의 괴물이 등불을 꺼뜨리려 하자, 서윤은 엽서를 펼쳐 종이 위의 작은 태양을 하늘로 띄웠다. "
        "등대가 다시 켜지고 배들의 경적이 들려오자, 서윤은 답장을 쓰기 위해 우체통 앞으로 돌아왔다."
    )

    bundle = MockLLMStoryProvider().analyze("바닷가 엽서 우체통", source, panel_count=6)

    assert bundle.panel_specs.panels[3].setting == "winter seaside, breakwater, and lighthouse"


def test_non_default_primary_character_gets_stable_visual_lock_traits() -> None:
    source = (
        "새벽 도서관에서 지우는 반납함 뒤에 떨어진 은색 열쇠를 발견했다. "
        "지우는 겁을 삼키며 붉은 목도리를 고쳐 매고, 가장 희미한 별을 따라 서가 깊숙한 곳으로 걸어갔다."
    )

    bundle = MockLLMStoryProvider().analyze("도서관 별빛 열쇠", source, panel_count=6)
    primary = bundle.characters.characters[0]

    assert "same female protagonist in every panel" in primary.visual_lock_traits
    assert "short dark bob hair" in primary.visual_lock_traits
    assert "red scarf" in primary.visual_lock_traits
    assert "male protagonist" in primary.forbidden_traits
    assert "white hair" in primary.negative_tags
