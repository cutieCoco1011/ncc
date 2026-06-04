import assert from "node:assert/strict";
import test from "node:test";

import { workflowFromArtifacts } from "../lib/artifactHydration.mjs";
import {
  createWorkflow,
  editCharacter,
  editPanel,
  selectCandidate,
  selectedCount,
  updateDialogue
} from "../lib/mockWorkflow.mjs";

test("mock creator workflow starts with six panels and eighteen candidates", () => {
  const workflow = createWorkflow();
  assert.equal(workflow.panels.length, 6);
  assert.equal(workflow.candidates.length, 18);
  assert.equal(selectedCount(workflow), 6);
  assert.ok(workflow.panels[0].dialogue.includes("물건"));
});

test("artifact hydration uses persisted lettering and backend invalidation", () => {
  const artifacts = {
    source: "source",
    project: {
      artifact_status: {
        panel_specs: "invalid",
        prompt_ir: "valid",
        nai_prompts: "valid",
        image_candidates: "valid",
        export: "invalid"
      }
    },
    characters: {
      characters: [
        {
          character_id: "harin",
          name: "하린",
          visual_lock_traits: ["short black hair", "round glasses", "yellow raincoat"],
          forbidden_traits: ["blue eyes"]
        }
      ]
    },
    storyboard: {
      panels: [
        {
          panel_id: "p1",
          order: 1,
          beat: "beat",
          camera: "close",
          composition: "tram stop",
          visible_characters: ["harin"],
          draft_dialogue: "초안 대사"
        }
      ]
    },
    image_candidates: {
      candidates: [
        {
          candidate_id: "p1-c1",
          panel_id: "p1",
          seed: 1,
          qa_status: "pass",
          selected: true,
          image_path: "images/p1_candidate_1.png",
          prompt: { base_prompt: "rain" }
        }
      ]
    },
    lettering: {
      balloons: [
        {
          balloon_id: "p1-speech",
          panel_id: "p1",
          kind: "speech",
          text: "저장된 말풍선"
        }
      ]
    }
  };
  const workflow = workflowFromArtifacts(artifacts, "demo");
  assert.equal(workflow.panels[0].dialogue, "저장된 말풍선");
  assert.equal(workflow.invalidation.panel_specs, true);
  assert.ok(workflow.candidates[0].imageUrl.includes("/projects/demo/files/images/p1_candidate_1.png"));
});

test("edits explicitly invalidate downstream artifacts", () => {
  const workflow = createWorkflow();
  const editedCharacter = editCharacter(workflow, "harin", { visualLocks: ["검은 단발", "둥근 안경", "노란 우비", "젖은 앞머리"] });
  assert.equal(editedCharacter.invalidation.image_candidates, true);

  const editedPanel = editPanel(workflow, "p2", { camera: "초근접" });
  assert.equal(editedPanel.invalidation.prompt_ir, true);

  const selected = selectCandidate(workflow, "p3", "p3-c2");
  assert.equal(selected.invalidation.export, true);
  assert.equal(selected.candidates.find((candidate) => candidate.id === "p3-c2").selected, true);

  const lettered = updateDialogue(workflow, "p1", "정말 반짝이잖아.");
  assert.equal(lettered.invalidation.export, true);
  assert.equal(lettered.panels[0].dialogue, "정말 반짝이잖아.");
});
