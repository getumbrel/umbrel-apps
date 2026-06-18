const http = require("http");
const https = require("https");
const fs = require("fs");
const fsp = require("fs/promises");
const path = require("path");

const PORT = Number(process.env.PORT || 3000);
const OLLAMA_BASE_URL = (process.env.OLLAMA_BASE_URL || "http://ollama_ollama_1:11434").replace(/\/+$/, "");
const OLLAMA_PROXY_TIMEOUT_MS = Number(process.env.OLLAMA_PROXY_TIMEOUT_MS || 300000);
const CONFIG_DIR = process.env.CONFIG_DIR || "/config";
const PUBLIC_DIR = path.join(__dirname, "public");
const CATALOG_PATH = path.join(__dirname, "catalog.json");
const CONFIG_PATH = path.join(CONFIG_DIR, "ollama-dashboard.json");
const MANIFEST_PATH = path.join(CONFIG_DIR, "model-manifest.json");
const DISABLED_MODELS_ENV_PATH = path.join(CONFIG_DIR, "disabled-models.env");
const pullJobs = new Map();
const searchCache = new Map();
const cloudCatalogCache = { checkedAt: 0, models: [] };
const OLLAMA_LIBRARY_BASE_URL = (process.env.OLLAMA_LIBRARY_BASE_URL || "https://ollama.com").replace(/\/+$/, "");
const OLLAMA_CLOUD_CATALOG_ENABLED = !["0", "false", "no", "off"].includes(String(process.env.OLLAMA_CLOUD_CATALOG_ENABLED || "1").trim().toLowerCase());
const OLLAMA_CLOUD_CATALOG_URL = process.env.OLLAMA_CLOUD_CATALOG_URL || `${OLLAMA_LIBRARY_BASE_URL}/search?c=cloud`;
const OLLAMA_CLOUD_CATALOG_TTL_MS = Number(process.env.OLLAMA_CLOUD_CATALOG_TTL_SECONDS || 21600) * 1000;
const OLLAMA_CLOUD_CATALOG_MAX_LIBRARIES = Number(process.env.OLLAMA_CLOUD_CATALOG_MAX_LIBRARIES || 200);
const OLLAMA_CLOUD_CATALOG_MAX_PAGES = Number(process.env.OLLAMA_CLOUD_CATALOG_MAX_PAGES || 8);

const contentTypes = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml"
};

async function ensureConfigDir() {
  await fsp.mkdir(CONFIG_DIR, { recursive: true });
}

async function readJson(file, fallback) {
  try {
    return JSON.parse(await fsp.readFile(file, "utf8"));
  } catch {
    return fallback;
  }
}

async function writeJsonAtomic(file, data) {
  await ensureConfigDir();
  const tmp = `${file}.tmp`;
  await fsp.writeFile(tmp, `${JSON.stringify(data, null, 2)}\n`);
  await fsp.rename(tmp, file);
}

async function readBody(req) {
  const raw = await readRawBody(req);
  return raw.length ? JSON.parse(raw.toString("utf8")) : {};
}

async function readRawBody(req) {
  const chunks = [];
  for await (const chunk of req) chunks.push(chunk);
  return Buffer.concat(chunks);
}

function sendJson(res, status, payload) {
  const body = JSON.stringify(payload);
  res.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    "cache-control": "no-store"
  });
  res.end(body);
}

function sendError(res, status, error, detail) {
  sendJson(res, status, { error, detail: detail ? String(detail) : undefined });
}

async function fetchOllamaJson(route, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), options.timeoutMs || 10000);
  try {
    const response = await fetch(`${OLLAMA_BASE_URL}${route}`, {
      method: options.method || "GET",
      headers: { "content-type": "application/json" },
      body: options.body ? JSON.stringify(options.body) : undefined,
      signal: controller.signal
    });
    const text = await response.text();
    const data = text ? JSON.parse(text) : {};
    if (!response.ok) {
      throw new Error(data.error || data.message || `HTTP ${response.status}`);
    }
    return data;
  } finally {
    clearTimeout(timeout);
  }
}

async function fetchTags() {
  try {
    const data = await fetchOllamaJson("/api/tags", { timeoutMs: 5000 });
    return { ok: true, models: Array.isArray(data.models) ? data.models : [] };
  } catch (error) {
    return { ok: false, error: error.message, models: [] };
  }
}

async function fetchTextUrl(url, timeoutMs = 12000) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, {
      headers: {
        "accept": "text/html,application/json",
        "user-agent": "ollama-umbrel-dashboard/ollama-cloud-discovery"
      },
      signal: controller.signal
    });
    if (!response.ok) throw new Error(`${url} returned HTTP ${response.status}`);
    return await response.text();
  } finally {
    clearTimeout(timeout);
  }
}

function normalizeModelId(value) {
  return String(value || "").trim();
}

function isCloudModel(id) {
  const normalized = normalizeModelId(id).toLowerCase();
  const tag = normalized.includes(":") ? normalized.split(":").pop() : "";
  return normalized.endsWith(":cloud") || tag.endsWith("-cloud");
}

function modelTypeFor(id, entry = {}) {
  const source = String(entry.source || "").toLowerCase();
  if (entry.type === "cloud" || isCloudModel(id) || source === "ollama-cloud" || source === "cloud-catalog" || source === "saved-cloud") {
    return "cloud";
  }
  return "local";
}

function modelName(entry) {
  return entry.name || entry.model || entry.id || "";
}

function dedupeKeepOrder(items) {
  const seen = new Set();
  const ordered = [];
  for (const item of items) {
    if (!item || seen.has(item)) continue;
    seen.add(item);
    ordered.push(item);
  }
  return ordered;
}

function cloudModelMeta(id) {
  const lower = String(id || "").toLowerCase();
  const vision = ["gemini", "gemma4", "qwen3.5", "kimi-k2.5", "kimi-k2.6", "ministral", "devstral"].some((hint) => lower.includes(hint));
  const nonTool = ["embed", "embedding", "ocr", "vision", "-vl", ":vl", "whisper", "tts"].some((hint) => lower.includes(hint));
  return {
    id,
    name: id,
    source: "ollama-cloud-catalog",
    type: "cloud",
    reasoning: ["deepseek", "qwen", "glm", "nemotron", "minimax", "kimi", "gemini", "gemma"].some((hint) => lower.includes(hint)),
    contextWindow: 256000,
    maxTokens: 128000,
    supportsChat: true,
    supportsTools: !nonTool,
    supportsJson: true,
    input: vision ? ["text", "image"] : ["text"],
    supportsVision: vision
  };
}

function parseLibraryLinks(html) {
  const libraries = [];
  const pattern = /href=["']\/library\/([a-zA-Z0-9_.-]+)["']/g;
  let match;
  while ((match = pattern.exec(html))) {
    libraries.push(match[1].trim());
  }
  return dedupeKeepOrder(libraries);
}

function parseCloudTags(name, html) {
  const tags = [];
  const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const pattern = new RegExp(`href=["']/library/${escaped}:([^"']+)["']`, "g");
  let match;
  while ((match = pattern.exec(html))) {
    const tag = decodeURIComponent(match[1]).trim();
    if (tag && tag.toLowerCase().includes("cloud")) tags.push(tag);
  }
  if (!tags.length && html.toLowerCase().includes("cloud")) tags.push("cloud");
  return dedupeKeepOrder(tags);
}

async function discoverCloudCatalogModels(force = false) {
  if (!OLLAMA_CLOUD_CATALOG_ENABLED) return [];
  const now = Date.now();
  if (!force && cloudCatalogCache.models.length && now - cloudCatalogCache.checkedAt < OLLAMA_CLOUD_CATALOG_TTL_MS) {
    return cloudCatalogCache.models.slice();
  }

  try {
    const catalogUrl = new URL(OLLAMA_CLOUD_CATALOG_URL);
    const libraries = [];
    const maxPages = Math.max(1, OLLAMA_CLOUD_CATALOG_MAX_PAGES);
    const maxLibraries = Math.max(1, OLLAMA_CLOUD_CATALOG_MAX_LIBRARIES);
    for (let page = 1; page <= maxPages; page += 1) {
      const pageUrl = new URL(catalogUrl);
      if (page > 1) pageUrl.searchParams.set("p", String(page));
      const before = libraries.length;
      for (const library of parseLibraryLinks(await fetchTextUrl(pageUrl.toString()))) {
        if (!libraries.includes(library)) libraries.push(library);
        if (libraries.length >= maxLibraries) break;
      }
      if (libraries.length >= maxLibraries) break;
      if (page > 1 && libraries.length === before) break;
    }

    const models = [];
    let index = 0;
    const workers = Array.from({ length: Math.min(6, libraries.length) }, async () => {
      while (index < libraries.length) {
        const name = libraries[index];
        index += 1;
        try {
          const html = await fetchTextUrl(`${OLLAMA_LIBRARY_BASE_URL}/library/${encodeURIComponent(name)}`);
          const tags = parseCloudTags(name, html);
          for (const tag of tags) models.push(`${name}:${tag}`);
        } catch {
          models.push(`${name}:cloud`);
        }
      }
    });
    await Promise.all(workers);

    const discovered = dedupeKeepOrder(models).filter(isCloudModel).map(cloudModelMeta);
    if (discovered.length) {
      cloudCatalogCache.checkedAt = now;
      cloudCatalogCache.models = discovered;
      return discovered.slice();
    }
  } catch {
    return cloudCatalogCache.models.slice();
  }
  return cloudCatalogCache.models.slice();
}

async function buildState(options = {}) {
  const [catalog, config, tags, cloudCatalog] = await Promise.all([
    readJson(CATALOG_PATH, { cloud: [], local: [] }),
    readJson(CONFIG_PATH, { version: 1, models: {} }),
    fetchTags(),
    discoverCloudCatalogModels(Boolean(options.forceCloudCatalog))
  ]);
  const saved = config.models && typeof config.models === "object" ? config.models : {};
  const byId = new Map();

  function upsert(id, patch) {
    const modelId = normalizeModelId(id);
    if (!modelId) return;
    byId.set(modelId, { ...(byId.get(modelId) || { id: modelId }), ...patch });
  }

  for (const entry of catalog.cloud || []) {
    upsert(entry.id, { ...entry, source: "cloud-catalog", type: "cloud" });
  }
  for (const entry of cloudCatalog) {
    upsert(entry.id, { ...entry, source: "ollama-cloud-catalog", type: "cloud" });
  }
  for (const entry of catalog.local || []) {
    upsert(entry.id, { ...entry, source: "local-catalog", type: "local", downloadable: true });
  }
  for (const tag of tags.models) {
    const id = normalizeModelId(tag.name || tag.model);
    const details = tag.details && typeof tag.details === "object" ? tag.details : {};
    const cloud = isCloudModel(id);
    upsert(id, {
      source: cloud ? "ollama-cloud" : "installed",
      type: cloud ? "cloud" : "local",
      installed: true,
      digest: tag.digest,
      modifiedAt: tag.modified_at,
      sizeBytes: tag.size,
      family: details.family,
      families: details.families,
      parameterSize: details.parameter_size,
      quantization: details.quantization_level
    });
  }
  for (const [id, entry] of Object.entries(saved)) {
    const type = modelTypeFor(id, entry);
    upsert(id, {
      source: entry.source || (type === "cloud" ? "saved-cloud" : "saved-local"),
      type
    });
  }

  const models = Array.from(byId.values()).map((model) => {
    const savedEntry = saved[model.id];
    const cloud = modelTypeFor(model.id, model) === "cloud";
    const enabled = typeof savedEntry?.enabled === "boolean" ? savedEntry.enabled : cloud;
    return {
      id: model.id,
      name: model.name || model.id,
      type: cloud ? "cloud" : "local",
      source: model.source,
      enabled,
      installed: Boolean(model.installed || cloud),
      downloadable: !cloud,
      pulling: pullJobs.has(model.id),
      pull: pullJobs.get(model.id) || null,
      digest: model.digest,
      modifiedAt: model.modifiedAt,
      size: model.size,
      sizeBytes: model.sizeBytes,
      family: model.family,
      families: model.families,
      parameterSize: model.parameterSize,
      quantization: model.quantization,
      reasoning: Boolean(model.reasoning),
      supportsChat: model.supportsChat !== false,
      supportsTools: model.supportsTools,
      supportsJson: model.supportsJson,
      contextWindow: model.contextWindow,
      maxTokens: model.maxTokens
    };
  }).sort((a, b) => {
    if (a.type !== b.type) return a.type === "cloud" ? -1 : 1;
    if (a.installed !== b.installed) return a.installed ? -1 : 1;
    return a.id.localeCompare(b.id);
  });

  return {
    ollamaReachable: tags.ok,
    ollamaError: tags.ok ? null : tags.error,
    ollamaBaseUrl: OLLAMA_BASE_URL,
    configPath: CONFIG_PATH,
    manifestPath: MANIFEST_PATH,
    disabledModelsEnvPath: DISABLED_MODELS_ENV_PATH,
    cloudCatalog: {
      enabled: OLLAMA_CLOUD_CATALOG_ENABLED,
      source: OLLAMA_CLOUD_CATALOG_URL,
      checkedAt: cloudCatalogCache.checkedAt ? new Date(cloudCatalogCache.checkedAt).toISOString() : null,
      discovered: cloudCatalog.length
    },
    models,
    pullJobs: Object.fromEntries(pullJobs)
  };
}

function manifestEntry(model) {
  return {
    id: model.id,
    name: model.name || model.id,
    servable: Boolean(model.enabled),
    resident: Boolean(model.installed && model.type === "local"),
    preferred: Boolean(model.enabled),
    reasoning: Boolean(model.reasoning),
    contextWindow: model.contextWindow,
    maxTokens: model.maxTokens,
    input: ["text"],
    supportsChat: model.supportsChat !== false,
    supportsTools: model.supportsTools,
    supportsJson: model.supportsJson,
    supportsStreaming: true,
    reason: model.enabled ? "enabled in Ollama Umbrel dashboard" : "disabled in Ollama Umbrel dashboard"
  };
}

async function persistSelection(selection) {
  const state = await buildState();
  const selected = new Map();
  for (const item of selection) {
    const id = normalizeModelId(item.id || item.model || item.name);
    if (id) selected.set(id, Boolean(item.enabled));
  }
  const known = new Map(state.models.map((model) => [model.id, model]));
  for (const [id] of selected) {
    if (!known.has(id)) {
      const type = modelTypeFor(id);
      known.set(id, {
        id,
        name: id,
        type,
        installed: false,
        downloadable: type !== "cloud",
        supportsChat: true
      });
    }
  }
  const models = Array.from(known.values()).map((model) => ({
    ...model,
    enabled: selected.has(model.id) ? selected.get(model.id) : model.enabled
  }));
  const config = {
    version: 1,
    updatedAt: new Date().toISOString(),
    models: Object.fromEntries(models.map((model) => [
      model.id,
      {
        enabled: Boolean(model.enabled),
        source: model.source || (model.type === "cloud" ? "cloud" : "local")
      }
    ]))
  };
  await writeJsonAtomic(CONFIG_PATH, config);
  await writeJsonAtomic(MANIFEST_PATH, {
    version: 1,
    updatedAt: config.updatedAt,
    models: models.map(manifestEntry)
  });
  const disabled = models.filter((model) => !model.enabled).map((model) => model.id).sort();
  await fsp.writeFile(DISABLED_MODELS_ENV_PATH, `SAGE_ROUTER_DISABLED_MODELS=${disabled.join(",")}\n`);

  for (const model of models) {
    if (model.enabled && model.type === "local" && !model.installed) {
      startPull(model.id);
    }
  }
}

async function isModelEnabled(modelId) {
  const id = normalizeModelId(modelId);
  if (!id) return true;
  const config = await readJson(CONFIG_PATH, { version: 1, models: {} });
  const saved = config.models && typeof config.models === "object" ? config.models : {};
  if (typeof saved[id]?.enabled === "boolean") return saved[id].enabled;
  return isCloudModel(id);
}

function decodeHtml(value) {
  return String(value || "")
    .replace(/&nbsp;/g, " ")
    .replace(/&#39;/g, "'")
    .replace(/&quot;/g, "\"")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">");
}

function stripHtml(value) {
  return decodeHtml(String(value || "").replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim());
}

function firstMatch(value, regex) {
  const match = regex.exec(value);
  return match ? stripHtml(match[1]) : "";
}

function parseOllamaSearch(html) {
  const results = [];
  const seen = new Set();
  const itemPattern = /<li\b[^>]*x-test-model[^>]*>([\s\S]*?)<\/li>/g;
  let item;
  while ((item = itemPattern.exec(html))) {
    const chunk = item[1];
    const title = firstMatch(chunk, /<span\b[^>]*x-test-search-response-title[^>]*>([\s\S]*?)<\/span>/);
    if (!title || seen.has(title)) continue;
    seen.add(title);
    const hrefMatch = /<a\s+href="([^"]+)"/.exec(chunk);
    const href = hrefMatch ? decodeHtml(hrefMatch[1]) : "";
    const description = firstMatch(chunk, /<p\b[^>]*>([\s\S]*?)<\/p>/);
    const pulls = firstMatch(chunk, /<span\b[^>]*x-test-pull-count[^>]*>([\s\S]*?)<\/span>/);
    const type = modelTypeFor(title);
    results.push({
      id: title,
      name: title,
      type,
      source: "ollama.com",
      installed: type === "cloud",
      downloadable: type !== "cloud",
      enabled: false,
      description,
      pulls,
      url: href ? `${OLLAMA_LIBRARY_BASE_URL}${href}` : `${OLLAMA_LIBRARY_BASE_URL}/search`
    });
  }
  return results.slice(0, 25);
}

async function searchOllamaModels(query) {
  const normalized = String(query || "").trim();
  if (normalized.length < 2) return [];
  const key = normalized.toLowerCase();
  const cached = searchCache.get(key);
  if (cached && Date.now() - cached.timestamp < 5 * 60 * 1000) return cached.results;

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10000);
  try {
    const response = await fetch(`${OLLAMA_LIBRARY_BASE_URL}/search?q=${encodeURIComponent(normalized)}`, {
      headers: {
        "accept": "text/html",
        "user-agent": "ollama-umbrel-dashboard/1.0"
      },
      signal: controller.signal
    });
    if (!response.ok) throw new Error(`ollama.com search returned HTTP ${response.status}`);
    const results = parseOllamaSearch(await response.text());
    searchCache.set(key, { timestamp: Date.now(), results });
    return results;
  } finally {
    clearTimeout(timeout);
  }
}

function shouldEnforceModelSelection(method, pathname) {
  if (method !== "POST") return false;
  return [
    "/api/generate",
    "/api/chat",
    "/api/embed",
    "/api/embeddings",
    "/v1/chat/completions",
    "/v1/completions",
    "/v1/embeddings"
  ].includes(pathname);
}

async function startPull(modelId) {
  if (pullJobs.has(modelId)) return pullJobs.get(modelId);
  const job = {
    model: modelId,
    status: "queued",
    message: "Queued",
    completed: 0,
    total: 0,
    startedAt: new Date().toISOString()
  };
  pullJobs.set(modelId, job);
  runPull(modelId, job).catch((error) => {
    Object.assign(job, {
      status: "error",
      message: error.message,
      finishedAt: new Date().toISOString()
    });
  });
  return job;
}

async function runPull(modelId, job) {
  job.status = "pulling";
  job.message = "Starting pull";
  const response = await fetch(`${OLLAMA_BASE_URL}/api/pull`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ model: modelId, stream: true })
  });
  if (!response.ok || !response.body) {
    const text = await response.text().catch(() => "");
    throw new Error(text || `Ollama pull failed with HTTP ${response.status}`);
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    for (const line of lines) {
      if (!line.trim()) continue;
      try {
        const event = JSON.parse(line);
        job.message = event.status || job.message;
        job.digest = event.digest || job.digest;
        job.completed = Number(event.completed || job.completed || 0);
        job.total = Number(event.total || job.total || 0);
      } catch {
        job.message = line.trim();
      }
    }
  }
  job.status = "complete";
  job.message = "Ready";
  job.finishedAt = new Date().toISOString();
  setTimeout(() => pullJobs.delete(modelId), 10 * 60 * 1000).unref();
}

function proxyOllama(req, res, bodyBuffer = null) {
  const target = new URL(req.url, OLLAMA_BASE_URL);
  const transport = target.protocol === "https:" ? https : http;
  const headers = { ...req.headers, host: target.host };
  if (bodyBuffer) headers["content-length"] = Buffer.byteLength(bodyBuffer);
  const proxyReq = transport.request(target, { method: req.method, headers }, (proxyRes) => {
    res.writeHead(proxyRes.statusCode || 502, proxyRes.headers);
    proxyRes.pipe(res);
  });
  proxyReq.setTimeout(OLLAMA_PROXY_TIMEOUT_MS, () => {
    proxyReq.destroy(new Error(`Ollama did not respond within ${OLLAMA_PROXY_TIMEOUT_MS}ms`));
  });
  proxyReq.on("error", (error) => sendError(res, 502, "ollama_proxy_failed", error.message));
  if (bodyBuffer) {
    proxyReq.end(bodyBuffer);
  } else {
    req.pipe(proxyReq);
  }
}

async function serveStatic(req, res) {
  const requestPath = decodeURIComponent(new URL(req.url, "http://dashboard.local").pathname);
  const relative = requestPath === "/" ? "index.html" : requestPath.replace(/^\/+/, "");
  const filePath = path.normalize(path.join(PUBLIC_DIR, relative));
  if (filePath !== PUBLIC_DIR && !filePath.startsWith(`${PUBLIC_DIR}${path.sep}`)) {
    sendError(res, 403, "forbidden");
    return;
  }
  try {
    const data = await fsp.readFile(filePath);
    res.writeHead(200, {
      "content-type": contentTypes[path.extname(filePath)] || "application/octet-stream",
      "cache-control": filePath.endsWith("index.html") ? "no-store" : "public, max-age=300"
    });
    res.end(data);
  } catch {
    sendError(res, 404, "not_found");
  }
}

const server = http.createServer(async (req, res) => {
  try {
    const url = new URL(req.url, "http://dashboard.local");
    if (req.method === "GET" && url.pathname === "/api/dashboard/state") {
      sendJson(res, 200, await buildState({ forceCloudCatalog: url.searchParams.get("refresh") === "1" }));
      return;
    }
    if (req.method === "GET" && url.pathname === "/api/dashboard/search") {
      sendJson(res, 200, { models: await searchOllamaModels(url.searchParams.get("q")) });
      return;
    }
    if (req.method === "POST" && url.pathname === "/api/dashboard/config") {
      const body = await readBody(req);
      await persistSelection(Array.isArray(body.models) ? body.models : []);
      sendJson(res, 200, await buildState());
      return;
    }
    if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/v1/")) {
      if (shouldEnforceModelSelection(req.method, url.pathname)) {
        const bodyBuffer = await readRawBody(req);
        const payload = bodyBuffer.length ? JSON.parse(bodyBuffer.toString("utf8")) : {};
        if (!(await isModelEnabled(payload.model))) {
          sendError(res, 403, "model_disabled", `${payload.model || "requested model"} is disabled in the Ollama dashboard`);
          return;
        }
        proxyOllama(req, res, bodyBuffer);
        return;
      }
      proxyOllama(req, res);
      return;
    }
    if (req.method === "GET" || req.method === "HEAD") {
      await serveStatic(req, res);
      return;
    }
    sendError(res, 405, "method_not_allowed");
  } catch (error) {
    sendError(res, 500, "dashboard_error", error.message);
  }
});

ensureConfigDir()
  .then(() => server.listen(PORT, "0.0.0.0", () => {
    console.log(`Ollama dashboard listening on ${PORT}, proxying ${OLLAMA_BASE_URL}`);
  }))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
