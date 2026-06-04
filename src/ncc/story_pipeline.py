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
        analysis = StoryAnalysis(
            project_id=project_id,
            source_hash=source_revision,
            summary="하린이 비 오는 밤 브로치를 따라 잃어버린 동생의 기억을 되찾는 이야기.",
            event_order=events,
            emotional_progression=emotions,
            provider=ProviderKind.MOCK,
            provider_metadata={"provider": "mock", "panel_count": panel_count},
        )
        characters = CharacterBible(
            project_id=project_id,
            source_hash=source_revision,
            characters=[
                CharacterProfile(
                    character_id="harin",
                    name="하린",
                    aliases=["주인공", "노란 우비의 아이"],
                    visual_lock_traits=["short black hair", "round glasses", "yellow raincoat"],
                    allowed_variations=["wet hair", "determined expression", "rain droplets"],
                    forbidden_traits=["long blond hair", "blue eyes", "adult woman"],
                    voice_personality_summary="겁이 나도 단서를 따라가는 조심스럽고 용감한 아이.",
                    positive_tags=["short black hair", "round glasses", "yellow raincoat", "child"],
                    negative_tags=["long blond hair", "blue eyes", "adult woman"],
                ),
                CharacterProfile(
                    character_id="younger_sibling",
                    name="동생",
                    aliases=["잃어버린 동생", "전광판의 이름"],
                    visual_lock_traits=["small silhouette", "soft smile", "blue light aura"],
                    allowed_variations=["memory fragment", "distant figure"],
                    forbidden_traits=["villain", "monster face", "older adult"],
                    voice_personality_summary="희미하지만 따뜻한 목소리로 하린을 부른다.",
                    positive_tags=["small silhouette", "soft smile", "blue light aura"],
                    negative_tags=["villain", "monster face", "older adult"],
                ),
            ],
        )
        storyboard_panels = _build_storyboard_panels(events, emotions)
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
        events.append(fallback[len(events) % len(fallback)])
    return events[:panel_count]


def _emotional_arc(panel_count: int) -> list[str]:
    arc = ["호기심", "불안", "결심", "공포", "용기", "안도", "희망", "여운"]
    return arc[:panel_count]


def _build_storyboard_panels(events: list[str], emotions: list[str]) -> list[StoryboardPanel]:
    cameras = [
        "establishing long shot",
        "close-up",
        "medium tracking shot",
        "low angle",
        "dramatic close-up",
        "wide vertical finale",
        "soft profile shot",
        "quiet pullback",
    ]
    compositions = [
        "rainy tram stop with glowing brooch foreground",
        "blue station display reflecting in glasses",
        "narrow alley with diagonal rain lines",
        "shadow monster looming over memory light",
        "brooch light burst centered around Harin",
        "first tram arriving under clearing rain",
        "memory silhouette fading warmly",
        "empty stop with hopeful morning color",
    ]
    dialogues = [
        "이건... 누구 물건이지?",
        "동생 이름이 왜 여기 있어?",
        "무섭지만 확인해야 해.",
        "그 기억을 가져가지 마!",
        "빛나 줘, 제발!",
        "꼭 다시 만날 거야.",
        "내 목소리 들려?",
        "비가 그쳤어.",
    ]
    panels: list[StoryboardPanel] = []
    for index, event in enumerate(events):
        order = index + 1
        visible = ["harin"]
        if order in {2, 4, 6, 7}:
            visible.append("younger_sibling")
        panels.append(
            StoryboardPanel(
                panel_id=f"p{order}",
                order=order,
                beat=event,
                camera=cameras[index],
                composition=compositions[index],
                visible_characters=visible,
                setting="rainy old tram stop and narrow alley",
                emotion=emotions[index],
                draft_dialogue=dialogues[index],
                caption="" if order != 1 else "비 오는 밤, 낡은 정류장.",
            )
        )
    return panels
