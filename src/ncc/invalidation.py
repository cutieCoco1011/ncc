from __future__ import annotations

from .models import InvalidationEvent


EDIT_RULES: dict[str, list[str]] = {
    "character_settings": [
        "panel_specs",
        "prompt_ir",
        "nai_prompts",
        "image_candidates",
        "lettering",
        "export",
    ],
    "storyboard": [
        "panel_specs",
        "prompt_ir",
        "nai_prompts",
        "image_candidates",
        "lettering",
        "export",
    ],
    "panel_spec": ["prompt_ir", "nai_prompts", "image_candidates", "lettering", "export"],
    "prompt_ir": ["nai_prompts", "image_candidates", "lettering", "export"],
    "image_candidates": ["lettering", "export"],
    "candidate_selection": ["export"],
    "lettering": ["export"],
}


def invalidated_artifacts_for_edit(edit_type: str) -> list[str]:
    if edit_type not in EDIT_RULES:
        raise ValueError(f"unknown edit type: {edit_type}")
    return list(EDIT_RULES[edit_type])


def build_invalidation_event(edit_type: str, edited_ids: list[str] | None = None) -> InvalidationEvent:
    invalid_artifacts = invalidated_artifacts_for_edit(edit_type)
    return InvalidationEvent(
        edit_type=edit_type,
        edited_ids=edited_ids or [],
        invalid_artifacts=invalid_artifacts,
        reason=f"{edit_type} changed; refresh affected downstream artifacts manually.",
    )
