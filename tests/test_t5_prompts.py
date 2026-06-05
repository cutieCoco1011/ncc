from ncc.fixtures import GOLD_PATH_KOREAN_SOURCE
from ncc.models import (
    CharacterBible,
    CharacterProfile,
    PanelSpec,
    PanelSpecSet,
    ReferenceImageMetadata,
    text_hash,
)
from ncc.prompts import PromptCompiler
from ncc.story_pipeline import MockLLMStoryProvider
from ncc.tags import LocalDanbooruTagProvider


def test_prompt_compiler_preserves_base_character_and_undesired_separation() -> None:
    bundle = MockLLMStoryProvider().analyze("demo", GOLD_PATH_KOREAN_SOURCE, panel_count=6)
    compiler = PromptCompiler()

    ir_set = compiler.build_prompt_ir("demo", bundle.panel_specs, bundle.characters)
    nai_set = compiler.compile_nai_prompts("demo", ir_set)

    first_ir = ir_set.prompts[0]
    assert "harin" in first_ir.character_prompts
    assert "yellow raincoat" in first_ir.character_prompts["harin"]
    assert "long blond hair" in first_ir.character_undesired["harin"]
    assert first_ir.priority_metadata["dialogue_kept_for_lettering"] is True
    assert "동생 이름이 왜 여기 있어?" not in nai_set.prompts[1].base_prompt
    assert "speech bubble text" in nai_set.prompts[0].undesired_prompt


def test_forbidden_traits_never_become_positive_prompt_tokens() -> None:
    bundle = MockLLMStoryProvider().analyze("demo", GOLD_PATH_KOREAN_SOURCE, panel_count=6)
    prompt_ir = PromptCompiler().build_prompt_ir("demo", bundle.panel_specs, bundle.characters)

    harin_prompt = prompt_ir.prompts[0].character_prompts["harin"]
    assert "blue eyes" not in harin_prompt
    assert "adult woman" not in harin_prompt


def test_prompt_tags_follow_non_default_source_keywords() -> None:
    source = (
        "겨울 바닷가에서 서윤은 녹슨 우체통 안에 젖지 않은 엽서 한 장을 발견했다. "
        "엽서에는 아직 오지 않은 폭풍의 날짜와, 등대지기가 남긴 짧은 부탁이 적혀 있었다. "
        "서윤은 하얀 장갑을 낀 손으로 엽서를 품고, 파도가 낮게 속삭이는 방파제를 따라 등대로 향했다. "
        "바람의 괴물이 등불을 꺼뜨리려 하자, 서윤은 엽서를 펼쳐 종이 위의 작은 태양을 하늘로 띄웠다. "
        "등대가 다시 켜지고 배들의 경적이 들려오자, 서윤은 답장을 쓰기 위해 우체통 앞으로 돌아왔다."
    )
    bundle = MockLLMStoryProvider().analyze("바닷가 엽서 우체통", source, panel_count=6)
    prompt_ir = PromptCompiler().build_prompt_ir("demo", bundle.panel_specs, bundle.characters)

    first_prompt_tags = {candidate.tag for candidate in prompt_ir.prompts[0].tag_candidates}
    assert "winter seaside" in first_prompt_tags
    assert "postcard" in first_prompt_tags
    assert "tram stop" not in first_prompt_tags
    assert "main_character" in prompt_ir.prompts[0].character_prompts


def test_default_prompt_tags_are_explicitly_mock_provenance() -> None:
    source = (
        "겨울 바닷가에서 서윤은 녹슨 우체통 안에 젖지 않은 엽서 한 장을 발견했다. "
        "서윤은 하얀 장갑을 낀 손으로 엽서를 품고 방파제를 따라 등대로 향했다."
    )
    bundle = MockLLMStoryProvider().analyze("바닷가 엽서 우체통", source, panel_count=6)
    prompt_ir = PromptCompiler().build_prompt_ir("demo", bundle.panel_specs, bundle.characters)

    first = prompt_ir.prompts[0]
    assert {candidate.source for candidate in first.tag_candidates} == {"static-mock"}
    assert all(candidate.provenance["provider"] == "mock" for candidate in first.tag_candidates)


def test_local_tag_provider_writes_non_mock_prompt_provenance() -> None:
    source = (
        "겨울 바닷가에서 서윤은 녹슨 우체통 안에 젖지 않은 엽서 한 장을 발견했다. "
        "서윤은 하얀 장갑을 낀 손으로 엽서를 품고 방파제를 따라 등대로 향했다."
    )
    bundle = MockLLMStoryProvider().analyze("바닷가 엽서 우체통", source, panel_count=6)
    prompt_ir = PromptCompiler(LocalDanbooruTagProvider()).build_prompt_ir(
        "demo",
        bundle.panel_specs,
        bundle.characters,
    )

    first = prompt_ir.prompts[0]
    assert any(candidate.tag == "winter_seaside" for candidate in first.tag_candidates)
    assert all(candidate.provenance["provider"] == "local" for candidate in first.tag_candidates)


def test_local_tag_provider_does_not_send_korean_text_to_nai_prompt() -> None:
    source = (
        "겨울 바닷가에서 서윤은 녹슨 우체통 안에 젖지 않은 엽서 한 장을 발견했다. "
        "서윤은 하얀 장갑을 낀 손으로 엽서를 품고 방파제를 따라 등대로 향했다."
    )
    bundle = MockLLMStoryProvider().analyze("바닷가 엽서 우체통", source, panel_count=6)
    compiler = PromptCompiler(LocalDanbooruTagProvider())
    prompt_ir = compiler.build_prompt_ir("demo", bundle.panel_specs, bundle.characters)
    nai_set = compiler.compile_nai_prompts("demo", prompt_ir)

    assert not any("가" <= character <= "힣" for character in nai_set.prompts[0].base_prompt)


def test_local_prompt_stage_preserves_panel_spec_visual_motifs_without_korean_leakage() -> None:
    source_hash = text_hash("panel visual motif preservation")
    panel_specs = PanelSpecSet(
        project_id="demo",
        source_hash=source_hash,
        panels=[
            PanelSpec(
                panel_id="p1",
                order=1,
                beat="하린이 고개를 든다.",
                camera="close-up",
                composition="blue station display reflecting in glasses, glowing cat brooch foreground",
                visible_character_ids=["harin"],
                setting="rainy old tram stop and narrow alley",
                emotion="불안",
                source_panel_id="p1",
            ),
            PanelSpec(
                panel_id="p2",
                order=2,
                beat="하린이 빛을 따라간다.",
                camera="low angle",
                composition="shadow creature looming over memory light",
                visible_character_ids=["harin"],
                setting="rainy old tram stop and narrow alley",
                emotion="공포",
                source_panel_id="p2",
            ),
            PanelSpec(
                panel_id="p3",
                order=3,
                beat="하린이 전차에 오른다.",
                camera="wide vertical finale",
                composition="first tram arriving under clearing rain",
                visible_character_ids=["harin"],
                setting="rainy old tram stop and narrow alley",
                emotion="안도",
                source_panel_id="p3",
            ),
            PanelSpec(
                panel_id="p4",
                order=4,
                beat="하린이 약속을 떠올린다.",
                camera="medium shot",
                composition="hopeful light around the protagonist",
                visible_character_ids=["harin"],
                setting="rainy old tram stop and narrow alley",
                emotion="용기",
                source_panel_id="p4",
            ),
        ],
    )
    characters = CharacterBible(
        project_id="demo",
        source_hash=source_hash,
        characters=[
            CharacterProfile(
                character_id="harin",
                name="하린",
                visual_lock_traits=["short black hair", "round glasses", "yellow raincoat"],
                forbidden_traits=["long blond hair", "blue eyes", "adult woman"],
                voice_personality_summary="겁이 많지만 포기하지 않는다.",
                positive_tags=["Korean teenage girl", "yellow raincoat"],
                negative_tags=["male protagonist"],
                reference_image_metadata=ReferenceImageMetadata(note="none"),
            )
        ],
    )

    compiler = PromptCompiler(LocalDanbooruTagProvider())
    prompt_ir = compiler.build_prompt_ir("demo", panel_specs, characters)
    nai_prompts = compiler.compile_nai_prompts("demo", prompt_ir)

    prompts = {prompt.panel_id: prompt.base_prompt for prompt in nai_prompts.prompts}
    assert {"cat_brooch", "blue_station_display", "tram_stop", "rain", "narrow_alley"} <= set(
        prompts["p1"].split(", ")
    )
    assert {"shadow_creature", "memory_light"} <= set(prompts["p2"].split(", "))
    assert "tram" in set(prompts["p3"].split(", "))
    assert not any("가" <= character <= "힣" for prompt in prompts.values() for character in prompt)


def test_prompt_compiler_adds_character_consistency_controls() -> None:
    source = (
        "막차가 끊긴 지하철역에서 민아는 작동하지 않는 사탕 기계가 혼자 빛나는 것을 보았다. "
        "민아는 파란 운동화 끈을 단단히 묶고, 텅 빈 승강장을 가로질러 숨겨진 안내 방송을 따라갔다."
    )
    bundle = MockLLMStoryProvider().analyze("지하철 사탕 기계", source, panel_count=6)
    nai_set = PromptCompiler().compile_nai_prompts(
        "demo",
        PromptCompiler().build_prompt_ir("demo", bundle.panel_specs, bundle.characters),
    )

    prompt = nai_set.prompts[0]
    assert "single protagonist only" in prompt.base_prompt
    assert "consistent character design" in prompt.base_prompt
    assert "same female protagonist in every panel" in prompt.character_prompts["main_character"]
    assert "blue sneakers" in prompt.character_prompts["main_character"]
    assert "gender swap" in prompt.undesired_prompt
    assert "male protagonist" in prompt.undesired_prompt
