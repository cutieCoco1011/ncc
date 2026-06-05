export const workflowGuideSteps = [
  {
    title: "원본 입력",
    detail: "짧은 한국어 장면 4~8문장을 붙여넣습니다."
  },
  {
    title: "이야기 확인",
    detail: "캐릭터 고정 조건과 6개 패널 장면이 맞는지 봅니다."
  },
  {
    title: "후보 선택",
    detail: "패널마다 이미지 후보 3장 중 export에 쓸 1장을 고릅니다."
  },
  {
    title: "말풍선과 PNG",
    detail: "한국어 말풍선을 수정하고 세로 웹툰 PNG를 내보냅니다."
  }
];

export function providerModeLabel(imageProvider) {
  if (!imageProvider) return "backend 확인 중";
  if (imageProvider.provider === "novelai" && imageProvider.configured) return "실제 NovelAI";
  if (imageProvider.provider === "mock") return "backend mock";
  if (!imageProvider.configured) return "image provider 미설정";
  return imageProvider.provider;
}

export function providerModeNote(imageProvider) {
  if (!imageProvider) return "backend provider 상태를 불러오는 중입니다.";
  if (imageProvider.provider === "novelai" && imageProvider.configured) {
    return "실제 이미지 생성은 NovelAI로 프롬프트를 보내며, 결과 후보 PNG를 로컬 프로젝트에 저장합니다.";
  }
  if (imageProvider.provider === "mock") {
    return "backend mock은 흐름 점검용 샘플 이미지입니다. 최종 이미지 품질 확인에는 실제 NovelAI 생성이 필요합니다.";
  }
  if (!imageProvider.configured) {
    return `${imageProvider.credential_env || "image credential"} 설정 후 실제 이미지 생성을 실행할 수 있습니다.`;
  }
  return imageProvider.disclosure || "선택된 backend image provider로 이미지 후보를 생성합니다.";
}
