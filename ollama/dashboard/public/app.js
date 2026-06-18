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
let filter = "all";
let saving = false;

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
  return parts.join(" / ") || model.source || "";
}

function visibleModels() {
  const query = searchInput.value.trim().toLowerCase();
  return models.filter((model) => {
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

async function load() {
  const response = await fetch("/api/dashboard/state", { cache: "no-store" });
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
  if (model) model.enabled = input.checked;
  render();
});

segments.forEach((button) => {
  button.addEventListener("click", () => {
    filter = button.dataset.filter;
    segments.forEach((item) => item.classList.toggle("active", item === button));
    render();
  });
});

searchInput.addEventListener("input", render);
refreshButton.addEventListener("click", () => load().catch((error) => {
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
    type: id.endsWith(":cloud") ? "cloud" : "local",
    enabled: id.endsWith(":cloud"),
    installed: id.endsWith(":cloud"),
    downloadable: !id.endsWith(":cloud"),
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
