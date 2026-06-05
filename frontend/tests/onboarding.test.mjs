import assert from "node:assert/strict";
import test from "node:test";

import { fetchProviders } from "../lib/apiClient.mjs";
import { providerModeLabel, providerModeNote, workflowGuideSteps } from "../lib/onboardingGuide.mjs";

test("onboarding guide exposes the whole creator workflow", () => {
  assert.deepEqual(
    workflowGuideSteps.map((step) => step.title),
    ["원본 입력", "이야기 확인", "후보 선택", "말풍선과 PNG"]
  );
  assert.ok(workflowGuideSteps[2].detail.includes("후보 3장"));
  assert.ok(workflowGuideSteps[3].detail.includes("PNG"));
});

test("provider copy clearly separates mock from real NovelAI generation", () => {
  const novelai = {
    provider: "novelai",
    configured: true,
    disclosure: "Prompts may be sent to NovelAI."
  };
  const mock = {
    provider: "mock",
    configured: true,
    disclosure: "Mock generation runs locally."
  };

  assert.equal(providerModeLabel(novelai), "실제 NovelAI");
  assert.match(providerModeNote(novelai), /NovelAI/);
  assert.equal(providerModeLabel(mock), "backend mock");
  assert.match(providerModeNote(mock), /흐름 점검용 샘플 이미지/);
  assert.match(providerModeNote(mock), /실제 NovelAI 생성/);
});

test("fetchProviders reads backend provider status", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url) => {
    assert.equal(url, "http://example.test/providers");
    return {
      ok: true,
      async json() {
        return { image: { provider: "novelai", configured: true } };
      }
    };
  };
  try {
    const providers = await fetchProviders("http://example.test");
    assert.equal(providers.image.provider, "novelai");
  } finally {
    globalThis.fetch = originalFetch;
  }
});
