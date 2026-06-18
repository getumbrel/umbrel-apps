const rows = document.querySelector("#models");
const statusEl = document.querySelector("#status");
const saveButton = document.querySelector("#save");
const refreshButton = document.querySelector("#refresh");
const searchInput = document.querySelector("#search");
const customInput = document.querySelector("#custom-model");
const addButton = document.querySelector("#add-model");
const segments = Array.from(document.querySelectorAll(".segment"));
const counts = {
  enabled: document.querySelector("#enabled-count"),
  cloud: document.querySelector("#cloud-count"),
  local: document.querySelector("#local-count"),
  pull: document.querySelector("#pull-count")
};

let models = [];
let remoteModels = [];
let filter = "all";
let saving = false;
let searchTimer = null;
let searchRequest = 0;

function isCloudModel(id) {
  const normalized = String(id || "").trim().toLowerCase();
  const tag = normalized.includes(":") ? normalized.split(":").pop() : "";
  return normalized.endsWith(":cloud") || tag.endsWith("-cloud");
}

function formatBytes(bytes) {
  if (!bytes) return "";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = Number(bytes);
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(value >= 10 || unit === 0 ? 0 : 1)} ${units[unit]}`;
}

function statusFor(model) {
  if (model.pull?.status === "pulling" || model.pull?.status === "queued") {
    const progress = model.pull.total ? ` ${Math.round((model.pull.completed / model.pull.total) * 100)}%` : "";
    return { label: `${model.pull.message || "Pulling"}${progress}`, tone: "warn" };
  }
  if (model.pull?.status === "error") return { label: model.pull.message || "Pull failed", tone: "error" };
  if (model.type === "cloud") return { label: "Cloud", tone: "cloud" };
  if (model.installed) return { label: "Installed", tone: "local" };
  return { label: "Downloadable", tone: "warn" };
}

function detailText(model) {
  const parts = [];
  if (model.family) parts.push(model.family);
  if (model.parameterSize) parts.push(model.parameterSize);
  if (model.quantization) parts.push(model.quantization);
  if (model.size || model.sizeBytes) parts.push(model.size || formatBytes(model.sizeBytes));
  if (model.contextWindow) parts.push(`${Number(model.contextWindow).toLocaleString()} context`);
  if (model.reasoning) parts.push("reasoning");
  if (model.supportsChat === false) parts.push("embedding");
  if (model.pulls) parts.push(`${model.pulls} pulls`);
  if (model.description) parts.push(model.description);
  return parts.join(" / ") || model.source || "";
}

function allModels() {
  const byId = new Map(models.map((model) => [model.id, model]));
  for (const model of remoteModels) {
    if (!byId.has(model.id)) byId.set(model.id, { ...model, remote: true });
  }
  return Array.from(byId.values());
}

function visibleModels() {
  const query = searchInput.value.trim().toLowerCase();
  return allModels().filter((model) => {
    if (filter === "cloud" && model.type !== "cloud") return false;
    if (filter === "local" && model.type !== "local") return false;
    if (filter === "enabled" && !model.enabled) return false;
    if (!query) return true;
    return [model.id, model.name, model.family, model.source].filter(Boolean).join(" ").toLowerCase().includes(query);
  });
}

function render() {
  const enabled = models.filter((model) => model.enabled).length;
  const cloud = models.filter((model) => model.type === "cloud").length;
  const local = models.filter((model) => model.type === "local").length;
  const pulling = models.filter((model) => model.pull && ["queued", "pulling"].includes(model.pull.status)).length;
  counts.enabled.textContent = enabled;
  counts.cloud.textContent = cloud;
  counts.local.textContent = local;
  counts.pull.textContent = pulling;

  rows.innerHTML = "";
  for (const model of visibleModels()) {
    const tr = document.createElement("tr");
    const state = statusFor(model);
    tr.innerHTML = `
      <td>
        <label class="switch" title="Enable ${model.id}">
          <input type="checkbox" ${model.enabled ? "checked" : ""} data-id="${escapeHtml(model.id)}">
          <span class="slider"></span>
        </label>
      </td>
      <td>
        <div class="modelName">
          <strong>${escapeHtml(model.name || model.id)}</strong>
          <code>${escapeHtml(model.id)}</code>
        </div>
      </td>
      <td><span class="badge ${model.type}">${model.type === "cloud" ? "Cloud" : "Local"}</span></td>
      <td><span class="badge ${state.tone}">${escapeHtml(state.label)}</span></td>
      <td class="details">${escapeHtml(detailText(model))}</td>
    `;
    rows.appendChild(tr);
  }
  if (!rows.children.length) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td colspan="5" class="details">No models match the current filter.</td>`;
    rows.appendChild(tr);
  }
}

function escapeHtml(value) {
  return String(value || "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "\"": "&quot;",
    "'": "&#39;"
  }[char]));
}

async function load(forceRefresh = false) {
  const response = await fetch(`/api/dashboard/state${forceRefresh ? "?refresh=1" : ""}`, { cache: "no-store" });
  const state = await response.json();
  if (!response.ok) throw new Error(state.detail || state.error || "Failed to load state");
  models = state.models || [];
  statusEl.textContent = state.ollamaReachable
    ? `Connected to ${state.ollamaBaseUrl}. Selection is persisted at ${state.configPath}.`
    : `Ollama is not reachable: ${state.ollamaError || "unknown error"}`;
  render();
}

async function save() {
  saving = true;
  saveButton.disabled = true;
  saveButton.textContent = "Saving";
  try {
    const response = await fetch("/api/dashboard/config", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ models: models.map(({ id, enabled }) => ({ id, enabled })) })
    });
    const state = await response.json();
    if (!response.ok) throw new Error(state.detail || state.error || "Save failed");
    models = state.models || [];
    statusEl.textContent = "Selection saved. Enabled local models will pull in the background.";
    render();
  } finally {
    saving = false;
    saveButton.disabled = false;
    saveButton.textContent = "Save";
  }
}

rows.addEventListener("change", (event) => {
  const input = event.target.closest("input[type='checkbox'][data-id]");
  if (!input) return;
  const model = models.find((item) => item.id === input.dataset.id);
  if (model) {
    model.enabled = input.checked;
  } else if (input.checked) {
    const remote = remoteModels.find((item) => item.id === input.dataset.id);
    if (remote) {
      models.push({
        ...remote,
        remote: undefined,
        type: isCloudModel(remote.id) ? "cloud" : remote.type,
        enabled: true,
        installed: remote.installed || isCloudModel(remote.id),
        downloadable: !isCloudModel(remote.id)
      });
    }
  }
  render();
});

segments.forEach((button) => {
  button.addEventListener("click", () => {
    filter = button.dataset.filter;
    segments.forEach((item) => item.classList.toggle("active", item === button));
    render();
  });
});

async function searchRemoteModels(query, requestId) {
  if (query.trim().length < 2) {
    remoteModels = [];
    render();
    return;
  }
  const response = await fetch(`/api/dashboard/search?q=${encodeURIComponent(query.trim())}`, { cache: "no-store" });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.detail || payload.error || "Model search failed");
  if (requestId !== searchRequest) return;
  remoteModels = payload.models || [];
  render();
}

searchInput.addEventListener("input", () => {
  render();
  clearTimeout(searchTimer);
  const query = searchInput.value;
  const requestId = ++searchRequest;
  searchTimer = setTimeout(() => {
    searchRemoteModels(query, requestId).catch((error) => {
      if (requestId !== searchRequest) return;
      remoteModels = [];
      statusEl.textContent = error.message;
      render();
    });
  }, 250);
});
refreshButton.addEventListener("click", () => load(true).catch((error) => {
  statusEl.textContent = error.message;
}));
saveButton.addEventListener("click", () => {
  if (!saving) save().catch((error) => {
    statusEl.textContent = error.message;
  });
});
addButton.addEventListener("click", () => {
  const id = customInput.value.trim();
  if (!id || models.some((model) => model.id === id)) return;
  models.push({
    id,
    name: id,
    type: isCloudModel(id) ? "cloud" : "local",
    enabled: isCloudModel(id),
    installed: isCloudModel(id),
    downloadable: !isCloudModel(id),
    source: "custom"
  });
  customInput.value = "";
  render();
});
customInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") addButton.click();
});

load().catch((error) => {
  statusEl.textContent = error.message;
  render();
});
setInterval(() => {
  if (!saving && models.some((model) => model.pull && ["queued", "pulling"].includes(model.pull.status))) {
    load().catch(() => {});
  }
}, 5000);
