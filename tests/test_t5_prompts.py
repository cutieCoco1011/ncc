from ncc.fixtures import GOLD_PATH_KOREAN_SOURCE
from ncc.prompts import PromptCompiler
from ncc.story_pipeline import MockLLMStoryProvider


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
