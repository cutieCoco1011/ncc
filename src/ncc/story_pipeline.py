from __future__ import annotations

import re
from dataclasses import dataclass

from .models import (
    CharacterBible,
    CharacterProfile,
    PanelSpec,
    PanelSpecSet,
    ProviderKind,
    StoryAnalysis,
    Storyboard,
    StoryboardPanel,
    text_hash,
)


@dataclass(frozen=True)
class StoryBundle:
    analysis: StoryAnalysis
    characters: CharacterBible
    storyboard: Storyboard
    panel_specs: PanelSpecSet


class MockLLMStoryProvider:
    disclosure = "Mock LLM runs locally; no source text is sent externally."

    def analyze(self, project_id: str, source_text: str, panel_count: int = 6) -> StoryBundle:
        if not 4 <= panel_count <= 8:
            raise ValueError("panel_count must be between 4 and 8")
        source_revision = text_hash(source_text)
        events = _extract_events(source_text, panel_count)
        emotions = _emotional_arc(panel_count)
        primary = _infer_primary_character(source_text)
        support = _infer_supporting_character(source_text)
        analysis = StoryAnalysis(
            project_id=project_id,
            source_hash=source_revision,
            summary=_summary_for_source(primary["name"], events),
            event_order=events,
            emotional_progression=emotions,
            provider=ProviderKind.MOCK,
            provider_metadata={
                "provider": "mock",
                "panel_count": panel_count,
                "primary_character": primary["name"],
            },
        )
        character_profiles = [
            CharacterProfile(
                character_id=primary["character_id"],
                name=primary["name"],
                aliases=primary["aliases"],
                visual_lock_traits=primary["visual_lock_traits"],
                allowed_variations=primary["allowed_variations"],
                forbidden_traits=primary["forbidden_traits"],
                voice_personality_summary=primary["voice_personality_summary"],
                positive_tags=primary["positive_tags"],
                negative_tags=primary["negative_tags"],
            )
        ]
        if support is not None:
            character_profiles.append(
                CharacterProfile(
                    character_id=support["character_id"],
                    name=support["name"],
                    aliases=support["aliases"],
                    visual_lock_traits=support["visual_lock_traits"],
                    allowed_variations=support["allowed_variations"],
                    forbidden_traits=support["forbidden_traits"],
                    voice_personality_summary=support["voice_personality_summary"],
                    positive_tags=support["positive_tags"],
                    negative_tags=support["negative_tags"],
                )
            )
        characters = CharacterBible(
            project_id=project_id,
            source_hash=source_revision,
            characters=character_profiles,
        )
        storyboard_panels = _build_storyboard_panels(events, emotions, primary["character_id"], support)
        storyboard = Storyboard(project_id=project_id, source_hash=source_revision, panels=storyboard_panels)
        panel_specs = PanelSpecSet(
            project_id=project_id,
            source_hash=source_revision,
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
                    caption=panel.caption,
                    source_panel_id=panel.panel_id,
                )
                for panel in storyboard_panels
            ],
        )
        return StoryBundle(
            analysis=analysis,
            characters=characters,
            storyboard=storyboard,
            panel_specs=panel_specs,
        )


def panel_specs_from_storyboard(project_id: str, source_hash: str, storyboard: Storyboard) -> PanelSpecSet:
    return PanelSpecSet(
        project_id=project_id,
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
                caption=panel.caption,
                source_panel_id=panel.panel_id,
            )
            for panel in storyboard.panels
        ],
    )


def _extract_events(source_text: str, panel_count: int) -> list[str]:
    sentences = [part.strip() for part in re.split(r"(?<=[.!?。])\s+", source_text) if part.strip()]
    fallback = [
        "비 오는 정류장에서 브로치를 줍는다.",
        "전광판이 동생의 이름으로 켜진다.",
        "하린이 빗속의 목소리를 따라간다.",
        "그림자 괴물이 기억을 삼키려 한다.",
        "브로치의 빛으로 괴물을 몰아낸다.",
        "하린이 다시 만날 약속을 품고 전차에 오른다.",
    ]
    events = sentences or fallback
    while len(events) < panel_count:
        events.append(_followup_event(events[-1], len(events) + 1) if sentences else fallback[len(events) % len(fallback)])
    return events[:panel_count]


def _followup_event(previous_event: str, order: int) -> str:
    stem = previous_event.rstrip(".!?。 ")
    if order >= 6:
        return f"{stem} 이후, 주인공은 남은 여운을 안고 다음 약속을 준비한다."
    return f"{stem} 이후 이어지는 단서를 확인한다."


def _emotional_arc(panel_count: int) -> list[str]:
    arc = ["호기심", "불안", "결심", "공포", "용기", "안도", "희망", "여운"]
    return arc[:panel_count]


def _infer_primary_character(source_text: str) -> dict[str, object]:
    name = _first_korean_name(source_text) or "주인공"
    if name == "하린":
        return {
            "character_id": "harin",
            "name": "하린",
            "aliases": ["주인공", "노란 우비의 아이"],
            "visual_lock_traits": ["short black hair", "round glasses", "yellow raincoat"],
            "allowed_variations": ["wet hair", "determined expression", "rain droplets"],
            "forbidden_traits": ["long blond hair", "blue eyes", "adult woman"],
            "voice_personality_summary": "겁이 나도 단서를 따라가는 조심스럽고 용감한 아이.",
            "positive_tags": ["short black hair", "round glasses", "yellow raincoat", "child"],
            "negative_tags": ["long blond hair", "blue eyes", "adult woman"],
        }

    stable_traits, stable_forbidden = _stable_primary_traits(source_text)
    outfit = _outfit_traits(source_text)
    return {
        "character_id": "main_character",
        "name": name,
        "aliases": ["주인공", f"{name}"],
        "visual_lock_traits": _dedupe(stable_traits + outfit),
        "allowed_variations": ["determined expression", "dynamic pose", "story-specific prop"],
        "forbidden_traits": _dedupe(
            [
                "male protagonist",
                "boy",
                "adult man",
                "different protagonist",
                "inconsistent outfit",
                "different hair color",
                "extra fingers",
            ]
            + stable_forbidden
        ),
        "voice_personality_summary": f"{name}은 단서를 따라가며 두려움보다 결심을 선택하는 인물.",
        "positive_tags": _dedupe(stable_traits + outfit),
        "negative_tags": _dedupe(
            [
                "male protagonist",
                "boy",
                "adult man",
                "different protagonist",
                "inconsistent outfit",
                "different hair color",
                "extra fingers",
            ]
            + stable_forbidden
        ),
    }


def _first_korean_name(source_text: str) -> str | None:
    for match in re.finditer(r"([가-힣]{2,4})(?:은|는|이|가)\b", source_text):
        candidate = match.group(1)
        if candidate not in {"새벽", "막차", "겨울", "아침", "문장", "사탕", "엽서", "우산", "비가"}:
            return candidate
    return None


def _outfit_traits(source_text: str) -> list[str]:
    traits: list[str] = []
    keyword_traits = [
        ("노란 우비", "yellow raincoat"),
        ("붉은 목도리", "red scarf"),
        ("파란 운동화", "blue sneakers"),
        ("하얀 장갑", "white gloves"),
        ("우산", "umbrella prop"),
        ("열쇠", "silver key prop"),
        ("엽서", "postcard prop"),
        ("사탕", "glowing candy prop"),
        ("잉크", "starlight ink bottle prop"),
    ]
    for keyword, trait in keyword_traits:
        if keyword in source_text:
            traits.append(trait)
    return traits[:3] or ["distinct outfit", "short dark hair", "story prop"]


def _stable_primary_traits(source_text: str) -> tuple[list[str], list[str]]:
    base = ["same female protagonist in every panel", "Korean teenage girl", "expressive dark eyes"]
    if "붉은 목도리" in source_text:
        return (
            base + ["short dark bob hair", "red scarf", "navy winter coat"],
            ["white hair", "silver hair", "long blond hair", "staff", "wand"],
        )
    if "파란 운동화" in source_text or "사탕" in source_text:
        return (
            base + ["short brown bob hair", "white shirt", "dark skirt", "blue sneakers"],
            ["white hair", "silver hair", "long blond hair", "red scarf"],
        )
    if "하얀 장갑" in source_text or "엽서" in source_text:
        return (
            base + ["short black bob hair", "teal winter coat", "white gloves"],
            ["white hair", "silver hair", "long blond hair", "red scarf"],
        )
    return (
        base + ["short dark bob hair", "distinct outfit"],
        ["white hair", "silver hair", "long blond hair"],
    )


def _infer_supporting_character(source_text: str) -> dict[str, object] | None:
    support_map = [
        ("동생", "younger_sibling", "동생", ["small silhouette", "soft smile", "blue light aura"]),
        ("할머니", "grandmother_memory", "할머니", ["warm silhouette", "gentle smile", "starlight aura"]),
        ("친구", "friend", "친구", ["distant friend", "soft expression", "letter recipient"]),
        ("등대지기", "lighthouse_keeper", "등대지기", ["distant lighthouse keeper", "storm coat", "lantern glow"]),
    ]
    for keyword, character_id, name, visual_traits in support_map:
        if keyword in source_text:
            return {
                "character_id": character_id,
                "name": name,
                "aliases": [keyword, f"{keyword}의 기억"],
                "visual_lock_traits": visual_traits,
                "allowed_variations": ["memory fragment", "distant figure"],
                "forbidden_traits": ["villain", "monster face", "extra fingers"],
                "voice_personality_summary": f"{name}은 이야기의 감정적 단서로 등장한다.",
                "positive_tags": visual_traits,
                "negative_tags": ["villain", "monster face", "extra fingers"],
            }
    return None


def _summary_for_source(primary_name: str, events: list[str]) -> str:
    first_event = events[0] if events else "단서를 발견한다."
    return f"{primary_name}이 {first_event} 이후 이어지는 단서를 따라가는 이야기."


def _build_storyboard_panels(
    events: list[str],
    emotions: list[str],
    primary_character_id: str,
    support: dict[str, object] | None,
) -> list[StoryboardPanel]:
    cameras = [
        "medium shot with foreground object",
        "close-up",
        "medium tracking shot",
        "low angle",
        "dramatic close-up",
        "wide vertical finale",
        "soft profile shot",
        "quiet pullback",
    ]
    panels: list[StoryboardPanel] = []
    story_setting = _setting_for_event(" ".join(events))
    for index, event in enumerate(events):
        order = index + 1
        setting = _setting_for_event(event)
        if setting == "Korean urban fantasy scene":
            setting = story_setting
        visible = [primary_character_id]
        if support is not None and order in {2, 4, 6, 7}:
            visible.append(str(support["character_id"]))
        panels.append(
            StoryboardPanel(
                panel_id=f"p{order}",
                order=order,
                beat=event,
                camera=cameras[index],
                composition=_composition_for_event(event, setting, order),
                visible_characters=visible,
                setting=setting,
                emotion=emotions[index],
                draft_dialogue=_dialogue_for_event(event, order),
                caption="" if order != 1 else _caption_for_event(event),
            )
        )
    return panels


def _setting_for_event(event: str) -> str:
    setting_keywords = [
        (("도서관", "서가", "책"), "quiet dawn library and tall bookshelves"),
        (("문구점", "잉크", "편지"), "dawn stationery shop and narrow alley"),
        (("지하철", "승강장", "플랫폼"), "empty late-night subway platform"),
        (("바닷가", "등대", "방파제", "우체통"), "winter seaside, breakwater, and lighthouse"),
        (("한강", "다리", "우산"), "rainy riverside under a Han River bridge"),
        (("전차", "정류장", "골목"), "rainy old tram stop and narrow alley"),
    ]
    for keywords, setting in setting_keywords:
        if any(_keyword_present(keyword, event) for keyword in keywords):
            return setting
    return "Korean urban fantasy scene"


def _composition_for_event(event: str, setting: str, order: int) -> str:
    motifs = [
        ("열쇠", "protagonist holding a glowing silver key, silver key clearly visible in hand"),
        ("천문도", "star chart spreading across the wall"),
        ("서가", "deep bookshelves framing the protagonist"),
        ("사탕", "protagonist holding transparent glowing candy, candy clearly visible in hand"),
        ("플랫폼", "empty platform lines leading into darkness"),
        ("노선도", "subway map returning in bright fragments"),
        ("엽서", "protagonist holding a dry postcard beside a rusted mailbox, postcard clearly visible"),
        ("등대", "lighthouse beam cutting through storm air"),
        ("우체통", "rusted mailbox beside foaming waves"),
        ("우산", "umbrella reversing falling rain"),
        ("브로치", "glowing brooch foreground"),
        ("전광판", "blue station display reflecting in glasses"),
        ("괴물", "shadow creature looming over memory light"),
    ]
    for keyword, motif in motifs:
        if _keyword_present(keyword, event):
            return f"{setting}, {motif}, protagonist clearly visible, readable webtoon panel"
    if order == 1:
        return f"{setting}, object discovery foreground, protagonist clearly visible, readable webtoon panel"
    if order >= 5:
        return f"{setting}, vertical finale with hopeful light, protagonist clearly visible, readable webtoon panel"
    return f"{setting}, cinematic webtoon composition, protagonist clearly visible, readable webtoon panel"


def _dialogue_for_event(event: str, order: int) -> str:
    if "열쇠" in event:
        return "이 열쇠가 왜 여기에..."
    if "사탕" in event:
        return "이 사탕, 이상하게 빛나."
    if "엽서" in event:
        return "젖지 않은 엽서라니..."
    if "우산" in event:
        return "빗방울이 거꾸로 올라가."
    if "잉크" in event:
        return "글자가 하늘에 떠올랐어."
    if "동생" in event:
        return "동생 이름이 왜 여기 있어?"
    if "괴물" in event or "그림자" in event:
        return "그걸 가져가지 마!"
    if order >= 5:
        return "이제 답을 찾을 수 있어."
    return "확인해 봐야 해."


def _caption_for_event(event: str) -> str:
    if _keyword_present("바닷가", event):
        return "겨울 바닷가, 낡은 우체통."
    if _keyword_present("지하철", event):
        return "막차가 끊긴 지하철역."
    if _keyword_present("도서관", event):
        return "새벽 도서관, 조용한 서가."
    if _keyword_present("문구점", event):
        return "새벽 문구점의 불빛."
    return "이야기가 시작된 밤."


def _keyword_present(keyword: str, text: str) -> bool:
    return any(
        not _korean_keyword_negated(text, match.span())
        for match in re.finditer(re.escape(keyword), text)
    )


def _korean_keyword_negated(text: str, span: tuple[int, int]) -> bool:
    start, end = span
    before = text[max(0, start - 32):start]
    after = text[end:min(len(text), end + 32)]
    if re.search(r"(?:없는|없이|아닌|제외한|빼고)\s*$", before):
        return True
    return (
        re.match(
            r"\s*(?:[은는이가을를와과에의로도만]\s*){0,2}"
            r"(?:아닌|아니다|아니고|아니며|아니지만|없(?:는|다|고|어|어서|지만)?|없이|말고|제외)",
            after,
        )
        is not None
    )


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = value.strip()
        key = normalized.lower()
        if normalized and key not in seen:
            seen.add(key)
            result.append(normalized)
    return result
