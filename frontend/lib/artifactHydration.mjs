import { projectFileUrl } from "./apiClient.mjs";

export function workflowFromArtifacts(artifacts, projectId) {
  const speechByPanel = new Map(
    (artifacts.lettering?.balloons || [])
      .filter((balloon) => balloon.kind === "speech")
      .map((balloon) => [balloon.panel_id, balloon.text])
  );
  const panels = artifacts.storyboard.panels.map((panel) => ({
    id: panel.panel_id,
    order: panel.order,
    beat: panel.beat,
    camera: panel.camera,
    composition: panel.composition,
    visibleCharacters: panel.visible_characters,
    dialogue: speechByPanel.get(panel.panel_id) || panel.draft_dialogue,
    invalid: artifacts.project.artifact_status.panel_specs === "invalid"
  }));
  const characters = artifacts.characters.characters.map((character) => ({
    id: character.character_id,
    name: character.name,
    visualLocks: character.visual_lock_traits,
    forbidden: character.forbidden_traits
  }));
  const candidates = artifacts.image_candidates.candidates.map((candidate) => ({
    id: candidate.candidate_id,
    panelId: candidate.panel_id,
    seed: candidate.seed,
    qa: candidate.qa_status,
    selected: candidate.selected,
    prompt: candidate.prompt.base_prompt,
    imageUrl: projectFileUrl(projectId, candidate.image_path)
  }));
  const status = artifacts.project.artifact_status;
  return {
    source: artifacts.source,
    panels,
    characters,
    candidates,
    invalidation: {
      panel_specs: status.panel_specs === "invalid",
      prompt_ir: status.prompt_ir === "invalid",
      nai_prompts: status.nai_prompts === "invalid",
      image_candidates: status.image_candidates === "invalid",
      export: status.export === "invalid"
    }
  };
}
