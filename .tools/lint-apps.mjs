#!/usr/bin/env node

import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import YAML from "yaml";

let ROOT = path.resolve(process.env.UMBREL_APP_LINT_ROOT || path.resolve(import.meta.dirname, ".."));

// Keep this list to hooks that umbrelOS actually calls for app packages.
const VALID_HOOKS = new Set([
  "pre-install",
  "post-install",
  "pre-start",
  "post-start",
  "pre-stop",
  "post-stop",
  "pre-update",
  "post-update",
]);

const VALID_CATEGORIES = new Set(["ai", "automation", "bitcoin", "crypto", "developer", "files", "finance", "media", "networking", "social"]);
const VALID_PERMISSIONS = new Set(["STORAGE_DOWNLOADS", "GPU"]);
const REQUIRED_MANIFEST_FIELDS = [
  "manifestVersion",
  "id",
  "category",
  "name",
  "version",
  "tagline",
  "description",
  "developer",
  "website",
  "dependencies",
  "repo",
  "support",
  "port",
  "gallery",
  "path",
  "submitter",
  "submission",
];
const STRING_MANIFEST_FIELDS = ["id", "category", "name", "version", "tagline", "description", "website", "support", "path", "submission"];
const OPTIONAL_STRING_MANIFEST_FIELDS = ["releaseNotes", "defaultUsername", "defaultPassword", "defaultShell", "icon"];
const OPTIONAL_BOOLEAN_MANIFEST_FIELDS = ["deterministicPassword", "optimizedForUmbrelHome", "torOnly", "requiresHttps", "disabled"];
const WIDGET_TYPES = new Set(["text-with-buttons", "text-with-progress", "two-stats-with-guage", "three-stats", "four-stats", "list", "list-emoji"]);
const LINT_INFRASTRUCTURE_FILES = new Set([
  ".tools/lint-apps.mjs",
  ".github/workflows/lint-apps.yml",
  "package-lock.json",
  "package.json",
]);
const RESERVED_HOST_PORTS = [
  { port: 80, protocol: "tcp", label: "umbrelOS dashboard HTTP" },
  { port: 443, protocol: "tcp", label: "umbrelOS dashboard HTTPS" },
  { port: 2000, protocol: "tcp", label: "umbrelOS app auth" },
];

const IMAGE_ACCEPT_HEADER = [
  "application/vnd.oci.image.index.v1+json",
  "application/vnd.oci.image.manifest.v1+json",
  "application/vnd.docker.distribution.manifest.list.v2+json",
  "application/vnd.docker.distribution.manifest.v2+json",
].join(", ");

function parseArgs(args) {
  const options = {
    all: false,
    apps: [],
    changed: null,
    checkImages: false,
    format: "text",
    root: ROOT,
  };

  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (arg === "--all") {
      options.all = true;
    } else if (arg === "--changed") {
      options.changed = args[++index];
      if (!options.changed) usage("Missing value for --changed.");
    } else if (arg === "--check-images") {
      options.checkImages = true;
    } else if (arg === "--format") {
      options.format = args[++index];
      if (!options.format) usage("Missing value for --format.");
    } else if (arg === "--root") {
      const root = args[++index];
      if (!root) usage("Missing value for --root.");
      options.root = path.resolve(root);
    } else if (arg === "-h" || arg === "--help") {
      usage(null, 0);
    } else if (arg.startsWith("-")) {
      usage(`Unknown option ${arg}.`);
    } else {
      options.apps.push(arg.replace(/\/$/, ""));
    }
  }

  if (!["text", "github", "json"].includes(options.format)) {
    usage(`Unknown format ${options.format}.`);
  }

  if (options.apps.length === 0 && !options.all && !options.changed) {
    usage("Provide an app id, --all, or --changed RANGE.");
  }

  return options;
}

function usage(error, exitCode = 2) {
  const message = `Usage: npm run lint:apps -- [APP ...] [--all] [--changed RANGE] [--check-images] [--format text|github|json] [--root PATH]`;
  if (error) console.error(error);
  console.error(message);
  process.exit(exitCode);
}

class AppLinter {
  constructor(options) {
    this.options = options;
    this.issues = [];
    this.appDirs = discoverAppDirs();
    // Disabled packages have been removed from the active App Store, so they
    // should not reserve ports or fail normal app submission linting.
    this.activeAppDirs = this.appDirs.filter((app) => !this.appDisabled(app));
    this.baseRef = baseRefFromChangedRange(options.changed) || defaultBaseRef(options);
    this.portIndex = new Map();
    this.imageManifestCache = new Map();
  }

  async run() {
    const apps = this.selectedApps();
    if (apps.length === 0) {
      this.report(apps);
      return this.hasErrors() ? 1 : 0;
    }

    this.portIndex = this.buildPortIndex();
    for (const app of apps) {
      await this.lintApp(app);
    }

    this.report(apps);
    return this.hasErrors() ? 1 : 0;
  }

  selectedApps() {
    const apps = this.options.all
      ? this.activeAppDirs
      : this.options.changed
        ? this.changedApps(this.options.changed)
        : this.options.apps;

    return unique(apps).filter((app) => {
      if (this.activeAppDirs.includes(app)) return true;
      if (this.appDirs.includes(app)) return false;
      this.add("error", "app.unknown", app, null, `No app package found at ${app}/umbrel-app.yml.`);
      return false;
    });
  }

  changedApps(range) {
    let output;
    try {
      output = execFileSync("git", ["diff", "--name-only", range], {
        cwd: ROOT,
        encoding: "utf8",
      });
    } catch {
      this.add("error", "git.changed", ".tools/lint-apps.mjs", null, `Could not list changed files for ${range}.`);
      return [];
    }

    const files = output
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);

    this.lintInfrastructureChanges(files);
    this.lintDeletedApps(range);

    return unique(files.map((file) => file.split("/", 1)[0]).filter((app) => this.appDirs.includes(app))).sort();
  }

  lintInfrastructureChanges(files) {
    for (const file of files) {
      if (!LINT_INFRASTRUCTURE_FILES.has(file)) continue;

      this.add("warning", "lint.infrastructure", file, null, "This PR changes app lint infrastructure; keep app submissions focused on app package files unless tooling changes are intentional.");
    }
  }

  lintDeletedApps(range) {
    let output;
    try {
      output = execFileSync("git", ["diff", "--name-status", range], {
        cwd: ROOT,
        encoding: "utf8",
      });
    } catch {
      return;
    }

    for (const line of output.split(/\r?\n/).filter(Boolean)) {
      const [status, oldPath] = line.split("\t");
      const deletedManifest = (status === "D" || status.startsWith("R")) && oldPath?.endsWith("/umbrel-app.yml");
      if (!deletedManifest) continue;

      this.add("error", "app.deleted", oldPath, null, "App submissions must not delete or rename released app packages. Restore this package path or coordinate removal separately.");
    }
  }

  async lintApp(app) {
    const manifestPath = path.join(ROOT, app, "umbrel-app.yml");
    const composePath = path.join(ROOT, app, "docker-compose.yml");

    const manifestResult = this.parseYaml(manifestPath, `${app}/umbrel-app.yml`);
    if (!manifestResult) return;

    const { value: manifest, content: manifestContent } = manifestResult;
    this.lintManifest(app, manifest, manifestContent);
    await this.lintCompose(app, manifest, manifestContent, composePath);
    this.lintExports(app);
    this.lintTemplates(app);
    this.lintHooks(app);
    this.lintPackageFiles(app);
  }

  lintManifest(app, manifest, content) {
    if (!isObject(manifest)) {
      this.add("error", "manifest.type", `${app}/umbrel-app.yml`, 1, "Manifest must be a YAML object.");
      return;
    }

    for (const field of REQUIRED_MANIFEST_FIELDS) {
      if (!(field in manifest)) {
        this.add("error", "manifest.required", `${app}/umbrel-app.yml`, 1, `Missing required manifest field \`${field}\`.`);
      }
    }

    if (manifest.id !== app) {
      this.add("error", "manifest.id", `${app}/umbrel-app.yml`, keyLine(content, "id"), "`id` must match the app directory.");
    }

    if (typeof manifest.id === "string" && !/^[a-z0-9][a-z0-9-]*[a-z0-9]$/.test(manifest.id)) {
      this.add("error", "manifest.id", `${app}/umbrel-app.yml`, keyLine(content, "id"), "`id` must use lowercase kebab-case.");
    }

    if (!validManifestVersion(manifest.manifestVersion)) {
      this.add("error", "manifest.version", `${app}/umbrel-app.yml`, keyLine(content, "manifestVersion"), "`manifestVersion` must be a numeric app-framework version such as `1` or `1.2`.");
    }

    for (const field of STRING_MANIFEST_FIELDS) {
      if (manifest[field] !== undefined && typeof manifest[field] !== "string") {
        this.add("error", `manifest.${toRuleName(field)}`, `${app}/umbrel-app.yml`, keyLine(content, field), `\`${field}\` must be a string.`);
      }
    }

    for (const field of OPTIONAL_STRING_MANIFEST_FIELDS) {
      if (manifest[field] !== undefined && typeof manifest[field] !== "string") {
        this.add("error", `manifest.${toRuleName(field)}`, `${app}/umbrel-app.yml`, keyLine(content, field), `\`${field}\` must be a string when set.`);
      }
    }

    for (const field of OPTIONAL_BOOLEAN_MANIFEST_FIELDS) {
      if (manifest[field] !== undefined && typeof manifest[field] !== "boolean") {
        this.add("error", `manifest.${toRuleName(field)}`, `${app}/umbrel-app.yml`, keyLine(content, field), `\`${field}\` must be true or false when set.`);
      }
    }

    // A few existing manifests use numeric project names here. Keep accepting
    // numbers so the linter does not force unrelated metadata churn.
    if (manifest.developer !== undefined && typeof manifest.developer !== "string" && typeof manifest.developer !== "number") {
      this.add("error", "manifest.developer", `${app}/umbrel-app.yml`, keyLine(content, "developer"), "`developer` must be a string.");
    }

    if (manifest.submitter !== undefined && typeof manifest.submitter !== "string" && typeof manifest.submitter !== "number") {
      this.add("error", "manifest.submitter", `${app}/umbrel-app.yml`, keyLine(content, "submitter"), "`submitter` must be a string.");
    }

    if (typeof manifest.category === "string" && !VALID_CATEGORIES.has(manifest.category)) {
      this.add("error", "manifest.category", `${app}/umbrel-app.yml`, keyLine(content, "category"), `Unknown category \`${manifest.category}\`.`);
    }

    for (const field of ["name", "version", "tagline", "description", "website", "support", "submitter", "submission"]) {
      if (typeof manifest[field] === "string" && manifest[field].trim() === "") {
        this.add("error", `manifest.${toRuleName(field)}`, `${app}/umbrel-app.yml`, keyLine(content, field), `\`${field}\` must not be empty.`);
      }
    }

    if (typeof manifest.website === "string" && !validUrl(manifest.website)) {
      this.add("error", "manifest.website", `${app}/umbrel-app.yml`, keyLine(content, "website"), "`website` must be a valid URL.");
    }

    if (typeof manifest.repo === "string" && manifest.repo !== "" && !validUrl(manifest.repo)) {
      this.add("error", "manifest.repo", `${app}/umbrel-app.yml`, keyLine(content, "repo"), "`repo` must be empty or a valid URL.");
    }

    if (typeof manifest.submission === "string" && !validUrl(manifest.submission)) {
      this.add("error", "manifest.submission", `${app}/umbrel-app.yml`, keyLine(content, "submission"), "`submission` must be a valid pull request URL.");
    }

    const port = manifest.port;
    if (!Number.isInteger(port) || port <= 0 || port > 65535) {
      this.add("error", "manifest.port", `${app}/umbrel-app.yml`, keyLine(content, "port"), "`port` must be an integer from 1 to 65535.");
    } else {
      const conflicts = conflictingPortEntries(this.portIndex, port, "tcp", app);
      if (conflicts.length > 0) {
        this.add("error", "manifest.port_unique", `${app}/umbrel-app.yml`, keyLine(content, "port"), `Manifest port ${port}/tcp conflicts with ${formatPortConflicts(conflicts)}.`);
      }
    }

    if (typeof manifest.path !== "string" || !(manifest.path === "" || manifest.path.startsWith("/"))) {
      this.add("error", "manifest.path", `${app}/umbrel-app.yml`, keyLine(content, "path"), "`path` must be empty or start with `/`.");
    }

    this.lintManifestList(app, content, manifest, "dependencies", (dependency) => this.lintDependency(app, content, dependency));
    this.lintManifestList(app, content, manifest, "implements", (implementedApp) => this.lintImplementedApp(app, content, implementedApp));
    this.lintManifestList(app, content, manifest, "permissions", (permission) => this.lintPermission(app, content, permission));
    this.lintManifestList(app, content, manifest, "gallery");
    this.lintManifestList(app, content, manifest, "backupIgnore", (ignoredPath) => this.lintBackupIgnorePath(app, content, ignoredPath));
    this.lintWidgets(app, manifest, content);

    if (this.isNewApp(app)) {
      if (typeof manifest.releaseNotes !== "string") {
        this.add("error", "manifest.release_notes", `${app}/umbrel-app.yml`, keyLine(content, "releaseNotes"), "`releaseNotes` must be set to an empty string for new app submissions.");
      } else if (manifest.releaseNotes.length > 0) {
        this.add("error", "manifest.release_notes", `${app}/umbrel-app.yml`, keyLine(content, "releaseNotes"), "`releaseNotes` must be empty for new app submissions.");
      }

      if (Array.isArray(manifest.gallery) && manifest.gallery.length > 0) {
        this.add("warning", "manifest.gallery", `${app}/umbrel-app.yml`, keyLine(content, "gallery"), "Leave `gallery: []` for new official App Store submissions; Umbrel will create final gallery assets.");
      }

      if (typeof manifest.icon === "string" && manifest.icon.length > 0) {
        this.add("warning", "manifest.icon", `${app}/umbrel-app.yml`, keyLine(content, "icon"), "Omit `icon` for new official App Store submissions; Umbrel will create and host the final icon asset.");
      }
    } else {
      const baseManifest = this.baseManifest(app);
      const versionChanged = baseManifest && manifest.version !== undefined && baseManifest.version !== undefined && manifest.version.toString() !== baseManifest.version.toString();
      const releaseNotesBlank = typeof manifest.releaseNotes !== "string" || manifest.releaseNotes.trim() === "";
      if (versionChanged && releaseNotesBlank) {
        this.add("warning", "manifest.release_notes", `${app}/umbrel-app.yml`, keyLine(content, "releaseNotes"), "Existing app updates should include user-facing `releaseNotes` for the Umbrel update dialog.");
      }
    }
  }

  lintManifestList(app, content, manifest, field, lintItem = null) {
    if (manifest[field] === undefined) return;

    if (!Array.isArray(manifest[field])) {
      this.add("error", `manifest.${toRuleName(field)}`, `${app}/umbrel-app.yml`, keyLine(content, field), `\`${field}\` must be a list.`);
      return;
    }

    const seen = new Set();
    for (const item of manifest[field]) {
      if (typeof item !== "string") {
        this.add("error", `manifest.${toRuleName(field)}`, `${app}/umbrel-app.yml`, keyLine(content, field), `\`${field}\` entries must be strings.`);
        continue;
      }

      if (seen.has(item)) {
        this.add("error", `manifest.${toRuleName(field)}`, `${app}/umbrel-app.yml`, keyLine(content, field), `\`${field}\` contains duplicate entry \`${item}\`.`);
        continue;
      }
      seen.add(item);

      if (lintItem) lintItem(item);
    }
  }

  lintDependency(app, content, dependency) {
    if (dependency === app) {
      this.add("error", "manifest.dependencies", `${app}/umbrel-app.yml`, keyLine(content, "dependencies"), "An app cannot depend on itself.");
    } else if (!this.appDirs.includes(dependency)) {
      this.add("error", "manifest.dependencies", `${app}/umbrel-app.yml`, keyLine(content, "dependencies"), `Unknown dependency app \`${dependency}\`.`);
    } else if (this.appDisabled(dependency)) {
      this.add("error", "manifest.dependencies", `${app}/umbrel-app.yml`, keyLine(content, "dependencies"), `Dependency app \`${dependency}\` is disabled and is not available in the active App Store.`);
    }
  }

  lintImplementedApp(app, content, implementedApp) {
    if (implementedApp === app) {
      this.add("error", "manifest.implements", `${app}/umbrel-app.yml`, keyLine(content, "implements"), "An app cannot implement itself.");
    } else if (!this.appDirs.includes(implementedApp)) {
      this.add("error", "manifest.implements", `${app}/umbrel-app.yml`, keyLine(content, "implements"), `Unknown implemented app \`${implementedApp}\`.`);
    } else if (this.appDisabled(implementedApp)) {
      this.add("error", "manifest.implements", `${app}/umbrel-app.yml`, keyLine(content, "implements"), `Implemented app \`${implementedApp}\` is disabled and is not available in the active App Store.`);
    }
  }

  lintPermission(app, content, permission) {
    if (!VALID_PERMISSIONS.has(permission)) {
      this.add("error", "manifest.permissions", `${app}/umbrel-app.yml`, keyLine(content, "permissions"), `Unknown permission \`${permission}\`.`);
    }
  }

  lintBackupIgnorePath(app, content, ignoredPath) {
    if (!validBackupIgnorePath(ignoredPath)) {
      this.add("error", "manifest.backup_ignore", `${app}/umbrel-app.yml`, keyLine(content, "backupIgnore"), `Invalid backupIgnore path \`${ignoredPath}\`.`);
    }

    if (["*", "/*", ".", "./", "data", "data/"].includes(ignoredPath)) {
      this.add("warning", "manifest.backup_ignore", `${app}/umbrel-app.yml`, keyLine(content, "backupIgnore"), `backupIgnore path \`${ignoredPath}\` appears to exclude too much app data.`);
    }
  }

  lintWidgets(app, manifest, content) {
    if (manifest.widgets === undefined) return;

    if (!Array.isArray(manifest.widgets)) {
      this.add("error", "manifest.widgets", `${app}/umbrel-app.yml`, keyLine(content, "widgets"), "`widgets` must be a list.");
      return;
    }

    const ids = new Set();
    for (const widget of manifest.widgets) {
      if (!isObject(widget)) {
        this.add("error", "manifest.widgets", `${app}/umbrel-app.yml`, keyLine(content, "widgets"), "Each widget must be a YAML object.");
        continue;
      }

      for (const field of ["id", "type", "refresh", "endpoint"]) {
        if (typeof widget[field] !== "string" || widget[field] === "") {
          this.add("error", "manifest.widgets", `${app}/umbrel-app.yml`, keyLine(content, "widgets"), `Widget \`${field}\` must be a non-empty string.`);
        }
      }

      if (typeof widget.link !== "string") {
        this.add("error", "manifest.widgets", `${app}/umbrel-app.yml`, keyLine(content, "widgets"), "Widget `link` must be a string.");
      }

      if (!isObject(widget.example)) {
        this.add("error", "manifest.widgets", `${app}/umbrel-app.yml`, keyLine(content, "widgets"), "Widget `example` must be a YAML object.");
      }

      if (typeof widget.id === "string") {
        if (!/^[a-z0-9][a-z0-9-]*[a-z0-9]$/.test(widget.id)) {
          this.add("error", "manifest.widgets", `${app}/umbrel-app.yml`, keyLine(content, "widgets"), `Widget id \`${widget.id}\` must use lowercase kebab-case.`);
        }
        if (ids.has(widget.id)) {
          this.add("error", "manifest.widgets", `${app}/umbrel-app.yml`, keyLine(content, "widgets"), `Duplicate widget id \`${widget.id}\`.`);
        }
        ids.add(widget.id);
      }

      if (typeof widget.type === "string" && !WIDGET_TYPES.has(widget.type)) {
        this.add("error", "manifest.widgets", `${app}/umbrel-app.yml`, keyLine(content, "widgets"), `Unknown widget type \`${widget.type}\`.`);
      }

      if (typeof widget.endpoint === "string" && !validWidgetEndpoint(widget.endpoint)) {
        this.add("error", "manifest.widgets", `${app}/umbrel-app.yml`, keyLine(content, "widgets"), `Widget endpoint \`${widget.endpoint}\` must be in \`service:port/path\` format without a URL scheme.`);
      }
    }
  }

  async lintCompose(app, manifest, manifestContent, composePath) {
    if (!fs.existsSync(composePath)) {
      this.add("error", "compose.missing", `${app}/docker-compose.yml`, null, "Missing docker-compose.yml.");
      return;
    }

    const composeResult = this.parseYaml(composePath, `${app}/docker-compose.yml`);
    if (!composeResult) return;

    const { value: compose, content } = composeResult;
    if (!isObject(compose)) {
      this.add("error", "compose.type", `${app}/docker-compose.yml`, 1, "Compose file must be a YAML object.");
      return;
    }

    const services = compose.services;
    if (!isObject(services) || Object.keys(services).length === 0) {
      this.add("error", "compose.services", `${app}/docker-compose.yml`, keyLine(content, "services"), "Compose file must define at least one service.");
      return;
    }

    this.lintComposeRoot(app, content, compose);

    const staticExports = staticExportValues(app);
    let hasDownloadsMount = false;
    for (const [service, config] of Object.entries(services)) {
      if (!isObject(config)) continue;

      this.lintServiceBuild(app, content, service, config);
      await this.lintServiceImage(app, content, service, config);
      this.lintServiceRestart(app, content, service, config);
      this.lintServiceDependencies(app, content, service, config, services);
      this.lintServicePorts(app, content, service, config, manifest, services, staticExports);
      this.lintServiceAccess(app, content, service, config);
      if (this.lintServiceVolumes(app, content, service, config)) hasDownloadsMount = true;
    }

    if (hasDownloadsMount && !arrayIncludes(manifest.permissions, "STORAGE_DOWNLOADS")) {
      this.add("error", "permissions.downloads", `${app}/umbrel-app.yml`, keyLine(manifestContent, "permissions"), "Mounts Umbrel Downloads storage but does not declare `STORAGE_DOWNLOADS` in `permissions:`.");
    }

    this.lintAppProxy(app, content, services);
    this.lintLaunchRoute(app, manifest, content, services, staticExports);
  }

  lintComposeRoot(app, content, compose) {
    if (compose.networks !== undefined) {
      this.add("warning", "compose.networks", `${app}/docker-compose.yml`, keyLine(content, "networks"), "Top-level `networks:` is unusual for Umbrel apps; umbrelOS injects the default network.");
    }

    if (compose.volumes !== undefined) {
      this.add("warning", "compose.volumes", `${app}/docker-compose.yml`, keyLine(content, "volumes"), "Top-level Docker named volumes are unusual for Umbrel apps; persist app data with `${APP_DATA_DIR}` bind mounts.");
    }
  }

  lintServiceBuild(app, content, service, config) {
    if (config.build !== undefined) {
      this.add("error", "compose.build", `${app}/docker-compose.yml`, serviceKeyLine(content, service, "build"), `Service \`${service}\` must use a prebuilt image, not \`build:\`.`);
    }
  }

  async lintServiceImage(app, content, service, config) {
    const image = config.image;
    if (!image) return;

    if (typeof image !== "string") {
      this.add("error", "image.type", `${app}/docker-compose.yml`, serviceKeyLine(content, service, "image"), `Image for service \`${service}\` must be a string.`);
      return;
    }

    const parsed = parseImageRef(image);
    if (!parsed) {
      this.add("error", "image.pinned", `${app}/docker-compose.yml`, serviceKeyLine(content, service, "image"), `Image \`${image}\` must include both a tag and \`@sha256:\` digest.`);
      return;
    }

    if (parsed.tag === "latest") {
      this.add("error", "image.latest", `${app}/docker-compose.yml`, serviceKeyLine(content, service, "image"), `Image \`${image}\` uses the moving \`latest\` tag.`);
    }

    if (this.options.checkImages) {
      await this.checkImage(app, content, service, image, parsed);
    }
  }

  lintServiceRestart(app, content, service, config) {
    if (service === "app_proxy" || (config.image === undefined && config.build === undefined)) return;

    if (config.restart === undefined) {
      this.add("warning", "service.restart", `${app}/docker-compose.yml`, serviceLine(content, service), `Service \`${service}\` should set \`restart: on-failure\` unless it is an intentional one-shot service.`);
    } else if (config.restart !== "on-failure") {
      this.add("warning", "service.restart", `${app}/docker-compose.yml`, serviceKeyLine(content, service, "restart"), `Service \`${service}\` uses \`restart: ${config.restart}\`; use \`on-failure\` unless this service specifically needs different Docker restart behavior.`);
    }
  }

  lintServiceDependencies(app, content, service, config, services) {
    for (const dependency of serviceDependencies(config.depends_on)) {
      if (!services[dependency.name]) {
        this.add("error", "service.depends_on", `${app}/docker-compose.yml`, serviceKeyLine(content, service, "depends_on"), `Service \`${service}\` depends on unknown service \`${dependency.name}\`.`);
        continue;
      }

      if (dependency.condition === "service_healthy" && !isObject(services[dependency.name]?.healthcheck)) {
        this.add("error", "service.depends_on", `${app}/docker-compose.yml`, serviceKeyLine(content, service, "depends_on"), `Service \`${service}\` waits for \`${dependency.name}\` to be healthy, but \`${dependency.name}\` has no healthcheck.`);
      }
    }
  }

  lintServicePorts(app, content, service, config, manifest, services, staticExports) {
    if (config.ports === undefined) return;

    if (!Array.isArray(config.ports)) {
      this.add("error", "ports.type", `${app}/docker-compose.yml`, serviceKeyLine(content, service, "ports"), `Service \`${service}\` ports must be a list.`);
      return;
    }

    const line = serviceKeyLine(content, service, "ports");
    for (const portMapping of config.ports) {
      const parsed = parsePortMapping(portMapping, staticExports);

      if (!parsed) {
        this.add("error", "ports.format", `${app}/docker-compose.yml`, line, `Service \`${service}\` has an invalid port mapping.`);
        continue;
      }

      if (!parsed.explicit) {
        this.add("error", "ports.explicit", `${app}/docker-compose.yml`, line, `Service \`${service}\` must use explicit host:container port mappings.`);
        continue;
      }

      if (parsed.unresolvedHost) {
        this.add("warning", "ports.unresolved", `${app}/docker-compose.yml`, line, `Service \`${service}\` publishes unresolved host port \`${parsed.hostValue}\`; verify it does not conflict with app manifest ports, other app ports, or umbrelOS reserved ports.`);
        continue;
      }

      const allConflicts = portEntries(this.portIndex, parsed.publishedPort, parsed.protocol);
      const conflicts = allConflicts.filter((entry) => {
        if (entry.app !== app) return true;
        // Non-app_proxy apps often publish their own manifest port directly.
        if (entry.kind === "manifest") return false;
        return !(entry.service === service && entry.kind === "compose");
      });
      if (conflicts.length > 0) {
        const sameAppConflicts = conflicts.filter((entry) => entry.app === app);
        const severity = parsed.protocol === "udp" && sameAppConflicts.length === 0 ? "warning" : "error";
        const message = portConflictMessage(service, parsed.publishedPort, parsed.protocol, conflicts);
        this.add(severity, "ports.unique", `${app}/docker-compose.yml`, line, message);
      }

      if (services.app_proxy && parsed.protocol === "tcp" && parsed.publishedPort === manifest.port) {
        this.add("error", "ports.app_proxy", `${app}/docker-compose.yml`, line, `Service \`${service}\` publishes the manifest port ${manifest.port}/tcp, which is already used by app_proxy.`);
      }
    }
  }

  lintServiceAccess(app, content, service, config) {
    if (config.container_name !== undefined) {
      this.add("warning", "service.container_name", `${app}/docker-compose.yml`, serviceKeyLine(content, service, "container_name"), `Service \`${service}\` sets \`container_name\`; Umbrel injects container names automatically.`);
    }

    if (config.privileged === true) {
      this.add("warning", "access.privileged", `${app}/docker-compose.yml`, serviceKeyLine(content, service, "privileged"), `Service \`${service}\` uses \`privileged: true\`; justify this in the PR.`);
    }

    if (config.network_mode === "host") {
      this.add("warning", "access.host_network", `${app}/docker-compose.yml`, serviceKeyLine(content, service, "network_mode"), `Service \`${service}\` uses host networking; justify this in the PR.`);
    }

    if (Array.isArray(config.devices) && config.devices.length > 0) {
      this.add("warning", "access.devices", `${app}/docker-compose.yml`, serviceKeyLine(content, service, "devices"), `Service \`${service}\` maps host devices; justify this in the PR.`);
    }

    if (Array.isArray(config.cap_add) && config.cap_add.length > 0) {
      this.add("warning", "access.cap_add", `${app}/docker-compose.yml`, serviceKeyLine(content, service, "cap_add"), `Service \`${service}\` adds Linux capabilities; justify this in the PR.`);
    }

    if (Array.isArray(config.security_opt) && config.security_opt.length > 0) {
      this.add("warning", "access.security_opt", `${app}/docker-compose.yml`, serviceKeyLine(content, service, "security_opt"), `Service \`${service}\` sets security options; justify this in the PR.`);
    }

    for (const field of ["pid", "ipc", "uts", "cgroupns_mode", "userns_mode"]) {
      if (config[field] === "host") {
        this.add("warning", `access.${toRuleName(field)}`, `${app}/docker-compose.yml`, serviceKeyLine(content, service, field), `Service \`${service}\` uses host ${field}; justify this in the PR.`);
      }
    }
  }

  lintServiceVolumes(app, content, service, config) {
    const volumes = config.volumes;
    if (!Array.isArray(volumes)) return false;

    let hasDownloadsMount = false;
    for (const volume of volumes) {
      if (typeof volume !== "string") {
        // umbrelOS mutates compose volume strings during app install/update.
        this.add("error", "volumes.syntax", `${app}/docker-compose.yml`, serviceKeyLine(content, service, "volumes"), "Use short-syntax string bind mounts; umbrelOS compose patching expects volume strings.");
        continue;
      }

      const source = volumeSource(volume);
      if (!source) continue;

      const line = serviceKeyLine(content, service, "volumes");

      if (source.includes("/var/run/docker.sock") || source.includes("/run/docker.sock")) {
        this.add("error", "access.docker_socket", `${app}/docker-compose.yml`, line, "Do not mount the Docker socket; it gives the container host-level Docker control.");
      }

      if (directAppDataMount(source)) {
        this.add("error", "persistence.app_data_root", `${app}/docker-compose.yml`, line, "Do not bind mount `${APP_DATA_DIR}` directly; use a subdirectory such as `${APP_DATA_DIR}/data/...`.");
      }

      const appDataPath = appDataSubpath(source);
      if (appDataPath) {
        if (!appDataPath.includes("$") && !committedAppDataPathExists(app, appDataPath)) {
          this.add("warning", "persistence.missing_source", `${app}/docker-compose.yml`, line, `Bind mount source \`${source}\` is not committed at \`${app}/${appDataPath}\`.`);
        }
      }

      if (downloadsMount(source)) hasDownloadsMount = true;

      if (broadHostMount(source)) {
        this.add("warning", "access.host_mount", `${app}/docker-compose.yml`, line, `Host mount \`${source}\` should be justified in the PR.`);
      }
    }

    return hasDownloadsMount;
  }

  lintAppProxy(app, content, services) {
    const proxy = services.app_proxy;
    if (!isObject(proxy)) return;

    const environment = environmentMap(proxy.environment);
    let targetService = null;
    if (!environment.has("APP_HOST")) {
      this.add("error", "app_proxy.host", `${app}/docker-compose.yml`, serviceKeyLine(content, "app_proxy", "environment"), "`app_proxy` must set `APP_HOST`.");
    } else {
      const appHost = environment.get("APP_HOST");
      targetService = appProxyTargetService(app, services, appHost);
      if (typeof appHost === "string" && !appHost.includes("$") && !targetService) {
        this.add("error", "app_proxy.host", `${app}/docker-compose.yml`, serviceKeyLine(content, "app_proxy", "environment"), `APP_HOST \`${appHost}\` must point to a service in this compose file.`);
      }
    }

    const appPort = environment.get("APP_PORT");
    if (appPort === undefined) {
      this.add("error", "app_proxy.port", `${app}/docker-compose.yml`, serviceKeyLine(content, "app_proxy", "environment"), "`app_proxy` must set `APP_PORT` to the container's listening UI port.");
    } else if (!appPort.toString().startsWith("$") && !/^\d+$/.test(appPort.toString())) {
      this.add("error", "app_proxy.port", `${app}/docker-compose.yml`, serviceKeyLine(content, "app_proxy", "environment"), "`APP_PORT` must be numeric unless it is provided by an environment variable.");
    }

    this.lintAppProxyAuth(app, environment, content);

    if (targetService && services[targetService]?.network_mode === "host") {
      this.add("error", "app_proxy.host_network", `${app}/docker-compose.yml`, serviceKeyLine(content, "app_proxy", "environment"), "`app_proxy` cannot route to a service using host networking.");
    }
  }

  lintAppProxyAuth(app, environment, content) {
    const authAdd = environment.get("PROXY_AUTH_ADD");
    if (authAdd !== undefined) {
      const normalized = authAdd.toString().toLowerCase();
      if (!["true", "false"].includes(normalized)) {
        this.add("error", "app_proxy.auth", `${app}/docker-compose.yml`, serviceKeyLine(content, "app_proxy", "environment"), "`PROXY_AUTH_ADD` must be `true` or `false`.");
      }
    }

    for (const key of ["PROXY_AUTH_WHITELIST", "PROXY_AUTH_BLACKLIST"]) {
      const value = environment.get(key);
      if (value === undefined) continue;

      if (value.toString().trim() === "") {
        this.add("error", "app_proxy.auth", `${app}/docker-compose.yml`, serviceKeyLine(content, "app_proxy", "environment"), `\`${key}\` must not be empty when set.`);
      }

      if (hasBroadProxyAuthPattern(value.toString())) {
        this.add("warning", "app_proxy.auth", `${app}/docker-compose.yml`, serviceKeyLine(content, "app_proxy", "environment"), `\`${key}\` includes a broad route; keep auth bypass paths as narrow as possible.`);
      }
    }

    if (authAdd?.toString().toLowerCase() === "false" && environment.has("PROXY_AUTH_WHITELIST")) {
      this.add("warning", "app_proxy.auth", `${app}/docker-compose.yml`, serviceKeyLine(content, "app_proxy", "environment"), "`PROXY_AUTH_WHITELIST` has no effect when `PROXY_AUTH_ADD` is false.");
    }
  }

  lintLaunchRoute(app, manifest, content, services, staticExports) {
    if (services.app_proxy) return;

    const publishedPorts = publishedPortsForServices(services, staticExports);
    if (Number.isInteger(manifest.port) && publishedPorts.includes(manifest.port)) return;

    const hasHostNetworkService = Object.values(services).some((service) => isObject(service) && service.network_mode === "host");
    if (hasHostNetworkService) return;

    this.add("error", "app.launch", `${app}/docker-compose.yml`, keyLine(content, "services"), "App must be launchable through `app_proxy`, a raw published manifest port, or host networking.");
  }

  lintHooks(app) {
    const hooksDir = path.join(ROOT, app, "hooks");
    if (!fs.existsSync(hooksDir)) return;

    for (const entry of fs.readdirSync(hooksDir).sort()) {
      if (entry === ".gitkeep") continue;

      const hookPath = path.join(hooksDir, entry);
      const file = `${app}/hooks/${entry}`;

      if (!VALID_HOOKS.has(entry)) {
        this.add("error", "hooks.name", file, null, `\`${entry}\` is not a supported hook name.`);
      }

      if (!fs.statSync(hookPath).isFile()) continue;

      if ((fs.statSync(hookPath).mode & 0o111) === 0) {
        this.add("error", "hooks.executable", file, null, "Hook files must be executable.");
      }

      const firstLine = fs.readFileSync(hookPath, "utf8").split(/\r?\n/, 1)[0] || "";
      if (!firstLine.startsWith("#!")) {
        this.add("warning", "hooks.shebang", file, 1, "Hook files should start with a shebang.");
      }

    }
  }

  lintExports(app) {
    const exportsPath = path.join(ROOT, app, "exports.sh");
    if (!fs.existsSync(exportsPath)) return;

    const file = `${app}/exports.sh`;
    const stat = fs.statSync(exportsPath);
    const content = fs.readFileSync(exportsPath, "utf8");
    const firstLine = content.split(/\r?\n/, 1)[0] || "";

    if ((stat.mode & 0o111) !== 0) {
      this.add("warning", "exports.executable", file, null, "`exports.sh` is sourced by Umbrel and does not need executable permissions.");
    }

    if (firstLine.startsWith("#!")) {
      this.add("warning", "exports.shebang", file, 1, "`exports.sh` is sourced by Umbrel and does not need a shebang.");
    }

    const exitLine = lineMatching(content, /^\s*exit\b/);
    if (exitLine) {
      this.add("error", "exports.exit", file, exitLine, "`exports.sh` must not call `exit` because it is sourced by Umbrel.");
    }

    const cdLine = lineMatching(content, /^\s*cd\b/);
    if (cdLine) {
      this.add("error", "exports.cd", file, cdLine, "`exports.sh` must not change the caller's working directory.");
    }

    const setLine = lineMatching(content, /^\s*set\s+-/);
    if (setLine) {
      this.add("error", "exports.shell_options", file, setLine, "`exports.sh` must not change shell options because it is sourced by Umbrel.");
    }

    const lifecycleLine = lineMatching(content, /^\s*(docker|mkdir|chown|chmod)\b/);
    if (lifecycleLine) {
      this.add("warning", "exports.lifecycle", file, lifecycleLine, "`exports.sh` should only export values; move Docker, directory, and ownership work to compose, templates, or hooks.");
    }
  }

  lintTemplates(app) {
    for (const filePath of walkFiles(path.join(ROOT, app))) {
      if (!filePath.endsWith(".template")) continue;

      const relative = path.relative(ROOT, filePath);
      const appRelative = path.relative(path.join(ROOT, app), filePath);
      const outputPath = filePath.slice(0, -".template".length);

      if (appRelative.includes(path.sep)) {
        this.add("warning", "templates.location", relative, null, "Only top-level `*.template` files are rendered automatically by umbrelOS.");
      }

      if (fs.existsSync(outputPath)) {
        this.add("warning", "templates.rendered_output", path.relative(ROOT, outputPath), null, "Do not commit rendered template output beside the `.template` file.");
      }
    }
  }

  lintPackageFiles(app) {
    for (const filePath of walkFiles(path.join(ROOT, app))) {
      const relative = path.relative(ROOT, filePath);
      if (
        new RegExp(`^${escapeRegex(app)}/(screenshots?|gallery)(/|$)`, "i").test(relative) ||
        new RegExp(`^${escapeRegex(app)}/(icon|logo|screenshot|gallery).*\\.(png|jpe?g|webp|gif|svg)$`, "i").test(relative)
      ) {
        this.add("warning", "package.review_assets", relative, null, "Do not commit App Store screenshots, gallery assets, or icon/logo assets; include them in the PR body instead.");
      }

      if (runtimeArtifactPath(relative)) {
        this.add("warning", "package.runtime_artifact", relative, null, "This looks like generated runtime data, logs, credentials, or a local database; commit it only if it is intentional seed/config data.");
      }
    }
  }

  buildPortIndex() {
    const ports = new Map();
    for (const reservedPort of RESERVED_HOST_PORTS) {
      addPortIndexEntry(ports, {
        app: null,
        file: null,
        kind: "reserved",
        label: reservedPort.label,
        port: reservedPort.port,
        protocol: reservedPort.protocol,
      });
    }

    for (const app of this.activeAppDirs) {
      const manifestResult = parseYamlQuietly(path.join(ROOT, app, "umbrel-app.yml"));
      if (isObject(manifestResult?.value) && Number.isInteger(manifestResult.value.port)) {
        addPortIndexEntry(ports, {
          app,
          file: `${app}/umbrel-app.yml`,
          kind: "manifest",
          port: manifestResult.value.port,
          protocol: "tcp",
        });
      }

      const composeResult = parseYamlQuietly(path.join(ROOT, app, "docker-compose.yml"));
      if (!isObject(composeResult?.value?.services)) continue;

      const staticExports = staticExportValues(app);
      for (const [service, config] of Object.entries(composeResult.value.services)) {
        if (!isObject(config) || !Array.isArray(config.ports)) continue;

        for (const portMapping of config.ports) {
          const parsed = parsePortMapping(portMapping, staticExports);
          if (!parsed?.explicit || !parsed.publishedPort) continue;

          addPortIndexEntry(ports, {
            app,
            file: `${app}/docker-compose.yml`,
            kind: "compose",
            port: parsed.publishedPort,
            protocol: parsed.protocol,
            service,
          });
        }
      }
    }
    return ports;
  }

  appDisabled(app) {
    const manifestResult = parseYamlQuietly(path.join(ROOT, app, "umbrel-app.yml"));
    return manifestResult?.value?.disabled === true;
  }

  isNewApp(app) {
    if (!this.baseRef) return false;

    try {
      execFileSync("git", ["cat-file", "-e", `${this.baseRef}:${app}/umbrel-app.yml`], {
        cwd: ROOT,
        stdio: "ignore",
      });
      return false;
    } catch {
      return true;
    }
  }

  baseManifest(app) {
    if (!this.baseRef) return null;

    try {
      const content = execFileSync("git", ["show", `${this.baseRef}:${app}/umbrel-app.yml`], {
        cwd: ROOT,
        encoding: "utf8",
      });
      const manifest = YAML.parse(content);
      return isObject(manifest) ? manifest : null;
    } catch {
      return null;
    }
  }

  async checkImage(app, content, service, image, parsed) {
    // Use the registry API instead of Docker so CI can verify public pullability
    // and architecture support without pulling or executing PR-supplied images.
    let tagResponse;
    try {
      tagResponse = await this.fetchImageManifest(parsed, parsed.tag);
    } catch (error) {
      this.add("error", "image.pullable", `${app}/docker-compose.yml`, serviceKeyLine(content, service, "image"), `Could not fetch public image manifest for \`${image}\`: ${error.message}`);
      return;
    }

    const tagDigest = normalizeDigest(tagResponse.digest);
    if (tagDigest && tagDigest !== parsed.digest) {
      this.add("warning", "image.digest", `${app}/docker-compose.yml`, serviceKeyLine(content, service, "image"), `Image \`${image}\` is pinned to ${parsed.digest}, but its tag now resolves to ${tagDigest}. The upstream publisher likely moved or rebuilt this tag after the package was pinned. Keep the existing digest unless this PR is intentionally updating that image.`);
    }

    let platformManifest = tagResponse.manifest;
    if (!tagDigest || tagDigest !== parsed.digest) {
      try {
        platformManifest = (await this.fetchImageManifest(parsed, parsed.digest)).manifest;
      } catch (error) {
        this.add("error", "image.pullable", `${app}/docker-compose.yml`, serviceKeyLine(content, service, "image"), `Could not fetch public image manifest for \`${image}\`: ${error.message}`);
        return;
      }
    }

    const platforms = manifestPlatforms(platformManifest);
    if (!platforms.has("linux/amd64") || !platforms.has("linux/arm64")) {
      this.add("error", "image.architecture", `${app}/docker-compose.yml`, serviceKeyLine(content, service, "image"), `Image \`${image}\` must publish a multi-platform manifest for linux/amd64 and linux/arm64.`);
    }
  }

  async fetchImageManifest(image, reference) {
    const cacheKey = `${image.apiHost}/${image.repository}@${reference}`;
    if (!this.imageManifestCache.has(cacheKey)) {
      this.imageManifestCache.set(cacheKey, fetchManifest(image, reference));
    }
    return this.imageManifestCache.get(cacheKey);
  }

  parseYaml(filePath, displayPath) {
    try {
      const content = fs.readFileSync(filePath, "utf8");
      return { value: YAML.parse(content), content };
    } catch (error) {
      this.add("error", "yaml.parse", displayPath, null, `${displayPath} is not valid YAML: ${error.message}`);
      return null;
    }
  }

  add(severity, rule, file, line, message) {
    this.issues.push({ severity, rule, file, line, message });
  }

  hasErrors() {
    return this.issues.some((issue) => issue.severity === "error");
  }

  report(apps) {
    if (this.options.format === "json") {
      console.log(JSON.stringify({ apps, issues: this.issues }, null, 2));
    } else if (this.options.format === "github") {
      reportGithub(apps, this.issues);
    } else {
      reportText(apps, this.issues);
    }
  }
}

function discoverAppDirs() {
  return fs
    .readdirSync(ROOT, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name)
    .filter((entry) => fs.existsSync(path.join(ROOT, entry, "umbrel-app.yml")))
    .sort();
}

function baseRefFromChangedRange(range) {
  return range ? range.split(/\.\.\.?/, 1)[0] : null;
}

function defaultBaseRef(options) {
  if (options.all || options.changed || options.apps.length === 0) return null;

  try {
    execFileSync("git", ["rev-parse", "--verify", "origin/master"], {
      cwd: ROOT,
      stdio: "ignore",
    });
    return "origin/master";
  } catch {
    return null;
  }
}

function validManifestVersion(value) {
  return (typeof value === "number" || typeof value === "string") && /^\d+(\.\d+){0,2}$/.test(value.toString());
}

function toRuleName(field) {
  return field.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`);
}

function validUrl(value) {
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

function validBackupIgnorePath(value) {
  if (!/^[-a-zA-Z0-9._/*]+$/.test(value)) return false;
  if (value.startsWith("/")) return false;

  const normalized = path.posix.normalize(value);
  return normalized !== ".." && !normalized.startsWith("../");
}

function validWidgetEndpoint(value) {
  if (value.includes("://")) return false;
  const match = value.match(/^[a-zA-Z0-9_-]+:\d+(\/.*)?$/);
  return Boolean(match);
}

function serviceDependencies(dependsOn) {
  if (dependsOn === undefined) return [];
  if (typeof dependsOn === "string") return [{ name: dependsOn, condition: null }];
  if (Array.isArray(dependsOn)) return dependsOn.filter((dependency) => typeof dependency === "string").map((name) => ({ name, condition: null }));
  if (!isObject(dependsOn)) return [];

  return Object.entries(dependsOn).map(([name, config]) => ({
    name,
    condition: isObject(config) && typeof config.condition === "string" ? config.condition : null,
  }));
}

function hasBroadProxyAuthPattern(value) {
  return value
    .split(/[,\s]+/)
    .map((pattern) => pattern.trim())
    .filter(Boolean)
    .some((pattern) => ["/", "/*", "/**"].includes(pattern));
}

function parseYamlQuietly(filePath) {
  try {
    const content = fs.readFileSync(filePath, "utf8");
    return { value: YAML.parse(content), content };
  } catch {
    return null;
  }
}

function addPortIndexEntry(ports, entry) {
  if (!Number.isInteger(entry.port) || !validPortNumber(entry.port)) return;
  const protocol = normalizeProtocol(entry.protocol);
  const key = portIndexKey(entry.port, protocol);
  if (!ports.has(key)) ports.set(key, []);
  ports.get(key).push({ ...entry, protocol });
}

function conflictingPortEntries(ports, port, protocol, app) {
  return portEntries(ports, port, protocol).filter((entry) => entry.app !== app);
}

function portEntries(ports, port, protocol) {
  return ports.get(portIndexKey(port, protocol)) || [];
}

function portIndexKey(port, protocol) {
  return `${normalizeProtocol(protocol)}:${port}`;
}

function normalizeProtocol(protocol) {
  return protocol?.toString().toLowerCase() === "udp" ? "udp" : "tcp";
}

function formatPortConflicts(entries) {
  return entries.map((entry) => {
    if (entry.kind === "reserved") return entry.label;
    if (entry.kind === "manifest") return `${entry.app} manifest`;
    if (entry.kind === "compose") return `${entry.app} compose service \`${entry.service}\``;
    return entry.app || "unknown entry";
  }).join(", ");
}

function portConflictMessage(service, port, protocol, conflicts) {
  const base = `Service \`${service}\` publishes host port ${port}/${protocol}, which conflicts with ${formatPortConflicts(conflicts)}.`;
  if (protocol !== "udp") return base;

  return `${base} UDP ports are often protocol or client-facing, so verify whether these apps can be co-installed or whether upstream supports changing the advertised public port.`;
}

function publishedPortsForServices(services, staticExports = new Map()) {
  const ports = [];
  for (const service of Object.values(services || {})) {
    if (!isObject(service) || !Array.isArray(service.ports)) continue;

    for (const portMapping of service.ports) {
      const parsed = parsePortMapping(portMapping, staticExports);
      if (parsed?.protocol === "tcp" && parsed?.publishedPort !== null && parsed?.publishedPort !== undefined) {
        ports.push(parsed.publishedPort);
      }
    }
  }
  return ports;
}

function parsePortMapping(portMapping, staticExports = new Map()) {
  if (typeof portMapping === "number") {
    return {
      explicit: false,
      hostValue: portMapping.toString(),
      publishedPort: validPortNumber(portMapping) ? portMapping : null,
      protocol: "tcp",
      unresolvedHost: false,
    };
  }

  if (typeof portMapping === "string") {
    const trimmed = portMapping.trim();
    const protocolMatch = trimmed.match(/\/(tcp|udp)$/i);
    const protocol = normalizeProtocol(protocolMatch?.[1]);
    const value = protocolMatch ? trimmed.slice(0, -protocolMatch[0].length) : trimmed;
    const parts = value.split(":");

    if (parts.length === 1) {
      return {
        explicit: false,
        hostValue: parts[0],
        publishedPort: resolvePortNumber(parts[0], staticExports),
        protocol,
        unresolvedHost: false,
      };
    }

    if (parts.length === 2 || parts.length === 3) {
      const hostValue = parts.at(-2);
      const publishedPort = resolvePortNumber(hostValue, staticExports);
      return {
        explicit: true,
        hostValue,
        publishedPort,
        protocol,
        unresolvedHost: publishedPort === null,
      };
    }

    return {
      explicit: true,
      hostValue: value,
      publishedPort: null,
      protocol,
      unresolvedHost: true,
    };
  }

  if (isObject(portMapping)) {
    const hostValue = portMapping.published;
    const publishedPort = resolvePortNumber(hostValue, staticExports);
    return {
      explicit: portMapping.published !== undefined,
      hostValue: hostValue?.toString() || "",
      publishedPort,
      protocol: normalizeProtocol(portMapping.protocol),
      unresolvedHost: portMapping.published !== undefined && publishedPort === null,
    };
  }

  return null;
}

function staticExportValues(app) {
  const exportsPath = path.join(ROOT, app, "exports.sh");
  const values = new Map();
  if (!fs.existsSync(exportsPath)) return values;

  // Do not execute exports.sh here. Only simple numeric exports are resolved so
  // port collision checks stay deterministic and side-effect free.
  const content = fs.readFileSync(exportsPath, "utf8");
  for (const line of content.split(/\r?\n/)) {
    const match = line.match(/^export\s+([A-Z_][A-Z0-9_]*)=(?:"(\d+)"|'(\d+)'|(\d+))\s*(?:#.*)?$/);
    if (!match) continue;

    values.set(match[1], match[2] || match[3] || match[4]);
  }
  return values;
}

function resolvePortNumber(value, staticExports) {
  const direct = parsePortNumber(value);
  if (direct !== null) return direct;
  if (typeof value !== "string") return null;

  const variable = value.match(/^\$([A-Z_][A-Z0-9_]*)$/) || value.match(/^\$\{([A-Z_][A-Z0-9_]*)\}$/);
  if (!variable) return null;

  return parsePortNumber(staticExports.get(variable[1]));
}

function parsePortNumber(value) {
  if (typeof value === "number") return validPortNumber(value) ? value : null;
  if (typeof value !== "string") return null;
  if (!/^\d+$/.test(value)) return null;

  const parsed = Number(value);
  return validPortNumber(parsed) ? parsed : null;
}

function validPortNumber(value) {
  return Number.isInteger(value) && value > 0 && value <= 65535;
}

function committedAppDataPathExists(app, appDataPath) {
  const normalized = path.normalize(appDataPath);
  const committedPath = path.join(ROOT, app, normalized);
  if (fs.existsSync(committedPath)) return true;

  if (!normalized.includes(path.sep)) {
    return fs.existsSync(`${committedPath}.template`);
  }

  return false;
}

function lineMatching(content, pattern) {
  const lines = content.split(/\r?\n/);
  const index = lines.findIndex((line) => pattern.test(line));
  return index === -1 ? null : index + 1;
}

function runtimeArtifactPath(relative) {
  const basename = path.basename(relative).toLowerCase();
  if (basename.endsWith(".template")) return false;

  return (
    basename === ".env" ||
    /\.(db|sqlite|sqlite3|log|pid|sock|pem|key)$/i.test(basename)
  );
}

function appProxyTargetService(app, services, appHost) {
  if (typeof appHost !== "string") return null;

  for (const [serviceName, config] of Object.entries(services)) {
    if (serviceName === "app_proxy" || !isObject(config)) continue;

    const validHosts = new Set([serviceName, `${app}_${serviceName}_1`]);
    // Some released packages set container_name; app_proxy still resolves it,
    // but new packages should rely on Umbrel's injected container names.
    if (typeof config.container_name === "string") validHosts.add(config.container_name);
    if (validHosts.has(appHost)) return serviceName;
  }

  return null;
}

function parseImageRef(image) {
  const match = image.match(/^(?<name>.+):(?<tag>[^:@/]+)@sha256:(?<digest>[a-fA-F0-9]{64})$/);
  if (!match?.groups) return null;

  const parts = match.groups.name.split("/");
  let registry = "docker.io";
  if (parts[0].includes(".") || parts[0].includes(":") || parts[0] === "localhost") {
    registry = parts.shift();
  }

  let repository = parts.join("/");
  if (registry === "docker.io" && !repository.includes("/")) repository = `library/${repository}`;

  return {
    registry,
    apiHost: registry === "docker.io" ? "registry-1.docker.io" : registry,
    repository,
    tag: match.groups.tag,
    digest: `sha256:${match.groups.digest.toLowerCase()}`,
  };
}

async function fetchManifest(image, reference) {
  const url = `https://${image.apiHost}/v2/${image.repository}/manifests/${encodeURIComponent(reference)}`;
  let response = await fetchWithRetry(url, {
    headers: { Accept: IMAGE_ACCEPT_HEADER },
  });

  if (response.status === 401) {
    const token = await bearerToken(response.headers.get("www-authenticate"), image);
    response = await fetchWithRetry(url, {
      headers: {
        Accept: IMAGE_ACCEPT_HEADER,
        Authorization: `Bearer ${token}`,
      },
    });
  }

  if (!response.ok) {
    throw new Error(registryHttpError(response));
  }

  return {
    manifest: await response.json(),
    digest: response.headers.get("docker-content-digest"),
  };
}

const TOKEN_CACHE = new Map();

async function bearerToken(header, image) {
  if (!header) throw new Error("registry requires authentication but did not provide a bearer challenge");
  if (!header.startsWith("Bearer ")) throw new Error("only bearer registry authentication is supported");

  const values = new Map();
  for (const [, key, value] of header.matchAll(/(\w+)="([^"]*)"/g)) {
    values.set(key, value);
  }

  const realm = values.get("realm");
  if (!realm) throw new Error("registry bearer challenge is missing realm");
  const url = new URL(realm);
  if (!validTokenRealm(url, image)) throw new Error(`registry bearer realm ${url.origin} is not allowed for ${image.registry}`);

  const service = values.get("service");
  const scope = values.get("scope") || `repository:${image.repository}:pull`;
  const cacheKey = `${realm}|${service || ""}|${scope}`;
  if (TOKEN_CACHE.has(cacheKey)) return TOKEN_CACHE.get(cacheKey);

  if (service) url.searchParams.set("service", service);
  url.searchParams.set("scope", scope);

  const response = await fetchWithRetry(url);
  if (!response.ok) throw new Error(`token request failed with HTTP ${response.status}`);

  const body = await response.json();
  const token = body.token || body.access_token;
  if (!token) throw new Error("token response did not include a token");
  TOKEN_CACHE.set(cacheKey, token);
  return token;
}

async function fetchWithTimeout(url, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 20_000);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } finally {
    clearTimeout(timeout);
  }
}

async function fetchWithRetry(url, options = {}) {
  let lastError;
  for (let attempt = 0; attempt < 2; attempt += 1) {
    try {
      const response = await fetchWithTimeout(url, options);
      if (!retryableHttpStatus(response.status) || attempt === 1) return response;
    } catch (error) {
      lastError = error;
      if (attempt === 1) throw error;
    }

    await delay(1_000);
  }

  throw lastError;
}

function retryableHttpStatus(status) {
  return status === 429 || status === 500 || status === 502 || status === 503 || status === 504;
}

function registryHttpError(response) {
  if (response.status === 429) return "HTTP 429 rate limited by registry";
  return `HTTP ${response.status}`;
}

function validTokenRealm(url, image) {
  if (url.protocol !== "https:") return false;

  const allowedHosts = new Set([image.apiHost]);
  if (image.registry === "docker.io") allowedHosts.add("auth.docker.io");

  return allowedHosts.has(url.hostname);
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function manifestPlatforms(manifest) {
  const platforms = new Set();
  if (!Array.isArray(manifest?.manifests)) return platforms;

  for (const entry of manifest.manifests) {
    const platform = entry.platform;
    if (platform?.os && platform?.architecture) {
      platforms.add(`${platform.os}/${platform.architecture}`);
    }
  }
  return platforms;
}

function normalizeDigest(digest) {
  return typeof digest === "string" ? digest.toLowerCase() : null;
}

function volumeSource(volume) {
  if (typeof volume === "string") return volume.split(":", 1)[0];
  if (isObject(volume)) return volume.source;
  return null;
}

function directAppDataMount(source) {
  return /^\$\{?APP_DATA_DIR\}?\/?$/.test(source);
}

function appDataSubpath(source) {
  if (!source.includes("APP_DATA_DIR")) return null;
  const cleaned = source
    .replace(/^\$\{APP_DATA_DIR\}/, "")
    .replace(/^\$APP_DATA_DIR/, "")
    .replace(/^\//, "");
  return cleaned || null;
}

function downloadsMount(source) {
  return (
    source.includes("${UMBREL_ROOT}/data/storage/downloads") ||
    source.includes("$UMBREL_ROOT/data/storage/downloads") ||
    source.includes("/home/umbrel/umbrel/data/storage/downloads")
  );
}

function broadHostMount(source) {
  if (!source.startsWith("/")) return false;
  if (downloadsMount(source)) return false;
  if (source.includes("/var/run/docker.sock") || source.includes("/run/docker.sock")) return false;
  if (["/etc/localtime", "/etc/timezone"].includes(source)) return false;
  return true;
}

function environmentMap(environment) {
  const map = new Map();
  if (Array.isArray(environment)) {
    for (const entry of environment) {
      if (typeof entry !== "string") continue;
      const [key, ...value] = entry.split("=");
      map.set(key, value.join("="));
    }
  } else if (isObject(environment)) {
    for (const [key, value] of Object.entries(environment)) {
      map.set(key, String(value));
    }
  }
  return map;
}

function keyLine(content, key) {
  const lines = content.split(/\r?\n/);
  const regex = new RegExp(`^\\s*${escapeRegex(key)}\\s*:`);
  const index = lines.findIndex((line) => regex.test(line));
  return index === -1 ? null : index + 1;
}

function serviceKeyLine(content, service, key) {
  const lines = content.split(/\r?\n/);
  let inServices = false;
  let inService = false;
  let serviceIndent = null;

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    const stripped = line.trim();
    if (stripped.startsWith("#")) continue;

    if (/^services:\s*$/.test(line)) {
      inServices = true;
      continue;
    }
    if (!inServices) continue;

    const indent = line.match(/^ */)[0].length;
    if (indent === 2 && new RegExp(`^  ${escapeRegex(service)}:\\s*$`).test(line)) {
      inService = true;
      serviceIndent = indent;
      continue;
    }

    if (inService && indent <= serviceIndent && stripped !== "") {
      inService = false;
    }

    if (inService && new RegExp(`^ {4}${escapeRegex(key)}\\s*:`).test(line)) {
      return index + 1;
    }
  }

  return null;
}

function serviceLine(content, service) {
  const lines = content.split(/\r?\n/);
  let inServices = false;

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    const stripped = line.trim();
    if (stripped.startsWith("#")) continue;

    if (/^services:\s*$/.test(line)) {
      inServices = true;
      continue;
    }
    if (!inServices) continue;

    if (new RegExp(`^  ${escapeRegex(service)}:\\s*$`).test(line)) {
      return index + 1;
    }
  }

  return null;
}

function walkFiles(directory) {
  const files = [];
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) files.push(...walkFiles(fullPath));
    if (entry.isFile()) files.push(fullPath);
  }
  return files;
}

function reportText(apps, issues) {
  if (apps.length === 0 && issues.length === 0) {
    console.log("No active app packages to lint.");
    return;
  }

  if (apps.length > 0) console.log(`Linting ${apps.join(", ")}`);
  if (issues.length === 0) {
    console.log("No issues found.");
    return;
  }

  for (const issue of issues) {
    const location = issue.line ? `${issue.file}:${issue.line}` : issue.file;
    console.log(`${issue.severity.toUpperCase()} ${issue.rule} ${location}`);
    console.log(`  ${issue.message}`);
  }

  const errors = issues.filter((issue) => issue.severity === "error").length;
  const warnings = issues.filter((issue) => issue.severity === "warning").length;
  console.log(`${errors} error(s), ${warnings} warning(s).`);
}

function reportGithub(apps, issues) {
  for (const issue of issues) {
    const command = issue.severity === "error" ? "error" : "warning";
    const props = [`file=${githubProp(issue.file)}`, `title=${githubProp(issue.rule)}`];
    if (issue.line) props.push(`line=${issue.line}`);
    console.log(`::${command} ${props.join(",")}::${githubData(issue.message)}`);
  }

  const summaryPath = process.env.GITHUB_STEP_SUMMARY;
  if (summaryPath) {
    fs.appendFileSync(summaryPath, githubSummary(apps, issues));
  }

  if (apps.length === 0 && issues.length === 0) {
    console.log("No active app packages to lint.");
  } else if (issues.length === 0) {
    console.log("No lint issues found.");
  }
}

function githubSummary(apps, issues) {
  if (apps.length === 0 && issues.length === 0) {
    return [
      "## Umbrel app lint skipped",
      "",
      "No active app package changes were detected.",
      "",
    ].join("\n");
  }

  const errors = issues.filter((issue) => issue.severity === "error").length;
  const warnings = issues.filter((issue) => issue.severity === "warning").length;
  const heading = summaryHeading(errors, warnings);
  const lines = [
    heading,
    "",
    apps.length === 0 ? "Checked: no valid app packages" : `Checked: ${apps.map((app) => `\`${app}\``).join(", ")}`,
    "",
  ];

  if (issues.length === 0) {
    lines.push("No issues found.", "");
    return lines.join("\n");
  }

  lines.push(summaryStatus(errors, warnings), "");

  if (apps.length > 0) {
    lines.push(
      "### Reproduce locally",
      "",
      "```sh",
      "npm ci",
      `npm run lint:apps -- ${apps.join(" ")} --check-images`,
      "```",
      "",
      "### Agent handoff",
      "",
      summaryHandoff(apps, errors, warnings),
      "",
    );
  }

  lines.push("| Severity | Rule | Location | Issue |", "| --- | --- | --- | --- |");

  for (const issue of issues) {
    const location = issue.line ? `${issue.file}:${issue.line}` : issue.file;
    lines.push(`| ${titleCase(issue.severity)} | \`${markdownCell(issue.rule)}\` | \`${markdownCell(location)}\` | ${markdownCell(issue.message)} |`);
  }

  lines.push("");
  return lines.join("\n");
}

function summaryHeading(errors, warnings) {
  if (errors > 0) return "## Umbrel app lint failed";
  if (warnings > 0) return "## Umbrel app lint passed with warnings";
  return "## Umbrel app lint passed";
}

function summaryStatus(errors, warnings) {
  if (errors > 0) {
    return `Found ${plural(errors, "error")} and ${plural(warnings, "warning")}. Errors need to be resolved before merge. Warnings may be acceptable when intentional; explain them in the PR.`;
  }

  if (warnings > 0) {
    return `Found ${plural(warnings, "warning")}. Warnings do not fail the check, but explain them in the PR if they are intentional.`;
  }

  return "No issues found.";
}

function summaryHandoff(apps, errors, warnings) {
  const appList = apps.map((app) => `\`${app}\``).join(", ");
  if (errors > 0) {
    return `Fix the Umbrel app lint errors below. Keep the change scoped to ${appList}, then rerun the command above.`;
  }

  if (warnings > 0) {
    return `Review the warnings below. If they are intentional, explain them in the PR; otherwise keep the change scoped to ${appList} and rerun the command above.`;
  }

  return `No lint issues were found for ${appList}.`;
}

function plural(count, singular) {
  return `${count} ${singular}${count === 1 ? "" : "s"}`;
}

function titleCase(value) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function markdownCell(value) {
  return value
    .toString()
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll("`", "&#96;")
    .replaceAll("|", "\\|")
    .replaceAll("\n", "<br>");
}

function githubData(value) {
  return value.toString().replaceAll("%", "%25").replaceAll("\r", "%0D").replaceAll("\n", "%0A");
}

function githubProp(value) {
  return githubData(value).replaceAll(":", "%3A").replaceAll(",", "%2C");
}

function isObject(value) {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function arrayIncludes(value, expected) {
  return Array.isArray(value) && value.includes(expected);
}

function unique(values) {
  return [...new Set(values)];
}

function escapeRegex(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

const cliOptions = parseArgs(process.argv.slice(2));
ROOT = cliOptions.root;
const cliLinter = new AppLinter(cliOptions);
process.exit(await cliLinter.run());
