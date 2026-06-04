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
