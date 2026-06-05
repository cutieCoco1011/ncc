"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  fetchArtifacts,
  fetchProviders,
  latestExportUrl,
  listProjects,
  patchBackendCharacter,
  patchBackendStoryboard,
  runBackendExport,
  runBackendLettering,
  runBackendPanelSpecs,
  runGoldPath,
  runStage,
  selectBackendCandidate,
  updateBackendLettering
} from "../lib/apiClient.mjs";
import { workflowFromArtifacts } from "../lib/artifactHydration.mjs";
import {
  createWorkflow,
  defaultSource,
  editCharacter,
  editPanel,
  selectCandidate,
  selectedCount,
  updateDialogue
} from "../lib/mockWorkflow.mjs";
import {
  providerModeLabel,
  providerModeNote,
  tagProviderModeLabel,
  tagProviderModeNote,
  workflowGuideSteps
} from "../lib/onboardingGuide.mjs";

export default function CreatorPage() {
  const [source, setSource] = useState(defaultSource);
  const [workflow, setWorkflow] = useState(() => createWorkflow(defaultSource));
  const [projectId, setProjectId] = useState("");
  const [activePanelId, setActivePanelId] = useState("p1");
  const [status, setStatus] = useState("샘플 미리보기 준비됨");
  const [exportUrl, setExportUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [letteringSaving, setLetteringSaving] = useState(false);
  const [providers, setProviders] = useState(null);
  const letteringSaveRef = useRef(Promise.resolve());
  const activePanel = workflow.panels.find((panel) => panel.id === activePanelId) || workflow.panels[0];
  const activeCandidates = workflow.candidates.filter((candidate) => candidate.panelId === activePanel.id);
  const activePreviewCandidate = activeCandidates.find((candidate) => candidate.selected) || activeCandidates[0];
  const selected = selectedCount(workflow);
  const tagProvider = providers?.tag;
  const imageProvider = providers?.image;
  const backendModeLabel = providerModeLabel(imageProvider);
  const tagModeLabel = tagProviderModeLabel(tagProvider);
  const modeLabel = projectId ? backendModeLabel : "샘플 미리보기";

  async function loadBackendArtifacts(nextProjectId = projectId) {
    if (!nextProjectId) return;
    const artifacts = await fetchArtifacts(nextProjectId);
    setWorkflow(workflowFromArtifacts(artifacts, nextProjectId));
    setActivePanelId((current) => artifacts.storyboard?.panels?.some((panel) => panel.panel_id === current) ? current : "p1");
  }

  async function runBackendGoldPath() {
    setBusy(true);
    setStatus("원본을 분석하고 이미지 후보를 생성하는 중");
    try {
      const result = await runGoldPath({ title: titleFromSource(source), source_text: source, panel_count: 6 });
      setProjectId(result.project_id);
      setExportUrl(latestExportUrl(result.project_id));
      await loadBackendArtifacts(result.project_id);
      setStatus(`PNG 준비됨: ${result.export_width}x${result.export_height}`);
    } catch (error) {
      setStatus(error.message);
    } finally {
      setBusy(false);
    }
  }

  async function openLatestProject() {
    setBusy(true);
    setStatus("최근 backend 프로젝트를 불러오는 중");
    try {
      const projects = await listProjects();
      if (!projects.length) {
        setStatus("불러올 backend 프로젝트가 없습니다");
        return;
      }
      const [latest] = [...projects].sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at));
      setProjectId(latest.project_id);
      setExportUrl(latestExportUrl(latest.project_id));
      await loadBackendArtifacts(latest.project_id);
      setStatus(`불러옴: ${latest.title}`);
    } catch (error) {
      setStatus(error.message);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (typeof window !== "undefined" && new window.URLSearchParams(window.location.search).get("latest") === "1") {
      openLatestProject();
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    fetchProviders()
      .then((nextProviders) => {
        if (!cancelled) setProviders(nextProviders);
      })
      .catch((error) => {
        if (!cancelled) setStatus(`provider 상태 확인 실패: ${error.message}`);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  function regenerateMock() {
    setProjectId("");
    setExportUrl("");
    setWorkflow(createWorkflow(source));
    setActivePanelId("p1");
    setStatus("샘플 미리보기 다시 생성됨");
  }

  async function handleSelect(candidate) {
    if (!projectId) {
      setWorkflow((current) => selectCandidate(current, candidate.panelId, candidate.id));
      return;
    }
    setBusy(true);
    try {
      await selectBackendCandidate(projectId, candidate.id);
      await loadBackendArtifacts(projectId);
      setStatus(`${candidate.id} 선택됨. PNG를 다시 내보내야 합니다.`);
    } catch (error) {
      setStatus(error.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleDialogue(panelId, text) {
    setWorkflow((current) => updateDialogue(current, panelId, text));
    if (!projectId) return;
    setLetteringSaving(true);
    const save = letteringSaveRef.current
      .catch(() => {})
      .then(() => updateBackendLettering(projectId, `${panelId}-speech`, { text }));
    letteringSaveRef.current = save;
    try {
      await save;
      setStatus("말풍선 수정됨. PNG를 다시 내보내야 합니다.");
    } catch (error) {
      setStatus(error.message);
    } finally {
      if (letteringSaveRef.current === save) {
        setLetteringSaving(false);
      }
    }
  }

  async function handleExport() {
    if (!projectId) {
      setStatus("PNG를 내보내려면 먼저 backend 생성 또는 최근 작업 열기를 실행하세요");
      return;
    }
    setBusy(true);
    try {
      await letteringSaveRef.current;
      await runBackendLettering(projectId);
      await runBackendExport(projectId);
      await loadBackendArtifacts(projectId);
      setExportUrl(latestExportUrl(projectId));
      setStatus("PNG export 갱신됨");
    } catch (error) {
      setStatus(error.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleRefreshPanelSpecs() {
    if (!projectId) {
      setStatus("패널을 다시 만들려면 먼저 backend 생성 또는 최근 작업 열기를 실행하세요");
      return;
    }
    setBusy(true);
    try {
      await runBackendPanelSpecs(projectId);
      await loadBackendArtifacts(projectId);
      setStatus("수정한 이야기에서 패널을 다시 만들었습니다");
    } catch (error) {
      setStatus(error.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleRefreshStage(stage) {
    if (!projectId) {
      setStatus("단계를 갱신하려면 먼저 backend 생성 또는 최근 작업 열기를 실행하세요");
      return;
    }
    setBusy(true);
    try {
      await runStage(projectId, stage);
      await loadBackendArtifacts(projectId);
      setStatus(`${stage} 갱신됨`);
    } catch (error) {
      setStatus(error.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <h1>ncc creator</h1>
          <p>짧은 한국어 장면을 이미지 후보와 말풍선이 있는 세로 웹툰 PNG로 만듭니다.</p>
        </div>
        <div className="metrics" aria-label="workflow status">
          <span>{workflow.panels.length} panels</span>
          <span>{workflow.candidates.length} candidates</span>
          <span>{selected} selected</span>
          <span>{tagModeLabel}</span>
          <span>{modeLabel}</span>
        </div>
      </header>

      <WorkflowGuide
        tagProvider={tagProvider}
        tagModeLabel={tagModeLabel}
        imageProvider={imageProvider}
        backendModeLabel={backendModeLabel}
      />

      <section className="workspace">
        <SourcePanel
          source={source}
          setSource={setSource}
          regenerateMock={regenerateMock}
          runBackendGoldPath={runBackendGoldPath}
          openLatestProject={openLatestProject}
          busy={busy}
          status={status}
          tagProvider={tagProvider}
          imageProvider={imageProvider}
        />
        <ReviewPanel
          workflow={workflow}
          setWorkflow={setWorkflow}
          projectId={projectId}
          reload={loadBackendArtifacts}
          setStatus={setStatus}
          refreshPanelSpecs={handleRefreshPanelSpecs}
          refreshStage={handleRefreshStage}
        />
        <CandidatePanel
          panels={workflow.panels}
          activePanelId={activePanelId}
          setActivePanelId={setActivePanelId}
          activeCandidates={activeCandidates}
          onSelect={handleSelect}
          busy={busy || letteringSaving}
        />
        <LetteringPanel
          panel={activePanel}
          candidate={activePreviewCandidate}
          onDialogue={handleDialogue}
          onExport={handleExport}
          busy={busy || letteringSaving}
          exportUrl={exportUrl}
        />
      </section>
    </main>
  );
}

function titleFromSource(source) {
  const [firstSentence] = source.split(/(?<=[.!?。])\s+/);
  const title = (firstSentence || source).trim().replace(/\s+/g, " ").slice(0, 24);
  return title || "무제 프로젝트";
}

function WorkflowGuide({ tagProvider, tagModeLabel, imageProvider, backendModeLabel }) {
  return (
    <section className="workflow-guide" aria-label="처음 사용하는 순서">
      <div className="guide-intro">
        <strong>처음이라면 이 순서로 진행하세요</strong>
        <span>태그 변환: {tagModeLabel}. {tagProviderModeNote(tagProvider)}</span>
        <span>이미지 생성: {backendModeLabel}. {providerModeNote(imageProvider)}</span>
      </div>
      <ol className="guide-steps">
        {workflowGuideSteps.map((step, index) => (
          <li key={step.title}>
            <span>{index + 1}</span>
            <div>
              <strong>{step.title}</strong>
              <p>{step.detail}</p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

function SourcePanel({
  source,
  setSource,
  regenerateMock,
  runBackendGoldPath,
  openLatestProject,
  busy,
  status,
  tagProvider,
  imageProvider
}) {
  const backendActionLabel = imageProvider?.provider === "novelai" && imageProvider.configured
    ? "실제 이미지 생성"
    : "백엔드 mock 생성";
  return (
    <section className="pane source-pane">
      <div className="pane-title">
        <div>
          <h2>1. 원본 입력</h2>
          <p>장면을 붙여넣고 실제 결과가 필요하면 실제 이미지 생성을 실행하세요.</p>
        </div>
        <div className="button-row">
          <button onClick={regenerateMock} disabled={busy}>샘플 미리보기</button>
          <button onClick={openLatestProject} disabled={busy}>최근 작업 열기</button>
          <button className="primary-action" onClick={runBackendGoldPath} disabled={busy}>
            {backendActionLabel}
          </button>
        </div>
      </div>
      <textarea value={source} onChange={(event) => setSource(event.target.value)} />
      <p className="provider-note">태그 변환: {tagProviderModeNote(tagProvider)}</p>
      <p className="provider-note">이미지 생성: {providerModeNote(imageProvider)}</p>
      <div className="stage-strip">
        <span>이야기 분석</span>
        <span>캐릭터</span>
        <span>6패널</span>
        <span>프롬프트</span>
        <span>이미지 후보</span>
      </div>
      <p className="status-line">{status}</p>
    </section>
  );
}

function ReviewPanel({ workflow, setWorkflow, projectId, reload, setStatus, refreshPanelSpecs, refreshStage }) {
  const character = workflow.characters[0];
  async function persistCharacter(value) {
    setWorkflow((current) => editCharacter(current, character.id, { visualLocks: value.split(/,\s*/).filter(Boolean) }));
    if (!projectId) return;
    try {
      await patchBackendCharacter(projectId, character.id, { visual_lock_traits: value.split(/,\s*/).filter(Boolean) });
      await reload(projectId);
      setStatus("character edit saved; downstream artifacts invalidated");
    } catch (error) {
      setStatus(error.message);
    }
  }

  async function persistPanel(panel, value) {
    setWorkflow((current) => editPanel(current, panel.id, { beat: value }));
    if (!projectId) return;
    try {
      await patchBackendStoryboard(projectId, panel.id, { beat: value });
      await reload(projectId);
      setStatus(`${panel.id} storyboard edit saved; downstream artifacts invalidated`);
    } catch (error) {
      setStatus(error.message);
    }
  }

  return (
    <section className="pane review-pane">
      <div className="pane-title">
        <div>
          <h2>2. 이야기 확인</h2>
          <p>캐릭터와 패널 내용이 원본과 맞는지 확인합니다.</p>
        </div>
        <InvalidationBadges invalidation={workflow.invalidation} />
      </div>
      <label>
        캐릭터 고정 조건
        <input
          value={character.visualLocks.join(", ")}
          onChange={(event) =>
            setWorkflow((current) =>
              editCharacter(current, character.id, { visualLocks: event.target.value.split(/,\s*/).filter(Boolean) })
            )
          }
          onBlur={(event) => persistCharacter(event.target.value)}
        />
      </label>
      <div className="panel-list">
        {workflow.panels.map((panel) => (
          <label key={panel.id}>
            <span>{panel.order}</span>
            <input
              value={panel.beat}
              onChange={(event) => setWorkflow((current) => editPanel(current, panel.id, { beat: event.target.value }))}
              onBlur={(event) => persistPanel(panel, event.target.value)}
            />
          </label>
        ))}
      </div>
      <div className="refresh-grid">
        <button onClick={refreshPanelSpecs}>패널 다시 만들기</button>
        <button onClick={() => refreshStage("prompts")}>프롬프트 갱신</button>
        <button onClick={() => refreshStage("images")}>이미지 재생성</button>
        <button onClick={() => refreshStage("qa")}>후보 QA 갱신</button>
      </div>
    </section>
  );
}

function CandidatePanel({ panels, activePanelId, setActivePanelId, activeCandidates, onSelect, busy }) {
  return (
    <section className="pane candidates-pane">
      <div className="pane-title">
        <div>
          <h2>3. 후보 이미지 선택</h2>
          <p>패널 번호를 고른 뒤 후보 3장 중 export에 넣을 이미지를 선택합니다.</p>
        </div>
        <div className="segmented">
          {panels.map((panel) => (
            <button
              key={panel.id}
              className={panel.id === activePanelId ? "active" : ""}
              onClick={() => setActivePanelId(panel.id)}
            >
              {panel.order}
            </button>
          ))}
        </div>
      </div>
      <div className="candidate-grid">
        {activeCandidates.map((candidate) => (
          <button
            key={candidate.id}
            className={`candidate ${candidate.selected ? "selected" : ""}`}
            onClick={() => onSelect(candidate)}
            disabled={busy}
          >
            {candidate.imageUrl ? (
              <img className="thumb" src={candidate.imageUrl} alt={`${candidate.id} 후보 이미지`} />
            ) : (
              <span className="thumb" />
            )}
            <strong>{candidate.id}{candidate.selected ? " 선택됨" : ""}</strong>
            <small>seed {candidate.seed}</small>
            <small>{candidate.provider}{candidate.model ? ` / ${candidate.model}` : ""}</small>
            <small>{candidate.qa}</small>
          </button>
        ))}
      </div>
    </section>
  );
}

function LetteringPanel({ panel, candidate, onDialogue, onExport, busy, exportUrl }) {
  const preview = useMemo(() => ({ ...panel }), [panel]);
  return (
    <section className="pane lettering-pane">
      <div className="pane-title">
        <div>
          <h2>4. 말풍선과 PNG</h2>
          <p>말풍선 문구를 수정한 뒤 최신 선택으로 PNG를 내보냅니다.</p>
        </div>
        <button onClick={onExport} disabled={busy}>PNG Export</button>
      </div>
      <label>
        말풍선
        <input value={panel.dialogue} onChange={(event) => onDialogue(panel.id, event.target.value)} />
      </label>
      <CanvasPreview panel={preview} candidate={candidate} />
      {exportUrl ? (
        <a className="export-link" href={exportUrl} target="_blank" rel="noreferrer">
          PNG 열기
        </a>
      ) : null}
    </section>
  );
}

function CanvasPreview({ panel, candidate }) {
  const ref = useRef(null);
  useEffect(() => {
    const canvas = ref.current;
    const ctx = canvas.getContext("2d");
    let cancelled = false;

    function drawBase(image) {
      if (cancelled) return;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      if (image) {
        drawCoverImage(ctx, image, canvas.width, canvas.height);
      } else {
        ctx.fillStyle = "#4f6f7f";
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.strokeStyle = "#ffffff";
        ctx.lineWidth = 3;
        ctx.strokeRect(18, 18, canvas.width - 36, canvas.height - 36);
      }
      ctx.fillStyle = "#ffffff";
      ctx.beginPath();
      ctx.ellipse(160, 110, 116, 52, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = "#171717";
      ctx.stroke();
      ctx.fillStyle = "#171717";
      ctx.font = "18px system-ui, sans-serif";
      wrapCanvasText(ctx, panel.dialogue, 86, 94, 150, 24);
    }

    if (candidate?.imageUrl) {
      const image = new window.Image();
      image.onload = () => drawBase(image);
      image.onerror = () => drawBase(null);
      image.src = candidate.imageUrl;
    } else {
      drawBase(null);
    }

    return () => {
      cancelled = true;
    };
  }, [panel, candidate]);
  return <canvas ref={ref} width="320" height="360" aria-label="lettering preview" />;
}

function drawCoverImage(ctx, image, width, height) {
  const scale = Math.max(width / image.naturalWidth, height / image.naturalHeight);
  const drawWidth = image.naturalWidth * scale;
  const drawHeight = image.naturalHeight * scale;
  ctx.drawImage(image, (width - drawWidth) / 2, (height - drawHeight) / 2, drawWidth, drawHeight);
}

function InvalidationBadges({ invalidation }) {
  return (
    <div className="badges">
      {Object.entries(invalidation).map(([name, invalid]) => (
        <span key={name} className={invalid ? "invalid" : ""}>
          {name}
        </span>
      ))}
    </div>
  );
}

function wrapCanvasText(ctx, text, x, y, maxWidth, lineHeight) {
  const chars = [...text];
  let line = "";
  for (const char of chars) {
    const candidate = line + char;
    if (ctx.measureText(candidate).width > maxWidth && line) {
      ctx.fillText(line, x, y);
      line = char;
      y += lineHeight;
    } else {
      line = candidate;
    }
  }
  if (line) ctx.fillText(line, x, y);
}
