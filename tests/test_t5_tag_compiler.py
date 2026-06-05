from ncc.settings import AppSettings
import json

import pytest

from ncc.tags import (
    CanonicalTagCompiler,
    OpenAICompatibleTagCandidateExtractor,
    SourceTextTagPipeline,
    _candidate_tags_from_model_content,
    normalize_danbooru_tag,
)


class FixedSuggestionExtractor:
    provider_name = "deepseek"

    def candidates_for_text(self, _text: str) -> list[str]:
        return ["lighthouse", "speech bubble text", "unknown vibes"]


class NegatedSeasideSuggestionExtractor:
    provider_name = "deepseek"

    def candidates_for_text(self, _text: str) -> list[str]:
        return ["winter seaside", "lighthouse", "tram stop"]


class FailingSuggestionExtractor:
    provider_name = "deepseek"

    def candidates_for_text(self, _text: str) -> list[str]:
        raise RuntimeError("upstream timeout")


def test_normalize_danbooru_tag() -> None:
    assert normalize_danbooru_tag("Yellow Raincoat") == "yellow_raincoat"
    assert normalize_danbooru_tag("  speech bubble text  ") == "speech_bubble_text"
    assert normalize_danbooru_tag("한국어") == ""


def test_local_compiler_maps_aliases_and_filters_positive_blocklist() -> None:
    compiler = CanonicalTagCompiler.from_default_lexicon()

    result = compiler.compile_candidates(
        panel_id="p1",
        provider="local",
        candidates=["노란 우비", "winter seaside", "speech bubble text", "unknown pretty vibes"],
        evidence={"beat": "노란 우비를 입은 서윤이 겨울 바닷가에 있다."},
    )

    assert {tag.tag for tag in result.positive} == {"yellow_raincoat", "winter_seaside"}
    assert "speech_bubble_text" in {tag.tag for tag in result.negative}
    assert all(tag.provenance["provider"] == "local" for tag in result.positive)


def test_cross_model_suggestions_compile_to_same_core_tags() -> None:
    compiler = CanonicalTagCompiler.from_default_lexicon()
    model_outputs = [
        ("openai", ["yellow raincoat", "postcard", "speech bubble text"]),
        ("deepseek", ["Yellow Raincoat", "post card", "speech bubble text"]),
        ("mimo", ["yellow_raincoat", "postcard", "text in image"]),
    ]

    compiled_sets = []
    for provider, tags in model_outputs:
        compiled = compiler.compile_candidates(
            panel_id="p1",
            provider=provider,
            candidates=tags,
            evidence={"beat": "노란 우비와 엽서"},
        )
        compiled_sets.append({tag.tag for tag in compiled.positive})

    assert compiled_sets[0] == compiled_sets[1] == compiled_sets[2] == {
        "yellow_raincoat",
        "postcard",
    }


def test_korean_aliases_do_not_match_inside_larger_words() -> None:
    compiler = CanonicalTagCompiler.from_default_lexicon()

    result = compiler.compile_candidates(
        panel_id="p1",
        provider="local",
        candidates=["노란 우비와 엽서가 있는 겨울 바닷가 장면"],
        evidence={"source": "test"},
    )

    tags = {tag.tag for tag in result.positive}
    assert {"yellow_raincoat", "postcard", "winter_seaside"} <= tags
    assert "library" not in tags
    assert "rain" not in tags


def test_korean_aliases_still_match_common_particles() -> None:
    compiler = CanonicalTagCompiler.from_default_lexicon()

    result = compiler.compile_candidates(
        panel_id="p1",
        provider="local",
        candidates=["비가 내리는 바닷가에서 엽서를 본다"],
        evidence={"source": "test"},
    )

    assert {"rain", "winter_seaside", "postcard"} <= {tag.tag for tag in result.positive}


def test_english_aliases_do_not_match_inside_other_words() -> None:
    compiler = CanonicalTagCompiler.from_default_lexicon()

    result = compiler.compile_candidates(
        panel_id="p1",
        provider="local",
        candidates=["a girl in a yellow raincoat finds a postcard at the winter seaside"],
        evidence={"source": "test"},
    )

    tags = {tag.tag for tag in result.positive}
    assert {"yellow_raincoat", "postcard", "winter_seaside"} <= tags
    assert "rain" not in tags


def test_korean_english_and_japanese_sources_converge_to_same_core_tags() -> None:
    compiler = CanonicalTagCompiler.from_default_lexicon()
    sources = [
        "노란 우비를 입은 소녀가 겨울 바닷가에서 엽서를 발견한다. 멀리 등대에 비가 내린다.",
        "a girl in a yellow raincoat finds a postcard at the winter seaside. rain falls near a lighthouse.",
        "黄色いレインコートの少女が冬の海辺ではがきを見つける。遠くの灯台に雨が降る。",
    ]

    compiled_sets = [
        {
            tag.tag
            for tag in compiler.compile_candidates(
                panel_id="p1",
                provider="local",
                candidates=[source],
                evidence={"source": "test"},
            ).positive
        }
        for source in sources
    ]

    core_tags = {"yellow_raincoat", "winter_seaside", "postcard", "lighthouse", "rain"}
    assert all(core_tags <= tags for tags in compiled_sets)


def test_negated_aliases_do_not_become_positive_tags_across_languages() -> None:
    pipeline = SourceTextTagPipeline(CanonicalTagCompiler.from_default_lexicon())
    sources = [
        ("en", "a tram stop scene with a yellow raincoat but no rain", {"tram_stop", "yellow_raincoat"}, {"rain"}),
        ("ko", "비가 아닌 푸른 빛이 오래된 전차 정류장을 비춘다", {"tram_stop"}, {"rain"}),
        ("jp", "海辺ではない場所で、黄色いレインコートではない服を着た少女がはがきだけを見つける", {"postcard"}, {"winter_seaside", "yellow_raincoat"}),
    ]

    for language, source, expected, forbidden in sources:
        compiled = pipeline.compile_source_text(
            panel_id=f"neg-{language}",
            provider="local",
            source_text=source,
        )
        tags = {tag.tag for tag in compiled.positive}
        assert expected <= tags
        assert tags.isdisjoint(forbidden)


def test_current_project_core_motifs_compile_from_multilingual_source_text() -> None:
    compiler = CanonicalTagCompiler.from_default_lexicon()
    sources = [
        "비 오는 전차 정류장에서 고양이 브로치가 빛나고, 푸른 전광판과 골목 끝의 그림자 괴물이 보인다.",
        "rain falls at a tram stop, a cat brooch glows, a blue station display shines, and a shadow creature waits in a narrow alley.",
        "雨の電車の停留所で猫のブローチが光り、青い駅の表示板と路地の影の怪物が見える。",
    ]

    compiled_sets = [
        {
            tag.tag
            for tag in compiler.compile_candidates(
                panel_id="current-project",
                provider="local",
                candidates=[source],
                evidence={"source": "test"},
            ).positive
        }
        for source in sources
    ]

    core_tags = {"rain", "tram_stop", "cat_brooch", "blue_station_display", "narrow_alley", "shadow_creature"}
    assert all(core_tags <= tags for tags in compiled_sets)


def test_model_suggestions_are_candidates_only_and_still_canonicalized() -> None:
    pipeline = SourceTextTagPipeline(
        CanonicalTagCompiler.from_default_lexicon(),
        extractors=[FixedSuggestionExtractor()],
    )

    compiled = pipeline.compile_source_text(
        panel_id="p1",
        provider="deepseek",
        source_text="모델은 후보만 제안한다.",
    )

    positive = {tag.tag for tag in compiled.positive}
    negative = {tag.tag for tag in compiled.negative}
    assert positive == {"lighthouse"}
    assert negative == {"speech_bubble_text"}
    assert all(tag.provenance["provider"] == "deepseek" for tag in compiled.positive)
    assert all(tag.provenance["compiler"] == "local_canonical" for tag in compiled.positive)
    assert all(tag.provenance["extractor"] == "deepseek" for tag in compiled.positive)


def test_model_suggestions_are_vetoed_by_negated_source_aliases() -> None:
    pipeline = SourceTextTagPipeline(
        CanonicalTagCompiler.from_default_lexicon(),
        extractors=[
            CanonicalTagCompiler.from_default_lexicon().alias_extractor,
            NegatedSeasideSuggestionExtractor(),
        ],
        fail_on_extractor_error=True,
    )

    compiled = pipeline.compile_source_text(
        panel_id="p1",
        provider="deepseek",
        source_text="비 오는 전차 정류장이 배경이고, 바닷가는 아니다.",
    )

    positive = {tag.tag for tag in compiled.positive}
    assert "tram_stop" in positive
    assert "winter_seaside" not in positive
    assert "lighthouse" not in positive


def test_negated_setting_veto_does_not_remove_explicit_positive_motif() -> None:
    pipeline = SourceTextTagPipeline(
        CanonicalTagCompiler.from_default_lexicon(),
        extractors=[
            CanonicalTagCompiler.from_default_lexicon().alias_extractor,
            NegatedSeasideSuggestionExtractor(),
        ],
        fail_on_extractor_error=True,
    )

    compiled = pipeline.compile_source_text(
        panel_id="p1",
        provider="deepseek",
        source_text="바닷가는 아니지만 멀리 등대는 보인다. 비 오는 전차 정류장이 배경이다.",
    )

    positive = {tag.tag for tag in compiled.positive}
    assert "winter_seaside" not in positive
    assert "lighthouse" in positive
    assert "tram_stop" in positive


def test_external_suggestion_failures_do_not_silently_fallback_when_required() -> None:
    pipeline = SourceTextTagPipeline(
        CanonicalTagCompiler.from_default_lexicon(),
        extractors=[FailingSuggestionExtractor()],
        fail_on_extractor_error=True,
    )

    with pytest.raises(ValueError, match="tag candidate extractor failed: deepseek"):
        pipeline.compile_source_text(
            panel_id="p1",
            provider="deepseek",
            source_text="비 오는 정류장",
        )


def test_deepseek_suggester_defaults_match_official_v4_api(monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    monkeypatch.delenv("DEEPSEEK_BASE_URL", raising=False)

    extractor = OpenAICompatibleTagCandidateExtractor.from_env("deepseek")

    assert extractor.model == "deepseek-v4-pro"
    assert extractor.endpoint == "https://api.deepseek.com/chat/completions"


def test_deepseek_suggester_disables_thinking_and_parses_candidate_json(monkeypatch) -> None:
    captured_payload = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc, _traceback) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(
                {"choices": [{"message": {"content": "{\"tags\":[\"lighthouse\"]}"}}]}
            ).encode("utf-8")

    def fake_urlopen(request, timeout, context):
        captured_payload.update(json.loads(request.data.decode("utf-8")))
        assert timeout == 30
        assert context is not None
        return FakeResponse()

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    monkeypatch.delenv("DEEPSEEK_BASE_URL", raising=False)
    monkeypatch.setattr("ncc.tags.urllib.request.urlopen", fake_urlopen)
    extractor = OpenAICompatibleTagCandidateExtractor.from_env("deepseek")

    assert extractor.candidates_for_text("등대가 보인다") == ["lighthouse"]
    assert captured_payload["model"] == "deepseek-v4-pro"
    assert captured_payload["thinking"] == {"type": "disabled"}
    assert captured_payload["response_format"] == {"type": "json_object"}


def test_model_suggester_wraps_malformed_api_response(monkeypatch) -> None:
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc, _traceback) -> None:
            return None

        def read(self) -> bytes:
            return b'{"error":{"message":"bad request"}}'

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr("ncc.tags.urllib.request.urlopen", lambda _request, timeout, context: FakeResponse())
    extractor = OpenAICompatibleTagCandidateExtractor.from_env("deepseek")

    with pytest.raises(RuntimeError, match="deepseek tag suggestion returned malformed response"):
        extractor.candidates_for_text("등대가 보인다")


def test_model_content_parser_handles_fenced_json_and_string_tags() -> None:
    content = '```json\n{"tags": "lighthouse, rain\\ntram stop"}\n```'

    assert _candidate_tags_from_model_content(content) == ["lighthouse", "rain", "tram stop"]


def test_local_tag_provider_is_configured_without_llm_key(monkeypatch) -> None:
    monkeypatch.setenv("NCC_TAG_PROVIDER", "local")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    settings = AppSettings.from_env()

    assert settings.tag.provider.value == "local"
    assert settings.tag.configured is True
    assert settings.tag.credential_env is None


def test_deepseek_tag_provider_reports_candidate_extraction_not_final_prompt(monkeypatch) -> None:
    monkeypatch.setenv("NCC_TAG_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-v4-pro")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

    settings = AppSettings.from_env()

    assert settings.tag.provider.value == "deepseek"
    assert settings.tag.configured is True
    assert settings.tag.credential_env == "DEEPSEEK_API_KEY"
    assert "local Danbooru compiler" in settings.tag.disclosure
    assert "deepseek" in settings.tag.disclosure
