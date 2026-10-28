"""Exercise actual bootstrap, upstream tools and HTTP isolation against a fake API.

Requires Python >=3.13, uv on PATH, and network access for first startup.
No real health data or credentials are used. This is not an Umbrel install test.
"""

from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request

PACKAGE = Path(__file__).resolve().parents[1]
REVOKED = set()


class FakeAPI(BaseHTTPRequestHandler):
    def do_GET(self):
        key = self.headers.get("X-Open-Wearables-API-Key")
        if key not in ("ow_test_a", "ow_test_b") or key in REVOKED:
            self.send_response(401)
            self.end_headers()
            return
        if not self.path.startswith("/api/v1/users"):
            self.send_response(404)
            self.end_headers()
            return
        time.sleep(0.01)
        body = json.dumps({"items": [{"id": key, "first_name": key}], "total": 1}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def request(method="tools/list", key="ow_test_a", params=None, **extra):
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    if key is not None:
        headers["Authorization"] = "Bearer " + key
    headers.update(extra)
    data = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}).encode()
    req = urllib.request.Request("http://127.0.0.1:3495/mcp", data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            body = response.read().decode()
            if response.headers.get("Content-Type", "").startswith("text/event-stream"):
                body = next(line[6:] for line in body.splitlines() if line.startswith("data: "))
            return response.status, json.loads(body)
    except urllib.error.HTTPError as error:
        with error:
            return error.code, error.read().decode()


class MCPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api = ThreadingHTTPServer(("127.0.0.1", 0), FakeAPI)
        threading.Thread(target=cls.api.serve_forever, daemon=True).start()
        cls.runtime = tempfile.TemporaryDirectory(prefix="ow-mcp-test-")
        cls.log = tempfile.TemporaryFile(mode="w+")
        env = os.environ.copy()
        env.update({
            "OPEN_WEARABLES_API_URL": "http://127.0.0.1:" + str(cls.api.server_port),
            "MCP_RUNTIME_DIR": cls.runtime.name,
            "MCP_HTTP_ADAPTER": str(PACKAGE / "mcp-http.py.template"),
            "MCP_ALLOWED_HOSTS": "127.0.0.1:3495,localhost:3495",
        })
        cls.process = subprocess.Popen(
            [os.sys.executable, str(PACKAGE / "mcp-bootstrap.py.template")],
            env=env, stdout=cls.log, stderr=cls.log,
        )
        try:
            for _ in range(240):
                if cls.process.poll() is not None:
                    raise RuntimeError("MCP startup exited")
                try:
                    if request(key=None)[0] == 401:
                        return
                except OSError:
                    pass
                time.sleep(1)
            raise TimeoutError("MCP startup timed out")
        except BaseException:
            cls.log.seek(0)
            print(cls.log.read())
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        cls.process.terminate()
        try:
            cls.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            cls.process.kill()
            cls.process.wait()
        cls.api.shutdown()
        cls.api.server_close()
        cls.log.close()
        cls.runtime.cleanup()

    def test_authentication_and_browser_boundaries(self):
        self.assertEqual(request(key=None)[0], 401)
        self.assertEqual(request(key="invalid")[0], 401)
        self.assertEqual(request(Host="attacker.example:3495")[0], 403)
        self.assertEqual(request(Origin="http://localhost:3495")[0], 403)

    def test_initialize_and_upstream_tools(self):
        status, result = request("initialize", params={
            "protocolVersion": "2025-03-26", "capabilities": {},
            "clientInfo": {"name": "umbrel-package-test", "version": "1"},
        })
        self.assertEqual(status, 200)
        self.assertIn("serverInfo", result["result"])
        status, result = request()
        self.assertEqual(status, 200)
        names = {tool["name"] for tool in result["result"]["tools"]}
        self.assertTrue({"get_users", "get_activity_summary", "get_sleep_summary", "get_workout_events",
                         "get_timeseries", "get_menstrual_cycles"}.issubset(names))

    def test_concurrent_credentials_and_revocation(self):
        def call(key):
            status, result = request("tools/call", key=key, params={"name": "get_users", "arguments": {}})
            self.assertEqual(status, 200)
            payload = result["result"]
            self.assertFalse(payload.get("isError"), payload)
            data = json.loads(payload["content"][0]["text"])
            self.assertEqual(data["users"][0]["id"], key)

        with ThreadPoolExecutor(max_workers=8) as executor:
            list(executor.map(call, ["ow_test_a", "ow_test_b"] * 8))
        REVOKED.add("ow_test_a")
        try:
            self.assertEqual(request(key="ow_test_a")[0], 401)
            call("ow_test_b")
        finally:
            REVOKED.clear()


if __name__ == "__main__":
    unittest.main(verbosity=2)
