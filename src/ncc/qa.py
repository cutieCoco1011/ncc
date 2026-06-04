from __future__ import annotations

from .invalidation import build_invalidation_event
from .models import (
    CandidateImage,
    CandidateSet,
    CandidateState,
    CharacterBible,
    InvalidationEvent,
    QAFlag,
    QAStatus,
)


class CandidateQAService:
    def evaluate(self, candidates: CandidateSet, characters: CharacterBible) -> CandidateSet:
        character_by_id = {character.character_id: character for character in characters.characters}
        evaluated: list[CandidateImage] = []
        for candidate in candidates.candidates:
            combined_prompt = " ".join(
                [candidate.prompt.base_prompt]
                + list(candidate.prompt.character_prompts.values())
                + [candidate.prompt.undesired_prompt]
            ).lower()
            flags: list[QAFlag] = []
            for character_id, prompt_text in candidate.prompt.character_prompts.items():
                character = character_by_id.get(character_id)
                if not character:
                    flags.append(
                        QAFlag(
                            code="unknown_character",
                            message=f"Candidate references unknown character {character_id}.",
                            severity="error",
                        )
                    )
                    continue
                missing = [
                    trait for trait in character.visual_lock_traits if trait.lower() not in prompt_text.lower()
                ]
                for trait in missing:
                    flags.append(
                        QAFlag(
                            code="missing_visual_lock",
                            message=f"{character.name} is missing visual lock trait: {trait}.",
                            severity="warning",
                            provenance={"character_id": character_id},
                        )
                    )
                for trait in character.forbidden_traits:
                    if trait.lower() in candidate.prompt.base_prompt.lower() or trait.lower() in " ".join(
                        candidate.prompt.character_prompts.values()
                    ).lower():
                        flags.append(
                            QAFlag(
                                code="forbidden_trait_positive",
                                message=f"Forbidden trait appears in positive prompt: {trait}.",
                                severity="error",
                                provenance={"character_id": character_id},
                            )
                        )
                    elif trait.lower() in combined_prompt:
                        flags.append(
                            QAFlag(
                                code="forbidden_trait_guarded",
                                message=f"Forbidden trait is guarded in undesired prompt: {trait}.",
                                severity="info",
                                provenance={"character_id": character_id},
                            )
                        )
            status = QAStatus.PASS
            state = candidate.state
            if any(flag.severity == "error" for flag in flags):
                status = QAStatus.FAIL
                state = CandidateState.FLAGGED
            elif any(flag.severity == "warning" for flag in flags):
                status = QAStatus.WARN
                state = CandidateState.FLAGGED
            evaluated.append(candidate.model_copy(update={"qa_status": status, "qa_flags": flags, "state": state}))
        return CandidateSet(project_id=candidates.project_id, candidates=evaluated)


class SelectionService:
    def select_candidate(
        self, candidates: CandidateSet, panel_id: str, candidate_id: str
    ) -> tuple[CandidateSet, InvalidationEvent]:
        found = False
        updated: list[CandidateImage] = []
        for candidate in candidates.candidates:
            if candidate.panel_id != panel_id:
                updated.append(candidate)
                continue
            selected = candidate.candidate_id == candidate_id
            found = found or selected
            updated.append(
                candidate.model_copy(
                    update={
                        "selected": selected,
                        "state": _state_after_selection(candidate, selected),
                        "rejected_reason": None if selected else candidate.rejected_reason,
                    }
                )
            )
        if not found:
            raise ValueError(f"candidate {candidate_id} for panel {panel_id} does not exist")
        return (
            CandidateSet(project_id=candidates.project_id, candidates=updated),
            build_invalidation_event("candidate_selection", [candidate_id]),
        )

    def reject_candidate(self, candidates: CandidateSet, candidate_id: str, reason: str) -> CandidateSet:
        updated: list[CandidateImage] = []
        found = False
        for candidate in candidates.candidates:
            if candidate.candidate_id == candidate_id:
                found = True
                updated.append(
                    candidate.model_copy(
                        update={
                            "selected": False,
                            "state": CandidateState.REJECTED,
                            "rejected_reason": reason,
                        }
                    )
                )
            else:
                updated.append(candidate)
        if not found:
            raise ValueError(f"candidate {candidate_id} does not exist")
        return CandidateSet(project_id=candidates.project_id, candidates=updated)

    def select_first_per_panel(self, candidates: CandidateSet) -> tuple[CandidateSet, list[InvalidationEvent]]:
        selected = candidates
        events: list[InvalidationEvent] = []
        for panel_id, panel_candidates in sorted(candidates.by_panel().items()):
            selected, event = self.select_candidate(selected, panel_id, panel_candidates[0].candidate_id)
            events.append(event)
        return selected, events


def _state_after_selection(candidate: CandidateImage, selected: bool) -> CandidateState:
    if selected:
        return CandidateState.SELECTED
    if candidate.state == CandidateState.SELECTED:
        return CandidateState.GENERATED
    return candidate.state
