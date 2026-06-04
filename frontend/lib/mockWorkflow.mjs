export const defaultSource =
  "비 오는 밤, 하린은 낡은 전차 정류장에서 반짝이는 고양이 브로치를 주웠다. 브로치를 손에 쥐자 멈춰 있던 전광판이 푸르게 켜지고, 오래전 잃어버린 동생의 이름이 나타났다. 하린은 겁이 났지만 노란 우비의 모자를 고쳐 쓰고, 빗속에서 들려오는 작은 목소리를 따라 골목으로 들어갔다. 골목 끝에서 그림자 괴물이 동생의 기억을 삼키려 하자, 하린은 브로치를 들어 환한 빛을 터뜨렸다. 괴물이 사라지고 동생의 웃음소리가 돌아오자, 하린은 다시 만날 수 있다는 약속을 품고 첫 전차에 올랐다.";

const dialogue = [
  "이건... 누구 물건이지?",
  "동생 이름이 왜 여기 있어?",
  "무섭지만 확인해야 해.",
  "그 기억을 가져가지 마!",
  "빛나 줘, 제발!",
  "꼭 다시 만날 거야."
];

export function createWorkflow(source = defaultSource, panelCount = 6) {
  const panels = Array.from({ length: panelCount }, (_, index) => {
    const order = index + 1;
    return {
      id: `p${order}`,
      order,
      beat: splitSource(source, panelCount)[index],
      camera: ["롱샷", "클로즈업", "추적 미디엄샷", "로우앵글", "극적 클로즈업", "와이드 피날레"][index],
      composition: [
        "비 내리는 전차 정류장",
        "안경에 비친 푸른 전광판",
        "사선 빗줄기의 좁은 골목",
        "기억의 빛 위로 드리운 그림자",
        "브로치에서 터지는 빛",
        "첫 전차와 걷히는 비"
      ][index],
      visibleCharacters: order === 2 || order === 4 || order === 6 ? ["하린", "동생"] : ["하린"],
      dialogue: dialogue[index],
      invalid: false
    };
  });
  const candidates = panels.flatMap((panel) =>
    [1, 2, 3].map((candidateIndex) => ({
      id: `${panel.id}-c${candidateIndex}`,
      panelId: panel.id,
      seed: 4242 + panel.order * 100 + candidateIndex,
      qa: candidateIndex === 2 ? "주의" : "통과",
      selected: candidateIndex === 1,
      prompt: `vertical webtoon panel, ${panel.composition}, no rendered text`
    }))
  );
  return {
    source,
    panels,
    candidates,
    characters: [
      {
        id: "harin",
        name: "하린",
        visualLocks: ["검은 단발", "둥근 안경", "노란 우비"],
        forbidden: ["금발 장발", "파란 눈"]
      }
    ],
    invalidation: {
      panel_specs: false,
      prompt_ir: false,
      nai_prompts: false,
      image_candidates: false,
      export: false
    }
  };
}

export function editCharacter(workflow, characterId, patch) {
  return {
    ...workflow,
    characters: workflow.characters.map((character) =>
      character.id === characterId ? { ...character, ...patch } : character
    ),
    invalidation: {
      ...workflow.invalidation,
      panel_specs: true,
      prompt_ir: true,
      nai_prompts: true,
      image_candidates: true
    }
  };
}

export function editPanel(workflow, panelId, patch) {
  return {
    ...workflow,
    panels: workflow.panels.map((panel) => (panel.id === panelId ? { ...panel, ...patch, invalid: true } : panel)),
    invalidation: {
      ...workflow.invalidation,
      panel_specs: true,
      prompt_ir: true,
      nai_prompts: true,
      image_candidates: true
    }
  };
}

export function selectCandidate(workflow, panelId, candidateId) {
  return {
    ...workflow,
    candidates: workflow.candidates.map((candidate) =>
      candidate.panelId === panelId ? { ...candidate, selected: candidate.id === candidateId } : candidate
    ),
    invalidation: {
      ...workflow.invalidation,
      export: true
    }
  };
}

export function updateDialogue(workflow, panelId, text) {
  return {
    ...workflow,
    panels: workflow.panels.map((panel) => (panel.id === panelId ? { ...panel, dialogue: text } : panel)),
    invalidation: {
      ...workflow.invalidation,
      export: true
    }
  };
}

export function selectedCount(workflow) {
  return workflow.candidates.filter((candidate) => candidate.selected).length;
}

function splitSource(source, count) {
  const parts = source
    .split(/(?<=다\.)\s+/)
    .map((part) => part.trim())
    .filter(Boolean);
  while (parts.length < count) {
    parts.push(parts[parts.length - 1] || "하린이 다음 단서를 찾는다.");
  }
  return parts.slice(0, count);
}
