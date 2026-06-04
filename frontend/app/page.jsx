"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  fetchArtifacts,
  latestExportUrl,
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

export default function CreatorPage() {
  const [source, setSource] = useState(defaultSource);
  const [workflow, setWorkflow] = useState(() => createWorkflow(defaultSource));
  const [projectId, setProjectId] = useState("");
  const [activePanelId, setActivePanelId] = useState("p1");
  const [status, setStatus] = useState("mock workflow ready");
  const [exportUrl, setExportUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const activePanel = workflow.panels.find((panel) => panel.id === activePanelId) || workflow.panels[0];
  const activeCandidates = workflow.candidates.filter((candidate) => candidate.panelId === activePanel.id);
  const selected = selectedCount(workflow);

  async function loadBackendArtifacts(nextProjectId = projectId) {
    if (!nextProjectId) return;
    const artifacts = await fetchArtifacts(nextProjectId);
    setWorkflow(workflowFromArtifacts(artifacts, nextProjectId));
    setActivePanelId((current) => artifacts.storyboard?.panels?.some((panel) => panel.panel_id === current) ? current : "p1");
  }

  async function runBackendGoldPath() {
    setBusy(true);
    setStatus("backend gold path running");
    try {
      const result = await runGoldPath({ title: "비 오는 정류장의 약속", source_text: source, panel_count: 6 });
      setProjectId(result.project_id);
      setExportUrl(latestExportUrl(result.project_id));
      await loadBackendArtifacts(result.project_id);
      setStatus(`export ready: ${result.export_width}x${result.export_height}`);
    } catch (error) {
      setStatus(error.message);
    } finally {
      setBusy(false);
    }
  }

  function regenerateMock() {
    setProjectId("");
    setExportUrl("");
    setWorkflow(createWorkflow(source));
    setActivePanelId("p1");
    setStatus("mock workflow regenerated");
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
      setStatus(`${candidate.id} selected; export invalidated`);
    } catch (error) {
      setStatus(error.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleDialogue(panelId, text) {
    setWorkflow((current) => updateDialogue(current, panelId, text));
    if (!projectId) return;
    try {
      await updateBackendLettering(projectId, `${panelId}-speech`, { text });
      setStatus("lettering updated; export invalidated");
    } catch (error) {
      setStatus(error.message);
    }
  }

  async function handleExport() {
    if (!projectId) {
      setStatus("run backend gold path before exporting");
      return;
    }
    setBusy(true);
    try {
      await runBackendLettering(projectId);
      await runBackendExport(projectId);
      await loadBackendArtifacts(projectId);
      setExportUrl(latestExportUrl(projectId));
      setStatus("PNG export refreshed");
    } catch (error) {
      setStatus(error.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleRefreshPanelSpecs() {
    if (!projectId) {
      setStatus("run backend gold path before refreshing panel specs");
      return;
    }
    setBusy(true);
    try {
      await runBackendPanelSpecs(projectId);
      await loadBackendArtifacts(projectId);
      setStatus("panel specs refreshed from edited storyboard");
    } catch (error) {
      setStatus(error.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleRefreshStage(stage) {
    if (!projectId) {
      setStatus("run backend gold path before refreshing stages");
      return;
    }
    setBusy(true);
    try {
      await runStage(projectId, stage);
      await loadBackendArtifacts(projectId);
      setStatus(`${stage} refreshed`);
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
          <p>한국어 장면을 6패널 세로 웹툰으로 컴파일</p>
        </div>
        <div className="metrics" aria-label="workflow status">
          <span>{workflow.panels.length} panels</span>
          <span>{workflow.candidates.length} candidates</span>
          <span>{selected} selected</span>
          <span>{projectId ? "backend" : "mock"}</span>
        </div>
      </header>

      <section className="workspace">
        <SourcePanel
          source={source}
          setSource={setSource}
          regenerateMock={regenerateMock}
          runBackendGoldPath={runBackendGoldPath}
          busy={busy}
          status={status}
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
          busy={busy}
        />
        <LetteringPanel
          panel={activePanel}
          onDialogue={handleDialogue}
          onExport={handleExport}
          busy={busy}
          exportUrl={exportUrl}
        />
      </section>
    </main>
  );
}

function SourcePanel({ source, setSource, regenerateMock, runBackendGoldPath, busy, status }) {
  return (
    <section className="pane source-pane">
      <div className="pane-title">
        <h2>소스</h2>
        <div className="button-row">
          <button onClick={regenerateMock} disabled={busy}>mock</button>
          <button onClick={runBackendGoldPath} disabled={busy}>backend</button>
        </div>
      </div>
      <textarea value={source} onChange={(event) => setSource(event.target.value)} />
      <div className="stage-strip">
        <span>analysis</span>
        <span>characters</span>
        <span>storyboard</span>
        <span>prompts</span>
        <span>images</span>
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
        <h2>리뷰</h2>
        <InvalidationBadges invalidation={workflow.invalidation} />
      </div>
      <label>
        캐릭터 visual lock
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
        <button onClick={refreshPanelSpecs}>panel specs refresh</button>
        <button onClick={() => refreshStage("prompts")}>prompts refresh</button>
        <button onClick={() => refreshStage("images")}>images refresh</button>
        <button onClick={() => refreshStage("qa")}>QA refresh</button>
      </div>
    </section>
  );
}

function CandidatePanel({ panels, activePanelId, setActivePanelId, activeCandidates, onSelect, busy }) {
  return (
    <section className="pane candidates-pane">
      <div className="pane-title">
        <h2>후보 선택</h2>
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
            {candidate.imageUrl ? <img className="thumb" src={candidate.imageUrl} alt="" /> : <span className="thumb" />}
            <strong>{candidate.id}</strong>
            <small>seed {candidate.seed}</small>
            <small>{candidate.provider}{candidate.model ? ` / ${candidate.model}` : ""}</small>
            <small>{candidate.qa}</small>
          </button>
        ))}
      </div>
    </section>
  );
}

function LetteringPanel({ panel, onDialogue, onExport, busy, exportUrl }) {
  const preview = useMemo(() => ({ ...panel }), [panel]);
  return (
    <section className="pane lettering-pane">
      <div className="pane-title">
        <h2>레터링</h2>
        <button onClick={onExport} disabled={busy}>PNG Export</button>
      </div>
      <label>
        말풍선
        <input value={panel.dialogue} onChange={(event) => onDialogue(panel.id, event.target.value)} />
      </label>
      <CanvasPreview panel={preview} />
      {exportUrl ? (
        <a className="export-link" href={exportUrl} target="_blank" rel="noreferrer">
          export file
        </a>
      ) : null}
    </section>
  );
}

function CanvasPreview({ panel }) {
  const ref = useRef(null);
  useEffect(() => {
    const canvas = ref.current;
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "#4f6f7f";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 3;
    ctx.strokeRect(18, 18, canvas.width - 36, canvas.height - 36);
    ctx.fillStyle = "#ffffff";
    ctx.beginPath();
    ctx.ellipse(160, 110, 116, 52, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = "#171717";
    ctx.stroke();
    ctx.fillStyle = "#171717";
    ctx.font = "18px system-ui, sans-serif";
    wrapCanvasText(ctx, panel.dialogue, 86, 94, 150, 24);
    ctx.fillStyle = "#ffffff";
    ctx.font = "16px system-ui, sans-serif";
    ctx.fillText(panel.composition, 34, 284);
  }, [panel]);
  return <canvas ref={ref} width="320" height="360" aria-label="lettering preview" />;
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
