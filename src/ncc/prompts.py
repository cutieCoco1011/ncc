from __future__ import annotations

from .models import (
    CharacterBible,
    NAIPrompt,
    NAIPromptSet,
    PanelSpecSet,
    PromptIR,
    PromptIRSet,
    TagCandidate,
)


class StaticTagProvider:
    def tags_for_panel(self, panel_id: str, beat: str, emotion: str) -> list[TagCandidate]:
        base_tags = [
            ("vertical webtoon panel", 0.99),
            ("cinematic composition", 0.88),
            ("dramatic lighting", 0.8),
            (emotion, 0.72),
        ]
        keyword_tags = [
            (("비", "빗", "폭풍"), "rain", 0.86),
            (("괴물", "그림자", "monster"), "shadow creature", 0.82),
            (("전차", "정류장"), "tram stop", 0.85),
            (("도서관", "서가", "책"), "library", 0.84),
            (("열쇠",), "silver key", 0.82),
            (("별", "천문도"), "starlight", 0.82),
            (("지하철", "승강장", "플랫폼"), "subway station", 0.84),
            (("사탕",), "glowing candy", 0.8),
            (("바닷가", "파도", "방파제"), "winter seaside", 0.84),
            (("등대",), "lighthouse", 0.84),
            (("엽서", "우체통"), "postcard", 0.8),
            (("우산",), "umbrella", 0.8),
            (("문구점", "잉크"), "stationery shop", 0.8),
        ]
        for keywords, tag, confidence in keyword_tags:
            if any(keyword in beat for keyword in keywords):
                base_tags.append((tag, confidence))
        return [
            TagCandidate(tag=tag, source="static-mock", confidence=confidence, provenance={"panel_id": panel_id})
            for tag, confidence in base_tags
        ]


class PromptCompiler:
    def __init__(self, tag_provider: StaticTagProvider | None = None) -> None:
        self.tag_provider = tag_provider or StaticTagProvider()

    def build_prompt_ir(
        self,
        project_id: str,
        panel_specs: PanelSpecSet,
        characters: CharacterBible,
    ) -> PromptIRSet:
        character_by_id = {character.character_id: character for character in characters.characters}
        prompts: list[PromptIR] = []
        for panel in panel_specs.panels:
            tag_candidates = self.tag_provider.tags_for_panel(panel.panel_id, panel.beat, panel.emotion)
            character_prompts: dict[str, list[str]] = {}
            character_undesired: dict[str, list[str]] = {}
            for character_id in panel.visible_character_ids:
                if character_id not in character_by_id:
                    raise ValueError(f"panel {panel.panel_id} references unknown character: {character_id}")
                character = character_by_id[character_id]
                positive = _dedupe(character.visual_lock_traits + character.positive_tags)
                forbidden = _dedupe(character.forbidden_traits + character.negative_tags)
                character_prompts[character_id] = [tag for tag in positive if tag not in forbidden]
                character_undesired[character_id] = forbidden
            base_prompt = _dedupe(
                [
                    "anime webtoon illustration",
                    "full color comic panel",
                    "clear readable scene",
                    "balanced lighting",
                    "protagonist clearly visible",
                    "single protagonist only",
                    "consistent character design",
                    panel.setting,
                    panel.camera,
                    panel.composition,
                    panel.emotion,
                    "clean webtoon background",
                    "no rendered text",
                ]
                + [candidate.tag for candidate in tag_candidates]
            )
            prompts.append(
                PromptIR(
                    panel_id=panel.panel_id,
                    base_prompt=base_prompt,
                    character_prompts=character_prompts,
                    global_undesired=[
                        "text",
                        "watermark",
                        "logo",
                        "speech bubble text",
                        "overly dark",
                        "black frame",
                        "empty scene",
                        "silhouette only",
                        "low contrast",
                        "missing protagonist",
                        "gender swap",
                        "different character",
                    ],
                    character_undesired=character_undesired,
                    tag_candidates=tag_candidates,
                    priority_metadata={
                        "visual_locks": {
                            character_id: character_by_id[character_id].visual_lock_traits
                            for character_id in panel.visible_character_ids
                        },
                        "dialogue_kept_for_lettering": bool(panel.dialogue or panel.caption),
                    },
                    source_revision=panel_specs.source_hash,
                )
            )
        return PromptIRSet(project_id=project_id, prompts=prompts)

    def compile_nai_prompts(self, project_id: str, prompt_ir: PromptIRSet) -> NAIPromptSet:
        prompts: list[NAIPrompt] = []
        for index, ir in enumerate(prompt_ir.prompts):
            character_prompts = {
                character_id: ", ".join(tokens) for character_id, tokens in ir.character_prompts.items()
            }
            undesired = _dedupe(
                ir.global_undesired
                + [token for tokens in ir.character_undesired.values() for token in tokens]
            )
            prompts.append(
                NAIPrompt(
                    panel_id=ir.panel_id,
                    base_prompt=", ".join(ir.base_prompt),
                    character_prompts=character_prompts,
                    undesired_prompt=", ".join(undesired),
                    seed=4242 + index * 101,
                    settings={
                        "width": 832,
                        "height": 1216,
                        "steps": 28,
                        "scale": 6.5,
                        "sampler": "k_euler_ancestral",
                    },
                    reference_metadata={"compiler": "ncc-v1", "source_revision": ir.source_revision},
                )
            )
        return NAIPromptSet(project_id=project_id, prompts=prompts)


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
