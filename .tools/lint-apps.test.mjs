import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { AppLinter } from "./lint-apps.mjs";

const digest = `sha256:${"a".repeat(64)}`;
const movedDigest = `sha256:${"b".repeat(64)}`;
const parsed = { tag: "1.2.3", digest };
const image = `example/app:${parsed.tag}@${digest}`;
const content = `services:\n  server:\n    image: ${image}\n`;

function manifestResponse(digest, architectures = ["amd64", "arm64"]) {
  return {
    digest,
    manifest: { manifests: architectures.map((architecture) => ({ platform: { os: "linux", architecture } })) },
  };
}

async function checkImage(responses, unchanged = true) {
  const calls = [];
  const linter = Object.create(AppLinter.prototype);
  linter.issues = [];
  linter.imageUnchanged = () => unchanged;
  linter.fetchImageManifest = async (_image, reference) => {
    calls.push(reference);
    assert.ok(Object.hasOwn(responses, reference), `Unexpected lookup: ${reference}`);
    const response = responses[reference];
    if (response instanceof Error) throw response;
    return response;
  };
  await linter.checkImage("example", content, "server", image, parsed);
  return { issues: linter.issues, calls };
}

function rules(issues) {
  return issues.map(({ severity, rule }) => [severity, rule]);
}

test("matching tag and digest reuse the verified manifest", async () => {
  const { issues, calls } = await checkImage({ [parsed.tag]: manifestResponse(digest) });
  assert.deepEqual(issues, []);
  assert.deepEqual(calls, [parsed.tag]);
});

for (const reason of ["HTTP 404", "HTTP 401", "HTTP 429 rate limited by registry", "HTTP 503", "fetch failed"]) {
  test(`unavailable tag (${reason}) warns for an unchanged reference with an available pin`, async () => {
    const { issues, calls } = await checkImage({
      [parsed.tag]: new Error(reason),
      [digest]: manifestResponse(digest),
    });
    assert.deepEqual(rules(issues), [["warning", "image.tag"]]);
    assert.ok(issues[0].message.includes(reason));
    assert.ok(issues[0].message.includes(digest));
    assert.match(issues[0].message, /investigat/i);
    assert.doesNotMatch(issues[0].message, /keep the existing digest/i);
    assert.deepEqual(calls, [parsed.tag, digest]);
  });
}

test("unavailable tag remains an error when the reference is not proven unchanged", async () => {
  const { issues, calls } = await checkImage({ [parsed.tag]: new Error("HTTP 404") }, false);
  assert.deepEqual(rules(issues), [["error", "image.tag"]]);
  assert.deepEqual(calls, [parsed.tag]);
});

test("missing tag and missing pinned digest still fail", async () => {
  const { issues, calls } = await checkImage({
    [parsed.tag]: new Error("HTTP 404"),
    [digest]: new Error("HTTP 404"),
  });
  assert.deepEqual(rules(issues), [["error", "image.pullable"]]);
  assert.ok(issues[0].message.includes(digest));
  assert.deepEqual(calls, [parsed.tag, digest]);
});

test("missing tag does not bypass pinned architecture validation", async () => {
  const { issues } = await checkImage({
    [parsed.tag]: new Error("HTTP 404"),
    [digest]: manifestResponse(digest, ["amd64"]),
  });
  assert.deepEqual(rules(issues), [["warning", "image.tag"], ["error", "image.architecture"]]);
});

test("a moved tag warns and checks the original pinned manifest", async () => {
  const { issues, calls } = await checkImage({
    [parsed.tag]: manifestResponse(movedDigest, ["amd64"]),
    [digest]: manifestResponse(digest),
  });
  assert.deepEqual(rules(issues), [["warning", "image.digest"]]);
  assert.deepEqual(calls, [parsed.tag, digest]);
});

test("a valid moved tag cannot hide a missing pinned digest", async () => {
  const { issues } = await checkImage({
    [parsed.tag]: manifestResponse(movedDigest),
    [digest]: new Error("HTTP 404"),
  });
  assert.deepEqual(rules(issues), [["warning", "image.digest"], ["error", "image.pullable"]]);
});

test("architecture validation follows the pin, not a moved tag", async () => {
  const { issues } = await checkImage({
    [parsed.tag]: manifestResponse(movedDigest),
    [digest]: manifestResponse(digest, ["amd64"]),
  });
  assert.deepEqual(rules(issues), [["warning", "image.digest"], ["error", "image.architecture"]]);
});

test("a tag response without a digest header requires a pinned lookup", async () => {
  const { issues, calls } = await checkImage({
    [parsed.tag]: manifestResponse(null),
    [digest]: manifestResponse(digest),
  });
  assert.deepEqual(issues, []);
  assert.deepEqual(calls, [parsed.tag, digest]);
});

test("matching tag still requires both supported architectures", async () => {
  const { issues } = await checkImage({ [parsed.tag]: manifestResponse(digest, ["arm64"]) });
  assert.deepEqual(rules(issues), [["error", "image.architecture"]]);
});

test("missing-tag eligibility uses the exact image in the base app and service", async (t) => {
  const fixture = fs.mkdtempSync(path.join(os.tmpdir(), "umbrel-image-lint-"));
  try {
    for (const [app, compose] of Object.entries({ example: content, malformed: "services: [" })) {
      fs.mkdirSync(path.join(fixture, app));
      fs.writeFileSync(path.join(fixture, app, "docker-compose.yml"), compose);
    }
    const git = (...args) => execFileSync("git", args, { cwd: fixture, stdio: "pipe" });
    git("init", "--quiet");
    git("add", ".");
    git("-c", "user.name=Lint Test", "-c", "user.email=lint@example.invalid", "-c", "commit.gpgsign=false", "commit", "--quiet", "-m", "Base image fixtures");
    // Eligibility must come from the Git base, not the current working copy.
    fs.writeFileSync(path.join(fixture, "example", "docker-compose.yml"), content.replace(digest, movedDigest));

    const cases = [
      { name: "unchanged reference", unchanged: true },
      { name: "changed tag", image: image.replace(":1.2.3@", ":2.0.0@") },
      { name: "changed digest", image: image.replace(digest, movedDigest) },
      { name: "changed registry", image: `ghcr.io/${image}` },
      { name: "changed repository", image: image.replace("example/app:", "example/other:") },
      { name: "new or renamed app", app: "new-app" },
      { name: "new or renamed service", service: "new-server" },
      { name: "no comparison baseline", changed: null },
      { name: "unreadable comparison baseline", changed: "missing-base..HEAD" },
      { name: "malformed base compose", app: "malformed" },
    ].map((entry) => ({ app: "example", service: "server", image, changed: "HEAD..HEAD", unchanged: false, ...entry }));

    // ROOT is module-global, so run this real Git fixture in a subprocess.
    const script = `
      import { AppLinter } from ${JSON.stringify(new URL("./lint-apps.mjs", import.meta.url).href)};
      const results = [];
      for (const entry of JSON.parse(process.argv[1])) {
        const linter = new AppLinter({ checkImages: true, changed: entry.changed });
        const calls = [];
        linter.fetchImageManifest = async (_image, reference) => {
          calls.push(reference);
          if (!reference.startsWith("sha256:")) throw new Error("HTTP 404");
          return { digest: reference, manifest: ${JSON.stringify(manifestResponse(digest).manifest)} };
        };
        const unchanged = linter.imageUnchanged(entry.app, entry.service, entry.image);
        await linter.lintServiceImage(entry.app, ${JSON.stringify(content)}, entry.service, { image: entry.image });
        results.push({ unchanged, calls, rules: linter.issues.map(({ severity, rule }) => [severity, rule]) });
      }
      console.log(JSON.stringify(results));
    `;
    const results = JSON.parse(execFileSync(process.execPath, ["--input-type=module", "-e", script, JSON.stringify(cases)], {
      cwd: fixture,
      env: { ...process.env, UMBREL_APP_LINT_ROOT: fixture },
      encoding: "utf8",
      stdio: ["ignore", "pipe", "pipe"],
    }));
    for (const [index, entry] of cases.entries()) {
      await t.test(entry.name, () => {
        const result = results[index];
        assert.equal(result.unchanged, entry.unchanged);
        assert.deepEqual(result.rules, [[entry.unchanged ? "warning" : "error", "image.tag"]]);
        assert.equal(result.calls.length, entry.unchanged ? 2 : 1);
      });
    }
  } finally {
    fs.rmSync(fixture, { recursive: true, force: true });
  }
});

test("CLI still handles help and invalid arguments with the expected exit status", () => {
  const cli = fileURLToPath(new URL("./lint-apps.mjs", import.meta.url));
  const help = spawnSync(process.execPath, [cli, "--help"], { encoding: "utf8" });
  assert.equal(help.status, 0);
  assert.match(help.stderr, /Usage:/);
  const invalid = spawnSync(process.execPath, [cli, "--not-a-real-option"], { encoding: "utf8" });
  assert.equal(invalid.status, 2);
  assert.match(invalid.stderr, /Unknown option/);
});
