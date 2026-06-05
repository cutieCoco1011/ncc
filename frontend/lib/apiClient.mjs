const DEFAULT_BASE_URL = "http://127.0.0.1:8000";
export { DEFAULT_BASE_URL };

export async function createProject(payload, baseUrl = DEFAULT_BASE_URL) {
  const response = await fetch(`${baseUrl}/projects`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!response.ok) {
    throw new Error(`create project failed: ${response.status}`);
  }
  return response.json();
}

export async function runStage(projectId, stage, baseUrl = DEFAULT_BASE_URL) {
  const response = await fetch(`${baseUrl}/projects/${projectId}/stages/${stage}`, {
    method: "POST"
  });
  if (!response.ok) {
    throw new Error(`stage ${stage} failed: ${response.status}`);
  }
  return response.json();
}

export async function runGoldPath(payload = {}, baseUrl = DEFAULT_BASE_URL) {
  const response = await fetch(`${baseUrl}/gold-path`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!response.ok) {
    throw new Error(`gold path failed: ${response.status}`);
  }
  return response.json();
}

export async function fetchArtifacts(projectId, baseUrl = DEFAULT_BASE_URL) {
  const response = await fetch(`${baseUrl}/projects/${projectId}/artifacts`);
  if (!response.ok) {
    throw new Error(`fetch artifacts failed: ${response.status}`);
  }
  return response.json();
}

export async function listProjects(baseUrl = DEFAULT_BASE_URL) {
  const response = await fetch(`${baseUrl}/projects`);
  if (!response.ok) {
    throw new Error(`list projects failed: ${response.status}`);
  }
  return response.json();
}

export async function fetchProviders(baseUrl = DEFAULT_BASE_URL) {
  const response = await fetch(`${baseUrl}/providers`);
  if (!response.ok) {
    throw new Error(`fetch providers failed: ${response.status}`);
  }
  return response.json();
}

export async function selectBackendCandidate(projectId, candidateId, baseUrl = DEFAULT_BASE_URL) {
  const response = await fetch(`${baseUrl}/projects/${projectId}/candidates/${candidateId}/select`, {
    method: "POST"
  });
  if (!response.ok) {
    throw new Error(`select candidate failed: ${response.status}`);
  }
  return response.json();
}

export async function patchBackendCharacter(projectId, characterId, patch, baseUrl = DEFAULT_BASE_URL) {
  const response = await fetch(`${baseUrl}/projects/${projectId}/characters/${characterId}`, {
    method: "PATCH",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(patch)
  });
  if (!response.ok) {
    throw new Error(`patch character failed: ${response.status}`);
  }
  return response.json();
}

export async function patchBackendStoryboard(projectId, panelId, patch, baseUrl = DEFAULT_BASE_URL) {
  const response = await fetch(`${baseUrl}/projects/${projectId}/storyboard/${panelId}`, {
    method: "PATCH",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(patch)
  });
  if (!response.ok) {
    throw new Error(`patch storyboard failed: ${response.status}`);
  }
  return response.json();
}

export async function updateBackendLettering(projectId, balloonId, patch, baseUrl = DEFAULT_BASE_URL) {
  const response = await fetch(`${baseUrl}/projects/${projectId}/lettering/${balloonId}`, {
    method: "PATCH",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(patch)
  });
  if (!response.ok) {
    throw new Error(`update lettering failed: ${response.status}`);
  }
  return response.json();
}

export async function runBackendLettering(projectId, baseUrl = DEFAULT_BASE_URL) {
  return runStage(projectId, "lettering", baseUrl);
}

export async function runBackendPanelSpecs(projectId, baseUrl = DEFAULT_BASE_URL) {
  return runStage(projectId, "panel-specs", baseUrl);
}

export async function runBackendExport(projectId, baseUrl = DEFAULT_BASE_URL) {
  return runStage(projectId, "export", baseUrl);
}

export function projectFileUrl(projectId, relativePath, baseUrl = DEFAULT_BASE_URL) {
  return `${baseUrl}/projects/${projectId}/files/${relativePath}`;
}

export function latestExportUrl(projectId, baseUrl = DEFAULT_BASE_URL) {
  return `${baseUrl}/projects/${projectId}/exports/latest`;
}
