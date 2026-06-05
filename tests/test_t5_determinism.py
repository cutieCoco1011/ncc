from ncc.prompts import PromptCompiler
from ncc.story_pipeline import MockLLMStoryProvider
from ncc.tags import CanonicalTagCompiler, LocalDanbooruTagProvider


def _compiled_prompt_signature(source: str) -> tuple[str, str]:
    bundle = MockLLMStoryProvider().analyze("determinism", source, panel_count=6)
    compiler = PromptCompiler(LocalDanbooruTagProvider())
    prompt_ir = compiler.build_prompt_ir("determinism", bundle.panel_specs, bundle.characters)
    nai_prompts = compiler.compile_nai_prompts("determinism", prompt_ir)
    return (
        prompt_ir.model_dump_json(),
        nai_prompts.model_dump_json(),
    )


def test_local_tag_compiler_is_identical_across_50_runs() -> None:
    source = (
        "겨울 바닷가에서 서윤은 녹슨 우체통 안에 젖지 않은 엽서 한 장을 발견했다. "
        "서윤은 하얀 장갑을 낀 손으로 엽서를 품고 방파제를 따라 등대로 향했다."
    )

    signatures = {_compiled_prompt_signature(source) for _ in range(50)}

    assert len(signatures) == 1


def test_llm_raw_variance_does_not_change_final_canonical_tags() -> None:
    compiler = CanonicalTagCompiler.from_default_lexicon()
    raw_suggestions = [
        ["yellow raincoat", "postcard", "winter seaside"],
        ["yellow_raincoat", "post card", "winter seaside"],
        ["노란 우비", "엽서", "바닷가"],
    ] * 17

    compiled_sets = {
        tuple(
            sorted(
                tag.tag
                for tag in compiler.compile_candidates(
                    panel_id="p1",
                    provider="llm-fixture",
                    candidates=suggestions,
                    evidence={"source": "fixture"},
                ).positive
            )
        )
        for suggestions in raw_suggestions[:50]
    }

    assert len(raw_suggestions[:50]) == 50
    assert len({tuple(suggestions) for suggestions in raw_suggestions[:50]}) == 3
    assert compiled_sets == {("postcard", "winter_seaside", "yellow_raincoat")}
