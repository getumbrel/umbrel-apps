import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { test } from "node:test";
import YAML from "yaml";

const app = path.resolve(import.meta.dirname, "../paperless");

function origins(environment = {}) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "paperless-csrf-"));
  try {
    const script = [
      'hostname() { test "${TEST_HOSTNAME_FAIL:-0}" = 0 || return 1; printf %s "${TEST_IPS:-}"; }',
      'busctl() { test "${TEST_AVAHI_FAIL:-0}" = 0 || return 1; printf %s "${TEST_AVAHI:-}"; }',
      "chown() { :; }",
      "stat() { printf 1000:1000; }",
      'source "$TEST_EXPORTS"',
      'printf %s "${APP_PAPERLESS_CSRF_TRUSTED_ORIGINS:-}"',
    ].join("\n");
    return execFileSync("bash", ["-euo", "pipefail", "-c", script], {
      encoding: "utf8",
      env: {
        PATH: process.env.PATH,
        UMBREL_ROOT: root,
        TEST_EXPORTS: process.env.PAPERLESS_TEST_EXPORTS || path.join(app, "exports.sh"),
        DEVICE_DOMAIN_NAME: "umbrel.local",
        DEVICE_HOSTNAME: "umbrel",
        ...environment,
      },
    }).split(",").filter(Boolean);
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
}

test("Paperless receives the generated origins through Compose", () => {
  const compose = YAML.parse(fs.readFileSync(path.join(app, "docker-compose.yml"), "utf8"));
  assert.equal(compose.services.webserver.environment.PAPERLESS_CSRF_TRUSTED_ORIGINS,
    "${APP_PAPERLESS_CSRF_TRUSTED_ORIGINS}");
});

test("HTTPS login trusts the device names, IPv4 and bracketed IPv6 on its app port", () => {
  assert.deepEqual(origins({ TEST_IPS: "192.168.1.20 2001:db8::20" }), [
    "https://umbrel.local:2349",
    "https://umbrel:2349",
    "https://192.168.1.20:2349",
    "https://[2001:db8::20]:2349",
  ]);
});

test("Avahi hostname collisions use the advertised name without its trailing dot", () => {
  assert.ok(origins({ TEST_AVAHI: 's "umbrel-2.local."' }).includes("https://umbrel-2.local:2349"));
});

test("optional discovery failures do not stop exports under strict shell options", () => {
  assert.deepEqual(origins({ TEST_HOSTNAME_FAIL: "1", TEST_AVAHI_FAIL: "1" }), [
    "https://umbrel.local:2349", "https://umbrel:2349",
  ]);
  assert.deepEqual(origins({ DEVICE_DOMAIN_NAME: "", DEVICE_HOSTNAME: "" }), []);
});

test("invalid hosts and spoofed forwarding headers cannot add trusted origins", () => {
  assert.deepEqual(origins({
    DEVICE_DOMAIN_NAME: "umbrel.local,https://evil.example",
    DEVICE_HOSTNAME: "*.example",
    TEST_AVAHI: 's "evil.example/path"',
    TEST_IPS: "192.168.1.20 evil.example/path",
    HTTP_X_FORWARDED_HOST: "evil.example",
    HTTP_X_FORWARDED_PROTO: "https",
  }), ["https://192.168.1.20:2349"]);
});
